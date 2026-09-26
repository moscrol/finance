"""Offline acceptance through real CLI children and observable write boundaries."""
from __future__ import annotations

from datetime import datetime

import duckdb
import pytest

from market_feature_store.db import init_db
from market_feature_store.sync import compute_local_stats as stats
from tests import test_bridge_hithink_stock_daily as bridge_seed
from tests import test_compute_local_stats as local_seed
from tests.test_bridge_transaction_boundaries import _ObservedConnection
from tests.test_review_sync_export_release import _load

TABLES = ("fact_theme_limit_heat_daily", "fact_theme_limit_stock_daily",
          "fact_limit_advance_daily", "fact_leader_height_daily")
MEMBERS = {"990001.FP": ["600001.SH", "300001.SZ", "000001.SZ"],
           "990002.FP": ["002514.SZ"]}


def _derived(con):
    return {table: con.execute(f"SELECT * FROM {table} ORDER BY ALL").fetchall() for table in TABLES}


@pytest.mark.parametrize("defect", ["missing-bar", "invalid-close", "synthetic-nontrading"])
def test_recovery_invalid_inputs_never_reach_derived_dml(defect):
    with local_seed._db() as con:
        local_seed._seed_two_days(con)
        local_seed._seed_universe_and_members(con)
        stats.compute_limit_stats_local("2026-09-02", con=con)
        before = _derived(con)
        stopped = ()
        if defect == "missing-bar":
            con.execute("DELETE FROM fact_stock_daily WHERE stock_ts_code='000001.SZ'")
        elif defect == "invalid-close":
            con.execute("UPDATE fact_stock_daily SET close=NULL WHERE stock_ts_code='000001.SZ'")
        else:
            stopped = ("600999.SH",)
        observed = _ObservedConnection(con)
        with pytest.raises(ValueError):
            stats.compute_limit_stats_local("2026-09-02", con=observed,
                                            recovery_members=MEMBERS, recovery_nontrading=stopped)
        assert not {"DELETE", "INSERT", "UPDATE", "COMMIT"} & set(observed.events)
        assert _derived(con) == before


def test_daily_and_explicit_complete_recovery_have_same_derived_values():
    with local_seed._db() as con:
        local_seed._seed_two_days(con)
        local_seed._seed_universe_and_members(con)
        daily = stats.compute_limit_stats_local("2026-09-02", con=con)
        before = _derived(con)
        recovery = stats.compute_limit_stats_local("2026-09-02", con=con, recovery_members=MEMBERS)
        after = _derived(con)
        assert daily["denominator_basis"] == "observed_member_rows"
        assert recovery["denominator_basis"] == "frozen_identity"
        for table in TABLES:
            # Timestamps are run provenance, not market values.
            assert [[v for v in r if not isinstance(v, datetime)] for r in before[table]] == [
                [v for v in r if not isinstance(v, datetime)] for r in after[table]]


def test_derived_failure_after_heat_insert_rolls_back_all_four_tables():
    with local_seed._db() as con:
        local_seed._seed_two_days(con)
        local_seed._seed_universe_and_members(con)
        stats.compute_limit_stats_local("2026-09-02", con=con)
        before = _derived(con)

        def after_heat():
            assert con.execute("SELECT count(*) FROM fact_theme_limit_heat_daily").fetchone()[0] > 0
            assert con.execute("SELECT count(*) FROM fact_theme_limit_stock_daily").fetchone()[0] == 0
            raise RuntimeError("injected after heat insert")

        observed = _ObservedConnection(con, after_insert=after_heat)
        with pytest.raises(RuntimeError, match="injected after heat insert"):
            stats.compute_limit_stats_local("2026-09-02", con=observed, recovery_members=MEMBERS)
        assert observed.events[-1] == "ROLLBACK"
        assert "COMMIT" not in observed.events
        assert _derived(con) == before


