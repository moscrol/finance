#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
REL = WIKI / 'relations'
REPORT_CONTEXTS = REL / 'report_contexts.json'
ENTITY_EXPOSURES = REL / 'entity_exposures.json'
LAYERS = ['upstream_materials', 'upstream_equipment', 'midstream', 'downstream', 'ecosystem']
RICH_FIELDS = ['summary', 'demand_drivers', 'direction_scan', 'validation_checklist']
ALLOWED_CONTEXT_FACT_HARDNESS = {'', 'research_claim', 'review_candidate', 'market_narrative', 'unknown'}
ALLOWED_CONTEXT_EVIDENCE_LAYERS = {'', 'L1', 'L1_L3_candidate'}
FORBIDDEN_CONTEXT_SOURCE_QUALITY = {'official_disclosure', 'company_primary'}
FORBIDDEN_CONTEXT_UPDATE_TYPES = {'baseline', 'hard_delta'}
SENTENCE_MARKERS = ('。', '，', '；', '：', '报告称', '预计', '同比', '达到', '超过', '占比', '市占率')


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def load_entity_names() -> list[str]:
    if not ENTITY_EXPOSURES.exists():
        return []
    data = load_json(ENTITY_EXPOSURES)
    names = [str(name) for name in (data.get('entities') or {})]
    return sorted([name for name in names if len(name) >= 2], key=len, reverse=True)


def compact(text: str) -> str:
    return re.sub(r'\s+', '', str(text or ''))


def is_long_sentence(value: str) -> bool:
    text = str(value or '').strip()
    if len(text) >= 34:
        return True
    return len(text) >= 18 and any(token in text for token in SENTENCE_MARKERS)


def find_names(text: str, names: list[str], limit: int = 20) -> list[str]:
    body = str(text or '')
    found = []
    for name in names:
        if name in body:
            found.append(name)
            if len(found) >= limit:
                break
    return found


def add_issue(issues: list[dict], severity: str, category: str, source: str, message: str, detail: str = '') -> None:
    issues.append({'severity': severity, 'category': category, 'source': source, 'message': message, 'detail': detail})


def check_company_mentions(source: str, ctx: dict, names: list[str], issues: list[dict]) -> None:
    mentions = ctx.get('company_mentions')
    evidence_text = ' '.join(str(item.get('text', '')) for item in (ctx.get('evidence') or []) if isinstance(item, dict))
    evidence_names = find_names(evidence_text, names)
    if evidence_names and not mentions:
        add_issue(issues, 'WARNING', 'missing_company_mentions', source, 'evidence 提到公司但缺 company_mentions', '、'.join(evidence_names[:12]))
    if mentions is None:
        return
    if not isinstance(mentions, list):
        add_issue(issues, 'ERROR', 'schema', source, 'company_mentions must be a list')
        return
    for idx, row in enumerate(mentions):
        loc = f'company_mentions[{idx}]'
        if not isinstance(row, dict):
            add_issue(issues, 'ERROR', 'schema', source, f'{loc} must be object')
            continue
        company = str(row.get('company') or '').strip()
        if not company:
            add_issue(issues, 'ERROR', 'company_mentions', source, f'{loc} missing company')
        if not row.get('role'):
            add_issue(issues, 'WARNING', 'company_mentions', source, f'{loc} missing role')
        if not row.get('chain_layer'):
            add_issue(issues, 'WARNING', 'company_mentions', source, f'{loc} missing chain_layer')
        ev_text = str(row.get('evidence_text') or '').strip()
        if not ev_text:
            add_issue(issues, 'WARNING', 'company_mentions', source, f'{loc} missing evidence_text')
        elif compact(ev_text) not in compact(evidence_text):
            add_issue(issues, 'WARNING', 'company_mentions', source, f'{loc} evidence_text not found in ctx.evidence')
        hardness = str(row.get('fact_hardness') or '').strip()
        if hardness not in ALLOWED_CONTEXT_FACT_HARDNESS:
            add_issue(issues, 'ERROR', 'evidence_boundary', source, f'{loc} invalid fact_hardness={hardness}')
        layer = str(row.get('evidence_layer') or '').strip()
        if layer not in ALLOWED_CONTEXT_EVIDENCE_LAYERS:
            add_issue(issues, 'ERROR', 'evidence_boundary', source, f'{loc} invalid evidence_layer={layer}')
        source_quality = str(row.get('source_quality') or '').strip()
        if source_quality in FORBIDDEN_CONTEXT_SOURCE_QUALITY:
            add_issue(issues, 'ERROR', 'evidence_boundary', source, f'{loc} must not use source_quality={source_quality}')
        update_type = str(row.get('update_type') or '').strip()
        if update_type in FORBIDDEN_CONTEXT_UPDATE_TYPES:
            add_issue(issues, 'ERROR', 'evidence_boundary', source, f'{loc} must not use update_type={update_type}')


