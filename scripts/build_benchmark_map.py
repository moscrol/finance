#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path
from typing import Any


DEFAULT_VAULT = Path.home() / "Desktop/c c/知识库/wiki"


def clean_text(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [clean_text(x) for x in value if clean_text(x)]
    text = clean_text(value)
    if not text:
        return []
    return [x.strip() for x in re.split(r"[,，、/｜|;；]+", text) if x.strip()]


def unique(values: list[str]) -> list[str]:
    seen = set()
    out = []
    for value in values:
        text = clean_text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def extract_json_blocks(text: str) -> list[Any]:
    blocks = []
    for match in re.finditer(r"```json\s*(.*?)\s*```", text, flags=re.S | re.I):
        raw = match.group(1).strip()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, (dict, list)):
            blocks.append(parsed)
    return blocks


def split_md_row(line: str) -> list[str]:
    cells = [clean_text(cell) for cell in line.strip().strip("|").split("|")]
    return [re.sub(r"\*\*(.*?)\*\*", r"\1", cell).strip() for cell in cells]


def is_separator(line: str) -> bool:
    cells = split_md_row(line)
    return bool(cells) and all(re.fullmatch(r":?-{2,}:?", cell) for cell in cells)


def parse_markdown_tables(text: str) -> list[dict[str, Any]]:
    lines = text.splitlines()
    tables = []
    section = ""
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("#"):
            section = line.lstrip("#").strip()
            i += 1
            continue
        if line.strip().startswith("|") and i + 1 < len(lines) and is_separator(lines[i + 1]):
            headers = split_md_row(line)
            rows = []
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = split_md_row(lines[i])
                rows.append({headers[j]: cells[j] if j < len(cells) else "" for j in range(len(headers))})
                i += 1
            tables.append({"section": section, "headers": headers, "rows": rows})
            continue
        i += 1
    return tables


def first_table_value(tables: list[dict[str, Any]], field: str) -> str:
    for table in tables:
        if set(table.get("headers") or []) >= {"字段", "内容"}:
            for row in table.get("rows") or []:
                if clean_text(row.get("字段")) == field:
                    return clean_text(row.get("内容"))
    return ""


def table_values(tables: list[dict[str, Any]], field: str) -> list[str]:
    values = []
    for table in tables:
        if set(table.get("headers") or []) >= {"字段", "内容"}:
            for row in table.get("rows") or []:
                if clean_text(row.get("字段")) == field:
                    values.append(clean_text(row.get("内容")))
    return unique(values)


def horizontal_table_values(tables: list[dict[str, Any]], field: str) -> list[str]:
    values = []
    for table in tables:
        headers = table.get("headers") or []
        if not headers or clean_text(headers[0]) != "项目":
            continue
        for row in table.get("rows") or []:
            if clean_text(row.get("项目")) == field:
                for header in headers[1:]:
                    value = clean_text(row.get(header))
                    if value:
                        values.append(value)
    return unique(values)


def horizontal_company_headers(tables: list[dict[str, Any]]) -> list[str]:
    values = []
    for table in tables:
        headers = table.get("headers") or []
        if headers and clean_text(headers[0]) == "项目" and len(headers) > 2:
            values.extend(clean_text(header) for header in headers[1:] if clean_text(header))
    return unique(values)


def frontmatter_value(text: str, field: str) -> str:
    match = re.search(rf"^\s*>\s*\*\*{re.escape(field)}\*\*\s*[：:]\s*(.+?)\s*$", text, flags=re.M)
    return clean_text(match.group(1)) if match else ""


