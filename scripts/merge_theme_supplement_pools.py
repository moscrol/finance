#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

LIST_SECTIONS = [
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
    "evidence_items",
    "unmapped_tables",
]

REQUIRED_SECTIONS = ["demand_scenarios", "material_process_scan", "validation_items", "catalyst_calendar"]


def sha_id(*parts: Any) -> str:
    raw = "|".join(str(part or "") for part in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def row_key(section: str, row: dict[str, Any]) -> str:
    if row.get("item_id"):
        return str(row.get("item_id"))
    return sha_id(section, row.get("term"), row.get("direction"), row.get("name"), row.get("scenario"), row.get("segment"), row.get("evidence_summary"), row.get("source"), row.get("source_date"))


def merge_rows(section: str, *row_lists: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    result = []
    for rows in row_lists:
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            key = row_key(section, row)
            if key in seen:
                continue
            seen.add(key)
            result.append(row)
    return result


def merge_definition_profile(base: dict[str, Any], incoming: dict[str, Any], prefer: str) -> dict[str, Any]:
    base_profile = base.get("definition_profile") if isinstance(base.get("definition_profile"), dict) else {}
    incoming_profile = incoming.get("definition_profile") if isinstance(incoming.get("definition_profile"), dict) else {}
    if prefer == "incoming" and incoming_profile.get("one_line_anchor"):
        return incoming_profile
    if base_profile.get("one_line_anchor"):
        return base_profile
    return incoming_profile


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


def build_summary(pool: dict[str, Any]) -> dict[str, Any]:
    counts = {section: len(pool.get(section, [])) if isinstance(pool.get(section), list) else 0 for section in LIST_SECTIONS if section != "evidence_items" and section != "unmapped_tables"}
    evidence_items = pool.get("evidence_items", []) if isinstance(pool.get("evidence_items"), list) else []
    return {
        "theme": pool.get("theme", ""),
        "source_file": pool.get("source_file", ""),
        "source_file_count": len(pool.get("source_files", [])) if isinstance(pool.get("source_files"), list) else 0,
        "row_count": sum(counts.values()),
        "table_counts": counts,
        "evidence_item_count": len(evidence_items),
        "generation_scope": "merged_theme_supplement_pool",
        "missing_required_sections": [section for section in REQUIRED_SECTIONS if not pool.get(section)],
        "confidence_distribution": dict(Counter(str(item.get("confidence", "")) for item in evidence_items if isinstance(item, dict))),
        "needs_review_count": sum(1 for item in evidence_items if isinstance(item, dict) and item.get("needs_review")),
        "safety_statement": "Merged Theme Radar supplement pool only. It does not write entities/relations/knowledge-base files.",
    }


def merge_pools(base: dict[str, Any], incoming: dict[str, Any], prefer_definition: str) -> dict[str, Any]:
    theme = incoming.get("theme") or base.get("theme") or ""
    if base.get("theme") and incoming.get("theme") and base.get("theme") != incoming.get("theme"):
        raise ValueError(f"theme mismatch: {base.get('theme')} vs {incoming.get('theme')}")
    pool: dict[str, Any] = {
        "version": max(int(base.get("version", 1) or 1), int(incoming.get("version", 1) or 1)),
        "theme": theme,
        "generated_at": date.today().isoformat(),
        "source_file": incoming.get("source_file") or base.get("source_file") or "",
        "source_files": merge_rows("source_files", [{"item_id": str(path), "path": path} for path in base.get("source_files", []) + incoming.get("source_files", [])]),
        "generation_scope": "merged_theme_supplement_pool",
        "definition_profile": merge_definition_profile(base, incoming, prefer_definition),
    }
    pool["source_files"] = [row.get("path", "") for row in pool["source_files"] if row.get("path")]
    for section in LIST_SECTIONS:
        if section in {"evidence_items", "unmapped_tables"}:
            continue
        if section == "industry_chain_panorama":
            pool[section] = merge_rows(section, base.get(section, []), incoming.get(section, []))
        elif section == "definition_profile_rows":
            pool[section] = merge_rows(section, base.get(section, []), incoming.get(section, []))
        else:
            pool[section] = merge_rows(section, incoming.get(section, []), base.get(section, []))
    rows_for_evidence = []
    for section in LIST_SECTIONS:
        if section in {"evidence_items", "unmapped_tables"}:
            continue
        rows_for_evidence.extend(pool.get(section, []) if isinstance(pool.get(section), list) else [])
    generated_evidence = [evidence_item_from_row(theme, row) for row in rows_for_evidence]
    pool["evidence_items"] = merge_rows("evidence_items", incoming.get("evidence_items", []), base.get("evidence_items", []), generated_evidence)
    pool["unmapped_tables"] = merge_rows("unmapped_tables", incoming.get("unmapped_tables", []), base.get("unmapped_tables", []))
    pool["summary"] = build_summary(pool)
    return pool


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge a DeepDive base supplement pool with a demand-four-table supplement pool")
    parser.add_argument("--base-pool", required=True)
    parser.add_argument("--incoming-pool", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--prefer-definition", choices=["base", "incoming"], default="base")
    args = parser.parse_args()

    base = load_json(Path(args.base_pool).expanduser())
    incoming = load_json(Path(args.incoming_pool).expanduser())
    merged = merge_pools(base, incoming, args.prefer_definition)
    out_path = Path(args.out).expanduser()
    write_json(out_path, merged)
    print(json.dumps(merged["summary"], ensure_ascii=False, indent=2))
    print(f"[OK] wrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
