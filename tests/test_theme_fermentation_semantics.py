import importlib.util
import sys
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from market_feature_store.signals import DOUBLE_RED_DESCRIPTION, DOUBLE_RED_SQL, is_double_red


ROOT = Path(__file__).resolve().parents[1]
TRACE = ROOT / "skills" / "theme-fermentation-tracer" / "scripts" / "trace.py"


def load_trace():
    spec = importlib.util.spec_from_file_location("theme_fermentation_trace_test", TRACE)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load trace.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeCursor:
    description = [("value",)]

    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, rows=None, error=None):
        self.rows = rows or []
        self.error = error

    def execute(self, sql, params):
        if self.error:
            raise RuntimeError(self.error)
        return FakeCursor(self.rows)


class DoubleRedSemanticsTest(unittest.TestCase):
    def test_strict_definition_requires_price_diff_and_amount(self):
        self.assertEqual(DOUBLE_RED_SQL, "pct_chg > 0 AND diff_ratio > 10 AND amount > 500")
        self.assertIn("成交额大于 500 亿", DOUBLE_RED_DESCRIPTION)
        self.assertTrue(is_double_red(1.0, 11.0, 501.0))
        self.assertTrue(is_double_red(Decimal("1"), Decimal("11"), Decimal("501")))
        self.assertFalse(is_double_red(1.0, 11.0, 500.0))
        self.assertFalse(is_double_red(1.0, 10.0, 600.0))
        self.assertFalse(is_double_red(-1.0, 20.0, 600.0))

    def test_tracer_uses_strict_definition_for_streaks(self):
        trace = load_trace()
        rows = [
            {"trade_date": date(2026, 7, 8), "sector_name": "A", "pct_chg": 1.0, "diff_ratio": 20.0, "amount": 100.0, "multi_period_resonance": False},
            {"trade_date": date(2026, 7, 9), "sector_name": "A", "pct_chg": 1.0, "diff_ratio": 20.0, "amount": 600.0, "multi_period_resonance": False},
        ]
        with patch.object(trace, "query_rows", return_value=rows):
            timeline = trace.sector_timeline(object(), ["A"], date(2026, 7, 8), date(2026, 7, 9))

        self.assertFalse(timeline[0]["double_red"])
        self.assertEqual(timeline[0]["double_red_streak"], 0)
        self.assertTrue(timeline[1]["double_red"])
        self.assertEqual(timeline[1]["double_red_streak"], 1)


class QueryStateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.trace = load_trace()

    def test_query_distinguishes_success_no_data_and_error(self):
        success = self.trace.query(FakeConnection(rows=[(1,)]), "select 1", [])
        no_data = self.trace.query(FakeConnection(rows=[]), "select 1", [])
        error = self.trace.query(FakeConnection(error="schema missing"), "select 1", [])

        self.assertEqual(success.status, "success")
        self.assertEqual(no_data.status, "no_data")
        self.assertEqual(error.status, "error")
        self.assertIn("schema missing", error.error)

    def test_query_error_cannot_be_consumed_as_empty_business_result(self):
        with self.assertRaises(self.trace.QueryExecutionError):
            self.trace.query_rows(FakeConnection(error="schema missing"), "select 1", [])


if __name__ == "__main__":
    unittest.main()
