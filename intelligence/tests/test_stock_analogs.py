"""D11 个股走势类比：签名/距离/前向事实/加载降级/渲染纪律/接线门控。"""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from intelligence.services.stock_analogs import (
    DEFAULT_WINDOW,
    MIN_HISTORY_MULTIPLE,
    StockSignature,
    _distance,
    _forward_facts,
    _signature,
    find_stock_analog_windows,
    load_stock_analog_artifact,
    parse_stock_analog_intent,
    stock_analog_block_for_llm,
)


def _row(date: str, pct: float | None, amount: float | None) -> tuple:
    return (date, pct, amount)


def _series(n: int, pct: float = 0.5, amount: float = 5.0) -> list[tuple]:
    return [_row(f"2025-{(i // 28) + 1:02d}-{(i % 28) + 1:02d}", pct, amount) for i in range(n)]


class ParseIntentTests(unittest.TestCase):
    def test_analog_terms_route(self) -> None:
        self.assertTrue(parse_stock_analog_intent("英维克历史上有没有类似这段的走势"))
        self.assertTrue(parse_stock_analog_intent("300750 对标过往哪一段"))

    def test_plain_stock_question_does_not_route(self) -> None:
        self.assertFalse(parse_stock_analog_intent("英维克现在贵不贵"))
        self.assertFalse(parse_stock_analog_intent(""))


class SignatureTests(unittest.TestCase):
    def test_signature_counts_strong_days_and_ratio(self) -> None:
        rows = [_row("d1", 6.0, 2.0), _row("d2", 1.0, 3.0), _row("d3", 5.0, 4.0)]
        sig = _signature(rows)
        self.assertEqual(sig.strong_days, 2)
        self.assertAlmostEqual(sig.amount_ratio, 2.0)
        self.assertAlmostEqual(sig.avg_pct, 4.0)

    def test_distance_none_when_fields_missing(self) -> None:
        a = StockSignature(1, None, 1.0)
        b = StockSignature(1, 1.0, 1.0)
        self.assertIsNone(_distance(a, b, 20))

    def test_identical_signatures_zero_distance(self) -> None:
        a = StockSignature(3, 1.5, 2.0)
        self.assertEqual(_distance(a, a, 20), 0.0)


class ForwardFactsTests(unittest.TestCase):
    def test_peak_days_and_drawdown(self) -> None:
        # 先涨 3 天（+10% 复利）再跌 2 天：峰在第 3 日，末值低于峰值
        rows = [_row(f"d{i}", p, 1.0) for i, p in enumerate([10.0, 10.0, 10.0, -5.0, -5.0])]
        fwd = _forward_facts(rows, 5)
        assert fwd is not None
        self.assertEqual(fwd["days_to_peak"], 3)
        self.assertAlmostEqual(fwd["max_cum_pct"], 33.1, places=1)
        self.assertLess(fwd["cum_pct"], fwd["max_cum_pct"])
        self.assertLess(fwd["drawdown_from_peak_pct"], 0)

    def test_insufficient_rows_returns_none(self) -> None:
        self.assertIsNone(_forward_facts([_row("d1", 1.0, 1.0)], 5))

    def test_mostly_null_pct_returns_none(self) -> None:
        rows = [_row(f"d{i}", None, 1.0) for i in range(5)]
        self.assertIsNone(_forward_facts(rows, 5))


class FindWindowsTests(unittest.TestCase):
    def test_short_history_returns_none(self) -> None:
        rows = _series(DEFAULT_WINDOW * MIN_HISTORY_MULTIPLE - 1)
        current, analogs = find_stock_analog_windows(rows)
        self.assertIsNone(current)
        self.assertEqual(analogs, [])

    def test_finds_planted_similar_window(self) -> None:
        # 200 日平稳序列，在 40~60 埋一段与当前窗口同形态的强势段
        rows = _series(200, pct=0.1, amount=5.0)
        for i in range(40, 60):
            rows[i] = _row(rows[i][0], 6.0, 5.0 + (i - 40) * 0.5)
        for i in range(180, 200):
            rows[i] = _row(rows[i][0], 6.0, 5.0 + (i - 180) * 0.5)
        current, analogs = find_stock_analog_windows(rows, window=20)
        assert current is not None
        self.assertTrue(analogs)
        best = analogs[0]
        self.assertEqual(best["signature"]["strong_days"], 20)
        # 埋的段应是距离最近的
        self.assertLessEqual(best["distance"], analogs[-1]["distance"])
        # 前向事实带多观测量
        fwd10 = best["forwards"][10]
        assert fwd10 is not None
        self.assertIn("max_cum_pct", fwd10)
        self.assertIn("days_to_peak", fwd10)

    def test_windows_do_not_overlap(self) -> None:
        rows = _series(300, pct=1.0, amount=5.0)
        _, analogs = find_stock_analog_windows(rows, window=20, top_k=3)
        spans = [(a["start_date"], a["end_date"]) for a in analogs]
        self.assertEqual(len(spans), len(set(spans)))
        dates = sorted((a["start_date"], a["end_date"]) for a in analogs)
        for (s1, e1), (s2, e2) in zip(dates, dates[1:]):
            self.assertLess(e1, s2)


