#!/usr/bin/env python3
import json
import re
from pathlib import Path

BASE = Path('/Users/lbq/Desktop/c c/知识库/wiki/raw/ifind-baseline')

def batch_num(path):
    m = re.search(r'batch(\d+)\.json$', path.name)
    return int(m.group(1)) if m else 0

def backup(path):
    b = path.with_suffix(path.suffix + '.bak-top-concepts')
    if not b.exists():
        b.write_text(path.read_text(encoding='utf-8'), encoding='utf-8')

def main():
    changed = []
    for path in sorted(BASE.glob('baseline-updates-*-batch*.json'), key=batch_num):
        if not (1 <= batch_num(path) <= 70):
            continue
        data = json.loads(path.read_text(encoding='utf-8'))
        touched = False
        for update in data.get('updates', []) or []:
            existing = [str(x).strip() for x in update.get('concepts', []) or [] if str(x).strip()]
            merged = []
            for x in existing:
                if x not in merged:
                    merged.append(x)
            for exp in update.get('exposures', []) or []:
                concept = str(exp.get('concept') or '').strip()
                if concept and concept not in merged:
                    merged.append(concept)
            if merged and merged != existing:
                update['concepts'] = merged
                touched = True
                changed.append({'batch': batch_num(path), 'file': path.name, 'company': update.get('company'), 'concepts': merged})
        if touched:
            backup(path)
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'changed_updates': len(changed), 'samples': changed[:40]}, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
