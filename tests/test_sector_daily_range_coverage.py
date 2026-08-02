import unittest
from unittest.mock import MagicMock, patch

from market_feature_store.sync import sync_fupanhui_sector_daily as sync


class SectorDailyRangeCoverageTest(unittest.TestCase):
    def test_partial_api_response_only_marks_covered_dates_synced(self):
        connection = MagicMock()
        coverage = {
            "2026-07-08": {
                "rows": 220,
                "fresh_rows": 220,
                "fresh_null_diff": 0,
                "minimum_rows": 220,
                "ok": True,
            },
            "2026-07-09": {
                "rows": 80,
                "fresh_rows": 80,
                "fresh_null_diff": 0,
                "minimum_rows": 220,
                "ok": False,
            },
        }
        with (
            patch.object(sync, "init_db"),
            patch.object(sync, "connect", return_value=connection),
            patch.object(sync, "_resolve_range_dates", return_value=(["2026-07-08", "2026-07-09"], "range")),
            patch.object(sync, "_existing_sector_daily_counts", return_value={}),
            patch.object(
                sync,
                "_published_sector_counts",
                return_value=({"2026-07-08": 220, "2026-07-09": 220}, {}),
            ),
            patch.object(sync, "sync_fact_sector_daily", return_value={"rows_written": 300}),
            patch.object(sync, "_validate_synced_dates", return_value=coverage),
            patch.object(sync, "_sector_daily_table_stats", return_value=(300, 2, "2026-07-08", "2026-07-09", 0)),
        ):
            result = sync.sync_fact_sector_daily_range(
                start_date="2026-07-08",
                end_date="2026-07-09",
                chunk_days=2,
                sleep=0,
            )

        self.assertEqual(result["synced_dates"], 1)
        self.assertEqual(result["failed_chunks"], 1)
        self.assertEqual(result["failed_dates"], 1)
        self.assertEqual(result["failures"][0]["trade_date"], "2026-07-09")
        self.assertIn("partial response", result["failures"][0]["error"])

    def test_missing_published_snapshot_is_failure_not_legacy_fallback(self):
        connection = MagicMock()
        sync_one = MagicMock(return_value={"rows_written": 1})
        with (
            patch.object(sync, "init_db"),
            patch.object(sync, "connect", return_value=connection),
            patch.object(
                sync,
                "_resolve_range_dates",
                return_value=(["2026-07-08"], "range"),
            ),
            patch.object(sync, "_existing_sector_daily_counts", return_value={}),
            patch.object(
                sync,
                "_published_sector_counts",
                return_value=({}, {"2026-07-08": "no published snapshot"}),
            ),
            patch.object(sync, "sync_fact_sector_daily", sync_one),
            patch.object(
                sync,
                "_sector_daily_table_stats",
                return_value=(0, 0, None, None, 0),
            ),
        ):
            result = sync.sync_fact_sector_daily_range(
                start_date="2026-07-08",
                end_date="2026-07-08",
                sleep=0,
            )

        self.assertEqual(result["synced_dates"], 0)
        self.assertEqual(result["failed_dates"], 1)
        self.assertIn("published snapshot unavailable", result["failures"][0]["error"])
        sync_one.assert_not_called()


if __name__ == "__main__":
    unittest.main()
