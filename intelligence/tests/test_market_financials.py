from __future__ import annotations

import sys
import unittest

from intelligence.services.market_financials import (
    QuarterFinancials,
    _parse_sina_lrb_rows,
    _secucode,
    akshare_available,
    build_financials_block,
    enrich_quality_fields,
    fetch_quarterly_financials_chain,
    financials_block_for_target,
    parse_financials_intent,
    profit_quality_watch,
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


class FallbackAttemptedDisclosureTests(unittest.TestCase):
    """备源没跑过时，缺口文案不得声称「两源均未取到」。

    2026-08-10 实测：akshare 在 .venv-workbench 里从未安装，而
    ``fetch_quarterly_financials_akshare`` 的 ``except Exception`` 把 ImportError
    和网络失败压成同一个 ``[]``。于是那句「东财 F10 与 AKShare 均未取到」对
    **每一次**财报缺口都成立地撒谎——声称试过两个源，实际只试了一个。

    危害不在文案本身：它把「备源不可用」这个基础设施事实，伪装成「这家公司查不到
    财报」这个数据事实。仪表显示备源已尝试，于是没人会去修备源。
    """

    def test_uninstalled_fallback_is_disclosed_as_not_attempted(self) -> None:
        block = build_financials_block(
            "某公司", "000001.SZ", [], fallback_attempted=False
        )
        self.assertIn("未安装，本次未尝试", block)
        # 关键反向断言：不得再谎称两源都试过。
        self.assertNotIn("均未取到", block)
        # 必须说清这是环境问题，否则读者会当成该公司无数据。
        self.assertIn("非该公司无数据", block)

    def test_attempted_fallback_keeps_dual_source_wording(self) -> None:
        """备源真跑过时保留原文案——修复不是把话一律改弱。"""

        block = build_financials_block(
            "某公司", "000001.SZ", [], fallback_attempted=True
        )
        self.assertIn("东财 F10 与 AKShare(新浪财务摘要) 均未取到", block)
        self.assertNotIn("未尝试", block)

    def test_injected_fallback_counts_as_attempted(self) -> None:
        """显式注入 fallback_fetcher ⇒ 备源确实执行过，按「已尝试」措辞。

        这条钉住 ``financials_block_for_target`` 的传递：判据是「这次有没有真的
        调用备源」，不是「akshare 装没装」。注入假 fetcher 的调用方（含既有测试）
        行为不得被这次修复改变。
        """

        block = financials_block_for_target(
            "300454.SZ",
            "深信服",
            fetcher=lambda *a: [],
            fallback_fetcher=lambda *a: [],
        )
        self.assertIn("均未取到", block)
        self.assertNotIn("未尝试", block)

    def test_availability_probe_does_not_import(self) -> None:
        """``akshare_available`` 只查 spec，不 import——import 会拖进整棵依赖树。

        它必须在 akshare 缺失时正常返回 False 而不抛异常，因为缺口路径要靠它
        选文案；这个探针自己崩掉会让整个 D7 块失败。
        """

        self.assertIsInstance(akshare_available(), bool)
        self.assertNotIn("akshare", sys.modules)


class ProviderChainTests(unittest.TestCase):
    def _rows(self) -> list[QuarterFinancials]:
        return [
            QuarterFinancials("2026一季报", "2026-03-31", 16.27, 28.9, -0.65, 74.2, 60.3, -3.97),
        ]

    def test_unplugged_primary_walks_to_sina(self) -> None:
        result = fetch_quarterly_financials_chain(
            "300454.SZ",
            "深信服",
            today="2026-08-18",
            primary=lambda *a, **k: [],
            secondary=lambda *a, **k: self._rows(),
            tertiary=lambda *a, **k: [],
        )
        self.assertEqual(result.status, "degraded")
        self.assertEqual(result.provider, "新浪利润表")
        self.assertEqual(result.as_of, "2026-08-18")
        self.assertEqual(result.attempted, ("东财 F10", "新浪利润表"))
        self.assertEqual(result.rows[0].revenue_yi, 16.27)

    def test_primary_http_402_walks_to_sina(self) -> None:
        import urllib.error

        def boom(*a, **k):
            raise urllib.error.HTTPError(
                "https://example.test/f10",
                402,
                "Payment Required",
                hdrs={},
                fp=None,
            )

        result = fetch_quarterly_financials_chain(
            "300454.SZ",
            today="2026-08-18",
            primary=boom,
            secondary=lambda *a, **k: self._rows(),
            tertiary=lambda *a, **k: [],
        )
        self.assertEqual(result.status, "degraded")
        self.assertEqual(result.provider, "新浪利润表")
        self.assertTrue(any("402" in note for note in result.notes))

    def test_all_sources_empty_is_no_data_not_query_failed(self) -> None:
        result = fetch_quarterly_financials_chain(
            "300454.SZ",
            today="2026-08-18",
            primary=lambda *a, **k: [],
            secondary=lambda *a, **k: [],
            tertiary=lambda *a, **k: [],
            tertiary_available=True,
        )
        self.assertEqual(result.status, "NO_DATA")
        self.assertEqual(result.rows, ())
        block = financials_block_for_target(
            "300454.SZ",
            "深信服",
            chain=lambda *a, **k: result,
        )
        self.assertIn("状态=NO_DATA", block)
        self.assertNotIn("查询失败", block)
        self.assertIn("东财 F10", block)
        self.assertIn("新浪利润表", block)

    def test_uninstalled_tertiary_is_missing_config(self) -> None:
        result = fetch_quarterly_financials_chain(
            "300454.SZ",
            today="2026-08-18",
            primary=lambda *a, **k: [],
            secondary=lambda *a, **k: [],
            tertiary=lambda *a, **k: [],
            tertiary_available=False,
        )
        self.assertEqual(result.status, "missing_config")
        block = financials_block_for_target(
            "300454.SZ",
            "深信服",
            chain=lambda *a, **k: result,
        )
        self.assertIn("missing_config", block)
        self.assertIn("未尝试", block)
        self.assertNotIn("查询失败", block)

    def test_block_cites_provider_and_as_of(self) -> None:
        result = fetch_quarterly_financials_chain(
            "300454.SZ",
            today="2026-08-18",
            primary=lambda *a, **k: self._rows(),
            secondary=lambda *a, **k: [],
            tertiary=lambda *a, **k: [],
        )
        self.assertEqual(result.status, "ok")
        block = financials_block_for_target(
            "300454.SZ",
            "深信服",
            chain=lambda *a, **k: result,
        )
        self.assertIn("东财 F10", block)
        self.assertIn("取数日=2026-08-18", block)
        self.assertIn("provider=东财 F10", block)

    def test_sina_lrb_maps_income_line_items(self) -> None:
        rows = _parse_sina_lrb_rows(
            {
                "20260331": {
                    "data": [
                        {"item_title": "营业总收入", "item_value": "1627000000", "item_tongbi": "28.9"},
                        {
                            "item_title": "归属于母公司股东的净利润",
                            "item_value": "-65000000",
                            "item_tongbi": "-3.97",
                        },
                        {"item_title": "销售毛利率", "item_value": "60.3"},
                    ]
                }
            },
            periods=6,
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].report_name, "2026一季报")
        self.assertEqual(rows[0].revenue_yi, 16.27)
        self.assertEqual(rows[0].revenue_yoy, 28.9)
        self.assertEqual(rows[0].netprofit_yi, -0.65)
        self.assertEqual(rows[0].gross_margin, 60.3)


