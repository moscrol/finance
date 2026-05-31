#!/usr/bin/env python3
import json
import re
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
AUDIT = WIKI / 'raw/theme-radar/missing-wikilinks-audit.json'
OUT_JSON = WIKI / 'raw/theme-radar/missing-wikilinks-manual-decision.json'
OUT_MD = WIKI / 'raw/theme-radar/missing-wikilinks-manual-decision.md'
LIMITS = {
    'alias_candidate': 80,
    'concept_candidate_high_freq': 80,
    'concept_candidate_review': 80,
    'report_source_backlink': 20,
    'noise_delete_link': 30,
}

CREATE_CONCEPT = {
    '国产替代', 'CPU', 'ASIC', '连锁药房', '通用航空', '铝箔', '医疗服务', '算力服务', 'HJT', '电网设备',
    '小金属', '电子材料', '行业应用软件', '光伏支架', '光伏辅材', '直升机', '高铁', '石油', '文旅IP运营',
    '金融IT', '工业AI', 'CDMO', 'L3级自动驾驶', 'Low-E玻璃', '有色金属', '稀土永磁', '贵金属', '核聚变',
}
ALIAS_TO_EXISTING = {
    'SoC': 'SOC芯片',
    'PEEK上游': 'PEEK材料',
    'ASIC芯片': 'ASIC',
    'AI服务器产业链': 'AI服务器',
    '国产AI芯片': 'AI芯片',
    '钠电材料': '钠电池',
    '磷酸锰铁锂': '磷酸铁锂',
    'GPU芯片': 'GPU',
}
SOURCE_OR_REPORT_PATTERNS = ['研究报告', '电话会议', '晨报', '纪要', '深度报告']
NOISE_EXACT = {'产业链', '供应链重构', '产业链整合', '技术迭代', '核心标的', '受益标的', '待补充'}
BROAD_REVIEW = {'CDMO', 'CPU', 'ASIC', '国产替代', '医疗服务', '石油', '高铁', '直升机'}


def md_escape(value):
    return str(value).replace('|', '\\|').replace('\n', ' ')


def existing_index():
    idx = {}
    for sub in ['entities', 'concepts', 'sources']:
        for path in (WIKI / sub).glob('*.md'):
            if '.bak' not in path.name:
                idx[path.stem] = sub
    return idx


def infer_action(row, existing):
    target = row['target']
    category = row.get('category', '')
    if target in NOISE_EXACT:
        return 'noise_delete_link', '', '泛词/占位词，不建议保留 wikilink'
    if target in existing:
        return 'already_exists_reaudit', target, f'已有 {existing[target]} 页面，建议重跑/检查索引'
    if target in ALIAS_TO_EXISTING:
        page = ALIAS_TO_EXISTING[target]
        if page in existing or page in CREATE_CONCEPT:
            return 'alias_to_existing', page, '明确同义/上下位归一；保留显示文本'
        return 'manual_review', page, '建议 alias，但目标页尚不存在或需确认'
    if any(token in target for token in SOURCE_OR_REPORT_PATTERNS):
        return 'source_or_report', '', '像资料标题/报告引用，优先匹配 sources，不建 concept'
    if target in CREATE_CONCEPT:
        action = 'create_concept'
        rationale = '可独立承接产业/技术/行业研究'
        if target in BROAD_REVIEW:
            rationale += '；边界偏宽，需人工确认定义范围'
        return action, target, rationale
    if category == 'report_source_backlink':
        return 'source_or_report', '', 'report-source 残留，需查是否存在 source 标题差异'
    if category == 'noise_delete_link':
        return 'noise_delete_link', '', '审计已判定为噪音链接'
    if row.get('count', 0) >= 10 and category == 'alias_candidate':
        return 'manual_review', '', '高频 alias 但缺明确目标，需人工定边界'
    if row.get('count', 0) >= 4 and category in {'concept_candidate_high_freq', 'concept_candidate_review'}:
        return 'create_concept_review', target, '中高频候选，可考虑建概念但需确认是否泛词'
    if re.search(r'[A-Za-z0-9]', target) and row.get('count', 0) >= 2:
        return 'create_concept_review', target, '含技术缩写/型号，低频长尾候选，需人工确认'
    return 'manual_review', '', '低频或语义边界不清，暂不自动处理'


def main():
    data = json.loads(AUDIT.read_text(encoding='utf-8'))
    existing = existing_index()
    rows = []
    for category, limit in LIMITS.items():
        selected = [r for r in data['items'] if r.get('category') == category][:limit]
        for r in selected:
            action, target_page, rationale = infer_action(r, existing)
            rows.append({
                'target': r['target'],
                'count': r.get('count', 0),
                'category': category,
                'recommended_action': action,
                'target_page': target_page,
                'rationale': rationale,
                'examples': r.get('examples', [])[:3],
                'source_dirs': r.get('source_dirs', {}),
                'decision': '',
                'final_target_page': '',
                'notes': '',
            })
    rows.sort(key=lambda x: (-x['count'], x['category'], x['target']))
    summary = {}
    for r in rows:
        summary[r['recommended_action']] = summary.get(r['recommended_action'], 0) + 1
    result = {'summary': summary, 'total_rows': len(rows), 'rows': rows}
    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = [
        '# Missing Wikilinks Manual Decision Table', '',
        '用途：人工确认剩余 missing wikilink 的处理动作。只改 `decision`、`final_target_page`、`notes` 三列即可。', '',
        '建议动作：', '',
        '- `create_concept`：建概念页。',
        '- `create_concept_review`：可能建概念页，但需确认是否泛词/重复。',
        '- `alias_to_existing`：替换为已有页，建议保留显示文本。',
        '- `source_or_report`：匹配 sources 或保留待查，不建概念。',
        '- `noise_delete_link`：去掉双链。',
        '- `manual_review`：暂不自动处理。', '',
        '## Summary', '', '```json', json.dumps(summary, ensure_ascii=False, indent=2), '```', '',
        '## Decision Table', '',
        '| target | count | category | recommended_action | target_page | rationale | examples | decision | final_target_page | notes |',
        '|---|---:|---|---|---|---|---|---|---|---|',
    ]
    for r in rows:
        examples = '<br>'.join(f'`{e}`' for e in r['examples'])
        lines.append('| ' + ' | '.join([
            md_escape(r['target']), str(r['count']), md_escape(r['category']), md_escape(r['recommended_action']),
            md_escape(r['target_page']), md_escape(r['rationale']), md_escape(examples), '', '', ''
        ]) + ' |')
    OUT_MD.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps({'out_json': str(OUT_JSON), 'out_md': str(OUT_MD), 'total_rows': len(rows), 'summary': summary}, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
