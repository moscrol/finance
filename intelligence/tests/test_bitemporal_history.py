from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from intelligence.eval.bitemporal_history import (
    build_as_known_at,
    build_final_history,
    compare_snapshots,
    cutoff_for_date,
    feature_contract_check,
)
from scripts.bitemporal_history_eval import main


class BitemporalHistoryTests(unittest.TestCase):
    def setUp(self) -> None:
        try:
            import duckdb
        except Exception:
            self.skipTest("duckdb is not installed")
        self.duckdb = duckdb

    def _db(self, root: Path) -> Path:
        path = root / "market.duckdb"
        con = self.duckdb.connect(str(path))
        try:
            con.execute(
                """
                CREATE TABLE fact_market_daily (
                    trade_date DATE,
                    total_amount DOUBLE,
                    updated_at TIMESTAMP
                )
                """
            )
            con.execute(
                """
                CREATE TABLE fact_sector_daily (
                    trade_date DATE,
                    sector_name VARCHAR,
                    amount DOUBLE,
                    updated_at TIMESTAMP
                )
                """
            )
            con.execute(
                """
                CREATE TABLE fact_stock_daily (
                    trade_date DATE,
                    stock_ts_code VARCHAR,
                    close DOUBLE,
                    updated_at TIMESTAMP
                )
                """
            )
            con.execute(
                """
                INSERT INTO fact_market_daily
                VALUES ('2026-07-01', 30000, '2026-07-01 20:00:00')
                """
            )
            con.execute(
                """
                INSERT INTO fact_sector_daily
                VALUES ('2026-07-01', '储能', 1200, '2026-07-03 09:00:00')
                """
            )
            con.execute(
                """
                INSERT INTO fact_stock_daily
                VALUES ('2026-07-01', '000001.SZ', 10.5, '2026-07-01 20:00:00')
                """
            )
        finally:
            con.close()
        return path

    def test_final_history_ex_post_marked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            snapshot = build_final_history("2026-07-01", self._db(Path(tmp)))
            sector = snapshot["tables"]["fact_sector_daily"]["rows"][0]
            market = snapshot["tables"]["fact_market_daily"]["rows"][0]
            self.assertEqual(sector["revision_note"], "ex-post")
            self.assertIsNone(market["revision_note"])
            self.assertEqual(sector["valid_time"], "2026-07-01")
            self.assertEqual(snapshot["status"], "ready")

    def test_as_known_at_respects_cutoff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshot = build_as_known_at(
                "2026-07-01",
                self._db(root),
                root,
                root,
                cutoff_for_date("2026-07-01"),
            )
            self.assertEqual(
                snapshot["tables"]["fact_sector_daily"]["known_row_count"], 0
            )
            self.assertEqual(
                snapshot["tables"]["fact_market_daily"]["known_row_count"], 1
            )
            known_rows = [
                row
                for table in snapshot["tables"].values()
                for row in table["rows"]
            ]
            self.assertTrue(
                all(
                    row["known_at"] < snapshot["cutoff_timestamp"]
                    for row in known_rows
                )
            )
            self.assertEqual(snapshot["status"], "partial")

    def test_strict_isolation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = self._db(root)
            output = root / "out"
            result = main(
                [
                    "pilot",
                    "--db",
                    str(db),
                    "--kb-root",
                    str(root),
                    "--finance-root",
                    str(root),
                    "--dates",
                    '["2026-07-01"]',
                    "--out-dir",
                    str(output),
                    "--feature-contract",
                    "fact_market_daily:total_amount:1",
                ]
            )
            self.assertEqual(result, 0)
            final_path = output / "final_history" / "2026-07-01.final.json"
            known_path = output / "as_known_at" / "2026-07-01.known.json"
            self.assertTrue(final_path.exists())
            self.assertTrue(known_path.exists())
            self.assertNotEqual(final_path.parent, known_path.parent)
            final = json.loads(final_path.read_text(encoding="utf-8"))
            known = json.loads(known_path.read_text(encoding="utf-8"))
            self.assertEqual(final["view"], "final_history")
            self.assertEqual(known["view"], "as_known_at")
            self.assertEqual(
                final["source_snapshot_sha256"],
                known["source_snapshot_sha256"],
            )
            for table, final_table in final["tables"].items():
                self.assertEqual(
                    final_table["row_count"],
                    known["tables"][table]["final_row_count"],
                )
            self.assertNotIn(
                "ex-post",
                {
                    row["revision_note"]
                    for table in known["tables"].values()
                    for row in table["rows"]
                },
            )

    def test_phase2_inputs_and_outcomes_use_separate_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = self._db(root)
            inputs = root / "inputs"
            outcomes = root / "outcomes"
            result = main(
                [
                    "inputs",
                    "--db",
                    str(db),
                    "--kb-root",
                    str(root),
                    "--finance-root",
                    str(root),
                    "--dates",
                    '["2026-07-01"]',
                    "--out-dir",
                    str(inputs),
                    "--feature-contract",
                    "fact_market_daily:total_amount:1",
                ]
            )
            self.assertEqual(result, 0)
            self.assertTrue(
                (
                    inputs
                    / "as_known_at"
                    / "2026-07-01.known.json"
                ).exists()
            )
            self.assertFalse((inputs / "final_history").exists())
            self.assertTrue((inputs / "input.report.json").exists())

            result = main(
                [
                    "outcomes",
                    "--db",
                    str(db),
                    "--dates",
                    '["2026-07-01"]',
                    "--out-dir",
                    str(outcomes),
                ]
            )
            self.assertEqual(result, 0)
            self.assertTrue(
                (
                    outcomes
                    / "final_history"
                    / "2026-07-01.final.json"
                ).exists()
            )
            comparison = root / "comparison.json"
            result = main(
                [
                    "compare-batch",
                    "--known-dir",
                    str(inputs / "as_known_at"),
                    "--final-dir",
                    str(outcomes / "final_history"),
                    "--dates",
                    '["2026-07-01"]',
                    "--out",
                    str(comparison),
                ]
            )
            self.assertEqual(result, 0)
            body = json.loads(comparison.read_text(encoding="utf-8"))
            self.assertTrue(body["physically_separate"])
            self.assertEqual(body["date_count"], 1)

    def test_feature_contract_detects_gaps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "contract.duckdb"
            con = self.duckdb.connect(str(path))
            try:
                con.execute(
                    """
                    CREATE TABLE fact_market_daily (
                        trade_date DATE,
                        total_amount DOUBLE,
                        updated_at TIMESTAMP
                    )
                    """
                )
                for day in range(1, 21):
                    updated_at = (
                        "2026-01-25 09:00:00"
                        if day == 10
                        else f"2026-01-{day:02d} 20:00:00"
                    )
                    con.execute(
                        "INSERT INTO fact_market_daily VALUES (?, ?, ?)",
                        [f"2026-01-{day:02d}", 1000 + day, updated_at],
                    )
            finally:
                con.close()
            result = feature_contract_check(
                "2026-01-20",
                path,
                20,
                "fact_market_daily",
                "total_amount",
            )
            self.assertFalse(result["eligible"])
            self.assertEqual(result["status"], "ineligible")
            self.assertEqual(result["missing_dates"], ["2026-01-10"])

    def test_major_field_revision_needs_review(self) -> None:
        final = {
            "date": "2026-07-01",
            "view": "final_history",
            "tables": {
                "fact_stock_daily": {
                    "rows": [
                        {
                            "trade_date": "2026-07-01",
                            "stock_ts_code": "000001.SZ",
                            "close": 10.5,
                        }
                    ]
                }
            },
        }
        known = {
            "date": "2026-07-01",
            "view": "as_known_at",
            "tables": {
                "fact_stock_daily": {
                    "rows": [
                        {
                            "trade_date": "2026-07-01",
                            "stock_ts_code": "000001.SZ",
                            "close": 10.0,
                        }
                    ]
                }
            },
        }
        comparison = compare_snapshots(final, known)
        self.assertEqual(comparison["status"], "needs_review")
        self.assertEqual(comparison["needs_review"][0]["field"], "close")


if __name__ == "__main__":
    unittest.main()
