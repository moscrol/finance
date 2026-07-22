from __future__ import annotations

from pathlib import Path

from intelligence.eval.capability_monotonicity import (
    DEFAULT_CAPABILITY_CASES,
    CapabilityRunResult,
    CapabilityScore,
    ThreeArmRecord,
    summarize_three_arm_records,
)
from scripts import semantic_acceptance


def test_missing_monotonicity_evidence_is_not_reported_as_passed() -> None:
    result = semantic_acceptance.summarize_capability_monotonicity(None)

    assert result == {
        "status": "not_requested",
        "evidence_present": False,
        "passed": False,
        "issues": [],
    }


def test_explicitly_requested_but_missing_monotonicity_is_not_evaluated() -> None:
    result = semantic_acceptance.summarize_capability_monotonicity(
        None,
        requested=True,
    )

    assert result == {
        "status": "not_evaluated",
        "evidence_present": False,
        "passed": False,
        "issues": ["monotonicity_evidence_missing"],
    }


def _valid_capability_report(
    *, current_score: CapabilityScore | None = None
) -> dict[str, object]:
    case = DEFAULT_CAPABILITY_CASES[0]
    score = CapabilityScore(4, 4, 4, 4, 4)
    result = lambda arm: CapabilityRunResult(
        case_id=case.case_id,
        arm=arm,
        answer="直接回答，并明确事实边界。",
        score=current_score if arm == "current" and current_score else score,
        latency=1.0,
        llm_calls=1,
        tool_calls=0 if arm == "bare" else 2,
        fallback_reason=None,
        protocol_passed=True,
        protocol_issues=(),
    )
    return summarize_three_arm_records(
        [
            ThreeArmRecord(
                case=case,
                bare=result("bare"),
                current=result("current"),
                episode=result("episode"),
            )
        ]
    )


def test_capability_summary_recomputes_each_three_arm_evaluation() -> None:
    report = _valid_capability_report(
        current_score=CapabilityScore(1, 1, 1, 4, 1)
    )
    report["passed"] = True

    summary = semantic_acceptance.summarize_capability_monotonicity(report)

    assert summary["status"] == "failed"
    assert summary["passed"] is False
    assert "capability_regression" in summary["issues"]


def test_capability_summary_marks_verified_three_arm_report_passed() -> None:
    summary = semantic_acceptance.summarize_capability_monotonicity(
        _valid_capability_report()
    )

    assert summary["status"] == "passed"
    assert summary["passed"] is True


def test_capability_summary_rejects_missing_episode_arm() -> None:
    report = _valid_capability_report()
    del report["evaluations"][0]["record"]["episode"]

    summary = semantic_acceptance.summarize_capability_monotonicity(report)

    assert summary["status"] == "failed"
    assert summary["issues"] == ["monotonicity_evidence_invalid"]


def test_reported_comparison_regression_cannot_be_hidden_by_top_level_passed() -> None:
    report = _valid_capability_report()
    report["evaluations"][0]["current"]["failure_reasons"] = [
        "capability_regression"
    ]
    report["passed"] = True

    summary = semantic_acceptance.summarize_capability_monotonicity(report)

    assert summary["status"] == "failed"
    assert summary["passed"] is False
    assert summary["issues"] == ["capability_regression"]


def test_report_threshold_cannot_override_fixed_capability_margin() -> None:
    report = _valid_capability_report()
    report["threshold"] = 1.0

    summary = semantic_acceptance.summarize_capability_monotonicity(report)

    assert summary["status"] == "failed"
    assert summary["issues"] == ["capability_margin_invalid"]


def test_cli_accepts_optional_capability_monotonicity_report(tmp_path: Path) -> None:
    report = tmp_path / "capability.json"

    args = semantic_acceptance.build_parser().parse_args(
        [
            "--base-url",
            "http://127.0.0.1:8795",
            "--user",
            "test",
            "--output",
            str(tmp_path / "acceptance.json"),
            "--capability-monotonicity-report",
            str(report),
        ]
    )

    assert args.capability_monotonicity_report == report


