"""桥的断言与写入边界。全离线：内存 DuckDB + 最小 schema，不碰任何真实库。

用真实相邻交易日 2026-09-17 → 2026-09-18（走真实交易日历），
避免测试自造日历、掩盖 previous_scheduled_trading_day 的行为。
"""
from __future__ import annotations

from datetime import datetime

import duckdb
import pytest

from market_feature_store.sync import bridge_hithink_stock_daily as bridge
from market_feature_store.sync.bridge_hithink_stock_daily import (
    BridgePolicy,
    BridgeRefused,
    apply_bridge_day,
    build_bridge_day,
    resolve_universe,
)

PREV, TD = "2026-09-17", "2026-09-18"
_SCHEMA = """
CREATE TABLE fact_stock_daily(
  trade_date DATE, stock_ts_code VARCHAR, stock_name VARCHAR, close DOUBLE,
  pre_close DOUBLE, pct_chg DOUBLE, amount DOUBLE, turnover DOUBLE,
  source VARCHAR, updated_at TIMESTAMP, open DOUBLE, high DOUBLE,
  low DOUBLE, volume DOUBLE);
CREATE TABLE fact_stock_daily_hithink(
  stock_ts_code VARCHAR, trade_date DATE, open DOUBLE, high DOUBLE, low DOUBLE,
  close DOUBLE, volume DOUBLE, turnover DOUBLE, adjusted VARCHAR,
  source VARCHAR, updated_at TIMESTAMP);
CREATE TABLE fact_stock_adjustment_hithink(
  stock_ts_code VARCHAR, ex_date DATE, dividend_per_share DOUBLE,
  per_share_bonus DOUBLE, allotment_ratio DOUBLE, allotment_price DOUBLE,
  currency VARCHAR, source VARCHAR, updated_at TIMESTAMP);
"""
_NOW = datetime(2026, 9, 22, 19, 24, 37)


def _codes(n: int) -> list[str]:
    return [f"{i:06d}.SZ" for i in range(1, n + 1)]


def _con(codes: list[str], *, days=(PREV, TD), close=10.0) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute(_SCHEMA)
    for day in days:
        for code in codes:
            con.execute(
                "INSERT INTO fact_stock_daily_hithink VALUES (?,?,?,?,?,?,?,?,'none',"
                "'hithink:daily-k-10d',?)",
                [code, day, close, close, close, close, 100_000.0, 1_000_000.0, _NOW],
            )
    return con


def _seed_canonical(con, codes, day, *, name="旧名", names=None, close=9.0) -> None:
    """names 可逐码覆盖（值为 None 表示该行 stock_name 是 NULL）。"""
    for code in codes:
        value = names.get(code) if names is not None else name
        con.execute(
            "INSERT INTO fact_stock_daily VALUES (?,?,?,?,?,?,?,?,'eastmoney:snapshot',?,?,?,?,?)",
            [day, code, value, close, close, 0.0, 1.0, 0.5, _NOW, close, close, close, 1000.0],
        )


def test_resolve_universe_only_that_day() -> None:
    con = _con(_codes(3))
    con.execute(
        "INSERT INTO fact_stock_daily_hithink VALUES ('999999.SZ','2026-09-16',"
        "1,1,1,1,1,1,'none','hithink:daily-k',?)", [_NOW])
    assert resolve_universe(con, TD) == _codes(3)


def test_refuses_when_no_bars() -> None:
    con = _con(_codes(3))
    with pytest.raises(BridgeRefused, match="无任何 bar"):
        build_bridge_day(con, "2026-09-16")


def test_refuses_when_day_already_populated() -> None:
    """整日有行是 repair 的场景，不是 bridge 的；默认必须拒绝，防覆盖东财行。"""
    con = _con(_codes(3))
    _seed_canonical(con, _codes(3), TD)
    with pytest.raises(BridgeRefused, match="已有 3 行"):
        build_bridge_day(con, TD)


def test_allow_replace_existing_opens_the_gate() -> None:
    con = _con(_codes(3))
    _seed_canonical(con, _codes(3), TD)
    plan = build_bridge_day(con, TD, policy=BridgePolicy(allow_replace_existing=True))
    assert plan["existing_rows_before"] == 3


def test_refuses_on_universe_drift() -> None:
    """只取到一小撮代码时必须拒跑——常见于范围解析退化成单板块。"""
    con = _con(_codes(3))
    _seed_canonical(con, _codes(100), PREV)
    with pytest.raises(BridgeRefused, match="范围异常"):
        build_bridge_day(con, TD)


