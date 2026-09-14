"""P3c: bind read ceilings before runtime consumers, not full input/restore acceptance."""

from copy import deepcopy
from dataclasses import replace
import json
from threading import Event
from uuid import uuid4

import pytest

from intelligence.runtime.agent_episode import ContinuousAgentEpisode
from intelligence.runtime.continuous_turn_adapter import ContinuousTurnAdapter
from intelligence.runtime.episode_tool_batch import (
    EpisodeToolBatchSession,
    ToolMenu,
    tool_definitions_for_menu,
)
from intelligence.runtime.turn_control_core import TurnControlResult
from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import ModelToolCall, ModelTurn
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.episode_scope import EpisodeScope, TOOL_ERROR
from intelligence.services.query_understanding import understand_query
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.repair_coordinator import CoverageDelta, RepairGoal
from intelligence.services.research_tool_registry import ResearchToolRegistry, ToolSpec


def _fixture(scope):
    question = {
        "full": "今天市场怎么样？",
        "local_only": "不要联网。今天市场怎么样？",
        "material_only": "只依据以下材料回答。\n\n「甲收入100，订单20。」\n\n1. 甲订单占收入多少？",
    }[scope]
    # Pin this test to the Episode lane, not the still-unwired deterministic route.
    frame = replace(
        understand_query(question).task_frame, question_type="general_finance_qa"
    )
    context = build_episode_context(
        frame,
        task_id=f"runtime-ceiling-{uuid4().hex}",
        capabilities=("finance_query",),
        today="2026-07-24",
        latest_data_date="2026-07-24",
        timeout=30,
        synthesis_reserve=0,
    )
    return frame, context


def _registry(attempts=None):
    def forbidden(*args, **kwargs):
        if attempts is not None:
            attempts.append((args, kwargs))
        raise AssertionError("uncertified runner/parser/loader reached")

    return ResearchToolRegistry(
        (
            ToolSpec(
                name="uncertified_read",
                capability="finance_query",
                description="UNCERTIFIED_TOOL_SENTINEL",
                cost="local",
                freshness="stable",
                runner=forbidden,
                parse_arguments=forbidden,
            ),
            ToolSpec(
                name="certified_read",
                capability="finance_query",
                description="CERTIFIED_TOOL_SENTINEL",
                cost="local",
                freshness="stable",
                runner=forbidden,
                io_effect="local_read",
            ),
        ),
        opening_prefetch=(
            AgentEvidence(
                tool="web_search",
                title="old external",
                detail="PREFETCH_SENTINEL",
                source="web",
                source_date="2026-07-24",
            ),
        ),
        calc_loader=forbidden,
    )


@pytest.mark.parametrize("scope", ["local_only", "material_only"])
def test_episode_binds_original_registry_before_prompt_seed_and_continuation(scope):
    frame, context = _fixture(scope)
    registry = _registry()
    calls, states = [], []
    cancelled = Event()

    class Model:
        def complete(self, *, messages, tools, timeout):
            calls.append(deepcopy({"messages": messages, "tools": tools}))
            cancelled.set()
            return ModelTurn("", (), "scripted", "")

    outcome = ContinuousAgentEpisode(Model(), is_cancelled=cancelled.is_set).run(
        task_frame=frame,
        context=context,
        registry=registry,
        _continuation_sink=states,
    )
    assert len(calls) == len(states) == 1
    wire = json.dumps(calls, ensure_ascii=False)
    assert "PREFETCH_SENTINEL" not in wire
    assert "UNCERTIFIED_TOOL_SENTINEL" not in wire
    assert "uncertified_read" not in wire
    assert ("certified_read" in wire) == (scope == "local_only")
    assert outcome.evidence == ()
    state = states[0]
    assert state.registry.read_scope == scope
    assert state.registry.opening_prefetch == () and state.registry.calc_loader is None
    assert state.episode_scope.registry.read_scope == scope
    assert not state.evidence_ledger.snapshot().evidence_ids
    configure = next(
        event.payload for event in outcome.events if event.kind == "configure"
    )
    assert tuple(configure["authorized_tools"]) == (
        ("certified_read",) if scope == "local_only" else ()
    )
    assert not any(event.kind == "tool_result" for event in outcome.events)
    # Caller-owned registry remains untouched; every consumer uses the bound copy.
    assert registry.read_scope == "full" and registry.opening_prefetch


