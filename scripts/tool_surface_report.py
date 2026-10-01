#!/usr/bin/env python3
"""量「每轮发给模型的工具说明」有多大：逐工具字符数，按题型。

工具说明就是给模型看的界面。弱模型对它的体量最敏感，强模型也要为它付每轮的
上下文与延迟。2026-10-01 首测：8 个工具 35,939 字符，finance_query 一个占 89%。

用法：
  python3 scripts/tool_surface_report.py                      # 默认几种题型
  python3 scripts/tool_surface_report.py --question-type market_watch --json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile

REPO = Path(__file__).resolve().parents[1]
# 直接 `python3 scripts/xxx.py` 运行时 sys.path[0] 是 scripts/，intelligence 包不可见。
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

DEFAULT_TYPES = ("market_watch", "stock_deep_dive", "theme_analysis", "quick_fact", "market_forecast")


def _frame(question_type: str):
    from intelligence.services.task_frame import TaskFrame

    return TaskFrame(
        raw_question="今天两市成交额多少",
        user_goal="看盘",
        question_type=question_type,
        subject="A股",
        subject_kind="market_pattern",
        market_scope="A股",
        timeframe="今天",
        required_outputs=("direct_assessment",),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="market_data",
        confidence=0.9,
    )


def measure(question_type: str) -> dict[str, object]:
    """按生产默认授权装配一次注册表，返回逐工具的字符数。不读库、不联网。"""

    from intelligence.services.episode_factory import build_episode_context
    from intelligence.services.episode_tools import build_episode_registry

    frame = _frame(question_type)
    context = build_episode_context(
        frame, task_id=f"tool-surface-{question_type}-{id(frame)}", capabilities=None, timeout=60.0
    )
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        registry = build_episode_registry(frame, context, knowledge_wiki=root / "wiki", finance_root=root)
        definitions = registry.tool_definitions(context.contract.allowed_capabilities)
    tools = []
    for definition in definitions:
        function = definition["function"]
        tools.append({
            "name": function["name"],
            "total_chars": len(json.dumps(definition, ensure_ascii=False)),
            "description_chars": len(function["description"]),
            "parameters_chars": len(json.dumps(function["parameters"], ensure_ascii=False)),
        })
    tools.sort(key=lambda row: -int(row["total_chars"]))
    return {
        "question_type": question_type,
        "tools": tools,
        "tool_count": len(tools),
        "total_chars": sum(int(row["total_chars"]) for row in tools),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--question-type", action="append", dest="types")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    reports = [measure(qt) for qt in (args.types or DEFAULT_TYPES)]
    if args.json:
        print(json.dumps(reports, ensure_ascii=False, indent=2))
        return 0
    for report in reports:
        print(f"== {report['question_type']}: {report['tool_count']} 个工具，{report['total_chars']} 字符")
        for row in report["tools"]:
            print(f"  {row['total_chars']:>6}  {row['name']:<24} 说明 {row['description_chars']:>5}  参数 {row['parameters_chars']:>5}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
