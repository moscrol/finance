"""板块宇宙 (sector universe) 深模块。

这是生产代码里唯一允许触碰物理代际表
(`fact_sector_daily_generation` / `fact_sector_stock_daily_generation`) 以及
快照/回执表的地方。对外公开的 `fact_sector_daily` /
`fact_sector_stock_daily` 是只读视图, 只暴露某个交易日「唯一已发布代际」,
因此读者不会跨代际混池, 也不需要知道底层存储。

本文件当前实现 Task 2 的范围: schema 装载 + 幂等的 legacy 迁移。
发布 (Task 3)、代际写入 (Task 4)、成员回执 (Task 5)、完成审计 (Task 7)
在后续任务中按同一接口边界补齐。
"""
from __future__ import annotations

from pathlib import Path

import duckdb

PACKAGE_DIR = Path(__file__).resolve().parent
SECTOR_SCHEMA_PATH = PACKAGE_DIR / "sector_schema.sql"

#: 迁移前历史行统一挂在这个哨兵代际下, 它永远不会有 published 表头。
LEGACY_SNAPSHOT_ID = "legacy"

_MIGRATIONS = (
    ("fact_sector_daily", "_legacy_fact_sector_daily", "fact_sector_daily_generation"),
    (
        "fact_sector_stock_daily",
        "_legacy_fact_sector_stock_daily",
        "fact_sector_stock_daily_generation",
    ),
)


def _table_type(con: duckdb.DuckDBPyConnection, name: str) -> str | None:
    row = con.execute(
        """
        SELECT table_type FROM information_schema.tables
        WHERE table_schema = 'main' AND table_name = ?
        """,
        [name],
    ).fetchone()
    return row[0] if row else None


def _columns(con: duckdb.DuckDBPyConnection, name: str) -> tuple[str, ...]:
    rows = con.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = 'main' AND table_name = ?
        ORDER BY ordinal_position
        """,
        [name],
    ).fetchall()
    return tuple(str(row[0]) for row in rows)


def _drop_dependent_indexes(con: duckdb.DuckDBPyConnection, table_name: str) -> None:
    """删掉挂在遗留表上的显式索引。

    生产库上 schema.sql 为两张事实表建了 5 个显式索引; DuckDB 会因为这些依赖拒绝
    `ALTER TABLE ... RENAME`。索引本身是可重建的加速结构, 不含数据: 代际表在
    sector_schema.sql 里重新建了等价索引, 遗留表随迁移结束一起被删除。
    """
    rows = con.execute(
        "SELECT index_name FROM duckdb_indexes() WHERE schema_name = 'main' AND table_name = ?",
        [table_name],
    ).fetchall()
    for (index_name,) in rows:
        con.execute(f'DROP INDEX IF EXISTS "{index_name}"')


def _copy_legacy_rows(
    con: duckdb.DuckDBPyConnection,
    *,
    legacy_name: str,
    generation_name: str,
) -> None:
    """按列名 (不是列序) 把 legacy 行复制进代际表并打上 legacy 戳。

    生产库里 `multi_period_*` / `pct_chg_3d` 等列是历史 ALTER 追加的, 物理列序
    与 schema.sql 不一致, 因此必须按名映射; legacy 表缺失的列补 NULL。
    """
    legacy_columns = set(_columns(con, legacy_name))
    target_columns = [
        column
        for column in _columns(con, generation_name)
        if column != "sector_universe_snapshot_id"
    ]
    selected = ", ".join(
        f'l."{column}"' if column in legacy_columns else f'NULL AS "{column}"'
        for column in target_columns
    )
    quoted_targets = ", ".join(f'"{column}"' for column in target_columns)
    con.execute(
        f'INSERT INTO "{generation_name}" (sector_universe_snapshot_id, {quoted_targets}) '
        f'SELECT ?, {selected} FROM "{legacy_name}" AS l '
        "ON CONFLICT DO NOTHING",
        [LEGACY_SNAPSHOT_ID],
    )


class SectorUniverseStore:
    """板块宇宙的唯一生产入口。

    调用方只使用本类的公开方法; 物理表名不在本模块和
    `market_feature_store/sector_schema.sql` 之外出现。
    """

    def __init__(self, con: duckdb.DuckDBPyConnection) -> None:
        self._con = con

    @property
    def connection(self) -> duckdb.DuckDBPyConnection:
        return self._con

    @staticmethod
    def ensure_schema(con: duckdb.DuckDBPyConnection) -> None:
        """建代际 schema, 并把遗留的两张物理事实表一次性迁进代际存储。

        幂等: 表已经是视图时只重放 DDL, 不再迁移。整个过程在单个事务里,
        任何一步失败都回滚, 遗留表保持原名原状。
        """
        con.execute("BEGIN TRANSACTION")
        try:
            pending: list[tuple[str, str]] = []
            for public_name, legacy_name, generation_name in _MIGRATIONS:
                if _table_type(con, public_name) == "BASE TABLE":
                    _drop_dependent_indexes(con, public_name)
                    con.execute(f'ALTER TABLE "{public_name}" RENAME TO "{legacy_name}"')
                    pending.append((legacy_name, generation_name))

            con.execute(SECTOR_SCHEMA_PATH.read_text(encoding="utf-8"))

            for legacy_name, generation_name in pending:
                _copy_legacy_rows(
                    con,
                    legacy_name=legacy_name,
                    generation_name=generation_name,
                )
            for legacy_name, _generation_name in pending:
                con.execute(f'DROP TABLE "{legacy_name}"')
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
