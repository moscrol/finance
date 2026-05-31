#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

FINANCE = Path(__file__).resolve().parents[1]
WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
THEME_DIR = WIKI / 'raw/theme-radar'
REL = WIKI / 'relations'
QUEUE = THEME_DIR / 'concept-graph-ingest-queue.json'
APPLY_RESULT = THEME_DIR / 'concept-graph-ingest-apply-result.json'
AUDIT_RESULT = THEME_DIR / 'theme-radar-db-quality-audit.json'
RUN_RESULT = THEME_DIR / 'concept-graph-batch-run-result.json'
JSON_FILES = [
    REL / 'concept_graph.json',
    REL / 'entity_exposures.json',
    REL / 'evidence_index.json',
    REL / 'aliases.json',
]


def load_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_run_result(data):
    RUN_RESULT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def tail(path, max_lines=20):
    if not path.exists():
        return ''
    lines = path.read_text(encoding='utf-8', errors='replace').splitlines()
    return '\n'.join(lines[-max_lines:])


def run_script(script_name, log_path):
    with log_path.open('w', encoding='utf-8') as handle:
        proc = subprocess.run(
            [sys.executable, str(FINANCE / 'scripts' / script_name)],
            cwd=str(FINANCE),
            stdout=handle,
            stderr=subprocess.STDOUT,
            text=True,
        )
    if proc.returncode != 0:
        raise RuntimeError(f'{script_name} failed with exit code {proc.returncode}\n{tail(log_path)}')


def validate_relation_jsons():
    for path in JSON_FILES:
        load_json(path)


def run_round(round_no):
    queue_log = Path(f'/tmp/cg_queue_auto{round_no}.out')
    apply_log = Path(f'/tmp/cg_apply_auto{round_no}.out')
    audit_log = Path(f'/tmp/theme_db_verify_auto{round_no}.out')

    run_script('build_concept_graph_ingest_queue.py', queue_log)
    queue = load_json(QUEUE)
    queue_total = int((queue.get('summary') or {}).get('total') or len(queue.get('items') or []))
    if queue_total <= 0:
        return {'round': round_no, 'status': 'empty_queue'}

    run_script('apply_concept_graph_ingest_queue.py', apply_log)
    validate_relation_jsons()
    run_script('audit_theme_radar_database.py', audit_log)

    apply_result = load_json(APPLY_RESULT)
    audit_result = load_json(AUDIT_RESULT)
    summary = audit_result['summary']
    failed_count = int(apply_result.get('failed_count') or 0)
    applied_count = int(apply_result.get('applied_count') or 0)
    if failed_count > 0:
        raise RuntimeError(f'round {round_no} has failed_count={failed_count}')
    if applied_count <= 0:
        return {'round': round_no, 'status': 'no_applied', 'queue_total': queue_total}

    return {
        'round': round_no,
        'status': 'ok',
        'queue_total': queue_total,
        'applied_count': applied_count,
        'failed_count': failed_count,
        'concept_graph_nodes': summary['concept_graph_nodes'],
        'concept_files_missing_graph_count': summary['concept_files_missing_graph_count'],
        'evidence_items': summary['evidence_items'],
        'p1_remaining_visible': len((audit_result.get('queues') or {}).get('P1_concept_graph_ingest') or []),
        'logs': {
            'queue': str(queue_log),
            'apply': str(apply_log),
            'audit': str(audit_log),
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--rounds', type=int, default=1)
    parser.add_argument('--start-round', type=int, default=1)
    args = parser.parse_args()

    if args.rounds <= 0:
        raise SystemExit('--rounds must be positive')

    run_result = {
        'started_at': datetime.now().isoformat(timespec='seconds'),
        'completed_at': '',
        'status': 'running',
        'start_round': args.start_round,
        'rounds_requested': args.rounds,
        'rounds': [],
    }
    write_run_result(run_result)

    try:
        for offset in range(args.rounds):
            round_no = args.start_round + offset
            item = run_round(round_no)
            run_result['rounds'].append(item)
            write_run_result(run_result)
            print(json.dumps(item, ensure_ascii=False, indent=2))
            if item['status'] != 'ok':
                run_result['status'] = item['status']
                break
        else:
            run_result['status'] = 'ok'
    except Exception as exc:
        run_result['status'] = 'failed'
        run_result['error'] = str(exc)
        write_run_result(run_result)
        raise
    finally:
        run_result['completed_at'] = datetime.now().isoformat(timespec='seconds')
        write_run_result(run_result)

    if run_result['status'] != 'ok':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