@pytest.mark.parametrize("scope", ["local_only", "material_only"])
def test_adapter_binds_registry_before_promotion_precheck_and_runtime(
    scope, monkeypatch
):
    from intelligence.runtime import continuous_turn_adapter as adapter_module

    frame, context = _fixture(scope)
    registry, observed = _registry(), []

    def promotion(candidate, **kwargs):
        observed.append(("promotion", kwargs["opening_prefetch"]))
        return candidate

    def precheck(candidate, run_context):
        observed.append(("precheck", candidate.read_scope, candidate.opening_prefetch))
        return ()

    class Runtime:
        def run(self, *, task_frame, context, registry):
            observed.append(
                (
                    "runtime",
                    registry.read_scope,
                    registry.opening_prefetch,
                    registry.calc_loader,
                )
            )
            raise RuntimeError("intentional stop after boundary capture")

    class Semantic:
        def verify(self, **kwargs):
            raise AssertionError("runtime failed; no semantic call")

    monkeypatch.setattr(adapter_module, "maybe_promote_forecast_residual", promotion)
    monkeypatch.setattr(adapter_module, "_precheck_satisfiability", precheck)
    control = TurnControlResult(
        task_frame=frame,
        execution_route=frame.question_type,
        terminal_kind="research",
        needs_retrieval=True,
        capabilities=("finance_query",),
        contract_required=True,
    )
    ContinuousTurnAdapter(
        runtime=Runtime(),
        semantic_verifier=Semantic(),
        mode="on",
        context_factory=lambda *a, **k: context,
        registry_factory=lambda *a, **k: registry,
    ).handle(frame=frame, control=control)
    assert observed == [
        ("promotion", ()),
        ("precheck", scope, ()),
        ("runtime", scope, (), None),
    ]
    assert registry.read_scope == "full" and registry.opening_prefetch


@pytest.mark.parametrize("scope", ["local_only", "material_only"])
def test_restricted_adapter_fails_before_consuming_incompatible_registry(scope):
    frame, context = _fixture(scope)
    attempts = []

    class IncompatibleRegistry:
        @property
        def opening_prefetch(self):
            attempts.append("prefetch")
            raise AssertionError("must bind before touching prefetch")

    class Runtime:
        def run(self, **kwargs):
            attempts.append("runtime")
            raise AssertionError("incompatible restricted assembly")

    class Semantic:
        def verify(self, **kwargs):
            attempts.append("semantic")
            raise AssertionError("failed assembly cannot reach verifier")

    control = TurnControlResult(
        task_frame=frame,
        execution_route=frame.question_type,
        terminal_kind="research",
        needs_retrieval=True,
        capabilities=("finance_query",),
        contract_required=True,
    )
    result = ContinuousTurnAdapter(
        runtime=Runtime(),
        semantic_verifier=Semantic(),
        mode="on",
        context_factory=lambda *a, **k: context,
        registry_factory=lambda *a, **k: IncompatibleRegistry(),
    ).handle(frame=frame, control=control)
    assert attempts == []
    assert result.handled and result.status == "failed"
    assert result.private_artifact["failure"]["type"] == "AttributeError"


@pytest.mark.parametrize("with_scope", [False, True])
@pytest.mark.parametrize("read_scope", ["local_only", "material_only"])
def test_batch_entry_hides_and_rejects_unknown_io_before_parsing_or_dispatch(
    read_scope, with_scope
):
    _, context = _fixture(read_scope)
    attempts = []
    registry = _registry(attempts)
    events, dispatches = [], []

    class Sink:
        def emit(self, kind, payload):
            events.append((kind, dict(payload)))

    scope = (
        EpisodeScope(
            episode_id=context.contract.task_id,
            user_id="fixture",
            context=context,
            registry=registry,
            event_sink=Sink(),
        )
        if with_scope
        else None
    )
    batch = EpisodeToolBatchSession(scope=scope)
    batch.on_dispatch = dispatches.append
    menu = batch.menu(registry=registry, context=context)
    assert "uncertified_read" not in menu.visible
    assert ("certified_read" in menu.visible) == (read_scope == "local_only")
    # Even a stale caller-supplied menu must not advertise the uncertified tool.
    stale_menu = ToolMenu(("certified_read", "uncertified_read"), (), menu.would_grant)
    definitions = tool_definitions_for_menu(
        stale_menu, registry=registry, context=context
    )
    assert {d["function"]["name"] for d in definitions} == set(menu.visible)
    result = batch.execute(
        (ModelToolCall("forbidden", "uncertified_read", {}),),
        registry=registry,
        context=context,
        remaining_slots=1,
    )
    assert result.executed_count == 0
    assert dispatches == []
    assert attempts == []  # parser/runner failures could otherwise be swallowed.
    assert result.items[0].error == "unknown_or_unauthorized_tool"
    if with_scope:
        assert any(
            kind == TOOL_ERROR and payload["stage"] == "authorize" and payload["reason"]
            for kind, payload in events
        )


