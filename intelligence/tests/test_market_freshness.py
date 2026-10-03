from datetime import datetime
from hashlib import sha256
from zoneinfo import ZoneInfo

import duckdb
import pytest

from intelligence.services import workbench_overview
from intelligence.services.workbench_overview import market_freshness
from market_feature_store import trading_days

CN = ZoneInfo("Asia/Shanghai")


def at(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=CN)


@pytest.mark.parametrize(
    ("moment", "expected", "missing"),
    [
        ("2026-09-29T09:00:00", "2026-09-28", ["2026-09-28"]),
        ("2026-09-29T15:29:59", "2026-09-28", ["2026-09-28"]),
        ("2026-09-29T15:30:00", "2026-09-29", ["2026-09-28", "2026-09-29"]),
        ("2026-09-29T16:00:00", "2026-09-29", ["2026-09-28", "2026-09-29"]),
        # Mid-Autumn closure and weekend; neither adds a missing session.
        ("2026-09-25T16:00:00", "2026-09-24", []),
        ("2026-09-27T16:00:00", "2026-09-24", []),
        ("2026-10-07T16:00:00", "2026-09-30", ["2026-09-28", "2026-09-29", "2026-09-30"]),
    ],
)
def test_settlement_cutoff_and_holidays(moment, expected, missing):
    got = market_freshness("2026-09-24", now=at(moment))

    assert got["expected_trade_date"] == expected
    assert got["lag_trading_days"] == len(missing)
    assert got["missing_trade_dates"] == missing
    assert got["calendar_certain"] is True
    assert got["status"] == ("stale" if missing else "current")


@pytest.mark.parametrize(
    "moment",
    [
        datetime.fromisoformat("2026-09-29T07:30:00+00:00"),
        datetime.fromisoformat("2026-09-29T00:30:00-07:00"),
        datetime.fromisoformat("2026-09-29T15:30:00"),
    ],
)
def test_clock_is_always_interpreted_in_shanghai(moment):
    got = market_freshness("2026-09-29", now=moment)

    assert got["expected_trade_date"] == "2026-09-29"
    assert got["checked_at"] == "2026-09-29T15:30:00+08:00"
    assert got["status"] == "current"


@pytest.mark.parametrize(
    ("cutoff", "status"),
    [
        (None, "missing"),
        ("", "missing"),
        ("bad-date", "invalid"),
        ("20260929", "invalid"),
        ("2026-W40-2", "invalid"),
        ("2026-02-30", "invalid"),
        ("2026-09-28T00:00:00", "invalid"),
        ("2026-09-25", "invalid"),
        ("2026-09-27", "invalid"),
        ("2026-09-30", "future"),
        ("2027-01-01", "future"),
        ("2026-09-29", "unsettled"),
    ],
)
def test_unusable_or_unsettled_dates_are_not_current(cutoff, status):
    got = market_freshness(cutoff, now=at("2026-09-29T11:00:00"))

    assert got["status"] == status
    assert got["lag_trading_days"] is None
    assert got["missing_trade_dates"] == []
    assert got["expected_trade_date"] == "2026-09-28"


@pytest.mark.parametrize(
    ("cutoff", "moment", "expected"),
    [
        ("2026-09-30", "2027-01-04T16:00:00", None),
        ("2025-12-31", "2026-01-01T16:00:00", None),
        # Today's calendar is known; the cutoff year is not.
        ("2025-12-31", "2026-01-05T16:00:00", "2026-01-05"),
    ],
)
def test_unknown_calendar_years_do_not_become_current(cutoff, moment, expected):
    got = market_freshness(cutoff, now=at(moment))

    assert got["status"] == "unknown"
    assert got["expected_trade_date"] == expected
    assert got["calendar_certain"] is False
    assert got["lag_trading_days"] is None
    assert got["missing_trade_dates"] == []


def test_known_cross_year_calendar_counts_only_scheduled_sessions(monkeypatch):
    real_closed_dates = trading_days.closed_dates
    monkeypatch.setattr(
        trading_days,
        "closed_dates",
        lambda year: frozenset() if year == 2025 else real_closed_dates(year),
    )

    holiday = market_freshness("2025-12-31", now=at("2026-01-02T16:00:00"))
    settled = market_freshness("2025-12-30", now=at("2026-01-05T16:00:00"))

    assert holiday["status"] == "current"
    assert holiday["expected_trade_date"] == "2025-12-31"
    assert settled["missing_trade_dates"] == ["2025-12-31", "2026-01-05"]
    assert settled["lag_trading_days"] == 2


