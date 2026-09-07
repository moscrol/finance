"""fact_stock_daily 日内价量列（open/high/low/volume）：两条写入器都要落、老库能补列、只补 OHLC 不碰东财行。

起因（2026-09-07 双轨对账）：fupanhui 新高家数按日内最高价算，我们只有收盘价，差 ±20%；
剥离 fupanhui 的前提是自己的底数据带 OHLC。同批修掉 mootdx 名字带 \\x00 填充的老毛病。
"""
from __future__ import annotations

from datetime import datetime

import duckdb
import pandas as pd
import pytest

from market_feature_store.db import init_db
from market_feature_store.sync import sync_eastmoney_stock_snapshot as em
from market_feature_store.sync import sync_mootdx_stock_daily as mx


def _bars():
    return pd.DataFrame(
        {
            "datetime": ["2026-09-01", "2026-09-02", "2026-09-03"],
            "open": [10.0, 10.5, 11.0],
            "high": [10.8, 11.2, 11.9],
            "low": [9.9, 10.4, 10.9],
            "close": [10.5, 11.0, 11.8],
            "vol": [12345.0, 23456.0, 34567.0],
            "amount": [1.2e8, 2.3e8, 3.4e8],
        }
    )


class TestMootdxRows:
    def test_rows_carry_ohlc_and_clean_name(self):
        rows = mx._build_rows(_bars(), "600000", "浦发银行\x00\x00", "2026-09-02", datetime(2026, 9, 7), "mootdx")
        assert len(rows) == 2 and len(rows[0]) == len(mx.COLS)
        row = dict(zip(mx.COLS, rows[0]))
        assert row["trade_date"] == "2026-09-02" and row["stock_name"] == "浦发银行"
        assert (row["open"], row["high"], row["low"], row["volume"]) == (10.5, 11.2, 10.4, 23456.0)
        assert row["pre_close"] == 10.5 and row["pct_chg"] == pytest.approx(4.76)
        assert row["amount"] == pytest.approx(2.3)  # 亿

    def test_end_date_limits_to_single_day(self):
        rows = mx._build_rows(_bars(), "600000", "浦发银行", "2026-09-02", datetime(2026, 9, 7), "mootdx", end_date="2026-09-02")
        assert [r[0] for r in rows] == ["2026-09-02"]

    def test_clean_name_strips_nul_padding(self):
        assert mx.clean_name("酒鬼酒\x00\x00") == "酒鬼酒"
        assert mx.clean_name(" ST沈化\x00 ") == "ST沈化"
        assert mx.clean_name(None) == ""


