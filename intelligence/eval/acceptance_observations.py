"""Integrity-checked sidecars for semantic truth and blind experience labels."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from intelligence.eval.acceptance_verdict import (
    compile_case_contract,
    load_verdict_overlay,
)


REPO = Path(__file__).resolve().parents[2]
REFERENCE_ELIGIBILITY_PATH = (
    REPO / "intelligence/eval/cases/acceptance_reference_eligibility.json"
)
_SHA256_LENGTH = 64
_ARTIFACT_KINDS = {
    "acceptance_truth_observations",
    "acceptance_experience_labels",
}
_TOP_LEVEL_FIELDS = {
    "format_version",
    "artifact_kind",
    "created_at",
    "source",
    "evaluator",
    "rubric_sha256",
    "comparison",
    "case_observations",
    "artifact_sha256",
}
_ELIGIBILITY_STATES = {"eligible", "limited", "ineligible", "missing"}
_TRUTH_DIMENSIONS = {
    "numeric_accuracy",
    "temporal_integrity",
    "entity_accuracy",
    "methodology",
    "honesty",
    "causal_support",
    "multi_turn_consistency",
    "source_integrity",
    "definition_alignment",
}
_EXPERIENCE_DIMENSIONS = {
    "directness",
    "organization",
    "actionability",
    "source_clarity",
    "followup_burden",
    "reasoning_chain",
}


class ObservationArtifactError(ValueError):
    """The observation artifact is malformed or bound to different evidence."""


@dataclass(frozen=True)
class ObservationArtifact:
    kind: str
    created_at: str
    evaluator_id: str
    evaluator_kind: str
    evaluator_model: str | None
    evaluator_independent: bool
    rubric_sha256: str
    source_run_sha256: str
    source_cases_sha256: str
    source_overlay_sha256: str
    artifact_sha256: str
    comparison: Mapping[str, Any]
    case_observations: Mapping[str, Mapping[str, Any]]

    def for_case(self, case_id: str) -> dict[str, Any]:
        raw = self.case_observations.get(case_id) or {}
        return json.loads(json.dumps(raw, ensure_ascii=False))


def canonical_artifact_hash(payload: Mapping[str, Any]) -> str:
    """Hash canonical JSON while excluding only the artifact's own hash field."""

    body = {key: value for key, value in payload.items() if key != "artifact_sha256"}
    encoded = json.dumps(
        body,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_reference_eligibility(
    path: Path | None = None,
    *,
    cases_path: Path,
) -> dict[str, dict[str, Any]]:
    """Validate the typed, case-specific eligibility of frozen reference answers."""

    eligibility_path = path or REFERENCE_ELIGIBILITY_PATH
    try:
        payload = json.loads(eligibility_path.read_text(encoding="utf-8"))
        cases_doc = json.loads(cases_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ObservationArtifactError(f"unable to load reference eligibility: {exc}") from exc
    if payload.get("format_version") != 1 or payload.get("reference_agent") != "knevo":
        raise ObservationArtifactError("invalid reference eligibility header")
    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, dict):
        raise ObservationArtifactError("reference eligibility cases must be an object")
    expected_ids = {str(case["id"]) for case in cases_doc.get("cases") or []}
    if set(raw_cases) != expected_ids:
        missing = sorted(expected_ids - set(raw_cases))
        extra = sorted(set(raw_cases) - expected_ids)
        raise ObservationArtifactError(
            f"reference eligibility ids mismatch: missing={missing}, extra={extra}"
        )

    snapshot_root = eligibility_path.parent / "reference_snapshots"
    result: dict[str, dict[str, Any]] = {}
    for case_id, raw in raw_cases.items():
        if not isinstance(raw, dict):
            raise ObservationArtifactError(f"eligibility {case_id} must be an object")
        required = {
            "snapshot",
            "independent_sample",
            "truth_status",
            "experience_status",
            "truth_dimensions",
            "experience_dimensions",
            "excluded_dimensions",
            "reason",
        }
        if set(raw) != required:
            raise ObservationArtifactError(f"eligibility {case_id} has wrong fields")
        truth_status = raw.get("truth_status")
        experience_status = raw.get("experience_status")
        if truth_status not in _ELIGIBILITY_STATES or experience_status not in _ELIGIBILITY_STATES:
            raise ObservationArtifactError(f"eligibility {case_id} has invalid status")
        if not isinstance(raw.get("independent_sample"), bool):
            raise ObservationArtifactError(f"eligibility {case_id} needs independent_sample")
        if not isinstance(raw.get("reason"), str) or not raw["reason"].strip():
            raise ObservationArtifactError(f"eligibility {case_id} needs reason")
        truth_dimensions = set(raw.get("truth_dimensions") or [])
        experience_dimensions = set(raw.get("experience_dimensions") or [])
        if truth_dimensions - _TRUTH_DIMENSIONS:
            raise ObservationArtifactError(f"eligibility {case_id} has unknown truth dimensions")
        if experience_dimensions - _EXPERIENCE_DIMENSIONS:
            raise ObservationArtifactError(
                f"eligibility {case_id} has unknown experience dimensions"
            )

        snapshot_name = raw.get("snapshot")
        if snapshot_name is None:
            if truth_status != "missing" or experience_status != "missing":
                raise ObservationArtifactError(
                    f"eligibility {case_id} without snapshot must be missing on both axes"
                )
        else:
            snapshot_path = snapshot_root / str(snapshot_name)
            if not snapshot_path.is_file():
                raise ObservationArtifactError(f"eligibility {case_id} snapshot is missing")
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            if snapshot.get("case_id") != case_id or snapshot.get("agent") != "knevo":
                raise ObservationArtifactError(f"eligibility {case_id} snapshot identity mismatch")
            answer = str(snapshot.get("answer") or "")
            if hashlib.sha256(answer.encode("utf-8")).hexdigest() != snapshot.get(
                "answer_sha256"
            ):
                raise ObservationArtifactError(f"eligibility {case_id} snapshot hash mismatch")
            alias_of = (snapshot.get("source_meta") or {}).get("alias_of")
            if alias_of and raw.get("independent_sample") is not False:
                raise ObservationArtifactError(
                    f"eligibility {case_id} aliases {alias_of} but is marked independent"
                )
        result[case_id] = dict(raw)
    return result


def load_observation_artifact(
    path: Path,
    *,
    run_path: Path,
    cases_path: Path,
    overlay_path: Path,
    reference_eligibility_path: Path | None = None,
    blind_manifest_path: Path | None = None,
) -> ObservationArtifact:
    """Load one sidecar and prove that it belongs to the selected frozen inputs."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ObservationArtifactError(f"unable to read observation artifact: {exc}") from exc
    if not isinstance(payload, dict):
        raise ObservationArtifactError("observation artifact must be a JSON object")
    unknown = sorted(set(payload) - _TOP_LEVEL_FIELDS)
    if unknown:
        raise ObservationArtifactError("unknown top-level fields: " + ", ".join(unknown))
    if payload.get("format_version") != 1:
        raise ObservationArtifactError("unsupported observation format_version")
    kind = str(payload.get("artifact_kind") or "")
    if kind not in _ARTIFACT_KINDS:
        raise ObservationArtifactError(f"unsupported artifact_kind: {kind or '<missing>'}")
    comparison = payload.get("comparison")
    if kind == "acceptance_truth_observations" and comparison is not None:
        raise ObservationArtifactError("truth artifact cannot carry comparison identity")

    declared_hash = str(payload.get("artifact_sha256") or "")
    actual_hash = canonical_artifact_hash(payload)
    if declared_hash != actual_hash:
        raise ObservationArtifactError("artifact_sha256 mismatch")

    created_at = payload.get("created_at")
    if not isinstance(created_at, str) or not created_at.strip():
        raise ObservationArtifactError("created_at is required")
    rubric_hash = str(payload.get("rubric_sha256") or "")
    if not _is_sha256(rubric_hash):
        raise ObservationArtifactError("rubric_sha256 must be a SHA-256 hex digest")

    source = payload.get("source")
    if not isinstance(source, dict):
        raise ObservationArtifactError("source object is required")
    expected_sources = {
        "run_path": _display_path(run_path),
        "run_sha256": _sha256_file(run_path),
        "cases_sha256": _sha256_file(cases_path),
        "overlay_sha256": _sha256_file(overlay_path),
    }
    for field_name, expected in expected_sources.items():
        if source.get(field_name) != expected:
            raise ObservationArtifactError(f"source {field_name} mismatch")

    evaluator = payload.get("evaluator")
    if not isinstance(evaluator, dict):
        raise ObservationArtifactError("evaluator object is required")
    if set(evaluator) - {"id", "kind", "model", "independent"}:
        raise ObservationArtifactError("evaluator object has unknown fields")
    evaluator_id = str(evaluator.get("id") or "").strip()
    evaluator_kind = str(evaluator.get("kind") or "").strip()
    evaluator_model = (
        str(evaluator["model"]).strip() if evaluator.get("model") is not None else None
    )
    if not evaluator_id or not evaluator_kind:
        raise ObservationArtifactError("evaluator id and kind are required")
    if evaluator_kind == "semantic_model" and not evaluator_model:
        raise ObservationArtifactError("semantic_model evaluator requires model provenance")
    if not isinstance(evaluator.get("independent"), bool):
        raise ObservationArtifactError("evaluator independent flag is required")
    if kind == "acceptance_experience_labels" and evaluator.get("independent") is not True:
        raise ObservationArtifactError("blind experience evaluator must be independent")

    cases_doc = json.loads(cases_path.read_text(encoding="utf-8"))
    cases = {str(case["id"]): case for case in cases_doc.get("cases") or []}
    overlay = load_verdict_overlay(overlay_path)
    eligibility: dict[str, dict[str, Any]] = {}
    blind_pairs: dict[str, dict[str, Any]] = {}
    if kind == "acceptance_experience_labels":
        if not isinstance(comparison, dict):
            raise ObservationArtifactError("experience artifact requires comparison object")
        eligibility_path = reference_eligibility_path or REFERENCE_ELIGIBILITY_PATH
        if blind_manifest_path is None:
            raise ObservationArtifactError("experience artifact requires blind_manifest_path")
        eligibility = load_reference_eligibility(
            eligibility_path,
            cases_path=cases_path,
        )
        expected_comparison = {
            "reference_agent": "knevo",
            "reference_eligibility_sha256": _sha256_file(eligibility_path),
        }
        for field_name, expected in expected_comparison.items():
            if comparison.get(field_name) != expected:
                raise ObservationArtifactError(f"comparison {field_name} mismatch")
        blind_hash, blind_pairs = _load_blind_manifest(
            blind_manifest_path,
            run_sha256=expected_sources["run_sha256"],
        )
        if comparison.get("blind_manifest_sha256") != blind_hash:
            raise ObservationArtifactError("comparison blind_manifest_sha256 mismatch")
        if set(comparison) != {
            "reference_agent",
            "reference_eligibility_sha256",
            "blind_manifest_sha256",
        }:
            raise ObservationArtifactError("comparison object has unknown fields")
    raw_observations = payload.get("case_observations")
    if not isinstance(raw_observations, dict):
        raise ObservationArtifactError("case_observations object is required")
    unknown_cases = sorted(set(raw_observations) - set(cases))
    if unknown_cases:
        raise ObservationArtifactError("unknown case ids: " + ", ".join(unknown_cases))
    run_doc = json.loads(run_path.read_text(encoding="utf-8"))
    run_cases = {
        str(item.get("case_id")): item
        for item in (run_doc.get("cases") or [])
        if isinstance(item, dict) and item.get("case_id")
    }
    absent_from_run = sorted(set(raw_observations) - set(run_cases))
    if absent_from_run:
        raise ObservationArtifactError(
            "case ids absent from source run: " + ", ".join(absent_from_run)
        )

    validated: dict[str, Mapping[str, Any]] = {}
    for case_id, raw in raw_observations.items():
        if not isinstance(raw, dict):
            raise ObservationArtifactError(f"{case_id} observation must be an object")
        contract = compile_case_contract(cases[case_id], overlay[case_id])
        if kind == "acceptance_truth_observations":
            validated[case_id] = _validate_truth(
                case_id,
                raw,
                contract,
                case_run=run_cases[case_id],
            )
        else:
            validated[case_id] = _validate_experience(
                case_id,
                raw,
                eligibility=eligibility[case_id],
                blind_pairs=blind_pairs,
                eligibility_path=reference_eligibility_path or REFERENCE_ELIGIBILITY_PATH,
            )

    return ObservationArtifact(
        kind=kind,
        created_at=created_at,
        evaluator_id=evaluator_id,
        evaluator_kind=evaluator_kind,
        evaluator_model=evaluator_model,
        evaluator_independent=bool(evaluator["independent"]),
        rubric_sha256=rubric_hash,
        source_run_sha256=expected_sources["run_sha256"],
        source_cases_sha256=expected_sources["cases_sha256"],
        source_overlay_sha256=expected_sources["overlay_sha256"],
        artifact_sha256=declared_hash,
        comparison=dict(comparison or {}),
        case_observations=validated,
    )


def _validate_truth(
    case_id: str,
    raw: Mapping[str, Any],
    contract,
    *,
    case_run: Mapping[str, Any],
) -> Mapping[str, Any]:
    if set(raw) != {"truth_observations"}:
        raise ObservationArtifactError(
            f"{case_id} truth artifact may contain only truth_observations"
        )
    observations = raw.get("truth_observations")
    if not isinstance(observations, dict) or not observations:
        raise ObservationArtifactError(f"{case_id} truth_observations must be non-empty")
    allowed = _external_rule_ids(contract)
    unknown = sorted(set(observations) - allowed)
    if unknown:
        raise ObservationArtifactError(
            f"{case_id} cannot externally observe rules: {', '.join(unknown)}"
        )
    result: dict[str, Any] = {}
    for rule_id, observation in observations.items():
        if not isinstance(observation, dict):
            raise ObservationArtifactError(f"{case_id}.{rule_id} must be an object")
        if set(observation) != {"state", "reason", "evidence_refs"}:
            raise ObservationArtifactError(
                f"{case_id}.{rule_id} must contain state, reason, evidence_refs"
            )
        if observation.get("state") not in {"pass", "fail", "unjudgeable"}:
            raise ObservationArtifactError(f"{case_id}.{rule_id} has invalid state")
        reason = observation.get("reason")
        refs = observation.get("evidence_refs")
        if not isinstance(reason, str) or not reason.strip():
            raise ObservationArtifactError(f"{case_id}.{rule_id} requires reason")
        if not isinstance(refs, list) or not refs or not all(
            isinstance(item, str) and item.strip() for item in refs
        ):
            raise ObservationArtifactError(f"{case_id}.{rule_id} requires evidence_refs")
        for evidence_ref in refs:
            _validate_evidence_ref(case_id, rule_id, evidence_ref, case_run)
        result[rule_id] = dict(observation)
    return {"truth_observations": result}


def _validate_experience(
    case_id: str,
    raw: Mapping[str, Any],
    *,
    eligibility: Mapping[str, Any],
    blind_pairs: Mapping[str, Mapping[str, Any]],
    eligibility_path: Path,
) -> Mapping[str, Any]:
    if set(raw) != {"experience_verdict"}:
        raise ObservationArtifactError(
            f"{case_id} experience artifact may contain only experience_verdict"
        )
    verdict = raw.get("experience_verdict")
    if not isinstance(verdict, dict):
        raise ObservationArtifactError(f"{case_id}.experience_verdict must be an object")
    allowed = {"eligible", "label", "reason", "blinded_pair_id", "dimensions"}
    if set(verdict) - allowed:
        raise ObservationArtifactError(f"{case_id} experience verdict has unknown fields")
    eligible = verdict.get("eligible")
    reason = verdict.get("reason")
    if not isinstance(eligible, bool) or not isinstance(reason, str) or not reason.strip():
        raise ObservationArtifactError(f"{case_id} experience verdict needs eligibility/reason")
    if eligible:
        if eligibility.get("experience_status") not in {"eligible", "limited"}:
            raise ObservationArtifactError(
                f"{case_id} reference is not experience-eligible"
            )
        if verdict.get("label") not in {"workbench", "reference", "tie"}:
            raise ObservationArtifactError(f"{case_id} has invalid blind label")
        pair_id = str(verdict.get("blinded_pair_id") or "").strip()
        if not pair_id:
            raise ObservationArtifactError(f"{case_id} requires blinded_pair_id")
        pair = blind_pairs.get(pair_id)
        if not pair or pair.get("case_id") != case_id:
            raise ObservationArtifactError(f"{case_id} blind pair identity mismatch")
        dimensions = verdict.get("dimensions")
        if not isinstance(dimensions, list) or not dimensions:
            raise ObservationArtifactError(f"{case_id} requires compared dimensions")
        allowed_dimensions = set(eligibility.get("experience_dimensions") or [])
        if set(dimensions) - allowed_dimensions:
            raise ObservationArtifactError(
                f"{case_id} blind dimensions exceed reference eligibility"
            )
        snapshot_name = eligibility.get("snapshot")
        snapshot_path = eligibility_path.parent / "reference_snapshots" / str(snapshot_name)
        if pair.get("reference_snapshot_sha256") != _sha256_file(snapshot_path):
            raise ObservationArtifactError(f"{case_id} reference snapshot hash mismatch")
    elif verdict.get("label") is not None:
        raise ObservationArtifactError(f"{case_id} ineligible verdict cannot carry a label")
    return {"experience_verdict": dict(verdict)}


def _load_blind_manifest(
    path: Path,
    *,
    run_sha256: str,
) -> tuple[str, dict[str, dict[str, Any]]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ObservationArtifactError(f"unable to load blind manifest: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("format_version") != 1:
        raise ObservationArtifactError("invalid blind manifest header")
    if set(payload) != {
        "format_version",
        "created_at",
        "pairs",
        "artifact_sha256",
    }:
        raise ObservationArtifactError("blind manifest has wrong fields")
    declared_hash = str(payload.get("artifact_sha256") or "")
    if declared_hash != canonical_artifact_hash(payload):
        raise ObservationArtifactError("blind manifest artifact_sha256 mismatch")
    pairs = payload.get("pairs")
    if not isinstance(pairs, dict) or not pairs:
        raise ObservationArtifactError("blind manifest pairs must be non-empty")
    validated: dict[str, dict[str, Any]] = {}
    for pair_id, raw in pairs.items():
        if not isinstance(raw, dict) or set(raw) != {
            "case_id",
            "left",
            "right",
            "workbench_run_sha256",
            "reference_snapshot_sha256",
        }:
            raise ObservationArtifactError(f"blind pair {pair_id} has wrong fields")
        if {raw.get("left"), raw.get("right")} != {"workbench", "reference"}:
            raise ObservationArtifactError(f"blind pair {pair_id} has invalid identities")
        if raw.get("workbench_run_sha256") != run_sha256:
            raise ObservationArtifactError(f"blind pair {pair_id} run hash mismatch")
        if not _is_sha256(str(raw.get("reference_snapshot_sha256") or "")):
            raise ObservationArtifactError(f"blind pair {pair_id} snapshot hash invalid")
        validated[str(pair_id)] = dict(raw)
    return declared_hash, validated


def _validate_evidence_ref(
    case_id: str,
    rule_id: str,
    evidence_ref: str,
    case_run: Mapping[str, Any],
) -> None:
    match = re.fullmatch(r"(turn|citation|evidence):(\d+)(?::(\d+))?", evidence_ref)
    if not match:
        raise ObservationArtifactError(
            f"{case_id}.{rule_id} has invalid evidence_ref {evidence_ref!r}"
        )
    kind, turn_index_text, item_index_text = match.groups()
    turns = case_run.get("turns") or []
    turn_index = int(turn_index_text)
    if turn_index >= len(turns):
        raise ObservationArtifactError(
            f"{case_id}.{rule_id} evidence_ref turn is out of range"
        )
    if kind == "turn":
        if item_index_text is not None:
            raise ObservationArtifactError(
                f"{case_id}.{rule_id} turn evidence_ref cannot contain item index"
            )
        return
    if item_index_text is None:
        raise ObservationArtifactError(
            f"{case_id}.{rule_id} {kind} evidence_ref needs item index"
        )
    items = turns[turn_index].get(f"{kind}s") or []
    if int(item_index_text) >= len(items):
        raise ObservationArtifactError(
            f"{case_id}.{rule_id} {kind} evidence_ref is out of range"
        )


def _external_rule_ids(contract) -> set[str]:
    case = contract.case
    allowed: set[str] = set()
    if contract.coverage == "semantic_required":
        allowed.add("pass_rule")
    if case.get("expect_answer_set") and contract.coverage == "structured":
        allowed.add("answer_set")
    if case.get("inherit_from"):
        allowed.add("inherited_golden")
    if case.get("check_cross_turn_consistency"):
        allowed.add("cross_turn_consistency")
    return allowed


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO.resolve()))
    except ValueError:
        return str(path.resolve())


def _is_sha256(value: str) -> bool:
    return len(value) == _SHA256_LENGTH and all(ch in "0123456789abcdef" for ch in value)
