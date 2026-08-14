from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from intelligence.eval.acceptance_observations import (
    ObservationArtifactError,
    canonical_artifact_hash,
    load_observation_artifact,
    load_reference_eligibility,
)


ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "intelligence/eval/cases/acceptance_cases.json"
OVERLAY = ROOT / "intelligence/eval/cases/acceptance_verdict_contracts.json"
ELIGIBILITY = ROOT / "intelligence/eval/cases/acceptance_reference_eligibility.json"
RUN = ROOT / "intelligence/eval/runs/20260727T032229Z.json"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _truth_payload() -> dict:
    payload = {
        "format_version": 1,
        "artifact_kind": "acceptance_truth_observations",
        "created_at": "2026-07-29T12:00:00Z",
        "source": {
            "run_path": "intelligence/eval/runs/20260727T032229Z.json",
            "run_sha256": _sha(RUN),
            "cases_sha256": _sha(CASES),
            "overlay_sha256": _sha(OVERLAY),
        },
        "evaluator": {
            "id": "independent-semantic-reviewer",
            "kind": "semantic_model",
            "model": "gpt-5.6-sol",
            "independent": True,
        },
        "rubric_sha256": "a" * 64,
        "case_observations": {
            "C9-citation-integrity": {
                "truth_observations": {
                    "pass_rule": {
                        "state": "fail",
                        "reason": "answer does not explain the causal question",
                        "evidence_refs": ["turn:0"],
                    }
                }
            }
        },
    }
    payload["artifact_sha256"] = canonical_artifact_hash(payload)
    return payload


def _experience_payload(blind_manifest: Path) -> dict:
    payload = {
        "format_version": 1,
        "artifact_kind": "acceptance_experience_labels",
        "created_at": "2026-07-29T12:00:00Z",
        "source": {
            "run_path": "intelligence/eval/runs/20260727T032229Z.json",
            "run_sha256": _sha(RUN),
            "cases_sha256": _sha(CASES),
            "overlay_sha256": _sha(OVERLAY),
        },
        "evaluator": {
            "id": "independent-blind-reviewer",
            "kind": "blind_reviewer",
            "model": "gpt-5.6-sol",
            "independent": True,
        },
        "rubric_sha256": "c" * 64,
        "comparison": {
            "reference_agent": "knevo",
            "reference_eligibility_sha256": _sha(ELIGIBILITY),
            "blind_manifest_sha256": json.loads(
                blind_manifest.read_text(encoding="utf-8")
            )["artifact_sha256"],
        },
        "case_observations": {
            "C9-citation-integrity": {
                "experience_verdict": {
                    "eligible": True,
                    "label": "reference",
                    "reason": "reference answer is more direct",
                    "blinded_pair_id": "pair-07",
                    "dimensions": ["directness", "source_clarity"],
                }
            }
        },
    }
    payload["artifact_sha256"] = canonical_artifact_hash(payload)
    return payload


