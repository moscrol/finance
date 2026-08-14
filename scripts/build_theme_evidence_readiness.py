#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

# Direct execution needs the sibling scripts directory before this local import.
import theme_radar_quality_rules as quality_rules  # noqa: E402

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
REL = WIKI / 'relations'
OUT_DIR = WIKI / 'raw/theme-radar'

OFFICIAL_SOURCE_QUALITY = {'official_disclosure', 'company_primary', 'exchange_interaction'}
BROKER_SOURCE_QUALITY = {'broker_research_high', 'broker_research_normal'}
HIGH_HARDNESS = {'hard_fact'}
MEDIUM_HARDNESS = {'review_candidate', 'research_claim', 'baseline'}
LOW_HARDNESS = {'legacy_rebuilt', 'market_narrative', 'unknown', ''}
STRENGTH_RANK = {'core': 0, 'related': 1, 'peripheral': 2, '': 3}
CONFIDENCE_RANK = {'low': 0, 'medium': 1, 'high': 2}
DIRECT_TOKENS = ('产品', '产能', '客户', '订单', '中标', '量产', '收入', '市占率', '供应商', '官网', '年报', '公告', '互动易', '标准')
OFFICIAL_SOURCE_TOKENS = ('年报', '公告', '官网', '互动易', '巨潮', '定期报告', '公司公告', '公司官网', '官方')
BASELINE_SOURCE_TOKENS = ('iFinD baseline', 'AkShare baseline', 'Baseline', '基础资料', '公司摘要')


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def strip_wikilink(value):
    text = str(value or '').strip()
    while text.startswith('[[') and text.endswith(']]'):
        text = text[2:-2].strip()
    if '|' in text:
        text = text.split('|', 1)[0].strip()
    return text[:-3] if text.endswith('.md') else text


def safe_filename(value):
    return re.sub(r'[/:*?"<>|\n\r\t]+', '_', str(value or '')).strip()


def is_theme_related(item, theme):
    concept = strip_wikilink(item.get('concept', ''))
    if concept == theme:
        return True
    blob = ' '.join(str(item.get(k, '')) for k in ('source', 'evidence', 'concept'))
    return theme in blob


def infer_hardness(item):
    return quality_rules.infer_evidence_item_hardness(item or {})


def source_quality(item):
    return str((item or {}).get('source_quality') or '').strip()


def is_official_item(item):
    sq = source_quality(item)
    source = str((item or {}).get('source') or '')
    evidence = str((item or {}).get('evidence') or '')
    hardness = infer_hardness(item)
    return sq in OFFICIAL_SOURCE_QUALITY or hardness in HIGH_HARDNESS or any(token in source or token in evidence for token in OFFICIAL_SOURCE_TOKENS)


def has_direct_theme_signal(item, theme):
    evidence = str((item or {}).get('evidence') or '')
    source = str((item or {}).get('source') or '')
    concept = strip_wikilink((item or {}).get('concept', ''))
    if concept == theme and any(token in evidence for token in DIRECT_TOKENS):
        return True
    return theme in evidence and any(token in evidence or token in source for token in DIRECT_TOKENS)


def exposure_bucket(exp):
    update_type = str((exp or {}).get('update_type') or '').strip()
    fact_hardness = str((exp or {}).get('fact_hardness') or '').strip()
    evidence = str((exp or {}).get('evidence') or '')
    sources = ' '.join(str(x) for x in (exp or {}).get('sources', []) or [])
    if update_type in {'baseline', 'curated_research', 'delta', 'graph_only'}:
        return update_type
    if any(token in sources for token in BASELINE_SOURCE_TOKENS):
        return 'baseline'
    if fact_hardness == 'legacy_rebuilt' or '从既有' in evidence:
        return 'graph_only'
    return 'missing'


def collect_companies(theme, concept_graph, exposures):
    rows = {}
    node = (concept_graph.get('concepts') or {}).get(theme) or {}
    for item in node.get('companies', []) or []:
        name = item.get('name') or item.get('company') or ''
        if not name:
            continue
        rows.setdefault(name, {'company': name, 'code': item.get('code', ''), 'graph_company': item, 'exposure': {}})
    for name, ent in (exposures.get('entities') or {}).items():
        exp = ((ent or {}).get('concepts') or {}).get(theme)
        if not exp:
            continue
        rows.setdefault(name, {'company': name, 'code': '', 'graph_company': {}, 'exposure': {}})
        codes = ent.get('codes') if isinstance(ent, dict) else []
        rows[name]['code'] = rows[name].get('code') or ((codes or [''])[0] if isinstance(codes, list) else '')
        rows[name]['exposure'] = exp or {}
    return list(rows.values())


