"""SectorUniverseStore 的临时 DuckDB 接口测试。

全部用例只连接 :memory: 或 tmp_path, 不触碰生产库。
"""
from __future__ import annotations

from datetime import date

import duckdb
import pytest

from market_feature_store import db
from market_feature_store.sector_universe import (
    MemberResult,
    SectorDescriptor,
    SectorUniverseStore,
    SectorUniverseValidationError,
)

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


def _publish(
    con: duckdb.DuckDBPyConnection,
    *,
    captured_at: str = "2026-07-29T10:00:00+08:00",
    suffix: str = "A",
):
    return SectorUniverseStore(con).publish_snapshot(
        trade_date="2026-07-28",
        provider_source="fupanhui",
        sectors=(
            SectorDescriptor(f"990001{suffix}.FP", "MLCC", 2),
            SectorDescriptor(f"990002{suffix}.FP", "6G概念", 1),
        ),
        captured_at=captured_at,
    )


def _daily_rows(suffix: str, pct_chg: float) -> tuple[dict[str, object], ...]:
    return (
        _daily_row(f"990001{suffix}.FP", pct_chg),
        _daily_row(f"990002{suffix}.FP", pct_chg + 0.5),
    )


def _table_type(con: duckdb.DuckDBPyConnection, name: str) -> str | None:
    row = con.execute(
        "select table_type from information_schema.tables "
        "where table_schema = 'main' and table_name = ?",
        [name],
    ).fetchone()
    return row[0] if row else None


def test_public_sector_daily_view_exposes_only_published_generation(store_con):
    store = SectorUniverseStore(store_con)
    published_a = _publish(store_con, suffix="A")
    store.replace_sector_daily(published_a.snapshot_id, _daily_rows("A", 1.0))
    published_b = _publish(
        store_con,
        captured_at="2026-07-29T10:05:00+08:00",
        suffix="B",
    )
    store.replace_sector_daily(published_b.snapshot_id, _daily_rows("B", 2.0))

    assert store_con.execute(
        "select sector_ts_code, pct_chg, sector_universe_snapshot_id "
        "from fact_sector_daily order by sector_ts_code"
    ).fetchall() == [
        ("990001B.FP", 2.0, published_b.snapshot_id),
        ("990002B.FP", 2.5, published_b.snapshot_id),
    ]
    assert store_con.execute(
        "select count(*) from fact_sector_daily_generation"
    ).fetchone() == (4,)


def test_replace_sector_daily_rejects_partial_or_foreign_batch_without_deleting_current(store_con):
    store = SectorUniverseStore(store_con)
    published = _publish(store_con)
    store.replace_sector_daily(published.snapshot_id, _daily_rows("A", 1.0))

    with pytest.raises(SectorUniverseValidationError, match="missing=1, foreign=1"):
        store.replace_sector_daily(
            published.snapshot_id,
            (
                _daily_row("990001A.FP", 9.0),
                _daily_row("FOREIGN.FP", 9.5),
            ),
        )

    assert store_con.execute(
        "select sector_ts_code, pct_chg from fact_sector_daily order by sector_ts_code"
    ).fetchall() == [("990001A.FP", 1.0), ("990002A.FP", 1.5)]


def test_replace_sector_daily_rejects_snapshot_after_it_is_superseded(store_con):
    store = SectorUniverseStore(store_con)
    published_a = _publish(store_con, suffix="A")
    store.replace_sector_daily(published_a.snapshot_id, _daily_rows("A", 1.0))
    _publish(
        store_con,
        captured_at="2026-07-29T10:05:00+08:00",
        suffix="B",
    )

    with pytest.raises(SectorUniverseValidationError, match="published snapshot"):
        store.replace_sector_daily(published_a.snapshot_id, _daily_rows("A", 9.0))

    assert store_con.execute(
        "select pct_chg from fact_sector_daily_generation "
        "where sector_universe_snapshot_id=? order by sector_ts_code",
        [published_a.snapshot_id],
    ).fetchall() == [(1.0,), (1.5,)]


