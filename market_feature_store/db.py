"""DuckDB 连接与初始化助手。

数据库文件默认位于 PROJECT_DIR/db/ 下, 已被 .gitignore 忽略, 不入库。
schema.sql 与本模块同目录, 可重复执行 (全部 CREATE ... IF NOT EXISTS)。

可移植性: 数据库路径可用环境变量 MARKET_FEATURE_STORE_DB 覆盖, 便于在
不同机器 / 自定义目录 / 样本库自测时切换, 不必把库放在仓内 db/ 下。
未设置时回退到 PROJECT_DIR/db/market_feature_store.duckdb (与原行为一致)。
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Callable

import duckdb

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PACKAGE_DIR.parent
_ENV_DB = os.environ.get("MARKET_FEATURE_STORE_DB")
DB_PATH = Path(_ENV_DB).expanduser() if _ENV_DB else PROJECT_DIR / "db" / "market_feature_store.duckdb"
DB_DIR = DB_PATH.parent
SCHEMA_PATH = PACKAGE_DIR / "schema.sql"

# duckdb 对文件锁冲突只给 IOException + 消息文本，没有专用异常类型；
# 两个片段分别覆盖「拿不到锁」与「谁在持锁」两种措辞，缩窄误判面。
_LOCK_CONFLICT_MARKERS = ("Could not set lock", "Conflicting lock")


class DatabaseLockedError(RuntimeError):
    """只读诊断连接在重试窗口内始终拿不到 duckdb 文件锁。

    语义：库文件被写进程（通常是 sync/backfill）独占，检查**没有执行**——
    调用方必须把它与「检查执行了但数据不完整」区分开，不得混报。
    """


def is_lock_conflict(exc: BaseException) -> bool:
    """该异常是否为 duckdb 文件锁冲突（可等待重试），而非其他 IO 故障。"""
    return isinstance(exc, duckdb.IOException) and any(
        marker in str(exc) for marker in _LOCK_CONFLICT_MARKERS
    )


def connect(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """打开 DuckDB 连接。非只读模式会确保 db 目录存在。"""
    if not read_only:
        DB_DIR.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(DB_PATH), read_only=read_only)


def connect_read_only_with_retry(
    *,
    attempts: int = 6,
    delay_seconds: float = 10.0,
    opener: Callable[[], duckdb.DuckDBPyConnection] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> duckdb.DuckDBPyConnection:
    """只读连接 + 文件锁有界重试；等不到锁时抛 DatabaseLockedError。

    供只读诊断类调用方（质检闸门等）使用：夜间 sync/backfill 持写锁是常态，
    直接 connect 会当场炸 IOException，被外层误报成「数据不完整」。这里
    在有界窗口内等写进程收工；非锁类 IOException 原样抛出，不掩盖真故障。

    opener 可注入是为了让调用方保留自己模块级的 connect 绑定
    （既有测试靠 monkeypatch 那个符号换假库），默认走本模块 connect。
    """
    if attempts < 1:
        raise ValueError(f"attempts 必须 >= 1，得到 {attempts}")
    open_connection = opener or (lambda: connect(read_only=True))
    last_error: duckdb.IOException | None = None
    for attempt in range(attempts):
        try:
            return open_connection()
        except duckdb.IOException as exc:
            if not is_lock_conflict(exc):
                raise
            last_error = exc
            if attempt + 1 < attempts:
                sleep(delay_seconds)
    waited = delay_seconds * (attempts - 1)
    raise DatabaseLockedError(
        f"duckdb 文件锁持续被占用：重试 {attempts} 次（约 {waited:.0f}s）仍未拿到"
        f"只读锁；最后错误：{last_error}"
    ) from last_error


def init_db(con: duckdb.DuckDBPyConnection | None = None) -> None:
    """由 SectorUniverseStore.ensure_schema() 统一装载 schema 并完成代际迁移。

    2026-08-02 合 main 后，两张 sector 事实表的 VIEW 定义也进了 schema.sql
    （main a5321eec，与生产库 37 个对象逐一校验）。于是**顺序变成硬约束**：
    必须先把遗留的 BASE TABLE 改名，才能建同名 VIEW，否则 DuckDB 报
    「Existing object fact_sector_daily is of type Table, trying to replace
    with type View」。

    ensure_schema() 内部就是这个顺序（改名 → 重放 schema.sql 全文 → 拷贝遗留行），
    且无条件重放，所以这里不能再先跑一遍 schema.sql——那正好会踩在改名之前。
    """
    from .sector_universe import SectorUniverseStore

    own = con is None
    if own:
        con = connect()
    try:
        SectorUniverseStore.ensure_schema(con)
    finally:
        if own:
            con.close()


def get_published_snapshot_id(con: duckdb.DuckDBPyConnection, trade_date: str) -> str:
    """获取某交易日已发布的 sector_universe_snapshot_id。

    fact_sector_daily / fact_sector_stock_daily 已重构为视图，
    底层 *_generation 表需要 snapshot_id 作为主键的一部分。
    如果当天没有 published 快照，回退到 'legacy'。
    """
    row = con.execute(
        """
        SELECT snapshot_id FROM ops_sector_universe_snapshot_daily
        WHERE trade_date = ? AND status = 'published'
        ORDER BY captured_at DESC LIMIT 1
        """,
        [trade_date],
    ).fetchone()
    return row[0] if row else "legacy"


def list_tables(con: duckdb.DuckDBPyConnection) -> list[str]:
    """返回 main schema 下全部表名 (按名称排序)。"""
    rows = con.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'main'
        ORDER BY table_name
        """
    ).fetchall()
    return [r[0] for r in rows]
