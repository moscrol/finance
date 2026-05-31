#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

FINANCE = Path('/Users/lbq/Desktop/c c/金融')
RAW = Path('/Users/lbq/Desktop/c c/知识库/raw')
WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
REL = WIKI / 'relations'
CTX = REL / 'report_contexts.json'
RADAR = FINANCE / 'skills/theme-radar/scripts/radar.py'
RADAR_OUT = WIKI / 'raw/theme-radar/regression'
STATE = WIKI / 'raw/theme-radar/fullmd-report-context-refine-state.json'

PREFER = ['机器人', '固态电池', '液冷', '商业航天', '低空', '卫星', '电解液', '钠离子', '复合铜箔', 'PCB', '服务器', '算力']
LAYERS = ['upstream_materials', 'upstream_equipment', 'midstream', 'downstream', 'ecosystem']
STOPWORDS = {
    '主要', '包括', '其中', '行业', '领域', '环节', '方面', '企业', '公司', '产品', '市场', '技术', '供应商',
    '年', '亿元', '万吨', '数据显示', '根据', '预计', '同比', '增长', '下降', '达到', '超过', '左右', '以上',
}

LAYER_HINTS = {
    'upstream_materials': ['原料', '材料', '天然矿物', '人工合成原料', '上游原料', '上游材料', '化工原料'],
    'upstream_equipment': ['设备', '装备', '零部件', '组件', '芯片', '模块', '系统', '工艺', '制造设备'],
    'midstream': ['中游', '制造', '生产', '加工', '封装', '模组', '组装', '产品结构', '生产环节'],
    'downstream': ['下游', '应用', '终端', '需求', '消费', '客户', '场景'],
    'ecosystem': ['趋势', '生态', '政策', '标准', '模式', '技术方向', '演进', '格局', '竞争', '协议'],
}

EXTRACT_TRIGGERS = ['包括', '涵盖', '主要有', '主要包括', '分为', '延伸至', '应用于', '集中于', '产品包括', '如', '例如', '其次为', '供应链']
EVIDENCE_TRIGGERS = ['产业链', '供应链', '上游', '中游', '下游', '技术路径', '技术方向', '应用领域', '生产路径', '成本构成']

INITIAL_DONE = {
    '华为芯片产业新格局深度研究报告：自主可控突破与供应链重构',
    '推理芯片产业新变化与新格局研究报告',
    '光模块产业新变化和新格局研究分析报告',
    '芯片IP产业新变化和新格局研究分析',
    '封测产业新变化与新格局深度研究报告',
    'AI算力产业新格局与供应链深度研究报告',
    '华为算力产业深度研究：技术突破与供应链重构下的投资机会',
    '模拟芯片产业新变化与新格局研究分析报告',
    '晶圆代工产业新变化与新格局深度研究报告',
    '超聚变产业新格局与供应链深度分析报告',
    '鸿蒙产业新变化与新格局全面分析报告',
    '汽车零部件产业新变化与新格局研究报告',
    '智能驾驶产业新格局与供应链深度研究报告',
    '铜箔产业新变化与新格局研究分析报告',
    '光伏产业新变化与新格局深度研究报告',
    '无人出租车产业新格局与投资机会深度研究报告',
    '火电改造产业新变化与新格局深度研究报告',
    '稀土永磁产业新变化与新格局深度研究报告',
    '油运产业深度研究报告：十六年熊市后的历史性拐点',
    '中国盾构机产业新格局与投资机会深度研究报告',
    '照明设备产业新格局与供应链分析报告',
    '骨架膜产业新变化与新格局深度研究报告',
    '海上风电产业投资价值分析报告',
    '铀矿产业新变化与新格局深度研究报告',
    '光伏铜粉产业新变化与新格局研究分析',
}


def load_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def load_state() -> dict:
    if not STATE.exists():
        return {'completed_sources': sorted(INITIAL_DONE), 'runs': []}
    state = load_json(STATE)
    completed = set(state.get('completed_sources') or [])
    completed.update(INITIAL_DONE)
    state['completed_sources'] = sorted(completed)
    state.setdefault('runs', [])
    return state


def save_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    write_json(STATE, state)


