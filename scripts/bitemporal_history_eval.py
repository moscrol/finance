#!/usr/bin/env python3
"""Build paired final-history and strict point-in-time archives."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from intelligence.eval.bitemporal_history import (  # noqa: E402
    build_final_history,
    build_gold_standard_template,
    compare_snapshots,
    iter_pilot_cases,
    render_pilot_report,
    write_json,
)

DEFAULT_CONTRACTS = (("fact_market_daily", "total_amount", 20),)
ROW_METADATA_FIELDS = {"valid_time", "known_at", "revision_note"}


def _parse_dates(raw: str) -> list[str]:
    value = raw.strip()
    if value.startswith("["):
        parsed = json.loads(value)
        if not isinstance(parsed, list):
            raise ValueError("--dates JSON must be a list")
        dates = [str(item).strip() for item in parsed]
    else:
        dates = [item.strip() for item in value.split(",")]
    dates = [item.strip("\"'") for item in dates if item]
    if len(dates) != len(set(dates)):
        raise ValueError("--dates contains duplicates")
    return dates


def _parse_contract(raw: str) -> tuple[str, str, int]:
    parts = raw.split(":")
    if len(parts) != 3:
        raise ValueError("feature contract must be TABLE:METRIC:DAYS")
    return parts[0], parts[1], int(parts[2])


def _rows(snapshot: dict) -> int:
    return sum(
        int(table.get("row_count", table.get("known_row_count", 0)))
        for table in snapshot["tables"].values()
    )


def _ex_post_rows(snapshot: dict) -> int:
    return sum(
        int(table.get("ex_post_rows", 0))
        for table in snapshot["tables"].values()
    )


def _field_count(snapshot: dict) -> int:
    return sum(
        value is not None
        for table in snapshot["tables"].values()
        for row in table["rows"]
        for field, value in row.items()
        if field not in ROW_METADATA_FIELDS
    )


def _changed_field_count(comparison: dict) -> int:
    return sum(
        len(change["field_changes"])
        for table in comparison["tables"].values()
        for change in table["changes"]
    )


def _load_json(path: str | Path) -> dict:
    return json.loads(Path(path).expanduser().read_text(encoding="utf-8"))


def cmd_pilot(args: argparse.Namespace) -> int:
    dates = _parse_dates(args.dates)
    output = Path(args.out_dir).expanduser()
    final_dir = output / "final_history"
    known_dir = output / "as_known_at"
    gold_dir = output / "gold"
    if final_dir == known_dir:
        raise ValueError("final and known outputs must be physically isolated")

    contracts = (
        [_parse_contract(raw) for raw in args.feature_contract]
        if args.feature_contract
        else list(DEFAULT_CONTRACTS)
    )
    cases = []
    final_counts: Counter[str] = Counter()
    known_counts: Counter[str] = Counter()
    comparison_counts: Counter[str] = Counter()
    pilot_cases = iter_pilot_cases(
        dates,
        args.db,
        args.kb_root,
        args.finance_root,
        contracts,
    )
    for pilot_case in pilot_cases:
        value = pilot_case["date"]
        cutoff = pilot_case["cutoff"]
        final = pilot_case["final"]
        known = pilot_case["known"]
        comparison = pilot_case["comparison"]
        contract_results = pilot_case["feature_contracts"]
        final_path = final_dir / f"{value}.final.json"
        known_path = known_dir / f"{value}.known.json"
        if final_path.parent == known_path.parent:
            raise ValueError("final and known snapshots share a directory")
        write_json(final_path, final)
        write_json(known_path, known)
        write_json(
            gold_dir / f"{value}.gold.json",
            build_gold_standard_template(value),
        )

        final_counts[final["status"]] += 1
        known_counts[known["status"]] += 1
        comparison_counts[comparison["status"]] += 1
        artifact_count = sum(
            int(repo["artifact_count"])
            for repo in known["repositories"].values()
        )
        final_fields = _field_count(final)
        known_fields = _field_count(known)
        cases.append(
            {
                "date": value,
                "cutoff_timestamp": cutoff.isoformat(),
                "final_path": str(final_path),
                "known_path": str(known_path),
                "gold_path": str(gold_dir / f"{value}.gold.json"),
                "final_status": final["status"],
                "known_status": known["status"],
                "comparison_status": comparison["status"],
                "final_rows": _rows(final),
                "known_rows": _rows(known),
                "ex_post_rows": _ex_post_rows(final),
                "artifact_count": artifact_count,
                "needs_review_count": len(comparison["needs_review"]),
                "comparison_counts": comparison["counts"],
                "final_field_count": final_fields,
                "known_field_count": known_fields,
                "missing_field_count": max(final_fields - known_fields, 0),
                "conflict_field_count": _changed_field_count(comparison),
                "field_coverage_pct": (
                    round(100 * known_fields / final_fields, 2)
                    if final_fields
                    else 0.0
                ),
                "feature_contracts": contract_results,
                "feature_contract_status": (
                    "eligible"
                    if contract_results
                    and all(result["eligible"] for result in contract_results)
                    else "ineligible"
                ),
            }
        )
    report = {
        "schema_version": "bitemporal-history-pilot-1.0",
        "task_id": "bitemporal-history-v1",
        "date_count": len(dates),
        "dates": dates,
        "output_isolation": {
            "final_history": str(final_dir),
            "as_known_at": str(known_dir),
            "physically_separate": final_dir != known_dir,
        },
        "status_counts": {
            "final": dict(final_counts),
            "known": dict(known_counts),
            "comparison": dict(comparison_counts),
        },
        "cases": cases,
        "decision_eligible": False,
        "next_gate": (
            "Human review is required before expanding beyond 10 dates."
        ),
    }
    write_json(output / "pilot.report.json", report)
    report_path = output / "pilot.report.md"
    report_path.write_text(render_pilot_report(report), encoding="utf-8")
    print(json.dumps(report["status_counts"], ensure_ascii=False))
    print(f"written: {report_path}")
    return 0


def cmd_outcomes(args: argparse.Namespace) -> int:
    output = Path(args.out_dir).expanduser()
    for value in _parse_dates(args.dates):
        write_json(
            output / f"{value}.final.json",
            build_final_history(value, args.db),
        )
    return 0


def cmd_gold_template(args: argparse.Namespace) -> int:
    write_json(args.out, build_gold_standard_template(args.date))
    return 0


def cmd_score(args: argparse.Namespace) -> int:
    comparison = compare_snapshots(
        _load_json(args.final),
        _load_json(args.known),
    )
    write_json(args.out, comparison)
    print(json.dumps(comparison["counts"], ensure_ascii=False))
    return 0


def cmd_audit_ledger(args: argparse.Namespace) -> int:
    reports = [_load_json(path) for path in args.report]
    cases = [case for report in reports for case in report["cases"]]
    status_counts: Counter[str] = Counter(
        case["known_status"] for case in cases
    )
    ledger = {
        "schema_version": "bitemporal-history-ledger-1.0",
        "report_count": len(reports),
        "case_count": len(cases),
        "known_status_counts": dict(status_counts),
        "average_field_coverage_pct": (
            round(
                sum(case["field_coverage_pct"] for case in cases)
                / len(cases),
                2,
            )
            if cases
            else 0.0
        ),
        "needs_review_count": sum(
            case["needs_review_count"] for case in cases
        ),
        "decision_eligible": False,
        "cases": cases,
    }
    write_json(args.out, ledger)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    pilot = sub.add_parser(
        "pilot",
        help="生成10日双时态档案、金标准模板和覆盖报告",
    )
    pilot.add_argument("--db", required=True)
    pilot.add_argument("--kb-root", required=True)
    pilot.add_argument("--finance-root", required=True)
    pilot.add_argument("--dates", required=True)
    pilot.add_argument("--out-dir", required=True)
    pilot.add_argument(
        "--feature-contract",
        action="append",
        default=[],
        metavar="TABLE:METRIC:DAYS",
    )
    pilot.set_defaults(func=cmd_pilot)

    outcomes = sub.add_parser(
        "outcomes",
        help="生成最终历史视图",
    )
    outcomes.add_argument("--db", required=True)
    outcomes.add_argument("--dates", required=True)
    outcomes.add_argument("--out-dir", required=True)
    outcomes.set_defaults(func=cmd_outcomes)

    gold = sub.add_parser(
        "gold-template",
        help="生成人工金标准模板",
    )
    gold.add_argument("--date", required=True)
    gold.add_argument("--out", required=True)
    gold.set_defaults(func=cmd_gold_template)

    score = sub.add_parser(
        "score",
        help="比较一对 final/known 快照",
    )
    score.add_argument("--final", required=True)
    score.add_argument("--known", required=True)
    score.add_argument("--out", required=True)
    score.set_defaults(func=cmd_score)

    ledger = sub.add_parser(
        "audit-ledger",
        help="聚合一个或多个 pilot 报告",
    )
    ledger.add_argument("--report", action="append", required=True)
    ledger.add_argument("--out", required=True)
    ledger.set_defaults(func=cmd_audit_ledger)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
