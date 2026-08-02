#!/usr/bin/env python3
"""Build a read-only daily operations ledger across finance and knowledge repos."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Direct execution needs the repository root on sys.path before project imports.
from intelligence.paths import ProjectPaths, default_paths, vector_index_dir_for  # noqa: E402


STATUS_PASS = "PASS"
STATUS_WARN = "WARN"
STATUS_FAIL = "FAIL"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class FileCheck:
    name: str
    path: Path

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "path": str(self.path),
            "exists": self.path.exists(),
        }


def validate_date(value: str) -> str:
    if not DATE_RE.match(value):
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD")
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise argparse.ArgumentTypeError("date must be a valid calendar day") from exc
    return value


def date_compact(date: str) -> str:
    return date.replace("-", "")


def count_files(root: Path, pattern: str = "*") -> int:
    if not root.exists():
        return 0
    return sum(1 for path in root.glob(pattern) if path.is_file())


def load_json(path: Path) -> tuple[Any | None, str | None]:
    if not path.exists():
        return None, "missing"
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:  # pragma: no cover - defensive for local malformed files
        return None, f"{type(exc).__name__}: {exc}"


def latest_file(root: Path, pattern: str) -> Path | None:
    if not root.exists():
        return None
    files = sorted((path for path in root.glob(pattern) if path.is_file()), key=lambda p: p.name)
    return files[-1] if files else None


def expected_market_outputs(paths: ProjectPaths, date: str) -> list[FileCheck]:
    exports = paths.market_exports
    daily_dir = paths.review_daily_root / date
    return [
        FileCheck("daily_review_md", exports / f"{date}-daily-review.md"),
        FileCheck("advancers_ma5_png", exports / f"{date}-advancers-ma5.png"),
        FileCheck("theme_candidates_json", exports / f"{date}-theme-candidates.json"),
        FileCheck("theme_candidates_md", exports / f"{date}-theme-candidates.md"),
        FileCheck("theme_backfill_queue_json", exports / f"{date}-theme-backfill-queue.json"),
        FileCheck("theme_backfill_review_queue_json", exports / f"{date}-theme-backfill-review-queue.json"),
        FileCheck("theme_backfill_review_queue_md", exports / f"{date}-theme-backfill-review-queue.md"),
        FileCheck("daily_review_html", daily_dir / f"{date}-daily-review.html"),
        FileCheck("theme_candidates_html", daily_dir / f"{date}-theme-candidates.html"),
        FileCheck("daily_workflow_summary_json", exports / f"{date}-daily-workflow-summary.json"),
    ]


def scan_market(paths: ProjectPaths, date: str) -> dict[str, Any]:
    checks = [check.as_dict() for check in expected_market_outputs(paths, date)]
    missing = [item for item in checks if not item["exists"]]
    return {
        "status": STATUS_PASS if not missing else STATUS_WARN,
        "checks": checks,
        "missing_count": len(missing),
        "missing": missing,
    }


def scan_morning_briefing(paths: ProjectPaths, date: str) -> dict[str, Any]:
    briefings = paths.knowledge_wiki / "briefings"
    files = sorted(briefings.glob(f"{date}*.md")) if briefings.exists() else []
    return {
        "status": STATUS_PASS if files else STATUS_WARN,
        "root": str(briefings),
        "count": len(files),
        "files": [str(path) for path in files],
    }


def scan_ima_stock(paths: ProjectPaths, date: str) -> dict[str, Any]:
    knowledge_root = paths.knowledge_wiki.parent
    raw_root = paths.knowledge_wiki / "raw" / "ima-stock" / "ingested" / date
    raw_files = [
        path
        for path in raw_root.rglob("*.md")
        if path.is_file() and "manifest" not in path.name.lower()
    ] if raw_root.exists() else []
    inbox = knowledge_root / "未入库"
    done = knowledge_root / "已入库"
    review = knowledge_root / "待人工确认"
    inbox_count = count_files(inbox, "*.md")
    review_count = count_files(review, "*.md")
    status = STATUS_PASS if inbox_count == 0 and review_count == 0 else STATUS_WARN
    return {
        "status": status,
        "raw_root": str(raw_root),
        "raw_md_count": len(raw_files),
        "incoming_uningested_md_count": inbox_count,
        "done_folder_md_count": count_files(done, "**/*.md") if done.exists() else 0,
        "manual_review_md_count": review_count,
        "folders": {
            "inbox": str(inbox),
            "done": str(done),
            "manual_review": str(review),
        },
    }


def scan_relations(paths: ProjectPaths) -> dict[str, Any]:
    relations = paths.knowledge_wiki / "relations"
    names = [
        "evidence_index.json",
        "entity_exposures.json",
        "concept_graph.json",
        "theme_signals.json",
        "catalyst_calendar.json",
        "mention_frequency.json",
    ]
    checks = [FileCheck(name, relations / name).as_dict() for name in names]
    missing = [item for item in checks if not item["exists"]]
    return {
        "status": STATUS_PASS if not missing else STATUS_WARN,
        "root": str(relations),
        "checks": checks,
        "missing": missing,
    }


def scan_debts(paths: ProjectPaths) -> dict[str, Any]:
    raw = paths.knowledge_wiki / "raw"
    theme = raw / "theme-radar"
    ima_audits = raw / "ima-stock" / "audits"
    missing_concepts, concept_error = load_json(theme / "missing-concept-audit.json")
    missing_sources, source_error = load_json(theme / "missing-evidence-source-audit.json")
    latest_ima_path = latest_file(ima_audits, "entity-stock-ima-coverage-*.json")
    ima_coverage, ima_error = load_json(latest_ima_path) if latest_ima_path else (None, "missing")

    concept_count = len((missing_concepts or {}).get("missing_concepts", [])) if isinstance(missing_concepts, dict) else None
    source_count = len((missing_sources or {}).get("missing_sources", [])) if isinstance(missing_sources, dict) else None
    ima_missing_count = len((ima_coverage or {}).get("missing", [])) if isinstance(ima_coverage, dict) else None

    return {
        "status": STATUS_WARN if any(count for count in (concept_count, source_count, ima_missing_count)) else STATUS_PASS,
        "missing_concepts": {
            "count": concept_count,
            "path": str(theme / "missing-concept-audit.json"),
            "error": concept_error,
        },
        "missing_sources": {
            "count": source_count,
            "path": str(theme / "missing-evidence-source-audit.json"),
            "error": source_error,
        },
        "ima_stock_coverage": {
            "missing_count": ima_missing_count,
            "path": str(latest_ima_path) if latest_ima_path else None,
            "error": ima_error,
        },
    }


def build_next_actions(ledger: dict[str, Any]) -> list[str]:
    actions: list[str] = []
    market = ledger["sections"]["market_review"]
    if market["missing"]:
        actions.append("Run or resume finance daily workflow for the date; market review outputs are incomplete.")
    morning = ledger["sections"]["morning_briefing"]
    if morning["count"] == 0:
        actions.append("Ingest or render the morning briefing into wiki/briefings for this date.")
    ima = ledger["sections"]["ima_stock"]
    if ima["incoming_uningested_md_count"]:
        actions.append(f"Run IMA stock-card ingest for {ima['incoming_uningested_md_count']} files in 未入库.")
    if ima["manual_review_md_count"]:
        actions.append(f"Review {ima['manual_review_md_count']} files in 待人工确认 before bulk ingest.")
    debts = ledger["debts"]
    if debts["missing_sources"]["count"]:
        actions.append("Backfill source manifests for missing evidence sources before trusting traceability metrics.")
    if debts["missing_concepts"]["count"]:
        actions.append("Run concept normalization/backfill queue for missing concepts; do not solve this with blind DeepDive.")
    if debts["ima_stock_coverage"]["missing_count"]:
        actions.append("Prioritize IMA stock cards for uncovered stock entities based on market activity, not alphabetically.")
    if not actions:
        actions.append("Daily operational surface is complete; next step is logic-market matching and performance scoring.")
    return actions


def derive_status(ledger: dict[str, Any]) -> str:
    sections = ledger["sections"]
    if any(section["status"] == STATUS_FAIL for section in sections.values()):
        return STATUS_FAIL
    if any(section["status"] == STATUS_WARN for section in sections.values()):
        return STATUS_WARN
    if ledger["debts"]["status"] == STATUS_WARN:
        return STATUS_WARN
    return STATUS_PASS


def build_ledger(date: str, paths: ProjectPaths | None = None) -> dict[str, Any]:
    paths = paths or default_paths()
    ledger = {
        "date": date,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "paths": {
            "finance_root": str(paths.finance_root),
            "knowledge_wiki": str(paths.knowledge_wiki),
            "market_exports": str(paths.market_exports),
        },
        "sections": {
            "market_review": scan_market(paths, date),
            "morning_briefing": scan_morning_briefing(paths, date),
            "ima_stock": scan_ima_stock(paths, date),
            "relations": scan_relations(paths),
        },
        "debts": scan_debts(paths),
    }
    ledger["status"] = derive_status(ledger)
    ledger["next_actions"] = build_next_actions(ledger)
    return ledger


def render_markdown(ledger: dict[str, Any]) -> str:
    date = ledger["date"]
    lines = [
        f"# Daily Ops Ledger - {date}",
        "",
        f"- Status: {ledger['status']}",
        f"- Generated: {ledger['generated_at']}",
        f"- Finance repo: `{ledger['paths']['finance_root']}`",
        f"- Knowledge wiki: `{ledger['paths']['knowledge_wiki']}`",
        "",
        "## Market Review",
        "",
        f"- Missing outputs: {ledger['sections']['market_review']['missing_count']}",
    ]
    for item in ledger["sections"]["market_review"]["missing"]:
        lines.append(f"- Missing `{item['name']}`: `{item['path']}`")

    morning = ledger["sections"]["morning_briefing"]
    lines.extend([
        "",
        "## Morning Briefing",
        "",
        f"- Date-prefixed briefing files: {morning['count']}",
    ])
    for path in morning["files"][:20]:
        lines.append(f"- `{path}`")

    ima = ledger["sections"]["ima_stock"]
    lines.extend([
        "",
        "## IMA Stock Cards",
        "",
        f"- Raw MD for date: {ima['raw_md_count']}",
        f"- 未入库 MD: {ima['incoming_uningested_md_count']}",
        f"- 待人工确认 MD: {ima['manual_review_md_count']}",
        f"- 已入库 MD total: {ima['done_folder_md_count']}",
    ])

    relations = ledger["sections"]["relations"]
    lines.extend([
        "",
        "## Relations Surfaces",
        "",
        f"- Missing relation files: {len(relations['missing'])}",
    ])
    for item in relations["missing"]:
        lines.append(f"- Missing `{item['name']}`: `{item['path']}`")

    debts = ledger["debts"]
    lines.extend([
        "",
        "## Structural Debt",
        "",
        f"- Missing concepts: {debts['missing_concepts']['count']}",
        f"- Missing evidence sources: {debts['missing_sources']['count']}",
        f"- Stock entities without IMA card: {debts['ima_stock_coverage']['missing_count']}",
        "",
        "## Next Actions",
        "",
    ])
    for action in ledger["next_actions"]:
        lines.append(f"- {action}")
    lines.append("")
    return "\n".join(lines)


def write_outputs(ledger: dict[str, Any], out_json: Path, out_md: Path) -> None:
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_md.write_text(render_markdown(ledger), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True, type=validate_date, help="Date in YYYY-MM-DD")
    parser.add_argument("--finance-root", default=None, help="Override finance repo root")
    parser.add_argument("--knowledge-wiki", default=None, help="Override knowledge wiki root")
    parser.add_argument("--out-json", default=None, help="Output JSON path")
    parser.add_argument("--out-md", default=None, help="Output Markdown path")
    parser.add_argument("--print-json", action="store_true", help="Print ledger JSON to stdout")
    return parser


def paths_from_args(args: argparse.Namespace) -> ProjectPaths:
    paths = default_paths()
    finance_root = Path(args.finance_root).expanduser() if args.finance_root else paths.finance_root
    knowledge_wiki = Path(args.knowledge_wiki).expanduser() if args.knowledge_wiki else paths.knowledge_wiki
    return ProjectPaths(
        finance_root=finance_root,
        knowledge_wiki=knowledge_wiki,
        finance_site=paths.finance_site,
        market_snapshot_dir=paths.market_snapshot_dir,
        vector_index_dir=vector_index_dir_for(knowledge_wiki),
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    paths = paths_from_args(args)
    ledger = build_ledger(args.date, paths)
    out_json = Path(args.out_json) if args.out_json else paths.market_exports / f"{args.date}-daily-ops-ledger.json"
    out_md = Path(args.out_md) if args.out_md else paths.market_exports / f"{args.date}-daily-ops-ledger.md"
    write_outputs(ledger, out_json, out_md)
    if args.print_json:
        print(json.dumps(ledger, ensure_ascii=False, indent=2))
    else:
        print(f"wrote {out_json}")
        print(f"wrote {out_md}")
        print(f"status {ledger['status']}")
    return 0 if ledger["status"] in {STATUS_PASS, STATUS_WARN} else 1


if __name__ == "__main__":
    raise SystemExit(main())
