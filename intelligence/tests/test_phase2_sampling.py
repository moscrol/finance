from __future__ import annotations

import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

import duckdb

from intelligence.eval.phase2_sampling import (
    build_phase2_plan,
    discover_canonical_report,
    select_stratified_dates,
)


class Phase2SamplingTest(unittest.TestCase):
    def test_exact_date_report_priority(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            export = root / "market_feature_store" / "exports"
            review = root / "复盘" / "daily" / "2026-06-11"
            export.mkdir(parents=True)
            review.mkdir(parents=True)
            (export / "2026-06-11-daily-agent.json").write_text(
                "{}",
                encoding="utf-8",
            )
            (review / "2026-06-11-daily-review.html").write_text(
                "<p>review</p>",
                encoding="utf-8",
            )
            self.assertEqual(
                discover_canonical_report(root, "2026-06-11"),
                (
                    "market_feature_store/exports/"
                    "2026-06-11-daily-agent.json"
                ),
            )
            self.assertIsNone(
                discover_canonical_report(root, "2026-06-12")
            )

    def test_selector_keeps_reports_and_stratifies_missing_dates(
        self,
    ) -> None:
        frame = [
            {
                "report_date": f"2026-06-{day:02d}",
                "month": "2026-06",
                "market_stage": "横盘" if day % 2 else "主升",
                "data_completeness": (
                    "partial" if day % 3 else "pending"
                ),
                "canonical_report_path": (
                    f"report-{day}.json" if day in {1, 2} else None
                ),
            }
            for day in range(1, 9)
        ]
        selected = select_stratified_dates(
            frame,
            count=6,
            seed="test",
        )
        selected_dates = {
            str(row["report_date"]) for row in selected
        }
        self.assertEqual(len(selected), 6)
        self.assertIn("2026-06-01", selected_dates)
        self.assertIn("2026-06-02", selected_dates)
        self.assertGreater(
            len(
                {
                    (
                        row["market_stage"],
                        row["data_completeness"],
                    )
                    for row in selected
                }
            ),
            1,
        )

    def test_phase2_plan_marks_true_negative_controls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            database = root / "market.duckdb"
            connection = duckdb.connect(str(database))
            for table in (
                "fact_market_daily",
                "fact_sector_daily",
                "fact_stock_daily",
            ):
                connection.execute(
                    f"""
                    CREATE TABLE {table} (
                        trade_date DATE,
                        market_stage VARCHAR,
                        updated_at TIMESTAMP
                    )
                    """
                )
            start = date(2026, 1, 1)
            for offset in range(60):
                value = start + timedelta(days=offset)
                known_at = f"{value.isoformat()} 18:00:00"
                for table in (
                    "fact_market_daily",
                    "fact_sector_daily",
                    "fact_stock_daily",
                ):
                    connection.execute(
                        f"INSERT INTO {table} VALUES (?, ?, ?)",
                        [value, "横盘", known_at],
                    )
            connection.close()
            report = (
                root
                / "market_feature_store"
                / "exports"
                / "2026-01-01-daily-agent.json"
            )
            report.parent.mkdir(parents=True)
            report.write_text("{}", encoding="utf-8")
            plan, registry = build_phase2_plan(
                db_path=database,
                repo_root=root,
                start="2026-01-01",
                end="2026-03-01",
                count=50,
                seed="test",
            )
            self.assertEqual(plan["selected_count"], 50)
            self.assertEqual(
                plan["selected_strata"]["report_status"]["registered"],
                1,
            )
            self.assertEqual(
                plan["selected_strata"]["report_status"]["missing"],
                49,
            )
            reports = registry["reports"]
            self.assertTrue(
                any(
                    report["report_date"] == "2026-01-01"
                    and report["status"] == "registered"
                    for report in reports
                )
            )


if __name__ == "__main__":
    unittest.main()
