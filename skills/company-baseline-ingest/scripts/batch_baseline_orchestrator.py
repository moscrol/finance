#!/usr/bin/env python3
"""Orchestrator to automatically find next missing companies, fetch, assemble and write baselines."""

import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

# Path Config
WIKI_DIR = Path('/Users/lbq/Desktop/c c/知识库/wiki')
ENTITIES_DIR = WIKI_DIR / 'entities'
RAW_DIR = WIKI_DIR / 'raw/ifind-baseline'
SCRIPTS_DIR = Path('/Users/lbq/Desktop/c c/金融/skills/company-baseline-ingest/scripts')

FETCH_SCRIPT = SCRIPTS_DIR / 'fetch_ifind_baseline.py'
WRITER_SCRIPT = SCRIPTS_DIR / 'entity_baseline_writer.py'
PLACEHOLDER_VALUES = {
    "主要从事行业相关核心产品的研发、制造与技术支持。",
    "核心产品/服务",
    "国内各行业大型集团客户、主流终端合作方",
    "可比公司",
    "行业同类上市公司",
}
NON_CONCEPT_TAGS = {
    "A股",
    "上市公司",
    "B股",
    "北交所",
    "美股",
    "港股",
    "公司",
    "企业",
    "龙头",
    "核心标的",
    "上游运营商",
    "中游制造",
    "下游应用",
    "信息化",
}
GEO_CONCEPT_TAGS = {
    "中国",
    "美国",
    "日本",
    "韩国",
    "德国",
    "法国",
    "英国",
    "俄罗斯",
    "澳大利亚",
    "加拿大",
    "巴西",
    "智利",
    "阿根廷",
    "印度尼西亚",
    "津巴布韦",
    "非洲",
    "欧洲",
    "东南亚",
    "中东",
}

def get_covered_companies():
    covered = {"SK海力士", "东方通", "中旗新材", "先临三维", "凯大催化", "凯德石英", "同兴科技"}
    for p in RAW_DIR.glob('baseline-updates-*.json'):
        try:
            data = json.loads(p.read_text(encoding='utf-8'))
            if "automatic batch" in str(data.get("source_name", "")):
                continue
            for u in data.get('updates', []):
                covered.add(u.get('company'))
        except Exception as e:
            print(f"Error reading {p.name}: {e}")
    return covered

def get_a_share_candidates(covered):
    candidates = []
    for p in sorted(ENTITIES_DIR.glob('*.md')):
        company = p.stem
        if company in covered:
            continue
        try:
            text = p.read_text(encoding='utf-8', errors='ignore')
            # Extract tickers
            tickers = []
            m = re.search(r'tickers:\s*\[([^\]]*)\]', text)
            if m:
                tickers = [t.strip().replace('"', '').replace("'", "") for t in m.group(1).split(',') if t.strip()]
            if not tickers:
                m_code = re.search(r'\b(?:00|30|60|68|83|87|43)\d{4}\b', text[:1200])
                if m_code:
                    tickers = [m_code.group(0)]
            
            if not tickers:
                continue
                
            code = tickers[0]
            # Verify if it looks like A-share/Beijing code
            if not re.match(r'^(00|30|60|68|83|87|43)\d{4}$', code):
                continue
                
            # Keep track of existing tags
            tags = []
            m_tags = re.search(r'tags:\s*\[([^\]]*)\]', text)
            if m_tags:
                tags = [t.strip().replace('"', '').replace("'", "") for t in m_tags.group(1).split(',') if t.strip()]
            concepts = clean_concepts(tags, company, code)
            
            candidates.append({
                "company": company,
                "code": code,
                "concepts": concepts,
                "file_path": p
            })
        except Exception as e:
            print(f"Error parsing candidate {company}: {e}")
    return candidates

