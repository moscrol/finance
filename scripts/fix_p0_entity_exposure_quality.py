#!/usr/bin/env python3
import json
import shutil
from datetime import date, datetime
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
REL = WIKI / 'relations'
AUDIT = WIKI / 'raw/theme-radar/theme-radar-db-quality-audit.json'
EXPOSURES = REL / 'entity_exposures.json'
CONCEPT_GRAPH = REL / 'concept_graph.json'
RESULT = WIKI / 'raw/theme-radar/p0-entity-exposure-quality-fix-result.json'
BACKUP_SUFFIX = '.bak-p0-quality-fix'

GENERIC_ROLES = {'受益标的', '待验证受益标的', '中游制造及提供商', '相关公司', ''}


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


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
    audit = load(AUDIT)
    exposures = load(EXPOSURES)
    graph = load(CONCEPT_GRAPH)
    queue = audit.get('queues', {}).get('P0_entity_exposure_quality', []) or []
    shutil.copy2(EXPOSURES, Path(str(EXPOSURES) + BACKUP_SUFFIX))

    counts = {
        'rows_seen': 0,
        'rows_changed': 0,
        'strength_downgraded': 0,
        'role_patched': 0,
        'update_type_patched': 0,
        'evidence_layer_patched': 0,
        'chain_layer_patched': 0,
        'confidence_patched': 0,
        'missing_target': 0,
    }
    changed_items = []

    for item in queue:
        entity = item.get('entity')
        concept = item.get('concept')
        flags = set(item.get('flags') or [])
        counts['rows_seen'] += 1
        ent = (exposures.get('entities') or {}).get(entity)
        exp = (ent.get('concepts') or {}).get(concept) if ent else None
        if not exp:
            counts['missing_target'] += 1
            continue
        changed = False
        if 'possible_overranked' in flags and exp.get('strength') in {'core', 'related'}:
            exp['strength'] = 'peripheral'
            counts['strength_downgraded'] += 1
            changed = True
        if 'generic_or_missing_role' in flags and str(exp.get('role') or '').strip() in GENERIC_ROLES:
            exp['role'] = '图谱弱关联'
            counts['role_patched'] += 1
            changed = True
        if 'missing_update_type' in flags and not exp.get('update_type'):
            exp['update_type'] = 'graph_only'
            counts['update_type_patched'] += 1
            changed = True
        if 'missing_evidence_layer' in flags and not exp.get('evidence_layer'):
            exp['evidence_layer'] = 'graph_only'
            counts['evidence_layer_patched'] += 1
            changed = True
        if 'missing_chain_layer' in flags and not exp.get('chain_layer'):
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
            changed_items.append({'entity': entity, 'concept': concept})

    write(EXPOSURES, exposures)
    result = {
        'timestamp': datetime.now().isoformat(timespec='seconds'),
        'backup': str(Path(str(EXPOSURES) + BACKUP_SUFFIX).relative_to(WIKI)),
        'counts': counts,
        'changed_items_sample': changed_items[:80],
    }
    write(RESULT, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
