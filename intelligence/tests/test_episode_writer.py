"""Single-writer ownership is a control boundary, not a replay permission."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
import json
from pathlib import Path
import selectors
import subprocess
import sys
from threading import Event

import pytest

from intelligence.runtime.agent_episode import ContinuousAgentEpisode
from intelligence.services.agent_runtime import EpisodeEvent
from intelligence.services.episode_messages import user_message
from intelligence.services.episode_restore import RestoreUnavailable, restore_episode
from intelligence.services.episode_store import (
    EpisodeState,
    EpisodeWriterBusy,
    FencedEpisodeStore,
    JsonlEpisodeStore,
    MemoryEpisodeStore,
)
from intelligence.tests.conformance.races._drive import build_rig
from intelligence.tests.test_episode_restore_persistence import EPISODE_ID, NOW, _authority, _crashed
from intelligence.tests.test_episode_session import _goal

ROOT = Path(__file__).resolve().parents[2]


def _child(code, *args):
    result = subprocess.run(
        [sys.executable, "-B", "-c", code, *map(str, args)], cwd=ROOT,
        capture_output=True, text=True, timeout=30, check=True,
    )
    return json.loads(result.stdout)


RESTORE_CHILD = """
import json, sys
from intelligence.services.episode_restore import restore_episode
from intelligence.services.episode_store import EpisodeWriterBusy, JsonlEpisodeStore
from intelligence.tests.test_episode_restore_persistence import EPISODE_ID, NOW, _authority
try:
    result = restore_episode(EPISODE_ID, JsonlEpisodeStore(sys.argv[1]), now=NOW, **_authority())
except EpisodeWriterBusy:
    print(json.dumps({'busy': True}))
else:
    print(json.dumps({'busy': False, 'result': result.to_dict()}))
"""


@pytest.mark.parametrize("disk", [False, True])
def test_writer_is_exclusive_per_episode_and_does_not_block_diagnostics(tmp_path, disk):
    store = JsonlEpisodeStore(tmp_path) if disk else MemoryEpisodeStore()
    other = JsonlEpisodeStore(tmp_path) if disk else store
    store.append("one", (EpisodeEvent(1, "task", {}),))
    store.put_state("one", EpisodeState(episode_id="one", phase="planning", last_sequence=1))
    before = store.load("one")
    with store.writer("one"):
        assert other.load("one") == before
        assert other.list_open() == ("one",)
        with pytest.raises(EpisodeWriterBusy):
            with other.writer("one"):
                pytest.fail("second writer entered")
        with other.writer("two"):
            other.append("two", (EpisodeEvent(1, "task", {}),))
    with other.writer("one"):
        assert other.load("one") == before


def test_fence_delegates_ownership_without_latching_a_contender_failure(tmp_path):
    first = FencedEpisodeStore(JsonlEpisodeStore(tmp_path))
    second = FencedEpisodeStore(JsonlEpisodeStore(tmp_path))
    with first.writer("one"):
        with pytest.raises(EpisodeWriterBusy):
            with second.writer("one"):
                pytest.fail("second wrapper entered")
        with second.writer("two"):
            pass
    assert first.failure == second.failure == ""


@pytest.mark.parametrize("episode_id", ["", ".", ".."])
def test_writer_rejects_non_child_directory_names(tmp_path, episode_id):
    store = JsonlEpisodeStore(tmp_path / "episodes")
    with pytest.raises(ValueError):
        with store.writer(episode_id):
            pytest.fail("root or parent directory locked")
    assert not (tmp_path / ".writer.lock").exists()


def test_drive_locks_the_same_normalized_identity_as_the_ledger(tmp_path):
    rig = build_rig("normalized-owner")
    store = JsonlEpisodeStore(tmp_path)
    episode = ContinuousAgentEpisode(rig.model, store=store)
    context = replace(rig.context, contract=replace(rig.context.contract, task_id=" normalized-owner "))
    with store.writer(rig.task_id):
        with pytest.raises(EpisodeWriterBusy):
            episode.run(task_frame=rig.frame, context=context, registry=rig.registry)
    assert store.load(rig.task_id) == ((), None)
    assert rig.model.calls == 0


def test_separate_process_cannot_restore_until_owner_releases(tmp_path):
    store = JsonlEpisodeStore(tmp_path)
    _crashed(store)
    before = store.load(EPISODE_ID)
    with store.writer(EPISODE_ID):
        assert _child(RESTORE_CHILD, tmp_path) == {"busy": True}
        assert store.load(EPISODE_ID) == before
    report = _child(RESTORE_CHILD, tmp_path)
    assert report["busy"] is False
    assert report["result"]["plan"]["action"] == "finalize"
    # 合成结算 + 未知效果登记：后者记的是「那次模型请求可能已计费」，跨进程一样要留。
    assert [e["kind"] for e in report["result"]["synthesized"]] == ["model_error", "effects_unknown"]
    saved = store.load(EPISODE_ID)
    assert _child(RESTORE_CHILD, tmp_path)["result"]["synthesized"] == []
    assert store.load(EPISODE_ID) == saved


def test_killing_real_drive_releases_lock_but_keeps_unexecuted_intent(tmp_path):
    code = """
