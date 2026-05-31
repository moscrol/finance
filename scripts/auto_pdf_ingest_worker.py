#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import date
from pathlib import Path

KB = Path("/Users/lbq/Desktop/c c/知识库")
WIKI = KB / "wiki"
FINANCE = Path("/Users/lbq/Desktop/c c/金融")
WRITER = FINANCE / "skills" / "entity-delta-ingest" / "scripts" / "entity_delta_writer.py"

CONCEPT_MAP = [
    (("UFS", "存储", "晶圆", "主控芯片"), ["存储芯片", "AI存储", "先进封装"]),
    (("手套", "丁腈", "PVC", "聚氨酯"), ["医疗器械", "出海"]),
    (("半导体设备", "激光开槽", "激光隐切", "激光划片", "MEMS", "第三代半导体"), ["半导体设备", "激光设备", "第三代半导体"]),
    (("煤焦油", "炭黑", "针状焦", "蒽油", "洗油"), ["精细化工"]),
    (("储能", "液冷", "换热器", "热管理", "冷却模块"), ["热管理", "储能", "液冷服务器"]),
    (("起落架", "大飞机", "刹车盘", "航空", "AS9100"), ["航空航天", "大飞机", "C919大飞机", "军工"]),
    (("算力", "MaaS", "Token", "云", "AIDC"), ["算力服务", "AI服务器", "数据中心"]),
    (("智能驾驶", "智驾", "车载", "ADAS", "座舱"), ["智能驾驶", "汽车电子"]),
]

ROLE_MAP = [
    (("UFS", "存储", "晶圆", "主控芯片"), "存储模组与嵌入式存储产品供应商", "midstream_manufacturing"),
    (("手套", "丁腈", "PVC", "聚氨酯"), "医疗防护手套与医用耗材生产商", "midstream_manufacturing"),
    (("半导体设备", "激光开槽", "激光隐切", "激光划片"), "半导体精密加工与检测设备供应商", "upstream_equipment"),
    (("煤焦油", "炭黑", "针状焦"), "煤焦油深加工和炭黑生产商", "upstream_materials"),
    (("储能", "液冷", "换热器", "热管理"), "热管理与换热设备供应商", "upstream_components"),
    (("起落架", "大飞机", "刹车盘", "航空"), "航空刹车制动与起落架相关产品供应商", "upstream_components"),
]


def infer_report_type(source: str) -> str:
    if "早知道" in source:
        return "market_news"
    if "调研" in source:
        return "ir_research"
    if "脱水" in source and "强势" not in source:
        return "beneficiary_list"
    if "评级日报" in source or "风口研报" in source:
        return "rating_digest"
    if "强势" in source:
        return "core_company_or_theme_review"
    return "unknown"


def clean_text(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"--- OCR CHUNK \d+ ---\n", "", text)
    return text.strip()


def next_log_id() -> int:
    text = (WIKI / "log.md").read_text(encoding="utf-8")
    ids = [int(x) for x in re.findall(r"^### #(\d+) \|", text, re.M)]
    return max(ids) + 1 if ids else 1


def update_index() -> dict[str, int]:
    path = WIKI / "index.md"
    text = path.read_text(encoding="utf-8")
    sources = len(list((WIKI / "sources").glob("*.md")))
    concepts = len(list((WIKI / "concepts").glob("*.md")))
    entities = len(list((WIKI / "entities").glob("*.md")))
    synthesis = len(list((WIKI / "synthesis").glob("*.md")))
    total = sources + concepts + entities + synthesis
    text = re.sub(r"^revision:\s*(\d+)\s*$", lambda m: f"revision: {int(m.group(1)) + 1}", text, count=1, flags=re.M)
    text = re.sub(
        r"\*\*\d+ 页 \| \d+ 个来源 \| \d+ 个概念 \| \d+ 个实体 \| \d+ 个综合分析\*\*",
        f"**{total} 页 | {sources} 个来源 | {concepts} 个概念 | {entities} 个实体 | {synthesis} 个综合分析**",
        text,
        count=1,
    )
    text = re.sub(r"## Sources（\d+个）", f"## Sources（{sources}个）", text, count=1)
    path.write_text(text, encoding="utf-8")
    return {"sources": sources, "concepts": concepts, "entities": entities, "synthesis": synthesis, "total": total}


