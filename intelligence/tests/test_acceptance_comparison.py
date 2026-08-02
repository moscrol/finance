from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from intelligence.eval import acceptance
from intelligence.eval.acceptance_comparison import (
    ComparisonArtifactError,
    build_comparison_queue,
    canonical_payload_hash,
    load_comparison_result,
    queue_payload,
)


REPO = Path(__file__).resolve().parents[2]
RUN = REPO / "intelligence/eval/runs/20260801T035325Z.json"


def _valid_result_payload() -> tuple[dict, object]:
    queue = build_comparison_queue(RUN, agent="knevo")
    payload = queue_payload(queue, created_at="2026-08-01T12:00:00+00:00")
    payload["artifact_kind"] = "acceptance_information_comparisons"
    payload["evaluator"] = {
        "id": "codex-independent-review",
        "kind": "semantic_model",
        "model": "gpt-5.6-sol",
        "independent": True,
    }
    payload["case_observations"] = {
        "A1-market-overview": {
            "state": "tie",
            "reason": "Workbench is more auditable; Knevo is broader.",
            "workbench_unique": ["project-local market stage"],
            "reference_unique": ["broader narrative context"],
            "unsupported_detail_risks": ["reference uses non-local numeric sources"],
        }
    }
    payload["artifact_sha256"] = canonical_payload_hash(payload)
    return payload, queue


def _write_payload(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "comparison.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def test_valid_comparison_result_binds_both_answers(tmp_path: Path) -> None:
    payload, queue = _valid_result_payload()

    artifact = load_comparison_result(_write_payload(tmp_path, payload), queue=queue)

    assert artifact.case_observations["A1-market-overview"]["state"] == "tie"
    assert artifact.evaluator_model == "gpt-5.6-sol"


@pytest.mark.parametrize(
    "mutation",
    [
        "run_hash",
        "cases_hash",
        "overlay_hash",
        "rubric_hash",
        "snapshot_hash",
        "artifact_hash",
    ],
)
def test_comparison_mutation_fails_closed(
    tmp_path: Path,
    mutation: str,
) -> None:
    payload, queue = _valid_result_payload()
    mutated = copy.deepcopy(payload)
    if mutation == "run_hash":
        mutated["source"]["run_sha256"] = "0" * 64
    elif mutation == "cases_hash":
        mutated["source"]["cases_sha256"] = "0" * 64
    elif mutation == "overlay_hash":
        mutated["source"]["overlay_sha256"] = "0" * 64
    elif mutation == "rubric_hash":
        mutated["rubric_sha256"] = "0" * 64
    elif mutation == "snapshot_hash":
        mutated["source"]["reference_snapshots"]["A1-market-overview"][
            "file_sha256"
        ] = "0" * 64
    elif mutation == "artifact_hash":
        mutated["artifact_sha256"] = "0" * 64

    if mutation != "artifact_hash":
        mutated["artifact_sha256"] = canonical_payload_hash(mutated)

    with pytest.raises(ComparisonArtifactError):
        load_comparison_result(_write_payload(tmp_path, mutated), queue=queue)


def test_ineligible_or_missing_snapshot_is_not_queued() -> None:
    queue = build_comparison_queue(RUN, agent="knevo")

    assert queue.entries["A1-market-overview"].status == "eligible"
    assert queue.entries["A4-dual-red"].status == "ineligible"
    assert queue.entries["A8-market-stage"].status == "ineligible"
    assert queue.entries["A9-sentiment-contradiction"].status == "missing"


def test_noneligible_case_cannot_receive_comparison(tmp_path: Path) -> None:
    payload, queue = _valid_result_payload()
    payload["case_observations"]["A8-market-stage"] = {
        "state": "workbench_wins",
        "reason": "invalid comparison",
        "workbench_unique": [],
        "reference_unique": [],
        "unsupported_detail_risks": [],
    }
    payload["artifact_sha256"] = canonical_payload_hash(payload)

    with pytest.raises(ComparisonArtifactError, match="not comparison-eligible"):
        load_comparison_result(_write_payload(tmp_path, payload), queue=queue)


def test_unknown_comparison_state_fails_closed(tmp_path: Path) -> None:
    payload, queue = _valid_result_payload()
    payload["case_observations"]["A1-market-overview"]["state"] = "close-enough"
    payload["artifact_sha256"] = canonical_payload_hash(payload)

    with pytest.raises(ComparisonArtifactError, match="invalid state"):
        load_comparison_result(_write_payload(tmp_path, payload), queue=queue)


def test_board_displays_valid_information_comparison(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload, _queue = _valid_result_payload()
    result_path = _write_payload(tmp_path, payload)

    assert (
        acceptance.main(
            [
                "board",
                "--run",
                str(RUN),
                "--information-comparisons",
                str(result_path),
            ]
        )
        == 0
    )

    output = capsys.readouterr().out
    a1 = next(line for line in output.splitlines() if line.startswith("| A1-"))
    assert "| ➖ 持平 |" in a1
    assert "信息量已评/未评 1/9" in output
