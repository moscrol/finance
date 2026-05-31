#!/usr/bin/env python3
import json
import shutil
from datetime import date, datetime
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
REL = WIKI / 'relations'
AUDIT = WIKI / 'raw/theme-radar/theme-radar-db-quality-audit.json'
REPORT_CONTEXTS = REL / 'report_contexts.json'
EXPOSURES = REL / 'entity_exposures.json'
GRAPH = REL / 'concept_graph.json'
RESULT = WIKI / 'raw/theme-radar/p2-report-context-backfill-result.json'
BACKUP_SUFFIX = '.bak-p2-context-backfill'

STRENGTH_SCORE = {'core': 3, 'related': 2, 'peripheral': 1}


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def collect_exposures(concept, exposures):
    rows = []
    for entity, data in (exposures.get('entities') or {}).items():
        exp = (data.get('concepts') or {}).get(concept)
        if not exp:
            continue
        rows.append({
            'entity': entity,
            'codes': data.get('codes') or [],
            'role': exp.get('role') or '',
            'strength': exp.get('strength') or '',
            'evidence': exp.get('evidence') or '',
            'sources': exp.get('sources') or [],
            'chain_layer': exp.get('chain_layer') or '',
            'evidence_layer': exp.get('evidence_layer') or '',
        })
    rows.sort(key=lambda r: (-STRENGTH_SCORE.get(r['strength'], 0), r['entity']))
    return rows


def evidence_rows(concept, rows):
    evidence = []
    texts = []
    for row in rows:
        text = str(row.get('evidence') or '').strip()
        if text and text not in texts:
            texts.append(text)
            evidence.append({'heading': row['entity'], 'text': text[:300]})
        if len(evidence) >= 8:
            break
    if not evidence:
        entities = '、'.join(row['entity'] for row in rows[:12])
        evidence.append({'heading': '实体暴露聚合', 'text': f'{concept} 在现有实体暴露中关联 {len(rows)} 个实体：{entities}'})
    return evidence


def build_supply_chain(concept, node, rows):
    supply = {}
    for layer, values in (node.get('supply_chain') or {}).items():
        supply[str(layer)] = list(dict.fromkeys([str(v) for v in values if str(v).strip()]))[:20]
    ecosystem = [row['entity'] for row in rows[:30]]
    if ecosystem:
        supply['ecosystem'] = list(dict.fromkeys(ecosystem))
    by_layer = {}
    for row in rows:
        layer = str(row.get('chain_layer') or '').strip()
        if not layer:
            continue
        by_layer.setdefault(layer, []).append(row['entity'])
    for layer, entities in by_layer.items():
        supply.setdefault(layer, [])
        for entity in entities[:20]:
            if entity not in supply[layer]:
                supply[layer].append(entity)
    supply.setdefault('midstream', [])
    for item in [concept] + (node.get('related_concepts') or [])[:10]:
        if item not in supply['midstream']:
            supply['midstream'].append(item)
    return supply


def main():
    audit = load(AUDIT)
    contexts = load(REPORT_CONTEXTS)
    exposures = load(EXPOSURES)
    graph = load(GRAPH)
    backup = Path(str(REPORT_CONTEXTS) + BACKUP_SUFFIX)
    shutil.copy2(REPORT_CONTEXTS, backup)
    reports = contexts.setdefault('reports', {})
    queue = audit.get('queues', {}).get('P2_report_context_backfill', []) or []
    written = []
    skipped = []
    for item in queue:
        concept = item.get('concept')
        if not concept:
            continue
        key = f'theme-radar上下文回填：{concept}'
        if key in reports:
            skipped.append(concept)
            continue
        node = (graph.get('concepts') or {}).get(concept) or {}
        rows = collect_exposures(concept, exposures)
        related = []
        for value in (node.get('related_concepts') or []) + (node.get('parents') or []):
            if value and value != concept and value not in related:
                related.append(value)
        reports[key] = {
            'concept': concept,
            'evidence': evidence_rows(concept, rows),
            'related_concepts': related[:20],
            'source_date': date.today().isoformat(),
            'source_name': key,
            'supply_chain': build_supply_chain(concept, node, rows),
            'context_type': 'theme_radar_graph_aggregation',
            'source_basis': 'entity_exposures + concept_graph',
            'exposure_count': len(rows),
            'updated': date.today().isoformat(),
        }
        written.append({'concept': concept, 'exposures': len(rows), 'key': key})
    contexts['updated'] = datetime.now().isoformat(timespec='seconds')
    contexts.setdefault('version', 1)
    write(REPORT_CONTEXTS, contexts)
    result = {
        'timestamp': datetime.now().isoformat(timespec='seconds'),
        'backup': str(backup.relative_to(WIKI)),
        'written_count': len(written),
        'skipped_count': len(skipped),
        'written_sample': written[:80],
        'skipped_sample': skipped[:80],
    }
    write(RESULT, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
