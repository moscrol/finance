"""同花顺涨停 / 跌停 / 炸板池（工单 #41 C）。夹具自造响应，不碰真 key。"""

from __future__ import annotations

import inspect
from datetime import date

import duckdb
import pytest

from market_feature_store.hithink_client import HithinkAPIError, shanghai_midnight_ms
from market_feature_store.sync import sync_daily_full
from market_feature_store.sync import sync_hithink_limit_pools as htc


POOL_DDL = """
CREATE TABLE fact_limit_pool_hithink (
    trade_date DATE, pool TEXT, stock_ts_code TEXT, ticker TEXT,
    is_st BOOLEAN, is_new BOOLEAN, last_price DOUBLE, pct_chg DOUBLE,
    limit_up_time TEXT, limit_up_reason TEXT, continue_day_text TEXT,
    continue_day_cnt INTEGER, seal_money DOUBLE, max_seal_money DOUBLE,
    first_limit_time TEXT, last_limit_time TEXT,
    turnover_ratio_pct DOUBLE, open_times INTEGER, turnover DOUBLE,
    source TEXT, updated_at TIMESTAMP,
    PRIMARY KEY (trade_date, pool, stock_ts_code)
)
"""
CAL_DDL = """
CREATE TABLE fact_stock_daily_hithink (
    trade_date DATE, stock_ts_code TEXT
)
"""
MARKET_DDL = """
CREATE TABLE fact_market_daily (
    trade_date DATE PRIMARY KEY, limit_up INTEGER
)
"""
ADV_DDL = """
CREATE TABLE fact_limit_advance_daily (
    trade_date DATE, stock_ts_code TEXT, boards INTEGER
)
"""


def _empty_db(path) -> None:
    con = duckdb.connect(str(path))
    try:
        con.execute(POOL_DDL)
        con.execute(CAL_DDL)
        con.execute(MARKET_DDL)
        con.execute(ADV_DDL)
        con.executemany(
            "INSERT INTO fact_stock_daily_hithink VALUES (?,?)",
            [
                (date(2026, 9, 7), "000001.SZ"),
                (date(2026, 9, 8), "000001.SZ"),
            ],
        )
    finally:
        con.close()


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "mfs.duckdb"
    _empty_db(path)
    return path


def _up_item(code: str, *, boards: int = 2) -> dict:
    return {
        "thscode": code,
        "ticker": code.split(".")[0],
        "name": "不该落库",
        "is_st": False,
        "is_new": False,
        "last_price": 10.0,
        "price_change_ratio_pct": 10.0,
        "limit_up_time": "09:30:00",
        "limit_up_reason": "测试",
        "continue_day_text": f"{boards}连板",
        "continue_day_cnt": boards,
        "seal_money": 1.0e8,
        "max_seal_money": 2.0e8,
    }


def _down_item(code: str) -> dict:
    return {
        "thscode": code,
        "ticker": code.split(".")[0],
        "name": "不该落库",
        "last_price": 3.0,
        "price_change_ratio_pct": -10.0,
        "first_limit_time": "10:00:00",
        "last_limit_time": "14:00:00",
        "turnover_ratio_pct": 8.0,
    }


def _break_item(code: str) -> dict:
    return {
        "thscode": code,
        "ticker": code.split(".")[0],
        "name": "不该落库",
        "last_price": 9.0,
        "price_change_ratio_pct": 5.0,
        "open_times": 2,
        "turnover_ratio_pct": 20.0,
        "turnover": 5.0e8,
    }


def _payload(items, *, page: int = 1, pages: int = 1) -> dict:
    return {
        "code": 0,
        "data": {
            "item": items,
            "pagination": {
                "total": len(items) if pages == 1 else 2,
                "pages": pages,
                "size": 200,
                "page": page,
            },
        },
    }


def test_requested_fields_are_read() -> None:
    src = inspect.getsource(htc)
    for pool, fields in htc.FIELDS.items():
        for field in fields:
            assert f'"{field}"' in src or f"'{field}'" in src, f"{pool}.{field}"
    assert "/api/a-share/special-data/limit-up-pool" in src
    assert "/api/a-share/special-data/limit-down-pool" in src
    assert "/api/a-share/special-data/limit-break-pool" in src


def test_pages_gt_1_fetches_next_page() -> None:
    calls: list[int] = []

    def getter(path, params=None, **_k):
        assert path.endswith("/limit-up-pool")
        page = int(params["page"])
        calls.append(page)
        if page == 1:
            return _payload([_up_item("000001.SZ")], page=1, pages=2)
        return _payload([_up_item("000002.SZ")], page=2, pages=2)

    rows = htc.fetch_pool_day(htc.POOL_UP, date(2026, 9, 8), getter)
    assert calls == [1, 2]
    assert [row["thscode"] for row in rows] == ["000001.SZ", "000002.SZ"]


def test_empty_set_on_non_trading_day() -> None:
    def getter(path, params=None, **_k):
        return _payload([])

    assert htc.fetch_pool_day(htc.POOL_UP, date(2026, 9, 6), getter) == []


def test_code_1002_is_empty_not_error() -> None:
    def getter(path, params=None, **_k):
        raise HithinkAPIError(
            "hithink /api/a-share/special-data/limit-down-pool "
            "http=200 code=1002 超出范围"
        )

    assert htc.fetch_pool_day(htc.POOL_DOWN, date(2019, 9, 8), getter) == []


