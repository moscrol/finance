#!/usr/bin/env python3
"""
concept_delta_writer.py — 概念边际变化入库

Reads structured JSON from stdin and appends dated delta notes to existing
Obsidian concept pages.
"""

import json
import os
import re
import sys
from contextlib import redirect_stderr, redirect_stdout
from datetime import date
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
from knowledge_graph import update_concept_graph  # noqa: E402

VAULT = Path(os.path.expanduser(os.environ.get("CONCEPT_VAULT", "~/Desktop/c c/知识库/wiki")))
CONCEPTS_DIR = VAULT / "concepts"
SOURCES_DIR = VAULT / "sources"
AKSHARE_NAME_CODE_CACHE = None


def today():
    return date.today().isoformat()


def normalize_target(value):
    text = str(value or "").strip()
    while text.startswith("[[") and text.endswith("]]"):
        text = text[2:-2].strip()
    if text.endswith(".md"):
        text = text[:-3]
    return text.strip()


def wikilink(value):
    target = normalize_target(value)
    return f"[[{target}]]" if target else ""


def yaml_list(values):
    return "[" + ", ".join(json.dumps(v, ensure_ascii=False) for v in values) + "]"


def safe_filename(title):
    return re.sub(r'[/:*?"<>|\n\r\t]+', "_", str(title)).strip() or "未命名概念"


def split_frontmatter(text):
    prefix = ""
    rest = text
    if rest.startswith("\n---\n"):
        prefix = "\n"
        rest = rest[1:]
    if not rest.startswith("---\n"):
        return prefix, None, rest
    lines = rest.splitlines()
    for i in range(1, min(len(lines), 200)):
        if lines[i].strip() == "---":
            fm = lines[1:i]
            body = "\n".join(lines[i + 1 :])
            if rest.endswith("\n"):
                body += "\n"
            return prefix, fm, body
    return prefix, None, rest


def parse_simple_frontmatter(lines):
    data = {}
    for line in lines or []:
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if m:
            data[m.group(1)] = m.group(2).strip()
    return data


def parse_list_value(value):
    value = str(value or "").strip()
    if not value or value == "[]":
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(v) for v in parsed]
    except Exception:
        pass
    matches = re.findall(r'"([^"]+)"', value)
    if matches:
        return matches
    links = re.findall(r"\[\[([^\]]+)\]\]", value)
    if links:
        return [wikilink(v) for v in links]
    return [v.strip() for v in value.strip("[]").split(",") if v.strip()]


def upsert_frontmatter_line(lines, key, rendered_value):
    prefix = f"{key}:"
    for i, line in enumerate(lines):
        if line.startswith(prefix):
            lines[i] = f"{key}: {rendered_value}"
            return
    lines.append(f"{key}: {rendered_value}")


def increment_revision(value):
    m = re.search(r"\d+", str(value or ""))
    return str(int(m.group(0)) + 1) if m else "1"


def load_akshare_name_code():
    global AKSHARE_NAME_CODE_CACHE
    if AKSHARE_NAME_CODE_CACHE is not None:
        return AKSHARE_NAME_CODE_CACHE
    try:
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            import akshare as ak
            df = ak.stock_info_a_code_name()
        code_col = "code" if "code" in df.columns else df.columns[0]
        name_col = "name" if "name" in df.columns else df.columns[1]
        AKSHARE_NAME_CODE_CACHE = {
            str(name).strip(): str(code).zfill(6)
            for code, name in zip(df[code_col], df[name_col])
            if str(name).strip() and str(code).strip()
        }
    except Exception:
        AKSHARE_NAME_CODE_CACHE = {}
    return AKSHARE_NAME_CODE_CACHE


def resolve_code(company, code):
    code = re.sub(r"\D", "", str(code or ""))
    if len(code) == 6:
        return code
    return load_akshare_name_code().get(str(company or "").strip(), "")


def escape_table_cell(value):
    text = "—" if value is None or value == "" else str(value)
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("\n", "<br>")


def parse_existing_related_concepts(body):
    m = re.search(r"## 相关概念\s*\n+(.+?)(?:\n## |\Z)", body, re.S)
    if not m:
        return []
    return [normalize_target(x) for x in re.findall(r"\[\[([^\]]+)\]\]", m.group(1))]


def upsert_related_concepts(body, concepts):
    new_concepts = [normalize_target(c) for c in concepts if normalize_target(c)]
    if not new_concepts:
        return body
    existing = parse_existing_related_concepts(body)
    merged = []
    for item in existing + new_concepts:
        if item and item not in merged:
            merged.append(item)
    section = "## 相关概念\n\n" + " · ".join(wikilink(c) for c in merged) + "\n"
    if "## 相关概念" in body:
        return re.sub(r"## 相关概念\s*\n+.*?(?=\n## |\Z)", section, body, flags=re.S)
    return body.rstrip() + "\n\n" + section


