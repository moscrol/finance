import json
import subprocess
import sys

sys.path.insert(0, '/Users/lbq/Desktop/c c/金融/scripts')
import auto_pdf_ingest_worker as w

SOURCE = '0322评级日报'
SOURCE_DATE = '2026-03-23'
PDF = '/Users/lbq/Desktop/研报/2026-03-23/评级日报 260322.pdf'
LOG_ID = 320

payload = {
    'source_name': SOURCE,
    'source_date': SOURCE_DATE,
    'source_file': PDF,
    'raw_sources': [f'raw/{SOURCE}.md'],
    'create_missing': True,
    'updates': [
        {
            'company': '大秦铁路',
            'date': SOURCE_DATE,
            'title': '西煤东运铁路量价修复线索',
            'concepts': ['煤炭运输', '西煤东运', '公转铁', '铁路货运'],
            'role': '西煤东运核心铁路干线运营商',
            'chain_layer': 'transport_logistics',
            'tier': 'related',
            'confidence': 'medium',
            'evidence_layer': 'L1_L3_candidate',
            'update_type': 'curated_research',
            'fact_hardness': 'review_candidate',
            'source_quality': 'broker_research_high',
            'review_required': True,
            'evidence': '0322评级日报：地缘冲突推升海外煤价与燃油成本，进口替代和公转铁共同驱动西煤东运铁路量价改善；大秦线运量约占北方港口煤炭下水量43%，3月1-18日日均运量约121万吨，同比+8%，3月中旬接近125万吨满载水平。',
            'bullets': [
                '进口煤价格高于内贸煤可能压缩进口量，供需缺口由国内产能填补，利好西煤东运铁路干线。',
                '3月1-18日大秦线日均运量约121万吨、同比增长8%，3月中旬接近125万吨满载水平。',
                '油价抬升推动公路运输成本上行，重载电气化铁路成本受油价影响较小，公转铁竞争力提升。',
                '研报称当前PB约0.64倍，并上调2026年归母净利润8.6%至80亿元；该预测需原始研报核验。',
            ],
        }
    ],
    'watchlist': [
        {'company': '龙净环保', 'reason': '仅在研报来源列表出现，正文未展开，不入relations'},
        {'company': '同力天启', 'reason': '仅在研报来源列表出现且缺实体，不create_missing'},
    ],
}

proc = subprocess.run(
    ['python3', '/Users/lbq/Desktop/c c/金融/skills/entity-delta-ingest/scripts/entity_delta_writer.py'],
    input=json.dumps(payload, ensure_ascii=False),
    text=True,
    capture_output=True,
)
print(proc.stdout)
if proc.returncode:
    print(proc.stderr, file=sys.stderr)
    raise SystemExit(proc.returncode)

w.append_log(
    LOG_ID,
    SOURCE,
    SOURCE_DATE,
    [f'[[{SOURCE}]] (source note)', f'raw/{SOURCE}.md'],
    ['[[大秦铁路]]', '[[index.md]]', 'entity_exposures.json + evidence_index.json'],
    'manual rating_digest curated_research create_missing for 大秦铁路',
)
w.rewrite_source_log(SOURCE, LOG_ID, 'PDF ingest curated_research manual')
print(w.update_index())
