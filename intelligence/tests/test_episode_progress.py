from __future__ import annotations

import importlib
import json
from pathlib import Path
from threading import Event

import pytest

from intelligence.services.agent_runtime import EpisodeEvent
from intelligence.services.episode_event_lanes import DURABLE_EVENT_KINDS
from intelligence.services.episode_progress import (
    PROGRESS_EVENT_KINDS,
    EpisodeProgress,
    RunEpisodeProgressPublisher,
    project_episode_progress,
)
from intelligence.services.research_tool_registry import TOOL_PRE_EXECUTE
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
    # Live 阶段事件不进 UI 进度：未知 kind 返 None，不会多出进度条目。
    assert project_episode_progress(EpisodeEvent(3, TOOL_PRE_EXECUTE, {})) is None


def test_progress_kinds_are_registered_durable_kinds() -> None:
    """UI 进度只投影已登记的 durable kind，不另造一套词表。

    进度表是精选子集（不是全表）：model_turn / configure 等故意不出进度。
    但子集里的每一个必须在车道表里——否则 UI 认的 kind 和投影层认的 kind 会漂。
    """

    unknown = sorted(PROGRESS_EVENT_KINDS - DURABLE_EVENT_KINDS)
    assert unknown == [], f"进度表有车道表不认识的 kind: {unknown}"


def test_runtime_no_longer_owns_episode_progress() -> None:
    """D5 收口：进度投影在 services，runtime 不得再留一份。

    两份并存就是第二事实源。旧路径必须消失，不能靠「没人 import」假装迁完。
    """

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("intelligence.runtime.episode_progress")
    assert (
        project_episode_progress.__module__
        == "intelligence.services.episode_progress"
    )


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