def normalize_companies(raw):
    result = []
    seen = set()
    for item in raw or []:
        if isinstance(item, str):
            data = {"name": item, "code": "", "tier": "related", "reason": ""}
        elif isinstance(item, dict):
            data = {
                "name": str(item.get("name", "")).strip(),
                "code": str(item.get("code", "")).strip(),
                "tier": item.get("tier", "related"),
                "reason": str(item.get("reason", "")).strip(),
                "role": str(item.get("role", "")).strip(),
                "chain_layer": str(item.get("chain_layer", "")).strip(),
            }
            # Pass through Theme Radar fields if present
            for field in ["source_quality", "fact_hardness", "evidence_layer", "update_type", "review_required"]:
                if field in item:
                    data[field] = item[field]
        else:
            continue
        if not data["name"] or data["name"] in seen:
            continue
        if data["tier"] not in {"core", "related", "peripheral"}:
            data["tier"] = "related"
        data["code"] = resolve_code(data["name"], data["code"])
        seen.add(data["name"])
        result.append(data)
    return result


def render_key_data(items):
    if not items:
        return []
    lines = ["#### 关键数据", "", "| 指标 | 数值 | 备注 |", "|------|------|------|"]
    for item in items:
        lines.append(
            f"| {escape_table_cell(item.get('indicator', '—'))} | "
            f"{escape_table_cell(item.get('value', '—'))} | "
            f"{escape_table_cell(item.get('note', '—'))} |"
        )
    lines.append("")
    return lines


def render_catalysts(items):
    if not items:
        return []
    lines = ["#### 催化事件", "", "| 时间 | 事件 | 影响 |", "|------|------|------|"]
    for item in items:
        lines.append(
            f"| {escape_table_cell(item.get('time', '—'))} | "
            f"{escape_table_cell(item.get('event', '—'))} | "
            f"{escape_table_cell(item.get('impact', '—'))} |"
        )
    lines.append("")
    return lines


def render_companies(companies):
    if not companies:
        return []
    tier_label = {"core": "核心", "related": "受益", "peripheral": "边缘"}
    lines = ["#### 标的增量", "", "| 公司 | 代码 | 定位 | 逻辑 |", "|------|------|------|------|"]
    for c in companies:
        lines.append(
            f"| {escape_table_cell(c['name'])} | {escape_table_cell(c.get('code', ''))} | "
            f"{tier_label.get(c.get('tier', 'related'), '受益')} | {escape_table_cell(c.get('reason', ''))} |"
        )
    lines.append("")
    return lines


def render_delta(update, source_name, source_date):
    entry_date = update.get("date") or source_date or today()
    title = str(update.get("title") or "概念增量").strip()
    summary = str(update.get("summary") or "").strip()
    key_insights = [str(x).strip() for x in update.get("key_insights", []) if str(x).strip()]
    risks = [str(x).strip() for x in update.get("risks", []) if str(x).strip()]
    related = [normalize_target(c) for c in update.get("related_concepts", []) if normalize_target(c)]
    evidence = str(update.get("evidence") or "").strip()
    companies = normalize_companies(update.get("companies", []))

    lines = [f"### {entry_date}｜{source_name}", "", f"**{title}**", ""]
    if summary:
        lines += [summary, ""]
    if key_insights:
        lines += ["#### 边际变化", ""]
        for item in key_insights:
            lines.append(f"- {item}")
        lines.append("")
    lines += render_key_data(update.get("key_data", []))
    lines += render_catalysts(update.get("catalysts", []))
    lines += render_companies(companies)
    if risks:
        lines += ["#### 风险与反证", ""]
        for item in risks:
            lines.append(f"- {item}")
        lines.append("")
    if related:
        lines.append(f"- 相关概念：{' · '.join(wikilink(c) for c in related)}")
    if evidence:
        lines.append(f"- 原文依据：{evidence}")
    lines.append("")
    return "\n".join(lines), companies


def append_delta_to_body(body, delta_md, related_concepts):
    body = body.rstrip() + "\n"
    if "## 概念增量\n" not in body:
        body += "\n## 概念增量\n\n"
    body += delta_md
    return upsert_related_concepts(body, related_concepts)


def find_concept_path(concept):
    name = normalize_target(concept)
    if not name:
        return None
    direct = CONCEPTS_DIR / f"{safe_filename(name)}.md"
    if direct.exists():
        return direct
    for path in CONCEPTS_DIR.glob("*.md"):
        if path.stem == name:
            return path
    return None