@pytest.fixture
def cli_fixture(tmp_path, monkeypatch):
    path = tmp_path / "fixture.duckdb"
    with duckdb.connect(str(path)) as con, bridge_seed._con(bridge_seed._codes(3)) as vendor:
        init_db(con)
        bars = vendor.execute("SELECT * FROM fact_stock_daily_hithink").fetchall()
        con.executemany(
            "INSERT INTO fact_stock_daily_hithink "
            "(stock_ts_code, trade_date, open, high, low, close, volume, turnover, adjusted, source, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)", bars)
        bridge_seed._seed_canonical(con, bridge_seed._codes(3), bridge_seed.PREV)
    monkeypatch.setenv("MARKET_FEATURE_STORE_DB", str(path))
    monkeypatch.delenv("MARKET_FEATURE_STORE_PRODUCTION_DB", raising=False)
    review = _load()
    monkeypatch.setattr(review, "connect", lambda **kw: duckdb.connect(str(path), **kw))
    monkeypatch.setattr(review, "SKILL_DIR", tmp_path)
    monkeypatch.setattr(review, "RUNLOG", tmp_path / "runlog.md")
    return review, path


@pytest.mark.parametrize("scenario", ["bridge", "missing-vendor", "partial-primary"])
def test_fallback_chain_uses_actual_bridge_subprocess(cli_fixture, monkeypatch, scenario):
    review, path = cli_fixture
    with duckdb.connect(str(path)) as con:
        if scenario == "missing-vendor":
            con.execute("DELETE FROM fact_stock_daily_hithink WHERE trade_date=?", [bridge_seed.TD])
        if scenario == "partial-primary":
            bridge_seed._seed_canonical(con, bridge_seed._codes(1), bridge_seed.TD, close=99.0)
    real_step = review.run_step
    commands = []

    def offline_sources(label, argv, timeout):
        commands.append(argv[3])
        if argv[3] in {"sync-stock-daily-snapshot", "fill-stock-daily-fallback"}:
            # Only external providers are replaced. Bridge imports and DB selection are real.
            return real_step(label, [review.PY, "-c", "raise SystemExit(1)"], timeout)
        assert argv[3] == "bridge-stock-daily"
        return real_step(label, argv, timeout)

    monkeypatch.setattr(review, "run_step", offline_sources)
    result = review.sync_stock_daily(bridge_seed.TD, 30, hithink_fallback=True)
    success = scenario == "bridge"
    assert result["status"] == ("ok" if success else "fail")
    assert ("bridge-stock-daily" in commands) == (scenario != "partial-primary")
    with duckdb.connect(str(path), read_only=True) as con:
        assert con.execute("SELECT count(*) FROM fact_stock_daily WHERE trade_date=?",
                           [bridge_seed.TD]).fetchone()[0] == (3 if success else int(scenario == "partial-primary"))
    review.write_runlog(bridge_seed.TD, [result], False, plan="local")
    log = review.RUNLOG.read_text()
    assert "stock-daily (snapshot) | fail" in log
    assert "stock-daily fallback | fail" in log
    if success:
        assert "bridge-stock-daily | ok" in log


def test_real_cli_production_guard_does_not_open_pinned_fixture(cli_fixture, monkeypatch):
    review, path = cli_fixture
    monkeypatch.setenv("MARKET_FEATURE_STORE_PRODUCTION_DB", str(path))
    before = path.read_bytes()
    result = review.run_step("bridge-stock-daily", review.CLI + [
        "bridge-stock-daily", "--trade-date", bridge_seed.TD], 30)
    assert result["status"] == "fail" and result["code"] == 2
    assert path.read_bytes() == before


def test_real_release_gate_rejects_incomplete_fixture_before_export(cli_fixture):
    review, path = cli_fixture
    before = path.read_bytes()
    results, allowed = review.run_release_steps(bridge_seed.TD, 30, plan="local")
    assert allowed is False
    assert [r["label"] for r in results] == ["same-day-gate"]
    assert results[0]["status"] == "fail"
    assert path.read_bytes() == before
