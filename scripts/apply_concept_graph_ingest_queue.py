#!/usr/bin/env python3
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

FINANCE = Path('/Users/lbq/Desktop/c c/金融')
WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
QUEUE = WIKI / 'raw/theme-radar/concept-graph-ingest-queue.json'
RESULT = WIKI / 'raw/theme-radar/concept-graph-ingest-apply-result.json'
REL = WIKI / 'relations'

sys.path.insert(0, str(FINANCE / 'skills/lib'))
from knowledge_graph import update_concept_graph  # noqa: E402

BACKUP_SUFFIX = '.bak-concept-graph-ingest'


def backup(path):
    if path.exists():
        bak = Path(str(path) + BACKUP_SUFFIX)
        if not bak.exists():
            shutil.copy2(path, bak)
        return str(bak.relative_to(WIKI))
    return ''


def main():
    data = json.loads(QUEUE.read_text(encoding='utf-8'))
    backups = []
    for name in ['concept_graph.json', 'entity_exposures.json', 'aliases.json', 'evidence_index.json']:
        b = backup(REL / name)
        if b:
            backups.append(b)

    applied = []
    failed = []
    for item in data.get('items', []):
        concept = item['concept']
        try:
            update_concept_graph(
                concept,
                source_name='theme-radar-db-quality-audit',
                source_date=datetime.now().date().isoformat(),
                parent_concepts=item.get('parent_concepts', []),
                related_concepts=item.get('related_concepts', []),
                supply_chain=item.get('supply_chain', {}),
                companies=item.get('companies', []),
                evidence=item.get('evidence', ''),
                confidence=item.get('confidence', 'medium'),
                aliases=[],
            )
            applied.append({'concept': concept, 'companies': len(item.get('companies', [])), 'parents': item.get('parent_concepts', [])})
        except Exception as exc:
            failed.append({'concept': concept, 'error': str(exc)})

    result = {
        'timestamp': datetime.now().isoformat(timespec='seconds'),
        'queue': str(QUEUE.relative_to(WIKI)),
        'backups': backups,
        'applied_count': len(applied),
        'failed_count': len(failed),
        'applied': applied,
        'failed': failed,
    }
    RESULT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if failed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
