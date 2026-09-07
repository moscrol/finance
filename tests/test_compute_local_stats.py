"""本地加工层（不靠 fupanhui）：名单冻结、涨跌停统计、市场总览数字层。口径钉自 2026-09-07 双轨实测。"""
from __future__ import annotations

from datetime import datetime, timezone

import duckdb
import pytest

from market_feature_store.db import init_db
from market_feature_store.sector_universe import SectorDescriptor, SectorUniverseStore
from market_feature_store.sync import compute_local_stats as cls_


def _db():
    con = duckdb.connect()
    init_db(con)
    return con


def _stock(con, d, code, name, close, pre, amount=1.0):
    pct = round((close / pre - 1) * 100, 2)
    con.execute(
        "INSERT INTO fact_stock_daily (trade_date, stock_ts_code, stock_name, close, pre_close, pct_chg, amount, source, updated_at) "
        "VALUES (?,?,?,?,?,?,?, 'eastmoney:snapshot', now())",
        [d, code, name, close, pre, pct, amount],
    )


def _seed_two_days(con):
    # 09-01：600001 涨停(首板)；09-02：600001 再涨停(二板)、300001 20% 板、920001 北交所 tie 板、*ST 10% 板、000001 平盘
    _stock(con, "2026-09-01", "600001.SH", "甲", 11.0, 10.0)          # 10.0×1.1=11.00 涨停
    _stock(con, "2026-09-01", "300001.SZ", "乙", 10.0, 10.0)
    _stock(con, "2026-09-01", "920001.BJ", "丙", 16.25, 12.5)         # 30% 板
    _stock(con, "2026-09-02", "600001.SH", "甲", 12.1, 11.0)          # 11.0×1.1=12.10 二板
    _stock(con, "2026-09-02", "300001.SZ", "乙", 12.0, 10.0)          # 20% 板
    _stock(con, "2026-09-02", "920001.BJ", "丙", 21.12, 16.25)        # 16.25×1.3=21.125 → 北交所向下取整 21.12 = 涨停
    _stock(con, "2026-09-02", "002514.SZ", "*ST宝馨", 2.27, 2.06)     # 10% 板但 ST → 不计
    _stock(con, "2026-09-02", "000001.SZ", "平安银行", 10.0, 10.0, amount=100.0)
    _stock(con, "2026-09-02", "600999.SH", "停牌股", 5.0, 5.0, amount=0.0)  # amount=0 不计


def _seed_universe_and_members(con):
    store = SectorUniverseStore(con)
    con.execute("INSERT INTO dim_sector (sector_ts_code, sector_name) VALUES ('990001.FP', '题材A'), ('990002.FP', '题材B')")
    published = store.publish_snapshot(
        trade_date="2026-09-02", provider_source="fupanhui",
        sectors=[SectorDescriptor("990001.FP", "题材A", 3), SectorDescriptor("990002.FP", "题材B", 1)],
        captured_at=datetime(2026, 9, 2, 18, 0, tzinfo=timezone.utc),
    )
    # fact_sector_stock_daily 是只暴露 published 代际的 VIEW，测试往代际表里写并挂上 snapshot_id
    for sec, name, stock in [("990001.FP", "题材A", "600001.SH"), ("990001.FP", "题材A", "300001.SZ"),
                             ("990001.FP", "题材A", "000001.SZ"), ("990002.FP", "题材B", "002514.SZ")]:
        con.execute(
            "INSERT INTO fact_sector_stock_daily_generation (trade_date, sector_universe_snapshot_id, sector_ts_code, sector_name, "
            "stock_ts_code, stock_name, price, pct_chg, amount, source, updated_at) "
            "VALUES ('2026-09-02', ?, ?, ?, ?, 'x', 1, 1, 1, 'fupanhui', now())",
            [published.snapshot_id, sec, name, stock],
        )


def test_limit_stats_exclude_st_and_use_exchange_rounding():
    con = _db()
    _seed_two_days(con)
    _seed_universe_and_members(con)
    r = cls_.compute_limit_stats_local("2026-09-02", con=con)
    assert r["action"] == "written"
    assert r["market_limit_up"] == 3            # 甲(二板)、乙(20%)、丙(北交所 21.12)；*ST 不计、停牌不计
    assert r["leader_height"] == 2 and r["ladder_rows"] == 2   # 甲、丙 都是二板（丙 09-01 12.5×1.3=16.25 也是板）
    heat = con.execute(
        "SELECT sector_ts_code, limit_up_count, total_count, market_limit_up_count, rank FROM fact_theme_limit_heat_daily ORDER BY rank"
    ).fetchall()
    assert heat == [("990001.FP", 2, 3, 3, 1)]  # 题材B 只有 ST，不出现在热度表
    ladder = con.execute("SELECT stock_ts_code, boards, CAST(first_limit_date AS VARCHAR), theme FROM fact_limit_advance_daily ORDER BY 1").fetchall()
    assert ladder == [("600001.SH", 2, "2026-09-01", "题材A"), ("920001.BJ", 2, "2026-09-01", None)]
    assert con.execute("SELECT DISTINCT source FROM fact_theme_limit_stock_daily").fetchall() == [("local:limit-rule",)]