def test_publish_snapshot_retires_absent_provider_rows_only_after_validation(store_con):
    store_con.execute(
        "insert into dim_sector values "
        "('OLD.TI','旧板块',null,true,'2026-07-24','2026-07-24','fupanhui',now())"
    )

    published = SectorUniverseStore(store_con).publish_snapshot(
        trade_date="2026-07-28",
        provider_source="fupanhui",
        sectors=(SectorDescriptor("990001.FP", "MLCC", 27),),
        captured_at="2026-07-29T10:00:00+08:00",
    )

    assert published.sector_count == 1
    assert published.declared_relationship_count == 27
    assert store_con.execute(
        "select is_active from dim_sector where sector_ts_code='OLD.TI'"
    ).fetchone() == (False,)
    assert store_con.execute(
        "select count(*) from ops_sector_universe_snapshot_daily where status='published'"
    ).fetchone() == (1,)
    assert store_con.execute(
        "select status, expected_stock_count from ops_sector_member_sync_daily"
    ).fetchall() == [("pending", 27)]


def test_publish_snapshot_rejects_partial_input_without_changing_active_identities(store_con):
    store_con.execute(
        "insert into dim_sector values "
        "('OLD.TI','旧板块',null,true,'2026-07-24','2026-07-24','fupanhui',now())"
    )

    with pytest.raises(SectorUniverseValidationError, match="non-empty"):
        SectorUniverseStore(store_con).publish_snapshot(
            trade_date="2026-07-28",
            provider_source="fupanhui",
            sectors=(SectorDescriptor("990001.FP", "", 27),),
            captured_at="2026-07-29T10:00:00+08:00",
        )

    assert store_con.execute(
        "select is_active from dim_sector where sector_ts_code='OLD.TI'"
    ).fetchone() == (True,)
    assert store_con.execute(
        "select count(*) from ops_sector_universe_snapshot_daily"
    ).fetchone() == (0,)


def test_publish_snapshot_hash_is_canonical_and_replay_keeps_original_provenance(store_con):
    store = SectorUniverseStore(store_con)
    sectors = (
        SectorDescriptor(" 990002.fp ", "6G概念", 3),
        SectorDescriptor("990001.FP", " MLCC ", 27),
    )

    first = store.publish_snapshot(
        trade_date="2026-07-28",
        provider_source="FUPANHUI",
        sectors=sectors,
        captured_at="2026-07-29T10:00:00+08:00",
    )
    replay = store.publish_snapshot(
        trade_date="2026-07-28",
        provider_source="fupanhui",
        sectors=tuple(reversed(sectors)),
        captured_at="2026-07-29T10:05:00+08:00",
    )

    assert first.snapshot_id == "f6061726ac388b35267d4f3039a41d9596e46374dadf18a02b4615b9ffe666b2"
    assert replay.snapshot_id == first.snapshot_id
    assert replay.captured_at == first.captured_at
    assert store_con.execute(
        "select count(*) from ops_sector_universe_snapshot_daily"
    ).fetchone() == (1,)
    assert store_con.execute(
        "select count(*) from fact_sector_universe_daily"
    ).fetchone() == (2,)
    assert store_con.execute(
        "select count(*) from ops_sector_member_sync_daily"
    ).fetchone() == (2,)


def test_publish_snapshot_rejects_below_95_percent_name_continuity(store_con):
    store = SectorUniverseStore(store_con)
    prior = tuple(
        SectorDescriptor(f"OLD{index:02d}.TI", f"板块{index:02d}", 1)
        for index in range(20)
    )
    store.publish_snapshot(
        trade_date="2026-07-28",
        provider_source="fupanhui",
        sectors=prior,
        captured_at="2026-07-28T18:00:00+08:00",
    )
    partial = tuple(
        SectorDescriptor(f"NEW{index:02d}.FP", f"板块{index:02d}", 1)
        for index in range(18)
    ) + (
        SectorDescriptor("NEW18.FP", "新板块18", 1),
        SectorDescriptor("NEW19.FP", "新板块19", 1),
    )

    with pytest.raises(SectorUniverseValidationError, match="continuity"):
        store.publish_snapshot(
            trade_date="2026-07-29",
            provider_source="fupanhui",
            sectors=partial,
            captured_at="2026-07-29T18:00:00+08:00",
        )

    assert store_con.execute(
        "select status from ops_sector_universe_snapshot_daily where trade_date='2026-07-29'"
    ).fetchall() == [("rejected",)]
    assert store_con.execute(
        "select count(*) from dim_sector where is_active"
    ).fetchone() == (20,)
    assert store_con.execute(
        "select count(*) from ops_sector_member_sync_daily where trade_date='2026-07-29'"
    ).fetchone() == (0,)


