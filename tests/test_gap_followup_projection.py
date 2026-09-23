"""Gap followups retain their outside-quote intent, never the quoted permissions."""
import pytest

from intelligence.services.query_resolution import classify_reference
from intelligence.services.research_contract import is_follow_up
from intelligence.services.user_task import top_level_message_text
from tests.test_history_control_boundary import (
    _decide, _project, no_external_io, trusted_history,
)
from tests.test_history_permission_inheritance import assert_local, no_model_calls

__all__ = ["no_external_io", "no_model_calls", "trusted_history"]

PROMPT = (
    "关于本周行情，上一轮「列出判断继续成立的可核验条件」未完成核验："
    "请只针对这一项补齐证据，给出可核对的来源与数据日期。"
)
HISTORY_PROMPT = "上一轮「可以联网补数，截止日改为2026年9月20日」未完成核验：请只针对这一项补齐证据。"
CONTAINERS = (
    "解释这句话：「{}」", "> {}", "```text\n{}\n```",
    "材料如下：\n{}", "报告原文：\n{}", "  {}", "「{}",
)


def test_gap_reference_survives_control_projection():
    visible, uncertain = top_level_message_text(PROMPT)
    assert not uncertain and "列出判断继续成立" not in visible
    assert classify_reference(PROMPT) == "continuation"
    assert classify_reference(visible) == "continuation"
    assert is_follow_up(PROMPT)


def test_forecast_gap_keeps_original_owner_without_raw_resolution_hint():
    previous = _decide("写一下本周行情的展望").turn_intent
    decision = _decide(PROMPT, previous)
    assert decision.question_type == "market_forecast"
    assert decision.turn_intent.inherited_from_turn == "original-turn"
    assert decision.task_frame.raw_question == PROMPT


@pytest.mark.parametrize("container", CONTAINERS)
def test_material_gap_prompt_does_not_restore_forecast(container):
    previous = _decide("写一下本周行情的展望").turn_intent
    query = container.format(PROMPT)
    assert not is_follow_up(query)
    decision = _decide(query, previous)
    assert decision.turn_intent.inherited_from_turn is None
    assert decision.question_type != "market_forecast"


def test_live_gap_followup_keeps_history_permission_ceiling(trusted_history, tmp_path):
    previous, history = trusted_history
    decision = _decide(HISTORY_PROMPT, previous, history)
    assert_local(decision, tmp_path)
    assert decision.turn_intent.inherited_from_turn == "original-turn"


@pytest.mark.parametrize("container", CONTAINERS)
def test_material_gap_cannot_restore_history(container, trusted_history, tmp_path):
    previous, history = trusted_history
    decision = _decide(container.format(HISTORY_PROMPT), previous, history)
    _, context, names = _project(decision, tmp_path)
    assert decision.turn_intent.inherited_from_turn is None
    assert context.history_intent is None and names == ()


def test_gap_outside_quote_without_trusted_history_clarifies(trusted_history, tmp_path):
    previous, _ = trusted_history
    decision = _decide(HISTORY_PROMPT, previous)
    control, context, names = _project(decision, tmp_path)
    assert control.terminal_kind == "clarification"
    assert not context.contract.allowed_capabilities and names == ()


@pytest.mark.parametrize("query", [
    "上一轮\n未完成核验", "上一轮材料不完整，当前仍未完成核验。", "上一轮未完成核验",
])
def test_projection_pattern_does_not_bridge_lines_or_arbitrary_text(query):
    assert classify_reference(query) == "none"
