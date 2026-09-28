"""Rejected finishes can recover in-place while the original research window is open."""

import pytest

from intelligence.runtime.agent_episode import ContinuousAgentEpisode, ModelTurn
from intelligence.runtime.harness_reference_loop import HarnessReferenceLoop
from intelligence.tests.test_answer_capability_prompt import _ToolCapturingModel
from intelligence.tests.test_research_harness import (
    _context, _evidence, _finish_content, _frame, _registry, _tool_turn,
)


@pytest.mark.parametrize("loop", [ContinuousAgentEpisode, HarnessReferenceLoop])
def test_format_then_evidence_error_can_obtain_evidence_in_same_episode(loop):
    frame = _frame()
    context = _context(frame, max_steps=5)
    deadline = context.deadline
    model = _ToolCapturingModel([
        ModelTurn("不是合法终稿", (), "scripted", ""),
        ModelTurn(_finish_content(hashes=("E2",)), (), "scripted", ""),
        _tool_turn(),
        ModelTurn(_finish_content(hashes=("E1",)), (), "scripted", ""),
    ])
    outcome = loop(model).run(task_frame=frame, context=context,
                              registry=_registry((_evidence("evidence-1"),)))
    assert outcome.status == "completed"
    assert model.calls == 4
    assert outcome.usage.tool_calls == 1
    assert model.seen_tools[2]  # Evidence correction still offers authorized tools.
    repair = str(model.seen_messages[2][-1]["content"])
    assert "证据" in repair and "授权工具" in repair
    assert context.deadline is deadline
    assert model.seen_messages[-1][:2] == model.seen_messages[0][:2]
    assert any(item["role"] == "tool" for item in model.seen_messages[-1])
    codes = [e.payload["code"] for e in outcome.events if e.kind == "invalid_action"]
    assert codes == ["not_json_object", "unknown_evidence_ref"]


@pytest.mark.parametrize("loop", [ContinuousAgentEpisode, HarnessReferenceLoop])
@pytest.mark.parametrize("content", ["坏格式", _finish_content(hashes=("E2",))])
def test_same_repair_direction_is_bounded(loop, content):
    model = _ToolCapturingModel([ModelTurn(content, (), "scripted", "")] * 3)
    frame = _frame()
    outcome = loop(model).run(task_frame=frame, context=_context(frame, max_steps=5),
                              registry=_registry(()))
    assert outcome.status != "completed"
    assert model.calls == 2
    assert outcome.usage.tool_calls == 0


@pytest.mark.parametrize("loop", [ContinuousAgentEpisode, HarnessReferenceLoop])
def test_integrity_error_never_gets_a_repair_opportunity(loop):
    model = _ToolCapturingModel([
        ModelTurn(_finish_content(hashes=("f" * 64,)), (), "scripted", ""),
    ])
    frame = _frame()
    outcome = loop(model).run(task_frame=frame, context=_context(frame), registry=_registry(()))
    assert outcome.status != "completed"
    assert model.calls == 1
    assert any(e.kind == "invalid_action" and e.payload["code"] == "forged_hash"
               for e in outcome.events)


@pytest.mark.parametrize("loop", [ContinuousAgentEpisode, HarnessReferenceLoop])
def test_closed_research_does_not_reopen_for_evidence_error(loop):
    model = _ToolCapturingModel([
        _tool_turn(),
        ModelTurn(_finish_content(hashes=("E2",)), (), "scripted", ""),
        ModelTurn(_finish_content(status="partial", hashes=("E1",), gap="尚有事实待核实"),
                  (), "scripted", ""),
    ])
    frame = _frame()
    outcome = loop(model).run(task_frame=frame, context=_context(frame, max_steps=1),
                              registry=_registry((_evidence("evidence-1"),)))
    assert outcome.status != "completed"
    assert model.calls == (3 if loop is ContinuousAgentEpisode else 2)
    assert all(tools == [] for tools in model.seen_tools[1:])
    assert outcome.usage.tool_calls == 1


def test_repair_does_not_reset_production_model_round_budget():
    model = _ToolCapturingModel([
        ModelTurn("坏格式", (), "scripted", ""),
        ModelTurn(_finish_content(hashes=("E2",)), (), "scripted", ""),
    ])
    frame = _frame()
    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame, context=_context(frame, max_steps=1), registry=_registry(()),
    )
    assert model.calls == 2
    assert model.seen_tools[1] == []
    assert outcome.status != "completed"
    assert outcome.usage.tool_calls == 0


@pytest.mark.parametrize("loop", [ContinuousAgentEpisode, HarnessReferenceLoop])
def test_cancelled_repair_cannot_dispatch_another_model_or_tool(loop):
    model = _ToolCapturingModel([ModelTurn("坏格式", (), "scripted", "")])
    frame = _frame()
    outcome = loop(model, is_cancelled=lambda: model.calls > 0).run(
        task_frame=frame, context=_context(frame), registry=_registry(()),
    )
    assert outcome.status != "completed"
    assert outcome.stop_reason == "cancelled"
    assert model.calls == 1
    assert outcome.usage.tool_calls == 0
