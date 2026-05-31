#!/usr/bin/env python3
import json
import re
from pathlib import Path

BASE = Path('/Users/lbq/Desktop/c c/知识库/wiki')
BATCH = BASE / 'raw/ifind-baseline/baseline-updates-2026-05-26-batch88.json'
SKIP_NAMES = {'其他', '其他业务', '其他收入'}

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

def pick_header(headers, kind, rank):
    for header in headers:
        if kind in header and f'第{rank}名' in header:
            return header
    return ''

def yuan_to_yi(value):
    text = str(value or '').replace(',', '').strip()
    if not text:
        return ''
    try:
        return f'{float(text) / 100000000:.2f}亿元'
    except ValueError:
        return ''

def margin_value(value):
    text = str(value or '').replace('%', '').strip()
    if not text:
        return ''
    try:
        return f'{float(text):.2f}%'
    except ValueError:
        return ''

def period_value(raw_date):
    text = str(raw_date or '').strip()
    if re.fullmatch(r'\d{8}', text):
        return f'{text[:4]}-{text[4:6]}-{text[6:]}'
    return text or 'iFinD最新主营构成'

def income_indicator(name):
    return name if name.endswith('收入') else f'{name}收入'

def margin_indicator(name):
    base = name[:-2] if name.endswith('收入') else name
    return f'{base}毛利率'

def extract_key_data(raw_path):
    raw = json.loads(raw_path.read_text(encoding='utf-8'))
    for result in raw.get('results', []):
        content = result.get('content', '')
        for table in tables(content):
            headers, rows = parse_table(table)
            if not any('主营构成' in h and '项目收入' in h for h in headers):
                continue
            if not rows:
                continue
            row = rows[0]
            period = period_value(row.get('日期', ''))
            key_data = []
            for rank in range(1, 4):
                name_h = pick_header(headers, '项目名称', rank)
                income_h = pick_header(headers, '项目收入', rank)
                margin_h = pick_header(headers, '项目毛利率', rank)
                name = str(row.get(name_h, '')).strip()
                if not name or name in SKIP_NAMES:
                    continue
                income = yuan_to_yi(row.get(income_h, ''))
                margin = margin_value(row.get(margin_h, ''))
                if income:
                    key_data.append({
                        'indicator': income_indicator(name),
                        'value': income,
                        'period': period,
                        'source': 'iFinD 主营构成'
                    })
                if margin:
                    key_data.append({
                        'indicator': margin_indicator(name),
                        'value': margin,
                        'period': period,
                        'source': 'iFinD 主营构成'
                    })
                if len(key_data) >= 4:
                    break
            return key_data
    return []

data = json.loads(BATCH.read_text(encoding='utf-8'))
summary = {}
for update in data.get('updates', []):
    raw_path = BASE / update['raw_source']
    key_data = extract_key_data(raw_path)
    update['key_data'] = key_data
    summary[update['company']] = len(key_data)
BATCH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'status': 'ok', 'summary': summary}, ensure_ascii=False, indent=2))
