"""Audit L6 evidence without promoting judge status or activity into quality.

Claim semantics remain a source-level reviewer responsibility. The review must
bind the exact episode hash and supply verbatim source excerpts. Missing review
or an unobserved mechanism never becomes PASS. This tool does not call models.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def changed_model_drafts(episode: dict) -> list[dict]:
    drafts = []
    for event in episode.get("events", []):
        payload = event.get("payload", {})
        if event.get("kind") != "model_turn" or payload.get("error"):
            continue
        try:
            answer = json.loads(payload.get("content") or "null")
        except (ValueError, TypeError):
            continue
        if isinstance(answer, dict) and isinstance(answer.get("draft"), str):
            drafts.append(
                {
                    "sequence": event["sequence"],
                    "phase": payload.get("phase"),
                    "served_model": payload.get("served_model"),
                    "draft_sha256": hashlib.sha256(
                        answer["draft"].encode()
                    ).hexdigest(),
                }
            )
    return drafts


def audit(episode: dict, review: dict, *, episode_sha256: str) -> dict:
    if review.get("episode_sha256") != episode_sha256:
        raise ValueError("review does not bind this episode")
    semantic = episode.get("semantic_verifier", {})
    drafts = changed_model_drafts(episode)
    revised = episode.get("repair_attempts", 0) >= 1 and any(
        draft["phase"] == "repair"
        and draft["served_model"]
        and any(
            prior["served_model"] and prior["draft_sha256"] != draft["draft_sha256"]
            for prior in drafts[:index]
        )
        for index, draft in enumerate(drafts)
    )
    evidence = {
        e["content_hash"]: e for e in episode.get("outcome", {}).get("evidence", [])
    }
    decisions = semantic.get("sentence_verdicts", [])
    failed_claims = []
    reviewed = []
    for row in review.get("claims", []):
        source = evidence.get(row.get("evidence_hash"))
        if (
            source is None
            or not row.get("source_excerpt")
            or row["source_excerpt"] not in source.get("detail", "")
        ):
            raise ValueError("review source excerpt not found in bound evidence")
        if not row.get("sentence") or row["sentence"] not in episode.get(
            "outcome", {}
        ).get("draft", ""):
            raise ValueError("review claim not found in submitted draft")
        supported = all(
            row.get(field) is True
            for field in (
                "entity_matches",
                "date_matches",
                "window_matches",
                "unit_matches",
                "numeric_supported",
            )
        )
        deleted = any(
            v.get("sentence") == row["sentence"] and v.get("decision") == "deleted"
            for v in decisions
        )
        lost = (
            supported and deleted and row.get("condition_retained_in_public") is False
        )
        if lost:
            failed_claims.append(row["sentence"])
        reviewed.append(
            {
                "sentence": row["sentence"],
                "source_supported": supported,
                "deleted": deleted,
                "supported_condition_lost": lost,
            }
        )
    late = review.get("late_reports", [])
    for row in late:
        if row.get("adopted") not in (True, False) or not row.get("artifact_pointer"):
            raise ValueError(
                "late report review requires a decision and evidence pointer"
            )
    late_adopted = any(row["adopted"] for row in late)
    findings = []
    if failed_claims:
        findings.append("evidence_supported_numeric_condition_deleted")
    if late_adopted:
        findings.append("late_judge_report_adopted")
    if findings:
        verdict = "NOT_PASSED"
    elif semantic.get("judge_status") == "unavailable":
        verdict = "BLOCKED_JUDGE_UNAVAILABLE"
    elif review.get("all_numeric_conditions_reviewed") is not True:
        verdict = "BLOCKED_CLAIM_REVIEW"
    elif (
        not revised or not late or not any(row["source_supported"] for row in reviewed)
    ):
        verdict = "NOT_EXERCISED"
    else:
        verdict = "PASS"
    return {
        "verdict": verdict,
        "episode_sha256": episode_sha256,
        "model_revision_observed": revised,
        "drafts": drafts,
        "claims": reviewed,
        "supported_conditions_lost": failed_claims,
        "late_report_observed": bool(late),
        "late_report_adopted": late_adopted,
        "findings": findings,
        "all_numeric_conditions_reviewed": review.get("all_numeric_conditions_reviewed")
        is True,
        "judge_status": semantic.get("judge_status"),
        "judge_mode": semantic.get("judge_mode"),
        "independent_financial_review": False,
        "scope": "source-review aggregation; synthetic deadline proof and batch closure are separate prerequisites",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(
        json.loads(args.episode.read_text()),
        json.loads(args.review.read_text()),
        episode_sha256=fingerprint(args.episode),
    )
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"verdict": result["verdict"], "output": str(args.output)}))
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
