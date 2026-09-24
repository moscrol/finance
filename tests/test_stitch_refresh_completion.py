"""Refresh completion belongs to this call, not to yesterday's success receipt.

Use the real member writer and CLI with tiny in-memory DuckDB fixtures; never
read production or fetch market caps. The recovery consumer is tested separately.
"""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from market_feature_store.cli import build_parser, cmd_stitch_sector_stocks
from market_feature_store.sector_universe import SectorUniverseStore
from market_feature_store.sync import sync_local_sector_members as stitch
from tests import test_tiered_sync_local as fixture

SECTORS = [("990001.FP", "MLCC", 3), ("990002.FP", "6G", 2), ("990003.FP", "机器人", 2)]
MEMBERS = {
    "990001.FP": ["000001.SZ", "000002.SZ", "000003.SZ"],
    "990002.FP": ["600000.SH", "600001.SH"],
    "990003.FP": ["300001.SZ", "300002.SZ"],
}


@pytest.fixture
def completed(monkeypatch):
    # The original independent R1: 200 days exceeds recovery's unchanged 180-day bound.
    monkeypatch.setattr(fixture, "D1", "2026-03-01")
    monkeypatch.setattr(fixture, "D2", "2026-09-17")
    monkeypatch.setattr(fixture, "CAPTURED", {
        day: day + "T16:00:00+08:00" for day in (fixture.D1, fixture.D2)
    })
    generator = fixture.con.__wrapped__()
    con = next(generator)
    try:
        fixture._seed_day1(con)
        pub = fixture._publish(con, fixture.D2, SECTORS)
        for sector, codes in MEMBERS.items():
            fixture._record(con, pub.snapshot_id, sector, fixture.D2, [
                fixture._provider_member(code, source="local:stitch") for code in codes
            ])
        SectorUniverseStore(con).replace_sector_daily(pub.snapshot_id, [
            {"sector_ts_code": sector, "pct_chg": 1.0, "amount": len(codes) * 2.0, "diff_ratio": 0.0}
            for sector, codes in MEMBERS.items()
        ])
        fixture._eastmoney(con, fixture.D2, [
            (code, 12.0 if code == "000001.SZ" else 10.0, 20.0, 4.0)
            for codes in MEMBERS.values() for code in codes
        ])
        yield con
    finally:
        generator.close()


def call_cli(con, monkeypatch, *, refresh=True, age=180, dry_run=False):
    original = stitch.stitch_sector_members
    summaries = []

    def use_fixture(*args, **kwargs):
        summary = original(*args, con=con, **kwargs)
        summaries.append(summary)
        return summary

    monkeypatch.setattr(stitch, "stitch_sector_members", use_fixture)
    command = ["stitch-sector-stocks", "--trade-date", fixture.D2, "--no-caps",
               "--max-baseline-age-days", str(age)]
    if refresh:
        command.append("--include-completed")
    if dry_run:
        command.append("--dry-run")
    rc = cmd_stitch_sector_stocks(build_parser().parse_args(command))
    return rc, summaries[0]


def member_price(con):
    return con.execute(
        "SELECT price FROM fact_sector_stock_daily WHERE trade_date=? AND stock_ts_code=?",
        [fixture.D2, "000001.SZ"],
    ).fetchone()[0]


def test_refresh_cannot_borrow_old_success_when_baseline_expired(completed, monkeypatch, capsys):
    rc, summary = call_cli(completed, monkeypatch)
    assert summary["audit_complete"] is True  # Old, truthful audit is not rewritten.
    assert summary["skipped"] == {"no_baseline": 3}
    assert summary["stitched"] == 0
    assert member_price(completed) == 10.0  # Base quote is 12; recovery must stop.
    assert rc == 2
    assert summary["refresh_complete"] is False
    assert "刷新未完成" in capsys.readouterr().out


def test_refresh_with_qualified_baseline_really_rewrites_members(completed, monkeypatch):
    # Fixture control only; production/recovery still requests 180 days.
    rc, summary = call_cli(completed, monkeypatch, age=365)
    assert rc == 0
    assert summary["refresh_complete"] is True
    assert summary["stitched"] == summary["candidates"] == 3
    assert member_price(completed) == 12.0


def test_partial_refresh_is_not_complete(completed, monkeypatch):
    original = stitch._baselines

    def missing_one(*args, **kwargs):
        return {k: v for k, v in original(*args, **kwargs).items() if k != "990001.FP"}

    monkeypatch.setattr(stitch, "_baselines", missing_one)
    rc, summary = call_cli(completed, monkeypatch, age=365)
    assert summary["stitched"] == 2
    assert summary["audit_complete"] is True
    assert summary["skipped"] == {"no_baseline": 1}
    assert rc == 2 and summary["refresh_complete"] is False


