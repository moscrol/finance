from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from intelligence.services.market_capital import (
    BlockTradeRow,
    MarginRow,
    UnlockRow,
    capital_block_for_llm,
    parse_capital_intent,
    parse_capital_slices,
)

try:
    import duckdb
except Exception:  # pragma: no cover
    duckdb = None


class ParseCapitalIntentTests(unittest.TestCase):
    def test_three_intents_route(self) -> None:
        self.assertEqual(parse_capital_slices("贵州茅台两融余额"), frozenset({"margin"}))
        self.assertEqual(parse_capital_slices("茅台大宗交易"), frozenset({"block"}))
        self.assertEqual(parse_capital_slices("中船科技未来解禁"), frozenset({"unlock"}))
        self.assertTrue(parse_capital_intent("融资盘重不重"))
        self.assertTrue(parse_capital_intent("限售解禁时间表"))

    def test_negative_samples_do_not_route(self) -> None:
        self.assertFalse(parse_capital_intent("今天信创板块盘面怎么样"))
        self.assertFalse(parse_capital_intent("深信服近几个季度毛利率"))
        self.assertFalse(parse_capital_intent("深信服的大单资金流怎么样"))
        self.assertFalse(parse_capital_intent("深信服龙虎榜席位"))
        self.assertFalse(parse_capital_intent(""))


@unittest.skipIf(duckdb is None, "duckdb 不可用")
class CapitalBlockTests(unittest.TestCase):
    def _make_db(self, path: Path) -> None:
        con = duckdb.connect(str(path))
        con.execute(
            "create table fact_stock_daily (trade_date date, stock_ts_code varchar, stock_name varchar)"
        )
        con.execute(
            "insert into fact_stock_daily values "
            "('2026-08-14','600519.SH','贵州茅台'),"
            "('2026-08-14','600072.SH','中船科技')"
        )
        con.close()

    def test_maotai_margin_matches_eastmoney(self) -> None:
        # 东财 RPTA_WEB_RZRQ_GGMX 600519，取数日 2026-08-18：2026-08-14
        # RZYE=17671699929  RZ MRE=358442397  RQYE=123072560.91
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            self._make_db(db)
            block = capital_block_for_llm(
                "贵州茅台两融",
                db,
                as_of="2026-08-18",
                margin_fetcher=lambda *a, **k: [
                    MarginRow("2026-08-14", 176.72, 3.58, 1.23),
                ],
                block_fetcher=lambda *a, **k: [],
                unlock_fetcher=lambda *a, **k: [],
            )
            self.assertIn("[D12]", block)
            self.assertIn("贵州茅台", block)
            self.assertIn("176.72", block)
            self.assertIn("3.58", block)
            self.assertIn("1.23", block)
            self.assertIn("2026-08-14", block)
            self.assertIn("口径", block)
            self.assertNotIn("大宗交易", block)
            self.assertNotIn("查询失败", block)

    def test_maotai_block_trade_matches_eastmoney(self) -> None:
        # 东财 RPT_DATA_BLOCKTRADE 600519，取数日 2026-08-18：2026-08-03
        # DEAL_PRICE=1358.98 CLOSE=1358.98 DEAL_AMT=20112900
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            self._make_db(db)
            block = capital_block_for_llm(
                "贵州茅台大宗",
                db,
                as_of="2026-08-18",
                margin_fetcher=lambda *a, **k: [],
                block_fetcher=lambda *a, **k: [
                    BlockTradeRow(
                        "2026-08-03",
                        1358.98,
                        0.0,
                        2011.29,
                        "中信证券股份有限公司总部(非营业场所)",
                        "广发证券股份有限公司昆明东风东路证券营业部",
                    ),
                ],
                unlock_fetcher=lambda *a, **k: [],
            )
            self.assertIn("1358.98", block)
            self.assertIn("中信证券", block)
            self.assertIn("2011.29", block)
            self.assertNotIn("融资余额", block)

    def test_cssc_unlock_matches_eastmoney(self) -> None:
        # 东财 RPT_LIFT_STAGE 600072，取数日 2026-08-18：FREE_DATE=2026-08-18
        # 定向增发机构配售股份 CURRENT_FREE_SHARES=22999.1878 FREE_RATIO=0.212299414599
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            self._make_db(db)
            block = capital_block_for_llm(
                "中船科技解禁",
                db,
                as_of="2026-08-18",
                margin_fetcher=lambda *a, **k: [],
                block_fetcher=lambda *a, **k: [],
                unlock_fetcher=lambda *a, **k: [
                    UnlockRow("2026-08-18", "定向增发机构配售股份", 22999.19, 21.23),
                ],
            )
            self.assertIn("2026-08-18", block)
            self.assertIn("定向增发机构配售股份", block)
            self.assertIn("22999.19", block)
            self.assertIn("21.23", block)
            self.assertIn("未来 90 天", block)

    def test_unlock_empty_window_declares_none(self) -> None:
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            self._make_db(db)
            block = capital_block_for_llm(
                "贵州茅台解禁",
                db,
                as_of="2026-08-18",
                margin_fetcher=lambda *a, **k: [],
                block_fetcher=lambda *a, **k: [],
                unlock_fetcher=lambda *a, **k: [],
            )
            self.assertIn("未来 90 天无待解禁", block)
            self.assertIn("[D12]", block)

    def test_no_stock_returns_empty(self) -> None:
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            self._make_db(db)
            self.assertEqual(
                capital_block_for_llm("今天两融怎么样", db, as_of="2026-08-18"),
                "",
            )


if __name__ == "__main__":
    unittest.main()
