from __future__ import annotations

import unittest
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from intelligence.services.market_analogs import (
    DEFAULT_WINDOW,
    analog_block_for_llm,
    find_analog_windows,
    parse_analog_intent,
)

try:
    import duckdb
except Exception:  # pragma: no cover
    duckdb = None


class ParseAnalogIntentTests(unittest.TestCase):
    def test_analog_terms_route(self) -> None:
        self.assertTrue(parse_analog_intent("历史上类似的高低切换怎么走"))
        self.assertTrue(parse_analog_intent("上一次信创这样放量之后发生了什么"))
        self.assertTrue(parse_analog_intent("有没有先例可以参考"))

    def test_plain_questions_do_not_route(self) -> None:
        self.assertFalse(parse_analog_intent("今天信创板块怎么样"))
        self.assertFalse(parse_analog_intent("数据安全的中期赔率"))
        self.assertFalse(parse_analog_intent(""))


def _row(d: date, pct: float, diff: float, amount: float) -> tuple:
    return (d.isoformat(), pct, diff, amount)


def _history(n: int, hot_ranges: list[tuple[int, int]]) -> list[tuple]:
    """构造 n 日历史：默认弱势日，hot_ranges 段是双红强势日。"""
    start = date(2025, 1, 1)
    rows = []
    for i in range(n):
        hot = any(a <= i < b for a, b in hot_ranges)
        if hot:
            rows.append(_row(start + timedelta(days=i), 2.5, 15.0, 900.0))
        else:
            rows.append(_row(start + timedelta(days=i), -0.5, 2.0, 300.0))
    return rows


class FindAnalogWindowsTests(unittest.TestCase):
    def test_short_history_returns_none(self) -> None:
        rows = _history(30, [])
        current, analogs = find_analog_windows(rows, window=DEFAULT_WINDOW)
        self.assertIsNone(current)
        self.assertEqual(analogs, [])

    def test_finds_similar_hot_window(self) -> None:
        # 历史上 40-60 日是强势段，当前（末尾 20 日）也是强势段 → 应命中历史强势窗口
        rows = _history(200, [(40, 60), (180, 200)])
        current, analogs = find_analog_windows(rows, window=20)
        assert current is not None
        self.assertEqual(current.double_red_days, 20)
        self.assertTrue(analogs)
        best = analogs[0]
        self.assertEqual(best["signature"].double_red_days, 20)
        # 后续 5/10/20 日事实存在（历史窗口之后还有数据）
        self.assertIsNotNone(best["forwards"][5])
        self.assertIsNotNone(best["forwards"][20])

    def test_windows_do_not_overlap(self) -> None:
        rows = _history(300, [(40, 60), (100, 120), (280, 300)])
        _, analogs = find_analog_windows(rows, window=20, top_k=3)
        spans = [(a["start_date"], a["end_date"]) for a in analogs]
        for i in range(len(spans)):
            for j in range(i + 1, len(spans)):
                s1, e1 = spans[i]
                s2, e2 = spans[j]
                self.assertTrue(e1 < s2 or e2 < s1 or (e1 <= s2 or e2 <= s1))


@unittest.skipIf(duckdb is None, "duckdb 不可用")
class AnalogBlockTests(unittest.TestCase):
    def _make_db(self, path: Path, n: int = 200) -> None:
        con = duckdb.connect(str(path))
        con.execute(
            "create table fact_sector_daily (trade_date date, sector_name varchar, pct_chg double, diff_ratio double, amount double)"
        )
        for d, pct, diff, amount in _history(n, [(40, 60), (180, 200)]):
            con.execute(
                "insert into fact_sector_daily values (?, '信创', ?, ?, ?)",
                [d, pct, diff, amount],
            )
        con.close()

    def test_block_renders_with_citation_and_discipline(self) -> None:
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            self._make_db(db)
            block = analog_block_for_llm("历史上信创类似的走势后来怎么走", "信创", db)
            self.assertIn("[D8]", block)
            self.assertIn("信创", block)
            self.assertIn("后续5日", block)
            self.assertIn("不是概率预测", block)

    def test_short_history_declares_gap(self) -> None:
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            self._make_db(db, n=30)
            block = analog_block_for_llm("历史上信创类似走势", "信创", db)
            self.assertIn("数据缺口", block)

    def test_missing_db_returns_empty(self) -> None:
        self.assertEqual(
            analog_block_for_llm("历史上类似怎么走", "信创", "/nonexistent/x.duckdb"),
            "",
        )


if __name__ == "__main__":
    unittest.main()
