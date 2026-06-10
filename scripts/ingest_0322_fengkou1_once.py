import json
import subprocess
import sys

sys.path.insert(0, '/Users/lbq/Desktop/c c/金融/scripts')
import auto_pdf_ingest_worker as w

SOURCE = '0322风口研报1'
SOURCE_DATE = '2026-03-23'
PDF = '/Users/lbq/Desktop/研报/2026-03-23/风口研报1 260322.pdf'
LOG_ID = 321

payload = {
    'source_name': SOURCE,
    'source_date': SOURCE_DATE,
    'source_file': PDF,
    'raw_sources': [f'raw/{SOURCE}.md'],
    'create_missing': False,
    'updates': [
        {
            'company': '大秦铁路',
            'date': SOURCE_DATE,
            'title': '西煤东运资产重估与隐性提价线索',
            'concepts': ['煤炭运输', '西煤东运', '公转铁', '铁路货运'],
            'role': '西煤东运核心铁路干线运营商',
            'chain_layer': 'downstream_operation',
            'tier': 'related',
            'confidence': 'medium',
            'evidence_layer': 'L1_L3_candidate',
            'update_type': 'curated_research',
            'fact_hardness': 'review_candidate',
            'source_quality': 'broker_research_high',
            'review_required': True,
            'evidence': '0322风口研报1：地缘冲突推升海外煤价与油价，进口替代和公转铁逻辑带动西煤东运铁路需求；大秦线约占北方港口煤炭下水量43%，3月日均运量接近满载，运费优惠收窄可能形成隐性提价。',
            'bullets': [
                '海外煤价上涨和进口煤高于内贸长协价可能抑制进口量，供需缺口转由国内铁路调运填补。',
                '大秦线运量约占北方港口煤炭下水量43%，3月日均运量已接近满载。',
                '油价上涨放大电气化重载铁路成本优势，运费优惠收窄可能形成隐性提价。',
            ],
        },
        {
            'company': '源杰科技',
            'date': SOURCE_DATE,
            'title': '硅光+CPO与CW激光器芯片线索',
            'concepts': ['硅光', 'CPO', 'CW激光器', '光芯片'],
            'role': '硅光/CPO用CW激光器芯片与光芯片供应商',
            'chain_layer': 'upstream_components',
            'tier': 'related',
            'confidence': 'medium',
            'evidence_layer': 'L1_L3_candidate',
            'update_type': 'curated_research',
            'fact_hardness': 'review_candidate',
            'source_quality': 'broker_research_high',
            'review_required': True,
            'evidence': '0322风口研报1：源杰科技专注光芯片研发，硅光大功率CW产品用于数据中心与云计算；针对400G/800G光模块需求量产CW 70mW激光器芯片，CPO交换机中CW光源单颗价值量及功率需求提升。',
            'bullets': [
                '公司硅光大功率CW产品已推出，应用于数据中心与云计算场景。',
                '依托IDM模式和DFB激光器设计/工艺/测试积累，量产CW 70mW激光器芯片。',
                'CPO交换机中CW光源单颗价值量和功率需求有望提升。',
            ],
        },
    ],
    'watchlist': [],
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
    ['[[大秦铁路]]', '[[源杰科技]]', '[[index.md]]', 'entity_exposures.json + evidence_index.json'],
    'manual fengkou curated_research for 大秦铁路 and 源杰科技',
)
w.rewrite_source_log(SOURCE, LOG_ID, 'PDF ingest curated_research manual')
print(w.update_index())
