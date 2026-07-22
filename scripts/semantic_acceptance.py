#!/usr/bin/env python3
"""Replay the three representative long-tail questions against one runtime."""

from __future__ import annotations

import argparse
import json
import sys
from argparse import Namespace
from decimal import Decimal
from pathlib import Path
from typing import Mapping

# When invoked as ``python scripts/semantic_acceptance.py`` Python places the
# scripts directory (rather than the repository root) on sys.path.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.smoke_workbench_self_use import (
    SmokeProtocolError,
    _atomic_write_json,
    _request_json,
    _url,
    run_smoke,
)
from intelligence.eval.capability_monotonicity import (
    CAPABILITY_MARGIN,
    ThreeArmRecord,
    evaluate_three_arm_record,
)

DEFAULT_QUESTIONS = (
    "科创50现在的支撑位在哪里，失效条件是什么",
    "明天是反弹还是继续下跌，分别给出理由",
    "你觉得目前市场的主线是什么，给我你的判断依据",
)


def load_capability_monotonicity_report(path: Path) -> dict[str, object]:
    """Load a JSON report; semantic validation happens in the summary seam."""

    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("capability report must be a JSON object")
    return loaded


def _capability_invalid(
    *, case_count: int | None = None, issue: str = "monotonicity_evidence_invalid"
) -> dict[str, object]:
    result: dict[str, object] = {
        "status": "failed",
        "evidence_present": True,
        "passed": False,
        "issues": [issue],
    }
    if case_count is not None:
        result["case_count"] = case_count
    return result


def summarize_capability_monotonicity(
    evidence: Mapping[str, object] | None,
    *,
    requested: bool = False,
) -> dict[str, object]:
    """Validate and re-derive an independent capability report.

    ``requested=False`` is the historical CLI path: it is explicitly marked
    ``not_requested`` and can retain the old protocol smoke exit code, but it
    can never claim capability monotonicity passed.
    """

    if evidence is None:
        return {
            "status": "not_evaluated" if requested else "not_requested",
            "evidence_present": False,
            "passed": False,
            "issues": (
                ["monotonicity_evidence_missing"] if requested else []
            ),
        }
    if evidence.get("gate") != "capability_monotonicity":
        return _capability_invalid()
    reported_passed = evidence.get("passed")
    case_count = evidence.get("case_count")
    reported_threshold = evidence.get("threshold")
    evaluations = evidence.get("evaluations")
    if (
        not isinstance(reported_passed, bool)
        or isinstance(case_count, bool)
        or not isinstance(case_count, int)
        or case_count < 1
        or not isinstance(evaluations, list)
        or len(evaluations) != case_count
    ):
        return _capability_invalid(
            case_count=case_count if isinstance(case_count, int) else None
        )
    try:
        if Decimal(str(reported_threshold)) != CAPABILITY_MARGIN:
            return _capability_invalid(
                case_count=case_count,
                issue="capability_margin_invalid",
            )
    except (ArithmeticError, ValueError):
        return _capability_invalid(
            case_count=case_count,
            issue="capability_margin_invalid",
        )

    issues: list[str] = []
    derived_passed: list[bool] = []
    derived_regressions = 0
    reported_regressions = 0
    for evaluation in evaluations:
        if not isinstance(evaluation, Mapping):
            return _capability_invalid(case_count=case_count)
        case_id = evaluation.get("case_id")
        record_payload = evaluation.get("record")
        if not isinstance(case_id, str) or not isinstance(record_payload, Mapping):
            return _capability_invalid(case_count=case_count)
        try:
            record = ThreeArmRecord.from_dict(record_payload)
            if record.case.case_id != case_id:
                return _capability_invalid(case_count=case_count)
            derived = evaluate_three_arm_record(record)
        except (KeyError, TypeError, ValueError):
            return _capability_invalid(case_count=case_count)
        if not isinstance(evaluation.get("passed"), bool):
            return _capability_invalid(case_count=case_count)
        reported_comparisons: dict[str, Mapping[str, object]] = {}
        evaluation_reported_regression = False
        for arm in ("current", "episode"):
            comparison = evaluation.get(arm)
            if not isinstance(comparison, Mapping):
                return _capability_invalid(case_count=case_count)
            if comparison.get("harness_arm") != arm:
                return _capability_invalid(case_count=case_count)
            if not isinstance(comparison.get("passed"), bool):
                return _capability_invalid(case_count=case_count)
            if not isinstance(comparison.get("failure_reasons"), list) or not all(
                isinstance(reason, str)
                for reason in comparison["failure_reasons"]
            ):
                return _capability_invalid(case_count=case_count)
            if "capability_regression" in comparison["failure_reasons"]:
                reported_regressions += 1
                evaluation_reported_regression = True
            reported_comparisons[arm] = comparison
        expected = derived.to_dict()
        if evaluation["passed"] != derived.passed:
            if not evaluation_reported_regression:
                return _capability_invalid(case_count=case_count)
        derived_passed.append(derived.passed)
        for arm in ("current", "episode"):
            expected_reasons = expected[arm]["failure_reasons"]
            if dict(reported_comparisons[arm]) != expected[arm]:
                if "capability_regression" not in reported_comparisons[arm][
                    "failure_reasons"
                ]:
                    return _capability_invalid(case_count=case_count)
            for reason in expected_reasons:
                if reason not in issues:
                    issues.append(reason)
            if "capability_regression" in expected_reasons:
                derived_regressions += 1

    expected_passed = bool(derived_passed) and all(derived_passed)
    if reported_regressions:
        return {
            "status": "failed",
            "evidence_present": True,
            "passed": False,
            "issues": ["capability_regression"],
            "case_count": case_count,
        }
    if not isinstance(evidence.get("evidence_present"), bool):
        return _capability_invalid(case_count=case_count)
    if evidence["evidence_present"] is not True:
        return _capability_invalid(case_count=case_count)
    if reported_passed != expected_passed:
        # A stale top-level boolean cannot override a result derived from arms.
        if not expected_passed and not issues:
            issues.append("capability_monotonicity_failed")
    for field, expected_value in (
        ("arm_comparison_count", case_count * 2),
        ("regression_count", derived_regressions),
    ):
        if evidence.get(field) != expected_value:
            return _capability_invalid(case_count=case_count)
    if not expected_passed and not issues:
        issues.append("capability_monotonicity_failed")
    return {
        "status": "passed" if expected_passed else "failed",
        "evidence_present": True,
        "passed": expected_passed,
        "issues": issues,
        "case_count": case_count,
    }