def append_log(log_id: int, source: str, source_date: str, created: list[str], updated: list[str], key: str) -> None:
    path = WIKI / "log.md"
    text = path.read_text(encoding="utf-8")
    if f"[[{source}]]" in text:
        return
    entry = f"""
### #{log_id:03d} | {date.today().isoformat()} | ingest | {source} PDF ingest

- **trigger**: automated PDF ingest worker
- **source**: [[{source}]]（队列日期 {source_date}）
- **created**: {', '.join(created) if created else '[]'}
- **updated**: {', '.join(updated) if updated else '[]'}
- **key**: {key}
"""
    path.write_text(text.rstrip() + "\n" + entry, encoding="utf-8")


def rewrite_source_log(source: str, log_id: int, label: str) -> None:
    path = WIKI / "sources" / f"{source}.md"
    text = path.read_text(encoding="utf-8")
    text = re.sub(r'^log:\s*\[.*?\]\s*$', f'log: ["#{log_id:03d} {label}"]', text, count=1, flags=re.M)
    path.write_text(text, encoding="utf-8")


def infer_concepts(section: str) -> list[str]:
    concepts: list[str] = []
    for keys, vals in CONCEPT_MAP:
        if any(k in section for k in keys):
            for val in vals:
                if val not in concepts:
                    concepts.append(val)
    return concepts or ["产业观察"]


def infer_role_layer(section: str) -> tuple[str, str]:
    for keys, role, layer in ROLE_MAP:
        if any(k in section for k in keys):
            return role, layer
    return "公司级调研线索待核验", "midstream_manufacturing"


def split_sentences(section: str, limit: int = 5) -> list[str]:
    text = re.sub(r"===== PAGE \d+ =====", "", section)
    text = re.sub(r"【[^】]+】", "", text)
    parts = [p.strip() for p in re.split(r"(?<=[。！？])", text) if p.strip()]
    bullets = []
    for part in parts:
        if len(part) < 8 or "免责声明" in part or "风险提示" in part:
            continue
        bullets.append(part[:180])
        if len(bullets) >= limit:
            break
    return bullets


def truncate_section_tail(section: str) -> str:
    lines = section.splitlines()
    kept = []
    stop_markers = ("研报来源", "免责声明", "风险提示", "相关公司：", "相关公司:", "内容来源")
    for line in lines:
        stripped = line.strip()
        if any(marker in stripped for marker in stop_markers):
            break
        kept.append(line)
    return "\n".join(kept).strip()


def parse_ir_sections(text: str) -> list[dict]:
    lines = clean_text(text).splitlines()
    matches = []
    for idx, line in enumerate(lines):
        m = re.match(r"^([\u4e00-\u9fa5A-Za-z0-9（）()·]{2,20})：(.+)$", line.strip())
        if not m:
            continue
        name = m.group(1).strip()
        if name in {"点评", "内容来源"} or "公司" in name:
            continue
        matches.append((idx, name, m.group(2).strip()))
    sections = []
    for pos, (idx, name, title) in enumerate(matches):
        end = matches[pos + 1][0] if pos + 1 < len(matches) else len(lines)
        block = truncate_section_tail("\n".join([title] + lines[idx + 1:end]).strip())
        if len(block) < 80:
            continue
        sections.append({"company": name, "title": title[:80], "section": block})
    return sections


