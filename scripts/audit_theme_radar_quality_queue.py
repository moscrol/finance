#!/usr/bin/env python3
import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import theme_radar_quality_rules as quality_rules

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
REL = WIKI / 'relations'
OUT_JSON = WIKI / 'raw/theme-radar/theme-radar-quality-queue.json'
OUT_MD = WIKI / 'raw/theme-radar/theme-radar-quality-queue.md'
DEFAULT_THEMES = ['先进封装', '商业航天', '固态电池', '人形机器人']

EVIDENCE_BUCKETS = ('baseline', 'curated_research', 'delta', 'graph_only', 'missing')
GENERIC_ROLES = {
    '',
    '受益标的',
    '待验证受益标的',
    '产业链供应商',
    '相关公司',
    '中游制造',
    '上游设备',
    '上游材料',
    '图谱弱关联',
    '市场信号弱关联',
}
COARSE_CHAIN_LAYERS = {
    '',
    '设备/整机/应用',
    '上游材料/设备/芯片制造',
    'downstream',
    'midstream',
    'upstream',
    '上游',
    '中游',
    '下游',
}
WEAK_TOKENS = (
    '弱相关', '待验证', '潜在相关', '市场信号弱关联', '基础资料未直接', '不直接证明',
    '从既有entity markdown重建', '从既有concept markdown重建', 'L2_candidate', 'L1_L3_candidate',
)
HARD_FACT_TOKENS = (
    '公告', '年报', '官网', '合同', '中标', '认证', '量产', '投产', '扩产', '产能',
    '客户导入', '订单', '收入', '营收', '出货', '良率', '送样', '长协', '独家供应',
)
RESEARCH_CLAIM_TOKENS = ('龙头', '唯一', '领先', '壁垒', '市占率', '份额', '毛利率', '绑定', '配套', '布局')
MARKET_NARRATIVE_TOKENS = ('受益', '弹性', '催化', '市场逻辑', '题材', '映射', '预期')

CHAIN_LAYER_NORMALIZE_MAP = {
    'upstream_materials': 'upstream_materials',
    'upstream_components': 'upstream_components',
    'upstream_equipment': 'upstream_equipment',
    'midstream': 'midstream_manufacturing',
    'midstream_manufacturing': 'midstream_manufacturing',
    'midstream_components': 'midstream_components',
    'midstream_service': 'midstream_service',
    'midstream_equipment': 'midstream_equipment',
    'downstream': 'downstream_application',
    'downstream_application': 'downstream_application',
    'downstream_operation': 'downstream_operation',
    'downstream_infrastructure': 'downstream_application',
    'ecosystem': 'ecosystem',
}
CHAIN_LAYER_KEYWORDS = (
    ('材料', 'upstream_materials'),
    ('零部件', 'upstream_components'),
    ('器件', 'upstream_components'),
    ('芯片', 'upstream_components'),
    ('载荷', 'upstream_components'),
    ('设备', 'upstream_equipment'),
    ('装备', 'upstream_equipment'),
    ('制造', 'midstream_manufacturing'),
    ('封装', 'midstream_manufacturing'),
    ('封测', 'midstream_manufacturing'),
    ('代工', 'midstream_manufacturing'),
    ('电池', 'midstream_manufacturing'),
    ('服务', 'midstream_service'),
    ('软件', 'midstream_service'),
    ('运营', 'downstream_operation'),
    ('应用', 'downstream_application'),
    ('生态', 'ecosystem'),
)


def load_json(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding='utf-8'))


def strip_wikilink(value):
    text = str(value or '').strip()
    if text.startswith('[[') and text.endswith(']]'):
        text = text[2:-2]
    if '|' in text:
        text = text.split('|', 1)[0]
    return text.strip()


def normalize_chain_layer(value):
    return quality_rules.normalize_chain_layer(value)


def exposure_bucket(exp):
    update_type = str(exp.get('update_type') or '').strip()
    fact_hardness = str(exp.get('fact_hardness') or '').strip()
    evidence = str(exp.get('evidence') or '')
    sources = ' '.join(str(x) for x in exp.get('sources', []) or [])
    if update_type in EVIDENCE_BUCKETS:
        return update_type
    if 'iFinD baseline' in sources or 'AkShare baseline' in sources or 'Baseline' in sources:
        return 'baseline'
    explicit_weak_graph_only = (
        update_type == 'graph_only'
        or fact_hardness == 'legacy_rebuilt'
        or '从既有entity markdown重建' in evidence
        or '从既有concept markdown重建' in evidence
    )
    if not explicit_weak_graph_only and any(token in sources for token in ('市场逻辑', '强势股', '评级日报', '复盘', '脱水')):
        return 'delta'
    return 'missing'


