#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path

A_SHARE_RE = re.compile(r"^(00|30|60|68|83|87|43)\d{4}$")
FOREIGN_SUFFIX_RE = re.compile(r"\b\d{4,6}\.(KS|KQ|HK|US|O|N|L|T)\b", re.I)
DEFAULT_WIKI = Path("/Users/lbq/Desktop/c c/知识库/wiki")
NON_CONCEPT_TAGS = {"A股", "上市公司", "公司", "企业", "港股", "美股", "北交所"}


def read_text(path):
    return path.read_text(encoding="utf-8", errors="ignore")


def parse_frontmatter(text):
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}
    data = {}
    for line in text[4:end].splitlines():
        match = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if match:
            data[match.group(1)] = match.group(2).strip()
    return data


def parse_list(value):
    value = str(value or "").strip()
    if not value or value == "[]":
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    except Exception:
        pass
    quoted = re.findall(r'"([^"]+)"', value)
    if quoted:
        return [item.strip() for item in quoted if item.strip()]
    return [item.strip().strip("'").strip('"') for item in value.strip("[]").split(",") if item.strip()]


def clean_concepts(tags, company, code):
    concepts = []
    for tag in tags:
        tag = str(tag or "").strip()
        if not tag or tag in NON_CONCEPT_TAGS or tag == company or code in tag:
            continue
        if re.fullmatch(r"\d{6}", tag) or len(tag) == 1:
            continue
        if tag not in concepts:
            concepts.append(tag)
    return concepts[:12]


def find_ticker(meta, text):
    if FOREIGN_SUFFIX_RE.search(text[:1600]):
        return ""
    for ticker in parse_list(meta.get("tickers", "[]")):
        if re.search(r"\.(KS|KQ|HK|US|O|N|L|T)\b", ticker, re.I):
            continue
        code = re.sub(r"\D", "", ticker)
        if A_SHARE_RE.fullmatch(code):
            return code
    match = re.search(r"\b(?:00|30|60|68|83|87|43)\d{4}\b", text[:1600])
    return match.group(0) if match else ""


def has_usable_baseline(text, meta):
    raw_sources = " ".join(parse_list(meta.get("raw_sources", "[]")))
    if "baseline" in raw_sources and "## 基础画像" in text:
        section = text.split("## 基础画像", 1)[1].split("\n## ", 1)[0]
        if "主营业务" in section and "待补充" not in section[:800]:
            return True
    return False


def scan(wiki_dir, include_existing=False):
    rows = []
    entities_dir = wiki_dir / "entities"
    for order, path in enumerate(sorted(entities_dir.glob("*.md")), 1):
        text = read_text(path)
        meta = parse_frontmatter(text)
        company = path.stem
        code = find_ticker(meta, text)
        if not code:
            continue
        if has_usable_baseline(text, meta) and not include_existing:
            continue
        tags = parse_list(meta.get("tags", "[]"))
        rows.append({
            "company": company,
            "code": code,
            "entity_file": str(path.relative_to(wiki_dir)),
            "status": "pending",
            "reason": "missing_or_incomplete_baseline",
            "order": order,
            "concepts": clean_concepts(tags, company, code),
        })
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wiki-dir", default=str(DEFAULT_WIKI))
    parser.add_argument("--out", default="")
    parser.add_argument("--include-existing", action="store_true")
    args = parser.parse_args()
    wiki_dir = Path(args.wiki_dir).expanduser()
    out = Path(args.out).expanduser() if args.out else wiki_dir / "raw/baseline-queue/entity-baseline-queue.jsonl"
    rows = scan(wiki_dir, include_existing=args.include_existing)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    print(json.dumps({"status": "ok", "queue": str(out), "pending": len(rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
