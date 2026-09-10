from __future__ import annotations

import json
from datetime import date

import duckdb

from market_feature_store import db
from market_feature_store.sync import sync_polymarket_macro_odds as pm_sync


def _connect_test_db(path):
    def connect(read_only: bool = False):
        return duckdb.connect(str(path), read_only=read_only)

    return connect


def _init_test_db(path):
    def init_db():
        con = duckdb.connect(str(path))
        try:
            con.execute(db.SCHEMA_PATH.read_text(encoding="utf-8"))
        finally:
            con.close()

    return init_db


def _rows(db_path):
    con = duckdb.connect(str(db_path))
    try:
        return con.execute(
            "SELECT trade_date, event_id, market_id, tag, outcome, probability, "
            "volume, end_date, source FROM fact_polymarket_macro_odds_daily "
            "ORDER BY market_id, outcome"
        ).fetchall()
    finally:
        con.close()


def _event(event_id, tags, markets):
    return {"id": event_id, "title": "t", "tags": [{"label": t} for t in tags], "markets": markets}


def _market(market_id, question, outcomes, prices, volume=100.0, end_date="2026-12-31T00:00:00Z"):
    return {
        "id": market_id,
        "conditionId": f"0x{market_id}",
        "question": question,
        "outcomes": json.dumps(outcomes),
        "outcomePrices": json.dumps(prices),
        "volume": volume,
        "volume24hr": 10.0,
        "endDate": end_date,
    }


# 默认 _market 的 endDate 是 2026-12-31，下面不关心过期的用例都显式传 as_of
# 钉在这个日子之前，否则 2027 年这些用例会因为“测试数据过期了”集体变红。
_AS_OF = date(2026, 9, 10)


def test_matched_tag_is_case_insensitive_and_whitelist_only():
    assert pm_sync._matched_tag(_event("1", ["Geopolitics", "Sports"], [])) == "Geopolitics"
    assert pm_sync._matched_tag(_event("2", ["Sports", "Awards"], [])) is None
    assert pm_sync._matched_tag(_event("3", ["FED"], [])) == "FED"


def test_fetch_relevant_markets_filters_and_parses_outcomes(monkeypatch):
    page1 = [
        _event(
            "e1", ["Geopolitics"],
            [_market("m1", "Will X happen?", ["Yes", "No"], ["0.62", "0.38"])],
        ),
        _event(
            "e2", ["Sports"],  # not in whitelist, must be dropped
            [_market("m2", "Who wins?", ["A", "B"], ["0.5", "0.5"])],
        ),
    ]

    def fake_get(path, params, timeout=None, deadline=None):
        assert path == "/events"
        if params["offset"] == 0:
            return page1
        return []

    monkeypatch.setattr(pm_sync, "_get", fake_get)
    monkeypatch.setattr(pm_sync, "_PAGE_PAUSE_S", 0)

    records, truncated = pm_sync.fetch_relevant_markets(pages=3, page_size=100, as_of=_AS_OF)

    assert truncated is False
    assert len(records) == 2  # m1 has 2 outcomes, m2 dropped entirely
    assert {r["outcome"] for r in records} == {"Yes", "No"}
    assert all(r["market_id"] == "m1" for r in records)
    assert all(r["tag"] == "Geopolitics" for r in records)
    yes = next(r for r in records if r["outcome"] == "Yes")
    assert yes["probability"] == 0.62
    assert yes["end_date"] == date(2026, 12, 31)


def test_expired_markets_are_dropped_because_upstream_closed_flag_lies(monkeypatch):
    """回归：2026-09-10 实测 `closed=false` 里 328/1106 行已过期、概率退化 0/1。

    过期市场的历史累计成交量很大，按 volume 排序会直接占据头部，而它们
    长得跟前瞻概率一模一样——必须在入库前就挡掉，不能交给下游记得过滤。
    """
    events = [
        _event(
            "e1", ["Geopolitics"],
            [
                # 已结算的旧市场：截止日早于快照日、成交量最大、概率退化
                _market("old", "Netanyahu out by March 31?", ["Yes", "No"],
                        ["0", "1"], volume=1e8, end_date="2026-04-01T00:00:00Z"),
                # 前瞻市场：保留
                _market("live", "Rate cut in Q4?", ["Yes", "No"],
                        ["0.6", "0.4"], end_date="2026-12-31T00:00:00Z"),
                # 当日到期：当天还在交易，保留
                _market("today", "Resolves today?", ["Yes", "No"],
                        ["0.5", "0.5"], end_date="2026-09-10T00:00:00Z"),
                # 上游没给 endDate：无法判定，保留
                _market("nodate", "No end date?", ["Yes", "No"],
                        ["0.3", "0.7"], end_date=None),
            ],
        ),
    ]
    monkeypatch.setattr(pm_sync, "_get", lambda path, params, timeout=None, deadline=None: events)

    records, truncated = pm_sync.fetch_relevant_markets(as_of=date(2026, 9, 10))

    assert truncated is False
    assert {r["market_id"] for r in records} == {"live", "today", "nodate"}
    assert all(r["market_id"] != "old" for r in records)


def test_is_expired_boundary():
    today = date(2026, 9, 10)
    assert pm_sync._is_expired(date(2026, 9, 9), today) is True
    assert pm_sync._is_expired(date(2026, 9, 10), today) is False  # 当天还在交易
    assert pm_sync._is_expired(date(2026, 9, 11), today) is False
    assert pm_sync._is_expired(None, today) is False  # 无法判定不丢


