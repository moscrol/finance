#!/usr/bin/env python3
import json
import shutil
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
ENTITIES = WIKI / 'entities'
RAW_IFIND = WIKI / 'raw/ifind-baseline'
REL = WIKI / 'relations'
ARCHIVE = WIKI / 'archive'
RAW_QUAR = ARCHIVE / 'quarantine/ifind-overlimit-raw'
ENTITY_BAK_ARCHIVE = ARCHIVE / 'entity-backups'

OVERLIMIT_NAMES = {'天赐材料', '天宜上佳', '比亚迪', '天智航', '新易盛', '天禄科技', '天源迪科'}


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def dump(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def backup(path, suffix):
    b = path.with_suffix(path.suffix + suffix)
    if not b.exists():
        b.write_text(path.read_text(encoding='utf-8'), encoding='utf-8')


def quarantine_overlimit_raw():
    RAW_QUAR.mkdir(parents=True, exist_ok=True)
    moved = []
    for name in OVERLIMIT_NAMES:
        for path in RAW_IFIND.glob(f'{name}*.json'):
            dest = RAW_QUAR / path.name
            if dest.exists():
                continue
            shutil.move(str(path), str(dest))
            moved.append({'from': str(path.relative_to(WIKI)), 'to': str(dest.relative_to(WIKI))})
    manifest = RAW_QUAR / 'README.md'
    manifest.write_text('# Quarantined iFinD overlimit raw files\n\n这些 raw 文件为空壳或超限错误输出，避免后续 agent 误用。\n\n' + '\n'.join(f"- `{x['to']}`" for x in moved) + '\n', encoding='utf-8')
    return moved


def archive_entity_backups():
    ENTITY_BAK_ARCHIVE.mkdir(parents=True, exist_ok=True)
    moved = []
    for path in sorted(ENTITIES.iterdir()):
        if not path.is_file() or '.bak' not in path.name:
            continue
        dest = ENTITY_BAK_ARCHIVE / path.name
        if dest.exists():
            idx = 1
            while True:
                candidate = ENTITY_BAK_ARCHIVE / f'{path.name}.{idx}'
                if not candidate.exists():
                    dest = candidate
                    break
                idx += 1
        shutil.move(str(path), str(dest))
        moved.append({'from': str(path.relative_to(WIKI)), 'to': str(dest.relative_to(WIKI))})
    return moved


def downgrade_core_l1_graph_only_exposures():
    path = REL / 'entity_exposures.json'
    data = load(path)
    changes = []
    for company, node in (data.get('entities') or {}).items():
        for concept, exp in ((node or {}).get('concepts') or {}).items():
            if not isinstance(exp, dict):
                continue
            if exp.get('strength') == 'core' and exp.get('evidence_layer') == 'L1' and exp.get('update_type') == 'graph_only':
                before = {'strength': exp.get('strength'), 'confidence': exp.get('confidence')}
                exp['strength'] = 'related'
                exp['confidence'] = 'low' if not exp.get('confidence') else exp.get('confidence')
                exp['qc_note'] = '降级：core + L1 + graph_only 缺少 L2/L3 支撑，避免 theme-radar 自动高排。'
                changes.append({'company': company, 'concept': concept, 'before': before, 'after': {'strength': exp.get('strength'), 'confidence': exp.get('confidence')}})
    if changes:
        backup(path, '.bak-core-l1-graph-only-downgrade')
        dump(path, data)
    return changes


def downgrade_core_l1_graph_only_evidence_index():
    path = REL / 'evidence_index.json'
    data = load(path)
    count = 0
    def walk(obj):
        nonlocal count
        if isinstance(obj, dict):
            if obj.get('strength') == 'core' and obj.get('evidence_layer') == 'L1' and obj.get('update_type') == 'graph_only':
                obj['strength'] = 'related'
                obj['qc_note'] = '降级：core + L1 + graph_only 缺少 L2/L3 支撑，避免 theme-radar 自动高排。'
                count += 1
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for x in obj:
                walk(x)
    walk(data)
    if count:
        backup(path, '.bak-core-l1-graph-only-downgrade')
        dump(path, data)
    return count


def main():
    result = {
        'quarantined_overlimit_raw': quarantine_overlimit_raw(),
        'archived_entity_backups': archive_entity_backups(),
        'downgraded_entity_exposures': downgrade_core_l1_graph_only_exposures(),
        'downgraded_evidence_index_items': downgrade_core_l1_graph_only_evidence_index(),
    }
    print(json.dumps({
        'quarantined_overlimit_raw_count': len(result['quarantined_overlimit_raw']),
        'archived_entity_backups_count': len(result['archived_entity_backups']),
        'downgraded_entity_exposures_count': len(result['downgraded_entity_exposures']),
        'downgraded_evidence_index_items': result['downgraded_evidence_index_items'],
        'samples': {
            'raw': result['quarantined_overlimit_raw'][:10],
            'downgraded': result['downgraded_entity_exposures'][:10],
        }
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
