#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path

VAULT = Path('/Users/lbq/Desktop/c c/知识库/wiki')
BASE = VAULT / 'raw/ifind-baseline'
ENTITIES = VAULT / 'entities'
REL = VAULT / 'relations'

RULES = [
    ('upstream_equipment', ['水电镀设备', '设备', '装备', '机床', '仪器', '检测', '量测', '刻蚀', '沉积', '光刻', '封装设备', '电镀', '机器人', '减速器', '传感器', '电机', '控制器', 'PLC', '伺服', '泵', '阀', '压缩机', '电源', '变压器', '磁性元器件', '连接器', '线缆', '电缆', '液压件', '散热器', '运动器材', '医疗器械', '厨房小家电']),
    ('downstream_application', ['零售', '连锁', '药房', 'DTP', '运营', '整车', '汽车', 'eVTOL', '飞行汽车', '低空经济', '通用航空', '终端', '消费电子', '手机', '医疗服务', '医院', '药品', '疫苗', '食品', '饮料', '水泥', '建筑', '地产', '机场', '航空公司', '运营服务', '应用', '游戏', '教育', '旅游', '滑雪', '体育产业', '互联网医疗', '消费升级', '谷子经济', '预制菜', '动物保健']),
    ('downstream_infrastructure', ['IDC', '数据中心', '智算中心', '算力', '云计算', '运营商', '通信服务', '宽带', '基站', '充电桩', '电网', '电力', '储能电站', '油气服务', '航运', '物流', '核电', '可控核聚变', '工程总包']),
    ('upstream_materials', ['半导体材料', '光刻胶', '光刻胶树脂', '光致产酸剂', '材料', '原料', '化学', '化工', '气体', '特气', '靶材', '硅片', '晶圆材料', '抛光液', 'CMP', '隔膜', '电解液', '正极', '负极', '铜箔', '铝箔', '磁材', '稀土', '碳纤维', '玻纤', '树脂', '薄膜', '陶瓷', '石英', '金属', '有机硅', '氟', '磷', '锂矿', '钠', '镁', '钛材', '合金']),
    ('midstream_components', ['芯片', '半导体', 'IC', 'SoC', 'MCU', '存储', '光模块', 'CPO', 'PCB', '服务器', '整机', '模组', '组件', '电池', '电芯', '电池包', '结构件', '零部件', '部件', '器件', '元器件', '封测', '封装', '代工', '制造商', '供应商', '偏光片', 'PTA', 'PX', 'PET瓶片', '粘胶短纤', '涤纶长丝', '革基布', '航空锻造', '民用航空发动机']),
    ('midstream_solution', ['系统', '解决方案', '集成', '软件', '平台', '数据库', '操作系统', '云平台', '信息化', '自动化', 'DCS', 'MES', 'ERP', '网络安全', '信息安全', '工业互联网', '数据安全', '政企安全', '细胞基因CDMO']),
    ('upstream_resource', ['资源', '矿', '煤', '油', '天然气', '盐湖', '开采', '种植', '养殖', '农牧', '林业', '造纸', '白羽鸡育种', '生物医药', '创新药']),
]

def batch_num(path):
    m = re.search(r'batch(\d+)\.json$', path.name)
    return int(m.group(1)) if m else 0

def safe_filename(value):
    return re.sub(r'[/:*?"<>|\n\r\t]+', '_', str(value)).strip()

def infer_layer(concept, role, evidence, main_business=''):
    text = ' '.join(str(x or '') for x in [concept, role, evidence, main_business])
    for layer, kws in RULES:
        if any(kw in text for kw in kws):
            return layer
    return ''

def backup(path, suffix):
    b = path.with_suffix(path.suffix + suffix)
    if not b.exists():
        b.write_text(path.read_text(encoding='utf-8'), encoding='utf-8')

def patch_batch_json(apply=False):
    changes=[]
    for path in sorted(BASE.glob('baseline-updates-*-batch*.json'), key=batch_num):
        if not (1 <= batch_num(path) <= 70):
            continue
        data=json.loads(path.read_text(encoding='utf-8'))
        touched=False
        for u in data.get('updates',[]) or []:
            mb=u.get('main_business','')
            for exp in u.get('exposures',[]) or []:
                layer=infer_layer(exp.get('concept'), exp.get('role'), exp.get('evidence'), mb)
                if layer and exp.get('chain_layer') != layer:
                    changes.append({'batch':batch_num(path),'company':u.get('company'),'concept':exp.get('concept'),'layer':layer})
                    if apply:
                        exp['chain_layer']=layer
                        touched=True
        if apply and touched:
            backup(path,'.bak-chain-layer')
            path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return changes

def patch_entity_page(company, concept, layer):
    path=ENTITIES/f'{safe_filename(company)}.md'
    if not path.exists():
        return False
    text=path.read_text(encoding='utf-8')
    lines=text.splitlines()
    changed=False
    for i,line in enumerate(lines):
        if f'[[{concept}]]' not in line or not line.strip().startswith('|'):
            continue
        parts=[p.strip() for p in line.strip().strip('|').split('|')]
        # old 5-col: concept role strength confidence evidence -> upgrade to 8-col table not safe without header
        # Keep entity markdown stable; relations/batch JSON carry chain_layer for theme-radar.
    return changed

def patch_entity_exposures(changes, apply=False):
    path=REL/'entity_exposures.json'
    data=json.loads(path.read_text(encoding='utf-8'))
    entities=data.get('entities',data)
    count=0
    for ch in changes:
        node=entities.get(ch['company']) if isinstance(entities,dict) else None
        if not isinstance(node,dict):
            continue
        exp=(node.get('concepts') or {}).get(ch['concept'])
        if isinstance(exp,dict) and exp.get('chain_layer') != ch['layer']:
            count+=1
            if apply:
                exp['chain_layer']=ch['layer']
    if apply and count:
        backup(path,'.bak-chain-layer')
        path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return count

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    changes=patch_batch_json(apply=args.apply)
    rel_count=patch_entity_exposures(changes,apply=args.apply)
    by_layer={}
    for ch in changes:
        by_layer[ch['layer']]=by_layer.get(ch['layer'],0)+1
    print(json.dumps({'apply':args.apply,'batch_json_chain_layer_fills':len(changes),'entity_exposures_fills':rel_count,'by_layer':by_layer,'samples':changes[:40]},ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
