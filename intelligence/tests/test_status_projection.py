"""R-20260816-18：三份 artifact status 必须走同一投影。

冻结形状来自 2026-08-16 两份生产 run 的 status 切片（无题面/正文）：
``run_20260816_221823_213588`` 是 ``outcome=failed ∧ run.json=completed``；
``run_20260816_230528_976709`` 是 outcome=partial，run=completed，不在禁对里。
"""

from __future__ import annotations

import json
from pathlib import Path

from intelligence.services.status_projection import (
    ArtifactStatuses,
    coalesce_episode_status,
    episode_status_from_turn,
    project_artifact_statuses,
)

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "r18_status_projection"


def _load_slice(name: str) -> dict[str, object]:
    return json.loads((_FIXTURE_DIR / name).read_text(encoding="utf-8"))


def test_projection_never_pairs_failed_outcome_with_completed_run() -> None:
    for status in ("completed", "partial", "degraded", "failed", "cancelled", "", "weird"):
        projected = project_artifact_statuses(status)
        assert not (
            projected.episode == "failed" and projected.run == "completed"
        ), status


def test_failed_outcome_projects_run_failed_and_report_blocked() -> None:
    projected = project_artifact_statuses("failed")
    assert projected == ArtifactStatuses(
        episode="failed",
        run="failed",
        report="blocked",
        report_business="blocked",
        transport="failed",
    )


def test_partial_and_degraded_keep_transport_complete() -> None:
    for status in ("partial", "degraded"):
        projected = project_artifact_statuses(status)
        assert projected.episode == status
        assert projected.run == "completed"
        assert projected.report == "partial"
        assert projected.report_business == "partial"
        assert projected.transport == "completed"


def test_completed_projects_all_success() -> None:
    projected = project_artifact_statuses("completed")
    assert projected.episode == "completed"
    assert projected.run == "completed"
    assert projected.report == "completed"
    assert projected.report_business == "complete"
    assert projected.transport == "completed"


def test_coalesce_research_failure_wins_over_degraded_delivery() -> None:
    assert coalesce_episode_status("degraded", "failed") == "failed"
    assert coalesce_episode_status("failed", None) == "failed"
    assert coalesce_episode_status("degraded", None) == "degraded"
    assert coalesce_episode_status("partial", "completed") == "partial"
    assert coalesce_episode_status("completed", "partial") == "completed"


def test_frozen_221823_contradiction_is_resolved_by_projection() -> None:
    captured = _load_slice("run_20260816_221823_213588.json")
    run_status = captured["run"]["status"]
    outcome_status = captured["episode"]["outcome"]["status"]
    assert outcome_status == "failed"
    assert run_status == "completed"

    projected = project_artifact_statuses(
        coalesce_episode_status("degraded", outcome_status)
    )
    assert projected.episode == "failed"
    assert projected.run == "failed"
    assert projected.report == "blocked"


def test_frozen_230528_partial_may_keep_run_completed() -> None:
    captured = _load_slice("run_20260816_230528_976709.json")
    outcome_status = captured["episode"]["outcome"]["status"]
    assert outcome_status == "partial"
    assert captured["run"]["status"] == "completed"

    projected = project_artifact_statuses(
        coalesce_episode_status("degraded", outcome_status)
    )
    assert projected.episode == "degraded"
    assert projected.run == "completed"
    assert not (projected.episode == "failed" and projected.run == "completed")


class _Turn:
    def __init__(self, status: str, artifact: dict[str, object] | None) -> None:
        self.status = status
        self.private_artifact = artifact


def test_episode_status_from_turn_reads_failed_outcome_out_of_degraded_delivery() -> None:
    turn = _Turn(
        "degraded",
        {"outcome": {"status": "failed", "stop_reason": "repair_model_unavailable"}},
    )
    assert episode_status_from_turn(turn) == "failed"
    assert project_artifact_statuses(episode_status_from_turn(turn)).run == "failed"


def test_episode_status_from_turn_keeps_degraded_when_artifact_has_no_outcome() -> None:
    turn = _Turn("degraded", {"judge_status": "unavailable"})
    assert episode_status_from_turn(turn) == "degraded"