class ProfitQualityWatchTests(unittest.TestCase):
    def test_margin_up_ocf_down_triggers(self) -> None:
        rows = [
            QuarterFinancials(
                "2026一季报", "2026-03-31", gross_margin=21.0, ocf_yi=-25.7
            ),
            QuarterFinancials(
                "2025一季报", "2025-03-31", gross_margin=16.46, ocf_yi=-3.94
            ),
        ]
        line = profit_quality_watch(rows)
        self.assertIsNotNone(line)
        assert line is not None
        self.assertIn("利润质量待核", line)
        self.assertIn("16.46", line)
        self.assertIn("21.0", line)
        self.assertIn("-3.94", line)
        self.assertIn("-25.7", line)
        self.assertIn("改善", line)
        self.assertIn("反向", line)
        self.assertIn("不下结论", line)

    def test_both_improve_does_not_trigger(self) -> None:
        rows = [
            QuarterFinancials(
                "2026一季报", "2026-03-31", gross_margin=21.0, ocf_yi=2.0
            ),
            QuarterFinancials(
                "2025一季报", "2025-03-31", gross_margin=16.46, ocf_yi=1.0
            ),
        ]
        self.assertIsNone(profit_quality_watch(rows))

    def test_adjacent_different_period_is_not_yoy_peer(self) -> None:
        rows = [
            QuarterFinancials(
                "2026一季报", "2026-03-31", gross_margin=21.0, ocf_yi=-25.7
            ),
            QuarterFinancials(
                "2025年报", "2025-12-31", gross_margin=17.9, ocf_yi=29.71
            ),
        ]
        self.assertIsNone(profit_quality_watch(rows))


