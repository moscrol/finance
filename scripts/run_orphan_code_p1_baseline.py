#!/usr/bin/env python3
import importlib.util
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
FINANCE = Path('/Users/lbq/Desktop/c c/金融')
QUEUE = WIKI / 'raw/theme-radar/orphan-code-baseline-queue.json'
RAW_DIR = WIKI / 'raw/ifind-baseline'
SCRIPTS_DIR = FINANCE / 'skills/company-baseline-ingest/scripts'
ORCH_PATH = SCRIPTS_DIR / 'batch_baseline_orchestrator.py'
WRITER = SCRIPTS_DIR / 'entity_baseline_writer.py'
OUT = RAW_DIR / f'baseline-updates-{date.today().isoformat()}-orphan-code-p1.json'
RESULT = WIKI / 'raw/theme-radar/orphan-code-p1-baseline-result.json'

spec = importlib.util.spec_from_file_location('baseline_orchestrator', ORCH_PATH)
orch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(orch)


def fetch(company, code):
    return orch.fetch_company_raw(company, code)


def main():
    queue = json.loads(QUEUE.read_text(encoding='utf-8'))
    targets = queue['queues']['P1_baseline_priority']
    fetched = []
    fetch_failed = []
    updates = []
    assemble_failed = []

    for row in targets:
        company = row['entity']
        code = row['codes'][0] if row.get('codes') else ''
        ok = fetch(company, code)
        if ok:
            fetched.append({'company': company, 'code': code})
        else:
            fetch_failed.append({'company': company, 'code': code})

    for row in targets:
        company = row['entity']
        code = row['codes'][0] if row.get('codes') else ''
        concepts = row.get('sample_concepts', [])
        up = orch.parse_and_build_update(company, code, concepts)
        if up:
            updates.append(up)
        else:
            assemble_failed.append({'company': company, 'code': code, 'concepts': concepts})

    batch = {
        'source_name': f'iFinD baseline {date.today().isoformat()} orphan-code-p1',
        'updates': updates,
    }
    OUT.write_text(json.dumps(batch, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    writer_output = None
    writer_error = None
    if updates:
        try:
            res = subprocess.run(
                [sys.executable, str(WRITER)],
                input=json.dumps(batch, ensure_ascii=False),
                capture_output=True,
                text=True,
                check=True,
                cwd=str(SCRIPTS_DIR),
            )
            try:
                writer_output = json.loads(res.stdout)
            except json.JSONDecodeError:
                writer_output = {'raw_stdout': res.stdout, 'stderr': res.stderr}
        except subprocess.CalledProcessError as e:
            writer_error = {'returncode': e.returncode, 'stdout': e.stdout, 'stderr': e.stderr}

    result = {
        'targets_count': len(targets),
        'fetched_count': len(fetched),
        'fetch_failed_count': len(fetch_failed),
        'updates_count': len(updates),
        'assemble_failed_count': len(assemble_failed),
        'batch_json': str(OUT.relative_to(WIKI)),
        'fetched': fetched,
        'fetch_failed': fetch_failed,
        'assemble_failed': assemble_failed,
        'writer_output': writer_output,
        'writer_error': writer_error,
    }
    RESULT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if writer_error:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
