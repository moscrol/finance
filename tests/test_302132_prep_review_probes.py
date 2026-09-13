"""Review probes for the existing feature empty-result contract (memory only).

These tests characterize current behavior; they are NOT the future scoped API's
acceptance tests. In particular, the first behavior must change for an explicitly
approved insufficient-history target slice, not for unscoped daily runs.
"""
from datetime import date

import duckdb
import pytest

from scripts.compute_features import compute_features


def test_current_empty_technical_result_preserves_existing_target_row():
    with duckdb.connect(":memory:") as con:
        con.execute("CREATE TABLE fact_market_daily (trade_date DATE)")
        con.execute("INSERT INTO fact_market_daily VALUES (DATE '2026-06-15')")
        con.execute("CREATE TABLE fact_stock_daily (trade_date DATE, stock_ts_code TEXT, "
                    "stock_name TEXT, close DOUBLE)")
        con.execute("INSERT INTO fact_stock_daily VALUES "
                    "(DATE '2026-06-15', '302132.SZ', '中航成飞', 61.35)")
        con.execute("CREATE TABLE feature_stock_technical_daily (trade_date DATE, stock_ts_code TEXT, "
                    "stock_name TEXT, close DOUBLE, ma26 DOUBLE, std26 DOUBLE, up_value DOUBLE, "
                    "deviation_pct DOUBLE, calculated_at TIMESTAMP)")
        con.execute("INSERT INTO feature_stock_technical_daily VALUES "
                    "(DATE '2026-06-15','302132.SZ','中航成飞',61.35,99,1,100,-38.65,TIMESTAMP '2026-06-15')")
        before = con.execute("SELECT * FROM feature_stock_technical_daily").fetchall()
        with pytest.raises(RuntimeError, match="staging 结果为空"):
            compute_features("2026-06-15", selected=("technical",), con=con)
        assert con.execute("SELECT * FROM feature_stock_technical_daily").fetchall() == before
        assert con.execute("SELECT count(*) FROM _stage_feature_stock_technical_daily").fetchone() == (0,)


def test_current_nonempty_daily_recompute_deletes_insufficient_target_when_other_stock_is_valid():
    with duckdb.connect(":memory:") as con:
        con.execute("CREATE TABLE fact_market_daily (trade_date DATE)")
        con.execute("INSERT INTO fact_market_daily VALUES (DATE '2026-06-15')")
        con.execute("CREATE TABLE fact_stock_daily (trade_date DATE, stock_ts_code TEXT, "
                    "stock_name TEXT, close DOUBLE)")
        con.execute("INSERT INTO fact_stock_daily VALUES "
                    "(DATE '2026-06-15', '302132.SZ', '中航成飞', 61.35)")
        con.execute("INSERT INTO fact_stock_daily SELECT d::DATE, 'OTHER', 'other', 10 "
                    "FROM generate_series(DATE '2026-05-21', DATE '2026-06-15', INTERVAL 1 DAY) t(d)")
        con.execute("CREATE TABLE feature_stock_technical_daily (trade_date DATE, stock_ts_code TEXT, "
                    "stock_name TEXT, close DOUBLE, ma26 DOUBLE, std26 DOUBLE, up_value DOUBLE, "
                    "deviation_pct DOUBLE, calculated_at TIMESTAMP)")
        con.execute("INSERT INTO feature_stock_technical_daily VALUES "
                    "(DATE '2026-06-15','302132.SZ','中航成飞',61.35,99,1,100,-38.65,TIMESTAMP '2026-06-15')")
        compute_features("2026-06-15", selected=("technical",), con=con)
        assert con.execute("SELECT trade_date, stock_ts_code FROM feature_stock_technical_daily").fetchall() == [
            (date(2026, 6, 15), "OTHER")]
