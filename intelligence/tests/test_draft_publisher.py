from __future__ import annotations

from pathlib import Path

import pytest

from intelligence.services.draft_publisher import (
    RunDraftDeltaPublisher,
    draft_streaming_enabled,
)
from intelligence.services.run_store import RunStore


def make(tmp_path: Path) -> tuple[RunStore, str, RunDraftDeltaPublisher]:
    store = RunStore(user_id="draft-stream-test", root=tmp_path / "runs")
    run = store.create_run("明天你怎么看", "ask", session_id="conv_1")
    publisher = RunDraftDeltaPublisher(
        run_store=store,
        run_id=run.run_id,
        conversation_id="conv_1",
        message_id="msg_1",
    )
    return store, run.run_id, publisher


def deltas(store: RunStore, run_id: str) -> list[str]:
    return [
        event["payload"]["delta"]
        for event in store.load_stream_events(run_id)
        if event["event_type"] == "text.delta"
    ]


def test_each_fragment_becomes_one_replayable_event(tmp_path: Path) -> None:
    store, run_id, publisher = make(tmp_path)

    for piece in ("第一段。", "第二段。", "第三段。"):
        publisher.publish(piece)

    assert deltas(store, run_id) == ["第一段。", "第二段。", "第三段。"]
    assert publisher.emitted_chars == 12
    # 事件 id 必须各不相同，否则 run_store 会判成冲突重复。
    ids = [
        event["event_id"]
        for event in store.load_stream_events(run_id)
        if event["event_type"] == "text.delta"
    ]
    assert len(set(ids)) == len(ids)


def test_empty_fragments_never_reach_the_stream(tmp_path: Path) -> None:
    store, run_id, publisher = make(tmp_path)

    publisher.publish("")
    publisher.publish("有内容")

    assert deltas(store, run_id) == ["有内容"]


def test_identities_must_be_present(tmp_path: Path) -> None:
    store = RunStore(user_id="draft-stream-test", root=tmp_path / "runs")
    run = store.create_run("q", "ask", session_id="conv_1")

    with pytest.raises(ValueError):
        RunDraftDeltaPublisher(
            run_store=store,
            run_id=run.run_id,
            conversation_id="",
            message_id="msg_1",
        )


def test_kill_switch_is_on_by_default_and_only_off_disables(monkeypatch) -> None:
    monkeypatch.delenv("WORKBENCH_DRAFT_STREAM", raising=False)
    assert draft_streaming_enabled() is True

    monkeypatch.setenv("WORKBENCH_DRAFT_STREAM", "off")
    assert draft_streaming_enabled() is False

    monkeypatch.setenv("WORKBENCH_DRAFT_STREAM", "OFF")
    assert draft_streaming_enabled() is False

    # 只有明确的 off 才关：拼错的值不该静默把流式关掉。
    monkeypatch.setenv("WORKBENCH_DRAFT_STREAM", "false")
    assert draft_streaming_enabled() is True