def write_market_news(source: str, source_date: str, pdf: str, text: str, dry_run: bool) -> dict:
    log_id = next_log_id()
    body = clean_text(text)
    raw = f"""# {source}

来源文件：{pdf}
来源：PDF 自动入库
队列日期：{source_date}
抽取方式：auto extractor

## 摘要

本篇为早知道/市场新闻类材料，包含市场热点、题材观察和公司要闻线索。该类来源按 observation_only_zero_exposure 处理，不作为 Theme Radar 关系图谱或实体事实写入依据。

## 原文摘录

{body[:5000]}

## 入库说明

本篇按 `market_news / observation_only_zero_exposure` 处理。所有公司和题材仅进入观察，不创建实体、不更新实体、不写入 `entity_exposures.json` 或 `evidence_index.json`。
"""
    source_note = f"""---
title: "{source}"
type: source
source_date: {source_date}
tags: [早知道, 市场新闻, 市场观察]
created: {date.today().isoformat()}
updated: {date.today().isoformat()}
revision: 1
sources: []
source_quality: market_news
log: ["#{log_id:03d} created from [[{source}]] PDF ingest — observation_only_zero_exposure"]
---

# {source}

来源：PDF 自动入库
队列日期：{source_date}
类型：市场新闻 / 早知道
质量：market_news
原文：`raw/{source}.md`
抽取：auto extractor

## 概要

本篇为早知道/市场新闻类材料，包含市场热点、题材观察和公司要闻线索。该类来源以市场观察和交易资讯为主，不作为 Theme Radar 关系图谱或实体事实写入依据。

## 观察列表

- 市场热点、题材变化和公司要闻仅作观察。
- 因 source_quality=market_news，本轮不创建实体、不更新实体、不写关系图谱。

## 入库判断

本篇按 `market_news / observation_only_zero_exposure` 处理。所有公司和题材仅进入观察，不创建实体、不更新实体、不写入 `entity_exposures.json` 或 `evidence_index.json`。
"""
    if dry_run:
        return {"mode": "market_news", "log_id": log_id, "dry_run": True}
    (KB / "raw" / f"{source}.md").write_text(raw, encoding="utf-8")
    (WIKI / "sources" / f"{source}.md").write_text(source_note, encoding="utf-8")
    append_log(log_id, source, source_date, [f"[[{source}]] (source note)", f"raw/{source}.md"], ["[[index.md]]"], "source-only market_news observation, zero relation writes")
    rewrite_source_log(source, log_id, "PDF ingest source-only observation")
    counts = update_index()
    return {"mode": "market_news", "log_id": f"#{log_id:03d}", "counts": counts}


def call_writer(payload: dict) -> dict:
    result = subprocess.run(["python3", str(WRITER)], input=json.dumps(payload, ensure_ascii=False), text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout or f"entity_delta_writer failed: {result.returncode}")
    try:
        return json.loads(result.stdout)
    except Exception:
        return {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}


def cleanup_after_writer(source: str, source_date: str, companies: list[str], remove_updated_section: bool = False) -> None:
    ann = "- 注：来自调研日报/券商聚合材料，source_quality=broker_research_high，fact_hardness=review_candidate，evidence_layer=L1_L3_candidate，需公司投资者关系活动记录表原文验证\n"
    marker = f"### {source_date}｜{source}"
    for company in companies:
        path = WIKI / "entities" / f"{company}.md"
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        first = text.find(marker)
        if first == -1:
            continue
        while True:
            second = text.find(marker, first + 1)
            if second == -1:
                break
            next_section = text.find("\n### ", second + 1)
            next_h2 = text.find("\n## ", second + 1)
            candidates = [x for x in (next_section, next_h2) if x != -1]
            end = min(candidates) if candidates else len(text)
            text = text[:second].rstrip() + "\n" + text[end:]
        first = text.find(marker)
        next_section = text.find("\n### ", first + 1)
        next_h2 = text.find("\n## ", second + 1) if second != -1 else text.find("\n## ", first + 1)
        candidates = [x for x in (next_section, next_h2) if x != -1]
        end = min(candidates) if candidates else len(text)
        section = text[first:end]
        if "source_quality=broker_research_high" not in section:
            section = section.rstrip() + "\n" + ann
            text = text[:first] + section + text[end:]
        path.write_text(text, encoding="utf-8")
    source_path = WIKI / "sources" / f"{source}.md"
    if source_path.exists():
        text = source_path.read_text(encoding="utf-8")
        # Remove duplicate sections
        for heading in ["## 已更新实体", "## 观察列表", "## 仅更新图谱"]:
            first = text.find("\n" + heading)
            if first != -1:
                second = text.find("\n" + heading, first + 1)
                while second != -1:
                    next_h2 = text.find("\n## ", second + 1)
                    end = next_h2 if next_h2 != -1 else len(text)
                    text = text[:second].rstrip() + "\n" + text[end:]
                    second = text.find("\n" + heading, first + 1)
        # Optionally remove the first 已更新实体 section (for graph_only updates)
        if remove_updated_section:
            first = text.find("\n## 已更新实体")
            if first != -1:
                next_h2 = text.find("\n## ", first + 1)
                end = next_h2 if next_h2 != -1 else len(text)
                text = text[:first].rstrip() + "\n" + text[end:]
        source_path.write_text(text, encoding="utf-8")


