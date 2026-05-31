#!/usr/bin/env python3
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

import theme_radar_quality_rules as quality_rules

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
QUEUE = WIKI / 'raw/theme-radar/theme-radar-quality-queue.json'
OUT_JSON = WIKI / 'raw/theme-radar/theme-radar-quality-auto-adjudication.json'
OUT_MD = WIKI / 'raw/theme-radar/theme-radar-quality-auto-adjudication.md'


def load_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def adjudicate(item):
    issues = {item.get('issue')}
    role = item.get('role', '')
    chain = item.get('chain_layer', '')
    h = quality_rules.inferred_hardness(item)
    score = quality_rules.direct_score(item)
    inferred = quality_rules.infer_layer(role)
    weak_role = quality_rules.is_weak_role(role)
    generic_role = quality_rules.is_generic_role(role)
    actions = []
    decision = 'mark_review_required'
    confidence = 'low'
    rationale = []

    if item.get('issue') == 'chain_layer_conflict':
        if inferred and inferred != chain and not weak_role and not generic_role and score >= 1:
            actions.append({'field': 'chain_layer', 'value': inferred, 'reason': 'role-specific layer overrides conflicting chain_layer'})
            decision = 'fix_chain_layer'
            confidence = 'medium' if score >= 1 else 'low'
        if score <= 0 or weak_role or generic_role:
            actions.append({'field': 'strength', 'value': 'peripheral', 'reason': 'weak or indirect relation should not rank core/related'})
            actions.append({'field': 'review_required', 'value': True, 'reason': 'chain-layer conflict with weak directness'})
            decision = 'downgrade_or_review'
            confidence = 'medium'
    elif item.get('issue') == 'role_too_generic':
        actions.append({'field': 'review_required', 'value': True, 'reason': 'generic role cannot support ranking'})
        if score <= 0:
            actions.append({'field': 'strength', 'value': 'peripheral', 'reason': 'generic role and no direct theme evidence'})
        decision = 'gate_generic_role'
        confidence = 'medium'
    elif item.get('issue') == 'weak_granularity':
        actions.append({'field': 'review_required', 'value': True, 'reason': 'weak granularity signal'})
        if score <= 0:
            actions.append({'field': 'strength', 'value': 'peripheral', 'reason': 'weak granularity without direct score'})
        decision = 'gate_weak_granularity'
        confidence = 'medium'
    elif item.get('issue') == 'chain_layer_too_coarse':
        if inferred:
            actions.append({'field': 'chain_layer', 'value': inferred, 'reason': 'inferred from role keyword'})
            decision = 'fix_chain_layer'
            confidence = 'medium'
        else:
            actions.append({'field': 'review_required', 'value': True, 'reason': 'coarse chain_layer without safe inference'})
            decision = 'gate_coarse_chain_layer'
            confidence = 'medium'
    elif item.get('issue') == 'curated_research_needs_hardness':
        if h != 'unknown':
            actions.append({'field': 'fact_hardness', 'value': h, 'reason': 'derived from evidence hardness'})
        if h in {'legacy_rebuilt', 'market_narrative', 'research_claim', 'unknown'}:
            actions.append({'field': 'review_required', 'value': True, 'reason': 'non-hard evidence requires gating'})
        decision = 'set_hardness_or_gate'
        confidence = 'medium' if h in {'baseline', 'review_candidate'} else 'low'
    elif item.get('issue') == 'baseline_scope_mismatch':
        if h == 'baseline':
            actions.append({'field': 'update_type', 'value': 'baseline', 'reason': 'baseline evidence exists for company'})
            actions.append({'field': 'fact_hardness', 'value': 'baseline', 'reason': 'baseline evidence exists for company'})
            decision = 'promote_baseline_bucket'
            confidence = 'medium'

    if not actions:
        actions.append({'field': 'review_required', 'value': True, 'reason': 'fallback gate by theme-radar adjudicator'})
    rationale.append(f'direct_score={score}')
    rationale.append(f'hardness={h}')
    if inferred:
        rationale.append(f'inferred_layer={inferred}')
    return {
        'theme': item.get('theme'),
        'company': item.get('company'),
        'code': item.get('code', ''),
        'issue': item.get('issue'),
        'severity': item.get('severity'),
        'decision': decision,
        'confidence': confidence,
        'current': {
            'strength': item.get('strength', ''),
            'bucket': item.get('bucket', ''),
            'role': role,
            'chain_layer': chain,
            'update_type': item.get('update_type', ''),
            'evidence_layer': item.get('evidence_layer', ''),
        },
        'actions': actions,
        'rationale': rationale,
        'evidence_sample': item.get('evidence_sample', ''),
    }


def merge_adjudications(rows):
    grouped = {}
    for row in rows:
        key = (row['theme'], row['company'])
        target = grouped.setdefault(key, {k: row[k] for k in ('theme', 'company', 'code')})
        target.setdefault('issues', []).append(row['issue'])
        target.setdefault('decisions', []).append(row['decision'])
        target.setdefault('rationale', []).extend(row['rationale'])
        target.setdefault('current', row['current'])
        actions = target.setdefault('actions', [])
        for action in row['actions']:
            if action not in actions:
                actions.append(action)
        if row['severity'] == 'P0':
            target['severity'] = 'P0'
        else:
            target.setdefault('severity', row['severity'])
        if row['confidence'] == 'low':
            target['confidence'] = 'low'
        else:
            target.setdefault('confidence', row['confidence'])
    return list(grouped.values())


def render_md(result):
    lines = ['# Theme Radar Auto Adjudication', '', f"Generated: {result['generated_at']}", '']
    lines.extend(['## Summary', '', '| 指标 | 数量 |', '|---|---:|'])
    for key, value in result['summary'].items():
        if not isinstance(value, dict):
            lines.append(f'| {key} | {value} |')
    lines.extend(['', '## Actions by field', '', '```json', json.dumps(result['summary']['actions_by_field'], ensure_ascii=False, indent=2), '```'])
    lines.extend(['', '## Adjudicated company-theme pairs', '', '| Theme | Company | Severity | Confidence | Issues | Actions |', '|---|---|---|---|---|---|'])
    for row in result['items'][:120]:
        actions = '; '.join(f"{a['field']}={a['value']}" for a in row['actions'])
        lines.append(f"| {row['theme']} | {row['company']} | {row.get('severity', '')} | {row.get('confidence', '')} | {', '.join(sorted(set(row['issues'])))} | {actions} |")
    return '\n'.join(lines) + '\n'


def main():
    queue = load_json(QUEUE)
    adjudicated = [adjudicate(item) for item in queue.get('items', [])]
    merged = merge_adjudications(adjudicated)
    merged = sorted(merged, key=lambda x: (x.get('severity') != 'P0', x['theme'], x['company']))
    summary = {
        'source_items': len(queue.get('items', [])),
        'company_theme_pairs': len(merged),
        'actions_count': sum(len(x['actions']) for x in merged),
        'actions_by_field': dict(Counter(a['field'] for x in merged for a in x['actions'])),
        'pairs_by_theme': dict(Counter(x['theme'] for x in merged)),
        'low_confidence_pairs': sum(1 for x in merged if x.get('confidence') == 'low'),
    }
    result = {
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'source_queue': str(QUEUE.relative_to(WIKI)),
        'summary': summary,
        'items': merged,
    }
    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    OUT_MD.write_text(render_md(result), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(str(OUT_JSON))
    print(str(OUT_MD))


if __name__ == '__main__':
    main()
