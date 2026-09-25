"""cheap 计划三件本地组件的临时 DuckDB 测试：成分拼接、板块日行情派生、席位换源换算。

全部用 :memory:，schema 走 SectorUniverseStore.ensure_schema（即 schema.sql 全文）。
场景刻意覆盖门禁与深模块的约束：无值成员剔除而非留 NULL、缺口超界不拼、
fallback 源拒绝、identity 变动的板块留给复盘会、板块日行情缺成分 fail closed。
"""
from __future__ import annotations

from datetime import date

import duckdb
import pytest

from market_feature_store.sector_universe import (
    MemberResult,
    SectorDescriptor,
    SectorUniverseStore,
)
from market_feature_store.sync import sync_local_sector_daily as local_daily
from market_feature_store.sync import sync_local_sector_members as stitch
from market_feature_store.sync.sync_akshare_dragon_seats import classify_seat, to_rows

DIM_SECTOR_DDL = (
    "create table dim_sector(sector_ts_code text primary key, sector_name text, "
    "sw_l1 text, is_active boolean, first_seen_date date, last_seen_date date, "
    "source text, updated_at timestamp)"
)
D1, D2 = "2026-09-01", "2026-09-02"
CAPTURED = {D1: "2026-09-01T16:00:00+08:00", D2: "2026-09-02T16:00:00+08:00"}


@pytest.fixture
def con():
    c = duckdb.connect(":memory:")
    c.execute(DIM_SECTOR_DDL)
    SectorUniverseStore.ensure_schema(c)
    for d in (D1, D2):
        c.execute("insert into fact_market_daily (trade_date) values (?)", [d])
    try:
        yield c
    finally:
        c.close()


def _publish(con, trade_date, sectors):
    return SectorUniverseStore(con).publish_snapshot(
        trade_date=trade_date,
        provider_source="fupanhui",
        sectors=tuple(SectorDescriptor(code, name, n) for code, name, n in sectors),
        captured_at=CAPTURED[trade_date],
    )


def _provider_member(code, name="股", price=10.0, pct=1.0, amount=2.0, **extra):
    row = {"ts_code": code, "name": name, "price": price, "pct_chg": pct, "amount": amount,
           "sw_industry": "电子", "leader_plate": "AI", "role_tags_json": "[]",
           "circ_mv": 100.0, "float_mcap_yi": 50.0, "total_mcap_yi": 80.0, "mcap_source": "tencent",
           "source": "fupanhui"}
    row.update(extra)
    return row


def _record(con, snapshot_id, sector, trade_date, members):
    return SectorUniverseStore(con).record_member_result(
        snapshot_id, sector, MemberResult.success(served_date=trade_date, stocks=members)
    )


def _eastmoney(con, trade_date, rows, source="eastmoney:snapshot"):
    con.executemany(
        "insert into fact_stock_daily (trade_date, stock_ts_code, close, pct_chg, amount, source) values (?,?,?,?,?,?)",
        [(trade_date, code, close, pct, amt, source) for code, close, pct, amt in rows],
    )


def _seed_day1(con):
    """09-01：三板块全部 fupanhui 名单 + 板块日行情。"""
    pub = _publish(con, D1, [("990001.FP", "MLCC", 3), ("990002.FP", "6G", 2), ("990003.FP", "机器人", 2)])
    _record(con, pub.snapshot_id, "990001.FP", D1, [_provider_member("000001.SZ", "平安"), _provider_member("000002.SZ", "万科"), _provider_member("000003.SZ", "退市股")])
    _record(con, pub.snapshot_id, "990002.FP", D1, [_provider_member("600000.SH", "浦发"), _provider_member("600001.SH", "邯钢")])
    _record(con, pub.snapshot_id, "990003.FP", D1, [_provider_member("300001.SZ", "特锐德"), _provider_member("300002.SZ", "神州泰岳")])
    SectorUniverseStore(con).replace_sector_daily(pub.snapshot_id, [
        {"sector_ts_code": "990001.FP", "pct_chg": 1.0, "amount": 6.0, "diff_ratio": 0.0},
        {"sector_ts_code": "990002.FP", "pct_chg": 1.0, "amount": 4.0, "diff_ratio": 0.0},
        {"sector_ts_code": "990003.FP", "pct_chg": 1.0, "amount": 4.0, "diff_ratio": 0.0},
    ])
    # 09-01 东财行：给 N 日涨幅复算留一天历史
    _eastmoney(con, D1, [(c, 10.0, 1.0, 2.0) for c in ("000001.SZ", "000002.SZ", "000003.SZ", "600000.SH", "600001.SH", "300001.SZ", "300002.SZ")])
    return pub


