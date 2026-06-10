#!/usr/bin/env python3
"""Write static entity baseline sections and relation JSON."""

import argparse
import json
import os
import re
import sys
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))

from knowledge_graph import update_entity_exposures  # noqa: E402


VAULT = Path(os.path.expanduser(os.environ.get("ENTITY_VAULT", os.environ.get("CONCEPT_VAULT", "~/Desktop/c c/知识库/wiki"))))
ENTITIES_DIR = VAULT / "entities"
VALID_STRENGTHS = {"core", "related", "peripheral"}
VALID_CONFIDENCE = {"high", "medium", "low"}
FORBIDDEN_PHRASES = {
    "主要从事行业相关核心产品的研发、制造与技术支持",
    "核心产品/服务",
    "国内各行业大型集团客户",
    "主流终端合作方",
    "公司是行业主流的",
    "automatic batch",
}
RAW_SOURCE_RE = re.compile(r"^raw/(ifind|akshare|a-stock|cninfo|eastmoney|manual-verified)-baseline/[^/]+\.json$")
SOURCE_LABELS = {
    "ifind": "iFinD 基础资料 / 公司摘要",
    "akshare": "AkShare 公开资料 / 主营构成",
    "a-stock": "a-stock-data / mootdx F10 / AkShare fallback",
    "cninfo": "巨潮资讯 / 定期报告",
    "eastmoney": "东方财富公开资料 / 公司资料",
    "manual-verified": "人工核验公开资料",
}
INVALID_RAW_CONTENT_PHRASES = (
    "用户使用工具已超限",
    "工具已超限",
    "调用已超限",
    "rate limit",
    "quota",
)


def today():
    return date.today().isoformat()


def safe_filename(title):
    return re.sub(r'[/:*?"<>|\n\r\t]+', "_", str(title)).strip() or "未命名实体"


def strip_code_suffix(name):
    return re.sub(r"（\d{6}）$", "", str(name or "")).strip()


def market_from_code(code):
    code = str(code or "")
    if re.match(r"^(0|3|6)\d{5}$", code):
        return "A股"
    if re.match(r"^(8|9)\d{5}$", code):
        return "北交所"
    return "未知"


def wikilink(value):
    text = str(value or "").strip()
    while text.startswith("[[") and text.endswith("]]"):
        text = text[2:-2].strip()
    if text.endswith(".md"):
        text = text[:-3]
    return f"[[{text}]]" if text else ""


def yaml_list(values):
    clean = []
    for value in values or []:
        value = str(value).strip()
        if value and value not in clean:
            clean.append(value)
    return "[" + ", ".join(json.dumps(v, ensure_ascii=False) for v in clean) + "]"


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


def find_entity_path(company, code=""):
    direct = ENTITIES_DIR / f"{safe_filename(company)}.md"
    if direct.exists():
        return direct
    for path in ENTITIES_DIR.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        if f"title: {company}" in text or f"title: \"{company}" in text:
            return path
        if code and re.search(rf"\b{re.escape(code)}\b", text[:1200]):
            return path
    return direct


def escape_cell(value):
    text = "待补充" if value in (None, "", []) else str(value)
    return text.replace("|", "\\|").replace("\n", "<br>")


def render_links(values):
    links = [wikilink(v) for v in values or [] if wikilink(v)]
    return " · ".join(links) if links else "待补充"


def section_re(title):
    return rf"## {re.escape(title)}\s*\n+.*?(?=\n## |\Z)"


def upsert_section(body, title, content):
    section = f"## {title}\n\n{content.rstrip()}\n"
    if re.search(section_re(title), body, flags=re.S):
        return re.sub(section_re(title), section, body, flags=re.S)
    insert_before = re.search(r"\n## 边际变化\n", body)
    if insert_before:
        idx = insert_before.start()
        return body[:idx].rstrip() + "\n\n" + section + body[idx:]
    return body.rstrip() + "\n\n" + section


def merge_section_lines(body, title, content):
    rendered = [line for line in content.rstrip().splitlines() if line.strip()]
    match = re.search(section_re(title), body, flags=re.S)
    if not match:
        return upsert_section(body, title, content)
    existing = match.group(0).rstrip()
    existing_lines = set(existing.splitlines())
    additions = [line for line in rendered if line not in existing_lines]
    if not additions:
        return body
    merged = existing + "\n" + "\n".join(additions) + "\n"
    return body[: match.start()] + merged + body[match.end() :]


def has_section(body, title):
    return bool(re.search(section_re(title), body, flags=re.S))


