#!/usr/bin/env python3
import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
REL = WIKI / 'relations'
ADJUDICATION = WIKI / 'raw/theme-radar/theme-radar-quality-auto-adjudication.json'
RESULT = WIKI / 'raw/theme-radar/theme-radar-quality-auto-adjudication-apply-result.json'
EXPOSURES = REL / 'entity_exposures.json'
BACKUP_SUFFIX = '.bak-theme-radar-auto-adjudication'
ALLOWED_FIELDS = {'chain_layer', 'strength', 'review_required', 'fact_hardness', 'update_type'}


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


def action_key(action):
    return (action.get('field'), json.dumps(action.get('value'), ensure_ascii=False, sort_keys=True))


def dedupe_actions(actions):
    seen = set()
    out = []
    for action in actions:
        key = action_key(action)
        if key in seen:
            continue
        seen.add(key)
        out.append(action)
    return out


def should_skip(row, action, include_low_chain):
    field = action.get('field')
    if field not in ALLOWED_FIELDS:
        return 'field_not_allowed'
    if field == 'chain_layer' and row.get('confidence') == 'low' and not include_low_chain:
        return 'low_confidence_chain_layer_skipped'
    if field == 'strength' and action.get('value') == 'peripheral' and row.get('current', {}).get('strength') == 'core':
        return 'core_downgrade_skipped'
    return ''


def main():
    parser = argparse.ArgumentParser(description='Apply Theme Radar auto adjudication actions to entity_exposures.json.')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--include-low-chain', action='store_true')
    parser.add_argument('--only-fields', default='')
    parser.add_argument('--exclude-fields', default='')
    args = parser.parse_args()
    only_fields = {x.strip() for x in args.only_fields.split(',') if x.strip()}
    exclude_fields = {x.strip() for x in args.exclude_fields.split(',') if x.strip()}

    adjudication = load_json(ADJUDICATION)
    exposures = load_json(EXPOSURES)
    applied = []
    skipped = []

    for row in adjudication.get('items', []):
        theme = row.get('theme')
        company = row.get('company')
        exp = get_exposure(exposures, company, theme)
        if exp is None:
            skipped.append({'theme': theme, 'company': company, 'reason': 'exposure_not_found'})
            continue
        changes = []
        for action in dedupe_actions(row.get('actions', [])):
            field = action.get('field')
            if only_fields and field not in only_fields:
                skipped.append({'theme': theme, 'company': company, 'field': field, 'value': action.get('value'), 'reason': 'field_not_in_only_fields'})
                continue
            if field in exclude_fields:
                skipped.append({'theme': theme, 'company': company, 'field': field, 'value': action.get('value'), 'reason': 'field_excluded'})
                continue
            reason = should_skip(row, action, args.include_low_chain)
            if reason:
                skipped.append({'theme': theme, 'company': company, 'field': field, 'value': action.get('value'), 'reason': reason})
                continue
            old = exp.get(field)
            new = action.get('value')
            if old == new:
                continue
            exp[field] = new
            changes.append({'field': field, 'old': old, 'new': new, 'reason': action.get('reason', '')})
        if changes:
            applied.append({'theme': theme, 'company': company, 'confidence': row.get('confidence'), 'changes': changes})

    backups = []
    if args.apply and applied:
        backups.append(backup(EXPOSURES))
        exposures['updated'] = datetime.now().date().isoformat()
        write_json(EXPOSURES, exposures)

    result = {
        'timestamp': datetime.now().isoformat(timespec='seconds'),
        'mode': 'apply' if args.apply else 'dry_run',
        'include_low_chain': args.include_low_chain,
        'source': str(ADJUDICATION.relative_to(WIKI)),
        'target': str(EXPOSURES.relative_to(WIKI)),
        'backups': backups,
        'candidate_pairs': len(adjudication.get('items', [])),
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