def test_unknown_year_inside_gap_discards_partial_count(monkeypatch):
    real_closed_dates = trading_days.closed_dates
    monkeypatch.setattr(
        trading_days,
        "closed_dates",
        lambda year: frozenset() if year == 2024 else real_closed_dates(year),
    )

    got = market_freshness("2024-12-30", now=at("2026-01-05T16:00:00"))

    assert got["expected_trade_date"] == "2026-01-05"
    assert got["calendar_certain"] is False
    assert got["status"] == "unknown"
    assert got["lag_trading_days"] is None
    assert got["missing_trade_dates"] == []


def test_calendar_source_is_shared_and_not_affected_by_operations_overrides(monkeypatch):
    monkeypatch.setenv("L2_FORCE_TRADE_DAY", "1")
    monkeypatch.setenv("L2_FORCE_NON_TRADE_DAY", "1")

    got = market_freshness("2026-09-24", now=at("2026-09-27T16:00:00"))

    assert got["status"] == "current"
    assert got["expected_trade_date"] == "2026-09-24"


def test_missing_list_is_capped_but_lag_counts_all_sessions():
    got = market_freshness("2026-01-05", now=at("2026-03-05T16:00:00"))

    assert got["status"] == "stale"
    assert got["lag_trading_days"] == 37
    assert len(got["missing_trade_dates"]) == 30
    assert got["missing_trade_dates"][0] == "2026-01-06"
    assert "2026-02-16" not in got["missing_trade_dates"]


@pytest.fixture
def frozen_clock(monkeypatch):
    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return at("2026-09-29T16:00:00").astimezone(tz)

    monkeypatch.setattr(workbench_overview, "datetime", FrozenDatetime)


@pytest.mark.parametrize(
    ("cutoff", "status", "lag"),
    [
        (None, "missing", None),
        ("not-a-date", "invalid", None),
        ("2026-09-30", "future", None),
        ("2025-12-31", "unknown", None),
        ("2026-09-24", "stale", 2),
        ("2026-09-29", "current", 0),
    ],
)
def test_overview_reads_actual_database_cutoff_without_writing(
    tmp_path, frozen_clock, cutoff, status, lag
):
    root = tmp_path / "finance"
    database = root / "db" / "market_feature_store.duckdb"
    database.parent.mkdir(parents=True)
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    with duckdb.connect(str(database)) as con:
        # VARCHAR also exercises malformed legacy dates through the real read.
        con.execute("""
            CREATE TABLE fact_market_daily (
                trade_date VARCHAR, market_stage VARCHAR, advancers INTEGER,
                limit_up INTEGER, limit_down INTEGER, total_amount DOUBLE,
                amount_vs_yesterday_pct DOUBLE, amount_ma20 DOUBLE,
                top3_industry_ratio DOUBLE, concentration_state VARCHAR,
                strength_marginal_pct DOUBLE, strength_status VARCHAR
            )
        """)
        if cutoff:
            con.execute(
                "INSERT INTO fact_market_daily VALUES (?, '轮动', 2800, 52, 6, 18000, 3.2, 17500, 35, '中等集中', 1.8, '正常')",
                [cutoff],
            )
    before = sha256(database.read_bytes()).hexdigest()

    overview = workbench_overview.build_workbench_overview(root, wiki)

    assert overview["market_freshness"] == {
        "as_of": cutoff,
        "expected_trade_date": "2026-09-29",
        "status": status,
        "lag_trading_days": lag,
        "missing_trade_dates": ["2026-09-28", "2026-09-29"] if status == "stale" else [],
        "calendar_certain": status != "unknown",
        "checked_at": "2026-09-29T16:00:00+08:00",
    }
    if status in {"current", "stale"}:
        assert overview["as_of_date"] == cutoff
        assert overview["market"]["trade_date"] == cutoff
        assert overview["market"]["stage"] == "轮动"
    assert sha256(database.read_bytes()).hexdigest() == before


@pytest.mark.parametrize("database_contents", [None, b"not a duckdb file"])
def test_missing_or_unreadable_database_keeps_freshness_unknown(
    tmp_path, frozen_clock, database_contents
):
    if database_contents is not None:
        database = tmp_path / "db" / "market_feature_store.duckdb"
        database.parent.mkdir()
        database.write_bytes(database_contents)

    overview = workbench_overview.build_workbench_overview(tmp_path, tmp_path / "wiki")

    assert overview["market_freshness"]["status"] == "missing"
    assert overview["market_freshness"]["as_of"] is None
    assert overview["market_freshness"]["lag_trading_days"] is None
    assert overview["market_freshness"]["expected_trade_date"] == "2026-09-29"
    assert overview["as_of_date"] is None