def update_concept_file(path, update, source_name, source_date):
    text = path.read_text(encoding="utf-8")
    prefix, fm_lines, body = split_frontmatter(text)
    if fm_lines is None:
        fm_lines = [f"title: {json.dumps(path.stem, ensure_ascii=False)}", f"created: {today()}", "revision: 0", "sources: []"]
    meta = parse_simple_frontmatter(fm_lines)
    delta_md, companies = render_delta(update, source_name, source_date)

    sources = parse_list_value(meta.get("sources", "[]"))
    source_link = wikilink(source_name)
    if source_link and source_link not in sources:
        sources.append(source_link)
    tickers = parse_list_value(meta.get("tickers", "[]"))
    for c in companies:
        code = c.get("code", "")
        if code and code not in tickers:
            tickers.append(code)
    log = parse_list_value(meta.get("log", "[]"))
    log_item = f"added concept delta from {source_link}"
    if source_link and log_item not in log:
        log.append(log_item)

    upsert_frontmatter_line(fm_lines, "updated", today())
    upsert_frontmatter_line(fm_lines, "revision", increment_revision(meta.get("revision", "0")))
    upsert_frontmatter_line(fm_lines, "sources", yaml_list(sources))
    if tickers:
        upsert_frontmatter_line(fm_lines, "tickers", yaml_list(sorted(set(tickers))))
    if log:
        upsert_frontmatter_line(fm_lines, "log", yaml_list(log))

    related = update.get("related_concepts", [])
    new_body = append_delta_to_body(body, delta_md, related)
    content = prefix + "---\n" + "\n".join(fm_lines) + "\n---\n" + new_body
    path.write_text(content, encoding="utf-8")

    # Propagate Theme Radar fields from update level to companies
    update_source_quality = str(update.get("source_quality", "")).strip()
    update_fact_hardness = str(update.get("fact_hardness", "")).strip()
    update_evidence_layer = str(update.get("evidence_layer", "")).strip()
    update_review_required = bool(update.get("review_required", False))

    for c in companies:
        if not c.get("source_quality") and update_source_quality:
            c["source_quality"] = update_source_quality
        if not c.get("fact_hardness") and update_fact_hardness:
            c["fact_hardness"] = update_fact_hardness
        if not c.get("evidence_layer") and update_evidence_layer:
            c["evidence_layer"] = update_evidence_layer
        if not c.get("review_required") and update_review_required:
            c["review_required"] = update_review_required

    graph_files = update_concept_graph(
        path.stem,
        source_name=source_name,
        source_date=source_date,
        parent_concepts=update.get("parent_concepts", []),
        related_concepts=related,
        relationships=update.get("relationships", {}),
        supply_chain=update.get("supply_chain_layers", {}),
        companies=companies,
        ticker_map={c["name"]: c.get("code", "") for c in companies},
        evidence=update.get("evidence", ""),
        confidence=update.get("confidence", "medium"),
        aliases=update.get("aliases", []),
    )
    return companies, graph_files


def create_source_note(data, updated, skipped):
    source_name = normalize_target(data.get("source_name") or "未命名来源")
    if not source_name:
        return None
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)
    path = SOURCES_DIR / f"{safe_filename(source_name)}.md"
    source_date = data.get("source_date", "")
    source_file = data.get("source_file", "")

    if path.exists():
        text = path.read_text(encoding="utf-8").rstrip()
        additions = ["", "## 已更新概念", ""]
    else:
        lines = ["---", f"title: {json.dumps(source_name, ensure_ascii=False)}", "type: source"]
        if source_date:
            lines.append(f"source_date: {source_date}")
        lines += [f"created: {today()}", "---", "", f"# {source_name}", ""]
        if source_file:
            lines += [f"本地文件：`{source_file}`", ""]
        text = "\n".join(lines).rstrip()
        additions = ["", "## 已更新概念", ""]

    for name in updated:
        additions.append(f"- [[{name}]]")
    if skipped:
        additions += ["", "## 跳过概念增量", ""]
        for item in skipped:
            additions.append(f"- {item.get('concept', '')}：{item.get('reason', '')}")
    path.write_text(text + "\n" + "\n".join(additions) + "\n", encoding="utf-8")
    return str(path)


def write_updates(data):
    CONCEPTS_DIR.mkdir(parents=True, exist_ok=True)
    source_name = normalize_target(data.get("source_name") or "未命名来源")
    source_date = data.get("source_date") or today()
    updated, skipped = [], []
    company_report = {}
    graph_files = {}

    for update in data.get("updates", []):
        concept = normalize_target(update.get("concept", ""))
        if not concept:
            skipped.append({"concept": "", "reason": "missing concept"})
            continue
        path = find_concept_path(concept)
        if path is None:
            skipped.append({"concept": concept, "reason": "concept not found"})
            continue
        companies, files = update_concept_file(path, update, source_name, source_date)
        graph_files.update(files)
        updated.append(path.stem)
        company_report[path.stem] = {
            c["name"]: c.get("code", "")
            for c in companies
        }

    source_file = create_source_note(data, updated, skipped)
    return {
        "status": "ok",
        "updated_concepts": updated,
        "skipped_updates": skipped,
        "company_codes": company_report,
        "watchlist": data.get("watchlist", []),
        "source_file": source_file,
        "graph_files": graph_files,
    }


def main():
    if sys.stdin.isatty():
        print("Usage: python3 concept_delta_writer.py <<'JSON'\n{...}\nJSON", file=sys.stderr)
        sys.exit(1)
    data = json.loads(sys.stdin.read())
    print(json.dumps(write_updates(data), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