def render_baseline(update):
    industry = update.get("industry", {}) or {}
    products = update.get("products", []) or []
    concepts = update.get("concepts", []) or []
    source_label = baseline_source_label(update)
    lines = [
        "| 维度 | 内容 |",
        "|---|---|",
        f"| 所属行业 | {escape_cell('；'.join(f'{k}：{v}' for k, v in industry.items() if v))} |",
        f"| 主营业务 | {escape_cell(update.get('main_business', ''))} |",
        f"| 主营产品/能力 | {escape_cell('、'.join(map(str, products)))} |",
        f"| 相关概念 | {render_links(concepts)} |",
        f"| 主要客户/生态 | {escape_cell('、'.join(map(str, update.get('customers_ecosystem', []) or [])))} |",
        f"| 主要竞争对手 | {escape_cell('、'.join(map(str, update.get('competitors', []) or [])))} |",
        f"| baseline来源 | {escape_cell(source_label)} |",
    ]
    return "\n".join(lines)


def render_exposures(update):
    rows = ["| 概念 | 角色 | 产业链层级 | 强度 | 置信度 | 证据层 | 更新类型 | 依据 |", "|---|---|---|---|---|---|---|---|"]
    for item in update.get("exposures", []) or []:
        rows.append(
            f"| {wikilink(item.get('concept', '')) or escape_cell(item.get('concept', ''))} | "
            f"{escape_cell(item.get('role', ''))} | "
            f"{escape_cell(item.get('chain_layer', ''))} | "
            f"{escape_cell(item.get('strength', 'related'))} | "
            f"{escape_cell(item.get('confidence', 'medium'))} | "
            f"{escape_cell(item.get('evidence_layer', 'L2'))} | "
            f"{escape_cell(item.get('update_type', 'baseline'))} | "
            f"{escape_cell(item.get('evidence', ''))} |"
        )
    if len(rows) == 2:
        rows.append("| 待补充 | 待补充 | 待补充 | related | low | L2 | baseline | baseline未抽取到明确产业链暴露 |")
    return "\n".join(rows)


def render_key_data(update):
    source_label = baseline_source_label(update)
    rows = ["| 指标 | 数值 | 时间/口径 | 来源 |", "|---|---:|---|---|"]
    for item in update.get("key_data", []) or []:
        rows.append(
            f"| {escape_cell(item.get('indicator', ''))} | "
            f"{escape_cell(item.get('value', ''))} | "
            f"{escape_cell(item.get('period', ''))} | "
            f"{escape_cell(item.get('source', 'iFinD'))} |"
        )
    if len(rows) == 2:
        rows.append(f"| 待补充 | 待补充 | 待补充 | {escape_cell(source_label)} |")
    return "\n".join(rows)


def baseline_source_type(update):
    source_type = str(update.get("source_type", "")).strip()
    if source_type:
        return source_type
    raw_source = str(update.get("raw_source", "")).strip()
    m = re.match(r"^raw/([^/]+)-baseline/", raw_source)
    return m.group(1) if m else "ifind"


def baseline_source_label(update):
    label = str(update.get("baseline_source_label", "")).strip()
    if label:
        return label
    return SOURCE_LABELS.get(baseline_source_type(update), baseline_source_type(update))


def evidence_section_title(update):
    return "iFinD 证据" if baseline_source_type(update) == "ifind" else "Baseline 证据"


def render_list(items, fallback):
    values = [str(x).strip() for x in items or [] if str(x).strip()]
    if not values:
        values = [fallback]
    return "\n".join(f"- {x}" for x in values)


def render_evidence(update):
    raw_source = update.get("raw_source", "")
    lines = []
    if raw_source:
        lines.append(f"- Raw：`{raw_source}`")
    for item in update.get("exposures", []) or []:
        evidence = str(item.get("evidence", "")).strip()
        if evidence:
            lines.append(f"- {item.get('concept', '未命名概念')}：{evidence}")
    return "\n".join(lines or ["- 待补充。"])


def validate_raw_source_content(update, raw_path):
    company = update.get("company", "")
    try:
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"{company}: raw_source is not valid JSON: {exc}")

    raw_text = json.dumps(raw, ensure_ascii=False)
    if any(phrase in raw_text for phrase in INVALID_RAW_CONTENT_PHRASES):
        raise ValueError(f"{company}: raw_source contains invalid/limited iFinD response")

    contents = extract_raw_contents(raw)
    if not contents:
        raise ValueError(f"{company}: raw_source has no usable iFinD content")

    combined = "\n".join(contents)
    required_fragments = [
        str(update.get("main_business", "")).strip(),
        *[str(x).strip() for x in update.get("products", []) or []],
    ]
    missing = []
    for fragment in required_fragments:
        if fragment and fragment != "待补充" and fragment not in combined:
            missing.append(fragment)
    if missing:
        raise ValueError(f"{company}: update contains fields not supported by raw_source: {missing[:3]}")


