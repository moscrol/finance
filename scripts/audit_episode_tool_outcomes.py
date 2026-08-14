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

用法：
    python3 scripts/audit_episode_tool_outcomes.py <users_dir>/<user>/runs [...]
    python3 scripts/audit_episode_tool_outcomes.py ~/.local/share/finance-workbench/users/*/runs
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from intelligence.services.provider_observability import (  # noqa: E402
    ProviderTrace,
    provider_trace_tool_name,
)

_OK_STATUSES = {"success", "fallback_success"}


def _tool_name(raw: dict) -> str:
    try:
        return provider_trace_tool_name(ProviderTrace.from_dict(raw))
    except Exception:
        # 收据可能来自更早的 schema；退化成同样的口径，不要静默改口径。
        provider = str(raw.get("provider") or "")
        if provider.startswith("agent:"):
            return provider[len("agent:") :] or str(raw.get("capability") or "?")
        return str(raw.get("capability") or "?")


def audit(run_dirs: list[Path]) -> dict:
    per_tool: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
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
        for raw in data.get("traces") or []:
            if isinstance(raw, dict):
                per_tool[_tool_name(raw)][str(raw.get("status"))] += 1
        retrieved += len((data.get("outcome") or {}).get("evidence") or ())
        completion = (data.get("structural_verifier") or {}).get("completion") or {}
        ids: set[str] = set()
        for output in completion.get("outputs") or []:
            ids |= set(output.get("evidence_ids") or ())
        bound += len(ids)
    return {"runs": runs, "per_tool": per_tool, "retrieved": retrieved, "bound": bound}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs_dirs", nargs="+", type=Path)
    args = parser.parse_args()

    run_dirs = [child for root in args.runs_dirs for child in sorted(root.glob("run_*"))]
    if not run_dirs:
        print("没有找到 run_* 目录", file=sys.stderr)
        return 2

    report = audit(run_dirs)
    print(f"episode: {report['runs']} 个\n")
    print(f"{'工具':<20}{'调用':>6}{'成功':>6}{'成功率':>8}   状态分布")
    for tool, counts in sorted(report["per_tool"].items(), key=lambda kv: -sum(kv[1].values())):
        total = sum(counts.values())
        ok = sum(counts[status] for status in _OK_STATUSES)
        print(f"{tool:<20}{total:>6}{ok:>6}{ok / total * 100:>7.0f}%   {dict(counts)}")

    got, used = report["retrieved"], report["bound"]
    rate = f"{used / got * 100:.0f}%" if got else "—"
    print(f"\n证据：检索 {got} 条 → 绑进答案 {used} 条，消费率 {rate}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
