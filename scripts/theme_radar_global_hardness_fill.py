#!/usr/bin/env python3
import argparse
import json
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
QUEUE = WIKI / 'raw/theme-radar/theme-radar-quality-queue-global.json'
EXPOSURES = WIKI / 'relations/entity_exposures.json'
RESULT = WIKI / 'raw/theme-radar/theme-radar-hardness-fill-result.json'
PRIORITY = ('review_candidate', 'research_claim', 'market_narrative', 'legacy_rebuilt')
REVIEW_VALUES = {'review_candidate', 'research_claim', 'market_narrative', 'legacy_rebuilt'}


def load_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def backup(path):
    target = Path(str(path) + '.bak-theme-radar-hardness-fill-' + datetime.now().strftime('%Y%m%d%H%M%S'))
    shutil.copy2(path, target)
    return str(target.relative_to(WIKI))


def get_exp(data, theme, company):
    ent = (data.get('entities') or {}).get(company) or {}
    return (ent.get('concepts') or {}).get(theme)


def infer_hardness(item):
    vals = Counter((ev.get('fact_hardness') or 'unknown') for ev in item.get('evidence_items') or [])
    for v in PRIORITY:
        if vals.get(v):
            return v
    return ''


def build_rows(queue, exposures):
    rows = []
    seen = set()
    for item in queue.get('items', []):
        if item.get('issue') != 'curated_research_needs_hardness':
            continue
        key = (item.get('theme'), item.get('company'))
        if key in seen:
            continue
        seen.add(key)
        hardness = infer_hardness(item)
        if not hardness:
            rows.append({'theme': key[0], 'company': key[1], 'status': 'skip_no_safe_hardness', 'hardness': '', 'changes': []})
            continue
        exp = get_exp(exposures, key[0], key[1])
        if exp is None:
            rows.append({'theme': key[0], 'company': key[1], 'status': 'missing_exp', 'hardness': hardness, 'changes': []})
            continue
        current = str(exp.get('fact_hardness') or '').strip()
        if current:
            rows.append({'theme': key[0], 'company': key[1], 'status': 'skip_existing_hardness', 'hardness': hardness, 'changes': []})
            continue
        changes = [{'field': 'fact_hardness', 'old': exp.get('fact_hardness'), 'new': hardness}]
        if hardness in REVIEW_VALUES and exp.get('review_required') is not True:
            changes.append({'field': 'review_required', 'old': exp.get('review_required'), 'new': True})
        rows.append({'theme': key[0], 'company': key[1], 'status': 'change', 'hardness': hardness, 'changes': changes})
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--limit', type=int, default=0)
    parser.add_argument('--hardness', default='')
    args = parser.parse_args()
    queue = load_json(QUEUE)
    exposures = load_json(EXPOSURES)
    rows = build_rows(queue, exposures)
    if args.hardness:
        wanted = {x.strip() for x in args.hardness.split(',') if x.strip()}
        rows = [r for r in rows if r.get('hardness') in wanted or r['status'] != 'change']
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
        'hardness_counts': dict(Counter(r.get('hardness') for r in applied_rows)),
        'status_counts': {s: sum(1 for r in rows if r['status'] == s) for s in sorted({r['status'] for r in rows})},
        'rows': rows,
    }
    write_json(RESULT, result)
    print(json.dumps({k: v for k, v in result.items() if k != 'rows'}, ensure_ascii=False, indent=2))
    print(RESULT)


if __name__ == '__main__':
    main()
