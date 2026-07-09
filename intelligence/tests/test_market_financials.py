from __future__ import annotations

import unittest

from intelligence.services.market_financials import (
    QuarterFinancials,
    _secucode,
    build_financials_block,
    financials_block_for_target,
    parse_financials_intent,
)


class ParseFinancialsIntentTests(unittest.TestCase):
    def test_financial_questions_route(self) -> None:
        self.assertTrue(parse_financials_intent("厦门钨业 H1 快报正极能否扭亏"))
        self.assertTrue(parse_financials_intent("深信服近几个季度营收和毛利率怎么走"))
        self.assertTrue(parse_financials_intent("这家公司业绩兑现节奏如何"))

    def test_non_financial_questions_do_not_route(self) -> None:
        self.assertFalse(parse_financials_intent("今天信创板块盘面怎么样"))
        self.assertFalse(parse_financials_intent("过去 10 个交易日涨停家数逐日变化"))


class SecucodeTests(unittest.TestCase):
    def test_suffix_inference(self) -> None:
        self.assertEqual(_secucode("300454"), "300454.SZ")
        self.assertEqual(_secucode("688111"), "688111.SH")
        self.assertEqual(_secucode("600000"), "600000.SH")
        self.assertEqual(_secucode("830879"), "830879.BJ")

    def test_existing_suffix_preserved(self) -> None:
        self.assertEqual(_secucode("300454.SZ"), "300454.SZ")
        self.assertEqual(_secucode("600000.sh"), "600000.SH")

    def test_invalid_returns_none(self) -> None:
        self.assertIsNone(_secucode("not-a-code"))
        self.assertIsNone(_secucode(""))


class FinancialsBlockTests(unittest.TestCase):
    def _rows(self) -> list[QuarterFinancials]:
        return [
            QuarterFinancials("2026一季报", "2026-03-31", 16.27, 28.9, -0.65, 74.2, 60.3, -3.97),
            QuarterFinancials("2025年报", "2025-12-31", 80.43, 5.1, 3.93, 99.6, 59.3, 4.88),
        ]

    def test_block_renders_table_and_usage(self) -> None:
        block = build_financials_block("深信服", "300454.SZ", self._rows())
        self.assertIn("[D7]", block)
        self.assertIn("2026一季报", block)
        self.assertIn("16.27", block)
        self.assertIn("60.3", block)
        self.assertIn("累计", block)
        self.assertIn("使用要求", block)

    def test_empty_rows_declare_gap(self) -> None:
        block = build_financials_block("某公司", "000001.SZ", [])
        self.assertIn("缺逐季财报", block)
        self.assertNotIn("| 报告期 |", block)

    def test_fetch_disabled_flag(self) -> None:
        block = build_financials_block("x", "x", [], fetch_disabled=True)
        self.assertIn("已被 FINANCE_FINANCIALS_FETCH=0 关闭", block)

    def test_none_fields_render_gap_marker(self) -> None:
        rows = [QuarterFinancials("2026一季报", "2026-03-31", None, None, None, None, None, None)]
        block = build_financials_block("空数据", "000002.SZ", rows)
        self.assertIn("| 缺 |", block)

    def test_block_for_target_uses_injected_fetcher(self) -> None:
        captured: dict[str, object] = {}

        def fake_fetch(ts_code: str, name: str, periods: int) -> list[QuarterFinancials]:
            captured["ts_code"] = ts_code
            captured["periods"] = periods
            return self._rows()

        block = financials_block_for_target("300454.SZ", "深信服", periods=4, fetcher=fake_fetch)
        self.assertEqual(captured["ts_code"], "300454.SZ")
        self.assertEqual(captured["periods"], 4)
        self.assertIn("2026一季报", block)

    def test_fallback_used_when_primary_empty(self) -> None:
        def empty_fetch(ts_code: str, name: str, periods: int) -> list[QuarterFinancials]:
            return []

        def fallback_fetch(ts_code: str, name: str, periods: int) -> list[QuarterFinancials]:
            return self._rows()

        block = financials_block_for_target(
            "300454.SZ", "深信服", fetcher=empty_fetch, fallback_fetcher=fallback_fetch
        )
        self.assertIn("AKShare·新浪财务摘要", block)
        self.assertIn("2026一季报", block)

    def test_both_sources_empty_declare_dual_gap(self) -> None:
        def empty_fetch(ts_code: str, name: str, periods: int) -> list[QuarterFinancials]:
            return []

        block = financials_block_for_target(
            "300454.SZ", "深信服", fetcher=empty_fetch, fallback_fetcher=empty_fetch
        )
        self.assertIn("东财 F10 与 AKShare(新浪财务摘要) 均未取到", block)

    def test_primary_success_keeps_eastmoney_source(self) -> None:
        block = financials_block_for_target(
            "300454.SZ", "深信服", fetcher=lambda *a: self._rows()
        )
        self.assertIn("东财 F10 主要财务指标", block)
        self.assertNotIn("AKShare", block)


if __name__ == "__main__":
    unittest.main()
