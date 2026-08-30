"""D8 / D11 的 as_of 截断：**解析器和取数必须一起截**。

背景（R-20260830-01）：D10 早就有 ``as_of``，D8 / D11 没有，所以 Engine A 的开场
预取只能给这两块写 gap。补参数时最容易漏的不是历史查询，是**解析器**——
``_resolve_stock`` 的股票名录钉在 ``max(trade_date)``、``resolve_query_themes``
的题材名录扫全表，两者都是**数据自己派生的基准**。只截历史、不截名录时：

- 块头写的股票名来自库尾那天的宇宙，窗口却截到 as_of，两个日期不是同一天；
- 截止日当时还不存在的题材/个股照样被解析出来。

而且这两种漏都**整块自洽**，「有没有出块」「有没有 [D8] 标记」类断言一条都照不出来。
所以本文件的断言形状固定为两种：**(1) 块里不许出现晚于 as_of 的日期**、
**(2) 截止日当时不存在的主体必须解析不到**。两条都对「只截历史」这个变异敏感。

``as_of=None``（引擎 B 侧调用）的行为不在本文件测——那是 ``test_market_analogs`` /
``test_stock_analogs`` 既有用例的职责，它们全部不传 as_of，就是 B 侧的回归。
"""

from __future__ import annotations

import re
import unittest
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from intelligence.services.market_analogs import analog_block_for_llm
from intelligence.services.stock_analogs import (
    load_stock_analog_artifact,
    stock_analog_block_for_llm,
)
import intelligence.tests.test_market_analogs as _mma
import intelligence.tests.test_stock_analogs as _msa

try:
    import duckdb
except Exception:  # pragma: no cover
    duckdb = None

_ISO_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _max_date_in(block: str) -> str | None:
    """块里出现的最大 ISO 日期。窗口起止日就是渲染出来的，不必解析结构。"""
    hits = _ISO_RE.findall(block or "")
    return max(hits) if hits else None


@unittest.skipIf(duckdb is None, "duckdb 不可用")
class StockAnalogAsOfTests(unittest.TestCase):
    """D11：``_resolve_stock`` 与历史查询同截。"""

    def _make_db(self, path: Path) -> None:
        """复用 test_stock_analogs 的建表 SQL，再补一只「库尾才上市」的股。

        不另写一份 DDL：同一张表两份建表语句会各自漂移，而漂的时候没人知道。
        """
        _msa._make_db(path, n=200)
        con = duckdb.connect(str(path))
        base = date(2025, 1, 1)
        for i in range(150, 200):
            con.execute(
                "insert into fact_stock_daily values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    base + timedelta(days=i),
                    "300999.SZ",
                    "库尾新股",
                    10.0,
                    10.0,
                    3.0,
                    5.0,
                    2.0,
                    "t",
                    None,
                ],
            )
        con.close()

    def test_block_never_shows_dates_after_as_of(self) -> None:
        """取数截断：块内最大日期不得越过 as_of。"""
        cut = (date(2025, 1, 1) + timedelta(days=120)).isoformat()
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            self._make_db(db)
            block = stock_analog_block_for_llm(
                "英维克这段走势历史上有类似的吗", db, as_of=cut
            )
        self.assertIn("[D11]", block)
        latest = _max_date_in(block)
        self.assertIsNotNone(latest)
        self.assertLessEqual(latest, cut)

    def test_two_as_of_give_different_blocks(self) -> None:
        """同题不同 as_of 必须给出不同的块；相同即说明 as_of 被忽略。"""
        early = (date(2025, 1, 1) + timedelta(days=120)).isoformat()
        late = (date(2025, 1, 1) + timedelta(days=199)).isoformat()
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            self._make_db(db)
            q = "英维克这段走势历史上有类似的吗"
            block_early = stock_analog_block_for_llm(q, db, as_of=early)
            block_late = stock_analog_block_for_llm(q, db, as_of=late)
        self.assertIn("[D11]", block_early)
        self.assertIn("[D11]", block_late)
        self.assertNotEqual(block_early, block_late)

    def test_stock_not_yet_listed_at_as_of_does_not_resolve(self) -> None:
        """解析器截断：截止日当时还没上市的股，不得被名录解析出来。

        这条对「只截历史查询、不截 ``_resolve_stock``」的变异敏感：漏截时
        ``stock_code`` 会被填上，块照常渲染（只是内容退化成数据缺口行），
        断言「出没出块」永远发现不了。
        """
        cut = (date(2025, 1, 1) + timedelta(days=120)).isoformat()
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            self._make_db(db)
            q = "库尾新股 历史上有类似的走势吗"
            truncated = load_stock_analog_artifact(q, db, as_of=cut)
            untruncated = load_stock_analog_artifact(q, db)
            block = stock_analog_block_for_llm(q, db, as_of=cut)
        self.assertIsNone(truncated.stock_code)
        self.assertEqual(block, "")
        # 反向对照：不截断时它是解析得到的，证明上面那条不是「这只股压根查不到」。
        self.assertEqual(untruncated.stock_code, "300999.SZ")


