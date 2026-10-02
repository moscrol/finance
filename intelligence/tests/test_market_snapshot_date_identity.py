"""Snapshot date identity must be decided before any undated spot observation.

All providers and databases are synthetic; no market API or production data is
read or written. Freeze the shared calendar clock, not a second holiday table.
"""

from datetime import date, datetime
import json
from zoneinfo import ZoneInfo

import pytest

from intelligence.services import akshare_market_snapshot as akshare_service
from intelligence.services.market_snapshot_sync import sync_market_snapshot
from intelligence.tests.test_akshare_market_snapshot import _module
from intelligence.tests.test_duckdb_market_snapshot import _build_db
from intelligence.tests.test_market_snapshot_sync import _write_akshare_result
from market_feature_store import trading_days


BEIJING = ZoneInfo("Asia/Shanghai")


def _now(day: str) -> datetime:
    return datetime.fromisoformat(day + "T17:00:00").replace(tzinfo=BEIJING)


@pytest.fixture(autouse=True)
def shared_calendar_clock(monkeypatch):
    class CalendarDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 10, 30)

    monkeypatch.setattr(trading_days, "date", CalendarDate)
    monkeypatch.delenv("L2_FORCE_TRADE_DAY", raising=False)
    monkeypatch.delenv("L2_FORCE_NON_TRADE_DAY", raising=False)


@pytest.mark.parametrize(
    "requested,captured,available",
    [
        ("2026-10-01", "2026-10-01", "2026-09-30"),
        ("2026-10-02", "2026-10-02", "2026-09-30"),
        ("2026-07-18", "2026-07-18", "2026-07-16"),
        ("2026-07-16", "2026-07-17", "2026-07-15"),
        ("2026-07-20", "2026-07-16", "2026-07-15"),
    ],
)
def test_sync_never_dates_current_spot_as_closed_past_or_future_observations(
    tmp_path, requested, captured, available
):
    root = tmp_path / "snapshots"
    db_path = _build_db(tmp_path / "market.duckdb", trade_date=available)
    provider_calls = []

    def spot_runner(output_dir, trade_date):
        provider_calls.append(trade_date)
        return _write_akshare_result(output_dir, trade_date, quality="complete")

    result = sync_market_snapshot(
        root, db_path=db_path, target_date=requested,
        akshare_runner=spot_runner, now=_now(captured),
    )
    assert provider_calls == []
    assert result.ok is True
    assert result.provider == "duckdb_latest"
    assert result.served_trade_date == available
    assert not (root / f"{requested}.json").exists()
    document = json.loads((root / "latest.json").read_text())
    meta = json.loads((root / "meta.json").read_text())
    for value in (document, meta):
        assert value["requested_trade_date"] == requested
        assert value["served_trade_date"] == available
        assert value["source_data_date"] == available
        assert value["freshness"] == "historical"
    assert document["captured_at"].startswith(captured)
    assert any("AkShare" in (attempt.error or "") for attempt in result.attempts)


def test_historical_exact_duckdb_keeps_exact_source_day_but_is_not_fresh(tmp_path):
    root = tmp_path / "snapshots"
    db_path = _build_db(tmp_path / "market.duckdb", trade_date="2026-07-16")
    provider_calls = []
    result = sync_market_snapshot(
        root, db_path=db_path, target_date="2026-07-16",
        akshare_runner=lambda *args: provider_calls.append(args),
        now=_now("2026-07-17"),
    )
    assert provider_calls == []
    assert result.ok is True
    assert result.provider == "duckdb_exact"
    assert result.served_trade_date == "2026-07-16"
    assert result.attempts[0].freshness == "historical"
    document = json.loads((root / "2026-07-16.json").read_text())
    assert document["trade_date"] == document["source_data_date"] == "2026-07-16"
    assert document["captured_at"].startswith("2026-07-17")
    assert document["freshness"] == "historical"


def test_unknown_calendar_does_not_certify_exact_duckdb_or_spot_data(tmp_path, monkeypatch):
    monkeypatch.setattr(trading_days, "closed_dates", lambda year: None)
    root = tmp_path / "snapshots"
    db_path = _build_db(tmp_path / "market.duckdb", trade_date="2026-07-16")
    provider_calls = []
    result = sync_market_snapshot(
        root, db_path=db_path, target_date="2026-07-16",
        akshare_runner=lambda *args: provider_calls.append(args),
        now=_now("2026-07-16"),
    )
    assert provider_calls == []
    assert result.ok is False
    assert result.served_trade_date is None
    assert not (root / "2026-07-16.json").exists()
    assert not (root / "latest.json").exists()
    assert "unknown" in " ".join(attempt.error or "" for attempt in result.attempts)


def test_future_request_cannot_select_future_duckdb_rows_as_latest(tmp_path):
    root = tmp_path / "snapshots"
    db_path = _build_db(tmp_path / "market.duckdb", trade_date="2026-07-17")
    provider_calls = []
    result = sync_market_snapshot(
        root, db_path=db_path, target_date="2026-07-20",
        akshare_runner=lambda *args: provider_calls.append(args),
        now=_now("2026-07-16"),
    )
    assert provider_calls == []
    assert result.ok is False
    assert result.served_trade_date is None
    assert not (root / "latest.json").exists()
    assert not (root / "2026-07-17.json").exists()


