#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

REL = Path('/Users/lbq/Desktop/c c/知识库/wiki/relations')
CURRENT = REL / 'report_contexts.json'
RESTORE = REL / 'report_contexts.backup-auto-fullmd-context-refine-20260528175048-batch1.json'
STATE = Path('/Users/lbq/Desktop/c c/知识库/wiki/raw/theme-radar/fullmd-report-context-refine-state.json')

MANUAL_DONE = [
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
    '光伏产业新变化与新格局深度研究报告',
    '无人出租车产业新格局与投资机会深度研究报告',
    '火电改造产业新变化与新格局深度研究报告',
    '稀土永磁产业新变化与新格局深度研究报告',
    '油运产业深度研究报告：十六年熊市后的历史性拐点',
    '中国盾构机产业新格局与投资机会深度研究报告',
    '照明设备产业新格局与供应链分析报告',
    '骨架膜产业新变化与新格局深度研究报告',
    '海上风电产业投资价值分析报告',
    '铀矿产业新变化与新格局深度研究报告',
    '光伏铜粉产业新变化与新格局研究分析',
]


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    json.loads(path.read_text(encoding='utf-8'))


def main() -> None:
    if not RESTORE.exists():
        raise SystemExit(f'missing restore backup: {RESTORE}')
    stamp = datetime.now().strftime('%Y%m%d%H%M%S')
    safety = REL / f'report_contexts.backup-before-auto-rollback-{stamp}.json'
    shutil.copy2(CURRENT, safety)
    shutil.copy2(RESTORE, CURRENT)
    json.loads(CURRENT.read_text(encoding='utf-8'))
    state_backup = None
    if STATE.exists():
        state_backup = STATE.with_name(f'{STATE.stem}.backup-before-rollback-{stamp}.json')
        shutil.copy2(STATE, state_backup)
    STATE.parent.mkdir(parents=True, exist_ok=True)
    write_json(STATE, {
        'mode': 'manual_deep_read_only',
        'completed_sources': sorted(MANUAL_DONE),
        'runs': [],
        'rollback': {
            'time': datetime.now().isoformat(timespec='seconds'),
            'restored_from': str(RESTORE),
            'safety_backup': str(safety),
            'previous_state_backup': str(state_backup) if state_backup else None,
            'reason': 'auto surface extraction is not equivalent to full.md deep read',
        },
    })
    print(json.dumps({
        'restored_from': str(RESTORE),
        'safety_backup': str(safety),
        'state_backup': str(state_backup) if state_backup else None,
        'manual_completed': len(MANUAL_DONE),
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
