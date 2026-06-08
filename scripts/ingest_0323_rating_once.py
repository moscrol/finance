import json
import subprocess
import sys

sys.path.insert(0, '/Users/lbq/Desktop/c c/金融/scripts')
import auto_pdf_ingest_worker as w

SOURCE = '0323评级日报'
SOURCE_DATE = '2026-03-23'
PDF = '/Users/lbq/Desktop/研报/2026-03-23/0323评级日报.pdf'
LOG_ID = 319

payload = {
    'source_name': SOURCE,
    'source_date': SOURCE_DATE,
    'source_file': PDF,
    'raw_sources': [f'raw/{SOURCE}.md'],
    'create_missing': False,
    'updates': [
        {
            'company': '航天电器',
            'date': SOURCE_DATE,
            'title': '航天连接器与昇腾算力液冷连接器线索',
            'concepts': ['商业航天', '昇腾算力', '液冷服务器', '高速连接器'],
            'role': '航天高端连接器与AI算力高速/液冷互连产品供应商',
            'chain_layer': 'midstream_components',
            'tier': 'related',
            'confidence': 'medium',
            'evidence_layer': 'L1_L3_candidate',
            'update_type': 'curated_research',
            'fact_hardness': 'review_candidate',
            'source_quality': 'broker_research_high',
            'review_required': True,
            'evidence': '0323评级日报：航天电器主营高端连接器与互连一体化产品；子公司苏州华旃拟投资5725万元建设高速模组及液冷互连产品生产能力建设项目；受益商业航天星座组网、昇腾950系列放量及AI服务器液冷趋势。',
            'bullets': [
                '商业航天规模化发射带动航天连接器从定制化部件向规模化刚需耗材跃迁。',
                '苏州华旃拟投资5725万元建设高速模组及液冷互连产品生产能力。',
                '昇腾950系列及Atlas 950 SuperPoD放量预期提升高速连接器和液冷互连需求。',
            ],
        }
    ],
    'watchlist': [
        {'company': '中国巨石', 'reason': '仅在研报来源列表出现，正文未展开，不入relations'},
        {'company': '完美世界', 'reason': '仅在研报来源列表出现且缺实体，不create_missing'},
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
    ['[[航天电器]]', '[[index.md]]', 'entity_exposures.json + evidence_index.json'],
    'manual rating_digest curated_research for 航天电器',
)
w.rewrite_source_log(SOURCE, LOG_ID, 'PDF ingest curated_research manual')
print(w.update_index())
