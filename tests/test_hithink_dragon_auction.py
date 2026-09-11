"""同花顺龙虎榜 / 热榜 / 竞价（工单 #41 D）。夹具自造响应，不碰真 key。"""

from __future__ import annotations

import inspect
from datetime import date

import duckdb
import pytest

from market_feature_store.hithink_client import HithinkAPIError
from market_feature_store.sync import sync_daily_full
from market_feature_store.sync import sync_hithink_dragon_auction as htd


DDL = [
    """
    CREATE TABLE fact_dragon_tiger_hithink (
        trade_date DATE, stock_ts_code TEXT, ticker TEXT, pct_chg DOUBLE,
        buy_value DOUBLE, sell_value DOUBLE, net_value DOUBLE, net_rate DOUBLE,
        org_net_value DOUBLE, hot_money_net_value DOUBLE, hot_rank INTEGER,
        range_days INTEGER, limit_reason TEXT, source TEXT, updated_at TIMESTAMP,
        PRIMARY KEY (trade_date, stock_ts_code)
    )
    """,
    """
    CREATE TABLE fact_dragon_hot_money_hithink (
        trade_date DATE, hot_money_name TEXT, stock_ts_code TEXT, ticker TEXT,
        group_buying DOUBLE, buy_value DOUBLE, sell_value DOUBLE, net_value DOUBLE,
        net_rate DOUBLE, org_net_value DOUBLE, hot_money_net_value DOUBLE,
        hot_money_item_net_value DOUBLE, hot_money_item_net_rate DOUBLE,
        hot_rank INTEGER, range_days INTEGER, source TEXT, updated_at TIMESTAMP,
        PRIMARY KEY (trade_date, hot_money_name, stock_ts_code)
    )
    """,
    """
    CREATE TABLE fact_hot_stock_rank_hithink (
        trade_date DATE, stock_ts_code TEXT, ticker TEXT, rank INTEGER,
        source TEXT, updated_at TIMESTAMP,
        PRIMARY KEY (trade_date, stock_ts_code)
    )
    """,
    """
    CREATE TABLE fact_auction_hithink (
        trade_date DATE, stock_ts_code TEXT, kind TEXT, ticker TEXT,
        auction_price DOUBLE, auction_pct DOUBLE, auction_volume DOUBLE,
        auction_amount DOUBLE, auction_unmatched DOUBLE,
        auction_turnover_pct DOUBLE, auction_yesterday_ratio_pct DOUBLE,
        auction_volume_ratio DOUBLE, pre_close_price DOUBLE, open_price DOUBLE,
        last_price DOUBLE, float_market_cap DOUBLE, tags TEXT,
        source TEXT, updated_at TIMESTAMP,
        PRIMARY KEY (trade_date, stock_ts_code, kind)
    )
    """,
    "CREATE TABLE fact_stock_daily_hithink (trade_date DATE, stock_ts_code TEXT)",
    "CREATE TABLE fact_dragon_tiger_daily (trade_date DATE, stock_ts_code TEXT, net_amount DOUBLE)",
    """
    CREATE TABLE fact_dragon_seat_daily (
        trade_date DATE, stock_ts_code TEXT, seat_type TEXT, hm_name TEXT, exalter TEXT
    )
    """,
]


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "mfs.duckdb"
    con = duckdb.connect(str(path))
    try:
        for ddl in DDL:
            con.execute(ddl)
        con.executemany(
            "INSERT INTO fact_stock_daily_hithink VALUES (?,?)",
            [(date(2026, 9, 7), "000001.SZ"), (date(2026, 9, 8), "000001.SZ")],
        )
        con.execute(
            "INSERT INTO fact_dragon_tiger_daily VALUES (?, ?, ?)",
            [date(2026, 9, 8), "000001.SZ", 1.5],
        )
        con.execute(
            "INSERT INTO fact_dragon_seat_daily VALUES (?, ?, ?, ?, ?)",
            [date(2026, 9, 8), "000001.SZ", "游资", "赵老哥", "某营业部"],
        )
    finally:
        con.close()
    return path


