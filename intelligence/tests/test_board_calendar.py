from __future__ import annotations

from datetime import date
from pathlib import Path

import duckdb
import pytest

from intelligence.services import board_calendar
from intelligence.services.board_calendar import build_board_calendar
from market_feature_store import trading_days


@pytest.fixture(autouse=True)
def fixed_calendar_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    class FixedDate(date):
        @classmethod
        def today(cls) -> date:
            return cls(2026, 9, 28)

    monkeypatch.setattr(board_calendar, "date", FixedDate)
    monkeypatch.setattr(trading_days, "date", FixedDate)
    monkeypatch.delenv("L2_FORCE_TRADE_DAY", raising=False)
    monkeypatch.delenv("L2_FORCE_NON_TRADE_DAY", raising=False)


def _database(
    path: Path,
    *,
    many_boards: bool = False,
    board_gap: bool = False,
) -> None:
    con = duckdb.connect(str(path))
    con.execute("CREATE TABLE fact_market_daily (trade_date DATE)")
    market_dates = ["2026-09-23", "2026-09-24"]
    if board_gap:
        market_dates.insert(0, "2026-09-22")
    con.executemany(
        "INSERT INTO fact_market_daily VALUES (?)",
        [(value,) for value in market_dates],
    )
    con.execute(
        """
        CREATE TABLE fact_limit_advance_daily (
            trade_date DATE,
            stock_ts_code VARCHAR,
            stock_name VARCHAR,
            boards INTEGER,
            theme VARCHAR,
            pct_chg DOUBLE
        )
        """
    )
    rows = [
        ("2026-09-23", "000001.SZ", "甲公司", 2, "题材甲", 4.2),
        ("2026-09-24", "000002.SZ", "乙公司", 5, "题材乙", 10.0),
        ("2026-09-24", "000003.SZ", "丙公司", 3, None, None),
    ]
    if many_boards:
        rows.extend(
            (
                "2026-09-24",
                f"0000{index:02d}.SZ",
                f"样本{index}",
                2,
                None,
                None,
            )
            for index in range(4, 29)
        )
    con.executemany(
        "INSERT INTO fact_limit_advance_daily VALUES (?, ?, ?, ?, ?, ?)",
        rows,
    )
    con.close()


def _day(payload: dict, value: str) -> dict:
    return next(item for item in payload["calendar_days"] if item["date"] == value)


def test_calendar_separates_trading_days_closures_and_board_gaps(tmp_path: Path) -> None:
    db_path = tmp_path / "market.duckdb"
    _database(db_path)

    payload = build_board_calendar(db_path, month="2026-09", min_boards=3)

    assert payload["status"] == "partial"
    assert "缺少市场日数据" in payload["message"]
    assert len(payload["calendar_days"]) == 30
    assert [item["date"] for item in payload["trading_days"]] == [
        "2026-09-23",
        "2026-09-24",
    ]
    assert _day(payload, "2026-09-23")["data_status"] == "available"
    assert _day(payload, "2026-09-23")["stock_count"] == 0
    assert _day(payload, "2026-09-25")["calendar_status"] == "closed"
    assert _day(payload, "2026-09-26")["calendar_status"] == "closed"
    assert _day(payload, "2026-09-15")["calendar_status"] == "market_data_missing"
    assert _day(payload, "2026-09-15")["is_trading_day"] is True

    latest = _day(payload, "2026-09-24")
    assert latest["stock_count"] == 2
    assert [group["boards"] for group in latest["board_groups"]] == [5, 3]
    assert latest["board_groups"][0]["stocks"][0]["stock_name"] == "乙公司"


def test_board_data_gap_is_not_reported_as_a_quiet_trading_day(tmp_path: Path) -> None:
    db_path = tmp_path / "market.duckdb"
    _database(db_path, board_gap=True)

    payload = build_board_calendar(db_path, month="2026-09", min_boards=3)
    gap = _day(payload, "2026-09-22")

    assert payload["status"] == "partial"
    assert gap["calendar_status"] == "trading"
    assert gap["data_status"] == "board_data_missing"
    assert gap["stock_count"] == 0


