from datetime import date

from intelligence.services.trading_calendar import (
    next_trading_day,
    non_trading_day_note,
    question_non_trading_note,
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


# --- 非交易日事实（R15-C1/C2 生产形状） --------------------------------


def test_saturday_note_names_the_weekday_and_previous_trading_day() -> None:
    note = non_trading_day_note(date(2026, 7, 25))

    assert note is not None
    assert "周六" in note
    assert "休市" in note
    assert "2026-07-24" in note


def test_spring_festival_closure_note_uses_the_official_schedule() -> None:
    # 2026-02-17 是周二，只有公告休市表能判定它休市。
    note = non_trading_day_note(date(2026, 2, 17))

    assert note is not None
    assert "交易所公告休市" in note
    # 2/16-2/20 全休 + 2/23 也休，向前跨过周末落在 2/13（周五）。
    assert "2026-02-13" in note


def test_regular_trading_day_produces_no_note() -> None:
    assert non_trading_day_note(date(2026, 7, 23)) is None


def test_weekday_outside_closure_table_fails_closed() -> None:
    # 2027 无休市表：工作日无法证明休市，宁可漏报。
    assert non_trading_day_note(date(2027, 1, 1)) is None
    # 周末判定不依赖休市表，任何年份成立；前一交易日因表外 fail closed 省略。
    weekend = non_trading_day_note(date(2027, 1, 2))
    assert weekend is not None and "周六" in weekend
    assert "前一交易日" not in weekend


def test_question_note_extracts_full_dates_only() -> None:
    assert question_non_trading_note("2026-07-25 市场怎么样") is not None
    assert question_non_trading_note("2026年2月17日 涨停家数多少") is not None
    # 交易日不注入。
    assert question_non_trading_note("2026-07-23 市场怎么样") is None
    # 无年份写法的年份归属在 query_understanding，这里刻意放过。
    assert question_non_trading_note("7.25 市场怎么样") is None
    assert question_non_trading_note("今天市场怎么样") is None
