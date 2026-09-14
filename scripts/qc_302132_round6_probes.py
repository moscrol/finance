#!/usr/bin/env python3
"""Read-only acceptance replay and isolated receipt mutations for round-six review.

Only the disposable CoW copy and copied receipts under --output-dir are modified.
No repair entrypoint is called. Original artifacts and backups remain read-only.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--artifact-root', type=Path, required=True)
    ap.add_argument('--output-dir', type=Path, required=True)
    ap.add_argument('--source-mutation-only', action='store_true')
    ap.add_argument('--expect-fixed', action='store_true',
                    help='Exit 2 unless baseline PASS and every mutation gives structured FAIL rc=2')
    args = ap.parse_args()
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=False)
    source = args.artifact_root / 'fake-prod.duckdb'
    runs = {'apply': 'efc2b64d8870', 'verify': '11bad970c4e1'}
    originals = {
        tag: json.loads(Path(str(source) + f'.repair-backfill-execution.{rid}.json').read_text())
        for tag, rid in runs.items()
    }
    baseline = Path(originals['apply']['backup']['backup_path'])
    baseline_sha = originals['apply']['backup']['backup_sha256']
    revision = originals['apply']['code_revision']
    pq = args.artifact_root.parent / 'daily-k-10d.parquet'
    script = Path(__file__).with_name('verify_302132_backfill_acceptance.py')
    results = []
    artifact_paths = sorted(args.artifact_root.glob('*.json'))
    artifact_paths += sorted(args.artifact_root.glob('receipts-*/*.json'))
    before = {str(p): sha256(p) for p in artifact_paths}

    def final_rc():
        if not args.expect_fixed:
            return 0  # Diagnostic mode records observed behavior, not a green gate.
        ok = all(
            (r['rc'] == 0 and r.get('verdict') == 'PASS')
            if r['case'] == 'baseline_real_artifacts'
            else (r['rc'] == 2 and r.get('verdict') == 'FAIL')
            for r in results
        )
        return 0 if ok else 2

    def run(label, clone, expected_revision=revision, extras=()):
        report = out / f'{label}.json'
        command = [sys.executable, str(script), '--production', str(baseline),
                   '--clone', str(clone), '--parquet', str(pq),
                   '--run-apply', runs['apply'], '--run-verify', runs['verify'],
                   '--expected-revision', expected_revision,
                   '--expected-production-sha256', baseline_sha,
                   *extras, '--output', str(report)]
        process = subprocess.run(command, capture_output=True, text=True, timeout=240)
        (out / f'{label}.log').write_text(process.stdout + process.stderr)
        result = {'case': label, 'rc': process.returncode,
                  'output_exists': report.exists(), 'stdout': process.stdout.strip(),
                  'stderr_tail': process.stderr[-1000:]}
        if report.exists():
            data = json.loads(report.read_text())
            result.update(verdict=data['verdict'], failed=data['failed'],
                          n=len(data['checks']))
        results.append(result)
        print(json.dumps(result, ensure_ascii=False), flush=True)
        (out / 'summary.json').write_text(json.dumps(results, ensure_ascii=False, indent=2))

    # Old receipts: compare stored v5 prefixes independently before freezing their
    # current full hashes. This is NOT a proof of their historic full SHA256.
    v5 = json.loads((args.artifact_root / 'dryrun-acceptance-v5.json').read_text())
    old_prefixes = {c['name'].split(':', 1)[1]: c['detail'] for c in v5['checks']
                    if c['name'].startswith('old_receipt:')}
    old_args, old_manifest = [], []
    for p in sorted(args.artifact_root.glob('receipts-*/*.json')):
        digest = sha256(p)
        assert digest.startswith(old_prefixes[p.name])
        old_args += ['--expected-old-receipt', f'{p}={digest}']
        old_manifest.append({'path': str(p), 'sha256': digest,
                             'v5_prefix': old_prefixes[p.name]})
    (out / 'old-receipts-review-snapshot.json').write_text(
        json.dumps(old_manifest, ensure_ascii=False, indent=2))
    if not args.source_mutation_only:
        run('baseline_real_artifacts', source, extras=old_args)

    clone = out / 'disposable.duckdb'
    subprocess.run(['cp', '-c', str(source), str(clone)], check=True)

    def install(mutation):
        for tag, rid in runs.items():
            receipt = copy.deepcopy(originals[tag])
            mutation(tag, receipt)
            child_path = out / f'child-{rid}.json'
            child_path.write_text(json.dumps(receipt['child_report']))
            receipt['child_report_path'] = str(child_path)
            Path(str(clone) + f'.repair-backfill-execution.{rid}.json').write_text(
                json.dumps(receipt))

    if args.source_mutation_only:
        import duckdb
        install(lambda tag, r: None)
        # Ordinary data mutation: alter an authorized output cell and its source
        # in the disposable result together. Frozen baseline/receipts unchanged.
        with duckdb.connect(str(clone)) as con:
            before_open = con.execute("SELECT open FROM fact_stock_daily "
                                      "WHERE stock_ts_code='302132.SZ' "
                                      "AND trade_date='2026-07-02'").fetchone()[0]
            con.execute("UPDATE fact_stock_daily SET open=open+1 "
                        "WHERE stock_ts_code='302132.SZ' "
                        "AND trade_date='2026-07-02'")
            con.execute("UPDATE fact_stock_daily_hithink SET open=open+1 "
                        "WHERE stock_ts_code='302132.SZ' "
                        "AND trade_date='2026-07-02' AND adjusted='none'")
        (out / 'source-mutation.json').write_text(json.dumps({
            'date': '2026-07-02', 'field': 'open', 'before': before_open,
            'after': before_open + 1, 'tables': [
                'fact_stock_daily', 'fact_stock_daily_hithink']}))
        run('output_and_source_corrupted_together', clone)
        after = {str(p): sha256(p) for p in artifact_paths}
        assert before == after
        (out / 'original-artifacts-unchanged.json').write_text(json.dumps({
            'unchanged': True, 'sha256': after}, indent=2))
        clone.unlink()
        return final_rc()

    def verify_other_parquet(tag, r):
        if tag == 'verify':
            r['spec']['parquet_sha256'] = '0' * 64
            r['child_report']['parquet_sha256'] = '0' * 64
    install(verify_other_parquet)
    run('verify_other_parquet', clone)

    def missing_child_source_identity(tag, r):
        r['child_report'].pop('parallel_source_md5')
    install(missing_child_source_identity)
    run('missing_parallel_source_md5', clone)

    def missing_nested_pin(tag, r):
        r['spec']['pinned_technical_0911'].pop('ma26')
    install(missing_nested_pin)
    run('missing_nested_ma26', clone)

    def malformed_revision(tag, r):
        r['code_revision'] = 'not-a-git-revision'
        r['child_report']['code_revision'] = 'not-a-git-revision'
    install(malformed_revision)
    run('malformed_revision', clone, expected_revision='not-a-git-revision')

    def false_child_success(tag, r):
        r['child_report']['ok'] = False
    install(false_child_success)
    run('child_ok_false', clone)

    def empty_counts(tag, r):
        r['spec']['expected_window_counts'] = {}
    install(empty_counts)
    run('empty_expected_window_counts', clone)

    after = {str(p): sha256(p) for p in artifact_paths}
    assert before == after
    (out / 'original-artifacts-unchanged.json').write_text(json.dumps({
        'unchanged': before == after, 'sha256': after}, indent=2))
    clone.unlink()  # Only our specifically named disposable CoW database.
    return final_rc()


if __name__ == '__main__':
    raise SystemExit(main())
