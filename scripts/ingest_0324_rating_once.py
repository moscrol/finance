# -*- coding: utf-8 -*-
import json, subprocess, sys
sys.path.insert(0,'/Users/lbq/Desktop/c c/金融/scripts')
import auto_pdf_ingest_worker as w
S='0324评级日报'; D='2026-03-25'; PDF='/Users/lbq/Desktop/研报/2026-03-25/0324评级日报.pdf'; LOG=327
payload={'source_name':S,'source_date':D,'source_file':PDF,'raw_sources':[f'raw/{S}.md'],'create_missing':False,'updates':[{'company':'炬光科技','date':D,'title':'微纳光学与光通信高密度互连线索','concepts':['微纳光学','微透镜','OCS','CPO','光模块'],'role':'微纳光学与高速光互连耦合元件供应商','chain_layer':'upstream_components','tier':'related','confidence':'medium','evidence_layer':'L1_L3_candidate','update_type':'curated_research','fact_hardness':'review_candidate','source_quality':'broker_research_high','review_required':True,'evidence':'0324评级日报：炬光科技依托微纳光学平台，提供微透镜、微透镜阵列、V型槽及高精度耦合元件；光通信领域已完成可插拔、OCS和CPO相关产品布局，受益400G/800G/1.6T光模块向更高通道数演进。','bullets':['微透镜主要应用于TOSA/ROSA光束准直、耦合与聚焦环节，需求与通道数提升相关。','公司在光通信领域已完成可插拔、OCS和CPO相关产品布局。','CPO与MicroLED等高密度互连方案仍处推进阶段，需客户/下游联合开发和后续验证。']}],'watchlist':[{'company':'四方股份','reason':'仅相关个股/研报来源列表出现，正文未展开'},{'company':'华特气体','reason':'仅相关个股/研报来源列表出现，正文未展开'}]}
proc=subprocess.run(['python3','/Users/lbq/Desktop/c c/金融/skills/entity-delta-ingest/scripts/entity_delta_writer.py'],input=json.dumps(payload,ensure_ascii=False),text=True,capture_output=True)
print(proc.stdout)
if proc.returncode:
    print(proc.stderr,file=sys.stderr); raise SystemExit(proc.returncode)
w.append_log(LOG,S,D,[f'[[{S}]] (source note)',f'raw/{S}.md'],['[[炬光科技]]','entity_exposures.json + evidence_index.json','[[index.md]]'],'manual rating curated_research for 炬光科技')
w.rewrite_source_log(S,LOG,'PDF ingest curated_research manual')
print(w.update_index())
