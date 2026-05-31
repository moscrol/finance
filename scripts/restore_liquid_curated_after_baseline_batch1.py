#!/usr/bin/env python3
import json
from pathlib import Path

REL = Path('/Users/lbq/Desktop/c c/知识库/wiki/relations/entity_exposures.json')
EVID = Path('/Users/lbq/Desktop/c c/知识库/wiki/relations/evidence_index.json')
CONCEPT = '液冷服务器'
RESTORE = {
    '英维克': {
        'chain_layer': 'downstream',
        'evidence': '英维克（002837）：公司是液冷系统集成领域的绝对龙头。',
        'evidence_layer': 'L1_L3_candidate',
        'role': '6.2 核心投资标的评估',
        'strength': 'core',
    },
    '工业富联': {
        'chain_layer': 'downstream',
        'evidence': '工业富联（601138）：公司在液冷服务器制造领域具有规模优势。',
        'evidence_layer': 'L1_L3_candidate',
        'role': '中游制造',
        'strength': 'related',
    },
    '高澜股份': {
        'chain_layer': 'downstream',
        'evidence': '高澜股份在液冷业务方面发力显著，2025 年上半年液冷收入占比达 47.47%，同比增长 74.66%。',
        'evidence_layer': 'L1_L3_candidate',
        'role': '2.2 液冷系统集成商分析',
        'strength': 'related',
    },
    '飞荣达': {
        'chain_layer': 'upstream_materials',
        'evidence': '飞荣达在液冷部件生产中属于一线厂家，公司不仅自主研发了导热材料（如石墨烯复合相变材料）、冷却液（氟化冷却液替代品），还覆盖了液冷板模组（如微通道冷板）、3D VC 散热器以及系统解决方案。',
        'evidence_layer': 'L1_L3_candidate',
        'role': '上游材料',
        'strength': 'related',
    },
    '申菱环境': {
        'chain_layer': 'downstream',
        'evidence': '申菱环境和高澜股份虽然毛利率相对较低，但在特定细分市场具有竞争优势。',
        'evidence_layer': 'L2_candidate',
        'role': '3.3 边际份额与单利润水平',
        'strength': 'related',
    },
}

def backup(path):
    b = path.with_suffix(path.suffix + '.bak-restore-curated-after-baseline')
    if not b.exists():
        b.write_text(path.read_text(encoding='utf-8'), encoding='utf-8')

def restore_rel():
    data = json.loads(REL.read_text(encoding='utf-8'))
    ents = data.get('entities', data)
    changed = []
    for company, patch in RESTORE.items():
        exp = ents.get(company, {}).get('concepts', {}).get(CONCEPT)
        if not isinstance(exp, dict):
            continue
        before = {k: exp.get(k) for k in ('update_type','strength','role','evidence','evidence_layer','chain_layer')}
        exp.update(patch)
        exp['update_type'] = 'curated_research'
        exp['confidence'] = 'medium'
        sources = exp.get('sources', []) or []
        for source in ['[[液冷服务器产业新变化与新格局全面分析报告]]', '[[AkShare baseline 2026-05-27 theme-radar queue batch1]]']:
            if source not in sources:
                sources.append(source)
        exp['sources'] = sources
        changed.append({'company': company, 'before': before, 'after': {k: exp.get(k) for k in before}})
    backup(REL)
    REL.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return changed

def main():
    changed = restore_rel()
    print(json.dumps({'restored': changed}, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
