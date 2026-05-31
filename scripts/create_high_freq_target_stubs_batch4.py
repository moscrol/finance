#!/usr/bin/env python3
import json
import re
from datetime import date
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
AUDIT = WIKI / 'raw/theme-radar/missing-wikilinks-audit.json'
OUT = WIKI / 'raw/theme-radar/high-freq-target-stubs-batch4-result.json'
LIMIT = 30
SKIP_TARGETS = {'硅'}
ENTITY_TARGETS = set()


def safe_filename(value):
    return re.sub(r'[/:*?"<>|\n\r\t]+', '_', str(value)).strip()


def yaml_list(values):
    return '[' + ', '.join(json.dumps(v, ensure_ascii=False) for v in values) + ']'


def infer_tags(name, kind):
    tags = ['实体' if kind == 'entity' else '概念', '待补证', 'missing-wikilink-backfill']
    for token in ['AI', '算力', '芯片', '半导体', '机器人', '电池', '风电', '制造', '材料', '数据', '安全']:
        if token in name and token not in tags:
            tags.append(token)
    return tags


def render_stub(row, kind):
    name = row['target']
    today = date.today().isoformat()
    log_entry = f"created as high-frequency missing wikilink {kind} stub; count={row.get('count', 0)}"
    if kind == 'entity':
        front_extra = ['entity_type: 待补证']
        lead = '占位实体页：该实体由 missing wikilinks 高频队列自动生成，用于修复 Obsidian 断链和承接后续实体画像补全。'
        status_row = '| 实体状态 | 待补证 |'
        todo = ['- [ ] 补充实体基础画像。', '- [ ] 补充相关概念、产业链角色和证据来源。']
        folder = 'entities'
    else:
        front_extra = []
        lead = '占位概念页：该概念由 missing wikilinks 高频队列自动生成，用于修复 Obsidian 断链和承接后续主题研究。'
        status_row = '| 概念状态 | 待补证 |'
        todo = ['- [ ] 补充一句话定义。', '- [ ] 补充产业链位置、上下游和相关实体。', '- [ ] 补充至少 1 个 source 或 raw 证据。']
        folder = 'concepts'
    lines = ['---', f'title: {name}', f'tags: {yaml_list(infer_tags(name, kind))}', *front_extra, f'created: {today}', f'updated: {today}', 'revision: 1', 'sources: []', f'log: {yaml_list([log_entry])}', '---', '', f'# {name}', '', lead, '', '## 速览', '', '| 维度 | 内容 |', '|---|---|', status_row, f'| missing wikilink 频次 | {row.get("count", 0)} |', f'| 来源目录分布 | {json.dumps(row.get("source_dirs", {}), ensure_ascii=False)} |', '| 当前用途 | 链接归一 / 后续补全 |', '', '## 待补证定义', '', *todo, '', '## 首批出现位置', '']
    for ex in row.get('examples', [])[:5]:
        lines.append(f'- `{ex}`')
    lines.extend(['', '## 相关概念', '', '待补充。', '', '## 相关实体', '', '待补充。', ''])
    return folder, '\n'.join(lines)


def main():
    data = json.loads(AUDIT.read_text(encoding='utf-8'))
    candidates = [r for r in data['items'] if r.get('category') == 'concept_candidate_high_freq' and r.get('target') not in SKIP_TARGETS]
    rows = candidates[:LIMIT]
    created = []
    skipped = []
    for row in rows:
        name = row['target']
        kind = 'entity' if name in ENTITY_TARGETS else 'concept'
        folder, content = render_stub(row, kind)
        path = WIKI / folder / f'{safe_filename(name)}.md'
        if path.exists():
            skipped.append({'target': name, 'kind': kind, 'reason': 'exists', 'file': str(path.relative_to(WIKI))})
            continue
        path.write_text(content, encoding='utf-8')
        created.append({'target': name, 'kind': kind, 'count': row.get('count'), 'file': str(path.relative_to(WIKI))})
    result = {'limit': LIMIT, 'skipped_targets': sorted(SKIP_TARGETS), 'created_count': len(created), 'skipped_count': len(skipped), 'created': created, 'skipped': skipped}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
