"""DuckDB 连接与初始化助手。

数据库文件默认位于 PROJECT_DIR/db/ 下, 已被 .gitignore 忽略, 不入库。
schema.sql 与本模块同目录, 可重复执行 (全部 CREATE ... IF NOT EXISTS)。

可移植性: 数据库路径可用环境变量 MARKET_FEATURE_STORE_DB 覆盖, 便于在
不同机器 / 自定义目录 / 样本库自测时切换, 不必把库放在仓内 db/ 下。
未设置时回退到 PROJECT_DIR/db/market_feature_store.duckdb (与原行为一致)。
"""
from __future__ import annotations

import os
from pathlib import Path

import duckdb

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PACKAGE_DIR.parent
_ENV_DB = os.environ.get("MARKET_FEATURE_STORE_DB")
DB_PATH = Path(_ENV_DB).expanduser() if _ENV_DB else PROJECT_DIR / "db" / "market_feature_store.duckdb"
DB_DIR = DB_PATH.parent
SCHEMA_PATH = PACKAGE_DIR / "schema.sql"


def connect(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """打开 DuckDB 连接。非只读模式会确保 db 目录存在。"""
    if not read_only:
        DB_DIR.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(DB_PATH), read_only=read_only)


def init_db(con: duckdb.DuckDBPyConnection | None = None) -> None:
    """执行 schema.sql 建表。可传入已有连接, 否则自建。"""
    own = con is None
    if own:
        con = connect()
    try:
        con.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
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
