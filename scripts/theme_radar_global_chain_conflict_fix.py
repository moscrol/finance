#!/usr/bin/env python3
import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
AUDIT = WIKI / 'raw/theme-radar/theme-radar-chain-conflict-audit.json'
EXPOSURES = WIKI / 'relations/entity_exposures.json'
RESULT = WIKI / 'raw/theme-radar/theme-radar-chain-conflict-fix-result.json'


def load_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def backup(path):
    target = Path(str(path) + '.bak-theme-radar-chain-conflict-' + datetime.now().strftime('%Y%m%d%H%M%S'))
    shutil.copy2(path, target)
    return str(target.relative_to(WIKI))


def get_exp(data, theme, company):
    ent = (data.get('entities') or {}).get(company) or {}
    return (ent.get('concepts') or {}).get(theme)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--limit', type=int, default=0)
    parser.add_argument('--include-related', action='store_true')
    args = parser.parse_args()
    audit = load_json(AUDIT)
    exposures = load_json(EXPOSURES)
    rows = []
    for item in audit.get('candidates', []):
        if item.get('strength') != 'peripheral' and not args.include_related:
            rows.append({'theme': item.get('theme'), 'company': item.get('company'), 'status': 'skip_non_peripheral', 'changes': []})
            continue
        exp = get_exp(exposures, item.get('theme'), item.get('company'))
        if exp is None:
            rows.append({'theme': item.get('theme'), 'company': item.get('company'), 'status': 'missing_exp', 'changes': []})
            continue
        old = exp.get('chain_layer')
        new = item.get('suggested_chain_layer')
        if old == new:
            rows.append({'theme': item.get('theme'), 'company': item.get('company'), 'status': 'unchanged', 'changes': []})
            continue
        rows.append({'theme': item.get('theme'), 'company': item.get('company'), 'status': 'change', 'changes': [{'field': 'chain_layer', 'old': old, 'new': new, 'reason': 'global high-confidence role-derived chain_layer fix'}]})
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
    applied_rows = [r for r in rows if r['status'] == 'change']
    backups = []
    if args.apply and applied_rows:
        backups.append(backup(EXPOSURES))
        exposures['updated'] = datetime.now().date().isoformat()
        write_json(EXPOSURES, exposures)
    result = {
        'timestamp': datetime.now().isoformat(timespec='seconds'),
        'mode': 'apply' if args.apply else 'dry_run',
        'source': str(AUDIT.relative_to(WIKI)),
        'target': str(EXPOSURES.relative_to(WIKI)),
        'include_related': args.include_related,
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
