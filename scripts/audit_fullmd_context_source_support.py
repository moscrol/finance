#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

RAW = Path('/Users/lbq/Desktop/c c/知识库/raw')
CTX = Path('/Users/lbq/Desktop/c c/知识库/wiki/relations/report_contexts.json')
TARGETS = [
    '华为芯片产业新格局深度研究报告：自主可控突破与供应链重构',
    '推理芯片产业新变化与新格局研究报告',
    '光模块产业新变化和新格局研究分析报告',
    '芯片IP产业新变化和新格局研究分析',
    '封测产业新变化与新格局深度研究报告',
    'AI算力产业新格局与供应链深度研究报告',
    '华为算力产业深度研究：技术突破与供应链重构下的投资机会',
    '模拟芯片产业新变化与新格局研究分析报告',
    '晶圆代工产业新变化与新格局深度研究报告',
    '超聚变产业新格局与供应链深度分析报告',
    '鸿蒙产业新变化与新格局全面分析报告',
    '汽车零部件产业新变化与新格局研究报告',
    '智能驾驶产业新格局与供应链深度研究报告',
    '铜箔产业新变化与新格局研究分析报告',
]

ALIASES = {
    'Tier1系统集成': ['Tier 1', 'Tier1', '一级供应商'],
    'Tier0.5供应商': ['Tier 0.5', 'Tier0.5'],
    'L3/L4自动驾驶': ['L3', 'L4'],
    'AI芯片': ['AI 芯片', '人工智能芯片'],
    'EDA': ['EDA工具', 'EDA 工具'],
    'GPU': ['GPU'],
    'NPU': ['NPU'],
    'C-V2X': ['车路协同', '车路云'],
    'PET铜箔': ['PET 铜箔', 'PET基复合铜箔'],
    'PP铜箔': ['PP 铜箔', 'PP基复合铜箔'],
    '4.5μm铜箔': ['4.5μm', '4.5 微米'],
    'L3级自动驾驶': ['L3'],
}


def locate_raw(source: str) -> Path | None:
    files = list(RAW.glob('*-full.md'))
    for f in files:
        if source in f.stem:
            return f
    short = source.replace('报告', '').replace('分析', '').replace('研究', '')[:8]
    for f in files:
        if short and short in f.stem:
            return f
    return None


def supported(item: str, text: str) -> bool:
    probes = [item, item.replace(' ', '')]
    probes.extend(ALIASES.get(item, []))
    compact = text.replace(' ', '')
    return any(p and (p in text or p.replace(' ', '') in compact) for p in probes)


def main() -> None:
    data = json.loads(CTX.read_text(encoding='utf-8'))['reports']
    results = []
    for source in TARGETS:
        ctx = data[source]
        raw = locate_raw(source)
        if not raw:
            results.append({'source': source, 'error': 'raw_not_found'})
            continue
        text = raw.read_text(encoding='utf-8', errors='ignore')
        items = []
        for values in (ctx.get('supply_chain') or {}).values():
            items.extend(values or [])
        items.extend(ctx.get('related_concepts') or [])
        misses = [x for x in items if not supported(x, text)]
        results.append({
            'source': source,
            'raw': raw.name,
            'items': len(items),
            'supported': len(items) - len(misses),
            'misses': misses[:30],
        })
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
