#!/usr/bin/env python3
import json
import shutil
from datetime import date, datetime
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
EXPOSURES = WIKI / 'relations/entity_exposures.json'
OUT = WIKI / 'raw/theme-radar/commercial-aerospace-quality-fix-result.json'

PATCHES = {
    'SpaceX': {
        'chain_layer': 'ecosystem',
        'role': '图谱待核验（非直接产业链）',
        'fact_hardness': 'legacy_rebuilt',
        'confidence': 'low',
        'review_required': True,
    },
    '中国星网': {
        'chain_layer': 'ecosystem',
        'role': '图谱待核验（非直接产业链）',
        'fact_hardness': 'legacy_rebuilt',
        'confidence': 'low',
        'review_required': True,
    },
    '蓝箭航天': {
        'chain_layer': 'ecosystem',
        'role': '图谱待核验（非直接产业链）',
        'fact_hardness': 'legacy_rebuilt',
        'confidence': 'low',
        'review_required': True,
    },
    '瑞华泰': {
        'strength': 'peripheral',
        'chain_layer': 'ecosystem',
        'role': '市场信号待核验（非直接产业链）',
        'update_type': 'graph_only',
        'evidence_layer': 'graph_only',
        'fact_hardness': 'legacy_rebuilt',
        'confidence': 'low',
        'review_required': True,
    },
    '金利华电': {
        'strength': 'peripheral',
        'chain_layer': 'ecosystem',
        'role': '市场信号待核验（非直接产业链）',
        'update_type': 'graph_only',
        'evidence_layer': 'graph_only',
        'fact_hardness': 'legacy_rebuilt',
        'confidence': 'low',
        'review_required': True,
    },
    '钧达股份': {
        'strength': 'peripheral',
        'chain_layer': 'ecosystem',
        'role': '市场信号待核验（非直接产业链）',
        'update_type': 'graph_only',
        'evidence_layer': 'graph_only',
        'fact_hardness': 'legacy_rebuilt',
        'confidence': 'low',
        'review_required': True,
    },
    '中国卫通': {
        'chain_layer': 'downstream_operation',
        'role': '卫星通信运营商',
        'update_type': 'baseline',
        'evidence_layer': 'L2',
        'fact_hardness': 'baseline',
        'confidence': 'medium',
        'review_required': True,
    },
    '国机精工': {
        'chain_layer': 'upstream_components',
        'role': '火箭轴承及碳化硅陶瓷热防护瓦供应商',
        'update_type': 'curated_research',
        'evidence_layer': 'L1_L3_candidate',
        'fact_hardness': 'review_candidate',
        'source_quality': 'broker_research_normal',
        'confidence': 'medium',
        'review_required': True,
    },
    '铖昌科技': {
        'chain_layer': 'upstream_components',
        'role': '星载相控阵T/R芯片供应商',
        'update_type': 'curated_research',
        'evidence_layer': 'L1_L3_candidate',
        'fact_hardness': 'review_candidate',
        'source_quality': 'broker_research_normal',
        'confidence': 'medium',
        'review_required': True,
    },
    '福光股份': {
        'chain_layer': 'upstream_components',
        'role': '卫星光学载荷/激光通信光学产品供应商',
        'update_type': 'curated_research',
        'evidence_layer': 'L1_L3_candidate',
        'fact_hardness': 'review_candidate',
        'source_quality': 'broker_research_high',
        'confidence': 'medium',
        'review_required': True,
    },
}


def load_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def main():
    data = load_json(EXPOSURES)
    backup = EXPOSURES.with_name(f'entity_exposures.backup-commercial-aerospace-quality-{datetime.now().strftime("%Y%m%d-%H%M%S")}.json')
    shutil.copy2(EXPOSURES, backup)
    today = date.today().isoformat()
    changes = []
    missing = []
    for company, fields in PATCHES.items():
        exp = data.get('entities', {}).get(company, {}).get('concepts', {}).get('商业航天')
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
