"""板块系表记录时刻的解析规则：只认这一行自己的 `updated_at`（工单 #43 / 补强 spec OPT-01）。

用合成库而不是真库：要复现的失败形状是「T 日 1%、T+7 修订成 9%，名单快照台账的
`captured_at` 还留着 T」——真库里这种行和「重发布没改内容」的行长得一模一样，钉不出**方向**。

2026-09-06 ~ 09-08 这里钉的是反方向（`LEAST(updated_at, captured_at)`，把 strict 覆盖从 1 天抬到
16 天）。那 15 天建立在「重发布不改内容」的假设上，而 sync 的 `ON CONFLICT DO UPDATE` 合同不保证
它：同 generation 的行情被覆盖时 `sector_universe_snapshot_id` 不变、`captured_at` 也就不变，
河会把修订后的值标成 T 日 strict。本文件把反例钉成回归；覆盖面靠内容级写一次 `recorded_at`
（`2026-09-05-river-recorded-at-workorder.md`）拿回来，不靠再找一个更早的别的时刻。
"""

from __future__ import annotations

from typing import Any

import pytest

from intelligence.services.river import (
    Gap,
    RiverSlice,
    _capital_track,
    _enforce_cutoff,
    _market_track,
    sector_recorded_at_sql,
)

duckdb = pytest.importorskip("duckdb")

AS_OF = "2026-08-20"
EID = "990306.FP"
ENAME = "算力租赁"
SNAP = "snap-a"
REVISED_AT = "2026-08-27 11:00:00"  # T+7：同一行被 sync 覆盖成修订值


def _db(*, snapshot_id: str = SNAP, captured_at: str | None = "2026-08-20 18:30:00+08",
        updated_at: str = REVISED_AT, pct_chg: float = 9.0, with_ledger: bool = True) -> Any:
    """最小合成库。默认就是反例形状：T 日的行在 T+7 被覆盖成 9%，台账 `captured_at` 仍是 T。"""
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
        f"{pct_chg}, 620.0, 18.0, 1.1, '共振', TIMESTAMP '{updated_at}', '{snapshot_id}')"
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


def _slice(tracks: dict) -> RiverSlice:
    return RiverSlice(as_of=AS_OF, entity_id=EID, entity_name=ENAME, knowledge_cutoff=AS_OF, tracks=tracks)


class TestRevisedRowIsNotStrict:
    """补强 spec §1.3 的最小反例转回归：T+7 修订过的行，在 C=T 下不能既返回修订值又标 strict。"""

    def test_recorded_at_follows_the_row_not_the_roster(self) -> None:
        con = _db()
        obj = _sector_label(_market_track(con, AS_OF, EID, ENAME))
        assert obj.payload["pct_chg"] == 9.0, "库里现在就是修订值，河如实返回它"
        assert obj.recorded_at is not None
        assert obj.recorded_at[:10] == "2026-08-27", "记录时刻必须跟着这一行的 updated_at，不能被名单 captured_at 拉早"

    def test_slice_downgrades_and_strict_mode_filters_it(self) -> None:
        con = _db()
        market = _market_track(con, AS_OF, EID, ENAME)
        assert _slice({"market": market}).pit_grade == "trade_date_only"
        strict = _enforce_cutoff({"market": market}, AS_OF)
        surviving = [o.ref for o in strict["market"]] if isinstance(strict["market"], list) else []
        assert not any(ref.startswith("fact_sector_daily:") for ref in surviving), "require_strict 下修订行必须被滤掉"

    def test_capital_aggregate_follows_its_rows_too(self) -> None:
        con = _db()
        result = _capital_track(con, AS_OF, EID, ENAME)
        assert not isinstance(result, Gap)
        agg = next(o for o in result if o.ref.endswith(":agg"))
        assert agg.recorded_at is not None and agg.recorded_at[:10] == "2026-08-27"

    def test_honest_row_is_still_strict(self) -> None:
        """不能修成「全部降档」：T 日写入、之后没被碰过的行仍然 strict。"""
        con = _db(updated_at="2026-08-20 16:05:00", pct_chg=1.0)
        market = _market_track(con, AS_OF, EID, ENAME)
        obj = _sector_label(market)
        assert obj.recorded_at is not None and obj.recorded_at[:10] == "2026-08-20"
        assert _slice({"market": market}).pit_grade == "strict"


class TestLedgerIsNotContentEvidence:
    def test_legacy_snapshot_uses_updated_at(self) -> None:
        """`snapshot_id='legacy'` 的存量行：`updated_at`，不猜、不报错。"""
        con = _db(snapshot_id="legacy")
        obj = _sector_label(_market_track(con, AS_OF, EID, ENAME))
        assert obj.recorded_at is not None and obj.recorded_at[:10] == "2026-08-27"

    def test_missing_ledger_table_changes_nothing(self) -> None:
        """有没有台账表，读取面输出逐字段相同——台账已不是记录时刻的输入。"""
        with_ledger = _sector_label(_market_track(_db(with_ledger=True), AS_OF, EID, ENAME))
        without = _sector_label(_market_track(_db(with_ledger=False), AS_OF, EID, ENAME))
        assert with_ledger == without

    def test_resolved_time_equals_updated_at(self) -> None:
        """不变量：记录时刻就是这一行的 `updated_at`，不早于它（早了 = 替后来的内容背书）。"""
        for upd, cap in (
            ("2026-08-19 09:00:00", "2026-08-21 18:30:00+08"),
            ("2026-09-05 11:00:00", "2026-08-20 18:30:00+08"),
        ):
            con = _db(updated_at=upd, captured_at=cap)
            obj = _sector_label(_market_track(con, AS_OF, EID, ENAME))
            assert obj.recorded_at is not None
            assert obj.recorded_at[:10] == upd[:10]

    def test_source_hash_excludes_recorded_at(self) -> None:
        """记录时刻规则变了，`source_hash` 不能变——冻结快照与既有收据按哈希对内容。"""
        a = _sector_label(_market_track(_db(updated_at="2026-08-20 16:05:00"), AS_OF, EID, ENAME))
        b = _sector_label(_market_track(_db(updated_at=REVISED_AT), AS_OF, EID, ENAME))
        assert a.source_hash == b.source_hash and a.recorded_at != b.recorded_at


class TestSqlContract:
    def test_expression_never_touches_the_ledger(self) -> None:
        """表达式里不许出现 `snap.`：名单时刻不是行情内容的证据。"""
        expr = sector_recorded_at_sql("v")
        assert "snap." not in expr and "captured_at" not in expr
        assert "v.updated_at" in expr

    def test_audit_uses_the_same_rule(self) -> None:
        """审计脚本必须从 river 取规则，不许自己另写一套 SQL。

        两处口径必漂，而漂的时候审计会替河说谎：报出来的 strict 天数不是河真能给出的。
        """
        from pathlib import Path

        src = Path("scripts/river_pit_audit.py").read_text(encoding="utf-8")
        assert "from intelligence.services.river import" in src
        assert "sector_recorded_at_sql" in src
        assert "sector_ledger_join" not in src
