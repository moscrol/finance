#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
TARGET = WIKI / 'relations/report_contexts.json'


def updates() -> dict:
    return {
        '汽车零部件产业新变化与新格局研究报告': {
            'source_name': '汽车零部件产业新变化与新格局研究报告',
            'source_date': '2026-01-29',
            'concept': '汽车零部件',
            'supply_chain': {
                'upstream_materials': ['钢铁', '有色金属', '电子元器件', '塑料', '橡胶', '玻璃', '陶瓷', '传感器材料'],
                'upstream_equipment': ['冲压设备', '压铸设备', '注塑设备', '焊接设备', '检测设备', '电子电气测试设备'],
                'midstream': ['动力系统', '底盘系统', '车身系统', '电子电气系统', '热管理系统', '线控制动', '智能座舱', '三电系统', 'Tier1系统集成', 'Tier2零部件', 'Tier3基础材料'],
                'downstream': ['整车制造', '新能源汽车', '智能汽车', '汽车维修服务', '零配件批发', '后市场服务'],
                'ecosystem': ['电动化', '智能化', '网联化', '共享化', 'Tier0.5供应商', '长三角汽车零部件集群', '珠三角智能终端与动力电池集群'],
            },
            'related_concepts': ['新能源汽车', '智能驾驶', '智能座舱', '线控底盘', '热管理', '汽车电子', '三电系统', '减速器', '传感器'],
            'evidence': [
                {'heading': '供应链层级', 'text': '报告称汽车零部件供应链形成Tier1、Tier2、Tier3分级体系。'},
                {'heading': '产业结构', 'text': '上游包括钢铁、有色金属、电子元器件、塑料、橡胶等，中游涵盖动力、底盘、车身和电子电气系统。'},
                {'heading': '结构变化', 'text': '新能源与智能化重塑供应链价值，三电系统和智能驾驶相关部件份额提升。'},
                {'heading': '区域集群', 'text': '长三角、珠三角形成汽车零部件产业集聚，珠三角在车载智能终端和动力电池领域突出。'},
            ],
        },
        '智能驾驶产业新格局与供应链深度研究报告': {
            'source_name': '智能驾驶产业新格局与供应链深度研究报告',
            'source_date': '2026-01-29',
            'concept': '智能驾驶',
            'supply_chain': {
                'upstream_materials': ['车载镜头', '激光雷达器件', '毫米波雷达器件', '传感器芯片', '车规级芯片', '连接器', '线控制动材料'],
                'upstream_equipment': ['传感器测试设备', '域控制器测试平台', '车规验证平台', '路测数据采集系统', '仿真训练平台'],
                'midstream': ['感知层', '激光雷达', '摄像头', '毫米波雷达', '超声波雷达', '高精度地图', 'AI芯片', '域控制器', '操作系统', '自动驾驶算法', '线控底盘', '智能座舱', '车路协同C-V2X'],
                'downstream': ['乘用车', '商用车', 'Robotaxi', '无人配送车', '矿区自动驾驶', '车路云一体化', 'L2辅助驾驶', 'L3/L4自动驾驶'],
                'ecosystem': ['单车智能', '车路云一体化', '城市NOA', '高速NOA', '无图化', 'L3合法上路', '智能网联汽车'],
            },
            'related_concepts': ['无人驾驶', 'L3级自动驾驶', '激光雷达', '毫米波雷达', '域控制器', '线控底盘', '智能座舱', '车路云一体化', 'Robotaxi'],
            'evidence': [
                {'heading': '产业链架构', 'text': '报告将智能驾驶产业链分为感知层、决策层、执行层、平台层及整车制造五大环节。'},
                {'heading': '感知层', 'text': '感知层包括激光雷达、摄像头、毫米波雷达、超声波雷达和高精度地图/GPS。'},
                {'heading': '决策层', 'text': '决策层包括AI芯片、域控制器、操作系统和高精地图，是技术壁垒最高环节。'},
                {'heading': '应用场景', 'text': '下游覆盖乘用车、商用车、Robotaxi、无人配送、矿区自动驾驶和车路云一体化。'},
            ],
        },
        '铜箔产业新变化与新格局研究分析报告': {
            'source_name': '铜箔产业新变化与新格局研究分析报告',
            'source_date': '2026-01-29',
            'concept': '铜箔',
            'supply_chain': {
                'upstream_materials': ['电解铜', '铜矿', '铜杆', '添加剂', '表面处理剂', 'PET基膜', 'PP基膜'],
                'upstream_equipment': ['阴极辊', '生箔机', '表面处理设备', '分切设备', '复合铜箔设备', '真空镀膜设备'],
                'midstream': ['电解铜箔', '锂电铜箔', 'PCB铜箔', '高频高速铜箔', 'HVLP铜箔', '极薄铜箔', '4.5μm铜箔', '复合铜箔', 'PET铜箔'],
                'downstream': ['动力电池', '储能电池', '消费电池', 'PCB', 'AI服务器', '数据中心', '5G通信', '新能源汽车'],
                'ecosystem': ['极薄化', '复合化', '锂电材料', 'PCB材料', 'AI服务器高频高速材料', '双碳', '新能源供应链'],
            },
            'related_concepts': ['锂电铜箔', '复合铜箔', 'PET铜箔', 'PCB铜箔', '高频高速铜箔', 'HVLP铜箔', '动力电池', '储能', 'AI服务器', 'PCB'],
            'evidence': [
                {'heading': '产业链', 'text': '报告称铜箔上游由铜原料供应主导，中游包括锂电铜箔、PCB铜箔和复合铜箔制造。'},
                {'heading': '技术路线', 'text': '技术路线呈现极薄化和复合化双轨并进，4.5μm及以下极薄铜箔渗透率提升。'},
                {'heading': '应用结构', 'text': '锂电铜箔占比约58.7%，PCB铜箔占比约41.3%，高频高速铜箔受AI服务器和数据中心拉动。'},
                {'heading': '竞争格局', 'text': '诺德股份、嘉元科技、铜冠铜箔等为锂电铜箔和PCB铜箔细分龙头。'},
            ],
        },
    }


def item_count(ctx: dict) -> int:
    return sum(len(v or []) for v in (ctx.get('supply_chain') or {}).values())


def main() -> None:
    data = json.loads(TARGET.read_text(encoding='utf-8'))
    reports = data.setdefault('reports', {})
    backup = TARGET.with_name('report_contexts.backup-fullmd-context-refine-batch5-' + datetime.now().strftime('%Y%m%d%H%M%S') + '.json')
    shutil.copy2(TARGET, backup)
    changed = []
    for key, ctx in updates().items():
        old = reports.get(key, {})
        reports[key] = ctx
        changed.append({'source': key, 'old_items': item_count(old), 'new_items': item_count(ctx), 'related': len(ctx['related_concepts']), 'evidence': len(ctx['evidence'])})
    data['updated'] = datetime.now().date().isoformat()
    tmp = TARGET.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    tmp.replace(TARGET)
    json.loads(TARGET.read_text(encoding='utf-8'))
    print(json.dumps({'backup': str(backup), 'changed': changed}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
