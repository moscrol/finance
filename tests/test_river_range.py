"""区间聚合的契约测试（`river_query.range_aggregate`）。

用合成库：要钉的是**护栏在不在**（缺天报没报、跨换源报没报、全空列判没判成 gap），
真库里这三种情况不一定同时出现在同一个实体上，钉不住。
个股与板块两条算法必须分开验——个股有 close 能精确算，板块只能连乘，
把两者混成一条会让个股白白吃上缺天误差。
"""

from __future__ import annotations

from typing import Any

import pytest

from intelligence.services.river_query import (
    SECTOR_METHOD,
    STOCK_METHOD,
    range_aggregate,
    render_range,
)

duckdb = pytest.importorskip("duckdb")

DAYS = ["2026-08-03", "2026-08-04", "2026-08-05"]


@pytest.fixture()
def db(tmp_path: Any) -> str:
    path = tmp_path / "t.duckdb"
    con = duckdb.connect(str(path))
    con.execute("CREATE TABLE fact_market_daily (trade_date DATE)")
    con.executemany("INSERT INTO fact_market_daily VALUES (?)", [[d] for d in DAYS])

    con.execute(
        "CREATE TABLE fact_stock_daily (trade_date DATE, stock_ts_code VARCHAR,"
        " stock_name VARCHAR, close DOUBLE, pre_close DOUBLE, amount DOUBLE, turnover DOUBLE)"
    )
    # 100 → 110 → 99：先涨 10% 再跌 10%，区间 -1%，最大回撤 -10%。
    con.executemany(
        "INSERT INTO fact_stock_daily VALUES (?, '600000.SH', '测试股', ?, ?, ?, NULL)",
        [[DAYS[0], 100.0, 100.0, 10.0], [DAYS[1], 110.0, 100.0, 12.0], [DAYS[2], 99.0, 110.0, 8.0]],
    )

    con.execute(
        "CREATE TABLE fact_sector_daily (trade_date DATE, sector_ts_code VARCHAR,"
        " sector_name VARCHAR, pct_chg DOUBLE, amount DOUBLE)"
    )
    con.executemany(
        "INSERT INTO fact_sector_daily VALUES (?, ?, '测试板块', ?, ?)",
        [
            [DAYS[0], "886013.TI", 10.0, 100.0],
            [DAYS[1], "886013.TI", 10.0, 100.0],
            [DAYS[2], "990062.FP", -10.0, 100.0],
        ],
    )
    con.close()
    return str(path)


class TestStockExact:
    def test_uses_close_to_close_not_compounding(self, db: str) -> None:
        agg = range_aggregate(DAYS[0], DAYS[-1], "600000.SH", db_path=db)
        assert agg.kind == "stock"
        assert agg.method == STOCK_METHOD
        assert agg.values["cumulative_return_pct"] == pytest.approx(-1.0)

    def test_drawdown_and_peak(self, db: str) -> None:
        agg = range_aggregate(DAYS[0], DAYS[-1], "600000.SH", db_path=db)
        assert agg.values["max_drawdown_pct"] == pytest.approx(-10.0)
        assert agg.values["peak_return_pct"] == pytest.approx(10.0)
        assert agg.peak_date == DAYS[1]

    def test_all_null_column_becomes_a_gap_not_a_zero(self, db: str) -> None:
        """列在库里但一行都没写过值：SQL 跑得通、返回 NULL，看起来像「这段时间没数据」。

        实测 `fact_stock_daily.turnover` 全库非空 0 行——判成 gap 并写明原因，
        不许混进正常读数，更不许当成 0。
        """
        agg = range_aggregate(DAYS[0], DAYS[-1], "600000.SH", db_path=db)
        assert "turnover_avg" not in agg.values
        gap = next(g for g in agg.gaps if g.metric == "turnover_avg")
        assert "0 行有值" in gap.reason

    def test_complete_range_is_trustworthy(self, db: str) -> None:
        agg = range_aggregate(DAYS[0], DAYS[-1], "600000.SH", db_path=db)
        assert agg.coverage.complete and agg.trustworthy


