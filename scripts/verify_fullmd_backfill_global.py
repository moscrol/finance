#!/usr/bin/env python3
import json
import re
from pathlib import Path

VAULT = Path('/Users/lbq/Desktop/c c/知识库/wiki')
RAW = VAULT.parent / 'raw'
PAYLOAD_DIR = VAULT / 'raw/entity-delta-backfill'
REL = VAULT / 'relations'
ENTITIES = VAULT / 'entities'

SECTION_RE = re.compile(r'^### \d{4}-\d{2}-\d{2}｜(.+?)\n.*?(?=^### \d{4}-\d{2}-\d{2}｜|\Z)', re.M | re.S)

def load_payloads():
    rows = []
    source_names = set()
    raw_full_names = {p.stem.replace('-full', '') for p in RAW.glob('*-full.md')}
    for path in sorted(PAYLOAD_DIR.glob('*.entity-delta.json')):
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except Exception as exc:
            rows.append({'path': str(path), 'json_error': str(exc), 'data': None})
            continue
        source = data.get('source_name') or path.name.replace('.entity-delta.json', '')
        if source in raw_full_names or (RAW / f'{source}-full.md').exists():
            rows.append({'path': str(path), 'source': source, 'data': data})
            source_names.add(source)
    return rows, source_names

def count_payloads(rows):
    summary = {'payloads': 0, 'total_updates': 0, 'graph_only': 0, 'curated_research': 0, 'hard_delta': 0, 'l2_candidate': 0, 'l1_l3_candidate': 0, 'json_errors': 0}
    hard_delta_examples = []
    for row in rows:
        if row.get('json_error'):
            summary['json_errors'] += 1
            continue
        summary['payloads'] += 1
        for u in row['data'].get('updates', []) or []:
            graph = bool(u.get('graph_only'))
            exposure = bool(u.get('exposure_only'))
            update_type = u.get('update_type') or ''
            layer = u.get('evidence_layer') or ''
            is_hard = (not graph) and (not exposure) and update_type != 'curated_research'
            summary['total_updates'] += 1
            summary['graph_only'] += int(graph)
            summary['curated_research'] += int(update_type == 'curated_research')
            summary['hard_delta'] += int(is_hard)
            summary['l2_candidate'] += int(layer == 'L2_candidate')
            summary['l1_l3_candidate'] += int(layer == 'L1_L3_candidate')
            if is_hard and len(hard_delta_examples) < 20:
                hard_delta_examples.append({'source': row.get('source'), 'company': u.get('company'), 'update_type': update_type, 'layer': layer})
    return summary, hard_delta_examples

def has_full_source(obj, source_links):
    if not isinstance(obj, dict):
        return False
    if obj.get('source') in source_links:
        return True
    sources = obj.get('sources')
    return isinstance(sources, list) and any(s in source_links for s in sources)

def collect_relation_delta(obj, source_links, out, path=''):
    if isinstance(obj, dict):
        if has_full_source(obj, source_links) and obj.get('update_type') == 'delta':
            out.append({'path': path, 'company': obj.get('company') or obj.get('target') or obj.get('name'), 'concept': obj.get('concept'), 'source': obj.get('source') or obj.get('sources')})
        for k, v in obj.items():
            collect_relation_delta(v, source_links, out, f'{path}/{k}')
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            collect_relation_delta(item, source_links, out, f'{path}[{i}]')

def check_relations(source_names):
    source_links = {f'[[{s}]]' for s in source_names}
    result = {}
    for name in ['entity_exposures.json', 'evidence_index.json']:
        out = []
        path = REL / name
        data = json.loads(path.read_text(encoding='utf-8'))
        collect_relation_delta(data, source_links, out)
        result[name] = {'fullmd_delta_count': len(out), 'examples': out[:20]}
    return result

def section_content(text, title):
    m = re.search(rf'^## {re.escape(title)}\n(.*?)(?=^## |\Z)', text, re.M | re.S)
    return m.group(1) if m else ''

def check_entity_delta_residue(source_names):
    residue = []
    for path in sorted(ENTITIES.glob('*.md')):
        text = path.read_text(encoding='utf-8')
        delta = section_content(text, '边际变化')
        if not delta:
            continue
        for m in SECTION_RE.finditer(delta):
            source = m.group(1).strip()
            if source in source_names:
                residue.append({'file': path.name, 'source': source, 'snippet': m.group(0)[:160]})
                if len(residue) >= 50:
                    return residue
    return residue

def main():
    rows, source_names = load_payloads()
    summary, hard_examples = count_payloads(rows)
    relations = check_relations(source_names)
    residue = check_entity_delta_residue(source_names)
    result = {
        'summary': summary,
        'full_sources': len(source_names),
        'hard_delta_examples': hard_examples,
        'relations': relations,
        'entity_delta_fullmd_residue_count': len(residue),
        'entity_delta_fullmd_residue_examples': residue[:20],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
