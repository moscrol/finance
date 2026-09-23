"""Recovery inspection must not consume work before a driver executes it."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys

import pytest

from intelligence.services.episode_restore import RestoreUnavailable, restore_episode
from intelligence.services.episode_store import JsonlEpisodeStore
from intelligence.tests.test_episode_restore import (
    EPISODE_ID,
    SOON,
    _SCENARIO,
    _all_prefixes,
    _crashed_fallback_episode,
    _run_uninterrupted,
    _store_at,
)


@pytest.mark.parametrize("disk", [False, True])
def test_every_crash_prefix_keeps_its_next_action_until_execution(tmp_path, disk):
    recording, events = _run_uninterrupted(_SCENARIO)
    authority = {"context": recording.context, "registry": recording.registry}
    actions = set()
    for length in _all_prefixes(events, recording.states):
        root = tmp_path / str(length)
        store, state = _store_at(
            events, recording.states, length, jsonl_root=root if disk else None,
        )
        if not state.terminal and any(e.kind == "finish" for e in events[:length]):
            with pytest.raises(RestoreUnavailable, match="finish.*checkpoint"):
                restore_episode(EPISODE_ID, store, now=SOON, **authority)
            continue
        first = restore_episode(EPISODE_ID, store, now=SOON, **authority)
        saved = store.load(EPISODE_ID)
        if first.plan is not None:
            actions.add(first.plan.action)
        for _ in range(2):
            reader = JsonlEpisodeStore(root) if disk else store
            again = restore_episode(EPISODE_ID, reader, now=SOON, **authority)
            assert again.plan == first.plan, (length, state.phase, first.plan, again.plan)
            assert again.disposition == first.disposition
            assert again.synthesized == ()
            assert reader.load(EPISODE_ID) == saved
    assert {"retry_model", "replay_tools", "dispatch_tools", "interpret_turn", "model_turn"} <= actions


@pytest.mark.parametrize("disk", [False, True])
def test_partial_batch_replay_then_dispatch_retains_unissued_calls(tmp_path, disk):
    recording, events = _run_uninterrupted(_SCENARIO)
    authority = {"context": recording.context, "registry": recording.registry}
    requests = [e for e in events if e.kind == "tool_request"]
    first_id, second_id = [e.payload["call_id"] for e in requests]
    store, _ = _store_at(
        events, recording.states, requests[0].sequence,
        jsonl_root=tmp_path if disk else None,
    )
    replay = restore_episode(EPISODE_ID, store, now=SOON, **authority)
    assert replay.plan.action == "replay_tools" and replay.plan.call_ids == (first_id,)

    # Stand in only for the driver's completed effect, not for a guessed checkpoint.
    settlement = next(e for e in events if e.kind == "tool_result" and e.payload["call_id"] == first_id)
    store.append(EPISODE_ID, (replace(settlement, sequence=len(replay.events) + 1),), sync=True)
    reader = JsonlEpisodeStore(tmp_path) if disk else store
    dispatch = restore_episode(EPISODE_ID, reader, now=SOON, **authority)
    assert dispatch.plan.action == "dispatch_tools"
    assert dispatch.plan.call_ids == (second_id,)
    again = restore_episode(EPISODE_ID, reader, now=SOON, **authority)
    assert again.plan == dispatch.plan
    assert again.events == dispatch.events


@pytest.mark.parametrize("disk", [False, True])
def test_undispatched_application_call_is_settled_only_once(tmp_path, disk):
    episode_id, store, call_id, context, registry = _crashed_fallback_episode(
        after_kind="application_tool_call",
    )
    if disk:
        events, state = store.load(episode_id)
        store = JsonlEpisodeStore(tmp_path)
        store.append(episode_id, events, sync=True)
        store.put_state(episode_id, state)
    authority = {"context": context, "registry": registry}
    first = restore_episode(episode_id, store, now=SOON, **authority)
    assert [e.kind for e in first.synthesized] == ["tool_error"]
    saved = store.load(episode_id)
    for _ in range(2):
        reader = JsonlEpisodeStore(tmp_path) if disk else store
        again = restore_episode(episode_id, reader, now=SOON, **authority)
        assert again.plan == first.plan
        assert again.synthesized == ()
        assert reader.load(episode_id) == saved
        assert sum(e.kind == "tool_error" and e.payload.get("call_id") == call_id for e in again.events) == 1


@pytest.mark.parametrize("boundary", ["model_error", "state"])
@pytest.mark.parametrize("after_write", [False, True])
def test_retry_after_lost_ack_keeps_one_settlement_and_the_same_plan(tmp_path, boundary, after_write):
    from intelligence.tests.test_episode_restore_persistence import (
        EPISODE_ID as task_id, NOW, _authority, _crashed,
    )

    class LostAckStore(JsonlEpisodeStore):
        armed = False

        def append(self, episode_id, events, *, sync=False):
            fail = self.armed and boundary == events[-1].kind
            if not fail or after_write:
                super().append(episode_id, events, sync=sync)
            if fail:
                raise OSError("lost acknowledgement")

        def put_state(self, episode_id, state):
            fail = self.armed and boundary == "state"
            if not fail or after_write:
                super().put_state(episode_id, state)
            if fail:
                raise OSError("lost acknowledgement")

    store = LostAckStore(tmp_path)
    _, original = _crashed(store)
    store.armed = True
    with pytest.raises(OSError, match="lost acknowledgement"):
        restore_episode(task_id, store, now=NOW, **_authority())
    reader = JsonlEpisodeStore(tmp_path)
    result = restore_episode(task_id, reader, now=NOW, **_authority())
    assert result.plan.action == "finalize"
    assert result.state_after.phase == original.phase
    assert result.state_after.reserved_ids == original.reserved_ids
    assert sum(e.kind == "model_error" for e in result.events) == 1
    saved = reader.load(task_id)
    again = restore_episode(task_id, reader, now=NOW, **_authority())
    assert again.plan == result.plan and not again.synthesized
    assert reader.load(task_id) == saved


def test_fresh_processes_keep_synthesized_plan_snapshots_and_current_authority(tmp_path):
    from intelligence.tests.test_episode_restore_persistence import (
        EPISODE_ID as task_id, NOW, _authority, _crashed,
    )
    from intelligence.tests.test_root_budget_snapshot import _funded

    store = JsonlEpisodeStore(tmp_path)
    _, original = _crashed(store)
    root, _ = _funded(task_id)
    original = replace(original, budget_snapshot=root.to_snapshot(), budget_snapshot_sequence=3)
    store.put_state(task_id, original)
    first = restore_episode(task_id, store, now=NOW, **_authority())
    saved = store.load(task_id)
    assert first.plan.action == "finalize"
    code = """
import json, sys
from intelligence.services.episode_store import JsonlEpisodeStore
from intelligence.services.episode_restore import restore_episode
from intelligence.tests.test_episode_restore_persistence import EPISODE_ID, NOW, _authority
result = restore_episode(EPISODE_ID, JsonlEpisodeStore(sys.argv[1]), now=NOW, **_authority())
print(json.dumps(result.to_dict()))
"""
    for _ in range(2):
        process = subprocess.run(
            [sys.executable, "-B", "-c", code, str(tmp_path)],
            cwd=Path(__file__).resolve().parents[2],
            capture_output=True, text=True, timeout=30, check=True,
        )
        report = json.loads(process.stdout)
        assert report["plan"] == first.plan.to_dict()
        assert report["synthesized"] == []
        assert store.load(task_id) == saved
    after = saved[1]
    for name in ("budget_snapshot", "budget_snapshot_sequence", "authorization_snapshot",
                 "evidence_snapshot", "evidence_snapshot_sequence"):
        assert getattr(after, name) == getattr(original, name)
    assert after.last_sequence > after.budget_snapshot_sequence
    with pytest.raises(RestoreUnavailable, match="authorization"):
        restore_episode(task_id, store, now=NOW)
    assert store.load(task_id) == saved
