"""Revealed Knevo regression inputs; reviewer rules never become model input.

Prepare offline with ``python -m intelligence.eval.knevo_regression --prepare DIR``.
Run a chosen case through scripts/workbench_probe.py --case-set FILE --case-id ID.
Inspect saved evidence offline with --inspect-run DIR --case-id ID (no grading).
Preparation is not execution, delivery is not semantic acceptance. Q18 material
proxies do not certify the real retrieval/storage preconditions they simulate.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re

REPO = Path(__file__).resolve().parents[2]
DEFAULT_SUITE = REPO / "intelligence/eval/cases/knevo_absorption_regression.json"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _rules(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{name} must be a non-empty list")
    return tuple(_text(item, name) for item in value)


@dataclass(frozen=True)
class RegressionCase:
    case_id: str
    question: str
    source: str
    mode: str
    pass_rules: tuple[str, ...]
    fail_rules: tuple[str, ...]
    not_tested: str

    @property
    def question_sha256(self) -> str:
        return sha256(self.question.encode("utf-8"))


def _repo_file(root: Path, relative: object) -> Path:
    name = _text(relative, "repo-relative path")
    path = root / name
    if Path(name).is_absolute() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"path escapes repo: {name}")
    if not path.is_file():
        raise ValueError(f"missing source file: {name}")
    return path


def load_suite(path: Path = DEFAULT_SUITE, *, repo: Path = REPO) -> tuple[RegressionCase, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("unsupported regression schema")
    if payload.get("status") != "revealed_regression_not_benchmark":
        raise ValueError("suite must retain revealed/non-benchmark status")
    _text(payload.get("boundary"), "boundary")
    rows = payload.get("cases")
    if not isinstance(rows, list) or not rows:
        raise ValueError("cases must be a non-empty list")
    cases: list[RegressionCase] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("case must be an object")
        case_id = _text(row.get("id"), "id")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", case_id) or case_id in seen:
            raise ValueError(f"invalid or duplicate id: {case_id}")
        seen.add(case_id)
        mode = row.get("mode")
        if mode not in {"material_proxy", "original_material_pack"}:
            raise ValueError(f"unknown mode: {mode}")
        source = _text(row.get("source"), "source")
        _repo_file(repo, source)
        if ("question" in row) == ("question_file" in row):
            raise ValueError("exactly one of question/question_file is required")
        if "question_file" in row:
            data = _repo_file(repo, row["question_file"]).read_bytes()
            if sha256(data) != row.get("question_sha256"):
                raise ValueError(f"question hash mismatch: {case_id}")
            question = data.decode("utf-8")
        else:
            question = row["question"]
        _text(question, "question")
        cases.append(RegressionCase(
            case_id, question, source, mode,
            _rules(row.get("pass_rules"), "pass_rules"),
            _rules(row.get("fail_rules"), "fail_rules"),
            _text(row.get("not_tested"), "not_tested"),
        ))
    return tuple(cases)


def select_case(path: Path, case_id: str) -> RegressionCase:
    cases = load_suite(path)
    for case in cases:
        if case.case_id == case_id:
            return case
    raise ValueError(f"unknown regression case: {case_id}")


def prepare(output: Path, suite: Path = DEFAULT_SUITE) -> dict:
    """Create an owned, non-overwritable packet. Never call a model or write user data."""
    cases = load_suite(suite)
    output.mkdir(parents=True, exist_ok=False)
    questions_dir = output / "questions"
    questions_dir.mkdir()
    reviews = []
    for case in cases:
        filename = f"{case.case_id}.txt"
        (questions_dir / filename).write_bytes(case.question.encode("utf-8"))
        reviews.append({
            "case_id": case.case_id,
            "question_file": f"questions/{filename}",
            "question_sha256": case.question_sha256,
            "source": case.source,
            "mode": case.mode,
            "pass_rules": list(case.pass_rules),
            "fail_rules": list(case.fail_rules),
            "not_tested": case.not_tested,
            "execution": "not_run",
            "semantic_verdict": "not_evaluated",
            "run_id": None,
            "evidence": [],
        })
    report = {
        "suite_sha256": sha256(suite.read_bytes()),
        "status": "prepared_not_run",
        "entry": "workbench_conversation",
        "case_count": len(cases),
        "automatic_semantic_grading": False,
        "reviewer_only": True,
        "cases": reviews,
    }
    (output / "review-plan.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def inspect_run(directory: Path, case: RegressionCase) -> dict:
    """Read exact run artifacts; missing audit is unknown, never zero calls or a pass.

    Prevents three false positives: nonempty fallback == answered, posted question
    == effective task frame, and a successful internal judge == obeyed user scope.
    Only hashes/observables leave this function, not source text or model output.
    """
    def read_object(name: str, *, required: bool = False) -> dict | None:
        path = directory / name
        if not path.exists() and not required:
            return None
        if not path.resolve().is_relative_to(directory.resolve()):
            raise ValueError(f"artifact escapes run directory: {name}")
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError(f"artifact must be an object: {name}")
        return value

    run = read_object("run.json", required=True)
    if run.get("run_id") != directory.name:
        raise ValueError("run id does not match directory")
    question = _text(run.get("question"), "run question")
    if question.strip() != case.question.strip():
        raise ValueError("run question does not match selected case")
    episode = read_object("continuous-episode.json")
    report = read_object("report.json") or {}
    private_frame = (episode or {}).get("task_frame")
    frame = private_frame or report.get("task_frame") or {}
    frame_source = "private_episode" if private_frame else "public_report" if frame else None
    effective = frame.get("raw_question")
    events = (episode or {}).get("events")
    audit_available = isinstance(events, list)
    calls = [
        {"name": event.get("payload", {}).get("name"),
         "call_id": event.get("payload", {}).get("call_id")}
        for event in (events or []) if event.get("kind") == "tool_request"
    ] if audit_available else None
    material = frame.get("material_contract") or {}
    hashes = {}
    for name in ("run.json", "report.json", "answer.md", "continuous-episode.json", "trace.jsonl"):
        path = directory / name
        if path.is_file():
            if not path.resolve().is_relative_to(directory.resolve()):
                raise ValueError(f"artifact escapes run directory: {name}")
            hashes[name] = sha256(path.read_bytes())
    semantic = (episode or {}).get("semantic_verifier") or {}
    return {
        "case_id": case.case_id,
        "run_id": run["run_id"],
        "user": run.get("user"),
        "question_sha256": case.question_sha256,
        "run_question_sha256": sha256(question.encode("utf-8")),
        "run_question_exact": question == case.question,
        "frame_source": frame_source,
        "frame_question_sha256": sha256(effective.encode("utf-8")) if isinstance(effective, str) else None,
        "frame_question_same_after_strip": effective.strip() == question.strip() if isinstance(effective, str) else None,
        "transport_status": run.get("status"),
        "task_type": report.get("task_type"),
        "question_type": frame.get("question_type"),
        "material_classification": material.get("classification"),
        "material_scope": material.get("data_scope"),
        "material_authenticity": material.get("authenticity"),
        "structural_status": ((episode or {}).get("structural_verifier") or {}).get("verified_status"),
        "internal_semantic_status": semantic.get("status"),
        "internal_judge_status": semantic.get("judge_status"),
        "stop_reason": ((episode or {}).get("outcome") or {}).get("stop_reason"),
        "tool_audit_available": audit_available,
        "tool_requests": calls,
        "artifact_sha256": hashes,
        "semantic_verdict": "not_evaluated",
        "boundary": "Offline observables only; internal status and delivery are not rubric acceptance. Missing tool audit is unknown, not zero; prefetch/other IO is outside this count. Public report frames may be sanitized and do not prove the actual model input.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", type=Path)
    mode.add_argument("--inspect-run", type=Path)
    parser.add_argument("--case-id")
    args = parser.parse_args()
    if bool(args.inspect_run) != bool(args.case_id):
        parser.error("--inspect-run and --case-id must be used together")
    if args.prepare:
        report = prepare(args.prepare, args.suite)
        result = {"status": report["status"], "cases": report["case_count"]}
    else:
        result = inspect_run(args.inspect_run, select_case(args.suite, args.case_id))
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
