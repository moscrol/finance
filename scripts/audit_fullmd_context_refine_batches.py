#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

REL = Path('/Users/lbq/Desktop/c c/知识库/wiki/relations')
BASE = REL / 'report_contexts.backup-fullmd-context-refine-20260528153943.json'
CUR = REL / 'report_contexts.json'


def item_count(ctx: dict | None) -> int:
    if not ctx:
        return 0
    return sum(len(v or []) for v in (ctx.get('supply_chain') or {}).values())


def main() -> None:
    before = json.loads(BASE.read_text(encoding='utf-8'))['reports']
    current = json.loads(CUR.read_text(encoding='utf-8'))['reports']
    changed = []
    for key in sorted(set(before) | set(current)):
        old = before.get(key)
        new = current.get(key)
        if old == new:
            continue
        changed.append({
            'source': key,
            'concept_old': (old or {}).get('concept'),
            'concept_new': (new or {}).get('concept'),
            'items_old': item_count(old),
            'items_new': item_count(new),
            'related_old': len((old or {}).get('related_concepts') or []),
            'related_new': len((new or {}).get('related_concepts') or []),
            'evidence_old': len((old or {}).get('evidence') or []),
            'evidence_new': len((new or {}).get('evidence') or []),
        })
    print(json.dumps({'changed_count': len(changed), 'changed': changed}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
