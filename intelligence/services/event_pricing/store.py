"""旁路库里事件定价的四张表。与 ``methodology_backtest.store`` 同库不同表：

``history_labels`` 的 v3 构建 ``reset_tables`` 会整表 DROP，所以事件表**不混放**进去（第一刀 §3.5 同理），
版本号也另起命名空间 ``ev_version``，与 ``LABEL_VERSION`` / ``framework_version`` 互不覆盖。
"""

from __future__ import annotations

import duckdb

EVENT_DDL = (
    """
    CREATE TABLE IF NOT EXISTS history_event_calendar (
        event_class            VARCHAR NOT NULL,
        indicator              VARCHAR NOT NULL,
        event_date             DATE NOT NULL,
        reaction_day           DATE,
        scheduled              BOOLEAN NOT NULL,
        source_grade           VARCHAR NOT NULL,
        schedule_published_at  DATE,
        period                 VARCHAR,
        editorial_date         DATE,
        reaction_day_confidence VARCHAR,
        event_ids_json         VARCHAR,
        sectors_json           VARCHAR,
        title_sample           VARCHAR,
        ev_version             VARCHAR NOT NULL,
        computed_at            TIMESTAMP NOT NULL,
        PRIMARY KEY (event_class, indicator, event_date)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS history_event_anchors (
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
    CREATE TABLE IF NOT EXISTS history_event_gaps (
        gap_kind    VARCHAR NOT NULL,
        gap_key     VARCHAR NOT NULL,
        reason      VARCHAR NOT NULL,
        detail      VARCHAR,
        ev_version  VARCHAR NOT NULL,
        computed_at TIMESTAMP NOT NULL,
        PRIMARY KEY (gap_kind, gap_key, reason)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS history_event_reaction (
        node_id               VARCHAR PRIMARY KEY,
        event_class           VARCHAR NOT NULL,
        reaction_day          DATE NOT NULL,
        event_date            DATE NOT NULL,
        scheduled             BOOLEAN NOT NULL,
        source_grade          VARCHAR NOT NULL,
        entity_type           VARCHAR NOT NULL,
        entity_id             VARCHAR NOT NULL,
        pre_window_semantics  VARCHAR NOT NULL,
        pre_return_m          DOUBLE,
        d0_return             DOUBLE,
        d0_amount_ratio       DOUBLE,
        d0_limit_up           INTEGER,
        d0_limit_up_delta     INTEGER,
        fwd_return_3          DOUBLE,
        fwd_return_5          DOUBLE,
        fwd_return_10         DOUBLE,
        max_return_10         DOUBLE,
        days_to_peak_10       INTEGER,
        drawdown_after_peak_10 DOUBLE,
        excess_pre_m          DOUBLE,
        excess_d0             DOUBLE,
        excess_fwd_3          DOUBLE,
        excess_fwd_5          DOUBLE,
        excess_fwd_10         DOUBLE,
        shape_tag             VARCHAR,
        crowding_pct_dm1      DOUBLE,
        consensus_stage_dm1   VARCHAR,
        consensus_stage_gap   VARCHAR,
        dispersion_d0_iqr     DOUBLE,
        market_stage_dm1      VARCHAR,
        status                VARCHAR NOT NULL,
        ev_version            VARCHAR NOT NULL,
        computed_at           TIMESTAMP NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS history_event_cross_section (
        event_class   VARCHAR NOT NULL,
        reaction_day  DATE NOT NULL,
        entity_kind   VARCHAR NOT NULL,
        metric        VARCHAR NOT NULL,
        rank          INTEGER NOT NULL,
        entity_id     VARCHAR NOT NULL,
        entity_name   VARCHAR,
        value         DOUBLE,
        ev_version    VARCHAR NOT NULL,
        computed_at   TIMESTAMP NOT NULL,
        PRIMARY KEY (event_class, reaction_day, entity_kind, metric, rank)
    )
    """,
)

EVENT_TABLES = (
    "history_event_calendar",
    "history_event_anchors",
    "history_event_gaps",
    "history_event_reaction",
    "history_event_cross_section",
)
CALENDAR_TABLES = ("history_event_calendar",)
ANCHOR_TABLES = ("history_event_anchors", "history_event_gaps")
REACTION_TABLES = ("history_event_reaction", "history_event_cross_section")


def ensure_event_schema(con: duckdb.DuckDBPyConnection) -> None:
    for stmt in EVENT_DDL:
        con.execute(stmt)


def reset_event_tables(con: duckdb.DuckDBPyConnection, tables: tuple[str, ...]) -> None:
    for name in tables:
        if name not in EVENT_TABLES:
            raise ValueError(f"不是事件表: {name}")
        con.execute(f"DROP TABLE IF EXISTS {name}")
    ensure_event_schema(con)


def table_hash(con: duckdb.DuckDBPyConnection, table: str) -> str:
    """整表内容哈希（排除 computed_at 列），给「两次重建逐行相同」的验收用。"""
    if table not in EVENT_TABLES:
        raise ValueError(f"不是事件表: {table}")
    cols = [
        r[0]
        for r in con.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = ? ORDER BY ordinal_position",
            [table],
        ).fetchall()
        if r[0] != "computed_at"
    ]
    parts = ", ".join(f"coalesce(CAST({c} AS VARCHAR), '<null>')" for c in cols)
    row = con.execute(
        f"SELECT md5(string_agg(row_text, chr(10) ORDER BY row_text)) FROM ("
        f"SELECT concat_ws('|', {parts}) AS row_text FROM {table})"
    ).fetchone()
    return str(row[0]) if row and row[0] is not None else "empty"