def test_publish_snapshot_accepts_exactly_95_percent_normalized_name_continuity(store_con):
    store = SectorUniverseStore(store_con)
    prior = tuple(
        SectorDescriptor(f"OLD{index:02d}.TI", f"板块 {index:02d}", 1)
        for index in range(20)
    )
    store.publish_snapshot(
        trade_date="2026-07-28",
        provider_source="fupanhui",
        sectors=prior,
        captured_at="2026-07-28T18:00:00+08:00",
    )
    current = tuple(
        SectorDescriptor(f"NEW{index:02d}.FP", f"板块　{index:02d}", 1)
        for index in range(19)
    ) + (SectorDescriptor("NEW19.FP", "全新板块", 1),)

    published = store.publish_snapshot(
        trade_date="2026-07-29",
        provider_source="fupanhui",
        sectors=current,
        captured_at="2026-07-29T18:00:00+08:00",
    )

    assert published.sector_count == 20
    assert store_con.execute(
        "select count(*) from dim_sector where is_active and sector_ts_code like 'NEW%.FP'"
    ).fetchone() == (20,)
    assert store_con.execute(
        "select count(*) from dim_sector where is_active and sector_ts_code like 'OLD%.TI'"
    ).fetchone() == (0,)


def test_publish_snapshot_fails_closed_when_existing_headers_violate_single_publish(store_con):
    store_con.executemany(
        "insert into ops_sector_universe_snapshot_daily values "
        "('2026-07-28', ?, 'fupanhui', 1, 1, 'published', ?)",
        [
            ("conflict-a", "2026-07-29T09:00:00+08:00"),
            ("conflict-b", "2026-07-29T09:01:00+08:00"),
        ],
    )

    with pytest.raises(SectorUniverseValidationError, match="published snapshot"):
        SectorUniverseStore(store_con).publish_snapshot(
            trade_date="2026-07-28",
            provider_source="fupanhui",
            sectors=(SectorDescriptor("990001.FP", "MLCC", 27),),
            captured_at="2026-07-29T10:00:00+08:00",
        )

    assert store_con.execute(
        "select snapshot_id, status from ops_sector_universe_snapshot_daily order by snapshot_id"
    ).fetchall() == [("conflict-a", "published"), ("conflict-b", "published")]
    assert store_con.execute(
        "select count(*) from fact_sector_universe_daily"
    ).fetchone() == (0,)


def test_publish_snapshot_supersedes_same_day_generation_without_pooling_rows(store_con):
    store = SectorUniverseStore(store_con)
    first = store.publish_snapshot(
        trade_date="2026-07-28",
        provider_source="fupanhui",
        sectors=(
            SectorDescriptor("990001.FP", "MLCC", 2),
            SectorDescriptor("990002.FP", "6G概念", 1),
        ),
        captured_at="2026-07-29T10:00:00+08:00",
    )
    second = store.publish_snapshot(
        trade_date="2026-07-28",
        provider_source="fupanhui",
        sectors=(
            SectorDescriptor("990001.FP", "MLCC", 3),
            SectorDescriptor("990002.FP", "6G概念", 1),
        ),
        captured_at="2026-07-29T10:05:00+08:00",
    )

    assert first.snapshot_id != second.snapshot_id
    assert store_con.execute(
        "select snapshot_id, status from ops_sector_universe_snapshot_daily order by captured_at"
    ).fetchall() == [
        (first.snapshot_id, "superseded"),
        (second.snapshot_id, "published"),
    ]
    assert store_con.execute(
        "select count(*) from fact_sector_universe_daily"
    ).fetchone() == (4,)
    assert store_con.execute(
        "select count(*) from ops_sector_member_sync_daily"
    ).fetchone() == (4,)


def test_publish_snapshot_replay_rejects_corrupted_persisted_universe(store_con):
    store = SectorUniverseStore(store_con)
    sectors = (
        SectorDescriptor("990001.FP", "MLCC", 2),
        SectorDescriptor("990002.FP", "6G概念", 1),
    )
    published = store.publish_snapshot(
        trade_date="2026-07-28",
        provider_source="fupanhui",
        sectors=sectors,
        captured_at="2026-07-29T10:00:00+08:00",
    )
    store_con.execute(
        "update fact_sector_universe_daily set sector_name='被篡改' "
        "where snapshot_id=? and sector_ts_code='990001.FP'",
        [published.snapshot_id],
    )

    with pytest.raises(SectorUniverseValidationError, match="persisted universe"):
        store.publish_snapshot(
            trade_date="2026-07-28",
            provider_source="fupanhui",
            sectors=sectors,
            captured_at="2026-07-29T10:05:00+08:00",
        )