class TestSectorCompounding:
    def test_compounds_daily_pct(self, db: str) -> None:
        agg = range_aggregate(DAYS[0], DAYS[-1], "测试板块", db_path=db)
        assert agg.kind == "sector" and agg.method == SECTOR_METHOD
        # 1.10 * 1.10 * 0.90 - 1 = +8.9%
        assert agg.values["cumulative_return_pct"] == pytest.approx(8.9, abs=1e-6)

    def test_compounding_caveat_is_always_stated(self, db: str) -> None:
        """连乘的脆弱性不是「缺天时才提」——它是这个方法本身的性质，永远要说。"""
        agg = range_aggregate(DAYS[0], DAYS[-1], "测试板块", db_path=db)
        assert any("连乘" in c for c in agg.caveats)

    def test_provider_switch_is_reported(self, db: str) -> None:
        """跨换源日：两套代码成分不同，连乘等于把两个宇宙接在一起。必须报，不能静默。"""
        agg = range_aggregate(DAYS[0], DAYS[-1], "测试板块", db_path=db)
        assert agg.codes_seen == ("886013.TI", "990062.FP")
        assert not agg.trustworthy
        assert any("换源" in c for c in agg.caveats)


class TestCoverage:
    def test_missing_day_is_counted_and_named(self, db: str) -> None:
        con = duckdb.connect(db)
        con.execute("DELETE FROM fact_sector_daily WHERE trade_date = ?", [DAYS[1]])
        con.close()
        agg = range_aggregate(DAYS[0], DAYS[-1], "测试板块", db_path=db)
        assert agg.coverage.expected_days == 3
        assert agg.coverage.actual_days == 2
        assert agg.coverage.missing_dates == (DAYS[1],)
        assert not agg.coverage.complete
        assert any("覆盖不完整" in c for c in agg.caveats)

    def test_missing_day_silently_understates_without_the_guard(self, db: str) -> None:
        """护栏存在的理由：少乘一天，数就偏低，而 SQL 一声不吭。"""
        full = range_aggregate(DAYS[0], DAYS[-1], "测试板块", db_path=db)
        con = duckdb.connect(db)
        con.execute("DELETE FROM fact_sector_daily WHERE trade_date = ?", [DAYS[1]])
        con.close()
        partial = range_aggregate(DAYS[0], DAYS[-1], "测试板块", db_path=db)
        assert partial.values["cumulative_return_pct"] < full.values["cumulative_return_pct"]
        assert partial.coverage.complete is False

    def test_expected_days_come_from_the_market_calendar(self, db: str) -> None:
        """应有天数取自 `fact_market_daily`，不是「实体自己有几行」——否则缺天永远测不出来。"""
        agg = range_aggregate(DAYS[0], DAYS[-1], "测试板块", db_path=db)
        assert agg.coverage.expected_days == len(DAYS)