@unittest.skipIf(duckdb is None, "duckdb 不可用")
class ThemeAnalogAsOfTests(unittest.TestCase):
    """D8：``resolve_query_themes`` 与历史查询同截。"""

    def _make_db(self, path: Path) -> None:
        _mma.AnalogBlockTests._make_db(None, path, n=200)
        con = duckdb.connect(str(path))
        base = date(2025, 1, 1)
        for i in range(150, 200):
            con.execute(
                "insert into fact_sector_daily values (?, '库尾题材', ?, ?, ?)",
                [base + timedelta(days=i), 2.5, 15.0, 900.0],
            )
        con.close()

    def test_block_never_shows_dates_after_as_of(self) -> None:
        cut = (date(2025, 1, 1) + timedelta(days=120)).isoformat()
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            self._make_db(db)
            block = analog_block_for_llm(
                "历史上信创类似的走势后来怎么走", "信创", db, as_of=cut
            )
        self.assertIn("[D8]", block)
        latest = _max_date_in(block)
        self.assertIsNotNone(latest)
        self.assertLessEqual(latest, cut)

    def test_two_as_of_give_different_blocks(self) -> None:
        early = (date(2025, 1, 1) + timedelta(days=120)).isoformat()
        late = (date(2025, 1, 1) + timedelta(days=199)).isoformat()
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            self._make_db(db)
            q = "历史上信创类似的走势后来怎么走"
            block_early = analog_block_for_llm(q, "信创", db, as_of=early)
            block_late = analog_block_for_llm(q, "信创", db, as_of=late)
        self.assertIn("[D8]", block_early)
        self.assertIn("[D8]", block_late)
        self.assertNotEqual(block_early, block_late)

    def test_theme_absent_at_as_of_does_not_resolve(self) -> None:
        """解析器截断：截止日当时还不存在的题材名不得进名录。

        对「只截 ``fact_sector_daily`` 逐日行、不给 ``resolve_query_themes``
        传 as_of」这个变异敏感——漏截时题材会被解析出来，块里出现一行
        「历史行数不足」的数据缺口，看起来仍然像一次诚实降级。
        """
        cut = (date(2025, 1, 1) + timedelta(days=120)).isoformat()
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            self._make_db(db)
            q = "历史上库尾题材类似的走势后来怎么走"
            truncated = analog_block_for_llm(q, None, db, as_of=cut)
            untruncated = analog_block_for_llm(q, None, db)
        self.assertNotIn("库尾题材", truncated)
        self.assertIn("库尾题材", untruncated)


@unittest.skipIf(duckdb is None, "duckdb 不可用")
class PrefetchWiringTests(unittest.TestCase):
    """接线：算子命中时 Engine A 开场预取真的出块，不是永远出 gap。

    只断言「有 gap」的夹具，对「接线根本没生效」这个变异不敏感——原实现就是
    恒出 gap 且当时全绿。所以这里必须钉**出块**那一侧。
    """

    def _blob(self, items) -> str:
        return "\n".join(f"{item.title}\n{item.detail}" for item in items)

    def _collect(self, question: str, db: Path, as_of: date):
        from intelligence.services.asof_prefetch import collect_prefetch_items

        return collect_prefetch_items(
            question=question,
            question_type="general_finance_qa",
            subject="",
            as_of=as_of,
            market_db_path=db,
        )

    def test_theme_analog_question_emits_real_d8_block(self) -> None:
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            _mma.AnalogBlockTests._make_db(None, db, n=200)
            items = self._collect(
                "历史上信创类似的走势后来怎么走",
                db,
                date(2025, 1, 1) + timedelta(days=150),
            )
        blob = self._blob(items)
        self.assertIn("[D8]", blob)
        self.assertIn("后续5日", blob)
        self.assertNotIn("D8 未预取", blob)

    def test_stock_analog_question_emits_real_d11_block(self) -> None:
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            _msa._make_db(db, n=200)
            items = self._collect(
                "英维克这段走势历史上有类似的吗",
                db,
                date(2025, 1, 1) + timedelta(days=150),
            )
        blob = self._blob(items)
        self.assertIn("[D11]", blob)
        self.assertIn("后续5日", blob)
        self.assertNotIn("D11 未预取", blob)

    def test_prefetched_blocks_respect_as_of(self) -> None:
        """预取层传下去的 as_of 必须真的生效，不是只写进 source_date。"""
        cut = (date(2025, 1, 1) + timedelta(days=120)).isoformat()
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            _msa._make_db(db, n=200)
            items = self._collect(
                "英维克这段走势历史上有类似的吗", db, date.fromisoformat(cut)
            )
        blob = self._blob(items)
        latest = _max_date_in(blob)
        self.assertIsNotNone(latest)
        self.assertLessEqual(latest, cut)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
