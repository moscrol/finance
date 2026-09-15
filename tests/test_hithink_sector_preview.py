"""换池只读验算：不需要任何复盘会板块/成员表，复用同一公式与双红阈值。"""
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import duckdb
import pytest

from market_feature_store.hithink_sector_preview import preview_sector_calculation

DAY = date(2026, 9, 2)
PREV = date(2026, 9, 1)


@pytest.fixture
def con():
    c = duckdb.connect(":memory:")
    c.execute("""
        CREATE TABLE dim_sector_hithink (
            sector_ts_code TEXT, sector_name TEXT, category TEXT, updated_at TIMESTAMP,
            constituent_count INTEGER, constituents_captured_at TIMESTAMP, source TEXT);
        CREATE TABLE fact_sector_constituent_hithink (
            captured_at DATE, sector_ts_code TEXT, stock_ts_code TEXT,
            in_index INTEGER, source TEXT, updated_at TIMESTAMP);
        CREATE TABLE fact_stock_daily (
            trade_date DATE, stock_ts_code TEXT, close DOUBLE, pct_chg DOUBLE,
            amount DOUBLE, source TEXT);
        CREATE TABLE fact_sector_kline_daily (
            trade_date DATE, sector_ts_code TEXT, close DOUBLE, source TEXT);
        INSERT INTO dim_sector_hithink VALUES
            ('885001.TI', '新池', 'cn_concept', '2026-09-02', 2, '2026-09-02', 'hithink:ths-index-list');
        INSERT INTO fact_sector_kline_daily VALUES
            ('2026-09-01', '885001.TI', 100, 'hithink:index-historical'),
            ('2026-09-02', '885001.TI', 99, 'hithink:index-historical');
        INSERT INTO fact_sector_constituent_hithink VALUES
            ('2026-09-02', '885001.TI', '600001.SH', 1, 'hithink:ths-stock-list', '2026-09-02'),
            ('2026-09-02', '885001.TI', '600002.SH', 1, 'hithink:ths-stock-list', '2026-09-02');
        INSERT INTO fact_stock_daily VALUES
            ('2026-09-01', '600001.SH', 10, 0, 300, 'hithink:daily-k-10d'),
            ('2026-09-01', '600002.SH', 10, 0, 200, 'hithink:daily-k-10d'),
            ('2026-09-02', '600001.SH', 11, 10, 400, 'hithink:daily-k-10d'),
            ('2026-09-02', '600002.SH', 9.5, -5, 200, 'hithink:daily-k-10d');
    """)
    yield c
    c.close()


def preview(con, **kwargs):
    kwargs.setdefault("pct_basis", "member_equal_weight")
    return preview_sector_calculation(con, DAY, member_date=DAY, category="cn_concept", **kwargs)


def test_new_pool_uses_same_amount_diff_and_double_red_without_old_universe(con):
    result = preview(con)
    assert result["calculation_ready"] is True
    assert result["production_ready"] is False
    assert result["previous_trade_date"] == str(PREV)
    assert result["double_red_codes"] == ["885001.TI"]
    row = result["rows"][0]
    assert row["amount"] == 600.0
    assert row["previous_amount"] == 500.0
    assert row["diff_ratio"] == 20.0
    assert row["pct_chg"] == 2.5
    assert row["member_count"] == 2
    assert result["basis"]["pct_chg"] == "member_equal_weight"
    assert result["basis"]["previous_amount"] == "same_selected_members"
    assert "hithink:daily-k-10d" in result["value_sources"]
    json.dumps(result, allow_nan=False)


def test_changed_pool_changes_values_but_not_formula_and_fingerprint(con):
    before = preview(con)
    con.execute("DELETE FROM fact_sector_constituent_hithink WHERE stock_ts_code='600002.SH'")
    con.execute("UPDATE dim_sector_hithink SET constituent_count=1")
    after = preview(con)
    assert after["calculation_ready"] is True
    assert after["rows"][0]["amount"] == 400
    assert after["rows"][0]["diff_ratio"] == pytest.approx(33.3333)
    assert after["double_red_codes"] == []  # 未过成交额阈值，不要求复刻旧集合
    assert before["member_fingerprint"] != after["member_fingerprint"]


