"""Model-visible threshold instructions must respect the signed grounding mode.

These tests verify delivery/consistency, not that live predictions are correct.
Numeric/semantic validation and the optional-forward-slot gates remain unchanged.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from intelligence.runtime.agent_episode import ContinuousAgentEpisode
from intelligence.services.research_contract import RequiredOutput
from intelligence.services.research_harness import FinanceResearchHarness
from intelligence.tests.test_agent_episode import (
    ScriptedModel, _context, _finish_turn, _frame, _market_registry,
    _successful_runner, _tool_turn,
)


@pytest.mark.parametrize("mode,required", [
    ("evidence", True), ("model_reasoning", True), ("model_reasoning", False),
])
def test_initial_and_final_messages_preserve_conditional_threshold_authority(mode, required):
    frame = _frame()
    context = _context(frame, max_steps=1)
    context = replace(context, contract=replace(context.contract, required_outputs=(
        *context.contract.required_outputs,
        RequiredOutput(output_id="continuation_conditions", description="持续条件",
                       evidence_types=(), required=required, grounding_mode=mode),
    )))
    contract_before = context.contract.to_dict()
    model = ScriptedModel([_tool_turn("A股 最新行情"), _finish_turn()])
    ContinuousAgentEpisode(model).run(task_frame=frame, context=context,
                                    registry=_market_registry(_successful_runner))
    system = model.calls[0]["messages"][0]["content"]
    reminder = model.calls[1]["messages"][-1]["content"]
    for text in (system, reminder):
        for rule in (
            "仅当本轮契约将对应输出的 grounding_mode 设为 model_reasoning",
            "主观监测线", "选择理由与不确定性", "已观察事实仍须绑定直接证据",
            "否则使用已绑定事实支持的条件或相对变化", "不自拟精确阈值",
            "不得把精确数值阈值写成历史事实或已校准规律",
        ):
            assert rule in text
        assert "不得新增证据中没有的数值阈值" not in text
    assert context.contract.to_dict() == contract_before  # prose does not grant a new mode
    assert "每个保留的精确数字事实" in reminder


def test_threshold_rule_has_one_owner_for_initial_and_final_messages():
    from intelligence.services.episode_protocol import (
        THRESHOLD_GROUNDING_RULE, build_episode_instructions,
    )

    frame = _frame()
    system = build_episode_instructions(frame, _context(frame), _market_registry(_successful_runner))
    closing = FinanceResearchHarness().steering_message("begin_finalization", detail="budget")
    assert THRESHOLD_GROUNDING_RULE in system
    assert THRESHOLD_GROUNDING_RULE in closing
