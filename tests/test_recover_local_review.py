"""Recovery input proof precedes clone/write/publish; staging child is compulsory."""
from __future__ import annotations

import argparse
import json
from unittest.mock import Mock

import pytest

from scripts import recover_local_review as recovery


@pytest.fixture()
def captured_inputs(tmp_path):
    history = tmp_path / 'history.jsonl'
    snapshot = tmp_path / 'snapshot.json'
    row = {
        'trade_date': '2026-09-16', 'stock_ts_code': '000001.SZ',
        'source': 'sina:stock_zh_a_daily', 'close': 10.0, 'pre_close': 9.9,
        'pct_chg': 1.01, 'amount': 1.0, 'open': 9.9, 'high': 10.1,
        'low': 9.8, 'volume': 100000.0,
    }
    history.write_text(json.dumps(row) + '\n')
    snapshot.write_text(json.dumps([{'f297': 20260917}]))
    return history, snapshot, row


def validate(inputs):
    history, snapshot, _ = inputs
    return recovery.validate_inputs('2026-09-16', '2026-09-17', history, snapshot)


def test_valid_dates_and_provenance(captured_inputs):
    raw, rows = validate(captured_inputs)
    assert raw[0]['f297'] == 20260917
    assert rows[0]['trade_date'] == '2026-09-16'


@pytest.mark.parametrize('changes', [
    {'trade_date': '2026-09-17'}, {'source': 'eastmoney:snapshot'},
    {'amount': None}, {'close': float('nan')}, {'pre_close': 0}, {'volume': -1},
])
def test_rejects_unproven_or_invalid_history(captured_inputs, changes):
    history, _, row = captured_inputs
    history.write_text(json.dumps(row | changes) + '\n')
    with pytest.raises(ValueError):
        validate(captured_inputs)


def test_accepts_explicit_sina_cdr_provenance(captured_inputs):
    history, _, row = captured_inputs
    history.write_text(json.dumps(row | {'source': 'sina:stock_zh_a_cdr_daily', 'turnover': None}) + '\n')
    assert validate(captured_inputs)[1][0]['source'] == 'sina:stock_zh_a_cdr_daily'


def test_rejects_duplicate_history(captured_inputs):
    history, _, row = captured_inputs
    history.write_text((json.dumps(row) + '\n') * 2)
    with pytest.raises(ValueError, match='duplicate'):
        validate(captured_inputs)


def test_rejects_wrong_snapshot_date(captured_inputs):
    _, snapshot, _ = captured_inputs
    snapshot.write_text(json.dumps([{'f297': 20260916}]))
    with pytest.raises(ValueError, match='snapshot actual date'):
        validate(captured_inputs)


def test_rejects_direct_production_write(monkeypatch, tmp_path):
    from market_feature_store import db

    monkeypatch.setattr(db, 'DB_PATH', tmp_path / 'production.duckdb')
    monkeypatch.setenv('MARKET_FEATURE_STORE_RUN_ID', 'does-not-authorize-production')
    with pytest.raises(RuntimeError, match='staging publisher'):
        recovery.child(argparse.Namespace())


def test_parent_uses_guarded_publisher_and_backup(captured_inputs, monkeypatch, tmp_path):
    from market_feature_store import db
    from market_feature_store.sync import sync_daily_full

    target = tmp_path / 'canonical.duckdb'
    target.touch()
    monkeypatch.setenv('FINANCE_WS', str(tmp_path))
    monkeypatch.setenv('MARKET_FEATURE_STORE_DB', str(target))
    monkeypatch.setattr(db, 'DB_PATH', target)
    history, snapshot, _ = captured_inputs
    receipt = tmp_path / 'receipt.json'
    publish = Mock(return_value={'rc': 2, 'swapped': False})
    monkeypatch.setattr(sync_daily_full, 'run_daily_full_staged', publish)
    assert recovery.main([
        '--history-day', '2026-09-16', '--snapshot-day', '2026-09-17',
        '--history', str(history), '--snapshot', str(snapshot), '--receipt', str(receipt),
    ]) == 2
    assert publish.call_args.kwargs['pre_swap_backup'] is True
    assert publish.call_args.kwargs['child_argv'][-1] == '--child'
    assert json.loads(receipt.read_text())['swapped'] is False
    assert not (tmp_path / 'state/locks/daily-full-review.lock').exists()


def test_existing_nightly_lock_is_not_removed(monkeypatch, tmp_path):
    monkeypatch.setenv('FINANCE_WS', str(tmp_path))
    lock = tmp_path / 'state/locks/daily-full-review.lock'
    lock.mkdir(parents=True)
    (lock / 'pid').write_text('other-run')
    with pytest.raises(FileExistsError), recovery.nightly_lock():
        pytest.fail('must not start')
    assert (lock / 'pid').read_text() == 'other-run'
