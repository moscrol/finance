#!/usr/bin/env python3
"""
entity_delta_writer.py — 公司边际变化入库

Reads structured JSON from stdin and appends short, dated delta notes to
Obsidian entity pages.
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
from knowledge_graph import update_entity_exposures  # noqa: E402

VAULT = Path(os.path.expanduser(os.environ.get("ENTITY_VAULT", "~/Desktop/c c/知识库/wiki")))
ENTITIES_DIR = VAULT / "entities"
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
    return re.sub(r'[/:*?"<>|\n\r\t]+', "_", str(title)).strip() or "未命名实体"


def strip_code_suffix(name):
    return re.sub(r"（\d{6}）$", "", str(name or "")).strip()


def market_from_code(code):
    code = str(code or "")
    if re.match(r"^(0|3)\d{5}$", code):
        return "A股"
    if re.match(r"^6\d{5}$", code):
        return "A股"
    if re.match(r"^8\d{5}$|^9\d{5}$", code):
        return "北交所"
    return "未知"


def render_concepts(concepts):
    links = [wikilink(c) for c in concepts if wikilink(c)]
    return " · ".join(links) if links else "待补充"


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
        if not m:
            continue
        key, value = m.group(1), m.group(2).strip()
        data[key] = value
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
        return [f"[[{normalize_target(v)}]]" for v in links]
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


def entity_index():
    by_name = {}
    by_code = {}
    if not ENTITIES_DIR.exists():
        return by_name, by_code
    for path in ENTITIES_DIR.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        _, fm, _ = split_frontmatter(text)
        meta = parse_simple_frontmatter(fm or [])
        name = strip_code_suffix(meta.get("title", path.stem))
        by_name.setdefault(name, path)
        by_name.setdefault(path.stem, path)
        for code in re.findall(r"\b\d{6}\b", meta.get("tickers", "") + " " + meta.get("title", "")):
            by_code.setdefault(code, path)
    return by_name, by_code


def resolve_code(company, code):
    code = re.sub(r"\D", "", str(code or ""))
    if len(code) == 6:
        return code
    return load_akshare_name_code().get(company, "")


def find_entity_path(company, code, by_name, by_code):
    name_match = by_name.get(company) or by_name.get(strip_code_suffix(company))
    if name_match:
        return name_match
    if code and code in by_code:
        return by_code[code]
    return None


def render_delta(update, source_name, source_date):
    entry_date = update.get("date") or source_date or today()
    title = str(update.get("title") or "边际变化").strip()
    bullets = [str(b).strip() for b in update.get("bullets", []) if str(b).strip()]
    concepts = [normalize_target(c) for c in update.get("concepts", []) if normalize_target(c)]
    evidence = str(update.get("evidence") or "").strip()

    parts = [f"### {entry_date}｜{source_name}", ""]
    if title:
        parts.extend([f"**{title}**", ""])
    for bullet in bullets:
        parts.append(f"- {bullet}")
    if concepts:
        parts.append(f"- 相关概念：{' · '.join(wikilink(c) for c in concepts)}")
    if evidence:
        parts.append(f"- 原文依据：{evidence}")
    parts.append("")
    return "\n".join(parts)


def append_section_entry_to_body(body, section_title, entry_md, concepts):
    body = body.rstrip() + "\n"
    marker = f"## {section_title}\n"
    if marker not in body:
        insert_before = re.search(r"\n## 边际变化\n", body)
        if insert_before:
            idx = insert_before.start()
            body = body[:idx].rstrip() + f"\n\n{marker}\n" + body[idx:]
        else:
            body += f"\n{marker}\n"
    pattern = re.compile(rf"(## {re.escape(section_title)}\n\n?)", re.M)
    body = pattern.sub(r"\1" + entry_md, body, count=1)
    return upsert_related_concepts(body, concepts)


def append_delta_to_body(body, delta_md, concepts):
    return append_section_entry_to_body(body, "边际变化", delta_md, concepts)


def append_curated_research_to_body(body, entry_md, concepts):
    return append_section_entry_to_body(body, "高信度研究线索", entry_md, concepts)


def new_entity_frontmatter(update, source_name):
    company = update["company"]
    code = resolve_code(company, update.get("code", ""))
    display_title = f"{company}（{code}）" if code else company
    concepts = [normalize_target(c) for c in update.get("concepts", []) if normalize_target(c)]
    tags = []
    for concept in concepts:
        if concept not in tags:
            tags.append(concept)
    tags.extend(["A股", "上市公司"])

    lines = [
        f"title: {json.dumps(display_title, ensure_ascii=False)}",
        "aliases: []",
        f"tags: {yaml_list(tags)}",
        "entity_type: 上市公司",
    ]
    if code:
        lines.append(f"tickers: {yaml_list([code])}")
    lines.append(f"markets: {yaml_list([market_from_code(code)])}")
    lines.extend([
        f"created: {today()}",
        f"updated: {today()}",
        "revision: 0",
        f"sources: {yaml_list([wikilink(source_name)])}",
        "raw_sources: []",
        f"log: {yaml_list([f'#001 created from {wikilink(source_name)}'])}",
    ])
    return lines


def new_entity_body(update):
    company = update["company"]
    code = resolve_code(company, update.get("code", ""))
    display_title = f"{company}（{code}）" if code else company
    concepts = [normalize_target(c) for c in update.get("concepts", []) if normalize_target(c)]
    title = str(update.get("title") or "边际变化").strip()
    current_judgment = str(update.get("judgment") or "需核实").strip()

    return "\n".join([
        "",
        f"# {display_title}",
        "",
        f"一句话定位：{title}",
        "",
        "## 速览",
        "",
        "| 维度 | 内容 |",
        "|---|---|",
        "| 实体类型 | 上市公司 |",
        f"| 所属市场 | {market_from_code(code)} |",
        f"| 核心赛道 | {render_concepts(concepts)} |",
        "| 产业链位置 | 待补充 |",
        "| 核心产品/能力 | 待补充 |",
        "| 主要客户/生态 | 待补充 |",
        "| 主要竞争对手 | 待补充 |",
        f"| 当前判断 | {current_judgment} |",
        "| 信息可信度 | 中；来自单篇材料，待后续 raw/公告/研报交叉验证 |",
        "",
        "## 在赛道中的角色",
        "",
        "| 赛道/概念 | 角色定位 | 关键依据 | 边际变化 | 证据来源 |",
        "|---|---|---|---|---|",
        "",
        "## 关键数据",
        "",
        "| 指标 | 数据 | 时间/口径 | 来源 |",
        "|---|---:|---|---|",
        "",
        "## 业务与产品",
        "",
        "- 待补充。",
        "",
        "## 风险与反证",
        "",
        "- 待补充。",
        "",
        "## 待核实问题",
        "",
        "- [ ] 补充年报、公告、官网或后续研报验证。",
        "",
    ])


GENERIC_ROLES = {
    "", "受益标的", "相关公司", "产业链供应商", "待验证受益标的", "市场信号弱关联", "图谱弱关联",
}
CHAIN_LAYER_VALUES = {
    "upstream_materials", "upstream_components", "upstream_equipment",
    "midstream_manufacturing", "midstream_components", "midstream_service", "midstream_equipment",
    "downstream_application", "downstream_operation", "ecosystem",
    "upstream", "midstream", "downstream", "上游", "中游", "下游",
}

# Source quality enums
VALID_SOURCE_QUALITY = {
    "official_disclosure", "company_primary",
    "broker_research_high", "broker_research_normal",
    "market_news", "market_narrative", "legacy_rebuilt", "unknown",
}
BROKER_SOURCES = {"broker_research_high", "broker_research_normal"}
L3_SOURCES = {"official_disclosure", "company_primary"}


def validate_and_route(update):
    """Validate fields and determine write routing. Returns (route, reason, warnings).

    Routing rules:
    - hard_fact + L3 source → delta (边际变化)
    - review_candidate + broker source → curated_research (高信度研究线索)
    - research_claim → curated_research (高信度研究线索)
    - market_narrative/unknown/legacy_rebuilt → graph_only
    - broker source without explicit hardness → curated_research default
    """
    warnings = []
    fact_hardness = str(update.get("fact_hardness", "")).strip()
    update_type = str(update.get("update_type", "")).strip()
    evidence_layer = str(update.get("evidence_layer", "")).strip()
    source_quality = str(update.get("source_quality", "")).strip()
    role = str(update.get("role") or update.get("chain_role") or update.get("segment") or "").strip()

    # Role validation
    if role in GENERIC_ROLES:
        warnings.append(f"role is generic: '{role}'")
    if role in CHAIN_LAYER_VALUES:
        warnings.append(f"role equals chain_layer: '{role}'")

    # === Routing logic ===

    # 1. hard_fact: ONLY if source is L3 (official disclosure/company primary)
    if fact_hardness == "hard_fact":
        if source_quality in L3_SOURCES:
            return "delta", "hard_fact + L3 source → 边际变化", warnings
        else:
            # Empty or non-L3 source_quality: downgrade
            warnings.append(f"hard_fact requires L3 source_quality, got '{source_quality}' → downgrading to review_candidate/curated_research")
            update["fact_hardness"] = "review_candidate"
            update["review_required"] = True
            return "curated_research", "hard_fact + non-L3 source → 高信度研究线索 (review_candidate)", warnings

    # 2. review_candidate: broker research with company-level facts
    if fact_hardness == "review_candidate":
        update["review_required"] = True
        if evidence_layer and evidence_layer != "L1_L3_candidate":
            warnings.append(f"review_candidate should have evidence_layer=L1_L3_candidate, got {evidence_layer}")
        return "curated_research", "review_candidate → 高信度研究线索 (review_required=true)", warnings

    # 3. research_claim: normal broker research judgment
    if fact_hardness == "research_claim":
        return "curated_research", "research_claim → 高信度研究线索", warnings

    # 4. Soft hardness: graph_only
    if fact_hardness in {"market_narrative", "unknown", "legacy_rebuilt"}:
        return "graph_only", f"fact_hardness={fact_hardness} → graph_only", warnings

    # 5. baseline
    if fact_hardness == "baseline":
        return "baseline", "fact_hardness=baseline", warnings

    # 6. No fact_hardness specified: infer from source_quality
    if source_quality in BROKER_SOURCES:
        return "curated_research", f"source_quality={source_quality}, default curated_research", warnings

    if source_quality in L3_SOURCES:
        return "delta", f"source_quality={source_quality}, default delta", warnings

    # 7. Fallback: use update_type if specified
    if update_type == "curated_research":
        return "curated_research", "no hardness, update_type=curated_research", warnings
    if update_type == "graph_only":
        return "graph_only", "no hardness, update_type=graph_only", warnings

    # 8. Default: curated_research (conservative, don't write 边际变化)
    return "curated_research", "no hardness/source_quality specified, default curated_research", warnings


def update_entity_file(path, update, source_name, source_date, raw_sources=None):
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    prefix, fm_lines, body = split_frontmatter(text)
    if fm_lines is None:
        is_new = True
        fm_lines = new_entity_frontmatter(update, source_name)
        body = new_entity_body(update)
    else:
        is_new = False

    meta = parse_simple_frontmatter(fm_lines)
    code = resolve_code(update["company"], update.get("code", ""))
    sources = parse_list_value(meta.get("sources", "[]"))
    source_link = wikilink(source_name)
    if source_link and source_link not in sources:
        sources.append(source_link)
    tickers = parse_list_value(meta.get("tickers", "[]"))
    if code and code not in tickers:
        tickers.append(code)
    raw_source_values = parse_list_value(meta.get("raw_sources", "[]"))
    for raw_source in raw_sources or []:
        raw_source = str(raw_source).strip()
        if raw_source and raw_source not in raw_source_values:
            raw_source_values.append(raw_source)

    upsert_frontmatter_line(fm_lines, "updated", today())
    upsert_frontmatter_line(fm_lines, "revision", increment_revision(meta.get("revision", "0")))
    upsert_frontmatter_line(fm_lines, "sources", yaml_list(sources))
    if tickers:
        upsert_frontmatter_line(fm_lines, "tickers", yaml_list(sorted(set(tickers))))
    upsert_frontmatter_line(fm_lines, "markets", yaml_list([market_from_code(code)]))
    if raw_source_values:
        upsert_frontmatter_line(fm_lines, "raw_sources", yaml_list(raw_source_values))

    update_type = str(update.get("update_type") or "").strip()

    # Fact hardness routing gate (must run BEFORE log prefix determination)
    route, route_reason, field_warnings = validate_and_route(update)
    if field_warnings:
        print(f"  WARN [{update.get('company')}]: {'; '.join(field_warnings)}", file=sys.stderr)

    log = parse_list_value(meta.get("log", "[]"))
    if route == "curated_research":
        log_prefix = "added curated research from"
    elif route == "delta":
        log_prefix = "added delta from"
    elif route == "graph_only":
        log_prefix = "added graph-only exposure from"
    else:
        log_prefix = f"added {route} from"
    log_item = f"{log_prefix} {source_link}"
    if source_link and not is_new:
        # Remove old log entries for the same source with different prefixes
        old_prefixes = ["added delta from", "added curated research from", "added graph-only exposure from",
                        "added baseline from", "added hard_delta from"]
        log = [entry for entry in log
               if not any(entry.startswith(p) and source_link in entry for p in old_prefixes)
               or entry == log_item]
        if log_item not in log:
            log.append(log_item)
        upsert_frontmatter_line(fm_lines, "log", yaml_list(log))

    exposure_only = bool(update.get("exposure_only"))
    new_body = body
    if route == "curated_research":
        # fact_hardness=research_claim/market_narrative/unknown/legacy_rebuilt
        # Write to 高信度研究线索 or graph_only only
        new_body = append_curated_research_to_body(body, render_delta(update, source_name, source_date), update.get("concepts", []))
    elif route == "delta" and not exposure_only:
        # fact_hardness=hard_fact/review_candidate → write to 边际变化
        new_body = append_delta_to_body(body, render_delta(update, source_name, source_date), update.get("concepts", []))
    elif exposure_only or route == "graph_only":
        # Only update relations, not entity markdown
        if update.get("concepts"):
            new_body = upsert_related_concepts(body, update.get("concepts", []))
    elif route == "baseline":
        # Baseline updates: only relations
        if update.get("concepts"):
            new_body = upsert_related_concepts(body, update.get("concepts", []))
    content = prefix + "---\n" + "\n".join(fm_lines) + "\n---\n" + new_body
    path.write_text(content, encoding="utf-8")

    # Resolve role: use specific role, fallback to chain_layer description, then generic
    raw_role = update.get("role") or update.get("chain_role") or update.get("segment") or ""
    resolved_role = raw_role.strip()
    if not resolved_role or resolved_role in GENERIC_ROLES or resolved_role in CHAIN_LAYER_VALUES:
        # Try to construct from chain_layer
        chain = update.get("chain_layer", "")
        if chain and chain not in CHAIN_LAYER_VALUES:
            resolved_role = chain
        else:
            resolved_role = "待补充"

    return update_entity_exposures(
        update["company"],
        code=code,
        concepts=update.get("concepts", []),
        source_name=source_name,
        source_date=source_date,
        role=resolved_role,
        strength=update.get("tier") or update.get("strength") or "related",
        evidence=update.get("evidence", ""),
        confidence=update.get("confidence", "medium"),
        chain_layer=update.get("chain_layer", ""),
        evidence_layer=update.get("evidence_layer", ""),
        update_type=route if route != "delta" else (update_type or "delta"),
        fact_hardness=update.get("fact_hardness", ""),
        source_quality=update.get("source_quality", ""),
        review_required=bool(update.get("review_required", False)),
    )


def create_source_note(data, updated, created, skipped, graph_only=None):
    source_name = normalize_target(data.get("source_name") or "未命名来源")
    if not source_name:
        return None
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)
    path = SOURCES_DIR / f"{safe_filename(source_name)}.md"
    source_date = data.get("source_date", "")
    source_file = data.get("source_file", "")
    raw_sources = data.get("raw_sources", [])
    watchlist = data.get("watchlist", [])
    if path.exists():
        text = path.read_text(encoding="utf-8").rstrip()
        lines = [""]
    else:
        lines = [
            "---",
            f"title: {json.dumps(source_name, ensure_ascii=False)}",
            "type: source",
        ]
        if source_date:
            lines.append(f"source_date: {source_date}")
        lines.extend([f"created: {today()}", "---", "", f"# {source_name}", ""])
        if source_file:
            lines.extend([f"本地文件：`{source_file}`", ""])
        if raw_sources:
            lines.extend(["## Raw Sources", ""])
            for raw_source in raw_sources:
                lines.append(f"- `{raw_source}`")
            lines.append("")
        text = ""
    if updated or created:
        lines.extend(["## 已更新实体", ""])
        for name in updated + created:
            lines.append(f"- [[{name}]]")
        lines.append("")
    if graph_only:
        lines.extend(["## 仅更新图谱", ""])
        for name in graph_only:
            lines.append(f"- {name}")
        lines.append("")
    if skipped:
        lines.extend(["## 跳过", ""])
        for item in skipped:
            lines.append(f"- {item.get('company', '')}：{item.get('reason', '')}")
        lines.append("")
    if watchlist:
        lines.extend(["## 观察列表", ""])
        for item in watchlist:
            company = item.get("company", "")
            code = item.get("code", "")
            reason = item.get("reason", "")
            code_part = f"（{code}）" if code else ""
            lines.append(f"- {company}{code_part}：{reason}")
        lines.append("")
    path.write_text((text + "\n" + "\n".join(lines)).lstrip(), encoding="utf-8")
    return str(path)


def write_updates(data):
    ENTITIES_DIR.mkdir(parents=True, exist_ok=True)
    source_name = normalize_target(data.get("source_name") or "未命名来源")
    source_date = data.get("source_date") or today()
    default_create_missing = bool(data.get("create_missing", False))
    raw_sources = data.get("raw_sources", [])
    by_name, by_code = entity_index()

    updated, created, skipped, graph_only = [], [], [], []
    graph_files = {}
    for raw in data.get("updates", []):
        company = strip_code_suffix(raw.get("company", ""))
        if not company:
            skipped.append({"company": "", "reason": "missing company"})
            continue
        raw["company"] = company
        code = resolve_code(company, raw.get("code", ""))
        if raw.get("graph_only"):
            raw["code"] = code
            route, route_reason, field_warnings = validate_and_route(raw)
            if field_warnings:
                print(f"  WARN [{raw.get('company')}]: {'; '.join(field_warnings)}", file=sys.stderr)
            relation_update_type = raw.get("update_type") or ("review_candidate" if raw.get("fact_hardness") == "review_candidate" else "graph_only")
            files = update_entity_exposures(
                company,
                code=code,
                concepts=raw.get("concepts", []),
                source_name=source_name,
                source_date=source_date,
                role=raw.get("role") or raw.get("chain_role") or raw.get("segment") or "受益标的",
                strength=raw.get("tier") or raw.get("strength") or "related",
                evidence=raw.get("evidence", ""),
                confidence=raw.get("confidence", "medium"),
                chain_layer=raw.get("chain_layer", ""),
                evidence_layer=raw.get("evidence_layer", ""),
                update_type=relation_update_type,
                fact_hardness=raw.get("fact_hardness", ""),
                source_quality=raw.get("source_quality", ""),
                review_required=bool(raw.get("review_required", False)),
            )
            graph_files.update(files)
            graph_only.append(company)
            continue
        path = find_entity_path(company, code, by_name, by_code)
        create_missing = bool(raw.get("create_missing", default_create_missing))
        if path is None:
            if not create_missing:
                skipped.append({"company": company, "reason": "entity not found and create_missing=false"})
                continue
            path = ENTITIES_DIR / f"{safe_filename(company)}.md"
            created.append(company)
        else:
            updated.append(path.stem)
        raw["code"] = code
        files = update_entity_file(path, raw, source_name, source_date, raw_sources=raw_sources)
        graph_files.update(files)

    source_file = create_source_note(data, updated, created, skipped, graph_only=graph_only)
    return {
        "status": "ok",
        "updated_entities": updated,
        "created_entities": created,
        "graph_only_entities": graph_only,
        "skipped_updates": skipped,
        "watchlist": data.get("watchlist", []),
        "source_file": source_file,
        "graph_files": graph_files,
    }


def main():
    if sys.stdin.isatty():
        print("Usage: python3 entity_delta_writer.py <<'JSON'\n{...}\nJSON", file=sys.stderr)
        sys.exit(1)
    data = json.loads(sys.stdin.read())
    print(json.dumps(write_updates(data), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
