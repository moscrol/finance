#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

TARGET = Path('/Users/lbq/Desktop/c c/知识库/wiki/relations/report_contexts.json')
REMOVALS = {
    '稀土永磁产业新变化与新格局深度研究报告': ['永磁直驱风力发电机'],
    '油运产业深度研究报告：十六年熊市后的历史性拐点': ['中东 - 中国航线', '美湾至亚洲航线', '南美到亚洲航线'],
    '中国盾构机产业新格局与投资机会深度研究报告': ['智能制造'],
}


def main() -> None:
    data = json.loads(TARGET.read_text(encoding='utf-8'))
    backup = TARGET.with_name('report_contexts.backup-batch9-support-fix-' + datetime.now().strftime('%Y%m%d%H%M%S') + '.json')
    shutil.copy2(TARGET, backup)
    removed = []
    for source, bad_items in REMOVALS.items():
        ctx = data['reports'][source]
        bad = set(bad_items)
        for layer, values in (ctx.get('supply_chain') or {}).items():
            kept = [x for x in values if x not in bad]
            removed.extend((source, layer, x) for x in values if x in bad)
            ctx['supply_chain'][layer] = kept
        old_related = ctx.get('related_concepts') or []
        ctx['related_concepts'] = [x for x in old_related if x not in bad]
        removed.extend((source, 'related_concepts', x) for x in old_related if x in bad)
    tmp = TARGET.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    tmp.replace(TARGET)
    json.loads(TARGET.read_text(encoding='utf-8'))
    print(json.dumps({'backup': str(backup), 'removed': removed}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
