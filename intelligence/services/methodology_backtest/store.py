"""旁路库 ``history_labels.duckdb`` 的表结构与连接助手。

存储决策（设计稿 §5，写死）：标签落旁路 DuckDB，从主库只读重建；不改 ``market_feature_store/schema.sql``、
不写主库。旁路库任何时候可删，``build-labels`` / ``outcomes`` 从主库 + 代码重建，产物带 ``label_version``
与源库 ``max(trade_date)``。

主库通过 ``ATTACH ... (READ_ONLY)`` 挂进来做 join：同一时间只有一个写入连接的红线只对主库成立，
旁路库是我们自己的文件，写它不与夜跑抢锁。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb

from market_feature_store.db import DB_PATH as CANONICAL_DB_PATH
from market_feature_store.db import DatabaseLockedError, is_lock_conflict

SOURCE_ALIAS = "src"
DEFAULT_LABELS_DB_NAME = "history_labels.duckdb"

# 旁路库对象。全部 CREATE TABLE IF NOT EXISTS，重建时先 DROP 对应表再建。
DDL = (
    """
    CREATE TABLE IF NOT EXISTS history_calendar (
        idx         INTEGER PRIMARY KEY,
        trade_date  DATE NOT NULL UNIQUE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS history_labels (
        entity_type   VARCHAR NOT NULL,
        entity_id     VARCHAR NOT NULL,
        trade_date    DATE NOT NULL,
        label         VARCHAR NOT NULL,
        value_num     DOUBLE,
        value_text    VARCHAR,
        label_version VARCHAR NOT NULL,
        computed_at   TIMESTAMP NOT NULL,
        PRIMARY KEY (entity_type, entity_id, trade_date, label)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS history_data_gaps (
        trade_date    DATE PRIMARY KEY,
        reason        VARCHAR NOT NULL,
        zero_ratio    DOUBLE,
        sector_rows   INTEGER,
        label_version VARCHAR NOT NULL,
        computed_at   TIMESTAMP NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS history_outcomes (
        entity_type         VARCHAR NOT NULL,
        entity_id           VARCHAR NOT NULL,
        trade_date          DATE NOT NULL,
        horizon             INTEGER NOT NULL,
        fwd_return          DOUBLE,
        max_return          DOUBLE,
        days_to_peak        INTEGER,
        drawdown_after_peak DOUBLE,
        status              VARCHAR NOT NULL,
        computed_at         TIMESTAMP NOT NULL,
        PRIMARY KEY (entity_type, entity_id, trade_date, horizon)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS history_build_meta (
        build_kind            VARCHAR PRIMARY KEY,
        label_version         VARCHAR NOT NULL,
        source_db             VARCHAR NOT NULL,
        source_max_trade_date DATE,
        source_row_counts     VARCHAR,
        row_count             BIGINT,
        horizons              VARCHAR,
        computed_at           TIMESTAMP NOT NULL
    )
    """,
)

# Teaching-framework objects intentionally use a separate namespace.  The
# existing label reset is a whole-table rebuild; putting these rows in
# ``history_labels`` would allow an unrelated rebuild to delete them.
TEACHING_DDL = (
    """
    CREATE TABLE IF NOT EXISTS history_teaching_labels (
        entity_type   VARCHAR NOT NULL,
        entity_id     VARCHAR NOT NULL,
        trade_date    DATE NOT NULL,
        label         VARCHAR NOT NULL,
        value_num     DOUBLE,
        value_text    VARCHAR,
        label_version VARCHAR NOT NULL,
        framework_version VARCHAR NOT NULL,
        status        VARCHAR NOT NULL DEFAULT 'ok',
        status_reason VARCHAR,
        computed_at   TIMESTAMP NOT NULL,
        PRIMARY KEY (entity_type, entity_id, trade_date, label)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS history_teaching_gaps (
        trade_date        DATE NOT NULL,
        gap_kind          VARCHAR NOT NULL,
        missing_cols      VARCHAR,
        framework_version VARCHAR NOT NULL,
        status             VARCHAR NOT NULL DEFAULT 'gap',
        status_reason     VARCHAR,
        computed_at       TIMESTAMP NOT NULL,
        PRIMARY KEY (trade_date, gap_kind)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS history_leader_succession (
        node_id         VARCHAR UNIQUE,
        break_day       DATE PRIMARY KEY,
        leader_i        VARCHAR,
        leader_i_name   VARCHAR,
        leader_i_peak_boards INTEGER,
        birth_day       DATE,
        leader_next     VARCHAR,
        leader_next_name VARCHAR,
        birth_boards    INTEGER,
        candidates_json VARCHAR,
        gap_days        INTEGER,
        path_json       VARCHAR,
        shape_tags_json VARCHAR,
        handoff         BOOLEAN,
        context_break   VARCHAR,
        context_birth   VARCHAR,
        forward         VARCHAR,
        framework_version VARCHAR,
        status          VARCHAR NOT NULL DEFAULT 'ok',
        status_reason   VARCHAR,
        computed_at     TIMESTAMP NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS history_overtaken (
        event_day       DATE NOT NULL,
        leader_i        VARCHAR NOT NULL,
        leader_next     VARCHAR NOT NULL,
        granularity     VARCHAR NOT NULL,
        status          VARCHAR NOT NULL DEFAULT 'ok',
        status_reason   VARCHAR,
        computed_at     TIMESTAMP NOT NULL,
        PRIMARY KEY (event_day, leader_i, leader_next)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS history_teaching_receipts (
        build_id             VARCHAR PRIMARY KEY,
        build_kind           VARCHAR NOT NULL,
        framework_version    VARCHAR NOT NULL,
        label_version        VARCHAR NOT NULL,
        source_db            VARCHAR NOT NULL,
        source_max_trade_date DATE,
        source_row_counts    VARCHAR,
        source_fingerprint   VARCHAR,
        parameter_hash       VARCHAR NOT NULL,
        coverage_summary     VARCHAR,
        gap_summary          VARCHAR,
        canonical_hash       VARCHAR,
        status               VARCHAR NOT NULL DEFAULT 'ok',
        status_reason        VARCHAR,
        computed_at          TIMESTAMP NOT NULL
    )
    """,
)

LABELS_TABLES = ("history_calendar", "history_labels", "history_data_gaps")
OUTCOMES_TABLES = ("history_outcomes",)
TEACHING_TABLES = (
    "history_teaching_labels",
    "history_teaching_gaps",
    "history_leader_succession",
    "history_overtaken",
    "history_teaching_receipts",
)


def default_labels_db_path(source_db: str | Path | None = None) -> Path:
    """旁路库默认与主库同目录（``db/history_labels.duckdb``），跟着 ``MARKET_FEATURE_STORE_DB`` 走。"""
    base = Path(source_db).expanduser() if source_db else CANONICAL_DB_PATH
    return base.parent / DEFAULT_LABELS_DB_NAME


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def naive_utc(ts: datetime) -> datetime:
    """DuckDB TIMESTAMP 无时区；统一存 UTC 去 tzinfo，读回时按 UTC 解释。"""
    if ts.tzinfo is None:
        return ts
    return ts.astimezone(timezone.utc).replace(tzinfo=None)


def ensure_schema(con: duckdb.DuckDBPyConnection) -> None:
    for stmt in DDL:
        con.execute(stmt)
    for stmt in TEACHING_DDL:
        con.execute(stmt)
    # Keep existing sidecars readable when a new teaching slice adds a
    # version/context column.  Fresh databases get the stricter DDL above;
    # upgraded databases receive nullable columns and a conservative backfill.
    columns = {
        "history_teaching_labels": {"framework_version": "VARCHAR"},
        "history_leader_succession": {"forward": "VARCHAR"},
    }
    for table, additions in columns.items():
        existing = {
            str(row[1])
            for row in con.execute(f"PRAGMA table_info('{table}')").fetchall()
        }
        for name, ddl_type in additions.items():
            if name not in existing:
                con.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl_type}")
        if table == "history_teaching_labels" and "framework_version" not in existing:
            con.execute("UPDATE history_teaching_labels SET framework_version = label_version WHERE framework_version IS NULL")


def reset_tables(con: duckdb.DuckDBPyConnection, tables: tuple[str, ...]) -> None:
    for name in tables:
        con.execute(f"DROP TABLE IF EXISTS {name}")
    ensure_schema(con)


def reset_teaching_tables(con: duckdb.DuckDBPyConnection) -> None:
    """Rebuild only teaching tables, preserving all legacy sidecar tables."""

    for name in TEACHING_TABLES:
        con.execute(f"DROP TABLE IF EXISTS {name}")
    for stmt in TEACHING_DDL:
        con.execute(stmt)


def open_labels_db(path: str | Path, *, read_only: bool) -> duckdb.DuckDBPyConnection:
    p = Path(path).expanduser()
    if read_only and not p.is_file():
        raise FileNotFoundError(f"旁路库不存在: {p}（先跑 build-labels）")
    if not read_only:
        p.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(p), read_only=read_only)
    if not read_only:
        ensure_schema(con)
    return con


def attach_source(con: duckdb.DuckDBPyConnection, source_db: str | Path) -> Path:
    """把主库只读 ATTACH 为 ``src``。库不存在 fail closed；被写锁占用抛 DatabaseLockedError。"""
    p = Path(source_db).expanduser()
    if not p.is_file():
        raise FileNotFoundError(f"canonical DuckDB 不存在: {p}")
    quoted = str(p).replace("'", "''")
    try:
        con.execute(f"ATTACH '{quoted}' AS {SOURCE_ALIAS} (READ_ONLY)")
    except duckdb.IOException as exc:
        if is_lock_conflict(exc):
            raise DatabaseLockedError(f"主库被写进程独占，只读 ATTACH 失败: {exc}") from exc
        raise
    return p


def detach_source(con: duckdb.DuckDBPyConnection) -> None:
    try:
        con.execute(f"DETACH {SOURCE_ALIAS}")
    except duckdb.Error:
        pass


def write_meta(
    con: duckdb.DuckDBPyConnection,
    *,
    build_kind: str,
    label_version: str,
    source_db: Path,
    source_max_trade_date: Any,
    source_row_counts: dict[str, Any],
    row_count: int,
    horizons: tuple[int, ...] | None,
    computed_at: datetime,
) -> None:
    con.execute("DELETE FROM history_build_meta WHERE build_kind = ?", [build_kind])
    con.execute(
        """
        INSERT INTO history_build_meta
            (build_kind, label_version, source_db, source_max_trade_date, source_row_counts,
             row_count, horizons, computed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            build_kind,
            label_version,
            str(source_db),
            source_max_trade_date,
            json.dumps(source_row_counts, ensure_ascii=False, sort_keys=True),
            int(row_count),
            json.dumps(list(horizons)) if horizons is not None else None,
            naive_utc(computed_at),
        ],
    )


def read_meta(con: duckdb.DuckDBPyConnection) -> dict[str, dict[str, Any]]:
    rows = con.execute(
        """
        SELECT build_kind, label_version, source_db, source_max_trade_date, source_row_counts,
               row_count, horizons, computed_at
        FROM history_build_meta
        """
    ).fetchall()
    out: dict[str, dict[str, Any]] = {}
    for kind, version, src, max_date, counts, n, horizons, computed in rows:
        out[str(kind)] = {
            "label_version": version,
            "source_db": src,
            "source_max_trade_date": str(max_date) if max_date is not None else None,
            "source_row_counts": json.loads(counts) if counts else {},
            "row_count": int(n) if n is not None else None,
            "horizons": json.loads(horizons) if horizons else None,
            "computed_at": computed.replace(tzinfo=timezone.utc).isoformat(timespec="seconds")
            if computed is not None
            else None,
        }
    return out


@dataclass
class BuildReport:
    """一次 build 的读数：给 CLI 打印、给收据引用。"""

    build_kind: str
    labels_db: str
    source_db: str
    label_version: str
    source_max_trade_date: str | None
    calendar_start: str | None
    calendar_end: str | None
    calendar_days: int
    row_count: int
    computed_at: str
    rows_by_label: dict[str, int] = field(default_factory=dict)
    data_gap_days: list[str] = field(default_factory=list)
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "build_kind": self.build_kind,
            "labels_db": self.labels_db,
            "source_db": self.source_db,
            "label_version": self.label_version,
            "source_max_trade_date": self.source_max_trade_date,
            "calendar": {
                "start": self.calendar_start,
                "end": self.calendar_end,
                "days": self.calendar_days,
            },
            "row_count": self.row_count,
            "rows_by_label": dict(self.rows_by_label),
            "data_gap_days": list(self.data_gap_days),
            "computed_at": self.computed_at,
            **({"extras": self.extras} if self.extras else {}),
        }
