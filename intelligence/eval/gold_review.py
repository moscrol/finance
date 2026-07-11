from __future__ import annotations

import json
import hashlib
from copy import deepcopy
from datetime import datetime, timezone
from html import escape
from pathlib import Path

from intelligence.eval.claim_fidelity import (
    CLAIM_TYPES,
    REVIEW_STATUSES,
    build_gold_candidate,
    validate_approved_gold,
)
from intelligence.services.fidelity_contract import validate_daily_agent_report


REVIEW_FIELDS = (
    "expected_type",
    "entity_classification",
    "stage_feature",
    "causal_support",
    "timeline_event_id",
    "timeline_position",
)
HUMAN_APPROVAL_CONFIRMATION = "I_APPROVE_GOLD"
GOLD_SAMPLE_BATCH_SCHEMA_VERSION = "claim-fidelity-gold-sample-batch-1.0"
GOLD_SAMPLE_REVIEW_TARGET_MIN = 150
GOLD_SAMPLE_REVIEW_TARGET_MAX = 300
NON_APPROVED_GOLD_STATUSES = {
    "candidate",
    "pending",
    "needs_review",
    "unverifiable",
}


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


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


def _claim_text(claim: dict[str, object]) -> str:
    for field in ("text_span", "text", "summary"):
        value = claim.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    value = claim.get("value")
    if value not in {None, ""}:
        return str(value)
    return str(claim.get("claim_id") or "")


def _claim_stratum(claim: dict[str, object]) -> str:
    manifest_scope = str(claim.get("manifest_scope") or "unknown")
    claim_type = str(
        claim.get("claim_type") or claim.get("expected_type") or "unknown"
    )
    refs = claim.get("evidence_refs")
    evidence_bucket = (
        "with_evidence"
        if isinstance(refs, list) and bool(refs)
        else "without_evidence"
    )
    public_bucket = (
        "public_narrative"
        if claim.get("narrative_key") or manifest_scope == "public_narrative"
        else "evidence_fact"
    )
    return ":".join(
        (public_bucket, manifest_scope, claim_type, evidence_bucket)
    )


def _sample_id(
    *,
    report_date: str,
    source_report_path: str,
    source_report_sha256: str,
    claim_id: str,
) -> str:
    return "sample-" + hashlib.sha256(
        (
            f"{report_date}\0{source_report_path}\0"
            f"{source_report_sha256}\0{claim_id}"
        ).encode("utf-8")
    ).hexdigest()[:24]


def _claim_sort_key(
    sample: dict[str, object],
    *,
    seed: str,
) -> str:
    return hashlib.sha256(
        f"{seed}\0{sample['sample_id']}\0{sample['stratum']}".encode(
            "utf-8"
        )
    ).hexdigest()