def extract_raw_contents(raw):
    contents = []
    for result in raw.get("results", []) or []:
        content = result.get("content", "")
        if isinstance(content, (dict, list)):
            content_text = json.dumps(content, ensure_ascii=False)
        else:
            content_text = str(content or "")
        if content_text.strip():
            contents.append(content_text)
    for key in ("profile", "main_business", "business_scope", "business_composition", "industry", "products"):
        value = raw.get(key)
        if value:
            contents.append(json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value))
    return contents


def validate_update(update, source_name=""):
    company = update.get("company", "")
    if "automatic batch" in str(source_name):
        raise ValueError(f"{company}: automatic batch source_name is rejected")
    raw_source = str(update.get("raw_source", "")).strip()
    if not raw_source or not RAW_SOURCE_RE.fullmatch(raw_source):
        raise ValueError(f"{company}: raw_source must point to raw/{ifind,akshare,cninfo,eastmoney,manual-verified}-baseline/*.json")
    raw_path = VAULT / raw_source
    if not raw_path.exists():
        raise ValueError(f"{company}: raw_source file does not exist: {raw_source}")
    validate_raw_source_content(update, raw_path)

    searchable = json.dumps(update, ensure_ascii=False)
    for phrase in FORBIDDEN_PHRASES:
        if phrase in searchable:
            raise ValueError(f"{company}: forbidden placeholder phrase detected: {phrase}")

    main_business = str(update.get("main_business", "")).strip()
    if not main_business or main_business == "待补充":
        raise ValueError(f"{company}: missing main_business")

    products = [str(x).strip() for x in update.get("products", []) or [] if str(x).strip()]
    if not products:
        raise ValueError(f"{company}: missing products")

    exposures = update.get("exposures", []) or []
    if not exposures:
        raise ValueError(f"{company}: missing exposures")

    for i, item in enumerate(exposures, 1):
        concept = str(item.get("concept", "")).strip()
        role = str(item.get("role", "")).strip()
        evidence = str(item.get("evidence", "")).strip()
        strength = str(item.get("strength", "")).strip()
        confidence = str(item.get("confidence", "")).strip()
        if not all([concept, role, evidence, strength, confidence]):
            raise ValueError(f"{company}: exposure #{i} missing required fields")
        if strength not in VALID_STRENGTHS:
            raise ValueError(f"{company}: exposure #{i} invalid strength={strength!r}; use core/related/peripheral")
        if confidence not in VALID_CONFIDENCE:
            raise ValueError(f"{company}: exposure #{i} invalid confidence={confidence!r}; use high/medium/low")
        if len(evidence) < 12:
            raise ValueError(f"{company}: exposure #{i} evidence too short")


def new_body(update):
    company = update["company"]
    code = update.get("code", "")
    title = f"{company}（{code}）" if code else company
    return "\n".join(["", f"# {title}", "", "一句话定位：待补充。", ""])


def update_file(update, source_name):
    company = strip_code_suffix(update.get("company", ""))
    if not company:
        raise ValueError("missing company")
    update["company"] = company
    validate_update(update, source_name)
    code = re.sub(r"\D", "", str(update.get("code", "")))
    path = find_entity_path(company, code)
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    prefix, fm_lines, body = split_frontmatter(text)
    if fm_lines is None:
        fm_lines = [
            f"title: {json.dumps(f'{company}（{code}）' if code else company, ensure_ascii=False)}",
            "aliases: []",
            "tags: []",
            "entity_type: 上市公司",
            f"created: {today()}",
            "revision: 0",
            "sources: []",
            "raw_sources: []",
        ]
        body = new_body(update)
    meta = parse_simple_frontmatter(fm_lines)

    tags = parse_list_value(meta.get("tags", "[]"))
    for concept in update.get("concepts", []) or []:
        if concept and concept not in tags:
            tags.append(concept)
    tags += ["A股", "上市公司"]
    tickers = parse_list_value(meta.get("tickers", "[]"))
    if code and code not in tickers:
        tickers.append(code)
    raw_sources = parse_list_value(meta.get("raw_sources", "[]"))
    raw_source = str(update.get("raw_source", "")).strip()
    if raw_source and raw_source not in raw_sources:
        raw_sources.append(raw_source)

    upsert_frontmatter_line(fm_lines, "updated", today())
    upsert_frontmatter_line(fm_lines, "revision", increment_revision(meta.get("revision", "0")))
    upsert_frontmatter_line(fm_lines, "tags", yaml_list(tags))
    if tickers:
        upsert_frontmatter_line(fm_lines, "tickers", yaml_list(tickers))
    upsert_frontmatter_line(fm_lines, "markets", yaml_list([market_from_code(code)]))
    if raw_sources:
        upsert_frontmatter_line(fm_lines, "raw_sources", yaml_list(raw_sources))

    body = upsert_section(body, "Baseline 基础画像", render_baseline(update))
    body = upsert_section(body, "Baseline 产业链暴露", render_exposures(update))
    body = upsert_section(body, "Baseline 关键数据", render_key_data(update))
    body = upsert_section(body, "Baseline 风险与反证", render_list(update.get("risks", []), "待补充。"))
    body = upsert_section(body, "Baseline 待核实问题", render_list(update.get("open_questions", []), "补充年报、公告、官网或后续研报验证。"))
    body = merge_section_lines(body, evidence_section_title(update), render_evidence(update))

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(prefix + "---\n" + "\n".join(fm_lines) + "\n---\n" + body.rstrip() + "\n", encoding="utf-8")

    graph_files = {}
    for exp in update.get("exposures", []) or []:
        files = update_entity_exposures(
            company,
            code=code,
            concepts=[exp.get("concept", "")],
            source_name=source_name,
            role=exp.get("role", ""),
            strength=exp.get("strength", "related"),
            evidence=exp.get("evidence", ""),
            confidence=exp.get("confidence", "medium"),
            chain_layer=exp.get("chain_layer", ""),
            evidence_layer="L2",
            update_type="baseline",
        )
        graph_files.update(files)
    return str(path), graph_files


