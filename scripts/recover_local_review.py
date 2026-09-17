"""Recover dated local reviews through the existing guarded staging publisher.

Never substitute a live snapshot for a historical day. Capture the latest raw
Eastmoney snapshot and validated Sina JSONL first. All writes happen in a child
on MARKET_FEATURE_STORE_DB=.staging; only a fully successful, run-bound status
allows run_daily_full_staged to publish. Reuses the local plan and both gates.
The stock anchor for the later day is loaded first, but derived days are ordered.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def load_script(relative: str):
    spec = importlib.util.spec_from_file_location(Path(relative).stem, ROOT / relative)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_inputs(history_day: str, snapshot_day: str, history: Path, snapshot: Path):
    from market_feature_store.sync.sync_eastmoney_stock_snapshot import snapshot_trade_date

    if history_day >= snapshot_day:
        raise ValueError("history must precede snapshot")
    raw = json.loads(snapshot.read_text())
    if snapshot_trade_date(raw) != snapshot_day:
        raise ValueError("snapshot actual date differs from requested date")
    rows = [json.loads(line) for line in history.read_text().splitlines() if line.strip()]
    if not rows or any(r.get("trade_date") != history_day for r in rows):
        raise ValueError("empty or misdated historical input")
    codes = [r.get("stock_ts_code") for r in rows]
    if len(codes) != len(set(codes)):
        raise ValueError("duplicate historical stocks")
    if any(r.get("source") not in ("sina:stock_zh_a_daily", "sina:stock_zh_a_cdr_daily") for r in rows):
        raise ValueError("historical provenance mismatch")
    for r in rows:
        if any(not isinstance(r.get(k), (int, float)) or not math.isfinite(r[k])
               for k in ("close", "pre_close", "pct_chg", "amount", "open", "high", "low", "volume")):
            raise ValueError(f"missing/non-finite historical value: {r['stock_ts_code']}")
        if r['close'] <= 0 or r['pre_close'] <= 0 or r['amount'] < 0 or r['volume'] < 0:
            raise ValueError(f"invalid historical price/amount: {r['stock_ts_code']}")
    return raw, rows


@contextmanager
def nightly_lock():
    """Coordinate with installed S7/finalize, which predate the DB run mutex."""
    root = Path(os.environ['FINANCE_WS']).resolve()
    lock = Path(os.environ.get('FINANCE_LOCK_DIR', str(root / 'state/locks'))) / 'daily-full-review.lock'
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.mkdir()  # Existing lock is a refusal; never remove someone else's lock.
    try:
        (lock / 'pid').write_text(str(os.getpid()) + '\n')
        yield
    finally:
        (lock / 'pid').unlink(missing_ok=True)
        lock.rmdir()


def child(args) -> int:
    from market_feature_store import db
    from market_feature_store.sync import sync_eastmoney_stock_snapshot as snapshot_module

    if not str(db.DB_PATH).endswith('.staging') or not os.environ.get('MARKET_FEATURE_STORE_RUN_ID'):
        raise RuntimeError('child requires the staging publisher, not a direct write')
    raw, rows = validate_inputs(args.history_day, args.snapshot_day, args.history, args.snapshot)
    # Replay captured official bytes through the unchanged parser and date gate.
    with patch.object(snapshot_module, 'fetch_snapshot', return_value=raw):
        result = snapshot_module.sync_fact_stock_daily_snapshot(args.snapshot_day)
    print('snapshot replay:', result, flush=True)
    con = db.connect(read_only=True)
    try:
        anchor_count = con.execute(
            'SELECT count(*) FROM fact_stock_daily WHERE trade_date=? AND amount>0',
            [args.snapshot_day],
        ).fetchone()[0]
    finally:
        con.close()
    if len(rows) < anchor_count * 0.99:
        raise RuntimeError(f'history coverage {len(rows)}/{anchor_count} below 99%')
    history_module = load_script('skills/duckdb-backfill/scripts/backfill_stock_daily_sina.py')
    hist_args = argparse.Namespace(trade_date=args.history_day, rows=str(args.history))
    if history_module.cmd_validate(hist_args):
        raise RuntimeError('historical adjacent-day/units validation failed')
    history_module.cmd_write(hist_args)

    sync = load_script('skills/daily-full-review/scripts/run_review_sync.py')
    data_root = Path(os.environ['FINANCE_WS']).resolve()
    sync.RUNLOG = data_root / 'skills/daily-full-review/state/runlog.md'
    os.environ['DUCKDB_SNAPSHOT_OUT_ROOT'] = str(data_root / 'db/snapshots')
    results = []
    for day in (args.history_day, args.snapshot_day):
        plan = sync.build_plan(day, timeout=300, heavy_timeout=600, plan='local')
        for name, action in plan:
            if name in {'db-lock', 'stock-daily'}:
                continue  # Already verified local capture inputs, not live snapshot.
            if name == 'stitch-sector-stocks' and day == args.history_day:
                result = sync.run_step(name, sync.CLI + [name, '--trade-date', day,
                    '--max-baseline-age-days', '180', '--no-caps'], 600)
            else:
                result = action()
            results.append({'date': day, **result})
            if result['status'] != 'ok':
                raise RuntimeError(f'{day} {name} failed; no publish')
    # Cross-day gate sees BOTH dates fully derived; no partially-created calendar row.
    for day in (args.history_day, args.snapshot_day):
        checks, ok = sync.run_release_steps(day, 300, plan='local')
        results.extend({'date': day, **r} for r in checks)
        if not ok:
            raise RuntimeError(f'{day} quality gates failed; no publish')
    alignment = sync.run_step('backfill-alignment', [sys.executable,
        str(ROOT / 'skills/duckdb-backfill/scripts/qa_backfill_align.py'),
        args.history_day, args.snapshot_day, '--plan', 'local',
        '--json', str(args.receipt.with_suffix('.alignment.json'))], 300)
    results.append(alignment)
    if alignment['status'] != 'ok':
        raise RuntimeError('baseline alignment failed; no publish')
    sync.write_runlog(args.snapshot_day, results, True, plan='local')
    status = {'run_id': os.environ['MARKET_FEATURE_STORE_RUN_ID'],
              'trade_date': args.snapshot_day, 'ok': True, 'steps': results}
    Path(str(db.DB_PATH) + '.status.json').write_text(json.dumps(status, ensure_ascii=False))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--history-day', required=True)
    parser.add_argument('--snapshot-day', required=True)
    parser.add_argument('--history', type=Path, required=True)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--child', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    os.environ['REVIEW_SYNC_PLAN'] = 'local'
    validate_inputs(args.history_day, args.snapshot_day, args.history, args.snapshot)
    if args.child:
        return child(args)
    from market_feature_store import db
    from market_feature_store.sync.sync_daily_full import run_daily_full_staged

    target = Path(os.environ['MARKET_FEATURE_STORE_DB']).resolve(strict=True)
    if target != db.DB_PATH.resolve() or str(target).endswith('.staging'):
        raise RuntimeError('parent requires the explicit existing canonical database')
    command = [sys.executable, '-u', str(Path(__file__).resolve()), *(argv or sys.argv[1:]), '--child']
    with nightly_lock():
        result = run_daily_full_staged(args.snapshot_day, child_argv=command,
                                       kind='local-review-recovery', pre_swap_backup=True)
    args.receipt.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return result['rc']


if __name__ == '__main__':
    raise SystemExit(main())
