#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

RAW = Path('/Users/lbq/Desktop/c c/知识库/raw')
CTX = Path('/Users/lbq/Desktop/c c/知识库/wiki/relations/report_contexts.json')
TARGETS = [
    '光伏产业新变化和新格局深度分析报告',
    '无人出租车产业研究分析报告',
    '火电改造产业深度研究：新格局、供应链重构与投资机会分析',
]
ALIASES = {
    'TOPCON电池': ['TOPCon', 'TOPCon 电池'],
    'HJT电池': ['HJT', 'HJT 电池'],
    'BC电池': ['BC 技术', 'BC 电池'],
    '钙钛矿电池': ['钙钛矿叠层电池'],
    '光伏逆变器': ['逆变器'],
    '光伏支架': ['光伏支架系统'],
    'Robotaxi': ['Robotaxi（Robot + Taxi）'],
    '无人驾驶': ['无人驾驶汽车', '自动驾驶出租车'],
    'L3级自动驾驶': ['L3 级', 'L3 级有条件自动驾驶'],
    'L4级自动驾驶': ['L4 级', 'L4 级高度自动驾驶'],
    '车路云一体化': ['车路云一体化'],
    '智慧电厂': ['智慧电厂解决方案'],
    '数字孪生': ['数字孪生平台'],
    '灵活性改造': ['灵活性改造'],
    '节能降碳改造': ['节能降碳改造'],
    '供热改造': ['供热改造'],
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
