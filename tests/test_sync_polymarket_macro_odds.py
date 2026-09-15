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


# --------------------------------------------------------------------------- #
# W6 · E-007 赔率半边验收：快照时点（as-of 完整性）与落库完整性
#
# spec  docs/superpowers/specs/2026-09-10-knevo-arch-delta-worklist.md W6：
#   「fact_polymarket_macro_odds_daily 另验两件事：快照时点（as-of 完整性）与
#     落库完整性，含已知洞 truncated 只印 stdout 未落库。」
#
# 这半边**不能替日历半边作数**（spec 同段）：赔率表的市场截止日是「交易截止」，
# 不是官方发布日，回答不了「最新一期 CPI 哪天发布」——那是 latest_known 的活。
# --------------------------------------------------------------------------- #
def test_trade_date_is_a_label_not_a_data_date(tmp_path, monkeypatch):
    """as-of 完整性：上游只有「此刻」快照，``trade_date`` 纯粹是标注日。

    传一个久远的日期也照写不误——**这不是回补历史的能力**。谁用 --trade-date 去
    补过去某天的赔率，拿到的是今天的价、盖上那天的戳。与 CLAUDE.md 里 daily-full
    「取最新」语义写到历史日是同一个坑（把今天盘中价写成那天收盘）。
    """
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
                    "tag": "Fed", "question": "Rate cut?", "outcome": "Yes",
                    "probability": 0.7, "volume": 1.0, "volume_24hr": None,
                    "end_date": date(2026, 12, 31),
                },
            ],
            False,
        ),
    )

    pm_sync.sync("2020-01-01")

    rows = _rows(db_path)
    # 行确实落在 2020-01-01 名下，但那一天 Polymarket 上根本没有这个市场。
    assert rows[0][0] == date(2020, 1, 1)
    # 表里没有任何字段能告诉下游「这份快照实际抓取于何时」——updated_at 是写入时刻，
    # 不是行情时刻，两者在回补场景下会差好几年。
    con = duckdb.connect(str(db_path))
    try:
        cols = {c[0] for c in con.execute("DESCRIBE fact_polymarket_macro_odds_daily").fetchall()}
    finally:
        con.close()
    assert "trade_date" in cols and "updated_at" in cols
    assert not any("snapshot" in c.lower() or "as_of" in c.lower() for c in cols)


def test_truncated_leaves_no_trace_in_the_table_known_gap(tmp_path, monkeypatch):
    """落库完整性 · **已知洞**：truncated 只在返回值/stdout，表里查不出来。

    后果：下游查表看到 N 行，分不清「今天上游只给了一半」和「今天就这么多」。
    与 CLAUDE.md 里 fast_daily_sync 同一个失败形状——行数正常、覆盖率审计正常、
    值却是残的，只有跨日期 diff 抓得到。

    本条**钉的是洞的现状，不是期望**。原作者已在
    docs/handoffs/2026-09-10-polymarket-macro-odds.md 标注「接夜跑前必须先补」。
    补上那天（表加列或落 ops 台账），这条会红——请改判据、更新 W6 验收，别删测试。
    """
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
                    "tag": "Fed", "question": "Rate cut?", "outcome": "Yes",
                    "probability": 0.7, "volume": 1.0, "volume_24hr": None,
                    "end_date": date(2026, 12, 31),
                },
            ],
            True,  # 上游中断，这只是部分快照
        ),
    )

    result = pm_sync.sync("2026-09-10")

    # 信息在返回值里（CLI 据此印「部分快照」到 stdout）……
    assert result["truncated"] is True and result["rows"] == 1
    # ……但表里既没有标志列，也没有任何一行记下这件事。
    con = duckdb.connect(str(db_path))
    try:
        cols = {c[0] for c in con.execute("DESCRIBE fact_polymarket_macro_odds_daily").fetchall()}
        tables = {t[0] for t in con.execute("SHOW TABLES").fetchall()}
    finally:
        con.close()
    assert not any(
        k in c.lower() for c in cols for k in ("trunc", "partial", "complete", "degraded")
    ), "truncated 落库了 → 洞已补，请更新 W6 验收判据（本测试按设计会在此刻变红）"
    assert not any("polymarket" in t.lower() and t != "fact_polymarket_macro_odds_daily" for t in tables), \
        "出现了 polymarket 的 ops 台账 → 洞已补，同上"


def test_truncated_with_zero_rows_is_indistinguishable_from_never_run(tmp_path, monkeypatch):
    """最糟形状：三次全挂 → 0 行 + truncated=True，sync 提前 return，库里一个字都没有。

    于是「今天上游全挂」与「今天压根没跑同步」在库里长得一模一样。
    原作者实测 5 次中过 1 次（handoff §「三次全挂仍会发生」）。
    """
    db_path = tmp_path / "market_feature_store.duckdb"
    monkeypatch.setattr(pm_sync, "connect", _connect_test_db(db_path))
    monkeypatch.setattr(pm_sync, "init_db", _init_test_db(db_path))
    monkeypatch.setattr(pm_sync, "fetch_relevant_markets", lambda: ([], True))

    result = pm_sync.sync("2026-09-10")

    assert result == {"rows": 0, "tags_hit": {}, "truncated": True}
    # 连库文件都没建起来——init_db 在 0 行分支之后才调用。
    assert not db_path.exists(), "0 行分支若开始建库/落痕，说明洞已补，请更新 W6 验收判据"
