#!/usr/bin/env python3
import json
import re
from collections import defaultdict
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
EXPOSURES = WIKI / 'relations/entity_exposures.json'
OUT_JSON = WIKI / 'raw/theme-radar/entity-exposure-pollution-audit.json'
OUT_MD = WIKI / 'raw/theme-radar/entity-exposure-pollution-audit.md'

NON_COMPANY_TOKENS = [
    '独有', '受益', '产业链', '赛道', '方向', '逻辑', '公司', '供应商', '企业', '平台', '系统', '方案', '业务', '产品',
    '项目', '市场', '行业', '生态', '核心', '龙头', '标的', '概念', '板块', '环节', '材料', '设备', '技术', '服务',
]
GENERIC_ROLES = {'受益标的', '待验证受益标的', '相关公司', '中游制造及提供商'}


def load_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def read_frontmatter(path):
    text = path.read_text(encoding='utf-8', errors='ignore')[:3000]
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


def parse_tickers(value):
    return re.findall(r'\b\d{6}\b', str(value or ''))


def entity_index():
    by_name = {}
    by_code = defaultdict(list)
    for path in sorted((WIKI / 'entities').glob('*.md')):
        if '.bak' in path.name:
            continue
        fm = read_frontmatter(path)
        title = str(fm.get('title') or path.stem).strip().strip('"')
        tickers = parse_tickers(fm.get('tickers', ''))
        row = {'name': path.stem, 'title': title, 'file': str(path.relative_to(WIKI)), 'tickers': tickers}
        by_name[path.stem] = row
        by_name[title] = row
        for code in tickers:
            by_code[code].append(row)
    return by_name, by_code


def suspicious_name(name):
    flags = []
    if len(name) > 12 and not re.search(r'[（(][A-Z0-9.]+[）)]', name):
        flags.append('long_nonstandard_name')
    if any(token in name for token in NON_COMPANY_TOKENS):
        flags.append('contains_non_company_token')
    if re.search(r'[，,。；;：:]', name):
        flags.append('contains_punctuation_sentence_like')
    if name.endswith(('产业', '技术', '材料', '设备', '系统', '平台', '方案', '服务')):
        flags.append('concept_like_suffix')
    return flags


def edge_bucket(exp):
    update_type = str(exp.get('update_type') or '').strip()
    if update_type:
        return update_type
    sources = ' '.join(str(x) for x in exp.get('sources', []) or [])
    if 'iFinD baseline' in sources or 'AkShare baseline' in sources or 'Baseline' in sources:
        return 'baseline'
    if any(t in sources for t in ('市场逻辑', '复盘', '强势股', '评级日报', '脱水')):
        return 'delta'
    return 'missing'


def audit():
    data = load_json(EXPOSURES)
    by_name, by_code = entity_index()
    rows = []
    code_mismatches = []
    orphan_with_code = []
    concept_like_entities = []
    weak_edges = []

    for name, ent in sorted((data.get('entities') or {}).items()):
        codes = [str(c) for c in ent.get('codes', []) if re.fullmatch(r'\d{6}', str(c))]
        name_hit = by_name.get(name)
        name_flags = suspicious_name(name)
        candidate_by_code = []
        for code in codes:
            candidate_by_code.extend(by_code.get(code, []))
        mismatch = bool(codes and candidate_by_code and not name_hit and all(c['name'] != name and c['title'] != name for c in candidate_by_code))
        orphan_code = bool(codes and not candidate_by_code)
        edge_flags = []
        concepts = ent.get('concepts', {}) or {}
        for concept, exp in concepts.items():
            role = str(exp.get('role') or '').strip()
            flags = []
            bucket = edge_bucket(exp)
            if role in GENERIC_ROLES or not role:
                flags.append('generic_or_missing_role')
            if not exp.get('update_type'):
                flags.append('missing_update_type')
            if not exp.get('chain_layer'):
                flags.append('missing_chain_layer')
            if not exp.get('evidence_layer'):
                flags.append('missing_evidence_layer')
            if not exp.get('evidence'):
                flags.append('missing_evidence')
            if bucket == 'missing' and str(exp.get('strength') or '') in {'core', 'related'}:
                flags.append('possible_overranked')
            if flags:
                edge_flags.append({'concept': concept, 'strength': exp.get('strength', ''), 'bucket': bucket, 'role': role, 'flags': flags, 'sources': exp.get('sources', [])[:3]})
        severity = 0
        if mismatch:
            severity += 5
        if orphan_code:
            severity += 4
        severity += min(len(name_flags), 3) * 2
        severity += min(sum(1 for e in edge_flags if 'possible_overranked' in e['flags']), 5)
        if severity == 0:
            continue
        row = {
            'entity': name,
            'codes': codes,
            'entity_file_match': bool(name_hit),
            'code_candidates': candidate_by_code[:5],
            'name_flags': name_flags,
            'code_name_mismatch': mismatch,
            'orphan_code': orphan_code,
            'concept_count': len(concepts),
            'weak_edge_count': len(edge_flags),
            'severity': severity,
            'sample_edges': edge_flags[:8],
        }
        rows.append(row)
        if mismatch:
            code_mismatches.append(row)
        if orphan_code:
            orphan_with_code.append(row)
        if name_flags:
            concept_like_entities.append(row)
        if edge_flags:
            weak_edges.append(row)

    rows = sorted(rows, key=lambda r: (-r['severity'], r['entity']))
    return {
        'summary': {
            'entities_in_exposures': len(data.get('entities') or {}),
            'suspect_entities': len(rows),
            'code_name_mismatch_count': len(code_mismatches),
            'orphan_code_count': len(orphan_with_code),
            'concept_like_entity_name_count': len(concept_like_entities),
            'suspect_with_weak_edges_count': len(weak_edges),
        },
        'queues': {
            'high_confidence_code_name_mismatch': code_mismatches[:100],
            'concept_like_entity_names': concept_like_entities[:150],
            'orphan_codes': orphan_with_code[:100],
            'all_suspects_ranked': rows[:250],
        }
    }


def render_md(result):
    lines = ['# Entity Exposure Pollution Audit', '', '## Summary', '', '| 指标 | 数量 |', '|---|---:|']
    for k, v in result['summary'].items():
        lines.append(f'| {k} | {v} |')
    for q, title in [
        ('high_confidence_code_name_mismatch', 'High confidence code-name mismatch'),
        ('concept_like_entity_names', 'Concept-like entity names'),
        ('orphan_codes', 'Orphan codes'),
        ('all_suspects_ranked', 'All suspects ranked'),
    ]:
        lines.extend(['', f'## {title}', '', '| Entity | Codes | Severity | Flags | Code candidates | Sample concepts |', '|---|---|---:|---|---|---|'])
        for r in result['queues'][q][:50]:
            cands = '；'.join(f"{c['name']}({','.join(c['tickers'])})" for c in r.get('code_candidates', [])[:3])
            sample = '、'.join(e['concept'] for e in r.get('sample_edges', [])[:5])
            lines.append(f"| {r['entity']} | {','.join(r['codes'])} | {r['severity']} | {', '.join(r['name_flags'])} | {cands} | {sample} |")
    return '\n'.join(lines) + '\n'


def main():
    result = audit()
    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    OUT_MD.write_text(render_md(result), encoding='utf-8')
    print(json.dumps(result['summary'], ensure_ascii=False, indent=2))
    print(str(OUT_JSON))
    print(str(OUT_MD))


if __name__ == '__main__':
    main()
