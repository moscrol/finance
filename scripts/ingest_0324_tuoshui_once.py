# -*- coding: utf-8 -*-
import json, subprocess, sys
sys.path.insert(0,'/Users/lbq/Desktop/c c/金融/scripts')
import auto_pdf_ingest_worker as w
S='0324脱水研报'; D='2026-03-25'; PDF='/Users/lbq/Desktop/研报/2026-03-25/0324脱水研报.pdf'; LOG=326
items=[('比亚迪','新能源车出海','新能源车出海受益名单企业','downstream_operation'),('徐工机械','矿山机械','矿山机械出海/后市场/无人化受益名单企业','midstream_equipment'),('中科三环','稀土磁材','稀土磁材与稀土价格中枢上移受益名单企业','midstream_components'),('宁波韵升','稀土磁材','稀土磁材与稀土价格中枢上移受益名单企业','midstream_components'),('普洛药业','原料药','原料药提价与利润弹性受益名单企业','midstream_manufacturing'),('天宇股份','原料药','原料药提价与利润弹性受益名单企业','midstream_manufacturing'),('九洲药业','原料药','原料药提价与利润弹性受益名单企业','midstream_manufacturing')]
updates=[]
for c,concept,role,layer in items:
    updates.append(dict(company=c,date=D,title='脱水研报受益名单',concepts=[concept],role=role,chain_layer=layer,tier='peripheral',confidence='low',evidence_layer='graph_only',update_type='graph_only',fact_hardness='market_narrative',source_quality='broker_research_high',review_required=False,graph_only=True,evidence=f'0324脱水研报：{concept}主题受益名单提及{c}，仅作为图谱暴露，不写实体正文。',bullets=[]))
miss='上汽集团 吉利汽车 奇瑞汽车 耐普矿机 北矿科技 海安集团 中信重工 中国稀土 北方稀土 中稀有色 盛和资源 包钢股份 金力永磁 正海磁材 奥锐特 华海药业'.split()
payload={'source_name':S,'source_date':D,'source_file':PDF,'raw_sources':[f'raw/{S}.md'],'create_missing':False,'updates':updates,'watchlist':[{'company':x,'reason':'受益名单缺实体，不create_missing'} for x in miss]}
proc=subprocess.run(['python3','/Users/lbq/Desktop/c c/金融/skills/entity-delta-ingest/scripts/entity_delta_writer.py'],input=json.dumps(payload,ensure_ascii=False),text=True,capture_output=True)
print(proc.stdout)
if proc.returncode:
    print(proc.stderr,file=sys.stderr); raise SystemExit(proc.returncode)
w.cleanup_after_writer(S,D,[x[0] for x in items],remove_updated_section=True)
w.append_log(LOG,S,D,[f'[[{S}]] (source note)',f'raw/{S}.md'],['entity_exposures.json + evidence_index.json','[[index.md]]'],'manual beneficiary_list graph_only for 7 entities')
w.rewrite_source_log(S,LOG,'PDF ingest graph_only manual')
print(w.update_index())
