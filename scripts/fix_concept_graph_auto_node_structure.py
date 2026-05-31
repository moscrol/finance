import json
import re
import shutil
from datetime import date, datetime
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
REL = WIKI / 'relations'
THEME_DIR = WIKI / 'raw/theme-radar'
CONCEPT_GRAPH = REL / 'concept_graph.json'
RESULT = THEME_DIR / 'concept-graph-auto-node-structure-fix-result.json'
SOURCE = '[[theme-radar-db-quality-audit]]'
BACKUP_SUFFIX = '.bak-auto-node-structure-fix'

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

ANCHORS = {
    '人工智能': ['人工智能', 'AI', '算力'],
    '半导体': ['半导体', '芯片'],
    '通信': ['通信', '光通信'],
    '新能源': ['新能源', '储能'],
    '机器人': ['机器人'],
    '消费电子': ['消费电子'],
    '新材料': ['新材料'],
    '高端制造': ['高端制造'],
    '医药生物': ['医药生物'],
    '新兴技术': ['新兴技术'],
}


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def backup(path):
    bak = Path(str(path) + BACKUP_SUFFIX)
    shutil.copy2(path, bak)
    return str(bak.relative_to(WIKI))


def infer_parent(name):
    for parent, keys in DOMAIN_RULES:
        if any(key in name for key in keys):
            return parent
    return '新兴技术'


def tags_for(name):
    tags = set()
    for parent, keys in DOMAIN_RULES:
        for key in keys:
            if key in name:
                tags.add(parent)
                tags.add(key)
    for token in re.findall(r'[A-Za-z0-9]+', name):
        if len(token) >= 2:
            tags.add(token.upper())
    return tags


def company_names(node):
    names = set()
    for item in node.get('companies') or []:
        if isinstance(item, dict) and item.get('name'):
            names.add(str(item['name']))
    return names


def chain_layers(node):
    return set((node.get('supply_chain') or {}).keys())


def append_relation(graph, source, target, rel_type, confidence):
    row = {
        'from': source,
        'to': target,
        'type': rel_type,
        'source': SOURCE,
        'confidence': confidence or 'medium',
        'updated': date.today().isoformat(),
    }
    for existing in graph.get('relations') or []:
        if existing.get('from') == source and existing.get('to') == target and existing.get('type') == rel_type:
            return False
    graph.setdefault('relations', []).append(row)
    return True


def candidate_score(name, node, other_name, other_node, tag_cache, parent_cache):
    score = 0
    if parent_cache[name] != '新兴技术' and parent_cache[name] == parent_cache[other_name]:
        score += 6
    shared_tags = tag_cache[name] & tag_cache[other_name]
    score += min(len(shared_tags), 4) * 5
    shared_companies = company_names(node) & company_names(other_node)
    score += min(len(shared_companies), 3) * 4
    if chain_layers(node) & chain_layers(other_node):
        score += 2
    if len(name) >= 3 and len(other_name) >= 3 and (name in other_name or other_name in name):
        score += 4
    if other_node.get('companies'):
        score += 1
    return score


def infer_related(name, node, concepts, tag_cache, parent_cache):
    current = list(node.get('related_concepts') or [])
    seen = set(current)
    scored = []
    for other_name, other_node in concepts.items():
        if other_name == name or other_name in seen:
            continue
        score = candidate_score(name, node, other_name, other_node, tag_cache, parent_cache)
        if score > 0:
            scored.append((score, other_name))
    scored.sort(key=lambda item: (-item[0], item[1]))
    related = current[:]
    for _, other_name in scored[:5]:
        if other_name not in seen:
            related.append(other_name)
            seen.add(other_name)
        if len(related) >= 5:
            break
    if not related:
        parent = parent_cache[name]
        for anchor in ANCHORS.get(parent, []) + ANCHORS.get('新兴技术', []):
            if anchor in concepts and anchor != name and anchor not in seen:
                related.append(anchor)
                break
    return related[:5]


def main():
    graph = load(CONCEPT_GRAPH)
    concepts = graph.get('concepts') or {}
    backup_path = backup(CONCEPT_GRAPH)
    tag_cache = {name: tags_for(name) for name in concepts}
    parent_cache = {name: infer_parent(name) for name in concepts}
    auto_names = [name for name, node in concepts.items() if SOURCE in (node.get('sources') or [])]

    parent_added = 0
    related_added = 0
    relation_added = 0

    for name in auto_names:
        node = concepts[name]
        inferred_parent = parent_cache[name]
        parents = list(node.get('parents') or [])
        if inferred_parent and inferred_parent != '新兴技术' and inferred_parent not in parents:
            node['parents'] = [inferred_parent] + parents
            parent_added += 1
            if append_relation(graph, name, inferred_parent, '上位概念', node.get('confidence')):
                relation_added += 1
        related = infer_related(name, node, concepts, tag_cache, parent_cache)
        old_related = set(node.get('related_concepts') or [])
        if related and related != node.get('related_concepts'):
            node['related_concepts'] = related
            for target in related:
                if target not in old_related:
                    related_added += 1
                    if append_relation(graph, name, target, '相关', node.get('confidence')):
                        relation_added += 1

    write(CONCEPT_GRAPH, graph)
    result = {
        'timestamp': datetime.now().isoformat(timespec='seconds'),
        'source': SOURCE,
        'backup': backup_path,
        'auto_nodes': len(auto_names),
        'parent_added': parent_added,
        'related_added': related_added,
        'relation_added': relation_added,
    }
    write(RESULT, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