@pytest.mark.parametrize("amount, expected", [(550.0, False), (550.001, True), (500.0, False)])
def test_strict_boundary_shared_with_signals(con, amount, expected):
    con.execute("UPDATE fact_stock_daily SET amount=? WHERE trade_date=? AND stock_ts_code='600001.SH'", [amount - 200, DAY])
    assert bool(preview(con)["double_red_codes"]) is expected


@pytest.mark.parametrize("column,value", [("amount", None), ("pct_chg", None), ("close", 0), ("amount", float("nan")), ("pct_chg", float("inf")), ("amount", -1)])
def test_missing_invalid_values_block_instead_of_shrinking_pool(con, column, value):
    con.execute(f"UPDATE fact_stock_daily SET {column}=? WHERE trade_date=? AND stock_ts_code='600002.SH'", [value, DAY])
    result = preview(con)
    assert result["calculation_ready"] is False
    assert result["rows"] == [] and result["double_red_codes"] == []
    assert result["gaps"]
    json.dumps(result, allow_nan=False)


def test_no_previous_bar_and_no_previous_turnover_block(con):
    con.execute("DELETE FROM fact_stock_daily WHERE trade_date=? AND stock_ts_code='600002.SH'", [PREV])
    assert preview(con)["calculation_ready"] is False


def test_zero_previous_denominator_blocks(con):
    con.execute("UPDATE fact_stock_daily SET amount=0 WHERE trade_date=?", [PREV])
    assert preview(con)["calculation_ready"] is False


def test_wrong_value_source_is_not_a_valid_fallback(con):
    con.execute("UPDATE fact_stock_daily SET source='fupanhui:sector_stock_daily:fallback'")
    assert preview(con)["calculation_ready"] is False


def test_all_catalog_members_required_not_only_successful_sectors(con):
    con.execute("INSERT INTO dim_sector_hithink VALUES ('885002.TI', '缺名单', 'cn_concept', '2026-09-02', 1, '2026-09-02', 'hithink:ths-index-list')")
    result = preview(con)
    assert result["calculation_ready"] is False
    assert any(gap["sector_ts_code"] == "885002.TI" for gap in result["gaps"])


def test_misdated_current_members_are_rejected(con):
    con.execute("UPDATE fact_sector_constituent_hithink SET updated_at='2026-09-03'")
    assert preview(con)["calculation_ready"] is False


def test_future_catalog_is_rejected(con):
    con.execute("UPDATE dim_sector_hithink SET updated_at='2026-09-03'")
    assert preview(con)["calculation_ready"] is False


def test_future_member_date_and_closed_day_rejected(con):
    with pytest.raises(ValueError, match="member_date"):
        preview_sector_calculation(con, DAY, member_date=date(2026, 9, 3), category="cn_concept", pct_basis="member_equal_weight")
    with pytest.raises(ValueError, match="交易日"):
        preview_sector_calculation(con, date(2026, 9, 5), member_date=date(2026, 9, 5), category="cn_concept", pct_basis="member_equal_weight")


def test_explicit_carried_members_are_visible_and_age_bounded(con):
    con.execute("UPDATE fact_sector_constituent_hithink SET captured_at='2026-09-01', updated_at='2026-09-01'")
    con.execute("UPDATE dim_sector_hithink SET constituents_captured_at='2026-09-01'")
    result = preview_sector_calculation(con, DAY, member_date=PREV, category="cn_concept", pct_basis="member_equal_weight", max_member_age_days=1)
    assert result["calculation_ready"] is True and result["member_age_days"] == 1
    with pytest.raises(ValueError, match="member_date"):
        preview_sector_calculation(con, DAY, member_date=PREV, category="cn_concept", pct_basis="member_equal_weight")


def test_basis_is_required_and_never_silently_falls_back(con):
    with pytest.raises(TypeError, match="pct_basis"):
        preview_sector_calculation(con, DAY, member_date=DAY, category="cn_concept")
    with pytest.raises(ValueError, match="pct_basis"):
        preview(con, pct_basis="automatic")
    eqw = preview(con)
    index = preview(con, pct_basis="index_close_return")
    assert eqw["rows"][0]["pct_chg"] == 2.5
    assert index["rows"][0]["pct_chg"] == -1.0
    assert index["calculation_ready"] is True
    assert index["double_red_codes"] == []
    assert index["basis"]["pct_chg"] == "index_close_return"
    assert eqw["member_fingerprint"] == index["member_fingerprint"]
    assert index["rows"][0]["amount"] == eqw["rows"][0]["amount"]


