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


def extract_json_blocks(text: str) -> list[dict[str, Any]]:
    blocks = []
    for match in re.finditer(r"```json\s*(\{.*?\})\s*```", text, flags=re.S | re.I):
        raw = match.group(1).strip()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
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
        ("光模块", ("光模块", "光互联", "光通信", "Optical", "DSP", "CPO", "硅光", "Photonic", "AEC", "光引擎")),
        ("CPO", ("CPO", "Co-Packaged", "Photonic Fabric", "硅光")),
        ("光刻机", ("光刻机", "光刻系统", "EUV光刻", "DUV光刻", "ArFi", "High-NA", "TWINSCAN", "SMEE")),
        ("半导体设备", ("半导体设备", "光刻系统", "量测", "检测系统", "曝光系统", "装机基盘", "前道设备")),
        ("先进制程", ("先进制程", "3nm", "2nm", "sub-2nm", "7nm", "High-NA", "EUV")),
        ("晶圆制造", ("晶圆制造", "前道", "曝光", "掩模", "良率", "晶圆")),
        ("量测设备", ("量测", "检测系统", "Metrology", "Inspection", "缺陷检测", "良率控制")),
        ("半导体软件", ("计算光刻", "OPC", "Brion", "制造类EDA", "器件建模EDA", "TCAD")),
        ("AI算力", ("AI算力", "AI基础设施", "AI工厂", "Blackwell", "Hopper", "Vera Rubin", "CUDA", "AI训练", "AI推理", "算力")),
        ("国产GPU", ("国产GPU", "AI GPU", "DCU", "CUDA", "Blackwell", "Hopper", "图形GPU", "GeForce", "RTX")),
        ("AI芯片", ("AI芯片", "AI GPU", "DCU", "加速芯片", "定制AI加速芯片", "昇腾", "思元")),
        ("AI ASIC", ("AI ASIC", "Custom Silicon", "XPU", "定制AI", "定制ASIC", "云厂商定制")),
        ("交换芯片", ("交换芯片", "Ethernet Switch", "Teralynx", "Prestera", "UALink", "ESUN")),
        ("存储芯片", ("SSD控制器", "NAND Flash", "3D NAND", "HBM封装", "DRAM封测", "内存接口芯片", "存储器件")),
        ("存储互连", ("服务器存储连接", "FC SAN", "SAS", "RAID", "PCIe Switch", "PCIe Retimer", "NVMe-oF", "CXL互连")),
        ("AI服务器", ("AI服务器", "数据中心", "AI集群", "Scale-Up", "Scale-Out")),
        ("先进封装", ("Chiplet", "HBM", "先进封装", "die-to-die", "CPO")),
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


def normalize_from_tables(text: str, source_file: Path) -> dict[str, Any]:
    tables = parse_markdown_tables(text)
    company = first_table_value(tables, "海外公司")
    ticker = first_table_value(tables, "股票代码")
    market = first_table_value(tables, "上市地")
    theme = first_table_value(tables, "AI / 新技术相关业务") or first_table_value(tables, "核心定位")
    business_lines = []
    mapped = []
    gaps = []
    for table in tables:
        headers = set(table.get("headers") or [])
        section = clean_text(table.get("section"))
        if {"海外业务线", "业务定义", "关键产品/技术"}.issubset(headers):
            for row in table.get("rows") or []:
                business_lines.append(
                    {
                        "business_line": clean_text(row.get("海外业务线")),
                        "english_name": clean_text(row.get("英文名")),
                        "definition": clean_text(row.get("业务定义")),
                        "key_products": as_list(row.get("关键产品/技术")),
                        "downstream_applications": as_list(row.get("下游应用")),
                        "importance": clean_text(row.get("为什么重要")),
                        "source_type": clean_text(row.get("来源类型")),
                    }
                )
        if {"映射公司", "映射业务", "映射类型", "核心依据"}.issubset(headers):
            for row in table.get("rows") or []:
                mapped.append(
                    {
                        "company": clean_text(row.get("映射公司")),
                        "ticker": clean_text(row.get("股票代码")),
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
        if "国内缺口" in section and {"海外业务线", "缺口原因", "可能受益方向"}.issubset(headers):
            for row in table.get("rows") or []:
                gaps.append(
                    {
                        "business_line": clean_text(row.get("海外业务线")),
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
    if blocks:
        return normalize_from_json(blocks[-1], path)
    return normalize_from_tables(text, path)


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
