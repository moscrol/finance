"""Host-repaired effects probes derived from K3, with a wired budget mutant."""

from __future__ import annotations

from uuid import uuid4

import pytest

from intelligence.services.agent_runtime import EpisodeEvent
from intelligence.services.episode_effects import (
    UnknownEffect,
    charge_unknown_effects,
    unknown_effects_payload,
)
from intelligence.services.episode_store import EpisodeState, JsonlEpisodeStore
from k3_fixtures import NOW, budget_snapshot, budgets_module, dangling_model_episode

budget_mod = budgets_module()
release_root_budget = budget_mod.release_root_budget
restore_root_budget = budget_mod.restore_root_budget


def _model_effect(**overrides: object) -> UnknownEffect:
    base: dict[str, object] = {
        "effect": "model",
        "reserved_id": "turn-1",
        "intent_sequence": 2,
        "disposition": "settled_interrupted",
        "cost": "external",
        "io_effect": "external_or_mixed",
    }
    base.update(overrides)
    return UnknownEffect(**base)  # type: ignore[arg-type]


def test_charge_slots_only_never_negative_and_snapshotless_refuses() -> None:
    snap = budget_snapshot(f"k3-charge-{uuid4().hex[:8]}", calls=3)
    seconds_before = snap["remaining_seconds"]
    debited, receipt = charge_unknown_effects(
        snap, (_model_effect(), _model_effect(reserved_id="t9", intent_sequence=9))
    )
    assert receipt["slots_charged"] == 2 and receipt["slots_unavailable"] == 0
    assert debited["remaining_calls"] == 1
    assert debited["remaining_seconds"] == seconds_before  # never invent a time measurement
    assert snap["remaining_calls"] == 3  # pure function: caller's snapshot untouched

    overdrawn, receipt2 = charge_unknown_effects(
        debited,
        tuple(_model_effect(reserved_id=f"t{i}", intent_sequence=10 + i) for i in range(4)),
    )
    assert overdrawn["remaining_calls"] == 0
    assert receipt2["slots_unavailable"] == 3

    with pytest.raises(ValueError):
        charge_unknown_effects(None, (_model_effect(),))  # no ledger: refuse, never write off


def test_spend_gate_refuses_unreconciled_and_has_no_forgetful_default() -> None:
    episode = f"k3-gate-{uuid4().hex[:8]}"
    snap = budget_snapshot(episode, calls=3)
    effects = (_model_effect(),)
    with pytest.raises(ValueError, match="unreconciled"):
        restore_root_budget(
            snap, episode_id=episode, unreconciled_effects=unknown_effects_payload(effects)
        )
    with pytest.raises(TypeError):  # "forgot to pass" must not become "nothing owed"
        restore_root_budget(snap, episode_id=episode)  # type: ignore[call-arg]
    debited, _ = charge_unknown_effects(snap, effects)
    try:
        ledger = restore_root_budget(debited, episode_id=episode, unreconciled_effects=())
        assert ledger.remaining_calls == 2
    finally:
        release_root_budget(episode)


def test_restore_registers_the_window_once_and_never_spends_the_balance(tmp_path) -> None:
    import intelligence.services.episode_restore as restore_mod

    episode, store, context, registry = dangling_model_episode(tmp_path, retries=2, with_budget=True)
    first = restore_mod.restore_episode(episode, store, now=NOW, context=context, registry=registry)
    assert first.plan is not None and first.plan.action == "retry_model"
    assert [e.kind for e in first.synthesized] == ["effects_unknown"]
    assert len(first.unreconciled_effects) == 1
    effect = first.unreconciled_effects[0]
    assert effect.disposition == "retry_proposed"
    assert (effect.effect, effect.reserved_id) == ("model", "turn-1")

    for _ in range(3):
        again = restore_mod.restore_episode(episode, store, now=NOW, context=context, registry=registry)
        assert again.plan == first.plan
        assert again.synthesized == (), "repeated restores must not inflate the receipt list"
        assert len(again.unreconciled_effects) == 1

    # Cross-instance reread from disk: exactly one receipt persisted; restore did
    # NOT settle it (balance still at the pre-crash value - no charge smuggled in).
    reread = JsonlEpisodeStore(tmp_path).load(episode)[1]
    assert reread is not None
    assert len(reread.unreconciled_effects) == 1
    assert reread.budget_snapshot is not None and reread.budget_snapshot["remaining_calls"] == 3

    with pytest.raises(ValueError, match="unreconciled"):
        restore_root_budget(
            dict(reread.budget_snapshot),
            episode_id=episode,
            unreconciled_effects=list(reread.unreconciled_effects),
        )


