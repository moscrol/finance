#!/usr/bin/env python3
import json
import re
from datetime import date
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
AUDIT = WIKI / 'raw/theme-radar/missing-wikilinks-audit.json'
OUT = WIKI / 'raw/theme-radar/high-freq-target-stubs-batch3-result.json'
LIMIT = 30
ENTITY_TARGETS = {'上海微电子'}


def safe_filename(value):
    return re.sub(r'[/:*?"<>|\n\r\t]+', '_', str(value)).strip()


def yaml_list(values):
    return '[' + ', '.join(json.dumps(v, ensure_ascii=False) for v in values) + ']'


def infer_tags(name, kind):
    tags = ['待补证', 'missing-wikilink-backfill']
    tags.insert(0, '实体' if kind == 'entity' else '概念')
    for token in ['AI', '算力', '芯片', '半导体', '机器人', '电池', '风电', '制造', '材料', '数据', '安全']:
        if token in name and token not in tags:
            tags.append(token)
    return tags


def render_concept(row):
    name = row['target']
    today = date.today().isoformat()
    log_entry = f"created as high-frequency missing wikilink concept stub; count={row.get('count', 0)}"
    lines = [
        '---',
        f'title: {name}',
        f'tags: {yaml_list(infer_tags(name, "concept"))}',
        f'created: {today}',
        f'updated: {today}',
        'revision: 1',
        'sources: []',
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
        f'| 来源目录分布 | {json.dumps(row.get("source_dirs", {}), ensure_ascii=False)} |',
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
    for ex in row.get('examples', [])[:5]:
        lines.append(f'- `{ex}`')
    lines.extend(['', '## 相关概念', '', '待补充。', '', '## 相关实体', '', '待补充。', ''])
    return '\n'.join(lines)


def render_entity(row):
    name = row['target']
    today = date.today().isoformat()
    log_entry = f"created as high-frequency missing wikilink entity stub; count={row.get('count', 0)}"
    lines = [
        '---',
        f'title: {name}',
        f'tags: {yaml_list(infer_tags(name, "entity") + ["非上市公司"])}',
        'entity_type: 非上市公司',
        f'created: {today}',
        f'updated: {today}',
        'revision: 1',
        'sources: []',
        f'log: {yaml_list([log_entry])}',
        '---',
        '',
        f'# {name}',
        '',
        '占位实体页：该实体由 missing wikilinks 高频队列自动生成，用于修复 Obsidian 断链和承接后续实体画像补全。',
        '',
        '## 速览',
        '',
        '| 维度 | 内容 |',
        '|---|---|',
        '| 实体类型 | 待补证 / 非上市公司 |',
        f'| missing wikilink 频次 | {row.get("count", 0)} |',
        '| 当前用途 | 链接归一 / 后续实体画像补全 |',
        '',
        '## 待补证定义',
        '',
        '- [ ] 补充实体基础画像。',
        '- [ ] 补充相关概念、产业链角色和证据来源。',
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
    rows = [r for r in data['items'] if r.get('category') == 'concept_candidate_high_freq'][:LIMIT]
    created = []
    skipped = []
    for row in rows:
        name = row['target']
        kind = 'entity' if name in ENTITY_TARGETS else 'concept'
        base = WIKI / ('entities' if kind == 'entity' else 'concepts')
        path = base / f'{safe_filename(name)}.md'
        if path.exists():
            skipped.append({'target': name, 'kind': kind, 'reason': 'exists', 'file': str(path.relative_to(WIKI))})
            continue
        path.write_text(render_entity(row) if kind == 'entity' else render_concept(row), encoding='utf-8')
        created.append({'target': name, 'kind': kind, 'count': row.get('count'), 'file': str(path.relative_to(WIKI))})
    result = {'limit': LIMIT, 'created_count': len(created), 'skipped_count': len(skipped), 'created': created, 'skipped': skipped}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