def _write(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "observations.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _blind_manifest(tmp_path: Path) -> Path:
    snapshot = (
        ROOT
        / "intelligence/eval/cases/reference_snapshots/C9-citation-integrity.knevo.json"
    )
    payload = {
        "format_version": 1,
        "created_at": "2026-07-29T11:55:00Z",
        "pairs": {
            "pair-07": {
                "case_id": "C9-citation-integrity",
                "left": "workbench",
                "right": "reference",
                "workbench_run_sha256": _sha(RUN),
                "reference_snapshot_sha256": _sha(snapshot),
            }
        },
    }
    payload["artifact_sha256"] = canonical_artifact_hash(payload)
    path = tmp_path / "blind-manifest.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def test_valid_truth_artifact_is_bound_to_exact_sources(tmp_path: Path) -> None:
    artifact = load_observation_artifact(
        _write(tmp_path, _truth_payload()),
        run_path=RUN,
        cases_path=CASES,
        overlay_path=OVERLAY,
    )

    assert artifact.kind == "acceptance_truth_observations"
    assert artifact.evaluator_id == "independent-semantic-reviewer"
    assert artifact.for_case("C9-citation-integrity")["truth_observations"][
        "pass_rule"
    ]["state"] == "fail"


@pytest.mark.parametrize(
    "mutation",
    ["self_hash", "run_hash", "case_hash", "overlay_hash"],
)
def test_hash_mutation_is_rejected(tmp_path: Path, mutation: str) -> None:
    payload = _truth_payload()
    if mutation == "self_hash":
        payload["case_observations"]["C9-citation-integrity"]["truth_observations"][
            "pass_rule"
        ]["reason"] = "mutated after sealing"
    elif mutation == "run_hash":
        payload["source"]["run_sha256"] = "b" * 64
        payload["artifact_sha256"] = canonical_artifact_hash(payload)
    elif mutation == "case_hash":
        payload["source"]["cases_sha256"] = "b" * 64
        payload["artifact_sha256"] = canonical_artifact_hash(payload)
    else:
        payload["source"]["overlay_sha256"] = "b" * 64
        payload["artifact_sha256"] = canonical_artifact_hash(payload)

    with pytest.raises(ObservationArtifactError):
        load_observation_artifact(
            _write(tmp_path, payload),
            run_path=RUN,
            cases_path=CASES,
            overlay_path=OVERLAY,
        )


def test_valid_experience_artifact_preserves_blind_axis(tmp_path: Path) -> None:
    blind_manifest = _blind_manifest(tmp_path)
    artifact = load_observation_artifact(
        _write(tmp_path, _experience_payload(blind_manifest)),
        run_path=RUN,
        cases_path=CASES,
        overlay_path=OVERLAY,
        reference_eligibility_path=ELIGIBILITY,
        blind_manifest_path=blind_manifest,
    )

    verdict = artifact.for_case("C9-citation-integrity")["experience_verdict"]
    assert artifact.kind == "acceptance_experience_labels"
    assert verdict["label"] == "reference"
    assert verdict["blinded_pair_id"] == "pair-07"


def test_axis_and_rule_smuggling_are_rejected(tmp_path: Path) -> None:
    truth = _truth_payload()
    truth["case_observations"]["C9-citation-integrity"]["truth_observations"] = {
        "answer_present": {
            "state": "pass",
            "reason": "trying to override a deterministic rule",
            "evidence_refs": ["turn:0"],
        }
    }
    truth["artifact_sha256"] = canonical_artifact_hash(truth)
    with pytest.raises(ObservationArtifactError, match="cannot externally observe"):
        load_observation_artifact(
            _write(tmp_path, truth),
            run_path=RUN,
            cases_path=CASES,
            overlay_path=OVERLAY,
        )

    blind_manifest = _blind_manifest(tmp_path)
    experience = _experience_payload(blind_manifest)
    experience["case_observations"]["C9-citation-integrity"] = {
        "truth_observations": {}
    }
    experience["artifact_sha256"] = canonical_artifact_hash(experience)
    with pytest.raises(ObservationArtifactError, match="only experience_verdict"):
        load_observation_artifact(
            _write(tmp_path, experience),
            run_path=RUN,
            cases_path=CASES,
            overlay_path=OVERLAY,
            reference_eligibility_path=ELIGIBILITY,
            blind_manifest_path=blind_manifest,
        )


def test_observation_for_case_absent_from_run_is_rejected(tmp_path: Path) -> None:
    payload = _truth_payload()
    payload["case_observations"] = {
        "A2-next-day-call": {
            "truth_observations": {
                "pass_rule": {
                    "state": "pass",
                    "reason": "case was never in this run",
                    "evidence_refs": ["turn:0"],
                }
            }
        }
    }
    payload["artifact_sha256"] = canonical_artifact_hash(payload)

    with pytest.raises(ObservationArtifactError, match="absent from source run"):
        load_observation_artifact(
            _write(tmp_path, payload),
            run_path=RUN,
            cases_path=CASES,
            overlay_path=OVERLAY,
        )


def test_reference_eligibility_accounts_for_all_cases_and_aliases() -> None:
    eligibility = load_reference_eligibility(cases_path=CASES)

    assert len(eligibility) == 28
    assert eligibility["A4-dual-red"]["independent_sample"] is False
    assert eligibility["C7-temporal-leakage"]["independent_sample"] is False
    assert eligibility["C7-temporal-leakage"]["truth_status"] == "ineligible"
    assert eligibility["C1-future-date-no-data"]["truth_status"] == "eligible"
    assert sum(1 for item in eligibility.values() if item["snapshot"] is not None) == 22


def test_truth_evidence_reference_must_exist_in_bound_run(tmp_path: Path) -> None:
    payload = _truth_payload()
    payload["case_observations"]["C9-citation-integrity"]["truth_observations"][
        "pass_rule"
    ]["evidence_refs"] = ["turn:99"]
    payload["artifact_sha256"] = canonical_artifact_hash(payload)

    with pytest.raises(ObservationArtifactError, match="out of range"):
        load_observation_artifact(
            _write(tmp_path, payload),
            run_path=RUN,
            cases_path=CASES,
            overlay_path=OVERLAY,
        )
