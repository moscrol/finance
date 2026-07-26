from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts.agent_review.contract import EXTERNAL_REVIEWER, sha256_file
from scripts.agent_review.gate import compute_gate
from scripts.agent_review.submit import submit_request


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture()
def gate_case(tmp_path: Path):
    repo = tmp_path / "repo"
    (repo / "intelligence/services").mkdir(parents=True)
    (repo / "intelligence/tests").mkdir(parents=True)
    (repo / "intelligence/services/evidence_ledger.py").write_text(
        "VALUE = 1\n", encoding="utf-8"
    )
    (repo / "intelligence/tests/test_evidence_ledger.py").write_text(
        "from intelligence.services.evidence_ledger import VALUE\n"
        "def test_value():\n    assert VALUE\n",
        encoding="utf-8",
    )
    (repo / "slice.txt").write_text("0\n", encoding="utf-8")
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "gate@example.com")
    _git(repo, "config", "user.name", "Gate Test")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    state_root = tmp_path / "state"
    counter = 0

    class Case:
        def advance(self) -> None:
            nonlocal counter
            counter += 1
            (repo / "slice.txt").write_text(f"{counter}\n", encoding="utf-8")
            _git(repo, "add", ".")
            _git(repo, "commit", "-m", f"slice {counter}")

        def submit(
            self,
            *,
            depends_on: tuple[str, ...] = (),
            intensity: str = "light",
            age_minutes: int = 0,
            required_checks: tuple[str, ...] = ("focused",),
        ):
            created = datetime.now(timezone.utc) - timedelta(minutes=age_minutes)
            return submit_request(
                repo=repo,
                state_root=state_root,
                scope=f"slice {counter}",
                artifacts=("intelligence/services/evidence_ledger.py",),
                required_checks=required_checks,
                intensity=intensity,
                depends_on=depends_on,
                created_at=created.isoformat(),
            )

        def verdict(
            self,
            request,
            *,
            authority: str,
            status: str = "PASS",
            architecture_finding: str | None = None,
        ) -> None:
            request_path = state_root / "requests" / f"{request.review_id}.json"
            checks = {
                check: {"status": "PASS", "evidence": "verified"}
                for check in request.required_checks
            }
            for tests in request.artifact_tests.values():
                for test in tests:
                    checks[test] = {"status": "PASS", "evidence": "1 passed"}
            checks.update(
                {
                    "git_diff_check": {"status": "PASS", "evidence": "clean"},
                    "artifact_hygiene": {"status": "PASS", "evidence": "clean"},
                    "canonical_safety": {"status": "PASS", "evidence": "untouched"},
                }
            )
            findings = []
            if architecture_finding:
                findings.append(
                    {
                        "severity": "high",
                        "file": "scripts/agent_review/gate.py",
                        "line": 1,
                        "title": architecture_finding,
                        "evidence": "reproduced",
                        "recommendation": "fix forward",
                    }
                )
            payload = {
                "schema_version": 2,
                "review_id": request.review_id,
                "commit": request.commit,
                "request_sha256": sha256_file(request_path),
                "status": status,
                "reviewer": (
                    EXTERNAL_REVIEWER
                    if authority == "external"
                    else "codex:producer-fallback"
                ),
                "reviewer_class": (
                    "external" if authority == "external" else "producer_fallback"
                ),
                "authority": authority,
                "findings": findings,
                "checks": checks,
                "reviewed_at": datetime.now(timezone.utc).isoformat(),
                "summary": "reviewed",
                "next_action": "continue" if status == "PASS" else "fix",
            }
            directory = "verdicts" if authority == "external" else "provisional-verdicts"
            path = state_root / directory / f"{request.review_id}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload), encoding="utf-8")

    return Case(), repo, state_root


def test_waits_for_external_review_before_sla(gate_case):
    case, repo, state_root = gate_case
    case.advance()
    request = case.submit(age_minutes=1)

    decision = compute_gate(repo=repo, state_root=state_root)

    assert decision.gate_state == "WAITING_EXTERNAL"
    assert decision.allowed_next_action == "WAIT"
    assert not decision.fallback_eligible
    assert decision.pending_review_id == request.review_id


