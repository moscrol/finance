#!/usr/bin/env python3
import json
import re
from datetime import date
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
AUDIT = WIKI / 'raw/theme-radar/missing-wikilinks-audit.json'
OUT = WIKI / 'raw/theme-radar/low-risk-longtail-tech-stubs-batch1-result.json'
TARGETS = [
    'RWA代币化', 'Micro-OLED', 'HBM4', '全固态电池', '涂覆隔膜', 'AI PC', 'ASIC芯片',
    '5G-A', 'TSV', '新能源汽车热管理', '电池回收', '传感器技术', '冷板式液冷', 'TPU',
    'rPET', 'PP铜箔', 'LCD', 'BCI', 'CBN', '硅材料', '晶圆制造材料', '水电镀设备',
    '电镀设备', 'LED电子器件', '光伏电池组件', 'EVA', 'POE', '膜材料', '功能高分子材料',
    '光学膜材料', 'MIM', '数字芯片设计', 'ICT设备', 'EMI屏蔽材料', 'IVD流通', '类ABF材料',
    'TAC膜产业', 'AI金融', 'PWM控制器', 'g线光刻胶', 'i线光刻胶', 'AI平台', 'AI语音',
    'TCO镀膜', '体外诊断IVD', 'FDA认证', 'AI医疗', 'MCU芯片', 'LED照明', 'OLED照明',
    'AI短剧', 'IP改编', '特斯拉Optimus', '超高分子量聚乙烯(UHMWPE)', 'AI处理器', 'ITO导电膜'
]


def safe_filename(value):
    return re.sub(r'[/:*?"<>|\n\r\t]+', '_', str(value)).strip()


def yaml_list(values):
    return '[' + ', '.join(json.dumps(v, ensure_ascii=False) for v in values) + ']'


def infer_tags(name):
    tags = ['概念', '长尾技术词', '待补证', 'missing-wikilink-backfill']
    for token in ['AI', '芯片', '半导体', '电池', '光刻', '封装', '材料', '膜', '医疗', '光伏', '液冷', '热管理', '传感器', '软件', '数据']:
        if token in name and token not in tags:
            tags.append(token)
    return tags


def render_stub(row):
    name = row['target']
    today = date.today().isoformat()
    log_entry = f"created as low-risk longtail technical concept stub; count={row.get('count', 0)}"
    lines = [
        '---', f'title: {name}', f'tags: {yaml_list(infer_tags(name))}', f'created: {today}', f'updated: {today}',
        'revision: 1', 'sources: []', f'log: {yaml_list([log_entry])}', '---', '', f'# {name}', '',
        '占位概念页：该长尾技术词由 missing wikilinks 队列自动生成，用于修复断链和承接后续定义补全。', '',
        '## 速览', '', '| 维度 | 内容 |', '|---|---|', '| 概念状态 | 待补证 |',
        f'| missing wikilink 频次 | {row.get("count", 0)} |',
        f'| 来源目录分布 | {json.dumps(row.get("source_dirs", {}), ensure_ascii=False)} |',
        '| 当前用途 | 长尾技术词归一 / 后续 concept graph 补全 |', '', '## 待补证定义', '',
        '- [ ] 补充一句话定义。', '- [ ] 判断是否应并入已有上位概念或保留独立概念。', '- [ ] 补充至少 1 个 source 或 raw 证据。',
        '', '## 首批出现位置', ''
    ]
    for ex in row.get('examples', [])[:5]:
        lines.append(f'- `{ex}`')
    lines.extend(['', '## 相关概念', '', '待补充。', '', '## 相关实体', '', '待补充。', ''])
    return '\n'.join(lines)


def main():
    data = json.loads(AUDIT.read_text(encoding='utf-8'))
    by_target = {r['target']: r for r in data['items']}
    created = []
    skipped = []
    missing_from_audit = []
    for target in TARGETS:
        row = by_target.get(target)
        if not row:
            missing_from_audit.append(target)
            continue
        if row.get('count') not in (2, 3):
            skipped.append({'target': target, 'reason': f"count_not_2_or_3:{row.get('count')}"})
            continue
        path = WIKI / 'concepts' / f'{safe_filename(target)}.md'
        if path.exists():
            skipped.append({'target': target, 'reason': 'exists', 'file': str(path.relative_to(WIKI))})
            continue
        path.write_text(render_stub(row), encoding='utf-8')
        created.append({'target': target, 'count': row.get('count'), 'category': row.get('category'), 'file': str(path.relative_to(WIKI))})
    result = {'target_count': len(TARGETS), 'created_count': len(created), 'skipped_count': len(skipped), 'missing_from_audit': missing_from_audit, 'created': created, 'skipped': skipped}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
