"""A runner owns one inbox; rejected concurrent control must not finish its drive."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from intelligence.runtime.agent_episode import ContinuousAgentEpisode
from intelligence.services.episode_messages import user_message
from intelligence.services.episode_store import EpisodeWriterBusy, JsonlEpisodeStore, MemoryEpisodeStore
from intelligence.tests.conformance.races._drive import build_rig
from intelligence.tests.test_episode_session import _goal
from intelligence.tests.test_episode_writer import _completed_with_continuation


@pytest.mark.parametrize("backend", ["ephemeral", "memory", "disk"])
def test_one_runner_rejects_other_task_without_replacing_or_leaking_inbox(tmp_path, backend):
    store = {"ephemeral": lambda: None, "memory": MemoryEpisodeStore,
             "disk": lambda: JsonlEpisodeStore(tmp_path)}[backend]()
    first, second = build_rig("owner-a"), build_rig("owner-b")
    shared = ContinuousAgentEpisode(first.model, store=store)
    drive = shared.manual_drive(task_frame=first.frame, context=first.context, registry=first.registry)
    contender = shared.manual_drive(task_frame=second.frame, context=second.context, registry=second.registry)
    try:
        assert drive.step().phase == "model_pending"
        inbox = shared.inbox
        before = store.load(first.task_id) if store is not None else None
        with pytest.raises(EpisodeWriterBusy):
            contender.step()
        assert shared.inbox is inbox and not inbox.closed
        if store is not None:
            assert store.load(second.task_id) == ((), None)
            assert store.load(first.task_id) == before
        assert first.model.calls == 0
    finally:
        contender.close()
        drive.close()
    assert inbox.closed
    assert not inbox.send(user_message("late input")).accepted
    if store is not None:
        assert store.load(first.task_id) == before
    fresh = shared.manual_drive(task_frame=second.frame, context=second.context, registry=second.registry)
    try:
        assert fresh.step().phase == "model_pending"
        assert shared.inbox is not inbox and not shared.inbox.closed
    finally:
        fresh.close()


def test_live_run_blocks_repair_of_another_task_on_same_runner(tmp_path):
    rig, store, previous, state = _completed_with_continuation(tmp_path)
    other = build_rig("owner-other")
    drive = rig.episode.manual_drive(task_frame=other.frame, context=other.context, registry=other.registry)
    try:
        assert drive.step().phase == "model_pending"
        inbox = rig.episode.inbox
        before = store.load(rig.task_id)
        with pytest.raises(EpisodeWriterBusy):
            rig.episode.resume(state, previous, _goal(rig.task_id))
        assert rig.episode.inbox is inbox and not inbox.closed
        assert store.load(rig.task_id) == before
    finally:
        drive.close()


def test_live_repair_blocks_fresh_run_on_same_runner(tmp_path, monkeypatch):
    rig, store, previous, state = _completed_with_continuation(tmp_path)
    other = build_rig("owner-other")

    def repair(*_args):
        drive = rig.episode.manual_drive(task_frame=other.frame, context=other.context, registry=other.registry)
        try:
            with pytest.raises(EpisodeWriterBusy):
                drive.step()
            assert store.load(other.task_id) == ((), None)
        finally:
            drive.close()
        return previous

    monkeypatch.setattr(rig.episode, "_resume_owned", repair)
    assert rig.episode.resume(state, previous, _goal(rig.task_id)) is previous
    drive = rig.episode.manual_drive(task_frame=other.frame, context=other.context, registry=other.registry)
    try:
        assert drive.step().phase == "model_pending"
    finally:
        drive.close()


@pytest.mark.parametrize("operation", ["step", "close"])
def test_rejected_concurrent_drive_operation_keeps_owner_live(operation):
    rig = build_rig("running-owner")
    drive = rig.start()
    entered, release = Event(), Event()

    def pause_model():
        entered.set()
        assert release.wait(10), "model was not released"

    rig.model.on_call[1] = pause_model
    assert drive.step().phase == "model_pending"
    inbox = rig.episode.inbox
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(drive.step)
            try:
                assert entered.wait(10)
                with pytest.raises(EpisodeWriterBusy):
                    getattr(drive, operation)()
                assert not drive.finished and not inbox.closed
                with pytest.raises(EpisodeWriterBusy):
                    with rig.oracle.writer(rig.task_id):
                        pytest.fail("in-flight drive released ownership")
            finally:
                release.set()
                assert running.result(timeout=10).phase == "model_settled"
        assert not drive.finished
    finally:
        drive.close()
    assert drive.finished and drive.outcome is None and inbox.closed
    with rig.oracle.writer(rig.task_id):
        pass


@pytest.mark.parametrize("failure", ["busy", "load", "generator"])
def test_failed_control_entry_releases_runner_for_next_task(tmp_path, monkeypatch, failure):
    first, second = build_rig("failed-entry"), build_rig("next-entry")
    store = JsonlEpisodeStore(tmp_path)
    shared = ContinuousAgentEpisode(first.model, store=store)
    drive = shared.manual_drive(task_frame=first.frame, context=first.context, registry=first.registry)
    if failure == "busy":
        with store.writer(first.task_id):
            with pytest.raises(EpisodeWriterBusy):
                drive.step()
    else:
        def broken(*_args, **_kwargs):
            raise OSError("injected control failure")

        with monkeypatch.context() as patch:
            if failure == "load":
                patch.setattr(store, "load", broken)
            else:
                patch.setattr(shared, "_drive", broken)
            with pytest.raises(OSError, match="injected control failure"):
                drive.step()
    assert drive.finished
    fresh = shared.manual_drive(task_frame=second.frame, context=second.context, registry=second.registry)
    try:
        assert fresh.step().phase == "model_pending"
    finally:
        fresh.close()


def test_failed_repair_releases_runner_for_another_task(tmp_path, monkeypatch):
    rig, _store, previous, state = _completed_with_continuation(tmp_path)

    def broken(*_args):
        raise OSError("injected repair failure")

    monkeypatch.setattr(rig.episode, "_resume_owned", broken)
    with pytest.raises(OSError, match="injected repair failure"):
        rig.episode.resume(state, previous, _goal(rig.task_id))
    other = build_rig("after-repair-failure")
    drive = rig.episode.manual_drive(task_frame=other.frame, context=other.context, registry=other.registry)
    try:
        assert drive.step().phase == "model_pending"
    finally:
        drive.close()


def test_separate_runners_can_drive_different_tasks_at_the_same_time(tmp_path):
    store = JsonlEpisodeStore(tmp_path)
    first, second = build_rig("parallel-a"), build_rig("parallel-b")
    first.episode = ContinuousAgentEpisode(first.model, store=store)
    second.episode = ContinuousAgentEpisode(second.model, store=store)
    a, b = first.start(), second.start()
    try:
        assert a.step().phase == b.step().phase == "model_pending"
        inbox_a, inbox_b = first.episode.inbox, second.episode.inbox
        a.close()
        assert inbox_a.closed and not inbox_b.closed
        assert second.episode.steer("still active").accepted
    finally:
        a.close()
        b.close()
