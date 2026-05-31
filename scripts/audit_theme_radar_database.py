#!/usr/bin/env python3
import json
from collections import Counter, defaultdict
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
REL = WIKI / 'relations'
OUT_JSON = WIKI / 'raw/theme-radar/theme-radar-db-quality-audit.json'
OUT_MD = WIKI / 'raw/theme-radar/theme-radar-db-quality-audit.md'
RECENT_TAGS = (
    'missing-wikilink-concept-review',
    'missing-wikilink-concept-review-batch',
    'missing-wikilink-alias-candidate',
)
GENERIC_ROLES = {'受益标的', '待验证受益标的', '中游制造及提供商', '相关公司'}


def load_json(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding='utf-8'))


def iter_md_names(sub):
    root = WIKI / sub
    return sorted(p.stem for p in root.glob('*.md') if '.bak' not in p.name)


def read_frontmatter(path):
    text = path.read_text(encoding='utf-8', errors='ignore')[:4000]
    if not text.startswith('---'):
        return {}
    end = text.find('\n---', 3)
    if end == -1:
        return {}
    fm = {}
    for line in text[3:end].splitlines():
        if ':' not in line:
            continue
        key, value = line.split(':', 1)
        fm[key.strip()] = value.strip()
    return fm


def concept_stub_tags():
    rows = []
    for path in sorted((WIKI / 'concepts').glob('*.md')):
        if '.bak' in path.name:
            continue
        fm = read_frontmatter(path)
        tags = fm.get('tags', '')
        if any(tag in tags for tag in RECENT_TAGS):
            rows.append({'concept': path.stem, 'file': str(path.relative_to(WIKI)), 'tags': tags})
    return rows


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


def audit():
    concept_graph = load_json(REL / 'concept_graph.json', {'concepts': {}, 'relations': []})
    exposures = load_json(REL / 'entity_exposures.json', {'entities': {}})
    evidence_index = load_json(REL / 'evidence_index.json', {'items': []})
    report_contexts = load_json(REL / 'report_contexts.json', {'reports': {}})
    aliases = load_json(REL / 'aliases.json', {'aliases': {}})
    concept_files = set(iter_md_names('concepts'))
    entity_files = set(iter_md_names('entities'))
    source_files = set(iter_md_names('sources'))
    graph_concepts = concept_graph.get('concepts', {})
    relation_rows = concept_graph.get('relations', []) or []
    recent_stubs = concept_stub_tags()

    concepts_missing_graph = sorted(concept_files - set(graph_concepts))
    recent_stubs_missing_graph = [r for r in recent_stubs if r['concept'] not in graph_concepts]

    graph_quality = []
    for name, node in graph_concepts.items():
        parents = node.get('parents', []) or []
        related = node.get('related_concepts', []) or []
        supply = node.get('supply_chain', {}) or {}
        companies = node.get('companies', []) or []
        sources = node.get('sources', []) or []
        flags = []
        if not parents:
            flags.append('missing_parents')
        if not related:
            flags.append('missing_related_concepts')
        if not supply:
            flags.append('missing_supply_chain')
        if not companies:
            flags.append('missing_companies')
        if not sources:
            flags.append('missing_sources')
        if flags:
            graph_quality.append({
                'concept': name,
                'flags': flags,
                'parents_count': len(parents),
                'related_count': len(related),
                'supply_chain_layers': sorted(supply.keys()),
                'companies_count': len(companies),
                'sources_count': len(sources),
            })

    exposure_issues = []
    concept_exposure_counts = Counter()
    bucket_counts = Counter()
    update_type_counts = Counter()
    strength_counts = Counter()
    for entity, data in (exposures.get('entities', {}) or {}).items():
        concepts = data.get('concepts', {}) or {}
        for concept, exp in concepts.items():
            concept_exposure_counts[concept] += 1
            bucket = exposure_bucket(exp)
            bucket_counts[bucket] += 1
            update_type_counts[str(exp.get('update_type') or 'missing')] += 1
            strength_counts[str(exp.get('strength') or 'missing')] += 1
            role = str(exp.get('role') or '').strip()
            flags = []
            if not role or role in GENERIC_ROLES:
                flags.append('generic_or_missing_role')
            if not exp.get('evidence'):
                flags.append('missing_evidence')
            if not exp.get('chain_layer'):
                flags.append('missing_chain_layer')
            if not exp.get('evidence_layer'):
                flags.append('missing_evidence_layer')
            if not exp.get('update_type'):
                flags.append('missing_update_type')
            if bucket in {'graph_only', 'missing'} and str(exp.get('strength') or '') in {'core', 'related'}:
                flags.append('possible_overranked')
            if flags:
                exposure_issues.append({
                    'entity': entity,
                    'concept': concept,
                    'code': ','.join(data.get('codes', []) or []),
                    'strength': exp.get('strength', ''),
                    'bucket': bucket,
                    'role': role,
                    'flags': flags,
                    'sources': exp.get('sources', [])[:3],
                })

    evidence_targets = Counter()
    for item in evidence_index.get('items', []) or []:
        target = str(item.get('target') or '').strip('[]')
        concept = str(item.get('concept') or '').strip()
        if concept:
            evidence_targets[concept] += 1
        if target:
            evidence_targets[target] += 1

    report_concepts = Counter()
    for source_name, ctx in (report_contexts.get('reports', {}) or {}).items():
        concept = str(ctx.get('concept') or '').strip()
        if concept:
            report_concepts[concept] += 1
        for c in ctx.get('related_concepts', []) or []:
            report_concepts[str(c).strip()] += 1

    p0_exposures = sorted(
        exposure_issues,
        key=lambda r: (
            'possible_overranked' not in r['flags'],
            'missing_evidence' not in r['flags'],
            r['bucket'] not in {'missing', 'graph_only'},
            r['entity'],
        ),
    )[:80]

    candidate_concepts = []
    for concept in concepts_missing_graph:
        score = 0
        if concept in {r['concept'] for r in recent_stubs_missing_graph}:
            score += 3
        score += min(concept_exposure_counts[concept], 10) * 2
        score += min(evidence_targets[concept], 10)
        score += min(report_concepts[concept], 10)
        if score > 0:
            candidate_concepts.append({
                'concept': concept,
                'score': score,
                'exposures': concept_exposure_counts[concept],
                'evidence_items': evidence_targets[concept],
                'report_context_hits': report_concepts[concept],
                'reason': 'has_exposure_or_evidence_or_recent_stub',
            })
    p1_concepts = sorted(candidate_concepts, key=lambda r: (-r['score'], r['concept']))[:100]

    p2_report_context = []
    for concept, count in concept_exposure_counts.most_common():
        if concept in graph_concepts and report_concepts[concept] == 0:
            p2_report_context.append({
                'concept': concept,
                'exposures': count,
                'graph_exists': True,
                'report_context_hits': 0,
            })
        if len(p2_report_context) >= 80:
            break

    summary = {
        'concept_files': len(concept_files),
        'entity_files': len(entity_files),
        'source_files': len(source_files),
        'concept_graph_nodes': len(graph_concepts),
        'concept_graph_relations': len(relation_rows),
        'entity_exposure_entities': len(exposures.get('entities', {}) or {}),
        'entity_exposure_edges': sum(len((v.get('concepts', {}) or {})) for v in (exposures.get('entities', {}) or {}).values()),
        'evidence_items': len(evidence_index.get('items', []) or []),
        'report_contexts': len(report_contexts.get('reports', {}) or {}),
        'aliases': len(aliases.get('aliases', {}) or {}),
        'concept_files_missing_graph_count': len(concepts_missing_graph),
        'recent_stub_concepts_count': len(recent_stubs),
        'recent_stub_missing_graph_count': len(recent_stubs_missing_graph),
        'graph_nodes_with_quality_flags': len(graph_quality),
        'exposure_edges_with_quality_flags': len(exposure_issues),
        'bucket_counts': dict(bucket_counts),
        'update_type_counts': dict(update_type_counts),
        'strength_counts': dict(strength_counts),
    }

    result = {
        'summary': summary,
        'queues': {
            'P0_entity_exposure_quality': p0_exposures,
            'P1_concept_graph_ingest': p1_concepts,
            'P2_report_context_backfill': p2_report_context,
        },
        'samples': {
            'recent_stub_missing_graph': recent_stubs_missing_graph[:80],
            'graph_quality_flags': graph_quality[:80],
            'concept_files_missing_graph': concepts_missing_graph[:120],
        },
    }
    return result


