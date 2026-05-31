#!/usr/bin/env python3
import json
import re
from pathlib import Path

VAULT = Path('/Users/lbq/Desktop/c c/知识库/wiki')
BASE = VAULT / 'raw/ifind-baseline'
ENTITIES = VAULT / 'entities'
REL = VAULT / 'relations'

PATCHES = {
    ('上峰水泥', '水泥'): {'strength': 'core', 'confidence': 'medium', 'evidence': 'iFinD基础资料显示公司所属建筑材料行业；公司名称和主营业务可支撑水泥主业 baseline，但具体收入占比仍需年报补充。'},
    ('中兵红箭', '人造钻石'): {'strength': 'related', 'confidence': 'medium', 'evidence': 'iFinD基础资料支持超硬材料及其制品主业；人造钻石/培育钻石暴露来自既有实体与产品映射，需年报或公告进一步确认业务占比。'},
    ('中国移动', '运营商'): {'strength': 'core', 'confidence': 'medium', 'evidence': 'iFinD stock_info显示公司所属申万和同花顺行业为通信；可支撑通信运营商基础画像，后续需年报补充分业务拆分。'},
    ('中国移动', '通信服务'): {'strength': 'core', 'confidence': 'medium', 'evidence': 'iFinD stock_info支持公司通信行业归属；stock_summary为空，通信服务细分收入结构需后续用年报补充。'},
    ('中国移动', '5G通信'): {'strength': 'related', 'confidence': 'medium', 'evidence': 'iFinD基础资料支持通信运营商属性；5G通信暴露来自主营行业与既有实体映射，具体5G资本开支和业务占比需年报/公告补充。'},
    ('中微公司', '国产替代'): {'strength': 'related', 'confidence': 'medium', 'evidence': 'iFinD基础资料支持国产半导体关键设备平台属性；国产替代为主题映射，不等同单一主营业务，需结合具体设备品类和客户导入验证。'},
    ('中恒电气', 'HVDC高压直流'): {'strength': 'related', 'confidence': 'medium', 'evidence': 'iFinD基础资料支持数据中心电源、电力操作电源系统等电源产品；HVDC高压直流为产品/应用映射，需官网、年报或项目资料继续验证。'},
    ('中船特气', '国产替代'): {'strength': 'related', 'confidence': 'medium', 'evidence': 'iFinD基础资料支持电子特种气体平台属性；国产替代为主题映射，需结合具体气体品类、客户导入和收入结构验证。'},
    ('中芯国际', '国产替代'): {'strength': 'related', 'confidence': 'medium', 'evidence': 'iFinD基础主营聚焦芯片制造，是国内领先晶圆代工平台；国产替代为产业主题映射，具体先进制程和客户结构需公开资料继续验证。'},
    ('中铁工业', '国产替代'): {'strength': 'related', 'confidence': 'medium', 'evidence': 'iFinD基础资料支持全断面隧道掘进机等高端装备制造业务；国产替代为主题映射，需结合具体装备品类与订单/项目验证。'},
}

def batch_num(path):
    m = re.search(r'batch(\d+)\.json$', path.name)
    return int(m.group(1)) if m else 0

def safe_filename(value):
    return re.sub(r'[/:*?"<>|\n\r\t]+', '_', str(value)).strip()

def backup(path, suffix):
    b = path.with_suffix(path.suffix + suffix)
    if not b.exists():
        b.write_text(path.read_text(encoding='utf-8'), encoding='utf-8')

def patch_batch_json():
    changed=[]
    for path in sorted(BASE.glob('baseline-updates-*-batch*.json'), key=batch_num):
        if not (1 <= batch_num(path) <= 70):
            continue
        data=json.loads(path.read_text(encoding='utf-8'))
        touched=False
        for u in data.get('updates',[]) or []:
            company=u.get('company','')
            for exp in u.get('exposures',[]) or []:
                key=(company, exp.get('concept',''))
                if key in PATCHES:
                    exp.update(PATCHES[key])
                    exp.setdefault('evidence_layer','L2')
                    exp.setdefault('update_type','baseline')
                    touched=True
                    changed.append({'file':path.name,'company':company,'concept':key[1]})
        if touched:
            backup(path,'.bak-high-qc')
            path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return changed

def patch_entity_page(company, concept, patch):
    path=ENTITIES/f'{safe_filename(company)}.md'
    if not path.exists():
        return False
    text=path.read_text(encoding='utf-8')
    pattern=re.compile(rf'^(\| \[\[{re.escape(concept)}\]\] \| .*? \| ).*?( \| ).*?( \| L2 \| baseline \| ).*?( \|)$',re.M)
    def repl(m):
        line=m.group(0)
        parts=[p.strip() for p in line.strip('|').split('|')]
        if len(parts) < 8:
            return line
        parts[3]=patch['strength']
        parts[4]=patch['confidence']
        parts[7]=patch['evidence']
        return '| ' + ' | '.join(parts) + ' |'
    new_text,count=pattern.subn(repl,text,1)
    if count:
        backup(path,'.bak-high-qc')
        path.write_text(new_text,encoding='utf-8')
        return True
    return False

def patch_relations():
    results={}
    for name in ['entity_exposures.json','evidence_index.json']:
        path=REL/name
        data=json.loads(path.read_text(encoding='utf-8'))
        count=0
        def walk(obj):
            nonlocal count
            if isinstance(obj,dict):
                target=obj.get('target') or obj.get('name')
                concept=obj.get('concept')
                key=(target,concept)
                if key in PATCHES:
                    obj.update(PATCHES[key])
                    count+=1
                for v in obj.values():
                    walk(v)
            elif isinstance(obj,list):
                for x in obj:
                    walk(x)
        walk(data)
        if count:
            backup(path,'.bak-high-qc')
            path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        results[name]=count
    return results

def main():
    batch_changes=patch_batch_json()
    entity_changes=[]
    for (company,concept),patch in PATCHES.items():
        entity_changes.append({'company':company,'concept':concept,'updated':patch_entity_page(company,concept,patch)})
    relation_changes=patch_relations()
    print(json.dumps({'batch_json_changes':batch_changes,'entity_changes':entity_changes,'relation_changes':relation_changes},ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