def entity_has_markdown_baseline(company):
    path = WIKI / 'entities' / f'{safe_filename(company)}.md'
    if not path.exists():
        return False
    try:
        text = path.read_text(encoding='utf-8')[:6000]
    except Exception:
        return False
    return '## 公司基线' in text or '## 基础画像' in text or '## 静态基线' in text or 'baseline来源' in text


def row_for_company(theme, company, evidence_by_target):
    name = company['company']
    exp = company.get('exposure') or {}
    items = evidence_by_target.get(name, [])
    theme_items = [item for item in items if is_theme_related(item, theme)]
    baseline_items = [item for item in items if infer_hardness(item) == 'baseline' or any(token in str(item.get('source', '')) for token in BASELINE_SOURCE_TOKENS)]
    official_items = [item for item in theme_items if is_official_item(item)]
    direct_items = [item for item in theme_items if has_direct_theme_signal(item, theme)]
    review_items = [item for item in theme_items if infer_hardness(item) in {'review_candidate', 'research_claim'} or source_quality(item) in BROKER_SOURCE_QUALITY]
    bucket = exposure_bucket(exp)
    exp_hardness = str(exp.get('fact_hardness') or '').strip() or infer_hardness(exp)
    exp_sq = str(exp.get('source_quality') or '').strip()
    entity_baseline_ready = bool(baseline_items) or entity_has_markdown_baseline(name)
    theme_evidence_ready = bucket in {'baseline', 'curated_research', 'delta'} or bool(theme_items)
    official_evidence_ready = bool(official_items) or exp_sq in OFFICIAL_SOURCE_QUALITY or exp_hardness in HIGH_HARDNESS
    direct_theme_evidence_ready = bool(direct_items) or (theme in str(exp.get('evidence', '')) and any(token in str(exp.get('evidence', '')) for token in DIRECT_TOKENS))
    if official_evidence_ready and direct_theme_evidence_ready:
        tier = 'high'
    elif review_items or bucket in {'curated_research', 'delta'} or exp_hardness in MEDIUM_HARDNESS:
        tier = 'medium'
    else:
        tier = 'low'
    missing = []
    if not entity_baseline_ready:
        missing.append('缺 entity baseline')
    if not theme_evidence_ready:
        missing.append('缺题材直接证据')
    if not official_evidence_ready:
        missing.append('缺官方/公司级来源')
    if not direct_theme_evidence_ready:
        missing.append('缺产品/收入/客户/订单/产能等直接证据')
    if bucket == 'graph_only' or exp_hardness in {'legacy_rebuilt', 'market_narrative', 'unknown'}:
        missing.append('当前仅图谱/市场叙事/旧重建支撑')
    if exp.get('review_required'):
        missing.append('需要人工复核')
    is_non_direct_graph_only = (
        company_strength(exp) == 'peripheral'
        and bucket == 'graph_only'
        and (
            quality_rules.normalize_chain_layer(exp.get('chain_layer', '')) == 'ecosystem'
            or '非直接产业链' in str(exp.get('role', ''))
            or '市场信号待核验' in str(exp.get('role', ''))
        )
    )
    if official_evidence_ready and direct_theme_evidence_ready:
        next_action = '可优先用于雷达解释；后续只需例行复核'
    elif is_non_direct_graph_only:
        next_action = '暂不补公告；除非后续被提升为核心/相关候选，否则保留低置信图谱节点'
    elif not official_evidence_ready:
        next_action = '优先补年报/公告/官网/互动易中的题材直接证据'
    elif not direct_theme_evidence_ready:
        next_action = '从已有官方来源中抽取产品/收入/客户/订单/产能口径'
    elif review_items:
        next_action = '已有研报线索，补官方证据后可升高置信'
    else:
        next_action = '保留为低置信图谱节点或降级'
    if company_strength(exp) in {'core', 'related'} and tier == 'low':
        priority = 'P0'
    elif company_strength(exp) in {'core', 'related'} or bucket in {'curated_research', 'delta'}:
        priority = 'P1'
    else:
        priority = 'P2'
    sample_items = theme_items[:3] or items[:3]
    samples = [{'source': x.get('source', ''), 'concept': x.get('concept', ''), 'fact_hardness': infer_hardness(x), 'source_quality': source_quality(x), 'evidence': str(x.get('evidence', ''))[:160]} for x in sample_items]
    return {
        'theme': theme,
        'company': name,
        'code': company.get('code', ''),
        'priority': priority,
        'strength': company_strength(exp),
        'role': exp.get('role', ''),
        'chain_layer': exp.get('chain_layer', ''),
        'bucket': bucket,
        'fact_hardness': exp_hardness,
        'source_quality': exp_sq,
        'review_required': bool(exp.get('review_required')),
        'entity_baseline_ready': entity_baseline_ready,
        'theme_evidence_ready': theme_evidence_ready,
        'official_evidence_ready': official_evidence_ready,
        'direct_theme_evidence_ready': direct_theme_evidence_ready,
        'confidence_tier': tier,
        'missing_reason': '；'.join(dict.fromkeys(missing)) or '高置信证据基本齐备',
        'next_action': next_action,
        'evidence_item_count': len(items),
        'theme_evidence_item_count': len(theme_items),
        'official_theme_evidence_count': len(official_items),
        'direct_theme_evidence_count': len(direct_items),
        'evidence_samples': samples,
    }