def is_bad_concept_tag(tag, company="", code=""):
    tag = str(tag or "").strip()
    if not tag:
        return True
    if tag in NON_CONCEPT_TAGS or tag in GEO_CONCEPT_TAGS:
        return True
    if tag == company or company in tag:
        return True
    if code and code in tag:
        return True
    if re.fullmatch(r"\d{6}", tag):
        return True
    if re.fullmatch(r"[A-Za-z0-9._-]+", tag):
        return True
    if len(tag) == 1:
        return True
    if tag.endswith(("地区", "国家", "城市", "省", "市")):
        return True
    return False


def clean_concepts(tags, company="", code=""):
    concepts = []
    for tag in tags or []:
        tag = str(tag or "").strip().strip("[]")
        if is_bad_concept_tag(tag, company, code):
            continue
        if tag not in concepts:
            concepts.append(tag)
    return concepts

def fetch_company_raw(company, code):
    print(f"  Fetching raw iFinD data for {company} ({code})...")
    cmd = [
        sys.executable,
        str(FETCH_SCRIPT),
        "--company", company,
        "--code", code
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True, cwd=str(SCRIPTS_DIR))
        out = json.loads(res.stdout)
        return out.get('status') == 'ok'
    except Exception as e:
        print(f"  [ERROR] Fetch failed for {company}: {e}")
        return False

def parse_markdown_table_after(text, heading):
    idx = text.find(heading)
    if idx == -1:
        return []
    chunk = text[idx:]
    lines = [line.rstrip() for line in chunk.splitlines()]
    table = []
    in_table = False
    for line in lines:
        if line.lstrip().startswith('|'):
            in_table = True
            table.append(line)
        elif in_table:
            break
    if len(table) < 3:
        return []

    def cells(line):
        return [c.strip() for c in line.strip().strip('|').split('|')]

    headers = cells(table[0])
    rows = []
    for line in table[2:]:
        row_cells = cells(line)
        if len(row_cells) < len(headers):
            row_cells += [""] * (len(headers) - len(row_cells))
        rows.append(dict(zip(headers, row_cells)))
    return rows


def split_items(value, limit=8):
    items = []
    for item in re.split(r'[、,，;；/]+', str(value or '')):
        item = item.strip()
        if item and item not in items:
            items.append(item)
    return items[:limit]


def clean_values(values):
    clean = []
    for value in values:
        value = str(value or "").strip()
        if value and value not in PLACEHOLDER_VALUES and value not in clean:
            clean.append(value)
    return clean


def text_has_any(text, keywords):
    return any(k in text for k in keywords)


def enrich_concepts(concepts, company, main_biz, products, industry):
    enriched = list(concepts or [])
    text = f"{company} {main_biz} {' '.join(products or [])} {' '.join(str(v) for v in (industry or {}).values())}"
    additions = []
    if text_has_any(text, ["原油", "天然气", "油气开采", "石油和天然气开采"]):
        additions.append("油气开采")
        if "海油" in company or "海上油气" in text:
            additions.append("海上油气")
    if text_has_any(text, ["油田服务", "钻井", "测井", "固井", "物探", "油服"]):
        additions.append("油服")
    if text_has_any(text, ["船舶制造", "舰船", "船舶配套", "海洋运输装备"]):
        additions.append("船舶制造")
    if text_has_any(text, ["海洋工程", "海工装备", "海洋开发装备"]):
        additions.append("海工装备")
    if text_has_any(text, ["国防军工", "军工装备", "海洋防务", "水声电子防务", "特装电子"]):
        additions.append("军工装备")
    if text_has_any(text, ["减速器", "齿轮减速", "行星减速", "机械传动"]):
        additions.append("减速器")
    if text_has_any(text, ["锂盐", "碳酸锂", "氢氧化锂", "氟化锂"]):
        additions.append("锂盐")
    if text_has_any(text, ["锂辉石", "锂矿"]):
        additions.append("锂资源")

    for concept in additions:
        if not is_bad_concept_tag(concept, company) and concept not in enriched:
            enriched.append(concept)
    return filter_contextual_concepts(enriched, company, main_biz, products, industry)


