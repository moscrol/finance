#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

RAW = Path('/Users/lbq/Desktop/c c/知识库/raw')
CTX = Path('/Users/lbq/Desktop/c c/知识库/wiki/relations/report_contexts.json')
TARGETS = [
    '稀土永磁产业新变化与新格局深度研究报告',
    '油运产业深度研究报告：十六年熊市后的历史性拐点',
    '中国盾构机产业新格局与投资机会深度研究报告',
]
ALIASES = {
    '稀土': ['稀土元素', '稀土矿'],
    '钕铁硼': ['钕铁硼永磁体', '钕铁硼永磁材料'],
    '烧结钕铁硼': ['烧结钕铁硼是'],
    '粘结钕铁硼': ['粘结钕铁硼可'],
    '风电': ['风力发电'],
    'VLCC': ['超大型油轮（VLCC）'],
    'LNG运输': ['LNG 运输'],
    'LNG双燃料': ['LNG 双燃料'],
    '船舶制造': ['船舶制造层'],
    '船用钢材': ['船用钢材领域'],
    '甲醇燃料': ['甲醇燃料技术'],
    '氨燃料': ['氨燃料技术'],
    '氢燃料': ['氢燃料技术'],
    'CCUS': ['碳捕捉技术（CCUS）'],
    '盾构机': ['盾构机产业'],
    'TBM': ['硬岩隧道掘进机', 'TBM 盾构机'],
    '盾构刀具': ['盾构刀具（WC', '盾构刀具'],
    '地下管网': ['地下综合管廊'],
    '城市轨道交通': ['城市轨道交通运营里程'],
    '水利工程': ['水利工程领域'],
}


def locate_raw(source: str) -> Path:
    for f in RAW.glob('*-full.md'):
        if source in f.stem:
            return f
    raise FileNotFoundError(source)


def supported(item: str, text: str) -> bool:
    compact = text.replace(' ', '')
    probes = [item, item.replace(' ', '')]
    probes.extend(ALIASES.get(item, []))
    return any(p and (p in text or p.replace(' ', '') in compact) for p in probes)


def main() -> None:
    reports = json.loads(CTX.read_text(encoding='utf-8'))['reports']
    failed = False
    for source in TARGETS:
        ctx = reports[source]
        text = locate_raw(source).read_text(encoding='utf-8', errors='ignore')
        items = []
        for values in (ctx.get('supply_chain') or {}).values():
            items.extend(values or [])
        items.extend(ctx.get('related_concepts') or [])
        misses = [x for x in items if not supported(x, text)]
        print(f'{source}\t{len(items)-len(misses)}/{len(items)}\tmiss={len(misses)}')
        if misses:
            failed = True
            print('MISS:', '、'.join(misses))
    if failed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