@pytest.mark.parametrize("scope", ["local_only", "material_only"])
def test_repair_reentry_rebinds_registry_and_cannot_readd_unknown_tool(scope):
    frame, context = _fixture(scope)
    calls, states = [], []

    class Model:
        def complete(self, *, messages, tools, timeout):
            calls.append(deepcopy({"messages": messages, "tools": tools}))
            return ModelTurn(
                json.dumps(
                    {
                        "status": "partial",
                        "draft": "现有证据不足。",
                        "gaps": ["缺少证据"],
                        "bindings": [
                            {
                                "output_id": output.output_id,
                                "evidence_hashes": [],
                                "gap": "缺少证据",
                            }
                            for output in context.contract.required_outputs
                            if output.required
                        ],
                    },
                    ensure_ascii=False,
                ),
                (),
                "scripted",
                "",
            )

    episode = ContinuousAgentEpisode(Model())
    previous = episode.run(
        task_frame=frame,
        context=context,
        registry=_registry(),
        _continuation_sink=states,
    )
    state = states[0]
    # Emulate an older in-memory caller replacing its registry between repair rounds.
    state.registry = _registry()
    goal = RepairGoal(
        episode_id=context.contract.task_id,
        repair_goal_id="local-repair",
        cycle=1,
        missing_answer_elements=(),
        unsupported_claims=(),
        missing_evidence_modes=(),
        attempted_actions=(),
        evidence_progress=CoverageDelta(0, 0, 0),
        remaining_calls=1,
        remaining_seconds=8.0,
        reopen_tools=True,
    )
    before_repair = len(calls)
    episode.resume(state, previous, goal)
    assert len(calls) == before_repair + 1
    assert state.registry.read_scope == scope
    assert state.registry.calc_loader is None and state.registry.opening_prefetch == ()
    assert "uncertified_read" not in json.dumps(calls[-1], ensure_ascii=False)
    assert "PREFETCH_SENTINEL" not in json.dumps(calls[-1], ensure_ascii=False)


def test_batch_still_executes_certified_local_runner_with_real_observation():
    _, context = _fixture("local_only")
    calls = []

    def runner(query, tool_context):
        calls.append(query)
        return (
            [
                AgentEvidence(
                    tool="local_probe",
                    title="local",
                    detail="临时本地观察",
                    source="local",
                    source_date="2026-07-24",
                )
            ],
            "临时本地观察",
            ProviderTrace(
                provider="fixture", capability="finance_query", status="success"
            ),
        )

    registry = ResearchToolRegistry(
        (
            ToolSpec(
                name="local_probe",
                capability="finance_query",
                description="test",
                cost="local",
                freshness="stable",
                runner=runner,
                io_effect="local_read",
            ),
        )
    )
    batch = EpisodeToolBatchSession()
    result = batch.execute(
        (ModelToolCall("local", "local_probe", {"query": "probe"}),),
        registry=registry,
        context=context,
        remaining_slots=1,
    )
    assert calls == ["probe"]
    assert result.executed_count == 1
    assert result.items[0].observation.evidence[0].detail == "临时本地观察"


def test_rebinding_strips_late_prefetch_injection_without_relaxing_existing_ceiling():
    _, context = _fixture("local_only")
    registry = _registry().with_read_scope("material_only")
    registry.opening_prefetch = _registry().opening_prefetch
    registry.calc_loader = _registry().calc_loader
    bound = registry.for_context(context)
    assert bound.read_scope == "material_only"
    assert bound.opening_prefetch == () and bound.calc_loader is None
    assert bound.authorized_specs(context.contract.allowed_capabilities) == ()


