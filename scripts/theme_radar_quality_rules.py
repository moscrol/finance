#!/usr/bin/env python3
from __future__ import annotations

DIRECT_TOKENS = (
    '先进封装', '封装', '封测', 'SiP', 'TSV', 'Chiplet', 'FC-BGA', 'ABF', '载板', '基板', '电镀液', '添加剂', '刻蚀', '量检测', '测试',
    '商业航天', '卫星', '火箭', '星载', '载荷', '太阳能电池', '航天', '发射', '通信运营',
    '固态电池', '电池', '电解质', '硫化物', '锂电', '铝塑膜', 'BOPA', '涂布', '辊压', '负极', '正极',
)
WEAK_TOKENS = (
    '弱相关', '待验证', '潜在', '潜在相关', '市场信号弱关联', '图谱弱关联', '受益', '映射',
    '基础资料未直接', '不直接证明', '从既有entity markdown重建', '从既有concept markdown重建',
    'L2_candidate', 'L1_L3_candidate',
)
GENERIC_ROLES = ('', '上游设备', '上游材料', '中游制造', '中游封装测试', '市场信号弱关联', '图谱弱关联', '相关公司', '受益标的', '待验证受益标的', '产业链供应商')
BASELINE_TOKENS = ('iFinD baseline', 'AkShare baseline', '基础资料', '主营', '行业分类')
LEGACY_TOKENS = ('从既有entity markdown重建', '从既有concept markdown重建')
SOFT_FACT_HARDNESS = {'research_claim', 'market_narrative', 'legacy_rebuilt', 'unknown'}
HARD_FACT_HARDNESS = {'hard_fact', 'baseline'}