def derive_theme_routes(data: dict[str, Any]) -> list[str]:
    text_parts = [
        data.get("benchmark_theme"),
        data.get("core_position"),
        data.get("industry"),
    ]
    for row in data.get("benchmark_business_lines") or []:
        if isinstance(row, dict):
            text_parts.extend(
                [
                    row.get("business_line"),
                    row.get("english_name"),
                    row.get("definition"),
                    "、".join(as_list(row.get("key_products"))),
                    "、".join(as_list(row.get("downstream_applications"))),
                ]
            )
    for row in data.get("mapping_gaps") or []:
        if isinstance(row, dict):
            text_parts.extend([row.get("business_line"), row.get("gap_reason"), row.get("possible_beneficiary_direction")])
    text = " ".join(clean_text(x) for x in text_parts if clean_text(x))
    routes = []
    rules = [
        ("光模块", ("光模块", "光互联", "光通信", "Optical Transceiver", "Datacom Transceiver", "DSP", "CPO", "硅光", "Photonic", "AEC", "光引擎")),
        ("CPO", ("CPO", "Co-Packaged", "Photonic Fabric", "硅光")),
        ("光芯片", ("光芯片", "EML激光", "EML芯片", "VCSEL", "InP基", "InP芯片", "6英寸InP", "CW激光器", "激光芯片")),
        ("OCS光交换机", ("OCS光", "光电路交换机", "光路交换机", "Optical Circuit Switch", "MEMS光交换", "LCOS")),
        ("工业激光", ("工业激光", "Industrial Lasers", "光纤激光器", "超快激光器", "准分子激光器", "激光设备")),
        ("光学材料", ("光学晶体", "磁光材料", "TGG", "TSAG", "法拉第旋光片", "工程材料")),
        ("光刻机", ("光刻系统", "EUV光刻系统", "DUV光刻系统", "ArFi", "High-NA", "TWINSCAN", "SMEE")),
        ("半导体设备", ("半导体设备", "光刻系统", "量测", "检测系统", "曝光系统", "装机基盘", "前道设备")),
        ("先进制程", ("先进制程", "3nm", "2nm", "sub-2nm", "7nm", "High-NA", "EUV")),
        ("晶圆制造", ("前道", "曝光", "掩模")),
        ("量测设备", ("量测", "检测系统", "Metrology", "Inspection", "缺陷检测", "良率控制")),
        ("半导体软件", ("计算光刻", "OPC", "Brion", "制造类EDA", "器件建模EDA", "TCAD")),
        ("AI算力", ("AI算力", "AI基础设施", "AI工厂", "Blackwell", "Hopper", "Vera Rubin", "CUDA", "AI训练", "AI推理", "算力")),
        ("国产GPU", ("国产GPU", "DCU", "CUDA", "Blackwell", "Hopper", "图形GPU", "GeForce", "RTX")),
        ("AI芯片", ("AI芯片", "AI GPU", "DCU", "加速芯片", "定制AI加速芯片", "昇腾", "思元")),
        ("AI ASIC", ("AI ASIC", "Custom Silicon", "XPU", "定制AI", "定制ASIC", "云厂商定制")),
        ("交换芯片", ("以太网交换芯片", "Ethernet Switch", "Teralynx", "Prestera", "UALink", "ESUN")),
        ("存储芯片", ("服务器/数据中心DRAM", "移动/消费DRAM", "企业级SSD", "消费级NAND/SSD", "利基型/特种存储", "SSD控制器", "NAND Flash", "3D NAND", "HBM封装", "DRAM封测", "内存接口芯片", "存储器件")),
        ("HBM", ("HBM（高带宽内存）", "High Bandwidth Memory", "HBM3E", "HBM4", "HBM Base Die")),
        ("DRAM", ("服务器/数据中心DRAM", "移动/消费DRAM", "Server DRAM", "Mobile DRAM", "DDR5 RDIMM", "MRDIMM", "LPDDR")),
        ("3D NAND", ("消费级NAND/SSD", "Enterprise SSD", "NAND Flash", "3D NAND", "QLC eSSD", "TLC eSSD", "SLC NAND")),
        ("固态硬盘（SSD）", ("企业级SSD", "消费级NAND/SSD", "Enterprise SSD", "Client SSD", "PCIe 5.0/6.0 SSD")),
        ("利基存储", ("利基型/特种存储", "Specialty Memory", "NOR Flash", "SLC NAND", "MCP", "eMCP")),
        ("存储互连", ("服务器存储连接", "FC SAN", "SAS", "RAID", "PCIe Switch", "PCIe Retimer", "NVMe-oF", "CXL互连")),
        ("AI服务器", ("AI服务器", "数据中心", "AI集群", "Scale-Up", "Scale-Out")),
        ("晶圆代工", ("晶圆代工", "纯晶圆代工", "Foundry", "先进制程逻辑代工", "成熟/特色工艺代工")),
        ("先进封装", ("Chiplet", "HBM", "先进封装", "die-to-die", "CoWoS", "SoIC", "混合键合", "TSV")),
        ("CoWoS", ("CoWoS", "Chip on Wafer on Substrate", "硅中介层", "reticle")),
        ("硅光", ("硅光", "硅光子", "COUPE", "Photonic Engine", "光引擎", "CPO")),
        ("成熟制程", ("成熟/特色工艺", "特色工艺", "BCD", "SOI", "N28", "N16HV", "显示驱动")),
        ("光伏", ("光伏", "太阳能", "Solar", "CdTe", "薄膜组件")),
        ("光伏组件", ("光伏组件", "太阳能组件", "Module", "Series 6", "Series 7")),
        ("医疗器械", ("医疗器械", "医疗科技", "Medical Device", "MedTech", "介入医疗器械")),
        ("电生理", ("电生理", "Electrophysiology", "PFA", "消融", "Ablation")),
        ("手术机器人", ("手术机器人", "Surgical Robot", "da Vinci", "Hugo")),
        ("内镜耗材", ("内窥镜", "内镜", "Endoscopy", "Endoscopic")),
        ("生命科学工具", ("生命科学工具", "Life Sciences", "科学服务", "Scientific", "实验室产品", "科研试剂")),
        ("科学仪器", ("科学仪器", "分析仪器", "Analytical Instruments", "质谱", "色谱", "冷冻电镜")),
        ("生物制药上游", ("生物制药工艺", "Biotechnology", "Cytiva", "Pall", "层析介质", "一次性生物反应器")),
        ("创新药", ("创新药", "生物制药", "Biopharma", "Pharmaceutical", "药品", "药物", "新分子形式")),
        ("肿瘤药", ("肿瘤", "Oncology", "血液肿瘤", "肺癌", "乳腺癌", "Keytruda", "PD-1", "PD-L1", "EGFR", "BTK", "CDK4/6")),
        ("ADC", ("ADC", "抗体偶联药物", "HER2 ADC", "TROP2 ADC", "双抗ADC", "DXd-ADC")),
        ("双抗", ("双抗", "双特异性抗体", "PD-1/VEGF", "CD3×CD20", "TCE双抗")),
        ("自免药", ("自免", "免疫", "Immunology", "IL-4R", "IL-5", "IL-13", "IL-17", "IL-23", "JAK", "SLE")),
        ("罕见病", ("罕见病", "Rare Disease", "血友病", "补体", "C5", "生长激素")),
        ("体外诊断", ("体外诊断", "诊断", "IVD", "中心化诊断", "分子诊断", "POCT", "组织诊断", "病理", "伴随诊断")),
        ("GLP-1", ("GLP-1", "Semaglutide", "Tirzepatide", "司美格鲁肽", "替尔泊肽", "Mounjaro", "Zepbound", "Wegovy", "Ozempic")),
        ("减重药", ("减重", "肥胖", "Obesity", "体重管理", "代谢疾病", "MASH")),
        ("糖尿病", ("糖尿病", "Diabetes", "胰岛素", "Insulin", "SGLT2", "DPP-4")),
        ("无线连接芯片", ("无线连接芯片", "WiFi", "蓝牙", "NFC", "Wireless Connectivity")),
        ("基础设施软件", ("VMware", "虚拟化", "云基础设施", "混合云", "超融合", "vSphere", "vSAN", "NSX")),
        ("车载以太网", ("车载以太网", "车规WiFi", "汽车电子芯片")),
        ("自动驾驶", ("自动驾驶", "DRIVE", "Orin", "Thor", "智驾", "车载计算", "智能驾驶")),
        ("机器人", ("机器人", "Physical AI", "物理AI", "Isaac", "Cosmos", "Omniverse", "GR00T")),
        ("AI PC", ("AI PC", "RTX AI", "GeForce", "端侧AI", "AI工作站")),
    ]
    for label, tokens in rules:
        if any(token.lower() in text.lower() for token in tokens):
            routes.append(label)
    if any(route in routes for route in ["医疗器械", "电生理", "手术机器人", "内镜耗材"]):
        routes = [route for route in routes if route not in {"创新药", "肿瘤药", "ADC", "双抗", "自免药", "罕见病", "GLP-1", "减重药", "糖尿病"}]
    if any(route in routes for route in ["生命科学工具", "科学仪器", "生物制药上游"]):
        routes = [route for route in routes if route not in {"创新药", "肿瘤药", "ADC", "双抗", "自免药", "罕见病", "GLP-1", "减重药", "糖尿病"}]
    if "体外诊断" in routes and not re.search(r"体外诊断|IVD|临床诊断|分子诊断|POCT|免疫诊断", text, flags=re.I):
        routes = [route for route in routes if route != "体外诊断"]
    return unique(routes)


