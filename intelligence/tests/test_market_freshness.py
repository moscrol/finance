from datetime import datetime
from zoneinfo import ZoneInfo

from intelligence.services.workbench_overview import market_freshness

CN = ZoneInfo("Asia/Shanghai")


def at(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=CN)


def test_before_close_expects_previous_trading_day_and_skips_holiday():
    # 09-25（周五）中秋休市、09-26/27 周末：09-29 午间最近已收盘交易日是 09-28
    got = market_freshness("2026-09-24", now=at("2026-09-29T11:50:00"))
    assert got["expected_trade_date"] == "2026-09-28"
    assert got["lag_trading_days"] == 1
    assert got["missing_trade_dates"] == ["2026-09-28"]
    assert got["calendar_certain"] is True


def test_after_settle_counts_today():
    got = market_freshness("2026-09-24", now=at("2026-09-29T16:00:00"))
    assert got["expected_trade_date"] == "2026-09-29"
    assert got["lag_trading_days"] == 2


def test_up_to_date_is_zero():
    got = market_freshness("2026-09-28", now=at("2026-09-29T09:00:00"))
    assert got["lag_trading_days"] == 0
    assert got["missing_trade_dates"] == []


def test_missing_as_of_keeps_lag_unknown():
    got = market_freshness(None, now=at("2026-09-29T09:00:00"))
    assert got["lag_trading_days"] is None
    assert got["expected_trade_date"] == "2026-09-28"
