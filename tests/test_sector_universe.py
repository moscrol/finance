"""SectorUniverseStore 的临时 DuckDB 接口测试。

全部用例只连接 :memory: 或 tmp_path, 不触碰生产库。
"""
from __future__ import annotations

import duckdb
import pytest

from market_feature_store import db
from market_feature_store.sector_universe import SectorUniverseStore

LEGACY_SECTOR_DAILY_DDL = (
    "create table fact_sector_daily("
    "trade_date date, sector_ts_code text, sector_name text, sw_l1 text, "
    "pct_chg double, amount double, diff_ratio double, strength double, "
    "multi_period_resonance boolean, multi_period_source text, "
    "multi_period_updated_at timestamp, source text, updated_at timestamp, "
    "primary key(trade_date, sector_ts_code))"
)
LEGACY_SECTOR_STOCK_DAILY_DDL = (
    "create table fact_sector_stock_daily("
    "trade_date date, sector_ts_code text, sector_name text, sw_l1 text, "
    "stock_ts_code text, stock_name text, price double, pct_chg double, "
    "amount double, source text, updated_at timestamp, "
    "primary key(trade_date, sector_ts_code, stock_ts_code))"
)
DIM_SECTOR_DDL = (
    "create table dim_sector(sector_ts_code text primary key, sector_name text, "
    "sw_l1 text, is_active boolean, first_seen_date date, last_seen_date date, "
    "source text, updated_at timestamp)"
)


@pytest.fixture
def store_con():
    con = duckdb.connect(":memory:")
    con.execute(DIM_SECTOR_DDL)
    SectorUniverseStore.ensure_schema(con)
    try:
        yield con
    finally:
        con.close()


def _legacy_con() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:")
    con.execute(DIM_SECTOR_DDL)
    con.execute(LEGACY_SECTOR_DAILY_DDL)
    con.execute(LEGACY_SECTOR_STOCK_DAILY_DDL)
    return con


def _daily_row(code: str, pct_chg: float) -> dict[str, object]:
    return {
        "sector_ts_code": code,
        "sector_name": "测试板块",
        "pct_chg": pct_chg,
        "amount": 100.0,
        "diff_ratio": 2.0,
    }


def _stock(code: str) -> dict[str, object]:
    return {"ts_code": code, "name": "测试股", "price": 10.0, "pct_chg": 1.0, "amount": 100.0}


def _table_type(con: duckdb.DuckDBPyConnection, name: str) -> str | None:
    row = con.execute(
        "select table_type from information_schema.tables "
        "where table_schema = 'main' and table_name = ?",
        [name],
    ).fetchone()
    return row[0] if row else None


def test_ensure_sector_schema_migrates_legacy_tables_and_is_idempotent():
    con = _legacy_con()
    con.execute(
        "insert into fact_sector_daily(trade_date, sector_ts_code, sector_name) "
        "values ('2026-07-24', 'OLD.TI', '旧板块')"
    )
    con.execute(
        "insert into fact_sector_stock_daily(trade_date, sector_ts_code, stock_ts_code) "
        "values ('2026-07-24', 'OLD.TI', '000001.SZ')"
    )

    SectorUniverseStore.ensure_schema(con)
    SectorUniverseStore.ensure_schema(con)

    assert con.execute(
        "select sector_universe_snapshot_id from fact_sector_daily"
    ).fetchall() == [("legacy",)]
    assert con.execute(
        "select sector_universe_snapshot_id from fact_sector_stock_daily"
    ).fetchall() == [("legacy",)]
    assert _table_type(con, "fact_sector_daily") == "VIEW"
    assert _table_type(con, "fact_sector_stock_daily") == "VIEW"
    assert _table_type(con, "fact_sector_daily_generation") == "BASE TABLE"
    assert _table_type(con, "fact_sector_stock_daily_generation") == "BASE TABLE"
    con.close()


def test_ensure_schema_migrates_legacy_tables_that_still_carry_their_indexes():
    """生产库上 legacy 表带着 schema.sql 建的显式索引, RENAME 会被依赖关系拒绝。"""
    con = _legacy_con()
    con.execute("create index idx_fact_sector_daily_date on fact_sector_daily(trade_date)")
    con.execute("create index idx_fact_sector_daily_sector on fact_sector_daily(sector_ts_code)")
    con.execute("create index idx_fact_sector_stock_date on fact_sector_stock_daily(trade_date)")
    con.execute("create index idx_fact_sector_stock_stock on fact_sector_stock_daily(stock_ts_code)")
    con.execute(
        "create index idx_fact_sector_stock_sector on fact_sector_stock_daily(sector_ts_code)"
    )
    con.execute(
        "insert into fact_sector_daily(trade_date, sector_ts_code, sector_name) "
        "values ('2026-07-24', 'OLD.TI', '旧板块')"
    )
    con.execute(
        "insert into fact_sector_stock_daily(trade_date, sector_ts_code, stock_ts_code) "
        "values ('2026-07-24', 'OLD.TI', '000001.SZ')"
    )

    SectorUniverseStore.ensure_schema(con)

    assert con.execute(
        "select sector_name, sector_universe_snapshot_id from fact_sector_daily"
    ).fetchall() == [("旧板块", "legacy")]
    assert con.execute(
        "select stock_ts_code, sector_universe_snapshot_id from fact_sector_stock_daily"
    ).fetchall() == [("000001.SZ", "legacy")]
    assert _table_type(con, "fact_sector_daily") == "VIEW"
    con.close()


