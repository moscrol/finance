"""R-20260827-13: market-watch delivery uses the exchange calendar, not DB as its clock."""

from datetime import date, datetime
from zoneinfo import ZoneInfo
import plistlib
from pathlib import Path

import duckdb

from intelligence.services.ask import bind_market_watch_pack
from intelligence.services.ask_types import AskOptions
from intelligence.services.market_watch_pack import (
    MARKET_DATA_EXPECTED_BY,
    REQUIRED_BAGS,
    market_staleness_disclosure,
    merge_into_public_answer,
    run_market_watch_pack,
)
from intelligence.tests.test_market_watch_component_first import _db

SH = ZoneInfo("Asia/Shanghai")
REPO = Path(__file__).resolve().parents[2]


def add_market_day(db: Path, day: str) -> None:
    con = duckdb.connect(str(db))
    con.execute("insert into fact_market_daily values (?, '阶段', 1, 120, 1, '平稳', 1, 0, 0.1)", [day])
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
        "数据未更新：按交易日历应已有 2026-08-27 的数据，以下为 2026-08-25 数据（落后 2 个交易日）。"
    )
    assert pack.complete and len(pack.bags) == len(REQUIRED_BAGS)
    assert not pack.should_stop
    assert "- 停更：" + pack.staleness_disclosure in pack.render()
    public = merge_into_public_answer("量能平稳。", pack)
    assert pack.staleness_disclosure in public
    assert "量能平稳" in public
    # The normal Ask binder also delivers the same service-layer signal, not a renderer calculation.
    from intelligence.services import market_watch_pack
    monkeypatch.setattr(market_watch_pack, "_market_now", lambda: datetime(2026, 8, 27, 21, 30, tzinfo=SH))
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


def _at(y, m, d, hh, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=SH)


def test_trading_day_before_cutoff_is_normal_not_stale(tmp_path: Path):
    """09-30 盘中库里只有 09-29 是常态：21:00 前不披露，21:00 后才披露。"""
    db = _db(tmp_path)
    add_market_day(db, "2026-09-29")
    for clock in (_at(2026, 9, 30, 0, 5), _at(2026, 9, 30, 9, 0), _at(2026, 9, 30, 20, 59)):
        pack = run_market_watch_pack("今天市场怎么样", market_db_path=db, now=clock)
        assert pack.staleness_disclosure is None, clock
        assert "数据未更新" not in pack.render()
    late = run_market_watch_pack("今天市场怎么样", market_db_path=db, now=_at(2026, 9, 30, 21, 0))
    assert late.staleness_disclosure == (
        "数据未更新：按交易日历应已有 2026-09-30 的数据，以下为 2026-09-29 数据（落后 1 个交易日）。"
    )


def test_missed_previous_session_is_disclosed_even_before_cutoff(tmp_path: Path):
    """昨晚夜跑没出数：次日上午就该披露，基准是上一交易日而不是今天。"""
    assert market_staleness_disclosure("2026-09-28", date(2026, 9, 30), include_today=False) == (
        "数据未更新：按交易日历应已有 2026-09-29 的数据，以下为 2026-09-28 数据（落后 1 个交易日）。"
    )


def test_holiday_and_weekend_mornings_follow_the_calendar():
    # 10-01 休市：上午应有的是 09-30；有 09-30 就不披露，只有 09-29 就落后 1。
    assert market_staleness_disclosure("2026-09-30", date(2026, 10, 1), include_today=False) is None
    assert "落后 1 个交易日" in market_staleness_disclosure("2026-09-29", date(2026, 10, 1), include_today=False)
    # 09-25 周五交易所休市、09-26 周六：周六上午应有的是 09-24，有就不披露。
    assert market_staleness_disclosure("2026-09-24", date(2026, 9, 26), include_today=False) is None
    assert "应已有 2026-09-24" in market_staleness_disclosure("2026-09-23", date(2026, 9, 26), include_today=False)


def test_cutoff_is_after_nightly_sync_start():
    plist = REPO / "intelligence/dream/com.financeworkspace.daily-full-review-sync.plist"
    start = plistlib.loads(plist.read_bytes())["StartCalendarInterval"]
    start_minutes = int(start["Hour"]) * 60 + int(start.get("Minute", 0))
    cutoff_minutes = MARKET_DATA_EXPECTED_BY.hour * 60 + MARKET_DATA_EXPECTED_BY.minute
    # 至少给夜跑 sync + 换库留 2 小时；排期挪晚了这里先红，逼着一起改截止时刻。
    assert cutoff_minutes - start_minutes >= 120