def _make_db(path: Path, n: int = 200) -> None:
    import duckdb

    con = duckdb.connect(str(path))
    con.execute(
        """
        create table fact_stock_daily (
            trade_date date, stock_ts_code text, stock_name text,
            close double, pre_close double, pct_chg double,
            amount double, turnover double, source text, updated_at timestamp
        )
        """
    )
    from datetime import date, timedelta

    base = date(2025, 1, 1)
    for i in range(n):
        pct = 6.0 if 40 <= i < 60 or i >= n - 20 else 0.1
        con.execute(
            "insert into fact_stock_daily values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [base + timedelta(days=i), "300001.SZ", "英维克", 10.0, 10.0, pct, 5.0, 2.0, "t", None],
        )
    con.close()


class LoaderAndBlockTests(unittest.TestCase):
    def test_missing_db_degrades(self) -> None:
        artifact = load_stock_analog_artifact("英维克 历史上类似", "/nonexistent/x.duckdb")
        self.assertFalse(artifact.available)
        self.assertIsNotNone(artifact.degrade_reason)
        self.assertEqual(stock_analog_block_for_llm("英维克 历史上类似", "/nonexistent/x.duckdb"), "")

    def test_no_stock_in_query_yields_empty_block(self) -> None:
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            _make_db(db)
            artifact = load_stock_analog_artifact("固态电池历史上类似的行情", db)
            block = stock_analog_block_for_llm("固态电池历史上类似的行情", db)
        self.assertIsNone(artifact.stock_code)
        self.assertEqual(block, "")

    def test_resolves_by_name_and_renders_discipline(self) -> None:
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            _make_db(db)
            artifact = load_stock_analog_artifact("英维克这段走势历史上有类似的吗", db)
            block = stock_analog_block_for_llm("英维克这段走势历史上有类似的吗", db)
        self.assertTrue(artifact.available)
        self.assertEqual(artifact.stock_code, "300001.SZ")
        self.assertIn("[D11]", block)
        self.assertIn("小样本历史事实，不是概率预测", block)
        self.assertIn("区间最高", block)
        self.assertIn("除权除息", block)

    def test_resolves_by_code(self) -> None:
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            _make_db(db)
            artifact = load_stock_analog_artifact("300001 类似历史走势", db)
        self.assertEqual(artifact.stock_code, "300001.SZ")
        self.assertEqual(artifact.stock_name, "英维克")

    def test_short_history_declares_degrade_in_block(self) -> None:
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            _make_db(db, n=30)
            artifact = load_stock_analog_artifact("英维克 历史上类似", db)
            block = stock_analog_block_for_llm("英维克 历史上类似", db)
        self.assertFalse(artifact.available)
        self.assertIn("数据缺口", block)
        self.assertIn("禁止外推", block)

    def test_artifact_payload_serializes(self) -> None:
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            _make_db(db)
            payload = load_stock_analog_artifact("英维克 历史上类似", db).to_payload()
        self.assertEqual(payload["evidence_id"], "D11")
        self.assertTrue(payload["available"])
        self.assertIsInstance(payload["analogs"], list)


class WiringTests(unittest.TestCase):
    def test_registry_gating_via_legacy_flag(self) -> None:
        from intelligence.services import evidence_registry
        from intelligence.services.ask import AskOptions

        on = AskOptions(query="q")
        off = AskOptions(query="q", include_stock_analog_block=False)
        self.assertTrue(evidence_registry.provider_enabled(on, "D11"))
        self.assertFalse(evidence_registry.provider_enabled(off, "D11"))

    def test_d11_claims_are_inferred_not_verified(self) -> None:
        from intelligence.services.answer_model import ClaimStatus
        from intelligence.services.ask_synthesis import _claims_from_data_block

        claims = _claims_from_data_block(
            "- 与 2025-03 窗口距离 0.31，后续 10 日累计 +12.4%（区间最高 +18.2%）",
            "D11",
            "个股走势类比",
            "英维克",
        )
        self.assertTrue(claims)
        self.assertTrue(all(c.status == ClaimStatus.INFERRED for c in claims))


if __name__ == "__main__":
    unittest.main()
