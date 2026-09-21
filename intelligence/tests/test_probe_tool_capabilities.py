"""``probe_tool`` 的授权面必须是运行时能力，不是工具名。

2026-09-21 冒烟实测：``ALL_TOOLS = tuple(_DEFAULT_TOOL_METADATA)`` 把三个历史工具
（``history_query`` / ``read_history_result`` / ``save_history_research``，它们由
``finance_query`` 授权 + ``history_intent`` 条件装配）当能力传给
``build_episode_context`` → ``ValueError: unknown runtime capability``，试验场任何
工具都构造失败。``test_probe_tool_arguments`` 只钉参数保真度，抓不到这一层。
"""
from __future__ import annotations

from intelligence.services.episode_factory import build_episode_context
from intelligence.services.research_contract import release_root_budget
from intelligence.services.research_tool_registry import DEFAULT_RESEARCH_CAPABILITIES
from intelligence.services.task_frame import TaskFrame
from scripts import probe_tool

_HISTORY_TOOLS = frozenset({"history_query", "read_history_result", "save_history_research"})


def _frame() -> TaskFrame:
    return TaskFrame(
        raw_question="本周光伏板块为什么上涨",
        user_goal="probe",
        question_type="market_overview",
        subject=None,
        subject_kind="market_pattern",
        market_scope="a_share",
        timeframe=None,
        required_outputs=("direct_assessment",),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="standard",
        confidence=0.8,
    )


def test_probe_capabilities_are_a_subset_of_runtime_capabilities() -> None:
    assert set(probe_tool.PROBE_CAPABILITIES) <= set(DEFAULT_RESEARCH_CAPABILITIES)
    assert set(probe_tool.ALL_TOOLS) - set(probe_tool.PROBE_CAPABILITIES) == _HISTORY_TOOLS


def test_probe_context_builds_with_the_probe_capability_face() -> None:
    task_id = "probe-tool-capabilities-test"
    try:
        context = build_episode_context(
            _frame(),
            task_id=task_id,
            capabilities=probe_tool.PROBE_CAPABILITIES,
            tier="deep",
            timeout=30.0,
            today=None,
            latest_data_date=None,
        )
    finally:
        release_root_budget(task_id)
    assert set(context.contract.allowed_capabilities) <= set(DEFAULT_RESEARCH_CAPABILITIES)
