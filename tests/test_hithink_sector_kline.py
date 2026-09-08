"""同花顺板块 / 指数日 K（工单 #41 B）。夹具自造响应，不碰真 key。"""

from __future__ import annotations

import inspect
from datetime import date

import duckdb
import pytest

from market_feature_store.hithink_client import shanghai_midnight_ms
from market_feature_store.sync import sync_daily_full
from market_feature_store.sync import sync_hithink_sector_kline as htb


DIM_DDL = """
CREATE TABLE dim_sector_hithink (
    sector_ts_code TEXT PRIMARY KEY,
    sector_name TEXT,
    category TEXT,
    constituent_count INTEGER,
    constituents_captured_at TIMESTAMP,
    source TEXT,
    updated_at TIMESTAMP
)
"""
KLINE_DDL = """
CREATE TABLE fact_sector_kline_daily (
    trade_date DATE,
    sector_ts_code TEXT,
    open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE,
    volume DOUBLE, turnover DOUBLE,
    source TEXT, updated_at TIMESTAMP,
    PRIMARY KEY (trade_date, sector_ts_code)
)
"""
CONST_DDL = """
CREATE TABLE fact_sector_constituent_hithink (
    captured_at DATE,
    sector_ts_code TEXT,
    stock_ts_code TEXT,
    ticker TEXT,
    in_index INTEGER,
    source TEXT, updated_at TIMESTAMP,
    PRIMARY KEY (captured_at, sector_ts_code, stock_ts_code)
)
"""
OLD_DDL = """
CREATE TABLE fact_sector_daily (
    trade_date DATE,
    sector_ts_code TEXT,
    sector_name TEXT,
    pct_chg DOUBLE
)
"""


def _empty_db(path) -> None:
    con = duckdb.connect(str(path))
    try:
        con.execute(DIM_DDL)
        con.execute(KLINE_DDL)
        con.execute(CONST_DDL)
        con.execute(OLD_DDL)
    finally:
        con.close()


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "mfs.duckdb"
    _empty_db(path)
    return path


def _bar(day: date, close: float) -> dict:
    return {
        "date_ms": shanghai_midnight_ms(day),
        "open_price": close - 0.1,
        "high_price": close + 0.2,
        "low_price": close - 0.2,
        "close_price": close,
        "volume": 1000.0,
        "turnover": 1.0e7,
    }


def _getter(end: date):
    d0 = end - __import__("datetime").timedelta(days=1)
    d1 = end

    def get_json(path, params=None, **_k):
        params = params or {}
        if path.endswith("/ths-index-list"):
            tag = params.get("tag")
            if tag == "cn_concept":
                return {
                    "code": 0,
                    "data": {
                        "item": [
                            {"thscode": "886053.TI", "name": "BC电池"},
                            {"thscode": "885725.TI", "name": "芯片概念"},
                        ]
                    },
                }
            return {"code": 0, "data": {"item": []}}
        if path.endswith("/historical"):
            code = params["thscode"]
            assert (params["end"] - params["start"]) / 86_400_000 < htb.MAX_WINDOW_DAYS
            if code == "000001.SH":
                return {"code": 0, "data": {"item": [_bar(d0, 3000.0), _bar(d1, 3030.0)]}}
            if code == "886053.TI":
                return {"code": 0, "data": {"item": [_bar(d0, 1000.0), _bar(d1, 1010.0)]}}
            if code == "885725.TI":
                return {"code": 0, "data": {"item": [_bar(d0, 2000.0), _bar(d1, 2020.0)]}}
            return {"code": 0, "data": {"item": []}}
        if path.endswith("/ths-stock-list"):
            return {
                "code": 0,
                "data": {
                    "item": [
                        {"thscode": "600000.SH", "ticker": "600000", "name": "不该落库"},
                    ]
                },
            }
        raise AssertionError(path)

    return get_json


def test_window_rejects_1500_days() -> None:
    with pytest.raises(htb.HithinkSectorSyncError):
        htb.window_ms(date(2026, 9, 8), 1500)
    start, end = htb.window_ms(date(2026, 9, 8), 1499)
    assert (end - start) / 86_400_000 < htb.MAX_WINDOW_DAYS


def test_requested_fields_are_read() -> None:
    src = inspect.getsource(htb)
    for field in htb.CATALOG_FIELDS + htb.HISTORICAL_BAR_FIELDS + htb.CONSTITUENT_FIELDS:
        assert f'"{field}"' in src or f"'{field}'" in src, field