def filter_contextual_concepts(concepts, company, main_biz, products, industry):
    product_text = " ".join(products or [])
    industry_text = " ".join(str(v) for v in (industry or {}).values())
    business_text = f"{company} {main_biz} {product_text} {industry_text}"
    filtered = []
    for concept in concepts or []:
        concept = str(concept or "").strip()
        if not concept:
            continue
        if concept in {"石油", "天然气", "油气开采", "海上油气"} and not text_has_any(
            business_text, ["原油", "天然气", "油气开采", "石油和天然气开采", "油田服务", "钻井", "测井", "固井", "物探"]
        ):
            continue
        if concept in {"全球航运"} and not text_has_any(
            business_text, ["航运", "港口", "船舶运输", "海洋运输装备", "船舶制造"]
        ):
            continue
        if concept in {"全球锂矿", "锂辉石", "锂资源"} and not text_has_any(
            business_text, ["锂", "锂盐", "锂矿", "锂辉石", "碳酸锂", "氢氧化锂"]
        ):
            continue
        if concept not in filtered:
            filtered.append(concept)
    return filtered


def infer_exposure_profile(company, concept, main_biz, products, industry):
    product_text = " ".join(products or [])
    industry_text = " ".join(str(v) for v in (industry or {}).values())
    text = f"{company} {concept} {main_biz} {product_text} {industry_text}"
    business_text = f"{main_biz} {product_text} {industry_text}"
    concept_hit = concept in business_text or any(concept in p or p in concept for p in products)
    direct_product_hit = any(p and (p in concept or concept in p) for p in products or [])
    if text_has_any(concept, ["固态硬盘", "企业级SSD", "SSD"]) and text_has_any(business_text, ["企业级SSD", "SSD产品", "固态硬盘"]):
        concept_hit = True
        direct_product_hit = True
    if text_has_any(concept, ["电镀药水", "封装基板药水", "湿电子化学品"]) and text_has_any(business_text, ["电镀专用化学品", "湿电子化学品", "沉铜电镀"]):
        concept_hit = True
        direct_product_hit = True

    company_role_overrides = {
        "丽人丽妆": "美妆品牌电商运营/渠道服务商",
        "亿嘉和": "电力巡检机器人与智能运维设备商",
        "仙乐健康": "营养健康食品 ODM/剂型代工商",
        "众兴菌业": "食用菌种植生产商/天然原料弱相关",
        "华熙生物": "透明质酸与生物活性物原料/医美终端产品商",
        "博迈科": "海工模块设计建造/FPSO模块供应商",
    }
    if company in company_role_overrides:
        role = company_role_overrides[company]
    elif text_has_any(business_text, ["工业机器人整机", "机器人整机", "机器人系统集成"]):
        role = "工业机器人整机与系统集成商"
    elif text_has_any(business_text, ["运动控制", "伺服系统", "交流伺服", "数控系统"]):
        role = "工业机器人与运动控制系统供应商"
    elif text_has_any(business_text, ["企业级SSD", "SSD产品", "固态硬盘"]):
        role = "企业级 SSD 供应商"
    elif text_has_any(business_text, ["海洋馆", "主题公园", "景区", "景区经营", "旅游服务"]):
        role = "海洋馆/主题景区运营商"
    elif text_has_any(business_text, ["光器件", "光模块", "光通信"]):
        role = "光通信光器件供应商"
    elif text_has_any(business_text, ["有线电视", "广播电视网络", "信息化服务", "数据中心"]):
        role = "有线电视网络与政企信息化服务商"
    elif text_has_any(business_text, ["医药中间体", "原料药", "API"]):
        role = "医药中间体与原料药生产商"
    elif text_has_any(business_text, ["碳纳米管", "导电浆料"]):
        role = "碳纳米管导电材料供应商"
    elif text_has_any(business_text, ["动物疫苗", "饲料", "生猪养殖", "兽药"]):
        role = "动物疫苗、饲料与生猪养殖一体化经营商"
    elif text_has_any(business_text, ["湿电子化学品", "沉铜电镀", "电镀专用化学品"]):
        role = "电子电路湿电子化学品供应商"
    elif products:
        role = f"{products[0]}供应商" if concept_hit else "弱相关，待验证"
    else:
        role = "主营业务相关产品/服务商" if concept_hit else "弱相关，待验证"
    strength = "core" if direct_product_hit else ("core" if concept_hit else "related")
    confidence = "high" if direct_product_hit else ("medium" if concept_hit else "low")

    if company == "博迈科":
        return "海工模块设计建造/FPSO模块供应商", strength, "medium" if text_has_any(concept, ["海工", "FPSO", "海洋工程", "海上油气", "深海", "油气", "油服"]) else confidence

    if text_has_any(business_text, ["美妆", "化妆品", "品牌线上营销", "电子商务", "电商零售", "代运营"]):
        return "美妆品牌电商运营/渠道服务商", strength, confidence

    if text_has_any(business_text, ["巡检机器人", "带电作业机器人", "智能运维", "电力机器人", "智能巡检"]):
        if text_has_any(concept, ["机器人", "智能电网", "电力", "人工智能"]):
            return "电力巡检机器人与智能运维设备商", "core" if concept_hit else "related", "medium" if concept_hit else "low"
        role = "电力巡检机器人与智能运维设备商"

    if text_has_any(business_text, ["营养健康食品", "保健食品", "软胶囊", "片剂", "粉剂", "ODM", "合同生产"]):
        if text_has_any(concept, ["营养", "保健", "食品", "麦角硫因", "代工"]):
            return "营养健康食品 ODM/剂型代工商", "core" if concept_hit else "related", "medium" if concept_hit else "low"
        role = "营养健康食品 ODM/剂型代工商"

    if text_has_any(business_text, ["食用菌", "金针菇", "双孢菇", "菌菇", "真姬菇", "杏鲍菇"]):
        if text_has_any(concept, ["食用菌", "农业", "麦角硫因", "天然提取"]):
            return "食用菌种植生产商/天然原料弱相关", "core" if concept_hit else "related", "medium" if concept_hit else "low"
        role = "食用菌种植生产商/天然原料弱相关"

    if text_has_any(business_text, ["透明质酸", "玻尿酸", "生物活性物", "功能性护肤品", "医美", "原料产品"]):
        if text_has_any(concept, ["透明质酸", "玻尿酸", "医美", "麦角硫因", "生物活性物"]):
            return "透明质酸与生物活性物原料/医美终端产品商", "core" if concept_hit else "related", "medium" if concept_hit else "low"
        role = "透明质酸与生物活性物原料/医美终端产品商"

    if text_has_any(business_text, ["FPSO", "海工模块", "模块设计", "模块建造", "海洋工程装备", "海洋油气开发模块"]):
        if text_has_any(concept, ["海工", "FPSO", "海洋工程", "海上油气", "深海"]):
            return "海工模块设计建造/FPSO模块供应商", "core" if concept_hit else "related", "medium"
        role = "海工模块设计建造/FPSO模块供应商"

    if text_has_any(business_text, ["油田服务", "钻井", "测井", "固井", "物探", "油服"]):
        if text_has_any(concept, ["深海", "深水"]):
            return "深水/近海油田技术服务商", "related", "medium"
        if text_has_any(concept, ["油服", "油田服务", "油气", "石油", "油气开采", "海上油气"]):
            return "油气田技术服务商", "core", "medium"

    upstream_resource_owners = {"中国海油", "中国石油", "中国石化"}
    if company in upstream_resource_owners and text_has_any(business_text, ["原油", "天然气", "油气开采", "石油和天然气开采"]):
        if text_has_any(concept, ["海上油气"]):
            return "海上油气生产运营商", "core", "high"
        if text_has_any(concept, ["油气", "石油", "天然气", "油气开采"]):
            return "上游油气资源开发运营商", "core", "high"
        if text_has_any(concept, ["深海"]):
            return "海上油气资源开发运营商", "related", "medium"

    if text_has_any(business_text, ["船舶制造", "舰船", "船舶配套", "海洋运输装备"]):
        if text_has_any(concept, ["船舶制造", "海工装备", "海洋工程"]):
            return "船舶与海工装备制造商", "core", "medium"
        if text_has_any(concept, ["海洋防务", "军工", "舰船"]):
            return "军工舰船装备供应商", "core", "medium"
        if text_has_any(concept, ["海上油气", "深海"]):
            return "海工装备制造商", "related", "medium"

    if text_has_any(business_text, ["水声电子防务", "特装电子", "海洋防务", "国防军工"]):
        if text_has_any(concept, ["水声", "海洋防务", "军工", "军工装备"]):
            return "海洋防务电子装备供应商", "core", "medium"

    if text_has_any(business_text, ["减速器", "齿轮减速", "行星减速", "机械传动"]):
        if text_has_any(concept, ["减速器", "机械传动"]):
            return "精密传动与减速器供应商", "core", "high"
        if text_has_any(concept, ["机器人"]):
            return "机器人核心零部件供应商", "related", "medium"

    if text_has_any(business_text, ["锂盐", "碳酸锂", "氢氧化锂", "氟化锂"]):
        if text_has_any(concept, ["锂盐", "碳酸锂", "氢氧化锂"]):
            return "锂盐材料供应商", "core", "high"
        if text_has_any(concept, ["锂资源", "锂辉石"]):
            return "锂资源开发及锂盐加工商", "core", "medium"
        if text_has_any(concept, ["全球锂矿", "锂矿"]):
            return "锂资源开发及锂盐加工商", "related", "medium"

    if "软件" in concept or "IT" in concept or "人工智能" in concept:
        role = "技术/软件解决方案商" if concept_hit else "弱相关，待验证"
    elif "旅游" in concept or "景区" in concept or "文旅" in concept:
        role = role if role == "海洋馆/主题景区运营商" else ("景区/文旅综合运营商" if concept_hit else role)
    elif text_has_any(concept, ["材料", "粉", "砂", "树脂"]):
        role = "上游核心材料供应商" if concept_hit else role
    elif text_has_any(concept, ["设备", "机床", "半导体"]):
        role = "核心设备及产品供应商" if concept_hit else role
    elif text_has_any(concept, ["芯片", "集成电路"]):
        role = "核心芯片设计研发商" if concept_hit else role

    if confidence == "low" and role not in company_role_overrides.values() and role not in {
        "食用菌种植生产商/天然原料弱相关",
        "透明质酸与生物活性物原料/医美终端产品商",
    }:
        role = "弱相关，待验证"

    return role, strength, confidence