def fact_hardness(item):
    return quality_rules.infer_evidence_item_hardness(item)


def build_evidence_by_target(evidence_index):
    out = defaultdict(list)
    for item in evidence_index.get('items', []) or []:
        target = strip_wikilink(item.get('target', ''))
        if target:
            out[target].append(item)
    return out


def concept_companies(theme, concept_graph, exposures):
    rows = {}
    node = (concept_graph.get('concepts') or {}).get(theme) or {}
    for company in node.get('companies', []) or []:
        name = company.get('name') or company.get('company') or ''
        if not name:
            continue
        rows.setdefault(name, {'name': name, 'code': company.get('code', ''), 'concept': theme, 'graph_company': company, 'exposure': {}})
    for entity, ent in (exposures.get('entities') or {}).items():
        concepts = (ent or {}).get('concepts') or {}
        if theme not in concepts:
            continue
        rows.setdefault(entity, {'name': entity, 'code': (ent.get('codes') or [''])[0], 'concept': theme, 'graph_company': {}, 'exposure': {}})
        rows[entity]['code'] = rows[entity].get('code') or (ent.get('codes') or [''])[0]
        rows[entity]['exposure'] = concepts.get(theme) or {}
    return list(rows.values())


def issue_item(theme, company, exp, issue, severity, reason, suggested_action, evidence_items=None):
    return {
        'theme': theme,
        'company': company['name'],
        'code': company.get('code', ''),
        'issue': issue,
        'severity': severity,
        'strength': exp.get('strength', ''),
        'bucket': exposure_bucket(exp) if exp else 'missing',
        'role': exp.get('role', '') if exp else '',
        'chain_layer': exp.get('chain_layer', '') if exp else '',
        'evidence_layer': exp.get('evidence_layer', '') if exp else '',
        'update_type': exp.get('update_type', '') if exp else '',
        'reason': reason,
        'suggested_action': suggested_action,
        'sources': (exp.get('sources', []) or [])[:3] if exp else [],
        'evidence_sample': str(exp.get('evidence', ''))[:220] if exp else '',
        'evidence_items': evidence_items or [],
    }


def audit_theme(theme, concept_graph, exposures, evidence_by_target):
    rows = concept_companies(theme, concept_graph, exposures)
    items = []
    for company in rows:
        exp = company.get('exposure') or {}
        role = str(exp.get('role') or '').strip()
        chain_layer = str(exp.get('chain_layer') or '').strip()
        bucket = exposure_bucket(exp) if exp else 'missing'
        strength = str(exp.get('strength') or 'related')
        evidence_text = ' '.join([role, chain_layer, str(exp.get('evidence') or ''), str(exp.get('evidence_layer') or ''), str(exp.get('update_type') or '')])
        target_evidence = evidence_by_target.get(company['name'], [])
        evidence_hardness = Counter(fact_hardness(x) for x in target_evidence)
        evidence_sample = [
            {
                'source': x.get('source', ''),
                'evidence': str(x.get('evidence', ''))[:160],
                'fact_hardness': fact_hardness(x),
            }
            for x in target_evidence[:5]
        ]

        if quality_rules.is_generic_role(role):
            items.append(issue_item(theme, company, exp, 'role_too_generic', 'P1', '角色为空或过泛，无法支撑题材颗粒度排序。', '人工/脚本回填具体业务角色短语。', evidence_sample))
        if quality_rules.is_coarse_chain_layer(chain_layer):
            items.append(issue_item(theme, company, exp, 'chain_layer_too_coarse', 'P1', '链层过粗，影响产业链位置和排序解释。', '归一到通用链层枚举，并保留原始链层。', evidence_sample))
        raw_layer = normalize_chain_layer(chain_layer)
        role_layers = set(quality_rules.strict_role_chain_layers(role))
        if raw_layer not in ('', 'unknown') and role_layers and raw_layer not in role_layers:
            items.append(issue_item(theme, company, exp, 'chain_layer_conflict', 'P0', f'链层归一为 {raw_layer}，角色严格推断为 {sorted(role_layers)}，两者冲突。', '核对 role 与 chain_layer，优先按主营/产品事实修正。', evidence_sample))
        if bucket in {'graph_only', 'missing'} and strength in {'core', 'related'}:
            items.append(issue_item(theme, company, exp, 'graph_only_core_or_related', 'P0', 'core/related 公司只有 graph_only 或 missing 支撑，可能过度高估。', '补 baseline/硬事实，或降级 strength。', evidence_sample))
        if any(token in evidence_text for token in quality_rules.WEAK_TOKENS):
            items.append(issue_item(theme, company, exp, 'weak_granularity', 'P1', '证据含弱颗粒度信号，需核准直接业务关系。', '补充直接产品/收入占比/客户/量产证据，或降级。', evidence_sample))
        if bucket == 'curated_research' or evidence_hardness.get('research_claim') or evidence_hardness.get('review_candidate'):
            if not exp.get('fact_hardness'):
                items.append(issue_item(theme, company, exp, 'curated_research_needs_hardness', 'P1', '研究线索缺 fact_hardness，硬事实/研报声称/市场叙事混在一起。', '补 fact_hardness=hard_fact/review_candidate/research_claim/market_narrative/legacy_rebuilt。', evidence_sample))
        explicit_non_direct_graph_only = (
            bucket == 'graph_only'
            and strength == 'peripheral'
            and (
                normalize_chain_layer(chain_layer) == 'ecosystem'
                or '非直接产业链' in role
                or quality_rules.is_weak_role(role)
            )
        )
        if evidence_hardness.get('baseline') and bucket not in {'baseline', 'curated_research', 'delta'} and not explicit_non_direct_graph_only:
            items.append(issue_item(theme, company, exp, 'baseline_scope_mismatch', 'P1', 'evidence_index 有 baseline，但 exposure bucket 未体现。', '把公司级 baseline 合并入该题材暴露的 evidence bucket 或补 exposure 元数据。', evidence_sample))
    return items


