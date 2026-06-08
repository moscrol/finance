import json, subprocess, sys
sys.path.insert(0, '/Users/lbq/Desktop/c c/金融/scripts')
import auto_pdf_ingest_worker as w
SOURCE='0322风口研报3'; SOURCE_DATE='2026-03-23'; PDF='/Users/lbq/Desktop/研报/2026-03-23/风口研报3 260322.pdf'; LOG_ID=323
payload={'source_name':SOURCE,'source_date':SOURCE_DATE,'source_file':PDF,'raw_sources':[f'raw/{SOURCE}.md'],'create_missing':False,'updates':[{'company':'协创数据','date':SOURCE_DATE,'title':'算力租赁涨价周期与高强度算力布局线索','concepts':['算力租赁','智算中心','GPU服务器','云算力服务'],'role':'算力中心运营与智能算力服务商','chain_layer':'midstream_service','tier':'related','confidence':'medium','evidence_layer':'L1_L3_candidate','update_type':'curated_research','fact_hardness':'review_candidate','source_quality':'broker_research_high','review_required':True,'evidence':'0322风口研报3：协创数据高端GPU服务器在手订单充足，2025年5次算力服务器采购公告合计不超过212亿元，2026年2月新增不超过110亿元采购合同；多地部署算力中心，授信及H股上市推进支撑高强度算力布局。','bullets':['算力租赁市场进入新一轮涨价周期，公司高端GPU服务器在手订单充足。','2025年算力服务器采购公告合计不超过212亿元，2026年2月新增不超过110亿元采购合同。','多地部署并运营算力中心，服务头部互联网、自动驾驶、生物医药等客户。','2026年3月申请新增授信额度200亿元，H股上市备案材料已获证监会接收。']}],'watchlist':[]}
proc=subprocess.run(['python3','/Users/lbq/Desktop/c c/金融/skills/entity-delta-ingest/scripts/entity_delta_writer.py'],input=json.dumps(payload,ensure_ascii=False),text=True,capture_output=True)
print(proc.stdout)
if proc.returncode:
    print(proc.stderr,file=sys.stderr); raise SystemExit(proc.returncode)
w.append_log(LOG_ID,SOURCE,SOURCE_DATE,[f'[[{SOURCE}]] (source note)',f'raw/{SOURCE}.md'],['[[协创数据]]','[[index.md]]','entity_exposures.json + evidence_index.json'],'manual fengkou curated_research for 协创数据')
w.rewrite_source_log(SOURCE,LOG_ID,'PDF ingest curated_research manual')
print(w.update_index())
