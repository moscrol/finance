#!/usr/bin/env python3
import argparse
import json
import re
from collections import Counter
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
ENTITIES = WIKI / 'entities'
CONCEPTS = WIKI / 'concepts'
SOURCES = WIKI / 'sources'
RAW_IFIND = WIKI / 'raw/ifind-baseline'
REL = WIKI / 'relations'
OUT_JSON = WIKI / 'raw/theme-radar/quality-audit-latest.json'
OUT_MD = WIKI / 'raw/theme-radar/quality-audit-latest.md'

OVERLIMIT_PATTERNS = (
    '超限', '超过最大', 'maximum context', 'context length', 'token limit',
    '请求过长', 'input is too long', 'exceeds', 'over limit'
)
RESEARCH_MENTION_PATTERNS = ('研究报告提及', '研报提及公司边际信息', '研究报告提及公司')


def load_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def formal_md_count(path):
    return len([p for p in path.glob('*.md') if '.bak' not in p.name]) if path.exists() else 0


def backup_count():
    return len({p for p in ENTITIES.iterdir() if p.is_file() and '.bak' in p.name})


def relation_stats():
    out = {}
    for name in ['entity_exposures.json', 'evidence_index.json', 'report_contexts.json', 'concept_graph.json']:
        path = REL / name
        try:
            data = load_json(path)
            item = {'parse_ok': True}
            if name == 'entity_exposures.json':
                entities = data.get('entities', {})
                item['entities'] = len(entities)
                item['exposures'] = sum(len((v or {}).get('concepts', {}) or {}) for v in entities.values() if isinstance(v, dict))
            elif name == 'evidence_index.json':
                item['items'] = len(data.get('items', []))
            elif name == 'report_contexts.json':
                contexts = data.get('reports') or data.get('contexts') or data
                item['reports'] = len(contexts) if isinstance(contexts, (dict, list)) else 0
            elif name == 'concept_graph.json':
                item['concepts'] = len(data.get('concepts', {}))
                item['relations'] = len(data.get('relations', []))
            out[name] = item
        except Exception as exc:
            out[name] = {'parse_ok': False, 'error': str(exc)}
    return out


def find_overlimit_raw():
    rows = []
    for path in sorted(RAW_IFIND.glob('*.json')):
        try:
            text = path.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue
        low = text.lower()
        data = None
        try:
            data = json.loads(text)
        except Exception:
            pass
        has_pattern = any(p.lower() in low for p in OVERLIMIT_PATTERNS)
        empty_shell = False
        if isinstance(data, dict):
            results = data.get('results')
            updates = data.get('updates')
            empty_shell = (isinstance(results, list) and not any(r.get('ok') or r.get('content') for r in results if isinstance(r, dict))) or updates == []
        if has_pattern or empty_shell:
            rows.append({'file': str(path.relative_to(WIKI)), 'size': path.stat().st_size, 'has_overlimit_pattern': has_pattern, 'empty_shell': empty_shell})
    return rows


def core_l1_graph_only():
    data = load_json(REL / 'entity_exposures.json')
    rows = []
    for company, node in (data.get('entities') or {}).items():
        for concept, exp in ((node or {}).get('concepts') or {}).items():
            if not isinstance(exp, dict):
                continue
            if exp.get('strength') == 'core' and exp.get('evidence_layer') == 'L1' and exp.get('update_type') == 'graph_only':
                rows.append({
                    'company': company,
                    'concept': concept,
                    'role': exp.get('role', ''),
                    'source': exp.get('sources', [])[:3],
                    'evidence': str(exp.get('evidence', ''))[:180],
                })
    return rows


def research_mention_traces():
    rows = []
    for path in sorted(ENTITIES.glob('*.md')):
        if '.bak' in path.name:
            continue
        text = path.read_text(encoding='utf-8', errors='ignore')
        if any(p in text for p in RESEARCH_MENTION_PATTERNS):
            rows.append({'file': path.name})
    return rows


def target_index():
    targets = set()
    for base in [ENTITIES, CONCEPTS, SOURCES]:
        if not base.exists():
            continue
        for p in base.glob('*.md'):
            if '.bak' not in p.name:
                targets.add(p.stem)
    return targets


def missing_wikilinks(limit=80):
    targets = target_index()
    counts = Counter()
    examples = {}
    for base in [ENTITIES, CONCEPTS, SOURCES]:
        if not base.exists():
            continue
        for path in sorted(base.glob('*.md')):
            if '.bak' in path.name:
                continue
            text = path.read_text(encoding='utf-8', errors='ignore')
            for raw in re.findall(r'\[\[([^\]\n]+)\]\]', text):
                target = raw.split('|', 1)[0].split('#', 1)[0].strip()
                if not target or target in targets:
                    continue
                counts[target] += 1
                examples.setdefault(target, str(path.relative_to(WIKI)))
    rows = [{'target': k, 'count': v, 'example': examples.get(k, '')} for k, v in counts.most_common(limit)]
    return {'unique_missing_targets': len(counts), 'top': rows}


def build_report():
    rel_stats = relation_stats()
    overlimit = find_overlimit_raw()
    core_risks = core_l1_graph_only()
    research_traces = research_mention_traces()
    missing_links = missing_wikilinks()
    summary = {
        'counts': {
            'entities_md': formal_md_count(ENTITIES),
            'concepts_md': formal_md_count(CONCEPTS),
            'sources_md': formal_md_count(SOURCES),
            'entity_backup_files': backup_count(),
        },
        'relations': rel_stats,
        'issues': {
            'overlimit_ifind_raw_count': len(overlimit),
            'core_l1_graph_only_count': len(core_risks),
            'research_report_mention_entity_count': len(research_traces),
            'missing_wikilink_unique_targets': missing_links['unique_missing_targets'],
        },
    }
    return {
        'summary': summary,
        'overlimit_ifind_raw': overlimit,
        'core_l1_graph_only': core_risks,
        'research_report_mention_traces_sample': research_traces[:120],
        'missing_wikilinks': missing_links,
    }


def write_outputs(report):
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    s = report['summary']
    lines = ['# Knowledge Graph Quality Audit', '']
    lines.append('## Summary')
    lines.append('')
    lines.append('```json')
    lines.append(json.dumps(s, ensure_ascii=False, indent=2))
    lines.append('```')
    lines.append('')
    lines.append('## Core + L1 + graph_only examples')
    for row in report['core_l1_graph_only'][:50]:
        lines.append(f"- {row['company']} / {row['concept']}：{row['evidence']}")
    lines.append('')
    lines.append('## Overlimit iFinD raw')
    for row in report['overlimit_ifind_raw']:
        lines.append(f"- {row['file']} size={row['size']} overlimit={row['has_overlimit_pattern']} empty={row['empty_shell']}")
    OUT_MD.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--json-only', action='store_true')
    args = parser.parse_args()
    report = build_report()
    write_outputs(report)
    print(json.dumps(report['summary'], ensure_ascii=False, indent=2))
    if not args.json_only:
        print(f'WROTE {OUT_JSON}')
        print(f'WROTE {OUT_MD}')


if __name__ == '__main__':
    main()
