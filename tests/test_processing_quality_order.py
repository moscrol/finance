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


class SectorStocksReceiptLoopTest(unittest.TestCase):
    """夜间成分循环由回执审计驱动, 而非计数轮询。"""

    @classmethod
    def setUpClass(cls):
        cls.module = load_run_review_sync()

    @staticmethod
    def _audit(complete: bool, note: str = "brief"):
        class _Audit:
            def __init__(self) -> None:
                self.complete = complete

            def brief(self) -> str:
                return note

        return _Audit()

    def test_complete_audit_stops_without_running_a_loop(self):
        with (
            patch.object(self.module, "_sector_audit", return_value=self._audit(True)),
            patch.object(self.module, "run_step") as run_step,
        ):
            result = self.module.sync_sector_stocks("2026-07-28", 30)

        run_step.assert_not_called()
        self.assertEqual(result["status"], "ok")

    def test_incomplete_audit_after_max_loops_reports_partial(self):
        with (
            patch.object(self.module, "_sector_audit", return_value=self._audit(False)),
            patch.object(self.module, "run_step") as run_step,
        ):
            result = self.module.sync_sector_stocks("2026-07-28", 30, max_loops=3)

        self.assertEqual(run_step.call_count, 3)
        self.assertEqual(result["status"], "partial")

    def test_loop_stops_as_soon_as_the_audit_turns_complete(self):
        audits = [self._audit(False), self._audit(False), self._audit(True)]
        with (
            patch.object(self.module, "_sector_audit", side_effect=audits),
            patch.object(self.module, "run_step") as run_step,
        ):
            result = self.module.sync_sector_stocks("2026-07-28", 30, max_loops=10)

        self.assertEqual(run_step.call_count, 2)
        self.assertEqual(result["status"], "ok")

    def test_audit_is_rechecked_between_loops_not_cached(self):
        """每轮都要重新审计: 缓存会让一轮内新增的成功回执看不见。"""
        audits = [self._audit(False), self._audit(True)]
        with (
            patch.object(self.module, "_sector_audit", side_effect=audits) as audit,
            patch.object(self.module, "run_step"),
        ):
            self.module.sync_sector_stocks("2026-07-28", 30, max_loops=10)

        self.assertEqual(audit.call_count, 2)


class SectorCompletionGateTest(unittest.TestCase):
    """成分有缺口时不得生成报告——第三道门必须真的挡住。"""

    def test_incomplete_sector_universe_blocks_the_report(self):
        update = {"trade_date": "2026-07-28", "ok": True, "steps": [], "validation": {"ok": True}}
        gate = {"trade_date": "2026-07-28", "ok": False, "brief": "success=1/2"}
        with (
            patch.object(sync_daily_full, "run_daily_update", return_value=update),
            patch("market_feature_store.quality.check_daily", return_value={"ok": True}),
            patch.object(sync_daily_full, "sector_completion_gate", return_value=gate),
            patch("market_feature_store.reports.daily_review.build_daily_review") as build_report,
        ):
            result = sync_daily_full.run_daily_full("2026-07-28")

        build_report.assert_not_called()
        self.assertIsNone(result["review"])
        self.assertFalse(result["ok"])
        self.assertEqual(result["sector_gate"]["brief"], "success=1/2")

    def test_complete_sector_universe_allows_the_report(self):
        update = {"trade_date": "2026-07-28", "ok": True, "steps": [], "validation": {"ok": True}}
        gate = {"trade_date": "2026-07-28", "ok": True, "brief": "success=2/2"}
        with (
            patch.object(sync_daily_full, "run_daily_update", return_value=update),
            patch("market_feature_store.quality.check_daily", return_value={"ok": True}),
            patch.object(sync_daily_full, "sector_completion_gate", return_value=gate),
            patch("market_feature_store.reports.daily_review.build_daily_review") as build_report,
        ):
            result = sync_daily_full.run_daily_full("2026-07-28")

        build_report.assert_called_once()
        self.assertTrue(result["ok"])

    def test_earlier_gate_failure_skips_the_sector_gate(self):
        update = {"trade_date": "2026-07-28", "ok": False, "steps": [], "validation": {"ok": False}}
        with (
            patch.object(sync_daily_full, "run_daily_update", return_value=update),
            patch("market_feature_store.quality.check_daily"),
            patch.object(sync_daily_full, "sector_completion_gate") as sector_gate,
            patch("market_feature_store.reports.daily_review.build_daily_review"),
        ):
            result = sync_daily_full.run_daily_full("2026-07-28")

        sector_gate.assert_not_called()
        self.assertTrue(result["sector_gate"]["skipped"])
