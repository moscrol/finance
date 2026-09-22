"""A parseable tool call / FINAL_JSON is not proof that generation completed."""
from __future__ import annotations

import io
import json
from unittest.mock import patch

import pytest

from intelligence.runtime.agent_episode import ContinuousAgentEpisode
from intelligence.runtime.glm_agent_runtime import GLMModelClient, _turn_from_message
from intelligence.services import llm_refine
from intelligence.services.agent_runtime import ModelToolCall, ModelTurn
from intelligence.tests.conformance.fixtures import (
    AUTHORIZED_TOOL, ScenarioProbe, completed_finish, make_context, make_frame, make_registry,
)
from intelligence.tests.test_glm_agent_runtime import _provider
from intelligence.tests.test_llm_refine_tool_stream import _FakeResponse, sse


def envelope(reason):
    return {
        "content": "unfinished", "_finish_reason": reason,
        "_usage": {"prompt_tokens": 10, "completion_tokens": 20},
        "tool_calls": [{"id": "c1", "type": "function", "function": {
            "name": AUTHORIZED_TOOL, "arguments": '{"query":"市场宽度"}',
        }}],
    }


@pytest.mark.parametrize("reason", ["length", "max_tokens", "content_filter"])
@pytest.mark.parametrize("providers", [None, (_provider("a"), _provider("b"))])
def test_incomplete_envelope_is_not_executed_or_silently_retried(reason, providers):
    calls = []
    def complete(**_kwargs):
        calls.append(1)
        return envelope(reason), _provider("a"), ""
    turn = GLMModelClient(providers=providers, complete_fn=complete).complete(messages=[], tools=[], timeout=5)
    assert turn.error
    assert turn.tool_calls == ()
    assert turn.finish_reason == reason
    assert turn.to_dict()["finish_reason"] == reason
    assert turn.input_tokens == 10 and turn.output_tokens == 20
    assert turn.provider_attempts == 1
    assert len(calls) == 1
    assert turn._provider_trace[-1]["status"] == "failed"


@pytest.mark.parametrize("has_tools", [False, True])
def test_direct_model_turn_cannot_bypass_completion_boundary(has_tools):
    probe = ScenarioProbe()
    turn = ModelTurn(
        json.dumps(completed_finish()),
        (ModelToolCall("c1", AUTHORIZED_TOOL, {"query": "市场宽度"}),) if has_tools else (),
        finish_reason="length",
    )
    class Model:
        def complete(self, **_kwargs):
            return turn
    frame = make_frame()
    outcome = ContinuousAgentEpisode(Model()).run(
        task_frame=frame, context=make_context(frame), registry=make_registry(probe),
    )
    assert outcome.status != "completed"
    assert outcome.usage.tool_calls == 0
    assert outcome.usage.llm_calls == 1
    assert not outcome.draft
    events = [e for e in outcome.events if e.kind == "model_turn"]
    assert events[0].payload["finish_reason"] == "length"


@pytest.mark.parametrize("reason", ["stop", "tool_calls", None])
def test_complete_and_legacy_envelopes_keep_calls(reason):
    turn, error = _turn_from_message(envelope(reason), "fake", 1)
    assert not error and not turn.error
    assert len(turn.tool_calls) == 1
    assert turn.finish_reason == reason


@pytest.mark.parametrize("stream", [False, True])
def test_transport_preserves_truncation_reason(stream):
    choice = {"message": {"content": "ok"}, "finish_reason": "length"}
    response = (_FakeResponse(sse({"choices": [{"delta": {"content": "ok"}, "finish_reason": "length"}]}))
                if stream else io.BytesIO(json.dumps({"choices": [choice]}).encode()))
    with patch.object(llm_refine.urllib.request, "urlopen", return_value=response):
        if stream:
            result = llm_refine._post_chat_message_stream(
                _provider("a"), [], 5, 0, [], "auto", True, lambda _: None,
            )
        else:
            result = llm_refine._post_chat_message(_provider("a"), [], 5)
    assert result["_finish_reason"] == "length"


def test_truncated_finalizer_cannot_publish_parseable_finish():
    from dataclasses import replace
    from intelligence.tests.test_agent_episode import (
        ScriptedModel, _frame, _context, _tool_turn, _finish_turn,
        _market_registry, _successful_runner,
    )

    frame = _frame()
    model = ScriptedModel([
        _tool_turn("市场"), ModelTurn("", (), error="provider unavailable"),
        replace(_finish_turn(), finish_reason="max_tokens", input_tokens=11, output_tokens=12),
    ])
    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame, context=_context(frame, max_steps=1),
        registry=_market_registry(_successful_runner),
    )
    assert outcome.status != "completed" and not outcome.draft
    assert len(model.calls) == 3
    assert model.calls[-1]["tools"] == []
    assert outcome.usage.input_tokens == 11 and outcome.usage.output_tokens == 12
    last_model = [e for e in outcome.events if e.kind == "model_turn"][-1]
    assert last_model.payload["error"] == "incomplete_model_response:max_tokens"
