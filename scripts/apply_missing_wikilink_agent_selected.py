#!/usr/bin/env python3
import json
import re
import shutil
from datetime import date
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
DECISIONS = WIKI / 'raw/theme-radar/missing-wikilinks-manual-decision-agent-selected.json'
OUT = WIKI / 'raw/theme-radar/missing-wikilinks-agent-selected-apply-result.json'
CONCEPTS = WIKI / 'concepts'
ENTITIES = WIKI / 'entities'


def safe_filename(value):
    return re.sub(r'[/:*?"<>|\n\r\t]+', '_', str(value)).strip()


def yaml_list(values):
    return '[' + ', '.join(json.dumps(v, ensure_ascii=False) for v in values) + ']'


def infer_concept_tags(name):
    tags = ['概念', '待补证', 'missing-wikilink-agent-selected']
    for token in ['AI', '芯片', '半导体', '电池', '光伏', '光刻', '材料', '机器人', '算力', '数据', '医疗', '军工', '航空', '航天', '汽车']:
        if token in name and token not in tags:
            tags.append(token)
    return tags


def render_concept_stub(row, page_name):
    today = date.today().isoformat()
    title = row['target']
    log_entry = f"created from agent-selected missing wikilink decision; count={row.get('count', 0)}; page={page_name}"
    lines = [
        '---',
        f'title: {title}',
        f'tags: {yaml_list(infer_concept_tags(title))}',
        f'created: {today}',
        f'updated: {today}',
        'revision: 1',
        'sources: []',
        f'log: {yaml_list([log_entry])}',
        '---',
        '',
        f'# {title}',
        '',
        '占位概念页：该概念由 missing wikilinks agent-selected 决策生成，用于修复断链和承接题材雷达后续补证。',
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


def render_entity_stub(row, page_name):
    today = date.today().isoformat()
    title = row['target']
    log_entry = f"created from agent-selected missing wikilink entity decision; count={row.get('count', 0)}; page={page_name}"
    lines = [
        '---',
        f'title: {title}',
        'aliases: []',
        f'tags: {yaml_list(["实体", "待补证", "missing-wikilink-agent-selected"])}',
        'entity_type: 待核实',
        'tickers: []',
        'markets: []',
        f'created: {today}',
        f'updated: {today}',
        'revision: 1',
        'sources: []',
        'raw_sources: []',
        f'log: {yaml_list([log_entry])}',
        '---',
        '',
        f'# {title}',
        '',
        '占位实体页：该实体由 missing wikilinks agent-selected 决策生成，用于修复断链和承接后续基础画像补证。',
        '',
        '## 速览',
        '',
        '| 维度 | 内容 |',
        '|---|---|',
        '| 实体状态 | 待补证 |',
        f'| missing wikilink 频次 | {row.get("count", 0)} |',
        f'| 来源目录分布 | {json.dumps(row.get("source_dirs", {}), ensure_ascii=False)} |',
        '',
        '## 待补证问题',
        '',
        '- [ ] 补充主体类型、主营业务或项目属性。',
        '- [ ] 补充至少 1 个 source 或 raw 证据。',
        '',
        '## 首批出现位置',
        '',
    ]
    for ex in row.get('examples', [])[:5]:
        lines.append(f'- `{ex}`')
    lines.extend(['', '## 相关概念', '', '待补充。', '', '## 相关实体', '', '待补充。', ''])
    return '\n'.join(lines)


def iter_md_files():
    for sub in ['entities', 'concepts', 'sources']:
        for path in sorted((WIKI / sub).glob('*.md')):
            if '.bak' not in path.name:
                yield path


def backup(path):
    b = path.with_suffix(path.suffix + '.bak-agent-selected-batch1')
    if not b.exists():
        b.write_text(path.read_text(encoding='utf-8'), encoding='utf-8')


def archive_backups():
    moved = []
    specs = [('entities', 'entity-backups'), ('concepts', 'concept-backups'), ('sources', 'source-backups')]
    for sub, archive_name in specs:
        archive = WIKI / 'archive' / archive_name
        archive.mkdir(parents=True, exist_ok=True)
        for path in sorted((WIKI / sub).glob('*.bak-agent-selected-batch1')):
            dest = archive / path.name
            if dest.exists():
                i = 1
                while (archive / f'{path.name}.{i}').exists():
                    i += 1
                dest = archive / f'{path.name}.{i}'
            shutil.move(str(path), str(dest))
            moved.append(str(dest.relative_to(WIKI)))
    return moved


def apply_link_edits(alias_mapping, noise_targets):
    changed_files = []
    replacement_counts = {}
    noise_counts = {}
    def replace_links(text):
        def repl(match):
            inner = match.group(1)
            if '|' in inner:
                target, display = inner.split('|', 1)
                suffix = '|' + display
            else:
                target, suffix = inner, ''
            if '#' in target:
                base, anchor = target.split('#', 1)
                anchor = '#' + anchor
            else:
                base, anchor = target, ''
            base = base.strip()
            if base in noise_targets:
                noise_counts[base] = noise_counts.get(base, 0) + 1
                return display if suffix else base
            if base in alias_mapping:
                page = alias_mapping[base]
                replacement_counts[base] = replacement_counts.get(base, 0) + 1
                if suffix:
                    return f'[[{page}{anchor}{suffix}]]'
                if page == base:
                    return match.group(0)
                return f'[[{page}{anchor}|{base}]]'
            return match.group(0)
        return re.sub(r'\[\[([^\]\n]+)\]\]', repl, text)
    for path in iter_md_files():
        text = path.read_text(encoding='utf-8')
        new_text = replace_links(text)
        if new_text == text:
            continue
        backup(path)
        path.write_text(new_text, encoding='utf-8')
        changed_files.append(str(path.relative_to(WIKI)))
    return changed_files, replacement_counts, noise_counts


def main():
    data = json.loads(DECISIONS.read_text(encoding='utf-8'))
    existing = {p.stem for sub in ['entities', 'concepts', 'sources'] for p in (WIKI / sub).glob('*.md') if '.bak' not in p.name}
    created_concepts = []
    created_entities = []
    skipped_existing = []
    alias_mapping = {}
    noise_targets = set()
    source_or_report = []
    CONCEPTS.mkdir(parents=True, exist_ok=True)
    ENTITIES.mkdir(parents=True, exist_ok=True)
    for row in data['rows']:
        decision = row.get('decision')
        target = row['target']
        final_target = row.get('final_target_page') or target
        if decision == 'create_concept':
            page_name = safe_filename(final_target)
            path = CONCEPTS / f'{page_name}.md'
            if path.exists() or page_name in existing:
                skipped_existing.append({'target': target, 'decision': decision, 'file': f'concepts/{page_name}.md', 'reason': 'exists'})
            else:
                path.write_text(render_concept_stub(row, page_name), encoding='utf-8')
                created_concepts.append({'target': target, 'page': page_name, 'file': str(path.relative_to(WIKI)), 'count': row.get('count')})
                existing.add(page_name)
            if page_name != target:
                alias_mapping[target] = page_name
        elif decision == 'create_entity':
            page_name = safe_filename(final_target)
            path = ENTITIES / f'{page_name}.md'
            if path.exists() or page_name in existing:
                skipped_existing.append({'target': target, 'decision': decision, 'file': f'entities/{page_name}.md', 'reason': 'exists'})
            else:
                path.write_text(render_entity_stub(row, page_name), encoding='utf-8')
                created_entities.append({'target': target, 'page': page_name, 'file': str(path.relative_to(WIKI)), 'count': row.get('count')})
                existing.add(page_name)
            if page_name != target:
                alias_mapping[target] = page_name
        elif decision == 'alias_to_existing':
            page_name = safe_filename(final_target)
            alias_mapping[target] = page_name
        elif decision == 'noise_delete_link':
            noise_targets.add(target)
        elif decision == 'source_or_report':
            source_or_report.append({'target': target, 'count': row.get('count'), 'examples': row.get('examples', [])[:5], 'notes': row.get('notes', '')})
    changed_files, replacement_counts, noise_counts = apply_link_edits(alias_mapping, noise_targets)
    archived = archive_backups()
    result = {
        'decision_source': str(DECISIONS),
        'created_concepts_count': len(created_concepts),
        'created_entities_count': len(created_entities),
        'skipped_existing_count': len(skipped_existing),
        'alias_mapping_count': len(alias_mapping),
        'noise_target_count': len(noise_targets),
        'changed_file_count': len(changed_files),
        'total_alias_replacements': sum(replacement_counts.values()),
        'total_noise_unlinks': sum(noise_counts.values()),
        'archived_backup_count': len(archived),
        'source_or_report_count': len(source_or_report),
        'created_concepts': created_concepts,
        'created_entities': created_entities,
        'skipped_existing': skipped_existing,
        'alias_mapping': alias_mapping,
        'replacement_counts': replacement_counts,
        'noise_counts': noise_counts,
        'changed_files': changed_files,
        'source_or_report': source_or_report,
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
