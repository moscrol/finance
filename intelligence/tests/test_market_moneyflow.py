from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from intelligence.services.market_moneyflow import (
    moneyflow_block_for_llm,
    parse_moneyflow_intent,
)

try:
    import duckdb
except Exception:  # pragma: no cover
    duckdb = None


class ParseMoneyflowIntentTests(unittest.TestCase):
    def test_moneyflow_terms_route(self) -> None:
        self.assertTrue(parse_moneyflow_intent("深信服的大单资金流怎么样"))
        self.assertTrue(parse_moneyflow_intent("主买净额前排是谁"))
        self.assertTrue(parse_moneyflow_intent("有没有量化单在接力"))

    def test_plain_questions_do_not_route(self) -> None:
        self.assertFalse(parse_moneyflow_intent("信创板块今天怎么样"))
        self.assertFalse(parse_moneyflow_intent("深信服的毛利率"))
        self.assertFalse(parse_moneyflow_intent(""))


@unittest.skipIf(duckdb is None, "duckdb 不可用")
class MoneyflowBlockTests(unittest.TestCase):
    def _make_db(self, path: Path) -> None:
        con = duckdb.connect(str(path))
        con.execute(
            """
            create table feature_l2_capital_flow_daily (
                trade_date date, scan_type varchar, stock_code varchar, stock_ts_code varchar,
                stock_name varchar, main_buy_net_wan double, total_buy_net_wan double,
                float_mktcap_yi double, score double, pct_change double,
                big_order_threshold_wan double, rank integer, prev_limitup_date date,
                source varchar, calculated_at timestamp
            )
            """
        )
        con.execute(
            """
            create table feature_l2_quant_orders_daily (
                trade_date date, stock_code varchar, stock_ts_code varchar, stock_name varchar,
                quant_amount_wan double, quant_pct_of_big_buy double, cluster_count integer,
                order_count integer, biggest_cluster varchar, pct_change double,
                quant_threshold_wan double, big_order_threshold_wan double, rank integer,
                source varchar, calculated_at timestamp
            )
            """
        )
        con.execute(
            "insert into feature_l2_capital_flow_daily values "
            "('2026-07-08','limitup','300454','300454.XSHE','深信服',12000,15000,300,0.55,9.9,500,1,'2026-07-07','l2',now()),"
            "('2026-07-08','top100','000725','000725.XSHE','京东方Ａ',8000,9000,1500,0.06,3.1,800,2,null,'l2',now()),"
            "('2026-07-07','limitup','300454','300454.XSHE','深信服',6000,7000,300,0.30,5.0,500,3,'2026-07-04','l2',now())"
        )
        con.execute(
            "insert into feature_l2_quant_orders_daily values "
            "('2026-07-08','300454','300454.XSHE','深信服',4600,38.0,3,55,'849-857万x55笔=46695万',9.9,200,500,1,'l2',now())"
        )
        con.close()

    def test_stock_block_renders(self) -> None:
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            self._make_db(db)
            block = moneyflow_block_for_llm("深信服的大单资金流", None, db)
            self.assertIn("[D9]", block)
            self.assertIn("深信服", block)
            self.assertIn("量化单总额", block)
            self.assertIn("大单净流入榜", block)
            self.assertIn("使用要求", block)

    def test_uncovered_stock_declares_gap(self) -> None:
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            self._make_db(db)
            block = moneyflow_block_for_llm("大单资金流", "瑞华泰", db)
            # 瑞华泰不在特征表 -> 不能声称无资金流入，但榜单视角仍应渲染
            self.assertIn("大单净流入榜", block)
            self.assertNotIn("瑞华泰 近", block)

    def test_missing_db_returns_empty(self) -> None:
        self.assertEqual(
            moneyflow_block_for_llm("大单资金流", None, "/nonexistent/x.duckdb"), ""
        )

    def test_missing_table_returns_empty(self) -> None:
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            duckdb.connect(str(db)).close()
            self.assertEqual(moneyflow_block_for_llm("大单资金流", None, db), "")


if __name__ == "__main__":
    unittest.main()