def test_sync_dim_sector_publishes_provider_counts_through_store(tmp_path, monkeypatch):
    from market_feature_store.sync import sync_fupanhui_sectors as sync_module

    db_path = tmp_path / "sector-sync.duckdb"
    con = duckdb.connect(str(db_path))
    try:
        db.init_db(con)
    finally:
        con.close()

    monkeypatch.setattr(sync_module, "init_db", lambda: None)
    monkeypatch.setattr(sync_module, "connect", lambda: duckdb.connect(str(db_path)))
    monkeypatch.setattr(
        sync_module.fs,
        "list_sectors",
        lambda *, trade_date: [
            {"ts_code": "990001.FP", "name": "MLCC", "stock_count": 27},
            {"ts_code": "990002.FP", "name": "6G概念", "stock_count": 3},
        ],
    )
    monkeypatch.setattr(
        sync_module,
        "lookup_sw_l1",
        lambda name: "电子" if name == "MLCC" else None,
    )

    stats = sync_module.sync_dim_sector(trade_date="2026-07-28")

    assert stats["sector_count"] == 2
    assert stats["declared_relationship_count"] == 30
    assert len(stats["snapshot_id"]) == 64
    assert stats["fetched"] == 2
    assert stats["mapped_sw_l1"] == 1
    assert stats["unmapped_names"] == ["6G概念"]
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        assert con.execute(
            "select sector_ts_code, is_active, sw_l1 from dim_sector order by sector_ts_code"
        ).fetchall() == [
            ("990001.FP", True, "电子"),
            ("990002.FP", True, None),
        ]
        assert con.execute(
            "select expected_stock_count, status from ops_sector_member_sync_daily "
            "order by sector_ts_code"
        ).fetchall() == [(27, "pending"), (3, "pending")]
    finally:
        con.close()


def test_sync_dim_sector_refuses_to_guess_trade_date_when_provider_has_no_latest(monkeypatch):
    from market_feature_store.sync import sync_fupanhui_sectors as sync_module

    monkeypatch.setattr(sync_module, "init_db", lambda: None)
    monkeypatch.setattr(sync_module.fs, "get_latest_date", lambda: None)
    monkeypatch.setattr(
        sync_module.fs,
        "list_sectors",
        lambda **_kwargs: pytest.fail("list endpoint must not run before date validation"),
    )

    with pytest.raises(SectorUniverseValidationError, match="trade date"):
        sync_module.sync_dim_sector()


def test_sync_sector_daily_writes_only_target_date_for_published_universe(tmp_path, monkeypatch):
    from market_feature_store.sync import sync_fupanhui_sector_daily as sync_module

    db_path = tmp_path / "sector-daily-sync.duckdb"
    con = duckdb.connect(str(db_path))
    try:
        db.init_db(con)
        published = SectorUniverseStore(con).publish_snapshot(
            trade_date="2026-07-28",
            provider_source="fupanhui",
            sectors=(
                SectorDescriptor("990001.FP", "MLCC", 2, "电子"),
                SectorDescriptor("990002.FP", "6G概念", 1, "通信"),
            ),
            captured_at="2026-07-29T10:00:00+08:00",
        )
    finally:
        con.close()

    requested: list[str] = []

    def fake_batch(ts_codes, *, trade_date, days):
        requested.extend(ts_codes)
        assert trade_date == "2026-07-28"
        assert days == 25
        return {
            code: [
                {"trade_date": "2026-07-27", "pct_chg": -1.0, "amount": 90.0, "diff_ratio": -2.0},
                {"trade_date": "2026-07-28", "pct_chg": index + 1.0, "amount": 100.0, "diff_ratio": 2.0},
            ]
            for index, code in enumerate(ts_codes)
        }

    monkeypatch.setattr(sync_module, "init_db", lambda: None)
    monkeypatch.setattr(
        sync_module,
        "connect",
        lambda read_only=False: duckdb.connect(str(db_path), read_only=read_only),
    )
    monkeypatch.setattr(sync_module.fs, "get_sector_klines_batch", fake_batch)

    stats = sync_module.sync_fact_sector_daily(trade_date="2026-07-28", days=25)

    assert requested == ["990001.FP", "990002.FP"]
    assert stats["snapshot_id"] == published.snapshot_id
    assert stats["rows_written"] == 2
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        assert con.execute(
            "select trade_date, sector_ts_code, pct_chg, sector_universe_snapshot_id "
            "from fact_sector_daily order by sector_ts_code"
        ).fetchall() == [
            (date(2026, 7, 28), "990001.FP", 1.0, published.snapshot_id),
            (date(2026, 7, 28), "990002.FP", 2.0, published.snapshot_id),
        ]
    finally:
        con.close()


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


