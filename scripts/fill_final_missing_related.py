#!/usr/bin/env python3
import json
import shutil
from datetime import date
from pathlib import Path

PATH = Path('/Users/lbq/Desktop/c c/知识库/wiki/relations/concept_graph.json')
SOURCE = '[[theme-radar-structure-fix]]'
ANCHORS = {
    '新兴技术': '新兴技术',
    '医药生物': '医药生物',
    '新能源': '新能源',
}


def main():
    shutil.copy2(PATH, Path(str(PATH) + '.bak-final-related-fill'))
    graph = json.loads(PATH.read_text(encoding='utf-8'))
    concepts = graph.get('concepts') or {}
    filled = []
    for name, node in concepts.items():
        if node.get('related_concepts'):
            continue
        parent = (node.get('parents') or ['新兴技术'])[0]
        target = ANCHORS.get(parent, '新兴技术')
        if target == name or target not in concepts:
            target = '新兴技术'
        if target == name or target not in concepts:
            continue
        node['related_concepts'] = [target]
        if not any(row.get('from') == name and row.get('to') == target and row.get('type') == '相关' for row in graph.get('relations') or []):
            graph.setdefault('relations', []).append({
                'from': name,
                'to': target,
                'type': '相关',
                'source': SOURCE,
                'confidence': node.get('confidence') or 'low',
                'updated': date.today().isoformat(),
            })
        filled.append({'concept': name, 'related': target})
    PATH.write_text(json.dumps(graph, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'filled': len(filled), 'items': filled}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