def test_undeclared_application_call_is_settled_but_never_registered(tmp_path) -> None:
    """A declared-but-never-dispatched call never went out the door: it must be
    settled for history pairing, but must NOT enter the unknown-effects list."""
    from dataclasses import replace
    from datetime import timedelta

    import intelligence.services.episode_restore as restore_mod
    from intelligence.services.episode_authorization import capture_authorization_snapshot
    from intelligence.services.evidence_ledger import EvidenceLedger
    from intelligence.tests.conformance.fixtures import (
        ScenarioProbe,
        make_context,
        make_frame,
        make_registry,
    )

    episode = f"k3-app-{uuid4().hex[:8]}"
    context = make_context(make_frame(), task_id=episode)
    context = replace(context, contract=replace(context.contract, task_frame_hash="tf"))
    registry = make_registry(ScenarioProbe())
    evidence = EvidenceLedger(
        information_cutoff=context.information_cutoff.as_of_date
    ).to_recovery_snapshot(episode_id=episode, presented_evidence=())
    store = JsonlEpisodeStore(tmp_path)
    store.append(
        episode,
        (
            EpisodeEvent(1, "task", {"task_frame_hash": "tf"}),
            EpisodeEvent(2, "model_intent", {"turn_id": "turn-1"}),
            EpisodeEvent(3, "model_turn", {"turn_id": "turn-1", "tool_calls": (), "finish_reason": "stop"}),
            EpisodeEvent(4, "application_tool_call", {"call_id": "c-app", "name": "market_data"}),
        ),
        sync=True,
    )
    store.put_state(
        episode,
        EpisodeState(
            episode_id=episode, phase="planning", reserved_ids=(),
            deadline_at=(NOW + timedelta(minutes=2)).isoformat(), retry={"remaining": 1},
            last_sequence=4,
            authorization_snapshot=capture_authorization_snapshot(context, registry),
            evidence_snapshot=evidence, evidence_snapshot_sequence=4,
        ),
    )
    result = restore_mod.restore_episode(episode, store, now=NOW, context=context, registry=registry)
    kinds = [e.kind for e in result.synthesized]
    assert kinds == ["tool_error"], f"declaration must be settled exactly once, got {kinds}"
    assert result.synthesized[0].payload["error"] == "interrupted"
    assert "never dispatched" in result.synthesized[0].payload["detail"]
    assert result.unreconciled_effects == (), "undispatched declarations are not unknown effects"


def test_tool_window_records_disposition_and_unknown_specs_fail_closed(tmp_path) -> None:
    from dataclasses import replace
    from datetime import timedelta

    import intelligence.services.episode_restore as restore_mod
    from intelligence.services.episode_authorization import capture_authorization_snapshot
    from intelligence.services.evidence_ledger import EvidenceLedger
    from intelligence.tests.conformance.fixtures import (
        ScenarioProbe,
        make_context,
        make_frame,
        make_registry,
    )

    def build(tool_name: str, declared_replay: str, label: str):
        episode = f"k3-tool-{label}-{uuid4().hex[:8]}"
        context = make_context(make_frame(), task_id=episode)
        context = replace(context, contract=replace(context.contract, task_frame_hash="tf"))
        registry = make_registry(ScenarioProbe())
        evidence = EvidenceLedger(
            information_cutoff=context.information_cutoff.as_of_date
        ).to_recovery_snapshot(episode_id=episode, presented_evidence=())
        store = JsonlEpisodeStore(tmp_path / label)
        store.append(
            episode,
            (
                EpisodeEvent(1, "task", {"task_frame_hash": "tf"}),
                EpisodeEvent(2, "model_intent", {"turn_id": "turn-1"}),
                EpisodeEvent(3, "model_turn", {"turn_id": "turn-1", "tool_calls": ({"call_id": "c1", "name": tool_name},), "finish_reason": "tool_calls"}),
                EpisodeEvent(4, "tool_request", {"call_id": "c1", "name": tool_name, "replay": declared_replay}),
            ),
            sync=True,
        )
        store.put_state(
            episode,
            EpisodeState(
                episode_id=episode, phase="tools_pending", reserved_ids=("c1",),
                deadline_at=(NOW + timedelta(minutes=2)).isoformat(), retry={"remaining": 1},
                last_sequence=4,
                authorization_snapshot=capture_authorization_snapshot(context, registry),
                evidence_snapshot=evidence, evidence_snapshot_sequence=4,
            ),
        )
        return episode, store, context, registry

    # (1) Registry cannot resolve the tool: cost fails closed to "unknown".
    ep1, st1, cx1, rg1 = build("no_such_tool", "safe", "unknown")
    r1 = restore_mod.restore_episode(ep1, st1, now=NOW, context=cx1, registry=rg1)
    assert len(r1.unreconciled_effects) == 1
    e1 = r1.unreconciled_effects[0]
    assert e1.effect == "tool" and e1.disposition == "settled_interrupted"
    assert e1.cost == "unknown" and e1.io_effect == "unknown"
    assert e1.may_have_been_billed is True

    # (2) replay=safe is an idempotence claim, not a cost claim: even when a replay
    # is proposed, the window is STILL registered first.
    ep2, st2, cx2, rg2 = build("market_data", "safe", "replay")
    r2 = restore_mod.restore_episode(ep2, st2, now=NOW, context=cx2, registry=rg2)
    assert len(r2.unreconciled_effects) == 1
    e2 = r2.unreconciled_effects[0]
    assert [e.kind for e in r2.synthesized][0] == "effects_unknown"
    if r2.plan is not None and r2.plan.action == "replay_tools":
        assert e2.disposition == "replay_proposed"
    else:
        assert e2.disposition == "settled_interrupted"