class TestSchemaAndUpsert:
    def test_ensure_columns_adds_to_legacy_table_idempotently(self):
        con = duckdb.connect()
        con.execute(
            "CREATE TABLE fact_stock_daily (trade_date DATE, stock_ts_code TEXT, stock_name TEXT, close DOUBLE, "
            "pre_close DOUBLE, pct_chg DOUBLE, amount DOUBLE, turnover DOUBLE, source TEXT, updated_at TIMESTAMP, "
            "PRIMARY KEY (trade_date, stock_ts_code))"
        )
        mx.ensure_stock_daily_columns(con)
        mx.ensure_stock_daily_columns(con)
        cols = {r[0] for r in con.execute("DESCRIBE fact_stock_daily").fetchall()}
        assert set(mx.OHLC_COLUMNS) <= cols

    def test_schema_sql_declares_ohlc(self):
        con = duckdb.connect()
        init_db(con)
        cols = {r[0] for r in con.execute("DESCRIBE fact_stock_daily").fetchall()}
        assert set(mx.OHLC_COLUMNS) <= cols and set(mx.COLS) <= cols

    def _seed_eastmoney_row(self, con):
        con.execute(
            "INSERT INTO fact_stock_daily (trade_date, stock_ts_code, stock_name, close, pre_close, pct_chg, amount, "
            "turnover, source, updated_at) VALUES ('2026-09-02', '600000.SH', '浦发银行', 11.0, 10.55, 4.27, 2.31, 1.2, "
            "'eastmoney:snapshot', '2026-09-02 18:31:00')"
        )

    def test_ohlc_only_upsert_leaves_eastmoney_fields_alone(self):
        con = duckdb.connect()
        init_db(con)
        self._seed_eastmoney_row(con)
        rows = mx._build_rows(_bars(), "600000", "浦发银行\x00", "2026-09-01", datetime(2026, 9, 7), "mootdx")
        _buf_df = pd.DataFrame(rows, columns=mx.COLS)
        con.register("_buf_df", _buf_df)
        con.execute(mx.BULK_UPSERT_OHLC_ONLY_SQL)
        con.unregister("_buf_df")
        got = con.execute(
            "SELECT close, pre_close, pct_chg, source, stock_name, high, volume FROM fact_stock_daily WHERE trade_date='2026-09-02'"
        ).fetchone()
        assert got[:5] == (11.0, 10.55, 4.27, "eastmoney:snapshot", "浦发银行")  # 东财字段一字未动
        assert got[5] == 11.2 and got[6] == 23456.0  # OHLC 补上了
        # 没有的日期整行新增（历史回拉）
        assert con.execute("SELECT source, high FROM fact_stock_daily WHERE trade_date='2026-09-01'").fetchone() == ("mootdx", 10.8)

    def test_full_upsert_keeps_existing_ohlc_when_source_has_none(self):
        con = duckdb.connect()
        init_db(con)
        self._seed_eastmoney_row(con)
        con.execute("UPDATE fact_stock_daily SET high = 11.2, volume = 1.0 WHERE trade_date='2026-09-02'")
        row = ("2026-09-02", "600000.SH", "浦发银行", 11.0, 10.5, 4.76, 2.3, None, "mootdx", datetime(2026, 9, 7), None, None, None, None)
        _buf_df = pd.DataFrame([row], columns=mx.COLS)
        con.register("_buf_df", _buf_df)
        con.execute(mx.BULK_UPSERT_SQL)
        con.unregister("_buf_df")
        got = con.execute("SELECT source, pre_close, high, volume FROM fact_stock_daily WHERE trade_date='2026-09-02'").fetchone()
        assert got == ("mootdx", 10.5, 11.2, 1.0)  # 全量 upsert 换了来源字段，但没把已有 OHLC 抹成 NULL


class TestEastmoneyOhlc:
    def test_requested_ohlc_fields_land(self, monkeypatch: pytest.MonkeyPatch):
        captured: dict[str, object] = {}

        class _Con:
            def execute(self, *a, **k):
                return self

            def fetchone(self):
                return (0, 0, None, None)

            def register(self, name, df):
                captured[name] = df

            def unregister(self, *a, **k):
                return None

            def close(self):
                return None

        monkeypatch.setattr(em, "init_db", lambda *a, **k: None)
        monkeypatch.setattr(em, "connect", lambda *a, **k: _Con())
        monkeypatch.setattr(em, "ensure_stock_daily_columns", lambda con: None)
        monkeypatch.setattr(
            em,
            "fetch_snapshot",
            lambda **k: [{"f12": "600000", "f14": "浦发银行", "f2": 11.0, "f3": 4.27, "f18": 10.55, "f6": 2.31e8,
                          "f8": 1.2, "f17": 10.6, "f15": 11.2, "f16": 10.5, "f5": 231000}],
        )
        em.sync_fact_stock_daily_snapshot(trade_date="2026-09-02")
        df = captured["_buf_df"]
        assert list(df.columns) == mx.COLS
        r = df.iloc[0]
        assert (r["open"], r["high"], r["low"], r["volume"]) == (10.6, 11.2, 10.5, 231000)
        for f in ("f17", "f15", "f16", "f5"):
            assert f in em.EM_FIELDS