def collect_claim_review_samples(
    report_paths: list[str | Path],
    *,
    target_count: int = 200,
    seed: str = "fidelity-gold-review-v1",
) -> dict[str, object]:
    if target_count < GOLD_SAMPLE_REVIEW_TARGET_MIN:
        raise ValueError("target_count must be at least 150")
    if target_count > GOLD_SAMPLE_REVIEW_TARGET_MAX:
        raise ValueError("target_count must be at most 300")
    source_reports: list[dict[str, object]] = []
    candidates_by_stratum: dict[str, list[dict[str, object]]] = {}
    invalid_reports: list[dict[str, object]] = []
    for raw_path in sorted({str(Path(path).expanduser()) for path in report_paths}):
        path = Path(raw_path)
        report = read_json(path)
        errors = validate_daily_agent_report(report)
        report_date = str(report.get("date") or "")
        report_sha = hashlib.sha256(path.read_bytes()).hexdigest()
        claims = report.get("claims")
        if errors or not isinstance(claims, list):
            invalid_reports.append(
                {
                    "path": str(path),
                    "report_date": report_date,
                    "source_report_sha256": report_sha,
                    "errors": errors
                    or ["daily-agent claims must be a list"],
                }
            )
            continue
        source_reports.append(
            {
                "path": str(path),
                "report_date": report_date,
                "source_report_sha256": report_sha,
                "run_id": report.get("run_id"),
                "artifact_sha": report.get("artifact_sha"),
                "manifest_sha": report.get("manifest_sha"),
                "claim_count": len(claims),
                "contract_status": "valid",
            }
        )
        for index, claim in enumerate(claims):
            if not isinstance(claim, dict):
                continue
            claim_id = str(claim.get("claim_id") or f"claim-{index}")
            sample = {
                "sample_id": _sample_id(
                    report_date=report_date,
                    source_report_path=str(path),
                    source_report_sha256=report_sha,
                    claim_id=claim_id,
                ),
                "report_date": report_date,
                "source_report_path": str(path),
                "source_report_sha256": report_sha,
                "source_run_id": report.get("run_id"),
                "source_artifact_sha": report.get("artifact_sha"),
                "source_manifest_sha": report.get("manifest_sha"),
                "claim_id": claim_id,
                "manifest_scope": claim.get("manifest_scope"),
                "claim_type": claim.get("claim_type"),
                "expected_type": claim.get("expected_type"),
                "subject": claim.get("subject"),
                "predicate": claim.get("predicate"),
                "value": claim.get("value"),
                "location": claim.get("location"),
                "narrative_key": claim.get("narrative_key"),
                "text_span": _claim_text(claim),
                "evidence_refs": claim.get("evidence_refs")
                if isinstance(claim.get("evidence_refs"), list)
                else [],
            }
            sample["stratum"] = _claim_stratum(claim)
            candidates_by_stratum.setdefault(
                str(sample["stratum"]),
                [],
            ).append(sample)
    for rows in candidates_by_stratum.values():
        rows.sort(key=lambda row: _claim_sort_key(row, seed=seed))
    selected: list[dict[str, object]] = []
    while len(selected) < target_count and any(candidates_by_stratum.values()):
        for stratum in sorted(candidates_by_stratum):
            rows = candidates_by_stratum[stratum]
            if rows and len(selected) < target_count:
                selected.append(rows.pop(0))
    selected.sort(key=lambda row: str(row["sample_id"]))
    strata = {}
    selected_by_stratum: dict[str, int] = {}
    for sample in selected:
        key = str(sample["stratum"])
        selected_by_stratum[key] = selected_by_stratum.get(key, 0) + 1
    for key, remaining in sorted(candidates_by_stratum.items()):
        strata[key] = {
            "selected": selected_by_stratum.get(key, 0),
            "remaining": len(remaining),
            "available": selected_by_stratum.get(key, 0) + len(remaining),
        }
    batch = {
        "schema_version": GOLD_SAMPLE_BATCH_SCHEMA_VERSION,
        "seed": seed,
        "target_count": target_count,
        "min_required_count": GOLD_SAMPLE_REVIEW_TARGET_MIN,
        "max_allowed_count": GOLD_SAMPLE_REVIEW_TARGET_MAX,
        "selected_count": len(selected),
        "status": (
            "sampling_ready"
            if len(selected) >= GOLD_SAMPLE_REVIEW_TARGET_MIN
            else "insufficient_forward_claims"
        ),
        "selection_rule": (
            "Validate fidelity-contract reports, bucket by "
            "public/evidence scope + manifest scope + claim type + evidence "
            "coverage, hash-order within strata, then deterministic "
            "round-robin until target_count."
        ),
        "source_reports": source_reports,
        "invalid_reports": invalid_reports,
        "strata": strata,
        "claims": selected,
    }
    batch["batch_sha256"] = _sha256(
        {
            "schema_version": batch["schema_version"],
            "seed": batch["seed"],
            "target_count": batch["target_count"],
            "claims": batch["claims"],
        }
    )
    return batch


def validate_claim_review_batch(batch: dict[str, object]) -> list[str]:
    errors: list[str] = []
    if batch.get("schema_version") != GOLD_SAMPLE_BATCH_SCHEMA_VERSION:
        errors.append("sample batch schema mismatch")
    target = batch.get("target_count")
    if not isinstance(target, int):
        errors.append("target_count must be an integer")
    elif not (
        GOLD_SAMPLE_REVIEW_TARGET_MIN
        <= target
        <= GOLD_SAMPLE_REVIEW_TARGET_MAX
    ):
        errors.append("target_count must be between 150 and 300")
    claims = batch.get("claims")
    if not isinstance(claims, list):
        errors.append("claims must be a list")
        return errors
    if batch.get("selected_count") != len(claims):
        errors.append("selected_count mismatch")
    if len(claims) < GOLD_SAMPLE_REVIEW_TARGET_MIN:
        errors.append("selected_count is below 150")
    seen: set[str] = set()
    for index, sample in enumerate(claims):
        if not isinstance(sample, dict):
            errors.append(f"claims[{index}] must be an object")
            continue
        sample_id = str(sample.get("sample_id") or "")
        if not sample_id:
            errors.append(f"claims[{index}].sample_id is required")
        if sample_id in seen:
            errors.append(f"duplicate sample_id: {sample_id}")
        seen.add(sample_id)
        for field in (
            "report_date",
            "source_report_sha256",
            "claim_id",
            "stratum",
            "text_span",
        ):
            if not sample.get(field):
                errors.append(f"{sample_id or index}.{field} is required")
    expected_sha = _sha256(
        {
            "schema_version": batch.get("schema_version"),
            "seed": batch.get("seed"),
            "target_count": batch.get("target_count"),
            "claims": claims,
        }
    )
    if batch.get("batch_sha256") != expected_sha:
        errors.append("batch_sha256 mismatch")
    return errors


