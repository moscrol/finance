#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

P0_SECTIONS = ["demand_scenarios", "material_process_scan", "validation_items", "catalyst_calendar"]
P1_SECTIONS = ["definition_profile", "industry_chain_panorama", "recognition_timeline", "action_plan"]
P2_SECTIONS = ["snapshot_diff_rows", "progress_ruler"]
VALID_CONFIDENCE = {"high", "medium", "low"}

REQUIRED_FIELDS = {
    "demand_scenarios": [
        "scenario",
        "downstream_driver",
        "transmission_logic",
        "process_requirement",
        "beneficiary_links",
        "representative_entities",
        "evidence_summary",
        "source",
        "source_date",
        "next_validation",
        "confidence",
        "needs_review",
    ],
    "material_process_scan": [
        "name",
        "major_track",
        "chain_position",
        "prosperity_judgment",
        "prosperity_reason",
        "daily_review_frequency",
        "cognition_level",
        "classification",
        "core_catalyst",
        "representative_entities",
        "evidence_summary",
        "source",
        "source_date",
        "next_validation",
        "confidence",
        "needs_review",
    ],
    "validation_items": [
        "direction",
        "item",
        "validation_type",
        "validation_window",
        "upgrade_condition",
        "downgrade_condition",
        "status",
        "evidence_summary",
        "source",
        "source_date",
        "confidence",
        "needs_review",
    ],
    "catalyst_calendar": [
        "time_window",
        "event",
        "event_type",
        "direction",
        "impact_logic",
        "next_watch",
        "evidence_summary",
        "source",
        "source_date",
        "confidence",
        "needs_review",
    ],
    "industry_chain_panorama": [
        "layer",
        "segment",
        "key_elements",
        "representative_entities",
        "industry_logic",
        "evidence_summary",
        "source",
        "source_date",
        "confidence",
        "needs_review",
    ],
    "recognition_timeline": [
        "time_window",
        "event",
        "recognition_stage",
        "market_consensus",
        "fact_level",
        "direction",
        "evidence_summary",
        "source",
        "source_date",
        "confidence",
        "needs_review",
    ],
    "action_plan": [
        "priority_bucket",
        "direction",
        "core_logic",
        "action_thesis",
        "wait_for",
        "risk_warning",
        "evidence_summary",
        "source",
        "source_date",
        "confidence",
        "needs_review",
    ],
    "progress_ruler": [
        "direction",
        "current_stage",
        "stage_position",
        "stage_reason",
        "relative_position",
        "related_catalyst",
        "next_validation",
        "evidence_summary",
        "source",
        "source_date",
        "confidence",
        "needs_review",
    ],
}

LIST_FIELDS = {"beneficiary_links", "representative_entities", "related_entities", "key_elements"}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, list):
        return not [x for x in value if str(x).strip()]
    if isinstance(value, dict):
        return not value
    return False


def issue(level: str, issue_type: str, section: str, detail: str, row_index: int | None = None, item_id: str = "") -> dict[str, Any]:
    row: dict[str, Any] = {"level": level, "type": issue_type, "section": section, "detail": detail}
    if row_index is not None:
        row["row_index"] = row_index
    if item_id:
        row["item_id"] = item_id
    return row


def check_required_sections(pool: dict[str, Any]) -> list[dict[str, Any]]:
    issues = []
    for section in P0_SECTIONS:
        rows = pool.get(section, [])
        if not isinstance(rows, list) or not rows:
            issues.append(issue("error", "missing_p0_section", section, f"P0 section `{section}` is missing or empty"))
    for section in P1_SECTIONS:
        value = pool.get(section, [] if section != "definition_profile" else {})
        if section == "definition_profile":
            if not isinstance(value, dict) or not value.get("one_line_anchor"):
                issues.append(issue("warning", "missing_p1_section", section, "P1 definition profile is missing or lacks one_line_anchor"))
        elif not isinstance(value, list) or not value:
            issues.append(issue("warning", "missing_p1_section", section, f"P1 section `{section}` is missing or empty"))
    return issues


def check_rows(pool: dict[str, Any]) -> list[dict[str, Any]]:
    issues = []
    for section, fields in REQUIRED_FIELDS.items():
        rows = pool.get(section, [])
        if not isinstance(rows, list):
            issues.append(issue("error", "invalid_section_type", section, f"`{section}` must be a list"))
            continue
        required_level = "error" if section in P0_SECTIONS else "warning"
        for idx, row in enumerate(rows):
            if not isinstance(row, dict):
                issues.append(issue(required_level, "invalid_row_type", section, "row must be an object", idx))
                continue
            item_id = str(row.get("item_id") or "")
            for field in fields:
                if is_blank(row.get(field)):
                    issues.append(issue(required_level, "missing_required_field", section, f"missing `{field}`", idx, item_id))
            confidence = str(row.get("confidence") or "").strip()
            if confidence and confidence not in VALID_CONFIDENCE:
                issues.append(issue(required_level, "invalid_confidence", section, f"confidence `{confidence}` not in {sorted(VALID_CONFIDENCE)}", idx, item_id))
            if "needs_review" in row and not isinstance(row.get("needs_review"), bool):
                issues.append(issue(required_level, "invalid_needs_review", section, "needs_review must be boolean", idx, item_id))
            if "source" in fields and is_blank(row.get("source")):
                issues.append(issue(required_level, "missing_source", section, "source is required for traceability", idx, item_id))
            if "source_date" in fields and is_blank(row.get("source_date")):
                issues.append(issue(required_level, "missing_source_date", section, "source_date is required for traceability", idx, item_id))
            if "evidence_summary" in fields and len(str(row.get("evidence_summary") or "")) < 6:
                issues.append(issue(required_level, "weak_evidence_summary", section, "evidence_summary is too short", idx, item_id))
            for field in LIST_FIELDS & set(fields):
                if field in row and not isinstance(row.get(field), list):
                    issues.append(issue(required_level, "invalid_list_field", section, f"`{field}` should be a list", idx, item_id))
    return issues


