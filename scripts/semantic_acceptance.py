#!/usr/bin/env python3
"""Replay the three representative long-tail questions against one runtime."""

from __future__ import annotations

import argparse
import sys
from argparse import Namespace
from pathlib import Path

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

DEFAULT_QUESTIONS = (
    "科创50现在的支撑位在哪里，失效条件是什么",
    "明天是反弹还是继续下跌，分别给出理由",
    "你觉得目前市场的主线是什么，给我你的判断依据",
)


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
) -> tuple[int, dict[str, object]]:
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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        code, summary = run_acceptance(
            base_url=args.base_url,
            user=args.user,
            timeout=args.timeout,
            output=args.output,
            expected_revision=args.expected_revision,
        )
    except SmokeProtocolError as exc:
        print(f"semantic acceptance failed: {exc.stage}", file=sys.stderr)
        return 2
    print(f"semantic acceptance outcome: {summary['terminal_outcome']}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
