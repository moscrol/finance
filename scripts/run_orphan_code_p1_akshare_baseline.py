#!/usr/bin/env python3
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
FINANCE = Path('/Users/lbq/Desktop/c c/金融')
QUEUE = WIKI / 'raw/theme-radar/orphan-code-baseline-queue.json'
RAW_DIR = WIKI / 'raw/akshare-baseline'
OUT = RAW_DIR / f'baseline-updates-{date.today().isoformat()}-orphan-code-p1-akshare.json'
RESULT = WIKI / 'raw/theme-radar/orphan-code-p1-akshare-baseline-result.json'
FETCH = FINANCE / 'skills/company-baseline-ingest/scripts/fetch_akshare_baseline.py'
BUILD = FINANCE / 'skills/company-baseline-ingest/scripts/build_akshare_baseline_update.py'
WRITER = FINANCE / 'skills/company-baseline-ingest/scripts/entity_baseline_writer.py'


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def main():
    queue = json.loads(QUEUE.read_text(encoding='utf-8'))
    targets = queue['queues']['P1_baseline_priority']
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    fetched = []
    fetch_failed = []
    updates = []
    build_failed = []

    for row in targets:
        company = row['entity']
        code = row['codes'][0] if row.get('codes') else ''
        res = run([sys.executable, str(FETCH), '--company', company, '--code', code, '--out-dir', str(RAW_DIR)])
        if res.returncode == 0:
            try:
                meta = json.loads(res.stdout)
            except json.JSONDecodeError:
                meta = {'stdout': res.stdout}
            fetched.append({'company': company, 'code': code, **meta})
        else:
            fetch_failed.append({'company': company, 'code': code, 'stdout': res.stdout, 'stderr': res.stderr})

    for row in targets:
        company = row['entity']
        raw_file = RAW_DIR / f'{company}.json'
        if not raw_file.exists():
            build_failed.append({'company': company, 'reason': 'raw_file_missing'})
            continue
        tmp_out = RAW_DIR / f'.tmp-{company}-baseline.json'
        cmd = [sys.executable, str(BUILD), '--raw-file', str(raw_file), '--out', str(tmp_out), '--source-name', f'AkShare baseline {date.today().isoformat()} orphan-code-p1']
        for concept in row.get('sample_concepts', [])[:6]:
            cmd.extend(['--concept', concept])
        res = run(cmd)
        if res.returncode != 0:
            build_failed.append({'company': company, 'stdout': res.stdout, 'stderr': res.stderr})
            continue
        data = json.loads(tmp_out.read_text(encoding='utf-8'))
        update = data['updates'][0]
        if not update.get('main_business') or not update.get('products'):
            build_failed.append({'company': company, 'reason': 'missing_main_business_or_products', 'main_business': update.get('main_business'), 'products': update.get('products')})
            continue
        updates.append(update)
        tmp_out.unlink(missing_ok=True)

    batch = {'source_name': f'AkShare baseline {date.today().isoformat()} orphan-code-p1', 'updates': updates}
    OUT.write_text(json.dumps(batch, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    writer_output = None
    writer_error = None
    if updates:
        res = subprocess.run([sys.executable, str(WRITER)], input=json.dumps(batch, ensure_ascii=False), capture_output=True, text=True, check=False)
        if res.returncode == 0:
            try:
                writer_output = json.loads(res.stdout)
            except json.JSONDecodeError:
                writer_output = {'stdout': res.stdout, 'stderr': res.stderr}
        else:
            writer_error = {'returncode': res.returncode, 'stdout': res.stdout, 'stderr': res.stderr}

    result = {
        'targets_count': len(targets),
        'fetched_count': len(fetched),
        'fetch_failed_count': len(fetch_failed),
        'updates_count': len(updates),
        'build_failed_count': len(build_failed),
        'batch_json': str(OUT.relative_to(WIKI)),
        'fetched': fetched,
        'fetch_failed': fetch_failed,
        'build_failed': build_failed,
        'writer_output': writer_output,
        'writer_error': writer_error,
    }
    RESULT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if writer_error:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
