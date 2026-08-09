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


# --- stage derivation -------------------------------------------------------
#
# Everything below runs production routing and production contract assembly.
# Neither touches the network or a model: ``TurnControlCore`` takes a stub
# ``llm_complete`` and ``build_episode_context`` is pure composition.

CASES = {case.case_id: case for case in ladder.load_cases(FIXTURE)}

# The routing fact each floor rests on, measured against production
# ``TurnControlCore`` + ``build_episode_context``.  A floor is only meaningful
# while these hold: if a question re-routes (say to ``general_finance_qa``,
# whose authorization is ``kb_search``/``web_search``), its stage intersection
# changes and the rung silently stops testing what it claims to.
ROUTED_FACTS = {
    "next-session-index": ("market_forecast", ("market_data",)),
    "current-mainline": ("market_watch", ("market_data", "mainline_context")),
    "weekly-market-cause": ("market_cause", ("market_data", "news_search")),
}


@pytest.mark.parametrize("case_id", sorted(ROUTED_FACTS))
def test_routing_and_mandatory_capabilities_stay_put(case_id: str) -> None:
    """Pin the routing facts the stage floors are derived from."""

    expected_type, expected_mandatory = ROUTED_FACTS[case_id]
    control = ladder.resolve_control(CASES[case_id])
    assert control.task_frame.question_type == expected_type
    assert control.contract_required
    with ladder.stage_derivation(CASES[case_id], control, "S3") as derived:
        plan = derived.context.contract.evidence_plan
        assert plan.mandatory_capabilities == expected_mandatory


def test_floor_is_the_lowest_stage_whose_contract_can_be_built() -> None:
    """Each declared floor must be exactly the first constructible stage.

    ``ResearchTaskContract.__post_init__`` rejects a contract whose evidence
    plan demands a capability the stage does not authorize.  Declaring a floor
    lower than that point would record a designed failure; declaring it higher
    would skip a rung that actually works.
    """

    for case in CASES.values():
        control = ladder.resolve_control(case)
        constructible = []
        for stage in ladder.STAGES:
            with ladder.stage_derivation(case, control, stage.stage_id) as derived:
                if derived.context is not None:
                    constructible.append(stage.stage_id)
        assert constructible, f"{case.case_id} runs at no stage"
        assert constructible[0] == case.expected_stage_floor


def test_stage_below_floor_is_rejected_not_executed() -> None:
    """S1 cannot run a mainline case, and says why instead of crashing."""

    case = CASES["current-mainline"]
    control = ladder.resolve_control(case)
    with ladder.stage_derivation(case, control, "S1") as derived:
        assert derived.context is None
        assert derived.registry is None
        assert derived.rejection == "mandatory_capability_unauthorized"
        assert "mainline_context" in derived.rejection_detail


def test_planning_stage_builds_no_contract_and_no_registry() -> None:
    case = CASES["next-session-index"]
    control = ladder.resolve_control(case)
    with ladder.stage_derivation(case, control, "S0") as derived:
        assert derived.context is None
        assert derived.registry is None
        assert derived.enabled_capabilities == ()
        assert derived.rejection == "planning_only"


def test_stage_narrows_capabilities_without_touching_required_outputs() -> None:
    """The capability surface is the only business variable.

    Narrowing the tool schema alone would leave the contract authorizing more
    than the rung exposes, which is an unreal privilege path rather than a
    smaller assembly.
    """

    case = CASES["next-session-index"]
    control = ladder.resolve_control(case)
    with ladder.stage_derivation(case, control, "S3") as source:
        source_outputs = source.context.contract.required_outputs
        source_hash = source.context.contract.task_frame_hash
    with ladder.stage_derivation(case, control, "S1") as derived:
        contract = derived.context.contract
        assert contract.required_outputs == source_outputs
        assert contract.task_frame_hash == source_hash
        assert contract.allowed_capabilities == ("market_data",)
        assert derived.enabled_capabilities == ("market_data",)
        assert derived.registry.names() == ("market_data",)
        assert all(
            spec.capability in contract.allowed_capabilities
            for spec in derived.registry.authorized_specs()
        )


def test_every_stage_schema_tool_maps_back_to_an_enabled_capability() -> None:
    """Tool names and capability names are different namespaces.

    Comparing them directly happens to work today only because the 12
    registered tools are named after their capability; the mapping is the
    contract, so assert through it.
    """

    case = CASES["weekly-market-cause"]
    control = ladder.resolve_control(case)
    with ladder.stage_derivation(case, control, "S3") as derived:
        enabled = set(derived.enabled_capabilities)
        assert enabled
        for name in derived.registry.names():
            assert derived.registry.resolve(name).capability in enabled
        schema_names = {
            definition["function"]["name"]
            for definition in derived.registry.tool_definitions(
                derived.enabled_capabilities
            )
        }
        assert schema_names == set(derived.registry.names())


def test_stage_registry_refuses_an_unauthorized_capability() -> None:
    """A tool outside the rung must not execute even if the model asks.

    The case has to be one the rung can actually build (``next-session-index``
    floors at S1); a case rejected for its floor has no registry to probe, so
    it would prove nothing about authorization.
    """

    case = CASES["next-session-index"]
    control = ladder.resolve_control(case)
    with ladder.stage_derivation(case, control, "S1") as derived:
        from intelligence.services.research_tool_registry import UnknownResearchTool

        assert "news_search" not in derived.registry.names()
        with pytest.raises(UnknownResearchTool):
            derived.registry.execute(
                "news_search",
                {"query": "本周下跌原因"},
                context=derived.context,
                step_id="seam-ladder-unauthorized",
            )


def test_each_stage_gets_its_own_budget_and_deadline() -> None:
    """Stages must not share a root budget ledger or a deadline.

    ``ResearchDeadline`` is an absolute monotonic instant and the root budget
    is a live-registered ledger.  Reusing one context across rungs would let an
    early stage's tool calls drain a later stage, so a failure at S3 could come
    from spent budget rather than from the component S3 admitted.
    """

    case = CASES["next-session-index"]
    control = ladder.resolve_control(case)
    seen_ids: set[str] = set()
    ledgers: list[object] = []
    for stage_id in ("S1", "S2", "S3"):
        with ladder.stage_derivation(case, control, stage_id) as derived:
            contract = derived.context.contract
            assert contract.task_id not in seen_ids
            seen_ids.add(contract.task_id)
            budget = derived.context.root_budget
            assert budget is not None
            assert budget.episode_id == contract.task_id
            assert budget not in ledgers
            ledgers.append(budget)
            assert derived.context.deadline.remaining() > 0


def test_stage_derivation_releases_its_episode_registration() -> None:
    """The ledger registry rejects a second live budget for one episode id.

    Without release, re-running the same stage in one process dies on "root
    budget already exists" -- a harness artifact that reads like a runtime
    defect.
    """

    case = CASES["next-session-index"]
    control = ladder.resolve_control(case)
    with ladder.stage_derivation(case, control, "S1") as first:
        first_id = first.context.contract.task_id
    with ladder.stage_derivation(case, control, "S1") as second:
        assert second.context is not None
        assert second.context.contract.task_id == first_id