def normalize_from_json(data: dict[str, Any], source_file: Path) -> dict[str, Any]:
    business_lines = []
    for row in data.get("benchmark_business_lines") or []:
        if not isinstance(row, dict):
            continue
        business_lines.append(
            {
                "business_line": clean_text(row.get("business_line")),
                "english_name": clean_text(row.get("english_name")),
                "definition": clean_text(row.get("definition")),
                "key_products": as_list(row.get("key_products")),
                "downstream_applications": as_list(row.get("downstream_applications")),
                "importance": clean_text(row.get("importance")),
                "source_type": clean_text(row.get("source_type")),
            }
        )
    mapped = []
    for row in data.get("mapped_companies") or []:
        if not isinstance(row, dict):
            continue
        mapped.append(
            {
                "company": clean_text(row.get("company")),
                "ticker": clean_text(row.get("ticker")),
                "market": clean_text(row.get("market")),
                "mapped_business_line": clean_text(row.get("mapped_business_line")),
                "mapped_business": clean_text(row.get("mapped_business")),
                "mapping_type": clean_text(row.get("mapping_type")),
                "mapping_strength": clean_text(row.get("mapping_strength")),
                "mapping_score": row.get("mapping_score", 0),
                "core_basis": clean_text(row.get("core_basis")),
                "risk_note": clean_text(row.get("risk_note")),
            }
        )
    gaps = []
    for row in data.get("mapping_gaps") or []:
        if not isinstance(row, dict):
            continue
        gaps.append(
            {
                "business_line": clean_text(row.get("business_line")),
                "gap_reason": clean_text(row.get("gap_reason")),
                "possible_beneficiary_direction": clean_text(row.get("possible_beneficiary_direction")),
            }
        )
    out = {
        "benchmark_company": clean_text(data.get("benchmark_company")),
        "benchmark_ticker": clean_text(data.get("benchmark_ticker")),
        "benchmark_market": clean_text(data.get("benchmark_market")),
        "benchmark_theme": clean_text(data.get("benchmark_theme")),
        "benchmark_business_lines": [row for row in business_lines if row.get("business_line")],
        "mapped_companies": [row for row in mapped if row.get("company")],
        "mapping_gaps": [row for row in gaps if row.get("business_line")],
        "source_file": str(source_file),
        "source_type": "benchmark_map",
        "updated": date.today().isoformat(),
    }
    out["theme_routes"] = unique(as_list(data.get("theme_routes")) + derive_theme_routes(out))
    return out


