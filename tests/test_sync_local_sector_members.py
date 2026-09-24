"""QC S1（2026-09-13）：hithink 源必须能过板块拼接的值源白名单。

修复后 09-11 主表 5,547 行 source=hithink:daily-k-10d；白名单不接它时，
修后克隆同条件拼接从 403 板块掉到 0（QC stitch-before-after 证据）。
本回归锁死：hithink 源行被 _today_values 接受；fallback 自派生源仍被拒。
"""
from __future__ import annotations

from datetime import date

import duckdb
import pytest

from market_feature_store.sync.sync_local_sector_members import (
    VALUE_SOURCE_PREFIXES,
    _today_values,
    build_rows,
)

DDL = """
CREATE TABLE fact_stock_daily (
    trade_date DATE, stock_ts_code VARCHAR, stock_name VARCHAR,
    close DOUBLE, pre_close DOUBLE, pct_chg DOUBLE, amount DOUBLE,
    turnover DOUBLE, source VARCHAR, updated_at TIMESTAMP,
    open DOUBLE, high DOUBLE, low DOUBLE, volume DOUBLE,
    PRIMARY KEY (trade_date, stock_ts_code)
)
"""

TD = date(2026, 9, 11)


@pytest.fixture()
def con():
    c = duckdb.connect(":memory:")
    c.execute(DDL)
    rows = [
        # 东财旧源（对照）
        (TD, "000001.SZ", "平安银行", 10.02, 10.0, 0.2, 50.1, 1.1,
         "eastmoney:snapshot", "2026-09-11 18:00:00", 9.9, 10.1, 9.8, 5000.0),
        # hithink 重建源（S1 修复后必须被接受）
        (TD, "302132.SZ", "中航成飞", 63.42, 64.35, -1.45, 5.9863, None,
         "hithink:daily-k-10d", "2026-09-13 02:00:00", 64.01, 64.66, 62.82,
         94471.0),
        # fallback 自派生源（循环回灌，必须仍被拒）
        (TD, "600000.SH", "浦发银行", 19.7, 19.5, 1.03, 30.0, 0.9,
         "fupanhui:sector_stock_daily:fallback", "2026-09-11 18:00:00",
         19.5, 19.8, 19.4, 3000.0),
        # hithink 源但字段不齐（amount NULL，必须仍被拒）
        (TD, "999001.SH", "缺额", 1.0, 1.0, 0.0, None, None,
         "hithink:daily-k-10d", "2026-09-13 02:00:00", 1.0, 1.0, 1.0, 100.0),
    ]
    c.executemany("INSERT INTO fact_stock_daily VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    yield c
    c.close()


def test_hithink_source_accepted_fallback_still_rejected(con):
    values = _today_values(con, TD)
    assert "000001.SZ" in values
    assert "302132.SZ" in values
    assert values["302132.SZ"]["price"] == 63.42
    assert values["302132.SZ"]["pct_chg"] == -1.45
    assert "600000.SH" not in values  # fallback 源仍循环回灌被拒
    assert "999001.SH" not in values  # 字段不齐仍被拒


def test_whitelist_includes_hithink_prefix():
    assert "hithink" in VALUE_SOURCE_PREFIXES


def test_stitch_uses_dated_name_not_old_identity_baseline(con):
    values = _today_values(con, TD)
    assert values["302132.SZ"]["stock_name"] == "中航成飞"
    members = [{"stock_ts_code": "302132.SZ", "stock_name": "旧简称"},
               {"stock_ts_code": "600001.SH", "stock_name": "停牌股"}]
    rows, dropped = build_rows(members, values, highs={}, limits={}, caps={})
    assert rows[0]["name"] == "中航成飞"
    assert dropped == ["600001.SH"]
    assert len(rows) == 1  # identity is retained externally, never as a null-value shell


def test_stitch_retains_baseline_name_only_when_dated_name_is_missing(con):
    values = _today_values(con, TD)
    values["302132.SZ"]["stock_name"] = None
    rows, _ = build_rows([{"stock_ts_code": "302132.SZ", "stock_name": "基线名"}],
                         values, highs={}, limits={}, caps={})
    assert rows[0]["name"] == "基线名"