def infer_chain_layer(company, concept, role, main_biz, products, industry):
    company_overrides = {
        "中国海油": "upstream_resource",
        "中国海防": "midstream_equipment",
        "中国重工": "midstream_equipment",
        "中大力德": "upstream_components",
        "中海油服": "midstream_service",
        "博迈科": "midstream_equipment",
    }
    if company in company_overrides:
        return company_overrides[company]
    text = f"{company} {concept} {role} {main_biz} {' '.join(products or [])} {' '.join(str(v) for v in (industry or {}).values())}"
    if text_has_any(text, ["软件开发", "IT服务", "服务外包", "信息化服务", "技术/软件解决方案", "有线电视网络"]):
        return "midstream_service"
    if text_has_any(text, ["工业机器人整机", "机器人整机", "自动化设备", "系统集成", "运动控制", "伺服系统"]):
        return "midstream_equipment"
    if text_has_any(text, ["海洋馆", "主题景区", "主题公园", "旅游服务", "景区运营"]):
        return "downstream_application"
    if text_has_any(text, ["企业级SSD", "固态硬盘", "数据存储设备"]):
        return "midstream_equipment"
    if text_has_any(text, ["原油", "天然气", "油气开采", "资源开发运营", "锂资源", "矿山", "采矿"]):
        return "upstream_resource"
    if text_has_any(text, ["材料", "原料", "锂盐", "透明质酸", "生物活性物", "化学品", "树脂", "薄膜"]):
        return "upstream_materials"
    if text_has_any(text, ["零部件", "减速器", "连接器", "光模块", "芯片", "器件", "模组", "元件"]):
        return "upstream_components"
    if text_has_any(text, ["设备", "装备", "船舶", "海工", "机器人", "模块建造", "FPSO"]):
        return "midstream_equipment"
    if text_has_any(text, ["油服", "技术服务", "运维", "检测", "代运营", "渠道服务", "ODM", "代工", "流通"]):
        return "midstream_service"
    if text_has_any(text, ["终端", "品牌", "运营商", "电商", "零售", "医美"]):
        return "downstream_application"
    return "midstream"