@pytest.mark.parametrize("sql", [
    "DELETE FROM fact_sector_kline_daily WHERE trade_date='2026-09-01'",
    "UPDATE fact_sector_kline_daily SET close=NULL",
    "UPDATE fact_sector_kline_daily SET close=0",
    "UPDATE fact_sector_kline_daily SET close='NaN'::DOUBLE",
    "UPDATE fact_sector_kline_daily SET source='other'",
    "INSERT INTO fact_sector_kline_daily SELECT * FROM fact_sector_kline_daily",
])
def test_index_basis_needs_exact_valid_calendar_bars_not_eqw_fallback(con, sql):
    con.execute(sql)
    result = preview(con, pct_basis="index_close_return")
    assert not result["calculation_ready"]
    assert result["rows"] == []
    assert preview(con)["calculation_ready"]  # 等权可算，但指数缺口不能用它洗绿


@pytest.mark.parametrize("sql", [
    "DELETE FROM fact_sector_constituent_hithink WHERE stock_ts_code='600002.SH'",
    "UPDATE dim_sector_hithink SET constituent_count=NULL",
    "UPDATE dim_sector_hithink SET constituents_captured_at='2026-09-01'",
    "UPDATE dim_sector_hithink SET source='other'",
    "UPDATE dim_sector_hithink SET updated_at='2026-08-20'",
    "INSERT INTO dim_sector_hithink SELECT * FROM dim_sector_hithink",
    "UPDATE fact_sector_constituent_hithink SET stock_ts_code=''",
    "INSERT INTO fact_stock_daily SELECT * FROM fact_stock_daily",
])
def test_snapshot_denominator_and_identity_cannot_be_silently_shrunk(con, sql):
    con.execute(sql)
    assert not preview(con)["calculation_ready"]


def test_partial_preview_keeps_diagnostics_but_not_ready_signal_codes(con):
    con.execute("INSERT INTO dim_sector_hithink VALUES ('885002.TI', '缺名单', 'cn_concept', '2026-09-02', 1, '2026-09-02', 'hithink:ths-index-list')")
    result = preview(con)
    assert not result["calculation_ready"] and len(result["rows"]) == 1
    assert result["double_red_codes"] == []


def test_index_basis_does_not_require_unused_member_pct(con):
    con.execute("UPDATE fact_stock_daily SET pct_chg=NULL")
    assert preview(con, pct_basis="index_close_return")["calculation_ready"]
    assert not preview(con)["calculation_ready"]


def _persist_fixture(con, tmp_path):
    folder = tmp_path / "fixture"
    con.execute(f"EXPORT DATABASE '{folder}'")
    path = tmp_path / "fixture.duckdb"
    with duckdb.connect(str(path)) as writable:
        writable.execute(f"IMPORT DATABASE '{folder}'")
    return path


def test_preview_runs_on_read_only_connection_and_is_deterministic(con, tmp_path):
    # EXPORT/IMPORT 只用于夹具。被测函数用真正只读连接，任何隐藏写入都会失败。
    path = _persist_fixture(con, tmp_path)
    with duckdb.connect(str(path), read_only=True) as readonly:
        assert preview(readonly) == preview(readonly)


def _cli_args():
    return ["hithink-sector-preview", "--trade-date", str(DAY), "--member-date", str(DAY),
            "--category", "cn_concept", "--pct-basis", "member_equal_weight"]


def _run_cli(path, args):
    return subprocess.run(
        [sys.executable, "-m", "market_feature_store.cli", *args],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "MARKET_FEATURE_STORE_DB": str(path)},
        capture_output=True, text=True, timeout=20,
    )


@pytest.mark.parametrize("complete", [True, False])
def test_real_cli_is_read_only_and_returns_nonzero_for_incomplete(con, tmp_path, complete):
    if not complete:
        con.execute("UPDATE fact_stock_daily SET amount=NULL WHERE trade_date=?", [DAY])
    path = _persist_fixture(con, tmp_path)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    result = _run_cli(path, _cli_args())
    assert result.returncode == (0 if complete else 2), result.stderr
    report = json.loads(result.stdout)
    assert report["calculation_ready"] is complete
    assert report["production_ready"] is False
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_cli_requires_explicit_basis_before_opening_db(tmp_path):
    path = tmp_path / "missing" / "never-created.duckdb"
    result = _run_cli(path, _cli_args()[:-2])
    assert result.returncode == 2
    assert "--pct-basis" in result.stderr
    assert not path.parent.exists()


