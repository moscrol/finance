#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

RAW = Path('/Users/lbq/Desktop/c c/知识库/raw')
CTX = Path('/Users/lbq/Desktop/c c/知识库/wiki/relations/report_contexts.json')
TARGETS = [
    '照明设备产业新格局与供应链分析报告',
    '骨架膜产业新变化与新格局深度研究报告',
    '海上风电产业投资价值分析报告',
]
ALIASES = {
    'LED照明': ['LED 照明'],
    'LED芯片': ['LED 芯片'],
    'LED封装': ['LED 封装'],
    'Mini LED': ['Mini LED', 'MiniLED'],
    'Micro LED': ['Micro LED', 'MicroLED'],
    'MOCVD': ['MOCVD（金属有机化学气相沉积）设备'],
    '驱动IC': ['驱动 IC'],
    'Matter协议': ['Matter 协议'],
    '全固态电池': ['全固态电池标准体系建设指南'],
    '硫化物电解质': ['硫化物电解质材料'],
    '聚酰亚胺': ['聚酰亚胺 PI'],
    '涂覆隔膜': ['涂覆膜', '涂覆加工'],
    '风电': ['海上风电'],
    '风电叶片': ['叶片制造', '海上风电叶片'],
    '风电轴承': ['风电轴承'],
    '塔筒': ['塔筒和桩基'],
    '桩基': ['塔筒和桩基'],
    '直驱永磁': ['直驱永磁技术'],
    '漂浮式风电': ['漂浮式基础技术', '漂浮式风电机组'],
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
