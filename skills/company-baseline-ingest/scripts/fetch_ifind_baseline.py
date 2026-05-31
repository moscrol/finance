#!/usr/bin/env python3
"""Fetch iFinD raw context for entity baseline extraction."""

import argparse
import json
import os
import re
import sys
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
IFIND_DIR = ROOT / "ifind"
sys.path.insert(0, str(IFIND_DIR))

os.chdir(IFIND_DIR)
from call import call  # noqa: E402


def unwrap_ifind_text(result):
    try:
        content = result["data"]["result"]["content"][0]["text"]
    except Exception:
        try:
            content = result["data"]["result"]["content"][0]["text"]
        except Exception:
            return result
    try:
        parsed = json.loads(content)
    except Exception:
        return content
    data = parsed.get("data", {})
    return data.get("text") or data.get("answer") or data.get("data") or parsed


def safe_filename(name):
    return re.sub(r'[/:*?"<>|\n\r\t]+', "_", str(name)).strip() or "未命名公司"


def fetch(company, code="", notice_start="2025-01-01", news_start="2025-01-01", end=None, include_notices=False):
    end = end or date.today().isoformat()
    entity = f"{company}（{code}）" if code else company
    queries = [
        ("stock", "get_stock_info", {"query": f"{entity} 股票代码、所属申万行业、同花顺行业、证监会行业、主营业务简介"}),
        ("stock", "get_stock_summary", {"query": f"{entity} 主营业务、主营产品名称、主营产品类型、行业分类、业务构成"}),
    ]
    if include_notices:
        queries.extend([
            ("news", "search_notice", {
                "query": f"{entity} 年度报告 公司报告期从事主要业务 主营产品 收入构成",
                "time_start": notice_start,
                "time_end": end,
                "size": 3,
            }),
            ("news", "search_news", {
                "query": f"{entity} 近期业务进展 核心产品 客户 产能 项目",
                "time_start": news_start,
                "time_end": end,
                "size": 3,
            }),
        ])
    results = []
    for server, tool, params in queries:
        try:
            raw = call(server, tool, params)
            results.append({
                "server": server,
                "tool": tool,
                "params": params,
                "ok": bool(raw.get("ok")),
                "content": unwrap_ifind_text(raw),
            })
        except Exception as exc:
            results.append({
                "server": server,
                "tool": tool,
                "params": params,
                "ok": False,
                "error": str(exc),
            })
    return {
        "company": company,
        "code": code,
        "fetched_at": date.today().isoformat(),
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--company", required=True)
    parser.add_argument("--code", default="")
    parser.add_argument("--out-dir", default=str(Path.home() / "Desktop/c c/知识库/wiki/raw/ifind-baseline"))
    parser.add_argument("--notice-start", default="2025-01-01")
    parser.add_argument("--news-start", default="2025-01-01")
    parser.add_argument("--end", default=date.today().isoformat())
    parser.add_argument("--include-notices", action="store_true", help="Optional: also fetch notice/news snippets. Disabled by default.")
    args = parser.parse_args()

    data = fetch(args.company, args.code, args.notice_start, args.news_start, args.end, include_notices=args.include_notices)
    out_dir = Path(args.out_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{safe_filename(args.company)}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "raw_file": str(path), "ok_calls": sum(1 for r in data["results"] if r.get("ok"))}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
