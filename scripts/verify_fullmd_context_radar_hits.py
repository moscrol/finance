#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path('/Users/lbq/Desktop/c c/金融')
OUT = Path('/Users/lbq/Desktop/c c/知识库/wiki/raw/theme-radar/regression')
TARGETS = [
    ('华为芯片', '华为芯片产业新格局深度研究报告：自主可控突破与供应链重构'),
    ('推理芯片', '推理芯片产业新变化与新格局研究报告'),
    ('光模块', '光模块产业新变化和新格局研究分析报告'),
    ('芯片IP', '芯片IP产业新变化和新格局研究分析'),
    ('封测', '封测产业新变化与新格局深度研究报告'),
    ('AI算力', 'AI算力产业新格局与供应链深度研究报告'),
    ('华为算力', '华为算力产业深度研究：技术突破与供应链重构下的投资机会'),
    ('模拟芯片', '模拟芯片产业新变化与新格局研究分析报告'),
    ('晶圆代工', '晶圆代工产业新变化与新格局深度研究报告'),
    ('超聚变', '超聚变产业新格局与供应链深度分析报告'),
    ('鸿蒙', '鸿蒙产业新变化与新格局全面分析报告'),
    ('汽车零部件', '汽车零部件产业新变化与新格局研究报告'),
    ('智能驾驶', '智能驾驶产业新格局与供应链深度研究报告'),
    ('铜箔', '铜箔产业新变化与新格局研究分析报告'),
]


def main() -> None:
    results = []
    for term, source in TARGETS:
        out = OUT / f'{term}-context-final-batchcheck.md'
        subprocess.run(
            ['python3', 'skills/theme-radar/scripts/radar.py', '--term', term, '--out', str(out)],
            cwd=ROOT,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        text = out.read_text(encoding='utf-8', errors='ignore')
        hit = source in text
        row_count = sum(1 for line in text.splitlines() if source in line and line.startswith('|'))
        results.append((term, hit, row_count, out.name))
    for term, hit, row_count, name in results:
        print(f'{term}\t{"HIT" if hit else "MISS"}\trows={row_count}\t{name}')
    if not all(hit and row_count >= 1 for _, hit, row_count, _ in results):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