# ---------------------------------------------------------------------------
# Task 5：成分同步回执。把"静默丢失的工作"换成持久、可审计的 receipt。
# ---------------------------------------------------------------------------


def _member_status(con: duckdb.DuckDBPyConnection, code: str) -> tuple:
    return con.execute(
        "select status, attempt_count, actual_stock_count, last_error_code "
        "from ops_sector_member_sync_daily where sector_ts_code = ?",
        [code],
    ).fetchone()


def test_publish_creates_one_pending_receipt_per_declared_sector(store_con):
    published = _publish(store_con)
    rows = store_con.execute(
        "select sector_ts_code, status, expected_stock_count, attempt_count "
        "from ops_sector_member_sync_daily where snapshot_id = ? order by sector_ts_code",
        [published.snapshot_id],
    ).fetchall()
    assert rows == [
        ("990001A.FP", "pending", 2, 0),
        ("990002A.FP", "pending", 1, 0),
    ]


def test_error_receipt_does_not_starve_later_sector(store_con):
    """失败的板块不能反复霸占取工作队列，否则后面的板块永远同步不到。"""
    published = _publish(store_con)
    store = SectorUniverseStore(store_con)
    first = store.next_member_work(published.snapshot_id, limit=1, max_attempts=3)
    store.record_member_result(
        published.snapshot_id,
        first[0].sector_ts_code,
        MemberResult.error("provider_timeout"),
    )
    second = store.next_member_work(published.snapshot_id, limit=1, max_attempts=3)
    assert second[0].sector_ts_code != first[0].sector_ts_code


def test_count_mismatch_publishes_no_member_rows(store_con):
    """声明 2 只却只返回 1 只：拒绝，且一行成分事实都不许落库。"""
    published = _publish(store_con)
    store = SectorUniverseStore(store_con)
    result = store.record_member_result(
        published.snapshot_id,
        "990001A.FP",
        MemberResult.success(served_date="2026-07-28", stocks=(_stock("000001.SZ"),)),
    )
    assert result.status == "error"
    assert result.last_error_code == "member_count_mismatch"
    assert store_con.execute(
        "select count(*) from fact_sector_stock_daily_generation"
    ).fetchone() == (0,)


def test_exact_member_success_writes_rows_and_receipt_together(store_con):
    published = _publish(store_con)
    store = SectorUniverseStore(store_con)
    result = store.record_member_result(
        published.snapshot_id,
        "990001A.FP",
        MemberResult.success(
            served_date="2026-07-28",
            stocks=(_stock("000001.SZ"), _stock("000002.SZ")),
        ),
    )
    assert result.status == "success"
    assert _member_status(store_con, "990001A.FP")[:3] == ("success", 1, 2)
    assert store_con.execute(
        "select count(*) from fact_sector_stock_daily_generation "
        "where sector_ts_code = ?",
        ["990001A.FP"],
    ).fetchone() == (2,)


def test_retry_replaces_only_its_own_sector_generation(store_con):
    published = _publish(store_con)
    store = SectorUniverseStore(store_con)
    store.record_member_result(
        published.snapshot_id,
        "990001A.FP",
        MemberResult.success(
            served_date="2026-07-28",
            stocks=(_stock("000001.SZ"), _stock("000002.SZ")),
        ),
    )
    store.record_member_result(
        published.snapshot_id,
        "990002A.FP",
        MemberResult.success(served_date="2026-07-28", stocks=(_stock("000003.SZ"),)),
    )
    store.record_member_result(
        published.snapshot_id,
        "990001A.FP",
        MemberResult.success(
            served_date="2026-07-28",
            stocks=(_stock("000004.SZ"), _stock("000005.SZ")),
        ),
    )
    codes = store_con.execute(
        "select stock_ts_code from fact_sector_stock_daily_generation "
        "order by stock_ts_code"
    ).fetchall()
    assert [c[0] for c in codes] == ["000003.SZ", "000004.SZ", "000005.SZ"]