@pytest.mark.parametrize("replacement_io", ["unknown", "external_or_mixed"])
def test_batch_replacement_denial_uses_current_runner_and_retains_scope_history(
    replacement_io,
):
    _, context = _fixture("local_only")
    attempts, events, dispatches = [], [], []
    original = _registry(attempts)

    class Sink:
        def emit(self, kind, payload):
            events.append((kind, dict(payload)))

    scope = EpisodeScope(
        episode_id=context.contract.task_id,
        user_id="fixture",
        context=context,
        registry=original,
        event_sink=Sink(),
    )
    scope.record_invocation("earlier_tool")
    scope.record_derive_mismatch("earlier_mismatch")
    batch = EpisodeToolBatchSession(scope=scope)
    batch.on_dispatch = dispatches.append
    replacement = original.with_specs(
        replace(
            original.resolve("certified_read"),
            io_effect=replacement_io,
            parse_arguments=original.resolve("uncertified_read").parse_arguments,
        )
    )
    result = batch.execute(
        (ModelToolCall("replacement", "certified_read", {}),),
        registry=replacement,
        context=context,
        remaining_slots=1,
    )
    assert result.executed_count == 0 and attempts == dispatches == []
    denial = next(p for k, p in events if k == TOOL_ERROR)
    assert denial["stage"] == "authorize" and "IO" in denial["reason"]
    assert denial["capability"] == "finance_query"
    current = batch.bind_scope(registry=replacement, context=context)
    assert not current.authorize("certified_read").allowed
    assert current.invoked_tools is scope.invoked_tools
    assert current._derive_mismatches is scope._derive_mismatches
    assert "earlier_tool" in current.invoked_tools
    assert "earlier_mismatch" in current._derive_mismatches
    # An old immutable view remains a receipt of its own runner set.
    assert scope.authorize("certified_read").allowed


def test_repair_same_name_unknown_runner_has_matching_scope_denial_and_no_dispatch():
    frame, context = _fixture("local_only")
    attempts, states, live, dispatches = [], [], [], []
    registry = _registry(attempts)

    class Model:
        repair = False

        def complete(self, *, messages, tools, timeout):
            if self.repair:
                self.repair = False
                assert "certified_read" not in {d["function"]["name"] for d in tools}
                return ModelTurn(
                    "",
                    (ModelToolCall("repair-bad", "certified_read", {}),),
                    "scripted",
                    "",
                )
            return ModelTurn(
                json.dumps(
                    {
                        "status": "partial",
                        "draft": "现有证据不足。",
                        "gaps": ["缺少证据"],
                        "bindings": [
                            {
                                "output_id": o.output_id,
                                "evidence_hashes": [],
                                "gap": "缺少证据",
                            }
                            for o in context.contract.required_outputs
                            if o.required
                        ],
                    },
                    ensure_ascii=False,
                ),
                (),
                "scripted",
                "",
            )

    model = Model()
    episode = ContinuousAgentEpisode(model, event_sink=live.append)
    previous = episode.run(
        task_frame=frame, context=context, registry=registry, _continuation_sink=states
    )
    state = states[0]
    state.registry = registry.with_specs(
        replace(
            registry.resolve("certified_read"),
            io_effect="unknown",
            parse_arguments=registry.resolve("uncertified_read").parse_arguments,
        )
    )
    original_dispatch = state.tool_session.on_dispatch

    def record(intent):
        dispatches.append(intent)
        original_dispatch(intent)

    state.tool_session.on_dispatch = record
    goal = RepairGoal(
        episode_id=context.contract.task_id,
        repair_goal_id="replacement-repair",
        cycle=1,
        missing_answer_elements=(),
        unsupported_claims=(),
        missing_evidence_modes=(),
        attempted_actions=(),
        evidence_progress=CoverageDelta(0, 0, 0),
        remaining_calls=1,
        remaining_seconds=8,
        reopen_tools=True,
    )
    model.repair = True
    outcome = episode.resume(state, previous, goal)
    assert attempts == dispatches == []
    # A rejected model request may be recorded; it must never become durable dispatch intent.
    assert not any(
        e.kind == "tool_request" and "replay" in e.payload for e in outcome.events
    )
    denial = next(
        e.payload
        for e in live
        if e.kind == TOOL_ERROR and e.payload.get("tool_call_id") == "repair-bad"
    )
    assert "IO" in denial["reason"]
    assert not state.episode_scope.authorize("certified_read").allowed
    assert state.episode_scope.registry is state.registry


def test_scope_rebinding_preserves_stricter_ceiling_and_rejects_different_task():
    _, context = _fixture("local_only")
    registry = _registry().with_read_scope("material_only")
    scope = EpisodeScope(
        episode_id=context.contract.task_id,
        user_id="fixture",
        context=context,
        registry=registry,
    )
    rebound = scope.for_execution(context=context, registry=_registry())
    assert rebound.registry.read_scope == "material_only"
    assert rebound.allowed_tools() == ()
    assert (
        rebound.registry.opening_prefetch == () and rebound.registry.calc_loader is None
    )
    _, other_context = _fixture("local_only")
    with pytest.raises(ValueError, match="different episode"):
        scope.for_execution(context=other_context, registry=_registry())


def test_full_context_binding_preserves_original_registry_identity_and_prefetch():
    _, context = _fixture("full")
    registry = _registry()
    assert registry.for_context(context) is registry
    assert len(registry.tool_definitions(context.contract.allowed_capabilities)) == 2
