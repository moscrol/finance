from datetime import date

from intelligence.services.trading_calendar import (
    next_trading_day,
    trading_day_prompt_block,
)


def test_friday_advances_to_monday() -> None:
    assert (
        next_trading_day(
            "2026-07-10",
            known_trading_days=["2026-07-09", "2026-07-10"],
        )
        == "2026-07-13"
    )


def test_weekend_anchor_is_rejected() -> None:
    assert (
        next_trading_day(
            "2026-07-11",
            known_trading_days=["2026-07-10"],
        )
        is None
    )


def test_official_holiday_gap_is_skipped() -> None:
    assert (
        next_trading_day(
            date(2026, 9, 24),
            known_trading_days=["2026-09-24"],
        )
        == "2026-09-28"
    )


def test_preloaded_future_calendar_takes_precedence() -> None:
    assert (
        next_trading_day(
            "2026-07-10",
            known_trading_days=["2026-07-10", "2026-07-14"],
        )
        == "2026-07-14"
    )


def test_missing_or_unsupported_calendar_fails_closed() -> None:
    assert next_trading_day("2026-07-10", known_trading_days=[]) is None
    assert (
        next_trading_day(
            "2027-01-04",
            known_trading_days=["2027-01-04"],
        )
        is None
    )
    assert "无法确认下一交易日" in trading_day_prompt_block(
        "2026-07-10",
        db_path="/missing/calendar.duckdb",
    )


def test_invalid_calendar_dates_fail_closed() -> None:
    assert next_trading_day(
        "not-a-date",
        known_trading_days=["2026-07-10"],
    ) is None
    assert next_trading_day(
        "2026-07-10",
        known_trading_days=["bad-date"],
    ) is None
