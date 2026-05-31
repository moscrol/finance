#!/usr/bin/env python3
"""
concept_writer.py — 新概念入库引擎 v2

读取 LLM 提取的结构化 JSON，完成：
0. 入口判断（is_concept / existing_concept / existing_source）
1. 去重检查
2. 公司名→代码匹配（本地映射 + iFinD 兜底）
3. 概念关系定性 + 标的交叉对比
4. 催化事件时间线
5. 生成 frontmatter + markdown 写入 Obsidian vault
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
ENTITIES_DIR = VAULT / "entities"
SOURCES_DIR = VAULT / "sources"
IFIND_DIR = Path(os.path.expanduser(os.environ.get("IFIND_SKILL_DIR", "~/Desktop/c c/金融/skills/ifind")))
AKSHARE_CODE_NAME_CACHE = None


# ═══════════════════════════════════════════════════════════════
# 映射表
# ═══════════════════════════════════════════════════════════════

def load_entity_tickers():
    mapping = {}
    if not ENTITIES_DIR.exists():
        return mapping
    for path in ENTITIES_DIR.glob("*.md"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        title_m = re.search(r"^title:\s*(.+?)(?:（|$)", text, re.MULTILINE)
        tm = re.search(r"^tickers:\s*\[(.*?)\]", text, re.MULTILINE)
        if title_m and tm:
            name = title_m.group(1).strip()
            codes = re.findall(r'"*(\d{6})"*', tm.group(1))
            if codes:
                mapping[name] = codes
    return mapping


def load_concept_table_tickers():
    mapping = {}
    if not CONCEPTS_DIR.exists():
        return mapping
    for path in CONCEPTS_DIR.glob("*.md"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for line in text.split("\n"):
            m = re.match(
                r"\|\s*\*{0,2}([一-鿿\w]{2,10}"
                r"(?:股份|科技|能源|新材|集团|电气|电子|通信|智能|控股|实业|"
                r"技术|材料|精密|光电|互联|数据|动力|制造|激光|微电|导体|芯片|"
                r"电路|创|光|机)?)\*{0,2}\s*\|",
                line
            )
            if not m:
                continue
            name = m.group(1).strip("* ")
            if len(name) < 3:
                continue
            codes = re.findall(r"\b(\d{6})\b", line)
            if codes and name not in mapping:
                mapping[name] = codes
    return mapping


def load_all_name_map():
    m = {}
    m.update(load_entity_tickers())
    m.update(load_concept_table_tickers())
    return m


def load_code_to_name(name_map, extra_ticker_map=None):
    rev = {}
    for name, codes in name_map.items():
        for c in codes:
            if c not in rev:
                rev[c] = name
    if extra_ticker_map:
        for name, code in extra_ticker_map.items():
            if code and code not in rev:
                rev[code] = name
    for code, name in load_akshare_code_to_name().items():
        if code not in rev:
            rev[code] = name
    return rev


def load_akshare_code_to_name():
    """A股代码→名称兜底；失败时返回空映射，不影响入库主流程."""
    global AKSHARE_CODE_NAME_CACHE
    if AKSHARE_CODE_NAME_CACHE is not None:
        return AKSHARE_CODE_NAME_CACHE
    try:
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            import akshare as ak
            df = ak.stock_info_a_code_name()
        code_col = "code" if "code" in df.columns else df.columns[0]
        name_col = "name" if "name" in df.columns else df.columns[1]
        AKSHARE_CODE_NAME_CACHE = {
            str(code).zfill(6): str(name)
            for code, name in zip(df[code_col], df[name_col])
            if str(code).strip() and str(name).strip()
        }
    except Exception:
        AKSHARE_CODE_NAME_CACHE = {}
    return AKSHARE_CODE_NAME_CACHE


def load_concept_frontmatter_tickers():
    ct = {}
    if not CONCEPTS_DIR.exists():
        return ct
    for path in CONCEPTS_DIR.glob("*.md"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        tm = re.search(r"^tickers:\s*\[(.*?)\]", text, re.MULTILINE)
        if tm:
            codes = re.findall(r'"*(\d{6})"*', tm.group(1))
            cname = path.stem
            if codes:
                ct[cname] = codes
    return ct


# ═══════════════════════════════════════════════════════════════
# 索引
# ═══════════════════════════════════════════════════════════════

def list_existing_concepts():
    if not CONCEPTS_DIR.exists():
        return set()
    return {p.stem for p in CONCEPTS_DIR.glob("*.md")}


def list_existing_sources():
    if not SOURCES_DIR.exists():
        return set()
    return {p.stem for p in SOURCES_DIR.glob("*.md")}


# ═══════════════════════════════════════════════════════════════
# iFinD
# ═══════════════════════════════════════════════════════════════

def ifind_resolve_ticker(company_name):
    import subprocess
    safe_query = json.dumps(f"{company_name}的股票代码", ensure_ascii=False)
    script = f"""
