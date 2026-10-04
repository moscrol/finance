"""R-20260827-13: market-watch delivery uses the exchange calendar, not DB as its clock."""

from datetime import date, datetime
from zoneinfo import ZoneInfo
from pathlib import Path

import duckdb

from intelligence.services.ask import bind_market_watch_pack
from intelligence.services.ask_types import AskOptions
from intelligence.services.market_watch_pack import (
    MARKET_DATA_READY_HOUR,
    REQUIRED_BAGS,
    _today_session_expected,
    market_staleness_disclosure,
    merge_into_public_answer,
    run_market_watch_pack,
)
from intelligence.tests.test_market_watch_component_first import _db


def add_market_day(db: Path, day: str) -> None:
    con = duckdb.connect(str(db))
    con.execute(
        """
        insert into fact_market_daily(
          trade_date, market_stage, stage_day, total_amount,
          amount_vs_yesterday_pct, volume_state, limit_up, limit_down,
          sh_index_pct_chg
        ) values (?, '阶段', 1, 120, 1, '平稳', 1, 0, 0.1)
        """,
        [day],
    )
    con.close()


def test_weekend_and_exchange_holiday_do_not_claim_stale(tmp_path: Path):
    db = _db(tmp_path)  # newest Friday 08-21
    pack = run_market_watch_pack("今天市场怎么样", market_db_path=db, today=date(2026, 8, 22))
    assert pack.standing_date == "2026-08-21"
    assert pack.staleness_disclosure is None
    assert "数据未更新" not in pack.render()
    # 09-25 is an SSE closure; 09-26 is Saturday. 09-24 is the last trading day.
    add_market_day(db, "2026-09-24")
    holiday = run_market_watch_pack("今天市场怎么样", market_db_path=db, today=date(2026, 9, 26))
    assert holiday.staleness_disclosure is None
    assert "数据未更新" not in holiday.render()


def test_two_day_stop_is_disclosed_in_public_and_does_not_stop(tmp_path: Path, monkeypatch):
    db = _db(tmp_path)
    add_market_day(db, "2026-08-25")
    pack = run_market_watch_pack("今天市场怎么样", market_db_path=db, today=date(2026, 8, 27))
    assert pack.standing_date == "2026-08-25"
    assert pack.calendar_disclosure is None
    assert pack.staleness_disclosure == (
        "今日（2026-08-27）数据未更新，以下为 2026-08-25 数据（落后 2 个交易日）。"
    )
    assert pack.complete and len(pack.bags) == len(REQUIRED_BAGS)
    assert not pack.should_stop
    assert "- 停更：" + pack.staleness_disclosure in pack.render()
    public = merge_into_public_answer("量能平稳。", pack)
    assert pack.staleness_disclosure in public
    assert "量能平稳" in public
    # The normal Ask binder also delivers the same service-layer signal, not a renderer calculation.
    from intelligence.services import market_watch_pack
    monkeypatch.setattr(market_watch_pack, "_market_today", lambda: date(2026, 8, 27))
    monkeypatch.setattr(market_watch_pack, "_today_session_expected", lambda: True)  # 与墙钟无关
    bound = bind_market_watch_pack(AskOptions(query="今天市场怎么样", market_db_path=db, compose=True, synthesize=True))
    assert bound.market_watch_pack is not None
    assert bound.market_watch_pack.staleness_disclosure in bound.supplemental_evidence
    assert bound.compose is not False  # no calendar stop


def test_fresh_explicit_and_unknown_calendar_do_not_disclose(tmp_path: Path):
    db = _db(tmp_path)
    add_market_day(db, "2026-08-27")
    fresh = run_market_watch_pack("今天市场怎么样", market_db_path=db, today=date(2026, 8, 27))
    assert fresh.staleness_disclosure is None
    assert "数据未更新" not in fresh.render()
    explicit = run_market_watch_pack("2026-08-21 今天市场怎么样", market_db_path=db, today=date(2026, 8, 27))
    assert explicit.staleness_disclosure is None
    assert market_staleness_disclosure("2026-08-21", date(2027, 1, 12)) is None


def test_renderer_is_pure_and_does_not_decide_freshness(tmp_path: Path, monkeypatch):
    db = _db(tmp_path)
    add_market_day(db, "2026-08-25")
    pack = run_market_watch_pack("今天市场怎么样", market_db_path=db, today=date(2026, 8, 27))
    from intelligence.services import market_watch_pack
    def forbidden(*_args, **_kwargs):
        raise AssertionError("freshness must be computed before render")
    monkeypatch.setattr(market_watch_pack, "market_staleness_disclosure", forbidden)
    assert "数据未更新" in pack.render()


# ——— 盘中时点（2026-09-29 定案：21:00 前当日会话不计入期望）———

def test_intraday_previous_session_is_fresh_and_not_disclosed(tmp_path: Path, monkeypatch):
    # 交易日 08-27 上午：库里是 08-26 收盘，属正常，不得挂「今日数据未更新」。
    db = _db(tmp_path)
    add_market_day(db, "2026-08-26")
    from intelligence.services import market_watch_pack
    monkeypatch.setattr(market_watch_pack, "_market_today", lambda: date(2026, 8, 27))
    monkeypatch.setattr(market_watch_pack, "_today_session_expected", lambda: False)
    bound = bind_market_watch_pack(AskOptions(query="今天市场怎么样", market_db_path=db, compose=True, synthesize=True))
    assert bound.market_watch_pack.staleness_disclosure is None
    assert market_staleness_disclosure("2026-08-26", date(2026, 8, 27), today_expected=False) is None
    # 21:00 后今日会话已应入库：同一库就是落后 1 个交易日
    assert market_staleness_disclosure("2026-08-26", date(2026, 8, 27), today_expected=True) == (
        "今日（2026-08-27）数据未更新，以下为 2026-08-26 数据（落后 1 个交易日）。"
    )


def test_intraday_missing_previous_session_names_that_session():
    # 08-27 盘中，库只到 08-25：缺的是 08-26（最近应有交易日），不是「今日」。
    assert market_staleness_disclosure("2026-08-25", date(2026, 8, 27), today_expected=False) == (
        "最近交易日（2026-08-26）数据未更新，以下为 2026-08-25 数据（落后 1 个交易日）。"
    )


def test_ready_hour_boundary_uses_shanghai_clock():
    sh = ZoneInfo("Asia/Shanghai")
    assert _today_session_expected(datetime(2026, 8, 27, MARKET_DATA_READY_HOUR - 1, 59, tzinfo=sh)) is False
    assert _today_session_expected(datetime(2026, 8, 27, MARKET_DATA_READY_HOUR, 0, tzinfo=sh)) is True
    # 主机时区不影响：UTC 13:00 = 上海 21:00
    assert _today_session_expected(datetime(2026, 8, 27, 13, 0, tzinfo=ZoneInfo("UTC"))) is True