def test_refuses_on_low_coverage() -> None:
    """一半票缺前日 bar → 算通率 50% → 拒写半个市场。"""
    con = _con(_codes(10))
    con.execute("DELETE FROM fact_stock_daily_hithink WHERE trade_date = ? "
                "AND stock_ts_code IN (SELECT unnest(?::VARCHAR[]))", [PREV, _codes(5)])
    with pytest.raises(BridgeRefused, match="算通率"):
        build_bridge_day(con, TD)


def test_zero_volume_counts_as_gap_not_fabricated_bar() -> None:
    """零成交不等于平盘 K 线：它应进 gaps，不应被造成一行。"""
    con = _con(_codes(100))
    con.execute("UPDATE fact_stock_daily_hithink SET volume = 0 WHERE trade_date = ? "
                "AND stock_ts_code = '000001.SZ'", [TD])
    plan = build_bridge_day(con, TD)
    assert plan["calculated"] == 99
    assert "000001.SZ" in {g["stock_ts_code"] for g in plan["gaps"]}
    assert "000001.SZ" not in {r[1] for r in plan["rows"]}


def test_turnover_is_null_and_name_inherited() -> None:
    """换手率同花顺不提供必须留 NULL；名字取库内最近非空历史名。"""
    con = _con(_codes(3))
    _seed_canonical(con, _codes(3), "2026-09-10", name="老名")
    # PREV 全量在场（否则范围漂移守卫会先开火），但 000003 当日名字是 NULL。
    _seed_canonical(con, _codes(3), PREV,
                    names={"000001.SZ": "新名", "000002.SZ": "新名", "000003.SZ": None})
    plan = build_bridge_day(con, TD)
    by_code = {r[1]: r for r in plan["rows"]}
    assert by_code["000001.SZ"][2] == "新名"     # 取最近一条
    assert by_code["000003.SZ"][2] == "老名"     # 最近一条是 NULL，回退到更早的非空名
    assert all(r[7] is None for r in plan["rows"])   # turnover
    assert plan["named_rows"] == 3


def test_unnamed_new_listing_is_reported_not_guessed() -> None:
    con = _con(_codes(3))
    _seed_canonical(con, _codes(3), PREV, names={
        "000001.SZ": "旧名", "000002.SZ": "旧名", "000003.SZ": None})
    plan = build_bridge_day(con, TD)
    assert plan["unnamed_codes"] == ["000003.SZ"]
    assert {r[1]: r[2] for r in plan["rows"]}["000003.SZ"] is None


def test_cash_dividend_flows_into_pre_close() -> None:
    """除息日参考价 = 前一计划交易日裸收 − 现金红利，由 preview 负责。"""
    con = _con(_codes(3), close=10.0)
    con.execute("INSERT INTO fact_stock_adjustment_hithink VALUES "
                "('000001.SZ',?,0.5,0,0,0,'CNY','hithink:adjustment-factors',?)", [TD, _NOW])
    plan = build_bridge_day(con, TD)
    row = {r[1]: r for r in plan["rows"]}["000001.SZ"]
    assert row[4] == pytest.approx(9.5)                 # pre_close
    assert row[5] == pytest.approx(5.26)                # pct_chg = (10-9.5)/9.5*100


def test_noncash_action_is_refused_not_approximated() -> None:
    """送转配股不支持：进 gaps，不许用现金公式硬套。"""
    con = _con(_codes(100))
    con.execute("INSERT INTO fact_stock_adjustment_hithink VALUES "
                "('000001.SZ',?,0,0.5,0,0,'CNY','hithink:adjustment-factors',?)", [TD, _NOW])
    plan = build_bridge_day(con, TD)
    gap = next(g for g in plan["gaps"] if g["stock_ts_code"] == "000001.SZ")
    assert "unsupported-noncash-action" in gap["reasons"]


def test_apply_writes_day_and_leaves_other_days_alone() -> None:
    con = _con(_codes(3))
    _seed_canonical(con, _codes(3), PREV)
    before = con.execute("SELECT count(*), sum(close) FROM fact_stock_daily "
                         "WHERE trade_date = ?", [PREV]).fetchone()
    result = apply_bridge_day(con, build_bridge_day(con, TD))
    assert result["written_rows"] == 3 and result["final_rows"] == 3
    assert result["deleted_replaced"] == 0
    assert result["other_days_unchanged"] is True
    assert con.execute("SELECT count(*), sum(close) FROM fact_stock_daily "
                       "WHERE trade_date = ?", [PREV]).fetchone() == before
    written = con.execute("SELECT source, turnover, stock_name FROM fact_stock_daily "
                          "WHERE trade_date = ? LIMIT 1", [TD]).fetchone()
    assert written[0] == "hithink:daily-k-10d" and written[1] is None