def normalize_from_json_list(items: list[Any], source_file: Path) -> dict[str, Any]:
    maps = [normalize_from_json(row, source_file) for row in items if isinstance(row, dict)]
    company = " / ".join(unique([clean_text(row.get("benchmark_company")) for row in maps if clean_text(row.get("benchmark_company"))]))
    ticker = " / ".join(unique([clean_text(row.get("benchmark_ticker")) for row in maps if clean_text(row.get("benchmark_ticker"))]))
    market = " / ".join(unique([clean_text(row.get("benchmark_market")) for row in maps if clean_text(row.get("benchmark_market"))]))
    theme = " / ".join(unique([clean_text(row.get("benchmark_theme")) for row in maps if clean_text(row.get("benchmark_theme"))]))
    out = {
        "benchmark_company": company + "（组合对标）" if company else "",
        "benchmark_ticker": ticker,
        "benchmark_market": market,
        "benchmark_theme": theme,
        "benchmark_business_lines": [line for row in maps for line in row.get("benchmark_business_lines", []) if isinstance(line, dict)],
        "mapped_companies": [company for row in maps for company in row.get("mapped_companies", []) if isinstance(company, dict)],
        "mapping_gaps": [gap for row in maps for gap in row.get("mapping_gaps", []) if isinstance(gap, dict)],
        "source_file": str(source_file),
        "source_type": "benchmark_map",
        "updated": date.today().isoformat(),
    }
    out["theme_routes"] = unique([route for row in maps for route in as_list(row.get("theme_routes"))] + derive_theme_routes(out))
    return out


