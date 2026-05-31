#!/usr/bin/env python3
import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
QUEUE = WIKI / 'raw/theme-radar/theme-radar-quality-queue-global.json'
EXPOSURES = WIKI / 'relations/entity_exposures.json'
RESULT = WIKI / 'raw/theme-radar/theme-radar-baseline-merge-result.json'


def load_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def backup(path):
    target = Path(str(path) + '.bak-theme-radar-baseline-merge-' + datetime.now().strftime('%Y%m%d%H%M%S'))
    shutil.copy2(path, target)
    return str(target.relative_to(WIKI))


def get_exp(data, theme, company):
    ent = (data.get('entities') or {}).get(company) or {}
    return (ent.get('concepts') or {}).get(theme)


def has_baseline_evidence(item):
    for ev in item.get('evidence_items') or []:
        if ev.get('fact_hardness') == 'baseline':
            return True
        text = ' '.join(str(ev.get(k) or '') for k in ('source', 'evidence'))
        if 'baseline' in text or '基础资料' in text or '主营' in text:
            return True
    return False


def build_rows(queue, exposures):
    rows = []
    seen = set()
    for item in queue.get('items', []):
        if item.get('issue') != 'baseline_scope_mismatch':
            continue
        key = (item.get('theme'), item.get('company'))
        if key in seen:
            continue
        seen.add(key)
        if not has_baseline_evidence(item):
            rows.append({'theme': key[0], 'company': key[1], 'status': 'skip_no_baseline_evidence', 'changes': []})
            continue
        exp = get_exp(exposures, key[0], key[1])
        if exp is None:
            rows.append({'theme': key[0], 'company': key[1], 'status': 'missing_exp', 'changes': []})
            continue
        current_hardness = str(exp.get('fact_hardness') or '').strip()
        if current_hardness not in {'', 'unknown', 'legacy_rebuilt', 'baseline'}:
            rows.append({'theme': key[0], 'company': key[1], 'status': 'skip_existing_hardness', 'changes': []})
            continue
        changes = []
        for field, new in {'update_type': 'baseline', 'fact_hardness': 'baseline'}.items():
            old = exp.get(field)
            if old != new:
                changes.append({'field': field, 'old': old, 'new': new})
        rows.append({'theme': key[0], 'company': key[1], 'status': 'change' if changes else 'unchanged', 'changes': changes})
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--limit', type=int, default=0)
    args = parser.parse_args()
    queue = load_json(QUEUE)
    exposures = load_json(EXPOSURES)
    rows = build_rows(queue, exposures)
    change_rows = [r for r in rows if r['status'] == 'change']
    if args.limit:
        allowed = {(r['theme'], r['company']) for r in change_rows[:args.limit]}
        rows = [r for r in rows if r['status'] != 'change' or (r['theme'], r['company']) in allowed]
    if args.apply:
        for row in rows:
            if row['status'] != 'change':
                continue
            exp = get_exp(exposures, row['theme'], row['company'])
            for change in row['changes']:
                exp[change['field']] = change['new']
    backups = []
    applied_rows = [r for r in rows if r['status'] == 'change']
    if args.apply and applied_rows:
        backups.append(backup(EXPOSURES))
        exposures['updated'] = datetime.now().date().isoformat()
        write_json(EXPOSURES, exposures)
    result = {
        'timestamp': datetime.now().isoformat(timespec='seconds'),
        'mode': 'apply' if args.apply else 'dry_run',
        'backups': backups,
        'rows_count': len(rows),
        'change_rows_count': len(applied_rows),
        'changes_count': sum(len(r['changes']) for r in applied_rows),
        'status_counts': {s: sum(1 for r in rows if r['status'] == s) for s in sorted({r['status'] for r in rows})},
        'rows': rows,
    }
    write_json(RESULT, result)
    print(json.dumps({k: v for k, v in result.items() if k != 'rows'}, ensure_ascii=False, indent=2))
    print(RESULT)


if __name__ == '__main__':
    main()