def test_foreign_sector_is_rejected_without_creating_a_receipt(store_con):
    published = _publish(store_con)
    store = SectorUniverseStore(store_con)
    with pytest.raises(SectorUniverseValidationError):
        store.record_member_result(
            published.snapshot_id,
            "999999Z.FP",
            MemberResult.success(served_date="2026-07-28", stocks=(_stock("000001.SZ"),)),
        )
    assert store_con.execute(
        "select count(*) from ops_sector_member_sync_daily where sector_ts_code = ?",
        ["999999Z.FP"],
    ).fetchone() == (0,)


def test_served_date_must_equal_the_snapshot_trade_date(store_con):
    published = _publish(store_con)
    store = SectorUniverseStore(store_con)
    result = store.record_member_result(
        published.snapshot_id,
        "990002A.FP",
        MemberResult.success(served_date="2026-07-27", stocks=(_stock("000001.SZ"),)),
    )
    assert result.status == "error"
    assert result.last_error_code == "served_date_mismatch"
    assert store_con.execute(
        "select count(*) from fact_sector_stock_daily_generation"
    ).fetchone() == (0,)


def test_duplicate_stock_codes_are_rejected(store_con):
    published = _publish(store_con)
    store = SectorUniverseStore(store_con)
    result = store.record_member_result(
        published.snapshot_id,
        "990001A.FP",
        MemberResult.success(
            served_date="2026-07-28",
            stocks=(_stock("000001.SZ"), _stock("000001.SZ")),
        ),
    )
    assert result.status == "error"
    assert result.last_error_code == "duplicate_member_identity"


def test_work_selection_prefers_pending_then_fewest_attempts(store_con):
    published = _publish(store_con)
    store = SectorUniverseStore(store_con)
    store.record_member_result(
        published.snapshot_id, "990001A.FP", MemberResult.error("provider_timeout")
    )
    work = store.next_member_work(published.snapshot_id, limit=2, max_attempts=3)
    assert [item.sector_ts_code for item in work] == ["990002A.FP", "990001A.FP"]


def test_work_selection_excludes_success_and_exhausted_attempts(store_con):
    published = _publish(store_con)
    store = SectorUniverseStore(store_con)
    store.record_member_result(
        published.snapshot_id,
        "990002A.FP",
        MemberResult.success(served_date="2026-07-28", stocks=(_stock("000003.SZ"),)),
    )
    for _ in range(3):
        store.record_member_result(
            published.snapshot_id, "990001A.FP", MemberResult.error("provider_timeout")
        )
    assert store.next_member_work(published.snapshot_id, limit=5, max_attempts=3) == ()


def test_empty_result_is_retriable_and_keeps_no_rows(store_con):
    published = _publish(store_con)
    store = SectorUniverseStore(store_con)
    result = store.record_member_result(
        published.snapshot_id, "990002A.FP", MemberResult.empty()
    )
    assert result.status == "empty"
    assert store_con.execute(
        "select count(*) from fact_sector_stock_daily_generation"
    ).fetchone() == (0,)
    codes = [
        item.sector_ts_code
        for item in store.next_member_work(published.snapshot_id, limit=5, max_attempts=3)
    ]
    assert "990002A.FP" in codes


def test_member_work_requires_the_published_generation(store_con):
    _publish(store_con)
    store = SectorUniverseStore(store_con)
    with pytest.raises(SectorUniverseValidationError):
        store.next_member_work("not-a-snapshot", limit=1, max_attempts=3)


def test_fast_copy_refuses_a_date_that_has_a_published_universe(store_con):
    """已发布宇宙的交易日不许"复制昨天"——那会造出满足覆盖率但与声明矛盾的成分。"""
    import scripts.fast_daily_sync as fast

    _publish(store_con)
    rows, status = fast.fast_sector_stocks(store_con, "2026-07-28")

    assert rows == 0
    assert status == "refused_published_universe"
    assert store_con.execute(
        "select count(*) from fact_sector_stock_daily_generation"
    ).fetchone() == (0,)


def test_fast_copy_of_a_legacy_date_is_marked_degraded_and_leaves_no_receipt(store_con):
    store_con.execute(
        """
        INSERT INTO fact_sector_stock_daily_generation
            (trade_date, sector_universe_snapshot_id, sector_ts_code, sector_name,
             stock_ts_code, stock_name, source)
        VALUES ('2026-07-21', 'legacy', '990001A.FP', 'MLCC',
                '000001.SZ', '测试股', 'fupanhui')
        """
    )
    import scripts.fast_daily_sync as fast

    rows, status = fast.fast_sector_stocks(store_con, "2026-07-22")

    assert rows == 1
    assert status == "degraded_legacy_copy"
    assert store_con.execute(
        "select distinct sector_universe_snapshot_id "
        "from fact_sector_stock_daily_generation where trade_date = '2026-07-22'"
    ).fetchall() == [("legacy",)]
    assert store_con.execute(
        "select count(*) from ops_sector_member_sync_daily where trade_date = '2026-07-22'"
    ).fetchone() == (0,)


