"""D6 的 as_of 截断：**解析器、取数、候选池三样必须一起截**。

背景（2026-09-11 实测）：D6 此前整条链路都取库尾。`resolve_query_themes` 早就带
`as_of` 形参（D8/D11 那轮加的），`market_review_requested_date` /
`asof_prefetch.standing_iso_from_query` 都能从问句解析出截止日，D0 已经在用，
D9/D12 已在用 `options.date`——只有 D6 一个都没接。后果是：

    "2026-07-10 最值得关注的三个方向是哪三个"
      → is_direction_ranking_query = True（词面门，不看日期）
      → 题材 = 库尾成交额 top6，窗口 = 2026-08-13 ~ 2026-09-10

问 7 月、答 9 月，且块是自洽的（照常渲染拥挤度分位），不会被标 hindsight——
`river` 的 `knowledge_cutoff > as_of` 拒绝只管 river 读取面，ask 的 D 块不经过它。

本文件的断言形状固定为四种，每种对一个具体变异敏感：

1. **块里不许出现晚于 as_of 的日期** —— 对「只截题材名录、不截逐日取数」敏感；
2. **拥挤度分位的分母也得截** —— 对「只截趋势窗口、不截 trailing 分布」敏感。
   这一条单靠日期断言照不出来：分位是个数字，块里不渲染它的分布区间；
3. **候选池按截止日当天的成交额榜取** —— 对「兜底仍取库尾 top6」敏感，
   这是本轮兜底新引入的面，也是历史问句最容易被喂错的一处；
4. **截止日当时不存在的题材解析不到** —— 对「只截取数、不截名录」敏感。

`as_of=None`（既有调用方）的行为由第五条钉住：与显式传库尾最大日期逐字节相同。
"""

from __future__ import annotations

import re
import unittest
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from intelligence.services.market_midterm import (
    load_midterm_trend_artifact,
    midterm_trend_block_for_llm,
    resolve_query_themes,
    top_board_themes,
)

try:
    import duckdb
except Exception:  # pragma: no cover
    duckdb = None

_ISO_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
_BASE = date(2026, 1, 5)
# 截止日取第 60 个交易日。夹具形状：截止日之前「煤炭」大、之后「光模块」大，
# 且「光模块」在截止日当天根本没有行——截断失效时三条断言各自变红。
_CUT_INDEX = 60
_CUT = (_BASE + timedelta(days=_CUT_INDEX)).isoformat()
_RANKING_Q = "最值得关注的三个方向，按确定性排序"


def _max_date_in(block: str) -> str | None:
    hits = _ISO_RE.findall(block or "")
    return max(hits) if hits else None


def _make_db(path: Path) -> None:
    """煤炭截止日前大、截止日后缩量；光模块只在截止日之后存在且更大。"""
    con = duckdb.connect(str(path))
    con.execute(
        "create table fact_sector_daily "
        "(trade_date date, sector_name varchar, pct_chg double, diff_ratio double, amount double)"
    )
    for i in range(120):
        day = _BASE + timedelta(days=i)
        before = i <= _CUT_INDEX
        # 煤炭：截止日前逐日放量（截止日当天是自身历史最大 → 截断后分位 100%）；
        # 截止日后逐日缩量（库尾那天是自身 trailing 分布里最小 → 不截断时分位 ~2%）。
        # 这个形状是被变异逼出来的：初版「截止日后恒定 120」下最新值与整段并列，
        # 按 `<=` 计数的分位是 98.3%，断言照不出「hist 没同截」。
        amount = 300.0 + i * 10.0 if before else 2000.0 - (i - _CUT_INDEX) * 15.0
        con.execute(
            "insert into fact_sector_daily values (?, '煤炭', ?, ?, ?)",
            [day, 1.5, 12.0, amount],
        )
        if not before:
            # 光模块：截止日当天还不存在，之后成交额一路第一。
            con.execute(
                "insert into fact_sector_daily values (?, '光模块', ?, ?, ?)",
                [day, 2.5, 18.0, 5000.0],
            )
    con.execute(
        "create table fact_theme_limit_heat_daily "
        "(trade_date date, sector_name varchar, limit_up_count int, rank int)"
    )
    for i in range(120):
        con.execute(
            "insert into fact_theme_limit_heat_daily values (?, '煤炭', ?, ?)",
            [_BASE + timedelta(days=i), 3, 10],
        )
    con.close()


