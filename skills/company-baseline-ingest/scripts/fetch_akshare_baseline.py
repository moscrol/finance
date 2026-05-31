#!/usr/bin/env python3
"""Fetch AkShare public raw context for entity baseline extraction."""

import argparse
import json
import re
from datetime import date
from pathlib import Path

import akshare as ak


def safe_filename(name):
    return re.sub(r'[/:*?"<>|\n\r\t]+', "_", str(name)).strip() or "未命名公司"


def dataframe_records(df):
    if df is None:
        return []
    try:
        return json.loads(df.to_json(orient="records", force_ascii=False))
    except Exception:
        return []


def call_akshare(tool, **kwargs):
    try:
        func = getattr(ak, tool)
        data = func(**kwargs)
        return {"tool": tool, "params": kwargs, "ok": True, "content": dataframe_records(data)}
    except Exception as exc:
        return {"tool": tool, "params": kwargs, "ok": False, "error": str(exc)}


def first_text(records, keys):
    for row in records or []:
        if not isinstance(row, dict):
            continue
        for key in keys:
            value = row.get(key)
            if value not in (None, ""):
                return str(value).strip()
    return ""


def fetch(company, code):
    symbol = re.sub(r"\D", "", str(code or ""))
    results = [
        call_akshare("stock_individual_info_em", symbol=symbol),
        call_akshare("stock_zyjs_ths", symbol=symbol),
        call_akshare("stock_zygc_em", symbol=symbol),
        call_akshare("stock_profile_cninfo", symbol=symbol),
    ]
    raw = {
        "source_type": "akshare",
        "source_name": "AkShare public baseline raw",
        "company": company,
        "code": symbol,
        "fetched_at": date.today().isoformat(),
        "results": results,
    }

    all_records = []
    for result in results:
        content = result.get("content")
        if isinstance(content, list):
            all_records.extend(content)
    main_business = first_text(all_records, ["主营业务", "经营范围", "公司简介", "业务范围", "主营范围"])
    products = []
    for row in all_records:
        if not isinstance(row, dict):
            continue
        for key in ("主营产品", "产品名称", "业务名称", "分类方向", "项目名称"):
            value = row.get(key)
            if value not in (None, ""):
                text = str(value).strip()
                if text and text not in products:
                    products.append(text)
    industry = {}
    for row in all_records:
        if not isinstance(row, dict):
            continue
        for key in ("行业", "所属行业", "行业类别", "证监会行业", "申万行业"):
            value = row.get(key)
            if value not in (None, ""):
                industry[key] = str(value).strip()
    if main_business:
        raw["main_business"] = main_business
    if products:
        raw["products"] = products[:20]
    if industry:
        raw["industry"] = industry
    return raw


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--company", required=True)
    parser.add_argument("--code", required=True)
    parser.add_argument("--out-dir", default=str(Path.home() / "Desktop/c c/知识库/wiki/raw/akshare-baseline"))
    args = parser.parse_args()

    data = fetch(args.company, args.code)
    out_dir = Path(args.out_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{safe_filename(args.company)}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "raw_file": str(path), "ok_calls": sum(1 for r in data["results"] if r.get("ok"))}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
