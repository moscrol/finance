#!/usr/bin/env python3
import argparse
import json
import re
from datetime import date
from pathlib import Path

DEFAULT_WIKI = Path("/Users/lbq/Desktop/c c/知识库/wiki")


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def raw_rel_path(raw_path):
    path = Path(raw_path)
    parts = path.parts
    if "wiki" in parts:
        idx = parts.index("wiki")
        return "/".join(parts[idx + 1 :])
    return str(path)


def result_content(raw, tool):
    for item in raw.get("results", []) or []:
        if item.get("tool") == tool:
            return item.get("content") or {}
    return {}


def f10_text(raw):
    content = result_content(raw, "mootdx_f10")
    if not isinstance(content, dict):
        return ""
    return "\n".join(str(content.get(key, "")) for key in ("公司概况", "行业分析", "最新提示"))


def first_between(text, start, stops):
    idx = text.find(start)
    if idx < 0:
        return ""
    chunk = text[idx + len(start) : idx + len(start) + 500]
    end_positions = [chunk.find(stop) for stop in stops if chunk.find(stop) > 0]
    if end_positions:
        chunk = chunk[: min(end_positions)]
    return clean_table_text(chunk)


def clean_table_text(text):
    text = re.sub(r"[│｜|┌┐└┘├┤─┬┴┼]+", " ", str(text or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text.strip(" ：:")


def f10_company_name(raw, code):
    if str(raw.get("company") or "").strip():
        return str(raw.get("company")).strip()
    text = str(result_content(raw, "mootdx_f10").get("公司概况", ""))
    marker = f"◇{code} "
    idx = text.find(marker)
    if idx >= 0:
        return text[idx + len(marker) :].split()[0].strip()
    return raw.get("company", "")


def f10_industry(raw):
    text = str(result_content(raw, "mootdx_f10").get("行业分析", ""))
    marker = "【所属行业】"
    idx = text.find(marker)
    if idx >= 0:
        value = text[idx + len(marker) : idx + len(marker) + 120].strip()
        return value.split("共(", 1)[0].strip()
    stock_info = result_content(raw, "eastmoney_stock_info")
    return str(stock_info.get("industry") or "").strip()


def main_business(raw):
    text = f10_text(raw)
    value = first_between(text, "主营业务", ["公司简介", "经营范围", "├", "└"])
    if value:
        return value
    for item in raw.get("akshare_fallback", []) or []:
        for row in item.get("content", []) or []:
            for key in ("主营业务", "经营范围", "公司简介"):
                if row.get(key):
                    return str(row[key]).strip()
    return ""


def business_scope(raw):
    return first_between(f10_text(raw), "经营范围", ["主营业务", "公司简介", "├", "└"])


def akshare_products(raw):
    products = []
    generic = {"研发", "开发", "生产", "销售", "制造", "服务", "经营", "业务", "产品", "设计"}
    for item in raw.get("akshare_fallback", []) or []:
        for row in item.get("content", []) or []:
            for key in ("产品名称", "产品类型"):
                value = str(row.get(key) or "").strip()
                for part in re.split(r"[、,，;；/]+", value):
                    part = part.strip()
                    if part in generic:
                        continue
                    if 2 <= len(part) <= 24 and part not in products:
                        products.append(part)
    return products[:12]


def split_products(text):
    candidates = []
    product_text = str(text or "")
    product_text = product_text.replace("以及", "、").replace("及其", "及其")
    product_text = product_text.strip("。；; ")
    product_text = re.sub(r"^(从事|主要从事|公司从事)", "", product_text).strip()
    product_text = re.sub(r"(的)?(研发|开发|生产|销售|工程安装|售后服务|设计|制造|服务)([、,，和及与]*(研发|开发|生产|销售|工程安装|售后服务|设计|制造|服务))*业务?[。；;]*$", "", product_text)
    product_text = re.sub(r"四个领域产品.*$", "", product_text)
    product_text = re.sub(r"(主要)?包括[:：]", "、", product_text)
    for item in re.split(r"[、,，;；/]+", product_text):
        item = item.strip()
        item = re.sub(r"^(公司|主营业务|一般项目|许可项目)[:：]?", "", item).strip()
        item = item.strip("。；; ")
        item = re.sub(r"(的)?(研发|开发|生产|销售|工程安装|售后服务|设计|制造|服务|生产及|销售及|和销售|的生产)$", "", item).strip()
        for suffix in ("的生产", "的销售", "的研发", "的开发", "的制造"):
            if item.endswith(suffix):
                item = item[: -len(suffix)].strip()
        item = item.strip("。；; 及与和")
        for suffix in ("的生产", "的销售", "的研发", "的开发", "的制造"):
            if item.endswith(suffix):
                item = item[: -len(suffix)].strip()
        if item in {"研发", "开发", "生产", "销售", "制造", "服务", "经营", "业务", "产品", "设计"}:
            continue
        if 2 <= len(item) <= 24 and item not in candidates:
            candidates.append(item)
    return candidates[:12]


def infer_concepts(seed_concepts, main_biz, products, industry):
    concepts = []
    for item in seed_concepts or []:
        item = str(item or "").strip()
        if item and item not in concepts:
            concepts.append(item)
    text = f"{main_biz} {' '.join(products)} {industry}"
    rules = [
        ("商业航天", ["航天", "卫星", "火箭"]),
        ("无人系统", ["无人", "无人机", "智能无人飞行器"]),
        ("卫星互联网", ["卫星", "卫星通信", "卫星导航", "低轨"]),
        ("惯性导航", ["惯性", "导航", "光纤惯组"]),
        ("集成电路", ["集成电路", "芯片", "半导体"]),
        ("化工", ["基础化工", "化学制品", "聚氨酯", "异氰酸酯"]),
        ("高温合金", ["高温合金"]),
        ("医药生物", ["医药生物", "生物制品", "微生态制剂"]),
        ("电池材料", ["锂离子电池材料", "电池化学品"]),
        ("电子信息材料", ["电子信息材料"]),
        ("智能交通", ["智能交通"]),
        ("网络安全", ["网络安全", "互联网安全", "数字安全"]),
        ("数据安全", ["数据安全", "互联网数据服务", "数字安全"]),
        ("电子化学品", ["电子化学品"]),
        ("电镀添加剂", ["电镀化学品", "表面工程专用化学品"]),
        ("机器人", ["机器人", "伺服", "减速器"]),
        ("固态电池", ["固态电池"]),
        ("光模块", ["光模块", "光通信"]),
        ("PCB", ["印制电路", "PCB"]),
    ]
    for concept, keywords in rules:
        if concept not in concepts and any(keyword in text for keyword in keywords):
            concepts.append(concept)
    return concepts[:8]


def concept_support(concept, main_biz, products, industry):
    text = f"{main_biz} {' '.join(products)} {industry}"
    if concept and concept in text:
        return "medium"
    aliases = {
        "化工": ["基础化工", "化学制品", "聚氨酯", "异氰酸酯", "MDI"],
        "光学材料": ["聚氨酯", "异氰酸酯", "化学制品"],
        "光学塑料": ["聚氨酯", "异氰酸酯", "化学制品"],
        "高温合金": ["高温合金"],
        "医药生物": ["医药生物", "生物制品", "微生态制剂"],
        "电池材料": ["锂离子电池材料", "电池化学品"],
        "电子信息材料": ["电子信息材料"],
        "半导体材料": ["电子信息材料"],
        "智能交通": ["智能交通"],
        "网络安全": ["网络安全", "互联网安全", "数字安全"],
        "数据安全": ["数据安全", "互联网数据服务", "数字安全"],
        "电子化学品": ["电子化学品"],
        "电镀添加剂": ["电镀化学品", "表面工程专用化学品"],
    }
    hits = aliases.get(concept, [])
    if any(hit in text for hit in hits):
        return "low"
    return ""


def infer_role(company, concept, main_biz, products):
    text = f"{company} {concept} {main_biz} {' '.join(products)}"
    if "高温合金" in text and any(k in concept for k in ("航空发动机", "单晶叶片", "航空航天", "军工", "增材制造", "3D打印")):
        return "高温合金材料及航空航天相关材料供应商"
    if "聚氨酯" in text or "异氰酸酯" in text:
        if any(k in concept for k in ("光学材料", "光学塑料", "COC", "PMMA", "化工")):
            return "聚氨酯/异氰酸酯等化工材料供应商"
    if "锂离子电池材料" in text and any(k in concept for k in ("磷酸铁锂", "LFP", "电池")):
        return "锂离子电池材料供应商"
    if "电子信息材料" in text and any(k in concept for k in ("光刻胶", "半导体材料", "光刻胶单体", "光刻胶树脂", "光致产酸剂")):
        return "电子信息材料与光刻胶相关材料供应商"
    if "电子信息材料" in text and "电子信息材料" in concept:
        return "电子信息材料供应商"
    if "电池材料" in concept and "锂离子电池材料" in text:
        return "锂离子电池材料供应商"
    if "化工" in concept and ("聚氨酯" in text or "异氰酸酯" in text):
        return "聚氨酯/异氰酸酯等化工材料供应商"
    if "智能交通" in text and "激光雷达" in concept:
        return "智能交通与激光雷达相关产品供应商"
    if "智能交通" in text and "智能交通" in concept:
        return "智能交通产品与解决方案供应商"
    if concept in ("网络安全", "数据安全"):
        return "数字安全与互联网安全产品/服务商"
    if concept in ("电子化学品", "电镀添加剂"):
        return "表面工程专用化学品与电子化学品供应商"
    if concept and (concept in main_biz or any(concept in p or p in concept for p in products)):
        return f"{concept}相关产品/材料供应商"
    if "无人" in concept or "无人" in text:
        return "无人系统相关产品与装备供应商"
    if "航天" in concept or "卫星" in concept:
        return "航天电子信息与相关装备供应商"
    if "导航" in concept:
        return "导航与测控相关产品供应商"
    if "芯片" in concept or "集成电路" in concept:
        return "集成电路/电子器件相关产品供应商"
    if products:
        return f"{products[0]}相关产品供应商"
    return "主营业务相关产品/服务商"


def infer_chain_layer(role, main_biz, products):
    text = f"{role} {main_biz} {' '.join(products)}"
    if any(k in text for k in ("材料", "化学品", "原料")):
        return "upstream_materials"
    if any(k in text for k in ("器件", "芯片", "连接器", "模组", "组件")):
        return "upstream_components"
    if any(k in text for k in ("装备", "设备", "系统", "整机", "制造")):
        return "midstream_equipment"
    if any(k in text for k in ("服务", "运营")):
        return "midstream_service"
    return "midstream"


def build_update(raw, raw_path, seed_concepts):
    code = re.sub(r"\D", "", str(raw.get("code", "")))
    company = f10_company_name(raw, code)
    industry_text = f10_industry(raw)
    main_biz = main_business(raw)
    scope = business_scope(raw)
    products = akshare_products(raw) or split_products(main_biz) or split_products(scope)
    candidate_concepts = infer_concepts(seed_concepts, main_biz, products, industry_text)
    concepts = []
    unsupported_seed_concepts = []
    for concept in candidate_concepts:
        if concept_support(concept, main_biz, products, industry_text):
            concepts.append(concept)
        elif concept in (seed_concepts or []):
            unsupported_seed_concepts.append(concept)
    exposures = []
    for concept in concepts:
        role = infer_role(company, concept, main_biz, products)
        chain_layer = infer_chain_layer(role, main_biz, products)
        confidence = concept_support(concept, main_biz, products, industry_text) or "low"
        strength = "related" if confidence == "medium" else "peripheral"
        exposures.append({
            "concept": concept,
            "role": role,
            "chain_layer": chain_layer,
            "strength": strength,
            "confidence": confidence,
            "evidence_layer": "L2",
            "update_type": "baseline",
            "source_quality": "market_data_vendor_f10",
            "evidence": f"mootdx F10主营业务显示：{main_biz}",
        })
    raw["main_business"] = main_biz
    raw["products"] = products
    raw["industry"] = {"F10行业": industry_text} if industry_text else {}
    Path(raw_path).write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    open_questions = ["该公司相关题材暴露是否已有订单、客户认证、收入占比或产能等L3官方验证？"]
    if unsupported_seed_concepts:
        open_questions.append(f"已有标签/概念 {', '.join(unsupported_seed_concepts[:8])} 未由本次F10主营或行业字段直接支撑，需公告、年报或专题资料复核后再写入图谱。")
    return {
        "company": company,
        "code": code,
        "source_type": "a-stock",
        "baseline_source_label": "a-stock-data / mootdx F10 / AkShare fallback",
        "raw_source": raw_rel_path(raw_path),
        "industry": {"F10行业": industry_text} if industry_text else {},
        "main_business": main_biz,
        "products": products,
        "business_segments": [],
        "concepts": concepts,
        "customers_ecosystem": [],
        "competitors": [],
        "exposures": exposures,
        "key_data": [],
        "risks": ["F10/公开资料为L2 baseline，核心程度需后续公告、年报或订单验证。"],
        "open_questions": open_questions,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-file", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--concept", action="append", default=[])
    parser.add_argument("--source-name", default=f"a-stock baseline {date.today().isoformat()}")
    args = parser.parse_args()
    raw = load_json(args.raw_file)
    update = build_update(raw, args.raw_file, args.concept)
    data = {"source_name": args.source_name, "updates": [update]}
    out = Path(args.out).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "out": str(out), "updates": 1, "company": update.get("company")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