@unittest.skipIf(duckdb is None, "duckdb 不可用")
class MidtermAsOfTruncationTests(unittest.TestCase):
    def test_block_never_shows_dates_after_as_of(self) -> None:
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            _make_db(db)
            block = midterm_trend_block_for_llm(
                "煤炭的中期赔率怎么样", None, db, as_of=_CUT
            )
        self.assertIn("[D6]", block)
        latest = _max_date_in(block)
        self.assertIsNotNone(latest)
        self.assertLessEqual(latest, _CUT)

    def test_crowding_denominator_is_truncated_too(self) -> None:
        """拥挤度分位的 trailing 分布必须同截，否则是拿后来的分布给当时排名。

        夹具下：截到 60 日时最新成交额是自身历史最大 → 分位 100%；
        不截时库尾是一路缩量的末端、trailing 分布里最小 → 分位掉到个位数。
        「只截趋势窗口、忘了截 hist」会落在低位那一侧。
        """
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            _make_db(db)
            cut = load_midterm_trend_artifact("煤炭怎么看", None, db, as_of=_CUT)
            tail = load_midterm_trend_artifact("煤炭怎么看", None, db)
        cut_pct = cut.trends[0]["crowding_pct"]
        tail_pct = tail.trends[0]["crowding_pct"]
        self.assertEqual(cut_pct, 100.0)
        self.assertLess(tail_pct, 50.0)

    def test_board_fallback_uses_as_of_day_ranking(self) -> None:
        """候选池：排序题不点名题材时，兜底也得按截止日当天的成交额榜取。"""
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            _make_db(db)
            con = duckdb.connect(str(db), read_only=True)
            try:
                at_cut = top_board_themes(con, as_of=_CUT)
                at_tail = top_board_themes(con)
            finally:
                con.close()
            block_cut = midterm_trend_block_for_llm(
                _RANKING_Q, None, db, board_fallback=True, as_of=_CUT
            )
        self.assertEqual(at_cut, ["煤炭"])
        self.assertEqual(at_tail[0], "光模块")
        self.assertIn("煤炭", block_cut)
        self.assertNotIn("光模块", block_cut)

    def test_theme_absent_at_as_of_does_not_resolve(self) -> None:
        """解析器截断：截止日当时还不存在的题材名不得进名录。

        问句故意同时点名两个题材，这是被变异测试逼出来的：只问「光模块」时，
        漏截名录（只截取数）也会得到一个**空块**——题材解析出来了但取数为空，
        渲染层直接返回空串，`assertNotIn` 恒绿（实测：M1 变异下 10 条全过）。
        搂上一个截止日前就存在的题材后，块不再为空，漏截时会多出一行
        「数据缺口：光模块」——看着像一次诚实降级，实际是未来题材漏进了名录。
        """
        q = "煤炭和光模块的中期赔率哪个好"
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            _make_db(db)
            con = duckdb.connect(str(db), read_only=True)
            try:
                truncated = resolve_query_themes(con, q, as_of=_CUT)
                untruncated = resolve_query_themes(con, q)
            finally:
                con.close()
            artifact = load_midterm_trend_artifact(q, None, db, as_of=_CUT)
            block = midterm_trend_block_for_llm(q, None, db, as_of=_CUT)
        self.assertEqual(truncated, ["煤炭"])
        self.assertIn("光模块", untruncated)
        self.assertEqual(artifact.missing_themes, ())
        self.assertIn("煤炭", block)
        self.assertNotIn("光模块", block)

    def test_as_of_none_keeps_tail_numbers_and_says_nothing_about_cutoff(self) -> None:
        """既有调用方（不传 as_of）数字不变：None 就是库尾那天。

        只比表体：传了 as_of 时口径行多一句「截至 …」，那是故意的——历史问句下
        这行是模型分辨「当时/今天」的唯一依据；不传时不得凭空多出这句话。
        """
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            _make_db(db)
            tail_day = (_BASE + timedelta(days=119)).isoformat()
            implicit = midterm_trend_block_for_llm(
                _RANKING_Q, None, db, board_fallback=True
            )
            explicit = midterm_trend_block_for_llm(
                _RANKING_Q, None, db, board_fallback=True, as_of=tail_day
            )

        def _table(block: str) -> list[str]:
            return [ln for ln in block.splitlines() if ln.startswith("|")]

        self.assertNotEqual(implicit, "")
        self.assertEqual(_table(implicit), _table(explicit))
        self.assertNotIn("截至", implicit)
        self.assertIn(f"截至 {tail_day}", explicit)

    def test_coverage_days_counts_distinct_dates_not_rows(self) -> None:
        """「覆盖天数」必须是交易日个数，不是行数。

        同一板块名挂两套供应商代码是真库里的常态（全库 3,206 组重复）。
        接上 as_of 后这个遗留问题会浮上水面：实测 2026-07-10 的芯片，20 行窗口
        只覆盖 10 个交易日，而这一列原本报 20——与块头那个 10 天的日期区间矛盾。
        窗口本身仍是「行窗口」（改成去重日窗会动到库尾既有答案的数字，另算一件事），
        这里只保证渲染出来的数字不撒谁。
        """
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "dup.duckdb"
            con = duckdb.connect(str(db))
            con.execute(
                "create table fact_sector_daily (trade_date date, sector_name varchar, "
                "pct_chg double, diff_ratio double, amount double)"
            )
            for i in range(30):
                day = _BASE + timedelta(days=i)
                for amt in (500.0 + i, 499.0 + i):  # 两套供应商代码，值近乎相同
                    con.execute(
                        "insert into fact_sector_daily values (?, '煤炭', 1.0, 11.0, ?)",
                        [day, amt],
                    )
            con.execute(
                "create table fact_theme_limit_heat_daily (trade_date date, "
                "sector_name varchar, limit_up_count int, rank int)"
            )
            con.close()
            artifact = load_midterm_trend_artifact("煤炭的中期赔率", None, db, 20)
            block = midterm_trend_block_for_llm("煤炭的中期赔率", None, db, 20)
        self.assertEqual(artifact.trends[0]["days"], 10)
        self.assertIn("| 煤炭 | 10 |", block)

    def test_as_of_before_history_degrades_instead_of_borrowing_tail(self) -> None:
        """截止日早于建库日：只能空块，不许退回库尾借数。"""
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            _make_db(db)
            artifact = load_midterm_trend_artifact(
                _RANKING_Q, None, db, board_fallback=True, as_of="2020-01-01"
            )
            block = midterm_trend_block_for_llm(
                _RANKING_Q, None, db, board_fallback=True, as_of="2020-01-01"
            )
        self.assertEqual(artifact.trends, ())
        self.assertEqual(block, "")


