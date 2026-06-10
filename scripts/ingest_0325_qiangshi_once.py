# -*- coding: utf-8 -*-
import json, subprocess, sys
sys.path.insert(0,'/Users/lbq/Desktop/c c/金融/scripts')
import auto_pdf_ingest_worker as w
S='0325强势股脱水'; D='2026-03-26'; PDF='/Users/lbq/Desktop/研报/2026-03-26/0325强势股脱水.pdf'; LOG=329
rows=[
('长光华芯','光芯片EML与硅光项目线索',['光芯片','EML激光器','硅光'],'高功率半导体激光芯片与高速光通信芯片供应商','upstream_components','0325强势股脱水：长光华芯100G EML芯片已实现量产，200G EML完成送样，2026年2月通过子公司布局硅光技术，硅光集成项目预计2026年底完成通线。',['100G EML芯片已实现量产，200G EML完成送样。','通过子公司布局硅光技术，硅光集成项目预计2026年底完成通线。']),
('源杰科技','CW激光器与100G PAM4 EML客户验证线索',['光芯片','CW激光器','EML激光器','硅光'],'高速半导体光芯片供应商','upstream_components','0325强势股脱水：源杰科技聚焦高速半导体芯片全流程自主研发，CW100mW激光器及100G PAM4 EML均完成客户验证。',['CW100mW激光器完成客户验证。','100G PAM4 EML完成客户验证。']),
('立讯精密','CPC与硅光/NPO/CPO光铜并进线索',['CPC','铜连接','硅光模块','NPO','CPO'],'AI互连平台与光铜连接方案供应商','midstream_components','0325强势股脱水：立讯精密CPC 224G已进入产品化与公开验证阶段；800G硅光模块已量产，1.6T产品处于客户验证阶段，并展示3.2T NPO光引擎和自研CPO方案。',['CPC 224G强调高密度封装侧直连与单通道224Gbps能力，并规划向448G演进。','800G硅光模块已实现量产，1.6T产品处于客户验证阶段。','展示3.2T NPO光引擎、NPO插座、ELSFP模块及自研CPO方案。']),
('光环新网','火山引擎合作、AIDC与Agent工程化线索',['AIDC','云计算数据中心','火山引擎','AI Agent'],'云计算数据中心与AI算力服务运营商','downstream_operation','0325强势股脱水：光环新网为火山引擎区域核心授权合作伙伴，截至2025年9月已投产机柜超7.2万个，全国规划机柜超23万个；近期收购湃阳智能并发布Panacea智能体训推平台。',['为火山引擎区域核心授权合作伙伴，全国规划机柜规模超过23万个。','截至2025年9月已投产机柜总数超7.2万个，多地AIDC项目推进。','收购Agent工程化交付团队湃阳智能，发布Panacea智能体训推平台。'])]
updates=[]
for c,title,concepts,role,layer,evidence,bullets in rows:
    updates.append(dict(company=c,date=D,title=title,concepts=concepts,role=role,chain_layer=layer,tier='related',confidence='medium',evidence_layer='L1_L3_candidate',update_type='curated_research',fact_hardness='review_candidate',source_quality='broker_research_high',review_required=True,evidence=evidence,bullets=bullets))
payload={'source_name':S,'source_date':D,'source_file':PDF,'raw_sources':[f'raw/{S}.md'],'create_missing':True,'updates':updates,'watchlist':[]}
proc=subprocess.run(['python3','/Users/lbq/Desktop/c c/金融/skills/entity-delta-ingest/scripts/entity_delta_writer.py'],input=json.dumps(payload,ensure_ascii=False),text=True,capture_output=True)
print(proc.stdout)
if proc.returncode:
    print(proc.stderr,file=sys.stderr); raise SystemExit(proc.returncode)
w.append_log(LOG,S,D,[f'[[{S}]] (source note)',f'raw/{S}.md'],['[[长光华芯]]','[[源杰科技]]','[[立讯精密]]','[[光环新网]]','entity_exposures.json + evidence_index.json','[[index.md]]'],'manual strong-stock curated_research')
w.rewrite_source_log(S,LOG,'PDF ingest curated_research manual')
print(w.update_index())
