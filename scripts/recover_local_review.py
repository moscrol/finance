"""Recover dated local reviews through the existing guarded staging publisher.

Never substitute a live snapshot for a historical day. Capture the latest raw
Eastmoney snapshot and validated Sina JSONL first. All writes happen in a child
on MARKET_FEATURE_STORE_DB=.staging; only a fully successful, run-bound status
allows run_daily_full_staged to publish. Reuses the local plan and both gates.
The stock anchor for the later day is loaded first, but derived days are ordered.

Hash-bound Tencent manifests support input preparation only, in a new isolated
--prepare-dir. This mode returns 2 (not releasable), even when input preparation
succeeds. It never runs derived steps or publishes an incomplete database.
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


def recovery_stitch_command(sync, day: str, history_day: str) -> list[str]:
    # Recovery replaces base facts: an old success receipt is not proof that
    # materialized member rows still match those facts.
    command = sync.CLI + ['stitch-sector-stocks', '--trade-date', day,
                          '--max-baseline-age-days', '180', '--include-completed']
    if day == history_day:
        command.append('--no-caps')
    return command


def prepare_quote_child(args) -> int:
    from market_feature_store import db
    from market_feature_store.sync.sync_mootdx_stock_daily import BULK_UPSERT_SQL, COLS
    from scripts.dated_quote_recovery import load_manifest
    import pandas as pd

    if not args.prepare_dir or db.DB_PATH.resolve().parent != args.prepare_dir.resolve():
        raise RuntimeError('quote inputs require the isolated preparation directory')
    prepared = load_manifest(args.quote_manifest, args.quote_manifest_sha256)
    rows = [row for day in prepared for row in day.rows]
    dates = [day.trade_date for day in prepared]
    con = db.connect()
    try:
        con.execute('BEGIN TRANSACTION')
        try:
            if con.execute('SELECT count(*) FROM fact_stock_daily WHERE trade_date IN '
                           '(SELECT unnest(?::DATE[]))', [dates]).fetchone()[0]:
                raise RuntimeError('quote preparation refuses existing target-day stock rows')
            con.register('_buf_df', pd.DataFrame(rows, columns=COLS))
            try:
                con.execute(BULK_UPSERT_SQL)
            finally:
                con.unregister('_buf_df')
            readback = con.execute(f'SELECT {", ".join(COLS)} FROM fact_stock_daily '
                                   'WHERE trade_date IN (SELECT unnest(?::DATE[]))', [dates]).fetchall()
            if len(readback) != len(rows) or set(readback) != set(rows):
                raise RuntimeError('quote preparation readback differs from validated inputs')
            con.execute('COMMIT')
        except Exception:
            con.execute('ROLLBACK')
            raise
    finally:
        con.close()
    status = {'run_id': os.environ['MARKET_FEATURE_STORE_RUN_ID'],
              'trade_date': str(dates[-1]), 'ok': False, 'input_prepared': True,
              'quality_gates_attempted': False, 'publication_attempted': False,
              'steps': [{'label': 'dated-quote-inputs', 'status': 'prepared',
                         'days': [day.evidence for day in prepared], 'written_rows': len(rows)}]}
    with Path(str(db.DB_PATH) + '.status.json').open('x', encoding='utf-8') as handle:
        json.dump(status, handle, ensure_ascii=False, allow_nan=False)
    return 0


def child(args) -> int:
    from market_feature_store import db
    from market_feature_store.sync import sync_eastmoney_stock_snapshot as snapshot_module
    from market_feature_store.write_path import is_canonical_production

    if (not str(db.DB_PATH).endswith('.staging') or not os.environ.get('MARKET_FEATURE_STORE_RUN_ID')
            or is_canonical_production(db.DB_PATH)):
        raise RuntimeError('child requires the staging publisher, not a direct write')
    if getattr(args, 'quote_manifest', None):
        return prepare_quote_child(args)
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
            if name == 'hithink-research':
                # Replay must not mix captured history with newly fetched latest-only observations.
                result = {'label': name, 'status': 'skip', 'code': None, 'elapsed': 0.0,
                          'note': 'latest-only excluded from historical recovery; 研究观察值未更新'}
            elif name == 'stitch-sector-stocks':
                result = sync.run_step(name, recovery_stitch_command(sync, day, args.history_day), 600)
            else:
                result = action()
            results.append({'date': day, **result})
            # Only the local plan's declared optional parallel source may skip.
            # Keep its original skip receipt; required work and failed Hithink
            # requests must still stop before any success status is written.
            optional_skip = name in sync.HITHINK_STEPS and result['status'] == 'skip'
            if result['status'] != 'ok' and not optional_skip:
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
    parser.add_argument('--history-day')
    parser.add_argument('--snapshot-day')
    parser.add_argument('--history', type=Path)
    parser.add_argument('--snapshot', type=Path)
    parser.add_argument('--quote-manifest', type=Path)
    parser.add_argument('--quote-manifest-sha256')
    parser.add_argument('--prepare-dir', type=Path, help='New isolated directory; never publishes')
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--child', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    for name in ('quote_manifest', 'prepare_dir', 'receipt'):
        value = getattr(args, name)
        if value is not None:
            setattr(args, name, value.expanduser().absolute())
    os.environ['REVIEW_SYNC_PLAN'] = 'local'
    legacy = (args.history_day, args.snapshot_day, args.history, args.snapshot)
    quote_options = (args.quote_manifest, args.quote_manifest_sha256, args.prepare_dir)
    if any(quote_options):
        if not all(quote_options) or any(legacy):
            parser.error('quote manifest, SHA256 and prepare directory are required together; no legacy inputs')
        if args.child:
            return child(args)
        from scripts.dated_quote_recovery import load_manifest
        prepared = load_manifest(args.quote_manifest, args.quote_manifest_sha256)
        target_day = str(prepared[-1].trade_date)
        if args.receipt.exists() or args.receipt.is_symlink():
            raise FileExistsError('preparation receipt must be new')
    else:
        if not all(legacy):
            parser.error('history day/file and snapshot day/file are required')
        validate_inputs(args.history_day, args.snapshot_day, args.history, args.snapshot)
        if args.child:
            return child(args)
        target_day = args.snapshot_day
    from market_feature_store import db
    from market_feature_store.sync.sync_daily_full import run_daily_full_staged

    target = Path(os.environ['MARKET_FEATURE_STORE_DB']).resolve(strict=True)
    if target != db.DB_PATH.resolve() or str(target).endswith('.staging'):
        raise RuntimeError('parent requires the explicit existing canonical database')
    child_options = list(argv if argv is not None else sys.argv[1:])
    if args.quote_manifest:
        child_options = ['--quote-manifest', str(args.quote_manifest),
                         '--quote-manifest-sha256', args.quote_manifest_sha256,
                         '--prepare-dir', str(args.prepare_dir), '--receipt', str(args.receipt)]
    command = [sys.executable, '-u', str(Path(__file__).resolve()), *child_options, '--child']
    with nightly_lock():
        kwargs = {'prepare_dir': args.prepare_dir} if args.prepare_dir is not None else {}
        result = run_daily_full_staged(target_day, child_argv=command,
                                       kind='local-review-recovery', pre_swap_backup=True, **kwargs)
    with args.receipt.open('x' if args.quote_manifest else 'w', encoding='utf-8') as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2, default=str, allow_nan=False)
    return result['rc']


if __name__ == '__main__':
    raise SystemExit(main())
