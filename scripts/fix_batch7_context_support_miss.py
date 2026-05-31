#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

TARGET = Path('/Users/lbq/Desktop/c c/知识库/wiki/relations/report_contexts.json')
SOURCE = '培育钻石产业新变化与新格局研究报告'
BAD = '微波等离子体化学气相沉积设备'


def main() -> None:
    data = json.loads(TARGET.read_text(encoding='utf-8'))
    backup = TARGET.with_name('report_contexts.backup-batch7-support-fix-' + datetime.now().strftime('%Y%m%d%H%M%S') + '.json')
    shutil.copy2(TARGET, backup)
    chain = data['reports'][SOURCE]['supply_chain']
    removed = 0
    for layer, values in chain.items():
        kept = [x for x in values if x != BAD]
        removed += len(values) - len(kept)
        chain[layer] = kept
    tmp = TARGET.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    tmp.replace(TARGET)
    json.loads(TARGET.read_text(encoding='utf-8'))
    print(json.dumps({'backup': str(backup), 'removed': removed}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