CHAIN_LAYER_NORMALIZE_MAP = {
    'upstream_materials': 'upstream_materials',
    'upstream_components': 'upstream_components',
    'upstream_equipment': 'upstream_equipment',
    'midstream': 'midstream_manufacturing',
    'midstream_manufacturing': 'midstream_manufacturing',
    'midstream_components': 'midstream_components',
    'midstream_service': 'midstream_service',
    'midstream_equipment': 'midstream_equipment',
    'downstream': 'downstream_application',
    'downstream_application': 'downstream_application',
    'downstream_operation': 'downstream_operation',
    'downstream_integrated': 'downstream_application',
    'downstream_infrastructure': 'downstream_application',
    'ecosystem': 'ecosystem',
}
COARSE_CHAIN_LAYERS = {
    '',
    '设备/整机/应用',
    '上游材料/设备/芯片制造',
    'downstream',
    'midstream',
    'upstream',
    '上游',
    '中游',
    '下游',
}
HARD_FACT_TOKENS = (
    '公告', '年报', '官网', '合同', '中标', '认证', '量产', '投产', '扩产', '产能',
    '客户导入', '订单', '收入', '营收', '出货', '良率', '送样', '长协', '独家供应',
)
RESEARCH_CLAIM_TOKENS = ('龙头', '唯一', '领先', '壁垒', '市占率', '份额', '毛利率', '绑定', '配套', '布局')
MARKET_NARRATIVE_TOKENS = ('受益', '弹性', '催化', '市场逻辑', '题材', '映射', '预期')
CHAIN_LAYER_KEYWORDS = (
    ('电镀液', 'upstream_materials'),
    ('添加剂', 'upstream_materials'),
    ('清洗液', 'upstream_materials'),
    ('电子布', 'upstream_materials'),
    ('玻纤', 'upstream_materials'),
    ('铝塑膜', 'upstream_materials'),
    ('BOPA', 'upstream_materials'),
    ('固态电解质', 'upstream_materials'),
    ('电解质', 'upstream_materials'),
    ('测试商', 'midstream_service'),
    ('封装测试', 'midstream_service'),
    ('电学及性能测试', 'midstream_service'),
    ('太阳能电池芯片', 'upstream_components'),
    ('材料', 'upstream_materials'),
    ('零部件', 'upstream_components'),
    ('器件', 'upstream_components'),
    ('芯片', 'upstream_components'),
    ('载荷', 'upstream_components'),
    ('设备', 'upstream_equipment'),
    ('装备', 'upstream_equipment'),
    ('制造', 'midstream_manufacturing'),
    ('封装', 'midstream_manufacturing'),
    ('封测', 'midstream_manufacturing'),
    ('代工', 'midstream_manufacturing'),
    ('总装', 'midstream_manufacturing'),
    ('测试商', 'midstream_service'),
    ('测试', 'midstream_service'),
    ('服务', 'midstream_service'),
    ('软件', 'midstream_service'),
    ('运营', 'downstream_operation'),
    ('应用', 'downstream_application'),
    ('生态', 'ecosystem'),
    ('配套', 'ecosystem'),
)
ROLE_LAYER_RULES = (
    ('电镀液', 'upstream_materials'), ('添加剂', 'upstream_materials'), ('清洗液', 'upstream_materials'), ('电子布', 'upstream_materials'),
    ('玻纤', 'upstream_materials'), ('铝塑膜', 'upstream_materials'), ('BOPA', 'upstream_materials'), ('固态电解质', 'upstream_materials'),
    ('电解质', 'upstream_materials'), ('材料', 'upstream_materials'), ('设备', 'upstream_equipment'), ('刻蚀', 'upstream_equipment'),
    ('检测', 'upstream_equipment'), ('量检测', 'upstream_equipment'), ('测试商', 'midstream_service'), ('测试', 'midstream_service'),
    ('载板', 'upstream_components'), ('基板', 'upstream_components'), ('芯片', 'upstream_components'), ('载荷', 'upstream_components'),
    ('光学', 'upstream_components'), ('太阳能电池芯片', 'upstream_components'), ('封测', 'midstream_manufacturing'),
    ('封装', 'midstream_manufacturing'), ('SiP', 'midstream_manufacturing'), ('TSV', 'midstream_manufacturing'),
    ('电池', 'midstream_manufacturing'), ('运营商', 'downstream_operation'), ('运营', 'downstream_operation'), ('应用', 'downstream_application'),
)
AMBIGUOUS_ROLE_TOKENS = ('制造与流通', '平台', '配套', '应用与', '服务与', '生态', '潜在', '弱相关', '待验证')
GENERIC_CATEGORY_ROLES = {
    '芯片/核心器件',
    '下游应用',
    '下游应用/客户',
    '上游材料/设备',
    '上游光器件/激光设备',
    '核心设备及产品供应商',
    '上游设备及材料供应商',
}
SPECIFIC_MATERIAL_TOKENS = ('EMI', '屏蔽材料', '正极材料', '负极材料', '电镀', '电解质', '铝塑膜', 'BOPA', '电子纱', '玻纤', '稀土永磁', '钴酸锂', '三元正极', '铜箔', '膜材料')


def unique(items):
    out = []
    seen = set()
    for item in items:
        item = str(item or '').strip()
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def normalize_chain_layer(value: str) -> str:
    text = str(value or '').strip()
    if not text:
        return ''
    if text in CHAIN_LAYER_NORMALIZE_MAP:
        return CHAIN_LAYER_NORMALIZE_MAP[text]
    lowered = text.lower()
    for key, target in CHAIN_LAYER_NORMALIZE_MAP.items():
        if key in lowered:
            return target
    for token, target in CHAIN_LAYER_KEYWORDS:
        if token in text:
            return target
    return 'unknown'


def is_coarse_chain_layer(value: str) -> bool:
    return str(value or '').strip() in COARSE_CHAIN_LAYERS


def infer_layer(text: str) -> str:
    for token, layer in ROLE_LAYER_RULES:
        if token in str(text or ''):
            return layer
    return ''


def role_layer_hits(text: str) -> set[str]:
    hits = set()
    for token, layer in ROLE_LAYER_RULES:
        if token in str(text or ''):
            hits.add(layer)
    return hits


