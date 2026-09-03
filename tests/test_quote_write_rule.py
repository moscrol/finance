"""成分股表「一行必须至少带一个行情值」的三层规则 + 空壳清除/压缩维护。

层 ①: SectorUniverseStore.record_member_result 丢无报价行、整板块无报价记 error 回执;
层 ②: schema.sql 的 CHECK 兜住任何裸 INSERT;
层 ③: quality.check_daily 的空壳板块检查让漏网之鱼 FAIL。
维护: maintenance.run_maintenance_staged 把旧库 (无 CHECK、有空壳) 重建 + 压缩 + 换名。

全部用例只连 :memory: 或 tmp_path。
"""
from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from market_feature_store import db as _db
from market_feature_store import maintenance, quality
from market_feature_store.sector_universe import (
    MemberResult,
    SectorUniverseStore,
    SectorUniverseValidationError,
)

DIM_SECTOR_DDL = (
    "create table dim_sector(sector_ts_code text primary key, sector_name text not null, "
    "sw_l1 text, is_active boolean, first_seen_date date, last_seen_date date, "
    "source text, updated_at timestamp)"
)
TABLE = "fact_sector_stock_daily_generation"


def _fresh(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(DIM_SECTOR_DDL)
    SectorUniverseStore.ensure_schema(con)


@pytest.fixture
def con():
    con = duckdb.connect(":memory:")
    _fresh(con)
    try:
        yield con
    finally:
        con.close()


def _publish(con, *, sectors=(("990001A.FP", "板块A", 3),)):
    """发布一份最小宇宙, 返回 snapshot_id。"""
    from market_feature_store.sector_universe import SectorDescriptor

    for code, name, _n in sectors:
        con.execute(
            "insert into dim_sector(sector_ts_code, sector_name, is_active) values (?, ?, true)",
            [code, name],
        )
    published = SectorUniverseStore(con).publish_snapshot(
        trade_date="2026-07-28",
        provider_source="fupanhui",
        sectors=tuple(SectorDescriptor(code, name, n) for code, name, n in sectors),
        captured_at="2026-07-29T10:00:00+08:00",
    )
    return published.snapshot_id


def _stock(code: str, **quote) -> dict:
    row = {"ts_code": code, "name": "股" + code[:6]}
    row.update(quote)
    return row


# ---------------------------------------------------------------------------
# 层 ②: CHECK
# ---------------------------------------------------------------------------


def test_schema_check_rejects_row_without_any_quote(con):
    with pytest.raises(duckdb.ConstraintException):
        con.execute(
            f"insert into {TABLE}(trade_date, sector_universe_snapshot_id, sector_ts_code, stock_ts_code) "
            "values ('2026-07-28', 'legacy', '990001A.FP', '000001.SZ')"
        )
    # 三个行情列任一非空即可 (停牌股 amount=0 也算有行情)
    con.execute(
        f"insert into {TABLE}(trade_date, sector_universe_snapshot_id, sector_ts_code, stock_ts_code, amount) "
        "values ('2026-07-28', 'legacy', '990001A.FP', '000001.SZ', 0)"
    )
    assert maintenance.has_quote_check(con) is True


# ---------------------------------------------------------------------------
# 层 ①: 正门写入者
# ---------------------------------------------------------------------------


def test_member_result_drops_quoteless_rows_but_keeps_the_sector(con):
    snapshot_id = _publish(con)
    receipt = SectorUniverseStore(con).record_member_result(
        snapshot_id,
        "990001A.FP",
        MemberResult.success(
            served_date="2026-07-28",
            stocks=(
                _stock("000001.SZ", price=10.0, pct_chg=1.0, amount=5.0),
                _stock("000002.SZ", amount=0.0),  # 停牌: 只有 amount, 仍算有行情
                _stock("000003.SZ"),  # 无任何行情 → 当作未交付
            ),
        ),
    )
    assert receipt.status == "success"
    assert receipt.actual_stock_count == 2  # 丢掉的那只进缺口账 (expected 3 - actual 2)
    assert receipt.last_error_code is None
    assert sorted(
        r[0] for r in con.execute(f"select stock_ts_code from {TABLE}").fetchall()
    ) == ["000001.SZ", "000002.SZ"]


def test_member_result_rejects_sector_where_every_row_is_quoteless(con):
    snapshot_id = _publish(con)
    receipt = SectorUniverseStore(con).record_member_result(
        snapshot_id,
        "990001A.FP",
        MemberResult.success(
            served_date="2026-07-28",
            stocks=(_stock("000001.SZ"), _stock("000002.SZ"), _stock("000003.SZ")),
        ),
    )
    assert receipt.status == "error"
    assert receipt.last_error_code == "member_rows_quoteless"
    assert receipt.actual_stock_count is None
    assert con.execute(f"select count(*) from {TABLE}").fetchone() == (0,)
    # error 是可重试状态: 下一轮 next_member_work 仍会排到它
    codes = [
        item.sector_ts_code
        for item in SectorUniverseStore(con).next_member_work(snapshot_id, limit=5, max_attempts=3)
    ]
    assert "990001A.FP" in codes


def test_copy_legacy_member_generation_is_retired(con):
    con.execute(
        f"insert into {TABLE}(trade_date, sector_universe_snapshot_id, sector_ts_code, stock_ts_code, price) "
        "values ('2026-07-21', 'legacy', '990001A.FP', '000001.SZ', 10.0)"
    )
    with pytest.raises(SectorUniverseValidationError, match="retired"):
        SectorUniverseStore(con).copy_legacy_member_generation(
            target_date="2026-07-22", source_date="2026-07-21"
        )
    assert con.execute(f"select count(*) from {TABLE} where trade_date='2026-07-22'").fetchone() == (0,)


# ---------------------------------------------------------------------------
# 层 ③: 量具
# ---------------------------------------------------------------------------


def _seed_quality_calendar(con) -> None:
    con.execute(
        "insert into fact_market_daily(trade_date, total_amount) values ('2026-07-27', 1.5e12), ('2026-07-28', 1.6e12)"
    )


def test_check_daily_flags_quoteless_sectors(con):
    """CHECK 存在时正常写不出空壳; 这里模拟旧库形态 (去掉 CHECK) 验证量具独立于写入路径。"""
    _seed_quality_calendar(con)
    con.execute("drop view fact_sector_stock_daily")
    con.execute(f"drop table {TABLE}")
    con.execute(maintenance.target_table_ddl(TABLE).replace(
        ",\n    CHECK (price IS NOT NULL OR pct_chg IS NOT NULL OR amount IS NOT NULL)", ""
    ))
    SectorUniverseStore.ensure_schema(con)
    con.executemany(
        f"insert into {TABLE}(trade_date, sector_universe_snapshot_id, sector_ts_code, sector_name, stock_ts_code, price) "
        "values (?, 'legacy', ?, ?, ?, ?)",
        [
            ("2026-07-28", "990001A.FP", "空壳板块", "000001.SZ", None),
            ("2026-07-28", "990001A.FP", "空壳板块", "000002.SZ", None),
            ("2026-07-28", "990002A.FP", "正常板块", "000003.SZ", 10.0),
            ("2026-07-28", "990002A.FP", "正常板块", "000004.SZ", None),  # 部分空不算空壳板块
        ],
    )
    quoteless = quality.quoteless_sectors("2026-07-28", con)
    assert quoteless == [{"sector_ts_code": "990001A.FP", "sector_name": "空壳板块", "rows": 2}]

    report = quality.check_daily("2026-07-28", con, tables=["fact_sector_stock_daily"])
    assert report["ok"] is False
    assert report["quoteless_sectors"] == quoteless
    assert "空壳板块 1 个共 2 行" in report["brief"]


def test_check_daily_passes_when_rows_carry_quotes(con):
    _seed_quality_calendar(con)
    con.execute(
        f"insert into {TABLE}(trade_date, sector_universe_snapshot_id, sector_ts_code, sector_name, stock_ts_code, price) "
        "values ('2026-07-28', 'legacy', '990002A.FP', '正常板块', '000003.SZ', 10.0)"
    )
    report = quality.check_daily("2026-07-28", con, tables=["fact_sector_stock_daily"])
    assert report["quoteless_sectors"] == []
    assert report["ok"] is True


# ---------------------------------------------------------------------------
# 维护: 重建 (删空壳 + 装 CHECK) + 压缩 + 换名
# ---------------------------------------------------------------------------


def _legacy_shaped_db(path: Path) -> dict:
    """造一个「生产库旧形态」: 目标表没有 CHECK、混着空壳行与真行, 其他表也有数据。"""
    con = duckdb.connect(str(path))
    try:
        _fresh(con)
        con.execute("drop view fact_sector_stock_daily")
        con.execute(f"drop table {TABLE}")
        con.execute(maintenance.target_table_ddl(TABLE).replace(
            ",\n    CHECK (price IS NOT NULL OR pct_chg IS NOT NULL OR amount IS NOT NULL)", ""
        ))
        SectorUniverseStore.ensure_schema(con)  # 重建索引 + 视图
        con.execute(
            "insert into fact_market_daily(trade_date, total_amount) values ('2026-07-27', 1.5e12), ('2026-07-28', 1.6e12)"
        )
        con.execute(
            "insert into dim_sector(sector_ts_code, sector_name, is_active) values ('990001A.FP', '板块A', true)"
        )
        rows = []
        for day in ("2026-07-21", "2026-07-22", "2026-07-23"):
            for i in range(50):
                rows.append((day, "legacy", "990001A.FP", "板块A", f"{i:06d}.SZ", None, None, None, None))
        for i in range(30):
            rows.append(("2026-07-28", "legacy", "990001A.FP", "板块A", f"{i:06d}.SZ", 10.0 + i, 1.0, 5.0, "fupanhui"))
        rows.append(("2026-07-28", "legacy", "990001A.FP", "板块A", "999999.SZ", None, None, 0.0, "fupanhui"))
        con.executemany(
            f"insert into {TABLE}(trade_date, sector_universe_snapshot_id, sector_ts_code, sector_name, "
            "stock_ts_code, price, pct_chg, amount, source) values (?,?,?,?,?,?,?,?,?)",
            rows,
        )
        # 制造空闲块: 写一批再删掉, 压缩才有东西可回收
        con.execute("create table scratch as select range as i, repeat('x', 2000) as pad from range(20000)")
        con.execute("drop table scratch")
        assert maintenance.has_quote_check(con) is False
        return maintenance.db_shape(con)
    finally:
        con.close()


def test_dry_run_report_counts_shell_rows_and_check_state(tmp_path):
    target = tmp_path / "prod.duckdb"
    _legacy_shaped_db(target)
    report = maintenance.dry_run_report(target)
    assert report["shell"]["rows_total"] == 181
    assert report["shell"]["rows_shell"] == 150
    assert report["shell"]["rows_keep"] == 31
    assert report["shell"]["has_quote_check"] is False
    assert report["shell"]["shell_by_source"] == [
        {"source": "<NULL>", "rows": 150, "first": "2026-07-21", "last": "2026-07-23"}
    ]
    assert report["file"]["bytes"] > 0 and report["shape"]["tables"] >= 40


def test_rebuild_with_quote_check_is_exact_and_idempotent(tmp_path):
    target = tmp_path / "prod.duckdb"
    _legacy_shaped_db(target)
    con = duckdb.connect(str(target))
    try:
        first = maintenance.rebuild_with_quote_check(con)
        assert first["rebuilt"] is True
        assert first["before"]["rows_shell"] == 150 and first["after"]["rows_total"] == 31
        assert maintenance.has_quote_check(con) is True
        # 索引与视图按正典名重建
        idx = {r[0] for r in con.execute(f"select index_name from duckdb_indexes() where table_name='{TABLE}'").fetchall()}
        assert idx == {"idx_fact_sector_stock_gen_date", "idx_fact_sector_stock_gen_sector", "idx_fact_sector_stock_gen_stock"}
        assert con.execute("select count(*) from fact_sector_stock_daily where trade_date='2026-07-28'").fetchone() == (31,)
        # 停牌形态 (只有 amount=0) 保留
        assert con.execute(f"select amount from {TABLE} where stock_ts_code='999999.SZ'").fetchone() == (0.0,)
        # 装上 CHECK 后空壳再也写不进来
        with pytest.raises(duckdb.ConstraintException):
            con.execute(
                f"insert into {TABLE}(trade_date, sector_universe_snapshot_id, sector_ts_code, stock_ts_code) "
                "values ('2026-07-29', 'legacy', '990001A.FP', '000001.SZ')"
            )
        second = maintenance.rebuild_with_quote_check(con)
        assert second["rebuilt"] is False
    finally:
        con.close()


def test_rebuild_refuses_when_table_has_undeclared_columns(tmp_path):
    target = tmp_path / "prod.duckdb"
    _legacy_shaped_db(target)
    con = duckdb.connect(str(target))
    try:
        con.execute(f"alter table {TABLE} add column mystery_col text")
        with pytest.raises(RuntimeError, match="未声明的列"):
            maintenance.rebuild_with_quote_check(con)
        # 事务没开始就拒绝了: 数据原样
        assert con.execute(f"select count(*) from {TABLE}").fetchone() == (181,)
    finally:
        con.close()


def test_staged_maintenance_purges_compacts_and_swaps(tmp_path):
    target = tmp_path / "prod.duckdb"
    shape_before = _legacy_shaped_db(target)

    result = maintenance.run_maintenance_staged(target)

    assert result["swapped"] is True and result["reason"] == "ok", result
    names = [s["name"] for s in result["steps"]]
    assert names == ["rebuild_with_quote_check", "compact"]
    assert result["steps"][0]["before"]["rows_shell"] == 150
    # 小库上 DuckDB 关闭时会截掉尾部空闲块, 「空闲块变少」只在生产级文件上可观测;
    # 这里只验压缩产物不比源大, 正确性由下面的形状对账保证。
    assert result["steps"][1]["bytes_after"] <= result["steps"][1]["bytes_before"]
    assert result["file_after"]["bytes"] > 0
    # 中间产物全部清理
    assert not _db.staging_path(target).exists()
    assert not target.with_name(target.name + maintenance.COMPACT_SUFFIX).exists()
    assert not _db.wal_path(target).exists()

    con = duckdb.connect(str(target), read_only=True)
    try:
        shape_after = maintenance.db_shape(con)
        # 只有目标表行数变了 (150 空壳没了), 收据表 +1, 其余一行不差
        expected = dict(shape_before["rows"])
        expected[TABLE] = 31
        expected["ops_sync_run"] = shape_before["rows"]["ops_sync_run"] + 1
        assert shape_after["rows"] == expected
        assert shape_after["indexes"] == shape_before["indexes"]
        assert shape_after["views"] == shape_before["views"]
        assert shape_after["constraints"] == shape_before["constraints"] + 1  # 多了 CHECK
        assert maintenance.has_quote_check(con) is True
        # 视图在压缩后的新文件里仍可查
        assert con.execute("select count(*) from fact_sector_stock_daily").fetchone() == (31,)
        kind, plan, steps = con.execute(
            "select kind, plan, steps_summary from ops_sync_run where run_id = ?", [result["run_id"]]
        ).fetchone()
        assert (kind, plan) == ("maintenance", "staging-swap")
        assert '"rows_shell_removed": 150' in steps and '"name": "compact"' in steps
    finally:
        con.close()


def test_staged_maintenance_is_a_noop_swap_on_a_clean_db(tmp_path):
    target = tmp_path / "prod.duckdb"
    _legacy_shaped_db(target)
    assert maintenance.run_maintenance_staged(target)["swapped"] is True
    again = maintenance.run_maintenance_staged(target)
    assert again["swapped"] is True
    assert again["steps"][0]["rebuilt"] is False


def test_staged_maintenance_refuses_when_third_party_modified_target(tmp_path, monkeypatch):
    target = tmp_path / "prod.duckdb"
    _legacy_shaped_db(target)
    real_compact = maintenance.compact_database

    def compact_then_third_party_writes(source, dest):
        out = real_compact(source, dest)
        third = duckdb.connect(str(target))
        try:
            third.execute("insert into config_watchlist values ('000001.SZ', '平安银行', 'g', 'r', now())")
        finally:
            third.close()
        return out

    monkeypatch.setattr(maintenance, "compact_database", compact_then_third_party_writes)
    result = maintenance.run_maintenance_staged(target)
    assert result["swapped"] is False
    assert "第三方写者守卫" in result["reason"]
    con = duckdb.connect(str(target), read_only=True)
    try:
        # 生产库仍是旧形态 (空壳还在、无 CHECK), 第三方那一行也在
        assert con.execute(f"select count(*) from {TABLE}").fetchone() == (181,)
        assert maintenance.has_quote_check(con) is False
        assert con.execute("select count(*) from config_watchlist").fetchone() == (1,)
    finally:
        con.close()
