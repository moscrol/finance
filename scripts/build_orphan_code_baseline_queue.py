#!/usr/bin/env python3
import json
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
IN_JSON = WIKI / 'raw/theme-radar/entity-exposure-orphan-code-audit.json'
OUT_JSON = WIKI / 'raw/theme-radar/orphan-code-baseline-queue.json'
OUT_MD = WIKI / 'raw/theme-radar/orphan-code-baseline-queue.md'


def load_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def queue_row(row, priority, action, reason):
    return {
        'priority': priority,
        'action': action,
        'entity': row['entity'],
        'codes': row.get('codes', []),
        'concept_count': row.get('concept_count', 0),
        'strong_edge_count': row.get('strong_edge_count', 0),
        'weak_edge_count': row.get('weak_edge_count', 0),
        'sample_concepts': row.get('sample_concepts', []),
        'reason': reason,
        'baseline_status': 'pending',
        'notes': '',
    }


def build_queue():
    audit = load_json(IN_JSON)
    p1 = []
    p2 = []
    manual = []
    quarantine = []

    for row in audit['queues']['create_entity_stub_candidates']:
        p1.append(queue_row(
            row,
            'P1',
            'baseline_then_optional_entity_stub',
            'orphan code with >=3 weak concept exposures; do not upgrade exposure before baseline evidence',
        ))

    for row in audit['queues']['low_value_quarantine_candidates']:
        q = queue_row(
            row,
            'P2',
            'baseline_later_or_quarantine',
            'low frequency weak exposure; keep out of immediate entity creation unless baseline confirms relevance',
        )
        if row.get('concept_count', 0) >= 2:
            p2.append(q)
        else:
            q['priority'] = 'P3'
            quarantine.append(q)

    for row in audit['queues']['fuzzy_name_exists_review']:
        item = queue_row(
            row,
            'MANUAL',
            'manual_review_no_auto_merge',
            'fuzzy entity-name match may be false positive; do not merge automatically',
        )
        item['fuzzy_candidates'] = row.get('fuzzy_candidates', [])
        manual.append(item)

    items = p1 + p2 + manual + quarantine
    return {
        'summary': {
            'total': len(items),
            'P1_baseline_priority_count': len(p1),
            'P2_baseline_later_count': len(p2),
            'manual_review_count': len(manual),
            'P3_quarantine_count': len(quarantine),
        },
        'queues': {
            'P1_baseline_priority': p1,
            'P2_baseline_later': p2,
            'manual_review_no_auto_merge': manual,
            'P3_quarantine': quarantine,
        },
        'items': items,
    }


def render_md(data):
    lines = ['# Orphan Code Baseline Queue', '', '## Summary', '', '| 队列 | 数量 |', '|---|---:|']
    for k, v in data['summary'].items():
        lines.append(f'| {k} | {v} |')
    for key, title in [
        ('P1_baseline_priority', 'P1 baseline priority'),
        ('P2_baseline_later', 'P2 baseline later'),
        ('manual_review_no_auto_merge', 'Manual review no auto merge'),
        ('P3_quarantine', 'P3 quarantine'),
    ]:
        lines.extend(['', f'## {title}', '', '| Entity | Codes | Concepts | Strong | Weak | Action | Sample concepts |', '|---|---|---:|---:|---:|---|---|'])
        for r in data['queues'][key]:
            lines.append(f"| {r['entity']} | {','.join(r['codes'])} | {r['concept_count']} | {r['strong_edge_count']} | {r['weak_edge_count']} | {r['action']} | {'、'.join(r.get('sample_concepts', [])[:5])} |")
    lines.extend(['', '## Usage', '', '- **P1**：优先进入 baseline 批处理；baseline 确认后再决定是否创建实体页。', '- **P2**：低频但不止一个弱暴露，后续批量 baseline。', '- **MANUAL**：名称模糊，不允许自动合并。', '- **P3**：单一弱暴露，暂不建实体，保留 quarantine。'])
    return '\n'.join(lines) + '\n'


def main():
    data = build_queue()
    OUT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    OUT_MD.write_text(render_md(data), encoding='utf-8')
    print(json.dumps(data['summary'], ensure_ascii=False, indent=2))
    print(str(OUT_JSON))
    print(str(OUT_MD))


if __name__ == '__main__':
    main()
