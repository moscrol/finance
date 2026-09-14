"""Independent QC counterexamples; synthetic DBs only, never canonical writes.

These tests assert observed false acceptance, not desired correct behavior.
"""
from __future__ import annotations

from datetime import date, timedelta
import hashlib
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import duckdb
import pytest

import market_feature_store.sync.repair_backfill_stock_history as mod
from tests.test_repair_backfill_stock_history import CAL, CODE, _fixture, _spec


@pytest.fixture()
def review_env(tmp_path):
    db, pq = tmp_path / "mini.duckdb", tmp_path / "tail.parquet"
    fixture = _fixture(db, pq)
    spec = _spec(db, pq, fixture["pinned"])
    with duckdb.connect(str(db)) as con:
        yield con, pq, spec


def test_missing_retained_source_day_silently_bridges_lag(review_env):
    con, pq, spec = review_env
    # D2 already exists in main, so deleting its source is invisible to gap guard.
    con.execute("DELETE FROM fact_stock_daily_hithink WHERE stock_ts_code=? "
                "AND trade_date=?", [CODE, CAL[2]])
    report = mod.run_backfill_child(con, spec, pq)
    got = con.execute("SELECT pre_close, pct_chg FROM fact_stock_daily "
                      "WHERE stock_ts_code=? AND trade_date=?", [CODE, CAL[3]]).fetchone()
    assert report["mode"] == "apply"
    assert got == (10.5, 9.52)  # Wrong: preceding market day close is 11.0, pct 4.55.
    print("FALSE_ACCEPT missing D2 source -> D3 pre_close/pct_chg", got)


@pytest.mark.parametrize("field,value", [("open", None), ("pre_close", -999.0),
                                        ("source", "wrong:source")])
def test_verify_accepts_corrupt_backfilled_key_fields(review_env, field, value):
    con, pq, spec = review_env
    mod.run_backfill_child(con, spec, pq)
    if field == "source":
        # Swap the two allowed source labels. Count stays correct, but the wrong
        # source join excludes this day from oracle comparison entirely.
        value = mod.SOURCE_PARQUET
    con.execute(f"UPDATE fact_stock_daily SET {field}=? WHERE stock_ts_code=? "
                "AND trade_date=?", [value, CODE, CAL[3]])
    report = mod.run_backfill_child(con, spec, pq)
    assert report["mode"] == "verify"
    got = con.execute(f"SELECT {field} FROM fact_stock_daily WHERE stock_ts_code=? "
                      "AND trade_date=?", [CODE, CAL[3]]).fetchone()[0]
    assert got == value
    print("FALSE_ACCEPT verify corrupt", field, got)


def test_window_nontrading_start_passes_exact_span_acceptance(review_env, monkeypatch):
    con, pq, spec = review_env
    real = mod._rebuild_derived_scoped

    def corrupt(connection, contract, mode):
        result = real(connection, contract, mode)
        # D5 is Monday; previous Sunday gives identical counted calendar span.
        sunday = (date.fromisoformat(CAL[5]) - timedelta(days=1)).isoformat()
        connection.execute("UPDATE feature_stock_window SET start_date=? "
                           "WHERE stock_ts_code=? AND as_of_date=? AND start_date=?",
                           [sunday, CODE, CAL[10], CAL[5]])
        return result

    monkeypatch.setattr(mod, "_rebuild_derived_scoped", corrupt)
    report = mod.run_backfill_child(con, spec, pq)
    assert report["window_rows"] == 55
    assert con.execute("SELECT COUNT(*) FROM feature_stock_window WHERE stock_ts_code=? "
                       "AND EXTRACT(ISODOW FROM start_date)=7", [CODE]).fetchone()[0] == 1
    print("FALSE_ACCEPT Sunday start despite exact-date-set claim")


def test_pinned_timestamp_is_not_protected(review_env, monkeypatch):
    con, pq, spec = review_env
    real = mod._apply_main

    def corrupt(connection, contract, parquet, prev_day, mode):
        result = real(connection, contract, parquet, prev_day, mode)
        connection.execute("UPDATE fact_stock_daily SET updated_at='2000-01-01' "
                           "WHERE stock_ts_code=? AND trade_date=?", [CODE, spec.window_end])
        return result

    monkeypatch.setattr(mod, "_apply_main", corrupt)
    assert mod.run_backfill_child(con, spec, pq)["mode"] == "apply"
    print("FALSE_ACCEPT pinned row updated_at changed")