def _getter():
    calls: list[tuple] = []

    def get_json(path, params=None, **_k):
        params = params or {}
        calls.append((path, dict(params)))
        if path.endswith("/dragon-tiger-list"):
            if params.get("board_type") == "hot_money":
                return {
                    "code": 0,
                    "data": {
                        "hot_money_items": [
                            {
                                "name": "赵老哥",
                                "buying": 2.0e8,
                                "rows": [
                                    {
                                        "thscode": "000001.SZ",
                                        "ticker": "000001",
                                        "name": "不该落库",
                                        "buy_value": 2.0e8,
                                        "sell_value": 0.5e8,
                                        "net_value": 1.5e8,
                                        "net_rate": 0.1,
                                        "org_net_value": 0,
                                        "hot_money_net_value": 1.5e8,
                                        "hot_money_item_net_value": 1.5e8,
                                        "hot_money_item_net_rate": 0.1,
                                        "hot_rank": 1,
                                        "range_days": 1,
                                    }
                                ],
                            }
                        ]
                    },
                }
            return {
                "code": 0,
                "data": {
                    "stock_items": [
                        {
                            "thscode": "000001.SZ",
                            "ticker": "000001",
                            "name": "不该落库",
                            "concept_list": ["银行"],
                            "change": 5.0,
                            "buy_value": 3.0e8,
                            "sell_value": 1.5e8,
                            "net_value": 1.5e8,
                            "net_rate": 0.1,
                            "org_net_value": 0.0,
                            "hot_money_net_value": 1.5e8,
                            "hot_rank": 3,
                            "range_days": 1,
                            "limit_reason": "测试",
                        }
                    ]
                },
            }
        if path.endswith("/hot-stock-list-history"):
            return {
                "code": 0,
                "data": {
                    "item": [
                        {
                            "thscode": "000001.SZ",
                            "ticker": "000001",
                            "name": "不该落库",
                            "rank": 1,
                        }
                    ]
                },
            }
        if path.endswith("/short-term-benchmark"):
            return {
                "code": 0,
                "data": {
                    "item": [
                        {
                            "thscode": "000001.SZ",
                            "ticker": "000001",
                            "name": "不该落库",
                            "auction_pct": 3.2,
                            "tags": ["强"],
                        }
                    ]
                },
            }
        if path.endswith("/tickers/list"):
            return {
                "code": 0,
                "data": {
                    "item": [
                        {"thscode": "000001.SZ", "ticker": "000001", "name": "不该落库"}
                    ]
                },
            }
        if path.endswith("/snapshot"):
            codes = (params.get("thscodes") or "").split(",")
            assert len(codes) <= 100
            return {
                "code": 0,
                "data": {
                    "item": [
                        {
                            "thscode": "000001.SZ",
                            "ticker": "000001",
                            "name": "不该落库",
                            "auction_price": 10.0,
                            "auction_pct": 1.0,
                            "auction_volume": 100,
                            "auction_amount": 1.0e6,
                            "auction_unmatched": 0,
                            "auction_turnover_pct": 0.1,
                            "auction_yesterday_ratio_pct": 50.0,
                            "auction_volume_ratio": 1.2,
                            "pre_close_price": 9.9,
                            "open_price": 10.0,
                            "last_price": 10.0,
                            "float_market_cap": 1.0e11,
                        }
                    ]
                },
            }
        raise AssertionError(path)

    get_json.calls = calls  # type: ignore[attr-defined]
    return get_json


def test_requested_fields_are_read() -> None:
    src = inspect.getsource(htd)
    for field in (
        htd.DRAGON_STOCK_FIELDS
        + htd.HOT_MONEY_GROUP_FIELDS
        + htd.HOT_MONEY_ROW_FIELDS
        + htd.HOT_RANK_FIELDS
        + htd.BENCH_FIELDS
        + htd.SNAP_FIELDS
    ):
        assert f'"{field}"' in src or f"'{field}'" in src, field
    assert htd.PATH_DRAGON in src
    assert htd.PATH_HOT in src
    assert htd.PATH_BENCH in src
    assert htd.PATH_SNAP in src


def test_code_1003_is_empty() -> None:
    def getter(path, params=None, **_k):
        raise HithinkAPIError(
            "hithink /api/a-share/special-data/dragon-tiger-list "
            "http=200 code=1003 超出范围"
        )

    assert htd.fetch_dragon_all(date(2024, 1, 2), getter) == []