def build_exposure_evidence(company, concept, main_biz, products, confidence):
    base = f"iFinD主营业务为：{main_biz}；主营产品包括：{'、'.join(products)}。"
    if confidence == "high":
        return f"iFinD主营产品/主营业务与“{concept}”直接匹配，按核心主营暴露处理。{base}"
    if confidence == "medium":
        return f"iFinD主营业务或主营产品支持“{concept}”相关产业链暴露，核心程度仍需公告/年报继续验证。{base}"
    if confidence != "low":
        return base
    if concept == "麦角硫因" and company == "众兴菌业":
        return f"既有 raw/实体概念映射包含“{concept}”；iFinD仅支持其食用菌种植生产主营基础，不直接证明麦角硫因业务，按天然提取路线弱相关/商业价值有限处理。{base}"
    if concept == "麦角硫因" and company == "华熙生物":
        return f"既有 raw/report evidence 可作为“{concept}”判断主证据；iFinD仅支持其透明质酸与生物活性物原料主营基础，不单独证明麦角硫因产能或认证。{base}"
    if concept == "麦角硫因" and company == "丽人丽妆":
        return f"既有 raw/实体概念映射包含“{concept}”；iFinD仅支持其美妆品牌电商运营主营基础，不直接证明麦角硫因业务。{base}"
    return f"既有 raw/实体概念映射包含“{concept}”；iFinD仅支持主营业务基础，不直接证明该题材暴露，需后续公告/年报/研报证据交叉验证。{base}"