# ---------------------------------------------------------------------------
# Task 6：完成度审计。夜间编排唯一的停止条件, 不许各处自造公式。
# ---------------------------------------------------------------------------

DECLARED_TABLES = frozenset({"fact_sector_daily", "fact_sector_stock_daily"})


def test_completion_audit_denominator_is_the_snapshot_not_dim_sector(store_con):
    """分母必须来自已发布快照。dim_sector 里的陈旧 .TI 身份不得进分母。"""
    published = _publish(store_con)
    store_con.execute(
        "insert into dim_sector(sector_ts_code, sector_name, is_active) "
        "values ('885957.TI', '陈旧身份', true)"
    )
    audit = SectorUniverseStore(store_con).completion_audit(
        "2026-07-28", declared_tables=DECLARED_TABLES
    )
    assert audit.snapshot_id == published.snapshot_id
    assert audit.declared_sector_count == 2
    assert audit.complete is False


def test_completion_audit_counts_each_receipt_state(store_con):
    published = _publish(store_con)
    store = SectorUniverseStore(store_con)
    store.record_member_result(
        published.snapshot_id,
        "990001A.FP",
        MemberResult.success(
            served_date="2026-07-28",
            stocks=(_stock("000001.SZ"), _stock("000002.SZ")),
        ),
    )
    store.record_member_result(
        published.snapshot_id, "990002A.FP", MemberResult.error("provider_timeout")
    )
    audit = store.completion_audit("2026-07-28", declared_tables=DECLARED_TABLES)
    assert audit.status_counts["success"] == 1
    assert audit.status_counts["error"] == 1
    assert audit.retriable_error_count == 1
    assert audit.complete is False


def test_completion_audit_requires_every_declared_table(store_con):
    """成分抓全了但板块日线还没写, 依然不算完成——审计覆盖两张声明表。"""
    published = _publish(store_con)
    store = SectorUniverseStore(store_con)
    store.record_member_result(
        published.snapshot_id,
        "990001A.FP",
        MemberResult.success(
            served_date="2026-07-28",
            stocks=(_stock("000001.SZ"), _stock("000002.SZ")),
        ),
    )
    store.record_member_result(
        published.snapshot_id,
        "990002A.FP",
        MemberResult.success(served_date="2026-07-28", stocks=(_stock("000003.SZ"),)),
    )
    partial = store.completion_audit("2026-07-28", declared_tables=DECLARED_TABLES)
    assert partial.complete is False
    assert "fact_sector_daily" in partial.missing_tables

    store.replace_sector_daily(published.snapshot_id, _daily_rows("A", 1.0))
    done = store.completion_audit("2026-07-28", declared_tables=DECLARED_TABLES)
    assert done.complete is True
    assert done.missing_tables == ()


def test_completion_audit_fails_closed_without_a_published_universe(store_con):
    audit = SectorUniverseStore(store_con).completion_audit(
        "2026-07-28", declared_tables=DECLARED_TABLES
    )
    assert audit.complete is False
    assert audit.snapshot_id is None


# ---------------------------------------------------------------------------
# Task 7：精确门禁。审计必须能区分"看起来齐了"和"逐项对得上"。
# ---------------------------------------------------------------------------


def test_audit_reports_actual_relationship_count_against_declared(store_con):
    """406/407：名称连续性 100% 也不代表关系数对得上，缺一条就不算完成。"""
    published = _publish(store_con)
    store = SectorUniverseStore(store_con)
    store.record_member_result(
        published.snapshot_id,
        "990001A.FP",
        MemberResult.success(
            served_date="2026-07-28",
            stocks=(_stock("000001.SZ"), _stock("000002.SZ")),
        ),
    )
    audit = store.completion_audit("2026-07-28", declared_tables=DECLARED_TABLES)

    assert audit.declared_relationship_count == 3
    assert audit.actual_relationship_count == 2
    assert audit.relationships_match is False
    assert audit.complete is False