const {{ call }} = require('./call-node.js');
async function run() {{
  const r = await call('stock', 'get_stock_info', {{ query: {safe_query} }});
  const text = JSON.parse(r.data.result.content[0].text);
  const data = text.data.answer || '';
  const codes = data.match(/\\b\\d{{6}}\\b/g);
  if (codes) console.log(codes[0]);
  else console.log('');
}}
run().catch(() => console.log(''));
"""
    try:
        result = subprocess.run(
            ["node", "-e", script],
            cwd=str(IFIND_DIR),
            capture_output=True, text=True, timeout=15
        )
        code = result.stdout.strip()
        return code if re.match(r"^\d{6}$", code) else None
    except Exception:
        return None


def resolve_tickers(company_names, name_map):
    """公司名→代码解析：先本地映射，未命中调 iFinD 兜底"""
    result = {}
    for name in company_names:
        name = name.strip()
        if name in name_map:
            result[name] = name_map[name][0]
        else:
            code = ifind_resolve_ticker(name)
            if code:
                result[name] = code
            else:
                result[name] = ""
    return result


# ═══════════════════════════════════════════════════════════════
# 辅助
# ═══════════════════════════════════════════════════════════════

def normalize_companies(raw):
    """
    兼容两种格式：
      ["公司A", "公司B"]  → [{"name": "公司A", "tier": "related", "reason": ""}, ...]
      [{"name": "A", "tier": "core", "reason": "..."}] → 原样
    """
    if not raw:
        return []
    result = []
    seen = set()
    for item in raw:
        if isinstance(item, str):
            name = item.strip()
            tier = "related"
            reason = ""
        elif isinstance(item, dict):
            name = str(item.get("name", "")).strip()
            tier = item.get("tier", "related")
            reason = str(item.get("reason", "")).strip()
        else:
            continue
        if not name or name in seen:
            continue
        if tier not in {"core", "related", "peripheral"}:
            tier = "related"
        seen.add(name)
        result.append({"name": name, "tier": tier, "reason": reason})
    return result


def extract_company_names(companies):
    return [c["name"].strip() for c in companies if c.get("name")]


def find_existing_concepts(candidates):
    existing = list_existing_concepts()
    return [c for c in candidates if c.strip() in existing]


def check_duplicate(concept_title):
    return (CONCEPTS_DIR / f"{safe_concept_filename(concept_title)}.md").exists()


def escape_table_cell(value):
    text = "—" if value is None or value == "" else str(value)
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("\n", "<br>")


def yaml_list(values):
    return "[" + ", ".join(json.dumps(v, ensure_ascii=False) for v in values) + "]"


def normalize_wikilink_target(value):
    """Return bare page title from user/LLM input like '[[A]]' or 'A.md'."""
    text = str(value or "").strip()
    while text.startswith("[[") and text.endswith("]]"):
        text = text[2:-2].strip()
    if text.endswith(".md"):
        text = text[:-3]
    return text.strip()


def wikilink(value):
    target = normalize_wikilink_target(value)
    return f"[[{target}]]" if target else ""


def safe_concept_filename(title):
    return re.sub(r'[/:*?"<>|\n\r\t]+', "_", title).strip() or "未命名概念"


# ═══════════════════════════════════════════════════════════════
# 交叉对比
# ═══════════════════════════════════════════════════════════════

def cross_compare(new_tickers, linked_concepts, ct_map, code_name):
    new_set = set(new_tickers)
    results = []
    for lc_name, rel_type in linked_concepts.items():
        other_tickers = set(ct_map.get(lc_name, []))
        overlap_codes = new_set & other_tickers
        new_only_codes = new_set - other_tickers
        other_only_codes = other_tickers - new_set

        def with_names(codes):
            return [(code_name.get(c, "?"), c) for c in sorted(codes)]

        results.append({
            "concept": lc_name,
            "relationship": rel_type,
            "overlap": with_names(overlap_codes),
            "new_only": with_names(new_only_codes),
            "other_only": with_names(sorted(other_only_codes)[:8]),
        })
    return results


# ═══════════════════════════════════════════════════════════════
# 内容生成
# ═══════════════════════════════════════════════════════════════

def build_key_insights_section(key_insights):
    """生成 '## 边际变化' — 为什么是现在."""
    if not key_insights:
        return ""
    parts = ["## 边际变化", ""]
    for i, insight in enumerate(key_insights, 1):
        parts.append(f"{i}. {insight}")
    parts.append("")
    return "\n".join(parts)


def build_key_data_section(key_data):
    """生成 '## 关键数据' 结构化表格."""
    if not key_data:
        return ""
    parts = ["## 关键数据", ""]
    parts.append("| 指标 | 数值 | 备注 |")
    parts.append("|------|------|------|")
    for kd in key_data:
        indicator = escape_table_cell(kd.get("indicator", "—"))
        value = escape_table_cell(kd.get("value", "—"))
        note = escape_table_cell(kd.get("note", "—"))
        parts.append(f"| {indicator} | {value} | {note} |")
    parts.append("")
    return "\n".join(parts)


def build_risks_section(risks):
    """生成 '## 风险'."""
    if not risks:
        return ""
    parts = ["## 风险", ""]
    for risk in risks:
        parts.append(f"- {risk}")
    parts.append("")
    return "\n".join(parts)


def build_catalyst_section(catalysts):
    if not catalysts:
        return ""
    parts = ["## 催化事件", ""]
    parts.append("| 时间 | 事件 | 影响 |")
    parts.append("|------|------|------|")
    for cat in catalysts:
        time = escape_table_cell(cat.get("time", "—"))
        event = escape_table_cell(cat.get("event", "—"))
        impact = escape_table_cell(cat.get("impact", "—"))
        parts.append(f"| {time} | {event} | {impact} |")
    parts.append("")
    return "\n".join(parts)


def build_stocks_section(companies, ticker_map):
    """生成 '## 关键标的'，含定位和逻辑列."""
    has_tier = any(c.get("tier") and c["tier"] != "related" for c in companies)
    has_reason = any(c.get("reason") for c in companies)

    parts = ["## 关键标的", ""]
    if has_tier or has_reason:
        parts.append("| 公司 | 代码 | 定位 | 逻辑 |")
        parts.append("|------|------|------|------|")
        tier_label = {"core": "核心", "related": "受益", "peripheral": "边缘"}
        for c in companies:
            name = escape_table_cell(c["name"])
            code = escape_table_cell(ticker_map.get(c["name"].strip(), "—"))
            tier = tier_label.get(c.get("tier", "related"), "受益")
            reason = escape_table_cell(c.get("reason", "—"))
            parts.append(f"| {name} | {code} | {tier} | {reason} |")
    else:
        parts.append("| 公司 | 代码 |")
        parts.append("|------|------|")
        for c in companies:
            name = escape_table_cell(c["name"])
            code = escape_table_cell(ticker_map.get(c["name"].strip(), "—"))
            parts.append(f"| {name} | {code} |")
    parts.append("")
    return "\n".join(parts)


def build_relationship_section(cross_results, new_ticker_map):
    code_name = load_code_to_name(load_all_name_map(), new_ticker_map)
    parts = ["## 概念关系", ""]
    for cr in cross_results:
        overlap, new_only, other_only = cr["overlap"], cr["new_only"], cr["other_only"]
        parts.append(f"### [[{cr['concept']}]] — {cr['relationship']}")
        parts.append("")
        if overlap or new_only or other_only:
            parts.append("| 类别 | 标的 |")
            parts.append("|------|------|")
            for name, code in overlap:
                parts.append(f"| 重合 | {escape_table_cell(name)}（{code}） |")
            for name, code in new_only:
                code_str = f"（{code}）" if code != "?" else ""
                parts.append(f"| 本概念独有 | {escape_table_cell(name)}{code_str} |")
            for name, code in other_only:
                code_str = f"（{code}）" if code != "?" else ""
                parts.append(f"| {escape_table_cell(cr['concept'])}独有 | {escape_table_cell(name)}{code_str} |")
            parts.append("")

    pure_new_codes = {v for v in new_ticker_map.values() if v}
    for cr in cross_results:
        pure_new_codes -= {code for _, code in cr["overlap"]}

    if pure_new_codes:
        parts.append("### 纯增量标的")
        parts.append("")
        parts.append("以下标的在所有关联概念中均未出现，是本概念带来的纯增量信息：")
        parts.append("")
        for code in sorted(pure_new_codes):
            name = code_name.get(code, "?")
            parts.append(f"- **{name}**（{code}）")
        parts.append("")

    return "\n".join(parts)


def build_body(data, companies, ticker_map, matched_concepts, cross_results):
    parts = []

    parts.append(f"# {data['title']}")
    parts.append("")

    if data.get("definition"):
        parts.append(data["definition"])
        parts.append("")

    if data.get("oneliner"):
        parts.append(f"**一句话**：{data['oneliner']}")
        parts.append("")

    if data.get("core_thesis"):
        parts.append(f"**核心结论**：{data['core_thesis']}")
        parts.append("")

    if data.get("key_insights"):
        parts.append(build_key_insights_section(data["key_insights"]))

    if data.get("key_data"):
        parts.append(build_key_data_section(data["key_data"]))

    if data.get("mechanism"):
        parts.append("## 核心机制")
        parts.append("")
        parts.append(data["mechanism"])
        parts.append("")

    if data.get("supply_chain"):
        parts.append("## 产业链")
        parts.append("")
        parts.append(data["supply_chain"])
        parts.append("")

    if companies and ticker_map:
        parts.append(build_stocks_section(companies, ticker_map))

    if data.get("market_info"):
        parts.append("## 市场")
        parts.append("")
        parts.append(data["market_info"])
        parts.append("")

    if data.get("core_logic"):
        parts.append("## 核心逻辑")
        parts.append("")
        parts.append(data["core_logic"])
        parts.append("")

    if data.get("catalysts"):
        parts.append(build_catalyst_section(data["catalysts"]))

    if data.get("risks"):
        parts.append(build_risks_section(data["risks"]))

    if cross_results:
        parts.append(build_relationship_section(cross_results, ticker_map))
        parts.append("")

    if matched_concepts:
        parts.append("## 相关概念")
        parts.append("")
        parts.append(" · ".join(f"[[{c}]]" for c in matched_concepts))
        parts.append("")

    entities_with_ticker = [c["name"] for c in companies if ticker_map.get(c["name"].strip())]
    if entities_with_ticker:
        parts.append("## 相关实体")
        parts.append("")
        parts.append(" · ".join(f"[[{n}]]" for n in entities_with_ticker))
        parts.append("")

    return "\n".join(parts)


def build_frontmatter(data, ticker_map):
    today = date.today().isoformat()
    lines = ["---"]
    lines.append(f"title: {json.dumps(data['title'], ensure_ascii=False)}")

    tags = data.get("tags", [])
    if tags:
        lines.append(f"tags: {yaml_list(tags)}")

    tickers = sorted(set(c for c in ticker_map.values() if c))
    if tickers:
        lines.append(f"tickers: {yaml_list(tickers)}")

    lines.append(f"created: {today}")
    lines.append(f"updated: {today}")
    lines.append("revision: 1")

    # 优先用 existing_source，其次用 source_name
    sources = []
    log_parts = []
    existing = normalize_wikilink_target(data.get("existing_source", ""))
    source_name = normalize_wikilink_target(data.get("source_name", ""))
    if existing:
        existing_link = wikilink(existing)
        sources.append(existing_link)
        log_parts.append(f"#001 created from {existing_link}")
    if source_name and source_name != existing:
        source_link = wikilink(source_name)
        sources.append(source_link)
        if not log_parts:
            log_parts.append(f"#001 created from {source_link}")
        else:
            log_parts.append(f"also sourced from {source_link}")

    if sources:
        lines.append(f"sources: {yaml_list(sources)}")
    else:
        lines.append("sources: []")

    if log_parts:
        lines.append(f'log: {json.dumps(log_parts, ensure_ascii=False)}')

    lines.append("---")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════

def write_concept(data):
    concept_title = data["title"]
    CONCEPTS_DIR.mkdir(parents=True, exist_ok=True)

    # 0a. 入库判断
    if data.get("is_concept") is False:
        return {"status": "skipped", "reason": "is_concept=false — not a tradable concept"}

    # 0b. 已有 concept 检查
    existing_override = data.get("existing_concept")
    if existing_override:
        return {
            "status": "update_needed",
            "message": f"Related concept '{existing_override}' already exists. Consider updating it instead.",
            "existing_file": str(CONCEPTS_DIR / f"{safe_concept_filename(existing_override)}.md"),
        }

    # 0c. 已有 source 检查
    existing_source = data.get("existing_source", "")
    if existing_source:
        existing_sources = list_existing_sources()
        if existing_source not in existing_sources:
            existing_source = ""  # 声称的 source 不存在，回退

    # 1. 去重
    if check_duplicate(concept_title):
        return {"status": "duplicate", "message": f"'{concept_title}' already exists"}

    # 2. 加载映射
    name_map = load_all_name_map()

    # 3. 解析公司
    companies = normalize_companies(data.get("companies", []))
    company_names = extract_company_names(companies)
    ticker_map = resolve_tickers(company_names, name_map)

    code_name = load_code_to_name(name_map, ticker_map)
    ct_map = load_concept_frontmatter_tickers()

    # 4. 匹配概念
    candidates = data.get("related_concepts", [])
    matched = find_existing_concepts(candidates)

    # 5. 关系
    rel_input = data.get("relationships", {})
    linked_rels = {c: rel_input.get(c, "相关") for c in matched}

    # 6. 交叉对比
    new_codes = [v for v in ticker_map.values() if v]
    cross = cross_compare(new_codes, linked_rels, ct_map, code_name)

    # 7. 生成
    data["existing_source"] = existing_source  # 回写归一化后的值
    frontmatter = build_frontmatter(data, ticker_map)
    body = build_body(data, companies, ticker_map, matched, cross)
    full_content = frontmatter + "\n\n" + body + "\n"

    filepath = CONCEPTS_DIR / f"{safe_concept_filename(concept_title)}.md"
    tmp_path = filepath.with_suffix(filepath.suffix + ".tmp")
    tmp_path.write_text(full_content, encoding="utf-8")
    tmp_path.replace(filepath)

    graph_files = update_concept_graph(
        concept_title,
        source_name=data.get("source_name") or data.get("existing_source", ""),
        source_date=data.get("source_date", ""),
        parent_concepts=data.get("parent_concepts", []),
        related_concepts=matched,
        relationships=linked_rels,
        supply_chain=data.get("supply_chain_layers", {}),
        companies=companies,
        ticker_map=ticker_map,
        evidence=data.get("evidence") or data.get("core_thesis", ""),
        confidence=data.get("confidence", "medium"),
        aliases=data.get("aliases", []),
    )

    # 8. 报告
    pure_new_codes = set(new_codes)
    for cr in cross:
        pure_new_codes -= {code for _, code in cr["overlap"]}

    return {
        "status": "created",
        "file": str(filepath),
        "tickers_found": {k: v for k, v in ticker_map.items() if v},
        "tickers_missing": [k for k, v in ticker_map.items() if not v],
        "concepts_linked": matched,
        "concepts_not_found": [c for c in candidates if c not in matched],
        "cross_comparison": {
            cr["concept"]: {
                "关系": cr["relationship"],
                "重合": len(cr["overlap"]),
                "新独有": len(cr["new_only"]),
                "对方独有": len(cr["other_only"]),
            }
            for cr in cross
        },
        "pure_new_stocks": len(pure_new_codes),
        "graph_files": graph_files,
    }


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════

def main():
    if sys.stdin.isatty():
        print("Usage: python3 concept_writer.py <<'JSON'\n{...}\nJSON", file=sys.stderr)
        sys.exit(1)
    raw = sys.stdin.read()
    data = json.loads(raw)
    result = write_concept(data)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