def test_known_current_trading_day_still_uses_provider_when_exact_db_is_missing(tmp_path):
    root = tmp_path / "snapshots"
    provider_calls = []

    def spot_runner(output_dir, trade_date):
        provider_calls.append(trade_date)
        return _write_akshare_result(output_dir, trade_date, quality="complete")

    result = sync_market_snapshot(
        root, db_path=tmp_path / "absent.duckdb", target_date="2026-07-16",
        akshare_runner=spot_runner, now=_now("2026-07-16"),
    )
    assert provider_calls == ["2026-07-16"]
    assert result.ok is True
    assert result.provider == "akshare_exact"
    assert result.served_trade_date == "2026-07-16"


@pytest.mark.parametrize(
    "requested,captured,unknown",
    [
        ("2026-10-02", "2026-10-02", False),
        ("2026-07-18", "2026-07-18", False),
        ("2026-07-16", "2026-07-17", False),
        ("2026-07-20", "2026-07-16", False),
        ("2026-07-16", "2026-07-16", True),
    ],
)
def test_direct_entry_rejects_invalid_spot_date_before_importing_provider(
    tmp_path, monkeypatch, requested, captured, unknown
):
    if unknown:
        monkeypatch.setattr(trading_days, "closed_dates", lambda year: None)
    imports = []
    module = _module(spot=[{"涨跌幅": 1.0, "成交额": 100_000_000}], limit_up=[], limit_down=[])

    def load_provider(name):
        imports.append(name)
        return module

    monkeypatch.setattr(akshare_service, "import_module", load_provider)
    result = akshare_service.sync_akshare_market_snapshot(
        tmp_path, trade_date=requested, now=_now(captured),
    )
    assert imports == []
    assert result.ok is False
    assert result.quality == "failed"
    assert result.written_files == ()
    assert result.trade_date == requested
    assert not (tmp_path / f"{requested}.json").exists()
    assert not (tmp_path / "latest.json").exists()
    status = json.loads((tmp_path / "akshare_status.json").read_text())
    assert status["quality"] == "failed"
    assert result.errors


def test_blocked_direct_fetch_preserves_all_existing_canonical_files(tmp_path):
    paths = [tmp_path / name for name in ("2026-10-02.json", "latest.json", "meta.json")]
    for p in paths:
        p.write_text(json.dumps({"trade_date": "2026-09-30", "quality": "complete"}))
    before = {p: p.read_bytes() for p in paths}
    result = akshare_service.sync_akshare_market_snapshot(
        tmp_path, trade_date="2026-10-02", now=_now("2026-10-02"),
        akshare_module=_module(spot=[{"涨跌幅": 1.0}], limit_up=[], limit_down=[]),
    )
    assert result.ok is False
    assert result.preserved_existing_snapshot is True
    assert {p: p.read_bytes() for p in paths} == before


def test_invalid_calendar_date_is_rejected_before_provider_load(tmp_path, monkeypatch):
    imports = []
    monkeypatch.setattr(akshare_service, "import_module", lambda name: imports.append(name))
    with pytest.raises(ValueError):
        akshare_service.sync_akshare_market_snapshot(
            tmp_path, trade_date="2026-02-30", now=_now("2026-07-16"),
        )
    assert imports == []


@pytest.mark.parametrize("unknown", [False, True])
def test_fallback_cannot_certify_closed_or_unknown_database_dates(tmp_path, monkeypatch, unknown):
    if unknown:
        monkeypatch.setattr(trading_days, "closed_dates", lambda year: None)
    available = "2026-07-16" if unknown else "2026-10-01"
    requested = "2026-07-17" if unknown else "2026-10-02"
    root = tmp_path / "snapshots"
    db_path = _build_db(tmp_path / "market.duckdb", trade_date=available)
    provider_calls = []
    result = sync_market_snapshot(
        root, db_path=db_path, target_date=requested,
        akshare_runner=lambda *args: provider_calls.append(args), now=_now(requested),
    )
    assert provider_calls == []
    assert result.ok is False
    assert result.served_trade_date is None
    assert not (root / "latest.json").exists()


def test_historical_exact_request_does_not_regress_newer_latest_and_meta(tmp_path):
    root = tmp_path / "snapshots"
    _write_akshare_result(root, "2026-07-17", quality="complete")
    before = {name: (root / name).read_bytes() for name in ("latest.json", "meta.json")}
    db_path = _build_db(tmp_path / "market.duckdb", trade_date="2026-07-16")
    db_before = db_path.read_bytes()
    result = sync_market_snapshot(
        root, db_path=db_path, target_date="2026-07-16", now=_now("2026-07-20"),
    )
    assert result.ok is True
    assert result.provider == "duckdb_exact"
    assert (root / "2026-07-16.json").exists()
    assert {name: (root / name).read_bytes() for name in before} == before
    assert db_path.read_bytes() == db_before
    assert result.written_files == (str(root / "2026-07-16.json"),)
