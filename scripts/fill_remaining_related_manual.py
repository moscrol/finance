#!/usr/bin/env python3
import json
import shutil
from datetime import date
from pathlib import Path

PATH = Path('/Users/lbq/Desktop/c c/知识库/wiki/relations/concept_graph.json')
SOURCE = '[[theme-radar-structure-fix]]'
MANUAL = {
    'CXO': '医药生物',
    '化工出海': '新材料',
    '大众品提价': '消费电子',
    '环保助剂': '新材料',
    '电解铝': '新材料',
    '砷化镓外延片': '半导体',
    '硅微粉': '新材料',
    '词元经济': '人工智能',
    '驱蚊': '消费电子',
}


def main():
    shutil.copy2(PATH, Path(str(PATH) + '.bak-remaining-related-manual'))
    graph = json.loads(PATH.read_text(encoding='utf-8'))
    concepts = graph.get('concepts') or {}
    filled = []
    for name, target in MANUAL.items():
        node = concepts.get(name)
        if not node or node.get('related_concepts') or target not in concepts:
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
