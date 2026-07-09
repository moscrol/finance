from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from intelligence.services.market_midterm import (
    DEFAULT_WINDOW,
    midterm_trend_block_for_llm,
    parse_midterm_intent,
    resolve_query_themes,
)

try:
    import duckdb
except Exception:  # pragma: no cover
    duckdb = None


class ParseMidtermIntentTests(unittest.TestCase):
    def test_mid_term_odds_question_routes(self) -> None:
        intent = parse_midterm_intent(
            "比较数据要素、信创、数据安全三个方向的中期赔率（未来 3-6 个月），给出优先排序"
        )
        assert intent is not None
        self.assertEqual(intent.window, DEFAULT_WINDOW)

    def test_month_window_phrase_routes(self) -> None:
        self.assertIsNotNone(parse_midterm_intent("未来 6 个月信创怎么配置"))
        self.assertIsNotNone(parse_midterm_intent("3-6个月这个方向的配置价值"))

    def test_short_line_question_does_not_route(self) -> None:
        self.assertIsNone(parse_midterm_intent("今天信创板块怎么样"))
        self.assertIsNone(parse_midterm_intent("过去 10 个交易日涨停家数逐日变化"))


@unittest.skipIf(duckdb is None, "duckdb 不可用")
class MidtermBlockTests(unittest.TestCase):
    def _make_db(self, path: Path) -> None:
        con = duckdb.connect(str(path))
        con.execute(
            "create table fact_sector_daily "
            "(trade_date date, sector_name varchar, pct_chg double, diff_ratio double, amount double)"
        )
        # 信创：近3日成交额缩量（2000→1600），仅1天双红 → 短期脉冲
        con.execute(
            "insert into fact_sector_daily values"
            " ('2026-07-06', '信创', -1.0, 5.0, 2000.0),"
            " ('2026-07-07', '信创', -2.0, -18.0, 1800.0),"
            " ('2026-07-08', '信创', 1.5, 14.75, 1600.0),"   # 双红
            " ('2026-07-06', '数据要素', 0.5, 12.0, 600.0),"  # 双红
            " ('2026-07-07', '数据要素', 1.0, 15.0, 650.0),"  # 双红
            " ('2026-07-08', '数据要素', 2.0, 20.0, 700.0)"   # 双红，放量
        )
        con.execute(
            "create table fact_theme_limit_heat_daily "
            "(trade_date date, sector_name varchar, limit_up_count int, rank int)"
        )
        con.execute(
            "insert into fact_theme_limit_heat_daily values"
            " ('2026-07-06', '信创', 4, 22),"
            " ('2026-07-07', '信创', 2, 28),"
            " ('2026-07-08', '信创', 13, 5)"
        )
        con.close()

    def test_resolve_themes_longest_first(self) -> None:
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            self._make_db(db)
            con = duckdb.connect(str(db), read_only=True)
            try:
                themes = resolve_query_themes(con, "比较信创和数据要素的中期赔率")
            finally:
                con.close()
        self.assertIn("信创", themes)
        self.assertIn("数据要素", themes)

    def test_block_renders_trend_and_crowding(self) -> None:
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            self._make_db(db)
            block = midterm_trend_block_for_llm(
                "比较信创、数据要素的中期赔率（未来 3-6 个月）", "信创", db, window=20
            )
        self.assertIn("## 多日/中期趋势数据块 [D6]", block)
        self.assertIn("信创", block)
        self.assertIn("数据要素", block)
        # 信创缩量、涨停热度 4→13、rank5
        self.assertIn("缩量", block)
        self.assertIn("4→13", block)
        self.assertIn("当日强度 ≠ 中期赔率", block)

    def test_missing_theme_declares_gap(self) -> None:
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            self._make_db(db)
            # 数据安全在板块表无行 → 缺口声明
            block = midterm_trend_block_for_llm(
                "比较信创、数据安全的中期赔率", "信创", db, window=20
            )
        self.assertIn("数据安全", block)
        self.assertIn("数据缺口", block)

    def test_missing_db_returns_empty(self) -> None:
        self.assertEqual(
            midterm_trend_block_for_llm("信创中期赔率", "信创", "/nonexistent/x.duckdb"),
            "",
        )


if __name__ == "__main__":
    unittest.main()
