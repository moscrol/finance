#!/usr/bin/env python3
"""对一次留证跑批的答案做口径越界检查（只读，不连库、不调模型）。

输入是冻结下来的 run 目录（`run.json` + `continuous-episode.json` +
`answer.md`），证据边界全部从 Episode 事件里解析：证据日期、是否取过交易日历、
是否取过资金流、板块比较了几个。规则实现在
`intelligence/services/answer_claim_scope.py`。

用途是把"内容口径"验收变成可复跑的判据：同一个 run 目录，谁跑都是同一份结论。
**它只认四种已知形状**——干净不等于答案正确，命中也要人读原句确认。归属全集
这类库内事实本脚本不查库，用 `--scope-total` 显式传入并在交接里写明来源。

    python3 scripts/check_answer_claims.py <run 目录> [--scope-total N] [--json 输出]

命中退出码 1，干净 0，输入不完整或**证据上下文降级** 2。

退 2 那条是 2026-09-22 审查补的：原来 `--scope-total` 给了、但 episode 里解
不出比较范围数时，范围规则会静默且**退 0**——取数形状一变判据就惄惄变
绿。判据不可靠时宁可报错，不能冒充干净。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from intelligence.services.answer_claim_scope import (  # noqa: E402
    FUND_FLOW_METRICS,
    ClaimEvidenceContext,
    review_answer_claims,
    summarize_issues,
)

_SECTOR_FIELDS = {"sector_code", "sector_ts_code", "sector_name"}


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _tool_requests(episode: dict[str, Any]) -> list[dict[str, Any]]:
    events = episode.get("outcome", {}).get("events", [])
    return [
        event.get("payload", {})
        for event in events
        if isinstance(event, dict) and event.get("kind") == "tool_request"
    ]


def _sector_codes(requests: list[dict[str, Any]]) -> set[str]:
    codes: set[str] = set()
    for request in requests:
        arguments = request.get("arguments") or {}
        for condition in arguments.get("filters") or []:
            if not isinstance(condition, dict):
                continue
            if condition.get("field") not in _SECTOR_FIELDS:
                continue
            value = condition.get("value")
            if isinstance(value, list):
                codes.update(str(item) for item in value)
            elif value is not None:
                codes.add(str(value))
    return codes


def _fund_flow_metrics(requests: list[dict[str, Any]]) -> set[str]:
    """资金方向证据 = 请求里真的要了资金流**指标**。

    不再对整份 payload 做子串匹配：kb_search 的检索词、工具描述里随便出现
    「资金流」三个字，都会把证据判成取过（同日审查探针实测）。
    """

    seen: set[str] = set()
    for request in requests:
        arguments = request.get("arguments") or {}
        for metric in arguments.get("metrics") or []:
            if str(metric) in FUND_FLOW_METRICS:
                seen.add(str(metric))
    return seen


def build_context(
    run: dict[str, Any],
    episode: dict[str, Any],
    scope_total: int | None,
    calendar_source: str | None = None,
) -> tuple[ClaimEvidenceContext, dict[str, Any]]:
    """解出证据上下文，并把「怎么解出来的」一并返回供人核。"""

    requests = _tool_requests(episode)
    evidence = episode.get("outcome", {}).get("evidence", []) or []
    dates = sorted(
        {
            str(item.get("source_date"))
            for item in evidence
            if isinstance(item, dict) and item.get("source_date")
        }
    )
    codes = _sector_codes(requests)
    flow_metrics = _fund_flow_metrics(requests)
    context = ClaimEvidenceContext(
        question=str(run.get("question") or ""),
        evidence_dates=tuple(dates),
        calendar_evidence=bool(calendar_source),
        compared_scope_count=len(codes) or None,
        known_scope_total=scope_total,
        fund_flow_evidence=bool(flow_metrics),
    )
    degraded: list[str] = []
    if scope_total is not None and context.compared_scope_count is None:
        degraded.append(
            "给了 --scope-total 却没从 episode 解出比较范围数（本轮只认"
            f"filters 里的 {sorted(_SECTOR_FIELDS)}）：范围规则本次没有真在跑"
        )
    diagnostics = {
        "tool_request_count": len(requests),
        "tool_names": sorted({str(r.get("name")) for r in requests if r.get("name")}),
        "sector_codes_seen": sorted(codes),
        "fund_flow_metrics_seen": sorted(flow_metrics),
        "calendar_evidence_source": calendar_source
        or "未声明（finance_query 无交易日历 dataset，episode 推不出）",
        "degraded": degraded,
    }
    return context, diagnostics


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path, help="冻结的 run 目录")
    parser.add_argument(
        "--scope-total",
        type=int,
        default=None,
        help="归属全集个数（如当日板块归属数），本脚本不查库，需显式给出来源",
    )
    parser.add_argument(
        "--calendar-evidence-source",
        default=None,
        help=(
            "本次确实取过交易日历时，写明来源（如“trading_days.py 人工核对”）。"
            "工具面没有日历 dataset，所以这条豁免只能人工声明，不从 episode 猜"
        ),
    )
    parser.add_argument("--json", type=Path, default=None, help="收据写到该路径")
    args = parser.parse_args()

    run_path = args.run_dir / "run.json"
    episode_path = args.run_dir / "continuous-episode.json"
    answer_path = args.run_dir / "answer.md"
    missing = [str(p) for p in (run_path, episode_path, answer_path) if not p.is_file()]
    if missing:
        print("缺少留证文件：" + "、".join(missing), file=sys.stderr)
        return 2

    run = _read_json(run_path)
    episode = _read_json(episode_path)
    context, diagnostics = build_context(
        run, episode, args.scope_total, args.calendar_evidence_source
    )
    report = review_answer_claims(answer_path.read_text(encoding="utf-8"), context)

    receipt = report.to_dict()
    receipt["run_id"] = run.get("run_id") or args.run_dir.name
    receipt["scope_total_source"] = (
        "命令行显式传入" if args.scope_total is not None else "未提供"
    )
    receipt["context_diagnostics"] = diagnostics
    if args.json:
        args.json.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    for line in summarize_issues(report.issues):
        print(f"  ⚠️ {line}", file=sys.stderr)
    if diagnostics["degraded"]:
        for line in diagnostics["degraded"]:
            print(f"  ⛔ 证据上下文降级：{line}", file=sys.stderr)
        return 2
    return 1 if report.issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
