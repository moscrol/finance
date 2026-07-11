import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

from market_feature_store.sync import sync_daily_full


ROOT = Path(__file__).resolve().parents[1]
RUN_REVIEW_SYNC = ROOT / "skills" / "daily-full-review" / "scripts" / "run_review_sync.py"


def load_run_review_sync():
    spec = importlib.util.spec_from_file_location("run_review_sync_quality_test", RUN_REVIEW_SYNC)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load run_review_sync.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DailyFullQualityOrderTest(unittest.TestCase):
    def test_same_day_failure_does_not_generate_report(self):
        update = {"trade_date": "2026-07-10", "ok": False, "steps": [], "validation": {"ok": False}}
        with (
            patch.object(sync_daily_full, "run_daily_update", return_value=update),
            patch("market_feature_store.quality.check_daily") as cross_day,
            patch("market_feature_store.reports.daily_review.build_daily_review") as build_report,
        ):
            result = sync_daily_full.run_daily_full("2026-07-10")

        cross_day.assert_not_called()
        build_report.assert_not_called()
        self.assertIsNone(result["review"])
        self.assertFalse(result["ok"])

    def test_cross_day_failure_does_not_generate_report(self):
        update = {"trade_date": "2026-07-10", "ok": True, "steps": [], "validation": {"ok": True}}
        with (
            patch.object(sync_daily_full, "run_daily_update", return_value=update),
            patch("market_feature_store.quality.check_daily", return_value={"ok": False, "brief": "gap"}),
            patch("market_feature_store.reports.daily_review.build_daily_review") as build_report,
        ):
            result = sync_daily_full.run_daily_full("2026-07-10")

        build_report.assert_not_called()
        self.assertIsNone(result["review"])
        self.assertFalse(result["ok"])


class ReviewSyncReleaseOrderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_run_review_sync()

    def test_gate_failure_stops_before_export(self):
        failed = {"label": "same-day-gate", "status": "fail", "code": 1, "elapsed": 0.1}
        with patch.object(self.module, "run_step", return_value=failed) as run_step:
            results, ok = self.module.run_release_steps("2026-07-10", 30)

        self.assertFalse(ok)
        self.assertEqual(results, [failed])
        self.assertEqual(run_step.call_count, 1)

    def test_release_order_is_same_day_cross_day_then_export(self):
        def fake_run_step(label, argv, timeout):
            return {"label": label, "status": "ok", "code": 0, "elapsed": 0.1}

        with patch.object(self.module, "run_step", side_effect=fake_run_step) as run_step:
            results, ok = self.module.run_release_steps("2026-07-10", 30)

        self.assertTrue(ok)
        self.assertEqual(
            [result["label"] for result in results],
            ["same-day-gate", "cross-day-gate", "export-increment"],
        )
        self.assertEqual(run_step.call_count, 3)


if __name__ == "__main__":
    unittest.main()
