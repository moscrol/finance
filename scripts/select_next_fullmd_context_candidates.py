#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

RAW = Path('/Users/lbq/Desktop/c c/知识库/raw')
CTX = Path('/Users/lbq/Desktop/c c/知识库/wiki/relations/report_contexts.json')

DONE = {
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
}

PREFER = ['机器人', '固态电池', '液冷', '商业航天', '低空', '卫星', '电解液', '钠离子', '复合铜箔', 'PCB', '服务器', '算力']


def item_count(ctx: dict) -> int:
    return sum(len(v or []) for v in (ctx.get('supply_chain') or {}).values())


def has_raw(source: str) -> bool:
    return any(source in p.stem for p in RAW.glob('*-full.md'))


def score(source: str, ctx: dict) -> tuple:
    name = source + ' ' + str(ctx.get('concept') or '')
    prefer = 0 if any(x in name for x in PREFER) else 1
    return (prefer, item_count(ctx), len(ctx.get('evidence') or []), source)


def main() -> None:
    reports = json.loads(CTX.read_text(encoding='utf-8'))['reports']
    rows = []
    for source, ctx in reports.items():
        if source in DONE:
            continue
        if not has_raw(source):
            continue
        items = item_count(ctx)
        if items > 35 and len(ctx.get('evidence') or []) > 4:
            continue
        rows.append((score(source, ctx), source, ctx))
    rows.sort(key=lambda x: x[0])
    for _, source, ctx in rows[:20]:
        print(f"{source}\tconcept={ctx.get('concept')}\titems={item_count(ctx)}\trelated={len(ctx.get('related_concepts') or [])}\tevidence={len(ctx.get('evidence') or [])}")


if __name__ == '__main__':
    main()
