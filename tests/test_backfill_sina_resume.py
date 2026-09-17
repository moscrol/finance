"""Resume borrows only identities from a verified later snapshot, never prices."""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import duckdb
import pandas as pd
import pytest


@pytest.fixture()
def capture(tmp_path, monkeypatch):
    script = Path(__file__).resolve().parents[1] / 'skills/duckdb-backfill/scripts/backfill_stock_daily_sina.py'
    spec = importlib.util.spec_from_file_location('sina_resume_test', script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    db = tmp_path / 'db.duckdb'
    with duckdb.connect(str(db)) as con:
        con.execute('CREATE TABLE fact_stock_daily (trade_date DATE, stock_ts_code TEXT, stock_name TEXT)')
        con.execute("INSERT INTO fact_stock_daily VALUES ('2026-09-15', '000001.SZ', '旧股')")
    monkeypatch.setattr(module, '_db_path', lambda: str(db))
    api = Mock(return_value=pd.DataFrame([
        {'date': '2026-09-15', 'close': 10.0},
        {'date': '2026-09-16', 'close': 11.0, 'amount': 1e8, 'turnover': .1,
         'open': 10.0, 'high': 11.1, 'low': 9.9, 'volume': 1e7},
    ]))
    monkeypatch.setitem(sys.modules, 'akshare', SimpleNamespace(stock_zh_a_daily=api))
    out = tmp_path / 'rows.jsonl'
    old = {'trade_date': '2026-09-16', 'stock_ts_code': '000001.SZ', 'source': module.SOURCE}
    out.write_text(json.dumps(old) + '\n')
    snapshot = tmp_path / 'snapshot.json'
    snapshot.write_text(json.dumps([{'f12': '600001', 'f14': '新身份', 'f297': 20260917, 'f2': 999.0}]))
    args = argparse.Namespace(trade_date='2026-09-16', out=str(out), resume=True,
                              universe_snapshot=str(snapshot))
    return module, api, out, snapshot, args


def test_resume_preserves_existing_and_fetches_history_for_new_identity(capture):
    module, api, out, _, args = capture
    before = out.read_text()
    assert module.cmd_fetch(args) == 0
    assert out.read_text().startswith(before)
    rows = [json.loads(s) for s in out.read_text().splitlines()]
    assert len(rows) == 2
    assert rows[-1]['close'] == 11.0  # Never 999 from today's snapshot.
    assert rows[-1]['stock_ts_code'] == '600001.SH'
    assert api.call_args.kwargs['symbol'] == 'sh600001'


def test_resume_rejects_wrong_source_before_network_or_write(capture):
    module, api, out, _, args = capture
    out.write_text(json.dumps({'trade_date': '2026-09-16', 'source': 'wrong'}) + '\n')
    before = out.read_bytes()
    with pytest.raises(ValueError, match='date/source'):
        module.cmd_fetch(args)
    api.assert_not_called()
    assert out.read_bytes() == before


def test_ipo_reference_requires_exact_listing_day_and_positive_price(capture):
    module, _, _, _, _ = capture
    api = SimpleNamespace(stock_ipo_info=Mock(return_value=pd.DataFrame([
        {'item': '上市日期', 'value': '2026-09-16'},
        {'item': '发行价(元)', 'value': '27.60'},
    ])))
    assert module._ipo_reference(api, '688837.SH', '2026-09-16')['issue_price'] == 27.60
    with pytest.raises(ValueError, match='listing day'):
        module._ipo_reference(api, '688837.SH', '2026-09-15')
    api.stock_ipo_info.return_value.loc[1, 'value'] = 'nan'
    with pytest.raises(ValueError, match='issue price'):
        module._ipo_reference(api, '688837.SH', '2026-09-16')


def test_ipo_capture_retains_reference_and_exclusion_name(capture):
    module, api, out, _, args = capture
    api.return_value = api.return_value.iloc[1:]
    sys.modules['akshare'].stock_ipo_info = Mock(return_value=pd.DataFrame([
        {'item': '上市日期', 'value': '2026-09-16'},
        {'item': '发行价(元)', 'value': '5.00'},
    ]))
    assert module.cmd_fetch(args) == 0
    row = json.loads(out.read_text().splitlines()[-1])
    assert row['pre_close'] == 5.0
    assert row['pct_chg'] == 120.0
    assert row['stock_name'] == 'N新身份'
    assert row['ipo_reference']['pre_close_source'] == 'sina:stock_ipo_info'


def test_resume_rejects_unverified_snapshot(capture):
    module, api, out, snapshot, args = capture
    snapshot.write_text('[{"f12":"600001"}]')
    before = out.read_bytes()
    with pytest.raises(ValueError, match='verified later'):
        module.cmd_fetch(args)
    api.assert_not_called()
    assert out.read_bytes() == before