def render_md(result):
    s = result['summary']
    lines = ['# Theme Radar DB Quality Audit', '']
    lines.extend(['## Summary', '', '| 指标 | 数量 |', '|---|---:|'])
    for key, value in s.items():
        if isinstance(value, dict):
            continue
        lines.append(f'| {key} | {value} |')
    lines.extend(['', '## Evidence bucket counts', '', '```json', json.dumps(s.get('bucket_counts', {}), ensure_ascii=False, indent=2), '```'])
    lines.extend(['', '## P0 entity exposure quality', '', '| Entity | Concept | Bucket | Strength | Flags | Role |', '|---|---|---|---|---|---|'])
    for r in result['queues']['P0_entity_exposure_quality'][:40]:
        lines.append(f"| {r['entity']} | {r['concept']} | {r['bucket']} | {r['strength']} | {', '.join(r['flags'])} | {r['role']} |")
    lines.extend(['', '## P1 concept graph ingest', '', '| Concept | Score | Exposures | Evidence | Report contexts |', '|---|---:|---:|---:|---:|'])
    for r in result['queues']['P1_concept_graph_ingest'][:60]:
        lines.append(f"| {r['concept']} | {r['score']} | {r['exposures']} | {r['evidence_items']} | {r['report_context_hits']} |")
    lines.extend(['', '## P2 report context backfill', '', '| Concept | Exposures | Report context hits |', '|---|---:|---:|'])
    for r in result['queues']['P2_report_context_backfill'][:60]:
        lines.append(f"| {r['concept']} | {r['exposures']} | {r['report_context_hits']} |")
    lines.extend(['', '## Recommended next action', '', '- **P0**：先修 entity_exposures 中 possible_overranked / missing_evidence / generic role。', '- **P1**：再把有证据或暴露的高价值 concept stub 写入 concept_graph。', '- **P2**：随后补 report_contexts，提升产业链全景和细分方向扫描。'])
    return '\n'.join(lines) + '\n'


def main():
    result = audit()
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    OUT_MD.write_text(render_md(result), encoding='utf-8')
    print(json.dumps(result['summary'], ensure_ascii=False, indent=2))
    print(str(OUT_JSON))
    print(str(OUT_MD))


if __name__ == '__main__':
    main()
