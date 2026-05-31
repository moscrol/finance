#!/usr/bin/env python3
import argparse
import json
import subprocess
from pathlib import Path

FIN = Path('/Users/lbq/Desktop/c c/金融')
VAULT = Path('/Users/lbq/Desktop/c c/知识库/wiki')
BACKFILL = FIN / 'scripts/backfill_entities_from_full_reports.py'
PAYLOAD_DIR = VAULT / 'raw/entity-delta-backfill'
RAW_DIR = VAULT.parent / 'raw'

def count_payloads(payload_files):
    summary = {'updates': 0, 'graph_only': 0, 'curated_research': 0, 'hard_delta': 0, 'l2_candidate': 0, 'l1_l3_candidate': 0}
    samples = []
    for file in payload_files:
        path = Path(file)
        data = json.loads(path.read_text(encoding='utf-8'))
        for u in data.get('updates', []) or []:
            graph = bool(u.get('graph_only'))
            exposure = bool(u.get('exposure_only'))
            update_type = u.get('update_type') or ''
            layer = u.get('evidence_layer') or ''
            summary['updates'] += 1
            summary['graph_only'] += int(graph)
            summary['curated_research'] += int(update_type == 'curated_research')
            summary['hard_delta'] += int((not graph) and (not exposure) and update_type != 'curated_research')
            summary['l2_candidate'] += int(layer == 'L2_candidate')
            summary['l1_l3_candidate'] += int(layer == 'L1_L3_candidate')
            if update_type == 'curated_research' and len(samples) < 5:
                samples.append({'source': data.get('source_name'), 'company': u.get('company'), 'concepts': u.get('concepts'), 'layer': layer})
    return summary, samples

def payload_to_raw_name(payload_file):
    stem = Path(payload_file).name.replace('.entity-delta.json', '')
    candidate = RAW_DIR / f'{stem}-full.md'
    if candidate.exists():
        return candidate.name
    matches = sorted(RAW_DIR.glob(f'{stem}*-full.md'))
    return matches[0].name if matches else f'{stem}-full.md'

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--start-after', required=True)
    parser.add_argument('--batches', type=int, default=3)
    parser.add_argument('--limit', type=int, default=10)
    args = parser.parse_args()
    cursor = args.start_after
    results = []
    for idx in range(1, args.batches + 1):
        cmd = ['python3', str(BACKFILL), '--limit', str(args.limit), '--start-after', cursor, '--write-context', '--apply']
        proc = subprocess.run(cmd, cwd=str(FIN), text=True, capture_output=True)
        if proc.returncode != 0:
            results.append({'batch': idx, 'cursor': cursor, 'error': proc.stderr or proc.stdout})
            break
        data = json.loads(proc.stdout)
        payload_files = data.get('payload_files') or []
        summary, samples = count_payloads(payload_files)
        result = {'batch': idx, 'start_after': cursor, 'reports_seen': data.get('reports_seen'), 'payloads': data.get('payloads'), 'written': data.get('written'), 'errors': data.get('errors'), 'summary': summary, 'samples': samples}
        results.append(result)
        if data.get('errors') or summary['hard_delta']:
            break
        if not payload_files:
            break
        cursor = payload_to_raw_name(payload_files[-1])
    print(json.dumps({'final_cursor': cursor, 'results': results}, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
