#!/usr/bin/env python3
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
ENTITIES = WIKI / 'entities'
CONCEPTS = WIKI / 'concepts'
SOURCES = WIKI / 'sources'
OUT_JSON = WIKI / 'raw/theme-radar/missing-wikilinks-audit.json'
OUT_MD = WIKI / 'raw/theme-radar/missing-wikilinks-audit.md'
ACTION_JSON = WIKI / 'raw/theme-radar/missing-wikilinks-action-queue.json'

NOISE_EXACT = {
    'A股', 'B股', '港股', '美股', '上市公司', '公司', '企业', '核心标的', '龙头', '受益标的',
    '上游', '中游', '下游', '上游材料', '中游制造', '下游应用', '产业链供应商', '待补充',
    '中国', '美国', '日本', '韩国', '德国', '欧洲', '东南亚', '全球',
    '产业链', '产业链整合', '供应链重构', '技术迭代',
}
NOISE_PATTERNS = (
    r'^\d{4}-\d{2}-\d{2}$', r'^\d{6}$', r'^https?://',
    r'^(第[一二三四五六七八九十]+|一|二|三|四|五|六|七|八|九|十)$',
)
TECH_ACRONYMS = {
    'SOC', 'SoC', 'Chiplet', 'AIGC', 'BIPV', 'CDMO', 'eVTOL', 'FPSO', 'NPU', 'CPU',
    'TOPCon', 'OLED', 'SOFC', 'AIoT', 'C919', 'CPO', 'GPU', 'ASIC', 'EDA', 'MCU',
    'IGBT', 'SiC', 'GaN', 'KrF', 'ArF', 'DUV', 'EUV', 'BBU', 'HVDC', 'SST',
}
REPORT_PATTERNS = (
    '研究报告', '深度研究', '全面分析', '产业分析', '投资机会', '新变化', '新格局', '研究分析报告', '产业链深度',
)
ALIAS_HINTS = {
    '国产算力': ['AI算力', '算力'],
    '国产替代': ['国产替代'],
    '钠离子电池': ['钠电池'],
    'SOC': ['SoC', 'AI芯片'],
    'AIDC': ['数据中心', 'AI数据中心'],
    'AI数据中心': ['数据中心', 'AI算力'],
    '服务器电源': ['AI服务器电源'],
    '光互联': ['光通信', 'CPO'],
    '智能驾驶': ['无人驾驶'],
    '机器人': ['人形机器人'],
    '固态变压器': ['SST'],
}


def iter_md_files():
    for base in [ENTITIES, CONCEPTS, SOURCES]:
        if not base.exists():
            continue
        for path in sorted(base.glob('*.md')):
            if '.bak' not in path.name:
                yield path


def target_index():
    targets = set()
    for path in iter_md_files():
        targets.add(path.stem)
    return targets


def normalize_target(raw):
    target = raw.split('|', 1)[0].split('#', 1)[0].strip()
    return target.strip()


def classify(target, count, examples, existing_targets):
    if not target:
        return 'noise_delete_link', 'empty_target'
    if target in TECH_ACRONYMS:
        return 'alias_candidate', 'tech_acronym_or_industry_term'
    if target in NOISE_EXACT or any(re.search(p, target) for p in NOISE_PATTERNS):
        return 'noise_delete_link', 'generic_or_invalid_link'
    if any(p in target for p in REPORT_PATTERNS) or target.endswith(('报告', '研报')):
        return 'report_source_backlink', 'looks_like_report_or_source_title'
    if target in ALIAS_HINTS:
        return 'alias_candidate', 'known_alias_hint'
    if count >= 5:
        return 'concept_candidate_high_freq', 'high_frequency_missing_target'
    if re.search(r'[A-Za-z]', target) and re.search(r'[\u4e00-\u9fff]', target):
        return 'alias_candidate', 'mixed_cn_en_alias_candidate'
    if len(target) <= 1:
        return 'noise_delete_link', 'too_short'
    if count >= 2:
        return 'concept_candidate_review', 'repeated_missing_target'
    return 'low_freq_review', 'low_frequency_singleton'


def audit():
    existing = target_index()
    counts = Counter()
    example_files = defaultdict(list)
    source_dirs = defaultdict(Counter)
    for path in iter_md_files():
        text = path.read_text(encoding='utf-8', errors='ignore')
        rel = str(path.relative_to(WIKI))
        topdir = rel.split('/', 1)[0]
        for raw in re.findall(r'\[\[([^\]\n]+)\]\]', text):
            target = normalize_target(raw)
            if not target or target in existing:
                continue
            counts[target] += 1
            source_dirs[target][topdir] += 1
            if len(example_files[target]) < 5:
                example_files[target].append(rel)
    rows = []
    for target, count in counts.most_common():
        category, reason = classify(target, count, example_files[target], existing)
        rows.append({
            'target': target,
            'count': count,
            'category': category,
            'reason': reason,
            'suggested_alias_to': ALIAS_HINTS.get(target, []),
            'source_dirs': dict(source_dirs[target]),
            'examples': example_files[target],
        })
    return rows


def write_outputs(rows):
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    summary = {
        'unique_missing_targets': len(rows),
        'total_missing_link_occurrences': sum(r['count'] for r in rows),
        'by_category': dict(Counter(r['category'] for r in rows)),
        'top50': rows[:50],
    }
    payload = {'summary': summary, 'items': rows}
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    action_items = [r for r in rows if r['category'] in {'alias_candidate', 'concept_candidate_high_freq', 'report_source_backlink', 'noise_delete_link'}]
    ACTION_JSON.write_text(json.dumps({'summary': {'total': len(action_items), 'by_category': dict(Counter(r['category'] for r in action_items))}, 'items': action_items}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = ['# Missing Wikilinks Audit', '', '只分类，不直接创建概念或改链接。', '', '## Summary', '', '```json', json.dumps({k: v for k, v in summary.items() if k != 'top50'}, ensure_ascii=False, indent=2), '```', '']
    groups = defaultdict(list)
    for row in rows:
        groups[row['category']].append(row)
    for category in ['alias_candidate', 'concept_candidate_high_freq', 'report_source_backlink', 'noise_delete_link', 'concept_candidate_review', 'low_freq_review']:
        lines.append(f'## {category}')
        lines.append('')
        lines.append('| Target | Count | Reason | AliasTo | Examples |')
        lines.append('|---|---:|---|---|---|')
        for row in groups.get(category, [])[:80]:
            examples = '<br>'.join(row['examples'][:3])
            alias_to = '、'.join(row.get('suggested_alias_to') or [])
            lines.append(f"| {row['target']} | {row['count']} | {row['reason']} | {alias_to} | {examples} |")
        lines.append('')
    OUT_MD.write_text('\n'.join(lines), encoding='utf-8')
    return summary


def main():
    rows = audit()
    summary = write_outputs(rows)
    print(json.dumps({k: v for k, v in summary.items() if k != 'top50'}, ensure_ascii=False, indent=2))
    print(f'WROTE {OUT_JSON}')
    print(f'WROTE {OUT_MD}')
    print(f'WROTE {ACTION_JSON}')


if __name__ == '__main__':
    main()
