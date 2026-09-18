"""恢复只判下一步，不执行外部工作；保存确认是交付 plan/closed 的前置。"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from intelligence.services.agent_runtime import EpisodeEvent
from intelligence.services.episode_restore import RestoreUnavailable, restore_episode
from intelligence.services.episode_store import EpisodeState, JsonlEpisodeStore, MemoryEpisodeStore

EPISODE_ID = "restore-write-confirmation"
NOW = datetime(2026, 9, 18, tzinfo=timezone.utc)


def _crashed(store):
    events = (
        EpisodeEvent(1, "task", {"task_frame_hash": "tf", "question": "q"}),
        EpisodeEvent(2, "prompt_assembled", {"system": "s", "user": "u"}),
        EpisodeEvent(3, "model_intent", {"turn_id": "turn-1", "phase": "planning"}),
    )
    state = EpisodeState(
        episode_id=EPISODE_ID,
        phase="model_pending",
        reserved_ids=("turn-1",),
        deadline_at=(NOW + timedelta(minutes=2)).isoformat(),
        retry={"remaining": 0},
        last_sequence=len(events),
    )
    store.append(EPISODE_ID, events, sync=True)
    store.put_state(EPISODE_ID, state)
    return events, state


class BufferedStore(MemoryEpisodeStore):
    """Separate visible bytes from confirmed bytes; a checkpoint does not flush events."""

    def __init__(self):
        super().__init__()
        self.confirmed = ()
        self.checkpoints = []

    def append(self, episode_id, events, *, sync=False):
        super().append(episode_id, events, sync=sync)
        if sync:
            self.confirmed = self.load(episode_id)[0]

    def put_state(self, episode_id, state):
        self.checkpoints.append((state, len(self.confirmed)))
        super().put_state(episode_id, state)


@pytest.mark.parametrize("expired", [False, True])
def test_restore_confirms_settlements_before_returning_plan_or_closed(expired):
    store = BufferedStore()
    _crashed(store)
    store.append_log.clear()
    store.checkpoints.clear()

    result = restore_episode(
        EPISODE_ID, store, now=NOW + timedelta(hours=1) if expired else NOW,
    )

    assert result.disposition == ("closed" if expired else "resumable")
    assert result.events == store.confirmed
    assert store.append_log and all(sync for _, _, sync in store.append_log)
    assert all(state.last_sequence <= confirmed for state, confirmed in store.checkpoints)
    if expired:
        assert result.outcome is not None and result.outcome.persistence == "durable"
    else:
        assert result.plan is not None and result.plan.action == "finalize"


@pytest.mark.parametrize(("boundary", "expired"), [
    ("model_error", False), ("state", False),
    ("model_error", True), ("finish", True), ("state", True),
])
@pytest.mark.parametrize("after_write", [False, True])
def test_restore_ack_failure_propagates_without_advertising_next_action(tmp_path, boundary, expired, after_write):
    class FailingStore(JsonlEpisodeStore):
        armed = False
        failed = False
        writes_after_failure = 0
        attempted_states = 0

        def _write(self, name, fn):
            if self.failed:
                self.writes_after_failure += 1
            if self.armed and name == boundary:
                if after_write:
                    fn()
                self.failed = True
                raise OSError("restore acknowledgement lost")
            fn()

        def append(self, episode_id, events, *, sync=False):
            name = events[-1].kind
            self._write(name, lambda: super(FailingStore, self).append(episode_id, events, sync=sync))

        def put_state(self, episode_id, state):
            if self.armed:
                self.attempted_states += 1
            self._write("state", lambda: super(FailingStore, self).put_state(episode_id, state))

    store = FailingStore(tmp_path)
    prefix, initial_state = _crashed(store)
    store.armed = True

    with pytest.raises(OSError, match="restore acknowledgement lost"):
        restore_episode(EPISODE_ID, store, now=NOW + timedelta(hours=1) if expired else NOW)

    assert store.writes_after_failure == 0
    assert store.attempted_states == (1 if boundary == "state" else 0)
    landed, state = JsonlEpisodeStore(tmp_path).load(EPISODE_ID)
    assert landed[:len(prefix)] == prefix
    extra = {"model_error": 0, "finish": 1, "state": 2 if expired else 1}[boundary]
    if after_write and boundary != "state":
        extra += 1
    assert [e.kind for e in landed[len(prefix):]] == ["model_error", "finish"][:extra]
    if boundary == "state" and after_write:
        assert state.phase == ("done" if expired else "finalizing")
        assert state.last_sequence == len(landed)
    else:
        assert state == initial_state
    # No rollback: written finish can survive lost ACK. It is not enough to
    # advertise already_terminal without the corresponding completed checkpoint.
    if landed[-1].kind == "finish" and not state.terminal:
        before = JsonlEpisodeStore(tmp_path).load(EPISODE_ID)
        with pytest.raises(RestoreUnavailable, match="finish.*checkpoint"):
            restore_episode(EPISODE_ID, JsonlEpisodeStore(tmp_path), now=NOW)
        assert JsonlEpisodeStore(tmp_path).load(EPISODE_ID) == before


@pytest.mark.parametrize("shape", ["finish_without_done", "done_without_finish", "tail_after_done"])
def test_restore_refuses_unconfirmed_terminal_without_writes(shape):
    store = MemoryEpisodeStore()
    _, state = _crashed(store)
    finish = EpisodeEvent(4, "finish", {"status": "partial", "stop_reason": "model_finish"})
    if shape != "done_without_finish":
        store.append(EPISODE_ID, (finish,), sync=True)
    if shape != "finish_without_done":
        store.put_state(EPISODE_ID, replace(state, phase="done", reserved_ids=(), last_sequence=4 if shape == "tail_after_done" else 3))
    if shape == "tail_after_done":
        store.append(EPISODE_ID, (EpisodeEvent(5, "repair_goal", {"cycle": 1}),), sync=True)
    before = store.load(EPISODE_ID)
    writes = tuple(store.append_log)

    with pytest.raises(RestoreUnavailable, match="terminal|finish"):
        restore_episode(EPISODE_ID, store, now=NOW)

    assert store.load(EPISODE_ID) == before
    assert tuple(store.append_log) == writes


def test_old_finish_does_not_hide_the_active_repair_checkpoint():
    store = MemoryEpisodeStore()
    _crashed(store)
    store.append(EPISODE_ID, (
        EpisodeEvent(4, "model_turn", {"turn_id": "turn-1", "content": "{}"}),
        EpisodeEvent(5, "finish", {"status": "partial", "stop_reason": "model_finish"}),
        EpisodeEvent(6, "repair_goal", {"cycle": 1}),
        EpisodeEvent(7, "repair_reentry", {"cycle": 1}),
        EpisodeEvent(8, "model_intent", {"turn_id": "turn-2", "phase": "repair"}),
    ), sync=True)
    store.put_state(EPISODE_ID, EpisodeState(
        episode_id=EPISODE_ID, phase="model_pending", turn_index=2,
        reserved_ids=("turn-2",), retry={"remaining": 1},
        last_sequence=8, deadline_at=(NOW + timedelta(minutes=2)).isoformat(),
    ))
    before = store.load(EPISODE_ID)

    result = restore_episode(EPISODE_ID, store, now=NOW)

    assert result.disposition == "resumable" and not result.terminal
    assert result.plan.action == "retry_model"
    assert result.plan.phase == "repair" and result.plan.turn_id == "turn-2"
    assert store.load(EPISODE_ID) == before  # a plan is not permission to dispatch


def test_real_runtime_repair_prefix_is_not_mistaken_for_previous_completion(tmp_path):
    from intelligence.runtime.glm_agent_runtime import GLMAgentRuntime
    from intelligence.tests.test_agent_episode import (
        ScriptedModel, _frame, _context, _tool_turn, _finish_turn,
        _market_registry, _successful_runner,
    )
    from intelligence.tests.test_episode_session import _goal

    frame = _frame(("direct_assessment", "counterpoint"))
    context = _context(frame, max_steps=2)
    store = JsonlEpisodeStore(tmp_path / "live")
    captured = []

    class CaptureRepairModel(ScriptedModel):
        def complete(self, **kwargs):
            if len(self.calls) == 2:
                captured.append(store.load(context.contract.task_id))
            return super().complete(**kwargs)

    model = CaptureRepairModel([
        _tool_turn("市场"), _finish_turn(status="partial", gap="缺少反方证据"),
        _finish_turn(status="partial", gap="缺少反方证据"),
    ])
    session = GLMAgentRuntime(client=model, episode_store=store).start(
        frame, context=context, registry=_market_registry(_successful_runner),
    )
    try:
        assert session.outcome.persistence == "durable"
        session.resume(_goal(context.contract.task_id))
    finally:
        session.close()
    assert len(captured) == 1
    events, state = captured[0]
    assert any(e.kind == "finish" for e in events)
    assert state.phase == "model_pending" and state.reserved_ids == ("turn-3",)
    crash = JsonlEpisodeStore(tmp_path / "reopened-prefix")
    crash.append(context.contract.task_id, events, sync=True)
    crash.put_state(context.contract.task_id, state)
    before = crash.load(context.contract.task_id)

    result = restore_episode(
        context.contract.task_id, crash,
        now=datetime.fromisoformat(state.deadline_at) - timedelta(seconds=1),
    )

    assert result.disposition == "resumable"
    assert result.plan.phase == "repair" and result.plan.turn_id == "turn-3"
    assert result.plan.action == "retry_model"
    assert crash.load(context.contract.task_id) == before
    assert len(model.calls) == 3  # restore itself performs no additional effect


def test_confirmed_terminal_is_read_only_and_idempotent():
    store = MemoryEpisodeStore()
    _, state = _crashed(store)
    store.append(EPISODE_ID, (EpisodeEvent(4, "finish", {"status": "failed"}),), sync=True)
    store.put_state(EPISODE_ID, replace(state, phase="done", reserved_ids=(), last_sequence=4))
    before = store.load(EPISODE_ID)
    for _ in range(2):
        result = restore_episode(EPISODE_ID, store, now=NOW)
        assert result.disposition == "already_terminal"
        assert result.outcome is None and result.plan is None and not result.synthesized
        assert store.load(EPISODE_ID) == before
