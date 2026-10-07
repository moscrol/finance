"""Private evidence recovery preserves atoms, owners and model-visible citation order."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, fields, replace
from datetime import date
import hashlib
import json
from uuid import uuid4

import pytest

from intelligence.services import episode_evidence as snapshots
from intelligence.services.agent_research import AgentEvidence, StructuredObservation
from intelligence.services.agent_runtime import public_agent_evidence
from intelligence.services.episode_protocol import evidence_ordinal_table, resolve_evidence_refs
from intelligence.services.episode_store import EpisodeState
from intelligence.services.evidence_ledger import EvidenceLedger


def _atom(identity="provider-identity", **changes):
    return AgentEvidence(
        **dict(dict(
            tool="finance_query", title="原始观察", detail="原文不截断\n" * 500,
            source="公告", internal_locator="private://original/observation",
            source_date="2026-07-24", evidence_tier="L3", supports=("direct",),
            contradicts=("counter",), independent_key="issuer", freshness="current",
            content_hash=identity,
            observations=(StructuredObservation("公司", "2026-07-24", "营收亿元", 12.5),),
            derived_from=("prior-input",), reexcerpted=True, pointer_dropped=2,
            structural_neighbor_demoted=1, deep_read=True,
            publisher_kind="company", document_type="announcement",
        ), **changes)
    )


def _fixture():
    ledger = EvidenceLedger(information_cutoff=date(2026, 7, 24))
    first, second = _atom("first"), _atom("second", source_date=None, observations=())
    # Arrival order is NOT necessarily the parent's model-visible order.
    ledger.branch_sink("invocation:child-2").append(second)
    ledger.append(first, covered_outputs=("direct",), open_gaps=("verify",))
    ledger.mark_output_covered("comparison", evidence_ids=("second",))
    ledger.open_gap("not-covered")
    presented = (first, second)
    payload = snapshots.capture_evidence_snapshot(
        episode_id="episode", ledger=ledger, presented_evidence=presented,
    )
    return ledger, presented, payload


def _resign(payload):
    # A digest is an integrity check, not a substitute for semantic validation.
    body = {k: v for k, v in payload.items() if k != "sha256"}
    payload["sha256"] = hashlib.sha256(json.dumps(
        body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest()


def _legacy_payload(payload, version):
    """Reproduce old wire shapes: v4 predates retrieval direction, v3 also
    predates history provenance, v1/v2 also predate IO provenance."""
    payload = deepcopy(payload)
    payload["schema_version"] = version
    for entry in (*payload["entries"], *payload.get("presentations", ())):
        entry["atom"].pop("retrieval_direction")
        if version < 4:
            entry["atom"].pop("history_provenance")
        if version < 3:
            entry["atom"].pop("io_effect")
    if version == 1:
        payload["presented_hashes"] = [
            item["atom"]["content_hash"] for item in payload.pop("presentations")
        ]
    _resign(payload)
    return payload


def test_full_private_roundtrip_keeps_atoms_coverage_owners_and_distinct_citation_order():
    ledger, presented, payload = _fixture()
    payload = json.loads(json.dumps(payload, allow_nan=False))
    snapshot = snapshots.EpisodeEvidenceSnapshot.from_dict(payload, episode_id="episode")
    restored = EvidenceLedger.from_recovery_snapshot(payload, episode_id="episode")
    assert restored.items() == ledger.items()
    assert restored.snapshot() == ledger.snapshot()
    assert snapshot.presented_evidence == presented
    assert resolve_evidence_refs(["E1", "E2"], snapshot.presented_evidence) == ("first", "second")
    assert evidence_ordinal_table(restored.items()) != evidence_ordinal_table(snapshot.presented_evidence)
    assert snapshot.to_dict() == payload
    assert restored.to_recovery_snapshot(episode_id="episode", presented_evidence=presented) == payload
    assert set(payload["entries"][0]["atom"]) == {f.name for f in fields(AgentEvidence)}
    assert asdict(snapshot.presented_evidence[0]) == asdict(presented[0])
    assert "internal_locator" not in public_agent_evidence(snapshot.presented_evidence[0])
    assert "observations" not in public_agent_evidence(snapshot.presented_evidence[0])
    assert restored.append(replace(presented[0], detail="later replacement")) == ()
    assert restored.items()[1].detail == presented[0].detail  # first writer wins
    restored.append(_atom("third"))
    assert len(ledger.items()) == 2  # not an alias of the source ledger


@pytest.mark.parametrize("direction", [None, "support", "counter"])
def test_retrieval_direction_checkpoint_preserves_original_identity_and_targets(direction):
    original = _atom(contradicts=(), derived_from=())
    labelled = replace(original, retrieval_direction=direction)
    ledger = EvidenceLedger(information_cutoff=date(2026, 7, 24))
    ledger.append(labelled)
    payload = snapshots.capture_evidence_snapshot(
        episode_id="episode", ledger=ledger, presented_evidence=(labelled,),
    )

    assert payload["schema_version"] == 5
    assert payload["entries"][0]["atom"]["retrieval_direction"] == direction
    restored = EvidenceLedger.from_recovery_snapshot(payload, episode_id="episode")
    snapshot = snapshots.EpisodeEvidenceSnapshot.from_dict(payload, episode_id="episode")
    assert restored.items() == snapshot.presented_evidence == (labelled,)
    assert snapshot.to_dict() == payload
    assert snapshot.presented_evidence[0].to_observation("E1") == original.to_observation("E1")
    assert resolve_evidence_refs(["E1"], snapshot.presented_evidence) == ("provider-identity",)
    assert restored.snapshot().evidence_targets == (("provider-identity", ("direct",)),)


@pytest.mark.parametrize("location", ["entries", "presentations"])
@pytest.mark.parametrize("direction", [False, 1, [], {}, "", "conclusion", "support "])
def test_checkpoint_rejects_invalid_retrieval_directions(location, direction):
    _, _, payload = _fixture()
    payload[location][0]["atom"]["retrieval_direction"] = direction
    _resign(payload)
    with pytest.raises(ValueError, match="invalid evidence retrieval direction"):
        snapshots.EpisodeEvidenceSnapshot.from_dict(payload, episode_id="episode")


@pytest.mark.parametrize("version", [1, 2, 3, 4])
@pytest.mark.parametrize("direction", ["support", "counter"])
def test_nonempty_retrieval_direction_cannot_be_silently_exported_to_old_versions(version, direction):
    atom = _atom(retrieval_direction=direction)
    ledger = EvidenceLedger()
    ledger.append(atom)
    payload = ledger.to_recovery_snapshot(episode_id="episode", presented_evidence=(atom,))
    snapshot = snapshots.EpisodeEvidenceSnapshot.from_dict(payload, episode_id="episode")
    with pytest.raises(ValueError, match="cannot preserve retrieval direction"):
        replace(snapshot, schema_version=version).to_dict()


@pytest.mark.parametrize("version", [1, 2, 3, 4])
@pytest.mark.parametrize("field", ["retrieval_direction", "unknown_field"])
def test_old_snapshot_schema_does_not_acquire_new_fields_by_default(version, field):
    _, _, payload = _fixture()
    old = _legacy_payload(payload, version)
    old["entries"][0]["atom"][field] = None
    _resign(old)
    with pytest.raises(ValueError, match="atom fields are incomplete or unknown"):
        snapshots.EpisodeEvidenceSnapshot.from_dict(old, episode_id="episode")


def test_snapshot_digest_binds_retrieval_direction_without_changing_content_hash():
    _, _, payload = _fixture()
    payload["presentations"][0]["atom"]["retrieval_direction"] = "counter"
    with pytest.raises(ValueError, match="digest mismatch"):
        snapshots.EpisodeEvidenceSnapshot.from_dict(payload, episode_id="episode")


def test_restored_ledger_keeps_cutoff_gate_and_duplicate_owner_first_writer():
    _, presented, payload = _fixture()
    restored = EvidenceLedger.from_recovery_snapshot(payload, episode_id="episode")
    assert restored.branch_sink("wrong-owner").append(presented[1]) == ()
    assert dict(restored.snapshot().evidence_branch_owners) == {"second": "invocation:child-2"}
    assert restored.append(_atom("future", source_date="2026-07-25")) == ()
    assert restored.append(_atom("bad-date", source_date="not-a-date")) == ()
    assert restored.append(_atom("new")) == ("new",)
    decoded = snapshots.EpisodeEvidenceSnapshot.from_dict(
        restored.to_recovery_snapshot(episode_id="episode", presented_evidence=(*presented, _atom("new"))),
        episode_id="episode",
    )
    assert resolve_evidence_refs(["E1", "E2", "E3"], decoded.presented_evidence) == ("first", "second", "new")


@pytest.mark.parametrize(("path", "value"), [
    (("schema_version",), True), (("schema_version",), 6), (("kind",), "public_evidence"),
    # A partial or non-record provenance must not restore as an ordinary card.
    (("entries", 0, "atom", "history_provenance"), {"query_id": "forged"}),
    (("entries", 0, "atom", "history_provenance"), "run/history-query-forged.json"),
    (("episode_id",), "other"), (("information_cutoff",), "2026-99-99"),
    (("entries", 0, "atom", "source_date"), "2026-07-25"),
    (("entries", 0, "atom", "source_date"), "unknown"),
    (("entries", 0, "atom", "detail"), None),
    (("entries", 0, "atom", "content_hash"), " spaced "),
    (("entries", 0, "atom", "supports"), [False]),
    (("entries", 0, "atom", "observations"), [{"subject": "a", "as_of": "2026-07-24", "metric": "x", "value": True}]),
    (("entries", 0, "atom", "observations"), [{"subject": "a", "as_of": "2026-07-24", "metric": "x", "value": 1, "extra": "bad"}]),
    (("entries", 0, "atom", "pointer_dropped"), -1),
    (("entries", 0, "atom", "structural_neighbor_demoted"), True),
    (("entries", 0, "atom", "reexcerpted"), 1),
    (("entries", 0, "atom", "deep_read"), "false"),
    (("entries", 0, "targets"), []),
    (("entries", 0, "targets"), ["direct", "direct"]),
    (("entries", 0, "branch_owner"), ""),
    (("entries", 0, "cutoff_status"), "verified"),
    (("presentations", 0, "atom", "content_hash"), "missing"),
    (("presentations", 1, "atom", "content_hash"), "first"),
    (("covered_outputs",), ["not-targeted"]), (("open_gaps",), [" duplicate "]),
    (("unexpected",), True),
])
def test_semantically_invalid_snapshot_is_rejected_even_with_recomputed_digest(path, value):
    _, _, payload = _fixture()
    node = payload
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    _resign(payload)
    with pytest.raises(ValueError):
        snapshots.EpisodeEvidenceSnapshot.from_dict(payload, episode_id="episode")


@pytest.mark.parametrize("path", [
    ("entries",), ("presentations",), ("information_cutoff",),
    ("entries", 0, "branch_owner"), ("entries", 0, "cutoff_status"),
    ("entries", 0, "atom", "observations"), ("entries", 0, "atom", "source_date"),
    ("entries", 0, "atom", "derived_from"), ("entries", 0, "atom", "internal_locator"),
    ("entries", 0, "atom", "history_provenance"),
    ("entries", 0, "atom", "retrieval_direction"),
])
def test_missing_fields_are_not_filled_from_public_projection_or_defaults(path):
    _, _, payload = _fixture()
    node = payload
    for key in path[:-1]:
        node = node[key]
    del node[path[-1]]
    _resign(payload)
    with pytest.raises(ValueError):
        snapshots.EpisodeEvidenceSnapshot.from_dict(payload, episode_id="episode")


def test_digest_binds_body_not_just_provider_content_hash_and_rejects_duplicate_atoms():
    _, _, payload = _fixture()
    changed = deepcopy(payload)
    changed["entries"][0]["atom"]["detail"] = "changed original"
    with pytest.raises(ValueError, match="digest"):
        snapshots.EpisodeEvidenceSnapshot.from_dict(changed, episode_id="episode")
    changed = deepcopy(payload)
    changed["entries"].append(deepcopy(changed["entries"][0]))
    _resign(changed)
    with pytest.raises(ValueError):
        snapshots.EpisodeEvidenceSnapshot.from_dict(changed, episode_id="episode")


@pytest.mark.parametrize("value", [float("nan"), float("inf"), 10 ** 400])
def test_structured_observation_numbers_must_be_finite_and_never_coerced(value):
    ledger = EvidenceLedger()
    item = _atom(observations=(StructuredObservation("a", "2026-07-24", "x", value),))
    ledger.append(item)
    with pytest.raises(ValueError):
        snapshots.capture_evidence_snapshot(episode_id="episode", ledger=ledger, presented_evidence=(item,))


def test_capture_refuses_hash_collision_or_unadmitted_presented_atom():
    ledger, presented, _ = _fixture()
    for items in ((replace(presented[0], detail="different atom"),), (_atom("missing"),)):
        with pytest.raises(ValueError):
            snapshots.capture_evidence_snapshot(episode_id="episode", ledger=ledger, presented_evidence=items)


def test_checkpoint_is_deeply_frozen_detached_and_keeps_capture_prefix():
    _, _, payload = _fixture()
    state = EpisodeState(episode_id="episode", phase="planning", last_sequence=7,
                         evidence_snapshot=payload, evidence_snapshot_sequence=5)
    original = state.to_dict()
    payload["entries"][0]["atom"]["detail"] = "mutated caller"
    with pytest.raises(TypeError):
        state.evidence_snapshot["entries"][0]["atom"]["detail"] = "mutated frozen state"
    exported = state.to_dict()
    exported["evidence_snapshot"]["entries"][0]["targets"].append("mutated export")
    assert state.to_dict() == original
    assert EpisodeState.from_dict(original).to_dict() == original
    assert state.evidence_snapshot_sequence == 5


@pytest.mark.parametrize("sequence", [None, True, -1, 8, 1.5])
def test_snapshot_capture_position_must_belong_to_checkpoint_prefix(sequence):
    _, _, payload = _fixture()
    with pytest.raises(ValueError):
        EpisodeState(episode_id="episode", phase="planning", last_sequence=7,
                     evidence_snapshot=payload, evidence_snapshot_sequence=sequence)
    with pytest.raises(ValueError):
        EpisodeState(episode_id="episode", phase="planning", evidence_snapshot_sequence=1)


def test_legacy_checkpoint_stays_diagnostic_not_fabricated_empty_evidence():
    state = EpisodeState.from_dict({"episode_id": "episode", "phase": "planning", "log_version": 1})
    assert state.evidence_snapshot is None and state.evidence_snapshot_sequence is None


def test_loop_checkpoints_capture_received_full_atoms_not_the_public_event_projection(tmp_path):
    from intelligence.runtime.agent_episode import ContinuousAgentEpisode
    from intelligence.services.episode_store import JsonlEpisodeStore
    from intelligence.services.provider_observability import ProviderTrace
    from intelligence.services.research_tool_registry import ResearchToolRegistry
    from intelligence.tests.conformance.races._drive import build_rig

    rig = build_rig(f"evidence-{uuid4().hex}")
    item = _atom("runtime-evidence")
    spec = replace(rig.registry.resolve("market_data"), runner=lambda *_: (
        [item], "观察值", ProviderTrace(provider="test", capability="market_data", status="success"),
    ))
    rig.registry = ResearchToolRegistry((spec,))
    store = JsonlEpisodeStore(tmp_path)
    rig.episode = ContinuousAgentEpisode(rig.model, is_cancelled=rig.signal, store=store)
    rig.start()
    rig.run_until("model_pending")
    _, initial = store.load(rig.task_id)
    assert initial.evidence_snapshot is not None
    assert snapshots.EpisodeEvidenceSnapshot.from_dict(initial.evidence_snapshot, episode_id=rig.task_id).presented_evidence == ()
    rig.run_until("tools_settled")
    # Step itself precedes the next checkpoint: do not label old capture as reconciled.
    _, before = store.load(rig.task_id)
    assert snapshots.EpisodeEvidenceSnapshot.from_dict(before.evidence_snapshot, episode_id=rig.task_id).presented_evidence == ()
    rig.run_until("model_pending")
    events, state = store.load(rig.task_id)
    decoded = snapshots.EpisodeEvidenceSnapshot.from_dict(state.evidence_snapshot, episode_id=rig.task_id)
    assert decoded.presented_evidence == (item,)
    assert state.evidence_snapshot_sequence == state.last_sequence
    public = next(e.payload for e in events if e.kind == "tool_result")["evidence"][0]
    assert "observations" not in public and "internal_locator" not in public
    assert decoded.presented_evidence[0].internal_locator == item.internal_locator
    rig.finish()
    _, done = store.load(rig.task_id)
    assert snapshots.EpisodeEvidenceSnapshot.from_dict(done.evidence_snapshot, episode_id=rig.task_id).presented_evidence == (item,)


@pytest.mark.parametrize("expired", [False, True])
@pytest.mark.parametrize("version", [1, 2, 3])
def test_restore_keeps_original_capture_position_when_synthesizing_settlements(tmp_path, expired, version):
    from datetime import datetime, timedelta
    from intelligence.runtime.agent_episode import ContinuousAgentEpisode
    from intelligence.services.episode_restore import restore_episode
    from intelligence.services.episode_store import JsonlEpisodeStore
    from intelligence.tests.conformance.races._drive import build_rig

    rig = build_rig(f"evidence-prefix-{uuid4().hex}")
    live = JsonlEpisodeStore(tmp_path / "live")
    rig.episode = ContinuousAgentEpisode(rig.model, is_cancelled=rig.signal, store=live)
    rig.start()
    rig.run_until("tools_settled")
    rig.run_until("model_pending")
    events, checkpoint = live.load(rig.task_id)
    assert checkpoint.evidence_snapshot["presentations"]
    if version < 4:
        payload = _legacy_payload(checkpoint.to_dict()["evidence_snapshot"], version)
        checkpoint = replace(checkpoint, evidence_snapshot=payload)
    # Retry=0 exercises synthetic model_error -> finalizing, not just a readonly plan.
    checkpoint = replace(checkpoint, retry={"remaining": 0})
    rig.finish()
    crash = JsonlEpisodeStore(tmp_path / "crash")
    crash.append(rig.task_id, events, sync=True)
    crash.put_state(rig.task_id, checkpoint)
    result = restore_episode(rig.task_id, crash, context=rig.context, registry=rig.registry,
                             now=datetime.fromisoformat(checkpoint.deadline_at) + timedelta(seconds=1 if expired else -1))
    assert result.disposition == ("closed" if expired else "resumable")
    assert result.synthesized
    assert result.state_after.evidence_snapshot == checkpoint.evidence_snapshot
    assert result.state_after.evidence_snapshot_sequence == checkpoint.last_sequence < result.state_after.last_sequence
    assert crash.load(rig.task_id)[1].evidence_snapshot == checkpoint.evidence_snapshot
    # Closure is still a control-plane result; no reconstructed answer is broadcast.
    if expired:
        assert result.outcome.draft == "" and result.outcome.evidence == ()


@pytest.mark.parametrize("expired", [False, True])
@pytest.mark.parametrize("missing", [True, False])
def test_nonterminal_restore_refuses_missing_snapshot_or_cutoff_drift_without_writes(tmp_path, expired, missing):
    from datetime import datetime, timedelta
    from intelligence.runtime.agent_episode import ContinuousAgentEpisode
    from intelligence.services.episode_restore import RestoreUnavailable, restore_episode
    from intelligence.services.episode_store import JsonlEpisodeStore
    from intelligence.tests.conformance.races._drive import build_rig

    rig = build_rig(f"evidence-gate-{uuid4().hex}")
    live = JsonlEpisodeStore(tmp_path / "live")
    rig.episode = ContinuousAgentEpisode(rig.model, is_cancelled=rig.signal, store=live)
    rig.start()
    rig.run_until("model_pending")
    events, checkpoint = live.load(rig.task_id)
    rig.finish()
    if missing:
        checkpoint = replace(checkpoint, evidence_snapshot=None, evidence_snapshot_sequence=None)
    else:
        payload = checkpoint.to_dict()["evidence_snapshot"]
        payload["information_cutoff"] = "2026-07-23"
        _resign(payload)
        checkpoint = replace(checkpoint, evidence_snapshot=payload)
    crash = JsonlEpisodeStore(tmp_path / "crash")
    crash.append(rig.task_id, events, sync=True)
    crash.put_state(rig.task_id, checkpoint)
    before = crash.load(rig.task_id)
    with pytest.raises(RestoreUnavailable, match="evidence"):
        restore_episode(rig.task_id, crash, context=rig.context, registry=rig.registry,
                        now=datetime.fromisoformat(checkpoint.deadline_at) + timedelta(seconds=1 if expired else -1))
    assert crash.load(rig.task_id) == before


@pytest.mark.parametrize("boundary", ["planning", "tools_pending", "done"])
@pytest.mark.parametrize("failure", ["raise", "missing", "invalid"])
def test_required_evidence_encoding_failure_fences_tree_and_retains_received_results(tmp_path, monkeypatch, boundary, failure):
    from intelligence.runtime import agent_episode
    from intelligence.services.agent_runtime import EpisodeEvent
    from intelligence.services.episode_store import EpisodeStoreFailed, FencedEpisodeStore, JsonlEpisodeStore
    from intelligence.tests.conformance.races._drive import build_rig

    rig = build_rig(f"evidence-failure-{uuid4().hex}")
    raw = JsonlEpisodeStore(tmp_path)
    fence = FencedEpisodeStore(raw)
    rig.episode = agent_episode.ContinuousAgentEpisode(rig.model, is_cancelled=lambda: rig.signal.requested, store=fence)
    rig.start()
    if boundary == "tools_pending":
        rig.run_until("model_settled")
    elif boundary == "done":
        rig.run_until("before_finish")
    _, before = raw.load(rig.task_id)
    calls = rig.model.calls
    capture = agent_episode.capture_evidence_snapshot

    def fail(**kwargs):
        if failure == "raise":
            raise OSError("evidence encoding failed")
        if failure == "missing":
            return None
        payload = capture(**kwargs)
        payload["episode_id"] = "wrong-owner"
        _resign(payload)
        return payload

    monkeypatch.setattr(agent_episode, "capture_evidence_snapshot", fail)
    outcome = rig.finish()
    assert outcome.persistence == "failed" and outcome.stop_reason == "storage_failed"
    assert rig.model.calls == calls and outcome.usage.llm_calls == calls
    assert raw.load(rig.task_id)[1] == before
    assert fence.failure and not rig.signal.requested
    with pytest.raises(EpisodeStoreFailed):
        fence.append("sibling", (EpisodeEvent(1, "task", {}),), sync=True)
    assert raw.load("sibling") == ((), None)
    if boundary == "done":
        assert outcome.evidence and outcome.draft
    else:
        assert not outcome.evidence and outcome.usage.tool_calls == 0


def test_opening_prefetch_is_in_the_first_confirmed_checkpoint_before_model_dispatch(tmp_path):
    from intelligence.runtime.agent_episode import ContinuousAgentEpisode
    from intelligence.services.episode_store import JsonlEpisodeStore
    from intelligence.tests.conformance.races._drive import build_rig

    rig = build_rig(f"evidence-prefetch-{uuid4().hex}")
    item = _atom("prefetched")
    # Use the existing registry metadata path, copied by for_context/with_specs.
    from intelligence.services.research_tool_registry import ResearchToolRegistry
    rig.registry = ResearchToolRegistry((rig.registry.resolve("market_data"),), opening_prefetch=(item,))
    checkpoints = []

    class RecordingStore(JsonlEpisodeStore):
        def put_state(self, episode_id, state):
            super().put_state(episode_id, state)
            checkpoints.append(state)

    store = RecordingStore(tmp_path)
    rig.episode = ContinuousAgentEpisode(rig.model, is_cancelled=rig.signal, store=store)
    rig.start()
    rig.run_until("model_pending")
    snapshot = snapshots.EpisodeEvidenceSnapshot.from_dict(checkpoints[0].evidence_snapshot, episode_id=rig.task_id)
    assert checkpoints[0].phase == "planning" and rig.model.calls == 0
    assert snapshot.presented_evidence == (item,)
    assert resolve_evidence_refs(["E1"], snapshot.presented_evidence) == ("prefetched",)
    rig.finish()


@pytest.mark.parametrize("plan", [False, True])
def test_real_child_tree_keeps_parent_ownership_and_independent_child_evidence(tmp_path, plan):
    from intelligence.tests.test_sub_research_persistence import ObservedStore, run_tree

    store = ObservedStore(tmp_path)
    outcome, _, _, _, _ = run_tree(store, rounds=1, goals=("核验甲", "核验乙"), plan=plan)
    assert outcome.persistence == "durable"
    starts = [e for e in outcome.events if e.kind == "branch_started"]
    parent_id = starts[0].payload["episode_ref"]["parent_episode_id"]
    parent = store.load(parent_id)[1]
    parent_snapshot = snapshots.EpisodeEvidenceSnapshot.from_dict(parent.evidence_snapshot, episode_id=parent_id)
    assert parent_snapshot.presented_evidence == outcome.evidence
    owners = {entry.atom.content_hash: entry.branch_owner for entry in parent_snapshot.entries}
    assert set(owners.values()) == store.child_ids
    for child_id in store.child_ids:
        _, child = store.load(child_id)
        snapshot = snapshots.EpisodeEvidenceSnapshot.from_dict(child.evidence_snapshot, episode_id=child_id)
        assert snapshot.presented_evidence
        assert all(owners[item.content_hash] == child_id for item in snapshot.presented_evidence)
        assert all(entry.branch_owner is None for entry in snapshot.entries)
    assert len(parent_snapshot.entries) == 2


def test_unpresented_child_atom_has_no_citation_ordinal_until_parent_accepts_it():
    ledger, presented, _ = _fixture()
    extra = _atom("pending-child")
    ledger.branch_sink("child-pending").append(extra)
    snapshot = snapshots.EpisodeEvidenceSnapshot.from_dict(
        snapshots.capture_evidence_snapshot(episode_id="episode", ledger=ledger, presented_evidence=presented),
        episode_id="episode",
    )
    assert len(snapshot.entries) == 3 and len(snapshot.presented_evidence) == 2
    assert "pending-child" not in evidence_ordinal_table(snapshot.presented_evidence)


def test_concurrent_append_and_capture_never_mix_atom_and_owner_or_coverage():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    ledger = EvidenceLedger(information_cutoff=date(2026, 7, 24))
    barrier = Barrier(2)

    def append():
        barrier.wait(timeout=5)
        for index in range(60):
            ledger.branch_sink(f"child-{index}").append(_atom(f"e-{index}"))

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(append)
        barrier.wait(timeout=5)
        for _ in range(60):
            payload = snapshots.capture_evidence_snapshot(episode_id="episode", ledger=ledger, presented_evidence=())
            decoded = snapshots.EpisodeEvidenceSnapshot.from_dict(payload, episode_id="episode")
            assert all(entry.branch_owner == f"child-{index}" and entry.atom.content_hash == f"e-{index}"
                       for index, entry in enumerate(decoded.entries))
        future.result(timeout=10)
    assert len(ledger.items()) == 60


def test_repair_saves_fresh_evidence_while_retaining_old_citation_numbers(tmp_path):
    from intelligence.runtime.agent_episode import ContinuousAgentEpisode
    from intelligence.services.episode_store import JsonlEpisodeStore
    from intelligence.tests.test_agent_episode import (
        ScriptedModel, _frame, _context, _tool_turn, _finish_turn, _market_registry, _successful_runner,
    )
    from intelligence.tests.test_episode_session import _goal

    frame = _frame(("direct_assessment", "counterpoint"))
    context = _context(frame, max_steps=4)
    def runner(query, tool_context):
        evidence, observation, trace = _successful_runner(query, tool_context)
        if query == "反方证据":
            evidence = [replace(item, content_hash="repair-evidence") for item in evidence]
        return evidence, observation, trace

    registry = _market_registry(runner)
    store = JsonlEpisodeStore(tmp_path)
    model = ScriptedModel([
        _tool_turn("市场"), _finish_turn(status="partial", gap="缺少反方证据"),
        _tool_turn("反方证据", call_id="repair-call"), _finish_turn(status="partial", gap="仍待核验"),
    ])
    episode = ContinuousAgentEpisode(model, store=store)
    continuation = []
    previous = episode.run(task_frame=frame, context=context, registry=registry, _continuation_sink=continuation)
    first = store.load(context.contract.task_id)[1]
    repaired = episode.resume(continuation[0], previous, _goal(context.contract.task_id))
    assert previous.persistence == repaired.persistence == "durable"
    last = store.load(context.contract.task_id)[1]
    old = snapshots.EpisodeEvidenceSnapshot.from_dict(first.evidence_snapshot, episode_id=context.contract.task_id)
    fresh = snapshots.EpisodeEvidenceSnapshot.from_dict(last.evidence_snapshot, episode_id=context.contract.task_id)
    assert len(fresh.presented_evidence) == 2 and fresh.presented_evidence == repaired.evidence
    assert fresh.presented_evidence[:1] == old.presented_evidence
    assert resolve_evidence_refs(["E1"], fresh.presented_evidence) == old.presented_hashes
    assert last.evidence_snapshot_sequence > first.evidence_snapshot_sequence


@pytest.mark.parametrize("missing", ["ledger", "presentation", "cutoff"])
def test_missing_current_source_never_reuses_a_previous_evidence_snapshot(tmp_path, missing):
    from intelligence.runtime.agent_episode import _EpisodeLedger
    from intelligence.services.episode_store import FencedEpisodeStore, JsonlEpisodeStore
    from intelligence.tests.conformance.races._drive import build_rig

    rig = build_rig(f"evidence-source-{uuid4().hex}")
    raw = JsonlEpisodeStore(tmp_path)
    fence = FencedEpisodeStore(raw)
    ledger = _EpisodeLedger(rig.frame, episode_id=rig.task_id, store=fence)
    ledger.active_context, ledger.active_registry = rig.context, rig.registry
    ledger.active_evidence_ledger = EvidenceLedger(information_cutoff=rig.context.information_cutoff.as_of_date)
    ledger.presented_evidence = []
    ledger.put_state(phase="planning")
    assert not ledger.store_failures
    before = raw.load(rig.task_id)
    if missing == "ledger":
        ledger.active_evidence_ledger = None
    elif missing == "presentation":
        ledger.presented_evidence = None
    else:
        ledger.active_evidence_ledger = EvidenceLedger(information_cutoff=date(2026, 7, 23))
    ledger.put_state(phase="planning")
    assert ledger.store_failures and fence.failure
    assert raw.load(rig.task_id) == before


def test_unbounded_and_undated_evidence_stay_explicit_not_upgraded_on_roundtrip():
    ledger = EvidenceLedger()
    items = (_atom("dated"), _atom("undated", source_date=""))
    ledger.append(items)
    payload = ledger.to_recovery_snapshot(episode_id="episode", presented_evidence=items)
    restored = EvidenceLedger.from_recovery_snapshot(payload, episode_id="episode")
    assert restored.information_cutoff is None
    assert dict(restored.snapshot().evidence_cutoff_status) == {"dated": "unbounded", "undated": "undated"}
    assert restored.items() == items


def test_consistent_legacy_terminal_query_is_readonly_and_does_not_resend_evidence():
    from intelligence.services.agent_runtime import EpisodeEvent
    from intelligence.services.episode_restore import restore_episode
    from intelligence.services.episode_store import MemoryEpisodeStore

    store = MemoryEpisodeStore()
    store.append("episode", (EpisodeEvent(1, "task", {}), EpisodeEvent(2, "finish", {})), sync=True)
    store.put_state("episode", EpisodeState(episode_id="episode", phase="done", last_sequence=2))
    before = store.load("episode")
    result = restore_episode("episode", store)
    assert result.disposition == "already_terminal" and result.outcome is result.plan is None
    assert result.synthesized == () and store.load("episode") == before
