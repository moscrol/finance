"""盘面类槽位的契约描述必须携带「写出具体数值」的要求，且真的进契约。

背景（08-12 A 组冒烟，revision 5b7464be）：证据已绑定（3~15 条）仍真值 0/7，
12 条失败全在 fact 层——模型定性概括、省掉证据里的数字（draft 有 1000 字上限，
省数字是理性选择），而判卷按数字判。这是 #289「模型在看不见的评分表上被打分」
的引擎 A 版；修法同源：把要求写进模型看得见的契约（`_OUTPUT_DESCRIPTIONS`
→ `build_episode_input`），不碰指纹锁定的指令文本。

测试走 `build_episode_context`（可达性纪律：断言生效值，不断言配置表）。
"""
from __future__ import annotations

from intelligence.services.episode_factory import build_episode_context
from intelligence.services.task_frame import TaskFrame


def _frame(question_type: str, required_outputs: tuple[str, ...]) -> TaskFrame:
    return TaskFrame(
        raw_question="2026-07-23 今天市场怎么样",
        user_goal="复盘目标交易日市场",
        question_type=question_type,
        subject="A股市场",
        subject_kind="market_pattern",
        market_scope="A股",
        timeframe="2026-07-23",
        required_outputs=required_outputs,
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="dated_a_share_market",
        confidence=0.95,
    )


def _description(context, output_id: str) -> str:
    return next(
        item.description
        for item in context.contract.required_outputs
        if item.output_id == output_id
    )


def test_dated_review_slots_demand_concrete_numbers() -> None:
    context = build_episode_context(
        _frame(
            "dated_market_review",
            ("market_summary", "mainline_structure", "risk_signals"),
        ),
        task_id="fact-desc-test",
        capabilities=("market_data", "mainline_context"),
    )

    summary = _description(context, "market_summary")
    assert "具体数值" in summary
    assert "成交额" in summary and "涨停" in summary
    mainline = _description(context, "mainline_structure")
    assert "涨停家数" in mainline


def test_supporting_evidence_demands_verbatim_numbers() -> None:
    context = build_episode_context(
        _frame(
            "market_watch",
            ("direct_assessment", "supporting_evidence", "risk_signals"),
        ),
        task_id="fact-desc-test-2",
        capabilities=("market_data",),
    )

    supporting = _description(context, "supporting_evidence")
    assert "原样写进" in supporting
    assert "不得只作定性概括" in supporting


def test_non_market_slots_stay_unchanged() -> None:
    """通用槽位不背盘面数值要求——描述表是跨题型共享的。"""
    context = build_episode_context(
        _frame("market_watch", ("direct_assessment", "risk_signals")),
        task_id="fact-desc-test-3",
        capabilities=("market_data",),
    )

    assert _description(context, "direct_assessment") == "直接回答用户问题并说明判断强度"
    assert _description(context, "risk_signals") == "列出风险信号与观察条件"
