#!/usr/bin/env python3
import json
from pathlib import Path

REL = Path('/Users/lbq/Desktop/c c/知识库/wiki/relations/entity_exposures.json')
EVIDENCE = Path('/Users/lbq/Desktop/c c/知识库/wiki/relations/evidence_index.json')
CONCEPT = '液冷服务器'

PATCHES = {
    '中航光电': {'update_type': 'baseline', 'evidence_layer': 'L2', 'confidence': 'medium'},
    '中石科技': {'update_type': 'baseline', 'evidence_layer': 'L2', 'confidence': 'low', 'strength': 'peripheral'},
    '南风股份': {'strength': 'peripheral', 'chain_layer': 'upstream_equipment', 'update_type': 'delta', 'evidence_layer': 'L3', 'confidence': 'low', 'role': '液冷/温控设备待验证受益标的'},
    '川润股份': {'strength': 'peripheral', 'chain_layer': 'upstream_equipment', 'update_type': 'delta', 'evidence_layer': 'L3', 'confidence': 'low', 'role': '液冷设备与流体控制待验证受益标的'},
    '思泉新材': {'strength': 'peripheral', 'chain_layer': 'upstream_materials', 'update_type': 'delta', 'evidence_layer': 'L3', 'confidence': 'low', 'role': '导热材料待验证受益标的'},
    '海鸥股份': {'strength': 'peripheral', 'chain_layer': 'upstream_equipment', 'update_type': 'delta', 'evidence_layer': 'L3', 'confidence': 'low', 'role': '冷却塔/温控设备待验证受益标的'},
    '润泽科技': {'strength': 'peripheral', 'chain_layer': 'downstream_infrastructure', 'update_type': 'delta', 'evidence_layer': 'L3', 'confidence': 'low', 'role': '数据中心基础设施待验证受益标的'},
    '维通利': {'strength': 'peripheral', 'chain_layer': 'upstream_components', 'update_type': 'delta', 'evidence_layer': 'L3', 'confidence': 'low', 'role': '液冷连接/组件待验证受益标的'},
    '英特科技': {'strength': 'peripheral', 'chain_layer': 'upstream_equipment', 'update_type': 'delta', 'evidence_layer': 'L3', 'confidence': 'low', 'role': '热管理设备待验证受益标的'},
    '远东股份': {'strength': 'peripheral', 'chain_layer': 'upstream_components', 'update_type': 'delta', 'evidence_layer': 'L3', 'confidence': 'low', 'role': '线缆组件待验证受益标的'},
    '金石资源': {'strength': 'peripheral', 'chain_layer': 'upstream_materials', 'update_type': 'delta', 'evidence_layer': 'L3', 'confidence': 'low', 'role': '氟资源/氟化液上游待验证受益标的'},
    '铂力特': {'strength': 'peripheral', 'chain_layer': 'upstream_equipment', 'update_type': 'delta', 'evidence_layer': 'L3', 'confidence': 'low', 'role': '3D打印冷板工艺待验证受益标的'},
    '领益智造': {'strength': 'peripheral', 'chain_layer': 'upstream_components', 'update_type': 'delta', 'evidence_layer': 'L3', 'confidence': 'low', 'role': '散热/结构件待验证受益标的'},
    '飞龙股份': {'strength': 'peripheral', 'chain_layer': 'upstream_components', 'update_type': 'delta', 'evidence_layer': 'L3', 'confidence': 'low', 'role': '泵类热管理部件待验证受益标的'},
}

def backup(path):
    b = path.with_suffix(path.suffix + '.bak-liquid-radar-qc')
    if not b.exists():
        b.write_text(path.read_text(encoding='utf-8'), encoding='utf-8')

def patch_exposures():
    data = json.loads(REL.read_text(encoding='utf-8'))
    entities = data.get('entities', data)
    changes = []
    for company, patch in PATCHES.items():
        node = entities.get(company) if isinstance(entities, dict) else None
        exp = (node or {}).get('concepts', {}).get(CONCEPT) if isinstance(node, dict) else None
        if not isinstance(exp, dict):
            continue
        before = {k: exp.get(k) for k in patch}
        changed = False
        for k, v in patch.items():
            if exp.get(k) != v:
                exp[k] = v
                changed = True
        if changed:
            changes.append({'company': company, 'before': before, 'after': patch})
    if changes:
        backup(REL)
        REL.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return changes

def patch_evidence_index():
    data = json.loads(EVIDENCE.read_text(encoding='utf-8'))
    count = 0
    def walk(obj):
        nonlocal count
        if isinstance(obj, dict):
            company = obj.get('company') or obj.get('target') or obj.get('name')
            concept = obj.get('concept')
            if company in PATCHES and concept == CONCEPT:
                patch = PATCHES[company]
                for k in ('strength', 'chain_layer', 'update_type', 'evidence_layer', 'confidence', 'role'):
                    if k in patch and obj.get(k) != patch[k]:
                        obj[k] = patch[k]
                        count += 1
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for x in obj:
                walk(x)
    walk(data)
    if count:
        backup(EVIDENCE)
        EVIDENCE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return count

def main():
    changes = patch_exposures()
    evidence_changes = patch_evidence_index()
    print(json.dumps({'entity_exposures_changes': changes, 'evidence_index_field_changes': evidence_changes}, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