def test_identity_delta_classifies_by_expected_count(con):
    _seed_day1(con)
    _publish(con, D2, [("990001.FP", "MLCC", 3), ("990002.FP", "6G", 2), ("990003.FP", "机器人", 3), ("990009.FP", "新板块", 1)])
    delta = stitch.identity_delta(con, D2)
    assert delta.prev_date == date(2026, 9, 1)
    assert delta.unchanged == ("990001.FP", "990002.FP")
    assert delta.changed == ("990003.FP",)
    assert delta.new == ("990009.FP",)
    assert delta.gone == ()


def test_stitch_writes_true_values_drops_missing_and_leaves_changed_pending(con):
    _seed_day1(con)
    pub2 = _publish(con, D2, [("990001.FP", "MLCC", 3), ("990002.FP", "6G", 2), ("990003.FP", "机器人", 3)])
    # 09-02 东财：000003 退市无行；其余有值
    _eastmoney(con, D2, [("000001.SZ", 11.0, 10.0, 3.0), ("000002.SZ", 9.0, -10.0, 1.5),
                         ("600000.SH", 10.5, 5.0, 2.5), ("600001.SH", 10.0, 0.0, 2.0),
                         ("300001.SZ", 12.0, 20.0, 4.0), ("300002.SZ", 8.0, -20.0, 1.0)])
    con.execute("insert into fact_stock_high_daily (trade_date, stock_ts_code, primary_high_period, primary_high_label) values (?,?,?,?)",
                [D2, "000001.SZ", "20d", "20日新高"])
    con.execute("insert into fact_theme_limit_stock_daily (trade_date, sector_ts_code, stock_ts_code, limit_times) values (?,?,?,?)",
                [D2, "990001.FP", "000002.SZ", 2])

    summary = stitch.stitch_sector_members(D2, con=con, fetch_caps=False)

    assert summary["stitched"] == 2 and summary["candidates"] == 2
    assert summary["skipped"] == {} and summary["failed"] == []
    assert summary["dropped_members"] == 1
    assert summary["pending_for_provider"] == 1  # 990003 expected 变了
    assert summary["baseline_dates"] == {D1: 2}

    rows = con.execute(
        "select sector_ts_code, stock_ts_code, price, pct_chg, amount, high_status, limit_times, source, "
        "sw_industry, circ_mv, float_mcap_yi, mcap_source from fact_sector_stock_daily where trade_date = ? order by 1, 2",
        [D2],
    ).fetchall()
    assert [(r[0], r[1]) for r in rows] == [
        ("990001.FP", "000001.SZ"), ("990001.FP", "000002.SZ"), ("990002.FP", "600000.SH"), ("990002.FP", "600001.SH"),
    ]
    assert all(r[7] == "local:stitch" for r in rows)
    pingan = rows[0]
    assert (pingan[2], pingan[3], pingan[4]) == (11.0, 10.0, 3.0)  # 东财真值
    assert pingan[5] == "20d" and rows[1][6] == 2  # high_status / limit_times join
    assert pingan[8] == "电子" and pingan[9] == pytest.approx(110.0)  # 标签 carry；circ_mv 按 11/10 缩放
    assert pingan[10] == pytest.approx(55.0) and pingan[11] == "local:scaled"
    # 门禁：拼接行不得有 NULL 三件
    assert con.execute(
        "select count(*) from fact_sector_stock_daily where trade_date = ? and (price is null or pct_chg is null or amount is null)",
        [D2],
    ).fetchone()[0] == 0
    status = dict(con.execute(
        "select sector_ts_code, status from ops_sector_member_sync_daily where trade_date = ? and snapshot_id = ?",
        [D2, pub2.snapshot_id],
    ).fetchall())
    assert status == {"990001.FP": "success", "990002.FP": "success", "990003.FP": "pending"}
    shortfall = con.execute(
        "select expected_stock_count - actual_stock_count from ops_sector_member_sync_daily where trade_date = ? and sector_ts_code = '990001.FP'",
        [D2],
    ).fetchone()[0]
    assert shortfall == 1  # 缺口记录在台账上，不是静默丢


def test_stitch_rejects_fallback_value_source(con):
    _seed_day1(con)
    _publish(con, D2, [("990001.FP", "MLCC", 3), ("990002.FP", "6G", 2), ("990003.FP", "机器人", 2)])
    _eastmoney(con, D2, [("000001.SZ", 11.0, 10.0, 3.0)], source="fupanhui:sector_stock_daily:fallback")
    with pytest.raises(RuntimeError, match="东财"):
        stitch.stitch_sector_members(D2, con=con, fetch_caps=False)


