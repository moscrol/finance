"""统一检索缓存（方案 3）：TTL 缓存 + DuckDB per-run 只读连接复用。

两个独立职责：

1. ``RetrievalCache``：key = (source, normalized_query, as_of_date[, revision])，
   value 带 TTL。盘面数据把 as_of_date 编进 key（天然按日隔离，TTL=当日）；
   wiki 命中把索引 revision 编进 key（索引重建即失效）。线程安全。
2. ``duckdb_run_pool``：answer_query 一次运行内各 D 块不再各自
   ``duckdb.connect``，改为 pipeline 持有一个只读连接、provider 借用
   （``connect_readonly`` 返回该连接的独立 cursor，DuckDB cursor 各自线程安全）。
   没有激活 pool 时行为退回逐块独立连接，逐字节不变。
"""
from __future__ import annotations

import re
import threading
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any, Iterator, Literal


def _normalize_query(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "").lower())


DuckDBConnectionStatus = Literal[
    "available", "dependency_unavailable", "open_failed"
]


@dataclass(frozen=True)
class DuckDBConnectionResult:
    status: DuckDBConnectionStatus
    connection: Any | None = None
    error_type: str | None = None
    reason: str | None = None

    @property
    def available(self) -> bool:
        return self.status == "available" and self.connection is not None

    @property
    def locked(self) -> bool:
        return self.reason == "locked"


def is_writer_lock_error(exc: BaseException) -> bool:
    """DuckDB 单写者锁，不是「文件不存在」。认不出就不当成锁。"""

    blob = f"{type(exc).__name__} {exc}".lower()
    markers = ("could not set lock", "conflicting lock", "lock on file")
    return any(marker in blob for marker in markers)


def _load_duckdb() -> Any:
    return import_module("duckdb")


class RetrievalCache:
    """线程安全的 (source, query, as_of[, revision]) → value TTL 缓存。"""

    def __init__(self, default_ttl_seconds: float = 24 * 3600.0) -> None:
        self._default_ttl = default_ttl_seconds
        self._lock = threading.Lock()
        self._entries: dict[tuple, tuple[float, Any]] = {}

    @staticmethod
    def _key(
        source: str,
        query: str,
        as_of_date: str | None,
        revision: str | None,
    ) -> tuple:
        return (source, _normalize_query(query), as_of_date or "", revision or "")

    def get(
        self,
        source: str,
        query: str,
        as_of_date: str | None = None,
        revision: str | None = None,
    ) -> Any | None:
        key = self._key(source, query, as_of_date, revision)
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if time.monotonic() >= expires_at:
                del self._entries[key]
                return None
            return value

    def put(
        self,
        source: str,
        query: str,
        value: Any,
        as_of_date: str | None = None,
        revision: str | None = None,
        ttl_seconds: float | None = None,
    ) -> None:
        key = self._key(source, query, as_of_date, revision)
        ttl = self._default_ttl if ttl_seconds is None else ttl_seconds
        with self._lock:
            self._entries[key] = (time.monotonic() + ttl, value)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


_SHARED = RetrievalCache()


def shared_cache() -> RetrievalCache:
    return _SHARED


class _DuckDBPool:
    """per-run 只读连接池：同一 db 路径复用一个连接，借用方拿独立 cursor。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._connections: dict[str, Any] = {}

    def borrow(self, db_path: str) -> Any | None:
        with self._lock:
            con = self._connections.get(db_path)
            if con is None:
                duckdb = _load_duckdb()

                try:
                    con = duckdb.connect(db_path, read_only=True)
                except Exception:
                    return None
                self._connections[db_path] = con
            return con.cursor()

    def close(self) -> None:
        with self._lock:
            for con in self._connections.values():
                try:
                    con.close()
                except Exception:
                    pass
            self._connections.clear()


_ACTIVE_POOL: ContextVar[_DuckDBPool | None] = ContextVar(
    "duckdb_run_pool", default=None
)


@contextmanager
def duckdb_run_pool() -> Iterator[_DuckDBPool]:
    """在一次 answer_query 运行内激活连接复用；退出时统一关闭。"""
    pool = _DuckDBPool()
    token = _ACTIVE_POOL.set(pool)
    try:
        yield pool
    finally:
        _ACTIVE_POOL.reset(token)
        pool.close()


def connect_readonly(db_path: str | Path) -> Any:
    """借用 per-run 池连接（cursor）；无激活池时开独立只读连接（旧行为）。

    返回对象支持 execute/fetch*/close；调用方照旧 ``con.close()`` 即可
    （池模式下 close 只关 cursor，底层连接由 pool 统一收尾）。
    """
    pool = _ACTIVE_POOL.get()
    if pool is not None:
        cursor = pool.borrow(str(db_path))
        if cursor is not None:
            return cursor
    duckdb = _load_duckdb()

    return duckdb.connect(str(db_path), read_only=True)


def try_connect_readonly(db_path: str | Path) -> DuckDBConnectionResult:
    """Return a structured optional-dependency/open result without raising."""
    try:
        connection = connect_readonly(db_path)
    except (ImportError, ModuleNotFoundError) as exc:
        return DuckDBConnectionResult(
            "dependency_unavailable", error_type=type(exc).__name__
        )
    except Exception as exc:
        return DuckDBConnectionResult(
            "open_failed",
            error_type=type(exc).__name__,
            reason="locked" if is_writer_lock_error(exc) else None,
        )
    return DuckDBConnectionResult("available", connection=connection)
