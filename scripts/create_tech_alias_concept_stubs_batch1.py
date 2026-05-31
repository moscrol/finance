#!/usr/bin/env python3
import json
import re
from datetime import date
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
AUDIT = WIKI / 'raw/theme-radar/missing-wikilinks-audit.json'
OUT = WIKI / 'raw/theme-radar/tech-alias-concept-stubs-batch1-result.json'
TARGETS = [
    'Chiplet', 'AIGC', 'BIPV', 'eVTOL', 'FPSO', 'NPU', 'TOPCon', 'OLED', 'AIoT', 'C919',
    'GaN', 'MCU', 'DTP药房', 'AI软件', 'RV减速器', 'OCS（光电路交换机）', 'AI视觉', 'IGBT',
    'BBU电池备份单元', '高端CCL', 'BCD工艺', '5G基站', '3nm制程', '3D封装', 'CVD技术',
    'SiC', 'MiniLED产业', 'LED封装', '3D视觉', 'TCO玻璃', 'DUV光刻', 'POE胶膜', 'LNG船',
    'BMS电池管理系统', 'HVLP铜箔', 'Pancake光学', '800G光模块', 'CUDA生态', 'TWS耳机',
    'HPHT技术', 'x86架构', '4D毫米波雷达', 'L4级自动驾驶'
]


def safe_filename(value):
    return re.sub(r'[/:*?"<>|\n\r\t]+', '_', str(value)).strip()


def yaml_list(values):
    return '[' + ', '.join(json.dumps(v, ensure_ascii=False) for v in values) + ']'


def infer_tags(name):
    tags = ['概念', '技术词', '待补证', 'missing-wikilink-backfill']
    for token in ['AI', '芯片', '半导体', '电池', '光模块', '雷达', '汽车', '光刻', '封装', '材料']:
        if token in name and token not in tags:
            tags.append(token)
    return tags


def render_stub(row):
    name = row['target']
    today = date.today().isoformat()
    log_entry = f"created as technical missing wikilink concept stub; count={row.get('count', 0)}"
    lines = [
        '---',
        f'title: {name}',
        f'tags: {yaml_list(infer_tags(name))}',
        f'created: {today}',
        f'updated: {today}',
        'revision: 1',
        'sources: []',
        f'log: {yaml_list([log_entry])}',
        '---',
        '',
        f'# {name}',
        '',
        '占位概念页：该技术词由 missing wikilinks alias 队列自动生成，用于修复断链和承接后续定义补全。',
        '',
        '## 速览',
        '',
        '| 维度 | 内容 |',
        '|---|---|',
        '| 概念状态 | 待补证 |',
        f'| missing wikilink 频次 | {row.get("count", 0)} |',
        f'| 来源目录分布 | {json.dumps(row.get("source_dirs", {}), ensure_ascii=False)} |',
        '| 当前用途 | 技术词归一 / 后续 concept graph 补全 |',
        '',
        '## 待补证定义',
        '',
        '- [ ] 补充一句话定义。',
        '- [ ] 判断是否应并入已有上位概念或保留独立概念。',
        '- [ ] 补充至少 1 个 source 或 raw 证据。',
        '',
        '## 首批出现位置',
        '',
    ]
    for ex in row.get('examples', [])[:5]:
        lines.append(f'- `{ex}`')
    lines.extend(['', '## 相关概念', '', '待补充。', '', '## 相关实体', '', '待补充。', ''])
    return '\n'.join(lines)


def main():
    data = json.loads(AUDIT.read_text(encoding='utf-8'))
    by_target = {r['target']: r for r in data['items']}
    created = []
    skipped = []
    missing_from_audit = []
    for target in TARGETS:
        row = by_target.get(target)
        if not row:
            missing_from_audit.append(target)
            continue
        path = WIKI / 'concepts' / f'{safe_filename(target)}.md'
        if path.exists():
            skipped.append({'target': target, 'reason': 'exists', 'file': str(path.relative_to(WIKI))})
            continue
        path.write_text(render_stub(row), encoding='utf-8')
        created.append({'target': target, 'count': row.get('count'), 'category': row.get('category'), 'file': str(path.relative_to(WIKI))})
    result = {'target_count': len(TARGETS), 'created_count': len(created), 'skipped_count': len(skipped), 'missing_from_audit': missing_from_audit, 'created': created, 'skipped': skipped}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
