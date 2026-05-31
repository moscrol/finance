#!/usr/bin/env python3
import json
import re
from pathlib import Path

BASE = Path('/Users/lbq/Desktop/c c/知识库/wiki')
BATCH = BASE / 'raw/ifind-baseline/baseline-updates-2026-05-26-batch88.json'

def cells(line):
    return [c.strip() for c in line.strip().strip('|').split('|')]

def tables(text):
    current = []
    for line in str(text).splitlines():
        if line.lstrip().startswith('|'):
            current.append(line.rstrip())
        elif current:
            if len(current) >= 3:
                yield current
            current = []
    if len(current) >= 3:
        yield current

def parse_table(table):
    headers = cells(table[0])
    rows = []
    for line in table[2:]:
        row_cells = cells(line)
        if len(row_cells) < len(headers):
            row_cells += [''] * (len(headers) - len(row_cells))
        rows.append(dict(zip(headers, row_cells)))
    return headers, rows

def useful(row):
    keys = ''.join(row.keys())
    vals = ''.join(str(v) for v in row.values())
    return '主营构成' in keys or '主营构成' in vals or '项目收入' in keys or '毛利率' in keys

batch = json.loads(BATCH.read_text(encoding='utf-8'))
for update in batch['updates']:
    company = update['company']
    raw_path = BASE / update['raw_source']
    raw = json.loads(raw_path.read_text(encoding='utf-8'))
    print('\n###', company)
    for result in raw.get('results', []):
        content = result.get('content', '')
        for table in tables(content):
            headers, rows = parse_table(table)
            if any('主营构成' in h or '毛利率' in h or '项目收入' in h for h in headers):
                print('HEADERS:', headers[:12])
                for row in rows[:2]:
                    print('ROW:', {k: row.get(k, '') for k in headers[:12]})
                break
