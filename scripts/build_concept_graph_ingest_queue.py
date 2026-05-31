#!/usr/bin/env python3
import json
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
AUDIT = WIKI / 'raw/theme-radar/theme-radar-db-quality-audit.json'
EXPOSURES = WIKI / 'relations/entity_exposures.json'
EVIDENCE = WIKI / 'relations/evidence_index.json'
REPORT_CONTEXTS = WIKI / 'relations/report_contexts.json'
OUT_JSON = WIKI / 'raw/theme-radar/concept-graph-ingest-queue.json'
OUT_MD = WIKI / 'raw/theme-radar/concept-graph-ingest-queue.md'

DOMAIN_PARENTS = [
    ('AI', ['AI', '算力', 'GPU', 'CANN', '推理', '端侧', '模型', '智能体'], '人工智能'),
    ('半导体', ['半导体', '芯片', 'HBM', 'GPU', 'CANN', '硅片', '载板', '封装', 'EDA'], '半导体'),
    ('通信', ['卫星', '6G', '光模块', 'CPO', '光纤', '通信'], '通信'),
    ('机器人', ['机器人', '外骨骼', '具身'], '机器人'),
    ('消费电子', ['折叠屏', '端侧', '手机', 'AI硬件'], '消费电子'),
    ('新能源', ['储能', '电池', '锂', '光伏', '新能源'], '新能源'),
]

CHAIN_RULES = [
    ('上游材料', ['材料', '硅片', '载板', '基板', '树脂', '金属', '光纤']),
    ('上游设备', ['设备', 'EDA', '机床', '检测', '量检测']),
    ('中游制造', ['芯片', 'GPU', 'HBM', '模组', '服务器', '硬件', '折叠屏']),
    ('下游应用', ['应用', '端侧', '卫星互联网', 'AI设计', '机器人']),
]


def load(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding='utf-8'))


def infer_parent(concept):
    for _label, keys, parent in DOMAIN_PARENTS:
        if any(k in concept for k in keys):
            return parent
    return '新兴技术'


def infer_chain(concept, companies):
    layer = '中游制造'
    for candidate, keys in CHAIN_RULES:
        if any(k in concept for k in keys):
            layer = candidate
            break
    names = [c['name'] for c in companies[:12]]
    return {layer: names} if names else {layer: [concept]}


def main():
    audit = load(AUDIT, {})
    exposures = load(EXPOSURES, {'entities': {}})
    evidence = load(EVIDENCE, {'items': []})
    report_contexts = load(REPORT_CONTEXTS, {'reports': {}})
    p1 = audit.get('queues', {}).get('P1_concept_graph_ingest', [])[:30]

    concept_to_companies = {}
    for entity, ent in exposures.get('entities', {}).items():
        code = (ent.get('codes') or [''])[0]
        for concept, exp in (ent.get('concepts') or {}).items():
            concept_to_companies.setdefault(concept, []).append({
                'name': entity,
                'code': code,
                'role': exp.get('role', ''),
                'strength': exp.get('strength', 'related'),
                'reason': exp.get('evidence', ''),
                'chain_layer': exp.get('chain_layer', ''),
                'update_type': exp.get('update_type', ''),
            })

    concept_to_sources = {}
    for item in evidence.get('items', []) or []:
        c = item.get('concept') or item.get('target')
        if c:
            src = item.get('source')
            if src and src not in concept_to_sources.setdefault(c, []):
                concept_to_sources[c].append(src)
    for _report, ctx in (report_contexts.get('reports') or {}).items():
        for c in [ctx.get('concept')] + (ctx.get('related_concepts') or []):
            if c:
                src = ctx.get('source') or _report
                link = src if str(src).startswith('[[') else f'[[{src}]]'
                if link not in concept_to_sources.setdefault(c, []):
                    concept_to_sources[c].append(link)

    items = []
    for row in p1:
        concept = row['concept']
        companies = sorted(
            concept_to_companies.get(concept, []),
            key=lambda x: ({'core': 0, 'related': 1, 'peripheral': 2}.get(x.get('strength'), 9), x['name'])
        )[:20]
        parent = infer_parent(concept)
        item = {
            'concept': concept,
            'score': row.get('score', 0),
            'parent_concepts': [parent],
            'related_concepts': [],
            'supply_chain': infer_chain(concept, companies),
            'companies': companies[:12],
            'sources': concept_to_sources.get(concept, [])[:8],
            'confidence': 'medium' if row.get('evidence_items', 0) or row.get('exposures', 0) else 'low',
            'evidence': f"由 theme-radar 数据库体检队列入图：exposures={row.get('exposures', 0)}, evidence_items={row.get('evidence_items', 0)}, report_context_hits={row.get('report_context_hits', 0)}。",
        }
        items.append(item)

    result = {'summary': {'total': len(items)}, 'items': items}
    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = ['# Concept Graph Ingest Queue', '', '| Concept | Score | Parents | Companies | Sources |', '|---|---:|---|---:|---:|']
    for it in items:
        lines.append(f"| {it['concept']} | {it['score']} | {', '.join(it['parent_concepts'])} | {len(it['companies'])} | {len(it['sources'])} |")
    OUT_MD.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps(result['summary'], ensure_ascii=False, indent=2))
    print(str(OUT_JSON))
    print(str(OUT_MD))


if __name__ == '__main__':
    main()
