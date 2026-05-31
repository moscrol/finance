#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
REL = WIKI / 'relations'
CTX = REL / 'report_contexts.json'
EXPOSURES = REL / 'entity_exposures.json'
LAYERS = ['upstream_materials', 'upstream_equipment', 'midstream', 'downstream', 'ecosystem']
RICH_FIELDS = ['summary', 'demand_drivers', 'direction_scan', 'validation_checklist']
SENTENCE_MARKERS = ('。', '，', '；', '：', '报告称', '预计', '同比', '达到', '超过', '占比', '市占率')
CODE_SUFFIX_RE = re.compile(r'[（(]?(?:\\d{6}|\\d{3,6}\\.[A-Z]{2}|[A-Z]{1,5})[）)]?$')


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path: Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    tmp.replace(path)
    json.loads(path.read_text(encoding='utf-8'))


def entity_names() -> list[str]:
    data = load_json(EXPOSURES) if EXPOSURES.exists() else {'entities': {}}
    return sorted([str(x) for x in (data.get('entities') or {}) if len(str(x)) >= 2], key=len, reverse=True)


def item_text(item) -> str:
    if isinstance(item, dict):
        return str(item.get('name') or item.get('text') or '').strip()
    return str(item or '').strip()


def is_sentence(text: str) -> bool:
    return len(text) >= 34 or (len(text) >= 18 and any(x in text for x in SENTENCE_MARKERS))


def find_names(text: str, names: list[str], limit: int = 16) -> list[str]:
    hits = []
    for name in names:
        if name in text:
            hits.append(name)
            if len(hits) >= limit:
                break
    return hits


def canonical_company_item(text: str) -> str:
    value = str(text or '').strip()
    value = re.sub(r'[（(][^（）()]*?[）)]', '', value)
    value = CODE_SUFFIX_RE.sub('', value)
    return re.sub(r'\\s+', '', value).strip(' -_：:，,、')


def is_pure_company_item(text: str, names_set: set[str]) -> bool:
    value = str(text or '').strip()
    if not value or len(value) > 28:
        return False
    compact = canonical_company_item(value)
    return compact in names_set


def make_plan(data: dict, names: list[str], source_filter: str = '', concept_filter: str = '') -> dict:
    queues = defaultdict(list)
    reports = data.get('reports') or {}
    names_set = set(names)
    for source, ctx in reports.items():
        if source_filter and source_filter not in source:
            continue
        if concept_filter and str(ctx.get('concept') or '') != concept_filter:
            continue
        supply = ctx.get('supply_chain')
        if not isinstance(supply, dict):
            queues['schema_fix_queue'].append({'source': source, 'field': 'supply_chain', 'issue': 'not_object'})
            continue
        for layer in LAYERS:
            value = supply.get(layer)
            if not isinstance(value, list):
                queues['schema_fix_queue'].append({'source': source, 'field': f'supply_chain.{layer}', 'issue': 'not_list', 'value_type': type(value).__name__})
                continue
            for idx, item in enumerate(value):
                text = item_text(item)
                if not text:
                    continue
                hits = find_names(text, names, 8)
                if hits:
                    issue = 'pure_company_item' if is_pure_company_item(text, names_set) else 'company_in_supply_chain'
                    queues['supply_chain_cleanup_queue'].append({'source': source, 'layer': layer, 'index': idx, 'issue': issue, 'item': text[:160], 'companies': hits})
                if is_sentence(text):
                    queues['supply_chain_cleanup_queue'].append({'source': source, 'layer': layer, 'index': idx, 'issue': 'long_sentence_or_fact', 'item': text[:160]})
        evidence_text = ' '.join(str(x.get('text', '')) for x in (ctx.get('evidence') or []) if isinstance(x, dict))
        mentioned = find_names(evidence_text, names, 24)
        if mentioned and not ctx.get('company_mentions'):
            queues['company_mentions_queue'].append({'source': source, 'concept': ctx.get('concept'), 'companies': mentioned})
        missing = [field for field in RICH_FIELDS if not ctx.get(field)]
        if missing:
            queues['rich_fields_queue'].append({'source': source, 'concept': ctx.get('concept'), 'missing': missing})
    return {key: value for key, value in queues.items()}


