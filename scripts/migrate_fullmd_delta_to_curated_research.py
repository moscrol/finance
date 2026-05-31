#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path

DEFAULT_VAULT = Path('/Users/lbq/Desktop/c c/知识库/wiki')


def load_full_sources(vault):
    sources = set()
    backfill = vault / 'raw/entity-delta-backfill'
    for payload in backfill.glob('*.entity-delta.json'):
        try:
            data = json.loads(payload.read_text(encoding='utf-8'))
        except Exception:
            continue
        name = data.get('source_name') or payload.name.replace('.entity-delta.json', '')
        if name:
            sources.add(name)
    return sources


def split_sections(content):
    pattern = re.compile(r'^### \d{4}-\d{2}-\d{2}｜(.+?)\n.*?(?=^### \d{4}-\d{2}-\d{2}｜|\Z)', re.M | re.S)
    out = []
    pos = 0
    for match in pattern.finditer(content):
        if match.start() > pos:
            out.append(('text', '', content[pos:match.start()]))
        out.append(('section', match.group(1).strip(), match.group(0)))
        pos = match.end()
    if pos < len(content):
        out.append(('text', '', content[pos:]))
    return out


def section_content(text, title):
    m = re.search(rf'^## {re.escape(title)}\n(.*?)(?=^## |\Z)', text, re.M | re.S)
    if not m:
        return None
    return m.start(), m.end(), m.group(1)


def remove_empty_delta(text):
    m = section_content(text, '边际变化')
    if not m:
        return text
    start, end, content = m
    if not content.strip():
        return text[:start].rstrip() + '\n\n' + text[end:].lstrip()
    return text


def migrate_text(text, full_sources):
    delta = section_content(text, '边际变化')
    if not delta:
        return text, 0
    d_start, d_end, d_content = delta
    moved = []
    kept = []
    count = 0
    for kind, source, block in split_sections(d_content):
        if kind == 'section' and source in full_sources:
            if block.strip() not in text[:d_start]:
                moved.append(block.rstrip() + '\n')
            count += 1
        else:
            kept.append(block)
    if not count:
        return text, 0
    new_delta = '## 边际变化\n' + ''.join(kept).strip() + '\n'
    text = text[:d_start] + new_delta + text[d_end:]

    curated = section_content(text, '高信度研究线索')
    moved_text = '\n'.join(moved).strip() + '\n'
    if curated:
        c_start, c_end, c_content = curated
        new_curated = '## 高信度研究线索\n\n' + moved_text + c_content.lstrip()
        text = text[:c_start] + new_curated + text[c_end:]
    else:
        delta = section_content(text, '边际变化')
        if delta:
            d_start, _, _ = delta
            text = text[:d_start].rstrip() + '\n\n## 高信度研究线索\n\n' + moved_text + '\n' + text[d_start:].lstrip()
        else:
            text = text.rstrip() + '\n\n## 高信度研究线索\n\n' + moved_text
    text = remove_empty_delta(text)
    return text.rstrip() + '\n', count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--vault', type=Path, default=DEFAULT_VAULT)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()

    full_sources = load_full_sources(args.vault)
    changed = []
    for path in sorted((args.vault / 'entities').glob('*.md')):
        text = path.read_text(encoding='utf-8')
        new_text, count = migrate_text(text, full_sources)
        if count:
            changed.append({'file': str(path), 'sections': count})
            if args.apply:
                backup = path.with_suffix(path.suffix + '.bak-curated-migration')
                if not backup.exists():
                    backup.write_text(text, encoding='utf-8')
                path.write_text(new_text, encoding='utf-8')
    print(json.dumps({'apply': args.apply, 'full_sources': len(full_sources), 'changed_files': len(changed), 'moved_sections': sum(x['sections'] for x in changed), 'examples': changed[:30]}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