def extract_ranked_value(row, metric, rank):
    rank_text = f"第{rank}名"
    for key, value in (row or {}).items():
        if metric in str(key) and rank_text in str(key):
            return str(value or "").strip()
    return ""


def normalize_period(value):
    text = str(value or "").strip()
    m = re.fullmatch(r"(\d{4})(\d{2})(\d{2})", text)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return text


def normalize_amount_yuan(value):
    text = str(value or "").replace(",", "").strip()
    try:
        num = float(text)
    except Exception:
        return text
    if abs(num) >= 100000000:
        return f"{num / 100000000:.2f}亿元"
    if abs(num) >= 10000:
        return f"{num / 10000:.2f}万元"
    return f"{num:.2f}元"


def build_key_data(summary_content):
    rows = parse_markdown_table_after(summary_content, "## 日期序列相关数据")
    if not rows:
        return []
    row = rows[0]
    period = normalize_period(row.get("日期", ""))
    key_data = []
    for rank in range(1, 6):
        name = extract_ranked_value(row, "项目名称", rank)
        if not name or name in {"其他", "其他业务", "合计"}:
            continue
        name = re.sub(r"(收入|销售收入)$", "", name).strip()
        income = extract_ranked_value(row, "项目收入", rank)
        margin = extract_ranked_value(row, "项目毛利率", rank)
        if income:
            key_data.append({
                "indicator": f"{name}收入",
                "value": normalize_amount_yuan(income),
                "period": period,
                "source": "iFinD 主营构成",
            })
        if margin:
            key_data.append({
                "indicator": f"{name}毛利率",
                "value": f"{str(margin).strip()}%",
                "period": period,
                "source": "iFinD 主营构成",
            })
        if len(key_data) >= 6:
            break
    return key_data


