#!/usr/bin/env python3
import json
import re
import shutil
from datetime import date
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
AUDIT = WIKI / 'raw/theme-radar/missing-wikilinks-audit.json'
OUT = WIKI / 'raw/theme-radar/missing-wikilinks-alias-candidate-batch1-result.json'
CONCEPTS = WIKI / 'concepts'
ENTITIES = WIKI / 'entities'

SOURCE_OR_REPORT = {'某PCB电话会议晨报', '3D打印的第一性原理分析'}
NOISE = {'A股投资'}
ENTITY = {'华为Flex:ai'}
ALIAS_TO_EXISTING = {
    'AI+医疗': 'AI医疗',
    'AI+金融': 'AI金融',
    '固态变压器SST': 'SST',
    '氮化镓(GaN)': 'GaN',
}


def safe_filename(value):
    value = str(value).strip()
    value = re.sub(r'[/:*?"<>|\\\n\r\t]+', '_', value)
    return value.strip(' .')


def yaml_list(values):
    return '[' + ', '.join(json.dumps(v, ensure_ascii=False) for v in values) + ']'


def infer_tags(name):
    tags = ['概念', '待补证', 'missing-wikilink-alias-candidate']
    for token in ['AI', 'GPU', 'OLED', 'PCB', 'PET', 'PI', 'PP', 'LNG', 'IGBT', '5G', '6G', '800G', '1.6T', '芯片', '半导体', '光模块', '材料', '光学', '架构', '算法', '制程', '铜箔', '折叠屏']:
        if token in name and token not in tags:
            tags.append(token)
    return tags


def render_concept(row, page_name):
    today = date.today().isoformat()
    title = row['target']
    log_entry = f"created from alias_candidate cleanup; count={row.get('count', 0)}; page={page_name}"
    lines = [
        '---', f'title: {title}', f'tags: {yaml_list(infer_tags(title))}', f'created: {today}', f'updated: {today}',
        'revision: 1', 'sources: []', f'log: {yaml_list([log_entry])}', '---', '', f'# {title}', '',
        '占位概念页：该概念由 alias_candidate missing wikilinks 清理生成，用于修复断链和承接题材雷达后续补证。', '',
        '## 速览', '', '| 维度 | 内容 |', '|---|---|', '| 概念状态 | 待补证 |',
        f'| missing wikilink 频次 | {row.get("count", 0)} |', f'| 来源目录分布 | {json.dumps(row.get("source_dirs", {}), ensure_ascii=False)} |',
        '| 当前用途 | 题材雷达聚类 / 暴露识别 / 后续 concept graph 补全 |', '', '## 待补证定义', '',
        '- [ ] 补充一句话定义。', '- [ ] 判断是否应并入已有上位概念或保留独立概念。', '- [ ] 补充至少 1 个 source 或 raw 证据。', '',
        '## 首批出现位置', '',
    ]
    for ex in row.get('examples', [])[:5]:
        lines.append(f'- `{ex}`')
    lines.extend(['', '## 相关概念', '', '待补充。', '', '## 相关实体', '', '待补充。', ''])
    return '\n'.join(lines)