def test_ingest_and_fingerprint(db_path, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(htb, "init_db", lambda con: None)
    end = date(2026, 9, 8)
    getter = _getter(end)
    first = htb.sync_hithink_sector_kline(
        mode="incremental",
        db_path=db_path,
        end_date=end,
        get_json_fn=getter,
        skip_constituents=False,
    )
    assert first["kline"]["codes"] >= 2
    assert first["kline"]["ohlc_nulls"] == 0
    assert first["constituent_rows"] >= 1
    second = htb.sync_hithink_sector_kline(
        mode="incremental",
        db_path=db_path,
        end_date=end,
        get_json_fn=getter,
        skip_constituents=True,
    )
    assert second["fingerprint"] == first["fingerprint"]
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        names = [
            r[0]
            for r in con.execute(
                "SELECT stock_ts_code FROM fact_sector_constituent_hithink"
            ).fetchall()
        ]
        cols = [
            r[0]
            for r in con.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='fact_sector_constituent_hithink'"
            ).fetchall()
        ]
    finally:
        con.close()
    assert "600000.SH" in names
    assert "name" not in cols


def test_fp_map_exact_only_no_fuzzy(db_path, monkeypatch) -> None:
    monkeypatch.setattr(htb, "init_db", lambda con: None)
    end = date(2026, 9, 8)
    con = duckdb.connect(str(db_path))
    try:
        con.executemany(
            "INSERT INTO fact_sector_daily VALUES (?,?,?,?)",
            [
                (end, "123456.FP", "BC电池", 1.0),
                (end, "111111.FP", "芯片", 1.0),  # 对不上「芯片概念」
                (end, "886053.TI", "BC电池旧名", 1.0),
            ],
        )
    finally:
        con.close()
    htb.sync_hithink_sector_kline(
        mode="incremental",
        db_path=db_path,
        end_date=end,
        get_json_fn=_getter(end),
        skip_constituents=True,
        compare=True,
        mapping_path=None,
    )
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        mapping = htb.map_fp_names(con)
    finally:
        con.close()
    matched_names = {name for _fp, name, _ti in mapping["matched"]}
    assert "BC电池" in matched_names
    assert "芯片" not in matched_names
    gap_names = {name for _fp, name, _reason in mapping["gaps"]}
    assert "芯片" in gap_names
    assert any(code == "886053.TI" for code, _old, _new in mapping["ti_name_diff"])


def test_compare_pct(db_path, monkeypatch) -> None:
    monkeypatch.setattr(htb, "init_db", lambda con: None)
    end = date(2026, 9, 8)
    prev = date(2026, 9, 7)
    con = duckdb.connect(str(db_path))
    try:
        con.executemany(
            "INSERT INTO fact_sector_daily VALUES (?,?,?,?)",
            [
                (end, "886053.TI", "BC电池", 1.0),  # 1000→1010 = 1%
            ],
        )
    finally:
        con.close()
    stats = htb.sync_hithink_sector_kline(
        mode="incremental",
        db_path=db_path,
        end_date=end,
        get_json_fn=_getter(end),
        skip_constituents=True,
        compare=True,
    )
    assert stats["pct_compare"]["compared"] >= 1
    assert stats["pct_compare"]["rate"] == 1.0
    assert prev  # 夹具两天，给对比用


def test_skip_without_key(monkeypatch) -> None:
    monkeypatch.setattr(htb, "has_api_key", lambda: False)
    assert htb.skip_reason_if_no_key() == "no-key"


def test_daily_full_schedules_after_stock() -> None:
    src = inspect.getsource(sync_daily_full.run_daily_update)
    assert src.index("sync-hithink-stock-daily") < src.index("sync-hithink-sector-kline")
    assert (
        "run_hithink_sector_kline_step"
        in sync_daily_full.run_daily_update.__code__.co_names
    )


def test_daily_full_step_skips_without_key(monkeypatch) -> None:
    monkeypatch.setattr(
        "market_feature_store.sync.sync_hithink_sector_kline.skip_reason_if_no_key",
        lambda: "no-key",
    )
    assert sync_daily_full.run_hithink_sector_kline_step() == {
        "skipped": True,
        "reason": "no-key",
    }
