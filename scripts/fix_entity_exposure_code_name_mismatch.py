#!/usr/bin/env python3
import json
import shutil
from copy import deepcopy
from datetime import datetime
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
EXPOSURES = WIKI / 'relations/entity_exposures.json'
AUDIT = WIKI / 'raw/theme-radar/entity-exposure-pollution-audit.json'
OUT = WIKI / 'raw/theme-radar/entity-exposure-code-name-mismatch-fix-result.json'
BACKUP = WIKI / 'relations/entity_exposures.json.bak-code-name-mismatch'


def load_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def merge_unique(a, b):
    out = []
    seen = set()
    for item in (a or []) + (b or []):
        item = str(item).strip()
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def choose_value(old, new):
    return old if str(old or '').strip() else new


def merge_exposure(existing, incoming):
    merged = deepcopy(existing or {})
    incoming = incoming or {}
    for key in ['role', 'strength', 'evidence', 'confidence', 'chain_layer', 'evidence_layer', 'update_type', 'updated']:
        merged[key] = choose_value(merged.get(key), incoming.get(key))
    merged['sources'] = merge_unique(merged.get('sources', []), incoming.get('sources', []))
    for key, value in incoming.items():
        if key not in merged:
            merged[key] = value
    return merged


def main():
    data = load_json(EXPOSURES)
    audit = load_json(AUDIT)
    rows = audit['queues']['high_confidence_code_name_mismatch']
    moves = []
    skipped = []

    if not BACKUP.exists():
        shutil.copy2(EXPOSURES, BACKUP)

    entities = data.setdefault('entities', {})
    for row in rows:
        src = row['entity']
        candidates = row.get('code_candidates', [])
        if len(candidates) != 1:
            skipped.append({'entity': src, 'reason': 'candidate_not_unique', 'candidate_count': len(candidates)})
            continue
        dst = candidates[0]['name']
        if src == dst:
            skipped.append({'entity': src, 'reason': 'same_name'})
            continue
        if src not in entities:
            skipped.append({'entity': src, 'reason': 'source_missing'})
            continue
        src_ent = entities[src]
        dst_ent = entities.setdefault(dst, {'name': dst, 'codes': [], 'concepts': {}})
        dst_ent['name'] = dst
        dst_ent['codes'] = merge_unique(dst_ent.get('codes', []), src_ent.get('codes', []))
        dst_concepts = dst_ent.setdefault('concepts', {})
        moved_concepts = []
        merged_concepts = []
        for concept, exp in (src_ent.get('concepts', {}) or {}).items():
            if concept in dst_concepts:
                dst_concepts[concept] = merge_exposure(dst_concepts[concept], exp)
                merged_concepts.append(concept)
            else:
                dst_concepts[concept] = exp
                moved_concepts.append(concept)
        del entities[src]
        moves.append({
            'from': src,
            'to': dst,
            'codes': src_ent.get('codes', []),
            'moved_concepts': moved_concepts,
            'merged_concepts': merged_concepts,
        })

    result = {
        'timestamp': datetime.now().isoformat(timespec='seconds'),
        'backup': str(BACKUP.relative_to(WIKI)),
        'moved_count': len(moves),
        'skipped_count': len(skipped),
        'moves': moves,
        'skipped': skipped,
    }
    EXPOSURES.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
