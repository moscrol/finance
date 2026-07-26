from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence

from scripts.agent_review.contract import (
    ReviewRequest,
    git_output,
    is_ancestor,
    repair_chain_floor_review_id,
    repair_covers_request,
    validate_request,
)
from scripts.agent_review.validate_verdict import (
    VerdictValidation,
    validate_verdict_file,
)


NextAction = Literal["WAIT", "FIX", "IMPLEMENT_NEXT", "RELEASE_CHECK"]


@dataclass(frozen=True)
class GateDecision:
    branch: str
    tip: str
    gate_state: str
    latest_external_sealed_commit: str | None
    pending_review_id: str | None
    provisional_depth: int
    tainted_review_ids: tuple[str, ...]
    allowed_next_action: NextAction
    fallback_eligible: bool
    release_allowed: bool
    reasons: tuple[str, ...]
    invalid_records: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "branch": self.branch,
            "tip": self.tip,
            "gate_state": self.gate_state,
            "latest_external_sealed_commit": self.latest_external_sealed_commit,
            "pending_review_id": self.pending_review_id,
            "provisional_depth": self.provisional_depth,
            "tainted_review_ids": list(self.tainted_review_ids),
            "allowed_next_action": self.allowed_next_action,
            "fallback_eligible": self.fallback_eligible,
            "release_allowed": self.release_allowed,
            "reasons": list(self.reasons),
            "invalid_records": list(self.invalid_records),
        }


