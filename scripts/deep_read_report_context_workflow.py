#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

FINANCE = Path('/Users/lbq/Desktop/c c/金融')
RAW = Path('/Users/lbq/Desktop/c c/知识库/raw')
WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
REL = WIKI / 'relations'
CTX = REL / 'report_contexts.json'
STATE = WIKI / 'raw/theme-radar/fullmd-report-context-refine-state.json'
RADAR = FINANCE / 'skills/theme-radar/scripts/radar.py'
RADAR_OUT = WIKI / 'raw/theme-radar/regression'
LAYERS = ['upstream_materials', 'upstream_equipment', 'midstream', 'downstream', 'ecosystem']

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


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path: Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    tmp.replace(path)
    json.loads(path.read_text(encoding='utf-8'))


def load_state() -> dict:
    if not STATE.exists():
        return {'mode': 'manual_deep_read_only', 'completed_sources': sorted(INITIAL_DONE), 'runs': []}
    state = load_json(STATE)
    completed = set(state.get('completed_sources') or [])
    completed.update(INITIAL_DONE)
    state['completed_sources'] = sorted(completed)
    state.setdefault('runs', [])
    state['mode'] = 'manual_deep_read_only'
    return state


def locate_raw(source: str) -> Path | None:
    for path in RAW.glob('*-full.md'):
        if source in path.stem:
            return path
    compact_source = re.sub(r'[：:，,\s]', '', source)
    for path in RAW.glob('*-full.md'):
        compact_stem = re.sub(r'[：:，,\s]', '', path.stem)
        if compact_source and (compact_source in compact_stem or compact_stem.replace('-full', '') in compact_source):
            return path
    short = source.replace('报告', '').replace('分析', '').replace('研究', '')[:8]
    for path in RAW.glob('*-full.md'):
        if short and short in path.stem:
            return path
    return None


def item_count(ctx: dict) -> int:
    return sum(len(v or []) for v in (ctx.get('supply_chain') or {}).values())


def select_next() -> dict:
    reports = load_json(CTX)['reports']
    done = set(load_state().get('completed_sources') or [])
    rows = []
    seen_raw = set()
    for source, ctx in reports.items():
        if source in done:
            continue
        raw = locate_raw(source)
        if raw is None or raw.name in seen_raw:
            continue
        seen_raw.add(raw.name)
        rows.append((item_count(ctx), len(ctx.get('evidence') or []), source, raw))
    rows.sort(key=lambda row: (row[0], row[1], row[2]))
    if not rows:
        return {'empty': True}
    _, _, source, raw = rows[0]
    ctx = reports[source]
    return {
        'empty': False,
        'source': source,
        'concept': ctx.get('concept'),
        'raw': str(raw),
        'current_items': item_count(ctx),
        'current_related': len(ctx.get('related_concepts') or []),
        'current_evidence': len(ctx.get('evidence') or []),
    }


def compact(text: str) -> str:
    return re.sub(r'\s+', '', text or '')


def supported(item: str, text: str) -> bool:
    return bool(item) and (item in text or compact(item) in compact(text))


def audit_context(source: str, ctx: dict) -> dict:
    raw = locate_raw(source)
    if raw is None:
        return {'source': source, 'error': 'raw_not_found'}
    text = raw.read_text(encoding='utf-8', errors='ignore')
    items = []
    for layer in LAYERS:
        items.extend((ctx.get('supply_chain') or {}).get(layer) or [])
    items.extend(ctx.get('related_concepts') or [])
    misses = [str(item) for item in items if not supported(str(item), text)]
    evidence_misses = []
    for item in ctx.get('evidence') or []:
        if isinstance(item, dict):
            ev_text = str(item.get('text') or '').strip()
            if ev_text and ev_text not in text and compact(ev_text) not in compact(text):
                evidence_misses.append(ev_text)
    return {
        'source': source,
        'raw': raw.name,
        'items': len(items),
        'supported': len(items) - len(misses),
        'misses': misses,
        'evidence_misses': evidence_misses,
    }


def validate_context(source: str, ctx: dict) -> dict:
    errors = []
    if ctx.get('source_name') != source:
        errors.append('source_name_mismatch')
    if not ctx.get('concept'):
        errors.append('missing_concept')
    supply = ctx.get('supply_chain')
    if not isinstance(supply, dict):
        errors.append('missing_supply_chain')
    else:
        for layer in LAYERS:
            if layer not in supply or not isinstance(supply.get(layer), list):
                errors.append(f'missing_layer:{layer}')
    if not isinstance(ctx.get('related_concepts'), list):
        errors.append('missing_related_concepts')
    if not isinstance(ctx.get('evidence'), list) or not ctx.get('evidence'):
        errors.append('missing_evidence')
    audit = audit_context(source, ctx)
    if audit.get('misses'):
        errors.append('unsupported_items')
    if audit.get('evidence_misses'):
        errors.append('unsupported_evidence')
    return {'ok': not errors, 'errors': errors, 'audit': audit}


def safe_name(value: str) -> str:
    return re.sub(r'[^0-9A-Za-z\u4e00-\u9fff._-]+', '-', value).strip('-')[:80] or 'theme'


def run_radar(concept: str, source: str) -> dict:
    RADAR_OUT.mkdir(parents=True, exist_ok=True)
    out = RADAR_OUT / f'{safe_name(concept)}-manual-context-check.md'
    proc = subprocess.run([sys.executable, str(RADAR), '--term', concept, '--out', str(out)], cwd=str(FINANCE), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    body = out.read_text(encoding='utf-8', errors='ignore') if out.exists() else ''
    return {'concept': concept, 'out': str(out), 'returncode': proc.returncode, 'hit': source in body or concept in body, 'stderr': proc.stderr[-500:]}


def apply_context(path: Path, run_radar_check: bool) -> dict:
    payload = load_json(path)
    source = payload.get('source_name')
    if not source:
        raise SystemExit('context payload missing source_name')
    result = validate_context(source, payload)
    if not result['ok']:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(1)
    data = load_json(CTX)
    old = data['reports'].get(source, {})
    stamp = datetime.now().strftime('%Y%m%d%H%M%S')
    backup = CTX.with_name(f'report_contexts.backup-manual-deep-read-{stamp}.json')
    shutil.copy2(CTX, backup)
    data['reports'][source] = payload
    data['updated'] = datetime.now().date().isoformat()
    write_json(CTX, data)
    for name in ['report_contexts.json', 'entity_exposures.json', 'evidence_index.json']:
        json.loads((REL / name).read_text(encoding='utf-8'))
    state = load_state()
    completed = set(state.get('completed_sources') or [])
    completed.add(source)
    state['completed_sources'] = sorted(completed)
    run = {
        'time': datetime.now().isoformat(timespec='seconds'),
        'mode': 'manual_deep_read',
        'source': source,
        'concept': payload.get('concept'),
        'old_items': item_count(old),
        'new_items': item_count(payload),
        'backup': str(backup),
        'audit': result['audit'],
    }
    if run_radar_check:
        run['radar'] = run_radar(str(payload.get('concept') or source), source)
    state.setdefault('runs', []).append(run)
    write_json(STATE, state)
    return run


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='cmd', required=True)
    sub.add_parser('next')
    apply_parser = sub.add_parser('apply')
    apply_parser.add_argument('context_json')
    apply_parser.add_argument('--radar', action='store_true')
    args = parser.parse_args()
    if args.cmd == 'next':
        print(json.dumps(select_next(), ensure_ascii=False, indent=2))
    elif args.cmd == 'apply':
        print(json.dumps(apply_context(Path(args.context_json), args.radar), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
