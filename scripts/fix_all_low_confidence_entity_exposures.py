#!/usr/bin/env python3
import json
import shutil
from collections import Counter
from datetime import date, datetime
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
REL = WIKI / 'relations'
EXPOSURES = REL / 'entity_exposures.json'
GRAPH = REL / 'concept_graph.json'
RESULT = WIKI / 'raw/theme-radar/all-low-confidence-entity-exposures-fix-result.json'
BACKUP_SUFFIX = '.bak-all-low-confidence-fix'
GENERIC_ROLES = {'受益标的', '待验证受益标的', '中游制造及提供商', '相关公司', ''}


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def exposure_bucket(exp):
    update_type = str(exp.get('update_type') or '').strip()
    sources = ' '.join(str(x) for x in exp.get('sources', []) or [])
    if update_type in {'delta', 'curated_research', 'baseline', 'graph_only', 'missing'}:
        return update_type
    if 'iFinD baseline' in sources or 'AkShare baseline' in sources or 'Baseline' in sources:
        return 'baseline'
    if any(token in sources for token in ('市场逻辑', '强势股', '评级日报', '复盘', '脱水')):
        return 'delta'
    return 'missing'


def infer_chain_layer(concept, graph):
    node = (graph.get('concepts') or {}).get(concept) or {}
    supply = node.get('supply_chain') or {}
    for layer, values in supply.items():
        if values:
            return str(layer)
    parents = node.get('parents') or []
    if parents:
        return str(parents[0])
    return '图谱弱关联'


def main():
    exposures = load(EXPOSURES)
    graph = load(GRAPH)
    backup = Path(str(EXPOSURES) + BACKUP_SUFFIX)
    shutil.copy2(EXPOSURES, backup)
    counts = Counter()
    samples = []

    for entity, data in (exposures.get('entities') or {}).items():
        for concept, exp in (data.get('concepts') or {}).items():
            bucket = exposure_bucket(exp)
            if bucket not in {'graph_only', 'missing'}:
                continue
            changed = False
            counts['weak_edges_seen'] += 1
            if exp.get('strength') in {'core', 'related'}:
                exp['strength'] = 'peripheral'
                counts['strength_downgraded'] += 1
                changed = True
            if str(exp.get('role') or '').strip() in GENERIC_ROLES:
                exp['role'] = '图谱弱关联'
                counts['role_patched'] += 1
                changed = True
            if not exp.get('update_type'):
                exp['update_type'] = 'graph_only'
                counts['update_type_patched'] += 1
                changed = True
            if not exp.get('evidence_layer'):
                exp['evidence_layer'] = 'graph_only'
                counts['evidence_layer_patched'] += 1
                changed = True
            if not exp.get('chain_layer'):
                exp['chain_layer'] = infer_chain_layer(concept, graph)
                counts['chain_layer_patched'] += 1
                changed = True
            if not exp.get('confidence'):
                exp['confidence'] = 'low'
                counts['confidence_patched'] += 1
                changed = True
            if changed:
                exp['updated'] = date.today().isoformat()
                counts['rows_changed'] += 1
                if len(samples) < 80:
                    samples.append({'entity': entity, 'concept': concept, 'bucket': bucket})

    write(EXPOSURES, exposures)
    result = {
        'timestamp': datetime.now().isoformat(timespec='seconds'),
        'backup': str(backup.relative_to(WIKI)),
        'counts': dict(counts),
        'changed_sample': samples,
    }
    write(RESULT, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
