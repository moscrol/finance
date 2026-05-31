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
        '晶圆代工产业新变化与新格局深度研究报告': {
            'source_name': '晶圆代工产业新变化与新格局深度研究报告',
            'source_date': '2026-01-29',
            'concept': '晶圆代工',
            'supply_chain': {
                'upstream_materials': ['12英寸硅片', '硅晶圆', '光刻胶', '电子特气', '靶材', 'CMP材料', '湿电子化学品', '封装材料'],
                'upstream_equipment': ['EUV光刻机', 'DUV光刻机', '刻蚀设备', '薄膜沉积设备', '清洗设备', '离子注入设备', 'CMP设备', '量检测设备'],
                'midstream': ['先进制程晶圆代工', '成熟制程晶圆代工', '3nm制程', '5nm制程', '7nm制程', '14nm制程', '28nm制程', '特色工艺', '车规芯片代工', 'AI芯片代工'],
                'downstream': ['AI芯片', '手机SoC', '汽车电子', '工业控制', '物联网', '功率器件', '射频芯片', '显示驱动芯片'],
                'ecosystem': ['先进制程竞争', '成熟制程国产替代', '半导体国产化', 'China-for-China供应链', '地缘供应链重构'],
            },
            'related_concepts': ['半导体设备', '半导体材料', '先进制程', '成熟制程', '中芯国际', '华虹半导体', 'AI芯片', '汽车电子', '光刻机', '硅片'],
            'evidence': [
                {'heading': '市场格局', 'text': '报告称台积电份额突破70%，中芯国际稳居第三，中国大陆产能扩张是核心变量。'},
                {'heading': '国产化', 'text': '硅片、设备、材料等关键环节均出现国产突破，设备国产化率预计提升。'},
                {'heading': '制程结构', 'text': '先进制程由AI驱动，成熟制程受汽车电子、工业控制等刚性需求支撑。'},
                {'heading': '上游供应', 'text': '硅片、光刻设备、刻蚀、清洗、CMP及材料是晶圆代工产业链关键支撑。'},
            ],
        },
        '超聚变产业新格局与供应链深度分析报告': {
            'source_name': '超聚变产业新格局与供应链深度分析报告',
            'source_date': '2026-01-29',
            'concept': '超聚变',
            'supply_chain': {
                'upstream_materials': ['DDR4/DDR5内存', '企业级SSD', '机械硬盘', '存储PCB', '服务器主板', '电源模块', '液冷材料', '高速连接器'],
                'upstream_equipment': ['服务器制造设备', '液冷系统', 'AI加速卡', '测试设备', '数据中心基础设施设备', '电源散热设备'],
                'midstream': ['通用服务器', 'AI服务器', '液冷服务器', 'FusionServer', '昆仑服务器', 'AI加速卡集成', '存储模组', '国产双路服务器', 'FusionOS服务器操作系统'],
                'downstream': ['AI算力基础设施', '数据中心', '政务云', '企业数字化', '算力租赁', '城企数智', '智慧能源', '全球企业客户'],
                'ecosystem': ['华为服务器传承', '国产服务器生态', 'openEuler', '液冷服务器生态', 'AI服务器国产替代', '河南国资产业平台'],
            },
            'related_concepts': ['液冷服务器', 'AI服务器', '算力租赁', '数据中心', '华为昇腾', '服务器电源', '企业级SSD', 'openEuler', '国产算力'],
            'evidence': [
                {'heading': '公司定位', 'text': '报告称超聚变继承华为服务器衣钵，是中国AI算力基础设施的重要厂商。'},
                {'heading': '市场地位', 'text': '报告称公司位居中国服务器市场第二、全球第六，AI服务器和液冷服务器为优势领域。'},
                {'heading': '供应链结构', 'text': '供应链呈系统集成商、核心器件供应商、上游原材料供应商三层结构。'},
                {'heading': '关键部件', 'text': 'CPU、内存、SSD、主控、接口芯片、存储PCB、AI加速卡和液冷系统构成关键环节。'},
            ],
        },
        '鸿蒙产业新变化与新格局全面分析报告': {
            'source_name': '鸿蒙产业新变化与新格局全面分析报告',
            'source_date': '2026-01-29',
            'concept': '鸿蒙',
            'supply_chain': {
                'upstream_materials': ['终端芯片', '传感器', '通信模组', '车载硬件', 'IoT模组', '安全芯片'],
                'upstream_equipment': ['操作系统开发工具', '应用开发框架', '分布式开发工具', '测试认证工具', '终端代工产线'],
                'midstream': ['HarmonyOS NEXT', 'OpenHarmony', '鸿蒙PC', '鸿蒙智行', '智能座舱系统', '鸿蒙应用开发', '政企信创软件', '终端ODM代工', '安全服务'],
                'downstream': ['智能手机', 'PC', '智能汽车', '智能家居', 'IoT设备', '政企信创', '金融IT', '智慧屏', '可穿戴设备'],
                'ecosystem': ['鸿蒙生态', '开发者生态', '华为终端生态', '鸿蒙智联', '超级终端', '星闪互联', '国产操作系统替代'],
            },
            'related_concepts': ['操作系统', 'OpenHarmony', 'HarmonyOS NEXT', '智能座舱', '信创', '金融IT', 'IoT', '智能汽车', '华为生态', '终端ODM'],
            'evidence': [
                {'heading': '产业机会', 'text': '报告称投资机会集中在操作系统开发、芯片制造、终端代工、智能座舱、金融信创和安全服务。'},
                {'heading': '生态规模', 'text': '报告称HarmonyOS 5/6终端设备数量快速提升，鸿蒙设备和开发者生态进入扩张期。'},
                {'heading': '技术演进', 'text': 'HarmonyOS NEXT实现全栈自研，鸿蒙6.0强化流畅度、协同能力和安全性。'},
                {'heading': '下游场景', 'text': '鸿蒙生态覆盖手机、PC、智能汽车、智能家居、IoT和政企信创等场景。'},
            ],
        },
    }


def item_count(ctx: dict) -> int:
    return sum(len(v or []) for v in (ctx.get('supply_chain') or {}).values())


def main() -> None:
    data = json.loads(TARGET.read_text(encoding='utf-8'))
    reports = data.setdefault('reports', {})
    backup = TARGET.with_name('report_contexts.backup-fullmd-context-refine-batch4-' + datetime.now().strftime('%Y%m%d%H%M%S') + '.json')
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
