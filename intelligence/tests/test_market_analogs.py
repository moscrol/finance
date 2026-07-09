from __future__ import annotations

import unittest
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from intelligence.services.market_analogs import (
    DEFAULT_WINDOW,
    analog_block_for_llm,
    current_pattern_features,
    find_analog_windows,
    load_playbooks,
    match_playbooks,
    parse_analog_intent,
    playbook_distance,
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


def _drawdown_history(n: int = 80) -> list[tuple]:
    """构造末 60 日为「上涨→回撤→部分反弹」形态的历史（前段为平淡日）。"""
    start = date(2025, 1, 1)
    rows = []
    for i in range(n):
        off = i - (n - 60)  # 末 60 日内的位置
        if off < 0:
            rows.append(_row(start + timedelta(days=i), 0.1, 2.0, 300.0))
        elif off < 25:
            rows.append(_row(start + timedelta(days=i), 1.0, 15.0, 900.0))
        elif off < 45:
            rows.append(_row(start + timedelta(days=i), -0.8, 2.0, 400.0))
        else:
            rows.append(_row(start + timedelta(days=i), 0.4, 8.0, 500.0))
    return rows


class PlaybookTests(unittest.TestCase):
    def test_current_pattern_features(self) -> None:
        feats = current_pattern_features(_drawdown_history(), lookback=60)
        assert feats is not None
        self.assertLess(feats["drawdown_pct"], 0)
        self.assertGreater(feats["rebound_retrace_ratio"], 0)
        self.assertIn("volume_shrink_ratio", feats)

    def test_features_none_on_short_history(self) -> None:
        self.assertIsNone(current_pattern_features(_drawdown_history(10), lookback=60))

    def test_distance_missing_dims_penalized(self) -> None:
        cur = {"drawdown_pct": -15.0, "rebound_retrace_ratio": 0.5, "volume_shrink_ratio": 0.4}
        full = {"drawdown_pct": -15.0, "rebound_retrace_ratio": 0.5, "volume_shrink_ratio": 0.4}
        partial = {"drawdown_pct": -15.0}
        d_full = playbook_distance(cur, full)
        d_partial = playbook_distance(cur, partial)
        assert d_full is not None and d_partial is not None
        self.assertEqual(d_full, 0.0)
        self.assertEqual(d_partial, 0.0)  # 差异为 0 时惩罚乘法不改变结果
        partial_off = {"drawdown_pct": -20.0}
        full_off = {"drawdown_pct": -20.0, "rebound_retrace_ratio": 0.5, "volume_shrink_ratio": 0.4}
        d_po = playbook_distance(cur, partial_off)
        d_fo = playbook_distance(cur, full_off)
        assert d_po is not None and d_fo is not None
        self.assertGreater(d_po, d_fo)  # 同样差异，缺维卡距离更大（降权）

    def test_distance_none_when_no_shared_dims(self) -> None:
        self.assertIsNone(playbook_distance({"drawdown_pct": -10.0}, {"other": 1}))

    def test_load_playbooks_filters_drafts(self) -> None:
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "pb.jsonl"
            p.write_text(
                "# comment\n"
                '{"id": "a", "pattern": {"drawdown_pct": -12}, "source": {"review_status": "approved"}}\n'
                '{"id": "b", "pattern": {"drawdown_pct": -30}, "source": {"review_status": "draft"}}\n',
                encoding="utf-8",
            )
            approved = load_playbooks(p)
            self.assertEqual([c["id"] for c in approved], ["a"])
            self.assertEqual(len(load_playbooks(p, include_drafts=True)), 2)

    def test_match_playbooks_orders_by_distance(self) -> None:
        cur = {"drawdown_pct": -15.0, "rebound_retrace_ratio": 0.5, "volume_shrink_ratio": 0.4}
        cards = [
            {"id": "far", "pattern": {"drawdown_pct": -40.0, "rebound_retrace_ratio": 0.9, "volume_shrink_ratio": 1.2}},
            {"id": "near", "pattern": {"drawdown_pct": -14.0, "rebound_retrace_ratio": 0.55, "volume_shrink_ratio": 0.45}},
        ]
        matches = match_playbooks(cur, cards, top_k=2)
        self.assertEqual([c["id"] for _, c in matches], ["near", "far"])

    def test_repo_playbook_file_parses_and_has_no_approved_yet(self) -> None:
        # 仓内首批卡全为 draft（待人工审核），approved 列表应为空，不得自动生效
        drafts = load_playbooks(include_drafts=True)
        self.assertGreaterEqual(len(drafts), 1)
        for card in drafts:
            self.assertIn("pattern", card)
            self.assertIn("source", card)


@unittest.skipIf(duckdb is None, "duckdb 不可用")
class PlaybookBlockRenderTests(unittest.TestCase):
    def test_block_includes_playbook_section(self) -> None:
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            con = duckdb.connect(str(db))
            con.execute(
                "create table fact_sector_daily (trade_date date, sector_name varchar, pct_chg double, diff_ratio double, amount double)"
            )
            for d, pct, diff, amount in _drawdown_history(200):
                con.execute(
                    "insert into fact_sector_daily values (?, '信创', ?, ?, ?)",
                    [d, pct, diff, amount],
                )
            con.close()
            block = analog_block_for_llm("历史上信创类似的走势后来怎么走", "信创", db)
            self.assertIn("跨题材历史剧本类比", block)
            self.assertIn("当前形态特征", block)
            # 仓内卡全为 draft 时必须显式声明缺口而非使用未审核数字
            if not load_playbooks():
                self.assertIn("暂无人工审核通过", block)


if __name__ == "__main__":
    unittest.main()
