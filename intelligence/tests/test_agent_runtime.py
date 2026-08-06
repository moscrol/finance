from __future__ import annotations

from dataclasses import FrozenInstanceError
import json

import pytest

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import (
    AgentModelClient,
    AgentOutcome,
    AgentRuntime,
    ResumableAgentRuntime,
    AgentUsage,
    EpisodeEvent,
    ModelToolCall,
    ModelTurn,
    OutputEvidenceBinding,
)
from intelligence.services.provider_observability import ProviderTrace
from intelligence.runtime.openai_agents_runtime import OpenAIAgentsRuntime


TASK_HASH = "frame-hash-1"


def _task_event(task_hash: str = TASK_HASH, sequence: int = 1) -> EpisodeEvent:
    return EpisodeEvent(
        sequence=sequence,
        kind="task",
        payload={"task_frame_hash": task_hash, "question": "市场怎么看"},
    )


def _outcome(**overrides: object) -> AgentOutcome:
    values: dict[str, object] = {
        "task_frame_hash": TASK_HASH,
        "status": "partial",
        "draft": "当前证据只支持条件化判断。",
        "evidence": (),
        "traces": (),
        "gaps": ("仍缺最新资金数据",),
        "stop_reason": "budget_exhausted",
        "events": (_task_event(),),
        "bindings": (),
        "usage": AgentUsage(),
    }
    values.update(overrides)
    return AgentOutcome(**values)  # type: ignore[arg-type]


def test_agent_outcome_rejects_changed_task_frame_hash() -> None:
    with pytest.raises(ValueError, match="task frame hash"):
        _outcome(
            task_frame_hash="changed",
            events=(_task_event("original"),),
        )


def test_agent_outcome_requires_contiguous_event_sequence() -> None:
    with pytest.raises(ValueError, match="event sequence"):
        _outcome(
            events=(
                _task_event(),
                EpisodeEvent(3, "model_turn", {"content": "继续查"}),
            )
        )


def test_completed_outcome_requires_natural_language_draft() -> None:
    with pytest.raises(ValueError, match="completed.*draft"):
        _outcome(status="completed", draft="   ", stop_reason="model_finish")


def test_clarification_outcome_cannot_carry_research_evidence() -> None:
    evidence = AgentEvidence(
        tool="market_data",
        title="行情",
        detail="上涨",
        source="本地行情",
        content_hash="evidence-1",
    )

    with pytest.raises(ValueError, match="clarification.*evidence"):
        _outcome(
            status="clarification",
            draft="你指的是 A 股还是美股？",
            evidence=(evidence,),
            stop_reason="clarification_required",
        )


def test_duplicate_output_bindings_are_rejected() -> None:
    binding = OutputEvidenceBinding("direct_assessment", ("evidence-1",))

    with pytest.raises(ValueError, match="duplicate output binding"):
        _outcome(bindings=(binding, binding))


def test_model_turn_is_provider_neutral_and_json_safe() -> None:
    turn = ModelTurn(
        content="",
        tool_calls=(
            ModelToolCall("call-1", "market_data", {"query": "A股"}),
        ),
        provider_name="glm",
        error="",
    )

    payload = turn.to_dict()

    assert set(payload) == {
        "content",
        "tool_calls",
        "provider_name",
        "error",
        "provider_attempts",
    }
    assert payload["provider_attempts"] == 1
    assert payload["provider_name"] == "glm"
    assert payload["tool_calls"][0]["arguments"] == {"query": "A股"}
    json.dumps(payload, ensure_ascii=False)


def test_model_turn_and_usage_preserve_optional_token_measurements() -> None:
    turn = ModelTurn(
        content="done",
        tool_calls=(),
        provider_name="glm",
        input_tokens=120,
        output_tokens=35,
    )
    usage = AgentUsage(
        llm_calls=1,
        input_tokens=120,
        output_tokens=35,
    )

    assert turn.to_dict()["input_tokens"] == 120
    assert turn.to_dict()["output_tokens"] == 35
    assert usage.to_dict() == {
        "llm_calls": 1,
        "tool_calls": 0,
        "invalid_actions": 0,
        "input_tokens": 120,
        "output_tokens": 35,
    }


def test_model_turn_allows_zero_physical_provider_attempts() -> None:
    turn = ModelTurn(
        content="",
        tool_calls=(),
        provider_name="",
        error="model deadline exhausted",
        provider_attempts=0,
    )

    assert turn.provider_attempts == 0
    assert turn.to_dict()["provider_attempts"] == 0

    with pytest.raises(ValueError, match="non-negative integer"):
        ModelTurn("", (), provider_attempts=-1)


