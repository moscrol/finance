#!/usr/bin/env python3
import json
import re
import shutil
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
OUT = WIKI / 'raw/theme-radar/missing-wikilinks-slash-safe-alias-result.json'
ALIASES = {
    'AR/VR': 'AR_VR',
    'VR/AR': 'VR_AR',
    '5G/6G': '5G_6G',
    '800G/1.6T': '800G_1.6T',
}


def iter_md_files():
    for sub in ['entities', 'concepts', 'sources']:
        for path in sorted((WIKI / sub).glob('*.md')):
            if '.bak' not in path.name:
                yield path


def backup(path):
    bak = path.with_suffix(path.suffix + '.bak-slash-safe-alias')
    if not bak.exists():
        bak.write_text(path.read_text(encoding='utf-8'), encoding='utf-8')


def archive_backups():
    moved = []
    for sub, archive_name in [('entities', 'entity-backups'), ('concepts', 'concept-backups'), ('sources', 'source-backups')]:
        archive = WIKI / 'archive' / archive_name
        archive.mkdir(parents=True, exist_ok=True)
        for path in sorted((WIKI / sub).glob('*.bak-slash-safe-alias')):
            dest = archive / path.name
            i = 1
            while dest.exists():
                dest = archive / f'{path.name}.{i}'
                i += 1
            shutil.move(str(path), str(dest))
            moved.append(str(dest.relative_to(WIKI)))
    return moved


def main():
    changed_files = []
    counts = {}
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
        if base not in ALIASES:
            return match.group(0)
        page = ALIASES[base]
        shown = display if display is not None else base
        counts[base] = counts.get(base, 0) + 1
        return f'[[{page}{anchor}|{shown}]]'
    for path in iter_md_files():
        text = path.read_text(encoding='utf-8')
        new_text = re.sub(r'\[\[([^\]\n]+)\]\]', repl, text)
        if new_text == text:
            continue
        backup(path)
        path.write_text(new_text, encoding='utf-8')
        changed_files.append(str(path.relative_to(WIKI)))
    archived = archive_backups()
    result = {
        'aliases': ALIASES,
        'changed_file_count': len(changed_files),
        'replacement_counts': counts,
        'total_replacements': sum(counts.values()),
        'archived_backup_count': len(archived),
        'changed_files': changed_files,
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
