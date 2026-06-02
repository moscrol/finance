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

BASE_SECTIONS = [
    "definition_profile_rows",
    "demand_scenarios",
    "material_process_scan",
    "validation_items",
    "catalyst_calendar",
    "industry_chain_panorama",
    "recognition_timeline",
    "action_plan",
    "snapshot_diff_rows",
    "progress_ruler",
]

INTENTIONALLY_EMPTY_SECTIONS = [
    "demand_scenarios",
    "material_process_scan",
    "validation_items",
    "catalyst_calendar",
]

CHAIN_RECORD_TYPES = {
    "deep_dive_chain_path",
    "deep_dive_subdirection",
    "deep_dive_company_mapping",
}

GENERIC_SEGMENTS = {
    "",
    "-",
    "—",
    "无",
    "unknown",
    "题材定锚",
    "全产业链",
    "全链条",
    "全板块",
    "全行业",
    "明确收入结构",
    "明确收入增速",
    "收入结构",
    "收入增速",
    "价格",
    "需求",
    "业务数据",
    "财务数据",
    "年报数据",
    "公告",
}

LAYER_ORDER = ["上游材料", "上游设备", "上游", "中游制造", "中游", "下游应用", "下游", "全链条", "产业链环节"]


def sha_id(*parts: Any) -> str:
    raw = "|".join(str(part or "") for part in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def clean_text(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"<br\s*/?>", "；", text)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def unique_keep(values: list[Any], limit: int = 0) -> list[str]:
    seen = set()
    result = []
    for value in values:
        text = clean_text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
        if limit and len(result) >= limit:
            break
    return result


def normalize_bool(value: Any, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = clean_text(value).lower()
    if not text:
        return default
    if text in {"否", "false", "no", "n", "0", "无需核验", "不需要", "不需核验"} or text.startswith("false"):
        return False
    if text in {"是", "true", "yes", "y", "1", "需核验", "需要", "需要核验"} or text.startswith("true"):
        return True
    return default


def normalize_confidence(value: Any) -> str:
    text = clean_text(value).lower()
    if text in {"高", "high", "h"}:
        return "high"
    if text in {"低", "low", "l"}:
        return "low"
    if text in {"中", "medium", "mid", "m"}:
        return "medium"
    return text if text in {"high", "medium", "low"} else "medium"


def source_date_from_path(path: Path) -> str:
    match = re.search(r"(20\d{2})(\d{2})(\d{2})", path.stem)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    return date.today().isoformat()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            rows.append(json.loads(text))
    return rows


def load_registry(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data.get("canonical_themes", [])
    return [entry for entry in entries if entry.get("status") == "canonical" and entry.get("preferred_items_file")]


def row_source(record: dict[str, Any], fallback_file: Path) -> tuple[str, str]:
    source = clean_text(record.get("source_title"))
    source_date = clean_text(record.get("source_date"))
    refs = record.get("source_refs") if isinstance(record.get("source_refs"), list) else []
    if refs:
        first = refs[0] if isinstance(refs[0], dict) else {}
        source = source or clean_text(first.get("source_title"))
        source_date = source_date or clean_text(first.get("source_date"))
    return source or fallback_file.stem, source_date or source_date_from_path(fallback_file)


def source_file_from_record(record: dict[str, Any], fallback_file: Path) -> str:
    refs = record.get("source_refs") if isinstance(record.get("source_refs"), list) else []
    if refs and isinstance(refs[0], dict) and refs[0].get("path"):
        return str(refs[0].get("path"))
    return str(fallback_file)


def line_no_from_record(record: dict[str, Any]) -> Any:
    refs = record.get("source_refs") if isinstance(record.get("source_refs"), list) else []
    if refs and isinstance(refs[0], dict):
        return refs[0].get("line_no", "")
    return ""


def split_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return unique_keep(value)
    text = clean_text(value)
    if not text:
        return []
    return unique_keep(re.split(r"[、,，；;]+", text))


def extract_definition_profile(theme: str, records: list[dict[str, Any]], items_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    anchor = next((row for row in records if row.get("source_record_type") == "deep_dive_theme_anchor"), None)
    if not anchor:
        anchor = next((row for row in records if row.get("primary_info_type") == "theme_anchor"), None)
    if not anchor:
        return {}, []
    raw = anchor.get("raw_row") if isinstance(anchor.get("raw_row"), dict) else {}
    source, source_date = row_source(anchor, items_path)
    boundary_notes = unique_keep([
        raw.get("题材边界"),
        raw.get("边界"),
        raw.get("排除项"),
        anchor.get("risk_note"),
    ])
    why_it_matters = unique_keep([
        row.get("claim") for row in records
        if row.get("source_record_type") == "deep_dive_catalyst" and row.get("claim")
    ], 3)
    row = {
        "term": theme,
        "one_line_anchor": clean_text(raw.get("一句话定锚") or anchor.get("claim")),
        "technical_definition": clean_text(raw.get("核心定义") or anchor.get("claim")),
        "analogy": clean_text(raw.get("类比解释")),
        "adjacent_concepts": split_list(raw.get("相邻概念")),
        "boundary_notes": boundary_notes,
        "why_it_matters": why_it_matters,
        "evidence_summary": clean_text(anchor.get("claim")),
        "source": source,
        "source_date": source_date,
        "confidence": normalize_confidence(anchor.get("confidence")),
        "needs_review": normalize_bool(anchor.get("needs_review"), True),
        "section": "DeepDive 派生：概念定锚",
        "section_type": "definition_profile_rows",
        "source_file": source_file_from_record(anchor, items_path),
        "line_no": line_no_from_record(anchor),
        "raw_row": raw,
        "derived": True,
        "derived_from_item_id": anchor.get("item_id", ""),
    }
    row["item_id"] = sha_id(theme, "definition_profile_rows", row["one_line_anchor"], row["source"], row["source_date"])
    profile = {
        "term": row["term"],
        "one_line_anchor": row["one_line_anchor"],
        "technical_definition": row["technical_definition"],
        "analogy": row["analogy"],
        "adjacent_concepts": row["adjacent_concepts"],
        "boundary_notes": row["boundary_notes"],
        "why_it_matters": row["why_it_matters"],
        "supporting_item_ids": [row["item_id"]],
        "rows": [row],
    }
    return profile, [row]


def infer_layer(record: dict[str, Any]) -> str:
    text = " ".join(clean_text(record.get(key)) for key in ("chain_position", "segment", "component"))
    if "全链条" in text or "全产业链" in text:
        return "全链条"
    if any(token in text for token in ("上游", "原材料", "原料", "材料", "资源", "矿", "化学品", "合金")):
        return "上游材料"
    if any(token in text for token in ("设备", "装备", "机床", "工艺", "制造设备")):
        return "上游设备"
    if any(token in text for token in ("中游", "制造", "生产", "加工", "封装", "组件", "整机", "系统", "产品", "耗材", "器械", "药", "种子", "养殖")):
        return "中游制造"
    if any(token in text for token in ("下游", "应用", "场景", "客户", "终端", "消费", "医院", "渠道", "运营", "电网", "电厂", "出口")):
        return "下游应用"
    return "产业链环节"


def is_generic_segment(value: str) -> bool:
    text = clean_text(value)
    if text in GENERIC_SEGMENTS:
        return True
    return bool(re.fullmatch(r"(?:收入|订单|产能|客户|认证|量产|出货|利润|市场预测|财务|公告|年报)(?:数据|结构|增速|情况)?", text))


def chain_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for row in records:
        if row.get("source_record_type") not in CHAIN_RECORD_TYPES:
            continue
        if row.get("display_weight") == "low" or row.get("suggested_use") == "watchlist_only":
            continue
        segment = clean_text(row.get("segment") or row.get("chain_position") or row.get("component"))
        if is_generic_segment(segment):
            continue
        result.append(row)
    return result


def derive_industry_chain_panorama(theme: str, records: list[dict[str, Any]], items_path: Path) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    order: list[tuple[str, str]] = []
    for record in chain_records(records):
        segment = clean_text(record.get("segment") or record.get("chain_position") or record.get("component"))
        layer = infer_layer(record)
        key = (layer, segment)
        if key not in groups:
            groups[key] = {"components": [], "entities": [], "claims": [], "sources": [], "dates": [], "confidence": [], "needs_review": [], "files": [], "line_nos": [], "item_ids": []}
            order.append(key)
        group = groups[key]
        group["components"].append(record.get("component") or segment)
        if record.get("entity_name"):
            group["entities"].append(record.get("entity_name"))
        if record.get("claim"):
            group["claims"].append(record.get("claim"))
        source, source_date = row_source(record, items_path)
        group["sources"].append(source)
        group["dates"].append(source_date)
        group["confidence"].append(normalize_confidence(record.get("confidence")))
        group["needs_review"].append(normalize_bool(record.get("needs_review"), True))
        group["files"].append(source_file_from_record(record, items_path))
        group["line_nos"].append(line_no_from_record(record))
        group["item_ids"].append(record.get("item_id", ""))

    def sort_key(key: tuple[str, str]) -> tuple[int, str]:
        layer, segment = key
        rank = LAYER_ORDER.index(layer) if layer in LAYER_ORDER else len(LAYER_ORDER)
        return rank, segment

    rows = []
    for layer, segment in sorted(order, key=sort_key):
        group = groups[(layer, segment)]
        claims = unique_keep(group["claims"])
        evidence = max(claims, key=len) if claims else f"{segment} 是 {theme} DeepDive 信息池识别出的产业链环节。"
        confidence_counts = Counter(group["confidence"])
        confidence = "high" if confidence_counts.get("high") and not confidence_counts.get("low") else "medium"
        row = {
            "layer": layer,
            "segment": segment,
            "key_elements": unique_keep(group["components"], 12),
            "representative_entities": unique_keep(group["entities"], 12),
            "market_value_capacity": "",
            "supply_demand_status": infer_supply_demand_status("；".join(claims)),
            "industry_logic": evidence,
            "evidence_summary": evidence,
            "source": unique_keep(group["sources"], 3)[0] if unique_keep(group["sources"], 3) else items_path.stem,
            "source_date": unique_keep(group["dates"], 1)[0] if unique_keep(group["dates"], 1) else source_date_from_path(items_path),
            "next_validation": "结合需求四表、公告、定报和产业链跟踪数据继续验证。",
            "confidence": confidence,
            "needs_review": any(group["needs_review"]) if group["needs_review"] else True,
            "section": "DeepDive 派生：产业链底座",
            "section_type": "industry_chain_panorama",
            "source_file": unique_keep(group["files"], 1)[0] if unique_keep(group["files"], 1) else str(items_path),
            "line_no": unique_keep(group["line_nos"], 1)[0] if unique_keep(group["line_nos"], 1) else "",
            "derived": True,
            "derived_from_item_ids": unique_keep(group["item_ids"], 20),
        }
        row["item_id"] = sha_id(theme, "industry_chain_panorama", layer, segment, row["evidence_summary"], row["source"], row["source_date"])
        rows.append(row)
    return rows


def infer_supply_demand_status(text: str) -> str:
    value = clean_text(text)
    if any(token in value for token in ("供不应求", "紧缺", "短缺", "瓶颈", "断供", "配额", "库存低", "低库存")):
        return "供给偏紧"
    if any(token in value for token in ("涨价", "价格上涨", "价格中枢", "提价")):
        return "价格弹性"
    if any(token in value for token in ("放量", "高增长", "需求增长", "招标", "订单", "出海", "国产替代")):
        return "需求上行"
    return "待跟踪"


def evidence_item_from_row(theme: str, row: dict[str, Any]) -> dict[str, Any]:
    return {
        "item_id": row.get("item_id", ""),
        "theme": theme,
        "section_type": row.get("section_type", ""),
        "target": row.get("term") or row.get("segment") or "",
        "evidence": row.get("evidence_summary") or row.get("industry_logic") or "",
        "source": row.get("source", ""),
        "source_date": row.get("source_date", ""),
        "confidence": row.get("confidence", "medium"),
        "needs_review": bool(row.get("needs_review", True)),
        "source_file": row.get("source_file", ""),
        "line_no": row.get("line_no", ""),
    }


def build_pool(theme: str, items_path: Path) -> dict[str, Any]:
    records = load_jsonl(items_path)
    definition_profile, definition_rows = extract_definition_profile(theme, records, items_path)
    industry_rows = derive_industry_chain_panorama(theme, records, items_path)
    pool: dict[str, Any] = {
        "version": 1,
        "theme": theme,
        "generated_at": date.today().isoformat(),
        "source_file": str(items_path),
        "source_files": [str(items_path)],
        "generation_scope": "deep_dive_base_only",
        "definition_profile": definition_profile,
        "definition_profile_rows": definition_rows,
        "demand_scenarios": [],
        "material_process_scan": [],
        "validation_items": [],
        "catalyst_calendar": [],
        "industry_chain_panorama": industry_rows,
        "recognition_timeline": [],
        "action_plan": [],
        "snapshot_diff_rows": [],
        "progress_ruler": [],
        "evidence_items": [],
        "unmapped_tables": [],
    }
    pool["evidence_items"] = [evidence_item_from_row(theme, row) for row in definition_rows + industry_rows]
    counts = {key: len(pool.get(key, [])) if isinstance(pool.get(key), list) else (1 if pool.get(key) else 0) for key in BASE_SECTIONS}
    pool["summary"] = {
        "theme": theme,
        "source_file": str(items_path),
        "source_file_count": 1,
        "row_count": len(definition_rows) + len(industry_rows),
        "table_counts": counts,
        "evidence_item_count": len(pool["evidence_items"]),
        "generation_scope": "deep_dive_base_only",
        "derived_sections": [key for key in ("definition_profile", "industry_chain_panorama") if pool.get(key)],
        "intentionally_empty_sections": INTENTIONALLY_EMPTY_SECTIONS,
        "missing_required_sections": INTENTIONALLY_EMPTY_SECTIONS,
        "confidence_distribution": dict(Counter(str(item.get("confidence", "")) for item in pool["evidence_items"])),
        "needs_review_count": sum(1 for item in pool["evidence_items"] if item.get("needs_review")),
        "safety_statement": "DeepDive-derived Theme Radar base pool only. It does not write entities/relations/knowledge-base files.",
    }
    return pool


def output_path_for(out_dir: Path, prefix: str, suffix: str) -> Path:
    return out_dir / f"{prefix}{suffix}.theme_supplement_pool.json"


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Theme Radar definition profile and industry-chain base from DeepDive JSONL pools")
    parser.add_argument("--registry", default="/Users/a77/Desktop/c c/ima/canonical_theme_registry.json")
    parser.add_argument("--items-jsonl", default="")
    parser.add_argument("--theme", default="")
    parser.add_argument("--out-dir", default="/Users/a77/Desktop/c c/ima/parsed")
    parser.add_argument("--suffix", default=".deep_dive_base")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    out_dir = Path(args.out_dir).expanduser()
    written = []
    if args.items_jsonl:
        items_path = Path(args.items_jsonl).expanduser()
        theme = args.theme or re.sub(r"\.theme_information_items$", "", items_path.stem)
        pool = build_pool(theme, items_path)
        out_path = output_path_for(out_dir, items_path.stem.replace(".theme_information_items", ""), args.suffix)
        write_json(out_path, pool)
        written.append(out_path)
    else:
        registry_path = Path(args.registry).expanduser()
        base_dir = registry_path.parent
        entries = load_registry(registry_path)
        if args.theme:
            entries = [entry for entry in entries if entry.get("canonical_theme") == args.theme]
        if not args.all and not args.theme:
            raise SystemExit("Pass --all, --theme, or --items-jsonl")
        for entry in entries:
            items_path = base_dir / entry["preferred_items_file"]
            if not items_path.exists():
                continue
            pool = build_pool(entry["canonical_theme"], items_path)
            prefix = entry.get("preferred_parsed_prefix") or items_path.stem.replace(".theme_information_items", "")
            out_path = output_path_for(out_dir, prefix, args.suffix)
            write_json(out_path, pool)
            written.append(out_path)
    summary = {"written_count": len(written), "written": [str(path) for path in written[:10]], "truncated": max(0, len(written) - 10)}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