def check_evidence_items(pool: dict[str, Any]) -> list[dict[str, Any]]:
    issues = []
    rows = pool.get("evidence_items", [])
    if not isinstance(rows, list) or not rows:
        return [issue("error", "missing_evidence_items", "evidence_items", "evidence_items is missing or empty")]
    ids = [str(row.get("item_id") or "") for row in rows if isinstance(row, dict)]
    duplicate_ids = [item_id for item_id, count in Counter(ids).items() if item_id and count > 1]
    for item_id in duplicate_ids:
        issues.append(issue("warning", "duplicate_item_id", "evidence_items", f"duplicate item_id `{item_id}`", item_id=item_id))
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            issues.append(issue("error", "invalid_evidence_row", "evidence_items", "evidence row must be an object", idx))
            continue
        for field in ("item_id", "section_type", "target", "source", "source_date", "confidence", "needs_review"):
            if is_blank(row.get(field)):
                issues.append(issue("warning", "missing_evidence_field", "evidence_items", f"missing `{field}`", idx, str(row.get("item_id") or "")))
    return issues


def summarize(pool: dict[str, Any], issues: list[dict[str, Any]]) -> dict[str, Any]:
    errors = [x for x in issues if x.get("level") == "error"]
    warnings = [x for x in issues if x.get("level") == "warning"]
    table_counts = {}
    for section in P0_SECTIONS + P1_SECTIONS + P2_SECTIONS:
        value = pool.get(section)
        if isinstance(value, list):
            table_counts[section] = len(value)
        elif isinstance(value, dict):
            table_counts[section] = 1 if value else 0
        else:
            table_counts[section] = 0
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "theme": pool.get("theme", ""),
        "source_file": pool.get("source_file", ""),
        "status": "PASS" if not errors else "FAIL",
        "error_count": len(errors),
        "warning_count": len(warnings),
        "table_counts": table_counts,
        "issue_type_counts": dict(Counter(x.get("type") for x in issues)),
        "confidence_distribution": dict(Counter(str(x.get("confidence", "")) for x in pool.get("evidence_items", []) if isinstance(x, dict))),
        "needs_review_count": sum(1 for x in pool.get("evidence_items", []) if isinstance(x, dict) and x.get("needs_review")),
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines = [f"# Theme Supplement Pool Check: {result['summary'].get('theme', '')}", "", f"Generated: {result['summary'].get('generated_at', '')}", ""]
    lines.extend(["## Verdict", "", f"- Status: **{result['summary'].get('status')}**", f"- Errors: {result['summary'].get('error_count')}", f"- Warnings: {result['summary'].get('warning_count')}", ""])
    lines.extend(["## Table Counts", "", "| Section | Rows |", "|---|---:|"])
    for key, value in result["summary"].get("table_counts", {}).items():
        lines.append(f"| {key} | {value} |")
    lines.append("")
    if result.get("issues"):
        lines.extend(["## Issues", "", "| Level | Type | Section | Row | Item ID | Detail |", "|---|---|---|---:|---|---|"])
        for item in result["issues"]:
            lines.append(f"| {item.get('level')} | {item.get('type')} | {item.get('section')} | {item.get('row_index', '')} | {item.get('item_id', '')} | {item.get('detail')} |")
        lines.append("")
    return "\n".join(lines) + "\n"


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Theme Radar supplement pool JSON quality")
    parser.add_argument("supplement_pool_json")
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    parser.add_argument("--warn-only", action="store_true")
    args = parser.parse_args()

    path = Path(args.supplement_pool_json).expanduser()
    pool = load_json(path)
    issues = []
    issues.extend(check_required_sections(pool))
    issues.extend(check_rows(pool))
    issues.extend(check_evidence_items(pool))
    result = {"summary": summarize(pool, issues), "issues": issues}
    if args.out_json:
        write_json(Path(args.out_json).expanduser(), result)
    if args.out_md:
        out_md = Path(args.out_md).expanduser()
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(render_markdown(result), encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    if result["issues"]:
        print(json.dumps(result["issues"][:20], ensure_ascii=False, indent=2))
    if args.warn_only:
        return 0
    return 0 if result["summary"]["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