def write_json(path: Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    tmp.replace(path)
    json.loads(path.read_text(encoding='utf-8'))


def item_count(ctx: dict) -> int:
    return sum(len(v or []) for v in (ctx.get('supply_chain') or {}).values())


def locate_raw(source: str) -> Path | None:
    for path in RAW.glob('*-full.md'):
        if source in path.stem:
            return path
    compact = re.sub(r'[：:，,\s]', '', source)
    for path in RAW.glob('*-full.md'):
        stem = re.sub(r'[：:，,\s]', '', path.stem)
        if compact and (compact in stem or stem.replace('-full', '') in compact):
            return path
    short = source.replace('报告', '').replace('分析', '').replace('研究', '')[:8]
    for path in RAW.glob('*-full.md'):
        if short and short in path.stem:
            return path
    return None


def has_raw(source: str) -> bool:
    return locate_raw(source) is not None


def score_candidate(source: str, ctx: dict) -> tuple:
    name = source + ' ' + str(ctx.get('concept') or '')
    prefer = 0 if any(x in name for x in PREFER) else 1
    return (prefer, item_count(ctx), len(ctx.get('evidence') or []), source)


def select_candidates(reports: dict, batch_size: int, max_items: int, max_evidence: int, done: set[str]) -> list[str]:
    rows = []
    for source, ctx in reports.items():
        if source in done:
            continue
        raw_path = locate_raw(source)
        if raw_path is None:
            continue
        items = item_count(ctx)
        evidence = len(ctx.get('evidence') or [])
        if items > max_items and evidence > max_evidence:
            continue
        rows.append((score_candidate(source, ctx), source, raw_path.name))
    rows.sort(key=lambda row: row[0])
    selected = []
    seen_raw = set()
    for _, source, raw_name in rows:
        if raw_name in seen_raw:
            continue
        selected.append(source)
        seen_raw.add(raw_name)
        if len(selected) >= batch_size:
            break
    return selected


def normalize_spaces(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip()


def compact(text: str) -> str:
    return re.sub(r'\s+', '', text or '')


def supported(item: str, text: str) -> bool:
    if not item:
        return False
    return item in text or compact(item) in compact(text)


def split_sentences(text: str) -> list[str]:
    pieces = re.split(r'(?<=[。！？；])\s*|\n+', text)
    return [normalize_spaces(x) for x in pieces if len(normalize_spaces(x)) >= 12]


def detect_layer(line: str, current: str | None) -> str | None:
    stripped = line.strip()
    if not stripped:
        return current
    for layer, hints in LAYER_HINTS.items():
        if any(h in stripped for h in hints):
            return layer
    return current


def clean_term(raw: str) -> str | None:
    term = normalize_spaces(raw)
    term = re.sub(r'^[（(、，,。；;：:\-—\s]+|[）)、，,。；;：:\-—\s]+$', '', term)
    term = term.strip('"“”‘’[]【】')
    if not term:
        return None
    if len(term) < 2 and not re.fullmatch(r'[A-Za-z0-9]{2,}', term):
        return None
    if len(term) > 24:
        return None
    if any(x in term for x in ['同比', '亿元', '万吨', '年复合', '数据', '显示', '预计', '达到', '增长', '下降', '占比']):
        return None
    if any(x in term for x in ['有限公司', '股份', '集团', '证券', '.SH', '.SZ', '（60', '（00', '（30', '（68']):
        return None
    if term in STOPWORDS:
        return None
    if re.fullmatch(r'[0-9.%-]+', term):
        return None
    if re.search(r'[\u4e00-\u9fffA-Za-z]', term) is None:
        return None
    return term


def split_terms(fragment: str) -> list[str]:
    fragment = re.sub(r'[（(][0-9A-Za-z.%-]+[）)]', '', fragment)
    fragment = re.sub(r'等(多个|行业|领域|产品|关键)?', '、', fragment)
    parts = re.split(r'[、，,；;\/｜|]|以及|及|和|与|或|到|至|为主|其次为|最终', fragment)
    terms = []
    for part in parts:
        cleaned = clean_term(part)
        if cleaned:
            terms.append(cleaned)
    return terms


def extract_fragments(line: str) -> list[str]:
    fragments = []
    for trigger in EXTRACT_TRIGGERS:
        if trigger not in line:
            continue
        tail = line.split(trigger, 1)[1]
        tail = re.split(r'[。；\n]', tail, 1)[0]
        if tail:
            fragments.append(tail)
    if '：' in line or ':' in line:
        tail = re.split(r'[：:]', line, 1)[1]
        tail = re.split(r'[。；\n]', tail, 1)[0]
        if tail:
            fragments.append(tail)
    return fragments


def extract_supply_chain(text: str, old_ctx: dict) -> dict:
    supply = {layer: [] for layer in LAYERS}
    seen = defaultdict(set)
    current_layer = None
    for line in text.splitlines():
        current_layer = detect_layer(line, current_layer)
        if not current_layer:
            continue
        if not any(trigger in line for trigger in EXTRACT_TRIGGERS) and '：' not in line and ':' not in line:
            continue
        for fragment in extract_fragments(line):
            for term in split_terms(fragment):
                if supported(term, text) and term not in seen[current_layer]:
                    supply[current_layer].append(term)
                    seen[current_layer].add(term)
    old_supply = old_ctx.get('supply_chain') or {}
    for layer in LAYERS:
        for term in old_supply.get(layer, []) or []:
            cleaned = clean_term(str(term))
            if cleaned and supported(cleaned, text) and cleaned not in seen[layer]:
                supply[layer].append(cleaned)
                seen[layer].add(cleaned)
    for layer in LAYERS:
        supply[layer] = supply[layer][:18]
    return supply


def extract_related(concept: str, source: str, supply: dict, text: str, old_ctx: dict) -> list[str]:
    related = []
    seen = set()
    seeds = [concept]
    seeds.extend(old_ctx.get('related_concepts') or [])
    for values in supply.values():
        seeds.extend(values)
    for term in seeds:
        cleaned = clean_term(str(term))
        if not cleaned or cleaned in seen:
            continue
        if supported(cleaned, text):
            related.append(cleaned)
            seen.add(cleaned)
        if len(related) >= 12:
            break
    if not related:
        fallback = clean_term(concept) or clean_term(source.replace('产业', '').replace('报告', ''))
        if fallback and supported(fallback, text):
            related.append(fallback)
    return related


def extract_evidence(text: str, old_ctx: dict, limit: int = 8) -> list[dict]:
    evidence = []
    seen = set()
    for sentence in split_sentences(text):
        if not any(trigger in sentence for trigger in EVIDENCE_TRIGGERS):
            continue
        if len(sentence) > 140:
            sentence = sentence[:140].rstrip('，,、；;')
        if sentence in seen:
            continue
        heading = '原文支撑'
        for key in ['产业链', '供应链', '上游', '中游', '下游', '技术路径', '技术方向', '应用领域', '生产路径', '成本构成']:
            if key in sentence:
                heading = key
                break
        evidence.append({'heading': heading, 'text': sentence})
        seen.add(sentence)
        if len(evidence) >= limit:
            break
    for item in old_ctx.get('evidence') or []:
        if len(evidence) >= limit:
            break
        if not isinstance(item, dict):
            continue
        sentence = str(item.get('text') or '').strip()
        if sentence and sentence in text and sentence not in seen:
            evidence.append({'heading': str(item.get('heading') or '原文支撑'), 'text': sentence})
            seen.add(sentence)
    return evidence


def parse_source_date(text: str) -> str:
    match = re.search(r'(20\d{2})年(\d{1,2})月(\d{1,2})日', text[:1000])
    if not match:
        return datetime.now().date().isoformat()
    year, month, day = match.groups()
    return f'{year}-{int(month):02d}-{int(day):02d}'


def build_context(source: str, old_ctx: dict, raw_path: Path) -> dict:
    text = raw_path.read_text(encoding='utf-8', errors='ignore')
    concept = str(old_ctx.get('concept') or source.replace('产业新变化与新格局', '').replace('深度研究报告', '').replace('研究分析', '').replace('报告', '')).strip()
    supply = extract_supply_chain(text, old_ctx)
    related = extract_related(concept, source, supply, text, old_ctx)
    evidence = extract_evidence(text, old_ctx)
    return {
        'source_name': source,
        'source_date': old_ctx.get('source_date') or parse_source_date(text),
        'concept': concept,
        'supply_chain': supply,
        'related_concepts': related,
        'evidence': evidence,
    }


def audit_context(source: str, ctx: dict, raw_path: Path) -> dict:
    text = raw_path.read_text(encoding='utf-8', errors='ignore')
    items = []
    for values in (ctx.get('supply_chain') or {}).values():
        items.extend(values or [])
    items.extend(ctx.get('related_concepts') or [])
    misses = [item for item in items if not supported(str(item), text)]
    return {'source': source, 'raw': raw_path.name, 'items': len(items), 'supported': len(items) - len(misses), 'misses': misses}


def validate_relations() -> dict:
    result = {}
    for name in ['report_contexts.json', 'entity_exposures.json', 'evidence_index.json']:
        path = REL / name
        json.loads(path.read_text(encoding='utf-8'))
        result[name] = 'ok'
    return result


def safe_name(value: str) -> str:
    return re.sub(r'[^0-9A-Za-z\u4e00-\u9fff._-]+', '-', value).strip('-')[:80] or 'theme'


def run_radar(concept: str, source: str) -> dict:
    RADAR_OUT.mkdir(parents=True, exist_ok=True)
    out = RADAR_OUT / f'{safe_name(concept)}-auto-context-check.md'
    proc = subprocess.run(
        [sys.executable, str(RADAR), '--term', concept, '--out', str(out)],
        cwd=str(FINANCE),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    hit = False
    if out.exists():
        body = out.read_text(encoding='utf-8', errors='ignore')
        hit = source in body or concept in body
    return {'concept': concept, 'out': str(out), 'returncode': proc.returncode, 'hit': hit, 'stderr': proc.stderr[-500:]}


def run_once(args, data: dict, batch_no: int) -> dict:
    reports = data['reports']
    state = load_state()
    done = set(state.get('completed_sources') or [])
    sources = select_candidates(reports, args.batch_size, args.max_items, args.max_evidence, done)
    changed = []
    audits = []
    radar = []
    if not sources:
        return {'batch': batch_no, 'sources': [], 'changed': [], 'audits': [], 'radar': [], 'empty': True}
    backup = None
    if args.apply:
        backup = CTX.with_name('report_contexts.backup-auto-fullmd-context-refine-' + datetime.now().strftime('%Y%m%d%H%M%S') + f'-batch{batch_no}.json')
        shutil.copy2(CTX, backup)
    for source in sources:
        raw_path = locate_raw(source)
        if not raw_path:
            continue
        old = reports.get(source, {})
        new_ctx = build_context(source, old, raw_path)
        audit = audit_context(source, new_ctx, raw_path)
        if audit['misses']:
            bad = set(audit['misses'])
            for layer, values in (new_ctx.get('supply_chain') or {}).items():
                new_ctx['supply_chain'][layer] = [x for x in values if x not in bad]
            new_ctx['related_concepts'] = [x for x in new_ctx.get('related_concepts') or [] if x not in bad]
            audit = audit_context(source, new_ctx, raw_path)
        change = {
            'source': source,
            'concept': new_ctx.get('concept'),
            'raw': raw_path.name,
            'old_items': item_count(old),
            'new_items': item_count(new_ctx),
            'old_evidence': len(old.get('evidence') or []),
            'new_evidence': len(new_ctx.get('evidence') or []),
            'related': len(new_ctx.get('related_concepts') or []),
        }
        if args.apply:
            reports[source] = new_ctx
        changed.append(change)
        audits.append(audit)
    if args.apply:
        data['updated'] = datetime.now().date().isoformat()
        write_json(CTX, data)
        state = load_state()
        completed = set(state.get('completed_sources') or [])
        completed.update(row['source'] for row in changed)
        state['completed_sources'] = sorted(completed)
        state.setdefault('runs', []).append({
            'time': datetime.now().isoformat(timespec='seconds'),
            'batch': batch_no,
            'sources': [row['source'] for row in changed],
            'backup': str(backup) if backup else None,
            'radar': bool(args.radar),
        })
        save_state(state)
    validation = validate_relations()
    if args.radar:
        for row in changed:
            radar.append(run_radar(row['concept'], row['source']))
    return {'batch': batch_no, 'sources': sources, 'backup': str(backup) if backup else None, 'changed': changed, 'audits': audits, 'radar': radar, 'validation': validation, 'empty': False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch-size', type=int, default=3)
    parser.add_argument('--batches', type=int, default=1)
    parser.add_argument('--max-items', type=int, default=999)
    parser.add_argument('--max-evidence', type=int, default=999)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--radar', action='store_true')
    parser.add_argument('--unsafe-surface-extract', action='store_true')
    args = parser.parse_args()
    if not args.unsafe_surface_extract:
        raise SystemExit('disabled: this script performs surface extraction, not full.md deep read. Use scripts/deep_read_report_context_workflow.py instead.')
    data = load_json(CTX)
    results = []
    for batch_no in range(1, args.batches + 1):
        result = run_once(args, data, batch_no)
        results.append(result)
        if result.get('empty'):
            break
        if args.apply:
            data = load_json(CTX)
    failed_audit = [r for batch in results for r in batch.get('audits', []) if r.get('misses')]
    output = {'apply': args.apply, 'batch_size': args.batch_size, 'batches_requested': args.batches, 'results': results, 'failed_audit_count': len(failed_audit)}
    print(json.dumps(output, ensure_ascii=False, indent=2))
    if failed_audit:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