def raw_has_unique_security_match(raw_data, company, code):
    target_code = re.sub(r"\D", "", str(code or ""))
    matches = []
    seen = set()
    for result in raw_data.get("results", []):
        content = str(result.get("content", ""))
        rows = []
        rows.extend(parse_markdown_table_after(content, "|证券代码|证券简称|"))
        rows.extend(parse_markdown_table_after(content, "# 公司所属行业分类"))
        for row in rows:
            row_code = re.sub(r"\D", "", str(row.get("证券代码", "")))
            short_name = str(row.get("证券简称", "")).strip()
            if row_code != target_code:
                continue
            key = (row_code, short_name)
            if key in seen:
                continue
            seen.add(key)
            matches.append(row)
    if len(matches) != 1:
        print(f"  [SKIP] {company}: raw securities table must contain exactly one unique row for code {code}; got {len(matches)}.")
        return False
    short_name = str(matches[0].get("证券简称", "")).strip()
    if short_name and company not in short_name and short_name not in company:
        print(f"  [SKIP] {company}: raw security short name mismatch for code {code}: {short_name}.")
        return False
    return True

def parse_and_build_update(company, code, concepts):
    raw_path = RAW_DIR / f"{company}.json"
    if not raw_path.exists():
        return None
    try:
        raw_data = json.loads(raw_path.read_text(encoding='utf-8'))
    except Exception as e:
        print(f"  [ERROR] Failed to load raw JSON for {company}: {e}")
        return None
    if not raw_has_unique_security_match(raw_data, company, code):
        return None

    info_content = ""
    summary_content = ""
    for r in raw_data.get('results', []):
        if r.get('tool') == 'get_stock_info':
            info_content = r.get('content', '')
        elif r.get('tool') == 'get_stock_summary':
            summary_content = r.get('content', '')

    industry_rows = parse_markdown_table_after(summary_content, '# 公司所属行业分类')
    business_rows = parse_markdown_table_after(summary_content, '# 公司主营业务信息')
    fallback_rows = parse_markdown_table_after(info_content, '|证券代码|证券简称|')

    industry_row = industry_rows[0] if industry_rows else (fallback_rows[0] if fallback_rows else {})
    business_row = business_rows[0] if business_rows else {}

    sw_industry = industry_row.get('所属申万行业', '').strip()
    ths_industry = industry_row.get('所属同花顺行业', '').strip()
    csrc_industry = industry_row.get('所属新证监会行业', '') or industry_row.get('所属国民经济行业', '')
    industry = {
        "申万行业": sw_industry,
        "同花顺行业": ths_industry,
        "证监会行业": csrc_industry,
    }
    main_biz = business_row.get('主营业务', '').strip()
    products = clean_values(split_items(business_row.get('主营产品名称') or business_row.get('主营产品类型')))
    comp_list = clean_values(split_items(industry_row.get('竞争公司') or industry_row.get('可比公司'), limit=5))

    if not main_biz or not products:
        print(f"  [SKIP] {company}: raw iFinD data lacks main_business/products; needs manual LLM extraction.")
        return None
    concepts = enrich_concepts(clean_concepts(concepts, company, code), company, main_biz, products, industry)
    key_data = build_key_data(summary_content)

    # Exposures config
    exposures = []
    for c in concepts:
        c = str(c).strip()
        if not c:
            continue
        role, strength, confidence = infer_exposure_profile(company, c, main_biz, products, industry)
        chain_layer = infer_chain_layer(company, c, role, main_biz, products, industry)
        evidence = build_exposure_evidence(company, c, main_biz, products, confidence)
        exposures.append({
            "concept": c,
            "role": role,
            "chain_layer": chain_layer,
            "strength": strength,
            "confidence": confidence,
            "evidence": evidence
        })

    if not exposures:
        print(f"  [SKIP] {company}: no existing concepts to map exposures.")
        return None

    return {
        "company": company,
        "code": code,
        "industry": industry,
        "main_business": main_biz,
        "products": products,
        "concepts": concepts,
        "customers_ecosystem": [],
        "competitors": comp_list[:3],
        "exposures": exposures,
        "key_data": key_data,
        "risks": [
            "行业竞争加剧风险",
            "宏观经济环境及行业投资不及预期风险"
        ],
        "open_questions": [
            "产业链暴露来自 iFinD 主营业务与既有概念标签交叉判断，后续需用公告/年报继续验证核心程度。"
        ],
        "raw_source": f"raw/ifind-baseline/{company}.json"
    }

