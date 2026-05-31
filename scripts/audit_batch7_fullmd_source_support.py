#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

RAW = Path('/Users/lbq/Desktop/c c/知识库/raw')
CTX = Path('/Users/lbq/Desktop/c c/知识库/wiki/relations/report_contexts.json')
TARGETS = [
    '酒店餐饮产业新格局与供应链深度分析报告',
    '培育钻石产业新变化与新格局研究报告',
    '基因检测产业新变化和新格局深度研究报告',
]
ALIASES = {
    '餐饮供应链': ['酒店餐饮供应链', '餐饮企业'],
    '酒店用品': ['酒店用品供应'],
    '餐饮信息化': ['餐饮信息化领域', '酒店餐饮信息化'],
    '商用餐饮设备': ['商用厨房设备', '餐饮设备'],
    'HPHT': ['HPHT 法'],
    'CVD': ['CVD 法'],
    'MPCVD': ['MPCVD 设备'],
    '半导体散热': ['半导体散热片', '半导体散热'],
    '新能源汽车逆变器': ['新能源汽车逆变器', '电动汽车逆变器'],
    'NGS': ['NGS 技术', '二代'],
    'NIPT': ['NIPT/生殖健康'],
    '肿瘤早筛': ['早筛', '肿瘤基因检测'],
    '伴随诊断': ['伴随诊断'],
    '多组学': ['多组学整合'],
    '精准医学': ['精准医学中心'],
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
