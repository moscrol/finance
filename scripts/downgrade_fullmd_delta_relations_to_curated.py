#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

DEFAULT_VAULT = Path('/Users/lbq/Desktop/c c/知识库/wiki')


def load_full_sources(vault):
    sources = set()
    for payload in (vault / 'raw/entity-delta-backfill').glob('*.entity-delta.json'):
        try:
            data = json.loads(payload.read_text(encoding='utf-8'))
        except Exception:
            continue
        name = data.get('source_name') or payload.name.replace('.entity-delta.json', '')
        if name:
            sources.add(f'[[{name}]]')
    return sources


def has_full_source(obj, source_links):
    if not isinstance(obj, dict):
        return False
    if obj.get('source') in source_links:
        return True
    sources = obj.get('sources')
    return isinstance(sources, list) and any(s in source_links for s in sources)


def migrate(obj, source_links):
    changed = 0
    if isinstance(obj, dict):
        if has_full_source(obj, source_links) and obj.get('update_type') == 'delta':
            obj['update_type'] = 'curated_research'
            if obj.get('evidence_layer') == 'L3':
                obj['evidence_layer'] = 'L2_candidate'
            changed += 1
        for value in obj.values():
            changed += migrate(value, source_links)
    elif isinstance(obj, list):
        for item in obj:
            changed += migrate(item, source_links)
    return changed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--vault', type=Path, default=DEFAULT_VAULT)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()

    source_links = load_full_sources(args.vault)
    summary = {'apply': args.apply, 'full_sources': len(source_links)}
    for name in ['entity_exposures.json', 'evidence_index.json']:
        path = args.vault / 'relations' / name
        data = json.loads(path.read_text(encoding='utf-8'))
        changed = migrate(data, source_links)
        summary[name] = changed
        if args.apply and changed:
            backup = path.with_suffix(path.suffix + '.bak-curated-relations')
            if not backup.exists():
                backup.write_text(path.read_text(encoding='utf-8'), encoding='utf-8')
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
