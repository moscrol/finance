#!/usr/bin/env python3
import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
REL = WIKI / 'relations'
CANDIDATES = WIKI / 'raw/theme-radar/theme-radar-quality-apply-candidates.json'
RESULT = WIKI / 'raw/theme-radar/theme-radar-quality-apply-result.json'
EXPOSURES = REL / 'entity_exposures.json'
BACKUP_SUFFIX = '.bak-theme-radar-quality'
ALLOWED_FIELDS = {'chain_layer', 'update_type', 'fact_hardness', 'review_required'}


def load_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def backup(path):
    stamp = datetime.now().strftime('%Y%m%d%H%M%S')
    target = Path(str(path) + BACKUP_SUFFIX + '-' + stamp)
    shutil.copy2(path, target)
    return str(target.relative_to(WIKI))


def get_exposure(exposures, company, theme):
    entity = (exposures.get('entities') or {}).get(company) or {}
    return ((entity.get('concepts') or {}).get(theme) or None)


def apply_action(exp, action):
    field = action.get('field')
    if field not in ALLOWED_FIELDS:
        return False, f'field_not_allowed:{field}'
    old = exp.get(field)
    new = action.get('suggested_value')
    if old == new:
        return False, 'unchanged'
    exp[field] = new
    return True, 'updated'


def main():
    parser = argparse.ArgumentParser(description='Apply low-risk Theme Radar quality candidates to entity_exposures.json.')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--limit', type=int, default=0)
    args = parser.parse_args()

    candidates = load_json(CANDIDATES)
    exposures = load_json(EXPOSURES)
    rows = candidates.get('auto_safe_candidates', [])
    if args.limit:
        rows = rows[:args.limit]

    applied = []
    skipped = []
    for row in rows:
        theme = row.get('theme')
        company = row.get('company')
        exp = get_exposure(exposures, company, theme)
        if exp is None:
            skipped.append({'theme': theme, 'company': company, 'reason': 'exposure_not_found'})
            continue
        changes = []
        for action in row.get('actions', []):
            field = action.get('field')
            old = exp.get(field)
            ok, status = apply_action(exp, action)
            if ok:
                changes.append({'field': field, 'old': old, 'new': action.get('suggested_value'), 'reason': action.get('reason', '')})
            elif status != 'unchanged':
                skipped.append({'theme': theme, 'company': company, 'reason': status})
        if changes:
            applied.append({'theme': theme, 'company': company, 'changes': changes})

    backups = []
    if args.apply and applied:
        backups.append(backup(EXPOSURES))
        exposures['updated'] = datetime.now().date().isoformat()
        write_json(EXPOSURES, exposures)

    result = {
        'timestamp': datetime.now().isoformat(timespec='seconds'),
        'mode': 'apply' if args.apply else 'dry_run',
        'source_candidates': str(CANDIDATES.relative_to(WIKI)),
        'target': str(EXPOSURES.relative_to(WIKI)),
        'backups': backups,
        'candidate_count': len(rows),
        'would_apply_count' if not args.apply else 'applied_count': len(applied),
        'skipped_count': len(skipped),
        'applied': applied,
        'skipped': skipped,
    }
    RESULT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k not in {'applied', 'skipped'}}, ensure_ascii=False, indent=2))
    print(str(RESULT))


if __name__ == '__main__':
    main()
