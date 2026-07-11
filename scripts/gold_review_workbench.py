#!/usr/bin/env python3
"""Manage human Gold reviews without auto-approving candidates."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from intelligence.eval.gold_review import (  # noqa: E402
    HUMAN_APPROVAL_CONFIRMATION,
    approve_consensus,
    build_consensus_candidate,
    build_review_template,
    mark_non_approved_status,
    read_json,
    render_review_summary,
    review_completion,
    select_stratified_review_dates,
    validate_review,
    write_json,
)


def _init(args: argparse.Namespace) -> int:
    candidate = read_json(args.candidate)
    review = build_review_template(candidate, reviewer=args.reviewer)
    write_json(args.out, review)
    print(f"written: {args.out}")
    return 0


def _set_claim(args: argparse.Namespace) -> int:
    review = read_json(args.review)
    claims = review.get("claims")
    if not isinstance(claims, dict):
        raise ValueError("review claims must be an object")
    decision = claims.get(args.claim_id)
    if not isinstance(decision, dict):
        raise KeyError(f"unknown claim_id: {args.claim_id}")
    updates = {
        "expected_type": args.expected_type,
        "entity_classification": args.entity_classification,
        "stage_feature": args.stage_feature,
        "causal_support": args.causal_support,
        "timeline_event_id": args.timeline_event_id,
        "timeline_position": args.timeline_position,
        "notes": args.notes,
    }
    for field, value in updates.items():
        if value is not None:
            decision[field] = value
    if args.complete:
        review["review_status"] = "completed"
        review["reviewed_at"] = datetime.now(timezone.utc).isoformat()
    errors = validate_review(review)
    if errors:
        raise ValueError("; ".join(errors))
    write_json(args.review, review, protect_approved=False)
    print(
        json.dumps(
            review_completion(review),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _consensus(args: argparse.Namespace) -> int:
    candidate = read_json(args.candidate)
    reviews = [read_json(path) for path in args.reviews]
    consensus = build_consensus_candidate(candidate, reviews)
    write_json(args.out, consensus)
    print(
        json.dumps(
            {
                "gold_status": consensus["gold_status"],
                "reviewer_agreement": consensus["reviewer_agreement"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print(f"written: {args.out}")
    return 0


def _approve(args: argparse.Namespace) -> int:
    consensus = read_json(args.consensus)
    approved = approve_consensus(
        consensus,
        approver=args.approver,
        confirmation=args.confirmation,
        reviewed_at=args.reviewed_at,
    )
    write_json(args.out, approved)
    print(f"written: {args.out}")
    return 0


def _mark(args: argparse.Namespace) -> int:
    gold = read_json(args.gold)
    updated = mark_non_approved_status(
        gold,
        status=args.status,
        reviewer=args.reviewer,
        notes=args.notes or "",
    )
    write_json(args.out, updated)
    print(f"written: {args.out}")
    return 0


def _summary(args: argparse.Namespace) -> int:
    reviews = [read_json(path) for path in args.reviews]
    summary, html = render_review_summary(reviews)
    write_json(args.json_out, summary, protect_approved=False)
    html_path = Path(args.html_out).expanduser()
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html, encoding="utf-8")
    print(
        json.dumps(summary["agreement"], ensure_ascii=False, indent=2)
    )
    print(f"written: {args.json_out}")
    print(f"written: {args.html_out}")
    return 0


def _select(args: argparse.Namespace) -> int:
    selection = read_json(args.selection)
    dates = select_stratified_review_dates(selection, count=args.count)
    body = {
        "schema_version": "claim-fidelity-gold-review-batch-1.0",
        "requested_count": args.count,
        "selected_count": len(dates),
        "selection_rule": (
            "Deterministic round-robin over month, market stage, and "
            "PIT data completeness; only exact-date registered reports."
        ),
        "dates": dates,
    }
    write_json(args.out, body, protect_approved=False)
    print(
        json.dumps(
            {
                "selected_count": len(dates),
                "report_dates": [
                    row.get("report_date") for row in dates
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print(f"written: {args.out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init")
    init.add_argument("--candidate", required=True)
    init.add_argument("--reviewer", required=True)
    init.add_argument("--out", required=True)
    init.set_defaults(handler=_init)

    set_claim = subparsers.add_parser("set-claim")
    set_claim.add_argument("--review", required=True)
    set_claim.add_argument("--claim-id", required=True)
    set_claim.add_argument("--expected-type")
    set_claim.add_argument("--entity-classification")
    set_claim.add_argument("--stage-feature")
    set_claim.add_argument("--causal-support")
    set_claim.add_argument("--timeline-event-id")
    set_claim.add_argument("--timeline-position", type=int)
    set_claim.add_argument("--notes")
    set_claim.add_argument("--complete", action="store_true")
    set_claim.set_defaults(handler=_set_claim)

    consensus = subparsers.add_parser("consensus")
    consensus.add_argument("--candidate", required=True)
    consensus.add_argument("--reviews", nargs=2, required=True)
    consensus.add_argument("--out", required=True)
    consensus.set_defaults(handler=_consensus)

    approve = subparsers.add_parser("approve")
    approve.add_argument("--consensus", required=True)
    approve.add_argument("--approver", required=True)
    approve.add_argument(
        "--confirmation",
        required=True,
        help=f"Must equal {HUMAN_APPROVAL_CONFIRMATION}",
    )
    approve.add_argument("--reviewed-at")
    approve.add_argument("--out", required=True)
    approve.set_defaults(handler=_approve)

    mark = subparsers.add_parser("mark")
    mark.add_argument("--gold", required=True)
    mark.add_argument(
        "--status",
        choices=[
            "candidate",
            "pending",
            "needs_review",
            "unverifiable",
        ],
        required=True,
    )
    mark.add_argument("--reviewer", required=True)
    mark.add_argument("--notes")
    mark.add_argument("--out", required=True)
    mark.set_defaults(handler=_mark)

    summary = subparsers.add_parser("summary")
    summary.add_argument("--reviews", nargs="+", required=True)
    summary.add_argument("--json-out", required=True)
    summary.add_argument("--html-out", required=True)
    summary.set_defaults(handler=_summary)

    select = subparsers.add_parser("select")
    select.add_argument("--selection", required=True)
    select.add_argument("--count", type=int, default=20)
    select.add_argument("--out", required=True)
    select.set_defaults(handler=_select)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
