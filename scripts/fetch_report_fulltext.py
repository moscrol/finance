"""从 fupanhui.com 逐篇抓取研报全文，存入知识库 raw/ 目录。

用法：
    python fetch_report_fulltext.py          # 下载所有缺失的研报
    python fetch_report_fulltext.py --force  # 强制覆盖已有文件
    python fetch_report_fulltext.py --dry-run # 只打印待下载列表
"""

import json
import os
import re
import subprocess
import sys
import time

PROXY = os.environ.get("CDP_PROXY_URL", "http://localhost:3456")
RAW_DIR = os.path.expanduser("~/Desktop/c c/知识库/raw")
REPORT_IDS_PATH = os.path.join(os.path.dirname(__file__), "report_ids.json")
DETAIL_URL_TEMPLATE = "https://fupanhui.com/workspace/research/{}"


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


def slugify(title):
    s = re.sub(r'[\\/:*?"<>|]', '', title)
    s = s.strip()
    if len(s) > 80:
        s = s[:80]
    return s


def is_section_heading(line):
    line = line.strip()
    return bool(
        re.match(r"^\d+(\.\d+)*[、. ]+\S+", line)
        or re.match(r"^[一二三四五六七八九十]+[、.]\S+", line)
    )


def markdown_heading(line):
    line = line.strip()
    if not line or line.startswith("#"):
        return line
    m = re.match(r"^(\d+(?:\.\d+)*)[、. ]+(.+)$", line)
    if m:
        depth = min(m.group(1).count(".") + 2, 6)
        return f"{'#' * depth} {m.group(1)} {m.group(2).strip()}"
    if re.match(r"^[一二三四五六七八九十]+[、.]\S+", line):
        return f"## {line}"
    return line


def strip_detail_page_chrome(text, title):
    """Remove fupanhui detail-page chrome while keeping the report body.

    Newer report pages expose the full article as plain innerText, with UI rows
    such as "返回研报库", tags, "小表格", and "复制图片" before the body. The body
    usually starts after a repeated report title followed by numbered sections.
    """
    lines = [line.strip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    lines = [line for line in lines if line]

    title_positions = [i for i, line in enumerate(lines) if line == title]
    for pos in reversed(title_positions):
        window = lines[pos + 1 : pos + 25]
        if any(is_section_heading(line) for line in window):
            return "\n".join(lines[pos + 1 :]).strip()

    for marker in ("复制图片", "共 9 只", "共 8 只", "共 7 只", "共 6 只", "共 5 只"):
        if marker in lines:
            pos = lines.index(marker)
            if pos + 1 < len(lines) and lines[pos + 1] == title:
                return "\n".join(lines[pos + 2 :]).strip()

    if "返回研报库" in lines:
        pos = lines.index("返回研报库")
        return "\n".join(lines[pos + 1 :]).strip()
    return "\n".join(lines).strip()


def normalize_fulltext(text, title):
    body = strip_detail_page_chrome(text or "", title)
    normalized = []
    previous_blank = False
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            if not previous_blank:
                normalized.append("")
            previous_blank = True
            continue
        previous_blank = False
        normalized.append(markdown_heading(line))
    return "\n".join(normalized).strip() + "\n"


def get_fulltext(target, report_id):
    """Navigate to report detail page and extract full text."""
    url = DETAIL_URL_TEMPLATE.format(report_id)

    # Navigate to the report detail page
    cdp_get("/navigate", [("target", target), ("url", url)])
    time.sleep(3)

    # Get page text length first to check if content loaded
    js_len = '(function(){return document.body.innerText.length;})()'
    r = cdp_eval(target, js_len)
    text_len = int(r.get("value", "0"))

    if text_len < 1000:
        # Content might not have loaded yet, wait more
        time.sleep(3)
        r = cdp_eval(target, js_len)
        text_len = int(r.get("value", "0"))

    if text_len < 1000:
        return None, text_len

    # Extract text starting after the nav section
    # The detail page has "返回研报库" as a marker before the report content
    js_extract = '''(function(){
        var text = document.body.innerText;
        var marker = "返回研报库";
        var idx = text.indexOf(marker);
        if (idx !== -1) {
            return text.substring(idx);
        }
        // Fallback: return everything after the header
        return text;
    })()'''
    r = cdp_eval(target, js_extract)
    return r.get("value"), text_len


def main():
    force = "--force" in sys.argv
    dry_run = "--dry-run" in sys.argv

    # Load report IDs
    if not os.path.exists(REPORT_IDS_PATH):
        print(f"Report IDs file not found: {REPORT_IDS_PATH}")
        print("Run fetch_reports.py first to generate it.")
        return

    with open(REPORT_IDS_PATH, "r", encoding="utf-8") as f:
        reports = json.load(f)

    print(f"Loaded {len(reports)} report IDs")

    # Check which raw files already exist
    os.makedirs(RAW_DIR, exist_ok=True)
    existing_files = set(os.listdir(RAW_DIR))

    to_download = []
    for report in reports:
        rid = report["id"]
        title = report["title"]
        report_date = report.get("report_date", "")
        filename = f"{slugify(title)}-full.md"

        if not force and filename in existing_files:
            continue
        to_download.append({
            "id": rid,
            "title": title,
            "report_date": report_date,
            "filename": filename,
        })

    print(f"To download: {len(to_download)} reports ({len(reports) - len(to_download)} already exist)")

    if dry_run:
        for i, r in enumerate(to_download[:10]):
            print(f"  {i+1}. [{r['id']}] {r['title'][:50]}")
        if len(to_download) > 10:
            print(f"  ... and {len(to_download) - 10} more")
        return

    if not to_download:
        print("Nothing to download. Use --force to re-download.")
        return

    # Open a persistent tab
    resp = cdp_get("/new", [("url", DETAIL_URL_TEMPLATE.format(to_download[0]["id"]))])
    target = resp.get("targetId")
    if not target:
        print("Cannot open browser tab")
        return

    try:
        success = 0
        failed = 0
        for i, report in enumerate(to_download):
            rid = report["id"]
            title = report["title"]
            filename = report["filename"]

            text, text_len = get_fulltext(target, rid)

            if text and len(text) > 500:
                filepath = os.path.join(RAW_DIR, filename)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(f"# {title}\n\n")
                    f.write(f"> 来源：复盘会·研报库 | ID: {rid}\n\n")
                    f.write(normalize_fulltext(text, title))
                success += 1
                print(f"  [{i+1}/{len(to_download)}] ✓ {title[:40]} ({text_len} chars)")
            else:
                failed += 1
                print(f"  [{i+1}/{len(to_download)}] ✗ {title[:40]} (too short: {text_len})")

            # Small delay to avoid overwhelming the server
            time.sleep(0.5)

        print(f"\nDone: {success} saved, {failed} failed")
        print(f"Location: {RAW_DIR}")
    finally:
        cdp_get("/close", [("target", target)])


if __name__ == "__main__":
    main()
