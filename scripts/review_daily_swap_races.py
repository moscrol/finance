"""Offline regression probes: deletion escape and first-publication data loss.

Run with the project interpreter:
    python -m pytest -q scripts/review_daily_swap_races.py --tb=short

Only temporary DuckDB fixtures are used; no providers or production DB access.
Tests express desired safety behavior and intentionally fail on code 7c89ca81.
Monkeypatches inject real unlink / DuckDB commits immediately before real syscalls.
These are review evidence, not an alternative production publication path.
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

import duckdb
import pytest

from market_feature_store import db
from market_feature_store.sync import sync_daily_full as sdf

CHILD = """
import duckdb, json, os, pathlib
path = os.environ['MARKET_FEATURE_STORE_DB']
con = duckdb.connect(path)
con.execute('CREATE TABLE IF NOT EXISTS fact_market_daily (trade_date DATE, total_amount DOUBLE)')
con.execute("INSERT INTO fact_market_daily VALUES ('2026-08-15', 12345)")
con.close()
pathlib.Path(path + '.status.json').write_text(json.dumps({
    'trade_date': '2026-08-15', 'ok': True, 'steps': [],
    'run_id': os.environ['MARKET_FEATURE_STORE_RUN_ID'],
}))
"""


@pytest.mark.parametrize('window', ['clone_to_staging', '_run_daily_full_staged_locked'])
def test_target_delete_at_other_path_stat_returns_rc2(tmp_path, monkeypatch, window):
    target = tmp_path / 'prod.duckdb'
    con = duckdb.connect(str(target))
    con.execute('CREATE TABLE fact_market_daily (trade_date DATE, total_amount DOUBLE)')
    con.execute("INSERT INTO fact_market_daily VALUES ('2026-08-14', 10000)")
    con.close()
    monkeypatch.setattr(db, 'DB_PATH', target)
    monkeypatch.setattr(db, 'DB_DIR', target.parent)
    real_stat = Path.stat
    attacked = []

    def stat_after_delete(path, *args, **kwargs):
        caller = inspect.currentframe().f_back.f_code.co_name
        if path == target and caller == window and not attacked:
            attacked.append(caller)
            path.unlink()
        return real_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'stat', stat_after_delete)
    result = sdf.run_daily_full_staged(child_argv=[sys.executable, '-c', CHILD])
    assert attacked == [window], 'Injection must reach the intended boundary'
    assert result['rc'] == 2 and result['swapped'] is False
    assert not target.exists()


def test_bootstrap_must_not_lose_committed_duckdb_writer(tmp_path, monkeypatch):
    target = tmp_path / 'fresh.duckdb'
    monkeypatch.setattr(db, 'DB_PATH', target)
    monkeypatch.setattr(db, 'DB_DIR', target.parent)
    real_replace = db.os.replace
    attack = []

    def create_then_replace(src, dst, *args, **kwargs):
        if Path(src) == db.staging_path(target) and Path(dst) == target:
            assert not target.exists()
            # Ordinary writer: acquires DuckDB's EX lock, commits, then closes.
            con = duckdb.connect(str(target))
            con.execute('CREATE TABLE committed_by_other_writer (v INTEGER)')
            con.execute('INSERT INTO committed_by_other_writer VALUES (17000)')
            con.close()
            con = duckdb.connect(str(target), read_only=True)
            assert con.execute('SELECT v FROM committed_by_other_writer').fetchall() == [(17000,)]
            con.close()
            attack.append('committed-and-read-back')
        return real_replace(src, dst, *args, **kwargs)

    monkeypatch.setattr(db.os, 'replace', create_then_replace)
    result = sdf.run_daily_full_staged(child_argv=[sys.executable, '-c', CHILD])
    con = duckdb.connect(str(target), read_only=True)
    tables = {row[0] for row in con.execute('SHOW TABLES').fetchall()}
    con.close()
    assert attack == ['committed-and-read-back'], 'Attack must actually commit'
    assert not (
        result['rc'] == 0 and result['swapped'] and 'committed_by_other_writer' not in tables
    ), result
