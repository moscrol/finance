#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
EXPOSURES = WIKI / 'relations/entity_exposures.json'
OUT_JSON = WIKI / 'raw/theme-radar/theme-radar-fact-hardness-backfill-candidates.json'
OUT_MD = WIKI / 'raw/theme-radar/theme-radar-fact-hardness-backfill-candidates.md'
DEFAULT_THEMES = {'先进封装', '商业航天', '固态电池', '人形机器人'}


def load_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def infer_fact_hardness(exp: dict) -> tuple[str, str]:
    if exp.get('fact_hardness'):
        return '', ''
    update_type = str(exp.get('update_type') or '').strip()
    evidence_layer = str(exp.get('evidence_layer') or '').strip()
    sources = ' '.join(str(x) for x in exp.get('sources', []) or [])
    evidence = str(exp.get('evidence') or '')
    blob = ' '.join([update_type, evidence_layer, sources, evidence])
    if update_type == 'baseline' or 'iFinD baseline' in sources or 'AkShare baseline' in sources or 'Baseline' in sources:
        return 'baseline', 'baseline update_type/source'
    if evidence_layer == 'L1_L3_candidate' or update_type == 'review_candidate':
        return 'review_candidate', 'review_candidate evidence layer/update_type'
    if update_type == 'graph_only' or '从既有entity markdown重建' in blob or '从既有concept markdown重建' in blob:
        return 'legacy_rebuilt', 'graph_only or rebuilt markdown evidence'
    if update_type == 'delta':
        return 'market_narrative', 'delta signal without hard source'
    return '', ''


def collect_candidates(data: dict, themes: set[str]) -> list[dict]:
    rows = []
    for company, ent in (data.get('entities') or {}).items():
        for theme, exp in (ent.get('concepts') or {}).items():
            if themes and theme not in themes:
                continue
            value, reason = infer_fact_hardness(exp or {})
            if not value:
                continue
            rows.append({
                'theme': theme,
                'company': company,
                'code': (ent.get('codes') or [''])[0] if isinstance(ent.get('codes'), list) else '',
                'fact_hardness': value,
                'reason': reason,
                'update_type': exp.get('update_type', ''),
                'evidence_layer': exp.get('evidence_layer', ''),
                'role': exp.get('role', ''),
                'strength': exp.get('strength', ''),
            })
    return sorted(rows, key=lambda x: (x['theme'], x['fact_hardness'], x['company']))


def render_md(result: dict) -> str:
    lines = ['# Theme Radar Fact Hardness Backfill Candidates', '', f"Generated: {result['timestamp']}", '']
    lines.extend(['## Summary', '', '| 指标 | 数量 |', '|---|---:|'])
    for key, value in result['summary'].items():
        if not isinstance(value, dict):
            lines.append(f'| {key} | {value} |')
    lines.extend(['', '## By hardness', '', '```json', json.dumps(result['summary']['by_hardness'], ensure_ascii=False, indent=2), '```'])
    lines.extend(['', '## Candidates', '', '| Theme | Company | Strength | Update | Layer | Suggested hardness | Reason | Role |', '|---|---|---|---|---|---|---|---|'])
    for row in result['candidates'][:200]:
        lines.append(f"| {row['theme']} | {row['company']} | {row['strength']} | {row['update_type']} | {row['evidence_layer']} | {row['fact_hardness']} | {row['reason']} | {row['role']} |")
    return '\n'.join(lines) + '\n'


def backup(path: Path) -> str:
    target = Path(str(path) + '.bak-fact-hardness-' + datetime.now().strftime('%Y%m%d%H%M%S'))
    shutil.copy2(path, target)
    return str(target.relative_to(WIKI))


def apply_candidates(data: dict, candidates: list[dict]) -> int:
    changed = 0
    for row in candidates:
        exp = (((data.get('entities') or {}).get(row['company']) or {}).get('concepts') or {}).get(row['theme'])
        if not exp or exp.get('fact_hardness'):
            continue
        exp['fact_hardness'] = row['fact_hardness']
        changed += 1
    return changed


def main():
    parser = argparse.ArgumentParser(description='Build/apply fact_hardness backfill candidates for Theme Radar themes.')
    parser.add_argument('--themes', nargs='*', default=sorted(DEFAULT_THEMES))
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    data = load_json(EXPOSURES)
    candidates = collect_candidates(data, set(args.themes))
    backups = []
    applied = 0
    if args.apply and candidates:
        backups.append(backup(EXPOSURES))
        applied = apply_candidates(data, candidates)
        data['updated'] = datetime.now().date().isoformat()
        write_json(EXPOSURES, data)
    summary = {
        'mode': 'apply' if args.apply else 'dry_run',
        'themes_count': len(args.themes),
        'candidate_count': len(candidates),
        'applied_count': applied,
        'by_theme': dict(Counter(row['theme'] for row in candidates)),
        'by_hardness': dict(Counter(row['fact_hardness'] for row in candidates)),
    }
    result = {
        'timestamp': datetime.now().isoformat(timespec='seconds'),
        'themes': args.themes,
        'target': str(EXPOSURES.relative_to(WIKI)),
        'backups': backups,
        'summary': summary,
        'candidates': candidates,
    }
    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    OUT_MD.write_text(render_md(result), encoding='utf-8')
    print(json.dumps({**summary, 'json': str(OUT_JSON), 'md': str(OUT_MD), 'backups': backups}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