def test_validate_runtime_provenance_rejects_missing_identity() -> None:
    issues = semantic_acceptance.validate_runtime_provenance(
        {"status": "healthy", "runtime": {}}
    )

    assert "runtime_source_revision_missing" in issues
    assert "runtime_dependency_fingerprint_missing" in issues


def test_validate_runtime_provenance_rejects_wrong_revision() -> None:
    health = {
        "status": "healthy",
        "runtime": {
            "source_revision": "candidate",
            "code_root": "/worktree",
            "python_executable": "/venv/bin/python",
            "dependency_fingerprint": "f" * 64,
        },
    }

    issues = semantic_acceptance.validate_runtime_provenance(
        health,
        expected_revision="8792-runtime",
    )

    assert issues == ["runtime_revision_mismatch:candidate!=8792-runtime"]


def test_run_acceptance_replays_all_questions(monkeypatch, tmp_path: Path) -> None:
    health = {
        "status": "healthy",
        "runtime": {
            "source_revision": "candidate",
            "code_root": "/worktree",
            "python_executable": "/venv/bin/python",
            "dependency_fingerprint": "f" * 64,
        },
    }
    monkeypatch.setattr(
        semantic_acceptance,
        "_request_json",
        lambda *args, **kwargs: health,
    )

    def fake_smoke(args):
        return 0, {
            "terminal_outcome": "completed",
            "semantic": {"passed": True, "issues": []},
            "run_id": args.question[:4],
        }

    monkeypatch.setattr(semantic_acceptance, "run_smoke", fake_smoke)
    output = tmp_path / "acceptance.json"
    code, summary = semantic_acceptance.run_acceptance(
        base_url="http://127.0.0.1:8795",
        user="test",
        timeout=1,
        output=output,
        expected_revision="candidate",
    )

    assert code == 0
    assert summary["terminal_outcome"] == "passed"
    assert len(summary["runs"]) == 3
    assert summary["capability_monotonicity"]["status"] == "not_requested"
    assert summary["capability_monotonicity"]["passed"] is False
    assert output.is_file()


def test_explicit_capability_request_without_report_blocks_acceptance(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        semantic_acceptance,
        "_request_json",
        lambda *args, **kwargs: {
            "status": "healthy",
            "runtime": {
                "source_revision": "candidate",
                "code_root": "/worktree",
                "python_executable": "/venv/bin/python",
                "dependency_fingerprint": "f" * 64,
            },
        },
    )
    monkeypatch.setattr(
        semantic_acceptance,
        "run_smoke",
        lambda args: (
            0,
            {
                "terminal_outcome": "completed",
                "semantic": {"passed": True, "issues": []},
                "run_id": args.question[:4],
            },
        ),
    )

    code, summary = semantic_acceptance.run_acceptance(
        base_url="http://127.0.0.1:8795",
        user="test",
        timeout=1,
        output=tmp_path / "acceptance.json",
        capability_monotonicity_requested=True,
    )

    assert code == 1
    assert summary["terminal_outcome"] == "capability_monotonicity_failed"
    assert summary["capability_monotonicity"]["status"] == "not_evaluated"


def test_run_acceptance_fails_on_independent_capability_regression(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        semantic_acceptance,
        "_request_json",
        lambda *args, **kwargs: {
            "status": "healthy",
            "runtime": {
                "source_revision": "candidate",
                "code_root": "/worktree",
                "python_executable": "/venv/bin/python",
                "dependency_fingerprint": "f" * 64,
            },
        },
    )
    monkeypatch.setattr(
        semantic_acceptance,
        "run_smoke",
        lambda args: (
            0,
            {
                "terminal_outcome": "completed",
                "semantic": {"passed": True, "issues": []},
                "run_id": args.question[:4],
            },
        ),
    )
    evidence = _valid_capability_report(
        current_score=CapabilityScore(1, 1, 1, 4, 1)
    )

    code, summary = semantic_acceptance.run_acceptance(
        base_url="http://127.0.0.1:8795",
        user="test",
        timeout=1,
        output=tmp_path / "acceptance.json",
        capability_monotonicity_evidence=evidence,
    )

    assert code == 1
    assert summary["terminal_outcome"] == "capability_regression"
    assert summary["capability_monotonicity"]["issues"] == [
        "capability_regression"
    ]
