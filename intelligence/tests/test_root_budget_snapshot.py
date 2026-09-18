"""Recovery budget snapshots keep debits and dedup IDs; they do not authorize replay."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from threading import Barrier
from uuid import uuid4

import pytest

from intelligence.services import research_contract as budgets
from intelligence.services.agent_runtime import EpisodeEvent
from intelligence.services.episode_restore import restore_episode
from intelligence.services.episode_store import EpisodeState, JsonlEpisodeStore
from intelligence.services.repair_coordinator import BudgetGrant
from intelligence.services.research_contract import (
    InMemoryRootBudgetLedger, ResearchPolicy, release_root_budget, root_budget_for_policy,
)


def _funded(episode_id):
    root = InMemoryRootBudgetLedger(
        episode_id=episode_id, initial_calls=3, hard_calls_cap=6,
        initial_seconds=20.0, hard_seconds_cap=40.0,
    )
    root.consume_call(seconds=2.5)
    grant = BudgetGrant("repair-1", episode_id, 1, 1, 5.0)
    assert root.grant(grant)
    assert root.promote_caps(
        episode_id=episode_id, promotion_id="deep-1", hard_calls_cap=10, hard_seconds_cap=80.0,
    )
    root.consume_call_slot()
    root.consume_seconds(seconds=3.0)
    return root, grant


def test_snapshot_round_trip_keeps_debits_and_applied_grant_and_promotion_ids():
    episode = f"snapshot-{uuid4().hex}"
    root, grant = _funded(episode)
    payload = json.loads(json.dumps(root.to_snapshot(), allow_nan=False))
    # The model-facing diagnostic summary must not acquire recovery-only identities.
    assert "grants" not in root.to_dict() and "schema_version" not in root.to_dict()
    restored = budgets.restore_root_budget(payload, episode_id=episode)
    try:
        assert restored.to_dict() == root.to_dict()
        assert restored.remaining_calls == 2 and restored.remaining_seconds == 19.5
        assert restored.allocated_calls == 4 and restored.allocated_seconds == 25.0
        before = restored.to_snapshot()
        assert not restored.grant(grant)  # spare headroom exists; identity is the guard
        assert restored.promote_caps(
            episode_id=episode, promotion_id="deep-1", hard_calls_cap=10, hard_seconds_cap=80.0,
        )
        assert not restored.promote_caps(
            episode_id=episode, promotion_id="deep-1", hard_calls_cap=12, hard_seconds_cap=90.0,
        )
        assert restored.to_snapshot() == before
        assert restored.grant(BudgetGrant("repair-2", episode, 2, 1, 2.0))
        assert restored.remaining_calls == 3 and restored.remaining_seconds == 21.5
        payload["grants"]["repair-1"]["calls_granted"] = 99
        payload["promotions"]["deep-1"]["hard_calls_cap"] = 99
        assert restored.to_snapshot()["grants"]["repair-1"]["calls_granted"] == 1
        assert restored.to_snapshot()["promotions"]["deep-1"]["hard_calls_cap"] == 10
        assert root.remaining_calls == 2  # no alias to the old ledger
    finally:
        release_root_budget(episode)


@pytest.mark.parametrize(("field", "value"), [
    ("schema_version", 2), ("schema_version", True), ("kind", "branch_budget"),
    ("episode_id", "other"), ("remaining_calls", -1), ("remaining_calls", 5),
    ("initial_calls", True), ("remaining_calls", 1.5),
    ("remaining_seconds", float("nan")), ("remaining_seconds", float("inf")),
    ("remaining_seconds", -1.0), ("remaining_seconds", 26.0),
    ("allocated_calls", 5), ("allocated_seconds", 30.0),
    ("hard_calls_cap", 3), ("hard_seconds_cap", 24.0),
    ("grants", []), ("grants", {}), ("grants", {"": {"calls_granted": 1, "seconds_granted": 5.0}}),
    ("promotions", {}), ("initial_hard_calls_cap", 2),
    ("initial_hard_seconds_cap", 19.0),
    ("promotions", {"deep-1": {"hard_calls_cap": 12, "hard_seconds_cap": 90.0}}),
    ("grants", {"repair-1": {"calls_granted": True, "seconds_granted": 5.0}}),
    ("grants", {"repair-1": {"calls_granted": 1, "seconds_granted": 0.0}}),
    ("grants", {"repair-1": {"calls_granted": 1, "seconds_granted": float("nan")}}),
    ("promotions", {"deep-1": {"hard_calls_cap": 10, "hard_seconds_cap": float("inf")}}),
    ("promotions", {"deep-1": {"hard_calls_cap": 10, "hard_seconds_cap": 80.0},
                    "crossed": {"hard_calls_cap": 8, "hard_seconds_cap": 85.0}}),
    ("unexpected", True),
])
def test_invalid_snapshot_never_registers_a_live_budget(field, value):
    episode = f"snapshot-invalid-{uuid4().hex}"
    root, _ = _funded(episode)
    payload = root.to_snapshot()
    payload[field] = value
    try:
        with pytest.raises(ValueError):
            budgets.restore_root_budget(payload, episode_id=episode)
        # Rejected input must not poison the existing single-root registration gate.
        fresh = root_budget_for_policy(ResearchPolicy("quick", 2, 30, 10), episode_id=episode)
        assert fresh.remaining_calls == 2
    finally:
        release_root_budget(episode)


def test_legacy_summary_or_missing_dedup_records_cannot_be_upgraded_by_guessing():
    episode = f"snapshot-legacy-{uuid4().hex}"
    root, _ = _funded(episode)
    for payload in (root.to_dict(), {k: v for k, v in root.to_snapshot().items() if k != "promotions"}):
        with pytest.raises(ValueError):
            budgets.restore_root_budget(payload, episode_id=episode)
    with pytest.raises(ValueError):
        budgets.restore_root_budget(root.to_snapshot(), episode_id="different-owner")


def test_restore_and_fresh_allocation_share_the_same_single_root_gate():
    episode = f"snapshot-live-{uuid4().hex}"
    root, _ = _funded(episode)
    existing = root_budget_for_policy(ResearchPolicy("quick", 2, 30, 10), episode_id=episode)
    try:
        with pytest.raises(ValueError, match="already exists"):
            budgets.restore_root_budget(root.to_snapshot(), episode_id=episode)
        assert existing.remaining_calls == 2
    finally:
        release_root_budget(episode)
    restored = budgets.restore_root_budget(root.to_snapshot(), episode_id=episode)
    try:
        with pytest.raises(ValueError, match="already exists"):
            root_budget_for_policy(ResearchPolicy("quick", 2, 30, 10), episode_id=episode)
        assert restored.remaining_calls == 2
    finally:
        release_root_budget(episode)


def test_two_concurrent_restores_cannot_create_two_registered_roots():
    episode = f"snapshot-race-{uuid4().hex}"
    root, _ = _funded(episode)
    payload = root.to_snapshot()
    barrier = Barrier(2)

    def restore():
        barrier.wait(timeout=5)
        try:
            return budgets.restore_root_budget(payload, episode_id=episode)
        except ValueError as exc:
            return exc

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(restore) for _ in range(2)]
            results = [f.result(timeout=5) for f in futures]
        assert sum(isinstance(r, InMemoryRootBudgetLedger) for r in results) == 1
        assert sum(isinstance(r, ValueError) and "already exists" in str(r) for r in results) == 1
    finally:
        release_root_budget(episode)


def test_real_loop_checkpoints_current_budget_not_just_initial_configuration(tmp_path):
    from intelligence.tests.conformance.races._drive import build_rig

    episode = f"snapshot-loop-{uuid4().hex}"
    root, _ = _funded(episode)
    rig = build_rig(episode)
    rig.context = replace(rig.context, root_budget=root)
    store = JsonlEpisodeStore(tmp_path)
    from intelligence.runtime.agent_episode import ContinuousAgentEpisode
    rig.episode = ContinuousAgentEpisode(rig.model, is_cancelled=rig.signal, store=store)
    rig.start()
    assert rig.run_until("model_pending") is not None
    _, first = store.load(episode)
    assert first.budget_snapshot == root.to_snapshot()
    assert first.budget_snapshot_sequence == first.last_sequence
    before = deepcopy(first.to_dict()["budget_snapshot"])
    assert root.grant(BudgetGrant("repair-between-turns", episode, 2, 1, 3.0))
    outcome = rig.finish()
    assert outcome.persistence == "durable"
    _, done = JsonlEpisodeStore(tmp_path).load(episode)
    assert done.terminal and done.budget_snapshot == root.to_snapshot()
    assert done.budget_snapshot_sequence == done.last_sequence
    assert done.budget_snapshot["remaining_calls"] == 2  # two spent before, one new tool
    assert first.to_dict()["budget_snapshot"] == before
    assert "repair-between-turns" not in first.budget_snapshot["grants"]
    assert "repair-between-turns" in done.budget_snapshot["grants"]


@pytest.mark.parametrize("expired", [False, True])
def test_restore_synthesis_preserves_snapshot_without_registering_or_resetting_budget(tmp_path, expired):
    episode = f"snapshot-synthesis-{uuid4().hex}"
    root, _ = _funded(episode)
    now = datetime(2026, 9, 18, tzinfo=timezone.utc)
    store = JsonlEpisodeStore(tmp_path)
    events = (
        EpisodeEvent(1, "task", {"task_frame_hash": "tf"}),
        EpisodeEvent(2, "model_intent", {"turn_id": "turn-1"}),
    )
    store.append(episode, events, sync=True)
    state = EpisodeState(
        episode_id=episode, phase="model_pending", reserved_ids=("turn-1",),
        deadline_at=(now + timedelta(minutes=2)).isoformat(), retry={"remaining": 0},
        last_sequence=2, budget_snapshot=root.to_snapshot(), budget_snapshot_sequence=2,
    )
    store.put_state(episode, state)
    result = restore_episode(episode, store, now=now + timedelta(hours=1) if expired else now)
    assert result.disposition == ("closed" if expired else "resumable")
    assert result.state_after.budget_snapshot == state.budget_snapshot
    assert result.state_after.budget_snapshot_sequence == 2 < result.state_after.last_sequence
    assert JsonlEpisodeStore(tmp_path).load(episode)[1].budget_snapshot == state.budget_snapshot
    try:
        restored = budgets.restore_root_budget(result.state_after.budget_snapshot, episode_id=episode)
        assert restored.remaining_calls == 2 and restored.remaining_seconds == 19.5
    finally:
        release_root_budget(episode)


@pytest.mark.parametrize("boundary", ["planning", "tools_pending", "done"])
@pytest.mark.parametrize("failure", ["raise", "invalid", "owner", "missing"])
def test_snapshot_failure_fences_tree_before_more_effects_and_keeps_received_result(tmp_path, boundary, failure):
    from intelligence.runtime.agent_episode import ContinuousAgentEpisode
    from intelligence.services.episode_store import FencedEpisodeStore, EpisodeStoreFailed
    from intelligence.tests.conformance.races._drive import build_rig

    episode = f"snapshot-failed-{uuid4().hex}"
    root, _ = _funded(episode)
    rig = build_rig(episode)
    rig.context = replace(rig.context, root_budget=root)
    raw = JsonlEpisodeStore(tmp_path)
    fence = FencedEpisodeStore(raw)
    rig.episode = ContinuousAgentEpisode(rig.model, is_cancelled=lambda: rig.signal.requested, store=fence)
    rig.start()
    if boundary == "tools_pending":
        assert rig.run_until("model_settled") is not None
    elif boundary == "done":
        assert rig.run_until("before_finish") is not None
    prefix = raw.load(episode)
    model_calls = rig.model.calls
    snapshot = root.to_snapshot()

    def broken_snapshot():
        if failure == "raise":
            raise OSError("snapshot encoding failed")
        if failure == "missing":
            return None
        result = deepcopy(snapshot)
        result["remaining_calls" if failure == "invalid" else "episode_id"] = -1 if failure == "invalid" else "other"
        return result

    root.to_snapshot = broken_snapshot
    outcome = rig.finish()
    assert outcome.persistence == "failed" and outcome.stop_reason == "storage_failed"
    assert rig.model.calls == model_calls
    assert outcome.usage.llm_calls == model_calls
    assert fence.failure
    assert rig.episode._cancel.detail == "storage_failed"
    assert not rig.signal.requested  # internal persistence fault, not a user's stop
    before_rejected_write = raw.load("sibling")
    with pytest.raises(EpisodeStoreFailed):
        fence.append("sibling", (EpisodeEvent(1, "task", {}),), sync=True)
    assert raw.load("sibling") == before_rejected_write
    events, state = raw.load(episode)
    assert state == prefix[1]  # no valid-looking checkpoint without the required snapshot
    if boundary == "done":
        assert outcome.draft and outcome.evidence  # retain private result, not completed
        assert events[-1].kind == "finish"  # a visible finish still isn't a confirmed done


def test_tool_budget_is_debited_before_publishing_the_tools_settled_step(tmp_path):
    from intelligence.runtime.agent_episode import ContinuousAgentEpisode
    from intelligence.tests.conformance.races._drive import build_rig

    episode = f"snapshot-tool-debit-{uuid4().hex}"
    root, _ = _funded(episode)
    rig = build_rig(episode)
    rig.context = replace(rig.context, root_budget=root)
    rig.episode = ContinuousAgentEpisode(rig.model, is_cancelled=rig.signal, store=JsonlEpisodeStore(tmp_path))
    rig.start()
    assert rig.run_until("tools_settled") is not None
    try:
        assert root.remaining_calls == 1  # before any next checkpoint/dispatch
    finally:
        rig.finish()


def test_child_checkpoints_do_not_mint_a_standalone_root_snapshot(tmp_path):
    from intelligence.tests.test_sub_research_persistence import ObservedStore, run_tree

    store = ObservedStore(tmp_path)
    outcome, _, _, _, _ = run_tree(store)
    assert outcome.persistence == "durable"
    assert store.child_ids
    for child_id in store.child_ids:
        _, child_state = JsonlEpisodeStore(tmp_path).load(child_id)
        assert child_state.budget_snapshot is None


def test_checkpoint_budget_snapshot_is_deeply_frozen_and_legacy_missing_is_explicit():
    root, _ = _funded("snapshot-freeze")
    payload = root.to_snapshot()
    state = EpisodeState(
        episode_id=root.episode_id, phase="planning", budget_snapshot=payload, budget_snapshot_sequence=0,
    )
    payload["grants"]["repair-1"]["calls_granted"] = 99
    assert state.budget_snapshot["grants"]["repair-1"]["calls_granted"] == 1
    with pytest.raises(TypeError):
        state.budget_snapshot["grants"]["repair-1"]["calls_granted"] = 99
    exported = state.to_dict()
    exported["budget_snapshot"]["grants"].clear()
    assert "repair-1" in state.budget_snapshot["grants"]
    assert EpisodeState.from_dict(json.loads(json.dumps(state.to_dict()))) == state
    legacy = EpisodeState.from_dict({"episode_id": "legacy", "phase": "planning", "log_version": 1})
    assert legacy.budget_snapshot is None and legacy.budget_snapshot_sequence is None


@pytest.mark.parametrize("sequence", [None, True, -1, 4, 1.5, "1"])
def test_snapshot_prefix_must_be_explicit_and_within_the_checkpoint(sequence):
    root, _ = _funded("snapshot-sequence")
    with pytest.raises(ValueError, match="snapshot sequence"):
        EpisodeState(
            episode_id=root.episode_id, phase="planning", last_sequence=3,
            budget_snapshot=root.to_snapshot(), budget_snapshot_sequence=sequence,
        )
    with pytest.raises(ValueError, match="requires a snapshot"):
        EpisodeState(episode_id=root.episode_id, phase="planning", budget_snapshot_sequence=0)


def test_repair_checkpoint_includes_spent_tool_and_new_grant(tmp_path):
    from intelligence.runtime.glm_agent_runtime import GLMAgentRuntime
    from intelligence.tests.test_agent_episode import (
        ScriptedModel, _frame, _context, _tool_turn, _finish_turn, _market_registry, _successful_runner,
    )
    from intelligence.tests.test_episode_session import _goal

    frame = _frame(("direct_assessment", "counterpoint"))
    context = _context(frame, max_steps=4)
    root = InMemoryRootBudgetLedger(
        episode_id=context.contract.task_id, initial_calls=4, hard_calls_cap=8,
        initial_seconds=60.0, hard_seconds_cap=90.0,
    )
    context = replace(context, root_budget=root)
    checkpoints = []

    class Observed(JsonlEpisodeStore):
        def put_state(self, episode_id, state):
            super().put_state(episode_id, state)
            checkpoints.append((state, root.to_snapshot()))

    store = Observed(tmp_path)
    model = ScriptedModel([
        _tool_turn("市场"), _finish_turn(status="partial", gap="缺少反方证据"),
        _tool_turn("资金"), _finish_turn(status="partial", gap="缺少反方证据"),
    ])
    session = GLMAgentRuntime(client=model, episode_store=store).start(
        frame, context=context, registry=_market_registry(_successful_runner),
    )
    try:
        assert session.outcome.persistence == "durable"
        assert root.grant(BudgetGrant("repair-fresh", root.episode_id, 1, 1, 5.0))
        checkpoints.clear()
        repaired = session.resume(_goal(root.episode_id))
        assert repaired.persistence == "durable" and len(model.calls) == 4
        states = [state for state, _ in checkpoints if state.phase == "repair"]
        assert len(states) == 2
        assert states[0].budget_snapshot["remaining_calls"] == 4
        assert states[1].budget_snapshot["remaining_calls"] == 3  # debit BEFORE checkpoint
        assert all("repair-fresh" in s.budget_snapshot["grants"] for s in states)
        assert all(s.budget_snapshot == at_write for s, at_write in checkpoints)
    finally:
        session.close()


def test_live_deep_promotion_checkpoint_reopens_without_regranting(tmp_path):
    from intelligence.runtime.agent_episode import ContinuousAgentEpisode
    from intelligence.runtime.tier_promotion import apply_mode_promotion
    from intelligence.services.research_harness import FinanceResearchHarness
    from intelligence.services.mode_governor import ModeSignals
    from intelligence.tests.test_tier_promotion import (
        _ScriptedModel, _loop_context, _frame, _deep_plan, _deep_plan_turn, _tool_turn, _finish_turn, _registry,
    )

    episode = f"snapshot-promotion-{uuid4().hex}"
    context = _loop_context(episode)
    store = JsonlEpisodeStore(tmp_path)
    continuation = []
    outcome = ContinuousAgentEpisode(
        _ScriptedModel([_deep_plan_turn(), _tool_turn(), _finish_turn()]), store=store,
        harness=FinanceResearchHarness(
            mode_signals=lambda *_: ModeSignals(evidence_domains=("盘面", "新闻")),
        ),
    ).run(task_frame=_frame(), context=context, registry=_registry(), _continuation_sink=continuation)
    assert outcome.persistence == "durable" and outcome.status == "completed"
    _, state = JsonlEpisodeStore(tmp_path).load(episode)
    assert continuation[0].context.policy.tier == "deep"
    assert state.budget_snapshot["initial_hard_calls_cap"] == 8
    assert state.budget_snapshot["hard_calls_cap"] == 24
    assert state.budget_snapshot["remaining_calls"] == 23
    assert state.budget_snapshot["grants"] and state.budget_snapshot["promotions"]
    restored = budgets.restore_root_budget(state.budget_snapshot, episode_id=episode)
    try:
        before = restored.to_snapshot()
        # Replay the approval against the old tier context: identities, not a
        # current policy shortcut, must keep spent budget from being re-issued.
        old_context = replace(context, root_budget=restored)
        decision = FinanceResearchHarness(
            mode_signals=lambda *_: ModeSignals(evidence_domains=("盘面", "新闻")),
        ).govern_mode(task_frame=_frame(), plan=_deep_plan(), context=old_context, can_branch=False).decision
        promoted = apply_mode_promotion(old_context, decision)
        assert promoted.policy.tier == "deep" and promoted.root_budget is restored
        assert restored.to_snapshot() == before
    finally:
        release_root_budget(episode)


def test_snapshots_are_atomic_with_concurrent_grant_and_debit():
    root = InMemoryRootBudgetLedger(
        episode_id="snapshot-concurrent", initial_calls=200, hard_calls_cap=400,
        initial_seconds=200.0, hard_seconds_cap=400.0,
    )
    barrier = Barrier(2)

    def write_budget():
        barrier.wait(timeout=5)
        for index in range(100):
            assert root.grant(BudgetGrant(f"grant-{index}", root.episode_id, index, 1, 1.0))
            root.consume_call(seconds=0.5)

    def read_snapshots():
        barrier.wait(timeout=5)
        for _ in range(100):
            payload = root.to_snapshot()
            restored = InMemoryRootBudgetLedger.from_snapshot(payload, episode_id=root.episode_id)
            assert restored.to_snapshot() == payload

    with ThreadPoolExecutor(max_workers=2) as executor:
        writers = [executor.submit(write_budget), executor.submit(read_snapshots)]
        for future in writers:
            future.result(timeout=10)
    assert root.remaining_calls == 200 and root.allocated_calls == 300
    assert root.remaining_seconds == 250.0


def test_burned_seconds_do_not_refund_already_executed_tool_slots():
    from intelligence.runtime.agent_episode import _settle_batch_calls

    root = InMemoryRootBudgetLedger(
        episode_id="snapshot-overrun", initial_calls=3, hard_calls_cap=3,
        initial_seconds=1.0, hard_seconds_cap=1.0,
    )
    _settle_batch_calls(root, executed_count=2, batch_elapsed=10.0)
    restored = InMemoryRootBudgetLedger.from_snapshot(root.to_snapshot(), episode_id=root.episode_id)
    assert restored.remaining_seconds == 0.0
    assert restored.remaining_calls == 1  # overshooting time isn't free tool execution
