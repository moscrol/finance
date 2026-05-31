#!/usr/bin/env python3
import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
EXPOSURES = WIKI / 'relations/entity_exposures.json'
RESULT = WIKI / 'raw/theme-radar/theme-radar-role-fix-result.json'

FIXES = {
    ('无人驾驶', '万集科技'): {
        'role': '激光雷达/MEMS固态雷达供应商，适配城市NOA与L4客车场景',
        'chain_layer': 'upstream_components',
    },
    ('无人驾驶', '保隆科技'): {
        'role': '毫米波雷达与汽车传感器供应商',
        'chain_layer': 'upstream_components',
    },
    ('无人驾驶', '四维图新'): {
        'role': '高精地图与智能驾驶数据服务商',
        'chain_layer': 'midstream_service',
    },
    ('无人驾驶', '德赛西威'): {
        'role': '智能驾驶域控制器供应商',
        'chain_layer': 'upstream_components',
    },
    ('无人驾驶', '拓普集团'): {
        'role': '智能底盘供应商',
        'chain_layer': 'upstream_components',
    },
    ('无人驾驶', '比亚迪'): {
        'role': '新能源汽车整车厂商与智能驾驶车型应用方',
        'chain_layer': 'downstream_application',
        'review_required': True,
    },
    ('无人驾驶', '富临运业'): {
        'chain_layer': 'downstream_operation',
    },
    ('创新药', '凯莱英'): {
        'role': '小分子创新药CDMO服务商',
        'chain_layer': 'midstream_service',
    },
    ('创新药', '九洲药业'): {
        'role': '创新药定制研发生产/CDMO服务商',
        'chain_layer': 'midstream_service',
    },
    ('创新药', '信立泰'): {
        'chain_layer': 'midstream_manufacturing',
    },
    ('创新药', '上海医药'): {
        'role': '医药流通渠道潜在相关',
        'chain_layer': 'downstream_application',
    },
    ('无人驾驶', '千里科技'): {
        'role': 'Robotaxi闭环平台服务商',
        'chain_layer': 'midstream_service',
    },
}


def load_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def backup(path):
    target = Path(str(path) + '.bak-theme-radar-role-fix-' + datetime.now().strftime('%Y%m%d%H%M%S'))
    shutil.copy2(path, target)
    return str(target.relative_to(WIKI))


def exposure(data, theme, company):
    ent = (data.get('entities') or {}).get(company) or {}
    return (ent.get('concepts') or {}).get(theme)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    data = load_json(EXPOSURES)
    rows = []
    for (theme, company), fields in FIXES.items():
        exp = exposure(data, theme, company)
        if exp is None:
            rows.append({'theme': theme, 'company': company, 'status': 'missing', 'changes': []})
            continue
        changes = []
        for field, new in fields.items():
            old = exp.get(field)
            if old != new:
                changes.append({'field': field, 'old': old, 'new': new})
                if args.apply:
                    exp[field] = new
        rows.append({'theme': theme, 'company': company, 'status': 'change' if changes else 'unchanged', 'changes': changes})
    backups = []
    if args.apply and any(row['changes'] for row in rows):
        backups.append(backup(EXPOSURES))
        data['updated'] = datetime.now().date().isoformat()
        write_json(EXPOSURES, data)
    result = {
        'timestamp': datetime.now().isoformat(timespec='seconds'),
        'mode': 'apply' if args.apply else 'dry_run',
        'target': str(EXPOSURES.relative_to(WIKI)),
        'backups': backups,
        'changes_count': sum(len(row['changes']) for row in rows),
        'rows': rows,
    }
    write_json(RESULT, result)
    print(json.dumps({k: v for k, v in result.items() if k != 'rows'}, ensure_ascii=False, indent=2))
    print(RESULT)


if __name__ == '__main__':
    main()
