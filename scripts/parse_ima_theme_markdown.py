#!/usr/bin/env python3
"""
Parse IMA theme-radar Markdown exports.

Default mode is read-only: parse JSONL lines embedded in Markdown and print a
summary. It does not write to the knowledge base, entities, relations, or radar
files.
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REQUIRED_FIELDS = [
    "source_system",
    "theme",
    "entity_name",
    "ticker",
    "ticker_check_status",
    "theme_layer",
    "claim",
    "evidence_level",
    "source_type",
    "source_title",
    "source_date",
    "confidence",
    "needs_review",
    "suggested_use",
    "risk_note",
]

RISK_SOURCE_TYPES = {"自媒体专栏", "行业研报/自媒体", "研报及自媒体专栏", "用户提示词"}
ALLOWED_EVIDENCE = {
    "hard_fact",
    "curated_research",
    "review_candidate",
    "graph_only",
    "exposure_only",
}


def iter_jsonl_lines(text: str):
    for line_no, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            yield line_no, stripped


def load_records(path: Path):
    text = path.read_text(encoding="utf-8")
    records = []
    errors = []
    for line_no, line in iter_jsonl_lines(text):
        try:
            records.append((line_no, json.loads(line)))
        except json.JSONDecodeError as exc:
            errors.append(f"line {line_no}: {exc}")
    return records, errors


def validate_record(line_no: int, rec: dict):
    issues = []
    for field in REQUIRED_FIELDS:
        if field not in rec:
            issues.append(f"missing:{field}")
    if rec.get("source_system") != "IMA":
        issues.append("source_system_not_ima")
    if rec.get("evidence_level") not in ALLOWED_EVIDENCE:
        issues.append(f"bad_evidence_level:{rec.get('evidence_level')}")
    if rec.get("evidence_level") == "hard_fact":
        issues.append("hard_fact_not_allowed_for_raw_ima")
    if rec.get("source_type") in RISK_SOURCE_TYPES and rec.get("needs_review") is False:
        issues.append("risky_source_should_need_review")
    if rec.get("ticker") == "unknown" and rec.get("ticker_check_status") == "verified":
        issues.append("unknown_ticker_marked_verified")
    return issues


def build_summary(records):
    parsed = [rec for _, rec in records]
    by_theme_layer = Counter(rec.get("theme_layer", "") for rec in parsed)
    by_evidence = Counter(rec.get("evidence_level", "") for rec in parsed)
    by_use = Counter(rec.get("suggested_use", "") for rec in parsed)
    by_review = Counter(str(rec.get("needs_review")) for rec in parsed)
    entities = defaultdict(int)
    for rec in parsed:
        entities[rec.get("entity_name", "")] += 1
    return {
        "record_count": len(parsed),
        "unique_entity_count": len([k for k in entities if k]),
        "theme_layers": dict(by_theme_layer),
        "evidence_levels": dict(by_evidence),
        "suggested_uses": dict(by_use),
        "needs_review": dict(by_review),
        "entities": dict(sorted(entities.items())),
    }


def main():
    parser = argparse.ArgumentParser(description="Parse IMA theme-radar Markdown JSONL")
    parser.add_argument("markdown", help="IMA Markdown file path")
    parser.add_argument("--out-jsonl", default="", help="optional normalized JSONL output path")
    parser.add_argument("--out-summary", default="", help="optional summary JSON output path")
    args = parser.parse_args()

    path = Path(args.markdown).expanduser()
    if not path.exists():
        print(f"[ERR] file not found: {path}", file=sys.stderr)
        return 1

    records, parse_errors = load_records(path)
    if parse_errors:
        print("[ERR] JSONL parse errors:", file=sys.stderr)
        for err in parse_errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    if not records:
        print(f"[ERR] no JSONL records found: {path}", file=sys.stderr)
        return 1

    issue_map = {}
    for line_no, rec in records:
        issues = validate_record(line_no, rec)
        if issues:
            issue_map[line_no] = issues

    summary = build_summary(records)
    summary["source_file"] = str(path)
    summary["validation_issue_count"] = sum(len(v) for v in issue_map.values())
    summary["validation_issues"] = issue_map
    summary["safety_statement"] = (
        "Raw IMA records are review candidates only. Do not write them directly "
        "to entities/*.md, hard_fact, key_data, or entity_delta without official verification."
    )

    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if args.out_jsonl:
        out = Path(args.out_jsonl).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8") as f:
            for _, rec in records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"[OK] wrote jsonl: {out}")

    if args.out_summary:
        out = Path(args.out_summary).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"[OK] wrote summary: {out}")

    return 0 if not issue_map else 2


if __name__ == "__main__":
    raise SystemExit(main())
