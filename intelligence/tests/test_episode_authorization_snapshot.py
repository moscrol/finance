"""Saved authority is evidence, not permission: revalidate before recovery writes."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta
import hashlib
import json
from uuid import uuid4

import pytest

from intelligence.runtime.agent_episode import ContinuousAgentEpisode
from intelligence.services import episode_authorization as auth
from intelligence.services.episode_restore import RestoreUnavailable, restore_episode
from intelligence.services.episode_store import EpisodeState, JsonlEpisodeStore
from intelligence.services.material_contract import MaterialContract
from intelligence.services.research_tool_registry import ResearchToolRegistry
from intelligence.tests.conformance.races._drive import build_rig


def _fixture():
    rig = build_rig(f"authorization-{uuid4().hex}")
    spec = replace(rig.registry.resolve("market_data"), capability="finance_query", io_effect="local_read")
    rig.registry = ResearchToolRegistry((spec,))
    rig.context = replace(rig.context, contract=replace(
        rig.context.contract, allowed_capabilities=("finance_query",),
        required_outputs=tuple(replace(output, evidence_types=("finance_query",)) for output in rig.context.contract.required_outputs),
        material_contract=MaterialContract("constraint_confirmed", "real", "local_only", data_scope_declared=True),
    ))
    return rig


def _capture(rig):
    return auth.capture_authorization_snapshot(rig.context, rig.registry)


def test_round_trip_keeps_contract_policy_cutoff_and_effective_registry_scope():
    rig = _fixture()
    payload = _capture(rig)
    decoded = auth.EpisodeAuthorizationSnapshot.from_dict(payload, episode_id=rig.task_id)
    assert decoded.to_dict() == json.loads(json.dumps(payload, allow_nan=False))
    assert decoded.contract == rig.context.contract
    assert decoded.policy == rig.context.policy
    assert decoded.information_cutoff == rig.context.information_cutoff
    assert decoded.registry["read_scope"] == "local_only"
    assert decoded.registry["tools"][0]["io_effect"] == "local_read"
    assert decoded.registry["tools"][0]["parameters"]
    auth.validate_current_authorization(payload, context=rig.context, registry=rig.registry)
    payload["contract"]["allowed_capabilities"].append("web_search")
    assert decoded.contract.allowed_capabilities == ("finance_query",)
    with pytest.raises(TypeError):
        decoded.registry["tools"][0]["parameters"]["type"] = "array"


@pytest.mark.parametrize(("path", "value"), [
    (("schema_version",), True), (("schema_version",), 2), (("kind",), "context"),
    (("episode_id",), "wrong"), (("contract", "task_id"), "wrong"),
    (("contract", "contract_version"), "2"),
    (("contract", "allowed_capabilities"), "market_data"),
    (("contract", "required_outputs", 0, "required"), "false"),
    (("contract", "material_contract", "data_scope"), "material_only"),
    (("policy", "max_steps"), True), (("policy", "max_steps"), 1.5),
    (("policy", "total_seconds"), float("nan")),
    (("policy", "synthesis_reserve"), -1.0), (("policy", "tier"), "unlimited"),
    (("policy", "total_seconds"), 10 ** 400), (("information_cutoff", "source"), []),
    (("contract", "material_contract", "classification"), []),
    (("information_cutoff", "as_of_date"), "not-a-date"),
    (("registry", "read_scope"), "full"),
    (("registry", "tools", 0, "io_effect"), "external_or_mixed"),
    (("registry", "tools", 0, "capability"), "web_search"),
    (("registry", "tools", 0, "replay"), "maybe"),
    (("registry", "tools", 0, "parameters"), []),
    (("registry", "tools", 0, "produces"), [True]),
    (("registry_sha256",), "0" * 64), (("unexpected",), True),
])
def test_malformed_or_inconsistent_authorization_snapshot_is_rejected(path, value):
    rig = _fixture()
    payload = _capture(rig)
    node = payload
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    with pytest.raises(ValueError):
        auth.EpisodeAuthorizationSnapshot.from_dict(payload, episode_id=rig.task_id)


@pytest.mark.parametrize("path", [
    ("contract",), ("policy",), ("registry",), ("information_cutoff",),
    ("contract", "allowed_capabilities"), ("contract", "required_outputs", 0, "required"),
    ("contract", "material_contract", "authenticity"), ("policy", "synthesis_reserve"),
    ("registry", "tools", 0, "io_effect"),
])
def test_missing_recovery_fields_are_not_silently_filled_from_defaults(path):
    rig = _fixture()
    payload = _capture(rig)
    node = payload
    for key in path[:-1]:
        node = node[key]
    del node[path[-1]]
    with pytest.raises(ValueError):
        auth.EpisodeAuthorizationSnapshot.from_dict(payload, episode_id=rig.task_id)


@pytest.mark.parametrize("change", [
    "capabilities", "material_scope", "policy", "cutoff", "required_outputs", "task_hash",
    "io_effect", "parameters", "replay", "query_scope", "contract_text", "read_scope", "missing_tool", "trace_parent",
])
def test_current_authorization_drift_is_rejected_not_merged_or_upgraded(change):
    rig = _fixture()
    payload = _capture(rig)
    context, registry = rig.context, rig.registry
    spec = registry.resolve("market_data")
    if change == "capabilities":
        context = replace(context, contract=replace(context.contract, allowed_capabilities=("finance_query", "evidence_lookup")))
    elif change == "material_scope":
        context = replace(context, contract=replace(context.contract, material_contract=None))
    elif change == "policy":
        context = replace(context, policy=replace(context.policy, max_steps=4))
    elif change == "cutoff":
        context = replace(context, information_cutoff=replace(
            context.information_cutoff, as_of_date=context.information_cutoff.as_of_date - timedelta(days=1),
        ))
    elif change == "required_outputs":
        context = replace(context, contract=replace(context.contract, required_outputs=()))
    elif change == "task_hash":
        context = replace(context, contract=replace(context.contract, task_frame_hash="changed"))
    elif change == "trace_parent":
        context = replace(context, trace_parent_id="other")
    elif change == "read_scope":
        registry = registry.with_read_scope("material_only")
    elif change == "missing_tool":
        registry = registry.without("market_data")
    else:
        values = {
            "io_effect": {"io_effect": "unknown"}, "parameters": {"parameters": {"type": "object"}},
            "replay": {"replay": "never"}, "query_scope": {"query_scope": "episode"},
            "contract_text": {"contract": "changed tool contract"},
        }
        registry = registry.with_specs(replace(spec, **values[change]))
    with pytest.raises(ValueError, match="authorization"):
        auth.validate_current_authorization(payload, context=context, registry=registry)


def test_unrelated_tools_and_callable_objects_do_not_become_a_code_identity_claim():
    rig = _fixture()
    payload = _capture(rig)
    spec = rig.registry.resolve("market_data")
    registry = rig.registry.with_specs(
        replace(spec, runner=lambda *_: None),
        replace(spec, name="not-authorized", capability="web_search"),
    )
    assert _capture(rig) == auth.capture_authorization_snapshot(rig.context, registry)
    # A declaration manifest is not a signature of executable closures or their user binding.
    assert "runner" not in payload["registry"]["tools"][0]


def test_checkpoint_authorization_is_deeply_frozen_and_legacy_missing_is_explicit():
    rig = _fixture()
    payload = _capture(rig)
    state = EpisodeState(episode_id=rig.task_id, phase="planning", authorization_snapshot=payload)
    payload["contract"]["allowed_capabilities"].clear()
    assert state.authorization_snapshot["contract"]["allowed_capabilities"] == ("finance_query",)
    with pytest.raises(TypeError):
        state.authorization_snapshot["contract"]["material_contract"]["data_scope"] = "full"
    exported = state.to_dict()
    exported["authorization_snapshot"]["registry"]["tools"].clear()
    assert len(state.authorization_snapshot["registry"]["tools"]) == 1
    assert EpisodeState.from_dict(json.loads(json.dumps(state.to_dict()))) == state
    assert EpisodeState.from_dict({"episode_id": "old", "phase": "planning", "log_version": 1}).authorization_snapshot is None


def _crashed_prefix(tmp_path):
    rig = _fixture()
    live = JsonlEpisodeStore(tmp_path / "live")
    rig.episode = ContinuousAgentEpisode(rig.model, store=live)
    rig.start()
    assert rig.run_until("model_pending") is not None
    events, state = live.load(rig.task_id)
    assert state.authorization_snapshot is not None
    crash = JsonlEpisodeStore(tmp_path / "crash")
    crash.append(rig.task_id, events, sync=True)
    crash.put_state(rig.task_id, replace(state, retry={"remaining": 0}))
    rig.finish()  # no concurrent writer to the crash store
    return rig, crash


@pytest.mark.parametrize("missing", ["context", "registry", "both"])
def test_recovery_requires_current_authority_before_any_synthesis(tmp_path, missing):
    rig, store = _crashed_prefix(tmp_path)
    before = store.load(rig.task_id)
    kwargs = {}
    if missing != "context" and missing != "both":
        kwargs["context"] = rig.context
    if missing != "registry" and missing != "both":
        kwargs["registry"] = rig.registry
    with pytest.raises(RestoreUnavailable, match="authorization"):
        restore_episode(rig.task_id, store, **kwargs)
    assert store.load(rig.task_id) == before


@pytest.mark.parametrize("expired", [False, True])
def test_recovery_revalidates_before_writing_and_preserves_full_authorization(tmp_path, expired):
    rig, store = _crashed_prefix(tmp_path)
    before = store.load(rig.task_id)
    now = datetime.fromisoformat(before[1].deadline_at) + timedelta(seconds=1 if expired else -1)
    restricted = replace(rig.context, contract=replace(
        rig.context.contract, allowed_capabilities=(), required_outputs=(),
    ))
    with pytest.raises(RestoreUnavailable, match="authorization"):
        restore_episode(rig.task_id, store, context=restricted, registry=rig.registry, now=now)
    assert store.load(rig.task_id) == before
    result = ContinuousAgentEpisode.restore(
        rig.task_id, store, context=rig.context, registry=rig.registry, now=now,
    )
    assert result.disposition == ("closed" if expired else "resumable")
    assert result.synthesized
    assert result.state_after.authorization_snapshot == before[1].authorization_snapshot
    assert JsonlEpisodeStore(tmp_path / "crash").load(rig.task_id)[1] == result.state_after


def test_checkpoint_captures_actual_bound_tools_after_configuration(tmp_path):
    from intelligence.tests.test_sub_research_persistence import ObservedStore, run_tree

    store = ObservedStore(tmp_path)
    outcome, _, _, _, _ = run_tree(store)
    assert outcome.persistence == "durable"
    _, parent = store.load(outcome.events[0].payload["task_id"])
    declared = {item["name"] for item in parent.authorization_snapshot["registry"]["tools"]}
    assert "sub_research" in declared  # bound after configure; the summary is not enough
    for child_id in store.child_ids:
        _, child = store.load(child_id)
        assert "sub_research" not in {t["name"] for t in child.authorization_snapshot["registry"]["tools"]}


@pytest.mark.parametrize("boundary", ["planning", "tools_pending", "done"])
@pytest.mark.parametrize("failure", ["raise", "missing", "invalid"])
def test_authorization_encoding_failure_fences_before_more_effects(tmp_path, monkeypatch, boundary, failure):
    from intelligence.runtime import agent_episode
    from intelligence.services.episode_store import FencedEpisodeStore, EpisodeStoreFailed
    from intelligence.services.agent_runtime import EpisodeEvent

    rig = _fixture()
    raw = JsonlEpisodeStore(tmp_path)
    fence = FencedEpisodeStore(raw)
    rig.episode = ContinuousAgentEpisode(rig.model, store=fence)
    rig.start()
    if boundary == "tools_pending":
        assert rig.run_until("model_settled") is not None
    elif boundary == "done":
        assert rig.run_until("before_finish") is not None
    before = raw.load(rig.task_id)
    calls = rig.model.calls
    effects = [item for item in rig.oracle.timeline if item.kind == "effect"]
    payload = _capture(rig)

    def broken(*_args, **_kwargs):
        if failure == "raise":
            raise OSError("authorization encoding failed")
        if failure == "missing":
            return None
        value = deepcopy(payload)
        value["episode_id"] = "other"
        return value

    monkeypatch.setattr(agent_episode, "capture_authorization_snapshot", broken)
    result = rig.finish()
    assert result.persistence == "failed" and result.stop_reason == "storage_failed"
    assert rig.model.calls == calls
    assert [item for item in rig.oracle.timeline if item.kind == "effect"] == effects
    assert fence.failure
    assert raw.load(rig.task_id)[1] == before[1]
    with pytest.raises(EpisodeStoreFailed):
        fence.append("sibling", (EpisodeEvent(1, "task", {}),), sync=True)
    if boundary == "done":
        assert result.draft and result.evidence


@pytest.mark.parametrize(("field", "value"), [
    ("read_scope", "full"), ("io_effect", "external_or_mixed"),
    ("capability", "not_authorized"), ("replay", "maybe"),
    ("query_scope", "unknown"), ("parameters", []), ("produces", [True]),
    ("min_window_seconds", True), ("name", " spaced "),
])
def test_registry_semantics_reject_even_with_a_recomputed_digest(field, value):
    rig = _fixture()
    payload = _capture(rig)
    target = payload["registry"] if field == "read_scope" else payload["registry"]["tools"][0]
    target[field] = value
    # A checksum isn't an authorization signature. Prove semantics independently
    # from the digest; otherwise digest mismatch hides removed field validators.
    payload["registry_sha256"] = hashlib.sha256(json.dumps(
        payload["registry"], ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()
    with pytest.raises(ValueError):
        auth.EpisodeAuthorizationSnapshot.from_dict(payload, episode_id=rig.task_id)


@pytest.mark.parametrize("provide_current", [False, True])
def test_legacy_or_missing_snapshot_never_bypasses_authorization(tmp_path, provide_current):
    rig, store = _crashed_prefix(tmp_path)
    _, state = store.load(rig.task_id)
    store.put_state(rig.task_id, replace(state, authorization_snapshot=None))
    before = store.load(rig.task_id)
    kwargs = {"context": rig.context, "registry": rig.registry} if provide_current else {}
    with pytest.raises(RestoreUnavailable, match="authorization"):
        restore_episode(rig.task_id, store, **kwargs)
    assert store.load(rig.task_id) == before


@pytest.mark.parametrize("mismatch", ["episode", "task_event"])
def test_recovery_rejects_identity_mismatch_without_rewriting_log(tmp_path, mismatch):
    from intelligence.services.episode_store import MemoryEpisodeStore

    rig, original = _crashed_prefix(tmp_path)
    events, state = original.load(rig.task_id)
    context = rig.context
    if mismatch == "episode":
        context = replace(context, contract=replace(context.contract, task_id="other"))
    else:
        events = tuple(replace(e, payload={**e.payload, "task_frame_hash": "wrong"})
                       if e.kind in {"configure", "task", "prompt_assembled"} else e for e in events)
    store = MemoryEpisodeStore()
    store.append(rig.task_id, events, sync=True)
    store.put_state(rig.task_id, state)
    before = store.load(rig.task_id)
    with pytest.raises(RestoreUnavailable, match="authorization"):
        restore_episode(rig.task_id, store, context=context, registry=rig.registry)
    assert store.load(rig.task_id) == before


def test_unresolved_material_boundary_cannot_authorize_recovery(tmp_path):
    rig, store = _crashed_prefix(tmp_path)
    context = replace(rig.context, contract=replace(rig.context.contract,
        material_contract=MaterialContract("boundary_uncertain", None, None)))
    payload = auth.capture_authorization_snapshot(context, rig.registry)
    _, state = store.load(rig.task_id)
    store.put_state(rig.task_id, replace(state, authorization_snapshot=payload))
    before = store.load(rig.task_id)
    with pytest.raises(RestoreUnavailable, match="authorization"):
        restore_episode(rig.task_id, store, context=context, registry=rig.registry)
    assert store.load(rig.task_id) == before


def test_complete_material_and_evidence_contract_is_not_replaced_by_hashes():
    from intelligence.services.material_contract import MaterialQuestion, PremiseMark
    from intelligence.services.research_contract import EvidencePlan, EvidenceRequirement

    rig = _fixture()
    contract = replace(rig.context.contract,
        subject="测试主体", subject_kind="stock", timeframe="2026-09", presentation_profile="detailed",
        evidence_plan=EvidencePlan("explicit", (EvidenceRequirement("local", "finance_query", True, "dated", "verify"),), "dated"),
        material_contract=replace(rig.context.contract.material_contract,
            questions=(MaterialQuestion("q1", "依据是什么？"),),
            premise_marks=(PremiseMark("sha256:" + "a" * 64, "unverified_belief", 2, "q1"),),
            continuation_requested=True))
    rig.context = replace(rig.context, contract=contract)
    decoded = auth.EpisodeAuthorizationSnapshot.from_dict(_capture(rig), episode_id=rig.task_id)
    assert decoded.contract == contract
    assert decoded.contract.evidence_plan.requirements[0].reason == "verify"
    assert decoded.contract.material_contract.premise_marks[0].source_turn == 2


def test_live_promotion_captures_current_policy_not_original_configure(tmp_path):
    from intelligence.services.research_harness import FinanceResearchHarness
    from intelligence.services.mode_governor import ModeSignals
    from intelligence.tests.test_tier_promotion import (
        _ScriptedModel, _loop_context, _frame, _deep_plan_turn, _tool_turn, _finish_turn, _registry,
    )

    context = _loop_context(f"authorization-deep-{uuid4().hex}")
    store = JsonlEpisodeStore(tmp_path)
    captured, continuation = [], []

    class Model(_ScriptedModel):
        def complete(self, **kwargs):
            captured.append(store.load(context.contract.task_id))
            return super().complete(**kwargs)

    registry = _registry()
    model = Model([_deep_plan_turn(), _tool_turn(), _finish_turn()])
    outcome = ContinuousAgentEpisode(model, store=store, harness=FinanceResearchHarness(
        mode_signals=lambda *_: ModeSignals(evidence_domains=("盘面", "新闻")),
    )).run(task_frame=_frame(), context=context, registry=registry, _continuation_sink=continuation)
    assert outcome.persistence == "durable"
    first, promoted = captured[0][1], captured[1][1]
    current = continuation[0].context
    assert current.policy.tier == "deep" and context.policy.tier == "standard"
    assert first.authorization_snapshot["policy"]["tier"] == "standard"
    assert promoted.authorization_snapshot["policy"]["tier"] == "deep"
    assert promoted.authorization_snapshot["contract"]["research_tier"] == "standard"
    assert promoted.to_dict()["authorization_snapshot"] == auth.capture_authorization_snapshot(current, registry)
    assert JsonlEpisodeStore(tmp_path).load(context.contract.task_id)[1].authorization_snapshot == promoted.authorization_snapshot


def test_repair_checkpoint_refreshes_rebound_registry_and_downgraded_contract(tmp_path):
    from intelligence.tests.test_agent_episode import (
        ScriptedModel, _frame, _context, _tool_turn, _finish_turn, _market_registry, _successful_runner,
    )
    from intelligence.tests.test_episode_session import _goal

    frame = _frame(("direct_assessment", "counterpoint"))
    context = _context(frame, max_steps=4)
    store = JsonlEpisodeStore(tmp_path)
    continuation, captured = [], []

    class Model(ScriptedModel):
        def complete(self, **kwargs):
            if len(self.calls) == 2:
                captured.append(store.load(context.contract.task_id))
            return super().complete(**kwargs)

    model = Model([_tool_turn("市场"), _finish_turn(status="partial", gap="缺少反方证据"),
                   _finish_turn(status="partial", gap="缺少反方证据")])
    episode = ContinuousAgentEpisode(model, store=store)
    previous = episode.run(task_frame=frame, context=context, registry=_market_registry(_successful_runner),
                           _continuation_sink=continuation)
    state = continuation[0]
    _, first = store.load(context.contract.task_id)
    spec = state.registry.resolve("market_data")
    state.registry = state.registry.with_specs(replace(spec, contract="repair current declaration", replay="never"))
    repaired = episode.resume(state, previous, replace(_goal(context.contract.task_id), remaining_calls=0))
    assert repaired.persistence == "durable" and len(captured) == 1
    assert state.context.contract != context.contract  # real unreachable-output downgrade
    events, checkpoint = captured[0]
    expected = auth.capture_authorization_snapshot(state.context, state.registry)
    assert checkpoint.to_dict()["authorization_snapshot"] == expected
    assert checkpoint.authorization_snapshot != first.authorization_snapshot
    assert store.load(context.contract.task_id)[1].to_dict()["authorization_snapshot"] == expected
    # Recover the real repair prefix using separately retained current inputs.
    crash = JsonlEpisodeStore(tmp_path / "repair-crash")
    crash.append(context.contract.task_id, events, sync=True)
    crash.put_state(context.contract.task_id, checkpoint)
    result = restore_episode(context.contract.task_id, crash, context=state.context, registry=state.registry,
                             now=datetime.fromisoformat(checkpoint.deadline_at) - timedelta(seconds=1))
    assert result.plan.phase == "repair" and result.plan.action == "retry_model"


@pytest.mark.parametrize("fail_capture", [False, True])
def test_promoted_authority_is_confirmed_before_plan_child_effects(tmp_path, monkeypatch, fail_capture):
    from intelligence.runtime import agent_episode
    from intelligence.runtime.glm_agent_runtime import GLMAgentRuntime
    from intelligence.services.mode_governor import ModeSignals
    from intelligence.tests.test_sub_research_persistence import ObservedStore, TreeModel, registry
    from intelligence.tests.test_sub_research_tool import _frame
    from intelligence.tests.test_tier_promotion import _loop_context

    context = _loop_context(f"authorization-plan-{uuid4().hex}")
    context = replace(context, contract=replace(context.contract, allowed_capabilities=("market_data", "sub_research")))
    store = ObservedStore(tmp_path)
    observed, executed = [], []
    capture = agent_episode.capture_authorization_snapshot

    def maybe_fail(current, tools):
        if fail_capture and current.contract.task_id == context.contract.task_id and current.policy.tier == "deep":
            raise OSError("promoted authority not saved")
        return capture(current, tools)

    def before_child(_messages):
        events, checkpoint = store.load(context.contract.task_id)
        observed.append(checkpoint.authorization_snapshot["policy"]["tier"])
        decision = next(e for e in events if e.kind == "mode_decision")
        assert checkpoint.last_sequence >= decision.sequence

    monkeypatch.setattr(agent_episode, "capture_authorization_snapshot", maybe_fail)
    model = TreeModel(store, context.contract.task_id, plan=True, before_child=before_child)
    outcome = GLMAgentRuntime(client=model, episode_store=store,
        mode_signals=lambda *_: ModeSignals(user_mode="deep"),
    ).run(task_frame=_frame(), context=context, registry=registry(executed))
    if fail_capture:
        assert outcome.persistence == "failed" and outcome.stop_reason == "storage_failed"
        assert model.parent_calls == 1 and model.child_calls == 0
        assert observed == executed == [] and store.child_ids == set()
    else:
        assert outcome.persistence == "durable" and model.child_calls == 2
        assert observed == ["deep", "deep"] and len(executed) == 1


@pytest.mark.parametrize("with_tools", [False, True])
def test_promotion_checkpoint_preserves_the_settled_turn_recovery_position(tmp_path, with_tools):
    from intelligence.services.mode_governor import ModeSignals
    from intelligence.services.research_harness import FinanceResearchHarness
    from intelligence.tests.test_tier_promotion import (
        _ScriptedModel, _loop_context, _frame, _deep_plan_turn, _tool_turn, _finish_turn, _registry,
    )

    context = _loop_context(f"authorization-pc-{uuid4().hex}")
    captured, continuation = [], []

    class PromotionStore(JsonlEpisodeStore):
        def put_state(self, episode_id, state):
            previous = self.load(episode_id)[1]
            super().put_state(episode_id, state)
            if (previous is not None and previous.authorization_snapshot["policy"]["tier"] == "standard"
                    and state.authorization_snapshot["policy"]["tier"] == "deep"):
                captured.append((previous, self.load(episode_id)))

    store = PromotionStore(tmp_path / "live")
    registry = _registry()
    plan = _deep_plan_turn()
    turns = ([replace(plan, tool_calls=_tool_turn().tool_calls), _finish_turn()] if with_tools
             else [plan, _tool_turn(), _finish_turn()])
    model = _ScriptedModel(turns)
    outcome = ContinuousAgentEpisode(model, store=store, harness=FinanceResearchHarness(
        mode_signals=lambda *_: ModeSignals(evidence_domains=("盘面", "新闻")),
    )).run(task_frame=_frame(), context=context, registry=registry, _continuation_sink=continuation)
    assert outcome.persistence == "durable" and len(captured) == 1
    previous, (events, checkpoint) = captured[0]
    assert previous.phase == "model_pending" and previous.reserved_ids == ("turn-1",)
    assert not any(event.kind == "tool_request" for event in events)
    assert checkpoint.authorization_snapshot["policy"]["tier"] == "deep"
    assert checkpoint.budget_snapshot["hard_calls_cap"] == 24
    assert checkpoint.last_sequence >= next(event.sequence for event in events if event.kind == "mode_decision")

    # A real prefix, copied only after the live run has finished. No live writer
    # competes with recovery; current authority comes from the retained context,
    # not by decoding the saved authorization and granting it to itself.
    crash = JsonlEpisodeStore(tmp_path / "crash")
    crash.append(context.contract.task_id, events, sync=True)
    crash.put_state(context.contract.task_id, checkpoint)
    result = restore_episode(context.contract.task_id, crash, context=continuation[0].context,
                             registry=registry,
                             now=datetime.fromisoformat(checkpoint.deadline_at) - timedelta(seconds=1))
    assert result.plan.action == ("dispatch_tools" if with_tools else "interpret_turn")
    assert result.plan.turn_id == "turn-1"
    assert result.plan.call_ids == (("call-1",) if with_tools else ())
    assert checkpoint.phase == previous.phase
    assert checkpoint.reserved_ids == previous.reserved_ids
    assert checkpoint.retry == previous.retry
    assert checkpoint.cancel == previous.cancel


def test_required_registry_cannot_silently_fall_back_to_an_old_checkpoint(tmp_path):
    from intelligence.runtime.agent_episode import _EpisodeLedger
    from intelligence.services.episode_store import FencedEpisodeStore

    rig = _fixture()
    raw = JsonlEpisodeStore(tmp_path)
    fence = FencedEpisodeStore(raw)
    ledger = _EpisodeLedger(rig.frame, episode_id=rig.task_id, store=fence)
    ledger.active_context, ledger.active_registry = rig.context, rig.registry
    ledger.put_state(phase="planning")
    before = raw.load(rig.task_id)
    ledger.active_registry = None
    ledger.put_state(phase="planning")
    assert ledger.store_failures and fence.failure
    assert raw.load(rig.task_id) == before
