#!/usr/bin/env python3
import json
import re
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
IN_JSON = WIKI / 'raw/theme-radar/missing-wikilinks-manual-decision.json'
OUT_JSON = WIKI / 'raw/theme-radar/missing-wikilinks-manual-decision-autofilled.json'
OUT_MD = WIKI / 'raw/theme-radar/missing-wikilinks-manual-decision-autofilled.md'

HIGH_RISK_MANUAL = {
    '国产替代', 'CDMO', 'CPU', 'ASIC', '医疗服务', '石油', '高铁', '直升机', '硅', '大模型', '电容',
    '产能扩张', '储能系统', '商业模式', '行业景气', '需求增长', '成本下降', '供应链', '产业链',
}
AUTO_TECH_TOKENS = [
    '芯片', '电池', '光伏', '光刻', '封装', '材料', '雷达', '传感', '液冷', '热管理', '机器人', '控制器',
    '模组', '电源', '设备', '算法', '软件', '系统', '平台', '工艺', '玻璃', '铜箔', '膜', '医疗', '药',
    '金属', '航空', '电网', '支架', '辅材', '电机', '电容', '电感', '光纤', '光缆', '连接器', '服务器',
    '数据中心', '算力', '汽车', '座舱', '驾驶', '传动', '压缩机', '储能', '氢', '核', '合金', '陶瓷',
    '波导', '机床', '线缆', '电商', '科技', '制造', '通信', '工具', '碳化硅', '融合', '减速器',
    '叶片', '编辑', '半导体', '自动化', '钻石', '基因', '美容', '航空', '航天', '电力', '母机',
]
AUTO_INDUSTRY_TERMS = {
    '连锁药房', '通用航空', '铝箔', '算力服务', 'HJT', '电网设备', '小金属', '电子材料', '行业应用软件',
    '光伏支架', '光伏辅材', '文旅IP运营', '金融IT', '工业AI', 'Low-E玻璃', '有色金属', '稀土永磁', '贵金属',
    '核聚变', '原料药', '冷链物流', '冰雪旅游', '城市更新', '域控制器', '智能座舱', '盐湖提锂', '空芯光纤产业',
    '数控机床', '海底线缆', '煤炭', '跨境电商', '金融科技', '高端制造', '5G', 'IT服务', '军工电子',
    '化合物半导体', '增材制造', '工业自动化', '超级钻石产业', '进口替代', '6G通信', 'EDA工具',
    'SiC碳化硅', '军民融合', '减速器', '区块链', '单晶叶片', '卫星通信', '变压器', '口服美容',
    '基因编辑', '光波导', '垂直整合', '基建', '消费升级',
}
AUTO_SKIP_TOKENS = ['电话会议', '晨报', '纪要']
AUTO_NOISE_TOKENS = ['产业链', '产业链整合', '供应链重构', '技术迭代', '核心标的', '受益标的', '待补充']


def md_escape(value):
    return str(value).replace('|', '\\|').replace('\n', ' ')


def should_auto_create(row):
    target = row['target']
    if target in HIGH_RISK_MANUAL:
        return False
    if target in AUTO_INDUSTRY_TERMS:
        return True
    if row.get('recommended_action') == 'create_concept' and target not in HIGH_RISK_MANUAL:
        return True
    if row.get('recommended_action') == 'create_concept_review':
        if any(token in target for token in AUTO_TECH_TOKENS):
            return True
        if re.search(r'[A-Za-z][A-Za-z0-9+-]*', target) and row.get('count', 0) <= 6:
            return True
    return False


def fill_row(row):
    row = dict(row)
    target = row['target']
    recommended = row.get('recommended_action', '')
    if any(token in target for token in AUTO_SKIP_TOKENS):
        row['decision'] = 'source_or_report'
        row['final_target_page'] = ''
        row['notes'] = '像资料/纪要标题，不建概念'
        return row
    if target in AUTO_NOISE_TOKENS or recommended == 'noise_delete_link':
        row['decision'] = 'noise_delete_link'
        row['final_target_page'] = ''
        row['notes'] = '自动采纳噪音链接判断'
        return row
    if target in HIGH_RISK_MANUAL:
        row['decision'] = 'manual_review'
        row['final_target_page'] = ''
        row['notes'] = '高风险宽词/边界词，保留人工确认'
        return row
    if recommended in {'alias_to_existing', 'source_or_report'}:
        row['decision'] = recommended
        row['final_target_page'] = row.get('target_page', '')
        row['notes'] = '自动采纳低风险推荐动作'
        return row
    if should_auto_create(row):
        row['decision'] = 'create_concept'
        row['final_target_page'] = row.get('target_page') or target
        row['notes'] = '自动采纳：技术/行业/品类词，建待补证概念页'
        return row
    row['decision'] = 'manual_review'
    row['final_target_page'] = ''
    row['notes'] = '未命中自动规则，保留人工复核'
    return row


def write_md(result):
    lines = [
        '# Missing Wikilinks Manual Decision Autofilled', '',
        '用途：自动填充后的决策表。重点审核 `decision = manual_review` 的行。', '',
        '## Summary', '', '```json', json.dumps(result['summary'], ensure_ascii=False, indent=2), '```', '',
        '## Manual Review Rows', '',
        '| target | count | category | recommended_action | decision | final_target_page | rationale | examples | notes |',
        '|---|---:|---|---|---|---|---|---|---|',
    ]
    for r in result['rows']:
        if r.get('decision') != 'manual_review':
            continue
        examples = '<br>'.join(f'`{e}`' for e in r.get('examples', [])[:3])
        lines.append('| ' + ' | '.join([
            md_escape(r['target']), str(r['count']), md_escape(r['category']), md_escape(r['recommended_action']),
            md_escape(r['decision']), md_escape(r.get('final_target_page', '')), md_escape(r.get('rationale', '')), md_escape(examples), md_escape(r.get('notes', ''))
        ]) + ' |')
    lines.extend(['', '## All Rows', '', '| target | count | category | recommended_action | decision | final_target_page | notes |', '|---|---:|---|---|---|---|---|'])
    for r in result['rows']:
        lines.append('| ' + ' | '.join([
            md_escape(r['target']), str(r['count']), md_escape(r['category']), md_escape(r['recommended_action']),
            md_escape(r.get('decision', '')), md_escape(r.get('final_target_page', '')), md_escape(r.get('notes', ''))
        ]) + ' |')
    OUT_MD.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main():
    data = json.loads(IN_JSON.read_text(encoding='utf-8'))
    rows = [fill_row(r) for r in data['rows']]
    summary = {}
    for r in rows:
        summary[r['decision']] = summary.get(r['decision'], 0) + 1
    result = {'source': str(IN_JSON), 'total_rows': len(rows), 'summary': summary, 'rows': rows}
    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    write_md(result)
    manual = [r for r in rows if r['decision'] == 'manual_review']
    print(json.dumps({'out_json': str(OUT_JSON), 'out_md': str(OUT_MD), 'total_rows': len(rows), 'summary': summary, 'manual_review_top': manual[:30]}, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