def test_stitch_skips_sector_when_shortfall_exceeds_bound(con):
    pub1 = _publish(con, D1, [("990010.FP", "大板块", 12)])
    codes = [f"{i:06d}.SZ" for i in range(1, 13)]
    _record(con, pub1.snapshot_id, "990010.FP", D1, [_provider_member(c) for c in codes])
    _publish(con, D2, [("990010.FP", "大板块", 12)])
    _eastmoney(con, D2, [(c, 10.0, 1.0, 2.0) for c in codes[:4]])  # 12 只只剩 4 只有值 → 缺 8 > max(5, 0.6)
    summary = stitch.stitch_sector_members(D2, con=con, fetch_caps=False)
    assert summary["stitched"] == 0
    assert summary["skipped"] == {"shortfall": 1}
    assert summary["pending_for_provider"] == 1
    assert con.execute("select count(*) from fact_sector_stock_daily where trade_date = ?", [D2]).fetchone()[0] == 0


def test_stitch_dry_run_writes_nothing(con):
    _seed_day1(con)
    _publish(con, D2, [("990001.FP", "MLCC", 3), ("990002.FP", "6G", 2), ("990003.FP", "机器人", 2)])
    _eastmoney(con, D2, [(c, 10.0, 1.0, 2.0) for c in ("000001.SZ", "000002.SZ", "600000.SH", "600001.SH", "300001.SZ", "300002.SZ")])
    summary = stitch.stitch_sector_members(D2, con=con, fetch_caps=False, dry_run=True)
    assert summary["stitched"] == 3 and set(summary["rows"]) == {"990001.FP", "990002.FP", "990003.FP"}
    assert con.execute("select count(*) from fact_sector_stock_daily where trade_date = ?", [D2]).fetchone()[0] == 0


def test_local_sector_daily_fails_closed_then_derives_from_members(con):
    _seed_day1(con)
    pub2 = _publish(con, D2, [("990001.FP", "MLCC", 3), ("990002.FP", "6G", 2), ("990003.FP", "机器人", 3)])
    _eastmoney(con, D2, [("000001.SZ", 11.0, 10.0, 3.0), ("000002.SZ", 9.0, -10.0, 1.5), ("000003.SZ", 10.0, 0.0, 1.5),
                         ("600000.SH", 10.5, 5.0, 2.5), ("600001.SH", 10.0, 0.0, 2.0),
                         ("300001.SZ", 12.0, 20.0, 4.0), ("300002.SZ", 8.0, -20.0, 1.0), ("300003.SZ", 8.0, 0.0, 1.0)])
    stitch.stitch_sector_members(D2, con=con, fetch_caps=False)
    with pytest.raises(RuntimeError, match="无成分行"):
        local_daily.sync_sector_daily_local(D2, con=con)
    # 复盘会 delta 补上 identity 变动的板块
    _record(con, pub2.snapshot_id, "990003.FP", D2, [
        _provider_member("300001.SZ", price=12.0, pct=20.0, amount=4.0),
        _provider_member("300002.SZ", price=8.0, pct=-20.0, amount=1.0),
        _provider_member("300003.SZ", price=8.0, pct=0.0, amount=1.0),
    ])
    summary = local_daily.sync_sector_daily_local(D2, con=con)
    assert summary["rows_written"] == 3 and summary["pct_eqw"] == 3 and summary["prev_date"] == D1
    rows = {r[0]: r[1:] for r in con.execute(
        "select sector_ts_code, pct_chg, amount, diff_ratio, source from fact_sector_daily where trade_date = ?", [D2]
    ).fetchall()}
    # 990001：成分 3.0+1.5+1.5=6.0，昨额 6.0 → 边际量 0；等权涨幅 (10-10+0)/3=0
    assert rows["990001.FP"][1] == pytest.approx(6.0) and rows["990001.FP"][2] == pytest.approx(0.0)
    assert rows["990001.FP"][0] == pytest.approx(0.0)
    # 990002：2.5+2.0=4.5，昨额 4.0 → +12.5%
    assert rows["990002.FP"][1] == pytest.approx(4.5) and rows["990002.FP"][2] == pytest.approx(12.5)
    assert rows["990002.FP"][3] == "local:agg/pct=eqw"
    # payload 官方涨幅优先
    con.execute(
        "insert into ops_sector_search_payload_daily (trade_date, snapshot_id, sector_ts_code, pct_chg, raw_json, captured_at) values (?,?,?,?,?,now())",
        [D2, pub2.snapshot_id, "990002.FP", 3.33, "{}"],
    )
    summary = local_daily.sync_sector_daily_local(D2, con=con)
    assert summary["pct_official"] == 1
    row = con.execute("select pct_chg, source from fact_sector_daily where trade_date = ? and sector_ts_code = '990002.FP'", [D2]).fetchone()
    assert row == (3.33, "local:agg/pct=official")