class D6AsOfWiringTests(unittest.TestCase):
    """接线：ask 侧真的把截止日交给 D6，而不是让它自己取库尾。"""

    def test_as_of_prefers_bound_options_date(self) -> None:
        from intelligence.services.ask import d6_as_of_for

        self.assertEqual(d6_as_of_for("最值得关注的三个方向", "2026-07-10"), "2026-07-10")

    def test_as_of_falls_back_to_query_parse(self) -> None:
        from intelligence.services.ask import d6_as_of_for

        self.assertEqual(
            d6_as_of_for("2026-07-10 最值得关注的三个方向是哪三个", None), "2026-07-10"
        )

    def test_forward_looking_question_stays_untruncated(self) -> None:
        """前瞻问句没有截止日 → None → 库尾，与修复前一致。"""
        from intelligence.services.ask import d6_as_of_for

        self.assertIsNone(d6_as_of_for("明天最值得关注的三个方向", None))

    def test_builder_passes_as_of_into_d6(self) -> None:
        """源码级护栏：删掉 `as_of=` 这行，上面三条单元测试仍会全绿。

        D6 provider 是 `_answer_query_impl` 里的闭包，只有跑完整 compose 路径
        才构造得出来（要 LLM），所以这里退而求其次钉住调用形状——它只能证明
        「接线没被删」，证明不了语义，语义由本文件前半部分的真库断言负责。
        """
        import inspect

        from intelligence.services import ask

        source = inspect.getsource(ask._answer_query_impl)
        self.assertIn("d6_as_of = d6_as_of_for(options.query, options.date)", source)
        self.assertIn("as_of=d6_as_of,", source)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
