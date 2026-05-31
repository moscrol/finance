#!/usr/bin/env python3
import json
import re
from pathlib import Path
from collections import Counter, defaultdict

VAULT = Path('/Users/lbq/Desktop/c c/知识库/wiki')
REL = VAULT / 'relations/entity_exposures.json'
OUT_JSON = VAULT / 'raw/ifind-baseline/baseline-backfill-queue.json'
OUT_MD = VAULT / 'raw/ifind-baseline/baseline-backfill-queue.md'

LIQUID_SERVER_P0 = {'浪潮信息', '英维克', '工业富联', '飞荣达', '申菱环境', '高澜股份', '曙光数创'}

def is_a_share_code(code):
    return bool(re.fullmatch(r'[0368]\d{5}', str(code or '').strip()))

def has_baseline(exposures):
    for exp in exposures:
        sources = ' '.join(str(x) for x in exp.get('sources', []) or [])
        if exp.get('update_type') == 'baseline' or 'iFinD baseline' in sources or 'AkShare baseline' in sources or 'Baseline' in sources:
            return True
    return False

def classify_priority(row):
    if not row['missing_baseline']:
        return None
    if row['company'] in LIQUID_SERVER_P0:
        return 'P0'
    if row['is_a_share'] and row['curated_research_count'] >= 2:
        return 'P0'
    if row['is_a_share'] and row['curated_research_count'] >= 1 and (row['delta_count'] >= 1 or row['concept_count'] >= 2):
        return 'P0'
    if row['is_a_share'] and row['curated_research_count'] >= 1:
        return 'P1'
    if row['is_a_share'] and row['delta_count'] >= 2:
        return 'P1'
    if row['is_a_share'] and row['concept_count'] >= 5:
        return 'P1'
    if row['is_a_share'] and (row['graph_only_count'] >= 3 or row['source_count'] >= 5):
        return 'P2'
    if row['is_a_share']:
        return 'P3'
    return None

def priority_score(row):
    base = {'P0': 3000, 'P1': 2000, 'P2': 1000, 'P3': 0}.get(row['priority'], -999)
    return base + row['curated_research_count'] * 80 + row['delta_count'] * 30 + row['concept_count'] * 10 + row['source_count']

def build_rows():
    data = json.loads(REL.read_text(encoding='utf-8'))
    entities = data.get('entities', data)
    rows = []
    for company, node in entities.items():
        if not isinstance(node, dict):
            continue
        concepts = node.get('concepts') or {}
        if not isinstance(concepts, dict) or not concepts:
            continue
        codes = [str(x).strip() for x in node.get('codes', []) or [] if str(x).strip()]
        code = next((x for x in codes if is_a_share_code(x)), codes[0] if codes else '')
        exposures = [x for x in concepts.values() if isinstance(x, dict)]
        update_counter = Counter(str(x.get('update_type') or 'missing') for x in exposures)
        strengths = Counter(str(x.get('strength') or 'related') for x in exposures)
        source_set = set()
        themes = []
        for concept, exp in concepts.items():
            if isinstance(exp, dict):
                for source in exp.get('sources', []) or []:
                    source_set.add(source)
                if exp.get('update_type') in ('curated_research', 'delta', 'graph_only') or exp.get('strength') in ('core', 'related'):
                    themes.append(concept)
        row = {
            'company': company,
            'code': code,
            'is_a_share': is_a_share_code(code),
            'missing_baseline': not has_baseline(exposures),
            'concept_count': len(concepts),
            'source_count': len(source_set),
            'curated_research_count': update_counter.get('curated_research', 0),
            'delta_count': update_counter.get('delta', 0),
            'graph_only_count': update_counter.get('graph_only', 0),
            'missing_update_type_count': update_counter.get('missing', 0),
            'core_count': strengths.get('core', 0),
            'related_count': strengths.get('related', 0),
            'themes': sorted(set(themes))[:20],
            'reasons': [],
        }
        priority = classify_priority(row)
        if not priority:
            continue
        row['priority'] = priority
        if row['company'] in LIQUID_SERVER_P0:
            row['reasons'].append('liquid_server_need_deep_read')
        if row['curated_research_count']:
            row['reasons'].append('curated_research')
        if row['delta_count']:
            row['reasons'].append('delta_supported')
        if row['concept_count'] >= 5:
            row['reasons'].append('multi_concept_center')
        if row['graph_only_count'] >= 3:
            row['reasons'].append('graph_only_repeated')
        if row['missing_baseline']:
            row['reasons'].append('missing_baseline')
        row['score'] = priority_score(row)
        rows.append(row)
    return sorted(rows, key=lambda x: (-x['score'], x['priority'], x['company']))

def write_outputs(rows):
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        'version': 1,
        'description': 'Theme-radar driven baseline backfill priority queue. Not all entities should be backfilled.',
        'summary': {
            'total': len(rows),
            'by_priority': dict(Counter(r['priority'] for r in rows)),
        },
        'queue': rows,
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = ['# Baseline 补全优先队列', '', '说明：题材雷达驱动，不代表全量 entity 都需要补 baseline。', '']
    lines.append('| Priority | Company | Code | Score | Reasons | Concepts | curated | delta | graph_only | sources |')
    lines.append('|---|---|---:|---:|---|---|---:|---:|---:|---:|')
    for r in rows[:200]:
        lines.append('| {priority} | {company} | {code} | {score} | {reasons} | {themes} | {curated} | {delta} | {graph} | {sources} |'.format(
            priority=r['priority'], company=r['company'], code=r['code'], score=r['score'],
            reasons='、'.join(r['reasons']), themes='、'.join(r['themes'][:6]),
            curated=r['curated_research_count'], delta=r['delta_count'], graph=r['graph_only_count'], sources=r['source_count']))
    OUT_MD.write_text('\n'.join(lines) + '\n', encoding='utf-8')

def main():
    rows = build_rows()
    write_outputs(rows)
    print(json.dumps({
        'json': str(OUT_JSON),
        'markdown': str(OUT_MD),
        'total': len(rows),
        'by_priority': dict(Counter(r['priority'] for r in rows)),
        'top20': rows[:20],
        'liquid_server_p0': [r for r in rows if r['company'] in LIQUID_SERVER_P0],
    }, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
