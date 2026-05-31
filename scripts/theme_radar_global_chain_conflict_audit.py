#!/usr/bin/env python3
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import theme_radar_quality_rules as rules

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
QUEUE = WIKI / 'raw/theme-radar/theme-radar-quality-queue-global.json'
OUT = WIKI / 'raw/theme-radar/theme-radar-chain-conflict-audit.json'

AMBIGUOUS_TOKENS = ('制造与流通', '平台', '配套', '应用与', '服务与', '生态', '潜在', '弱相关', '待验证')
HIGH_CONF_HARDNESS = {'hard_fact', 'baseline', 'review_candidate', 'research_claim'}
SPECIFIC_MATERIAL_TOKENS = ('EMI', '屏蔽材料', '正极材料', '负极材料', '电镀', '电解质', '铝塑膜', 'BOPA', '电子纱', '玻纤', '稀土永磁', '钴酸锂', '三元正极', '铜箔', '膜材料')
GENERIC_CATEGORY_ROLES = {
    '芯片/核心器件',
    '下游应用',
    '下游应用/客户',
    '上游材料/设备',
    '上游光器件/激光设备',
    '核心设备及产品供应商',
    '上游设备及材料供应商',
}


def load_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def evidence_hardness(item):
    vals = [x.get('fact_hardness') for x in item.get('evidence_items') or [] if x.get('fact_hardness')]
    vals.append(item.get('fact_hardness'))
    vals = [str(x or '').strip() for x in vals if str(x or '').strip()]
    for v in ('hard_fact', 'baseline', 'review_candidate', 'research_claim', 'market_narrative', 'legacy_rebuilt'):
        if v in vals:
            return v
    return 'unknown'


def role_layer_hits(role):
    hits = set()
    for token, layer in rules.ROLE_LAYER_RULES:
        if token in str(role or ''):
            hits.add(layer)
    return hits


def high_confidence(item):
    role = str(item.get('role') or '')
    chain = str(item.get('chain_layer') or '')
    text = ' '.join(str(item.get(k) or '') for k in ('role', 'chain_layer', 'evidence_sample', 'update_type', 'evidence_layer'))
    inferred = rules.infer_layer(role)
    if not inferred:
        return False, 'no_inferred_layer'
    if len(role_layer_hits(role)) != 1:
        return False, 'multi_layer_role'
    if role.strip() in GENERIC_CATEGORY_ROLES or len(role.strip()) < 8 or role.strip()[:2].replace('.', '').isdigit():
        return False, 'category_like_role'
    if inferred == 'upstream_materials' and not any(x in role for x in SPECIFIC_MATERIAL_TOKENS):
        return False, 'broad_material_role'
    if rules.is_weak_role(role) or rules.is_generic_role(role):
        return False, 'weak_or_generic_role'
    if any(x in text for x in rules.WEAK_TOKENS):
        return False, 'weak_signal'
    if any(x in role for x in AMBIGUOUS_TOKENS):
        return False, 'ambiguous_role_token'
    if any(x in role for x in ('应用服务商', '软件服务商', '芯片包裹', '跨界投资', '布局商', '整机商', '企业', '供应商', '提供及生产商')):
        return False, 'service_or_biomedical_ambiguous'
    if '供应商/运营商' in role or '厂商/运营商' in role:
        return False, 'mixed_supplier_operator'
    if item.get('strength') == 'core':
        return False, 'skip_core'
    if evidence_hardness(item) not in HIGH_CONF_HARDNESS:
        return False, 'insufficient_hardness'
    if rules.normalize_chain_layer(chain) == inferred:
        return False, 'unchanged'
    return True, 'high_confidence'


def main():
    queue = load_json(QUEUE)
    items = [x for x in queue.get('items', []) if x.get('issue') == 'chain_layer_conflict']
    matrix = Counter()
    roles = Counter()
    themes = Counter()
    strengths = Counter()
    hardness = Counter()
    buckets = Counter()
    decisions = Counter()
    candidates = []
    for item in items:
        raw = rules.normalize_chain_layer(item.get('chain_layer', ''))
        role_layer = rules.normalize_chain_layer(item.get('role', ''))
        inferred = rules.infer_layer(item.get('role', ''))
        matrix[f'{raw}->{role_layer}'] += 1
        roles[str(item.get('role') or '')[:80]] += 1
        themes[item.get('theme') or ''] += 1
        strengths[item.get('strength') or ''] += 1
        buckets[item.get('bucket') or ''] += 1
        hardness[evidence_hardness(item)] += 1
        ok, reason = high_confidence(item)
        decisions[reason] += 1
        if ok:
            candidates.append({
                'theme': item.get('theme'),
                'company': item.get('company'),
                'strength': item.get('strength'),
                'bucket': item.get('bucket'),
                'role': item.get('role'),
                'chain_layer': item.get('chain_layer'),
                'current_normalized': raw,
                'role_normalized': role_layer,
                'suggested_chain_layer': inferred,
                'hardness': evidence_hardness(item),
                'evidence_sample': item.get('evidence_sample', ''),
            })
    result = {
        'generated_at': __import__('datetime').datetime.now().isoformat(timespec='seconds'),
        'source': str(QUEUE.relative_to(WIKI)),
        'total_conflicts': len(items),
        'high_confidence_candidates': len(candidates),
        'matrix_top': matrix.most_common(80),
        'themes_top': themes.most_common(80),
        'roles_top': roles.most_common(80),
        'strengths': dict(strengths),
        'buckets': dict(buckets),
        'hardness': dict(hardness),
        'decision_reasons': dict(decisions),
        'candidates': candidates,
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'candidates'}, ensure_ascii=False, indent=2))
    print(OUT)


if __name__ == '__main__':
    main()