def write_ir_research(source: str, source_date: str, pdf: str, text: str, dry_run: bool) -> dict:
    sections = parse_ir_sections(text)
    if not sections:
        raise SystemExit("ir_research_parse_failed: no company sections found")
    log_id = next_log_id()
    raw_body = clean_text(text)
    companies = [item["company"] for item in sections]
    updates = []
    for item in sections:
        concepts = infer_concepts(item["section"])
        role, layer = infer_role_layer(item["section"])
        bullets = split_sentences(item["section"])
        evidence = f"{source}：{item['company']} — {item['section'][:260]}（调研日报聚合转述，需公司投资者关系活动记录表原文验证）。"
        updates.append({
            "company": item["company"],
            "date": source_date,
            "title": item["title"],
            "concepts": concepts,
            "role": role,
            "chain_layer": layer,
            "tier": "related",
            "confidence": "medium",
            "evidence_layer": "L1_L3_candidate",
            "update_type": "curated_research",
            "fact_hardness": "review_candidate",
            "source_quality": "broker_research_high",
            "review_required": True,
            "bullets": bullets,
            "evidence": evidence,
        })
    raw = f"""# {source}

来源文件：{pdf}
来源：选股通调研日报
队列日期：{source_date}
抽取方式：auto extractor

## 摘要

本篇调研日报包含 {len(companies)} 家公司级 IR 聚合线索：{'、'.join(companies)}。本篇为二手聚合来源，按 `curated_research / review_candidate / L1_L3_candidate / review_required=true` 写入高信度研究线索，不写 `hard_fact`。

## 原文整理

{raw_body}
"""
    updated_lines = "\n".join(f"- [[{u['company']}]]：{u['title']}，按 `curated_research / review_candidate / L1_L3_candidate / review_required=true` 更新。" for u in updates)
    source_note = f"""---
title: "{source}"
type: source
source_date: {source_date}
tags: [调研日报, 选股通, IR聚合]
created: {date.today().isoformat()}
updated: {date.today().isoformat()}
revision: 1
sources: []
source_quality: broker_research_high
log: ["#{log_id:03d} created from [[{source}]] PDF ingest — curated_research"]
---

# {source}

来源：选股通调研日报
队列日期：{source_date}
类型：调研日报 / IR 聚合
质量：broker_research_high
原文：`raw/{source}.md`
抽取：auto extractor

## 概要

本篇调研日报包含 {len(companies)} 家公司级 IR 聚合线索：{'、'.join(companies)}。底层材料来自公司投资者关系活动记录表，但当前 source note 仍是二手聚合来源。

## 已更新实体

{updated_lines}

## 入库判断

本篇为调研日报聚合转述，公司级事实按高信度研究线索处理，不写 `hard_fact`，不写实体 `## 边际变化`。
"""
    if dry_run:
        return {"mode": "ir_research", "log_id": log_id, "companies": companies, "updates": updates, "dry_run": True}
    (KB / "raw" / f"{source}.md").write_text(raw, encoding="utf-8")
    (WIKI / "sources" / f"{source}.md").write_text(source_note, encoding="utf-8")
    writer_payload = {
        "source_name": source,
        "source_date": source_date,
        "source_file": pdf,
        "raw_sources": [f"raw/{source}.md"],
        "create_missing": True,
        "updates": updates,
        "watchlist": [],
    }
    writer_result = call_writer(writer_payload)
    cleanup_after_writer(source, source_date, companies)
    append_log(log_id, source, source_date, [f"[[{source}]] (source note)", f"raw/{source}.md"], [*(f"[[{c}]]" for c in companies), "[[index.md]]", "entity_exposures.json + evidence_index.json"], f"auto ir_research curated_research for {'、'.join(companies)}")
    rewrite_source_log(source, log_id, "PDF ingest curated_research")
    counts = update_index()
    return {"mode": "ir_research", "log_id": f"#{log_id:03d}", "companies": companies, "writer": writer_result, "counts": counts}


