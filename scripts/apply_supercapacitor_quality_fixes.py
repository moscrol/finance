#!/usr/bin/env python3
import json
import shutil
from datetime import date, datetime
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
EXPOSURES = WIKI / 'relations/entity_exposures.json'
OUT = WIKI / 'raw/theme-radar/supercapacitor-quality-fix-result.json'
THEME = '超级电容'

MARKET_SIGNAL_COMPANIES = [
    '三花智控', '东山精密', '东方财富', '东阳光', '中兴通讯', '中际旭创', '京东方A', '亿纬锂能',
    '宁德时代', '思源电气', '恩捷股份', '格力电器', '比亚迪', '汇川技术', '浪潮信息', '海康威视',
    '润泽科技', '深南电路', '潍柴动力', '盐湖股份', '立讯精密', '阳光电源', '顺丰控股', '鹏鼎控股',
]

PATCHES = {
    '先导智能': {
        'chain_layer': 'upstream_equipment',
        'role': '干法电极/电池设备供应商，技术可迁移至超级电容生产',
        'update_type': 'curated_research',
        'evidence_layer': 'L1_L3_candidate',
        'fact_hardness': 'research_claim',
        'source_quality': 'broker_research_normal',
        'confidence': 'medium',
        'review_required': True,
    },
    '天赐材料': {
        'chain_layer': 'upstream_materials',
        'role': '超级电容电解液/电容化学品相关供应商',
        'fact_hardness': 'review_candidate',
        'source_quality': 'broker_research_normal',
        'confidence': 'medium',
        'review_required': True,
    },
    '新宙邦': {
        'chain_layer': 'upstream_materials',
        'role': '电容器电解液/超级电容电解液供应商',
        'fact_hardness': 'review_candidate',
        'source_quality': 'broker_research_normal',
        'confidence': 'medium',
        'review_required': True,
    },
    '江海股份': {
        'chain_layer': 'midstream_manufacturing',
        'role': '超级电容器及电极箔相关厂商',
        'fact_hardness': 'review_candidate',
        'source_quality': 'broker_research_normal',
        'confidence': 'medium',
        'review_required': True,
    },
    '中材科技': {
        'chain_layer': 'upstream_materials',
        'role': '超级电容活性炭相关供应商',
        'fact_hardness': 'review_candidate',
        'source_quality': 'broker_research_normal',
        'confidence': 'medium',
        'review_required': True,
    },
    '元力股份': {
        'chain_layer': 'upstream_materials',
        'role': '超级电容炭供应商',
        'update_type': 'curated_research',
        'evidence_layer': 'L1_L3_candidate',
        'fact_hardness': 'review_candidate',
        'source_quality': 'broker_research_normal',
        'confidence': 'medium',
        'review_required': True,
    },
    '凯恩股份': {
        'chain_layer': 'upstream_materials',
        'role': '超级电容隔膜纸相关供应商',
        'update_type': 'curated_research',
        'evidence_layer': 'L1_L3_candidate',
        'fact_hardness': 'review_candidate',
        'source_quality': 'broker_research_normal',
        'confidence': 'medium',
        'review_required': True,
    },
    '沧州明珠': {
        'chain_layer': 'upstream_materials',
        'role': '超级电容隔膜/包装膜材料待核验供应商',
        'update_type': 'curated_research',
        'evidence_layer': 'L1_L3_candidate',
        'fact_hardness': 'review_candidate',
        'source_quality': 'broker_research_normal',
        'confidence': 'medium',
        'review_required': True,
    },
}

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


def load_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def main():
    data = load_json(EXPOSURES)
    backup = EXPOSURES.with_name(f'entity_exposures.backup-supercapacitor-quality-{datetime.now().strftime("%Y%m%d-%H%M%S")}.json')
    shutil.copy2(EXPOSURES, backup)
    today = date.today().isoformat()
    changes = []
    missing = []
    for company, fields in PATCHES.items():
        exp = data.get('entities', {}).get(company, {}).get('concepts', {}).get(THEME)
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