def test_ensure_schema_recreates_indexes_on_the_generation_tables():
    con = _legacy_con()
    con.execute("create index idx_fact_sector_daily_date on fact_sector_daily(trade_date)")

    SectorUniverseStore.ensure_schema(con)

    indexes = {
        row[0]
        for row in con.execute(
            "select index_name from duckdb_indexes() where table_name in "
            "('fact_sector_daily_generation','fact_sector_stock_daily_generation')"
        ).fetchall()
    }
    assert "idx_fact_sector_daily_generation_date" in indexes
    assert "idx_fact_sector_daily_generation_snapshot" in indexes
    assert "idx_fact_sector_stock_generation_snapshot" in indexes
    con.close()


def test_ensure_schema_removes_temporary_legacy_tables():
    con = _legacy_con()
    con.execute(
        "insert into fact_sector_daily(trade_date, sector_ts_code) values ('2026-07-24', 'OLD.TI')"
    )

    SectorUniverseStore.ensure_schema(con)

    remaining = con.execute(
        "select table_name from information_schema.tables "
        "where table_schema = 'main' and table_name like '\\_legacy\\_%' escape '\\'"
    ).fetchall()
    assert remaining == []
    con.close()


def test_ensure_schema_maps_legacy_columns_by_name_not_position():
    """生产库的 multi_period_* 列是 ALTER 追加的, 物理列序与 schema.sql 不同。"""
    con = duckdb.connect(":memory:")
    con.execute(DIM_SECTOR_DDL)
    con.execute(
        "create table fact_sector_daily("
        "trade_date date, sector_ts_code text, sector_name text, sw_l1 text, "
        "pct_chg double, amount double, diff_ratio double, strength double, "
        "source text, updated_at timestamp, multi_period_resonance boolean, "
        "multi_period_source text, multi_period_updated_at timestamp, "
        "primary key(trade_date, sector_ts_code))"
    )
    con.execute(LEGACY_SECTOR_STOCK_DAILY_DDL)
    con.execute(
        "insert into fact_sector_daily(trade_date, sector_ts_code, sector_name, pct_chg, "
        "source, multi_period_resonance, multi_period_source) "
        "values ('2026-07-24', 'OLD.TI', '旧板块', 1.5, 'fupanhui', true, 'feishu')"
    )

    SectorUniverseStore.ensure_schema(con)

    assert con.execute(
        "select sector_name, pct_chg, source, multi_period_resonance, multi_period_source "
        "from fact_sector_daily"
    ).fetchall() == [("旧板块", 1.5, "fupanhui", True, "feishu")]
    con.close()


def test_ensure_schema_fills_columns_absent_from_an_older_legacy_table():
    con = duckdb.connect(":memory:")
    con.execute(DIM_SECTOR_DDL)
    con.execute(LEGACY_SECTOR_DAILY_DDL)
    con.execute(
        "create table fact_sector_stock_daily("
        "trade_date date, sector_ts_code text, stock_ts_code text, stock_name text, "
        "primary key(trade_date, sector_ts_code, stock_ts_code))"
    )
    con.execute(
        "insert into fact_sector_stock_daily values "
        "('2026-07-24', 'OLD.TI', '000001.SZ', '测试股')"
    )

    SectorUniverseStore.ensure_schema(con)

    assert con.execute(
        "select stock_name, price, mcap_source, sector_universe_snapshot_id "
        "from fact_sector_stock_daily"
    ).fetchall() == [("测试股", None, None, "legacy")]
    con.close()


def test_ensure_schema_rolls_back_and_keeps_legacy_tables_when_copy_fails(monkeypatch):
    con = _legacy_con()
    con.execute(
        "insert into fact_sector_daily(trade_date, sector_ts_code, sector_name) "
        "values ('2026-07-24', 'OLD.TI', '旧板块')"
    )

    con.execute("create index idx_fact_sector_daily_date on fact_sector_daily(trade_date)")

    import market_feature_store.sector_universe as module

    def boom(_con, *_args, **_kwargs):
        raise RuntimeError("copy failed")

    monkeypatch.setattr(module, "_copy_legacy_rows", boom)

    with pytest.raises(RuntimeError, match="copy failed"):
        SectorUniverseStore.ensure_schema(con)

    assert _table_type(con, "fact_sector_daily") == "BASE TABLE"
    assert con.execute(
        "select sector_name from fact_sector_daily"
    ).fetchall() == [("旧板块",)]
    assert _table_type(con, "fact_sector_daily_generation") is None
    # 事务回滚必须把摘掉的索引一并还回来, 否则失败的迁移会静默降低生产查询性能。
    assert con.execute(
        "select index_name from duckdb_indexes() where table_name = 'fact_sector_daily'"
    ).fetchall() == [("idx_fact_sector_daily_date",)]
    con.close()


