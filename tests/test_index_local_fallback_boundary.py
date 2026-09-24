"""local must not contact fupanhui even when the upstream is empty/broken."""
from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path
from unittest.mock import Mock

import duckdb
import pytest

from market_feature_store.sync import sync_akshare_index_daily as index


@pytest.fixture()
def index_db(tmp_path, monkeypatch):
    path = tmp_path / 'index.duckdb'
    with duckdb.connect(str(path)) as con:
        con.execute('CREATE TABLE fact_market_daily (trade_date DATE PRIMARY KEY)')
    monkeypatch.setattr(index, 'init_db', lambda: None)
    monkeypatch.setattr(index, 'connect', lambda: duckdb.connect(str(path)))
    monkeypatch.delenv('REVIEW_SYNC_PLAN', raising=False)
    return path


@pytest.mark.parametrize('upstream_error', [False, True])
@pytest.mark.parametrize('boundary', ['flag', 'environment'])
def test_local_refuses_fallback_without_network(index_db, monkeypatch, upstream_error, boundary):
    upstream = Mock(return_value=[], side_effect=RuntimeError('unavailable') if upstream_error else None)
    fallback = Mock(side_effect=AssertionError('forbidden network'))
    monkeypatch.setattr(index, '_fetch_akshare_index', upstream)
    monkeypatch.setattr(index, '_fetch_fph_index', fallback)
    if boundary == 'environment':
        monkeypatch.setenv('REVIEW_SYNC_PLAN', 'local')
    with pytest.raises(RuntimeError, match='禁止请求复盘会'):
        index.sync_akshare_index_daily('2026-09-17', allow_fupanhui_fallback=boundary != 'flag')
    fallback.assert_not_called()
    with duckdb.connect(str(index_db), read_only=True) as con:
        assert con.execute('SELECT count(*) FROM fact_market_daily').fetchone()[0] == 0


def test_legacy_explicit_nonlocal_path_retains_fallback(index_db, monkeypatch):
    monkeypatch.setattr(index, '_fetch_akshare_index', lambda **kw: [])
    fallback = Mock(return_value=[{
        'trade_date': date(2026, 9, 17), 'close': 3000.0, 'pct_chg': 1.0,
        'open': None, 'high': None, 'low': None, 'volume': None, 'amount': None,
        'source': 'fupanhui:test',
    }])
    monkeypatch.setattr(index, '_fetch_fph_index', fallback)
    assert index.sync_akshare_index_daily('2026-09-17')['rows_written'] == 1
    fallback.assert_called_once_with('2026-09-17')


def test_local_plan_passes_request_boundary_explicitly(monkeypatch):
    path = Path(__file__).resolve().parents[1] / 'skills/daily-full-review/scripts/run_review_sync.py'
    spec = importlib.util.spec_from_file_location('local_index_plan', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    run = Mock(return_value={'status': 'ok'})
    monkeypatch.setattr(module, 'run_step', run)
    plan = dict(module.build_plan('2026-09-17', 300, 600, plan='local'))
    plan['index-daily']()
    assert '--no-fupanhui-fallback' in run.call_args.args[1]
