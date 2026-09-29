"""Isolated candidate: JSON-object wire formatting is contract/phase scoped."""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest import mock

import pytest

from intelligence.services import llm_refine
from intelligence.runtime import agent_episode
from intelligence.runtime.episode_finalizer import EpisodeFinalizer

P = llm_refine.LLMProvider(
    name="zhipu", api_key="fake", base_url="https://invalid.example/v4", model="glm-5.3"
)


class Response:
    def __init__(self, stream: bool):
        self.stream = stream
        self.headers = {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps({"choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}]}).encode()

    def __iter__(self):
        return iter([
            b'data: {"choices":[{"delta":{"content":"{}"}}]}\n',
            b'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n',
            b'data: [DONE]\n',
        ])


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("flag,terminal,expected", [
    ("off", True, False), ("on", False, False), ("on", True, True),
])
def test_only_explicit_terminal_scope_changes_wire(monkeypatch, stream, flag, terminal, expected):
    monkeypatch.setenv("ASK_MATERIAL_JSON_MODE", flag)
    requests = []

    def open_response(request, **kwargs):
        requests.append(json.loads(request.data))
        return Response(stream)

    with (mock.patch.object(llm_refine, "_reserve_llm_call"),
          mock.patch.object(llm_refine, "_record_llm_call"),
          mock.patch.object(llm_refine, "_open_deadline_http_response", side_effect=open_response)):
        with llm_refine.material_json_output_scope(terminal):
            if stream:
                msg = llm_refine._post_chat_message_stream(
                    P, [{"role": "user", "content": "只写 JSON"}], 5, 0.0, [], "auto", True, lambda _: None
                )
            else:
                msg = llm_refine._post_chat_message(
                    P, [{"role": "user", "content": "只写 JSON"}], 5, 0.0, [], "auto", True
                )
        assert msg["content"] == "{}"
        assert len(requests) == 1
        assert (requests[0].get("response_format") == {"type": "json_object"}) is expected
        # No leaked ContextVar after a completed or failed model turn.
        assert llm_refine._MATERIAL_JSON_OUTPUT.get() is False


def test_material_format_is_frozen_contract_not_empty_tool_list(monkeypatch):
    context = SimpleNamespace(contract=object(), prior_evidence=None)
    monkeypatch.setattr(agent_episode, "claim_finish_format", lambda contract, prior_evidence: None)
    assert agent_episode._material_claims_finish(context) is False
    monkeypatch.setattr(agent_episode, "claim_finish_format", lambda contract, prior_evidence: {"format": "material_claims_v1"})
    assert agent_episode._material_claims_finish(context) is True


def test_recovery_scopes_validated_material_contract_only(monkeypatch):
    monkeypatch.setenv("ASK_MATERIAL_JSON_MODE", "on")
    captured = []

    class Model:
        def complete(self, **kwargs):
            captured.append(llm_refine._MATERIAL_JSON_OUTPUT.get())
            return kwargs

    obj = EpisodeFinalizer(Model())
    context = SimpleNamespace(contract=object(), prior_evidence=None, deadline=SimpleNamespace(synthesis_timeout=lambda _v: 5))
    monkeypatch.setattr("intelligence.runtime.episode_finalizer.claim_finish_format", lambda contract, prior_evidence: None)
    obj._complete(system_prompt="x", payload={}, context=context)
    monkeypatch.setattr("intelligence.runtime.episode_finalizer.claim_finish_format", lambda contract, prior_evidence: {"format": "material_claims_v1"})
    obj._complete(system_prompt="x", payload={}, context=context)
    assert captured == [False, True]
    assert llm_refine._MATERIAL_JSON_OUTPUT.get() is False


def test_zero_tool_first_planning_turn_and_time_gate_boundary(monkeypatch):
    monkeypatch.setattr(
        agent_episode, "claim_finish_format",
        lambda contract, prior_evidence: {"format": "material_claims_v1"},
    )
    empty_contract = SimpleNamespace(allowed_capabilities=[])
    tool_contract = SimpleNamespace(allowed_capabilities=["web_search"])
    zero = SimpleNamespace(contract=empty_contract, prior_evidence=None)
    capable = SimpleNamespace(contract=tool_contract, prior_evidence=None)
    assert agent_episode._material_json_wire(zero, tools=[], finalizing=False)
    assert not agent_episode._material_json_wire(capable, tools=[], finalizing=False)
    assert not agent_episode._material_json_wire(capable, tools=[{"type": "function"}], finalizing=False)
    assert agent_episode._material_json_wire(capable, tools=[], finalizing=True)
    monkeypatch.setattr(agent_episode, "claim_finish_format", lambda contract, prior_evidence: None)
    assert not agent_episode._material_json_wire(zero, tools=[], finalizing=True)


def test_real_episode_first_no_tools_planning_turn_enables_json_scope(monkeypatch):
    from intelligence.runtime.agent_episode import ContinuousAgentEpisode
    from intelligence.services.agent_runtime import ModelTurn
    from intelligence.services.research_tool_registry import ResearchToolRegistry
    from intelligence.tests.test_e2_material_grounding import setup
    from intelligence.tests.test_e2_material_claim_rendering import claim_finish

    monkeypatch.setenv("ASK_MATERIAL_JSON_MODE", "on")
    frame, context = setup()
    assert context.contract.allowed_capabilities == ()
    seen = []

    class Writer:
        def complete(self, *, messages, tools, timeout):
            seen.append((bool(tools), llm_refine._MATERIAL_JSON_OUTPUT.get()))
            return ModelTurn(json.dumps(claim_finish(context), ensure_ascii=False), (), "offline", "")

    result = ContinuousAgentEpisode(Writer()).run(
        task_frame=frame, context=context, registry=ResearchToolRegistry(())
    )
    assert result.status == "completed"
    assert seen == [(False, True)]
    assert llm_refine._MATERIAL_JSON_OUTPUT.get() is False
