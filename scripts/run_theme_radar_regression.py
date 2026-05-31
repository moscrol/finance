#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

PROJECT = Path('/Users/lbq/Desktop/c c/金融')
WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
RADAR = PROJECT / 'skills/theme-radar/scripts/radar.py'
OUT_DIR = WIKI / 'raw/theme-radar/regression'
DEFAULT_THEMES = ('先进封装', '商业航天', '固态电池', '人形机器人')


def run_radar(theme: str) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f'{theme}-theme-radar-regression.md'
    subprocess.run(
        ['python3', str(RADAR), '--term', theme, '--out', str(out)],
        cwd=str(PROJECT),
        check=True,
        text=True,
        capture_output=True,
    )
    return out


def parse_int(value: str) -> int | None:
    value = str(value or '').strip()
    if not value:
        return None
    match = re.search(r'-?\d+', value)
    return int(match.group(0)) if match else None


def parse_report(path: Path) -> dict:
    text = path.read_text(encoding='utf-8')
    row = {'report': str(path.relative_to(WIKI))}
    metric_map = {
        '公司总数': 'companies',
        'baseline 支撑公司': 'baseline',
        '高信度研究线索公司': 'curated_research',
        '边际变化支撑公司': 'delta',
        'graph_only only 公司': 'graph_only_only',
        'missing evidence 公司': 'missing_evidence',
        'missing chain_layer 公司': 'missing_chain_layer',
        'chain_layer_conflict 公司': 'chain_layer_conflict',
        'possible_overranked': 'possible_overranked',
        'weak_granularity': 'weak_granularity',
        'review_required': 'review_required',
        'soft_fact_hardness': 'soft_fact_hardness',
        'need_deep_read': 'need_deep_read',
    }
    for label, key in metric_map.items():
        match = re.search(rf'\|\s*{re.escape(label)}\s*\|\s*(-?\d+)\s*\|', text)
        row[key] = int(match.group(1)) if match else None
    score_map = {
        '题材定义': 'definition_score',
        '产业链拆解': 'chain_score',
        'Top 10 公司排序': 'top10_score',
        '证据桶准确性': 'bucket_score',
        '精读候选队列': 'deep_queue_score',
        '结论可用性': 'usability_score',
    }
    for label, key in score_map.items():
        match = re.search(rf'\|\s*{re.escape(label)}\s*\|\s*\d+\s*\|\s*(-?\d+)\s*\|', text)
        row[key] = int(match.group(1)) if match else None
    total_match = re.search(r'\|\s*\*\*总分\*\*\s*\|\s*\*\*100\*\*\s*\|\s*\*\*(-?\d+)\*\*\s*\|\s*\*\*(.*?)\*\*\s*\|', text)
    row['total_score'] = int(total_match.group(1)) if total_match else None
    row['verdict'] = total_match.group(2).strip() if total_match else ''
    return row


def render_md(result: dict) -> str:
    rows = result['rows']
    lines = ['# Theme Radar Regression Matrix', '', f"Generated: {result['generated_at']}", '']
    lines.extend([
        '| Theme | Score | Verdict | Top10 | Bucket | Companies | Baseline | Curated | Delta | GraphOnlyOnly | Weak | Conflict | Review | SoftFact | Deep |',
        '|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|',
    ])
    for row in rows:
        lines.append(
            f"| {row['theme']} | {row.get('total_score')} | {row.get('verdict', '')} | {row.get('top10_score')} | {row.get('bucket_score')} | {row.get('companies')} | {row.get('baseline')} | {row.get('curated_research')} | {row.get('delta')} | {row.get('graph_only_only')} | {row.get('weak_granularity')} | {row.get('chain_layer_conflict')} | {row.get('review_required')} | {row.get('soft_fact_hardness')} | {row.get('need_deep_read')} |"
        )
    lines.extend(['', '## Reports', ''])
    for row in rows:
        lines.append(f"- {row['theme']}: `{row['report']}`")
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description='Run Theme Radar regression matrix.')
    parser.add_argument('--themes', nargs='*', default=list(DEFAULT_THEMES))
    args = parser.parse_args()
    rows = []
    for theme in args.themes:
        report = run_radar(theme)
        row = parse_report(report)
        row['theme'] = theme
        rows.append(row)
    result = {
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'themes': args.themes,
        'rows': rows,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUT_DIR / 'theme-radar-regression-matrix.json'
    md_path = OUT_DIR / 'theme-radar-regression-matrix.md'
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    md_path.write_text(render_md(result), encoding='utf-8')
    print(json.dumps({'themes': args.themes, 'json': str(json_path), 'md': str(md_path)}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
