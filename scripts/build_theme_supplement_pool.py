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
        "序号": "sequence",
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
        "#": "sequence",
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
        "来源/日期": "source",
        "日期": "source_date",
        "可信度": "confidence",
        "是否需核验": "needs_review",
    },
    "catalyst_calendar": {
        "#": "sequence",
        "时间": "time_window",
        "时间窗口": "time_window",
        "事件": "event",
        "验证事项": "event",
        "类型": "event_type",
        "事件类型": "event_type",
        "影响方向": "direction",
        "相关公司": "related_entities",
        "对应编号": "related_validation_refs",
        "影响逻辑": "impact_logic",
        "下一步观察": "next_watch",
        "核心观察点": "next_watch",
        "证据摘要": "evidence_summary",
        "来源": "source",
        "来源/日期": "source",
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
        "#": "sequence",
        "时间": "time_window",
        "时间窗口": "time_window",
        "事件": "event",
        "认知阶段": "recognition_stage",
        "市场认同度": "market_consensus",
        "事实等级": "fact_level",
        "相关方向": "direction",
        "影响方向": "direction",
        "相关公司": "related_entities",
        "证据摘要": "evidence_summary",
        "来源": "source",
        "来源/日期": "source",
        "日期": "source_date",
        "可信度": "confidence",
        "是否需核验": "needs_review",
    },
    "action_plan": {
        "优先级": "priority_bucket",
        "方向": "direction",
        "标的": "target_entity",
        "环节": "direction",
        "景气判断": "prosperity_judgment",
        "提及频率": "mention_frequency",
        "认知层级": "recognition_level",
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


def infer_section_from_headers(section: str, headers: list[str], source_file: str) -> str:
    normalized = normalize_section(section)
    if normalized:
        return normalized
    header_set = set(headers)
    source_name = Path(source_file).name
    if {"需求场景", "下游驱动", "传导逻辑"} & header_set and "需求场景" in header_set:
        return "demand_scenarios"
    if "工艺/材料/零部件名称" in header_set and "景气判断" in header_set:
        return "material_process_scan"
    if "验证事项" in header_set and "升级条件" in header_set and "降级条件" in header_set:
        return "validation_items"
    if "事件" in header_set and "影响方向" in header_set and "下一步观察" in header_set:
        return "catalyst_calendar"
    if "验证事项" in header_set and "核心观察点" in header_set and "时间" in header_set:
        return "catalyst_calendar"
    if "标的" in header_set and "环节" in header_set and "核心逻辑" in header_set:
        return "action_plan"
    if "认知阶段" in header_set and "事实等级" in header_set and "事件" in header_set:
        return "recognition_timeline"
    if "产业链景气度" in source_name and "景气判断" in header_set and "代表公司" in header_set:
        return "material_process_scan"
    return ""


def parse_markdown_tables(text: str, source_file: str = "") -> list[dict[str, Any]]:
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
            tables.append({"section": section, "section_key": infer_section_from_headers(section, headers, source_file), "headers": headers, "rows": rows, "source_file": source_file})
            continue
        i += 1
    return tables


def parse_theme(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            title = clean_text(line.lstrip("#"))
            title = re.sub(r"Theme\s*Radar\s*补充数据", "", title, flags=re.I).strip()
            title = re.sub(r"题材雷达.*$", "", title).strip()
            for sep in (" /", "—", "-", "_"):
                if sep in title:
                    title = title.split(sep, 1)[0].strip()
            return title or fallback
    stem = fallback
    stem = re.sub(r"_?ThemeRadar_?补充数据$", "", stem)
    stem = re.sub(r"_?theme_supplement_pool$", "", stem)
    return stem


def infer_direction_from_section(section: str) -> str:
    value = clean_text(section)
    value = re.sub(r"^\d+(?:\.\d+)?[、.\s]*", "", value)
    value = re.sub(r"^[一二三四五六七八九十]+[、.\s]*", "", value)
    value = re.sub(r"（.*?）", "", value)
    return value.strip()


def infer_validation_type(text: str) -> str:
    value = clean_text(text)
    mapping = [
        ("订单", "订单"),
        ("招标", "订单"),
        ("中标", "订单"),
        ("产能", "产能"),
        ("投产", "产能"),
        ("ASP", "ASP"),
        ("价格", "价格"),
        ("良率", "良率"),
        ("认证", "客户认证"),
        ("客户", "客户认证"),
        ("收入", "收入占比"),
        ("占比", "收入占比"),
        ("国产", "国产替代"),
        ("政策", "政策"),
        ("量产", "量产"),
        ("交付", "交付"),
        ("发射", "发射进度"),
        ("回收", "技术验证"),
    ]
    for token, label in mapping:
        if token in value:
            return label
    return "综合验证"


def classify_material_process(row: dict[str, Any]) -> str:
    text = " ".join(str(row.get(k) or "") for k in ("prosperity_judgment", "prosperity_reason", "core_catalyst"))
    if any(token in text for token in ("高景气", "爆发", "供不应求", "放量", "快速提升")):
        return "发酵"
    if any(token in text for token in ("景气上行", "稳健增长", "验证", "确定性")):
        return "布局"
    if any(token in text for token in ("景气启动", "从0到1", "早期", "认知差")):
        return "观察"
    return "观察"


RECOGNITION_CONSENSUS_MAP = {"暗流": "L1", "萌芽": "L2", "第一轮": "L3", "催化共振": "L4", "一致认同": "L5"}


def recognition_consensus(stage: str) -> str:
    text = clean_text(stage)
    if not text:
        return ""
    segments = [seg for seg in re.split(r"[→←—\->~/、]+", text) if seg.strip()]
    for seg in reversed(segments):
        seg = seg.strip()
        if seg in RECOGNITION_CONSENSUS_MAP:
            return RECOGNITION_CONSENSUS_MAP[seg]
    best = ""
    for key, level in RECOGNITION_CONSENSUS_MAP.items():
        if key in text and level > best:
            best = level
    return best


def infer_action_priority(row: dict[str, Any]) -> str:
    text = " ".join(str(row.get(k) or "") for k in ("prosperity_judgment", "mention_frequency", "recognition_level", "core_logic"))
    if "高频" in text and any(token in text for token in ("L2-L3", "L3", "L2")) and any(token in text for token in ("高景气", "爆发")):
        return "最优先"
    if "高频" in text or any(token in text for token in ("L2-L3", "L3", "L2")):
        return "次优先"
    return "观察"


def split_source_date(value: str) -> tuple[str, str]:
    text = clean_text(value)
    matches = re.findall(r"(?:20\d{2}[./-]\d{1,2}(?:[./-]\d{1,2})?|20\d{2}[./-]\d{1,2}|20\d{2})", text)
    if not matches:
        return text, ""
    source_date = matches[-1].replace(".", "-").replace("/", "-")
    source = text.rsplit(matches[-1], 1)[0].strip(" /，,；;")
    return source or text, source_date


def extract_default_date(text: str) -> str:
    for line in text.splitlines()[:20]:
        if any(token in line for token in ("更新日期", "最近更新", "覆盖时段", "更新窗口")):
            matches = re.findall(r"(?:20\d{2}[./-]\d{1,2}(?:[./-]\d{1,2})?|20\d{2}[./-]\d{1,2}|20\d{2})", line)
            if matches:
                return matches[-1].replace(".", "-").replace("/", "-")
    return ""


def split_list(value: str) -> list[str]:
    text = clean_text(value)
    if not text:
        return []
    parts = re.split(r"[、,，；;]+", text)
    return [p.strip() for p in parts if p.strip()]


def normalize_bool(value: str) -> bool:
    text = clean_text(value).lower()
    return text in {"是", "yes", "y", "true", "1", "需核验", "需要", "需要核验", "✅", "✔", "✓"}


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


def normalize_row(section_key: str, raw: dict[str, str], theme: str, source_file: str, line_no: int, section: str = "", default_source_date: str = "") -> dict[str, Any]:
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
    row["source_file"] = source_file
    row["line_no"] = line_no
    row["section"] = clean_text(section)
    row["section_type"] = section_key
    row["raw_row"] = raw
    if "confidence" not in row:
        row["confidence"] = "medium"
    if "needs_review" not in row:
        row["needs_review"] = True
    if section_key == "material_process_scan":
        row.setdefault("chain_position", infer_direction_from_section(section))
        if not row.get("daily_review_frequency"):
            row["daily_review_frequency"] = "未统计"
        row.setdefault("classification", classify_material_process(row))
    if section_key == "validation_items":
        row.setdefault("direction", infer_direction_from_section(section))
        row.setdefault("validation_type", infer_validation_type(row.get("item", "")))
        if row.get("source") and not row.get("source_date"):
            source, source_date = split_source_date(row.get("source", ""))
            row["source"] = source
            row["source_date"] = source_date
    if section_key == "catalyst_calendar":
        row.setdefault("evidence_summary", row.get("impact_logic", ""))
        if not row.get("direction"):
            inferred_direction = infer_direction_from_section(section)
            if "验证节点日历" in inferred_direction:
                inferred_direction = theme
            row["direction"] = inferred_direction or theme
        if not row.get("event_type"):
            row["event_type"] = "关键验证" if row.get("related_validation_refs") else "产业催化"
        if not row.get("impact_logic"):
            row["impact_logic"] = row.get("next_watch", "") or row.get("event", "")
        if not row.get("next_watch"):
            row["next_watch"] = row.get("event", "")
        if not row.get("evidence_summary"):
            row["evidence_summary"] = row.get("impact_logic", "") or row.get("next_watch", "") or row.get("event", "")
        if row.get("source") and not row.get("source_date"):
            source, source_date = split_source_date(row.get("source", ""))
            row["source"] = source
            row["source_date"] = source_date
    if section_key == "action_plan":
        row.setdefault("priority_bucket", infer_action_priority(row))
        if not row.get("core_logic"):
            row["core_logic"] = row.get("evidence_summary", "") or row.get("prosperity_judgment", "")
        target = row.get("target_entity", "")
        direction = row.get("direction", "")
        if not row.get("action_thesis"):
            row["action_thesis"] = "；".join([item for item in (f"重点跟踪：{target}" if target else "", row.get("prosperity_judgment", ""), row.get("mention_frequency", ""), row.get("recognition_level", "")) if item])
        if not row.get("wait_for"):
            row["wait_for"] = "结合最新财报、公告、订单和客户导入进展二次验证。"
        if not row.get("risk_warning"):
            row["risk_warning"] = "来自补充数据池的研究线索，非公告硬事实，需复核。"
        if not row.get("evidence_summary"):
            row["evidence_summary"] = "；".join([item for item in (target, direction, row.get("core_logic", "")) if item])
    if section_key == "recognition_timeline":
        if row.get("source") and not row.get("source_date"):
            source, source_date = split_source_date(row.get("source", ""))
            row["source"] = source
            row["source_date"] = source_date
        if not row.get("market_consensus"):
            row["market_consensus"] = recognition_consensus(row.get("recognition_stage", ""))
        if not row.get("direction"):
            row["direction"] = infer_direction_from_section(section) or theme
        if not row.get("evidence_summary"):
            row["evidence_summary"] = row.get("event", "")
    if not row.get("source"):
        row["source"] = Path(source_file).stem
    if not row.get("source_date") and default_source_date:
        row["source_date"] = default_source_date
    evidence_text = row.get("evidence_summary") or row.get("event") or row.get("item") or row.get("scenario") or row.get("name") or row.get("direction") or row.get("term") or ""
    row["item_id"] = sha_id(theme, section_key, evidence_text, row.get("source", ""), row.get("source_date", ""), str(line_no))
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


CHAIN_LAYER_ORDER = ["上游材料", "上游设备", "上游", "中游制造", "中游", "下游应用 / 软件服务", "下游应用", "下游"]


def derive_industry_chain_panorama(theme: str, rows: list[dict[str, Any]], source_file: str = "") -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], dict[str, list]] = {}
    order: list[tuple[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        layer = clean_text(row.get("chain_position") or "")
        if not layer:
            continue
        segment = clean_text(row.get("major_track") or "") or layer
        key = (layer, segment)
        if key not in groups:
            groups[key] = {"names": [], "entities": [], "prosperity": [], "evidence": [], "catalyst": [], "source_date": []}
            order.append(key)
        g = groups[key]
        if row.get("name"):
            g["names"].append(clean_text(row.get("name")))
        for entity in row.get("representative_entities") or []:
            if entity and entity not in g["entities"]:
                g["entities"].append(entity)
        if row.get("prosperity_judgment"):
            g["prosperity"].append(clean_text(row.get("prosperity_judgment")))
        if row.get("evidence_summary"):
            g["evidence"].append(clean_text(row.get("evidence_summary")))
        if row.get("core_catalyst"):
            g["catalyst"].append(clean_text(row.get("core_catalyst")))
        if row.get("source_date"):
            g["source_date"].append(clean_text(row.get("source_date")))

    def layer_rank(key: tuple[str, str]) -> int:
        layer = key[0]
        for idx, name in enumerate(CHAIN_LAYER_ORDER):
            if name in layer or layer in name:
                return idx
        return len(CHAIN_LAYER_ORDER)

    result = []
    for key in sorted(order, key=layer_rank):
        layer, segment = key
        g = groups[key]
        prosperity = unique_keep(g["prosperity"])[:3]
        industry_logic = "；".join(prosperity) or "；".join(g["catalyst"][:2]) or f"{segment} 环节景气跟踪"
        evidence = max(g["evidence"], key=len) if g["evidence"] else f"{segment} 环节产业链分布：{('、'.join(g['names'][:5]))}"
        source_date = max(g["source_date"]) if g["source_date"] else ""
        row = {
            "layer": layer,
            "segment": segment,
            "key_elements": g["names"][:12],
            "representative_entities": g["entities"][:12],
            "market_value_capacity": "",
            "supply_demand_status": "",
            "industry_logic": industry_logic,
            "evidence_summary": evidence,
            "source": "派生自产业链景气度跟踪表",
            "source_date": source_date,
            "confidence": "medium",
            "needs_review": True,
            "section": "派生：产业链全景",
            "section_type": "industry_chain_panorama",
            "source_file": source_file,
            "line_no": "",
            "derived": True,
        }
        row["item_id"] = sha_id(theme, "industry_chain_panorama", evidence, row["source"], source_date, segment)
        result.append(row)
    return result


def unique_keep(values: list[str]) -> list[str]:
    seen = set()
    out = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out


def markdown_paths(path: Path) -> list[Path]:
    if path.is_dir():
        return sorted(p for p in path.glob("*.md") if p.is_file())
    return [path]


def build_pool(path: Path, theme_arg: str = "") -> dict[str, Any]:
    paths = markdown_paths(path)
    if not paths:
        raise FileNotFoundError(f"no markdown files found under {path}")
    texts = [(p, p.read_text(encoding="utf-8")) for p in paths]
    theme = theme_arg or parse_theme(texts[0][1], texts[0][0].stem)
    pool: dict[str, Any] = {
        "version": 1,
        "theme": theme,
        "generated_at": date.today().isoformat(),
        "source_file": str(path),
        "source_files": [str(p) for p, _text in texts],
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
    for source_path, text in texts:
        source_theme = parse_theme(text, source_path.stem)
        default_source_date = extract_default_date(text)
        if not theme_arg and source_theme and source_theme != theme and (theme not in source_theme and source_theme not in theme):
            pass
        for table in parse_markdown_tables(text, str(source_path)):
            section_key = table.get("section_key") or ""
            if not section_key:
                pool["unmapped_tables"].append({"section": table.get("section", ""), "headers": table.get("headers", []), "row_count": len(table.get("rows", [])), "source_file": str(source_path)})
                continue
            for item in table.get("rows", []):
                row = normalize_row(section_key, item["row"], theme, str(source_path), int(item["line_no"]), table.get("section", ""), default_source_date)
                pool[section_key].append(row)
                pool["evidence_items"].append(evidence_item_from_row(theme, row))
    pool["definition_profile"] = definition_profile_from_rows(pool["definition_profile_rows"])
    derived_sections = []
    if not pool["industry_chain_panorama"] and pool["material_process_scan"]:
        derived = derive_industry_chain_panorama(theme, pool["material_process_scan"], str(path))
        if derived:
            pool["industry_chain_panorama"] = derived
            for row in derived:
                pool["evidence_items"].append(evidence_item_from_row(theme, row))
            derived_sections.append("industry_chain_panorama")
    counts = {key: len(pool.get(key, [])) for key in FIELD_MAPS}
    pool["summary"] = {
        "theme": theme,
        "source_file": str(path),
        "source_file_count": len(paths),
        "row_count": sum(counts.values()),
        "table_counts": counts,
        "evidence_item_count": len(pool["evidence_items"]),
        "missing_required_sections": [key for key in REQUIRED_SECTIONS if not pool.get(key)],
        "derived_sections": derived_sections,
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
