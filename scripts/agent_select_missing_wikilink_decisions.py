#!/usr/bin/env python3
import json
import re
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
IN_JSON = WIKI / 'raw/theme-radar/missing-wikilinks-manual-decision-autofilled.json'
OUT_JSON = WIKI / 'raw/theme-radar/missing-wikilinks-manual-decision-agent-selected.json'
OUT_MD = WIKI / 'raw/theme-radar/missing-wikilinks-manual-decision-agent-selected.md'

CREATE_ENTITY = {
    '中国铝业', '华为云', '特斯拉',
}
SOURCE_OR_REPORT = {
    '3D打印的第一性原理分析', '某PCB电话会议晨报',
}
NOISE = {
    '产业链', '产业链整合', '供应链重构', '技术迭代', '供应链', '组件', '产能扩张', '待补充',
}
ALIAS = {
    'SoC': 'SOC芯片',
    'ASIC芯片': 'ASIC',
    'SiC碳化硅': 'SiC',
    '氮化镓': 'GaN',
    'EDA工具': 'EDA（电子设计自动化）',
    'EDA软件': 'EDA（电子设计自动化）',
    '3C电子': '3C制造',
}

CONCEPT_EXACT = {
    '国产替代', 'CDMO', 'CPU', 'ASIC', '硅', '大模型', '电容', '储能系统', '复合调味料', '工程机械',
    '建材', '数据库', '电子化学品', '碳捕集', '稀土', '跨境支付', '偏光片', '特斯拉供应链',
    '中国低空经济', '中国盾构机', '体外诊断', '侵入式脑机接口', '充电模块', '农业', '出海', '包装纸',
    '医疗服务', '大尺寸硅片', '安防监控', '心血管器械', '换流阀', '显示驱动', '智慧交通', '智能化钻井',
    '林浆纸一体化', '柔性电子', '柔性电极', '沉淀法二氧化硅', '油服', '注塑机', '海洋防务', '深海',
    '特种纸', '环形锻件', '生猪养殖', '直升机', '石油', '石英砂', '硅片', '碳纳米管', '细胞治疗',
    '金融信创', '铜冶炼', '锂云母提锂', '食用菌', '餐饮供应链', '高铁', '3C制造', 'AI安全', 'APM软件',
    'BOPET薄膜', 'BOPP电容膜', 'C4化工', 'DLP技术', 'EBM技术', 'FDM技术', 'IC载板', 'IT分销',
    'IT基础设施服务', 'MLCC材料', 'PVD镀膜', 'SLAM算法', 'SLA技术', 'SLM技术', 'SLS技术', 'T/R芯片',
    'eVTOL电机', '临床前CRO', '光学级PET基膜', '动漫IP衍生品', '多模态AI', '嵌入式CPU', '开源3D打印',
    '政务AI', '汽车IT', '消费级3D打印', '细胞基因CDMO',
}

CREATE_BY_TOKEN = [
    '芯片', '电池', '光伏', '光刻', '封装', '材料', '雷达', '传感', '液冷', '热管理', '机器人', '控制器',
    '模组', '电源', '设备', '算法', '软件', '系统', '平台', '工艺', '玻璃', '铜箔', '膜', '医疗', '药',
    '金属', '航空', '电网', '支架', '辅材', '电机', '电容', '电感', '光纤', '光缆', '连接器', '服务器',
    '数据中心', '算力', '汽车', '座舱', '驾驶', '传动', '压缩机', '储能', '氢', '核', '合金', '陶瓷',
    '波导', '机床', '线缆', '电商', '科技', '制造', '通信', '工具', '碳化硅', '融合', '减速器', '叶片',
    '编辑', '半导体', '自动化', '钻石', '基因', '美容', '航天', '电力', '母机', '纸', '砂', '铝', '煤',
    '支付', '调味料', '数据库', '化学品', '捕集', '稀土', '机械', '防务', '养殖', '冶炼', '提锂', 'CRO',
]


def md_escape(value):
    return str(value).replace('|', '\\|').replace('\n', ' ')


def select(row):
    row = dict(row)
    target = row['target']
    if row.get('decision') != 'manual_review':
        row['agent_selected'] = False
        return row
    if target in NOISE:
        row.update(decision='noise_delete_link', final_target_page='', notes='agent-selected：泛词/催化动作词，不适合作为题材雷达节点')
    elif target in SOURCE_OR_REPORT or any(x in target for x in ['电话会议', '晨报', '纪要', '第一性原理分析']):
        row.update(decision='source_or_report', final_target_page='', notes='agent-selected：像资料标题或文章标题，不建概念')
    elif target in CREATE_ENTITY:
        row.update(decision='create_entity', final_target_page=target, notes='agent-selected：公司/品牌/平台主体，应入 entities 而非 concepts')
    elif target in ALIAS:
        row.update(decision='alias_to_existing', final_target_page=ALIAS[target], notes='agent-selected：明确同义/缩写归一，保留显示文本')
    elif target in CONCEPT_EXACT or any(token in target for token in CREATE_BY_TOKEN):
        row.update(decision='create_concept', final_target_page=target, notes='agent-selected：题材雷达需要可聚类的行业/技术/品类节点，建待补证概念页')
    elif re.search(r'[A-Za-z][A-Za-z0-9+/-]*', target):
        row.update(decision='create_concept', final_target_page=target, notes='agent-selected：英文缩写/技术短语，适合承接后续归一')
    else:
        row.update(decision='create_concept', final_target_page=target, notes='agent-selected：保守建待补证概念页，后续可再合并/降噪')
    row['agent_selected'] = True
    return row


def write_md(result):
    lines = [
        '# Missing Wikilinks Agent Selected Decisions', '',
        '原则：服务题材雷达排序/聚类/暴露识别；行业、技术、材料、产品、主题词优先保留为待补证概念；明显泛词、资料标题、主体实体分别转 noise/source/entity。', '',
        '## Summary', '', '```json', json.dumps(result['summary'], ensure_ascii=False, indent=2), '```', '',
        '## Agent Selected Rows', '',
        '| target | count | category | decision | final_target_page | notes | examples |',
        '|---|---:|---|---|---|---|---|',
    ]
    for r in result['rows']:
        if not r.get('agent_selected'):
            continue
        examples = '<br>'.join(f'`{e}`' for e in r.get('examples', [])[:3])
        lines.append('| ' + ' | '.join([
            md_escape(r['target']), str(r['count']), md_escape(r['category']), md_escape(r['decision']),
            md_escape(r.get('final_target_page', '')), md_escape(r.get('notes', '')), md_escape(examples),
        ]) + ' |')
    OUT_MD.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main():
    data = json.loads(IN_JSON.read_text(encoding='utf-8'))
    rows = [select(r) for r in data['rows']]
    summary = {}
    agent_selected = 0
    for r in rows:
        summary[r['decision']] = summary.get(r['decision'], 0) + 1
        if r.get('agent_selected'):
            agent_selected += 1
    result = {'source': str(IN_JSON), 'total_rows': len(rows), 'agent_selected_count': agent_selected, 'summary': summary, 'rows': rows}
    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    write_md(result)
    print(json.dumps({'out_json': str(OUT_JSON), 'out_md': str(OUT_MD), 'total_rows': len(rows), 'agent_selected_count': agent_selected, 'summary': summary}, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