def test_default_threshold_adapts_to_month_density_but_can_be_overridden(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "market.duckdb"
    _database(db_path, many_boards=True)

    default_payload = build_board_calendar(db_path, month="2026-09")
    two_board_payload = build_board_calendar(
        db_path,
        month="2026-09",
        min_boards=2,
    )

    assert default_payload["recommended_min_boards"] == 3
    assert default_payload["min_boards"] == 3
    assert two_board_payload["min_boards"] == 2
    assert _day(two_board_payload, "2026-09-24")["stock_count"] == 27


def test_missing_board_table_keeps_partial_reason(tmp_path: Path) -> None:
    db_path = tmp_path / "market-without-boards.duckdb"
    con = duckdb.connect(str(db_path))
    con.execute("CREATE TABLE fact_market_daily (trade_date DATE)")
    con.execute("INSERT INTO fact_market_daily VALUES ('2026-09-24')")
    con.close()

    payload = build_board_calendar(db_path, month="2026-09")

    assert payload["status"] == "partial"
    assert "连板数据表不存在" in payload["message"]
    assert _day(payload, "2026-09-24")["data_status"] == "board_data_missing"


def test_future_dates_are_not_treated_as_historical_weekends(tmp_path: Path) -> None:
    db_path = tmp_path / "market.duckdb"
    _database(db_path)

    payload = build_board_calendar(db_path, month="2099-01")

    assert payload["status"] == "no_market_data"
    assert _day(payload, "2099-01-03")["calendar_status"] == "future"
    assert _day(payload, "2099-01-03")["data_status"] == "not_applicable"
    assert _day(payload, "2099-01-05")["calendar_status"] == "future"


def test_missing_database_is_explicit(tmp_path: Path) -> None:
    payload = build_board_calendar(tmp_path / "missing.duckdb", month="2026-09")

    assert payload["status"] == "missing"
    assert payload["calendar_days"] == []
    assert payload["message"] == "市场数据库不存在"
    assert not (tmp_path / "missing.duckdb").exists()


def test_complete_date_range_is_ok_and_read_only(tmp_path: Path) -> None:
    db_path = tmp_path / "market.duckdb"
    _database(db_path)
    original_bytes = db_path.read_bytes()

    payload = build_board_calendar(
        db_path, start_date="2026-09-23", end_date="2026-09-24", min_boards=3,
    )

    assert payload["status"] == "ok"
    assert len(payload["calendar_days"]) == 2
    assert payload["market_data_cutoff"] == "2026-09-24"
    assert payload["board_data_cutoff"] == "2026-09-24"
    assert db_path.read_bytes() == original_bytes


def test_unregistered_calendar_year_remains_unknown(tmp_path: Path) -> None:
    db_path = tmp_path / "market.duckdb"
    _database(db_path)

    payload = build_board_calendar(db_path, month="2025-01")

    assert payload["status"] == "partial"
    assert _day(payload, "2025-01-02")["calendar_status"] == "calendar_unknown"
    assert _day(payload, "2025-01-04")["calendar_status"] == "closed"


def test_future_database_rows_are_not_served_as_market_facts(tmp_path: Path) -> None:
    db_path = tmp_path / "market.duckdb"
    _database(db_path)
    con = duckdb.connect(str(db_path))
    con.execute("INSERT INTO fact_market_daily VALUES ('2026-09-29')")
    con.execute(
        """
        INSERT INTO fact_limit_advance_daily
        VALUES ('2026-09-29', '000009.SZ', '未来股份', 9, '未来题材', 99.0)
        """
    )
    con.close()

    payload = build_board_calendar(
        db_path,
        start_date="2026-09-29",
        end_date="2026-09-30",
        min_boards=2,
    )

    assert payload["status"] == "no_market_data"
    assert payload["trading_days"] == []
    assert all(day["calendar_status"] == "future" for day in payload["calendar_days"])
    assert payload["market_data_cutoff"] == "2026-09-24"
    assert payload["board_data_cutoff"] == "2026-09-24"


@pytest.mark.parametrize("query", [
    {"month": "2026-9"},
    {"month": "2026-13"},
    {"month": "2026-09", "start_date": "2026-09-01"},
    {"start_date": "2026-09-01"},
    {"start_date": "20260901", "end_date": "2026-09-30"},
    {"start_date": "", "end_date": ""},
    {"start_date": "2026-09-30", "end_date": "2026-09-01"},
    {"start_date": "2025-01-01", "end_date": "2026-01-03"},
    {"min_boards": 1},
    {"min_boards": 21},
])
def test_invalid_queries_fail_before_database_access(tmp_path: Path, query: dict) -> None:
    with pytest.raises(ValueError):
        build_board_calendar(tmp_path / "missing.duckdb", **query)


def test_maximum_date_does_not_overflow(tmp_path: Path) -> None:
    db_path = tmp_path / "market.duckdb"
    _database(db_path)

    payload = build_board_calendar(db_path, month="9999-12")

    assert len(payload["calendar_days"]) == 31
    assert payload["calendar_days"][-1]["date"] == "9999-12-31"
