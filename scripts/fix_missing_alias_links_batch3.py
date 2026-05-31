#!/usr/bin/env python3
import json
import re
import shutil
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
OUT = WIKI / 'raw/theme-radar/missing-alias-links-batch3-result.json'
MAPPING = {
    'GaN氮化镓': 'GaN',
    'ArF光刻胶': '光刻胶',
    '工业级3D打印': '3D打印',
}


def iter_md_files():
    for sub in ['entities', 'concepts', 'sources']:
        for path in sorted((WIKI / sub).glob('*.md')):
            if '.bak' not in path.name:
                yield path


def replace_links(text):
    counts = {k: 0 for k in MAPPING}
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
        if base not in MAPPING:
            return match.group(0)
        counts[base] += 1
        return f'[[{MAPPING[base]}{anchor}{suffix}]]'
    return re.sub(r'\[\[([^\]\n]+)\]\]', repl, text), {k: v for k, v in counts.items() if v}


def backup(path):
    b = path.with_suffix(path.suffix + '.bak-alias-link-batch3')
    if not b.exists():
        b.write_text(path.read_text(encoding='utf-8'), encoding='utf-8')


def archive_backups():
    moved = []
    for sub, archive_name in [('entities', 'entity-backups'), ('concepts', 'concept-backups')]:
        archive = WIKI / 'archive' / archive_name
        archive.mkdir(parents=True, exist_ok=True)
        for path in sorted((WIKI / sub).glob('*.bak-alias-link-batch3')):
            dest = archive / path.name
            if dest.exists():
                i = 1
                while (archive / f'{path.name}.{i}').exists():
                    i += 1
                dest = archive / f'{path.name}.{i}'
            shutil.move(str(path), str(dest))
            moved.append(str(dest.relative_to(WIKI)))
    return moved


def main():
    existing = {p.stem for sub in ['entities', 'concepts', 'sources'] for p in (WIKI / sub).glob('*.md') if '.bak' not in p.name}
    missing_targets = sorted({v for v in MAPPING.values() if v not in existing})
    if missing_targets:
        raise SystemExit(f'missing mapping targets: {missing_targets}')
    changed_files = []
    total_counts = {}
    for path in iter_md_files():
        text = path.read_text(encoding='utf-8')
        new_text, counts = replace_links(text)
        if new_text == text:
            continue
        backup(path)
        path.write_text(new_text, encoding='utf-8')
        changed_files.append(str(path.relative_to(WIKI)))
        for k, v in counts.items():
            total_counts[k] = total_counts.get(k, 0) + v
    archived = archive_backups()
    result = {'mapping': MAPPING, 'changed_file_count': len(changed_files), 'changed_files': changed_files, 'replacement_counts': total_counts, 'total_replacements': sum(total_counts.values()), 'archived_backups': len(archived)}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
