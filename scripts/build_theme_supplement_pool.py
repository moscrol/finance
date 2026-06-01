#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

SECTION_MAP = {
    "概念定锚表": "definition_profile_rows",
    "需求场景表": "demand_scenarios",
    "工艺材料扫描表": "material_process_scan",
    "工艺/材料/零部件扫描表": "material_process_scan",
    "工艺/材料扫描表": "material_process_scan",
    "工艺材料零部件扫描表": "material_process_scan",
    "方向级验证清单": "validation_items",
    "催化日历": "catalyst_calendar",
    "产业链全景表": "industry_chain_panorama",
    "认知演变时间线": "recognition_timeline",
    "操作建议表": "action_plan",
    "V1V2增量比较表": "snapshot_diff_rows",
    "V1/V2增量比较表": "snapshot_diff_rows",
    "相邻方向横向对比表": "progress_ruler",
}

FIELD_MAPS = {
    "definition_profile_rows": {
        "术语": "term",
        "一句话定义": "one_line_anchor",
        "技术本质": "technical_definition",
        "类比解释": "analogy",
        "相邻概念": "adjacent_concepts",
        "与相邻概念区别": "boundary_notes",
        "为什么重要": "why_it_matters",
        "证据摘要": "evidence_summary",
        "来源": "source",
        "日期": "source_date",
        "可信度": "confidence",
        "是否需核验": "needs_review",
    },
    "demand_scenarios": {
        "需求场景": "scenario",
        "下游驱动": "downstream_driver",
        "传导逻辑": "transmission_logic",
        "对应工艺/材料/设备要求": "process_requirement",
        "受益环节": "beneficiary_links",
        "代表公司": "representative_entities",
        "证据摘要": "evidence_summary",
        "来源": "source",
        "日期": "source_date",
        "下一步验证": "next_validation",
        "可信度": "confidence",
        "是否需核验": "needs_review",
    },
    "material_process_scan": {
        "工艺/材料/零部件名称": "name",
        "工艺/材料名称": "name",
        "工艺材料名称": "name",
        "所属大赛道": "major_track",
        "所属产业链环节": "chain_position",
        "景气判断": "prosperity_judgment",
        "景气判断理由": "prosperity_reason",
        "每日复盘提及频率": "daily_review_frequency",
        "自进化认知层级": "cognition_level",
        "分类": "classification",
        "核心催化": "core_catalyst",
        "代表公司": "representative_entities",
        "证据摘要": "evidence_summary",
        "来源": "source",
        "日期": "source_date",
        "下一步验证": "next_validation",
        "可信度": "confidence",
        "是否需核验": "needs_review",
    },
    "validation_items": {
        "方向": "direction",
        "验证事项": "item",
        "验证类型": "validation_type",
        "验证窗口": "validation_window",
        "对应公司": "related_entities",
        "升级条件": "upgrade_condition",
        "降级条件": "downgrade_condition",
        "当前状态": "status",
        "证据摘要": "evidence_summary",
        "来源": "source",
        "日期": "source_date",
        "可信度": "confidence",
        "是否需核验": "needs_review",
    },
    "catalyst_calendar": {
        "时间窗口": "time_window",
        "事件": "event",
        "事件类型": "event_type",
        "影响方向": "direction",
        "相关公司": "related_entities",
        "影响逻辑": "impact_logic",
        "下一步观察": "next_watch",
        "证据摘要": "evidence_summary",
        "来源": "source",
        "日期": "source_date",
        "可信度": "confidence",
        "是否需核验": "needs_review",
    },
    "industry_chain_panorama": {
        "层级": "layer",
        "环节": "segment",
        "关键工艺/材料/设备/产品": "key_elements",
        "代表公司": "representative_entities",
        "市场空间/价值量/产能": "market_value_capacity",
        "供需状态": "supply_demand_status",
        "产业逻辑": "industry_logic",
        "证据摘要": "evidence_summary",
        "来源": "source",
        "日期": "source_date",
        "下一步验证": "next_validation",
        "可信度": "confidence",
        "是否需核验": "needs_review",
    },
    "recognition_timeline": {
        "时间窗口": "time_window",
        "事件": "event",
        "认知阶段": "recognition_stage",
        "市场认同度": "market_consensus",
        "事实等级": "fact_level",
        "相关方向": "direction",
        "相关公司": "related_entities",
        "证据摘要": "evidence_summary",
        "来源": "source",
        "日期": "source_date",
        "可信度": "confidence",
        "是否需核验": "needs_review",
    },
    "action_plan": {
        "优先级": "priority_bucket",
        "方向": "direction",
        "核心逻辑": "core_logic",
        "操作思路": "action_thesis",
        "等待条件": "wait_for",
        "风险提示": "risk_warning",
        "证据摘要": "evidence_summary",
        "来源": "source",
        "日期": "source_date",
        "可信度": "confidence",
        "是否需核验": "needs_review",
    },
    "snapshot_diff_rows": {
        "对比版本": "comparison_version",
        "新增方向": "new_directions",
        "认知升级方向": "upgraded_directions",
        "认知降级方向": "downgraded_directions",
        "新增证据": "new_evidence",
        "核心增量总结": "summary",
        "来源": "source",
        "日期": "source_date",
        "可信度": "confidence",
        "是否需核验": "needs_review",
    },
    "progress_ruler": {
        "方向": "direction",
        "当前阶段": "current_stage",
        "阶段位置": "stage_position",
        "阶段理由": "stage_reason",
        "领先/落后判断": "relative_position",
        "相关催化": "related_catalyst",
        "下一步验证": "next_validation",
        "证据摘要": "evidence_summary",
        "来源": "source",
        "日期": "source_date",
        "可信度": "confidence",
        "是否需核验": "needs_review",
    },
}

