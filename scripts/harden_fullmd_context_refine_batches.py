#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

REL = Path('/Users/lbq/Desktop/c c/知识库/wiki/relations')
BASE = REL / 'report_contexts.backup-fullmd-context-refine-20260528153943.json'
TARGET = REL / 'report_contexts.json'

PRUNE = {
    '华为芯片产业新格局深度研究报告：自主可控突破与供应链重构': [
        '家电与物联网模组', '运营商网络', '国产半导体供应链', '华为海思授权代理体系',
        'China-for-China供应链', '14nm/7nm国产制程适配', '海思芯片分销', '存储芯片/HBM材料配套',
    ],
    '推理芯片产业新变化与新格局研究报告': [
        '国产AI芯片生态', '云厂商采购体系', 'FOWLP封装', 'SiP封装', 'TSV/FOPLP封装', 'SOD材料',
    ],
    '光模块产业新变化和新格局研究分析报告': [
        '北美AI服务器', '光芯片制造设备', '耦合封装设备', '测试设备', '硅光工艺平台',
        '高速光模块测试平台', '磷化铟材料', '硅光材料', '光学透镜', '陶瓷套管', 'PCB/载板', '高速连接材料',
    ],
    '芯片IP产业新变化和新格局研究分析': [
        'AIGC芯片平台', '智慧出行芯片平台', 'IP验证工具', '仿真工具', '芯片设计环境',
        '工艺验证平台', '基础工艺库', '标准单元库', '数模混合IP基础模块',
    ],
    '封测产业新变化与新格局深度研究报告': [
        'China-for-China供应链', '长三角封测产业集群', '封装光刻机', 'Bumping设备',
        'RDL制造设备', 'TSV设备', '环氧塑封料EMC', '封装胶', '光刻胶/湿法材料',
    ],
    'AI算力产业新格局与供应链深度研究报告': [
        '制造业', '政府算力平台', '服务器制造设备', '液冷系统', '测试设备',
        'NAND存储', 'ABF载板', '高速连接器', '电源管理芯片', '散热材料',
    ],
    '华为算力产业深度研究：技术突破与供应链重构下的投资机会': [
        '运营商', '行业大模型', '华为四位一体合作体系', 'Atlas超节点', 'TaiShan超节点',
        '晶圆代工设备', '先进封装设备', '服务器整机制造设备', '高速互联测试设备',
        'ABF封装基板', 'PCB/高速背板', '网卡芯片', '高速连接器', '液冷材料',
    ],
    '模拟芯片产业新变化与新格局研究分析报告': [
        '通信基站', 'AI服务器供电', '成熟制程国产化', '成熟制程产线设备', '模拟工艺材料',
    ],
    '晶圆代工产业新变化与新格局深度研究报告': [
        '显示驱动芯片', 'China-for-China供应链', '地缘供应链重构', '车规芯片代工',
        'AI芯片代工', 'DUV光刻机', '清洗设备', '离子注入设备', 'CMP材料', '封装材料',
    ],
    '超聚变产业新格局与供应链深度分析报告': [
        '全球企业客户', '华为服务器传承', '国产服务器生态', '液冷服务器生态',
        '河南国资产业平台', '昆仑服务器', 'AI加速卡集成', '存储模组',
        'FusionOS服务器操作系统', '服务器制造设备', '测试设备', '数据中心基础设施设备',
        '电源散热设备', '液冷材料',
    ],
    '鸿蒙产业新变化与新格局全面分析报告': [
        'IoT设备', '金融IT', '星闪互联', '政企信创软件', '终端ODM代工',
        '操作系统开发工具', '应用开发框架', '分布式开发工具', '测试认证工具',
        '终端代工产线', '终端芯片', '通信模组', '车载硬件', 'IoT模组', '安全芯片', '终端ODM',
    ],
    '汽车零部件产业新变化与新格局研究报告': [
        '后市场服务', '长三角汽车零部件集群', '珠三角智能终端与动力电池集群',
        '冲压设备', '压铸设备', '注塑设备', '焊接设备', '检测设备', '电子电气测试设备', '传感器材料',
    ],
    '智能驾驶产业新格局与供应链深度研究报告': [
        'L3合法上路', '车路协同C-V2X', '传感器测试设备', '域控制器测试平台',
        '车规验证平台', '路测数据采集系统', '仿真训练平台', '激光雷达器件',
        '毫米波雷达器件', '传感器芯片', '车规级芯片', '连接器', '线控制动材料',
    ],
    '铜箔产业新变化与新格局研究分析报告': [
        '锂电材料', 'PCB材料', 'AI服务器高频高速材料', '新能源供应链',
        '分切设备', '真空镀膜设备', '铜杆', 'PET基膜', 'PP基膜',
    ],
}


def evidence_key(item: object) -> str:
    if isinstance(item, dict):
        return (item.get('heading') or '') + '|' + (item.get('text') or '')
    return str(item)


def merge_evidence(new: list, old: list) -> list:
    merged = []
    seen = set()
    for item in list(new or []) + list(old or []):
        key = evidence_key(item)
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return merged


def prune_context(ctx: dict, banned: set[str]) -> int:
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


def item_count(ctx: dict) -> int:
    return sum(len(v or []) for v in (ctx.get('supply_chain') or {}).values())


def main() -> None:
    before = json.loads(BASE.read_text(encoding='utf-8'))['reports']
    data = json.loads(TARGET.read_text(encoding='utf-8'))
    reports = data['reports']
    backup = TARGET.with_name('report_contexts.backup-fullmd-context-hardening-' + datetime.now().strftime('%Y%m%d%H%M%S') + '.json')
    shutil.copy2(TARGET, backup)
    result = []
    for source, banned_items in PRUNE.items():
        ctx = reports[source]
        old = before.get(source, {})
        old_items = item_count(ctx)
        old_ev = len(ctx.get('evidence') or [])
        ctx['evidence'] = merge_evidence(ctx.get('evidence') or [], old.get('evidence') or [])
        removed = prune_context(ctx, set(banned_items))
        result.append({
            'source': source,
            'items_before': old_items,
            'items_after': item_count(ctx),
            'removed': removed,
            'evidence_before': old_ev,
            'evidence_after': len(ctx.get('evidence') or []),
        })
    data['updated'] = datetime.now().date().isoformat()
    tmp = TARGET.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    tmp.replace(TARGET)
    json.loads(TARGET.read_text(encoding='utf-8'))
    print(json.dumps({'backup': str(backup), 'result': result}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
