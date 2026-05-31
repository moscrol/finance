#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

CTX = Path('/Users/lbq/Desktop/c c/知识库/wiki/relations/report_contexts.json')
TARGETS = [
    '铀矿产业新变化与新格局深度研究报告',
    '电容薄膜产业新变化与新格局深度研究报告',
    '光伏铜粉产业新变化与新格局研究分析',
]


def item_count(ctx: dict) -> int:
    return sum(len(v or []) for v in (ctx.get('supply_chain') or {}).values())


def main() -> None:
    reports = json.loads(CTX.read_text(encoding='utf-8'))['reports']
    for source in TARGETS:
        ctx = reports[source]
        print(source)
        print('concept=', ctx.get('concept'))
        print('items=', item_count(ctx), 'related=', len(ctx.get('related_concepts') or []), 'evidence=', len(ctx.get('evidence') or []))
        print('layers=', ','.join((ctx.get('supply_chain') or {}).keys()))
        print()


if __name__ == '__main__':
    main()