def test_light_sla_allows_fallback_but_not_direct_progress(gate_case):
    case, repo, state_root = gate_case
    case.advance()
    request = case.submit(age_minutes=16)

    decision = compute_gate(repo=repo, state_root=state_root)

    assert decision.gate_state == "WAITING_EXTERNAL"
    assert decision.allowed_next_action == "WAIT"
    assert decision.fallback_eligible
    assert decision.pending_review_id == request.review_id


def test_two_provisional_slices_allowed_but_third_denied(gate_case):
    case, repo, state_root = gate_case
    case.advance()
    first = case.submit(age_minutes=16)
    case.verdict(first, authority="provisional")
    first_decision = compute_gate(repo=repo, state_root=state_root)
    assert first_decision.allowed_next_action == "IMPLEMENT_NEXT"
    assert first_decision.provisional_depth == 1

    case.advance()
    second = case.submit(depends_on=(first.review_id,), age_minutes=16)
    case.verdict(second, authority="provisional")
    second_decision = compute_gate(repo=repo, state_root=state_root)

    assert second_decision.provisional_depth == 2
    assert second_decision.allowed_next_action == "WAIT"


def test_external_finding_taints_provisional_descendants(gate_case):
    case, repo, state_root = gate_case
    case.advance()
    first = case.submit(age_minutes=16)
    case.verdict(first, authority="provisional")
    case.advance()
    second = case.submit(depends_on=(first.review_id,), age_minutes=16)
    case.verdict(second, authority="provisional")
    case.verdict(
        first,
        authority="external",
        status="CHANGES_REQUIRED",
        architecture_finding="repair loop is not continuous",
    )

    decision = compute_gate(repo=repo, state_root=state_root)

    assert decision.gate_state == "CHANGES_REQUIRED"
    assert decision.allowed_next_action == "FIX"
    assert decision.tainted_review_ids == (second.review_id,)


def test_external_pass_clears_matching_provisional_debt(gate_case):
    case, repo, state_root = gate_case
    case.advance()
    first = case.submit(age_minutes=16)
    case.verdict(first, authority="provisional")
    case.verdict(first, authority="external")

    decision = compute_gate(repo=repo, state_root=state_root)

    assert decision.gate_state == "EXTERNAL_PASS"
    assert decision.provisional_depth == 0
    assert decision.latest_external_sealed_commit == first.commit
    assert decision.allowed_next_action == "IMPLEMENT_NEXT"


def test_release_denied_while_provisional_debt_remains(gate_case):
    case, repo, state_root = gate_case
    case.advance()
    request = case.submit(intensity="milestone", age_minutes=31)
    case.verdict(request, authority="provisional")

    decision = compute_gate(repo=repo, state_root=state_root, release=True)

    assert not decision.release_allowed
    assert decision.allowed_next_action != "RELEASE_CHECK"


def test_exact_external_release_pass_enables_technical_release_check(gate_case):
    case, repo, state_root = gate_case
    case.advance()
    request = case.submit(
        intensity="release",
        required_checks=("deterministic_full_regression", "frozen_live_benchmark"),
    )
    case.verdict(request, authority="external")

    decision = compute_gate(repo=repo, state_root=state_root, release=True)

    assert decision.release_allowed
    assert decision.allowed_next_action == "RELEASE_CHECK"


def test_invalid_external_identity_never_unlocks_gate(gate_case):
    case, repo, state_root = gate_case
    case.advance()
    request = case.submit()
    case.verdict(request, authority="external")
    verdict_path = state_root / "verdicts" / f"{request.review_id}.json"
    payload = json.loads(verdict_path.read_text())
    payload["reviewer"] = "codex:producer"
    verdict_path.write_text(json.dumps(payload), encoding="utf-8")

    decision = compute_gate(repo=repo, state_root=state_root)

    assert decision.gate_state == "INVALID"
    assert decision.allowed_next_action == "WAIT"
    assert request.review_id in decision.invalid_records