def test_ingest_fingerprint_no_name(db_path, monkeypatch) -> None:
    monkeypatch.setattr(htd, "init_db", lambda con: None)
    getter = _getter()
    first = htd.sync_hithink_dragon_auction(
        mode="full",
        db_path=db_path,
        end_date=date(2026, 9, 8),
        dates=[date(2026, 9, 8)],
        get_json_fn=getter,
        today=date(2026, 9, 8),
        compare=True,
    )
    assert first["rows_written"]["dragon"] == 1
    assert first["rows_written"]["hot_money"] == 1
    assert first["rows_written"]["hot_rank"] == 1
    assert first["rows_written"]["benchmark"] == 1
    assert first["rows_written"]["snapshot"] == 1
    assert first["net_compare"]["compared"] == 1
    assert first["net_compare"]["unit"] == "yi"
    assert first["hot_money_compare"]["matched"] == 1
    second = htd.sync_hithink_dragon_auction(
        mode="full",
        db_path=db_path,
        end_date=date(2026, 9, 8),
        dates=[date(2026, 9, 8)],
        get_json_fn=getter,
        today=date(2026, 9, 8),
        skip_auction_snapshot=True,
        compare=False,
    )
    assert second["fingerprint"] == first["fingerprint"]
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        for table in (
            "fact_dragon_tiger_hithink",
            "fact_dragon_hot_money_hithink",
            "fact_hot_stock_rank_hithink",
            "fact_auction_hithink",
        ):
            cols = [
                r[0]
                for r in con.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name=?",
                    [table],
                ).fetchall()
            ]
            assert "name" not in cols, table
        money = con.execute(
            "SELECT hot_money_name FROM fact_dragon_hot_money_hithink"
        ).fetchone()[0]
        leaked = con.execute(
            """
            SELECT COUNT(*) FROM fact_dragon_tiger_hithink
            WHERE CAST(stock_ts_code AS VARCHAR) LIKE '%不该%'
            """
        ).fetchone()[0]
    finally:
        con.close()
    assert money == "赵老哥"
    assert leaked == 0
    snap_calls = [c for c in getter.calls if c[0].endswith("/snapshot")]
    assert snap_calls
    assert len(snap_calls[0][1]["thscodes"].split(",")) <= 100


def test_skip_without_key(monkeypatch) -> None:
    monkeypatch.setattr(htd, "has_api_key", lambda: False)
    assert htd.skip_reason_if_no_key() == "no-key"


def test_daily_full_schedules_after_limit() -> None:
    src = inspect.getsource(sync_daily_full.run_daily_update)
    assert src.index("sync-hithink-limit-pools") < src.index(
        "sync-hithink-dragon-auction"
    )


def test_daily_full_step_skips_without_key(monkeypatch) -> None:
    monkeypatch.setattr(
        "market_feature_store.sync.sync_hithink_dragon_auction.skip_reason_if_no_key",
        lambda: "no-key",
    )
    assert sync_daily_full.run_hithink_dragon_auction_step() == {
        "skipped": True,
        "reason": "no-key",
    }


def test_snapshot_refuses_to_stamp_a_non_today_date(db_path, monkeypatch) -> None:
    """终态快照端点没有日期参数，永远返回「当前」那一份。

    --end-date 指到过去（或跨零点跑）时不能把今天的竞价盖上别人的日戳，
    否则就是「回补出来的每一天都长着今天的值」那类静默污染。
    """
    monkeypatch.setattr(htd, "init_db", lambda con: None)
    out = htd.sync_hithink_dragon_auction(
        mode="full",
        db_path=db_path,
        end_date=date(2026, 9, 8),
        dates=[date(2026, 9, 8)],
        get_json_fn=_getter(),
        today=date(2026, 9, 9),
    )
    assert out["rows_written"]["snapshot"] == 0
    assert "2026-09-08" in out["snapshot_skipped"]
    con = duckdb.connect(str(db_path))
    try:
        assert con.execute(
            "SELECT COUNT(*) FROM fact_auction_hithink WHERE kind = 'snapshot'"
        ).fetchone()[0] == 0
        # 风向标有 date 参数，不受这条守卫影响
        assert con.execute(
            "SELECT COUNT(*) FROM fact_auction_hithink WHERE kind = 'benchmark'"
        ).fetchone()[0] == 1
    finally:
        con.close()
