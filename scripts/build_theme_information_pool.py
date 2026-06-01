#!/usr/bin/env python3
"""
Build a neutral theme information pool from Markdown exports.

Use case: theme radar information parity, not fact audit.
- Keep broad/weak information; mark lower specificity/display weight.
- Focus on theme, marginal change, segment, and upstream/downstream relations.
- Does not write entities, relations, or knowledge-base files.
"""
import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

CHAIN_HEADERS = {"环节名称", "相关公司", "公司证券代码", "证据摘要"}
SOURCE_HEADERS = {"来源标题", "来源类型", "发布方", "日期"}
QUESTION_HEADERS = {"问题", "涉及公司", "优先级"}


def sha_id(*parts: str) -> str:
    raw = "|".join(str(p or "") for p in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def clean_text(value: str) -> str:
    s = str(value or "").strip()
    s = re.sub(r"<br\s*/?>", "；", s)
    s = re.sub(r"\*\*(.*?)\*\*", r"\1", s)
    return s.strip()


def split_md_row(line: str) -> list[str]:
    return [clean_text(c) for c in line.strip().strip("|").split("|")]


def is_separator(line: str) -> bool:
    cells = split_md_row(line)
    return bool(cells) and all(re.fullmatch(r":?-{2,}:?", c.strip()) for c in cells)


def parse_theme(text: str, fallback: str) -> str:
    def normalize_title(title: str) -> str:
        title = re.sub(r"^[🎯\s]+", "", title).strip()
        title = re.sub(r"(?:_)?题材雷达数据抽取$", "", title).strip()
        title = re.sub(r"题材\s*Deep\s*Dive\s*数据抽取报告$", "", title).strip()
        title = re.sub(r"\s*Deep\s*Dive\s*数据抽取报告$", "", title).strip()
        title = re.sub(r"_?DeepDive_\d{8}$", "", title).strip()
        title = re.sub(r"_?Deep_Dive数据抽取$", "", title).strip()
        title = re.sub(r"[\s—–-]+$", "", title).strip()
        title = re.sub(r"[\s—–-]*金融$", "", title).strip()
        title = re.sub(r"\s+", "", title)
        return title
    for line in text.splitlines():
        if line.startswith("# "):
            title = line.lstrip("#").strip()
            title = normalize_title(title)
            for sep in (" — ", "—", "-", "：", ":"):
                if sep in title:
                    return title.split(sep, 1)[0].strip() or fallback
            return title or fallback
        if "Deep Dive 数据抽取报告" in line:
            title = normalize_title(line.split("·", 1)[0])
            return title or normalize_title(fallback)
    return normalize_title(fallback)


def parse_markdown_tables(text: str) -> list[dict]:
    lines = text.splitlines()
    tables = []
    section = ""
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("#"):
            section = line.lstrip("#").strip()
            i += 1
            continue
        if line.strip().startswith("|") and i + 1 < len(lines) and is_separator(lines[i + 1]):
            headers = split_md_row(line)
            rows = []
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = split_md_row(lines[i])
                row = {headers[j]: cells[j] if j < len(cells) else "" for j in range(len(headers))}
                rows.append({"line_no": i + 1, "row": row})
                i += 1
            tables.append({"section": section, "headers": headers, "rows": rows})
            continue
        i += 1
    return tables


def parse_tsv_tables(text: str) -> list[dict]:
    lines = text.splitlines()
    tables = []
    section = ""
    i = 0
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if s and "\t" not in s and re.match(r"^(?:\d+(?:\.\d+)?\.|📋)", s):
            section = s
            i += 1
            continue
        if "\t" in line:
            headers = [clean_text(x) for x in line.split("\t")]
            rows = []
            i += 1
            while i < len(lines) and "\t" in lines[i]:
                cells = [clean_text(x) for x in lines[i].split("\t")]
                row = {headers[j]: cells[j] if j < len(cells) else "" for j in range(len(headers))}
                rows.append({"line_no": i + 1, "row": row})
                i += 1
            tables.append({"section": section, "headers": headers, "rows": rows})
            continue
        i += 1
    return tables


def parse_bullet_field_sections(text: str) -> list[dict]:
    lines = text.splitlines()
    sections = []
    current = None
    for i, line in enumerate(lines, 1):
        if line.startswith("## 公司：") or line.startswith("公司："):
            if current and current["rows"]:
                sections.append(current)
            current = {"section": line.lstrip("#").strip().replace("公司：", "", 1), "line_no": i, "rows": []}
            continue
        if line.startswith("#") or re.match(r"^\d+(?:\.\d+)?\.", line.strip()):
            if current and current["rows"]:
                sections.append(current)
            current = None
            continue
        if current:
            m = re.match(r"^-\s*\*\*(.+?)\*\*[：:]\s*(.*)$", line.strip())
            if not m:
                m = re.match(r"^([^：:\t]{2,40})[：:]\s*(.*)$", line.strip())
            if m:
                current["rows"].append({"line_no": i, "row": {"字段": clean_text(m.group(1)), "内容": clean_text(m.group(2))}})
    if current and current["rows"]:
        sections.append(current)
    return sections


def parse_plain_theme_anchor(text: str):
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if "题材定锚" in line and re.match(r"^\s*#?\s*1\.", line.strip()):
            start = i
            break
    if start is None:
        return None
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if re.match(r"^\s*#?\s*2\.", lines[j].strip()):
            end = j
            break
    section_lines = lines[start:end]
    wanted = {"核心定义", "一句话定锚", "题材边界"}
    data = {}
    i = 1
    while i < len(section_lines):
        key = section_lines[i].strip()
        if key in wanted:
            j = i + 1
            while j < len(section_lines) and not section_lines[j].strip():
                j += 1
            if j < len(section_lines):
                data[key] = clean_text(section_lines[j])
            i = j
        elif key.startswith("来源"):
            for part in key.split("|"):
                if ":" in part:
                    k, v = part.split(":", 1)
                    data[clean_text(k)] = clean_text(v)
        i += 1
    if not data.get("一句话定锚") and not data.get("核心定义"):
        return None
    rows = [{"line_no": start + 1, "row": {"字段": k, "内容": v}} for k, v in data.items()]
    return {"section": clean_text(section_lines[0]), "line_no": start + 1, "rows": rows}


def parse_jsonl_records(text: str) -> tuple[list[dict], list[str]]:
    records, errors = [], []
    for line_no, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if s.startswith("{") and s.endswith("}"):
            try:
                records.append({"line_no": line_no, "record": json.loads(s)})
            except json.JSONDecodeError as exc:
                errors.append(f"line {line_no}: {exc}")
    return records, errors


def normalize_confidence(v: str) -> str:
    v = str(v or "").strip().lower()
    if v.startswith(("高", "high")):
        return "high"
    if v.startswith(("中", "medium")) or "低~中" in v or "中~低" in v:
        return "medium"
    if v.startswith(("低", "low")):
        return "low"
    return "unknown"


def bool_like(v):
    if isinstance(v, bool):
        return v
    s = str(v or "").strip().lower()
    if s in {"是", "true", "yes", "1"}:
        return True
    if s in {"否", "false", "no", "0"}:
        return False
    if s.startswith("是"):
        return True
    if s.startswith("否"):
        return False
    return None


def split_values(value: str) -> list[str]:
    s = clean_text(value)
    if not s or s in {"—", "-", "无", "unknown"}:
        return []
    out = []
    for x in re.split(r"[、,，/；;]+", s):
        item = re.sub(r"^[^：:]{1,12}[：:]", "", x.strip()).strip()
        item = re.sub(r"等$", "", item).strip()
        if item:
            out.append(item)
    return out


def split_inline_ticker(name: str) -> tuple[str, str]:
    s = re.sub(r"[（(](?:CXMT|未上市|非A股|[^）)]*IPO[^）)]*)[）)]", "", str(name or "").strip()).strip()
    m = re.match(r"^(.+?)[（(]([0-9A-Za-z.]+)(?:[，,].*)?[）)]$", s)
    if not m:
        return s, ""
    return m.group(1).strip(), m.group(2).strip()


def entity_pairs(names: str, tickers: str) -> list[tuple[str, str]]:
    ns = split_values(names)
    ts = split_values(tickers)
    if not ns:
        return [("", "")]
    out = []
    for idx, raw_name in enumerate(ns):
        name, inline_ticker = split_inline_ticker(raw_name)
        ticker = ts[idx] if idx < len(ts) else (ts[0] if len(ts) == 1 and len(ns) == 1 else inline_ticker)
        out.append((name, ticker))
    return out


def field_map(row_entries: list[dict]) -> dict:
    out = {}
    for entry in row_entries:
        row = entry["row"]
        key = clean_text(row.get("字段", ""))
        if key:
            out[key] = clean_text(row.get("内容", ""))
    return out


def backfill_tickers(items: list[dict]) -> None:
    name_to_ticker = {}
    for item in items:
        name = str(item.get("entity_name") or "").strip()
        ticker = str(item.get("ticker") or "").strip()
        if name and ticker and ticker not in {"—", "-", "unknown"}:
            name_to_ticker.setdefault(name, ticker)
    for item in items:
        name = str(item.get("entity_name") or "").strip()
        if name and not str(item.get("ticker") or "").strip() and name in name_to_ticker:
            item["ticker"] = name_to_ticker[name]


def deep_source_type(source: str) -> str:
    source = source or ""
    if "公告" in source or "互动易" in source:
        return "公告/互动易"
    return infer_source_type(source) or "研报/资料"


def infer_source_type(title: str) -> str:
    s = title or ""
    if "专家" in s or "调研" in s:
        return "调研/专家会"
    if "研报" in s or "证券" in s or "通信" in s or "机械" in s:
        return "研报"
    if "半年报" in s or "年报" in s:
        return "定期报告"
    if "网页" in s:
        return "网页"
    return ""


def infer_info_types(claim: str, segment: str = "", entity: str = "") -> list[str]:
    text = " ".join([claim or "", segment or "", entity or ""])
    types = []
    if re.search(r"涨价|缺口|紧缺|放量|上修|扩产|产能|同比|增长|提升|送样|量产|订单|份额|毛利率|营收|净利", text):
        types.append("marginal_change")
    if re.search(r"供应|客户|合作|绑定|进入.*链|供货|采购|代工|收购", text):
        types.append("relationship")
    if re.search(r"行业|需求|市场空间|路线|CPO|OCS|1\.6T|800G|3\.2T", text):
        types.append("theme_driver")
    if not types:
        types.append("segment_mapping")
    return types


def infer_specificity(claim: str, entity: str = "", ticker: str = "") -> str:
    text = claim or ""
    score = 0
    if entity:
        score += 1
    if ticker and ticker not in {"未知", "unknown", ""}:
        score += 1
    if re.search(r"\d", text):
        score += 2
    if re.search(r"量产|送样|订单|产能|份额|涨价|同比|毛利率|营收|净利|客户|供应链|收购|扩产", text):
        score += 2
    if len(text) >= 28:
        score += 1
    if score >= 5:
        return "high"
    if score >= 3:
        return "medium"
    return "low"


def display_weight(specificity: str) -> str:
    return "low" if specificity == "low" else "normal"


def make_item(
    meta: dict,
    *,
    entity: str = "",
    ticker: str = "",
    chain_position: str = "",
    segment: str = "",
    component: str = "",
    claim: str = "",
    info_types=None,
    primary_info_type: str = "",
    source_title: str = "",
    source_type: str = "",
    source_date: str = "",
    confidence_raw: str = "",
    needs_review_raw=None,
    evidence_level: str = "",
    suggested_use: str = "",
    risk_note: str = "",
    source_record_type: str = "markdown_table",
    raw_row=None,
) -> dict:
    info_types = info_types or infer_info_types(claim, segment, entity)
    primary_info_type = primary_info_type or info_types[0]
    specificity = infer_specificity(claim, entity, ticker)
    return {
        "item_id": sha_id(meta["theme"], entity, ticker, segment, claim, meta["line_no"], source_record_type),
        "theme": meta["theme"],
        "entity_name": entity,
        "ticker": ticker,
        "chain_position": chain_position,
        "segment": segment,
        "component": component,
        "claim": claim,
        "info_types": info_types,
        "primary_info_type": primary_info_type,
        "specificity": specificity,
        "display_weight": display_weight(specificity),
        "source_systems": [meta["source_system"]],
        "source_refs": [{
            "system": meta["source_system"],
            "path": meta["source_file"],
            "section": meta.get("section", ""),
            "line_no": meta["line_no"],
            "source_title": source_title,
            "source_type": source_type,
            "source_date": source_date,
        }],
        "source_title": source_title,
        "source_type": source_type,
        "source_date": source_date,
        "confidence_raw": confidence_raw,
        "confidence": normalize_confidence(confidence_raw),
        "needs_review_raw": needs_review_raw,
        "needs_review": bool_like(needs_review_raw),
        "evidence_level": evidence_level,
        "suggested_use": suggested_use,
        "risk_note": risk_note,
        "source_record_type": source_record_type,
        "raw_row": raw_row or {},
    }


def item_from_chain_row(row: dict, meta: dict) -> dict:
    entity = row.get("相关公司", "")
    ticker = row.get("公司证券代码", "")
    segment = row.get("环节名称", "")
    component = row.get("关键材料/零部件/设备/软件", "")
    claim = row.get("证据摘要", "")
    src = row.get("来源", "")
    date = row.get("时间", "")
    specificity = infer_specificity(claim, entity, ticker)
    info_types = infer_info_types(claim, segment, entity)
    return {
        "item_id": sha_id(meta["theme"], entity, ticker, segment, claim, meta["line_no"]),
        "theme": meta["theme"],
        "entity_name": entity,
        "ticker": ticker,
        "chain_position": meta["section"],
        "segment": segment,
        "component": component,
        "claim": claim,
        "info_types": info_types,
        "primary_info_type": info_types[0],
        "specificity": specificity,
        "display_weight": display_weight(specificity),
        "source_systems": [meta["source_system"]],
        "source_refs": [{
            "system": meta["source_system"],
            "path": meta["source_file"],
            "section": meta["section"],
            "line_no": meta["line_no"],
            "source_title": src,
            "source_type": infer_source_type(src),
            "source_date": date,
        }],
        "source_title": src,
        "source_type": infer_source_type(src),
        "source_date": date,
        "confidence_raw": row.get("可信度", ""),
        "confidence": normalize_confidence(row.get("可信度", "")),
        "needs_review_raw": row.get("是否需要人工核验", ""),
        "needs_review": bool_like(row.get("是否需要人工核验", "")),
        "source_record_type": "markdown_table",
        "raw_row": row,
    }


def items_from_catalyst_row(row: dict, meta: dict) -> list[dict]:
    claim = row.get("具体内容", "")
    segment = row.get("影响的产业链环节", "") or row.get("影响产业链环节", "") or row.get("影响环节", "")
    source_title = row.get("来源", "")
    return [
        make_item(
            meta,
            entity=entity,
            ticker=ticker,
            chain_position=segment,
            segment=segment,
            claim=claim,
            info_types=["theme_driver", "marginal_change"],
            primary_info_type="marginal_change",
            source_title=source_title,
            source_type=deep_source_type(source_title),
            source_date=row.get("时间窗口", ""),
            confidence_raw=row.get("可信度", ""),
            needs_review_raw=row.get("needs_review", "") or row.get("需核验", "") or row.get("是否需要人工核验", ""),
            evidence_level="curated_research",
            suggested_use="deep_dive",
            source_record_type="deep_dive_catalyst",
            raw_row=row,
        )
        for entity, ticker in entity_pairs(row.get("相关公司", ""), "")
    ]


def items_from_catalyst_field_table(rows: list[dict], meta: dict) -> list[dict]:
    return items_from_catalyst_row(field_map(rows), meta)


def items_from_chain_path_row(row: dict, meta: dict) -> list[dict]:
    claim = "；".join(x for x in [row.get("传导路径", ""), row.get("瓶颈或价值量", "") or row.get("瓶颈/价值量", ""), row.get("下游驱动", "")] if x)
    segment = row.get("对应环节", "")
    component = row.get("关键材料/零部件/设备/软件/工艺", "") or row.get("关键材料/零部件/设备/软件", "") or row.get("关键材料/设备", "")
    source_title = row.get("来源", "")
    ticker_raw = row.get("证券代码", "") or row.get("代码", "")
    needs_review_raw = row.get("needs_review", "") or row.get("需核验", "") or row.get("是否需要人工核验", "")
    return [
        make_item(
            meta,
            entity=entity,
            ticker=ticker,
            chain_position=segment,
            segment=segment,
            component=component,
            claim=claim,
            info_types=["segment_mapping", "theme_driver"],
            primary_info_type="segment_mapping",
            source_title=source_title,
            source_type=deep_source_type(source_title),
            source_date=row.get("时间", ""),
            confidence_raw=row.get("可信度", ""),
            needs_review_raw=needs_review_raw,
            evidence_level="curated_research",
            suggested_use="deep_dive",
            source_record_type="deep_dive_chain_path",
            raw_row=row,
        )
        for entity, ticker in entity_pairs(row.get("代表公司", ""), ticker_raw)
    ]


def items_from_chain_path_field_table(rows: list[dict], meta: dict) -> list[dict]:
    return items_from_chain_path_row(field_map(rows), meta)


def items_from_subdirection_row(row: dict, meta: dict) -> list[dict]:
    segment = row.get("细分方向", "")
    claim = "；".join(x for x in [row.get("为什么重要", ""), row.get("关键证据", ""), row.get("下一步验证", "")] if x)
    source_title = row.get("来源", "")
    chain_position = row.get("所属产业链环节", "") or row.get("产业链环节", "")
    ticker_raw = row.get("证券代码", "") or row.get("代码", "")
    needs_review_raw = row.get("needs_review", "") or row.get("需核验", "") or row.get("是否需要人工核验", "")
    return [
        make_item(
            meta,
            entity=entity,
            ticker=ticker,
            chain_position=chain_position,
            segment=segment,
            claim=claim,
            info_types=["segment_mapping", "relationship"],
            primary_info_type="segment_mapping",
            source_title=source_title,
            source_type=deep_source_type(source_title),
            source_date=row.get("时间", ""),
            confidence_raw=row.get("可信度", ""),
            needs_review_raw=needs_review_raw,
            evidence_level="curated_research",
            suggested_use="deep_dive",
            source_record_type="deep_dive_subdirection",
            raw_row=row,
        )
        for entity, ticker in entity_pairs(row.get("代表公司", ""), ticker_raw)
    ]


def item_from_company_field_table(section: str, rows: list[dict], meta: dict):
    m = re.match(r"(.+?)（([^）]+)）$", section.strip())
    if not m:
        return None
    data = field_map(rows)
    claim = data.get("题材相关性一句话", "")
    if not claim:
        return None
    source_title = data.get("证据来源", "")
    evidence_raw = data.get("题材暴露类型", "")
    if "hard_fact" in evidence_raw:
        evidence_level = "hard_fact_candidate"
    elif "exposure_only" in evidence_raw:
        evidence_level = "exposure_only"
    elif "review" in evidence_raw:
        evidence_level = "review_candidate"
    else:
        evidence_level = "curated_research"
    return make_item(
        meta,
        entity=m.group(1).strip(),
        ticker=m.group(2).strip(),
        chain_position=data.get("所属产业链环节", ""),
        segment=data.get("对应细分方向", "") or data.get("所属产业链环节", ""),
        component=data.get("相关产品/技术/服务", ""),
        claim=claim,
        info_types=infer_info_types(" ".join([claim, data.get("原文摘录", "")]), data.get("对应细分方向", ""), m.group(1)),
        primary_info_type="segment_mapping",
        source_title=source_title,
        source_type=deep_source_type(source_title),
        source_date=data.get("证据日期", ""),
        confidence_raw=data.get("可信度", ""),
        needs_review_raw="true" if data.get("是否建议进入entities/*.md") != "是" else data.get("是否建议进入entities/*.md"),
        evidence_level=evidence_level,
        suggested_use="deep_dive" if data.get("是否建议进入Deep Dive") == "是" else "theme_radar",
        risk_note=data.get("风险提示", ""),
        source_record_type="deep_dive_company_mapping",
        raw_row=data,
    )


def item_from_theme_anchor_table(rows: list[dict], meta: dict):
    data = field_map(rows)
    claim = data.get("一句话定锚", "") or data.get("核心定义", "")
    if not claim:
        return None
    source_title = data.get("来源", "")
    return make_item(
        meta,
        segment="题材定锚",
        claim=claim,
        info_types=["theme_anchor", "theme_driver"],
        primary_info_type="theme_anchor",
        source_title=source_title,
        source_type=deep_source_type(source_title),
        source_date=data.get("时间", ""),
        confidence_raw=data.get("可信度", ""),
        needs_review_raw=data.get("是否需要人工核验", ""),
        evidence_level="curated_research",
        suggested_use="deep_dive",
        risk_note=data.get("排除项", ""),
        source_record_type="deep_dive_theme_anchor",
        raw_row=data,
    )


def item_from_watchlist_row(row: dict, meta: dict) -> dict:
    return make_item(
        meta,
        entity=row.get("公司", ""),
        ticker=row.get("代码", ""),
        chain_position=row.get("环节", ""),
        segment=row.get("环节", ""),
        claim=row.get("原因", ""),
        info_types=[row.get("暴露类型", "") or "exposure_only"],
        primary_info_type=row.get("暴露类型", "") or "exposure_only",
        confidence_raw="低",
        needs_review_raw=True,
        evidence_level=row.get("暴露类型", "") or "exposure_only",
        suggested_use="watchlist_only",
        risk_note=row.get("原因", ""),
        source_record_type="deep_dive_watchlist",
        raw_row=row,
    )


def item_from_marginal_row(row: dict, meta: dict) -> dict:
    source_title = row.get("来源", "")
    hard_raw = row.get("是否为公司级硬边际", "") or row.get("是否为硬边际", "")
    ticker = row.get("证券代码", "") or row.get("代码", "")
    return make_item(
        meta,
        entity=row.get("公司", ""),
        ticker=ticker,
        chain_position=row.get("所属环节", ""),
        segment=row.get("所属环节", ""),
        claim=row.get("具体内容", ""),
        info_types=["marginal_change"],
        primary_info_type="marginal_change",
        source_title=source_title,
        source_type=deep_source_type(source_title),
        source_date=row.get("时间窗口", ""),
        confidence_raw="中" if hard_raw == "是" else "低",
        needs_review_raw=row.get("建议进入entity delta", ""),
        evidence_level="review_candidate" if hard_raw != "是" else "hard_fact_candidate",
        suggested_use="deep_dive",
        risk_note="" if hard_raw == "是" else "边际变化来源需核验",
        source_record_type="deep_dive_marginal_change",
        raw_row=row,
    )


def item_from_hard_fact_row(row: dict, meta: dict) -> dict:
    source_title = row.get("来源", "")
    ticker = row.get("证券代码", "") or row.get("代码", "")
    return make_item(
        meta,
        entity=row.get("公司", ""),
        ticker=ticker,
        segment=row.get("事实类型", ""),
        claim=row.get("事实内容", ""),
        info_types=["relationship", "marginal_change"],
        primary_info_type="relationship",
        source_title=source_title,
        source_type=deep_source_type(source_title),
        source_date=row.get("时间", ""),
        confidence_raw="中",
        needs_review_raw=row.get("是否仍需人工核验", "") or row.get("仍需人工核验", ""),
        evidence_level="hard_fact_candidate",
        suggested_use="entity_delta_candidate",
        source_record_type="deep_dive_hard_fact_candidate",
        raw_row=row,
    )


def item_from_exposure_row(row: dict, meta: dict) -> dict:
    source_title = row.get("来源", "")
    level = row.get("建议evidence_level", "") or "exposure_only"
    ticker = row.get("证券代码", "") or row.get("代码", "")
    return make_item(
        meta,
        entity=row.get("公司", ""),
        ticker=ticker,
        claim=row.get("线索内容", ""),
        info_types=[level],
        primary_info_type=level,
        source_title=source_title,
        source_type=deep_source_type(source_title),
        source_date=row.get("时间", ""),
        confidence_raw="低" if level in {"review_candidate", "exposure_only"} else "中",
        needs_review_raw=True,
        evidence_level=level,
        suggested_use="theme_radar" if row.get("建议进入Theme Radar") == "是" else "watchlist_only",
        risk_note=row.get("为什么不能直接作为hard_fact", "") or row.get("为什么不能作为hard_fact", ""),
        source_record_type="deep_dive_exposure_line",
        raw_row=row,
    )


def item_from_jsonl(rec: dict, meta: dict) -> dict:
    entity = rec.get("entity_name", "")
    ticker = rec.get("ticker", "")
    chain_position = rec.get("chain_position") or ""
    segment = rec.get("segment") or rec.get("chain_segment") or rec.get("sub_theme") or ""
    component = rec.get("component") or rec.get("sub_theme") or ""
    claim = rec.get("claim", "")
    specificity = infer_specificity(claim, entity, ticker)
    info_types = rec.get("info_types") or infer_info_types(claim, segment, entity)
    primary_info_type = rec.get("primary_info_type") or info_types[0]
    system = rec.get("source_system") or meta["source_system"]
    return {
        "item_id": sha_id(meta["theme"], entity, ticker, segment, claim, meta["line_no"]),
        "theme": rec.get("theme") or meta["theme"],
        "entity_name": entity,
        "ticker": ticker,
        "chain_position": chain_position,
        "segment": segment,
        "component": component,
        "claim": claim,
        "info_types": info_types,
        "primary_info_type": primary_info_type,
        "specificity": specificity,
        "display_weight": display_weight(specificity),
        "source_systems": [system],
        "source_refs": [{
            "system": system,
            "path": meta["source_file"],
            "section": "JSONL 附录",
            "line_no": meta["line_no"],
            "source_title": rec.get("source_title", ""),
            "source_type": rec.get("source_type", ""),
            "source_date": rec.get("source_date", ""),
        }],
        "source_title": rec.get("source_title", ""),
        "source_type": rec.get("source_type", ""),
        "source_date": rec.get("source_date", ""),
        "confidence_raw": rec.get("confidence", ""),
        "confidence": normalize_confidence(rec.get("confidence", "")),
        "needs_review_raw": rec.get("needs_review"),
        "needs_review": bool_like(rec.get("needs_review")),
        "evidence_level": rec.get("evidence_level", ""),
        "suggested_use": rec.get("suggested_use", ""),
        "risk_note": rec.get("risk_note", ""),
        "source_record_type": "jsonl_appendix",
        "raw_record": rec,
    }


def source_from_row(row: dict, meta: dict) -> dict:
    title = row.get("来源标题", "")
    return {
        "source_id": sha_id(meta["theme"], title, row.get("日期", ""), row.get("URL或可追溯标识", "")),
        "theme": meta["theme"],
        "source_system": meta["source_system"],
        "source_title": title,
        "source_type": row.get("来源类型", ""),
        "publisher": row.get("发布方", ""),
        "source_date": row.get("日期", ""),
        "source_ref": row.get("URL或可追溯标识", ""),
        "related_entities": row.get("涉及公司", ""),
        "related_theme": row.get("涉及主题", ""),
        "confidence_raw": row.get("可信度", ""),
        "confidence": normalize_confidence(row.get("可信度", "")),
        "note": row.get("备注", ""),
        "path": meta["source_file"],
        "section": meta["section"],
        "line_no": meta["line_no"],
    }


def question_from_row(row: dict, meta: dict) -> dict:
    q = row.get("问题", "")
    return {
        "question_id": sha_id(meta["theme"], q, row.get("涉及公司", ""), meta["line_no"]),
        "theme": meta["theme"],
        "source_system": meta["source_system"],
        "question": q,
        "related_entities": row.get("涉及公司", ""),
        "related_sources": row.get("涉及来源", ""),
        "priority_raw": row.get("优先级", ""),
        "suggested_check_path": row.get("建议核验路径", ""),
        "path": meta["source_file"],
        "section": meta["section"],
        "line_no": meta["line_no"],
    }


def extract_theme_definition(text: str, theme: str, path: str, source_system: str) -> dict:
    notes = []
    in_def = False
    for i, line in enumerate(text.splitlines(), 1):
        if line.startswith("# 1."):
            in_def = True
        elif in_def and line.startswith("# 2."):
            break
        if in_def and line.strip() and not line.strip().startswith("---"):
            notes.append({"line_no": i, "text": line.strip()})
    return {"theme": theme, "source_system": source_system, "source_file": path, "notes": notes}


def build_outputs(path: Path, source_system: str) -> tuple[dict, list[str]]:
    text = path.read_text(encoding="utf-8")
    theme = parse_theme(text, path.stem)
    items, sources, questions, errors = [], [], [], []

    for table in parse_markdown_tables(text) + parse_tsv_tables(text):
        headers = set(table["headers"])
        for r in table["rows"]:
            meta = {"theme": theme, "source_system": source_system, "source_file": str(path), "section": table["section"], "line_no": r["line_no"]}
            if CHAIN_HEADERS.issubset(headers):
                items.append(item_from_chain_row(r["row"], meta))
            elif {"催化类型", "具体内容", "相关公司"}.issubset(headers) and ("影响的产业链环节" in headers or "影响产业链环节" in headers or "影响环节" in headers):
                items.extend(items_from_catalyst_row(r["row"], meta))
            elif {"起点", "传导路径", "对应环节", "代表公司"}.issubset(headers) and ("证券代码" in headers or "代码" in headers):
                items.extend(items_from_chain_path_row(r["row"], meta))
            elif {"细分方向", "为什么重要", "代表公司"}.issubset(headers) and ("证券代码" in headers or "代码" in headers) and ("所属产业链环节" in headers or "产业链环节" in headers):
                items.extend(items_from_subdirection_row(r["row"], meta))
            elif {"公司", "代码", "环节", "原因", "暴露类型"}.issubset(headers):
                items.append(item_from_watchlist_row(r["row"], meta))
            elif {"公司", "所属环节", "具体内容"}.issubset(headers) and ("证券代码" in headers or "代码" in headers) and ("边际变化类型" in headers or "变化类型" in headers):
                items.append(item_from_marginal_row(r["row"], meta))
            elif {"公司", "事实类型", "事实内容"}.issubset(headers) and ("证券代码" in headers or "代码" in headers):
                items.append(item_from_hard_fact_row(r["row"], meta))
            elif {"公司", "线索内容", "建议evidence_level"}.issubset(headers) and ("证券代码" in headers or "代码" in headers):
                items.append(item_from_exposure_row(r["row"], meta))
            elif headers == {"字段", "内容"}:
                data = field_map(table["rows"])
                if "题材定锚" in table["section"]:
                    item = item_from_theme_anchor_table(table["rows"], meta)
                    if item:
                        items.append(item)
                        break
                elif {"具体内容", "相关公司"}.issubset(data) and ("影响的产业链环节" in data or "影响产业链环节" in data or "影响环节" in data):
                    items.extend(items_from_catalyst_field_table(table["rows"], meta))
                    break
                elif {"起点", "传导路径", "对应环节", "代表公司"}.issubset(data) and ("证券代码" in data or "代码" in data):
                    items.extend(items_from_chain_path_field_table(table["rows"], meta))
                    break
                elif {"细分方向", "为什么重要", "代表公司"}.issubset(data) and ("所属产业链环节" in data or "产业链环节" in data):
                    items.extend(items_from_subdirection_row(data, meta))
                    break
                item = item_from_company_field_table(table["section"], table["rows"], meta)
                if item:
                    items.append(item)
                    break
            elif SOURCE_HEADERS.issubset(headers):
                sources.append(source_from_row(r["row"], meta))
            elif QUESTION_HEADERS.issubset(headers):
                questions.append(question_from_row(r["row"], meta))

    for section in parse_bullet_field_sections(text):
        meta = {"theme": theme, "source_system": source_system, "source_file": str(path), "section": section["section"], "line_no": section["line_no"]}
        item = item_from_company_field_table(section["section"], section["rows"], meta)
        if item:
            items.append(item)

    anchor_section = parse_plain_theme_anchor(text)
    if anchor_section:
        meta = {"theme": theme, "source_system": source_system, "source_file": str(path), "section": anchor_section["section"], "line_no": anchor_section["line_no"]}
        item = item_from_theme_anchor_table(anchor_section["rows"], meta)
        if item and not any(x.get("source_record_type") == "deep_dive_theme_anchor" for x in items):
            items.append(item)

    jsonl_records, jsonl_errors = parse_jsonl_records(text)
    errors.extend(jsonl_errors)
    for r in jsonl_records:
        meta = {"theme": theme, "source_system": source_system, "source_file": str(path), "line_no": r["line_no"]}
        items.append(item_from_jsonl(r["record"], meta))

    backfill_tickers(items)
    definition = extract_theme_definition(text, theme, str(path), source_system)
    summary = {
        "theme": theme,
        "source_file": str(path),
        "item_count": len(items),
        "source_count": len(sources),
        "review_question_count": len(questions),
        "definition_note_count": len(definition["notes"]),
        "items_by_record_type": dict(Counter(i["source_record_type"] for i in items)),
        "items_by_specificity": dict(Counter(i["specificity"] for i in items)),
        "items_by_primary_info_type": dict(Counter(i["primary_info_type"] for i in items)),
        "items_by_display_weight": dict(Counter(i["display_weight"] for i in items)),
        "unique_entity_count": len({i.get("entity_name") for i in items if i.get("entity_name")}),
        "top_segments": dict(Counter(i.get("segment", "") for i in items).most_common(20)),
        "safety_statement": "Theme information pool only. No entity/relation/knowledge-base writeback.",
    }
    return {"summary": summary, "items": items, "sources": sources, "review_questions": questions, "definition": definition}, errors


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build theme information pool from Markdown")
    parser.add_argument("markdown")
    parser.add_argument("--source-system", default="IMA")
    parser.add_argument("--out-dir", default="")
    args = parser.parse_args()

    path = Path(args.markdown).expanduser()
    if not path.exists():
        print(f"[ERR] file not found: {path}", file=sys.stderr)
        return 1

    outputs, errors = build_outputs(path, args.source_system)
    for err in errors:
        print(f"[WARN] {err}", file=sys.stderr)
    print(json.dumps(outputs["summary"], ensure_ascii=False, indent=2))

    if args.out_dir:
        out = Path(args.out_dir).expanduser()
        stem = path.stem
        write_jsonl(out / f"{stem}.theme_information_items.jsonl", outputs["items"])
        write_jsonl(out / f"{stem}.source_registry.jsonl", outputs["sources"])
        write_jsonl(out / f"{stem}.review_questions.jsonl", outputs["review_questions"])
        write_json(out / f"{stem}.theme_definition.json", outputs["definition"])
        write_json(out / f"{stem}.summary.json", outputs["summary"])
        print(f"[OK] wrote outputs: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
