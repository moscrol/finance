"""DuckDB 连接与初始化助手。

数据库文件位于 PROJECT_DIR/db/ 下, 已被 .gitignore 忽略, 不入库。
schema.sql 与本模块同目录, 可重复执行 (全部 CREATE ... IF NOT EXISTS)。
"""
from __future__ import annotations

from pathlib import Path

import duckdb

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PACKAGE_DIR.parent
DB_DIR = PROJECT_DIR / "db"
DB_PATH = DB_DIR / "market_feature_store.duckdb"
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
