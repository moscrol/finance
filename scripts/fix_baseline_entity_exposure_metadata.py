#!/usr/bin/env python3
import json
import shutil
from collections import Counter
from datetime import date, datetime
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
REL = WIKI / 'relations'
EXPOSURES = REL / 'entity_exposures.json'
RESULT = WIKI / 'raw/theme-radar/baseline-entity-exposure-metadata-fix-result.json'
BACKUP_SUFFIX = '.bak-baseline-metadata-fix'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def inferred_baseline(exp):
    update_type = str(exp.get('update_type') or '').strip()
    if update_type == 'baseline':
        return True
    if update_type:
        return False
    sources = ' '.join(str(x) for x in exp.get('sources', []) or [])
    return 'iFinD baseline' in sources or 'AkShare baseline' in sources or 'Baseline' in sources


def main():
    exposures = load(EXPOSURES)
    backup = Path(str(EXPOSURES) + BACKUP_SUFFIX)
    shutil.copy2(EXPOSURES, backup)
    counts = Counter()
    sample = []
    for entity, data in (exposures.get('entities') or {}).items():
        for concept, exp in (data.get('concepts') or {}).items():
            if not inferred_baseline(exp):
                continue
            counts['baseline_edges_seen'] += 1
            changed = False
            if not exp.get('update_type'):
                exp['update_type'] = 'baseline'
                counts['update_type_patched'] += 1
                changed = True
            if not exp.get('evidence_layer'):
                exp['evidence_layer'] = 'L1'
                counts['evidence_layer_patched'] += 1
                changed = True
            if not exp.get('confidence'):
                exp['confidence'] = 'medium'
                counts['confidence_patched'] += 1
                changed = True
            if changed:
                exp['updated'] = date.today().isoformat()
                counts['rows_changed'] += 1
                if len(sample) < 80:
                    sample.append({'entity': entity, 'concept': concept})
    write(EXPOSURES, exposures)
    result = {
        'timestamp': datetime.now().isoformat(timespec='seconds'),
        'backup': str(backup.relative_to(WIKI)),
        'counts': dict(counts),
        'changed_sample': sample,
    }
    write(RESULT, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