def render_md(result):
    lines = ['# Theme Radar Quality Queue', '', f"Generated: {result['generated_at']}", '']
    lines.extend(['## Summary', '', '| 指标 | 数量 |', '|---|---:|'])
    for key, value in result['summary'].items():
        if isinstance(value, dict):
            continue
        lines.append(f'| {key} | {value} |')
    lines.extend(['', '## Issues by type', '', '```json', json.dumps(result['summary']['issues_by_type'], ensure_ascii=False, indent=2), '```'])
    lines.extend(['', '## Top queue', '', '| Theme | Company | Severity | Issue | Bucket | Role | Chain layer | Suggested action |', '|---|---|---|---|---|---|---|---|'])
    for item in result['items'][:80]:
        lines.append(f"| {item['theme']} | {item['company']} | {item['severity']} | {item['issue']} | {item['bucket']} | {item['role']} | {item['chain_layer']} | {item['suggested_action']} |")
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description='Build read-only Theme Radar data quality queue for selected themes.')
    parser.add_argument('--themes', nargs='*', default=DEFAULT_THEMES)
    parser.add_argument('--all', action='store_true')
    parser.add_argument('--out-json', default=str(OUT_JSON))
    parser.add_argument('--out-md', default=str(OUT_MD))
    args = parser.parse_args()

    concept_graph = load_json(REL / 'concept_graph.json', {'concepts': {}})
    exposures = load_json(REL / 'entity_exposures.json', {'entities': {}})
    evidence_index = load_json(REL / 'evidence_index.json', {'items': []})
    evidence_by_target = build_evidence_by_target(evidence_index)
    if args.all:
        themes = set((concept_graph.get('concepts') or {}).keys())
        for ent in (exposures.get('entities') or {}).values():
            themes.update((ent.get('concepts') or {}).keys())
        args.themes = sorted(x for x in themes if x)
        if args.out_json == str(OUT_JSON):
            args.out_json = str(WIKI / 'raw/theme-radar/theme-radar-quality-queue-global.json')
        if args.out_md == str(OUT_MD):
            args.out_md = str(WIKI / 'raw/theme-radar/theme-radar-quality-queue-global.md')

    all_items = []
    theme_counts = {}
    for theme in args.themes:
        items = audit_theme(theme, concept_graph, exposures, evidence_by_target)
        theme_counts[theme] = len(items)
        all_items.extend(items)

    severity_rank = {'P0': 0, 'P1': 1, 'P2': 2}
    all_items = sorted(all_items, key=lambda x: (severity_rank.get(x['severity'], 9), x['theme'], x['company'], x['issue']))
    result = {
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'themes': args.themes,
        'summary': {
            'themes_count': len(args.themes),
            'items_count': len(all_items),
            'issues_by_theme': theme_counts,
            'issues_by_type': dict(Counter(x['issue'] for x in all_items)),
            'issues_by_severity': dict(Counter(x['severity'] for x in all_items)),
        },
        'items': all_items,
    }

    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    out_md.write_text(render_md(result), encoding='utf-8')
    print(json.dumps(result['summary'], ensure_ascii=False, indent=2))
    print(str(out_json))
    print(str(out_md))


if __name__ == '__main__':
    main()