def _extract_companies_from_beneficiary_text(text: str) -> tuple[list[str], list[str]]:
    """Extract company names from beneficiary list text (脱水研报 format).
    Returns (existing_entities, skipped_names)."""
    _SKIP_LABELS = {"摘要", "正文", "研报来源", "今日研报内容", "免责声明", "风险提示", "相关标的", "标的"}
    found = []
    # Only match lines that look like industry/category labels followed by company lists
    # Pattern: short label (2-8 chars) + colon + at least 3 separator-delimited items (company list)
    for m in re.finditer(r"^([\u4e00-\u9fff·\(\)（）]{2,8})[：:]\s*([\u4e00-\u9fff·\(\)（）A-Za-z0-9]+(?:[、,，]\s*[\u4e00-\u9fff·\(\)（）A-Za-z0-9]+){2,})", text, re.M):
        label = m.group(1)
        if label in _SKIP_LABELS:
            continue
        for name in re.split(r"[、,，]\s*", m.group(2)):
            name = name.strip().rstrip("。")
            if 2 <= len(name) <= 10:
                found.append(name)
    # Also match "核心公司：XXX、YYY" pattern (not line-anchored)
    for m in re.finditer(r"核心公司[：:]\s*([\u4e00-\u9fff·]+(?:[、,，]\s*[\u4e00-\u9fff·]+)+)", text):
        for name in re.split(r"[、,，]\s*", m.group(1)):
            name = name.strip().rstrip("。等")
            if 2 <= len(name) <= 10:
                found.append(name)
    # Also match "标的：XXX、YYY" pattern
    for m in re.finditer(r"标的[：:]\s*([\u4e00-\u9fff·]+(?:[、,，]\s*[\u4e00-\u9fff·]+)+)", text):
        for name in re.split(r"[、,，]\s*", m.group(1)):
            name = name.strip().rstrip("。等")
            if 2 <= len(name) <= 10:
                found.append(name)
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for n in found:
        if n not in seen:
            seen.add(n)
            unique.append(n)
    existing = [n for n in unique if (WIKI / "entities" / f"{n}.md").exists()]
    skipped = [n for n in unique if n not in existing]
    return existing, skipped


def write_beneficiary_list(source: str, source_date: str, pdf: str, text: str, dry_run: bool) -> dict:
    existing, skipped = _extract_companies_from_beneficiary_text(text)
    log_id = next_log_id()
    raw_body = clean_text(text)
    updates = []
    for comp in existing:
        concepts = infer_concepts(text[:2000])
        role, layer = infer_role_layer(text[:2000])
        updates.append({
            "company": comp,
            "date": source_date,
            "title": "脱水研报受益名单",
            "concepts": concepts,
            "role": role,
            "chain_layer": layer,
            "tier": "peripheral",
            "confidence": "low",
            "evidence_layer": "graph_only",
            "update_type": "graph_only",
            "fact_hardness": "market_narrative",
            "source_quality": "broker_research_medium",
            "review_required": False,
            "bullets": [],
            "evidence": f"{source}：{comp} 出现在受益名单中（脱水研报/券商研报聚合受益名单，无公司级独立事实，graph_only）。",
        })
    raw = f"""# {source}

来源文件：{pdf}
来源：选股通脱水研报
队列日期：{source_date}
抽取方式：auto extractor

## 摘要

本篇脱水研报为受益名单型来源，包含 {'、'.join(existing) if existing else '无已有实体'}。该类来源按 `graph_only / exposure_only / peripheral` 处理，不写 `hard_fact`，不建新实体。

## 原文整理

{raw_body}
"""
    watch_lines = "\n".join(f"- {name}：缺实体，本轮不 create_missing。" for name in skipped) or "- 无。"
    graph_lines = "\n".join(f"- [[{u['company']}]]：受益名单，按 `graph_only / market_narrative / peripheral` 更新。" for u in updates) or "- 无已有实体。"
    source_note = f"""---
title: "{source}"
type: source
source_date: {source_date}
tags: [脱水研报, 选股通, 券商研报聚合]
created: {date.today().isoformat()}
updated: {date.today().isoformat()}
revision: 1
sources: []
source_quality: broker_research_medium
log: ["#{log_id:03d} created from [[{source}]] PDF ingest — graph_only"]
---

# {source}

来源：选股通脱水研报
队列日期：{source_date}
类型：脱水研报 / 受益名单
质量：broker_research_medium
原文：`raw/{source}.md`
抽取：auto extractor

## 概要

本篇脱水研报为受益名单型来源，已有实体按 `graph_only / market_narrative / peripheral` 更新，不建新实体。

## 仅更新图谱

{graph_lines}

## 观察列表

{watch_lines}

## 入库判断

本篇为券商研报聚合受益名单，公司级事实按 `graph_only / market_narrative` 处理，不写 `hard_fact`，不写实体 `## 边际变化`。缺实体不 create_missing。
"""
    if dry_run:
        return {"mode": "beneficiary_list", "log_id": log_id, "existing": existing, "skipped": skipped, "dry_run": True}
    (KB / "raw" / f"{source}.md").write_text(raw, encoding="utf-8")
    (WIKI / "sources" / f"{source}.md").write_text(source_note, encoding="utf-8")
    if updates:
        writer_payload = {
            "source_name": source,
            "source_date": source_date,
            "source_file": pdf,
            "raw_sources": [f"raw/{source}.md"],
            "create_missing": False,
            "updates": updates,
            "watchlist": [{"company": n, "reason": "受益名单缺实体，不create_missing"} for n in skipped],
        }
        writer_result = call_writer(writer_payload)
        # Remove duplicate sections added by writer (graph_only entities should stay in 仅更新图谱)
        cleanup_after_writer(source, source_date, existing, remove_updated_section=True)
    else:
        writer_result = {"status": "no_updates", "note": "no existing entities found in beneficiary list"}
    append_log(log_id, source, source_date, [f"[[{source}]] (source note)", f"raw/{source}.md"], ["[[index.md]]"], f"beneficiary_list graph_only for {len(existing)} entities, {len(skipped)} skipped")
    rewrite_source_log(source, log_id, "PDF ingest graph_only/exposure_only")
    counts = update_index()
    return {"mode": "beneficiary_list", "log_id": f"#{log_id:03d}", "existing": existing, "skipped": skipped, "writer": writer_result, "counts": counts}