def company_strength(exp):
    return str((exp or {}).get('strength') or 'related').strip()


def sort_rows(rows):
    return sorted(rows, key=lambda x: (x['priority'], STRENGTH_RANK.get(x['strength'], 9), CONFIDENCE_RANK.get(x['confidence_tier'], 9), x['company']))


def render_md(result):
    lines = ['# Theme Evidence Readiness', '', f"Generated: {result['generated_at']}", f"Theme: {result['theme']}", '']
    lines.extend(['## Summary', '', '| 指标 | 数量 |', '|---|---:|'])
    for key, value in result['summary'].items():
        if isinstance(value, dict):
            continue
        lines.append(f'| {key} | {value} |')
    lines.extend(['', '## By confidence tier', '', '```json', json.dumps(result['summary']['by_confidence_tier'], ensure_ascii=False, indent=2), '```'])
    lines.extend(['', '## By priority', '', '```json', json.dumps(result['summary']['by_priority'], ensure_ascii=False, indent=2), '```'])
    lines.extend(['', '## Readiness queue', '', '| Priority | Company | Strength | Tier | Official | Direct | Baseline | Bucket | Role | Missing | Next action |', '|---|---|---|---|---|---|---|---|---|---|---|'])
    for row in result['rows'][:120]:
        lines.append('| {priority} | {company} | {strength} | {confidence_tier} | {official} | {direct} | {baseline} | {bucket} | {role} | {missing} | {action} |'.format(
            priority=row['priority'],
            company=row['company'],
            strength=row['strength'],
            confidence_tier=row['confidence_tier'],
            official='Y' if row['official_evidence_ready'] else 'N',
            direct='Y' if row['direct_theme_evidence_ready'] else 'N',
            baseline='Y' if row['entity_baseline_ready'] else 'N',
            bucket=row['bucket'],
            role=str(row['role']).replace('|', '\\|'),
            missing=row['missing_reason'].replace('|', '\\|'),
            action=row['next_action'].replace('|', '\\|'),
        ))
    return '\n'.join(lines) + '\n'


def build(theme):
    concept_graph = load_json(REL / 'concept_graph.json', {'concepts': {}})
    exposures = load_json(REL / 'entity_exposures.json', {'entities': {}})
    evidence_index = load_json(REL / 'evidence_index.json', {'items': []})
    evidence_by_target = {}
    for item in evidence_index.get('items', []) or []:
        target = strip_wikilink(item.get('target', ''))
        if target:
            evidence_by_target.setdefault(target, []).append(item)
    companies = collect_companies(theme, concept_graph, exposures)
    rows = sort_rows([row_for_company(theme, company, evidence_by_target) for company in companies])
    summary = {
        'company_count': len(rows),
        'high_confidence': sum(1 for x in rows if x['confidence_tier'] == 'high'),
        'medium_confidence': sum(1 for x in rows if x['confidence_tier'] == 'medium'),
        'low_confidence': sum(1 for x in rows if x['confidence_tier'] == 'low'),
        'entity_baseline_ready': sum(1 for x in rows if x['entity_baseline_ready']),
        'theme_evidence_ready': sum(1 for x in rows if x['theme_evidence_ready']),
        'official_evidence_ready': sum(1 for x in rows if x['official_evidence_ready']),
        'direct_theme_evidence_ready': sum(1 for x in rows if x['direct_theme_evidence_ready']),
        'review_required': sum(1 for x in rows if x['review_required']),
        'by_confidence_tier': dict(Counter(x['confidence_tier'] for x in rows)),
        'by_priority': dict(Counter(x['priority'] for x in rows)),
    }
    return {'generated_at': datetime.now().isoformat(timespec='seconds'), 'theme': theme, 'summary': summary, 'rows': rows}


def main():
    parser = argparse.ArgumentParser(description='Build read-only Theme Evidence Readiness report.')
    parser.add_argument('--theme', required=True)
    parser.add_argument('--out-json', default='')
    parser.add_argument('--out-md', default='')
    args = parser.parse_args()
    result = build(args.theme)
    out_json = Path(args.out_json) if args.out_json else OUT_DIR / f'theme-evidence-readiness-{args.theme}.json'
    out_md = Path(args.out_md) if args.out_md else OUT_DIR / f'theme-evidence-readiness-{args.theme}.md'
    write_json(out_json, result)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_md(result), encoding='utf-8')
    print(json.dumps({**result['summary'], 'json': str(out_json), 'md': str(out_md)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