def preflight_update(update, source_name):
    company = strip_code_suffix(update.get("company", ""))
    update = dict(update)
    update["company"] = company
    validate_update(update, source_name)
    code = re.sub(r"\D", "", str(update.get("code", "")))
    path = find_entity_path(company, code)
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    _, fm_lines, body = split_frontmatter(text)
    meta = parse_simple_frontmatter(fm_lines or [])
    tickers = parse_list_value(meta.get("tickers", "[]"))
    title = str(meta.get("title", "")).strip()
    title_codes = sorted(set(re.findall(r"\b\d{6}\b", title)))
    protected_sections = [title for title in ["基础画像", "产业链暴露", "关键数据", "风险与反证", "待核实问题"] if has_section(body, title)]
    baseline_sections = [title for title in ["Baseline 基础画像", "Baseline 产业链暴露", "Baseline 关键数据", "Baseline 风险与反证", "Baseline 待核实问题", evidence_section_title(update)] if has_section(body, title)]
    other_tickers = sorted(ticker for ticker in tickers if re.fullmatch(r"\d{6}", ticker) and ticker != code)
    risks = []
    if protected_sections:
        risks.append("protected_sections_present")
    if other_tickers:
        risks.append("other_tickers_present")
    if title_codes and code and code not in title_codes:
        risks.append("title_code_mismatch")
    return {
        "company": company,
        "code": code,
        "file": str(path),
        "exists": path.exists(),
        "protected_sections": protected_sections,
        "baseline_sections": baseline_sections,
        "tickers": tickers,
        "other_tickers": other_tickers,
        "title_codes": title_codes,
        "risks": risks,
        "will_write_sections": ["Baseline 基础画像", "Baseline 产业链暴露", "Baseline 关键数据", "Baseline 风险与反证", "Baseline 待核实问题", evidence_section_title(update)],
        "will_update_relations": bool(update.get("exposures")),
    }


def preflight_updates(data):
    source_name = data.get("source_name") or f"iFinD baseline {today()}"
    checked, skipped = [], []
    for update in data.get("updates", []):
        try:
            checked.append(preflight_update(update, source_name))
        except Exception as exc:
            skipped.append({"company": update.get("company", ""), "reason": str(exc)})
    return {"status": "ok", "checked": checked, "skipped": skipped}


def write_updates(data):
    ENTITIES_DIR.mkdir(parents=True, exist_ok=True)
    source_name = data.get("source_name") or f"iFinD baseline {today()}"
    updated, skipped = [], []
    graph_files = {}
    for update in data.get("updates", []):
        try:
            path, files = update_file(update, source_name)
            updated.append({"company": update.get("company"), "file": path})
            graph_files.update(files)
        except Exception as exc:
            skipped.append({"company": update.get("company", ""), "reason": str(exc)})
    return {"status": "ok", "updated": updated, "skipped": skipped, "graph_files": graph_files}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    if sys.stdin.isatty():
        print("Usage: python3 entity_baseline_writer.py [--preflight] <<'JSON'\n{...}\nJSON", file=sys.stderr)
        sys.exit(1)
    data = json.loads(sys.stdin.read())
    result = preflight_updates(data) if args.preflight else write_updates(data)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