def test_cli_missing_db_fails_structurally_without_creating_it(tmp_path):
    path = tmp_path / "missing" / "never-created.duckdb"
    result = _run_cli(path, _cli_args())
    assert result.returncode == 2
    report = json.loads(result.stdout)
    assert not report["calculation_ready"] and not report["production_ready"]
    assert report["gaps"][0]["reason"] == "database-unavailable-or-schema-mismatch"
    assert not path.parent.exists()


def test_cli_never_loads_key_initializes_or_calls_provider(con, tmp_path, monkeypatch, capsys):
    from market_feature_store import cli, db, hithink_client
    from market_feature_store.sources import fupanhui_source

    path = _persist_fixture(con, tmp_path)

    def forbidden(*a, **k):
        pytest.fail("只读预览不能建库/取 key/请求供应商")

    monkeypatch.setattr(db, "DB_PATH", path)
    monkeypatch.setattr(cli, "init_db", forbidden)
    monkeypatch.setattr(db, "init_db", forbidden)
    monkeypatch.setattr(hithink_client, "load_api_key", forbidden)
    monkeypatch.setattr(hithink_client, "get_json", forbidden)
    monkeypatch.setattr(fupanhui_source, "get_sector_klines_batch", forbidden)
    assert cli.main(_cli_args()) == 0
    assert json.loads(capsys.readouterr().out)["calculation_ready"]


def test_same_inputs_match_existing_generation_based_local_calculation(con):
    """用真 schema 和现有发布/成员/计算接口对账；不是生产切源器。"""
    from market_feature_store.db import init_db
    from market_feature_store.sector_universe import MemberResult, SectorDescriptor, SectorUniverseStore
    from market_feature_store.signals import is_double_red
    from market_feature_store.sync.sync_local_sector_daily import sync_sector_daily_local

    expected = preview(con)["rows"][0]
    with duckdb.connect(":memory:") as canonical:
        init_db(canonical)
        store = SectorUniverseStore(canonical)
        for day in (PREV, DAY):
            canonical.execute("INSERT INTO fact_market_daily (trade_date) VALUES (?)", [day])
            snapshot = store.publish_snapshot(
                trade_date=day, provider_source="hithink",
                sectors=[SectorDescriptor("885001.TI", "新池", 2)],
                captured_at=f"{day}T18:00:00+08:00",
            )
            stocks = con.execute(
                "SELECT stock_ts_code, close, pct_chg, amount, source "
                "FROM fact_stock_daily WHERE trade_date=? ORDER BY stock_ts_code", [day],
            ).fetchall()
            receipt = store.record_member_result(
                snapshot.snapshot_id, "885001.TI",
                MemberResult.success(served_date=str(day), stocks=[
                    {"ts_code": code, "price": close, "pct_chg": pct, "amount": amount, "source": source}
                    for code, close, pct, amount, source in stocks
                ]),
            )
            assert receipt.status == "success"
            if day == PREV:
                # 已知前日额夹具不是重建历史名单：本测试只对账相同输入的计算。
                store.replace_sector_daily(snapshot.snapshot_id, [{
                    "sector_ts_code": "885001.TI", "amount": 500, "pct_chg": 0, "diff_ratio": 0,
                }])
        result = sync_sector_daily_local(DAY, con=canonical, prefer_payload=False)
        assert result["rows_written"] == 1
        pct, amount, dr = canonical.execute(
            "SELECT pct_chg, amount, diff_ratio FROM fact_sector_daily WHERE trade_date=?", [DAY],
        ).fetchone()
        assert (pct, amount, dr) == (expected["pct_chg"], expected["amount"], expected["diff_ratio"])
        assert is_double_red(pct, dr, amount) is expected["double_red"]


def test_shared_previous_trading_day_has_one_implementation():
    from intelligence.services import trading_calendar
    from market_feature_store import trading_days

    assert trading_calendar.previous_scheduled_trading_day is trading_days.previous_scheduled_trading_day
    assert trading_days.previous_scheduled_trading_day(date(2026, 2, 24)) == date(2026, 2, 13)
    assert trading_days.previous_scheduled_trading_day(date(2026, 9, 7)) == date(2026, 9, 4)
    assert trading_days.previous_scheduled_trading_day(date(2025, 9, 2)) is None
