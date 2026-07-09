from __future__ import annotations

import unittest

import duckdb

from market_feature_store.quality import (
    calendar_gaps,
    check_daily,
    latest_trade_date,
    row_count_anomalies,
    value_range_violations,
)

TABLES = ["fact_sector_daily", "fact_stock_daily"]


def _mini_db() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:")
    con.execute(
        """
        CREATE TABLE fact_market_daily (
            trade_date DATE PRIMARY KEY, total_amount DOUBLE, advancers INTEGER,
            limit_up INTEGER, limit_down INTEGER, volume_ratio DOUBLE,
            sh_index_close DOUBLE, sh_index_pct_chg DOUBLE
        )
        """
    )
    con.execute("CREATE TABLE fact_sector_daily (trade_date DATE, sector_ts_code VARCHAR)")
    con.execute("CREATE TABLE fact_stock_daily (trade_date DATE, stock_ts_code VARCHAR)")
    return con


def _seed(con, dates: list[str], sector_rows: int = 10, stock_rows: int = 10) -> None:
    for d in dates:
        con.execute(
            "INSERT INTO fact_market_daily VALUES (?, 12000, 3000, 60, 10, 1.0, 3500, 0.5)", [d]
        )
        for i in range(sector_rows):
            con.execute("INSERT INTO fact_sector_daily VALUES (?, ?)", [d, f"S{i}"])
        for i in range(stock_rows):
            con.execute("INSERT INTO fact_stock_daily VALUES (?, ?)", [d, f"C{i}"])


DATES = [f"2026-07-0{i}" for i in range(1, 9)]


class CalendarGapsTest(unittest.TestCase):
    def test_no_gaps_when_all_tables_aligned(self):
        con = _mini_db()
        _seed(con, DATES)
        self.assertEqual(calendar_gaps(con, window=5, tables=TABLES), [])

    def test_detects_missing_dates_within_coverage(self):
        con = _mini_db()
        _seed(con, DATES)
        con.execute("DELETE FROM fact_sector_daily WHERE trade_date = '2026-07-06'")
        gaps = calendar_gaps(con, window=5, tables=TABLES)
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0]["table"], "fact_sector_daily")
        self.assertEqual(gaps[0]["missing_dates"], ["2026-07-06"])

    def test_short_table_not_flagged_before_its_first_date(self):
        con = _mini_db()
        _seed(con, DATES)
        con.execute("DELETE FROM fact_sector_daily WHERE trade_date < '2026-07-07'")
        self.assertEqual(calendar_gaps(con, window=5, tables=TABLES), [])

    def test_empty_table_reported(self):
        con = _mini_db()
        _seed(con, DATES)
        con.execute("DELETE FROM fact_sector_daily")
        gaps = calendar_gaps(con, window=3, tables=TABLES)
        self.assertEqual(gaps[0]["note"], "空表")
        self.assertEqual(len(gaps[0]["missing_dates"]), 3)


class RowCountAnomalyTest(unittest.TestCase):
    def test_normal_rows_not_flagged(self):
        con = _mini_db()
        _seed(con, DATES)
        self.assertEqual(row_count_anomalies("2026-07-08", con, tables=TABLES), [])

    def test_shrunk_rows_flagged(self):
        con = _mini_db()
        _seed(con, DATES[:-1])
        _seed(con, [DATES[-1]], sector_rows=2, stock_rows=10)
        anomalies = row_count_anomalies("2026-07-08", con, tables=TABLES)
        self.assertEqual([a["table"] for a in anomalies], ["fact_sector_daily"])
        self.assertEqual(anomalies[0]["rows"], 2)
        self.assertEqual(anomalies[0]["median"], 10)

    def test_no_history_no_flag(self):
        con = _mini_db()
        _seed(con, [DATES[0]], sector_rows=1)
        self.assertEqual(row_count_anomalies(DATES[0], con, tables=TABLES), [])


class ValueRangeTest(unittest.TestCase):
    def test_in_range_passes(self):
        con = _mini_db()
        _seed(con, DATES)
        self.assertEqual(value_range_violations("2026-07-08", con), [])

    def test_out_of_range_flagged(self):
        con = _mini_db()
        _seed(con, DATES[:-1])
        con.execute(
            "INSERT INTO fact_market_daily VALUES ('2026-07-08', 0, 9999, 60, 10, 1.0, 3500, 0.5)"
        )
        fields = {v["field"] for v in value_range_violations("2026-07-08", con)}
        self.assertEqual(fields, {"total_amount", "advancers"})

    def test_null_values_skipped(self):
        con = _mini_db()
        con.execute(
            "INSERT INTO fact_market_daily VALUES ('2026-07-08', NULL, NULL, NULL, NULL, NULL, NULL, NULL)"
        )
        self.assertEqual(value_range_violations("2026-07-08", con), [])

    def test_missing_row_reported(self):
        con = _mini_db()
        vio = value_range_violations("2026-07-08", con)
        self.assertIn("缺整行", vio[0]["note"])


class CheckDailyTest(unittest.TestCase):
    def test_pass_end_to_end(self):
        con = _mini_db()
        _seed(con, DATES)
        res = check_daily(con=con, window=5, tables=TABLES)
        self.assertTrue(res["ok"])
        self.assertEqual(res["trade_date"], "2026-07-08")
        self.assertEqual(res["brief"], "通过")

    def test_defaults_to_latest_trade_date(self):
        con = _mini_db()
        _seed(con, DATES)
        self.assertEqual(latest_trade_date(con), "2026-07-08")

    def test_fail_collects_problems_into_brief(self):
        con = _mini_db()
        _seed(con, DATES)
        con.execute("UPDATE fact_market_daily SET total_amount = 0 WHERE trade_date = '2026-07-08'")
        res = check_daily(con=con, window=5, tables=TABLES)
        self.assertFalse(res["ok"])
        self.assertIn("total_amount", res["brief"])

    def test_empty_db_reports_uninitialized(self):
        con = _mini_db()
        res = check_daily(con=con)
        self.assertFalse(res["ok"])
        self.assertIn("从未同步", res["brief"])


if __name__ == "__main__":
    unittest.main()
