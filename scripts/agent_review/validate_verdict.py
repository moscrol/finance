from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence

from scripts.agent_review.contract import (
    EXTERNAL_REVIEWER,
    PROVISIONAL_REVIEWER,
    ReviewRequest,
    git_output,
    is_ancestor,
    sha256_file,
    validate_request,
)


Authority = Literal["external", "provisional", "none"]
VALID_VERDICT_STATUSES = frozenset({"PASS", "CHANGES_REQUIRED", "BLOCKED"})
VALID_CHECK_STATUSES = frozenset({"PASS", "PARTIAL", "FAIL"})
VALID_SEVERITIES = frozenset({"high", "medium", "low", "info"})
BASELINE_CHECKS = frozenset(
    {"git_diff_check", "artifact_hygiene", "canonical_safety"}
)


@dataclass(frozen=True)
class VerdictValidation:
    valid: bool
    authority: Authority
    errors: tuple[str, ...]
    status: str
    review_id: str = ""
    commit: str = ""


def _load_object(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _dedupe(values: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _required_manifest(request: ReviewRequest) -> frozenset[str]:
    tests = {
        test
        for artifact_tests in request.artifact_tests.values()
        for test in artifact_tests
    }
    return frozenset(request.required_checks) | frozenset(tests) | BASELINE_CHECKS


def _validate_findings(value: object, errors: list[str]) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, list):
        errors.append("findings")
        return ()
    findings: list[Mapping[str, Any]] = []
    required = {
        "severity",
        "file",
        "line",
        "title",
        "evidence",
        "recommendation",
    }
    for item in value:
        if not isinstance(item, dict) or set(item) != required:
            errors.append("findings")
            continue
        if item.get("severity") not in VALID_SEVERITIES:
            errors.append("findings")
            continue
        if not isinstance(item.get("line"), int) or item["line"] < 0:
            errors.append("findings")
            continue
        if any(
            not isinstance(item.get(field), str) or not item[field].strip()
            for field in ("file", "title", "evidence", "recommendation")
        ):
            errors.append("findings")
            continue
        findings.append(item)
    return tuple(findings)


def _validate_checks(
    value: object,
    *,
    required: frozenset[str],
    errors: list[str],
) -> dict[str, str]:
    if not isinstance(value, dict):
        errors.append("checks")
        return {}
    statuses: dict[str, str] = {}
    for name, result in value.items():
        if not isinstance(name, str) or not isinstance(result, dict):
            errors.append("checks")
            continue
        if set(result) != {"status", "evidence"}:
            errors.append("checks")
            continue
        status = result.get("status")
        evidence = result.get("evidence")
        if status not in VALID_CHECK_STATUSES or not isinstance(evidence, str) or not evidence.strip():
            errors.append("checks")
            continue
        statuses[name] = status
    if not required.issubset(statuses):
        errors.append("check_manifest")
    return statuses


def validate_verdict(
    raw: Mapping[str, Any],
    *,
    request: ReviewRequest,
    request_sha256: str,
    repo: Path,
    authority: Literal["external", "provisional"],
    current_tip: str | None = None,
    expected_review_id: str | None = None,
) -> VerdictValidation:
    errors: list[str] = []
    expected_fields = {
        "schema_version",
        "review_id",
        "commit",
        "request_sha256",
        "status",
        "reviewer",
        "reviewer_class",
        "authority",
        "findings",
        "checks",
        "reviewed_at",
        "summary",
        "next_action",
    }
    if set(raw) != expected_fields:
        errors.append("verdict_fields")
    if raw.get("schema_version") != 2:
        errors.append("schema_version")
    if raw.get("review_id") != request.review_id or (
        expected_review_id is not None and raw.get("review_id") != expected_review_id
    ):
        errors.append("verdict_review_id")
    if raw.get("commit") != request.commit:
        errors.append("verdict_commit")
    if raw.get("request_sha256") != request_sha256:
        errors.append("request_hash_mismatch")
    status = raw.get("status")
    if status not in VALID_VERDICT_STATUSES:
        errors.append("verdict_status")
        status = ""
    reviewer = raw.get("reviewer")
    reviewer_class = raw.get("reviewer_class")
    declared_authority = raw.get("authority")
    if authority == "external":
        if reviewer != EXTERNAL_REVIEWER or reviewer_class != "external":
            errors.append("reviewer_identity")
        if declared_authority != "external":
            errors.append("verdict_authority")
    else:
        if reviewer != PROVISIONAL_REVIEWER or reviewer_class != "producer_fallback":
            errors.append("reviewer_identity")
        if declared_authority != "provisional":
            errors.append("verdict_authority")
        if request.intensity == "release":
            errors.append("release_requires_external")

    reviewed_at = raw.get("reviewed_at")
    try:
        parsed_reviewed_at = (
            datetime.fromisoformat(reviewed_at) if isinstance(reviewed_at, str) else None
        )
    except ValueError:
        parsed_reviewed_at = None
    if parsed_reviewed_at is None or parsed_reviewed_at.tzinfo is None:
        errors.append("reviewed_at")
    if not isinstance(raw.get("summary"), str) or not str(raw.get("summary", "")).strip():
        errors.append("summary")
    if not isinstance(raw.get("next_action"), str) or not str(raw.get("next_action", "")).strip():
        errors.append("next_action")

    findings = _validate_findings(raw.get("findings"), errors)
    checks = _validate_checks(
        raw.get("checks"),
        required=_required_manifest(request),
        errors=errors,
    )
    if status == "PASS":
        if any(checks.get(name) != "PASS" for name in _required_manifest(request)):
            errors.append("failed_check_for_pass")
        if any(finding.get("severity") == "high" for finding in findings):
            errors.append("high_finding_for_pass")
    elif status == "CHANGES_REQUIRED" and not findings and all(
        check_status == "PASS" for check_status in checks.values()
    ):
        errors.append("empty_changes_required")
    elif status == "BLOCKED" and not findings:
        errors.append("empty_blocked")

    tip = current_tip or git_output(repo, "rev-parse", "HEAD")
    if not is_ancestor(repo, request.commit, tip):
        errors.append("verdict_ancestry")
    effective_authority: Authority = authority if not errors else "none"
    return VerdictValidation(
        valid=not errors,
        authority=effective_authority,
        errors=_dedupe(errors),
        status=str(status),
        review_id=str(raw.get("review_id", "")),
        commit=str(raw.get("commit", "")),
    )


def validate_verdict_file(
    verdict_path: Path,
    *,
    state_root: Path,
    repo: Path,
    authority: Literal["external", "provisional"],
    current_tip: str | None = None,
    expected_review_id: str | None = None,
) -> VerdictValidation:
    raw_verdict = _load_object(verdict_path)
    if raw_verdict is None:
        return VerdictValidation(False, "none", ("verdict_json",), "")
    review_id = str(raw_verdict.get("review_id", ""))
    if expected_review_id is not None and review_id != expected_review_id:
        return VerdictValidation(
            False,
            "none",
            ("verdict_review_id",),
            str(raw_verdict.get("status", "")),
            review_id,
            str(raw_verdict.get("commit", "")),
        )
    request_path = state_root / "requests" / f"{review_id}.json"
    claim_path = state_root / "claims" / f"{review_id}.json"
    raw_request = _load_object(request_path)
    claim = _load_object(claim_path)
    if raw_request is None:
        return VerdictValidation(False, "none", ("request_json",), "", review_id)
    request_validation = validate_request(raw_request, repo=repo)
    if not request_validation.valid or request_validation.request is None:
        return VerdictValidation(
            False,
            "none",
            tuple(f"request:{error}" for error in request_validation.errors),
            str(raw_verdict.get("status", "")),
            review_id,
        )
    if claim is None or not isinstance(claim.get("request_sha256"), str):
        return VerdictValidation(
            False,
            "none",
            ("request_claim",),
            str(raw_verdict.get("status", "")),
            review_id,
        )
    claimed_hash = str(claim["request_sha256"])
    if sha256_file(request_path) != claimed_hash:
        return VerdictValidation(
            False,
            "none",
            ("request_hash_mismatch",),
            str(raw_verdict.get("status", "")),
            review_id,
            str(raw_verdict.get("commit", "")),
        )
    return validate_verdict(
        raw_verdict,
        request=request_validation.request,
        request_sha256=claimed_hash,
        repo=repo,
        authority=authority,
        current_tip=current_tip,
        expected_review_id=expected_review_id,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate one agent-review verdict")
    parser.add_argument("verdict", type=Path)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--authority", choices=("external", "provisional"), required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = validate_verdict_file(
        args.verdict,
        state_root=args.state_root,
        repo=args.repo,
        authority=args.authority,
    )
    print(
        json.dumps(
            {
                "valid": result.valid,
                "authority": result.authority,
                "errors": list(result.errors),
                "status": result.status,
                "review_id": result.review_id,
                "commit": result.commit,
            },
            sort_keys=True,
        )
    )
    return 0 if result.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
