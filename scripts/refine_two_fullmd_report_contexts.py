#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
TARGET = WIKI / 'relations/report_contexts.json'


def context_updates() -> dict:
    return {
        '华为芯片产业新格局深度研究报告：自主可控突破与供应链重构': {
            'source_name': '华为芯片产业新格局深度研究报告：自主可控突破与供应链重构',
            'source_date': '2026-01-29',
            'concept': '华为芯片',
            'supply_chain': {
                'upstream_materials': ['12英寸半导体硅片', 'CMP抛光液', '铜及铜阻挡层抛光液', '半导体硅材料', '存储芯片/HBM材料配套'],
                'upstream_equipment': ['EDA工具', '板级EDA', '半导体IP授权', '刻蚀设备', '薄膜沉积设备', '清洗设备', '热处理设备', 'MOCVD设备', '光刻机整机'],
                'midstream': ['芯片设计', '晶圆代工', '14nm/7nm国产制程适配', '先进封装', '2.5D/3D封装', 'Chiplet封装', 'HBM封装', '麒麟SoC', '鲲鹏CPU', '昇腾AI芯片', '汽车芯片', '通信芯片', '海思芯片分销'],
                'downstream': ['智能终端', '智能汽车', 'AI云服务', 'ICT基础设施', '服务器', '家电与物联网模组', '数据中心', '运营商网络'],
                'ecosystem': ['鸿蒙生态', '鲲鹏生态', '昇腾生态', '国产半导体供应链', '华为海思授权代理体系', 'China-for-China供应链'],
            },
            'related_concepts': ['国产算力', '昇腾', '鲲鹏', 'AI芯片', '先进封装', 'Chiplet', 'HBM', 'EDA', '半导体设备', '半导体材料', '晶圆代工', '光刻机', '智能汽车', '鸿蒙生态', '国产替代'],
            'evidence': [
                {'heading': '业务架构', 'text': '华为芯片产业涵盖消费电子芯片、通信芯片、汽车芯片、服务器芯片四大板块。'},
                {'heading': '制造环节', 'text': '中芯国际被报告列为华为芯片制造环节重要合作伙伴。'},
                {'heading': '封装测试', 'text': '长电科技、通富微电、华天科技构成华为芯片封测主线。'},
                {'heading': '设备材料', 'text': '北方华创、中微公司、沪硅产业、安集科技、上海微电子/上海电气对应设备材料与光刻机环节。'},
            ],
        },
        '推理芯片产业新变化与新格局研究报告': {
            'source_name': '推理芯片产业新变化与新格局研究报告',
            'source_date': '2026-01-29',
            'concept': '推理芯片',
            'supply_chain': {
                'upstream_materials': ['半导体硅片', '电子气体', '靶材', '湿电子化学品', 'CMP抛光垫', 'CMP抛光液', '前驱体', 'SOD材料', 'KrF光刻胶'],
                'upstream_equipment': ['EDA工具', '半导体IP授权', '高性能接口IP', '光刻设备', '刻蚀设备', '薄膜沉积设备', '清洗设备', '离子注入设备', 'CMP抛光设备'],
                'midstream': ['推理芯片设计', 'GPU推理芯片', 'NPU推理芯片', 'ASIC推理芯片', '存算一体芯片', '晶圆代工', '先进封装', 'FOWLP封装', 'SiP封装', 'Chiplet封装', 'TSV/FOPLP封装'],
                'downstream': ['云端推理', '数据中心', '云计算平台', '边缘推理', '终端AI', '智能手机', '智能穿戴', '智能驾驶', '工业互联网', '智算中心'],
                'ecosystem': ['CUDA生态', '大模型推理', '生成式AI应用', '边缘计算', '国产AI芯片生态', '云厂商采购体系'],
            },
            'related_concepts': ['AI芯片', 'NPU', 'ASIC芯片', 'GPU', '存算一体', '云计算', '数据中心', '边缘计算', '智能驾驶', '先进封装', 'Chiplet', 'HBM', 'EDA', '半导体IP', '半导体设备', '半导体材料'],
            'evidence': [
                {'heading': '定义与分类', 'text': '推理芯片用于执行AI模型推理任务，包含云端、边缘和终端推理芯片。'},
                {'heading': '设计环节', 'text': '华为昇腾、寒武纪、海光信息、云天励飞、恒烁股份、龙芯中科、安凯微被列为相关设计企业。'},
                {'heading': '制造封测', 'text': '中芯国际、华虹集团承担国产晶圆制造；长电科技、通富微电、华天科技对应封测。'},
                {'heading': '材料设备', 'text': '沪硅产业、安集科技、鼎龙股份、江化微、雅克科技、彤程新材及国产设备企业构成支撑。'},
            ],
        },
    }


def count_items(ctx: dict) -> int:
    return sum(len(v or []) for v in (ctx.get('supply_chain') or {}).values())


def main() -> None:
    data = json.loads(TARGET.read_text(encoding='utf-8'))
    reports = data.setdefault('reports', {})
    backup = TARGET.with_name('report_contexts.backup-fullmd-context-refine-' + datetime.now().strftime('%Y%m%d%H%M%S') + '.json')
    shutil.copy2(TARGET, backup)
    changed = []
    for key, ctx in context_updates().items():
        old = reports.get(key, {})
        reports[key] = ctx
        changed.append({
            'source': key,
            'old_supply_chain_items': count_items(old),
            'new_supply_chain_items': count_items(ctx),
            'evidence_items': len(ctx.get('evidence') or []),
        })
    data['updated'] = datetime.now().date().isoformat()
    tmp = TARGET.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    tmp.replace(TARGET)
    json.loads(TARGET.read_text(encoding='utf-8'))
    print(json.dumps({'backup': str(backup), 'changed': changed}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
