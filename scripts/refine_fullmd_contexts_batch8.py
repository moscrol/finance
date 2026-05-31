#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

TARGET = Path('/Users/lbq/Desktop/c c/知识库/wiki/relations/report_contexts.json')

UPDATES = {
    '光伏产业新变化和新格局深度分析报告': {
        'source_name': '光伏产业新变化和新格局深度分析报告',
        'source_date': '2026-01-29',
        'concept': '光伏',
        'supply_chain': {
            'upstream_materials': ['石英砂', '工业硅', '硅料', '多晶硅棒', '颗粒硅', 'N 型高纯硅料', 'N 型硅料', '透明背板', 'POE 胶膜', '新型边框'],
            'upstream_equipment': ['单轴跟踪系统', '逆变器', '集中式逆变器', '组串式逆变器', '微型逆变器', '光伏支架系统', '固定支架', '跟踪支架', '传感器技术', '控制系统', '驱动系统'],
            'midstream': ['硅片', '电池片', '组件', '系统集成', '改良西门子法', '硅烷流化床法', 'N 型硅片', 'TOPCon', 'HJT', 'BC', '双面组件', '大尺寸组件', '钙钛矿叠层电池'],
            'downstream': ['集中式光伏电站', '分布式光伏', '户用光伏', '工商业光伏', 'BIPV', '工商业屋顶', '幕墙', '采光顶', '公共设施', '地面电站'],
            'ecosystem': ['双碳目标', '分布式光伏整县推进政策', '建筑光伏一体化', 'P 型 PERC 技术', 'N 型高效技术', '叠层电池技术', '晶硅 - 钙钛矿叠层电池'],
        },
        'related_concepts': ['TOPCON电池', 'HJT电池', 'BC电池', '钙钛矿电池', 'BIPV', '分布式光伏', '集中式光伏', '光伏逆变器', '光伏支架', '颗粒硅'],
        'evidence': [
            {'heading': '产业链流程', 'text': '完整的产业链流程可概括为：石英砂→工业硅→硅料→硅片→电池片→组件→系统集成→应用。'},
            {'heading': '硅料路线', 'text': '硅料生产主要采用改良西门子法和硅烷流化床法，颗粒硅技术具有低能耗和低碳足迹优势。'},
            {'heading': '电池片技术', 'text': '电池片经历从 P 型 PERC 到 N 型 TOPCon、HJT、BC 的技术升级。'},
            {'heading': '组件封装', 'text': '组件技术创新体现在封装工艺、版型设计和智能化集成，透明背板、POE 胶膜、新型边框等材料提升可靠性和发电效率。'},
            {'heading': '下游系统', 'text': '下游包括集中式电站、分布式光伏和 BIPV，逆变器分为集中式、组串式和微型逆变器。'},
        ],
    },
    '无人出租车产业研究分析报告': {
        'source_name': '无人出租车产业研究分析报告',
        'source_date': '2026-01-29',
        'concept': '无人出租车产业',
        'supply_chain': {
            'upstream_materials': ['车规级零部件', '国产芯片', '传感器', '核心零部件', '进口零部件'],
            'upstream_equipment': ['激光雷达', '摄像头', '毫米波雷达', '超声波雷达', '高精度地图', '自动驾驶芯片', '域控制器', '线控底盘', '线控制动', '线控转向', '线控悬架', '执行器'],
            'midstream': ['Robotaxi', 'L3 级有条件自动驾驶', 'L4 级高度自动驾驶', '感知层', '决策层', '执行层', '纯视觉方案', '多传感器融合方案', '操作系统', '算法软件', '感知算法', '预测算法', '规划算法'],
            'downstream': ['Robotaxi 服务', '出租车服务', '试运营', '商业化运营', '一线城市', '新一线城市', '主副驾均无人 + 收费商业化运营', '出租车及网约车平台'],
            'ecosystem': ['车路云一体化', '智能网联汽车示范运营牌照', '商业运营牌照', '数据闭环体系', '轻资产 + AI 赋能', '规模化生产', '标准化设计', '国产供应商崛起'],
        },
        'related_concepts': ['Robotaxi', '无人驾驶', 'L3级自动驾驶', 'L4级自动驾驶', '激光雷达', '毫米波雷达', '高精度地图', '自动驾驶芯片', '域控制器', '线控底盘', '车路云一体化'],
        'evidence': [
            {'heading': '产业范围', 'text': '无人出租车产业涵盖从技术研发、车辆制造、运营服务到基础设施建设的完整产业链条。'},
            {'heading': '技术架构', 'text': '无人出租车的技术架构采用经典的“感知 - 决策 - 执行”三层架构。'},
            {'heading': '感知层', 'text': '感知层主要包括激光雷达、摄像头、毫米波雷达、超声波雷达和高精度地图。'},
            {'heading': '决策与执行', 'text': '决策层包括自动驾驶芯片、操作系统、算法软件和域控制器，执行层包括线控底盘、电控系统和执行器。'},
            {'heading': '技术路线', 'text': '当前无人出租车领域存在纯视觉方案和多传感器融合方案两条主要技术路线。'},
        ],
    },
    '火电改造产业深度研究：新格局、供应链重构与投资机会分析': {
        'source_name': '火电改造产业深度研究：新格局、供应链重构与投资机会分析',
        'source_date': '2026-01-29',
        'concept': '火电改造',
        'supply_chain': {
            'upstream_materials': ['煤炭', '天然气', '特种钢材', '高温合金', '核心零部件', '汽轮机叶片', '锅炉管', '高端阀门'],
            'upstream_equipment': ['锅炉', '汽轮机', '发电机', '环保设施', '控制系统', '低氮燃烧器', 'SCR 脱硝', '电除尘', '湿法脱硫', '湿式电除尘'],
            'midstream': ['主机设备制造', '辅机设备制造', '锅炉及燃烧系统改造', '低氮燃烧技术', '宽负荷燃烧技术', '生物质耦合燃烧', '汽轮机通流改造', '环保设施改造', '智能化控制系统改造'],
            'downstream': ['工程建设', 'EPC 总承包', '系统集成', '运维服务', '火电机组', '煤电机组', '智慧电厂解决方案'],
            'ecosystem': ['三改联动', '节能降碳改造', '灵活性改造', '供热改造', '新一代煤电升级专项行动', '超低排放改造', '数字孪生平台', 'CCUS'],
        },
        'related_concepts': ['电力', '储能', '特高压', '灵活性改造', '节能降碳改造', '供热改造', '超低排放改造', 'CCUS', '智慧电厂', '数字孪生'],
        'evidence': [
            {'heading': '技术路径', 'text': '当前火电改造主要包括“三改联动”，即节能降碳改造、灵活性改造和供热改造。'},
            {'heading': '产业链结构', 'text': '火电改造产业链呈现上游原材料供应、中游设备制造集成、下游工程实施与运营的三层结构。'},
            {'heading': '上游环节', 'text': '上游包括煤炭、天然气等能源资源，以及特种钢材、高温合金、核心零部件等原材料。'},
            {'heading': '中游环节', 'text': '中游涵盖主机设备制造和辅机设备制造，包括锅炉、汽轮机、发电机、环保设施、控制系统等。'},
            {'heading': '环保改造', 'text': '环保改造主流配置为“低氮燃烧器 + SCR 脱硝 + 电除尘 + 湿法脱硫 + 湿式电除尘”的核心组合。'},
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
    backup = TARGET.with_name('report_contexts.backup-fullmd-context-refine-batch8-' + datetime.now().strftime('%Y%m%d%H%M%S') + '.json')
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