def test_compare_rows_flags_shuanghong_flip():
    local = {"A": {"pct_chg": 0.5, "amount": 600.0, "diff_ratio": 12.0}, "B": {"pct_chg": -0.2, "amount": 100.0, "diff_ratio": 1.0}}
    provider = {"A": {"pct_chg": -0.1, "amount": 600.0, "diff_ratio": 12.0}, "B": {"pct_chg": -0.2, "amount": 100.0, "diff_ratio": 1.0}}
    result = local_daily.compare_rows(local, provider)
    assert result["compared"] == 2 and result["pct_sign_mismatch"] == 1
    assert result["shuanghong_flips"] == ["A"] and result["ok"] is False


def test_akshare_seat_rows_convert_units_and_classify():
    pandas = pytest.importorskip("pandas")
    frame = pandas.DataFrame([
        {"序号": 1, "交易营业部名称": "深股通专用", "买入金额": 1.515168e8, "买入金额-占总成交比例": 0.046482,
         "卖出金额": 1.500809e8, "卖出金额-占总成交比例": 0.046041, "净额": 1.435949e6, "类型": "x"},
        {"序号": 2, "交易营业部名称": "机构专用", "买入金额": 5e7, "买入金额-占总成交比例": 0.015,
         "卖出金额": 0.0, "卖出金额-占总成交比例": 0.0, "净额": 5e7, "类型": "x"},
        {"序号": 3, "交易营业部名称": "国泰海通证券股份有限公司无锡湖滨路证券营业部", "买入金额": 1.507985e8,
         "买入金额-占总成交比例": 0.046261, "卖出金额": 4.0117e4, "卖出金额-占总成交比例": 0.000012, "净额": 1.507584e8, "类型": "x"},
        {"序号": 4, "交易营业部名称": "机构专用", "买入金额": 1.0, "买入金额-占总成交比例": 0.0, "卖出金额": 0.0,
         "卖出金额-占总成交比例": 0.0, "净额": 1.0, "类型": "dup"},
    ])
    rows = to_rows(frame, trade_date=date(2026, 9, 2), stock_ts_code="002536.SZ", stock_name="飞龙股份", side="buy",
                   now=__import__("datetime").datetime(2026, 9, 2, 20, 0))
    assert len(rows) == 3  # 同名席位去重（主键含 exalter）
    north = rows[0]
    assert north[5] == "深股通专用" and north[6] == "游资" and north[7] == "深股通专用"
    assert north[8] == pytest.approx(1.5152, abs=1e-4) and north[9] == pytest.approx(1.5008, abs=1e-4)
    assert north[10] == pytest.approx(4.6482, abs=1e-3) and north[12] == pytest.approx(0.0144, abs=1e-3)
    assert rows[1][6] == "机构" and rows[1][7] is None
    assert rows[2][6] == "营业部" and rows[2][7] is None and rows[2][13].startswith("akshare:")
    assert classify_seat("沪股通专用") == ("游资", "沪股通专用")


def test_dragon_seats_cheap_falls_back_to_provider(monkeypatch):
    from market_feature_store.sync import sync_fupanhui_public_assets as pa

    monkeypatch.setattr(
        "market_feature_store.sync.sync_akshare_dragon_seats.sync_dragon_seats_akshare",
        lambda td: {"rows": 0, "errors": {"x": "boom"}},
    )
    monkeypatch.setattr(pa, "sync_dragon_seats", lambda td: {"rows": 7, "stocks": 3})
    result = pa.sync_dragon_seats_cheap("2026-09-02")
    assert result["path"] == "fupanhui-fallback" and result["rows"] == 7
    assert result["akshare_errors"] == {"x": "boom"}

    monkeypatch.setattr(
        "market_feature_store.sync.sync_akshare_dragon_seats.sync_dragon_seats_akshare",
        lambda td: {"rows": 30, "stocks": 3, "errors": {}},
    )
    assert pa.sync_dragon_seats_cheap("2026-09-02")["path"] == "akshare"
