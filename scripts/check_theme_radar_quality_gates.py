#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

PROJECT = Path('/Users/lbq/Desktop/c c/金融')
WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
OUT_DIR = WIKI / 'raw/theme-radar/regression'
AUDIT_JSON = WIKI / 'raw/theme-radar/theme-radar-quality-queue.json'
RESULT_JSON = WIKI / 'raw/theme-radar/theme-radar-quality-gates.json'
RESULT_MD = WIKI / 'raw/theme-radar/theme-radar-quality-gates.md'
THEMES = ['先进封装', '商业航天', '固态电池', '人形机器人']
MIN_SCORE = 50


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, cwd=str(PROJECT), check=True, text=True)


def load_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def render_md(result: dict) -> str:
    lines = ['# Theme Radar Quality Gates', '', f"Generated: {result['generated_at']}", '']
    lines.extend(['## Verdict', '', f"- Status: **{result['status']}**", f"- Failures: {len(result['failures'])}", f"- Warnings: {len(result.get('warnings', []))}", ''])
    lines.extend(['## Regression Matrix', '', '| Theme | Score | Verdict | Conflict | Overranked | SoftFact | GraphOnlyOnly |', '|---|---:|---|---:|---:|---:|---:|'])
    for row in result['regression_rows']:
        lines.append(f"| {row['theme']} | {row.get('total_score')} | {row.get('verdict', '')} | {row.get('chain_layer_conflict')} | {row.get('possible_overranked')} | {row.get('soft_fact_hardness')} | {row.get('graph_only_only')} |")
    lines.extend(['', '## Audit Summary', '', '```json', json.dumps(result['audit_summary'], ensure_ascii=False, indent=2), '```', ''])
    if result['failures']:
        lines.extend(['## Failures', '', '| Type | Theme | Detail |', '|---|---|---|'])
        for item in result['failures']:
            lines.append(f"| {item['type']} | {item.get('theme', '')} | {item['detail']} |")
        lines.append('')
    if result.get('warnings'):
        lines.extend(['## Warnings', '', '| Type | Theme | Detail |', '|---|---|---|'])
        for item in result['warnings']:
            lines.append(f"| {item['type']} | {item.get('theme', '')} | {item['detail']} |")
        lines.append('')
    return '\n'.join(lines) + '\n'


def main() -> int:
    run(['python3', 'scripts/audit_theme_radar_quality_queue.py', '--themes', *THEMES])
    run(['python3', 'scripts/run_theme_radar_regression.py', '--themes', *THEMES])

    audit = load_json(AUDIT_JSON)
    matrix = load_json(OUT_DIR / 'theme-radar-regression-matrix.json')
    rows = matrix.get('rows', [])
    failures = []
    warnings = []

    severity_counts = Counter(item.get('severity') for item in audit.get('items', []))
    if severity_counts.get('P0'):
        failures.append({'type': 'audit_p0', 'detail': f"P0 issues={severity_counts.get('P0')}"})

    for row in rows:
        theme = row.get('theme', '')
        if row.get('chain_layer_conflict', 0):
            failures.append({'type': 'chain_layer_conflict', 'theme': theme, 'detail': f"chain_layer_conflict={row.get('chain_layer_conflict')}"})
        if row.get('possible_overranked', 0):
            warnings.append({'type': 'possible_overranked', 'theme': theme, 'detail': f"possible_overranked={row.get('possible_overranked')}"})
        if row.get('soft_fact_hardness', 0) and row.get('total_score', 0) < MIN_SCORE:
            failures.append({'type': 'soft_fact_low_score', 'theme': theme, 'detail': f"soft_fact_hardness={row.get('soft_fact_hardness')}, score={row.get('total_score')}"})
        if row.get('total_score') is None or row.get('total_score', 0) < MIN_SCORE:
            failures.append({'type': 'low_score', 'theme': theme, 'detail': f"score={row.get('total_score')} < {MIN_SCORE}"})
        if '暂不可用' in str(row.get('verdict', '')):
            failures.append({'type': 'unusable_verdict', 'theme': theme, 'detail': row.get('verdict', '')})

    result = {
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'themes': THEMES,
        'status': 'PASS' if not failures else 'FAIL',
        'failures': failures,
        'warnings': warnings,
        'audit_summary': audit.get('summary', {}),
        'regression_rows': rows,
    }
    RESULT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    RESULT_MD.write_text(render_md(result), encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k not in {'regression_rows'}}, ensure_ascii=False, indent=2))
    print(str(RESULT_JSON))
    print(str(RESULT_MD))
    return 0 if not failures else 1


if __name__ == '__main__':
    raise SystemExit(main())
