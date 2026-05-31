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
    (("电子特气", "氦气", "三氯化硼", "溴化氢", "电子气体"), ["电子特气", "半导体材料"]),
    (("光通信", "CPO", "NPO", "EML", "VCSEL", "硅光", "薄膜铌酸锂"), ["光通信", "光模块", "CPO", "光芯片"]),
    (("煤炭", "煤化工", "动力煤", "炼焦煤"), ["煤炭", "煤化工"]),
    (("光伏", "钙钛矿", "HJT", "异质结", "太空光伏", "砷化镓", "辅材", "浆料", "胶膜"), ["光伏", "钙钛矿", "HJT异质结"]),
    (("体育产业", "体育赛事", "苏超", "世界杯", "赛事IP", "草坪"), ["体育产业"]),
]

ROLE_MAP = [
    (("电子特气", "氦气", "三氯化硼", "溴化氢"), "电子特种气体和半导体气体材料供应商", "upstream_materials"),
    (("光通信", "CPO", "EML", "VCSEL", "硅光"), "光通信芯片与半导体激光芯片供应商", "upstream_components"),
    (("光伏", "钙钛矿", "HJT", "异质结", "太空光伏"), "光伏设备与辅材供应商", "midstream_manufacturing"),
    (("体育产业", "体育赛事", "赛事IP"), "体育赛事与产业链服务商", "downstream_operation"),
]


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
    return "公司级研报聚合线索待核验", "midstream_manufacturing"


def truncate_section_tail(section: str) -> str:
    lines = section.splitlines()
    kept = []
    stop_markers = ("研报来源", "免责声明", "风险提示", "相关公司：", "相关公司:")
    for line in lines:
        stripped = line.strip()
        if any(marker in stripped for marker in stop_markers):
            break
        kept.append(line)
    return "\n".join(kept).strip()


def split_sentences(section: str, limit: int = 5) -> list[str]:
    text = re.sub(r"===== PAGE \d+ =====", "", section)
    parts = [p.strip() for p in re.split(r"(?<=[。！？])", text) if p.strip()]
    bullets = []
    for part in parts:
        if len(part) < 8 or "免责声明" in part or "风险提示" in part or "研报来源" in part:
            continue
        bullets.append(part[:180])
        if len(bullets) >= limit:
            break
    return bullets


def entity_exists(company: str) -> bool:
    return (WIKI / "entities" / f"{company}.md").exists()


def _extract_companies_from_block(block: str) -> list[str]:
    """Extract company names from '相关产业链：' lists inside a section."""
    found = []
    # Match lines like "光伏设备：双良节能、晶盛机电、连城数控、拉普拉斯、捷佳伟创、奥特维。"
    # Also "大光（光模块核心）：中际旭创、新易盛。"
    for m in re.finditer(r"[：:]\s*([\u4e00-\u9fff·\(\)（）A-Za-z0-9]+(?:[、,，]\s*[\u4e00-\u9fff·\(\)（）A-Za-z0-9]+)+)", block):
        for name in re.split(r"[、,，]\s*", m.group(1)):
            name = name.strip().rstrip("。")
            # Skip labels like "光模块核心" inside parentheses
            if 2 <= len(name) <= 10 and not re.match(r"^[\u4e00-\u9fff]{1,2}$", name):
                found.append(name)
    return found


def parse_numbered_company_sections(text: str) -> tuple[list[dict], list[str]]:
    lines = clean_text(text).splitlines()
    # Two formats:
    # A) "1、公司名：标题" (强势股脱水 - company as header)
    # B) "1、行业名：标题" (强势脱水 - industry as header, companies inside)
    matches = []
    for idx, line in enumerate(lines):
        m = re.match(r"^\s*\d+\s*[、,，]\s*([^：:]{2,20})[：:]\s*(.*)$", line.strip())
        if not m:
            continue
        name = re.sub(r"\s+", "", m.group(1).strip())
        title = m.group(2).strip()
        matches.append((idx, name, title))
    sections = []
    skipped = []
    for pos, (idx, name, title) in enumerate(matches):
        end = matches[pos + 1][0] if pos + 1 < len(matches) else len(lines)
        block = truncate_section_tail("\n".join([title] + lines[idx + 1:end]).strip())
        if entity_exists(name):
            # Format A: company is the section header
            sections.append({"company": name, "title": title[:80] or "强势股脱水公司主线", "section": block})
        else:
            # Format B: name is an industry/theme, extract companies from block
            companies_in_block = _extract_companies_from_block(block)
            for comp in companies_in_block:
                if entity_exists(comp):
                    sections.append({"company": comp, "title": f"{name}：{title[:60]}" or "强势脱水产业链", "section": block})
                else:
                    skipped.append(comp)
    return sections, skipped


def call_writer(payload: dict) -> dict:
    result = subprocess.run(["python3", str(WRITER)], input=json.dumps(payload, ensure_ascii=False), text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout or f"entity_delta_writer failed: {result.returncode}")
    try:
        return json.loads(result.stdout)
    except Exception:
        return {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}