def validate_runtime_provenance(
    health: object,
    *,
    expected_revision: str | None = None,
) -> list[str]:
    """Return actionable identity failures before spending research budget."""

    if not isinstance(health, dict) or health.get("status") != "healthy":
        return ["health_not_healthy"]
    runtime = health.get("runtime")
    if not isinstance(runtime, dict):
        return ["runtime_provenance_missing"]
    issues: list[str] = []
    for key in (
        "source_revision",
        "code_root",
        "python_executable",
        "dependency_fingerprint",
    ):
        value = runtime.get(key)
        if not isinstance(value, str) or not value.strip() or value == "unknown":
            issues.append(f"runtime_{key}_missing")
    if expected_revision and runtime.get("source_revision") != expected_revision:
        issues.append(
            f"runtime_revision_mismatch:{runtime.get('source_revision')}!={expected_revision}"
        )
    return issues


def run_acceptance(
    *,
    base_url: str,
    user: str,
    timeout: float,
    output: Path,
    expected_revision: str | None = None,
    questions: tuple[str, ...] = DEFAULT_QUESTIONS,
    capability_monotonicity_evidence: Mapping[str, object] | None = None,
    capability_monotonicity_requested: bool = False,
) -> tuple[int, dict[str, object]]:
    capability_requested = (
        capability_monotonicity_requested
        or capability_monotonicity_evidence is not None
    )
    health = _request_json(
        "GET",
        _url(base_url, "/api/health"),
        timeout=timeout,
        stage="health_provenance",
    )
    provenance_issues = validate_runtime_provenance(
        health,
        expected_revision=expected_revision,
    )
    summary: dict[str, object] = {
        "schema_version": 1,
        "base_url": base_url,
        "user": user,
        "questions": list(questions),
        "runtime": health.get("runtime") if isinstance(health, dict) else None,
        "provenance": {
            "passed": not provenance_issues,
            "issues": provenance_issues,
        },
        "capability_monotonicity": summarize_capability_monotonicity(
            capability_monotonicity_evidence,
            requested=capability_requested,
        ),
        "runs": [],
        "terminal_outcome": "protocol_error",
    }
    if provenance_issues:
        summary["terminal_outcome"] = "runtime_provenance_failed"
        _atomic_write_json(output, summary)
        return 2, summary

    runs: list[dict[str, object]] = []
    semantic_failed = False
    protocol_failed = False
    for index, question in enumerate(questions, start=1):
        question_summary_path = output.with_name(
            f"{output.stem}.question-{index}.json"
        )
        code, question_summary = run_smoke(
            Namespace(
                base_url=base_url,
                user=user,
                question=question,
                timeout=timeout,
                semantic=True,
                output=question_summary_path,
            )
        )
        _atomic_write_json(question_summary_path, question_summary)
        runs.append(
            {
                "question": question,
                "exit_code": code,
                "terminal_outcome": question_summary.get("terminal_outcome"),
                "failure_stage": question_summary.get("failure_stage"),
                "semantic": question_summary.get("semantic"),
                "run_id": question_summary.get("run_id"),
            }
        )
        if code == 2:
            protocol_failed = True
        elif code != 0:
            semantic_failed = True
    summary["runs"] = runs
    if protocol_failed:
        summary["terminal_outcome"] = "protocol_failed"
        exit_code = 2
    elif semantic_failed:
        summary["terminal_outcome"] = "semantic_failed"
        exit_code = 1
    elif capability_requested and summary["capability_monotonicity"]["status"] != "passed":
        issues = summary["capability_monotonicity"]["issues"]
        summary["terminal_outcome"] = (
            "capability_regression"
            if "capability_regression" in issues
            else "capability_monotonicity_failed"
        )
        exit_code = 1
    else:
        summary["terminal_outcome"] = "passed"
        exit_code = 0
    _atomic_write_json(output, summary)
    return exit_code, summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Replay representative long-tail questions with semantic gates"
    )
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-revision")
    parser.add_argument(
        "--capability-monotonicity-report",
        type=Path,
        help="Optional independent three-arm capability report to enforce",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        capability_evidence = None
        if args.capability_monotonicity_report is not None:
            capability_evidence = load_capability_monotonicity_report(
                args.capability_monotonicity_report
            )
        code, summary = run_acceptance(
            base_url=args.base_url,
            user=args.user,
            timeout=args.timeout,
            output=args.output,
            expected_revision=args.expected_revision,
            capability_monotonicity_evidence=capability_evidence,
            capability_monotonicity_requested=(
                args.capability_monotonicity_report is not None
            ),
        )
    except SmokeProtocolError as exc:
        print(f"semantic acceptance failed: {exc.stage}", file=sys.stderr)
        return 2
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"semantic acceptance failed: capability report: {exc}", file=sys.stderr)
        return 2
    print(f"semantic acceptance outcome: {summary['terminal_outcome']}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
