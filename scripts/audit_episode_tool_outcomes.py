#!/usr/bin/env python3
"""按**真实工具名**统计 episode 的工具成败与证据消费率。

防的失败形状（2026-08-14 实测踩到，且踩了不止一次）：

1. **按 ``capability`` 分组会把每个 agent 工具读成接近全灭。** agent 工具的
   trace 在成功/失败两条路上把工具名放进不同字段（成功 ``provider="agent:kb_search"``
   + ``capability="agent_loop"``；失败 ``capability="kb_search"``），于是
   ``group by capability`` 把所有成功扫进 ``agent_loop`` 桶。本脚本一律走
   ``provider_trace_tool_name()``，与运行时同一个归一化口径。
2. **数事件会漏掉整条分支路径。** 分支里执行的工具历史上不发 tool_* 事件
   （已由 branch_tool 事件补上，但旧收据里没有），所以工具口径以 ``traces``
   为准，不以事件为准。
3. **「检索到 N 条」不等于「用上了」。** 证据消费率 = 被 structural_verifier
   绑进 required outputs 的证据数 / 检索到的总数。2026-08-14 实测有 run 检索
   45 条、绑定 0 条——只看前一个数会得出「检索很健康」的反结论。

4. **「每轮给 40 个数据集」要拿调用证据说话**（2026-09-30 质检 P1「按路由收窄工具面」）。
   ``--by-dataset`` 把 ``finance_query`` 调用按题型（``contract.question_type``）×
   数据集（trace ``detail`` 里的 ``dataset=``，全仓只有 episode_tools 一个写法）拆开，
   并列出注册表 ``finance_query._DATASETS`` 里**在所扫 episode 中一次都没被调用**的
   数据集。「没被调用」只对所扫样本成立，不等于没用：样本覆盖不到的题型可能要它。

用法：
    python3 scripts/audit_episode_tool_outcomes.py <users_dir>/<user>/runs [...]
    python3 scripts/audit_episode_tool_outcomes.py ~/.local/share/finance-workbench/users/*/runs
    python3 scripts/audit_episode_tool_outcomes.py --by-dataset <runs 目录> [...]
    python3 scripts/audit_episode_tool_outcomes.py --json <runs 目录> [...]
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from intelligence.services.provider_observability import (  # noqa: E402
    ProviderTrace,
    provider_trace_tool_name,
)

_OK_STATUSES = {"success", "fallback_success"}
_DATASET_RE = re.compile(r"(?:^|;)\s*dataset=([A-Za-z0-9_\-]+)")


def _tool_name(raw: dict) -> str:
    try:
        return provider_trace_tool_name(ProviderTrace.from_dict(raw))
    except Exception:
        # 收据可能来自更早的 schema；退化成同样的口径，不要静默改口径。
        provider = str(raw.get("provider") or "")
        if provider.startswith("agent:"):
            return provider[len("agent:") :] or str(raw.get("capability") or "?")
        return str(raw.get("capability") or "?")


def _question_type(data: dict) -> str:
    for key in ("contract", "task_frame"):
        block = data.get(key)
        if isinstance(block, dict) and block.get("question_type"):
            return str(block["question_type"])
    return "?"


def _dataset(raw: dict) -> str:
    match = _DATASET_RE.search(str(raw.get("detail") or ""))
    return match.group(1) if match else "?"


def registered_datasets() -> list[str]:
    from intelligence.services.finance_query import _DATASETS

    return sorted(_DATASETS)


def never_called(report: dict, registry: list[str]) -> list[str]:
    used = {dataset for counts in report["by_route"].values() for dataset in counts}
    return [name for name in registry if name not in used]


def audit(run_dirs: list[Path]) -> dict:
    per_tool: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    by_route: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    dataset_status: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    route_runs: collections.Counter = collections.Counter()
    retrieved = bound = runs = 0
    for run_dir in run_dirs:
        episode = run_dir / "continuous-episode.json"
        if not episode.is_file():
            continue
        try:
            data = json.loads(episode.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        runs += 1
        route = _question_type(data)
        route_runs[route] += 1
        for raw in data.get("traces") or []:
            if isinstance(raw, dict):
                name = _tool_name(raw)
                per_tool[name][str(raw.get("status"))] += 1
                if name == "finance_query":
                    dataset = _dataset(raw)
                    by_route[route][dataset] += 1
                    dataset_status[dataset][str(raw.get("status"))] += 1
        retrieved += len((data.get("outcome") or {}).get("evidence") or ())
        completion = (data.get("structural_verifier") or {}).get("completion") or {}
        ids: set[str] = set()
        for output in completion.get("outputs") or []:
            ids |= set(output.get("evidence_ids") or ())
        bound += len(ids)
    return {
        "runs": runs,
        "per_tool": per_tool,
        "retrieved": retrieved,
        "bound": bound,
        "route_runs": route_runs,
        "by_route": by_route,
        "dataset_status": dataset_status,
    }


def _print_by_dataset(report: dict, registry: list[str]) -> None:
    print("\nfinance_query 按题型 × 数据集：")
    for route, count in report["route_runs"].most_common():
        datasets = report["by_route"].get(route) or collections.Counter()
        calls = sum(datasets.values())
        top = " · ".join(f"{name} {n}" for name, n in datasets.most_common(8)) or "（没调 finance_query）"
        print(f"  {route}（{count} 个 episode，调用 {calls} 次）：{top}")
    unused = never_called(report, registry)
    print(
        f"\n注册 {len(registry)} 个数据集：被调用过 {len(registry) - len(unused)} 个，"
        f"所扫 episode 里一次没调过 {len(unused)} 个"
    )
    if unused:
        print("  " + "、".join(unused))
    print("  （只对所扫样本成立：样本覆盖不到的题型可能要它，收窄前按题型核对）")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs_dirs", nargs="+", type=Path)
    parser.add_argument("--by-dataset", action="store_true", help="finance_query 按题型 × 数据集拆开，并列出没被调用的数据集")
    parser.add_argument("--json", action="store_true", help="机读输出（含按题型 × 数据集）")
    args = parser.parse_args(argv)

    run_dirs = [child for root in args.runs_dirs for child in sorted(root.glob("run_*"))]
    if not run_dirs:
        print("没有找到 run_* 目录", file=sys.stderr)
        return 2

    report = audit(run_dirs)
    if args.json:
        registry = registered_datasets()
        payload = {
            key: ({k: dict(v) for k, v in value.items()} if key in {"per_tool", "by_route", "dataset_status"} else value)
            for key, value in report.items()
        }
        payload["route_runs"] = dict(report["route_runs"])
        payload["registered_datasets"] = registry
        payload["never_called"] = never_called(report, registry)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    print(f"episode: {report['runs']} 个\n")
    print(f"{'工具':<20}{'调用':>6}{'成功':>6}{'成功率':>8}   状态分布")
    for tool, counts in sorted(report["per_tool"].items(), key=lambda kv: -sum(kv[1].values())):
        total = sum(counts.values())
        ok = sum(counts[status] for status in _OK_STATUSES)
        print(f"{tool:<20}{total:>6}{ok:>6}{ok / total * 100:>7.0f}%   {dict(counts)}")

    got, used = report["retrieved"], report["bound"]
    rate = f"{used / got * 100:.0f}%" if got else "—"
    print(f"\n证据：检索 {got} 条 → 绑进答案 {used} 条，消费率 {rate}")
    if args.by_dataset:
        _print_by_dataset(report, registered_datasets())
    return 0


if __name__ == "__main__":
    sys.exit(main())
