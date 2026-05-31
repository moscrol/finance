#!/usr/bin/env python3
import json
import re
from collections import defaultdict
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
POLLUTION = WIKI / 'raw/theme-radar/entity-exposure-pollution-audit.json'
EXPOSURES = WIKI / 'relations/entity_exposures.json'
OUT_JSON = WIKI / 'raw/theme-radar/entity-exposure-orphan-code-audit.json'
OUT_MD = WIKI / 'raw/theme-radar/entity-exposure-orphan-code-audit.md'

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


def parse_aliases(value):
    value = str(value or '').strip()
    if not value or value in {'[]', ''}:
        return []
    return [x.strip().strip('"\'') for x in re.split(r'[,，\[\]]+', value) if x.strip().strip('"\'')]


def entity_name_index():
    names = {}
    for path in sorted((WIKI / 'entities').glob('*.md')):
        if '.bak' in path.name:
            continue
        fm = read_frontmatter(path)
        title = str(fm.get('title') or '').strip().strip('"')
        aliases = parse_aliases(fm.get('aliases', ''))
        row = {'file_stem': path.stem, 'title': title, 'aliases': aliases, 'file': str(path.relative_to(WIKI))}
        for key in [path.stem, title] + aliases:
            if key:
                names[key] = row
    return names


def normalize_name(s):
    return re.sub(r'(股份有限公司|有限责任公司|集团股份|集团|股份|科技|公司|ST|\*ST|XD|N)$', '', str(s or '')).strip()


def fuzzy_candidates(name, name_index):
    n = normalize_name(name)
    out = []
    if not n:
        return out
    for key, row in name_index.items():
        kn = normalize_name(key)
        if not kn:
            continue
        if n == kn or n in kn or kn in n:
            if row not in out:
                out.append(row)
    return out[:10]


def edge_stats(entity, exposures):
    ent = exposures.get('entities', {}).get(entity, {})
    concepts = ent.get('concepts', {}) or {}
    weak = 0
    strong = 0
    missing_update_type = 0
    generic_role = 0
    for exp in concepts.values():
        role = str(exp.get('role') or '').strip()
        update_type = str(exp.get('update_type') or '').strip()
        if not update_type:
            missing_update_type += 1
        if not role or role in GENERIC_ROLES:
            generic_role += 1
        if update_type in {'curated_research', 'delta', 'baseline', 'hard_delta'}:
            strong += 1
        else:
            weak += 1
    return {
        'concept_count': len(concepts),
        'weak_edge_count': weak,
        'strong_edge_count': strong,
        'missing_update_type_count': missing_update_type,
        'generic_role_count': generic_role,
        'sample_concepts': list(concepts.keys())[:8],
    }


def audit():
    pollution = load_json(POLLUTION)
    exposures = load_json(EXPOSURES)
    name_index = entity_name_index()
    orphan_rows = pollution['queues']['orphan_codes']
    exact_name_exists = []
    fuzzy_name_exists = []
    create_entity_stub = []
    low_value_quarantine = []

    for row in orphan_rows:
        entity = row['entity']
        codes = row.get('codes', [])
        stats = edge_stats(entity, exposures)
        exact = name_index.get(entity)
        fuzzy = fuzzy_candidates(entity, name_index)
        out = {
            'entity': entity,
            'codes': codes,
            'exact_entity_file': exact,
            'fuzzy_candidates': fuzzy,
            **stats,
        }
        if exact:
            exact_name_exists.append(out)
        elif fuzzy:
            fuzzy_name_exists.append(out)
        elif stats['strong_edge_count'] > 0 or stats['concept_count'] >= 3:
            create_entity_stub.append(out)
        else:
            low_value_quarantine.append(out)

    result = {
        'summary': {
            'orphan_code_total': len(orphan_rows),
            'exact_name_exists_count': len(exact_name_exists),
            'fuzzy_name_exists_count': len(fuzzy_name_exists),
            'create_entity_stub_candidates_count': len(create_entity_stub),
            'low_value_quarantine_candidates_count': len(low_value_quarantine),
        },
        'queues': {
            'exact_name_exists_but_code_missing': exact_name_exists,
            'fuzzy_name_exists_review': fuzzy_name_exists,
            'create_entity_stub_candidates': create_entity_stub,
            'low_value_quarantine_candidates': low_value_quarantine,
        }
    }
    return result


def render_md(result):
    lines = ['# Entity Exposure Orphan Code Audit', '', '## Summary', '', '| 指标 | 数量 |', '|---|---:|']
    for k, v in result['summary'].items():
        lines.append(f'| {k} | {v} |')
    for key, title in [
        ('exact_name_exists_but_code_missing', 'Exact name exists but ticker missing'),
        ('fuzzy_name_exists_review', 'Fuzzy name exists review'),
        ('create_entity_stub_candidates', 'Create entity stub candidates'),
        ('low_value_quarantine_candidates', 'Low value quarantine candidates'),
    ]:
        lines.extend(['', f'## {title}', '', '| Entity | Codes | Concepts | Strong | Weak | Candidates / Concepts |', '|---|---|---:|---:|---:|---|'])
        for r in result['queues'][key][:80]:
            cands = '；'.join(c.get('file_stem', '') for c in r.get('fuzzy_candidates', [])[:5])
            if not cands:
                cands = '、'.join(r.get('sample_concepts', [])[:5])
            lines.append(f"| {r['entity']} | {','.join(r['codes'])} | {r['concept_count']} | {r['strong_edge_count']} | {r['weak_edge_count']} | {cands} |")
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