def strict_role_chain_layers(text: str) -> list[str]:
    role = str(text or '').strip()
    if not role:
        return []
    if role in GENERIC_CATEGORY_ROLES or len(role) < 8 or role[:2].replace('.', '').isdigit():
        return []
    if is_weak_role(role) or is_generic_role(role):
        return []
    if any(x in role for x in AMBIGUOUS_ROLE_TOKENS):
        return []
    if any(x in role for x in ('应用服务商', '软件服务商', '芯片包裹', '供应商/运营商', '厂商/运营商', '跨界投资', '布局商', '整机商', '企业', '供应商', '提供及生产商')):
        return []
    hits = role_layer_hits(role)
    if len(hits) != 1:
        return []
    layer = next(iter(hits))
    if layer == 'upstream_materials' and not any(x in role for x in SPECIFIC_MATERIAL_TOKENS):
        return []
    return [layer]


def fact_hardness_rank_from_values(values) -> str:
    clean = [str(x or '').strip() for x in values or [] if str(x or '').strip()]
    priority = ('hard_fact', 'baseline', 'review_candidate', 'research_claim', 'market_narrative', 'legacy_rebuilt')
    for value in priority:
        if value in clean:
            return value
    return 'unknown'


def fact_hardness_rank(company: dict) -> str:
    return fact_hardness_rank_from_values(company.get('fact_hardness', []))


def is_soft_fact_hardness(value: str) -> bool:
    return str(value or '').strip() in SOFT_FACT_HARDNESS


def evidence_score_adjustment(company: dict) -> int:
    hardness = fact_hardness_rank(company)
    score = 0
    if hardness in HARD_FACT_HARDNESS:
        score += 2
    elif hardness == 'review_candidate':
        score += 1
    elif is_soft_fact_hardness(hardness):
        score -= 2
    if company.get('review_required'):
        score -= 3
    return score


def should_force_peripheral_by_quality(company: dict) -> bool:
    return bool(company.get('review_required')) and fact_hardness_rank(company) in {'legacy_rebuilt', 'market_narrative', 'unknown'}


def text_blob(item: dict) -> str:
    evidence_items = item.get('evidence_items') or []
    parts = [item.get('role', ''), item.get('chain_layer', ''), item.get('evidence_sample', ''), ' '.join(item.get('sources') or [])]
    for ev in evidence_items:
        parts.append(ev.get('source', ''))
        parts.append(ev.get('evidence', ''))
        parts.append(ev.get('fact_hardness', ''))
    return ' '.join(str(x) for x in parts if x)


def direct_score(item: dict) -> int:
    blob = text_blob(item)
    score = sum(1 for token in DIRECT_TOKENS if token in blob)
    score += 2 if item.get('theme') and item.get('theme') in blob else 0
    score -= sum(1 for token in WEAK_TOKENS if token in blob)
    return score


def inferred_hardness(item: dict) -> str:
    values = [ev.get('fact_hardness') for ev in item.get('evidence_items') or []]
    hardness = fact_hardness_rank_from_values(values)
    if hardness != 'unknown':
        return hardness
    blob = text_blob(item)
    if any(x in blob for x in BASELINE_TOKENS):
        return 'baseline'
    if any(x in blob for x in LEGACY_TOKENS):
        return 'legacy_rebuilt'
    return 'unknown'


def infer_evidence_item_hardness(item: dict) -> str:
    source = str(item.get('source') or '')
    evidence = str(item.get('evidence') or '')
    update_type = str(item.get('update_type') or '')
    if item.get('fact_hardness'):
        return str(item.get('fact_hardness'))
    if 'iFinD baseline' in source or 'AkShare baseline' in source or update_type == 'baseline':
        return 'baseline'
    if '从既有' in evidence and '重建' in evidence:
        return 'legacy_rebuilt'
    if any(token in source for token in ('市场逻辑', '强势股', '复盘', '脱水')) or any(token in evidence for token in MARKET_NARRATIVE_TOKENS):
        return 'market_narrative'
    if any(token in evidence for token in HARD_FACT_TOKENS):
        return 'review_candidate'
    if any(token in evidence for token in RESEARCH_CLAIM_TOKENS) or '研究报告' in source:
        return 'research_claim'
    return 'unknown'


def is_weak_role(role: str) -> bool:
    return any(token in str(role or '') for token in WEAK_TOKENS)


def is_generic_role(role: str) -> bool:
    return (not str(role or '').strip()) or str(role or '').strip() in GENERIC_ROLES
