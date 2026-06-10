#!/usr/bin/env python3
import json
import sys
import time
from pathlib import Path

import requests
from mootdx.quotes import Quotes

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def request_json(method, session, url, **kwargs):
    last_error = None
    for _ in range(2):
        try:
            response = getattr(session, method)(url, **kwargs)
            return response.json()
        except Exception as exc:
            last_error = exc
            time.sleep(1.2)
    return {"_error": f"{type(last_error).__name__}: {last_error}"}


def eastmoney_stock_info(session, code):
    market_code = 1 if code.startswith("6") else 0
    payload = request_json(
        "get",
        session,
        "https://push2.eastmoney.com/api/qt/stock/get",
        params={
            "fltt": "2",
            "invt": "2",
            "fields": "f57,f58,f84,f85,f127,f116,f117,f189,f43",
            "secid": f"{market_code}.{code}",
        },
        timeout=15,
    )
    data = payload.get("data") or {}
    return {
        "code": data.get("f57"),
        "name": data.get("f58"),
        "industry": data.get("f127"),
        "total_shares": data.get("f84"),
        "float_shares": data.get("f85"),
        "mcap": data.get("f116"),
        "float_mcap": data.get("f117"),
        "list_date": str(data.get("f189", "")),
        "price": data.get("f43"),
    }


def sina_income_periods(session, code, num=2):
    prefix = "sh" if code.startswith("6") else "sz"
    payload = request_json(
        "get",
        session,
        "https://quotes.sina.cn/cn/api/openapi.php/CompanyFinanceService.getFinanceReport2022",
        params={"paperCode": prefix + code, "source": "lrb", "type": "0", "page": "1", "num": str(num)},
        timeout=15,
    )
    report_list = payload.get("result", {}).get("data", {}).get("report_list", {}) or {}
    return sorted(report_list.keys(), reverse=True)[:num]


def cninfo_recent_titles(session, code, page_size=5):
    if code.startswith("6"):
        org_id = f"gssh0{code}"
    elif code.startswith(("8", "4")):
        org_id = f"gsbj0{code}"
    else:
        org_id = f"gssz0{code}"
    payload = request_json(
        "post",
        session,
        "https://www.cninfo.com.cn/new/hisAnnouncement/query",
        data={
            "stock": f"{code},{org_id}",
            "tabName": "fulltext",
            "pageSize": str(page_size),
            "pageNum": "1",
            "column": "",
            "category": "",
            "plate": "",
            "seDate": "",
            "searchkey": "",
            "secid": "",
            "sortName": "",
            "sortType": "",
            "isHLtitle": "true",
        },
        headers={"User-Agent": UA, "Referer": "https://www.cninfo.com.cn/new/disclosure", "Origin": "https://www.cninfo.com.cn"},
        timeout=15,
    )
    return [item.get("announcementTitle", "") for item in (payload.get("announcements") or [])[:page_size]]


def f10_texts(code):
    client = Quotes.factory(market="std")
    texts = {}
    for category in ("公司概况", "行业分析", "最新提示"):
        try:
            texts[category] = client.F10(symbol=code, name=category) or ""
        except Exception as exc:
            texts[category] = f"ERROR: {type(exc).__name__}: {exc}"
    return texts


def first_snippet(texts, keyword, before=80, after=260):
    for text in texts.values():
        index = text.find(keyword)
        if index >= 0:
            return text[max(0, index - before) : index + after].replace("\n", " ").strip()
    return ""


def f10_company_name(texts, code):
    text = texts.get("公司概况", "")
    marker = f"◇{code} "
    index = text.find(marker)
    if index >= 0:
        rest = text[index + len(marker) :]
        return rest.split()[0].strip()
    return ""


def f10_industry(texts):
    text = texts.get("行业分析", "")
    marker = "【所属行业】"
    index = text.find(marker)
    if index >= 0:
        value = text[index + len(marker) : index + len(marker) + 80].strip()
        value = value.split("共(", 1)[0].strip()
        if value:
            return value
    return ""


def main():
    code = sys.argv[1] if len(sys.argv) > 1 else "600879"
    session = requests.Session()
    session.headers.update({"User-Agent": UA})
    result = {"code": code, "source": "a-stock-data smoke"}
    result["stock_info"] = eastmoney_stock_info(session, code)
    time.sleep(1.2)
    result["sina_lrb_periods"] = sina_income_periods(session, code)
    time.sleep(1.2)
    result["cninfo_titles"] = cninfo_recent_titles(session, code)
    result["f10"] = f10_texts(code)
    company = result["stock_info"].get("name") or f10_company_name(result["f10"], code)
    industry = result["stock_info"].get("industry") or f10_industry(result["f10"])
    result["baseline_candidate"] = {
        "company": company,
        "code": code,
        "industry": industry,
        "main_business_snippet": first_snippet(result["f10"], "主营业务"),
        "business_scope_snippet": first_snippet(result["f10"], "经营范围"),
        "evidence_layer": "L2",
        "source_quality": "market_data_vendor_f10",
    }
    out = Path(f"/tmp/a-stock-baseline-{code}.json")
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"file": str(out), "name": company, "industry": industry, "has_f10_business": bool(result["baseline_candidate"]["main_business_snippet"]), "lrb_periods": result["sina_lrb_periods"], "ann_count": len(result["cninfo_titles"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