def parse_rating_digest(text: str) -> list[dict]:
    """Parse rating digest (评级日报) format: stock codes + company name line + title line + body."""
    lines = clean_text(text).splitlines()
    sections = []
    idx = 0
    while idx < len(lines):
        line = lines[idx].strip()
        # Skip page markers and empty lines
        if not line or line.startswith("===== PAGE"):
            idx += 1
            continue
        # Skip stock code lines like "601339.SS"
        if re.match(r"^\d{6}\.[A-Z]{2}$", line):
            idx += 1
            continue
        # Try to match company name: 2-10 char Chinese name on its own line
        # Must NOT be a known non-company label
        _SKIP = {"研报来源", "免责声明", "风险提示", "内容来源", "本文来自", "本资讯"}
        if 2 <= len(line) <= 10 and re.match(r"^[\u4e00-\u9fffA-Za-z0-9·]+$", line) and line not in _SKIP:
            company = line
            # Next non-empty line should be the title
            title = ""
            body_start = idx + 1
            for j in range(idx + 1, len(lines)):
                l = lines[j].strip()
                if not l or l.startswith("===== PAGE"):
                    continue
                title = l
                body_start = j + 1
                break
            # Collect body until next stock code line, 研报来源, or another company line
            body_lines = []
            for j in range(body_start, len(lines)):
                l = lines[j].strip()
                if re.match(r"^\d{6}\.[A-Z]{2}$", l):
                    break
                if l.startswith("研报来源") or l.startswith("免责声明"):
                    break
                body_lines.append(lines[j])
            block = truncate_section_tail("\n".join([title] + body_lines).strip())
            if len(block) >= 50:
                sections.append({"company": company, "title": (title or "评级日报公司主线")[:80], "section": block})
            idx = body_start + len(body_lines)
            continue
        idx += 1
    return sections