import sys
from intelligence.runtime.agent_episode import ContinuousAgentEpisode
from intelligence.services.episode_store import JsonlEpisodeStore
from intelligence.tests.conformance.races._drive import build_rig
rig = build_rig('killed-writer')
rig.episode = ContinuousAgentEpisode(rig.model, store=JsonlEpisodeStore(sys.argv[1]))
rig.start()
assert rig.run_until('model_pending') is not None
assert rig.model.calls == 0
print('ready', flush=True)
sys.stdin.readline()
"""
    process = subprocess.Popen(
        [sys.executable, "-B", "-c", code, str(tmp_path)], cwd=ROOT,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        with selectors.DefaultSelector() as ready:
            ready.register(process.stdout, selectors.EVENT_READ)
            assert ready.select(timeout=30), "child did not reach the owned boundary"
            assert process.stdout.readline().strip() == "ready"
        store = JsonlEpisodeStore(tmp_path)
        events, state = store.load("killed-writer")
        assert state.phase == "model_pending"
        rig = build_rig("killed-writer")
        with pytest.raises(EpisodeWriterBusy):
            restore_episode(rig.task_id, store, context=rig.context, registry=rig.registry)
        assert store.load(rig.task_id) == (events, state)
        process.kill()
        process.communicate(timeout=10)
        assert process.returncode < 0
        result = restore_episode(rig.task_id, store, context=rig.context, registry=rig.registry)
        assert result.plan.action == "retry_model"
        assert result.plan.turn_id == state.reserved_ids[0]
        # 「keeps unexecuted intent」：意图原封不动、没被执行也没被结算。多出来的只有未知
        # 效果登记——被 kill 的那一枪到底发出去没有，这里永远也答不了。
        after_events, after_state = store.load(rig.task_id)
        assert after_events[: len(events)] == events
        assert [e.kind for e in after_events[len(events):]] == ["effects_unknown"]
        assert (after_state.phase, after_state.reserved_ids) == (state.phase, state.reserved_ids)
        assert [e.reserved_id for e in result.unreconciled_effects] == [state.reserved_ids[0]]
        assert (store.episode_dir(rig.task_id) / ".writer.lock").exists()
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=10)


@pytest.mark.parametrize("disk", [False, True])
def test_drive_guards_paused_effects_and_close_releases_without_a_finish(tmp_path, disk):
    store = JsonlEpisodeStore(tmp_path) if disk else MemoryEpisodeStore()
    rig = build_rig("paused-owner")
    rig.episode = ContinuousAgentEpisode(rig.model, store=store)
    drive = rig.start()
    assert rig.run_until("model_pending") is not None
    before = store.load(rig.task_id)
    competing = ContinuousAgentEpisode(rig.model, store=store)
    with pytest.raises(EpisodeWriterBusy):
        competing.run(task_frame=rig.frame, context=rig.context, registry=rig.registry)
    with pytest.raises(EpisodeWriterBusy):
        restore_episode(rig.task_id, store, context=rig.context, registry=rig.registry)
    assert store.load(rig.task_id) == before
    assert rig.model.calls == 0
    old_inbox = rig.episode.inbox
    drive.close()
    assert old_inbox.closed
    with store.writer(rig.task_id):
        assert not old_inbox.send(user_message("late message")).accepted
        assert store.load(rig.task_id) == before
    assert drive.finished and drive.outcome is None
    assert drive.step() is None
    assert rig.episode.inbox is None
    result = restore_episode(rig.task_id, store, context=rig.context, registry=rig.registry)
    assert result.plan.action == "retry_model"
    # 上面两次「Busy」下存储一字未动（拿不到写权就什么都不写）；拿到写权之后产生的
    # 唯一一条是未知效果登记，程序计数器仍停在原处。
    after_events, after_state = store.load(rig.task_id)
    assert after_events[: len(before[0])] == before[0]
    assert [e.kind for e in after_events[len(before[0]):]] == ["effects_unknown"]
    assert (after_state.phase, after_state.reserved_ids) == (before[1].phase, before[1].reserved_ids)
    with pytest.raises(RestoreUnavailable, match="existing episode"):
        competing.run(task_frame=rig.frame, context=rig.context, registry=rig.registry)
    assert rig.model.calls == 0


def test_close_drains_inflight_delivery_before_releasing_writer(tmp_path, monkeypatch):
    rig = build_rig("delivery-owner")
    store = JsonlEpisodeStore(tmp_path)
    rig.episode = ContinuousAgentEpisode(rig.model, store=store)
    drive = rig.start()
    assert rig.run_until("model_pending") is not None
    inbox = rig.episode.inbox
    delivery_started, finish_delivery, close_attempted = Event(), Event(), Event()
    delivery_lock = inbox._spool_lock

    def admit(_message):
        delivery_started.set()
        assert finish_delivery.wait(10), "test did not release delivery"
        return True

    class ObservedDeliveryLock:
        def __enter__(self):
            if delivery_started.is_set():
                close_attempted.set()
            delivery_lock.acquire()

        def __exit__(self, *_exc):
            delivery_lock.release()

    monkeypatch.setattr(inbox, "_admit", admit)
    monkeypatch.setattr(inbox, "_spool_lock", ObservedDeliveryLock())
    with ThreadPoolExecutor(max_workers=2) as pool:
        sending = pool.submit(inbox.send, user_message("pending message"))
        try:
            assert delivery_started.wait(10)
            closing = pool.submit(drive.close)
            assert close_attempted.wait(10)
            assert not closing.done()
            with pytest.raises(EpisodeWriterBusy):
                restore_episode(rig.task_id, store, context=rig.context, registry=rig.registry)
        finally:
            finish_delivery.set()
        receipt = sending.result(timeout=10)
        closing.result(timeout=10)
    assert receipt.accepted and inbox.closed
    result = restore_episode(rig.task_id, store, context=rig.context, registry=rig.registry)
    assert result.pending_inbox == (receipt.message_id,)
    assert not any(event.kind == "finish" for event in store.load(rig.task_id)[0])


def test_successful_drive_releases_but_never_restarts_existing_log(tmp_path):
    store = JsonlEpisodeStore(tmp_path)
    rig = build_rig("completed-owner")
    rig.episode = ContinuousAgentEpisode(rig.model, store=store)
    rig.start()
    outcome = rig.finish()
    assert outcome.status == "completed"
    before = store.load(rig.task_id)
    calls = rig.model.calls
    assert restore_episode(rig.task_id, JsonlEpisodeStore(tmp_path)).terminal
    with pytest.raises(RestoreUnavailable, match="existing episode"):
        rig.episode.run(task_frame=rig.frame, context=rig.context, registry=rig.registry)
    assert store.load(rig.task_id) == before
    assert rig.model.calls == calls


def test_generator_exception_releases_owner_and_keeps_exception(tmp_path, monkeypatch):
    rig = build_rig("broken-owner")
    store = JsonlEpisodeStore(tmp_path)
    rig.episode = ContinuousAgentEpisode(rig.model, store=store)

    def broken(**kwargs):
        yield None
        raise RuntimeError("injected driver failure")

    monkeypatch.setattr(rig.episode, "_drive", broken)
    drive = rig.start()
    drive.step()
    with pytest.raises(RuntimeError, match="injected driver failure"):
        drive.step()
    assert drive.finished
    with JsonlEpisodeStore(tmp_path).writer(rig.task_id):
        pass


def test_restore_takes_ownership_before_loading_and_releases_on_write_failure(tmp_path):
    class Observed(JsonlEpisodeStore):
        owned = False
        armed = False

        @contextmanager
        def writer(self, episode_id):
            with super().writer(episode_id):
                self.owned = True
                try:
                    yield
                finally:
                    self.owned = False

        def load(self, episode_id):
            if self.armed:
                assert self.owned, "restore loaded before acquiring ownership"
            return super().load(episode_id)

        def append(self, episode_id, events, *, sync=False):
            if self.armed:
                assert self.owned
                raise OSError("injected storage failure")
            super().append(episode_id, events, sync=sync)

    store = Observed(tmp_path)
    _crashed(store)
    store.armed = True
    with pytest.raises(OSError, match="injected storage failure"):
        restore_episode(EPISODE_ID, store, now=NOW, **_authority())
    assert not store.owned
    with JsonlEpisodeStore(tmp_path).writer(EPISODE_ID):
        pass


def test_restore_refuses_checkpoint_for_another_episode_even_when_terminal(tmp_path):
    store = JsonlEpisodeStore(tmp_path)
    store.append("one", (EpisodeEvent(1, "task", {"task_frame_hash": "frame"}),
                         EpisodeEvent(2, "finish", {})))
    state = EpisodeState(episode_id="other", phase="done", last_sequence=2)
    (store.episode_dir("one") / store.STATE_NAME).write_text(json.dumps(state.to_dict()))
    before = store.load("one")
    with pytest.raises(RestoreUnavailable, match="identity mismatch"):
        restore_episode("one", store)
    assert store.load("one") == before


def _completed_with_continuation(tmp_path):
    rig = build_rig("repair-owner")
    store = JsonlEpisodeStore(tmp_path)
    rig.episode = ContinuousAgentEpisode(rig.model, store=store)
    continuation = []
    previous = rig.episode.run(
        task_frame=rig.frame, context=rig.context, registry=rig.registry,
        _continuation_sink=continuation,
    )
    return rig, store, previous, continuation[0]


@pytest.mark.parametrize("changed", ["event", "state"])
def test_stale_repair_never_appends_or_calls_model(tmp_path, changed):
    rig, store, previous, state = _completed_with_continuation(tmp_path)
    if changed == "event":
        events, _ = store.load(rig.task_id)
        store.append(rig.task_id, (EpisodeEvent(len(events) + 1, "repair_reentry", {}),))
    else:
        store.put_state(rig.task_id, replace(state.ledger.state, updated_at="changed"))
    before = store.load(rig.task_id)
    calls = rig.model.calls
    with pytest.raises(RestoreUnavailable, match="no longer matches"):
        rig.episode.resume(state, previous, _goal(rig.task_id))
    assert store.load(rig.task_id) == before
    assert rig.model.calls == calls


@pytest.mark.parametrize("mismatch", ["store", "context", "goal", "outcome"])
def test_repair_rejects_foreign_owner_or_task_before_any_effect(tmp_path, mismatch):
    rig, store, previous, state = _completed_with_continuation(tmp_path)
    episode = rig.episode
    goal = _goal(rig.task_id)
    if mismatch == "store":
        episode = ContinuousAgentEpisode(rig.model)
    elif mismatch == "context":
        state.context = replace(state.context, contract=replace(state.context.contract, task_id="foreign"))
    elif mismatch == "goal":
        goal = replace(goal, episode_id="foreign")
    else:
        previous = replace(previous, task_frame_hash="foreign", events=tuple(
            replace(event, payload={**event.payload, "task_frame_hash": "foreign"})
            for event in previous.events
        ))
    before = store.load(rig.task_id)
    calls = rig.model.calls
    with pytest.raises(RestoreUnavailable, match="identity mismatch"):
        episode.resume(state, previous, goal)
    assert store.load(rig.task_id) == before
    assert rig.model.calls == calls


def test_repair_owns_entire_operation_and_releases_on_exception(tmp_path, monkeypatch):
    rig, store, previous, state = _completed_with_continuation(tmp_path)
    before = store.load(rig.task_id)
    with JsonlEpisodeStore(tmp_path).writer(rig.task_id):
        with pytest.raises(EpisodeWriterBusy):
            rig.episode.resume(state, previous, _goal(rig.task_id))
    assert store.load(rig.task_id) == before

    def broken(*args):
        with pytest.raises(EpisodeWriterBusy):
            with JsonlEpisodeStore(tmp_path).writer(rig.task_id):
                pytest.fail("repair released ownership too soon")
        raise RuntimeError("injected repair failure")

    monkeypatch.setattr(rig.episode, "_resume_owned", broken)
    with pytest.raises(RuntimeError, match="injected repair failure"):
        rig.episode.resume(state, previous, _goal(rig.task_id))
    with JsonlEpisodeStore(tmp_path).writer(rig.task_id):
        pass
