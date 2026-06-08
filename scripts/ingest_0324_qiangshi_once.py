# -*- coding: utf-8 -*-
import json, subprocess, sys
sys.path.insert(0, '/Users/lbq/Desktop/c c/金融/scripts')
import auto_pdf_ingest_worker as w
S='0324强势股脱水'; D='2026-03-25'; PDF='/Users/lbq/Desktop/研报/2026-03-25/0324强势股脱水.pdf'; LOG=325
updates=[]
cur=[
('中矿资源','津巴布韦硫酸锂项目与锂矿供给扰动线索',['锂矿','硫酸锂','锂电池'],'锂矿资源与海外锂盐项目企业','upstream_materials','0324强势股脱水：津巴布韦暂停锂精矿出口，中矿资源3万吨硫酸锂项目计划2027年投产，随着中资锂盐产能落地，出口规模中长期有望修复。',['津巴布韦是中国第二大锂精矿进口来源，供给扰动推升锂价上行预期。','中矿资源3万吨硫酸锂项目计划2027年投产，需原始研报/公告验证。']),
('长飞光纤','空芯光纤与AI数据中心光纤需求线索',['光纤','空芯光纤','AI数据中心'],'光纤光缆及新型光纤产品供应商','upstream_components','0324强势股脱水：长飞在OFC展示单盘91.2km、衰减0.04dB/km的空芯光纤，并与诺基亚、EXFO、VIAVI联合展示测试传输；AI数据中心和军用无人机推动光纤需求。',['AI数据中心单机柜光纤连接数为传统机柜5-10倍以上。','长飞展示空芯光纤与联合测试传输，需原始展会/研报验证。']),
('亨通光电','光纤光缆供给约束与CSP商用采购线索',['光纤','光纤光缆','DCI'],'光纤光缆及数据中心互联光纤供应商','upstream_components','0324强势股脱水：光棒扩产周期18-24个月形成供给约束；亨通光电已于2025年11月完成全球首次CSP商用采购，将应用于DCI场景。',['光棒扩产周期18-24个月，2026/2027年供需缺口或扩大。','亨通光电CSP商用采购和DCI应用线索需公告/原始研报验证。'])]
for company,title,concepts,role,layer,evidence,bullets in cur:
    updates.append(dict(company=company,date=D,title=title,concepts=concepts,role=role,chain_layer=layer,tier='related',confidence='medium',evidence_layer='L1_L3_candidate',update_type='curated_research',fact_hardness='review_candidate',source_quality='broker_research_high',review_required=True,evidence=evidence,bullets=bullets))
graph=[
('涪陵电力','算电协同','算力配套供电受益名单企业','downstream_operation'),('科华数据','算电协同','算力建设与服务受益名单企业','midstream_service'),('四方股份','数据中心电力设备','数据中心电力设备受益名单企业','midstream_equipment'),('金盘科技','数据中心电力设备','数据中心电力设备受益名单企业','midstream_equipment'),('中恒电气','数据中心电力设备','数据中心电力设备受益名单企业','midstream_equipment'),('科士达','数据中心电力设备','数据中心电力设备受益名单企业','midstream_equipment'),('国电南瑞','电力信息化','电力信息化/智慧调度受益名单企业','midstream_service'),('泽宇智能','电力信息化','电力信息化/智慧调度受益名单企业','midstream_service'),('润泽科技','智算中心','智算中心受益名单企业','downstream_operation'),('数据港','智算中心','智算中心受益名单企业','downstream_operation'),('奥飞数据','智算中心','智算中心受益名单企业','downstream_operation'),('韶能股份','储能与绿电','储能与绿电受益名单企业','downstream_operation')]
for company,concept,role,layer in graph:
    updates.append(dict(company=company,date=D,title='算电协同受益名单',concepts=[concept],role=role,chain_layer=layer,tier='peripheral',confidence='low',evidence_layer='graph_only',update_type='graph_only',fact_hardness='market_narrative',source_quality='broker_research_high',review_required=False,graph_only=True,evidence=f'0324强势股脱水：算电协同受益产业链及公司名单提及{company}，仅作为图谱暴露，不写实体正文。',bullets=[]))
payload={'source_name':S,'source_date':D,'source_file':PDF,'raw_sources':[f'raw/{S}.md'],'create_missing':False,'updates':updates,'watchlist':[{'company':c,'reason':'缺实体或仅行情/受益名单提及，不create_missing'} for c in ['富祥药业','融捷股份','西藏城投','华友钴业','南网科技','国网信通','南网数字','威胜信息','光环新网','南网储能','协鑫能科']]}
proc=subprocess.run(['python3','/Users/lbq/Desktop/c c/金融/skills/entity-delta-ingest/scripts/entity_delta_writer.py'],input=json.dumps(payload,ensure_ascii=False),text=True,capture_output=True)
print(proc.stdout)
if proc.returncode:
    print(proc.stderr,file=sys.stderr); raise SystemExit(proc.returncode)
w.append_log(LOG,S,D,[f'[[{S}]] (source note)',f'raw/{S}.md'],['[[中矿资源]]','[[长飞光纤]]','[[亨通光电]]','entity_exposures.json + evidence_index.json','[[index.md]]'],'manual strong-stock curated_research + graph_only')
w.rewrite_source_log(S,LOG,'PDF ingest curated_research/graph_only manual')
print(w.update_index())
