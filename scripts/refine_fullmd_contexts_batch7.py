#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

TARGET = Path('/Users/lbq/Desktop/c c/知识库/wiki/relations/report_contexts.json')

UPDATES = {
    '酒店餐饮产业新格局与供应链深度分析报告': {
        'source_name': '酒店餐饮产业新格局与供应链深度分析报告',
        'source_date': '2026-01-29',
        'concept': '酒店餐饮',
        'supply_chain': {
            'upstream_materials': ['农、林、牧、渔', '基础食材', '农产品', '肉类', '水产', '调味品', '基础调味品', '复合调味料'],
            'upstream_equipment': ['厨房设备', '洗涤设备', '制冷设备', '智能设备', '商用餐饮设备', '食品机械', '万能蒸烤箱', '智能薯条机器人', '燃气灶具', '洗碗机'],
            'midstream': ['食材加工', '调味品制造', '速冻食品', '预制菜', '中央厨房', '速冻米面', '速冻调制食品', '速冻菜肴制品', '冷冻烘焙食品', '酒店用品供应', '信息化系统'],
            'downstream': ['餐饮门店', '酒店', 'B 端客户', '终端消费者', '连锁餐饮企业', '团餐', '宴席'],
            'ecosystem': ['垂直整合', '数字化手段', '直采模式', '区域性直采', '酒店餐饮信息化', '一卡通系统', '消费管理系统'],
        },
        'related_concepts': ['餐饮供应链', '中央厨房', '预制菜', '速冻食品', '酒店用品', '餐饮信息化', '商用餐饮设备', '复合调味料'],
        'evidence': [
            {'heading': '产业链结构', 'text': '酒店餐饮产业链涵盖从原材料供应到终端消费的完整价值链，上游主要包括农、林、牧、渔等基础食材供应企业。'},
            {'heading': '中游环节', 'text': '中游涵盖食材加工、调味品制造、速冻食品、预制菜等供应商。'},
            {'heading': '下游客户', 'text': '下游连接餐饮门店、酒店等 B 端客户以及终端消费者。'},
            {'heading': '供应链趋势', 'text': '头部企业通过垂直整合和数字化手段提升供应链效率，中央厨房和直采模式成为重要趋势。'},
            {'heading': '信息化系统', 'text': '信息化系统是现代酒店餐饮企业运营管理的重要支撑，石基信息为酒店、餐饮、零售、休闲娱乐等大消费行业提供一体化信息系统解决方案。'},
        ],
    },
    '培育钻石产业新变化与新格局研究报告': {
        'source_name': '培育钻石产业新变化与新格局研究报告',
        'source_date': '2026-01-29',
        'concept': '培育钻石',
        'supply_chain': {
            'upstream_materials': ['碳（C）', '高纯石墨', '金属催化剂', '含碳气体', '高纯石墨粉', '金属触媒', 'Fe-Ni-Co 合金', '钻石晶种', '甲烷', '氢气', '钻石籽晶'],
            'upstream_equipment': ['六面顶压机', 'HPHT 设备', 'CVD 设备', 'MPCVD 设备', '自动化切割设备', '激光切割技术'],
            'midstream': ['HPHT 法', 'CVD 法', 'HPHT+CVD 混合法', '毛坯生产', '晶体生长', '切磨加工', '切割打磨', '培育钻石毛坯', '工业金刚石', '功能性金刚石'],
            'downstream': ['珠宝首饰', '工业应用', '机械加工', '切割工具', '建筑材料', '半导体', '半导体散热', '新能源汽车逆变器', '5G 基站射频模块', '光学', '量子计算'],
            'ecosystem': ['超硬材料', '中国主导上游', '印度垄断中游', '美国主导下游', '河南 HPHT 技术', '山东、江苏 CVD 技术', '出口管制', '后处理改色技术'],
        },
        'related_concepts': ['超硬材料', '功能性金刚石', 'HPHT', 'CVD', 'MPCVD', '半导体散热', '新能源汽车逆变器', '量子计算'],
        'evidence': [
            {'heading': '产业链格局', 'text': '产业链呈现“中国主导上游、印度垄断中游、美国主导下游”的格局。'},
            {'heading': '技术路径', 'text': '培育钻石产业形成了 HPHT 和 CVD 两大技术路径并行发展的格局。'},
            {'heading': '上游材料', 'text': '培育钻石上游原材料供应体系主要包括高纯石墨、金属催化剂、含碳气体等核心材料。'},
            {'heading': '生产设备', 'text': '培育钻石生产设备主要包括 HPHT 设备和 CVD 设备两大类，HPHT 核心设备是六面顶压机，CVD 主要是 MPCVD 设备。'},
            {'heading': '下游应用', 'text': '培育钻石的下游应用主要包括珠宝首饰、工业应用和新兴应用三大领域，半导体领域贡献了 62% 的工业需求增量。'},
        ],
    },
    '基因检测产业新变化和新格局深度研究报告': {
        'source_name': '基因检测产业新变化和新格局深度研究报告',
        'source_date': '2026-01-29',
        'concept': '基因检测',
        'supply_chain': {
            'upstream_materials': ['DNA', 'RNA', '蛋白质', '试剂耗材', '高端试剂', '关键试剂', '高端核心零部件'],
            'upstream_equipment': ['测序仪', '国产测序平台', 'Sanger', 'NGS', 'TGS', '单分子/纳米孔', '华大智造（MGI）'],
            'midstream': ['基因测序服务商', '基因检测', 'NIPT', '肿瘤基因检测', '遗传病检测', '消费级检测', '科研级', '伴随诊断', '早筛', '复发监测', '多组学整合'],
            'downstream': ['医疗机构', '药企', '个人用户', '疾病风险预测', '诊断', '治疗指导', '健康管理', '药物研发', '基础研究'],
            'ecosystem': ['精准医学中心', '国产替代', '医保覆盖', 'LDT 政策调整', '数据安全与伦理合规', 'AI 融合', '生成式生物智能'],
        },
        'related_concepts': ['NGS', 'NIPT', '肿瘤早筛', '伴随诊断', '遗传病检测', '消费级检测', '多组学', '精准医学', 'LDT'],
        'evidence': [
            {'heading': '产业定义', 'text': '基因检测以分子生物学技术为基础，通过分析个体 DNA、RNA、蛋白质等遗传物质信息，用于疾病风险预测、诊断、治疗指导及健康管理。'},
            {'heading': '技术分类', 'text': '技术历程包括第一代 Sanger、第二代 NGS、第三代单分子/纳米孔。'},
            {'heading': '应用场景', 'text': '应用场景分为临床级、消费级和科研级，临床级包括 NIPT、肿瘤、遗传病。'},
            {'heading': '产业链架构', 'text': '上游为测序仪、试剂耗材，中游为基因测序服务商，下游为医疗机构、药企、个人用户。'},
            {'heading': '技术趋势', 'text': '趋势包括 WGS 成本下降、国产突破、二代与三代结合、多组学整合以及 AI 融合。'},
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
    backup = TARGET.with_name('report_contexts.backup-fullmd-context-refine-batch7-' + datetime.now().strftime('%Y%m%d%H%M%S') + '.json')
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