def process_batch():
    covered = get_covered_companies()
    candidates = get_a_share_candidates(covered)
    
    if not candidates:
        print("[FINISHED] No more A-share baseline candidates left to ingest!")
        return False
        
    # Get current batch number
    existing_batches = []
    for p in RAW_DIR.glob('baseline-updates-*.json'):
        m = re.search(r'batch(\d+)', p.name)
        if m:
            existing_batches.append(int(m.group(1)))
    next_batch_num = max(existing_batches) + 1 if existing_batches else 71
    
    batch_companies = candidates[:5]
    print(f"\n==================================================")
    print(f"🚀 Starting BATCH {next_batch_num} | 5 Companies:")
    for idx, c in enumerate(batch_companies):
        print(f"  {idx+1}. {c['company']} ({c['code']})")
    print(f"==================================================")
    
    # Step 1: Fetch raw iFinD
    success_count = 0
    for c in batch_companies:
        ok = fetch_company_raw(c['company'], c['code'])
        if ok:
            success_count += 1
            
    if success_count == 0:
        print(f"[ERROR] Failed to fetch raw iFinD data for all 5 companies in Batch {next_batch_num}. Aborting.")
        return False
        
    # Step 2: Parse and Assemble Batch JSON
    updates = []
    for c in batch_companies:
        up = parse_and_build_update(c['company'], c['code'], c['concepts'])
        if up:
            updates.append(up)
            
    if not updates:
        print(f"[ERROR] No valid updates assembled for Batch {next_batch_num}. Aborting.")
        return False
        
    batch_json_data = {
        "source_name": f"iFinD baseline {date.today().isoformat()} batch{next_batch_num}",
        "updates": updates
    }
    
    batch_json_file = RAW_DIR / f"baseline-updates-{date.today().isoformat()}-batch{next_batch_num}.json"
    batch_json_file.write_text(json.dumps(batch_json_data, ensure_ascii=False, indent=2) + "\n", encoding='utf-8')
    print(f"✓ Saved Batch JSON to: {batch_json_file.name}")
    
    # Step 3: Run entity_baseline_writer
    print(f"  Writing Batch {next_batch_num} updates to Obsidian vault and Graph...")
    cmd = [
        sys.executable,
        str(WRITER_SCRIPT)
    ]
    try:
        res = subprocess.run(cmd, input=json.dumps(batch_json_data, ensure_ascii=False), capture_output=True, text=True, check=True, cwd=str(SCRIPTS_DIR))
        out = json.loads(res.stdout)
        if out.get('status') == 'ok':
            print(f"🎉 Batch {next_batch_num} successfully processed and updated!")
            print(f"  Updated: {len(out.get('updated', []))} files.")
            if out.get('skipped'):
                print(f"  [WARNING] Skipped: {out.get('skipped')}")
            return True
        else:
            print(f"  [ERROR] Writer execution output is not OK: {out}")
            return False
    except Exception as e:
        print(f"  [ERROR] Failed running writer: {e}")
        return False

def main():
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        target_runs = int(sys.argv[1])
    else:
        target_runs = 1
        
    print(f"Starting A-Share Baseline Orchestration Loop. Target runs: {target_runs}")
    completed_runs = 0
    for i in range(target_runs):
        ok = process_batch()
        if not ok:
            print(f"Orchestrator stopped at loop {i+1}.")
            break
        completed_runs += 1
        
    print(f"\n[SUMMARY] Orchestration loop completed. Runs: {completed_runs}/{target_runs}.")

if __name__ == '__main__':
    main()
