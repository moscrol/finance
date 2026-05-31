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
        'AI算力产业新格局与供应链深度研究报告': {
            'source_name': 'AI算力产业新格局与供应链深度研究报告',
            'source_date': '2026-01-29',
            'concept': 'AI算力',
            'supply_chain': {
                'upstream_materials': ['半导体IP', 'EDA工具', 'HBM/DRAM', 'NAND存储', 'ABF载板', 'PCB', '高速连接器', '电源管理芯片', '散热材料'],
                'upstream_equipment': ['芯片设计工具', '晶圆制造设备', '先进封装设备', '服务器制造设备', '液冷系统', '测试设备'],
                'midstream': ['GPU', 'ASIC', 'FPGA', 'NPU', 'AI芯片设计', '晶圆代工', '先进封装', 'AI服务器', '交换机', '光模块', '服务器电源', '液冷服务器'],
                'downstream': ['AI数据中心', '云厂商', '运营商', '金融', '电信', '互联网', '制造业', '政府算力平台', '大模型训练', '大模型推理'],
                'ecosystem': ['东数西算', '国产算力', 'CUDA生态', 'RISC-V生态', 'AI云服务', '智算中心', '算力租赁'],
            },
            'related_concepts': ['国产算力', 'AI芯片', 'GPU', 'ASIC芯片', 'NPU', '先进封装', 'HBM', 'AI服务器', '液冷服务器', '光模块', 'PCB', '数据中心', '云计算'],
            'evidence': [
                {'heading': '技术结构', 'text': '报告称GPU仍占AI芯片主导地位，ASIC成为增长最快的细分领域。'},
                {'heading': '上游核心', 'text': 'EDA、IP授权、芯片设计、封装测试构成AI算力上游与核心制造支撑。'},
                {'heading': '国产芯片', 'text': '海光信息、寒武纪等国产AI芯片企业在特定场景接近国际先进水平。'},
                {'heading': '系统环节', 'text': 'AI服务器、交换机、光模块、液冷、电源和PCB共同构成算力基础设施。'},
            ],
        },
        '华为算力产业深度研究：技术突破与供应链重构下的投资机会': {
            'source_name': '华为算力产业深度研究：技术突破与供应链重构下的投资机会',
            'source_date': '2026-01-29',
            'concept': '华为算力',
            'supply_chain': {
                'upstream_materials': ['ABF封装基板', 'PCB/高速背板', 'DRAM', 'NAND', 'HBM', '网卡芯片', '高速连接器', '液冷材料'],
                'upstream_equipment': ['晶圆代工设备', '先进封装设备', '服务器整机制造设备', '液冷系统', '高速互联测试设备'],
                'midstream': ['昇腾AI芯片', '鲲鹏CPU', '昇腾910C', 'Atlas超节点', 'TaiShan超节点', 'AI服务器', '服务器代工', '光模块', '液冷散热', '系统集成'],
                'downstream': ['政务', '金融', '交通', '制造', '智算中心', '华为云', '运营商', '行业大模型', '智慧城市'],
                'ecosystem': ['昇腾生态', '鲲鹏生态', 'MindSpore', 'CANN编译器', '国产算力供应链', '华为四位一体合作体系'],
            },
            'related_concepts': ['华为昇腾', '昇腾', '鲲鹏', '国产算力', 'AI服务器', '超节点', '液冷服务器', '光模块', 'ABF载板', 'PCB', 'MindSpore', '华为云'],
            'evidence': [
                {'heading': '价值分布', 'text': '报告称AI芯片在昇腾服务器中价值量约占60%，存储、CPU、网卡等共同构成硬件价值。'},
                {'heading': '中游制造', 'text': '华鲲振宇、拓维信息、神州数码等构成华为授权服务器制造生态。'},
                {'heading': '供应链', 'text': '中芯国际、兴森科技、深南电路、华丰科技、高澜股份分别对应代工、基板、连接器和液冷等关键环节。'},
                {'heading': '下游应用', 'text': '华为算力应用覆盖政务、金融、交通、制造等行业场景。'},
            ],
        },
        '模拟芯片产业新变化与新格局研究分析报告': {
            'source_name': '模拟芯片产业新变化与新格局研究分析报告',
            'source_date': '2026-01-29',
            'concept': '模拟芯片',
            'supply_chain': {
                'upstream_materials': ['硅晶圆', '光刻胶', '电子特气', '靶材', '封装材料', '高端光刻胶', '模拟工艺材料'],
                'upstream_equipment': ['光刻机', '刻蚀机', '薄膜沉积设备', '清洗设备', '测试设备', '成熟制程产线设备'],
                'midstream': ['模拟芯片设计', 'Fabless设计', '成熟制程晶圆代工', '电源管理芯片', '信号链芯片', 'ADC', 'DAC', '放大器', '接口芯片', '射频模拟芯片', 'BMS芯片'],
                'downstream': ['新能源汽车', '汽车电子', '工业控制', '通信基站', 'AI服务器', '数据中心', '消费电子', '机器人', '智能制造'],
                'ecosystem': ['国产模拟芯片替代', '汽车电动化', '工业自动化', '5G通信', 'AI服务器供电', '成熟制程国产化'],
            },
            'related_concepts': ['电源管理芯片', '信号链芯片', 'ADC', 'DAC', '汽车电子', '工业控制', 'AI服务器', '传感器', '半导体材料', '半导体设备', '晶圆代工'],
            'evidence': [
                {'heading': '产业链概览', 'text': '报告称模拟芯片产业链可分为上游材料设备、中游芯片设计制造、下游应用三大环节。'},
                {'heading': '上游材料设备', 'text': '硅晶圆、光刻胶、电子特气、靶材及光刻机、刻蚀机、薄膜沉积设备是关键支撑。'},
                {'heading': '中游制造', 'text': '国内模拟芯片企业多采用Fabless模式，制造端以中芯国际、华虹半导体等成熟制程代工为主。'},
                {'heading': '下游需求', 'text': '新能源汽车、AI与数据中心、5G通信、工业自动化推动电源管理和信号链芯片需求。'},
            ],
        },
    }


def item_count(ctx: dict) -> int:
    return sum(len(v or []) for v in (ctx.get('supply_chain') or {}).values())


def main() -> None:
    data = json.loads(TARGET.read_text(encoding='utf-8'))
    reports = data.setdefault('reports', {})
    backup = TARGET.with_name('report_contexts.backup-fullmd-context-refine-batch3-' + datetime.now().strftime('%Y%m%d%H%M%S') + '.json')
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