LIST_FIELDS = {
    "adjacent_concepts",
    "boundary_notes",
    "why_it_matters",
    "beneficiary_links",
    "representative_entities",
    "related_entities",
    "key_elements",
    "new_directions",
    "upgraded_directions",
    "downgraded_directions",
}

REQUIRED_SECTIONS = ["demand_scenarios", "material_process_scan", "validation_items", "catalyst_calendar"]


def sha_id(*parts: str) -> str:
    raw = "|".join(str(p or "") for p in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def clean_text(value: Any) -> str:
    s = str(value or "").strip()
    s = re.sub(r"<br\s*/?>", "；", s)
    s = re.sub(r"\*\*(.*?)\*\*", r"\1", s)
    s = s.replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", s).strip()


def split_md_row(line: str) -> list[str]:
    return [clean_text(c) for c in line.strip().strip("|").split("|")]


def is_separator(line: str) -> bool:
    cells = split_md_row(line)
    return bool(cells) and all(re.fullmatch(r":?-{2,}:?", c.strip()) for c in cells)


def normalize_section(section: str) -> str:
    value = re.sub(r"^\d+(?:\.\d+)?[、.\s]*", "", clean_text(section))
    value = value.replace(" ", "")
    for key in sorted(SECTION_MAP, key=len, reverse=True):
        if key.replace(" ", "") in value:
            return SECTION_MAP[key]
    return ""


def parse_markdown_tables(text: str) -> list[dict[str, Any]]:
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
            tables.append({"section": section, "section_key": normalize_section(section), "headers": headers, "rows": rows})
            continue
        i += 1
    return tables


def parse_theme(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            title = clean_text(line.lstrip("#"))
            title = re.sub(r"Theme\s*Radar\s*补充数据", "", title, flags=re.I).strip()
            title = re.sub(r"题材雷达.*$", "", title).strip()
            return title or fallback
    stem = fallback
    stem = re.sub(r"_?ThemeRadar_?补充数据$", "", stem)
    stem = re.sub(r"_?theme_supplement_pool$", "", stem)
    return stem


def split_list(value: str) -> list[str]:
    text = clean_text(value)
    if not text:
        return []
    parts = re.split(r"[、,，；;]+", text)
    return [p.strip() for p in parts if p.strip()]


def normalize_bool(value: str) -> bool:
    text = clean_text(value).lower()
    return text in {"是", "yes", "y", "true", "1", "需核验", "需要", "需要核验"}


def normalize_confidence(value: str) -> str:
    text = clean_text(value).lower()
    if text in {"高", "high", "h"}:
        return "high"
    if text in {"低", "low", "l"}:
        return "low"
    if text in {"中", "medium", "mid", "m"}:
        return "medium"
    return text or "medium"


def normalize_stage_position(value: str) -> int | str:
    text = clean_text(value)
    if re.fullmatch(r"\d+", text):
        return int(text)
    mapping = {"暗流": 1, "萌芽": 2, "第一轮": 3, "催化共振": 4, "一致认同": 5}
    return mapping.get(text, text)


def normalize_row(section_key: str, raw: dict[str, str], theme: str, source_file: str, line_no: int) -> dict[str, Any]:
    field_map = FIELD_MAPS.get(section_key, {})
    row: dict[str, Any] = {}
    for key, value in raw.items():
        target = field_map.get(clean_text(key), clean_text(key))
        if target in LIST_FIELDS:
            row[target] = split_list(value)
        elif target == "needs_review":
            row[target] = normalize_bool(value)
        elif target == "confidence":
            row[target] = normalize_confidence(value)
        elif target == "stage_position":
            row[target] = normalize_stage_position(value)
        else:
            row[target] = clean_text(value)
    evidence_text = row.get("evidence_summary") or row.get("event") or row.get("item") or row.get("scenario") or row.get("name") or row.get("direction") or row.get("term") or ""
    row["item_id"] = sha_id(theme, section_key, evidence_text, row.get("source", ""), row.get("source_date", ""), str(line_no))
    row["source_file"] = source_file
    row["line_no"] = line_no
    row["section_type"] = section_key
    row["raw_row"] = raw
    if "confidence" not in row:
        row["confidence"] = "medium"
    if "needs_review" not in row:
        row["needs_review"] = True
    return row


def evidence_item_from_row(theme: str, row: dict[str, Any]) -> dict[str, Any]:
    return {
        "item_id": row.get("item_id", ""),
        "theme": theme,
        "section_type": row.get("section_type", ""),
        "target": row.get("direction") or row.get("name") or row.get("scenario") or row.get("term") or row.get("segment") or "",
        "evidence": row.get("evidence_summary") or row.get("event") or row.get("core_logic") or row.get("industry_logic") or "",
        "source": row.get("source", ""),
        "source_date": row.get("source_date", ""),
        "confidence": row.get("confidence", "medium"),
        "needs_review": bool(row.get("needs_review", True)),
        "source_file": row.get("source_file", ""),
        "line_no": row.get("line_no", ""),
    }


def definition_profile_from_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {}
    first = rows[0]
    return {
        "term": first.get("term", ""),
        "one_line_anchor": first.get("one_line_anchor", ""),
        "technical_definition": first.get("technical_definition", ""),
        "analogy": first.get("analogy", ""),
        "adjacent_concepts": first.get("adjacent_concepts", []),
        "boundary_notes": first.get("boundary_notes", []),
        "why_it_matters": first.get("why_it_matters", []),
        "supporting_item_ids": [row.get("item_id") for row in rows if row.get("item_id")],
        "rows": rows,
    }


def build_pool(path: Path, theme_arg: str = "") -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    theme = theme_arg or parse_theme(text, path.stem)
    pool: dict[str, Any] = {
        "version": 1,
        "theme": theme,
        "generated_at": date.today().isoformat(),
        "source_file": str(path),
        "definition_profile": {},
        "definition_profile_rows": [],
        "demand_scenarios": [],
        "material_process_scan": [],
        "validation_items": [],
        "catalyst_calendar": [],
        "industry_chain_panorama": [],
        "recognition_timeline": [],
        "action_plan": [],
        "snapshot_diff_rows": [],
        "progress_ruler": [],
        "evidence_items": [],
        "unmapped_tables": [],
    }
    for table in parse_markdown_tables(text):
        section_key = table.get("section_key") or ""
        if not section_key:
            pool["unmapped_tables"].append({"section": table.get("section", ""), "headers": table.get("headers", []), "row_count": len(table.get("rows", []))})
            continue
        for item in table.get("rows", []):
            row = normalize_row(section_key, item["row"], theme, str(path), int(item["line_no"]))
            pool[section_key].append(row)
            pool["evidence_items"].append(evidence_item_from_row(theme, row))
    pool["definition_profile"] = definition_profile_from_rows(pool["definition_profile_rows"])
    counts = {key: len(pool.get(key, [])) for key in FIELD_MAPS}
    pool["summary"] = {
        "theme": theme,
        "source_file": str(path),
        "row_count": sum(counts.values()),
        "table_counts": counts,
        "evidence_item_count": len(pool["evidence_items"]),
        "missing_required_sections": [key for key in REQUIRED_SECTIONS if not pool.get(key)],
        "unmapped_table_count": len(pool["unmapped_tables"]),
        "confidence_distribution": dict(Counter(str(item.get("confidence", "")) for item in pool["evidence_items"])),
        "needs_review_count": sum(1 for item in pool["evidence_items"] if item.get("needs_review")),
        "safety_statement": "Theme supplement pool only. It does not write entities/relations/knowledge-base files.",
    }
    return pool


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Theme Radar supplement pool from Markdown tables")
    parser.add_argument("markdown")
    parser.add_argument("--theme", default="")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--prefix", default="")
    args = parser.parse_args()

    path = Path(args.markdown).expanduser()
    if not path.exists():
        raise FileNotFoundError(path)
    pool = build_pool(path, args.theme)
    out_dir = Path(args.out_dir).expanduser()
    prefix = args.prefix or pool["theme"]
    out_path = out_dir / f"{prefix}.theme_supplement_pool.json"
    write_json(out_path, pool)
    print(json.dumps(pool["summary"], ensure_ascii=False, indent=2))
    print(f"[OK] wrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
