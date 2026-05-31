"""从 fupanhui.com 批量抓取研报，转为 Obsidian Markdown 存入知识库。"""

import json
import os
import re
import subprocess
import sys
import time

PROXY = os.environ.get("CDP_PROXY_URL", "http://localhost:3456")
WIKI_SOURCES = os.path.expanduser("~/Desktop/c c/知识库/wiki/sources")


def cdp_get(path, params=None):
    cmd = ["curl", "-s", "-G", f"{PROXY}{path}"]
    if params:
        for k, v in params:
            cmd += ["--data-urlencode", f"{k}={v}"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return json.loads(r.stdout) if r.stdout.strip() else {}


def cdp_eval(target, expr):
    cmd = ["curl", "-s", "-X", "POST", f"{PROXY}/eval?target={target}",
           "-d", f"expr={expr}"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return json.loads(r.stdout) if r.stdout.strip() else {}


def fetch_api(target, api_path):
    js = ("(function(){var x=new XMLHttpRequest();"
          "x.open('GET','" + api_path + "',false);"
          "x.send();return x.responseText;})()")
    r = cdp_eval(target, js)
    try:
        return json.loads(r.get("value", "{}"))
    except (json.JSONDecodeError, TypeError):
        return {}


def fetch_all_reports(target):
    """Fetch all reports via paginated API."""
    all_reports = []
    page = 1
    while True:
        data = fetch_api(target,
            f"/api/v1/client/reports/list?page={page}&page_size=50&report_type=industry")
        items = data.get("data", {}).get("items", [])
        total = data.get("data", {}).get("total", 0)
        if not items:
            break
        all_reports.extend(items)
        print(f"  fetched page {page}: {len(items)} reports (total: {len(all_reports)}/{total})")
        if len(all_reports) >= total:
            break
        page += 1
    return all_reports


def slugify(title):
    """Create a filename-safe slug from title."""
    s = re.sub(r'[\\/:*?"<>|]', '', title)
    s = s.strip()
    if len(s) > 80:
        s = s[:80]
    return s


def report_to_md(report):
    """Convert a report dict to Obsidian Markdown string."""
    title = report.get("title", "Untitled")
    report_date = report.get("report_date", "")
    industry_tags = report.get("industry_tags", [])
    chain_tags = report.get("chain_tags", [])
    concept_tags = report.get("concept_tags", [])
    stocks = report.get("stocks", [])
    stock_count = report.get("stock_count", len(stocks))

    # Build tags
    tags = ["复盘会", "产业分析"] + industry_tags[:5]
    tags_str = json.dumps(tags, ensure_ascii=False)

    # Frontmatter
    lines = [
        "---",
        f"title: {title}",
        f"tags: {tags_str}",
        f"created: {report_date}",
        f"updated: {time.strftime('%Y-%m-%d')}",
        "revision: 1",
        'sources: [fupanhui.com]',
        'log: ["ingested from fupanhui.com"]',
        "---",
        "",
        f"# {title}",
        "",
        f"> 来源：复盘会·研报库 | {report_date} | {stock_count}只个股",
        "",
    ]

    # Industry chain
    if chain_tags:
        lines.append("## 产业链")
        lines.append("")
        lines.append("、".join(chain_tags))
        lines.append("")

    # Stocks table
    if stocks:
        lines.append("## 核心个股")
        lines.append("")
        lines.append("| 股票 | 代码 | 核心逻辑 |")
        lines.append("|------|------|----------|")
        for s in stocks:
            name = s.get("stock_name", "")
            code = s.get("stock_code", "")
            logic = s.get("core_logic", "").replace("|", "｜").replace("\n", " ")
            lines.append(f"| {name} | {code} | {logic} |")
        lines.append("")

    # Related concepts
    if concept_tags:
        links = [f"[[{c}]]" for c in concept_tags[:15]]
        lines.append("## 关联概念")
        lines.append("")
        lines.append(" · ".join(links))
        lines.append("")

    return "\n".join(lines)


def main():
    skip_existing = "--force" not in sys.argv

    resp = cdp_get("/new", [("url", "https://fupanhui.com")])
    target = resp.get("targetId")
    if not target:
        print("无法连接 CDP 代理")
        return

    try:
        time.sleep(2)
        print("Fetching reports from fupanhui API...")
        reports = fetch_all_reports(target)
        print(f"Total: {len(reports)} reports")

        os.makedirs(WIKI_SOURCES, exist_ok=True)

        created = 0
        skipped = 0
        for report in reports:
            title = report.get("title", "Untitled")
            filename = slugify(title) + ".md"
            filepath = os.path.join(WIKI_SOURCES, filename)

            if skip_existing and os.path.exists(filepath):
                skipped += 1
                continue

            md = report_to_md(report)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(md)
            created += 1

        print(f"\nDone: {created} created, {skipped} skipped (already exist)")
        print(f"Location: {WIKI_SOURCES}")

    finally:
        cdp_get("/close", [("target", target)])


if __name__ == "__main__":
    main()
