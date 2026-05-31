#!/usr/bin/env python3
import json
import re
import argparse
from datetime import date
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
CONCEPTS = WIKI / 'concepts'
AUDIT = WIKI / 'raw/theme-radar/missing-wikilinks-audit.json'
LIMIT = 30


def safe_filename(value):
    return re.sub(r'[/:*?"<>|\n\r\t]+', '_', str(value)).strip()


def yaml_list(values):
    return '[' + ', '.join(json.dumps(v, ensure_ascii=False) for v in values) + ']'


def infer_tags(name):
    tags = ['概念', '待补证', 'missing-wikilink-backfill']
    for token in ['AI', '算力', '芯片', '半导体', '机器人', '电池', '风电', '核电', '军工', '卫星', '制造', '材料', '数据']:
        if token in name and token not in tags:
            tags.append(token)
    return tags


def render_stub(row):
    name = row['target']
    today = date.today().isoformat()
    examples = row.get('examples', [])[:5]
    source_dirs = row.get('source_dirs', {})
    log_entry = f"created as high-frequency missing wikilink concept stub; count={row.get('count', 0)}"
    lines = [
        '---',
        f'title: {name}',
        f'tags: {yaml_list(infer_tags(name))}',
        f'created: {today}',
        f'updated: {today}',
        'revision: 1',
        f'sources: {yaml_list([])}',
        f'log: {yaml_list([log_entry])}',
        '---',
        '',
        f'# {name}',
        '',
        '占位概念页：该概念由 missing wikilinks 高频队列自动生成，用于修复 Obsidian 断链和承接后续主题研究。',
        '',
        '## 速览',
        '',
        '| 维度 | 内容 |',
        '|---|---|',
        '| 概念状态 | 待补证 |',
        f'| missing wikilink 频次 | {row.get("count", 0)} |',
        f'| 来源目录分布 | {json.dumps(source_dirs, ensure_ascii=False)} |',
        '| 当前用途 | 链接归一 / 后续 concept graph 补全 |',
        '',
        '## 待补证定义',
        '',
        '- [ ] 补充一句话定义。',
        '- [ ] 补充产业链位置、上下游和相关实体。',
        '- [ ] 补充至少 1 个 source 或 raw 证据。',
        '',
        '## 首批出现位置',
        '',
    ]
    for ex in examples:
        lines.append(f'- `{ex}`')
    lines.extend(['', '## 相关概念', '', '待补充。', '', '## 相关实体', '', '待补充。', ''])
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch-name', default='batch1')
    parser.add_argument('--limit', type=int, default=LIMIT)
    args = parser.parse_args()
    out = WIKI / f'raw/theme-radar/high-freq-concept-stubs-{args.batch_name}-result.json'
    data = json.loads(AUDIT.read_text(encoding='utf-8'))
    rows = [r for r in data['items'] if r.get('category') == 'concept_candidate_high_freq'][:args.limit]
    created = []
    skipped = []
    CONCEPTS.mkdir(parents=True, exist_ok=True)
    for row in rows:
        name = row['target']
        path = CONCEPTS / f'{safe_filename(name)}.md'
        if path.exists():
            skipped.append({'target': name, 'reason': 'exists', 'file': str(path.relative_to(WIKI))})
            continue
        path.write_text(render_stub(row), encoding='utf-8')
        created.append({'target': name, 'count': row.get('count'), 'file': str(path.relative_to(WIKI))})
    result = {'batch_name': args.batch_name, 'limit': args.limit, 'created_count': len(created), 'skipped_count': len(skipped), 'created': created, 'skipped': skipped}
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
