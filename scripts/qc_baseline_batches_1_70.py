#!/usr/bin/env python3
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path('/Users/lbq/Desktop/c c/知识库/wiki/raw/ifind-baseline')
OUT = Path('/Users/lbq/Desktop/c c/知识库/wiki/raw/ifind-baseline/baseline-qc-batch1-70-summary.json')

GENERIC_ROLE_PATTERNS = [
    '提供商', '制造及提供商', '相关企业', '相关公司', '产业链参与者', '布局企业', '受益标的',
    '中游制造及提供商', '上游材料/设备', '中游制造/服务', '下游应用/集成', '核心标的',
]
FORBIDDEN_EVIDENCE_TERMS = [
    '涨幅', '连板', '市场关注', '题材炒作', '短期催化', '资金流入', '龙虎榜', '涨停', '概念炒作',
]
WEAK_TERMS = ['待验证', '弱相关', '可能', '有望', '关注', '概念', '题材']
BAD_KEY_DATA_TERMS = ['总资产', '净资产', 'ROE', 'EPS', 'PE', '市盈率', '估值', '分红', '现金流', '负债率']


def batch_num(path):
    m = re.search(r'batch(\d+)\.json$', path.name)
    return int(m.group(1)) if m else 0


def add_issue(issues, severity, code, batch, company, detail):
    issues.append({
        'severity': severity,
        'code': code,
        'batch': batch,
        'company': company,
        'detail': detail,
    })


def main():
    files = sorted(
        [p for p in BASE.glob('baseline-updates-*-batch*.json') if 1 <= batch_num(p) <= 70],
        key=batch_num,
    )
    issues = []
    stats = Counter()
    companies = []
    per_batch = defaultdict(Counter)

    for path in files:
        b = batch_num(path)
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except Exception as exc:
            add_issue(issues, 'critical', 'json_parse_error', b, '', str(exc))
            continue
        source_name = str(data.get('source_name', ''))
        if 'iFinD baseline' not in source_name:
            add_issue(issues, 'medium', 'unexpected_source_name', b, '', source_name)
        for u in data.get('updates', []) or []:
            stats['updates'] += 1
            company = u.get('company', '')
            companies.append(company)
            raw_source = str(u.get('raw_source', ''))
            if not raw_source.startswith('raw/ifind-baseline/'):
                add_issue(issues, 'critical', 'bad_raw_source', b, company, raw_source)
            if not u.get('main_business') or str(u.get('main_business')).strip() == '待补充':
                add_issue(issues, 'high', 'missing_main_business', b, company, '')
            products = u.get('products') or []
            if not products:
                add_issue(issues, 'medium', 'missing_products', b, company, '')
            concepts = u.get('concepts') or []
            if not concepts:
                add_issue(issues, 'medium', 'missing_concepts', b, company, '')
            exposures = u.get('exposures') or []
            if not exposures:
                add_issue(issues, 'high', 'missing_exposures', b, company, '')
            for exp in exposures:
                role = str(exp.get('role', '')).strip()
                evidence = str(exp.get('evidence', '')).strip()
                strength = str(exp.get('strength', '')).strip()
                confidence = str(exp.get('confidence', '')).strip()
                chain_layer = str(exp.get('chain_layer', '')).strip()
                concept = str(exp.get('concept', '')).strip()
                if not role:
                    add_issue(issues, 'high', 'missing_role', b, company, concept)
                elif any(pat == role or pat in role for pat in GENERIC_ROLE_PATTERNS):
                    add_issue(issues, 'medium', 'generic_role', b, company, f'{concept}: {role}')
                if not chain_layer:
                    add_issue(issues, 'medium', 'missing_chain_layer', b, company, concept)
                if strength == 'core' and (confidence in ('low', '') or any(t in evidence for t in WEAK_TERMS)):
                    add_issue(issues, 'high', 'suspicious_core_strength', b, company, f'{concept}: {confidence}; {evidence[:120]}')
                if any(t in evidence for t in FORBIDDEN_EVIDENCE_TERMS):
                    add_issue(issues, 'high', 'market_or_short_term_evidence', b, company, f'{concept}: {evidence[:160]}')
                if len(evidence) < 12:
                    add_issue(issues, 'medium', 'thin_evidence', b, company, f'{concept}: {evidence}')
                if exp.get('evidence_layer') not in (None, '', 'L2'):
                    add_issue(issues, 'medium', 'unexpected_evidence_layer_for_baseline', b, company, f'{concept}: {exp.get("evidence_layer")}')
                if exp.get('update_type') not in (None, '', 'baseline'):
                    add_issue(issues, 'medium', 'unexpected_update_type_for_baseline', b, company, f'{concept}: {exp.get("update_type")}')
            for item in u.get('key_data', []) or []:
                text = json.dumps(item, ensure_ascii=False)
                if any(t in text for t in BAD_KEY_DATA_TERMS):
                    add_issue(issues, 'medium', 'noisy_key_data', b, company, text[:180])

    for issue in issues:
        stats[f'issues_{issue["severity"]}'] += 1
        per_batch[issue['batch']][issue['severity']] += 1
        per_batch[issue['batch']]['total'] += 1

    summary = {
        'batch_files': len(files),
        'updates': stats['updates'],
        'unique_companies': len(set(companies)),
        'issue_counts': {k: v for k, v in stats.items() if k.startswith('issues_')},
        'top_issue_codes': Counter(i['code'] for i in issues).most_common(30),
        'top_batches_by_issues': sorted(
            [{'batch': b, **dict(c)} for b, c in per_batch.items()],
            key=lambda x: x.get('total', 0),
            reverse=True,
        )[:20],
        'sample_issues': issues[:200],
    }
    OUT.write_text(json.dumps({'summary': summary, 'issues': issues}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f'WROTE {OUT}')


if __name__ == '__main__':
    main()
