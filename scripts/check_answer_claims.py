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
    review_answer_claims,
    summarize_issues,
)

from intelligence.services.claim_scope_context import build_context  # noqa: E402


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


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