def merge_rows_by_key(primary: list[dict[str, Any]], extra: list[dict[str, Any]], keys: tuple[str, ...]) -> list[dict[str, Any]]:
    rows = []
    seen = set()
    for row in list(primary or []) + list(extra or []):
        if not isinstance(row, dict):
            continue
        key = tuple(clean_text(row.get(field)) for field in keys)
        if key in seen:
            continue
        seen.add(key)
        rows.append(row)
    return rows


def merge_with_table_parse(parsed: dict[str, Any], table_parsed: dict[str, Any]) -> dict[str, Any]:
    out = dict(parsed)
    out["benchmark_business_lines"] = merge_rows_by_key(
        parsed.get("benchmark_business_lines", []),
        table_parsed.get("benchmark_business_lines", []),
        ("business_line",),
    )
    out["mapped_companies"] = merge_rows_by_key(
        parsed.get("mapped_companies", []),
        table_parsed.get("mapped_companies", []),
        ("company", "mapped_business_line", "mapped_business"),
    )
    out["mapping_gaps"] = merge_rows_by_key(
        parsed.get("mapping_gaps", []),
        table_parsed.get("mapping_gaps", []),
        ("business_line", "gap_reason"),
    )
    out["theme_routes"] = unique(as_list(parsed.get("theme_routes")) + as_list(table_parsed.get("theme_routes")) + derive_theme_routes(out))
    return out


def prefer_table_rows(parsed: dict[str, Any], table_parsed: dict[str, Any]) -> dict[str, Any]:
    out = dict(parsed)
    if table_parsed.get("benchmark_business_lines"):
        out["benchmark_business_lines"] = table_parsed.get("benchmark_business_lines", [])
    if table_parsed.get("mapped_companies"):
        out["mapped_companies"] = table_parsed.get("mapped_companies", [])
    if table_parsed.get("mapping_gaps"):
        out["mapping_gaps"] = table_parsed.get("mapping_gaps", [])
    out["theme_routes"] = unique(as_list(parsed.get("theme_routes")) + as_list(table_parsed.get("theme_routes")) + derive_theme_routes(out))
    return out


def normalize_from_tables(text: str, source_file: Path) -> dict[str, Any]:
    tables = parse_markdown_tables(text)
    company_values = table_values(tables, "海外公司") or horizontal_company_headers(tables)
    ticker_values = table_values(tables, "股票代码") or horizontal_table_values(tables, "股票代码")
    market_values = table_values(tables, "上市地") or horizontal_table_values(tables, "上市地")
    company = " / ".join(company_values) + "（组合对标）" if len(company_values) > 1 else (company_values[0] if company_values else "")
    ticker = " / ".join(ticker_values) if ticker_values else ""
    market = " / ".join(market_values) if market_values else ""
    theme_values = table_values(tables, "所属产业") or horizontal_table_values(tables, "所属产业")
    theme = frontmatter_value(text, "题材方向") or " / ".join(theme_values) or first_table_value(tables, "AI / 新技术相关业务") or first_table_value(tables, "核心定位")
    business_lines = []
    mapped = []
    gaps = []
    for table in tables:
        headers = set(table.get("headers") or [])
        section = clean_text(table.get("section"))
        business_field = ""
        if {"海外业务线", "业务定义", "关键产品/技术"}.issubset(headers):
            business_field = "海外业务线"
        elif {"业务线名称", "业务定义", "关键产品/技术"}.issubset(headers):
            business_field = "业务线名称"
        elif {"业务线", "关键产品"}.issubset(headers):
            business_field = "业务线"
        if business_field:
            for row in table.get("rows") or []:
                business_lines.append(
                    {
                        "business_line": clean_text(row.get(business_field)),
                        "english_name": clean_text(row.get("英文名")),
                        "definition": clean_text(row.get("业务定义")),
                        "key_products": as_list(row.get("关键产品/技术") or row.get("关键产品")),
                        "downstream_applications": as_list(row.get("下游应用")),
                        "importance": clean_text(row.get("为什么重要")),
                        "source_type": clean_text(row.get("来源类型") or row.get("来源")),
                    }
                )
        if {"映射公司", "映射业务", "映射类型", "核心依据"}.issubset(headers):
            for row in table.get("rows") or []:
                mapped.append(
                    {
                        "company": clean_text(row.get("映射公司")),
                        "ticker": clean_text(row.get("股票代码") or row.get("代码")),
                        "market": clean_text(row.get("市场")),
                        "mapped_business_line": clean_text(row.get("海外业务线")),
                        "mapped_business": clean_text(row.get("映射业务")),
                        "mapping_type": clean_text(row.get("映射类型")),
                        "mapping_strength": clean_text(row.get("映射强度")),
                        "mapping_score": 0,
                        "core_basis": clean_text(row.get("核心依据")),
                        "risk_note": "",
                    }
                )
        gap_business_field = ""
        for field in ["海外业务线", "业务线", "Medtronic业务线", "Boston Scientific业务线"]:
            if field in headers:
                gap_business_field = field
                break
        if "缺口" in section and gap_business_field and "缺口原因" in headers:
            for row in table.get("rows") or []:
                gaps.append(
                    {
                        "business_line": clean_text(row.get(gap_business_field)),
                        "gap_reason": clean_text(row.get("缺口原因")),
                        "possible_beneficiary_direction": clean_text(row.get("可能受益方向")),
                    }
                )
    out = {
        "benchmark_company": company,
        "benchmark_ticker": ticker,
        "benchmark_market": market,
        "benchmark_theme": theme,
        "benchmark_business_lines": [row for row in business_lines if row.get("business_line")],
        "mapped_companies": [row for row in mapped if row.get("company")],
        "mapping_gaps": [row for row in gaps if row.get("business_line")],
        "source_file": str(source_file),
        "source_type": "benchmark_map",
        "updated": date.today().isoformat(),
    }
    out["theme_routes"] = derive_theme_routes(out)
    return out


