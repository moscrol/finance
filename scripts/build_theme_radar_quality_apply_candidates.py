#!/usr/bin/env python3
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
QUEUE = WIKI / 'raw/theme-radar/theme-radar-quality-queue.json'
OUT_JSON = WIKI / 'raw/theme-radar/theme-radar-quality-apply-candidates.json'
OUT_MD = WIKI / 'raw/theme-radar/theme-radar-quality-apply-candidates.md'

ROLE_LAYER_RULES = (
    ('电镀液', 'upstream_materials'),
    ('添加剂', 'upstream_materials'),
    ('清洗液', 'upstream_materials'),
    ('电子布', 'upstream_materials'),
    ('玻纤', 'upstream_materials'),
    ('铝塑膜', 'upstream_materials'),
    ('BOPA', 'upstream_materials'),
    ('高分子', 'upstream_materials'),
    ('固态电解质', 'upstream_materials'),
    ('电解质', 'upstream_materials'),
    ('硫化物', 'upstream_materials'),
    ('材料', 'upstream_materials'),
    ('设备', 'upstream_equipment'),
    ('刻蚀', 'upstream_equipment'),
    ('清洗设备', 'upstream_equipment'),
    ('检测', 'upstream_equipment'),
    ('量检测', 'upstream_equipment'),
    ('涂布', 'upstream_equipment'),
    ('辊压', 'upstream_equipment'),
    ('载板', 'upstream_components'),
    ('基板', 'upstream_components'),
    ('芯片', 'upstream_components'),
    ('载荷', 'upstream_components'),
    ('光学', 'upstream_components'),
    ('封测', 'midstream_manufacturing'),
    ('封装', 'midstream_manufacturing'),
    ('SiP', 'midstream_manufacturing'),
    ('TSV', 'midstream_manufacturing'),
    ('电池', 'midstream_manufacturing'),
    ('运营商', 'downstream_operation'),
    ('运营', 'downstream_operation'),
    ('应用', 'downstream_application'),
)

HARDNESS_PRIORITY = ('baseline', 'review_candidate', 'research_claim', 'market_narrative', 'legacy_rebuilt', 'unknown')
AUTO_SAFE_ISSUES = {'baseline_scope_mismatch', 'chain_layer_too_coarse', 'curated_research_needs_hardness'}
MANUAL_ISSUES = {'chain_layer_conflict', 'role_too_generic', 'weak_granularity', 'graph_only_core_or_related'}


def load_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def infer_layer_from_role(role):
    text = str(role or '')
    for token, layer in ROLE_LAYER_RULES:
        if token in text:
            return layer
    return ''


def best_hardness(evidence_items):
    values = Counter(x.get('fact_hardness') or 'unknown' for x in evidence_items or [])
    for value in HARDNESS_PRIORITY:
        if values.get(value):
            return value
    return ''


def grouped_items(items):
    grouped = defaultdict(list)
    for item in items:
        grouped[(item['theme'], item['company'])].append(item)
    return grouped