def build_gold_candidate_from_sample_batch(
    batch: dict[str, object],
) -> dict[str, object]:
    errors = validate_claim_review_batch(batch)
    if errors:
        raise ValueError("; ".join(errors))
    claims = batch.get("claims")
    if not isinstance(claims, list):
        raise ValueError("claims must be a list")
    candidate = build_gold_candidate(
        "multi-date",
        str(batch["batch_sha256"]),
        [
            {
                "claim_id": sample["sample_id"],
                "text_span": sample["text_span"],
            }
            for sample in claims
            if isinstance(sample, dict)
        ],
    )
    candidate["schema_version"] = "claim-fidelity-gold-sample-1.0"
    candidate["source_batch_sha256"] = batch["batch_sha256"]
    candidate["sample_count"] = len(claims)
    candidate["sample_metadata"] = {
        str(sample["sample_id"]): sample
        for sample in claims
        if isinstance(sample, dict)
    }
    candidate["instructions"] = {
        **candidate["instructions"],
        "blind_review_protocol": (
            "Each reviewer fills an independent file. Do not inspect the "
            "other reviewer file or consensus output before marking complete."
        ),
        "minimum_sample_count": GOLD_SAMPLE_REVIEW_TARGET_MIN,
        "maximum_sample_count": GOLD_SAMPLE_REVIEW_TARGET_MAX,
    }
    return candidate


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
        "source_batch_sha256": candidate.get("source_batch_sha256"),
        "sample_metadata": deepcopy(candidate.get("sample_metadata") or {}),
        "instructions": {
            "rule": (
                "Set every applicable field explicitly. "
                "pending, needs_review, and unverifiable never count as pass."
            ),
            "allowed_claim_types": sorted(CLAIM_TYPES),
            "allowed_review_statuses": sorted(REVIEW_STATUSES),
            "blind_review_protocol": (
                "Complete this file independently. Do not read another "
                "reviewer file or consensus output until both reviews are "
                "marked completed."
            ),
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
    if left.get("reviewer") == right.get("reviewer"):
        raise ValueError("independent reviews require two reviewers")
    left_claims = left.get("claims")
    right_claims = right.get("claims")
    if not isinstance(left_claims, dict) or not isinstance(right_claims, dict):
        raise ValueError("both reviews require claims")
    compared = agreed = 0
    by_field: dict[str, dict[str, object]] = {
        field: {
            "agreed": 0,
            "compared": 0,
            "value": None,
            "kappa": None,
            "left_counts": {},
            "right_counts": {},
        }
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
            left_counts = by_field[field]["left_counts"]
            right_counts = by_field[field]["right_counts"]
            if isinstance(left_counts, dict):
                key = str(left_value)
                left_counts[key] = int(left_counts.get(key, 0)) + 1
            if isinstance(right_counts, dict):
                key = str(right_value)
                right_counts[key] = int(right_counts.get(key, 0)) + 1
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
        field_agreed = int(summary["agreed"])
        summary["value"] = (
            round(field_agreed / field_compared, 6)
            if field_compared
            else None
        )
        left_counts = summary["left_counts"]
        right_counts = summary["right_counts"]
        if (
            isinstance(left_counts, dict)
            and isinstance(right_counts, dict)
            and field_compared
        ):
            expected = sum(
                int(left_counts.get(value, 0))
                * int(right_counts.get(value, 0))
                for value in set(left_counts) | set(right_counts)
            ) / (field_compared * field_compared)
            observed = field_agreed / field_compared
            summary["kappa"] = (
                1.0
                if expected == 1.0 and observed == 1.0
                else (
                    round((observed - expected) / (1 - expected), 6)
                    if expected != 1.0
                    else None
                )
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
