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


def test_tool_labels_cover_exactly_the_registered_tools() -> None:
    """标签表与工具注册表必须一一对应，不能各自漂。

    少一个：那个工具的进度会退回「正在核对计划所需资料。」——不报错、不刷屏，
    只是用户永远看不到它，正是最难发现的一类退化。多一个：说明工具已删除或改名，
    标签成了死条目。两边都锁，新增工具忘了登记就在这里变红。
    """

    from intelligence.services.episode_progress import _TOOL_LABELS
    from intelligence.services.research_tool_registry import _DEFAULT_TOOL_METADATA

    missing = sorted(set(_DEFAULT_TOOL_METADATA) - set(_TOOL_LABELS))
    stale = sorted(set(_TOOL_LABELS) - set(_DEFAULT_TOOL_METADATA))

    assert missing == [], f"这些工具没有用户可见标签，进度会静默退回通用句: {missing}"
    assert stale == [], f"标签表里有注册表不认识的工具（已删或改名）: {stale}"


def test_tool_events_render_distinct_labels_not_one_repeated_sentence() -> None:
    """同一轮里两个不同工具必须给出两句不同的进度。

    回归的是实测 run_20260823_221135_424228：market_data 与 mainline_context
    两次调用在 UI 上都显示「正在核对计划所需资料。」，用户无法分辨 agent 在做什么。
    """

    market = project_episode_progress(
        EpisodeEvent(4, "tool_request", {"name": "market_data", "arguments": {}})
    )
    mainline = project_episode_progress(
        EpisodeEvent(6, "tool_request", {"name": "mainline_context", "arguments": {}})
    )
    result = project_episode_progress(
        EpisodeEvent(5, "tool_result", {"ok": True, "tool": "market_data"})
    )

    assert market is not None and mainline is not None and result is not None
    assert market.message == "正在查盘面快照。"
    assert mainline.message == "正在查主线结构。"
    assert result.message == "已取得盘面快照。"
    assert market.message != mainline.message


def test_unregistered_tool_falls_back_instead_of_leaking_its_name() -> None:
    """认不出来就 fail closed：退回通用句，绝不把工具名透出去。"""

    progress = project_episode_progress(
        EpisodeEvent(9, "tool_request", {"name": "some_unregistered_tool"})
    )

    assert progress is not None
    assert progress.message == "正在核对计划所需资料。"
    assert "some_unregistered_tool" not in json.dumps(
        progress.to_dict(), ensure_ascii=False
    )


def test_tool_labels_survive_the_public_trace_projection() -> None:
    """跨到客户端那一层不许把标签拍回通用句。

    ``api.app._public_trace_step`` 会丢掉 step 的 output_summary、按 stage 重新
    合成。2026-08-23 live（:8801 三轮）就栽在这——单测全绿、历史 payload 回放
    全绿，UI 上一个工具标签都没出现。**上游写了、下游不读**：新字段的验收点
    必须放在真正被消费的那一层，不是产出的那一层。
    """

    from intelligence.api import app as app_module

    progress = project_episode_progress(
        EpisodeEvent(4, "tool_request", {"name": "market_data"})
    )
    assert progress is not None
    step = {
        "step_id": "continuous:episode:4:tool_request",
        "name": progress.stage,
        "status": progress.status,
        "started_at": "2026-08-23T22:11:41+08:00",
        "finished_at": None,
        "output_summary": progress.message,
        "warnings": [],
    }

    public = app_module._public_trace_step(step)

    assert public["output_summary"] == "正在查盘面快照。"


def test_public_trace_projection_still_refuses_foreign_prose() -> None:
    """白名单只放行我们自己生成的句子，seam 没有被放宽。"""

    from intelligence.api import app as app_module

    public = app_module._public_trace_step(
        {
            "step_id": "some:other:producer",
            "name": "research",
            "status": "completed",
            "output_summary": "模型说：我调用了 finance_query 查 hidden_table。",
            "warnings": [],
        }
    )

    assert public["output_summary"] == "已完成一项证据核对。"
    assert "finance_query" not in json.dumps(public, ensure_ascii=False)
    assert "hidden_table" not in json.dumps(public, ensure_ascii=False)


def test_whitelist_is_generated_from_the_same_tables_it_guards() -> None:
    """白名单必须由那两张表生成，不能是手抄的第二份清单。"""

    from intelligence.services.episode_progress import (
        _EVENT_PROJECTIONS,
        _TOOL_LABELS,
        public_progress_messages,
    )

    allowed = public_progress_messages()

    for _stage, message, _status in _EVENT_PROJECTIONS.values():
        assert message in allowed
    for label in _TOOL_LABELS.values():
        assert f"正在查{label}。" in allowed
        assert f"已取得{label}。" in allowed


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
