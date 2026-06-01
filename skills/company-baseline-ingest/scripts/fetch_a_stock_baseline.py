#!/usr/bin/env python3
import argparse
import json
import re
import time
from datetime import date
from pathlib import Path

import akshare as ak
import requests
from mootdx.quotes import Quotes

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
DEFAULT_OUT = Path("/Users/lbq/Desktop/c c/知识库/wiki/raw/a-stock-baseline")


def safe_filename(name):
    return re.sub(r'[/\\:*?"<>|\n\r\t]+', "_", str(name)).strip() or "未命名公司"


def request_json(method, session, url, **kwargs):
    last_error = None
    for _ in range(2):
        try:
            response = getattr(session, method)(url, **kwargs)
            return response.json(), ""
        except Exception as exc:
            last_error = exc
            time.sleep(1.2)
    return {}, f"{type(last_error).__name__}: {last_error}"


def eastmoney_stock_info(session, code):
    market_code = 1 if code.startswith("6") else 0
    payload, error = request_json(
        "get",
        session,
        "https://push2.eastmoney.com/api/qt/stock/get",
        params={"fltt": "2", "invt": "2", "fields": "f57,f58,f84,f85,f127,f116,f117,f189,f43", "secid": f"{market_code}.{code}"},
        timeout=15,
    )
    data = payload.get("data") or {}
    return {
        "ok": bool(data),
        "error": error,
        "content": {
            "code": data.get("f57"),
            "name": data.get("f58"),
            "industry": data.get("f127"),
            "total_shares": data.get("f84"),
            "float_shares": data.get("f85"),
            "mcap": data.get("f116"),
            "float_mcap": data.get("f117"),
            "list_date": str(data.get("f189", "")),
            "price": data.get("f43"),
        },
    }


def sina_income_periods(session, code, num=4):
    prefix = "sh" if code.startswith("6") else "sz"
    payload, error = request_json(
        "get",
        session,
        "https://quotes.sina.cn/cn/api/openapi.php/CompanyFinanceService.getFinanceReport2022",
        params={"paperCode": prefix + code, "source": "lrb", "type": "0", "page": "1", "num": str(num)},
        timeout=15,
    )
    report_list = payload.get("result", {}).get("data", {}).get("report_list", {}) or {}
    return {"ok": bool(report_list), "error": error, "periods": sorted(report_list.keys(), reverse=True)[:num]}


def cninfo_announcements(session, code, page_size=5):
    if code.startswith("6"):
        org_id = f"gssh0{code}"
    elif code.startswith(("8", "4")):
        org_id = f"gsbj0{code}"
    else:
        org_id = f"gssz0{code}"
    payload, error = request_json(
        "post",
        session,
        "https://www.cninfo.com.cn/new/hisAnnouncement/query",
        data={"stock": f"{code},{org_id}", "tabName": "fulltext", "pageSize": str(page_size), "pageNum": "1", "column": "", "category": "", "plate": "", "seDate": "", "searchkey": "", "secid": "", "sortName": "", "sortType": "", "isHLtitle": "true"},
        headers={"User-Agent": UA, "Referer": "https://www.cninfo.com.cn/new/disclosure", "Origin": "https://www.cninfo.com.cn"},
        timeout=15,
    )
    rows = []
    for item in payload.get("announcements", []) or []:
        rows.append({"title": item.get("announcementTitle", ""), "type": item.get("announcementTypeName", ""), "announcement_id": item.get("announcementId", "")})
    return {"ok": bool(rows), "error": error, "items": rows[:page_size]}


def f10_texts(code):
    texts = {}
    errors = {}
    try:
        client = Quotes.factory(market="std")
    except Exception as exc:
        return {}, {"factory": f"{type(exc).__name__}: {exc}"}
    for category in ("公司概况", "行业分析", "最新提示"):
        try:
            texts[category] = client.F10(symbol=code, name=category) or ""
        except Exception as exc:
            texts[category] = ""
            errors[category] = f"{type(exc).__name__}: {exc}"
    return texts, errors


def dataframe_records(df):
    if df is None:
        return []
    try:
        return json.loads(df.to_json(orient="records", force_ascii=False))
    except Exception:
        return []


def akshare_fallback(code):
    calls = []
    for tool, kwargs in [
        ("stock_individual_info_em", {"symbol": code}),
        ("stock_zyjs_ths", {"symbol": code}),
        ("stock_zygc_em", {"symbol": code}),
        ("stock_profile_cninfo", {"symbol": code}),
    ]:
        try:
            data = getattr(ak, tool)(**kwargs)
            calls.append({"tool": tool, "ok": True, "content": dataframe_records(data)})
        except Exception as exc:
            calls.append({"tool": tool, "ok": False, "error": f"{type(exc).__name__}: {exc}"})
    return calls


def fetch(company, code, include_akshare=False):
    session = requests.Session()
    session.headers.update({"User-Agent": UA})
    f10, f10_errors = f10_texts(code)
    raw = {
        "source_type": "a-stock",
        "source_name": "a-stock-data + mootdx F10 baseline raw",
        "company": company,
        "code": re.sub(r"\D", "", str(code)),
        "fetched_at": date.today().isoformat(),
        "results": [
            {"tool": "eastmoney_stock_info", "server": "eastmoney", **eastmoney_stock_info(session, code)},
            {"tool": "sina_income_periods", "server": "sina", **sina_income_periods(session, code)},
            {"tool": "cninfo_announcements", "server": "cninfo", **cninfo_announcements(session, code)},
            {"tool": "mootdx_f10", "server": "mootdx", "ok": bool(f10), "error": f10_errors, "content": f10},
        ],
    }
    if include_akshare:
        raw["akshare_fallback"] = akshare_fallback(code)
    return raw


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--company", required=True)
    parser.add_argument("--code", required=True)
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT))
    parser.add_argument("--include-akshare", action="store_true")
    args = parser.parse_args()
    data = fetch(args.company, args.code, include_akshare=args.include_akshare)
    out_dir = Path(args.out_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{safe_filename(args.company)}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ok_calls = sum(1 for item in data.get("results", []) if item.get("ok"))
    print(json.dumps({"status": "ok", "raw_file": str(path), "ok_calls": ok_calls}, ensure_ascii=False))


if __name__ == "__main__":
    main()
