"""Offline review probes for dfb6ce87; temporary DuckDB files only.

Explicit invocation: python -m pytest -q scripts/review_daily_swap_round7.py
No providers or production database access. Desired-behavior assertions are
intentional, including any red result on the reviewed revision.
"""
from __future__ import annotations

import errno
import hashlib
import subprocess
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


def make_db(path):
    con = duckdb.connect(str(path))
    con.execute('CREATE TABLE fact_market_daily (trade_date DATE, total_amount DOUBLE)')
    con.execute("INSERT INTO fact_market_daily VALUES ('2026-08-14', 10000)")
    con.close()


def setup_target(tmp_path, monkeypatch, *, existing=True):
    target = tmp_path / 'prod.duckdb'
    if existing:
        make_db(target)
    monkeypatch.setattr(db, 'DB_PATH', target)
    monkeypatch.setattr(db, 'DB_DIR', target.parent)
    return target


def run():
    return sdf.run_daily_full_staged(child_argv=[sys.executable, '-c', CHILD])


@pytest.mark.parametrize('when', ['before', 'after'])
def test_clone_deletion_is_rejected(tmp_path, monkeypatch, when):
    target = setup_target(tmp_path, monkeypatch)
    real_run = subprocess.run
    fired = []

    def delete_around_copy(argv, *args, **kwargs):
        match = argv[:3] == ['cp', '-c', str(target)]
        if match and when == 'before':
            target.unlink()
            fired.append(when)
        result = real_run(argv, *args, **kwargs)
        if match and when == 'after':
            target.unlink()
            fired.append(when)
        return result

    monkeypatch.setattr(db.subprocess, 'run', delete_around_copy)
    result = run()
    assert fired == [when]
    assert result['rc'] == 2 and not result['swapped'], result
    assert not target.exists()
    if when == 'after':
        assert db.staging_path(target).exists()


def test_bootstrap_keeps_other_committed_database(tmp_path, monkeypatch):
    target = setup_target(tmp_path, monkeypatch, existing=False)
    fired = []
    real_link, real_replace = db.os.link, db.os.replace

    def attack(real):
        def wrapped(src, dst, *args, **kwargs):
            if Path(src) == db.staging_path(target) and Path(dst) == target:
                make_db(target)
                with duckdb.connect(str(target), read_only=True) as con:
                    assert con.execute('SELECT total_amount FROM fact_market_daily').fetchall() == [(10000,)]
                fired.append(hashlib.sha256(target.read_bytes()).hexdigest())
            return real(src, dst, *args, **kwargs)
        return wrapped

    monkeypatch.setattr(db.os, 'link', attack(real_link))
    monkeypatch.setattr(db.os, 'replace', attack(real_replace))
    result = run()
    assert len(fired) == 1
    assert result['rc'] == 2 and not result['swapped'], result
    assert hashlib.sha256(target.read_bytes()).hexdigest() == fired[0]
    assert db.staging_path(target).exists()


@pytest.mark.parametrize('code', [errno.EPERM, errno.ENOSPC, errno.EOPNOTSUPP])
def test_link_other_io_failure_is_blocked_without_fallback(tmp_path, monkeypatch, code):
    target = setup_target(tmp_path, monkeypatch, existing=False)
    fired, replaced = [], []

    def fail_link(src, dst, *args, **kwargs):
        if Path(src) == db.staging_path(target) and Path(dst) == target:
            fired.append(code)
            raise OSError(code, 'injected link failure')
        raise AssertionError('unexpected link')

    monkeypatch.setattr(db.os, 'link', fail_link)
    monkeypatch.setattr(db.os, 'replace', lambda *a, **k: replaced.append(a))
    result = run()
    assert fired == [code] and replaced == []
    assert result['rc'] == 2 and not result['swapped'], result
    assert 'injected link failure' in result['reason']
    assert not target.exists() and db.staging_path(target).exists()


def test_target_deleted_after_successful_opening_probe_is_not_bootstrapped(tmp_path, monkeypatch):
    target = setup_target(tmp_path, monkeypatch)
    real_probe = db.probe_no_active_writer
    fired = []

    def delete_after_probe(path):
        real_probe(path)
        if Path(path) == target and not fired:
            assert target.exists()
            target.unlink()
            fired.append('after-successful-opening-probe')

    monkeypatch.setattr(db, 'probe_no_active_writer', delete_after_probe)
    result = run()
    assert fired == ['after-successful-opening-probe']
    observed = {'rc': result['rc'], 'swapped': result['swapped'], 'copy': result['copy']}
    if target.exists():
        with duckdb.connect(str(target), read_only=True) as con:
            observed['rows'] = con.execute(
                'SELECT CAST(trade_date AS VARCHAR), total_amount FROM fact_market_daily'
            ).fetchall()
    print('AFTER_PROBE_DELETE_OBSERVED', observed)
    assert result['rc'] == 2 and not result['swapped'], observed
    assert not target.exists(), 'must not silently recreate a deleted existing database'


@pytest.mark.parametrize('code', [errno.EPERM, errno.ENOSPC])
def test_clone_io_debt_is_real_but_does_not_publish(tmp_path, monkeypatch, code):
    """Characterization only: documents existing raw OSError, not desired UX."""
    target = setup_target(tmp_path, monkeypatch)
    original_bytes = target.read_bytes()
    real_run = db.subprocess.run
    fired = []

    def fail_fast_copy(argv, *args, **kwargs):
        if argv[:3] == ['cp', '-c', str(target)]:
            raise subprocess.CalledProcessError(1, argv)
        return real_run(argv, *args, **kwargs)

    def fail_fallback(src, dst, *args, **kwargs):
        fired.append(code)
        raise OSError(code, 'injected clone failure')

    monkeypatch.setattr(db.subprocess, 'run', fail_fast_copy)
    monkeypatch.setattr(db.shutil, 'copy2', fail_fallback)
    with pytest.raises(OSError) as excinfo:
        run()
    assert fired == [code] and excinfo.value.errno == code
    assert target.read_bytes() == original_bytes
