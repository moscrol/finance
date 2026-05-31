#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

TARGET = Path('/Users/lbq/Desktop/c c/知识库/wiki/relations/report_contexts.json')

UPDATES = {
    '铀矿产业新变化与新格局深度研究报告': {
        'source_name': '铀矿产业新变化与新格局深度研究报告',
        'source_date': '2026-01-29',
        'concept': '铀矿',
        'supply_chain': {
            'upstream_materials': ['铀资源', '铀矿', '天然铀', '浓缩铀', '二氧化铀粉末', '锆合金包壳管', '铀 - 235'],
            'upstream_equipment': ['注入井', '抽出井', '多孔扩散膜', '高速旋转离心机', 'CF 系列离心机'],
            'midstream': ['铀矿开采', '地浸采铀', 'CO2+O2 地浸技术', '铀浓缩', '气体离心法', '核燃料制造', '燃料芯块', '燃料棒', '燃料组件', '高温气冷堆燃料元件'],
            'downstream': ['核能', '核电', '核反应堆', '核电站', '核电机组', '基荷电源'],
            'ecosystem': ['双碳', '核能复兴', '地缘政治', '美国对俄罗斯核燃料制裁', '哈萨克斯坦产量调整', '天然铀开发'],
        },
        'related_concepts': ['核能', '核电', '铀浓缩', '天然铀', '地浸采铀', '核燃料', '核级阀门', '乏燃料后处理'],
        'evidence': [
            {'heading': '供需缺口', 'text': '2024 年全球铀需求约 6.8 万吨，而矿山一次供应仅 5.6 万吨，供需缺口约 1.2 万吨。'},
            {'heading': '开采技术', 'text': '第三代技术以地浸采铀（ISL）为代表，其中 CO2+O2 地浸技术是目前的主流工艺，占国内 90% 以上产量。'},
            {'heading': '浓缩环节', 'text': '气体离心法成为当前主流技术，占全球铀浓缩产能 90% 以上。'},
            {'heading': '燃料制造', 'text': '核燃料制造包括将浓缩铀转化为二氧化铀粉末，再压制成燃料芯块，装入锆合金包壳管制成燃料棒，最终组装成燃料组件。'},
            {'heading': '供应格局', 'text': '2023 年全球铀矿生产前五厂商分别为 Kazatomprom、Cameco、Orano、中广核、UraniumOne。'},
        ],
    },
    '电容薄膜产业新变化与新格局深度研究报告': {
        'source_name': '电容薄膜产业新变化与新格局深度研究报告',
        'source_date': '2026-01-29',
        'concept': '电容薄膜',
        'supply_chain': {
            'upstream_materials': ['聚丙烯（PP）材料', '聚酯（PET）材料', 'PEN 薄膜', 'PPS 薄膜', '电极材料（铝 / 锌）', '引线端子（铜 / 锡合金）', '封装树脂', '抗氧剂', '阻燃剂'],
            'upstream_equipment': ['双向拉伸机组', '精密分切装备', '真空镀膜系统', '双向拉伸设备', '在线缺陷检测模块'],
            'midstream': ['BOPP', 'PET', 'PEN', '聚丙烯电容膜', '聚酯薄膜', '金属化膜', '薄膜电容器', '大功率薄膜电容', '金属化膜技术', '高性能复合薄膜技术'],
            'downstream': ['新能源汽车', '光伏储能', '5G 通信', '工业机器人伺服系统', '光伏逆变器', '车载充电器（OBC）', 'DC-DC 转换器', '逆变器', '空调压缩机'],
            'ecosystem': ['800V 高压平台', '第三代半导体器件', '超薄化', '纳米复合技术', '耐高温技术', '智能化与集成化', '长三角产业集群'],
        },
        'related_concepts': ['薄膜电容器', 'BOPP', 'PET', 'PEN', 'PPS', '金属化膜', '新能源汽车', '光伏储能', '5G 通信', '800V 高压平台'],
        'evidence': [
            {'heading': '材料体系', 'text': '报告重点关注 BOPP、PET、PEN 等主要薄膜类型的发展现状与趋势。'},
            {'heading': '应用需求', 'text': '新能源汽车领域单车薄膜电容用量是传统燃油车的 5-8 倍，主要应用于 OBC、DC-DC 转换器、逆变器、空调压缩机等关键部件。'},
            {'heading': '设备环节', 'text': '电容薄膜生产设备主要包括双向拉伸机组、精密分切装备、真空镀膜系统三大核心设备。'},
            {'heading': '辅助材料', 'text': '电容薄膜生产所需的辅助材料包括电极材料、引线端子、封装树脂、抗氧剂、阻燃剂等功能性助剂。'},
            {'heading': '竞争格局', 'text': '法拉电子与江海股份作为中国电容器用薄膜行业双雄，2024 年合计占据国内高端薄膜市场份额达 43.7%。'},
        ],
    },
    '光伏铜粉产业新变化与新格局研究分析': {
        'source_name': '光伏铜粉产业新变化与新格局研究分析',
        'source_date': '2026-01-29',
        'concept': '光伏铜粉',
        'supply_chain': {
            'upstream_materials': ['铜精矿', '废杂铜', '电解铜', '再生铜', '矿产铜', '阴极铜', '超细纳米铜粉'],
            'upstream_equipment': ['PERC 设备'],
            'midstream': ['光伏铜粉', '光伏铜浆', '银包铜浆料', '纯铜浆料', '电解铜粉', '水雾化铜粉', '球形铜粉', '气雾化法', '电解法', '化学还原法', '液相化学法', '粉体制备', '浆料配制'],
            'downstream': ['TOPCon', 'HJT', 'BC', 'PERC', '光伏电池制造', '太阳能电池栅线', '电池片生产', '光伏组件厂商'],
            'ecosystem': ['以铜代银', '铜电镀工艺', 'N 型电池', '光伏装机量', 'TOPCon + 钙钛矿', 'HJT + 钙钛矿'],
        },
        'related_concepts': ['HJT电池', 'TOPCON电池', 'BC电池', '银包铜浆料', '纯铜浆料', '铜电镀工艺', '以铜代银', '光伏银浆', '光伏电池'],
        'evidence': [
            {'heading': '产业定位', 'text': '光伏铜粉是光伏产业链中电池制造环节的关键材料，主要用于替代传统银浆作为电极材料。'},
            {'heading': '产品路线', 'text': '光伏铜粉的应用主要分为银包铜浆料和纯铜浆料两大类型。'},
            {'heading': '产业链结构', 'text': '上游主要包括铜精矿、废杂铜及电解铜等原材料供应，中游涉及雾化法、电解法、化学还原法等多种制粉工艺，下游应用主要集中在光伏电池制造领域。'},
            {'heading': '核心供应商', 'text': '铜粉制造环节主要供应商包括博迁新材、江南新材等 A 股上市公司，浆料制造环节聚和材料和帝科股份是两大领军企业。'},
            {'heading': '技术渗透', 'text': '铜电镀工艺的渗透率预计从 2025 年 15% 提升至 2030 年 40%。'},
        ],
    },
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


def item_count(ctx: dict) -> int:
    return sum(len(v or []) for v in (ctx.get('supply_chain') or {}).values())


def main() -> None:
    data = json.loads(TARGET.read_text(encoding='utf-8'))
    reports = data['reports']
    backup = TARGET.with_name('report_contexts.backup-fullmd-context-refine-batch6-' + datetime.now().strftime('%Y%m%d%H%M%S') + '.json')
    shutil.copy2(TARGET, backup)
    changed = []
    for source, ctx in UPDATES.items():
        old = reports.get(source, {})
        ctx['evidence'] = merge_evidence(ctx.get('evidence') or [], old.get('evidence') or [])
        reports[source] = ctx
        changed.append({
            'source': source,
            'old_items': item_count(old),
            'new_items': item_count(ctx),
            'old_evidence': len(old.get('evidence') or []),
            'new_evidence': len(ctx.get('evidence') or []),
            'related': len(ctx.get('related_concepts') or []),
        })
    data['updated'] = datetime.now().date().isoformat()
    tmp = TARGET.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    tmp.replace(TARGET)
    json.loads(TARGET.read_text(encoding='utf-8'))
    print(json.dumps({'backup': str(backup), 'changed': changed}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
