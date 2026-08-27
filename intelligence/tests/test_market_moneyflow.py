from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from intelligence.services.market_moneyflow import (
    load_moneyflow_snapshot,
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

    def test_snapshot_is_structured_and_deduplicates_cross_scan_stocks(self) -> None:
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            self._make_db(db)
            con = duckdb.connect(str(db))
            con.execute(
                "insert into feature_l2_capital_flow_daily values "
                "('2026-07-08','top100','300454','300454.XSHE','深信服',11000,14000,300,0.50,9.9,500,4,null,'l2',now())"
            )
            con.close()

            snapshot = load_moneyflow_snapshot(db, as_of_date="2026-07-08")

            self.assertEqual(snapshot.status, "ok")
            self.assertEqual(snapshot.trade_date, "2026-07-08")
            self.assertEqual([row.stock_name for row in snapshot.leaders].count("深信服"), 1)
            self.assertEqual(snapshot.coverage, {"limitup": 1, "top100": 2})
            self.assertEqual(snapshot.quant_orders[0].stock_name, "深信服")

    def test_snapshot_uses_last_available_day_and_marks_stale(self) -> None:
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            self._make_db(db)

            snapshot = load_moneyflow_snapshot(db, as_of_date="2026-07-10")

            self.assertEqual(snapshot.status, "stale")
            self.assertEqual(snapshot.trade_date, "2026-07-08")
            self.assertIn("早于报告日", snapshot.warnings[0])

    def test_disclosures_never_enter_the_degrade_channel(self) -> None:
        """恒定口径说明不得混进 warnings —— app.py 在 status != "ok" 时把 warnings
        逐条写进 run.degrades，而 acceptance.py 是「degrades 非空即判降级」。

        混在一起时，一次 L2 日期偏移会产生 3 条降级记录，其中只有 1 条是真降级，
        另 2 条是每次都出现的口径说明——降级归因就是这样被稀释的。
        """
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            self._make_db(db)

            fresh = load_moneyflow_snapshot(db, as_of_date="2026-07-08")
            stale = load_moneyflow_snapshot(db, as_of_date="2026-07-10")

            # 口径说明恒定存在，与本轮成败无关
            self.assertEqual(fresh.disclosures, stale.disclosures)
            self.assertTrue(any("缺行不等于无资金流入" in d for d in fresh.disclosures))
            self.assertTrue(any("不等同于问财" in d for d in fresh.disclosures))

            # 成功时不该有任何 warning；失败时只有那一条真降级
            self.assertEqual(fresh.warnings, ())
            self.assertEqual(len(stale.warnings), 1)
            for text in stale.disclosures:
                self.assertNotIn(text, stale.warnings)

    def test_llm_block_respects_as_of_date(self) -> None:
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            self._make_db(db)

            block = moneyflow_block_for_llm(
                "大单资金流",
                None,
                db,
                as_of_date="2026-07-07",
            )

            self.assertIn("最新扫描日 2026-07-07", block)
            self.assertNotIn("京东方", block)

    # ---- 时点限定（2026-08-26 blk-d9 实测：块尾口径行会被合成层丢弃，----
    # ---- 19 天前榜单被写成「当日榜单」。限定语必须排在被限定内容之前。----

    def test_llm_block_stale_qualifier_leads_when_as_of_is_later(self) -> None:
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            self._make_db(db)

            block = moneyflow_block_for_llm(
                "大单资金流", None, db, as_of_date="2026-07-20"
            )

            self.assertIn("时点限定（先读）", block)
            self.assertIn("最新扫描日 2026-07-08 早于盘面日期 2026-07-20", block)
            self.assertIn("不是当日榜单", block)
            self.assertIn("（2026-07-08，非当日）大单净流入榜", block)
            # 限定行必须先于口径行（合成层截断时先活下来的是限定语）
            self.assertLess(block.index("时点限定（先读）"), block.index("- 口径："))

    def test_llm_block_fresh_has_no_stale_qualifier(self) -> None:
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            self._make_db(db)

            block = moneyflow_block_for_llm(
                "大单资金流", None, db, as_of_date="2026-07-08"
            )

            self.assertNotIn("时点限定", block)
            self.assertNotIn("非当日", block)

    def test_llm_block_derives_reference_day_from_market_daily(self) -> None:
        """无日期问题（as_of=None）——最常见问法——参照日回退库内最新交易日。"""
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            self._make_db(db)
            con = duckdb.connect(str(db))
            con.execute("create table fact_market_daily (trade_date date, note varchar)")
            con.execute(
                "insert into fact_market_daily values ('2026-07-10','x'),('2026-07-09','x')"
            )
            con.close()

            block = moneyflow_block_for_llm("大单资金流", None, db)

            self.assertIn("最新扫描日 2026-07-08 早于盘面日期 2026-07-10", block)

    def test_llm_block_without_reference_day_keeps_old_behavior(self) -> None:
        """fixture 无 fact_market_daily 且未传 as_of：拿不到参照日就不发无据警告。"""
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            self._make_db(db)

            block = moneyflow_block_for_llm("大单资金流", None, db)

            self.assertIn("[D9]", block)
            self.assertNotIn("时点限定", block)


if __name__ == "__main__":
    unittest.main()
