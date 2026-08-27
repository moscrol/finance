"""验证时点前瞻槽 + theme 前瞻词形入闸——「假设×可验证时点×推翻条件」补齐时点件。

Knevo 结论元素④（未验证变量+可验证时点 / verify_by=指标×时点）在本仓契约里
没有对应槽：前瞻三槽只有 情景/延续/失效。本文件钉两刀：
- B 刀：`verification_timepoints` 进 FORWARD_HYPOTHESIS_OUTPUT_IDS，登记面五处齐
  （集合真源 / 契约描述 / marker 词表 / 提示词文案 / 挂载行为）。
- A 刀：`_OUTLOOK_JUDGMENT_RE` 补「后续走势 / 后市」词形——有色题
  （theme_analysis「后续的走势」）此前不入闸，推翻条件/时点整组缺席
  （2026-08-25 生产契约冻结实测）。
"""

from __future__ import annotations

from uuid import uuid4

from intelligence.services.episode_factory import (
    _OUTPUT_DESCRIPTIONS,
    build_episode_context,
)
from intelligence.services.episode_protocol import _question_type_rules
from intelligence.services.research_contract import FORWARD_HYPOTHESIS_OUTPUT_IDS
from intelligence.services.task_fulfillment import (
    answer_has_output_marker,
    output_marker_is_checkable,
)
from intelligence.services.turn_controller import decide_turn

Q_YSJS = "用spt的视角，分析下有色金属板块后续的走势，以及板块内有机会的个股有哪些"
# general_finance_qa + 前瞻信号（你认为）：走 _with_forward_hypothesis_slots 挂载路径。
# 不能用「后市会怎么走」——那会路由进 market_forecast（原生前瞻题型，交集判据不挂）。
Q_MONDAY = "站在spt视角下，你认为周一科技和医药板块的走势会怎么样，需要观察哪些个股的反馈"


def _contract(query: str):
    decision = decide_turn(query)
    return build_episode_context(
        decision.task_frame,
        task_id=f"verify-timepoint-{uuid4().hex}",
        today="2026-08-25",
        latest_data_date="2026-08-24",
    )


# ---------- B 刀：verification_timepoints 槽 ----------


def test_verification_timepoints_is_a_forward_slot() -> None:
    assert "verification_timepoints" in FORWARD_HYPOTHESIS_OUTPUT_IDS


def test_verification_timepoints_registered_in_contract_layer() -> None:
    """描述缺席会让挂槽后的装配 fail-closed 炸整题（R-20260825-04 同形）。"""

    assert "verification_timepoints" in _OUTPUT_DESCRIPTIONS


def test_verification_timepoints_marker_is_checkable() -> None:
    """无 marker 的槽是瞎仪表：覆盖统计把「没法看」读成 0%（prior_recall 教训）。"""

    assert output_marker_is_checkable("verification_timepoints")
    assert answer_has_output_marker(
        "verification_timepoints", "验证时点：9 月中报披露前后回看订单兑现。"
    )
    assert not answer_has_output_marker("verification_timepoints", "市场偏强。")


def test_forward_signal_question_mounts_timepoint_slot() -> None:
    context = _contract(Q_MONDAY)
    outputs = {item.output_id: item for item in context.contract.required_outputs}
    item = outputs["verification_timepoints"]
    assert item.required is False
    assert item.grounding_mode == "model_reasoning"
    assert item.evidence_types == ()


def test_prompt_rule_mentions_timepoint() -> None:
    context = _contract(Q_MONDAY)
    decision = decide_turn(Q_MONDAY)
    rules = _question_type_rules(decision.task_frame, context)
    assert "verification_timepoints" in rules
    assert "验证时点" in rules


# ---------- A 刀：theme 前瞻词形入闸 ----------


def test_theme_trend_followup_question_mounts_forward_slots() -> None:
    """有色原题（theme_analysis「后续的走势」）必须挂上前瞻槽组。"""

    context = _contract(Q_YSJS)
    outputs = {item.output_id: item for item in context.contract.required_outputs}
    for output_id in ("invalidation_conditions", "verification_timepoints"):
        item = outputs[output_id]
        assert item.required is False
        assert item.grounding_mode == "model_reasoning"


def test_fact_question_does_not_mount_forward_slots() -> None:
    """对照：事实题不因词形放宽被误挂。"""

    context = _contract("2026-02-17 涨停家数多少")
    outputs = {item.output_id for item in context.contract.required_outputs}
    assert not FORWARD_HYPOTHESIS_OUTPUT_IDS & outputs