def normalize_layer_value(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        text = item_text(value)
        return [text] if text else []
    text = str(value).strip()
    return [text] if text else []


def apply_schema_fixes(data: dict, plan: dict) -> int:
    changed = 0
    reports = data.get('reports') or {}
    for row in plan.get('schema_fix_queue', []):
        source = row.get('source')
        ctx = reports.get(source)
        if not isinstance(ctx, dict):
            continue
        if row.get('field') == 'supply_chain':
            ctx['supply_chain'] = {layer: [] for layer in LAYERS}
            changed += 1
            continue
        field = str(row.get('field') or '')
        if not field.startswith('supply_chain.'):
            continue
        layer = field.split('.', 1)[1]
        supply = ctx.setdefault('supply_chain', {})
        old = supply.get(layer)
        supply[layer] = normalize_layer_value(old)
        changed += 1
    return changed


def exposure_hint(exposures: dict, company: str, concept: str) -> dict:
    entity = (exposures.get('entities') or {}).get(company) or {}
    concepts = entity.get('concepts') or {}
    if concept in concepts:
        return concepts.get(concept) or {}
    return {}


def evidence_text_for_company(ctx: dict, company: str) -> str:
    for item in ctx.get('evidence') or []:
        if not isinstance(item, dict):
            continue
        text = str(item.get('text') or '').strip()
        if company in text:
            return text[:240]
    return ''


def apply_company_mentions(data: dict, plan: dict, exposures: dict) -> int:
    changed = 0
    reports = data.get('reports') or {}
    for row in plan.get('company_mentions_queue', []):
        source = row.get('source')
        ctx = reports.get(source)
        if not isinstance(ctx, dict):
            continue
        concept = str(ctx.get('concept') or row.get('concept') or '')
        mentions = []
        for company in row.get('companies') or []:
            hint = exposure_hint(exposures, str(company), concept)
            ev_text = evidence_text_for_company(ctx, str(company))
            mentions.append({
                'company': str(company),
                'concept': concept,
                'chain_layer': hint.get('chain_layer') or 'unknown',
                'role': hint.get('role') or 'report_context evidence mention',
                'evidence_text': ev_text,
                'directness': 'direct' if ev_text else 'context',
                'evidence_layer': 'L1_L3_candidate',
                'fact_hardness': 'research_claim',
                'review_required': True,
            })
        if mentions:
            ctx['company_mentions'] = mentions
            changed += 1
    return changed


def apply_supply_chain_pure_company_cleanup(data: dict, plan: dict, names: list[str]) -> int:
    names_set = set(names)
    changed = 0
    reports = data.get('reports') or {}
    target_sources = {row.get('source') for row in plan.get('supply_chain_cleanup_queue', []) if row.get('issue') == 'pure_company_item'}
    for source, ctx in reports.items():
        if source not in target_sources:
            continue
        supply = ctx.get('supply_chain')
        if not isinstance(supply, dict):
            continue
        for layer in LAYERS:
            values = supply.get(layer)
            if not isinstance(values, list):
                continue
            kept = [item for item in values if not is_pure_company_item(item_text(item), names_set)]
            removed = len(values) - len(kept)
            if removed:
                supply[layer] = kept
                changed += removed
    return changed


def add_evidence_once(ctx: dict, layer: str, text: str) -> None:
    evidence = ctx.setdefault('evidence', [])
    if not isinstance(evidence, list):
        ctx['evidence'] = []
        evidence = ctx['evidence']
    compact_text = re.sub(r'\s+', '', text)
    for item in evidence:
        if isinstance(item, dict) and re.sub(r'\s+', '', str(item.get('text') or '')) == compact_text:
            return
    evidence.append({'heading': f'supply_chain.{layer}', 'text': text[:240]})


def add_company_mention_once(ctx: dict, company: str, concept: str, layer: str, text: str, exposures: dict) -> None:
    mentions = ctx.setdefault('company_mentions', [])
    if not isinstance(mentions, list):
        ctx['company_mentions'] = []
        mentions = ctx['company_mentions']
    for item in mentions:
        if isinstance(item, dict) and item.get('company') == company and item.get('evidence_text') == text[:240]:
            return
    hint = exposure_hint(exposures, company, concept)
    mentions.append({
        'company': company,
        'concept': concept,
        'chain_layer': hint.get('chain_layer') or layer,
        'role': hint.get('role') or text[:120],
        'evidence_text': text[:240],
        'directness': 'direct',
        'evidence_layer': 'L1_L3_candidate',
        'fact_hardness': 'research_claim',
        'review_required': True,
    })


def apply_supply_chain_sentence_cleanup(data: dict, plan: dict, exposures: dict) -> int:
    reports = data.get('reports') or {}
    targets = defaultdict(lambda: defaultdict(set))
    rows_by_key = defaultdict(list)
    for row in plan.get('supply_chain_cleanup_queue', []):
        if row.get('issue') == 'pure_company_item':
            continue
        key = (row.get('source'), row.get('layer'), row.get('item'))
        rows_by_key[key].append(row)
        targets[row.get('source')][row.get('layer')].add(row.get('item'))
    changed = 0
    for source, layers in targets.items():
        ctx = reports.get(source)
        if not isinstance(ctx, dict):
            continue
        concept = str(ctx.get('concept') or '')
        supply = ctx.get('supply_chain')
        if not isinstance(supply, dict):
            continue
        for layer, items in layers.items():
            values = supply.get(layer)
            if not isinstance(values, list):
                continue
            kept = []
            for item in values:
                text = item_text(item)
                if text[:160] not in items:
                    kept.append(item)
                    continue
                add_evidence_once(ctx, layer, text)
                for row in rows_by_key.get((source, layer, text[:160]), []):
                    for company in row.get('companies') or []:
                        add_company_mention_once(ctx, str(company), concept, layer, text, exposures)
                changed += 1
            supply[layer] = kept
    return changed


def layer_terms(ctx: dict, layer: str, limit: int = 8) -> list[str]:
    values = ((ctx.get('supply_chain') or {}).get(layer) or [])
    result = []
    for item in values:
        text = item_text(item)
        if text and text not in result:
            result.append(text)
        if len(result) >= limit:
            break
    return result


def context_companies(ctx: dict, limit: int = 8) -> list[str]:
    result = []
    for item in ctx.get('company_mentions') or []:
        if not isinstance(item, dict):
            continue
        company = str(item.get('company') or '').strip()
        if company and company not in result:
            result.append(company)
        if len(result) >= limit:
            break
    return result


def build_summary(ctx: dict) -> str:
    concept = str(ctx.get('concept') or '该题材')
    downstream = '、'.join(layer_terms(ctx, 'downstream', 4)) or '下游需求'
    midstream = '、'.join(layer_terms(ctx, 'midstream', 4)) or '中游环节'
    upstream = '、'.join(layer_terms(ctx, 'upstream_materials', 3) + layer_terms(ctx, 'upstream_equipment', 3)) or '上游材料/设备'
    companies = '、'.join(context_companies(ctx, 5)) or '候选公司'
    return f'{concept}：已精读研报上下文覆盖下游 {downstream}，中游 {midstream}，上游 {upstream}；公司线索包括 {companies}，仍需用公告、年报、官网、互动易等公司级证据验证。'


def build_demand_drivers(ctx: dict) -> list[str]:
    drivers = []
    for value in layer_terms(ctx, 'downstream', 8):
        drivers.append(f'{value}需求拉动相关产业链环节。')
    for value in layer_terms(ctx, 'ecosystem', 4):
        drivers.append(f'{value}构成题材发酵或产业变化背景。')
    return drivers[:8] or ['下游需求、产业周期或技术迭代构成潜在驱动，需继续补事实验证。']


def build_direction_scan(ctx: dict) -> list[dict]:
    concept = str(ctx.get('concept') or '')
    candidates = context_companies(ctx, 8)
    directions = layer_terms(ctx, 'midstream', 6) + layer_terms(ctx, 'upstream_materials', 3) + layer_terms(ctx, 'upstream_equipment', 3)
    rows = []
    for value in directions[:8]:
        rows.append({
            'direction': value,
            'sector': concept,
            'prosperity': '来自已精读研报上下文的产业链方向，需结合公司证据和信号层确认景气。',
            'mention_frequency': '本地精读命中',
            'recognition_level': 'L1-L3',
            'classification': '精读线索',
            'core_catalyst': '、'.join(layer_terms(ctx, 'downstream', 3)) or '下游需求验证',
            'candidate_companies': candidates,
        })
    return rows


def build_validation_checklist(ctx: dict) -> list[dict]:
    concept = str(ctx.get('concept') or '题材')
    return [
        {'item': f'{concept}相关公司是否有明确产品/业务/客户/产能披露', 'why': '验证公司是否真实落在题材链条中', 'status': '待 L2/L3 证据'},
        {'item': '精读研报提到的公司是否已进入 company_mentions 并完成链层校准', 'why': '避免核心线索被低估或配套公司被高估', 'status': '自动队列+人工复核'},
        {'item': '核心方向是否出现订单、送样、认证、量产、价格、收入占比等事实', 'why': '从 L1 产业翻译升级到 L3 事实验证', 'status': '待补证'},
        {'item': '只由市场信号、泛概念或弱配套支撑的公司是否降权', 'why': '控制 context_overranked 和 weak_granularity 污染', 'status': '自动 QC'},
    ]


def apply_rich_fields(data: dict, plan: dict) -> int:
    reports = data.get('reports') or {}
    changed = 0
    for row in plan.get('rich_fields_queue', []):
        ctx = reports.get(row.get('source'))
        if not isinstance(ctx, dict):
            continue
        before = json.dumps({field: ctx.get(field) for field in RICH_FIELDS}, ensure_ascii=False, sort_keys=True)
        ctx.setdefault('summary', build_summary(ctx))
        ctx.setdefault('demand_drivers', build_demand_drivers(ctx))
        ctx.setdefault('direction_scan', build_direction_scan(ctx))
        ctx.setdefault('validation_checklist', build_validation_checklist(ctx))
        after = json.dumps({field: ctx.get(field) for field in RICH_FIELDS}, ensure_ascii=False, sort_keys=True)
        if before != after:
            changed += 1
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description='Build common repair queues for report_contexts.json.')
    parser.add_argument('--source')
    parser.add_argument('--concept')
    parser.add_argument('--limit', type=int, default=5)
    parser.add_argument('--apply-schema', action='store_true')
    parser.add_argument('--apply-company-mentions', action='store_true')
    parser.add_argument('--apply-supply-chain-pure-company', action='store_true')
    parser.add_argument('--apply-supply-chain-sentences', action='store_true')
    parser.add_argument('--apply-rich-fields', action='store_true')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()

    data = load_json(CTX)
    names = entity_names()
    plan = make_plan(data, names, args.source or '', args.concept or '')
    summary = {key: len(value) for key, value in plan.items()}
    if args.apply_schema:
        backup = CTX.with_name(f'report_contexts.backup-schema-repair-{datetime.now().strftime("%Y%m%d%H%M%S")}.json')
        shutil.copy2(CTX, backup)
        changed = apply_schema_fixes(data, plan)
        data['updated'] = datetime.now().date().isoformat()
        write_json(CTX, data)
        summary['schema_fixes_applied'] = changed
        summary['backup'] = str(backup)
    if args.apply_company_mentions:
        backup = CTX.with_name(f'report_contexts.backup-company-mentions-{datetime.now().strftime("%Y%m%d%H%M%S")}.json')
        shutil.copy2(CTX, backup)
        exposures = load_json(EXPOSURES) if EXPOSURES.exists() else {'entities': {}}
        changed = apply_company_mentions(data, plan, exposures)
        data['updated'] = datetime.now().date().isoformat()
        write_json(CTX, data)
        summary['company_mentions_applied'] = changed
        summary['backup'] = str(backup)
    if args.apply_supply_chain_pure_company:
        backup = CTX.with_name(f'report_contexts.backup-supply-chain-pure-company-{datetime.now().strftime("%Y%m%d%H%M%S")}.json')
        shutil.copy2(CTX, backup)
        changed = apply_supply_chain_pure_company_cleanup(data, plan, names)
        data['updated'] = datetime.now().date().isoformat()
        write_json(CTX, data)
        summary['supply_chain_pure_company_removed'] = changed
        summary['backup'] = str(backup)
    if args.apply_supply_chain_sentences:
        backup = CTX.with_name(f'report_contexts.backup-supply-chain-sentences-{datetime.now().strftime("%Y%m%d%H%M%S")}.json')
        shutil.copy2(CTX, backup)
        exposures = load_json(EXPOSURES) if EXPOSURES.exists() else {'entities': {}}
        changed = apply_supply_chain_sentence_cleanup(data, plan, exposures)
        data['updated'] = datetime.now().date().isoformat()
        write_json(CTX, data)
        summary['supply_chain_sentences_moved'] = changed
        summary['backup'] = str(backup)
    if args.apply_rich_fields:
        backup = CTX.with_name(f'report_contexts.backup-rich-fields-{datetime.now().strftime("%Y%m%d%H%M%S")}.json')
        shutil.copy2(CTX, backup)
        changed = apply_rich_fields(data, plan)
        data['updated'] = datetime.now().date().isoformat()
        write_json(CTX, data)
        summary['rich_fields_applied'] = changed
        summary['backup'] = str(backup)
    if args.json:
        print(json.dumps({'summary': summary, 'queues': plan}, ensure_ascii=False, indent=2))
    else:
        print('report_contexts_repair_plan')
        for key in ['schema_fix_queue', 'supply_chain_cleanup_queue', 'company_mentions_queue', 'rich_fields_queue']:
            rows = plan.get(key, [])
            print(f'- {key}: {len(rows)}')
            for row in rows[:args.limit]:
                print(f'  {row}')
        if args.apply_schema:
            print(f"schema_fixes_applied={summary.get('schema_fixes_applied', 0)}")
            print(f"backup={summary.get('backup')}")
        if args.apply_company_mentions:
            print(f"company_mentions_applied={summary.get('company_mentions_applied', 0)}")
            print(f"backup={summary.get('backup')}")
        if args.apply_supply_chain_pure_company:
            print(f"supply_chain_pure_company_removed={summary.get('supply_chain_pure_company_removed', 0)}")
            print(f"backup={summary.get('backup')}")
        if args.apply_supply_chain_sentences:
            print(f"supply_chain_sentences_moved={summary.get('supply_chain_sentences_moved', 0)}")
            print(f"backup={summary.get('backup')}")
        if args.apply_rich_fields:
            print(f"rich_fields_applied={summary.get('rich_fields_applied', 0)}")
            print(f"backup={summary.get('backup')}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
