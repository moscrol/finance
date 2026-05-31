#!/usr/bin/env python3
import json
import shutil
from datetime import datetime
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
REL = WIKI / 'relations'
THEME_DIR = WIKI / 'raw/theme-radar'
CONCEPT_GRAPH = REL / 'concept_graph.json'
ENTITY_EXPOSURES = REL / 'entity_exposures.json'
RESULT = THEME_DIR / 'concept-graph-auto-ingest-metadata-fix-result.json'
SOURCE = '[[theme-radar-db-quality-audit]]'
BACKUP_SUFFIX = '.bak-auto-ingest-metadata-fix'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def backup(path):
    bak = Path(str(path) + BACKUP_SUFFIX)
    shutil.copy2(path, bak)
    return str(bak.relative_to(WIKI))


def first_chain_layer(node):
    supply = node.get('supply_chain') or {}
    for layer, values in supply.items():
        if values:
            return str(layer)
    return ''


def main():
    graph = load(CONCEPT_GRAPH)
    exposures = load(ENTITY_EXPOSURES)
    backups = [backup(CONCEPT_GRAPH), backup(ENTITY_EXPOSURES)]
    concepts = graph.get('concepts') or {}

    patched_edges = 0
    patch_counts = {
        'update_type': 0,
        'evidence_layer': 0,
        'confidence': 0,
        'chain_layer': 0,
    }

    for entity, data in (exposures.get('entities') or {}).items():
        for concept, exp in (data.get('concepts') or {}).items():
            sources = exp.get('sources') or []
            if SOURCE not in sources:
                continue
            node = concepts.get(concept) or {}
            changed = False
            if not exp.get('update_type'):
                exp['update_type'] = 'graph_only'
                patch_counts['update_type'] += 1
                changed = True
            if not exp.get('evidence_layer'):
                exp['evidence_layer'] = 'graph_only'
                patch_counts['evidence_layer'] += 1
                changed = True
            if not exp.get('confidence'):
                exp['confidence'] = node.get('confidence') or 'low'
                patch_counts['confidence'] += 1
                changed = True
            if not exp.get('chain_layer'):
                layer = first_chain_layer(node)
                if layer:
                    exp['chain_layer'] = layer
                    patch_counts['chain_layer'] += 1
                    changed = True
            if changed:
                exp['updated'] = datetime.now().date().isoformat()
                patched_edges += 1

    write(ENTITY_EXPOSURES, exposures)
    result = {
        'timestamp': datetime.now().isoformat(timespec='seconds'),
        'source': SOURCE,
        'backups': backups,
        'patched_edges': patched_edges,
        'patch_counts': patch_counts,
    }
    write(RESULT, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