def test_agent_outcome_serializes_only_public_evidence_and_trace_fields() -> None:
    evidence = AgentEvidence(
        tool="news_search",
        title="政策消息",
        detail="公开摘要",
        source="https://example.invalid/news",
        internal_locator="/private/control/path",
        source_date="2026-07-22",
        evidence_tier="L1",
        content_hash="evidence-1",
    )
    trace = ProviderTrace(
        provider="news",
        capability="news_search",
        status="success",
        result_count=1,
        parent_id="run-1",
        step_id="step-1",
    )
    outcome = _outcome(
        evidence=(evidence,),
        traces=(trace,),
        bindings=(
            OutputEvidenceBinding("direct_assessment", ("evidence-1",)),
        ),
        usage=AgentUsage(llm_calls=2, tool_calls=1, invalid_actions=0),
    )

    payload = outcome.to_dict()

    assert "internal_locator" not in payload["evidence"][0]
    assert payload["evidence"][0]["content_hash"] == "evidence-1"
    assert payload["traces"][0]["step_id"] == "step-1"
    assert payload["usage"] == {
        "llm_calls": 2,
        "tool_calls": 1,
        "invalid_actions": 0,
    }
    json.dumps(payload, ensure_ascii=False)


def test_runtime_contracts_accept_scripted_adapters() -> None:
    class ScriptedModel:
        def complete(self, *, messages, tools, timeout):
            return ModelTurn("done", (), "scripted", "")

    class ScriptedRuntime:
        def run(self, *, task_frame, context, registry):
            return _outcome()

    assert isinstance(ScriptedModel(), AgentModelClient)
    assert isinstance(ScriptedRuntime(), AgentRuntime)


def test_resumable_runtime_contract_requires_start_and_run() -> None:
    class ScriptedRuntime:
        def start(self, task_frame, *, context, registry):
            del task_frame, context, registry
            return None

        def run(self, *, task_frame, context, registry):
            del task_frame, context, registry
            return _outcome()

    assert isinstance(ScriptedRuntime(), ResumableAgentRuntime)


def test_openai_agents_runtime_conforms_to_resumable_runtime_contract() -> None:
    runtime = OpenAIAgentsRuntime(
        runner=lambda _request: None,  # type: ignore[arg-type,return-value]
        backend="sdk_glm",
        model_name="fake-model",
        model_settings=object(),
    )

    assert isinstance(runtime, ResumableAgentRuntime)


def test_runtime_values_are_frozen_and_copy_input_mappings() -> None:
    arguments = {"query": "A股"}
    call = ModelToolCall("call-1", "market_data", arguments)
    arguments["query"] = "美股"

    assert call.arguments == {"query": "A股"}
    with pytest.raises(FrozenInstanceError):
        call.name = "web_search"  # type: ignore[misc]
    with pytest.raises(TypeError):
        call.arguments["query"] = "港股"  # type: ignore[index]


def test_non_json_provider_objects_cannot_cross_model_turn() -> None:
    with pytest.raises(ValueError, match="provider_name"):
        ModelTurn("", (), object(), "")  # type: ignore[arg-type]


def test_event_payload_rejects_non_json_values() -> None:
    with pytest.raises(ValueError, match="JSON-safe"):
        EpisodeEvent(1, "task", {"provider": object()})


def test_only_configure_may_precede_the_task_anchor() -> None:
    import pytest as _pytest

    from intelligence.services.agent_runtime import (
        AgentOutcome,
        AgentUsage,
        EpisodeEvent,
    )

    def _outcome(*kinds: str) -> AgentOutcome:
        return AgentOutcome(
            task_frame_hash="h" * 64,
            status="completed",
            draft="d",
            evidence=(),
            traces=(),
            gaps=(),
            stop_reason="model_finish",
            events=tuple(
                EpisodeEvent(index, kind, {"task_frame_hash": "h" * 64})
                for index, kind in enumerate(kinds, start=1)
            ),
            bindings=(),
            usage=AgentUsage(),
        )

    # The anchor guarantee is "an outcome is bound to a task frame", not "task is
    # literally index 0".  `configure` is the pre-run assembly landmark.
    assert [e.kind for e in _outcome("configure", "task").events] == [
        "configure",
        "task",
    ]
    assert _outcome("task").events[0].kind == "task"

    with _pytest.raises(ValueError, match="only configure may precede it"):
        _outcome("tool_request", "task")
    with _pytest.raises(ValueError, match="only configure may precede it"):
        _outcome("configure", "plan")
