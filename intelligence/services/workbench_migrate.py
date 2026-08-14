"""存量 JSON/JSONL → SQLite 的一次性回填（幂等，可重复跑）。

双写上线后，新写入自动进 SQLite；本模块把**历史** run/conversation 数据批量
回填进 ``workbench.sqlite3``，让读路径不再依赖旧文件回退。

幂等策略：runs/conversations 用 ``INSERT OR IGNORE``（不覆盖 SQLite 里更新的
状态），run_events 靠 ``(run_id, seq)`` 主键去重，messages 只在该会话在
SQLite 中还没有任何记录时整体搬入——重复执行不会产生重复数据。
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from intelligence.services.conversation_store import ConversationStore
from intelligence.services.run_store import RunStore


def migrate_user(
    user_id: str | None = None,
    *,
    runs_root: Path | None = None,
    conversations_root: Path | None = None,
) -> dict[str, int]:
    """把一个用户的存量 run/conversation JSON 数据回填进 SQLite，返回计数。"""
    counts = {"runs": 0, "run_events": 0, "conversations": 0, "messages": 0}

    run_store = RunStore(user_id, root=runs_root)
    if run_store.root.exists():
        for run_file in sorted(run_store.root.glob("run_*/run.json")):
            payload = json.loads(run_file.read_text(encoding="utf-8"))
            run_id = payload["run_id"]
            if run_store.db.get_run(run_id) is None:
                run_store.db.upsert_run(payload)
                counts["runs"] += 1
            if run_store.db.count_run_events(run_id) == 0:
                events = run_store._load_stream_events_from_file(run_id)
                if events:
                    run_store.db.insert_run_events(run_id, events)
                    counts["run_events"] += len(events)

    conversation_store = ConversationStore(
        user_id if user_id is not None else "demo", root=conversations_root
    )
    if conversation_store.root.exists():
        for directory in sorted(conversation_store.root.iterdir()):
            if not directory.is_dir() or not (directory / "conversation.json").is_file():
                continue
            conversation_id = directory.name
            if conversation_store.db.get_conversation(conversation_id) is None:
                payload = json.loads(
                    (directory / "conversation.json").read_text(encoding="utf-8")
                )
                conversation_store.db.upsert_conversation(payload)
                counts["conversations"] += 1
            if conversation_store.db.count_messages(conversation_id) == 0:
                messages = conversation_store._load_messages_from_file(conversation_id)
                if messages:
                    conversation_store.db.append_messages(
                        [asdict(message) for message in messages]
                    )
                    counts["messages"] += len(messages)

    return counts
