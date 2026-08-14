from __future__ import annotations

import json
from pathlib import Path
from threading import Event

from intelligence.services.agent_runtime import EpisodeEvent
from intelligence.runtime.episode_progress import (
    EpisodeProgress,
    RunEpisodeProgressPublisher,
    project_episode_progress,
)
from intelligence.services.run_store import RunStore


def test_projector_never_exposes_control_plane_payload() -> None:
    event = EpisodeEvent(
        3,
        "tool_request",
        {
            "tool": "finance_query",
            "query": "SELECT secret FROM hidden_table",
            "provider": "private-provider",
            "prompt": "internal prompt",
            "message": "raw model message",
            "hash": "private-hash",
        },
    )

    progress = project_episode_progress(event)

    assert progress is not None
    serialized = json.dumps(progress.to_dict(), ensure_ascii=False)
    for forbidden in (
        "finance_query",
        "SELECT",
        "hidden_table",
        "private-provider",
        "internal prompt",
        "raw model message",
        "private-hash",
    ):
        assert forbidden not in serialized


def test_projector_ignores_private_model_and_unknown_events() -> None:
    assert project_episode_progress(EpisodeEvent(1, "model_turn", {})) is None
    assert project_episode_progress(EpisodeEvent(2, "provider_trace", {})) is None


def test_projector_exposes_branch_repair_and_finalization_as_fixed_stages() -> None:
    projected = tuple(
        project_episode_progress(EpisodeEvent(index, kind, {"goal": "secret"}))
        for index, kind in enumerate(
            ("branch_started", "branch_completed", "repair_goal", "finalization"),
            start=1,
        )
    )

    assert all(item is not None for item in projected)
    assert [item.stage for item in projected if item is not None] == [
        "research",
        "research",
        "repair",
        "finalizing",
    ]
    assert all("secret" not in item.message for item in projected if item is not None)


def _running_store(tmp_path: Path) -> tuple[RunStore, str]:
    store = RunStore(user_id="progress-test", root=tmp_path / "runs")
    run = store.create_run("研究当前市场", "ask", session_id="conv-1")
    return store, run.run_id


def test_publisher_persists_replayable_trace_and_is_idempotent(
    tmp_path: Path,
) -> None:
    store, run_id = _running_store(tmp_path)
    publisher = RunEpisodeProgressPublisher(
        run_store=store,
        run_id=run_id,
        conversation_id="conv-1",
        message_id="msg-1",
    )
    progress = EpisodeProgress(
        key="episode:1:plan",
        stage="planning",
        message="已形成研究计划。",
        status="completed",
    )

    publisher.publish(progress)
    publisher.publish(progress)

    trace = store.load_trace(run_id)
    assert [step["step_id"] for step in trace] == ["continuous:episode:1:plan"]
    assert trace[0]["name"] == "planning"
    assert trace[0]["output_summary"] == "已形成研究计划。"
    replay = store.load_stream_events(run_id)
    assert [event["event_type"] for event in replay] == ["trace.step"]
    assert replay[0]["payload"]["step"] == trace[0]


def test_publisher_stops_appending_after_cancellation(tmp_path: Path) -> None:
    store, run_id = _running_store(tmp_path)
    cancelled = Event()
    publisher = RunEpisodeProgressPublisher(
        run_store=store,
        run_id=run_id,
        conversation_id="conv-1",
        message_id="msg-1",
        is_cancelled=cancelled.is_set,
    )
    publisher.publish(
        EpisodeProgress(
            key="episode:1:plan",
            stage="planning",
            message="已形成研究计划。",
            status="completed",
        )
    )

    cancelled.set()
    publisher.publish(
        EpisodeProgress(
            key="episode:2:tool_request",
            stage="research",
            message="正在核对计划所需资料。",
            status="running",
        )
    )

    assert len(store.load_trace(run_id)) == 1
    assert len(store.load_stream_events(run_id)) == 1


def test_publisher_event_prefix_keeps_recovery_replay_identity_unique(
    tmp_path: Path,
) -> None:
    store, run_id = _running_store(tmp_path)
    progress = EpisodeProgress(
        key="adapter:understanding",
        stage="understanding",
        message="已对齐本轮任务。",
        status="completed",
    )
    RunEpisodeProgressPublisher(
        run_store=store,
        run_id=run_id,
        conversation_id="conv-1",
        message_id="msg-1",
    ).publish(progress)
    RunEpisodeProgressPublisher(
        run_store=store,
        run_id=run_id,
        conversation_id="conv-1",
        message_id="msg-1",
        event_id_prefix="recovery:2:",
    ).publish(progress)

    events = store.load_stream_events(run_id)
    assert [event["event_id"] for event in events] == [
        "continuous:progress:adapter:understanding",
        "recovery:2:continuous:progress:adapter:understanding",
    ]