def test_limit_stats_refuses_to_overwrite_fupanhui_rows_unless_forced():
    con = _db()
    _seed_two_days(con)
    _seed_universe_and_members(con)
    con.execute(
        "INSERT INTO fact_limit_advance_daily (trade_date, stock_ts_code, stock_name, boards, source, updated_at) "
        "VALUES ('2026-09-02', '600001.SH', '甲', 2, 'fupanhui:limit/ladder', now())"
    )
    r = cls_.compute_limit_stats_local("2026-09-02", con=con)
    assert r["action"] == "skipped-has-foreign-rows" and "fact_limit_advance_daily" in r["skipped"]
    r = cls_.compute_limit_stats_local("2026-09-02", con=con, force=True)
    assert r["action"] == "written"


def test_market_overview_numbers():
    con = _db()
    _seed_two_days(con)
    for name, amt in [("电子", 300.0), ("通信", 200.0), ("机械设备", 100.0), ("银行", 50.0)]:
        con.execute(
            "INSERT INTO fact_sw_l1_daily (trade_date, sw_l1_code, sw_l1, close, pre_close, pct_chg, amount, source, updated_at) "
            "VALUES ('2026-09-02', ?, ?, 1, 1, 0, ?, 'akshare:index_hist_sw', now())",
            [name, name, amt],
        )
    con.execute("INSERT INTO fact_market_daily (trade_date, total_amount, source) VALUES ('2026-09-01', 100.0, 'fupanhui:reviews')")
    r = cls_.compute_market_overview_local("2026-09-02", con=con)
    assert r["action"] == "written"
    # 沪深不含北交所：甲1+乙1+*ST1+平安100+停牌0 = 103（920001.BJ 的 1.0 不计）
    assert r["total_amount"] == pytest.approx(103.0)
    assert r["advancers"] == 4 and r["limit_up"] == 3 and r["limit_down"] == 0
    assert r["amount_ma20"] == pytest.approx((103.0 + 100.0) / 2) and r["volume_ratio"] == pytest.approx(103.0 / 101.5 * 100, rel=1e-3)
    assert [n for n, _ in r["top3"]] == ["电子", "通信", "机械设备"] and r["top3_ratio"] == pytest.approx(92.3, abs=0.2)  # 三个一位小数份额之和
    row = con.execute("SELECT source, concentration_state, amount_vs_yesterday_pct FROM fact_market_daily WHERE trade_date='2026-09-02'").fetchone()
    assert row[0] == "local:overview" and row[1] == "集中" and row[2] == pytest.approx(3.0)


def test_market_overview_keeps_fupanhui_values_unless_forced():
    con = _db()
    _seed_two_days(con)
    con.execute("INSERT INTO fact_market_daily (trade_date, total_amount, advancers, source) VALUES ('2026-09-02', 999.0, 1, 'fupanhui:reviews')")
    r = cls_.compute_market_overview_local("2026-09-02", con=con)
    assert r["action"] == "skipped-has-foreign-values"
    assert con.execute("SELECT total_amount FROM fact_market_daily WHERE trade_date='2026-09-02'").fetchone()[0] == 999.0


def test_carry_forward_universe_publishes_and_supersedes():
    con = _db()
    _seed_universe_and_members(con)
    r = cls_.carry_forward_universe("2026-09-03", con=con)
    assert r["action"] == "carried" and r["sectors"] == 2 and r["provider_source"] == "local:carry"
    # 再来一次是幂等的
    assert cls_.carry_forward_universe("2026-09-03", con=con)["action"] == "exists"
    # 顶替：换成承接 09-02，旧的标 superseded，且当日只剩一份 published
    r2 = cls_.carry_forward_universe("2026-09-03", con=con, supersede=True, base_date="2026-09-02")
    assert r2["action"] == "carried-superseding"
    st = con.execute(
        "SELECT status, COUNT(*) FROM ops_sector_universe_snapshot_daily WHERE trade_date='2026-09-03' GROUP BY 1 ORDER BY 1"
    ).fetchall()
    assert dict(st)["published"] == 1
    snap = SectorUniverseStore(con).published_snapshot("2026-09-03")  # 默认不限 provider
    assert snap.provider_source == "local:carry" and snap.sector_count == 2