def test_ensure_schema_on_a_fresh_database_creates_empty_published_views():
    con = duckdb.connect(":memory:")
    con.execute(DIM_SECTOR_DDL)

    SectorUniverseStore.ensure_schema(con)

    assert _table_type(con, "fact_sector_daily") == "VIEW"
    assert con.execute("select count(*) from fact_sector_daily").fetchone() == (0,)
    assert con.execute("select count(*) from fact_sector_stock_daily").fetchone() == (0,)
    assert con.execute(
        "select count(*) from ops_sector_universe_snapshot_daily"
    ).fetchone() == (0,)
    assert con.execute("select count(*) from fact_sector_universe_daily").fetchone() == (0,)
    assert con.execute("select count(*) from ops_sector_member_sync_daily").fetchone() == (0,)
    con.close()


def test_published_generation_hides_legacy_rows_for_the_same_date(store_con):
    store_con.execute(
        "insert into fact_sector_daily_generation(trade_date, sector_universe_snapshot_id, "
        "sector_ts_code, pct_chg) values ('2026-07-28', 'legacy', 'OLD.TI', 9.0)"
    )
    store_con.execute(
        "insert into fact_sector_daily_generation(trade_date, sector_universe_snapshot_id, "
        "sector_ts_code, pct_chg) values ('2026-07-28', 'snap-a', '990001.FP', 1.0)"
    )
    assert store_con.execute("select sector_ts_code from fact_sector_daily").fetchall() == [
        ("OLD.TI",)
    ]

    store_con.execute(
        "insert into ops_sector_universe_snapshot_daily values "
        "('2026-07-28', 'snap-a', 'fupanhui', 1, 1, 'published', '2026-07-29T10:00:00+08:00')"
    )

    assert store_con.execute(
        "select sector_ts_code, pct_chg from fact_sector_daily"
    ).fetchall() == [("990001.FP", 1.0)]
    assert store_con.execute(
        "select count(*) from fact_sector_daily_generation"
    ).fetchone() == (2,)


def test_candidate_and_superseded_generations_stay_out_of_the_public_view(store_con):
    for snapshot_id, status in (("snap-a", "superseded"), ("snap-b", "candidate")):
        store_con.execute(
            "insert into ops_sector_universe_snapshot_daily values "
            "('2026-07-28', ?, 'fupanhui', 1, 1, ?, '2026-07-29T10:00:00+08:00')",
            [snapshot_id, status],
        )
        store_con.execute(
            "insert into fact_sector_stock_daily_generation(trade_date, "
            "sector_universe_snapshot_id, sector_ts_code, stock_ts_code) "
            "values ('2026-07-28', ?, '990001.FP', '000001.SZ')",
            [snapshot_id],
        )

    assert store_con.execute("select count(*) from fact_sector_stock_daily").fetchone() == (0,)
    assert store_con.execute(
        "select count(*) from fact_sector_stock_daily_generation"
    ).fetchone() == (2,)


def test_public_views_reject_direct_writes(store_con):
    with pytest.raises(duckdb.Error):
        store_con.execute(
            "insert into fact_sector_daily(trade_date, sector_ts_code) "
            "values ('2026-07-28', '990001.FP')"
        )


def test_init_db_installs_the_sector_migration(tmp_path, monkeypatch):
    db_path = tmp_path / "market_feature_store.duckdb"
    con = duckdb.connect(str(db_path))
    try:
        con.execute(db.SCHEMA_PATH.read_text(encoding="utf-8"))
        con.execute(LEGACY_SECTOR_DAILY_DDL)
        con.execute(LEGACY_SECTOR_STOCK_DAILY_DDL)
        con.execute(
            "insert into fact_sector_daily(trade_date, sector_ts_code, sector_name) "
            "values ('2026-07-24', 'OLD.TI', '旧板块')"
        )
    finally:
        con.close()

    monkeypatch.setattr(db, "DB_PATH", db_path)
    monkeypatch.setattr(db, "DB_DIR", tmp_path)
    db.init_db()

    con = duckdb.connect(str(db_path))
    try:
        assert _table_type(con, "fact_sector_daily") == "VIEW"
        assert con.execute(
            "select sector_name, sector_universe_snapshot_id from fact_sector_daily"
        ).fetchall() == [("旧板块", "legacy")]
    finally:
        con.close()


def test_schema_sql_no_longer_defines_the_physical_sector_facts():
    schema = db.SCHEMA_PATH.read_text(encoding="utf-8").lower()
    assert "create table if not exists fact_sector_daily " not in schema
    assert "create table if not exists fact_sector_daily(" not in schema
    assert "create table if not exists fact_sector_stock_daily " not in schema
    assert "create table if not exists fact_sector_stock_daily(" not in schema
