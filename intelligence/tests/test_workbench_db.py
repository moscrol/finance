"""SQLite 双写过渡的专项测试：双写一致、回退读、懒回填、并发写、批量迁移。"""

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from intelligence.services.conversation_store import ConversationStore
from intelligence.services.run_store import RunStore
from intelligence.services.workbench_db import DB_FILENAME
from intelligence.services.workbench_migrate import migrate_user


def _run_store(tmp_path: Path) -> RunStore:
    return RunStore(user_id="default", root=tmp_path / "runs")


def test_dual_write_run_lands_in_sqlite_and_json(tmp_path: Path):
    store = _run_store(tmp_path)
    run = store.create_run("双写检查", "ask")
    store.finish_run(run.run_id, "completed")

    db_path = tmp_path / "runs" / DB_FILENAME
    assert db_path.is_file()
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT status, payload FROM runs WHERE run_id = ?", (run.run_id,)
        ).fetchone()
    assert row[0] == "completed"
    file_payload = json.loads(
        (tmp_path / "runs" / run.run_id / "run.json").read_text(encoding="utf-8")
    )
    assert json.loads(row[1]) == file_payload


def test_stream_events_dual_write_and_sqlite_read(tmp_path: Path):
    store = _run_store(tmp_path)
    run = store.create_run("事件流", "ask")
    for index in range(3):
        store.append_stream_event(
            run.run_id,
            event_id=f"evt-{index}",
            event_type="report.module",
            payload={"index": index},
        )

    events = store.load_stream_events(run.run_id)
    assert [event["seq"] for event in events] == [1, 2, 3]
    assert store.load_stream_events(run.run_id, after=2)[0]["event_id"] == "evt-2"

    with sqlite3.connect(tmp_path / "runs" / DB_FILENAME) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM run_events WHERE run_id = ?", (run.run_id,)
        ).fetchone()[0]
    assert count == 3


def test_sqlite_read_survives_corrupt_stream_file(tmp_path: Path):
    """文件写坏（写一半被杀）不再影响读：SQLite 是读路径的第一优先级。"""
    store = _run_store(tmp_path)
    run = store.create_run("崩溃恢复", "ask")
    store.append_stream_event(
        run.run_id, event_id="evt-0", event_type="report.start", payload={}
    )
    stream = store.stream_path(run.run_id)
    stream.write_text('{"half-written', encoding="utf-8")

    events = store.load_stream_events(run.run_id)
    assert len(events) == 1 and events[0]["event_id"] == "evt-0"


def test_legacy_stream_file_is_lazily_backfilled_on_append(tmp_path: Path):
    store = _run_store(tmp_path)
    run = store.create_run("懒回填", "ask")
    legacy = {
        "event_id": "legacy-1",
        "event_type": "report.start",
        "created_at": "2026-07-01T09:00:00+08:00",
        "payload": {},
    }
    store.stream_path(run.run_id).write_text(
        json.dumps(legacy, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    store.append_stream_event(
        run.run_id, event_id="new-1", event_type="report.complete", payload={}
    )
    events = store.load_stream_events(run.run_id)
    assert [event["event_id"] for event in events] == ["legacy-1", "new-1"]
    assert [event["seq"] for event in events] == [1, 2]
    assert store.db.count_run_events(run.run_id) == 2


def test_concurrent_stream_appends_are_unique_and_contiguous(tmp_path: Path):
    store = _run_store(tmp_path)
    run = store.create_run("并发", "ask")

    def append(index: int):
        return store.append_stream_event(
            run.run_id,
            event_id=f"evt-{index}",
            event_type="report.module",
            payload={"index": index},
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(append, range(24)))

    events = store.load_stream_events(run.run_id)
    assert [event["seq"] for event in events] == list(range(1, 25))
    assert len({event["event_id"] for event in events}) == 24


def test_conversation_dual_write_and_sqlite_read(tmp_path: Path):
    store = ConversationStore("alice", root=tmp_path)
    conversation = store.create_conversation("双写会话")
    message = store.append_message(conversation.conversation_id, "user", "你好")

    with sqlite3.connect(tmp_path / DB_FILENAME) as conn:
        conv_count = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
        msg_count = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    assert (conv_count, msg_count) == (1, 1)

    # 删掉旧 JSON 文件后仍可从 SQLite 读出（读路径已切换）
    (tmp_path / conversation.conversation_id / "conversation.json").unlink()
    (tmp_path / conversation.conversation_id / "messages.jsonl").unlink()
    assert store.load_conversation(conversation.conversation_id).title == "双写会话"
    assert store.load_messages(conversation.conversation_id) == [message]
    assert [item.conversation_id for item in store.list_conversations()] == [
        conversation.conversation_id
    ]


def test_message_revision_read_from_sqlite_keeps_position(tmp_path: Path):
    store = ConversationStore("alice", root=tmp_path)
    conversation = store.create_conversation()
    first = store.append_message(conversation.conversation_id, "assistant", "初稿")
    store.append_message(conversation.conversation_id, "user", "追问")
    revised = store.revise_message(
        conversation.conversation_id,
        first.message_id,
        content="修订稿",
        status="completed",
    )

    messages = store.load_messages(conversation.conversation_id)
    assert [item.message_id for item in messages] == [
        first.message_id,
        messages[1].message_id,
    ]
    assert messages[0] == revised


def test_migrate_user_backfills_legacy_json(tmp_path: Path):
    runs_root = tmp_path / "runs"
    conversations_root = tmp_path / "conversations"

    # 先用双写 store 造数据，再清空 SQLite 模拟「只有旧 JSON」的存量状态
    run_store = RunStore(user_id="default", root=runs_root)
    run = run_store.create_run("迁移", "ask")
    run_store.append_stream_event(
        run.run_id, event_id="evt-0", event_type="report.start", payload={}
    )
    conv_store = ConversationStore("alice", root=conversations_root)
    conversation = conv_store.create_conversation("迁移会话")
    conv_store.append_message(conversation.conversation_id, "user", "存量消息")
    for db_path in (runs_root / DB_FILENAME, conversations_root / DB_FILENAME):
        with sqlite3.connect(db_path) as conn:
            for table in ("runs", "run_events", "conversations", "messages"):
                conn.execute(f"DELETE FROM {table}")

    counts = migrate_user(
        "default", runs_root=runs_root, conversations_root=conversations_root
    )
    assert counts == {"runs": 1, "run_events": 1, "conversations": 1, "messages": 1}
    # 幂等：重复执行不产生重复数据
    assert migrate_user(
        "default", runs_root=runs_root, conversations_root=conversations_root
    ) == {"runs": 0, "run_events": 0, "conversations": 0, "messages": 0}

    assert run_store.load_run(run.run_id).run_id == run.run_id
    assert run_store.db.count_run_events(run.run_id) == 1
    assert conv_store.db.count_messages(conversation.conversation_id) == 1
