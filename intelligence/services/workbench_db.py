"""Workbench 应用态的 SQLite 存储层（run_store / conversation_store 共用）。

为什么是 SQLite（教学）：

- **它是什么**：嵌入式事务数据库——单文件、无服务进程、Python 标准库自带
  （``sqlite3``）。手机 App、浏览器、macOS 系统本身都用它存应用状态。
- **为什么用它换 JSON 文件**：旧实现「整文件读→改→写回 + 自管文件锁」有三个
  结构性问题：并发写不安全（锁写错就丢数据）、写一半被杀留下半截坏 JSON（非
  原子）、全局查询要遍历几百个文件。SQLite 的 WAL（write-ahead log）先写日志
  再改数据页，断电/被杀后自动回滚到一致状态（ACID 原子性）；并发由数据库内置
  锁 + WAL 处理；查询走索引。
- **为什么不是 DuckDB**：DuckDB 是分析型列存（OLAP，单写者模型），适合复盘/
  行情大表聚合；run 事件流是「高频小事务」（OLTP），SQLite(WAL) 才是对口工具。
  这个 OLAP vs OLTP 的分工在别的项目也通用（面试常考点）。
- **过渡策略：双写**：写路径同时落 SQLite 和旧 JSON 文件（canonical 逐步切到
  SQLite，旧文件保留 git diff / jq 可读性与回滚余地）；读路径优先 SQLite，
  查不到再回退旧文件（存量数据零迁移也能读）。跑稳一段时间后可摘掉旧写。

线程/进程安全模型：

- 每次操作独立 ``sqlite3.connect``（连接不跨线程复用，规避 sqlite 线程限制）；
- ``PRAGMA journal_mode=WAL`` 允许读写并发；``busy_timeout`` 让写锁竞争时
  等待而不是立刻报 ``database is locked``；
- 唯一性由表约束保证（如 ``run_events`` 的 ``(run_id, seq)`` / ``(run_id,
  event_id)``），跨进程并发写重复直接被数据库拒绝——不再依赖调用方自觉加锁。
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

DB_FILENAME = "workbench.sqlite3"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id     TEXT PRIMARY KEY,
    user       TEXT NOT NULL,
    status     TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_runs_status ON runs (status);

CREATE TABLE IF NOT EXISTS run_events (
    run_id   TEXT    NOT NULL,
    seq      INTEGER NOT NULL,
    event_id TEXT    NOT NULL,
    payload  TEXT    NOT NULL,
    PRIMARY KEY (run_id, seq),
    UNIQUE (run_id, event_id)
);

CREATE TABLE IF NOT EXISTS conversations (
    conversation_id TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    payload         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_conversations_updated
    ON conversations (user_id, updated_at);

CREATE TABLE IF NOT EXISTS messages (
    record_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    message_id      TEXT NOT NULL,
    payload         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_conversation
    ON messages (conversation_id, record_id);
"""


class WorkbenchDB:
    """``workbench.sqlite3`` 的薄封装：建表 + 各表的最小读写原语。"""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    # ---------- runs ----------

    def upsert_run(self, payload: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO runs (run_id, user, status, created_at, payload)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    user = excluded.user,
                    status = excluded.status,
                    created_at = excluded.created_at,
                    payload = excluded.payload
                """,
                (
                    payload["run_id"],
                    payload["user"],
                    payload["status"],
                    payload["created_at"],
                    json.dumps(payload, ensure_ascii=False),
                ),
            )

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def list_runs(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT payload FROM runs ORDER BY run_id"
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

    # ---------- run_events ----------

    def count_run_events(self, run_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM run_events WHERE run_id = ?", (run_id,)
            ).fetchone()
        return int(row[0])

    def insert_run_event(self, run_id: str, seq: int, event_id: str, payload: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO run_events (run_id, seq, event_id, payload) VALUES (?, ?, ?, ?)",
                (run_id, seq, event_id, json.dumps(payload, ensure_ascii=False)),
            )

    def insert_run_events(self, run_id: str, events: list[dict[str, Any]]) -> None:
        """批量回填（幂等：已存在的 (run_id, seq) 跳过）。"""
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT OR IGNORE INTO run_events (run_id, seq, event_id, payload)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (
                        run_id,
                        event["seq"],
                        event["event_id"],
                        json.dumps(event, ensure_ascii=False),
                    )
                    for event in events
                ],
            )

    def get_run_events(self, run_id: str, after: int = 0) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT payload FROM run_events WHERE run_id = ? AND seq > ? ORDER BY seq",
                (run_id, after),
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

    # ---------- conversations ----------

    def upsert_conversation(self, payload: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO conversations (conversation_id, user_id, updated_at, payload)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(conversation_id) DO UPDATE SET
                    user_id = excluded.user_id,
                    updated_at = excluded.updated_at,
                    payload = excluded.payload
                """,
                (
                    payload["conversation_id"],
                    payload["user_id"],
                    payload["updated_at"],
                    json.dumps(payload, ensure_ascii=False),
                ),
            )

    def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM conversations WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def list_conversation_ids(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute("SELECT conversation_id FROM conversations").fetchall()
        return [row[0] for row in rows]

    # ---------- messages ----------

    def count_messages(self, conversation_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM messages WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchone()
        return int(row[0])

    def append_message(self, payload: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO messages (conversation_id, message_id, payload) VALUES (?, ?, ?)",
                (
                    payload["conversation_id"],
                    payload["message_id"],
                    json.dumps(payload, ensure_ascii=False),
                ),
            )

    def append_messages(self, payloads: list[dict[str, Any]]) -> None:
        with self._connect() as conn:
            conn.executemany(
                "INSERT INTO messages (conversation_id, message_id, payload) VALUES (?, ?, ?)",
                [
                    (
                        payload["conversation_id"],
                        payload["message_id"],
                        json.dumps(payload, ensure_ascii=False),
                    )
                    for payload in payloads
                ],
            )

    def get_messages(self, conversation_id: str) -> list[dict[str, Any]]:
        """按写入顺序返回全部消息记录（含同 message_id 的修订记录）。"""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT payload FROM messages WHERE conversation_id = ? ORDER BY record_id",
                (conversation_id,),
            ).fetchall()
        return [json.loads(row[0]) for row in rows]