@pytest.mark.parametrize("remove_all", [True, False], ids=["empty-members", "shortfall"])
def test_refresh_missing_values_stops(completed, monkeypatch, remove_all):
    original = stitch.build_rows

    def insufficient(*args, **kwargs):
        rows, dropped = original(*args, **kwargs)
        return ([], dropped) if remove_all else (rows[:1], dropped)

    monkeypatch.setattr(stitch, "build_rows", insufficient)
    if not remove_all:
        monkeypatch.setattr(stitch, "_shortfall_bound", lambda expected: 0)
    rc, summary = call_cli(completed, monkeypatch, age=365)
    assert summary["skipped"] == {"shortfall": 3}
    assert summary["audit_complete"] is True
    assert rc == 2 and summary["refresh_complete"] is False


def test_writer_failure_cannot_borrow_old_audit(completed, monkeypatch):
    monkeypatch.setattr(SectorUniverseStore, "record_member_result", lambda *a, **k:
                        SimpleNamespace(status="error", last_error_code="writer_failed"))
    rc, summary = call_cli(completed, monkeypatch, age=365)
    assert len(summary["failed"]) == 3 and summary["audit_complete"] is True
    assert rc == 2 and summary["refresh_complete"] is False


def test_writer_exception_propagates(completed, monkeypatch):
    def fail(*args, **kwargs):
        raise OSError("writer stopped")

    monkeypatch.setattr(SectorUniverseStore, "record_member_result", fail)
    with pytest.raises(OSError, match="writer stopped"):
        call_cli(completed, monkeypatch, age=365)


@pytest.mark.parametrize("pending_kind", [None, "changed", "new"])
@pytest.mark.parametrize("audit_complete", [True, False])
def test_zero_candidates_requires_no_pending_and_complete_audit(
    completed, monkeypatch, pending_kind, audit_complete,
):
    delta = stitch.identity_delta(completed, fixture.D2)
    # Defensive empty-work boundary: normal published universes are nonempty.
    delta = replace(delta, unchanged=(), changed=(), new=())
    if pending_kind:
        delta = replace(delta, **{pending_kind: ("990099.FP",)})
    monkeypatch.setattr(stitch, "identity_delta", lambda *args: delta)
    monkeypatch.setattr(SectorUniverseStore, "completion_audit", lambda *a, **k:
                        SimpleNamespace(complete=audit_complete, brief=lambda: "fixture audit"))
    rc, summary = call_cli(completed, monkeypatch)
    expected = pending_kind is None and audit_complete
    assert summary["stitched"] == summary["candidates"] == 0
    assert summary["refresh_complete"] is expected
    assert rc == (0 if expected else 2)
    assert member_price(completed) == 10.0


def test_nonrefresh_keeps_provider_fallback_contract(completed, monkeypatch):
    completed.execute("UPDATE ops_sector_member_sync_daily SET status='pending' WHERE trade_date=?",
                      [fixture.D2])
    rc, summary = call_cli(completed, monkeypatch, refresh=False)
    assert summary["skipped"] == {"no_baseline": 3}
    assert summary["pending_for_provider"] == 3
    assert rc == 0  # Ordinary incremental work may leave these for provider fill.
    assert summary["refresh_complete"] is None


def test_dry_run_is_preview_not_completed_write(completed, monkeypatch, capsys):
    rc, summary = call_cli(completed, monkeypatch, age=365, dry_run=True)
    assert rc == 0 and summary["stitched"] == 3 and summary["rows"]
    assert summary["refresh_complete"] is False
    assert summary["audit_complete"] is None
    assert member_price(completed) == 10.0
    assert "预览" in capsys.readouterr().out


def test_complete_writes_still_require_audit(completed, monkeypatch):
    monkeypatch.setattr(SectorUniverseStore, "completion_audit", lambda *a, **k:
                        SimpleNamespace(complete=False, brief=lambda: "incomplete"))
    rc, summary = call_cli(completed, monkeypatch, age=365)
    assert summary["stitched"] == summary["candidates"] == 3
    assert member_price(completed) == 12.0
    assert summary["refresh_complete"] is False and rc == 2


def test_recovery_bound_remains_180_days():
    from scripts import recover_local_review as recovery

    command = recovery.recovery_stitch_command(SimpleNamespace(CLI=[]), "2026-09-17", "2026-09-16")
    args = build_parser().parse_args(command)
    assert args.max_baseline_age_days == 180 and args.include_completed
