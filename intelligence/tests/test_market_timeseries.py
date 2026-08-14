from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from intelligence.services.market_timeseries import (
    DEFAULT_WINDOW,
    latest_double_red_snapshot_block_for_llm,
    parse_timeseries_intent,
    timeseries_block_for_llm,
)

try:
    import duckdb
except Exception:  # pragma: no cover
    duckdb = None


class ParseTimeseriesIntentTests(unittest.TestCase):
    def test_acceptance_question_routes_three_metrics(self) -> None:
        intent = parse_timeseries_intent(
            "帮我精确查数：过去 10 个交易日涨停家数、连板高度、双红板块数量的逐日变化"
        )
        assert intent is not None
        self.assertEqual(intent.window, 10)
        self.assertEqual(set(intent.metric_keys), {"limit_up", "max_boards", "double_red_count"})

    def test_window_defaults_when_only_intent_words(self) -> None:
        intent = parse_timeseries_intent("涨停家数逐日变化")
        assert intent is not None
        self.assertEqual(intent.window, DEFAULT_WINDOW)
        self.assertEqual(intent.metric_keys, ("limit_up",))

    def test_no_metric_alias_returns_none(self) -> None:
        self.assertIsNone(parse_timeseries_intent("过去 10 个交易日市场情绪怎么样"))

    def test_no_intent_words_returns_none(self) -> None:
        self.assertIsNone(parse_timeseries_intent("今天涨停家数多少"))
        self.assertIsNone(parse_timeseries_intent("深信服现在 PE TTM 80 倍，贵不贵？"))

    def test_window_is_clamped(self) -> None:
        intent = parse_timeseries_intent("过去 999 天涨停家数逐日变化")
        assert intent is not None
        self.assertLessEqual(intent.window, 60)

    def test_longest_alias_wins_over_substring(self) -> None:
        intent = parse_timeseries_intent("近5日涨停家数逐日")
        assert intent is not None
        self.assertEqual(intent.metric_keys, ("limit_up",))
        self.assertEqual(intent.window, 5)


@unittest.skipIf(duckdb is None, "duckdb 不可用")
class TimeseriesBlockTests(unittest.TestCase):
    def _make_db(self, path: Path) -> None:
        con = duckdb.connect(str(path))
        con.execute(
            "create table fact_market_daily (trade_date date, limit_up int, limit_down int, advancers int, total_amount double)"
        )
        con.execute(
            "insert into fact_market_daily values"
            " ('2026-07-06', 40, 10, 1500, 20000.0),"
            " ('2026-07-07', 50, 12, 1600, 21000.5),"
            " ('2026-07-08', 47, 42, 1593, 25633.57)"
        )
        con.execute(
            "create table fact_limit_advance_daily (trade_date date, boards int, promotion_rate varchar)"
        )
        # 2026-07-07 故意缺数据，验证缺口显式声明
        con.execute(
            "insert into fact_limit_advance_daily values"
            " ('2026-07-06', 2, '6/28=21%'), ('2026-07-06', 5, null),"
            " ('2026-07-08', 2, '8/30=27%'), ('2026-07-08', 7, null)"
        )
        con.execute(
            "create table fact_sector_daily (trade_date date, sector_name varchar, pct_chg double, diff_ratio double, amount double)"
        )
        con.execute(
            "insert into fact_sector_daily values"
            " ('2026-07-06', 'A', 1.2, 15.0, 600.0),"   # 双红
            " ('2026-07-06', 'B', -0.5, 20.0, 700.0),"  # 非双红
            " ('2026-07-07', 'A', 0.8, 5.0, 900.0),"    # 非双红（当日双红数=0）
            " ('2026-07-08', 'A', 2.0, 12.0, 800.0),"   # 双红
            " ('2026-07-08', 'B', 1.0, 11.0, 501.0)"    # 双红
        )
        con.close()

    def test_block_renders_table_with_gaps(self) -> None:
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            self._make_db(db)
            intent = parse_timeseries_intent(
                "帮我精确查数：过去 3 个交易日涨停家数、连板高度、双红板块数量的逐日变化"
            )
            assert intent is not None
            block = timeseries_block_for_llm(intent, db)
        self.assertIn("## 盘面时序直查数据块 [D0]", block)
        self.assertIn("| 2026-07-08 | 47 | 7 | 2 |", block)
        self.assertIn("| 2026-07-06 | 40 | 5 | 1 |", block)
        # 07-07 连板缺数标 —，双红有板块行则真 0
        self.assertIn("| 2026-07-07 | 50 | — | 0 |", block)
        self.assertIn("数据缺口", block)
        self.assertIn("2026-07-07", block)
        self.assertIn("pct_chg>0", block.replace(" ", ""))

    def test_on_date_holiday_declares_closure(self) -> None:
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            self._make_db(db)
            intent = parse_timeseries_intent("涨停家数逐日变化")
            assert intent is not None
            block = timeseries_block_for_llm(intent, db, on_date="2026-02-17")
        self.assertIn("休市", block)
        self.assertIn("2026-02-17", block)
        self.assertIn("| 2026-02-17 | — |", block)

    def test_missing_db_returns_empty(self) -> None:
        intent = parse_timeseries_intent("过去 5 日涨停家数逐日变化")
        assert intent is not None
        self.assertEqual(timeseries_block_for_llm(intent, "/nonexistent/x.duckdb"), "")

    def test_latest_double_red_snapshot_binds_definition_and_current_list(self) -> None:
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            self._make_db(db)
            block = latest_double_red_snapshot_block_for_llm(db)
        self.assertIn("双红定义：题材涨幅为正、边际量大于 10", block)
        self.assertIn("双红数据截至：2026-07-08", block)
        self.assertIn("A（涨幅 2.00%", block)
        self.assertIn("B（涨幅 1.00%", block)
        self.assertNotIn("2026-07-06", block)


if __name__ == "__main__":
    unittest.main()
