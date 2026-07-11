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
                "minimum_rows": 202,
                "ok": True,
            },
            "2026-07-09": {
                "rows": 80,
                "fresh_rows": 80,
                "fresh_null_diff": 0,
                "minimum_rows": 202,
                "ok": False,
            },
        }
        with (
            patch.object(sync, "init_db"),
            patch.object(sync, "connect", return_value=connection),
            patch.object(sync, "_load_sector_dim", return_value={f"S{i}": (f"sector-{i}", "sw") for i in range(224)}),
            patch.object(sync, "_resolve_range_dates", return_value=(["2026-07-08", "2026-07-09"], "range")),
            patch.object(sync, "_existing_sector_daily_counts", return_value={}),
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


if __name__ == "__main__":
    unittest.main()
