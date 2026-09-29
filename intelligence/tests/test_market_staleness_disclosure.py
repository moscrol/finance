"""R-20260827-13: market-watch delivery uses the exchange calendar, not DB as its clock."""

from datetime import date
from pathlib import Path

import duckdb

from intelligence.services.ask import bind_market_watch_pack
from intelligence.services.ask_types import AskOptions
from intelligence.services.market_watch_pack import (
    REQUIRED_BAGS,
    market_staleness_disclosure,
    merge_into_public_answer,
    run_market_watch_pack,
)
from intelligence.tests.test_market_watch_component_first import _db


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
