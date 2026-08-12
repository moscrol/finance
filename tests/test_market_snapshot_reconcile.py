from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import duckdb

from intelligence.services.market_snapshot_contract import validate_market_snapshot_root
from intelligence.services.market_snapshot_reconcile import (
    reconcile_snapshot_with_market_db,
)
from scripts.check_market_snapshot_contract import run_check
from tests.test_market_snapshot_contract import write_snapshot


def write_market_db(path: Path, *dates: str) -> None:
    con = duckdb.connect(str(path))
    try:
        con.execute("CREATE TABLE fact_market_daily (trade_date DATE)")
        for value in dates:
            con.execute(
                "INSERT INTO fact_market_daily VALUES (?::DATE)", [value]
            )
    finally:
        con.close()


class MarketSnapshotReconcileTest(unittest.TestCase):
    """快照 served_trade_date 必须等于 DuckDB max(trade_date)。

    对应 2026-08-12 事故：快照 08-12、DuckDB 08-11，差一天导致每条结构化
    查询被判 stale、证据整批作废。原格式门禁对此完全静默。
    """

    def _snapshot_result(self, tmp: Path, date: str = "2026-06-11") -> dict:
        root = tmp / "snapshot"
        root.mkdir()
        write_snapshot(root, date)
        return validate_market_snapshot_root(root, date)

    def test_equal_dates_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            snapshot = self._snapshot_result(base)
            db = base / "market.duckdb"
            write_market_db(db, "2026-06-10", "2026-06-11")

            result = reconcile_snapshot_with_market_db(snapshot, db)

            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["snapshot_served_trade_date"], "2026-06-11")
            self.assertEqual(result["duckdb_max_trade_date"], "2026-06-11")
            self.assertEqual(result["errors"], [])

    def test_snapshot_ahead_of_duckdb_fails(self):
        """事故原形状：快照超前一天 → 必须 FAIL 且指明方向。"""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            snapshot = self._snapshot_result(base, "2026-08-12")
            db = base / "market.duckdb"
            write_market_db(db, "2026-08-11")

            result = reconcile_snapshot_with_market_db(snapshot, db)

            self.assertEqual(result["status"], "FAIL")
            joined = " ".join(result["errors"])
            self.assertIn("2026-08-12", joined)
            self.assertIn("2026-08-11", joined)
            self.assertIn("超前", joined)

    def test_snapshot_behind_duckdb_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            snapshot = self._snapshot_result(base, "2026-08-11")
            db = base / "market.duckdb"
            write_market_db(db, "2026-08-11", "2026-08-12")

            result = reconcile_snapshot_with_market_db(snapshot, db)

            self.assertEqual(result["status"], "FAIL")
            self.assertIn("落后", " ".join(result["errors"]))

    def test_missing_db_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            snapshot = self._snapshot_result(base)

            result = reconcile_snapshot_with_market_db(
                snapshot, base / "absent.duckdb"
            )

            self.assertEqual(result["status"], "FAIL")
            self.assertIn("DuckDB 不存在", " ".join(result["errors"]))

    def test_missing_table_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            snapshot = self._snapshot_result(base)
            db = base / "market.duckdb"
            duckdb.connect(str(db)).close()

            result = reconcile_snapshot_with_market_db(snapshot, db)

            self.assertEqual(result["status"], "FAIL")
            self.assertIn("fact_market_daily", " ".join(result["errors"]))

    def test_empty_table_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            snapshot = self._snapshot_result(base)
            db = base / "market.duckdb"
            write_market_db(db)

            result = reconcile_snapshot_with_market_db(snapshot, db)

            self.assertEqual(result["status"], "FAIL")
            self.assertIn("无任何 trade_date", " ".join(result["errors"]))

    def test_missing_served_date_fails_closed(self):
        result = reconcile_snapshot_with_market_db(
            {"summary": {}, "date": ""}, Path("/nonexistent.duckdb")
        )

        self.assertEqual(result["status"], "FAIL")
        self.assertIn("served_trade_date", " ".join(result["errors"]))


class RunCheckGateTest(unittest.TestCase):
    """脚本级组合：格式 PASS 但对账不等 → 整体 FAIL、ready=False、exit 非零。"""

    def test_format_pass_but_mismatch_fails_overall(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "snapshot"
            root.mkdir()
            write_snapshot(root, "2026-08-12")
            db = base / "market.duckdb"
            write_market_db(db, "2026-08-11")

            result = run_check(root, "2026-08-12", db_path=db)

            self.assertEqual(result["status"], "FAIL")
            self.assertFalse(result["ready"])
            self.assertEqual(result["reconciliation"]["status"], "FAIL")
            self.assertIn("超前", " ".join(result["errors"]))

    def test_equal_dates_pass_overall(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "snapshot"
            root.mkdir()
            write_snapshot(root, "2026-08-11")
            db = base / "market.duckdb"
            write_market_db(db, "2026-08-11")

            result = run_check(root, "2026-08-11", db_path=db)

            self.assertEqual(result["status"], "PASS")
            self.assertTrue(result["ready"])
            self.assertEqual(result["reconciliation"]["status"], "PASS")

    def test_skip_db_preserves_format_only_behavior(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "snapshot"
            root.mkdir()
            write_snapshot(root, "2026-08-12")

            result = run_check(root, "2026-08-12", skip_db=True)

            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["reconciliation"]["status"], "SKIPPED")


if __name__ == "__main__":
    unittest.main()