def build_candidate(theme, company, rows):
    issues = {r['issue'] for r in rows}
    sample = rows[0]
    manual_reasons = sorted(issues & MANUAL_ISSUES)
    actions = []
    confidence = 'low'
    auto_safe = True

    if 'chain_layer_conflict' in issues:
        auto_safe = False
    if 'role_too_generic' in issues:
        auto_safe = False
    if 'weak_granularity' in issues and sample.get('strength') in {'core', 'related'}:
        auto_safe = False

    if 'baseline_scope_mismatch' in issues:
        actions.append({
            'field': 'update_type',
            'suggested_value': 'baseline',
            'reason': 'company evidence_index contains baseline evidence while exposure bucket is graph_only/missing',
        })
        confidence = 'medium'

    if 'chain_layer_too_coarse' in issues:
        inferred = infer_layer_from_role(sample.get('role', ''))
        if inferred:
            actions.append({
                'field': 'chain_layer',
                'suggested_value': inferred,
                'reason': 'inferred from specific role keywords',
            })
            confidence = 'medium' if confidence == 'low' else confidence
        else:
            auto_safe = False
            manual_reasons.append('cannot_infer_specific_chain_layer')

    if 'curated_research_needs_hardness' in issues:
        hardness = best_hardness(sample.get('evidence_items', []))
        if hardness and hardness != 'unknown':
            actions.append({
                'field': 'fact_hardness',
                'suggested_value': hardness,
                'reason': 'derived from evidence sample hardness classification',
            })
            if hardness in {'legacy_rebuilt', 'market_narrative', 'research_claim'}:
                actions.append({
                    'field': 'review_required',
                    'suggested_value': True,
                    'reason': 'non-hard-fact evidence should remain review gated',
                })
            confidence = 'medium' if hardness in {'baseline', 'review_candidate'} else 'low'
        else:
            auto_safe = False
            manual_reasons.append('cannot_infer_fact_hardness')

    if not actions:
        auto_safe = False

    if confidence == 'low':
        auto_safe = False
        manual_reasons.append('low_confidence_candidate')

    if not auto_safe:
        confidence = 'manual'

    return {
        'theme': theme,
        'company': company,
        'code': sample.get('code', ''),
        'issues': sorted(issues),
        'severity': 'P0' if any(r.get('severity') == 'P0' for r in rows) else 'P1',
        'auto_safe': auto_safe,
        'confidence': confidence,
        'manual_reasons': sorted(set(manual_reasons)),
        'current': {
            'strength': sample.get('strength', ''),
            'bucket': sample.get('bucket', ''),
            'role': sample.get('role', ''),
            'chain_layer': sample.get('chain_layer', ''),
            'evidence_layer': sample.get('evidence_layer', ''),
            'update_type': sample.get('update_type', ''),
        },
        'actions': actions,
        'sources': sample.get('sources', []),
        'evidence_sample': sample.get('evidence_sample', ''),
    }


def render_md(result):
    lines = ['# Theme Radar Quality Apply Candidates', '', f"Generated: {result['generated_at']}", '']
    lines.extend(['## Summary', '', '| 指标 | 数量 |', '|---|---:|'])
    for key, value in result['summary'].items():
        if isinstance(value, dict):
            continue
        lines.append(f'| {key} | {value} |')
    lines.extend(['', '## Auto-safe candidates', '', '| Theme | Company | Confidence | Issues | Actions |', '|---|---|---|---|---|'])
    for item in result['auto_safe_candidates'][:80]:
        actions = '; '.join(f"{a['field']}={a['suggested_value']}" for a in item['actions'])
        lines.append(f"| {item['theme']} | {item['company']} | {item['confidence']} | {', '.join(item['issues'])} | {actions} |")
    lines.extend(['', '## Manual review candidates', '', '| Theme | Company | Severity | Issues | Manual reasons |', '|---|---|---|---|---|'])
    for item in result['manual_review_candidates'][:80]:
        lines.append(f"| {item['theme']} | {item['company']} | {item['severity']} | {', '.join(item['issues'])} | {', '.join(item['manual_reasons'])} |")
    return '\n'.join(lines) + '\n'


def main():
    queue = load_json(QUEUE)
    candidates = [build_candidate(theme, company, rows) for (theme, company), rows in grouped_items(queue.get('items', [])).items()]
    auto_safe = sorted([c for c in candidates if c['auto_safe']], key=lambda x: (x['theme'], x['company']))
    manual = sorted([c for c in candidates if not c['auto_safe']], key=lambda x: (x['severity'] != 'P0', x['theme'], x['company']))
    result = {
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'source_queue': str(QUEUE.relative_to(WIKI)),
        'summary': {
            'total_company_theme_pairs': len(candidates),
            'auto_safe_count': len(auto_safe),
            'manual_review_count': len(manual),
            'auto_safe_by_theme': dict(Counter(c['theme'] for c in auto_safe)),
            'manual_by_theme': dict(Counter(c['theme'] for c in manual)),
            'auto_action_fields': dict(Counter(a['field'] for c in auto_safe for a in c['actions'])),
        },
        'auto_safe_candidates': auto_safe,
        'manual_review_candidates': manual,
    }
    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    OUT_MD.write_text(render_md(result), encoding='utf-8')
    print(json.dumps(result['summary'], ensure_ascii=False, indent=2))
    print(str(OUT_JSON))
    print(str(OUT_MD))


if __name__ == '__main__':
    main()
