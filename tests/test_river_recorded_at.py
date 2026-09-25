"""板块系表记录时刻的解析规则（`updated_at` 与快照台账 `captured_at` 取较早）。

用合成库而不是真库：要复现的失败形状是「重发布把 `updated_at` 推到今天、而快照台账
`captured_at` 还留着真时刻」，真库里这两种行混在一起，钉不出**方向**。方向钉反的代价
是实测的：整轨换成 `captured_at` 会让资金轨从 47 天 strict 掉到 20 天。
"""

from __future__ import annotations

from typing import Any

import pytest

from intelligence.services.river import (
    Gap,
    _capital_track,
    _market_track,
    sector_recorded_at_sql,
)

duckdb = pytest.importorskip("duckdb")

AS_OF = "2026-08-20"
EID = "990306.FP"
ENAME = "算力租赁"
SNAP = "snap-a"


def _db(*, snapshot_id: str = SNAP, captured_at: str | None = "2026-08-20 18:30:00+08",
        updated_at: str = "2026-09-05 11:00:00", with_ledger: bool = True) -> Any:
    """最小合成库。``updated_at`` 默认是「被重发布推到今天」的那种脏值。"""
    con = duckdb.connect(":memory:")
    con.execute(
        "CREATE TABLE fact_market_daily (trade_date DATE, market_stage VARCHAR, stage_day INT,"
        " total_amount DOUBLE, amount_vs_yesterday_pct DOUBLE, advancers INT, limit_up INT,"
        " limit_down INT, sh_deviation_pct DOUBLE, volume_state VARCHAR,"
        " concentration_state VARCHAR, updated_at TIMESTAMP)"
    )
    con.execute(
        "INSERT INTO fact_market_daily VALUES (DATE '2026-08-20','底部横盘',3,1.0,2.0,1500,50,8,"
        f"0.5,'正常','正常', TIMESTAMP '{updated_at}')"
    )
    con.execute(
        "CREATE TABLE fact_sector_daily (trade_date DATE, sector_ts_code VARCHAR,"
        " sector_name VARCHAR, sw_l1 VARCHAR, pct_chg DOUBLE, amount DOUBLE, diff_ratio DOUBLE,"
        " strength DOUBLE, multi_period_resonance VARCHAR, updated_at TIMESTAMP,"
        " sector_universe_snapshot_id VARCHAR)"
    )
    con.execute(
        f"INSERT INTO fact_sector_daily VALUES (DATE '{AS_OF}','{EID}','{ENAME}','计算机',"
        f"3.2, 620.0, 18.0, 1.1, '共振', TIMESTAMP '{updated_at}', '{snapshot_id}')"
    )
    con.execute(
        "CREATE TABLE fact_theme_limit_heat_daily (trade_date DATE, sector_name VARCHAR,"
        " limit_up_count INT, total_count INT, limit_up_ratio DOUBLE, market_share DOUBLE,"
        " rank INT, market_limit_up_count INT, data_stage VARCHAR, updated_at TIMESTAMP)"
    )
    con.execute(
        "CREATE TABLE fact_sector_stock_daily (trade_date DATE, sector_ts_code VARCHAR,"
        " fund_flow_1d DOUBLE, fund_flow_5d DOUBLE, amount DOUBLE, updated_at TIMESTAMP,"
        " sector_universe_snapshot_id VARCHAR)"
    )
    con.execute(
        f"INSERT INTO fact_sector_stock_daily VALUES (DATE '{AS_OF}','{EID}',1.0,2.0,10.0,"
        f"TIMESTAMP '{updated_at}','{snapshot_id}')"
    )
    con.execute(
        "CREATE TABLE fact_theme_flow_daily (trade_date DATE, theme_code VARCHAR,"
        " theme_name VARCHAR, total_fund DOUBLE, total_amount DOUBLE, stock_count INT,"
        " updated_at TIMESTAMP)"
    )
    if with_ledger:
        con.execute(
            "CREATE TABLE ops_sector_universe_snapshot_daily (trade_date DATE,"
            " snapshot_id VARCHAR, provider_source VARCHAR, sector_count INT,"
            " declared_relationship_count INT, status VARCHAR, captured_at TIMESTAMPTZ)"
        )
        if captured_at:
            con.execute(
                f"INSERT INTO ops_sector_universe_snapshot_daily VALUES (DATE '{AS_OF}','{SNAP}',"
                f"'fupanhui',403,0,'published', TIMESTAMPTZ '{captured_at}')"
            )
    return con


