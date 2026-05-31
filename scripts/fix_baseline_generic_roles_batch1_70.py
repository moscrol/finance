#!/usr/bin/env python3
import json
import re
from pathlib import Path

VAULT = Path('/Users/lbq/Desktop/c c/知识库/wiki')
BASE = VAULT / 'raw/ifind-baseline'
ENTITIES = VAULT / 'entities'
REL = VAULT / 'relations'

PATCHES = {
    ('东方国信','商业智能'): '企业级BI与数据分析平台厂商',
    ('东软集团','IT服务'): '医疗医保与政企行业软件系统集成商',
    ('中兴通讯','ICT设备'): '通信主设备与算力网络设备厂商',
    ('中兵红箭','人造钻石'): '超硬材料及人造金刚石业务平台',
    ('中兵红箭','培育钻石'): '培育钻石上游超硬材料平台',
    ('中国电信','通信服务'): '全国性固移融合通信运营商',
    ('中国电信','产业数字化'): '运营商云网融合与政企数字化平台',
    ('中国软件','IT服务'): '党政信创基础软件与行业信息化平台',
    ('中国长城','军工电子'): '国产计算整机与军工电子装备平台',
    ('中国长城','海洋信息安全'): '海洋信息化与安全计算设备平台',
    ('中孚信息','信息安全'): '保密安全与数据安全软件厂商',
    ('中孚信息','计算机设备'): '安全计算终端与保密硬件厂商',
    ('中来股份','光伏'): 'N型电池与光伏背板一体化厂商',
    ('中来股份','太阳能电池'): 'TOPCon/N型高效电池制造商',
    ('中来股份','组件'): '光伏组件与背板协同制造商',
    ('中来股份','光伏应用系统'): '分布式光伏系统集成与应用运营商',
    ('中电鑫龙','智慧城市'): '自主可控智慧城市系统集成商',
    ('中直股份','军工装备'): '直升机整机与航空装备主机厂',
    ('中科曙光','液冷服务器'): '液冷高端服务器与超算系统厂商',
    ('中科曙光','智算中心'): '智算中心服务器与算力基础设施厂商',
    ('中科曙光','算力租赁'): '云计算与算力服务基础设施运营商',
    ('中科飞测','良率管理'): '半导体量检测与良率管理设备厂商',
    ('中芯国际','设计服务'): '晶圆代工配套设计服务与IP支持平台',
    ('中际旭创','硅光'): '高速硅光/光收发模块龙头厂商',
    ('中际旭创','光通信'): '800G/1.6T高端光模块龙头厂商',
    ('乐普医疗','心脏支架'): '心血管介入器械与支架系统厂商',
    ('亚光股份','半导体材料'): '半导体石英耗材上游石英砂供应商',
    ('亚康股份','华为昇腾'): '昇腾算力机房运维与技术服务商',
    ('万兴科技','创作工具'): '视频与图形创意软件工具厂商',
    ('亨通光电','光通信'): '光棒光纤光缆与光通信器件平台',
    ('今飞凯达','轻量化'): '新能源汽车铝合金轮毂与轻量化结构件厂商',
    ('优刻得','信创'): '中立云计算与国产化适配云平台',
    ('伟思医疗','脑机接口'): '脑电采集与神经调控设备材料平台',
    ('佛塑科技','绝缘材料'): '高压高频绝缘功能薄膜厂商',
    ('佰维存储','信创'): '国产整机和服务器存储模块厂商',
    ('兴发集团','磷源'): '半导体级磷源与湿电子化学品供应商',
    ('冠昊生物','人脑工程'): '脑膜修复与脑皮层保护生物材料厂商',
}

def batch_num(path):
    m=re.search(r'batch(\d+)\.json$',path.name)
    return int(m.group(1)) if m else 0

def safe_filename(value):
    return re.sub(r'[/:*?"<>|\n\r\t]+','_',str(value)).strip()

def backup(path,suffix):
    b=path.with_suffix(path.suffix+suffix)
    if not b.exists():
        b.write_text(path.read_text(encoding='utf-8'),encoding='utf-8')

def patch_batch_json():
    changes=[]
    for path in sorted(BASE.glob('baseline-updates-*-batch*.json'),key=batch_num):
        if not (1<=batch_num(path)<=70):
            continue
        data=json.loads(path.read_text(encoding='utf-8'))
        touched=False
        for u in data.get('updates',[]) or []:
            company=u.get('company')
            for exp in u.get('exposures',[]) or []:
                key=(company,exp.get('concept'))
                if key in PATCHES and exp.get('role')!=PATCHES[key]:
                    exp['role']=PATCHES[key]
                    changes.append({'file':path.name,'company':company,'concept':key[1],'role':PATCHES[key]})
                    touched=True
        if touched:
            backup(path,'.bak-generic-role')
            path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return changes

def patch_entity(company,concept,role):
    path=ENTITIES/f'{safe_filename(company)}.md'
    if not path.exists():
        return False
    lines=path.read_text(encoding='utf-8').splitlines()
    changed=False
    in_baseline=False
    for i,line in enumerate(lines):
        if line.startswith('## 产业链暴露'):
            in_baseline=True
            continue
        if in_baseline and line.startswith('## '):
            in_baseline=False
        if not in_baseline or f'[[{concept}]]' not in line or not line.strip().startswith('|'):
            continue
        parts=[p.strip() for p in line.strip().strip('|').split('|')]
        if len(parts) >= 5:
            parts[1]=role
            lines[i]='| '+' | '.join(parts)+' |'
            changed=True
    if changed:
        backup(path,'.bak-generic-role')
        path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return changed

def patch_relation_file(name):
    path=REL/name
    data=json.loads(path.read_text(encoding='utf-8'))
    count=0
    if name=='entity_exposures.json':
        entities=data.get('entities',data)
        for (company,concept),role in PATCHES.items():
            node=entities.get(company) if isinstance(entities,dict) else None
            exp=(node or {}).get('concepts',{}).get(concept) if isinstance(node,dict) else None
            if isinstance(exp,dict) and exp.get('role')!=role:
                exp['role']=role; count+=1
    else:
        def walk(obj):
            nonlocal count
            if isinstance(obj,dict):
                company=obj.get('company') or obj.get('target') or obj.get('name')
                concept=obj.get('concept')
                key=(company,concept)
                if key in PATCHES and obj.get('role')!=PATCHES[key]:
                    obj['role']=PATCHES[key]; count+=1
                for v in obj.values(): walk(v)
            elif isinstance(obj,list):
                for x in obj: walk(x)
        walk(data)
    if count:
        backup(path,'.bak-generic-role')
        path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return count

def main():
    changes=patch_batch_json()
    entity_changes=[]
    for ch in changes:
        entity_changes.append({'company':ch['company'],'concept':ch['concept'],'updated':patch_entity(ch['company'],ch['concept'],ch['role'])})
    rel={'entity_exposures.json':patch_relation_file('entity_exposures.json'),'evidence_index.json':patch_relation_file('evidence_index.json')}
    print(json.dumps({'batch_json_changes':len(changes),'entity_changes':entity_changes,'relation_changes':rel},ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
