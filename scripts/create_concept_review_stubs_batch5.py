#!/usr/bin/env python3
import json
import re
from datetime import date
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
AUDIT = WIKI / 'raw/theme-radar/missing-wikilinks-audit.json'
OUT = WIKI / 'raw/theme-radar/missing-wikilinks-concept-review-batch5-result.json'
CONCEPTS = WIKI / 'concepts'
LIMIT = 80
SKIP = {'AR/VR', 'VR/AR'}


def safe_filename(value):
    value = str(value).strip()
    value = re.sub(r'[/:*?"<>|\\\n\r\t]+', '_', value)
    return value.strip(' .')


def yaml_list(values):
    return '[' + ', '.join(json.dumps(v, ensure_ascii=False) for v in values) + ']'


def infer_tags(name):
    tags = ['概念', '待补证', 'missing-wikilink-concept-review-batch5']
    for token in ['AI', '芯片', '半导体', '电池', '光伏', '光刻', '材料', '机器人', '算力', '数据', '医疗', '军工', '航空', '航天', '汽车', '能源', '装备', '量子', '储能', '电力', '光缆', '制氢']:
        if token in name and token not in tags:
            tags.append(token)
    return tags


def render_stub(row, page_name):
    today = date.today().isoformat()
    title = row['target']
    log_entry = f"created from concept_candidate_review batch5; count={row.get('count', 0)}; page={page_name}"
    lines = [
        '---',
        f'title: {title}',
        f'tags: {yaml_list(infer_tags(title))}',
        f'created: {today}',
        f'updated: {today}',
        'revision: 1',
        'sources: []',
        f'log: {yaml_list([log_entry])}',
        '---',
        '',
        f'# {title}',
        '',
        '占位概念页：该概念由 concept_candidate_review 批量清理生成，用于修复重复断链和承接题材雷达后续补证。',
        '',
        '## 速览',
        '',
        '| 维度 | 内容 |',
        '|---|---|',
        '| 概念状态 | 待补证 |',
        f'| missing wikilink 频次 | {row.get("count", 0)} |',
        f'| 来源目录分布 | {json.dumps(row.get("source_dirs", {}), ensure_ascii=False)} |',
        '| 当前用途 | 题材雷达聚类 / 暴露识别 / 后续 concept graph 补全 |',
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
    rows = [r for r in data['items'] if r['category'] == 'concept_candidate_review' and r['target'] not in SKIP][:LIMIT]
    existing = {p.stem for sub in ['entities', 'concepts', 'sources'] for p in (WIKI / sub).glob('*.md') if '.bak' not in p.name}
    created = []
    skipped = []
    for row in rows:
        page = safe_filename(row['target'])
        path = CONCEPTS / f'{page}.md'
        if page in existing or path.exists():
            skipped.append({'target': row['target'], 'file': str(path.relative_to(WIKI)), 'reason': 'exists'})
            continue
        path.write_text(render_stub(row, page), encoding='utf-8')
        existing.add(page)
        created.append({'target': row['target'], 'file': str(path.relative_to(WIKI)), 'count': row['count']})
    result = {
        'audit_source': str(AUDIT),
        'limit': LIMIT,
        'input_count': len(rows),
        'created_concepts_count': len(created),
        'skipped_existing_count': len(skipped),
        'created_concepts': created,
        'skipped_existing': skipped,
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
