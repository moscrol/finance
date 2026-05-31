#!/usr/bin/env python3
import json
import re
import shutil
from datetime import date
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
AUDIT = WIKI / 'raw/theme-radar/missing-wikilinks-audit.json'
OUT = WIKI / 'raw/theme-radar/missing-wikilinks-report-highfreq-apply-result.json'
CONCEPTS = WIKI / 'concepts'


def safe_filename(value):
    return re.sub(r'[/:*?"<>|\n\r\t]+', '_', str(value)).strip()


def yaml_list(values):
    return '[' + ', '.join(json.dumps(v, ensure_ascii=False) for v in values) + ']'


def infer_tags(name):
    tags = ['概念', '待补证', 'missing-wikilink-highfreq']
    for token in ['AI', '芯片', '半导体', '电池', '光伏', '光刻', '材料', '机器人', '算力', '数据', '医疗', '军工', '航空', '航天', '汽车', '能源', '装备']:
        if token in name and token not in tags:
            tags.append(token)
    return tags


def render_stub(row, page_name):
    today = date.today().isoformat()
    title = row['target']
    log_entry = f"created from remaining concept_candidate_high_freq cleanup; count={row.get('count', 0)}; page={page_name}"
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
        '占位概念页：该概念由剩余高频 missing wikilinks 清理生成，用于修复断链和承接题材雷达后续补证。',
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


def iter_md_files():
    for sub in ['entities', 'concepts', 'sources']:
        for path in sorted((WIKI / sub).glob('*.md')):
            if '.bak' not in path.name:
                yield path


def backup(path):
    bak = path.with_suffix(path.suffix + '.bak-report-highfreq-batch1')
    if not bak.exists():
        bak.write_text(path.read_text(encoding='utf-8'), encoding='utf-8')


def archive_backups():
    moved = []
    for sub, archive_name in [('entities', 'entity-backups'), ('concepts', 'concept-backups'), ('sources', 'source-backups')]:
        archive = WIKI / 'archive' / archive_name
        archive.mkdir(parents=True, exist_ok=True)
        for path in sorted((WIKI / sub).glob('*.bak-report-highfreq-batch1')):
            dest = archive / path.name
            if dest.exists():
                i = 1
                while (archive / f'{path.name}.{i}').exists():
                    i += 1
                dest = archive / f'{path.name}.{i}'
            shutil.move(str(path), str(dest))
            moved.append(str(dest.relative_to(WIKI)))
    return moved


def unlink_report_targets(report_targets):
    counts = {}
    changed = []
    def repl(match):
        inner = match.group(1)
        if '|' in inner:
            target, display = inner.split('|', 1)
        else:
            target, display = inner, None
        base = target.split('#', 1)[0].strip()
        if base in report_targets:
            counts[base] = counts.get(base, 0) + 1
            return display if display is not None else base
        return match.group(0)
    for path in iter_md_files():
        text = path.read_text(encoding='utf-8')
        new_text = re.sub(r'\[\[([^\]\n]+)\]\]', repl, text)
        if new_text != text:
            backup(path)
            path.write_text(new_text, encoding='utf-8')
            changed.append(str(path.relative_to(WIKI)))
    return changed, counts


def main():
    data = json.loads(AUDIT.read_text(encoding='utf-8'))
    items = data['items']
    high_freq = [r for r in items if r['category'] == 'concept_candidate_high_freq']
    reports = [r for r in items if r['category'] == 'report_source_backlink']
    existing = {p.stem for sub in ['entities', 'concepts', 'sources'] for p in (WIKI / sub).glob('*.md') if '.bak' not in p.name}
    created = []
    skipped = []
    for row in high_freq:
        page = safe_filename(row['target'])
        path = CONCEPTS / f'{page}.md'
        if page in existing or path.exists():
            skipped.append({'target': row['target'], 'file': str(path.relative_to(WIKI)), 'reason': 'exists'})
            continue
        path.write_text(render_stub(row, page), encoding='utf-8')
        existing.add(page)
        created.append({'target': row['target'], 'file': str(path.relative_to(WIKI)), 'count': row['count']})
    changed_files, report_unlinks = unlink_report_targets({r['target'] for r in reports})
    archived = archive_backups()
    result = {
        'audit_source': str(AUDIT),
        'created_concepts_count': len(created),
        'skipped_existing_count': len(skipped),
        'report_targets_count': len(reports),
        'changed_file_count': len(changed_files),
        'total_report_unlinks': sum(report_unlinks.values()),
        'archived_backup_count': len(archived),
        'created_concepts': created,
        'skipped_existing': skipped,
        'report_unlinks': report_unlinks,
        'changed_files': changed_files,
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
