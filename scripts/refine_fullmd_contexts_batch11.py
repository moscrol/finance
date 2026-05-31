#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

TARGET = Path('/Users/lbq/Desktop/c c/知识库/wiki/relations/report_contexts.json')

UPDATES = {
    'PTA产业新变化与新格局深度研究报告': {
        'source_name': 'PTA产业新变化与新格局深度研究报告',
        'source_date': '2026-01-29',
        'concept': 'PTA',
        'supply_chain': {
            'upstream_materials': ['原油', '石脑油', 'MX（间二甲苯）', 'PX（对二甲苯）', '醋酸', '催化剂（钴、锰）', '促进剂（溴化物）', 'MEG（乙二醇）'],
            'upstream_equipment': ['催化重整', '芳烃抽提', '异构化', '空气氧化', '加氢精制', 'BP-Amoco 工艺', 'INVISTA（原 DuPont-ICI）工艺', '三井化学（MPC）工艺', 'INVISTA-8 技术'],
            'midstream': ['PTA（精对苯二甲酸）', '粗对苯二甲酸（CTA）', 'PTA 生产环节', '第四代 PTA 生产技术', '第三代 PTA 产能工艺', '聚酯（PET）', '聚酯切片', '涤纶长丝', '涤纶短纤', '聚酯瓶片', '聚酯薄膜'],
            'downstream': ['纺织服装', '包装', '电子电器', '服装服饰', '食品包装', '汽车内饰', '基建材料', '饮料 / 食品包装'],
            'ecosystem': ['石油化工 - 基础化工 - 高分子材料 - 终端应用', '原油 - 石脑油 - PX-PTA 工艺路线', '原油 - PX-PTA - 聚酯 全产业链', 'PTA 加工费', '产能利用率', '供需过剩', '双碳目标'],
        },
        'related_concepts': ['PX', 'PET', '聚酯', '涤纶长丝', '涤纶短纤', '瓶级聚酯', '聚酯薄膜', '石脑油', '芳烃', '乙二醇'],
        'evidence': [
            {'heading': '产业定位', 'text': 'PTA（精对苯二甲酸）作为聚酯产业链的核心中间体，是连接上游石油化工与下游纺织服装、包装等行业的重要枢纽。'},
            {'heading': '产业链结构', 'text': 'PTA 产业链呈现“石油化工 - 基础化工 - 高分子材料 - 终端应用”的垂直一体化特征。'},
            {'heading': '生产路径', 'text': 'PTA 为纯油制产品，只有原油 - 石脑油 - PX-PTA 这一条工艺路线。'},
            {'heading': '上游成本', 'text': 'PX 是 PTA 生产的核心原料，占 PTA 生产成本的 85% 以上，生产还需要醋酸、钴锰催化剂和溴化物促进剂。'},
            {'heading': '下游应用', 'text': '在中国市场，约 75% 的 PTA 用于生产聚酯纤维，20% 用于生产瓶级聚酯，5% 用于聚酯薄膜。'},
        ],
    },
    '耐火材料产业新格局深度研究报告：技术迭代驱动产业链重塑与投资机会分析': {
        'source_name': '耐火材料产业新格局深度研究报告：技术迭代驱动产业链重塑与投资机会分析',
        'source_date': '2026-01-29',
        'concept': '耐火材料',
        'supply_chain': {
            'upstream_materials': ['铝矾土', '菱镁矿', '石墨', '锆英砂', '电熔镁砂', '电熔刚玉', '尖晶石', '硅溶胶', '氧化铁', '氧化镁', '树脂', '结合剂', '添加剂'],
            'upstream_equipment': ['压机', '电炉', '隧道窑', '配套信息控制系统', '原料处理', '配料混合', '成型', '干燥', '烧成'],
            'midstream': ['定形耐火材料', '烧成砖', '电熔砖', '不定形耐火材料', '浇注料', '捣打料', '投射料', '耐火投射料', '火焰喷补料', '耐火可塑料', '低水泥浇注料', '超低水泥浇注料', '无水泥浇注料'],
            'downstream': ['钢铁行业', '水泥', '有色金属', '玻璃', '锅炉', '加热炉', '高温工业', '航空航天', '国防军工', '煤化工'],
            'ecosystem': ['无铬化与环保化', '轻量化与节能化', '智能化与功能化', '长寿化与高性能化', '纳米复合技术', '无铬环保型制品', '轻量化隔热材料', '智能感知耐火系统', '智能监测耐火材料', '全生命周期服务模式'],
        },
        'related_concepts': ['钢铁', '耐火材料', '铝矾土', '菱镁矿', '石墨', '电熔镁砂', '电熔刚玉', '陶瓷纤维', '无铬耐火材料', '智能监测耐火材料'],
        'evidence': [
            {'heading': '产业定位', 'text': '耐火材料作为高温工业的基础支撑材料，在钢铁、水泥、玻璃、有色金属等行业中发挥作用。'},
            {'heading': '产业链结构', 'text': '耐火材料产业链呈现“三段式”结构：上游原料供应、中游制造加工、下游应用需求。'},
            {'heading': '上游原料', 'text': '上游原料供应包括天然矿物原料（铝矾土、菱镁矿、石墨、锆英砂等）和人工合成原料（电熔镁砂、电熔刚玉、尖晶石等）。'},
            {'heading': '中游制造', 'text': '中游制造环节涵盖定形耐火材料和不定形耐火材料，制造工艺包括原料处理、配料混合、成型、干燥、烧成等关键环节。'},
            {'heading': '技术方向', 'text': '当前耐火材料技术发展呈现无铬化与环保化、轻量化与节能化、智能化与功能化、长寿化与高性能化四大方向。'},
        ],
    },
    'AI耳机产业新变化与新格局研究分析': {
        'source_name': 'AI耳机产业新变化与新格局研究分析',
        'source_date': '2026-01-29',
        'concept': 'AI耳机',
        'supply_chain': {
            'upstream_materials': ['软包锂电池', '钛合金框架', '玻璃', '陶瓷', '金属', '耳机外壳', '充电盒', '触控面板', '金属装饰件'],
            'upstream_equipment': ['AI 芯片', 'AI 加速器（NPU）', '蓝牙芯片', '射频前端模块', '扬声器', '麦克风', '音频编解码器', 'MEMS 麦克风', '电池管理系统（BMS）', '低功耗蓝牙芯片', 'UWB（超宽带）技术'],
            'midstream': ['TWS 耳机', 'AI 耳机', '声学组件', '无线通信模块', '电池与充电管理系统', '结构件与外观件', '整机组装', '智能音频模组', '多麦克风波束成形', 'AI 降噪算法'],
            'downstream': ['品牌销售', '个人智能音频设备', '会议转录', '同声传译功能', '儿童英语学习场景', '教育垂直领域', '电商直播场景', '车载语音助手', '智能音箱', '会议系统'],
            'ecosystem': ['芯片设计 - 声学组件 - 整机组装 - 品牌销售', '垂直整合趋势', '专业化分工', '生态协同', '语音识别', '自然语言处理', '主动降噪（ANC）', '空间音频', '蓝牙 5.3', 'LE Audio', 'LC3 编解码器', '多模态交互技术'],
        },
        'related_concepts': ['AI应用', 'TWS耳机', 'AI芯片', 'NPU', '蓝牙芯片', 'MEMS麦克风', 'BMS电池管理系统', '主动降噪', '空间音频', '语音识别'],
        'evidence': [
            {'heading': '供应链结构', 'text': 'AI 耳机供应链形成了“芯片设计 - 声学组件 - 整机组装 - 品牌销售”的完整产业链条。'},
            {'heading': '成本构成', 'text': 'AI 耳机的成本构成包括芯片、声学组件、电池与充电管理、结构件和其他组件。'},
            {'heading': '芯片环节', 'text': 'AI 芯片是 AI 耳机的“大脑”，需要集成专门的 AI 加速器（NPU）。'},
            {'heading': '声学组件', 'text': '声学组件主要包括扬声器、麦克风、音频编解码器，需要支持主动降噪、环境音通透、波束成形等功能。'},
            {'heading': '软件算法', 'text': '软件与算法主要包括语音识别、自然语言处理、降噪算法、音效处理等，是 AI 耳机实现智能化功能的核心。'},
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
    backup = TARGET.with_name('report_contexts.backup-fullmd-context-refine-batch11-' + datetime.now().strftime('%Y%m%d%H%M%S') + '.json')
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
