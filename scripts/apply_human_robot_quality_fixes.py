#!/usr/bin/env python3
import json
import shutil
from datetime import date, datetime
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
EXPOSURES = WIKI / 'relations/entity_exposures.json'
OUT = WIKI / 'raw/theme-radar/human-robot-quality-fix-result.json'

PATCHES = {
    '中研股份': {
        'chain_layer': 'upstream_materials',
        'role': '机器人关节轻量化PEEK材料潜在供应商',
        'review_required': True,
    },
    '埃夫特': {
        'chain_layer': 'midstream_manufacturing',
        'role': '工业机器人整机制造及系统集成供应商',
        'review_required': True,
    },
    '埃斯顿': {
        'role': '自动化核心部件及运动控制系统供应商',
        'review_required': True,
    },
}

MARKET_SIGNAL_COMPANIES = [
    '智微智能', '汇川技术', '瑞芯微', '纽威数控', '绿的谐波', '锐翔智能', '雷赛智能', '领益智造',
]

GRAPH_ONLY_COMPANIES = [
    '光威复材', '双环传动', '柯力传感', '汉威科技', '沃特股份', '科大讯飞', '肇民科技',
]

for company in MARKET_SIGNAL_COMPANIES:
    PATCHES[company] = {
        'strength': 'peripheral',
        'chain_layer': 'ecosystem',
        'role': '市场信号待核验（非直接产业链）',
        'update_type': 'graph_only',
        'evidence_layer': 'graph_only',
        'fact_hardness': 'legacy_rebuilt',
        'confidence': 'low',
        'review_required': True,
    }

for company in GRAPH_ONLY_COMPANIES:
    PATCHES[company] = {
        'strength': 'peripheral',
        'chain_layer': 'ecosystem',
        'role': '图谱待核验（非直接产业链）',
        'confidence': 'low',
        'review_required': True,
    }


def load_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def main():
    data = load_json(EXPOSURES)
    backup = EXPOSURES.with_name(f'entity_exposures.backup-human-robot-quality-{datetime.now().strftime("%Y%m%d-%H%M%S")}.json')
    shutil.copy2(EXPOSURES, backup)
    changes = []
    missing = []
    today = date.today().isoformat()
    for company, fields in PATCHES.items():
        exp = data.get('entities', {}).get(company, {}).get('concepts', {}).get('人形机器人')
        if exp is None:
            missing.append(company)
            continue
        row = {'company': company, 'old': {}, 'new': {}}
        for field, value in fields.items():
            old = exp.get(field)
            if old != value:
                row['old'][field] = old
                row['new'][field] = value
                exp[field] = value
        if row['new']:
            exp['updated'] = today
            changes.append(row)
    data['updated'] = today
    write_json(EXPOSURES, data)
    result = {
        'timestamp': datetime.now().isoformat(timespec='seconds'),
        'target': str(EXPOSURES),
        'backup': str(backup),
        'changed_count': len(changes),
        'missing': missing,
        'changes': changes,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    write_json(OUT, result)
    print(json.dumps({k: v for k, v in result.items() if k != 'changes'}, ensure_ascii=False, indent=2))
    print(str(OUT))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