def _load_object(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _request_number(review_id: str) -> int:
    try:
        return int(review_id.rsplit("-", 1)[-1])
    except ValueError:
        return 10**12


def load_reachable_requests(
    *,
    repo: Path,
    state_root: Path,
    tip: str,
) -> tuple[list[ReviewRequest], list[str]]:
    requests: list[ReviewRequest] = []
    invalid: list[str] = []
    for path in sorted(
        (state_root / "requests").glob("ARL-*.json"),
        key=lambda item: _request_number(item.stem),
    ):
        raw = _load_object(path)
        if raw is None:
            invalid.append(path.stem)
            continue
        if raw.get("schema_version") not in {2, 3}:
            continue
        raw_commit = raw.get("commit")
        if isinstance(raw_commit, str) and not is_ancestor(repo, raw_commit, tip):
            # Abandoned history is classified but never governs this branch.
            continue
        validation = validate_request(raw, repo=repo)
        if not validation.valid or validation.request is None:
            invalid.append(str(raw.get("review_id", path.stem)))
            continue
        request = validation.request
        requests.append(request)
    return requests, invalid


def _verdict_for(
    request: ReviewRequest,
    *,
    repo: Path,
    state_root: Path,
    tip: str,
    authority: Literal["external", "provisional"],
) -> VerdictValidation | None:
    directory = "verdicts" if authority == "external" else "provisional-verdicts"
    path = state_root / directory / f"{request.review_id}.json"
    if not path.exists():
        return None
    return validate_verdict_file(
        path,
        state_root=state_root,
        repo=repo,
        authority=authority,
        current_tip=tip,
    )


def _inactive_for_request(state_root: Path, review_id: str) -> bool:
    state = _load_object(state_root / "state/external-review.json")
    if state is None:
        return False
    return (
        state.get("status") == "REVIEWER_INACTIVE"
        and state.get("review_id") == review_id
    )


def _sla_expired(request: ReviewRequest, now: datetime) -> bool:
    if request.intensity == "release":
        return False
    created_at = datetime.fromisoformat(request.created_at)
    wait = timedelta(minutes=15 if request.intensity == "light" else 30)
    return now >= created_at + wait


def compute_gate(
    *,
    repo: Path,
    state_root: Path,
    release: bool = False,
    now: datetime | None = None,
) -> GateDecision:
    repo = repo.resolve()
    state_root = state_root.resolve()
    tip = git_output(repo, "rev-parse", "HEAD")
    branch = git_output(repo, "branch", "--show-current") or "DETACHED"
    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    requests, invalid = load_reachable_requests(
        repo=repo,
        state_root=state_root,
        tip=tip,
    )
    if not requests:
        return GateDecision(
            branch=branch,
            tip=tip,
            gate_state="INVALID" if invalid else "WAITING_EXTERNAL",
            latest_external_sealed_commit=None,
            pending_review_id=None,
            provisional_depth=0,
            tainted_review_ids=(),
            allowed_next_action="WAIT",
            fallback_eligible=False,
            release_allowed=False,
            reasons=("no_valid_schema2_request",),
            invalid_records=tuple(sorted(set(invalid))),
        )

    external: dict[str, VerdictValidation] = {}
    provisional: dict[str, VerdictValidation] = {}
    for request in requests:
        external_result = _verdict_for(
            request,
            repo=repo,
            state_root=state_root,
            tip=tip,
            authority="external",
        )
        provisional_result = _verdict_for(
            request,
            repo=repo,
            state_root=state_root,
            tip=tip,
            authority="provisional",
        )
        if external_result is not None:
            if external_result.valid:
                external[request.review_id] = external_result
            else:
                invalid.append(request.review_id)
        if provisional_result is not None:
            if provisional_result.valid:
                provisional[request.review_id] = provisional_result
            else:
                invalid.append(request.review_id)

    latest = requests[-1]
    relevant_invalid = bool(invalid)
    if relevant_invalid:
        return GateDecision(
            branch=branch,
            tip=tip,
            gate_state="INVALID",
            latest_external_sealed_commit=None,
            pending_review_id=latest.review_id,
            provisional_depth=0,
            tainted_review_ids=(),
            allowed_next_action="WAIT",
            fallback_eligible=False,
            release_allowed=False,
            reasons=("latest_request_has_invalid_provenance",),
            invalid_records=tuple(sorted(set(invalid), key=_request_number)),
        )

    request_by_id = {request.review_id: request for request in requests}
    superseded_review_ids = {
        request.supersedes for request in requests if request.supersedes is not None
    }
    sealed_ids: set[str] = set()
    latest_sealed_commit: str | None = None
    for request in requests:
        verdict = external.get(request.review_id)
        schema2_dependencies = tuple(
            dependency for dependency in request.depends_on if dependency in request_by_id
        )
        dependencies_sealed = all(dependency in sealed_ids for dependency in schema2_dependencies)
        if verdict is not None and verdict.status == "PASS" and dependencies_sealed:
            sealed_ids.add(request.review_id)
            latest_sealed_commit = request.commit
        elif (
            verdict is not None
            and verdict.status == "PASS"
            and request.supersedes is not None
            and f"repair:{request.supersedes}" in request.required_checks
        ):
            # submit.py guarantees the repair request contains the union of all
            # tainted artifacts. An external PASS on that exact descendant can
            # therefore seal the reviewed fix-forward chain.
            coverage_floor = repair_chain_floor_review_id(request, request_by_id)
            sealed_ids.update(
                candidate.review_id
                for candidate in requests
                if repair_covers_request(
                    repo=repo,
                    repair=request,
                    candidate=candidate,
                    coverage_floor_review_id=coverage_floor,
                )
            )
            latest_sealed_commit = request.commit

    blocking_request: ReviewRequest | None = None
    blocking_status = ""
    for request in requests:
        verdict = external.get(request.review_id)
        if (
            verdict is not None
            and verdict.status in {"CHANGES_REQUIRED", "BLOCKED"}
            and request.review_id not in superseded_review_ids
        ):
            blocking_request = request
            blocking_status = verdict.status
            break
        fallback_verdict = provisional.get(request.review_id)
        if (
            fallback_verdict is not None
            and fallback_verdict.status in {"CHANGES_REQUIRED", "BLOCKED"}
        ):
            blocking_request = request
            blocking_status = fallback_verdict.status
            break

    provisional_debt = [
        request
        for request in requests
        if request.review_id not in sealed_ids
        and (result := provisional.get(request.review_id)) is not None
        and result.status == "PASS"
        and (
            latest_sealed_commit is None
            or is_ancestor(repo, latest_sealed_commit, request.commit)
        )
    ]
    tainted: tuple[str, ...] = ()
    if blocking_request is not None:
        tainted = tuple(
            request.review_id
            for request in provisional_debt
            if request.commit != blocking_request.commit
            and is_ancestor(repo, blocking_request.commit, request.commit)
        )
        return GateDecision(
            branch=branch,
            tip=tip,
            gate_state=blocking_status,
            latest_external_sealed_commit=latest_sealed_commit,
            pending_review_id=blocking_request.review_id,
            provisional_depth=len(provisional_debt),
            tainted_review_ids=tainted,
            allowed_next_action="FIX" if blocking_status == "CHANGES_REQUIRED" else "WAIT",
            fallback_eligible=False,
            release_allowed=False,
            reasons=("review_finding_requires_fix_forward",),
            invalid_records=tuple(sorted(set(invalid), key=_request_number)),
        )

    latest_external = external.get(latest.review_id)
    latest_provisional = provisional.get(latest.review_id)
    fallback_eligible = False
    pending_review_id: str | None = None
    if latest_external is not None and latest.review_id in sealed_ids:
        gate_state = "EXTERNAL_PASS"
        action: NextAction = "IMPLEMENT_NEXT"
    elif latest_provisional is not None and latest_provisional.status == "PASS":
        gate_state = "PROVISIONAL_PASS"
        action = "IMPLEMENT_NEXT" if len(provisional_debt) < 2 else "WAIT"
    else:
        gate_state = "WAITING_EXTERNAL"
        action = "WAIT"
        pending_review_id = latest.review_id
        fallback_eligible = (
            _inactive_for_request(state_root, latest.review_id)
            or _sla_expired(latest, current_time)
        ) and latest.intensity != "release" and len(provisional_debt) < 2

    release_allowed = False
    if release:
        milestone_ids = {
            request.review_id
            for request in requests
            if request.intensity in {"milestone", "release"}
        }
        release_checks = {"deterministic_full_regression", "frozen_live_benchmark"}
        release_allowed = (
            not provisional_debt
            and not invalid
            and milestone_ids.issubset(sealed_ids)
            and latest.intensity == "release"
            and latest.review_id in sealed_ids
            and latest.commit == tip
            and release_checks.issubset(set(latest.required_checks))
        )
        if release_allowed:
            action = "RELEASE_CHECK"

    reasons: list[str] = []
    if gate_state == "WAITING_EXTERNAL":
        reasons.append("external_verdict_missing")
    if len(provisional_debt) >= 2:
        reasons.append("provisional_depth_limit")
    if release and not release_allowed:
        reasons.append("release_requirements_not_satisfied")
    if invalid:
        reasons.append("historical_invalid_records_present")
    return GateDecision(
        branch=branch,
        tip=tip,
        gate_state=gate_state,
        latest_external_sealed_commit=latest_sealed_commit,
        pending_review_id=pending_review_id,
        provisional_depth=len(provisional_debt),
        tainted_review_ids=tainted,
        allowed_next_action=action,
        fallback_eligible=fallback_eligible,
        release_allowed=release_allowed,
        reasons=tuple(reasons),
        invalid_records=tuple(sorted(set(invalid), key=_request_number)),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compute Producer review authority")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--release", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    decision = compute_gate(
        repo=args.repo,
        state_root=args.state_root,
        release=args.release,
    )
    print(json.dumps(decision.to_dict(), ensure_ascii=False, sort_keys=True))
    return 0 if decision.allowed_next_action in {"IMPLEMENT_NEXT", "RELEASE_CHECK"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
