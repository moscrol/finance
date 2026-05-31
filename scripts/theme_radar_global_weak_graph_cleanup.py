#!/usr/bin/env python3
import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
QUEUE = WIKI / 'raw/theme-radar/theme-radar-quality-queue-global.json'
EXPOSURES = WIKI / 'relations/entity_exposures.json'
RESULT = WIKI / 'raw/theme-radar/theme-radar-weak-graph-cleanup-result.json'
WEAK_TOKENS = ('图谱弱关联', '市场信号弱关联', '弱相关', '待验证', '潜在相关', '从既有entity markdown重建', '从既有concept markdown重建')
GENERIC_ROLES = {'', '受益标的', '待验证受益标的', '产业链供应商', '相关公司', '中游制造', '图谱弱关联', '市场信号弱关联'}


def load_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def backup(path):
    target = Path(str(path) + '.bak-theme-radar-weak-graph-' + datetime.now().strftime('%Y%m%d%H%M%S'))
    shutil.copy2(path, target)
    return str(target.relative_to(WIKI))


def get_exp(data, theme, company):
    ent = (data.get('entities') or {}).get(company) or {}
    return (ent.get('concepts') or {}).get(theme)


def weak_enough(item):
    role = str(item.get('role') or '').strip()
    text = ' '.join(str(item.get(k) or '') for k in ('role', 'evidence_sample', 'update_type', 'bucket'))
    return role in GENERIC_ROLES or any(token in text for token in WEAK_TOKENS)


def build_rows(queue, exposures, include_core=False):
    rows = []
    seen = set()
    for item in queue.get('items', []):
        if item.get('issue') != 'graph_only_core_or_related':
            continue
        key = (item.get('theme'), item.get('company'))
        if key in seen:
            continue
        seen.add(key)
        if item.get('strength') == 'core' and not include_core:
            rows.append({'theme': key[0], 'company': key[1], 'status': 'skip_core', 'changes': []})
            continue
        if item.get('bucket') not in {'graph_only', 'missing'} or not weak_enough(item):
            rows.append({'theme': key[0], 'company': key[1], 'status': 'skip_not_weak_enough', 'changes': []})
            continue
        exp = get_exp(exposures, key[0], key[1])
        if exp is None:
            rows.append({'theme': key[0], 'company': key[1], 'status': 'missing_exp', 'changes': []})
            continue
        changes = []
        for field, new in {'strength': 'peripheral', 'review_required': True}.items():
            old = exp.get(field)
            if old != new:
                changes.append({'field': field, 'old': old, 'new': new})
        if not exp.get('fact_hardness') and '从既有' in str(exp.get('evidence') or ''):
            changes.append({'field': 'fact_hardness', 'old': exp.get('fact_hardness'), 'new': 'legacy_rebuilt'})
        rows.append({'theme': key[0], 'company': key[1], 'status': 'change' if changes else 'unchanged', 'changes': changes})
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--include-core', action='store_true')
    parser.add_argument('--limit', type=int, default=0)
    args = parser.parse_args()
    queue = load_json(QUEUE)
    exposures = load_json(EXPOSURES)
    rows = build_rows(queue, exposures, args.include_core)
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
        'include_core': args.include_core,
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