def test_code_5003_is_empty_not_error() -> None:
    def getter(path, params=None, **_k):
        raise HithinkAPIError(
            "hithink /api/a-share/special-data/limit-up-pool "
            "http=200 code=5003 hotspot_focus limit-up pool "
            "response contains missing ticker"
        )

    assert htc.fetch_pool_day(htc.POOL_UP, date(2022, 1, 10), getter) == []


def test_ingest_fingerprint_and_no_name(db_path, monkeypatch) -> None:
    monkeypatch.setattr(htc, "init_db", lambda con: None)
    calls: list[tuple[str, int, int]] = []

    def getter(path, params=None, **_k):
        params = params or {}
        day = date.fromisoformat("2026-09-08")
        if params.get("date_ms") == shanghai_midnight_ms(date(2026, 9, 7)):
            day = date(2026, 9, 7)
        pool = (
            "up"
            if path.endswith("limit-up-pool")
            else "down"
            if path.endswith("limit-down-pool")
            else "break"
        )
        calls.append((pool, params.get("page"), params.get("size")))
        assert params.get("size") == 200
        if pool == "up":
            suffix = "7" if day.day == 7 else "8"
            return _payload([_up_item(f"00000{suffix}.SZ", boards=2)])
        if pool == "down":
            return _payload([_down_item("000003.SZ")])
        return _payload([_break_item("000004.SZ")])

    first = htc.sync_hithink_limit_pools(
        mode="full",
        db_path=db_path,
        start=date(2026, 9, 7),
        end_date=date(2026, 9, 8),
        get_json_fn=getter,
        compare=False,
    )
    assert first["rows_written"] == 6
    assert first["empty_days"] == 0
    second = htc.sync_hithink_limit_pools(
        mode="full",
        db_path=db_path,
        start=date(2026, 9, 7),
        end_date=date(2026, 9, 8),
        get_json_fn=getter,
        compare=False,
    )
    assert second["fingerprint"] == first["fingerprint"]
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        cols = [
            r[0]
            for r in con.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='fact_limit_pool_hithink'"
            ).fetchall()
        ]
        names_as_codes = con.execute(
            "SELECT stock_ts_code, ticker, source FROM fact_limit_pool_hithink "
            "WHERE pool='limit_up' ORDER BY trade_date"
        ).fetchall()
        leaked = con.execute(
            "SELECT COUNT(*) FROM fact_limit_pool_hithink "
            "WHERE CAST(stock_ts_code AS VARCHAR) LIKE '%不该%'"
        ).fetchone()[0]
    finally:
        con.close()
    assert "name" not in cols
    assert leaked == 0
    assert names_as_codes[0][2] == "hithink:limit-up-pool"
    assert all(call[2] == 200 for call in calls)


def test_compare_counts_and_boards(db_path, monkeypatch) -> None:
    monkeypatch.setattr(htc, "init_db", lambda con: None)
    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            "INSERT INTO fact_market_daily VALUES (?, ?), (?, ?)",
            [date(2026, 9, 7), 1, date(2026, 9, 8), 1],
        )
        con.execute(
            "INSERT INTO fact_limit_advance_daily VALUES (?, ?, ?), (?, ?, ?)",
            [
                date(2026, 9, 7),
                "000007.SZ",
                2,
                date(2026, 9, 8),
                "000008.SZ",
                2,
            ],
        )
    finally:
        con.close()

    def getter(path, params=None, **_k):
        day = (
            date(2026, 9, 7)
            if params.get("date_ms") == shanghai_midnight_ms(date(2026, 9, 7))
            else date(2026, 9, 8)
        )
        if path.endswith("limit-up-pool"):
            code = "000007.SZ" if day.day == 7 else "000008.SZ"
            return _payload([_up_item(code, boards=2)])
        return _payload([])

    stats = htc.sync_hithink_limit_pools(
        mode="full",
        db_path=db_path,
        start=date(2026, 9, 7),
        end_date=date(2026, 9, 8),
        get_json_fn=getter,
        compare=True,
    )
    assert stats["count_compare"]["compared"] == 2
    assert stats["count_compare"]["rate"] == 1.0
    assert stats["boards_compare"]["compared"] == 2
    assert stats["boards_compare"]["rate"] == 1.0


def test_skip_without_key(monkeypatch) -> None:
    monkeypatch.setattr(htc, "has_api_key", lambda: False)
    assert htc.skip_reason_if_no_key() == "no-key"


def test_daily_full_schedules_after_sector() -> None:
    src = inspect.getsource(sync_daily_full.run_daily_update)
    assert src.index("sync-hithink-sector-kline") < src.index("sync-hithink-limit-pools")
    assert (
        "run_hithink_limit_pools_step"
        in sync_daily_full.run_daily_update.__code__.co_names
    )


def test_daily_full_step_skips_without_key(monkeypatch) -> None:
    monkeypatch.setattr(
        "market_feature_store.sync.sync_hithink_limit_pools.skip_reason_if_no_key",
        lambda: "no-key",
    )
    assert sync_daily_full.run_hithink_limit_pools_step() == {
        "skipped": True,
        "reason": "no-key",
    }
