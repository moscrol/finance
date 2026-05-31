#!/usr/bin/env python3
"""Build a minimal baseline update JSON from AkShare raw files."""

import argparse
import json
import re
from datetime import date
from pathlib import Path


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def raw_rel_path(raw_path):
    path = Path(raw_path)
    parts = path.parts
    if "wiki" in parts:
        idx = parts.index("wiki")
        return "/".join(parts[idx + 1 :])
    return str(path)


def records(raw):
    out = []
    for result in raw.get("results", []) or []:
        content = result.get("content")
        if isinstance(content, list):
            out.extend([x for x in content if isinstance(x, dict)])
    return out


def first_value(rows, keys):
    for row in rows:
        for key in keys:
            value = row.get(key)
            if value not in (None, ""):
                return str(value).strip()
    return ""


def infer_concepts(products, main_business, extra_concepts):
    concepts = list(extra_concepts or [])
    text = " ".join([main_business] + products)
    mapping = [
        ("光模块", ["光模块", "光通信", "光互联"]),
        ("CPO", ["光模块", "光通信"]),
        ("国产算力", ["光模块", "通信设备", "服务器", "算力"]),
        ("半导体", ["芯片", "半导体", "集成电路"]),
        ("固态电池", ["固态电池", "电池设备", "锂电"]),
    ]
    for concept, keywords in mapping:
        if concept not in concepts and any(k in text for k in keywords):
            concepts.append(concept)
    return concepts[:6]


def infer_chain_layer(main_business, products):
    text = " ".join([main_business] + products)
    if any(k in text for k in ("设备", "装备", "仪器")):
        return "upstream_equipment"
    if any(k in text for k in ("材料", "化学", "原料")):
        return "upstream_materials"
    if any(k in text for k in ("制造", "生产", "光模块", "芯片", "电池", "组件")):
        return "midstream"
    return "midstream"


def build_update(raw, raw_path, extra_concepts):
    rows = records(raw)
    company = raw.get("company", "")
    code = re.sub(r"\D", "", str(raw.get("code", "")))
    main_business = raw.get("main_business") or first_value(rows, ["主营业务", "经营范围", "公司简介"])
    products = raw.get("products") or []
    if not products:
        products = []
        for row in rows:
            for key in ("产品名称", "产品类型", "主营产品", "项目名称"):
                value = row.get(key)
                if value not in (None, ""):
                    text = str(value).strip()
                    if text and text not in products:
                        products.append(text)
    industry = raw.get("industry") or {}
    if not industry:
        value = first_value(rows, ["所属行业", "行业", "行业类别"])
        if value:
            industry = {"所属行业": value}
    concepts = infer_concepts(products, main_business, extra_concepts)
    chain_layer = infer_chain_layer(main_business, products)
    role = f"{products[0]}研发/生产商" if products else "主营业务相关产品/服务提供商"
    evidence = main_business
    exposure_concept = concepts[0] if concepts else (products[0] if products else "主营业务")
    return {
        "company": company,
        "code": code,
        "source_type": "akshare",
        "baseline_source_label": "AkShare 公开资料 / 巨潮公司资料",
        "raw_source": raw_rel_path(raw_path),
        "industry": industry,
        "main_business": main_business,
        "products": products[:12],
        "business_segments": [],
        "concepts": concepts,
        "customers_ecosystem": [],
        "competitors": [],
        "exposures": [
            {
                "concept": exposure_concept,
                "role": role,
                "chain_layer": chain_layer,
                "strength": "related",
                "confidence": "medium",
                "evidence_layer": "L2",
                "update_type": "baseline",
                "evidence": evidence,
            }
        ],
        "key_data": [],
        "risks": ["公开资料字段有限，产业链核心程度需结合年报、公告或客户验证继续核实。"],
        "open_questions": ["AkShare 公开资料只支持轻量 baseline，后续需补年报收入结构和客户/产品验证。"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-file", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--concept", action="append", default=[])
    parser.add_argument("--source-name", default=f"AkShare baseline {date.today().isoformat()}")
    args = parser.parse_args()

    raw = load_json(args.raw_file)
    data = {"source_name": args.source_name, "updates": [build_update(raw, args.raw_file, args.concept)]}
    out = Path(args.out).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "out": str(out), "updates": len(data["updates"])}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
