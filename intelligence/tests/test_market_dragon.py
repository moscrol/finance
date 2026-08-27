from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from intelligence.services.market_dragon import (
    dragon_block_for_llm,
    parse_dragon_intent,
)

try:
    import duckdb
except Exception:  # pragma: no cover
    duckdb = None


class ParseDragonIntentTests(unittest.TestCase):
    def test_dragon_terms_route(self) -> None:
        self.assertTrue(parse_dragon_intent("深信服龙虎榜席位怎么拆"))
        self.assertTrue(parse_dragon_intent("网宿科技有没有游资"))
        self.assertTrue(parse_dragon_intent("300017 机构专用席位"))

    def test_negative_samples_do_not_route(self) -> None:
        self.assertFalse(parse_dragon_intent("今天信创板块盘面怎么样"))
        self.assertFalse(parse_dragon_intent("深信服近几个季度毛利率"))
        self.assertFalse(parse_dragon_intent("深信服的大单资金流怎么样"))
        self.assertFalse(parse_dragon_intent(""))


@unittest.skipIf(duckdb is None, "duckdb 不可用")
class DragonBlockTests(unittest.TestCase):
    def _make_db(self, path: Path) -> None:
        con = duckdb.connect(str(path))
        con.execute(
            """
            create table fact_stock_daily (
                trade_date date, stock_ts_code varchar, stock_name varchar
            )
            """
        )
        con.execute(
            """
            create table fact_dragon_tiger_daily (
                trade_date date, stock_ts_code varchar, stock_name varchar,
                close double, pct_change double, turnover_rate double, amount double,
                l_buy double, l_sell double, l_amount double, net_amount double,
                net_rate double, amount_rate double, reason varchar,
                source varchar, updated_at timestamp
            )
            """
        )
        con.execute(
            """
            create table fact_dragon_seat_daily (
                trade_date date, stock_ts_code varchar, stock_name varchar,
                side varchar, seat_no integer, exalter varchar, seat_type varchar,
                hm_name varchar, buy double, sell double, buy_rate double,
                sell_rate double, net_buy double, source varchar, updated_at timestamp
            )
            """
        )
        con.execute(
            "insert into fact_stock_daily values "
            "('2026-08-14','300017.SZ','网宿科技'),"
            "('2026-08-14','300454.SZ','深信服')"
        )
        # 网宿科技 2026-08-14：本地 DuckDB 一手，取数日 2026-08-18。
        # 东财同日页：理由「日涨幅达到15%的前5只证券」、BILLBOARD_NET_AMT=9.72亿；
        # 买卖席位与库重叠（深股通/紫阳东路/江苏路/机构专用/华泰南京/东方呼和浩特）。
        # 库少 1 条买方机构专用（东财 1.89亿），块内须声明以本地库为准。
        con.execute(
            "insert into fact_dragon_tiger_daily values "
            "('2026-08-14','300017.SZ','网宿科技',17.33,20.01,20.3,76.62,"
            "13.79,4.07,17.86,9.72,12.68,23.3,'日涨幅达到15%的前5只证券',"
            "'fupanhui:public-api/data/dragon/list',now())"
        )
        con.executemany(
            "insert into fact_dragon_seat_daily values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [
                ("2026-08-14", "300017.SZ", "网宿科技", "buy", 1, "深股通专用", "游资",
                 "深股通专用", 6.72, 1.71, None, None, 5.01, "s", None),
                ("2026-08-14", "300017.SZ", "网宿科技", "buy", 2,
                 "国泰海通证券股份有限公司武汉紫阳东路证券营业部", "游资",
                 "紫阳东路", 2.08, 0.01, None, None, 2.07, "s", None),
                ("2026-08-14", "300017.SZ", "网宿科技", "buy", 3,
                 "国泰海通证券股份有限公司上海长宁区江苏路证券营业部", "营业部",
                 None, 1.65, 0.08, None, None, 1.57, "s", None),
                ("2026-08-14", "300017.SZ", "网宿科技", "buy", 4, "机构专用", "机构",
                 None, 1.4, 0.92, None, None, 0.48, "s", None),
                ("2026-08-14", "300017.SZ", "网宿科技", "sell", 1, "深股通专用", "游资",
                 "深股通专用", 6.72, 1.71, None, None, 5.01, "s", None),
                ("2026-08-14", "300017.SZ", "网宿科技", "sell", 2, "机构专用", "机构",
                 None, 1.89, 0.53, None, None, 1.36, "s", None),
                ("2026-08-14", "300017.SZ", "网宿科技", "sell", 3,
                 "华泰证券股份有限公司南京分公司", "营业部",
                 None, 0.05, 0.39, None, None, -0.34, "s", None),
                ("2026-08-14", "300017.SZ", "网宿科技", "sell", 4,
                 "东方证券股份有限公司呼和浩特乌兰察布东街证券营业部", "营业部",
                 None, 0.0, 0.42, None, None, -0.42, "s", None),
            ],
        )
        con.close()

    def test_wangsu_replay_matches_eastmoney_overlap(self) -> None:
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            self._make_db(db)
            block = dragon_block_for_llm("网宿科技龙虎榜席位", db)
            self.assertIn("[D13]", block)
            self.assertIn("网宿科技", block)
            self.assertIn("300017.SZ", block)
            self.assertIn("2026-08-14", block)
            self.assertIn("日涨幅达到15%的前5只证券", block)
            self.assertIn("9.72", block)
            self.assertIn("深股通专用", block)
            self.assertIn("紫阳东路", block)
            self.assertIn("机构专用", block)
            self.assertIn("游资", block)
            self.assertIn("机构", block)
            self.assertIn("营业部", block)
            self.assertIn("口径", block)
            self.assertIn("本地库为准", block)
            self.assertIn("不构成跟单", block)
            self.assertNotIn("跟单建议", block)
            self.assertNotIn("查询失败", block)

    def test_unlisted_stock_declares_gap(self) -> None:
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            self._make_db(db)
            block = dragon_block_for_llm("深信服龙虎榜", db)
            self.assertIn("[D13]", block)
            self.assertIn("深信服", block)
            self.assertIn("未上榜", block)
            self.assertIn("不构成跟单", block)
            self.assertNotIn("跟单建议", block)

    def test_no_stock_returns_empty(self) -> None:
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            self._make_db(db)
            self.assertEqual(dragon_block_for_llm("今天游资怎么样", db), "")


if __name__ == "__main__":
    unittest.main()
