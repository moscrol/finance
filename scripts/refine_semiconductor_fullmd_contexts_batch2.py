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
        '光模块产业新变化和新格局研究分析报告': {
            'source_name': '光模块产业新变化和新格局研究分析报告',
            'source_date': '2026-01-29',
            'concept': '光模块',
            'supply_chain': {
                'upstream_materials': ['磷化铟材料', '硅光材料', '光学透镜', '陶瓷套管', 'PCB/载板', '高速连接材料'],
                'upstream_equipment': ['光芯片制造设备', '耦合封装设备', '测试设备', '硅光工艺平台', '高速光模块测试平台'],
                'midstream': ['光芯片', '激光器芯片', '探测器芯片', 'PLC分路芯片', 'AWG波分芯片', '光器件', '硅光模块', 'LPO光模块', 'CPO', '400G光模块', '800G光模块', '1.6T光模块', '光模块制造'],
                'downstream': ['AI数据中心', '云厂商', '电信网络', '智能汽车', '东数西算', '运营商集采', '北美AI服务器'],
                'ecosystem': ['AI算力', '云计算', '共封装光学(CPO)', '硅光技术', 'LPO技术', '数据中心互联'],
            },
            'related_concepts': ['AI算力', '数据中心', '云计算', 'CPO', '硅光', 'LPO', '800G光模块', '1.6T光模块', '光芯片', '光器件', '东数西算'],
            'evidence': [
                {'heading': '产业链结构', 'text': '报告称光模块产业链从上游光材料、光芯片、光器件，到中游光模块制造，再到下游数据中心、电信网络与智能汽车。'},
                {'heading': '制造环节', 'text': '中际旭创、新易盛、光迅科技、华工科技等被报告列为光模块制造环节核心厂商。'},
                {'heading': '光芯片环节', 'text': '源杰科技、仕佳光子、光迅科技等对应高速光芯片、PLC/AWG和垂直整合能力。'},
                {'heading': '需求驱动', 'text': 'AI算力和数据中心是高速光模块需求的核心拉动，800G和1.6T进入快速迭代期。'},
            ],
        },
        '芯片IP产业新变化和新格局研究分析': {
            'source_name': '芯片IP产业新变化和新格局研究分析',
            'source_date': '2026-01-29',
            'concept': '芯片IP',
            'supply_chain': {
                'upstream_materials': ['基础工艺库', '标准单元库', '存储器编译器', '数模混合IP基础模块'],
                'upstream_equipment': ['EDA工具', 'IP验证工具', '仿真工具', '芯片设计环境', '工艺验证平台'],
                'midstream': ['处理器IP', 'CPU IP', 'GPU IP', 'NPU IP', 'DSP IP', '接口IP', '物理IP', '射频IP', '模拟IP', '数字IP', 'RISC-V IP', 'Chiplet解决方案'],
                'downstream': ['芯片设计公司', 'IDM厂商', '大型互联网公司', '汽车电子', '消费电子', '工业控制', 'AI芯片', 'SoC设计'],
                'ecosystem': ['ARM生态', 'RISC-V生态', '国产半导体IP', '芯片设计服务', 'AIGC芯片平台', '智慧出行芯片平台'],
            },
            'related_concepts': ['半导体IP', 'EDA', 'RISC-V', 'ARM', 'CPU', 'GPU', 'NPU', 'DSP', 'SoC', 'Chiplet', 'AI芯片', '汽车电子'],
            'evidence': [
                {'heading': '产业链架构', 'text': '报告称芯片IP产业链包括IP设计公司、EDA工具厂商、晶圆代工厂和封装测试厂。'},
                {'heading': '产品分类', 'text': '芯片IP主要分为处理器IP、接口IP、物理IP和数字IP，处理器IP包括CPU、GPU、NPU、DSP等。'},
                {'heading': '核心公司', 'text': '芯原股份、寒武纪、龙芯中科、全志科技、国科微、富瀚微、北京君正等被报告列为相关A股公司。'},
                {'heading': '国产化', 'text': '报告指出中国本土IP供应商份额提升，RISC-V和AI处理器IP是国产替代的重要方向。'},
            ],
        },
        '封测产业新变化与新格局深度研究报告': {
            'source_name': '封测产业新变化与新格局深度研究报告',
            'source_date': '2026-01-29',
            'concept': '封测',
            'supply_chain': {
                'upstream_materials': ['封装基板', 'ABF载板', 'ABF膜材料', '环氧塑封料EMC', '引线框架', '键合丝', '封装胶', '光刻胶/湿法材料'],
                'upstream_equipment': ['封装光刻机', '刻蚀机', '电镀设备', '测试机', '分选机', 'Bumping设备', 'RDL制造设备', 'TSV设备'],
                'midstream': ['晶圆减薄', '晶圆切割', '芯片贴装', '焊接键合', '塑封', '传统封装', '先进封装', '倒装芯片', 'WLP', 'Fan-Out', '2.5D/3D封装', 'SiP', 'Chiplet封装', 'OSAT封测服务'],
                'downstream': ['消费电子', '通信设备', '汽车电子', '工业控制', '人工智能', 'AI芯片', '5G基站', '数据中心', '新能源汽车'],
                'ecosystem': ['先进封装', 'Chiplet', 'HBM封装', '国产替代', 'China-for-China供应链', '长三角封测产业集群'],
            },
            'related_concepts': ['先进封装', 'Chiplet', 'HBM', 'ABF载板', '封装基板', 'Fan-Out', 'SiP', 'TSV', 'OSAT', '半导体设备', '半导体材料', 'AI芯片', '汽车电子'],
            'evidence': [
                {'heading': '产业定义', 'text': '报告称封测产业涵盖封装与测试两大环节，涉及晶圆减薄、切割、贴装、键合、塑封等工序。'},
                {'heading': '技术路线', 'text': '先进封装包括倒装芯片、WLP、2.5D/3D封装、SiP和Chiplet封装。'},
                {'heading': '垂直结构', 'text': '报告将上游分为封装材料、封装设备、半导体制造、IP及EDA工具；中游为OSAT封测服务；下游为消费电子、通信、汽车、工业和AI。'},
                {'heading': '材料设备', 'text': '封装基板、ABF载板、EMC、引线框架、键合丝及测试机、电镀设备、刻蚀设备是关键支撑。'},
            ],
        },
    }


def item_count(ctx: dict) -> int:
    return sum(len(v or []) for v in (ctx.get('supply_chain') or {}).values())


def main() -> None:
    data = json.loads(TARGET.read_text(encoding='utf-8'))
    reports = data.setdefault('reports', {})
    backup = TARGET.with_name('report_contexts.backup-fullmd-context-refine-batch2-' + datetime.now().strftime('%Y%m%d%H%M%S') + '.json')
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