def merge_maps(existing: dict[str, Any], new_map: dict[str, Any]) -> dict[str, Any]:
    maps = existing.get("maps") if isinstance(existing.get("maps"), list) else []
    key = (new_map.get("benchmark_company"), new_map.get("benchmark_ticker"))
    out_maps = []
    replaced = False
    for row in maps:
        if not isinstance(row, dict):
            continue
        row_key = (row.get("benchmark_company"), row.get("benchmark_ticker"))
        if row_key == key:
            out_maps.append(new_map)
            replaced = True
        else:
            out_maps.append(row)
    if not replaced:
        out_maps.append(new_map)
    return {"version": 1, "updated": date.today().isoformat(), "maps": out_maps}


def build_map(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    blocks = extract_json_blocks(text)
    table_parsed = normalize_from_tables(text, path)
    if blocks:
        block = blocks[-1]
        if isinstance(block, list):
            return prefer_table_rows(normalize_from_json_list(block, path), table_parsed)
        if isinstance(block, dict) and {"benchmark_company", "benchmark_business_lines"}.intersection(block.keys()):
            return merge_with_table_parse(normalize_from_json(block, path), table_parsed)
        return table_parsed
    return table_parsed


def main() -> int:
    parser = argparse.ArgumentParser(description="Build benchmark_maps.json from overseas benchmark markdown.")
    parser.add_argument("--input", required=True, help="海外龙头对标图谱 Markdown")
    parser.add_argument("--vault", default=str(DEFAULT_VAULT), help="wiki vault path")
    parser.add_argument("--out", help="output JSON path, default: <vault>/relations/benchmark_maps.json")
    parser.add_argument("--no-merge", action="store_true", help="write only the parsed map instead of merging into maps[]")
    args = parser.parse_args()

    src = Path(args.input).expanduser()
    out_path = Path(args.out).expanduser() if args.out else Path(args.vault).expanduser() / "relations/benchmark_maps.json"
    benchmark_map = build_map(src)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if args.no_merge:
        payload = benchmark_map
    else:
        existing = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {"version": 1, "maps": []}
        payload = merge_maps(existing, benchmark_map)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(out_path), "benchmark_company": benchmark_map.get("benchmark_company"), "routes": benchmark_map.get("theme_routes"), "business_lines": len(benchmark_map.get("benchmark_business_lines", [])), "mapped_companies": len(benchmark_map.get("mapped_companies", [])), "mapping_gaps": len(benchmark_map.get("mapping_gaps", []))}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
