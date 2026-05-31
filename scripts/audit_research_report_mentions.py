#!/usr/bin/env python3
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
ENTITIES = WIKI / 'entities'
OUT_JSON = WIKI / 'raw/theme-radar/research-report-mentions-audit.json'
OUT_MD = WIKI / 'raw/theme-radar/research-report-mentions-audit.md'

SECTION_HEADING_RE = re.compile(r'^(#{2,4})\s+(.+?)\s*$', re.M)
MENTION_PATTERNS = (
    '研究报告提及',
    '研报提及公司边际信息',
    '研究报告提及公司',
    '研究报告提及公司边际信息',
)
HARD_FACT_PATTERNS = (
    r'\d+(?:\.\d+)?\s*(?:%|亿元|万台|万套|万吨|GWh|MWh|MW|GW|家|个|项|条|台|套)',
    r'同比(?:增长|提升|下降)?\s*\+?\-?\d+',
    r'收入占比', r'市占率', r'市场份额', r'全球排名', r'国内排名', r'认证', r'进入.*供应链',
    r'客户.*(?:家|个|包括|覆盖)', r'订单', r'中标', r'量产', r'投产', r'产能', r'出货', r'良率',
    r'项目.*(?:交付|投产|落地|中标)', r'合同', r'绑定.*客户', r'白名单', r'AVL',
)
JUDGEMENT_PATTERNS = (
    '绝对龙头', '核心标的', '受益标的', '投资优势', '具有优势', '竞争优势', '不可替代',
    '有望', '可能', '值得关注', '受益', '弹性', '推荐', '看好', '空间', '逻辑',
    '产业链地位', '龙头', '领先地位', '重要标的', '相关标的',
)
TEMPLATE_PATTERNS = (
    '从既有entity markdown重建', '待补充', '研究报告提及公司边际信息',
    '**研究报告提及公司边际信息**', '**液冷服务器研究报告提及公司边际信息**',
)


def section_spans(text):
    matches = list(SECTION_HEADING_RE.finditer(text))
    spans = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        spans.append({'level': len(m.group(1)), 'title': m.group(2).strip(), 'start': start, 'end': end, 'text': text[start:end].strip()})
    return spans


def parent_h2(text, offset):
    h2 = None
    for m in re.finditer(r'^##\s+(.+?)\s*$', text, re.M):
        if m.start() <= offset:
            h2 = m.group(1).strip()
        else:
            break
    return h2 or ''


def classify(block):
    text = block['text']
    compact = re.sub(r'\s+', '', text)
    has_hard = any(re.search(p, text) for p in HARD_FACT_PATTERNS)
    has_judgement = any(p in text for p in JUDGEMENT_PATTERNS)
    template_score = sum(1 for p in TEMPLATE_PATTERNS if p in text)
    bullet_lines = [line for line in text.splitlines() if line.strip().startswith('-')]
    meaningful_bullets = [line for line in bullet_lines if '相关概念' not in line and '原文依据' not in line]
    meaningful_text = ''.join(meaningful_bullets)
    only_template = template_score and not meaningful_text.strip()
    thin_template = template_score and len(re.sub(r'\s+', '', meaningful_text)) < 40 and not has_hard
    if only_template or thin_template:
        return 'template_residue'
    if has_hard:
        return 'hard_fact_candidate'
    if has_judgement or len(meaningful_bullets) <= 2:
        return 'research_judgement_or_list'
    return 'review_needed'


def suggested_action(category, parent):
    if category == 'hard_fact_candidate':
        if parent == '高信度研究线索':
            return 'keep_in_high_confidence_review_sources'
        return 'review_then_migrate_to_high_confidence_if_supported'
    if category == 'research_judgement_or_list':
        return 'downgrade_to_graph_only_or_report_context'
    if category == 'template_residue':
        return 'cleanup_template_residue'
    return 'manual_review'


def audit():
    rows = []
    for path in sorted(ENTITIES.glob('*.md')):
        if '.bak' in path.name:
            continue
        text = path.read_text(encoding='utf-8', errors='ignore')
        if not any(p in text for p in MENTION_PATTERNS):
            continue
        spans = section_spans(text)
        for span in spans:
            if not any(p in span['text'] for p in MENTION_PATTERNS):
                continue
            parent = parent_h2(text, span['start'])
            category = classify(span)
            rows.append({
                'file': path.name,
                'entity': path.stem,
                'parent_section': parent,
                'heading': span['title'],
                'category': category,
                'suggested_action': suggested_action(category, parent),
                'line_estimate': text[:span['start']].count('\n') + 1,
                'snippet': span['text'][:700],
            })
    return rows


def write_outputs(rows):
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    summary = {
        'total_blocks': len(rows),
        'files': len(set(r['file'] for r in rows)),
        'by_category': dict(Counter(r['category'] for r in rows)),
        'by_parent_section': dict(Counter(r['parent_section'] for r in rows).most_common(30)),
        'by_action': dict(Counter(r['suggested_action'] for r in rows)),
    }
    payload = {'summary': summary, 'items': rows}
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    groups = defaultdict(list)
    for row in rows:
        groups[row['category']].append(row)
    lines = ['# 研究报告提及段落审计', '', '只分类，不直接改写实体。', '', '## Summary', '', '```json', json.dumps(summary, ensure_ascii=False, indent=2), '```', '']
    for category in ['hard_fact_candidate', 'research_judgement_or_list', 'template_residue', 'review_needed']:
        lines.append(f'## {category}')
        lines.append('')
        for row in groups.get(category, [])[:80]:
            snippet = re.sub(r'\s+', ' ', row['snippet'])[:220]
            lines.append(f"- `{row['file']}:{row['line_estimate']}` / {row['parent_section']} / {row['heading']} → {row['suggested_action']}：{snippet}")
        lines.append('')
    OUT_MD.write_text('\n'.join(lines), encoding='utf-8')
    return summary


def main():
    rows = audit()
    summary = write_outputs(rows)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f'WROTE {OUT_JSON}')
    print(f'WROTE {OUT_MD}')


if __name__ == '__main__':
    main()