def test_apply_is_atomic_on_failure() -> None:
    """写入中途失败必须整体回滚，不留半天数据。"""
    con = _con(_codes(3))
    _seed_canonical(con, _codes(3), PREV)
    plan = build_bridge_day(con, TD)
    plan["rows"][1] = plan["rows"][1][:3] + ("不是数字",) + plan["rows"][1][4:]
    with pytest.raises(Exception):
        apply_bridge_day(con, plan)
    assert con.execute("SELECT count(*) FROM fact_stock_daily WHERE trade_date = ?",
                       [TD]).fetchone()[0] == 0
    assert con.execute("SELECT count(*) FROM fact_stock_daily WHERE trade_date = ?",
                       [PREV]).fetchone()[0] == 3


def test_fingerprint_is_order_independent() -> None:
    """指纹不得随行写入顺序变化。

    原实现用 sum(close) 浮点求和，而浮点加法不满足结合律、DuckDB 又并行
    分片聚合，实测同一份未改动数据连跑 5 次出 3 个值，导致越界守卫随机误报。
    """
    codes = _codes(6)
    # 价格按代码固定（不按插入位置），只变插入顺序——否则变的是数据不是顺序。
    price = {code: 10.0 + i * 0.1 for i, code in enumerate(codes)}
    a, b = duckdb.connect(), duckdb.connect()
    a.execute(_SCHEMA)
    b.execute(_SCHEMA)
    for con, order in ((a, codes), (b, list(reversed(codes)))):
        for code in order:
            _seed_canonical(con, [code], PREV, close=price[code])
    assert bridge._day_fingerprints(a) == bridge._day_fingerprints(b)
    assert isinstance(bridge._day_fingerprints(a)[PREV][1], int)


def test_boundary_violation_rolls_back_instead_of_only_warning(monkeypatch) -> None:
    """越界校验必须在 COMMIT 之前：否则只能报警，脏数据已经落地了。"""
    con = _con(_codes(3))
    _seed_canonical(con, _codes(3), PREV)
    plan = build_bridge_day(con, TD)
    calls = {"n": 0}
    real = bridge._day_fingerprints

    def fake(c):
        calls["n"] += 1
        out = real(c)
        return {**out, PREV: (999, 999)} if calls["n"] == 1 else out

    monkeypatch.setattr(bridge, "_day_fingerprints", fake)
    with pytest.raises(BridgeRefused, match="写入越界"):
        apply_bridge_day(con, plan)
    assert con.execute("SELECT count(*) FROM fact_stock_daily WHERE trade_date = ?",
                       [TD]).fetchone()[0] == 0
    assert con.execute("SELECT count(*) FROM fact_stock_daily WHERE trade_date = ?",
                       [PREV]).fetchone()[0] == 3


def test_plan_never_claims_production_ready() -> None:
    """构造通过 ≠ 可发布：换库另需授权，这个标志不许被本模块翻成 True。"""
    con = _con(_codes(3))
    plan = build_bridge_day(con, TD)
    assert plan["production_ready"] is False
    assert plan["policy"]["policy_version"] == "hithink-bridge-policy-v1"
    assert plan["policy"]["turnover"] == "null_not_provided_by_vendor"


def test_absent_codes_are_reported_not_silently_dropped() -> None:
    """昨天在、今天供应商没给的票必须如实报出。

    不报的话，「停牌」和「供应商漏收」在下游长得一模一样——而两者
    对分母的处置完全不同。实例：09-18 的 688496.SH 是停牌形态。
    """
    # 宽度取 100：1 只停牌占比 ~1%，落在范围漂移守卫的 3% 容差内。
    con = _con(_codes(100))
    _seed_canonical(con, [*_codes(100), "688496.SH"], PREV)
    plan = build_bridge_day(con, TD)
    assert plan["absent_from_vendor"] == ["688496.SH"]
    assert plan["absent_count"] == 1
    assert "688496.SH" not in {r[1] for r in plan["rows"]}   # 不造 K 线


def test_unknown_nontrading_policy_is_refused() -> None:
    """政策标签必须有代码兑现；认不出的值一律拒跑，而不是当默认值忽略。"""
    con = _con(_codes(3))
    with pytest.raises(BridgeRefused, match="未知停牌政策"):
        build_bridge_day(con, TD, policy=BridgePolicy(nontrading="drop_silently"))
