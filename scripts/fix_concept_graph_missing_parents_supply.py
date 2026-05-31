#!/usr/bin/env python3
import json
import shutil
from datetime import date, datetime
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
REL = WIKI / 'relations'
THEME_DIR = WIKI / 'raw/theme-radar'
CONCEPT_GRAPH = REL / 'concept_graph.json'
RESULT = THEME_DIR / 'concept-graph-missing-parents-supply-fix-result.json'
SOURCE = '[[theme-radar-structure-fix]]'
BACKUP_SUFFIX = '.bak-missing-parents-supply-fix'

DOMAIN_RULES = [
    ('人工智能', ['AI', 'AIGC', '大模型', '算力', 'GPU', '推理', '智能体', 'Transformer', '机器学习', '数据中心', 'AI服务器', 'CAD', 'CAE', 'CAM', 'BIM', 'APM', 'ERP', 'DCS', 'DeFi', 'IT服务', 'IT基础', 'IT分销', '软件', '算法', '模型', '云', 'SaaS', 'PaaS']),
    ('半导体', ['半导体', '芯片', '制程', '晶圆', '封装', 'HBM', 'NAND', 'DRAM', '存储', 'EDA', '光刻', '先进制程', '载板', '硅片', '功率器件', 'SiC', 'IGBT', '5nm', '7nm', '2nm', '28nm', 'Chiplet', 'CIS', 'CPU', 'DCU', 'DDR', 'FPGA', 'GaN', 'HDI', 'IP核', 'IP授权', '堆叠', '光罩', '掩膜', '掩模', '光刻胶', '电子陶瓷']),
    ('通信', ['5G', '6G', '光模块', 'CPO', '光通信', '光纤', '铜缆', '以太网', '交换机', '卫星', '通信', '800G', '1.6T', '224G', '112G', 'AEC', 'ChaoJi', '物联网', '蜂窝']),
    ('新能源', ['电池', '储能', '光伏', '锂', '钠电', '固态电池', '充电', '800V', 'BMS', '正极', '负极', '隔膜', '氢能', '逆变器', '210尺寸', 'BIPV', 'CCUS', 'CTP', 'EVA', 'HJT', 'HVDC', '快充', '碳中和', '碳捕', '碳排']),
    ('机器人', ['机器人', '具身', '灵巧手', '减速器', '丝杠', '执行器', '伺服', '关节']),
    ('消费电子', ['手机', '折叠屏', 'OLED', 'Micro LED', '显示', 'MR', 'AR', 'VR', '可穿戴', '端侧', '8K', '超高清', '面板']),
    ('新材料', ['材料', '石英砂', '钛合金', '碳纤维', '陶瓷', '高分子', '树脂', '金属', '膜', '合金', '耐火', '化学品', '铜箔', 'CPI', '聚酰亚胺']),
    ('高端制造', ['机床', '工业母机', '设备', '制造', '检测', '量测', '数控', '机械', '大飞机', '航空', '航天', '高铁', 'C919', 'C929', 'FADEC', 'EPC', 'ITER', 'GW级']),
    ('医药生物', ['医药', '生物', '药物', 'ADC', 'CAR-T', '医疗', '器械', '诊断', '疫苗', '细胞', 'CDMO', 'CRO', 'DTP药房', 'FDA', 'IVD', 'GRAS']),
]

SUPPLY_BY_PARENT = {
    '人工智能': '应用/算力/软件',
    '半导体': '上游材料/设备/芯片制造',
    '通信': '设备/器件/网络',
    '新能源': '上游材料/中游制造/下游应用',
    '机器人': '核心零部件/本体/应用',
    '消费电子': '零部件/终端/应用',
    '新材料': '上游材料',
    '高端制造': '设备/整机/应用',
    '医药生物': '研发/生产/渠道',
    '新兴技术': '中游制造',
}


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def infer_parent(name):
    for parent, keys in DOMAIN_RULES:
        if any(key in name for key in keys):
            return parent
    return '新兴技术'


def append_relation(graph, source, target, rel_type, confidence):
    for existing in graph.get('relations') or []:
        if existing.get('from') == source and existing.get('to') == target and existing.get('type') == rel_type:
            return False
    graph.setdefault('relations', []).append({
        'from': source,
        'to': target,
        'type': rel_type,
        'source': SOURCE,
        'confidence': confidence or 'low',
        'updated': date.today().isoformat(),
    })
    return True


def main():
    graph = load(CONCEPT_GRAPH)
    backup = Path(str(CONCEPT_GRAPH) + BACKUP_SUFFIX)
    shutil.copy2(CONCEPT_GRAPH, backup)
    parents_added = 0
    supply_added = 0
    relations_added = 0
    for name, node in (graph.get('concepts') or {}).items():
        parent = infer_parent(name)
        if not node.get('parents'):
            node['parents'] = [parent]
            parents_added += 1
            if append_relation(graph, name, parent, '上位概念', node.get('confidence')):
                relations_added += 1
        effective_parent = (node.get('parents') or [parent])[0]
        if not node.get('supply_chain'):
            layer = SUPPLY_BY_PARENT.get(effective_parent) or SUPPLY_BY_PARENT['新兴技术']
            node['supply_chain'] = {layer: [name]}
            supply_added += 1
    write(CONCEPT_GRAPH, graph)
    result = {
        'timestamp': datetime.now().isoformat(timespec='seconds'),
        'backup': str(backup.relative_to(WIKI)),
        'parents_added': parents_added,
        'supply_added': supply_added,
        'relations_added': relations_added,
    }
    write(RESULT, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
