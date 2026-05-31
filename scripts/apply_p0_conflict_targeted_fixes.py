#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
TARGET = WIKI / 'relations/entity_exposures.json'
OUT = WIKI / 'raw/theme-radar/p0-conflict-targeted-fixes-apply-result.json'

FIXES = {
    ('先进封装', '上峰水泥'): {
        'role': '投资潜在相关（非直接产业链）',
        'chain_layer': 'ecosystem',
        'strength': 'peripheral',
        'review_required': True,
    },
    ('先进封装', '中国巨石'): {
        'chain_layer': 'upstream_materials',
        'strength': 'peripheral',
        'review_required': True,
    },
    ('先进封装', '中微公司'): {
        'role': '先进封装刻蚀/薄膜沉积设备供应商',
        'chain_layer': 'upstream_equipment',
        'review_required': True,
    },
    ('先进封装', '华海诚科'): {
        'role': '先进封装封装材料供应商',
        'chain_layer': 'upstream_materials',
        'review_required': True,
    },
    ('先进封装', '通富微电'): {
        'chain_layer': 'midstream_service',
    },
    ('商业航天', '乾照光电'): {
        'chain_layer': 'upstream_components',
        'strength': 'peripheral',
        'review_required': True,
    },
    ('固态电池', '中天科技'): {
        'chain_layer': 'upstream_materials',
        'strength': 'peripheral',
        'review_required': True,
    },
    ('固态电池', '纳科诺尔'): {
        'chain_layer': 'upstream_equipment',
    },
    ('固态电池', '赢合科技'): {
        'chain_layer': 'upstream_equipment',
    },
}


def load_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description='Apply targeted fixes for remaining Theme Radar P0 chain-layer conflicts.')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    data = load_json(TARGET)
    changes = []
    for (theme, company), updates in FIXES.items():
        ent = (data.get('entities') or {}).get(company)
        if not ent:
            raise SystemExit(f'missing entity: {company}')
        exp = (ent.get('concepts') or {}).get(theme)
        if not exp:
            raise SystemExit(f'missing exposure: {company}/{theme}')
        row = {'theme': theme, 'company': company, 'changes': []}
        for field, new_value in updates.items():
            old_value = exp.get(field)
            if old_value != new_value:
                row['changes'].append({'field': field, 'old': old_value, 'new': new_value})
                if args.apply:
                    exp[field] = new_value
        if row['changes']:
            changes.append(row)
    backups = []
    if args.apply and changes:
        backup = Path(str(TARGET) + '.bak-p0-conflict-fix-' + datetime.now().strftime('%Y%m%d%H%M%S'))
        shutil.copy2(TARGET, backup)
        backups.append(str(backup.relative_to(WIKI)))
        data['updated'] = datetime.now().date().isoformat()
        write_json(TARGET, data)
    result = {
        'timestamp': datetime.now().isoformat(timespec='seconds'),
        'mode': 'apply' if args.apply else 'dry_run',
        'target': str(TARGET.relative_to(WIKI)),
        'backups': backups,
        'changed_pairs': len(changes),
        'changes': changes,
    }
    write_json(OUT, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
