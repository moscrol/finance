from __future__ import annotations

from intelligence.eval.episode_bindings_rate import (
    judgment_hash_rate,
    legacy_bindings_rate,
    stratified_evidence_bound_rate,
)


def _episode(
    *,
    judgment_mode: str,
    judgment_hashes: list[str],
    judgment_gap: str = "",
    boundary_hashes: list[str] | None = None,
    boundary_gap: str = "",
) -> dict[str, object]:
    if boundary_hashes is None:
        boundary_hashes = ["e1"]
    return {
        "contract": {
            "required_outputs": [
                {"output_id": "direct_answer", "grounding_mode": judgment_mode},
                {"output_id": "evidence_boundary", "grounding_mode": "evidence"},
            ]
        },
        "outcome": {
            "bindings": [
                {
                    "output_id": "direct_answer",
                    "evidence_hashes": judgment_hashes,
                    "gap": judgment_gap,
                    "basis": judgment_mode,
                },
                {
                    "output_id": "evidence_boundary",
                    "evidence_hashes": boundary_hashes,
                    "gap": boundary_gap,
                    "basis": "evidence",
                },
            ]
        },
    }


def test_r15_zero_hash_judgment_is_unbound_on_legacy_and_bound_when_stratified() -> None:
    episode = _episode(judgment_mode="model_reasoning", judgment_hashes=[])
    assert legacy_bindings_rate(episode) == 0.5
    assert stratified_evidence_bound_rate(episode) == 1.0
    assert judgment_hash_rate(episode) == 0.0


def test_r15_gap_on_reasoning_slot_still_drops_legacy_only() -> None:
    episode = _episode(
        judgment_mode="model_reasoning",
        judgment_hashes=[],
        judgment_gap="缺少支撑数值估值区间",
        boundary_hashes=["e3", "e4"],
    )
    assert legacy_bindings_rate(episode) == 0.5
    assert stratified_evidence_bound_rate(episode) == 1.0


def test_pre_evidence_mode_unchanged() -> None:
    episode = _episode(
        judgment_mode="evidence",
        judgment_hashes=["E1", "E2"],
        boundary_hashes=["E1"],
    )
    assert legacy_bindings_rate(episode) == 1.0
    assert stratified_evidence_bound_rate(episode) == 1.0
    assert judgment_hash_rate(episode) is None


def test_missing_episode_is_none() -> None:
    assert legacy_bindings_rate(None) is None
    assert stratified_evidence_bound_rate(None) is None
    assert judgment_hash_rate(None) is None


def test_empty_bindings_are_zero() -> None:
    episode = {"contract": {"required_outputs": []}, "outcome": {"bindings": []}}
    assert legacy_bindings_rate(episode) == 0.0
    assert stratified_evidence_bound_rate(episode) == 0.0


def test_all_reasoning_slots_leave_stratified_undefined() -> None:
    episode = {
        "contract": {
            "required_outputs": [
                {"output_id": "direct_answer", "grounding_mode": "model_reasoning"},
            ]
        },
        "outcome": {
            "bindings": [
                {
                    "output_id": "direct_answer",
                    "evidence_hashes": [],
                    "gap": "",
                    "basis": "model_reasoning",
                }
            ]
        },
    }
    assert legacy_bindings_rate(episode) == 0.0
    assert stratified_evidence_bound_rate(episode) is None
    assert judgment_hash_rate(episode) == 0.0