def cleanup_after_writer(source: str, source_date: str, companies: list[str]) -> None:
    ann = "- 注：来自券商研报聚合材料，source_quality=broker_research_high，fact_hardness=review_candidate，evidence_layer=L1_L3_candidate，需公告/公司披露或研报原文验证\n"
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
        next_h2 = text.find("\n## ", first + 1)
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
        for heading in ["## 已更新实体", "## 观察列表", "## 仅更新图谱"]:
            first = text.find("\n" + heading)
            if first != -1:
                second = text.find("\n" + heading, first + 1)
                while second != -1:
                    next_h2 = text.find("\n## ", second + 1)
                    end = next_h2 if next_h2 != -1 else len(text)
                    text = text[:second].rstrip() + "\n" + text[end:]
                    second = text.find("\n" + heading, first + 1)
        source_path.write_text(text, encoding="utf-8")


def write_core_review(source: str, source_date: str, pdf: str, text: str, dry_run: bool) -> dict:
    if "强势股脱水" not in source and "强势脱水" not in source:
        raise SystemExit(f"unsupported_core_review_source={source}")
    sections, skipped = parse_numbered_company_sections(text)
    if not sections:
        raise SystemExit("core_review_parse_failed: no existing company sections found")
    log_id = next_log_id()
    raw_body = clean_text(text)
    companies = [item["company"] for item in sections]
    updates = []
    for item in sections:
        concepts = infer_concepts(item["section"])
        role, layer = infer_role_layer(item["section"])
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
            "bullets": split_sentences(item["section"]),
            "evidence": f"{source}：{item['company']} — {item['section'][:280]}（强势股脱水/券商研报聚合来源，需公告、公司披露或研报原文验证）。",
        })
    updated_lines = "\n".join(f"- [[{u['company']}]]：{u['title']}，按 `curated_research / review_candidate / L1_L3_candidate / review_required=true` 更新。" for u in updates)
    watch_lines = "\n".join(f"- {name}：非公司主线或缺实体，本轮不 create_missing。" for name in skipped) or "- 无。"
    raw = f"""# {source}

来源文件：{pdf}
来源：选股通强势股脱水
队列日期：{source_date}
抽取方式：auto extractor

## 摘要

本篇强势股脱水包含明确公司主线：{'、'.join(companies)}。非公司主线或缺实体的产业链名单仅观察，不自动新建实体。公司主线按 `curated_research / review_candidate / L1_L3_candidate / review_required=true` 写入高信度研究线索，不写 `hard_fact`。

## 原文整理

{raw_body}
"""
    source_note = f"""---
title: "{source}"
type: source
source_date: {source_date}
tags: [强势股脱水, 选股通, 券商研报聚合]
created: {date.today().isoformat()}
updated: {date.today().isoformat()}
revision: 1
sources: []
source_quality: broker_research_high
log: ["#{log_id:03d} created from [[{source}]] PDF ingest — curated_research"]
---

# {source}

来源：选股通强势股脱水
队列日期：{source_date}
类型：强势股脱水 / 券商研报聚合
质量：broker_research_high
原文：`raw/{source}.md`
抽取：auto extractor

## 概要

本篇强势股脱水包含明确公司主线：{'、'.join(companies)}。产业链名单和非公司主线仅观察，不自动新建实体。

## 已更新实体

{updated_lines}

## 观察列表

{watch_lines}

## 入库判断

本篇为券商研报聚合来源，公司主线按高信度研究线索处理，不写 `hard_fact`，不写实体 `## 边际变化`。缺实体或产业链名单不 create_missing。
"""
    if dry_run:
        return {"mode": "core_review", "log_id": log_id, "companies": companies, "skipped": skipped, "updates": updates, "dry_run": True}
    (KB / "raw" / f"{source}.md").write_text(raw, encoding="utf-8")
    (WIKI / "sources" / f"{source}.md").write_text(source_note, encoding="utf-8")
    writer_payload = {
        "source_name": source,
        "source_date": source_date,
        "source_file": pdf,
        "raw_sources": [f"raw/{source}.md"],
        "create_missing": False,
        "updates": updates,
        "watchlist": [{"company": name, "reason": "非公司主线或缺实体，默认不create_missing。"} for name in skipped],
    }
    writer_result = call_writer(writer_payload)
    cleanup_after_writer(source, source_date, companies)
    append_log(log_id, source, source_date, [f"[[{source}]] (source note)", f"raw/{source}.md"], [*(f"[[{c}]]" for c in companies), "[[index.md]]", "entity_exposures.json + evidence_index.json"], f"auto strong-stock curated_research for {'、'.join(companies)}; skipped={', '.join(skipped) if skipped else 'none'}")
    rewrite_source_log(source, log_id, "PDF ingest curated_research")
    counts = update_index()
    return {"mode": "core_review", "log_id": f"#{log_id:03d}", "companies": companies, "skipped": skipped, "writer": writer_result, "counts": counts}


def main() -> int:
    parser = argparse.ArgumentParser(description="Conservative worker for strong-stock PDF reviews.")
    parser.add_argument("--source", required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--text", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = write_core_review(args.source, args.date, args.pdf, args.text.read_text(encoding="utf-8"), args.dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