def test_audit_relationships_match_only_when_every_sector_is_exact(store_con):
    published = _publish(store_con)
    store = SectorUniverseStore(store_con)
    store.record_member_result(
        published.snapshot_id,
        "990001A.FP",
        MemberResult.success(
            served_date="2026-07-28",
            stocks=(_stock("000001.SZ"), _stock("000002.SZ")),
        ),
    )
    store.record_member_result(
        published.snapshot_id,
        "990002A.FP",
        MemberResult.success(served_date="2026-07-28", stocks=(_stock("000003.SZ"),)),
    )
    store.replace_sector_daily(published.snapshot_id, _daily_rows("A", 1.0))

    audit = store.completion_audit("2026-07-28", declared_tables=DECLARED_TABLES)

    assert audit.actual_relationship_count == 3
    assert audit.relationships_match is True
    assert audit.daily_identities_match is True
    assert audit.member_identities_contained is True
    assert audit.complete is True


def test_audit_rejects_member_facts_outside_the_published_universe(store_con):
    """快照外的板块事实不得被当成完成度的一部分。"""
    published = _publish(store_con)
    store_con.execute(
        """
        INSERT INTO fact_sector_stock_daily_generation
            (trade_date, sector_universe_snapshot_id, sector_ts_code, stock_ts_code)
        VALUES ('2026-07-28', ?, '999999Z.FP', '000009.SZ')
        """,
        [published.snapshot_id],
    )
    audit = SectorUniverseStore(store_con).completion_audit(
        "2026-07-28", declared_tables=DECLARED_TABLES
    )

    assert audit.member_identities_contained is False
    assert audit.complete is False


def test_audit_ignores_legacy_and_superseded_generations(store_con):
    """legacy 迁移行与被取代代际不得计入当日完成度。"""
    published = _publish(store_con)
    store_con.execute(
        """
        INSERT INTO fact_sector_stock_daily_generation
            (trade_date, sector_universe_snapshot_id, sector_ts_code, stock_ts_code)
        VALUES ('2026-07-28', 'legacy', '990001A.FP', '000001.SZ')
        """
    )
    audit = SectorUniverseStore(store_con).completion_audit(
        "2026-07-28", declared_tables=DECLARED_TABLES
    )

    assert audit.snapshot_id == published.snapshot_id
    assert audit.actual_relationship_count == 0
    assert audit.complete is False


def test_audit_counts_critical_nulls(store_con):
    """关键字段为空的行不能算作有效事实。"""
    published = _publish(store_con)
    store = SectorUniverseStore(store_con)
    store.record_member_result(
        published.snapshot_id,
        "990002A.FP",
        MemberResult.success(served_date="2026-07-28", stocks=(_stock("000003.SZ"),)),
    )
    store_con.execute(
        """
        UPDATE fact_sector_stock_daily_generation
        SET stock_name = NULL
        WHERE sector_ts_code = '990002A.FP'
        """
    )
    audit = store.completion_audit("2026-07-28", declared_tables=DECLARED_TABLES)

    assert audit.critical_null_count >= 1
    assert audit.complete is False


def test_audit_reports_adjacent_name_continuity(store_con):
    published = _publish(store_con)
    audit = SectorUniverseStore(store_con).completion_audit(
        "2026-07-28", declared_tables=DECLARED_TABLES
    )

    assert audit.snapshot_id == published.snapshot_id
    # 首个已发布代际没有相邻基准可比，连续性为 None 而非伪造 100%。
    assert audit.name_continuity is None


def test_audit_refuses_a_reduced_table_scope(store_con):
    """声明表范围收窄不得成为拿到绿灯的手段。"""
    _publish(store_con)
    store = SectorUniverseStore(store_con)

    with pytest.raises(SectorUniverseValidationError):
        store.completion_audit("2026-07-28", declared_tables=frozenset())


def test_audit_brief_names_the_failing_dimension(store_con):
    """夜间日志要能一眼看出是哪一项对不上，而不只是 not complete。"""
    published = _publish(store_con)
    store = SectorUniverseStore(store_con)
    store.record_member_result(
        published.snapshot_id,
        "990001A.FP",
        MemberResult.success(
            served_date="2026-07-28",
            stocks=(_stock("000001.SZ"), _stock("000002.SZ")),
        ),
    )
    brief = store.completion_audit(
        "2026-07-28", declared_tables=DECLARED_TABLES
    ).brief()

    assert "rel=2/3" in brief
    assert "relationships" in brief
    assert "daily_identities" in brief
    assert "continuity=-" in brief
