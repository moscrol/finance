"""Regression tests for the episode seam ladder runner.

The ladder's only experiment variable is the capability surface handed to one
Episode.  These tests pin the two things that make that variable meaningful:
the stage surface is strictly incremental, and each fixture case declares the
lowest stage at which its contract can even be *constructed*.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import run_episode_seam_ladder as ladder

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "episode_seam_ladder_cases.json"


def test_stage_surface_is_strictly_incremental() -> None:
    """Each stage adds capabilities and never removes one.

    A stage that dropped a capability would confound the ablation: a failure
    could no longer be attributed to the component that was just added.
    """

    stages = ladder.STAGES
    assert tuple(stage.stage_id for stage in stages) == ("S0", "S1", "S2", "S3")
    assert stages[0].capabilities == ()
    assert stages[1].capabilities == ("market_data",)
    assert stages[2].capabilities == ("market_data", "mainline_context")
    assert stages[3].capabilities == (
        "market_data",
        "mainline_context",
        "news_search",
        "evidence_search",
    )
    for earlier, later in zip(stages, stages[1:]):
        assert set(earlier.capabilities).issubset(set(later.capabilities))


def test_fixture_loads_three_market_cases_with_declared_floors() -> None:
    cases = ladder.load_cases(FIXTURE)
    assert tuple(case.case_id for case in cases) == (
        "next-session-index",
        "current-mainline",
        "weekly-market-cause",
    )
    assert tuple(case.expected_stage_floor for case in cases) == ("S1", "S2", "S3")
    assert {case.as_of for case in cases} == {"2026-08-07"}
    assert all(case.tier == "standard" and case.timeout > 0 for case in cases)


def test_stage_floor_ordering_selects_which_cases_run() -> None:
    """A case runs only from its floor upward.

    Below the floor the stage cannot satisfy the contract's mandatory evidence
    capabilities, so running it would record a designed failure rather than an
    observed seam defect.
    """

    cases = ladder.load_cases(FIXTURE)
    assert [case.case_id for case in ladder.cases_for_stage(cases, "S0")] == []
    assert [case.case_id for case in ladder.cases_for_stage(cases, "S1")] == [
        "next-session-index",
    ]
    assert [case.case_id for case in ladder.cases_for_stage(cases, "S2")] == [
        "next-session-index",
        "current-mainline",
    ]
    assert [case.case_id for case in ladder.cases_for_stage(cases, "S3")] == [
        "next-session-index",
        "current-mainline",
        "weekly-market-cause",
    ]


def _write_cases(tmp_path: Path, cases: list[dict[str, object]]) -> Path:
    path = tmp_path / "cases.json"
    path.write_text(
        json.dumps({"schema_version": 1, "cases": cases}),
        encoding="utf-8",
    )
    return path


def _valid_case(**overrides: object) -> dict[str, object]:
    case: dict[str, object] = {
        "id": "case-a",
        "question": "以 2026-08-07 收盘为准，明天大盘怎么看",
        "as_of": "2026-08-07",
        "tier": "standard",
        "timeout": 180.0,
        "expected_stage_floor": "S1",
    }
    case.update(overrides)
    return case


@pytest.mark.parametrize(
    ("cases", "reason"),
    [
        ([], "empty case list"),
        ([_valid_case(), _valid_case()], "duplicate ids"),
        ([_valid_case(expected_stage_floor="S9")], "unknown stage floor"),
        ([_valid_case(expected_stage_floor="S0")], "S0 runs no case"),
        ([_valid_case(timeout=0)], "non-positive timeout"),
        ([_valid_case(tier="turbo")], "unknown tier"),
        ([_valid_case(question="")], "empty question"),
        ([_valid_case(id="")], "empty id"),
    ],
)
def test_fixture_parsing_rejects_unusable_cases(
    tmp_path: Path,
    cases: list[dict[str, object]],
    reason: str,
) -> None:
    with pytest.raises(ValueError):
        ladder.load_cases(_write_cases(tmp_path, cases)), reason