class TestDuplicateRows:
    """2026-09-06 评审 #601 硬伤：同日重复行会被重复连乘，而覆盖率仍报「完整、可信」。"""

    def _dup(self, db: str) -> None:
        con = duckdb.connect(db)
        con.execute(
            "INSERT INTO fact_sector_daily VALUES (?, '886013.TI', '测试板块', 10.0, 100.0)",
            [DAYS[1]],
        )
        con.close()

    def test_duplicate_day_is_not_compounded_twice(self, db: str) -> None:
        """三天各 +10% 应为 33.1%；多乘一天会变成 46.41%（1.1**4）。"""
        con = duckdb.connect(db)
        con.execute("DELETE FROM fact_sector_daily")
        for d in DAYS:
            con.execute(
                "INSERT INTO fact_sector_daily VALUES (?, '886013.TI', '测试板块', 10.0, 100.0)", [d]
            )
        con.execute(
            "INSERT INTO fact_sector_daily VALUES (?, '886013.TI', '测试板块', 10.0, 100.0)", [DAYS[1]]
        )
        con.close()
        agg = range_aggregate(DAYS[0], DAYS[-1], "测试板块", db_path=db)
        assert agg.values["cumulative_return_pct"] == pytest.approx(33.1, abs=1e-6)
        assert agg.values["cumulative_return_pct"] != pytest.approx(46.41, abs=1e-6)

    def test_duplicate_is_reported_not_silently_deduped(self, db: str) -> None:
        self._dup(db)
        agg = range_aggregate(DAYS[0], DAYS[-1], "测试板块", db_path=db)
        assert agg.coverage.duplicate_dates == (DAYS[1],)
        assert any("同一天读到多行" in c for c in agg.caveats)

    def test_duplicate_makes_it_untrustworthy(self, db: str) -> None:
        """去重只是止血：无从判断哪一行对，所以不能自称可信。"""
        self._dup(db)
        agg = range_aggregate(DAYS[0], DAYS[-1], "测试板块", db_path=db)
        assert agg.coverage.complete is True, "去重后天数是齐的——complete 回答不了重复"
        assert agg.coverage.clean is False
        assert agg.trustworthy is False

    def test_require_complete_refuses_on_duplicates(self, db: str) -> None:
        self._dup(db)
        agg = range_aggregate(DAYS[0], DAYS[-1], "测试板块", db_path=db, require_complete=True)
        assert all(v is None for v in agg.values.values())

    def test_dedupe_is_deterministic(self, db: str) -> None:
        """「两次调用结果相同」不能因为去重取哪一行而变成假绿。"""
        self._dup(db)
        a = range_aggregate(DAYS[0], DAYS[-1], "测试板块", db_path=db).to_dict()
        b = range_aggregate(DAYS[0], DAYS[-1], "测试板块", db_path=db).to_dict()
        assert a == b

    def test_duplicate_does_not_hide_provider_switch(self, db: str) -> None:
        """去重可能丢掉换源那一侧的代码——codes_seen 必须用去重前的行算。"""
        con = duckdb.connect(db)
        con.execute(
            "INSERT INTO fact_sector_daily VALUES (?, '990062.FP', '测试板块', 1.0, 100.0)", [DAYS[0]]
        )
        con.close()
        agg = range_aggregate(DAYS[0], DAYS[-1], "测试板块", db_path=db)
        assert "990062.FP" in agg.codes_seen and "886013.TI" in agg.codes_seen
        assert any("换源" in c for c in agg.caveats)

    def test_stock_path_also_deduped(self, db: str) -> None:
        """个股走 close 首尾相除，重复行会打乱首尾与回撤曲线，同样要去重。"""
        con = duckdb.connect(db)
        con.execute(
            "INSERT INTO fact_stock_daily VALUES (?, '600000.SH', '测试股', 999.0, 999.0, 1.0, NULL)",
            [DAYS[2]],
        )
        con.close()
        agg = range_aggregate(DAYS[0], DAYS[-1], "600000.SH", db_path=db)
        assert agg.coverage.duplicate_dates == (DAYS[2],)
        assert agg.trustworthy is False


class TestRequireComplete:
    def test_refuses_to_emit_numbers_when_incomplete(self, db: str) -> None:
        agg = range_aggregate(DAYS[0], DAYS[-1], "测试板块", db_path=db, require_complete=True)
        assert all(v is None for v in agg.values.values())
        assert any(g.metric == "*" for g in agg.gaps)
        # 限制仍然要说清楚：不给数不等于不解释为什么。
        assert agg.caveats

    def test_passes_through_when_clean(self, db: str) -> None:
        agg = range_aggregate(DAYS[0], DAYS[-1], "600000.SH", db_path=db, require_complete=True)
        assert agg.values["cumulative_return_pct"] == pytest.approx(-1.0)


class TestEdges:
    def test_unknown_entity_returns_gap_not_zero(self, db: str) -> None:
        agg = range_aggregate(DAYS[0], DAYS[-1], "不存在的板块", db_path=db)
        assert agg.values == {}
        assert any(g.metric == "*" for g in agg.gaps)

    def test_render_always_prints_caveats_and_gaps(self, db: str) -> None:
        """caveats 被折叠掉的那一刻，这个数就变危险了——渲染层不许省略。"""
        text = render_range(range_aggregate(DAYS[0], DAYS[-1], "测试板块", db_path=db))
        assert "限制" in text and "算不出来的" in text
        assert "可直接使用：否" in text