def write_rating_digest(source: str, source_date: str, pdf: str, text: str, dry_run: bool) -> dict:
    sections = parse_rating_digest(text)
    if not sections:
        raise SystemExit("rating_digest_parse_failed: no company sections found")
    log_id = next_log_id()
    raw_body = clean_text(text)
    companies = [item["company"] for item in sections]
    updates = []
    for item in sections:
        concepts = infer_concepts(item["section"])
        role, layer = infer_role_layer(item["section"])
        bullets = split_sentences(item["section"])
        evidence = f"{source}：{item['company']} — {item['section'][:260]}（评级日报/券商研报聚合，需原始研报验证）。"
        updates.append({
            "company": item["company"],
            "date": source_date,
            "title": item["title"],
            "concepts": concepts,
            "role": role,
            "chain_layer": layer,
            "tier": "related",
            "confidence": "medium",
            "evidence_layer": "L1_L3_candidate",
            "update_type": "curated_research",
            "fact_hardness": "review_candidate",
            "source_quality": "broker_research_high",
            "review_required": True,
            "bullets": bullets,
            "evidence": evidence,
        })
    raw = f"""# {source}

来源文件：{pdf}
来源：选股通评级日报
队列日期：{source_date}
抽取方式：auto extractor

## 摘要

本篇评级日报包含 {len(companies)} 家公司级研报线索：{'、'.join(companies)}。本篇为券商研报聚合来源，按 `curated_research / review_candidate / L1_L3_candidate / review_required=true` 写入高信度研究线索，不写 `hard_fact`。

## 原文整理

{raw_body}
"""
    updated_lines = "\n".join(f"- [[{u['company']}]]：{u['title'][:60]}，按 `curated_research / review_candidate / L1_L3_candidate` 更新。" for u in updates)
    source_note = f"""---
title: "{source}"
type: source
source_date: {source_date}
tags: [评级日报, 选股通, 券商研报聚合]
created: {date.today().isoformat()}
updated: {date.today().isoformat()}
revision: 1
sources: []
source_quality: broker_research_high
log: ["#{log_id:03d} created from [[{source}]] PDF ingest — curated_research"]
---

# {source}

来源：选股通评级日报
队列日期：{source_date}
类型：评级日报 / 券商研报聚合
质量：broker_research_high
原文：`raw/{source}.md`
抽取：auto extractor

## 概要

本篇评级日报包含 {len(companies)} 家公司级研报线索：{'、'.join(companies)}。底层材料来自券商研报，但当前 source note 仍是二手聚合来源。

## 已更新实体

{updated_lines}

## 入库判断

本篇为评级日报聚合转述，公司级事实按高信度研究线索处理，不写 `hard_fact`，不写实体 `## 边际变化`。
"""
    if dry_run:
        return {"mode": "rating_digest", "log_id": log_id, "companies": companies, "updates": updates, "dry_run": True}
    (KB / "raw" / f"{source}.md").write_text(raw, encoding="utf-8")
    (WIKI / "sources" / f"{source}.md").write_text(source_note, encoding="utf-8")
    writer_payload = {
        "source_name": source,
        "source_date": source_date,
        "source_file": pdf,
        "raw_sources": [f"raw/{source}.md"],
        "create_missing": True,
        "updates": updates,
        "watchlist": [],
    }
    writer_result = call_writer(writer_payload)
    cleanup_after_writer(source, source_date, companies)
    append_log(log_id, source, source_date, [f"[[{source}]] (source note)", f"raw/{source}.md"], [*(f"[[{c}]]" for c in companies), "[[index.md]]", "entity_exposures.json + evidence_index.json"], f"auto rating_digest curated_research for {'、'.join(companies)}")
    rewrite_source_log(source, log_id, "PDF ingest curated_research")
    counts = update_index()
    return {"mode": "rating_digest", "log_id": f"#{log_id:03d}", "companies": companies, "writer": writer_result, "counts": counts}


def main() -> int:
    parser = argparse.ArgumentParser(description="Conservative default worker for PDF ingest queue.")
    parser.add_argument("--source", required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--text", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    text = args.text.read_text(encoding="utf-8")
    report_type = infer_report_type(args.source)
    if report_type == "market_news":
        result = write_market_news(args.source, args.date, args.pdf, text, args.dry_run)
    elif report_type == "ir_research":
        result = write_ir_research(args.source, args.date, args.pdf, text, args.dry_run)
    elif report_type == "beneficiary_list":
        result = write_beneficiary_list(args.source, args.date, args.pdf, text, args.dry_run)
    elif report_type == "rating_digest":
        result = write_rating_digest(args.source, args.date, args.pdf, text, args.dry_run)
    else:
        raise SystemExit(f"unsupported_report_type_for_default_worker: {report_type}; source={args.source}")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
