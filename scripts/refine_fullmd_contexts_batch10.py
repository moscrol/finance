#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

TARGET = Path('/Users/lbq/Desktop/c c/知识库/wiki/relations/report_contexts.json')

UPDATES = {
    '照明设备产业新格局与供应链分析报告': {
        'source_name': '照明设备产业新格局与供应链分析报告',
        'source_date': '2026-01-29',
        'concept': '照明设备',
        'supply_chain': {
            'upstream_materials': ['蓝宝石衬底', '硅衬底', '碳化硅衬底', '图形化蓝宝石衬底（PSS）', '荧光粉', 'YAG 荧光粉', 'KSF 红粉', '有机硅树脂', '环氧树脂', '铝', '铜', '石墨烯', '碳纤维', 'PC', 'ABS', 'PMMA'],
            'upstream_equipment': ['MOCVD（金属有机化学气相沉积）设备', '光刻机', '蚀刻机', '固晶机', '焊线机', '高速固晶机', '驱动 IC', '电源管理芯片', 'LED 照明驱动芯片', 'LED 驱动电源', '通信模块'],
            'midstream': ['LED 芯片', '外延片', 'GaN 基蓝绿光外延片', 'AlGaInP 基红黄光外延片', 'LED 封装', '中游封装与模组', 'Mini LED', 'Micro LED', 'Mini POB（板上封装）', 'Mini COB（板上芯片封装）', '智能照明控制系统', '系统集成'],
            'downstream': ['住宅照明', '商业照明', '工业照明', '户外照明', '独立式', '照明灯具', '智能照明', '植物照明', '汽车照明', '车规显示', '离网照明'],
            'ecosystem': ['LED 技术', '物联网', '人工智能', '可见光通信', 'Matter 协议', 'WiFi', '蓝牙', 'Zigbee', 'AI 动态调光算法', '太阳能照明', '环保材料', '可回收组件'],
        },
        'related_concepts': ['LED照明', 'LED芯片', 'LED封装', 'Mini LED', 'Micro LED', '智能照明', 'MOCVD', '驱动IC', '电源管理芯片', 'Matter协议'],
        'evidence': [
            {'heading': '产业链结构', 'text': '照明设备产业链可分为上游原材料及芯片制造、中游封装与模组、下游应用与设备三大环节。'},
            {'heading': '上游芯片', 'text': '上游原材料及芯片制造环节包括衬底材料和 LED 芯片，衬底材料主要包括蓝宝石衬底、硅衬底和碳化硅衬底三种技术路线。'},
            {'heading': '芯片设备材料', 'text': 'LED 芯片制造需要 MOCVD 设备、光刻机、蚀刻机、固晶机、焊线机等专用设备，荧光粉和封装材料也是关键材料。'},
            {'heading': '封装模组', 'text': 'LED 封装是连接芯片与终端应用的关键环节，Mini/Micro LED 封装、Mini POB 和 Mini COB 是重要技术方向。'},
            {'heading': '智能化', 'text': '照明设备正从功能性产品向智能化、网络化综合解决方案转变，涉及 Matter 协议、通信模块、AI 动态调光算法和边缘计算。'},
        ],
    },
    '骨架膜产业新变化与新格局深度研究报告': {
        'source_name': '骨架膜产业新变化与新格局深度研究报告',
        'source_date': '2026-01-29',
        'concept': '骨架膜',
        'supply_chain': {
            'upstream_materials': ['陶瓷材料', '氧化铝', '氧化锆', '氮化硅', '聚合物材料', '聚酰亚胺 PI', '芳纶', 'PE/PP', '硫化物电解质材料', '纳米氧化锆产品', '聚烯烃（PE/PP）', '成孔剂', '增塑剂'],
            'upstream_equipment': ['等静压工艺', 'ALD 包覆技术', '相转化法', '挤出成型', '涂覆', '卷对卷连续化生产', '微波烧结', '纳米涂布'],
            'midstream': ['骨架膜', '陶瓷隔膜', '聚合物骨架膜', '复合骨架膜', '基膜制造', '涂覆加工', '复合工艺', '硫化物骨架膜', '超高孔隙率骨架膜', '固态电解质膜', '刚性骨架 + 柔性电解质'],
            'downstream': ['固态电池', '聚合物全固态电池', '有机 - 无机复合型全固态电池', '硫化物全固态电池', '半固态电池', '新能源汽车', '储能系统', '消费电子', '柔性电池', '可穿戴设备'],
            'ecosystem': ['全固态电池标准体系建设指南', '全固态电池', '薄膜固态电池', '锂金属负极', '硅基负极', '高镍三元体系', '陶瓷电解质脆性问题', '锂枝晶', '热失控风险'],
        },
        'related_concepts': ['固态电池', '全固态电池', '半固态电池', '陶瓷隔膜', '聚合物骨架膜', '复合骨架膜', '硫化物电解质', '聚酰亚胺', '芳纶', '涂覆隔膜'],
        'evidence': [
            {'heading': '功能定义', 'text': '骨架膜作为固态电池的核心组件，从被动的离子通道转向主动的结构支撑和界面优化平台。'},
            {'heading': '产业链结构', 'text': '骨架膜产业链主要包括上游原材料供应、中游制造加工和下游应用三大环节。'},
            {'heading': '上游材料', 'text': '上游主要原材料包括陶瓷材料、聚合物材料以及硫化物电解质材料。'},
            {'heading': '中游工艺', 'text': '中游制造加工环节包括基膜制造、涂覆加工、复合工艺等关键步骤。'},
            {'heading': '技术路线', 'text': '骨架膜技术可分为陶瓷隔膜、聚合物骨架膜和复合骨架膜三大技术路线。'},
        ],
    },
    '海上风电产业投资价值分析报告': {
        'source_name': '海上风电产业投资价值分析报告',
        'source_date': '2026-01-29',
        'concept': '海上风电',
        'supply_chain': {
            'upstream_materials': ['钢材', '铝合金', '碳纤维', '玻璃纤维', '环氧树脂', '结构胶'],
            'upstream_equipment': ['叶片', '塔筒', '齿轮箱', '发电机', '轴承', '变流器', '传感器', '海缆', '风电铸件', '海底电缆', '塔筒和桩基', '导管架'],
            'midstream': ['海上风电整机制造', '工程建设', '风力发电机组', '海上风电场的设计', '海上施工', '安装调试', '海上升压站建设', '双馈', '直驱', '半直驱', '漂浮式基础技术'],
            'downstream': ['海上风电场', '运营维护', '电力销售', '设备状态监测', '故障检修', '定期维护', '远程预警', '居民用电', '工业用电', '商业用电'],
            'ecosystem': ['深远海', '机组大型化', '智能化运维技术', '直驱永磁技术', '柔性直流海缆', '海洋工程', '电气工程', '土木工程', '平准化度电成本（LCOE）'],
        },
        'related_concepts': ['风电', '海上风电', '风电叶片', '风电轴承', '海缆', '塔筒', '桩基', '直驱永磁', '柔性直流海缆', '漂浮式风电'],
        'evidence': [
            {'heading': '产业链架构', 'text': '海上风电产业链可以划分为上游原材料及零部件制造、中游整机制造与工程建设、下游运营维护与电力销售三大环节。'},
            {'heading': '上游构成', 'text': '上游基础原材料包括钢材、铝合金、碳纤维、玻璃纤维、环氧树脂、结构胶等，核心零部件包括叶片、塔筒、齿轮箱、发电机、轴承、变流器、传感器、海缆、风电铸件等。'},
            {'heading': '中游构成', 'text': '中游主要包括海上风电整机制造和工程建设，工程建设包括海上风电场的设计、海上施工、安装调试、海上升压站建设等。'},
            {'heading': '下游构成', 'text': '下游主要包括海上风电场的运营维护和电力销售，运营维护涵盖设备状态监测、故障检修、定期维护、远程预警等服务。'},
            {'heading': '核心环节', 'text': '整机、基础结构、海缆三大板块分别占比 45%、30%、15%，海缆环节呈现寡头垄断格局。'},
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
    backup = TARGET.with_name('report_contexts.backup-fullmd-context-refine-batch10-' + datetime.now().strftime('%Y%m%d%H%M%S') + '.json')
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