def test_real_cli_parent_rejects_child_hash_failure_without_publish(tmp_path):
    target = tmp_path / "not-production.duckdb"
    with duckdb.connect(str(target)) as con:
        con.execute("CREATE TABLE witness AS SELECT 123 AS x")
    before = hashlib.sha256(target.read_bytes()).hexdigest()
    pq = tmp_path / "invalid.parquet"
    pq.write_bytes(b"invalid frozen source")
    env = os.environ.copy()
    env["MARKET_FEATURE_STORE_DB"] = str(target)
    result = subprocess.run(
        [sys.executable, "-m", "market_feature_store.cli", "repair-backfill-302132",
         "--parquet", str(pq)], env=env, capture_output=True, text=True,
        cwd=Path(__file__).resolve().parents[1], timeout=30)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "子进程未写出 status.json (rc=2)" in result.stdout
    assert hashlib.sha256(target.read_bytes()).hexdigest() == before
    assert not Path(str(target) + ".staging.status.json").exists()
    assert not list(tmp_path.glob("*.bak-*"))


def test_cli_canonical_child_is_rejected_before_any_db_open(tmp_path, monkeypatch):
    from market_feature_store import cli
    from market_feature_store.write_path import canonical_production_candidates

    # No canonical connection is opened, even if the guard regresses.
    def forbidden_connect(*args, **kwargs):
        pytest.fail("must reject before attempting DB open")

    monkeypatch.setattr(duckdb, "connect", forbidden_connect)
    pq = tmp_path / "source.parquet"
    pq.write_bytes(b"guard must run before hash/read")
    for target in canonical_production_candidates():
        args = SimpleNamespace(parquet=str(pq), child=True, db=str(target), report_path=None)
        assert cli.cmd_repair_backfill_302132(args) == 2


def test_child_report_path_overwrites_canonical_witness(tmp_path, monkeypatch):
    from market_feature_store import cli

    db, pq = tmp_path / "staging.duckdb", tmp_path / "tail.parquet"
    fixture = _fixture(db, pq)
    spec = _spec(db, pq, fixture["pinned"])
    canonical = tmp_path / "canonical-witness.duckdb"
    with duckdb.connect(str(canonical)) as con:
        con.execute("CREATE TABLE witness AS SELECT 123 AS x")
    # This is a disposable witness explicitly designated canonical, not production.
    monkeypatch.setenv("MARKET_FEATURE_STORE_PRODUCTION_DB", str(canonical))
    monkeypatch.setattr(mod, "BackfillSpec", lambda: spec)
    args = SimpleNamespace(parquet=str(pq), child=True, db=str(db), report_path=str(canonical))
    assert cli.cmd_repair_backfill_302132(args) == 0
    import json
    assert json.loads(canonical.read_text())["ok"] is True
    print("FALSE_ACCEPT report_path replaced canonical-witness DuckDB with JSON")


def test_cli_parent_wires_scoped_child_and_backup(tmp_path, monkeypatch):
    from market_feature_store import cli
    from market_feature_store.sync import sync_daily_full

    pq = tmp_path / "source.parquet"
    pq.write_bytes(b"parent only checks existence")
    seen = {}

    def parent(**kwargs):
        seen.update(kwargs)
        return {"swapped": False, "reason": "test stub", "rc": 2}

    monkeypatch.setattr(sync_daily_full, "run_daily_full_staged", parent)
    args = SimpleNamespace(parquet=str(pq), child=False, db=None, report_path=None)
    assert cli.cmd_repair_backfill_302132(args) == 2
    assert seen["kind"] == "repair-backfill-302132"
    assert seen["pre_swap_backup"] is True
    assert seen["child_argv"] == [sys.executable, "-m", "market_feature_store.cli",
                                  "repair-backfill-302132", "--child", "--parquet", str(pq)]