def _sector_label(result: Any) -> Any:
    assert not isinstance(result, Gap)
    return next(o for o in result if o.ref.startswith("fact_sector_daily:"))


class TestLedgerRecovery:
    def test_dirty_updated_at_recovered_from_ledger(self) -> None:
        """重发布把 `updated_at` 推到 09-05，台账还留着 08-20 18:30——取台账那个。"""
        con = _db()
        obj = _sector_label(_market_track(con, AS_OF, EID, ENAME))
        assert obj.recorded_at is not None
        assert obj.recorded_at[:10] == "2026-08-20"

    def test_capital_aggregate_also_recovered(self) -> None:
        con = _db()
        result = _capital_track(con, AS_OF, EID, ENAME)
        assert not isinstance(result, Gap)
        agg = next(o for o in result if o.ref.endswith(":agg"))
        assert agg.recorded_at is not None and agg.recorded_at[:10] == "2026-08-20"

    def test_earlier_updated_at_wins_over_later_capture(self) -> None:
        """方向钉死：`updated_at` 更早时用它。

        整轨换成 `captured_at` 会倒退——实测资金轨 47 天 strict 掉到 20 天，
        因为台账 2026-07-27 才开始，而更早那些行的 `updated_at` 里有一批是诚实的。
        """
        con = _db(updated_at="2026-08-19 09:00:00", captured_at="2026-08-21 18:30:00+08")
        obj = _sector_label(_market_track(con, AS_OF, EID, ENAME))
        assert obj.recorded_at is not None and obj.recorded_at[:10] == "2026-08-19"

    def test_legacy_snapshot_falls_back_to_updated_at(self) -> None:
        """`snapshot_id='legacy'` 的存量行接不上台账：用 `updated_at`，不猜、不报错。"""
        con = _db(snapshot_id="legacy")
        obj = _sector_label(_market_track(con, AS_OF, EID, ENAME))
        assert obj.recorded_at is not None and obj.recorded_at[:10] == "2026-09-05"

    def test_missing_ledger_table_degrades_quietly(self) -> None:
        """老库没有台账表：退回只看 `updated_at`，读取面照常出对象。"""
        con = _db(with_ledger=False)
        obj = _sector_label(_market_track(con, AS_OF, EID, ENAME))
        assert obj.recorded_at is not None and obj.recorded_at[:10] == "2026-09-05"

    def test_resolved_time_never_later_than_either_source(self) -> None:
        """不变量：解析结果不会晚于任何一个来源——晚了就等于宣称它比证据更晚才存在。"""
        for upd, cap in (
            ("2026-08-19 09:00:00", "2026-08-21 18:30:00+08"),
            ("2026-09-05 11:00:00", "2026-08-20 18:30:00+08"),
        ):
            con = _db(updated_at=upd, captured_at=cap)
            obj = _sector_label(_market_track(con, AS_OF, EID, ENAME))
            assert obj.recorded_at is not None
            assert obj.recorded_at[:10] <= min(upd[:10], cap[:10])


class TestSqlContract:
    def test_expression_drops_ledger_when_asked(self) -> None:
        """无台账时表达式里不能再出现 `snap.`，否则查询会因未连接而报错。"""
        assert "snap." not in sector_recorded_at_sql("v", with_ledger=False)
        assert "snap.captured_at" in sector_recorded_at_sql("v", with_ledger=True)

    def test_audit_uses_the_same_rule(self) -> None:
        """审计脚本必须从 river 取规则，不许自己另写一套 SQL。

        两处口径必漂，而漂的时候审计会替河说谎：报出来的 strict 天数不是河真能给出的。
        """
        from pathlib import Path

        src = Path("scripts/river_pit_audit.py").read_text(encoding="utf-8")
        assert "from intelligence.services.river import" in src
        assert "sector_recorded_at_sql" in src