def render_entity(row, page_name):
    today = date.today().isoformat()
    title = row['target']
    log_entry = f"created from alias_candidate entity cleanup; count={row.get('count', 0)}; page={page_name}"
    lines = [
        '---', f'title: {title}', 'aliases: []', f'tags: {yaml_list(["实体", "待补证", "missing-wikilink-alias-candidate"])}',
        'entity_type: 待核实', 'tickers: []', 'markets: []', f'created: {today}', f'updated: {today}', 'revision: 1',
        'sources: []', 'raw_sources: []', f'log: {yaml_list([log_entry])}', '---', '', f'# {title}', '',
        '占位实体页：该实体由 alias_candidate missing wikilinks 清理生成，用于修复断链和承接后续补证。', '',
        '## 速览', '', '| 维度 | 内容 |', '|---|---|', '| 实体状态 | 待补证 |', f'| missing wikilink 频次 | {row.get("count", 0)} |', '',
        '## 待补证问题', '', '- [ ] 补充主体类型、主营业务或项目属性。', '- [ ] 补充至少 1 个 source 或 raw 证据。', '',
        '## 首批出现位置', '',
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
    bak = path.with_suffix(path.suffix + '.bak-alias-candidate-batch1')
    if not bak.exists():
        bak.write_text(path.read_text(encoding='utf-8'), encoding='utf-8')


def archive_backups():
    moved = []
    for sub, archive_name in [('entities', 'entity-backups'), ('concepts', 'concept-backups'), ('sources', 'source-backups')]:
        archive = WIKI / 'archive' / archive_name
        archive.mkdir(parents=True, exist_ok=True)
        for path in sorted((WIKI / sub).glob('*.bak-alias-candidate-batch1')):
            dest = archive / path.name
            i = 1
            while dest.exists():
                dest = archive / f'{path.name}.{i}'
                i += 1
            shutil.move(str(path), str(dest))
            moved.append(str(dest.relative_to(WIKI)))
    return moved


def apply_edits(alias_map, unlink_targets):
    changed = []
    alias_counts = {}
    unlink_counts = {}
    def repl(match):
        inner = match.group(1)
        if '|' in inner:
            raw_target, display = inner.split('|', 1)
        else:
            raw_target, display = inner, None
        if '#' in raw_target:
            base, anchor = raw_target.split('#', 1)
            anchor = '#' + anchor
        else:
            base, anchor = raw_target, ''
        base = base.strip()
        if base in unlink_targets:
            unlink_counts[base] = unlink_counts.get(base, 0) + 1
            return display if display is not None else base
        if base in alias_map:
            page = alias_map[base]
            alias_counts[base] = alias_counts.get(base, 0) + 1
            shown = display if display is not None else base
            if page == base and display is None:
                return match.group(0)
            return f'[[{page}{anchor}|{shown}]]'
        return match.group(0)
    for path in iter_md_files():
        text = path.read_text(encoding='utf-8')
        new = re.sub(r'\[\[([^\]\n]+)\]\]', repl, text)
        if new != text:
            backup(path)
            path.write_text(new, encoding='utf-8')
            changed.append(str(path.relative_to(WIKI)))
    return changed, alias_counts, unlink_counts


def main():
    data = json.loads(AUDIT.read_text(encoding='utf-8'))
    rows = [r for r in data['items'] if r['category'] == 'alias_candidate']
    existing = {p.stem for sub in ['entities', 'concepts', 'sources'] for p in (WIKI / sub).glob('*.md') if '.bak' not in p.name}
    created_concepts = []
    created_entities = []
    skipped_existing = []
    alias_map = dict(ALIAS_TO_EXISTING)
    unlink_targets = set(SOURCE_OR_REPORT) | set(NOISE)
    for row in rows:
        target = row['target']
        if target in unlink_targets or target in alias_map:
            continue
        if target in ENTITY:
            page = safe_filename(target)
            path = ENTITIES / f'{page}.md'
            if page in existing or path.exists():
                skipped_existing.append({'target': target, 'file': str(path.relative_to(WIKI)), 'reason': 'exists'})
            else:
                path.write_text(render_entity(row, page), encoding='utf-8')
                created_entities.append({'target': target, 'file': str(path.relative_to(WIKI)), 'count': row['count']})
                existing.add(page)
            if page != target:
                alias_map[target] = page
            continue
        page = safe_filename(target)
        path = CONCEPTS / f'{page}.md'
        if page in existing or path.exists():
            skipped_existing.append({'target': target, 'file': str(path.relative_to(WIKI)), 'reason': 'exists'})
        else:
            path.write_text(render_concept(row, page), encoding='utf-8')
            created_concepts.append({'target': target, 'file': str(path.relative_to(WIKI)), 'count': row['count']})
            existing.add(page)
        if page != target:
            alias_map[target] = page
    changed_files, alias_counts, unlink_counts = apply_edits(alias_map, unlink_targets)
    archived = archive_backups()
    result = {
        'audit_source': str(AUDIT),
        'alias_candidate_input_count': len(rows),
        'created_concepts_count': len(created_concepts),
        'created_entities_count': len(created_entities),
        'skipped_existing_count': len(skipped_existing),
        'alias_map_count': len(alias_map),
        'unlink_target_count': len(unlink_targets),
        'changed_file_count': len(changed_files),
        'total_alias_replacements': sum(alias_counts.values()),
        'total_unlinks': sum(unlink_counts.values()),
        'archived_backup_count': len(archived),
        'created_concepts': created_concepts,
        'created_entities': created_entities,
        'skipped_existing': skipped_existing,
        'alias_counts': alias_counts,
        'unlink_counts': unlink_counts,
        'changed_files': changed_files,
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
