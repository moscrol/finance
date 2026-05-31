#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

TARGET = Path('/Users/lbq/Desktop/c c/知识库/wiki/relations/report_contexts.json')

UPDATES = {
    '稀土永磁产业新变化与新格局深度研究报告': {
        'source_name': '稀土永磁产业新变化与新格局深度研究报告',
        'source_date': '2026-01-29',
        'concept': '稀土永磁',
        'supply_chain': {
            'upstream_materials': ['稀土元素', '钕', '镨', '钐', '镝', '铁', '钴', '稀土矿', '稀土氧化物', '轻稀土', '中重稀土', '重稀土'],
            'upstream_equipment': ['溶剂萃取', '冶炼分离', '晶界扩散技术', '真空热处理'],
            'midstream': ['钐钴永磁体', '钕铁硼永磁体', '烧结钕铁硼', '粘结钕铁硼', '热压钕铁硼', '钐铁氮', '永磁材料', '功能材料制备', '重稀土减量化', '无重稀土磁体'],
            'downstream': ['新能源汽车', '风力发电', '消费电子', '工业电机', '航空航天', '驱动电机', '永磁同步电机', '永磁直驱风力发电机', '扬声器', '振动马达', '音圈马达'],
            'ecosystem': ['开采选矿', '循环回收', '稀土管理条例', '稀土开采总量控制指标', '800V 高压平台', '碳化硅电驱系统', 'IE5 超高效电机标准'],
        },
        'related_concepts': ['稀土', '钕铁硼', '烧结钕铁硼', '粘结钕铁硼', '钐钴永磁体', '钐铁氮', '晶界扩散技术', '新能源汽车', '风电', '工业电机'],
        'evidence': [
            {'heading': '材料定义', 'text': '稀土永磁材料是指以稀土元素（如钕、镨、钐、镝等）与过渡金属（铁、钴等）为基础，经加工制成的合金永磁材料。'},
            {'heading': '产业链结构', 'text': '稀土永磁产业链包括开采选矿、冶炼分离、功能材料制备、终端应用和循环回收 5 个核心环节。'},
            {'heading': '中游材料', 'text': '功能材料制备环节将稀土氧化物转化为钕铁硼、钐钴等永磁材料。'},
            {'heading': '下游应用', 'text': '下游应用领域广泛分布于新能源汽车、风力发电、消费电子、工业电机、航空航天等领域。'},
            {'heading': '技术趋势', 'text': '晶界扩散技术的应用使重稀土用量降低 30%-70%，钐铁氮作为第四代稀土永磁材料正在崛起。'},
        ],
    },
    '油运产业深度研究报告：十六年熊市后的历史性拐点': {
        'source_name': '油运产业深度研究报告：十六年熊市后的历史性拐点',
        'source_date': '2026-01-29',
        'concept': '油运产业',
        'supply_chain': {
            'upstream_materials': ['原油', '成品油', '液化天然气（LNG）', '化学品', '船用钢材', '特种钢材', '有色金属', '电子设备', '高强度船板', '高性能 9Ni 钢板'],
            'upstream_equipment': ['油轮', 'VLCC', '苏伊士型油轮', '阿芙拉型油轮', '巴拿马型油轮', '船用发动机', '推进系统', '导航设备', '安全设备', '船用柴油机', '螺旋桨', '废气洗涤系统'],
            'midstream': ['原油运输', '成品油运输', 'LNG 运输', '化学品运输', '油运服务层', '船舶运营层', '船舶制造层', '核心设备层', '原材料供应层', '长期期租（COA）模式', '短期现货经营模式', '光船租赁模式'],
            'downstream': ['石油公司', '亚太地区', '中国', '印度', '中东 - 中国航线', '美湾至亚洲航线', '南美到亚洲航线', '内贸原油运输', '外贸油轮船队'],
            'ecosystem': ['地缘政治风险溢价', 'OPEC + 增产', '船队供给刚性', '老旧船舶淘汰', 'IMO 2020 限硫令', 'LNG 双燃料技术', '甲醇燃料技术', '氨燃料技术', '氢燃料技术', '燃料电池技术', '碳捕捉技术（CCUS）'],
        },
        'related_concepts': ['VLCC', 'LNG运输', '船舶制造', '船用柴油机', '船用钢材', 'LNG双燃料', '甲醇燃料', '氨燃料', '氢燃料', 'CCUS'],
        'evidence': [
            {'heading': '产业定义', 'text': '油运产业是指以船舶为运输工具，从事原油、成品油、液化天然气（LNG）等液态能源产品海上运输的产业。'},
            {'heading': '船型结构', 'text': '油轮船队主要包括超大型油轮（VLCC）、苏伊士型油轮、阿芙拉型油轮和巴拿马型油轮等。'},
            {'heading': '产业链层次', 'text': '供应链格局包括油运服务层、船舶运营层、船舶制造层、核心设备层和原材料供应层。'},
            {'heading': '核心设备', 'text': '核心设备层涵盖船用发动机、推进系统、导航设备、安全设备等关键部件。'},
            {'heading': '技术路线', 'text': '过渡性清洁能源技术主要包括 LNG 双燃料、甲醇、氨燃料等，革命性零碳技术包括氢燃料、燃料电池、碳捕捉技术（CCUS）等。'},
        ],
    },
    '中国盾构机产业新格局与投资机会深度研究报告': {
        'source_name': '中国盾构机产业新格局与投资机会深度研究报告',
        'source_date': '2026-01-29',
        'concept': '中国盾构机',
        'supply_chain': {
            'upstream_materials': ['高端钢材', '特种钢材', '高碳高铬合金钢', '硬质合金', '碳化钨', '金刚石复合片', '高性能合金材料', '高端特种钢材'],
            'upstream_equipment': ['主轴承', '液压系统', '液压油缸', '高压油缸', '电液比例阀', '刀具系统', '盾构刀具', '密封件', '电气控制系统', '驱动电机', '盾体', '刀盘结构件'],
            'midstream': ['盾构机', 'TBM', '整机制造', '硬岩隧道掘进机', '智能化盾构机', '土压平衡盾构', '泥水平衡盾构', '超大直径盾构机', '高原型 TBM', '智能掘进脑', '数字孪生盾构系统', 'AI 地质识别技术'],
            'downstream': ['地铁隧道', '水工隧道', '越江隧道', '铁路隧道', '城市轨道交通', '水利工程', '地下综合管廊', '跨海隧道', '交通基建施工企业', '专业工程设备租赁商'],
            'ecosystem': ['国产化率提升至 95%', '一带一路', '智能化', '数字化', '无人化掘进', '换刀机器人', '设备租赁', '绿色化', '永磁同步电机技术', 'AI 能效管理系统'],
        },
        'related_concepts': ['盾构机', 'TBM', '主轴承', '液压系统', '盾构刀具', '数字孪生', '智能制造', '地下管网', '城市轨道交通', '水利工程'],
        'evidence': [
            {'heading': '产业机会', 'text': '产业链投资机会集中在整机制造、核心零部件国产替代、原材料供应链优化、智能化配套服务四大环节。'},
            {'heading': '整机制造', 'text': '中国盾构机整机制造环节呈现高度集中的竞争格局，中铁工业和铁建重工两大龙头企业占据国内 80% 以上的市场份额。'},
            {'heading': '核心零部件', 'text': '核心零部件主要包括液压系统、主轴承、刀具系统、密封件、电气控制系统等。'},
            {'heading': '原材料', 'text': '盾构机制造对原材料要求极高，上游原材料包括高碳高铬合金钢、硬质合金、碳化钨、金刚石复合片等关键材料。'},
            {'heading': '下游应用', 'text': '盾构机下游应用主要包括地铁隧道、水工隧道、越江隧道、铁路隧道等基础设施建设。'},
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
    backup = TARGET.with_name('report_contexts.backup-fullmd-context-refine-batch9-' + datetime.now().strftime('%Y%m%d%H%M%S') + '.json')
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
