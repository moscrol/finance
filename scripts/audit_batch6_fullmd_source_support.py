#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

RAW = Path('/Users/lbq/Desktop/c c/知识库/raw')
CTX = Path('/Users/lbq/Desktop/c c/知识库/wiki/relations/report_contexts.json')
TARGETS = [
    '铀矿产业新变化与新格局深度研究报告',
    '电容薄膜产业新变化与新格局深度研究报告',
    '光伏铜粉产业新变化与新格局研究分析',
]
ALIASES = {
    '铀资源': ['铀资源量', '铀矿资源'],
    '铀矿': ['铀矿产业', '铀矿开采'],
    'CO2+O2 地浸技术': ['CO2+O2 地浸', 'CO2+O2 浸出法'],
    '燃料组件': ['燃料元件'],
    '核电': ['核电站', '核电机组'],
    'BOPP': ['聚丙烯（PP）薄膜', '聚丙烯电容膜'],
    'PET': ['聚酯（PET）薄膜', 'PET 薄膜'],
    'PEN': ['聚萘二甲酸乙二醇酯（PEN）薄膜'],
    'PPS': ['聚苯硫醚（PPS）薄膜'],
    '薄膜电容器': ['薄膜电容'],
    'TOPCON电池': ['TOPCon', 'TOPCon 电池'],
    'HJT电池': ['HJT', 'HJT 电池'],
    'BC电池': ['BC', 'BC 电池'],
    '光伏电池': ['光伏电池制造'],
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
