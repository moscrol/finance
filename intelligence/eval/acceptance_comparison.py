"""Integrity-bound Workbench/reference information comparisons."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from intelligence.eval.acceptance_observations import load_reference_eligibility
from intelligence.eval.acceptance_runs import load_validated_run, sha256_file
from intelligence.eval.acceptance_verdict import (
    VERDICT_OVERLAY_PATH,
    compile_case_contract,
    load_verdict_overlay,
)


REPO = Path(__file__).resolve().parents[2]
CASES_PATH = REPO / "intelligence/eval/cases/acceptance_cases.json"
ELIGIBILITY_PATH = (
    REPO / "intelligence/eval/cases/acceptance_reference_eligibility.json"
)
SNAPSHOT_DIR = REPO / "intelligence/eval/cases/reference_snapshots"
RUBRIC_PATH = REPO / "intelligence/eval/cases/acceptance_information_rubric.md"

_QUEUE_FIELDS = {
    "format_version",
    "artifact_kind",
    "created_at",
    "source",
    "rubric_sha256",
    "entries",
    "artifact_sha256",
}
_RESULT_FIELDS = _QUEUE_FIELDS | {"evaluator", "case_observations"}
_OBSERVATION_FIELDS = {
    "state",
    "reason",
    "workbench_unique",
    "reference_unique",
    "unsupported_detail_risks",
}
_COMPARISON_STATES = {
    "workbench_wins",
    "tie",
    "knevo_wins",
    "not_evaluated",
}


class ComparisonArtifactError(ValueError):
    """Comparison queue/result is malformed or bound to different evidence."""


@dataclass(frozen=True)
class ComparisonEntry:
    case_id: str
    status: str
    reason: str
    question: str
    workbench_answer: str
    workbench_answer_sha256: str
    reference_agent: str
    reference_path: str | None = None
    reference_answer: str | None = None
    reference_answer_sha256: str | None = None
    eligible_dimensions: tuple[str, ...] = ()
    excluded_dimensions: tuple[str, ...] = ()


@dataclass(frozen=True)
class ComparisonQueue:
    run_path: Path
    source: Mapping[str, Any]
    rubric_sha256: str
    entries: Mapping[str, ComparisonEntry]


@dataclass(frozen=True)
class ComparisonArtifact:
    evaluator_id: str
    evaluator_kind: str
    evaluator_model: str | None
    evaluator_independent: bool
    artifact_sha256: str
    case_observations: Mapping[str, Mapping[str, Any]]


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO.resolve()))
    except ValueError:
        return str(path.resolve())


def _resolve_path(raw: str) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else REPO / path


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_payload_hash(payload: Mapping[str, Any]) -> str:
    body = {key: value for key, value in payload.items() if key != "artifact_sha256"}
    encoded = json.dumps(
        body,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _entry_payload(entry: ComparisonEntry) -> dict[str, Any]:
    payload = asdict(entry)
    payload["eligible_dimensions"] = list(entry.eligible_dimensions)
    payload["excluded_dimensions"] = list(entry.excluded_dimensions)
    return payload


def build_comparison_queue(
    run_path: Path,
    *,
    agent: str,
    cases_path: Path = CASES_PATH,
    overlay_path: Path = VERDICT_OVERLAY_PATH,
    eligibility_path: Path = ELIGIBILITY_PATH,
    rubric_path: Path = RUBRIC_PATH,
) -> ComparisonQueue:
    """Build a frozen pair queue without calling an evaluator."""

    if agent != "knevo":
        raise ComparisonArtifactError("only frozen knevo eligibility is configured")
    cases_doc = json.loads(cases_path.read_text(encoding="utf-8"))
    cases = {str(case["id"]): case for case in cases_doc.get("cases") or []}
    case_tiers = {case_id: str(case["tier"]) for case_id, case in cases.items()}
    run_doc = load_validated_run(run_path, case_tiers)
    overlay = load_verdict_overlay(overlay_path)
    eligibility = load_reference_eligibility(
        eligibility_path,
        cases_path=cases_path,
    )

    entries: dict[str, ComparisonEntry] = {}
    reference_snapshots: dict[str, dict[str, str]] = {}
    for case_run in run_doc["cases"]:
        case_id = str(case_run["case_id"])
        case = cases[case_id]
        contract = compile_case_contract(case, overlay[case_id])
        turns = case_run.get("turns") or []
        answer = ""
        if turns and isinstance(turns[0], dict):
            answer = str(turns[0].get("answer") or "")
        eligibility_entry = eligibility[case_id]
        snapshot_name = eligibility_entry.get("snapshot")
        status = "eligible"
        reason = str(eligibility_entry.get("reason") or "")
        reference_path: str | None = None
        reference_answer: str | None = None
        reference_answer_sha256: str | None = None
        if not answer.strip():
            status = "no_workbench_answer"
            reason = "source run has no Workbench answer"
        elif not contract.reproducible:
            status = "ineligible"
            reason = contract.diagnostics[0] if contract.diagnostics else "case is not reproducible"
        elif snapshot_name is None:
            status = "missing"
        elif not eligibility_entry.get("independent_sample"):
            status = "ineligible"
        elif eligibility_entry.get("experience_status") not in {"eligible", "limited"}:
            status = "ineligible"
        else:
            snapshot_path = SNAPSHOT_DIR / str(snapshot_name)
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            reference_path = _display_path(snapshot_path)
            reference_answer = str(snapshot.get("answer") or "")
            reference_answer_sha256 = str(snapshot.get("answer_sha256") or "")
            reference_snapshots[case_id] = {
                "path": reference_path,
                "file_sha256": sha256_file(snapshot_path),
                "answer_sha256": reference_answer_sha256,
            }

        entries[case_id] = ComparisonEntry(
            case_id=case_id,
            status=status,
            reason=reason,
            question=str(case.get("query") or ""),
            workbench_answer=answer,
            workbench_answer_sha256=_sha256_text(answer),
            reference_agent=agent,
            reference_path=reference_path,
            reference_answer=reference_answer,
            reference_answer_sha256=reference_answer_sha256,
            eligible_dimensions=tuple(eligibility_entry.get("experience_dimensions") or ()),
            excluded_dimensions=tuple(eligibility_entry.get("excluded_dimensions") or ()),
        )

    source = {
        "run_path": _display_path(run_path),
        "run_sha256": sha256_file(run_path),
        "cases_sha256": sha256_file(cases_path),
        "overlay_sha256": sha256_file(overlay_path),
        "reference_agent": agent,
        "reference_eligibility_path": _display_path(eligibility_path),
        "reference_eligibility_sha256": sha256_file(eligibility_path),
        "reference_snapshots": reference_snapshots,
    }
    return ComparisonQueue(
        run_path=run_path,
        source=source,
        rubric_sha256=sha256_file(rubric_path),
        entries=entries,
    )


def queue_payload(
    queue: ComparisonQueue,
    *,
    created_at: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "format_version": 1,
        "artifact_kind": "acceptance_information_queue",
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "source": json.loads(json.dumps(queue.source, ensure_ascii=False)),
        "rubric_sha256": queue.rubric_sha256,
        "entries": {
            case_id: _entry_payload(entry)
            for case_id, entry in queue.entries.items()
        },
    }
    payload["artifact_sha256"] = canonical_payload_hash(payload)
    return payload


def write_comparison_queue(queue: ComparisonQueue, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output.open("x", encoding="utf-8") as handle:
            json.dump(queue_payload(queue), handle, ensure_ascii=False, indent=2)
    except FileExistsError as exc:
        raise ComparisonArtifactError(f"output already exists: {output}") from exc


def load_comparison_queue(path: Path) -> ComparisonQueue:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ComparisonArtifactError(f"unable to read comparison queue: {exc}") from exc
    if not isinstance(payload, dict) or set(payload) != _QUEUE_FIELDS:
        raise ComparisonArtifactError("comparison queue has wrong top-level fields")
    if payload.get("format_version") != 1 or payload.get("artifact_kind") != "acceptance_information_queue":
        raise ComparisonArtifactError("invalid comparison queue header")
    if payload.get("artifact_sha256") != canonical_payload_hash(payload):
        raise ComparisonArtifactError("comparison queue artifact_sha256 mismatch")
    source = payload.get("source")
    if not isinstance(source, dict) or source.get("reference_agent") != "knevo":
        raise ComparisonArtifactError("invalid comparison queue source")
    rebuilt = build_comparison_queue(
        _resolve_path(str(source.get("run_path") or "")),
        agent="knevo",
    )
    expected = queue_payload(rebuilt, created_at=str(payload.get("created_at") or ""))
    if payload != expected:
        raise ComparisonArtifactError("comparison queue no longer matches frozen sources")
    return rebuilt


def load_comparison_result(
    path: Path,
    *,
    queue: ComparisonQueue,
) -> ComparisonArtifact:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ComparisonArtifactError(f"unable to read comparison result: {exc}") from exc
    if not isinstance(payload, dict) or set(payload) != _RESULT_FIELDS:
        raise ComparisonArtifactError("comparison result has wrong top-level fields")
    if payload.get("format_version") != 1 or payload.get("artifact_kind") != "acceptance_information_comparisons":
        raise ComparisonArtifactError("invalid comparison result header")
    if payload.get("artifact_sha256") != canonical_payload_hash(payload):
        raise ComparisonArtifactError("comparison result artifact_sha256 mismatch")

    expected_queue = queue_payload(queue, created_at=str(payload.get("created_at") or ""))
    for field in ("source", "rubric_sha256", "entries"):
        if payload.get(field) != expected_queue[field]:
            raise ComparisonArtifactError(f"comparison result {field} mismatch")

    evaluator = payload.get("evaluator")
    if not isinstance(evaluator, dict) or set(evaluator) != {
        "id",
        "kind",
        "model",
        "independent",
    }:
        raise ComparisonArtifactError("invalid comparison evaluator")
    evaluator_id = str(evaluator.get("id") or "").strip()
    evaluator_kind = str(evaluator.get("kind") or "").strip()
    evaluator_model = str(evaluator.get("model") or "").strip() or None
    if not evaluator_id or not evaluator_kind or not evaluator_model:
        raise ComparisonArtifactError("comparison evaluator identity/model is required")
    if evaluator.get("independent") is not True:
        raise ComparisonArtifactError("comparison evaluator must be independent")

    raw_observations = payload.get("case_observations")
    if not isinstance(raw_observations, dict):
        raise ComparisonArtifactError("case_observations must be an object")
    unknown = sorted(set(raw_observations) - set(queue.entries))
    if unknown:
        raise ComparisonArtifactError("unknown comparison case ids: " + ", ".join(unknown))

    validated: dict[str, dict[str, Any]] = {}
    for case_id, raw in raw_observations.items():
        entry = queue.entries[case_id]
        if entry.status != "eligible":
            raise ComparisonArtifactError(f"{case_id} is not comparison-eligible")
        if not isinstance(raw, dict) or set(raw) != _OBSERVATION_FIELDS:
            raise ComparisonArtifactError(f"{case_id} comparison has wrong fields")
        state = raw.get("state")
        if state not in _COMPARISON_STATES:
            raise ComparisonArtifactError(f"{case_id} has invalid state")
        reason = raw.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise ComparisonArtifactError(f"{case_id} comparison reason is required")
        for field in (
            "workbench_unique",
            "reference_unique",
            "unsupported_detail_risks",
        ):
            values = raw.get(field)
            if not isinstance(values, list) or not all(
                isinstance(value, str) and value.strip() for value in values
            ):
                raise ComparisonArtifactError(f"{case_id}.{field} must be a string list")
        validated[case_id] = dict(raw)

    return ComparisonArtifact(
        evaluator_id=evaluator_id,
        evaluator_kind=evaluator_kind,
        evaluator_model=evaluator_model,
        evaluator_independent=True,
        artifact_sha256=str(payload["artifact_sha256"]),
        case_observations=validated,
    )
