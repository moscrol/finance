#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

TARGET = Path('/Users/lbq/Desktop/c c/知识库/wiki/relations/report_contexts.json')

PRUNE = {
    '华为芯片产业新格局深度研究报告：自主可控突破与供应链重构': ['鸿蒙生态', '麒麟SoC', '半导体IP授权', '清洗设备', '热处理设备', '半导体硅材料'],
    '推理芯片产业新变化与新格局研究报告': ['NPU推理芯片', 'ASIC推理芯片', 'Chiplet封装', 'CMP抛光液'],
    '芯片IP产业新变化和新格局研究分析': ['SoC设计', 'ARM生态', '芯片设计服务', 'NPU IP'],
    '封测产业新变化与新格局深度研究报告': ['晶圆切割', 'Chiplet封装', 'OSAT封测服务'],
    'AI算力产业新格局与供应链深度研究报告': ['云厂商', '大模型推理', 'AI芯片设计', '芯片设计工具', '晶圆制造设备', '先进封装设备', 'HBM/DRAM'],
    '华为算力产业深度研究：技术突破与供应链重构下的投资机会': ['鲲鹏生态', '国产算力供应链', '鲲鹏CPU', '服务器代工', '液冷服务器'],
    '模拟芯片产业新变化与新格局研究分析报告': ['汽车电动化', 'Fabless设计', '成熟制程晶圆代工'],
    '晶圆代工产业新变化与新格局深度研究报告': ['成熟制程国产替代', '半导体国产化', '成熟制程晶圆代工', '5nm制程', '7nm制程', '14nm制程', '硅晶圆'],
    '超聚变产业新格局与供应链深度分析报告': ['企业数字化', 'AI服务器国产替代', 'DDR4/DDR5内存', '电源模块', '国产算力'],
    '鸿蒙产业新变化与新格局全面分析报告': ['华为终端生态', '国产操作系统替代', '鸿蒙应用开发', 'IoT'],
    '汽车零部件产业新变化与新格局研究报告': ['Tier2零部件', 'Tier3基础材料'],
    '智能驾驶产业新格局与供应链深度研究报告': ['L2辅助驾驶', '自动驾驶算法'],
    '铜箔产业新变化与新格局研究分析报告': ['PET铜箔'],
}


def remove_items(ctx: dict, banned: set[str]) -> int:
    removed = 0
    for layer, values in (ctx.get('supply_chain') or {}).items():
        kept = [x for x in values if x not in banned]
        removed += len(values) - len(kept)
        ctx['supply_chain'][layer] = kept
    values = ctx.get('related_concepts') or []
    kept = [x for x in values if x not in banned]
    removed += len(values) - len(kept)
    ctx['related_concepts'] = kept
    return removed


def main() -> None:
    data = json.loads(TARGET.read_text(encoding='utf-8'))
    backup = TARGET.with_name('report_contexts.backup-fullmd-context-final-prune-' + datetime.now().strftime('%Y%m%d%H%M%S') + '.json')
    shutil.copy2(TARGET, backup)
    result = []
    for source, items in PRUNE.items():
        removed = remove_items(data['reports'][source], set(items))
        result.append({'source': source, 'removed': removed})
    data['updated'] = datetime.now().date().isoformat()
    tmp = TARGET.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    tmp.replace(TARGET)
    json.loads(TARGET.read_text(encoding='utf-8'))
    print(json.dumps({'backup': str(backup), 'result': result}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
