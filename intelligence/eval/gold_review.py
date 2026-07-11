from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from html import escape
from pathlib import Path

from intelligence.eval.claim_fidelity import (
    CLAIM_TYPES,
    REVIEW_STATUSES,
    validate_approved_gold,
)


REVIEW_FIELDS = (
    "expected_type",
    "entity_classification",
    "stage_feature",
    "causal_support",
    "timeline_event_id",
    "timeline_position",
)
HUMAN_APPROVAL_CONFIRMATION = "I_APPROVE_GOLD"
NON_APPROVED_GOLD_STATUSES = {
    "candidate",
    "pending",
    "needs_review",
    "unverifiable",
}


def read_json(path: str | Path) -> dict[str, object]:
    body = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    if not isinstance(body, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return body


def write_json(
    path: str | Path,
    body: dict[str, object],
    *,
    protect_approved: bool = True,
) -> None:
    target = Path(path).expanduser()
    if target.exists() and protect_approved:
        existing = read_json(target)
        if existing.get("gold_status") == "approved":
            raise FileExistsError("approved gold cannot be overwritten")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(body, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def build_review_template(
    candidate: dict[str, object],
    *,
    reviewer: str,
) -> dict[str, object]:
    if candidate.get("gold_status") != "candidate":
        raise ValueError("review templates require gold_status=candidate")
    claims = candidate.get("claims")
    if not isinstance(claims, dict):
        raise ValueError("candidate claims must be an object")
    return {
        "schema_version": "claim-fidelity-gold-review-1.0",
        "report_date": candidate.get("report_date"),
        "source_report_sha256": candidate.get("source_report_sha256"),
        "reviewer": reviewer,
        "reviewed_at": None,
        "review_status": "in_review",
        "claims": deepcopy(claims),
        "instructions": {
            "rule": (
                "Set every applicable field explicitly. "
                "pending, needs_review, and unverifiable never count as pass."
            ),
            "allowed_claim_types": sorted(CLAIM_TYPES),
            "allowed_review_statuses": sorted(REVIEW_STATUSES),
        },
    }


def mark_non_approved_status(
    gold: dict[str, object],
    *,
    status: str,
    reviewer: str,
    reviewed_at: str | None = None,
    notes: str = "",
) -> dict[str, object]:
    if status not in NON_APPROVED_GOLD_STATUSES:
        raise ValueError("status must remain non-approved")
    if gold.get("gold_status") == "approved":
        raise ValueError("approved gold cannot be downgraded")
    updated = deepcopy(gold)
    updated["gold_status"] = status
    updated["reviewer"] = reviewer
    updated["reviewed_at"] = reviewed_at or datetime.now(
        timezone.utc
    ).isoformat()
    if notes:
        updated["review_notes"] = notes
    return updated


def validate_review(review: dict[str, object]) -> list[str]:
    errors: list[str] = []
    if not review.get("reviewer"):
        errors.append("reviewer is required")
    if review.get("review_status") not in {"in_review", "completed"}:
        errors.append("review_status must be in_review or completed")
    if review.get("review_status") == "completed" and not review.get(
        "reviewed_at"
    ):
        errors.append("completed review requires reviewed_at")
    claims = review.get("claims")
    if not isinstance(claims, dict):
        errors.append("claims must be an object")
        return errors
    for claim_id, decision in claims.items():
        if not isinstance(decision, dict):
            errors.append(f"claims.{claim_id} must be an object")
            continue
        expected_type = decision.get("expected_type")
        if expected_type is not None and expected_type not in CLAIM_TYPES:
            errors.append(f"claims.{claim_id}.expected_type is invalid")
        for field in (
            "entity_classification",
            "stage_feature",
            "causal_support",
        ):
            if decision.get(field, "pending") not in REVIEW_STATUSES:
                errors.append(f"claims.{claim_id}.{field} is invalid")
        position = decision.get("timeline_position")
        if position is not None and not isinstance(position, int):
            errors.append(
                f"claims.{claim_id}.timeline_position must be integer or null"
            )
    return errors


def review_completion(review: dict[str, object]) -> dict[str, object]:
    claims = review.get("claims")
    if not isinstance(claims, dict):
        return {
            "complete": False,
            "completed_claims": 0,
            "claim_count": 0,
            "pending_fields": ["claims"],
        }
    pending_fields: list[str] = []
    completed_claims = 0
    for claim_id, decision in claims.items():
        if not isinstance(decision, dict):
            pending_fields.append(f"{claim_id}.*")
            continue
        claim_pending = []
        if decision.get("expected_type") not in CLAIM_TYPES:
            claim_pending.append("expected_type")
        for field in (
            "entity_classification",
            "stage_feature",
            "causal_support",
        ):
            if decision.get(field) in {None, "pending"}:
                claim_pending.append(field)
        if claim_pending:
            pending_fields.extend(
                f"{claim_id}.{field}" for field in claim_pending
            )
        else:
            completed_claims += 1
    complete = review.get("review_status") == "completed"
    complete = complete and not validate_review(review)
    complete = complete and not pending_fields
    return {
        "complete": complete,
        "completed_claims": completed_claims,
        "claim_count": len(claims),
        "pending_fields": pending_fields,
    }


def reviewer_agreement(
    left: dict[str, object],
    right: dict[str, object],
) -> dict[str, object]:
    left_claims = left.get("claims")
    right_claims = right.get("claims")
    if not isinstance(left_claims, dict) or not isinstance(right_claims, dict):
        raise ValueError("both reviews require claims")
    compared = agreed = 0
    by_field = {
        field: {"agreed": 0, "compared": 0, "value": None}
        for field in REVIEW_FIELDS
    }
    disagreements: list[dict[str, object]] = []
    claim_ids = sorted(set(left_claims) & set(right_claims))
    for claim_id in claim_ids:
        left_decision = left_claims[claim_id]
        right_decision = right_claims[claim_id]
        if not isinstance(left_decision, dict) or not isinstance(
            right_decision,
            dict,
        ):
            continue
        for field in REVIEW_FIELDS:
            left_value = left_decision.get(field)
            right_value = right_decision.get(field)
            if left_value in {None, "pending"} and right_value in {
                None,
                "pending",
            }:
                continue
            compared += 1
            by_field[field]["compared"] += 1
            if left_value == right_value:
                agreed += 1
                by_field[field]["agreed"] += 1
            else:
                disagreements.append(
                    {
                        "claim_id": claim_id,
                        "field": field,
                        "left": left_value,
                        "right": right_value,
                    }
                )
    for field, summary in by_field.items():
        field_compared = int(summary["compared"])
        summary["value"] = (
            round(int(summary["agreed"]) / field_compared, 6)
            if field_compared
            else None
        )
    return {
        "reviewers": [left.get("reviewer"), right.get("reviewer")],
        "agreed": agreed,
        "compared": compared,
        "value": round(agreed / compared, 6) if compared else None,
        "target": 0.8,
        "target_met": compared > 0 and agreed / compared >= 0.8,
        "by_field": by_field,
        "disagreements": disagreements,
    }


def build_consensus_candidate(
    candidate: dict[str, object],
    reviews: list[dict[str, object]],
) -> dict[str, object]:
    if len(reviews) != 2:
        raise ValueError("exactly two reviews are required")
    for review in reviews:
        completion = review_completion(review)
        if not completion["complete"]:
            raise ValueError("both reviews must be completed")
    candidate_claims = candidate.get("claims")
    if not isinstance(candidate_claims, dict):
        raise ValueError("candidate claims must be an object")
    left_claims = reviews[0]["claims"]
    right_claims = reviews[1]["claims"]
    if not isinstance(left_claims, dict) or not isinstance(right_claims, dict):
        raise ValueError("review claims must be objects")
    claims: dict[str, dict[str, object]] = {}
    for claim_id, source_claim in candidate_claims.items():
        if not isinstance(source_claim, dict):
            continue
        decision = deepcopy(source_claim)
        left = left_claims.get(claim_id)
        right = right_claims.get(claim_id)
        if not isinstance(left, dict) or not isinstance(right, dict):
            raise ValueError(f"review missing claim {claim_id}")
        for field in REVIEW_FIELDS:
            decision[field] = (
                left.get(field)
                if left.get(field) == right.get(field)
                else (
                    None
                    if field
                    in {
                        "expected_type",
                        "timeline_event_id",
                        "timeline_position",
                    }
                    else "pending"
                )
            )
        notes = [
            str(value).strip()
            for value in (left.get("notes"), right.get("notes"))
            if str(value or "").strip()
        ]
        decision["notes"] = "\n".join(dict.fromkeys(notes))
        claims[str(claim_id)] = decision
    agreement = reviewer_agreement(reviews[0], reviews[1])
    gold_status = (
        "needs_review"
        if agreement["disagreements"]
        else "candidate"
    )
    return {
        "schema_version": "claim-fidelity-gold-1.0",
        "report_date": candidate.get("report_date"),
        "source_report_sha256": candidate.get("source_report_sha256"),
        "gold_status": gold_status,
        "reviewer": None,
        "reviewed_at": None,
        "claims": claims,
        "review_history": [
            {
                "reviewer": review.get("reviewer"),
                "reviewed_at": review.get("reviewed_at"),
                "review_status": review.get("review_status"),
            }
            for review in reviews
        ],
        "reviewer_agreement": agreement,
        "instructions": {
            "rule": (
                "This consensus remains a candidate. "
                "A human must explicitly approve it."
            )
        },
    }


def approve_consensus(
    consensus: dict[str, object],
    *,
    approver: str,
    confirmation: str,
    reviewed_at: str | None = None,
) -> dict[str, object]:
    if confirmation != HUMAN_APPROVAL_CONFIRMATION:
        raise PermissionError("explicit human approval confirmation required")
    if consensus.get("gold_status") != "candidate":
        raise ValueError("only a gold candidate can be approved")
    agreement = consensus.get("reviewer_agreement")
    if not isinstance(agreement, dict):
        raise ValueError("reviewer agreement is required")
    disagreements = agreement.get("disagreements")
    if isinstance(disagreements, list) and disagreements:
        raise ValueError("review disagreements must be adjudicated first")
    approved = deepcopy(consensus)
    approved["gold_status"] = "approved"
    approved["reviewer"] = approver
    approved["reviewed_at"] = reviewed_at or datetime.now(
        timezone.utc
    ).isoformat()
    errors = validate_approved_gold(approved)
    if errors:
        raise ValueError("; ".join(errors))
    return approved


def select_stratified_review_dates(
    selection: dict[str, object],
    *,
    count: int = 20,
) -> list[dict[str, object]]:
    dates = selection.get("dates")
    if not isinstance(dates, list):
        raise ValueError("selection dates must be a list")
    available = []
    for row in dates:
        if not isinstance(row, dict):
            continue
        if not row.get("canonical_report_path"):
            continue
        if row.get("report_status") == "registered":
            available.append(row)
    buckets: dict[tuple[str, str, str], list[dict[str, object]]] = {}
    for row in available:
        key = (
            str(row.get("month") or ""),
            str(row.get("market_stage") or ""),
            str(row.get("data_completeness") or ""),
        )
        buckets.setdefault(key, []).append(row)
    for rows in buckets.values():
        rows.sort(key=lambda row: str(row.get("report_date") or ""))
    selected: list[dict[str, object]] = []
    while len(selected) < min(count, len(available)):
        progressed = False
        for key in sorted(buckets):
            if buckets[key] and len(selected) < count:
                selected.append(buckets[key].pop(0))
                progressed = True
        if not progressed:
            break
    return selected


def render_review_summary(
    reviews: list[dict[str, object]],
) -> tuple[dict[str, object], str]:
    completed = sum(
        bool(review_completion(review)["complete"]) for review in reviews
    )
    pairs = []
    grouped: dict[tuple[str, str], list[dict[str, object]]] = {}
    for review in reviews:
        key = (
            str(review.get("report_date") or ""),
            str(review.get("source_report_sha256") or ""),
        )
        grouped.setdefault(key, []).append(review)
    for key, group in sorted(grouped.items()):
        if len(group) == 2:
            pairs.append(
                {
                    "report_date": key[0],
                    **reviewer_agreement(group[0], group[1]),
                }
            )
    total_compared = sum(int(pair["compared"]) for pair in pairs)
    total_agreed = sum(int(pair["agreed"]) for pair in pairs)
    summary = {
        "schema_version": "claim-fidelity-gold-review-summary-1.0",
        "review_count": len(reviews),
        "completed_review_count": completed,
        "paired_report_count": len(pairs),
        "agreement": {
            "agreed": total_agreed,
            "compared": total_compared,
            "value": (
                round(total_agreed / total_compared, 6)
                if total_compared
                else None
            ),
            "target": 0.8,
        },
        "pairs": pairs,
    }
    rows = "".join(
        "<tr>"
        f"<td>{escape(str(pair['report_date']))}</td>"
        f"<td>{escape(' / '.join(str(item) for item in pair['reviewers']))}</td>"
        f"<td>{pair['agreed']} / {pair['compared']}</td>"
        f"<td>{escape(str(pair['value']))}</td>"
        f"<td>{len(pair['disagreements'])}</td>"
        "</tr>"
        for pair in pairs
    )
    html = (
        "<!doctype html><html lang=\"zh-CN\"><meta charset=\"utf-8\">"
        "<title>Gold 人工审核工作台</title>"
        "<style>body{font:14px system-ui;margin:32px;color:#172033}"
        "table{border-collapse:collapse;width:100%}"
        "th,td{border:1px solid #d8dee9;padding:8px;text-align:left}"
        "th{background:#f5f7fa}</style>"
        "<h1>Gold 人工审核工作台</h1>"
        f"<p>审核 {completed}/{len(reviews)} 完成；"
        f"双人一致率 {summary['agreement']['value']}，目标 ≥ 0.8。</p>"
        "<table><thead><tr><th>日期</th><th>审核人</th>"
        "<th>一致</th><th>一致率</th><th>分歧</th></tr></thead>"
        f"<tbody>{rows}</tbody></table></html>"
    )
    return summary, html