class XiamenTungstenReplayTests(unittest.TestCase):
    """厦钨 2026Q1 实数回放。来源：新浪三表 + 东财 F10 / RPT_HOLDERNUMLATEST，取数日 2026-08-18。"""

    def _rows(self) -> list[QuarterFinancials]:
        return [
            QuarterFinancials(
                "2026一季报",
                "2026-03-31",
                revenue_yi=157.43,
                netprofit_yi=11.07,
                gross_margin=21.0,
                ocf_yi=-25.7,
                contract_liability_yi=7.28,
                inventory_yi=197.31,
                holder_num=161907,
                holder_change_pct=67.94,
            ),
            QuarterFinancials(
                "2025一季报",
                "2025-03-31",
                revenue_yi=84.19,
                netprofit_yi=3.83,
                gross_margin=16.46,
                ocf_yi=-3.94,
                contract_liability_yi=5.63,
                inventory_yi=90.03,
            ),
        ]

    def test_replay_same_direction_as_knevo(self) -> None:
        block = build_financials_block("厦门钨业", "600549.SH", self._rows())
        self.assertIn("经营现金流", block)
        self.assertIn("合同负债", block)
        self.assertIn("存货", block)
        self.assertIn("股东户数", block)
        self.assertIn("161907", block)
        self.assertIn("67.94", block)
        self.assertIn("利润质量待核", block)
        self.assertIn("改善", block)
        self.assertIn("反向", block)
        self.assertNotIn("查询失败", block)

    def test_enrich_merges_sina_and_holders(self) -> None:
        base = [
            QuarterFinancials("2026一季报", "2026-03-31", revenue_yi=157.43, gross_margin=21.0),
            QuarterFinancials("2025一季报", "2025-03-31", revenue_yi=84.19, gross_margin=16.46),
        ]
        enriched = enrich_quality_fields(
            "600549.SH",
            base,
            llb={
                "2026-03-31": {"ocf_yi": -25.7},
                "2025-03-31": {"ocf_yi": -3.94},
            },
            fzb={
                "2026-03-31": {"contract_liability_yi": 7.28, "inventory_yi": 197.31},
                "2025-03-31": {"contract_liability_yi": 5.63, "inventory_yi": 90.03},
            },
            holders={"2026-03-31": (161907, 67.94)},
        )
        self.assertEqual(enriched[0].ocf_yi, -25.7)
        self.assertEqual(enriched[0].inventory_yi, 197.31)
        self.assertEqual(enriched[0].holder_num, 161907)
        self.assertIn("利润质量待核", profit_quality_watch(enriched) or "")


if __name__ == "__main__":
    unittest.main()