def test_sync_writes_rows_with_snapshot_trade_date(tmp_path, monkeypatch):
    db_path = tmp_path / "market_feature_store.duckdb"
    monkeypatch.setattr(pm_sync, "connect", _connect_test_db(db_path))
    monkeypatch.setattr(pm_sync, "init_db", _init_test_db(db_path))
    monkeypatch.setattr(
        pm_sync,
        "fetch_relevant_markets",
        lambda: (
            [
                {
                    "event_id": "e1", "market_id": "m1", "condition_id": "0xm1",
                    "tag": "Fed", "question": "Rate cut in Q4?", "outcome": "Yes",
                    "probability": 0.7, "volume": 5000.0, "volume_24hr": 12.0,
                    "end_date": date(2026, 12, 31),
                },
            ],
            False,
        ),
    )

    result = pm_sync.sync("2026-09-10")

    assert result == {"rows": 1, "tags_hit": {"Fed": 1}, "truncated": False}
    rows = _rows(db_path)
    assert rows == [
        (date(2026, 9, 10), "e1", "m1", "Fed", "Yes", 0.7, 5000.0, date(2026, 12, 31), pm_sync.SOURCE),
    ]


def test_sync_defaults_trade_date_to_today_when_omitted(tmp_path, monkeypatch):
    db_path = tmp_path / "market_feature_store.duckdb"
    monkeypatch.setattr(pm_sync, "connect", _connect_test_db(db_path))
    monkeypatch.setattr(pm_sync, "init_db", _init_test_db(db_path))
    monkeypatch.setattr(
        pm_sync,
        "fetch_relevant_markets",
        lambda: (
            [
                {
                    "event_id": "e1", "market_id": "m1", "condition_id": "0xm1",
                    "tag": "Crypto", "question": "BTC above 100k?", "outcome": "Yes",
                    "probability": 0.4, "volume": 1.0, "volume_24hr": None,
                    "end_date": None,
                },
            ],
            False,
        ),
    )

    result = pm_sync.sync()

    assert result["rows"] == 1
    rows = _rows(db_path)
    assert rows[0][0] == date.today()


def test_sync_reports_zero_rows_when_nothing_matches(tmp_path, monkeypatch):
    db_path = tmp_path / "market_feature_store.duckdb"
    monkeypatch.setattr(pm_sync, "connect", _connect_test_db(db_path))
    monkeypatch.setattr(pm_sync, "init_db", _init_test_db(db_path))
    monkeypatch.setattr(pm_sync, "fetch_relevant_markets", lambda: ([], False))

    result = pm_sync.sync("2026-09-10")

    assert result == {"rows": 0, "tags_hit": {}, "truncated": False}


def test_fetch_returns_partial_and_flags_truncated_when_upstream_stalls(monkeypatch):
    """回归：2026-09-10 实测 gamma-api 连发第二页会挂住且 socket 超时不触发。

    第一页拿到的数据必须留下并标 truncated，不能整批丢掉，也不能假装完整。
    """
    page0 = [
        _event("e1", ["Fed"], [_market("m1", "Rate cut?", ["Yes", "No"], ["0.6", "0.4"])]),
    ]

    attempts = {"n": 0}

    def fake_get(path, params, timeout=None, deadline=None):
        if params["offset"] == 0:
            return page0
        attempts["n"] += 1
        raise pm_sync.PolymarketTimeout("时长预算耗尽")

    monkeypatch.setattr(pm_sync, "_get", fake_get)
    monkeypatch.setattr(pm_sync, "_PAGE_PAUSE_S", 0)
    monkeypatch.setattr(pm_sync, "_RETRY_PAUSE_S", 0)

    # page_size=1 让第一页"满页"，分页才会继续到第二页（满页才翻页是正常行为）
    records, truncated = pm_sync.fetch_relevant_markets(pages=3, page_size=1, as_of=_AS_OF)

    assert truncated is True
    assert len(records) == 2  # 第一页的两个 outcome 保留
    assert {r["outcome"] for r in records} == {"Yes", "No"}
    # 死活不通才放弃：重试抽干了才标 truncated，不是一挂就认输
    assert attempts["n"] == pm_sync._MAX_ATTEMPTS


def test_transient_stall_is_retried_instead_of_losing_the_whole_day(monkeypatch):
    """回归：挂住是随机的（实测 8 次中 3 挂）且重试立马就成。

    不重试的旧行为：默认只拉 1 页，第一个请求一挂就返回 0 行——夜跑大约
    1/3 的夜晚整天没数据。重试成本 ~4s，必须重试。
    """
    page0 = [_event("e1", ["Fed"], [_market("m1", "Rate cut?", ["Yes", "No"], ["0.6", "0.4"])])]
    calls = {"n": 0}

    def flaky_get(path, params, timeout=None, deadline=None):
        calls["n"] += 1
        if calls["n"] == 1:  # 第一次挂住，第二次正常
            raise pm_sync.PolymarketTimeout("时长预算耗尽，已读 524288 字节")
        return page0

    monkeypatch.setattr(pm_sync, "_get", flaky_get)
    monkeypatch.setattr(pm_sync, "_RETRY_PAUSE_S", 0)

    records, truncated = pm_sync.fetch_relevant_markets(as_of=_AS_OF)

    assert truncated is False  # 重试成功不算部分快照
    assert len(records) == 2
    assert calls["n"] == 2