def check_context(source: str, ctx: dict, names: list[str]) -> list[dict]:
    issues: list[dict] = []
    if not isinstance(ctx, dict):
        add_issue(issues, 'ERROR', 'schema', source, 'context must be object')
        return issues
    if ctx.get('source_name') and ctx.get('source_name') != source:
        add_issue(issues, 'WARNING', 'schema', source, 'source_name differs from report_contexts key', str(ctx.get('source_name')))
    if not ctx.get('concept'):
        add_issue(issues, 'ERROR', 'schema', source, 'missing concept')
    if not isinstance(ctx.get('related_concepts'), list):
        add_issue(issues, 'ERROR', 'schema', source, 'related_concepts must be list')
    evidence = ctx.get('evidence')
    if not isinstance(evidence, list) or not evidence:
        add_issue(issues, 'ERROR', 'schema', source, 'missing evidence list')
    elif not any(isinstance(item, dict) and item.get('text') for item in evidence):
        add_issue(issues, 'ERROR', 'schema', source, 'evidence has no text entries')
    supply = ctx.get('supply_chain')
    if not isinstance(supply, dict):
        add_issue(issues, 'ERROR', 'schema', source, 'missing supply_chain object')
    else:
        for layer in LAYERS:
            values = supply.get(layer)
            if not isinstance(values, list):
                add_issue(issues, 'ERROR', 'schema', source, f'supply_chain.{layer} must be list')
                continue
            for item in values:
                text = str(item.get('name') if isinstance(item, dict) else item).strip()
                if not text:
                    continue
                if is_long_sentence(text):
                    add_issue(issues, 'WARNING', 'supply_chain_long_sentence', source, f'{layer}: item looks like sentence/fact', text[:120])
                hits = find_names(text, names, 5)
                if hits:
                    add_issue(issues, 'WARNING', 'company_in_supply_chain', source, f'{layer}: company name in supply_chain', f'{text} => {"、".join(hits)}')
    for field in RICH_FIELDS:
        if not ctx.get(field):
            add_issue(issues, 'WARNING', 'missing_radar_field', source, f'missing {field}')
    check_company_mentions(source, ctx, names, issues)
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description='Read-only Theme Radar report_contexts lint.')
    parser.add_argument('--source', help='只检查指定 source_name')
    parser.add_argument('--concept', help='只检查指定 concept')
    parser.add_argument('--limit', type=int, default=0, help='最多打印多少条 issue，0=全部')
    parser.add_argument('--json', action='store_true', help='输出 JSON')
    args = parser.parse_args()

    data = load_json(REPORT_CONTEXTS)
    reports = data.get('reports') or {}
    names = load_entity_names()
    all_issues = []
    scanned = 0
    for source, ctx in reports.items():
        if args.source and args.source not in source:
            continue
        if args.concept and str(ctx.get('concept') or '') != args.concept:
            continue
        scanned += 1
        all_issues.extend(check_context(source, ctx, names))

    counts = Counter(issue['category'] for issue in all_issues)
    sev = Counter(issue['severity'] for issue in all_issues)
    summary = {'scanned_reports': scanned, 'errors': sev.get('ERROR', 0), 'warnings': sev.get('WARNING', 0), 'categories': dict(counts)}
    if args.json:
        print(json.dumps({'summary': summary, 'issues': all_issues}, ensure_ascii=False, indent=2))
    else:
        print('report_contexts_lint')
        print(f"scanned={scanned} errors={summary['errors']} warnings={summary['warnings']}")
        for category, count in counts.most_common():
            print(f'- {category}: {count}')
        print()
        shown = all_issues if args.limit == 0 else all_issues[:args.limit]
        for issue in shown:
            print(f"[{issue['severity']}] {issue['category']} | {issue['source']} | {issue['message']}")
            if issue.get('detail'):
                print(f"  {issue['detail']}")
        if args.limit and len(all_issues) > args.limit:
            print(f'... {len(all_issues) - args.limit} more')
    return 1 if summary['errors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
