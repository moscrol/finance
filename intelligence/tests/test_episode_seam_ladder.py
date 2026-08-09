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
    assert all(case.timeout > 0 for case in cases)
    # Tier is per case, not a fixture-wide constant.  `weekly-market-cause`
    # moved to `deep` on 2026-08-10: measured live, the causal-evidence rung
    # needs ~130s end to end (133.5s on the run that first reached
    # `structural=completed`), and the `standard` policy caps a whole episode
    # at 90s — it could not finish for reasons that had nothing to do with the
    # seam under test.  `deep` also raises max_steps 6→12 and the synthesis
    # reserve 60→75s, and that reserve is what makes a workable judge window
    # affordable.  Pinning the tiers keeps a future edit from silently
    # re-flattening them.
    assert tuple(case.tier for case in cases) == ("standard", "standard", "deep")


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


# --- offline execution -------------------------------------------------------
#
# These drive the *real* Episode loop.  Only the model and the tools' data
# source are fixed; the registry's execute path, the structural verifier and
# the adapter are production, which is what makes a green rung meaningful.


def test_offline_s1_closes_the_loop_through_real_components() -> None:
    case = CASES["next-session-index"]
    result = ladder.run_offline_stage_case(
        case,
        ladder.resolve_control(case),
        "S1",
    )
    assert result["execution_kind"] == "continuous_episode"
    assert result["status"] == "completed"
    assert result["structural_status"] == "completed"
    assert result["semantic_status"] == "passed"
    assert result["tool_calls"] == 1
    assert result["evidence_hashes"]
    assert result["answer"].strip()
    assert result["missing_outputs"] == []
    assert result["structural_issues"] == []
    assert result["failure_class"] == ""


def test_offline_model_only_ever_sees_this_rungs_tools() -> None:
    """The capability surface is the experiment; a leak voids the reading."""

    case = CASES["next-session-index"]
    result = ladder.run_offline_stage_case(
        case,
        ladder.resolve_control(case),
        "S1",
    )
    assert result["enabled_capabilities"] == ["market_data"]
    assert result["tool_schema_names"] == ["market_data"]
    for offered in result["offered_schemas"]:
        assert set(offered) <= {"market_data"}


def test_offline_higher_rungs_admit_more_tools_and_stay_closed() -> None:
    """Adding a capability must not break an already-closed loop."""

    case = CASES["next-session-index"]
    control = ladder.resolve_control(case)
    surfaces = {}
    for stage_id in ("S1", "S2", "S3"):
        result = ladder.run_offline_stage_case(case, control, stage_id)
        assert result["structural_status"] == "completed", stage_id
        assert result["semantic_status"] == "passed", stage_id
        assert result["failure_class"] == "", stage_id
        surfaces[stage_id] = set(result["enabled_capabilities"])
    assert surfaces["S1"] < surfaces["S2"] < surfaces["S3"]


def test_offline_model_reasoning_slots_are_bound_by_their_own_basis() -> None:
    """``market_cause`` carries ``model_reasoning`` slots.

    ``validate_episode_finish`` compares each binding's ``basis`` with its
    required output's ``grounding_mode``, so a uniform ``evidence`` basis would
    be rejected.  Reaching ``completed`` here proves the per-slot basis is used.
    """

    case = CASES["weekly-market-cause"]
    result = ladder.run_offline_stage_case(
        case,
        ladder.resolve_control(case),
        "S3",
    )
    assert result["question_type"] == "market_cause"
    assert result["structural_status"] == "completed"
    assert result["structural_issues"] == []
    assert result["failure_class"] == ""


def test_offline_stage_below_floor_records_rejection_without_executing() -> None:
    case = CASES["weekly-market-cause"]
    result = ladder.run_offline_stage_case(
        case,
        ladder.resolve_control(case),
        "S2",
    )
    assert result["rejection"] == "mandatory_capability_unauthorized"
    assert "news_search" in result["rejection_detail"]
    assert "execution_kind" not in result
    assert result["tool_schema_names"] == []
    assert result["failure_class"] == ""


def test_offline_planning_stage_runs_nothing() -> None:
    case = CASES["next-session-index"]
    result = ladder.run_offline_stage_case(
        case,
        ladder.resolve_control(case),
        "S0",
    )
    assert result["rejection"] == "planning_only"
    assert result["enabled_capabilities"] == []
    assert "status" not in result


def test_episode_scoped_tool_gets_an_empty_argument_object() -> None:
    """``market_data`` declares an empty closed schema.

    It is ``query_scope="episode"``: one turn-scoped snapshot whose evidence
    surface cannot change by rewording a query.  Sending a ``query`` is rejected
    as ``invalid_arguments``, which then cascades into "output binding must
    contain evidence or a gap" and misreads as a binding defect.
    """

    assert ladder._arguments_for_schema(
        {"type": "object", "properties": {}, "additionalProperties": False}
    ) == {}
    query_arguments = ladder._arguments_for_schema(
        {
            "type": "object",
            "properties": {"query": {"type": "string", "minLength": 1}},
            "required": ["query"],
        }
    )
    assert set(query_arguments) == {"query"}
    assert str(query_arguments["query"]).strip()


def test_offline_tools_run_through_the_real_authorization_path() -> None:
    """Fixture runners replace only the data source, never ``execute``."""

    case = CASES["next-session-index"]
    control = ladder.resolve_control(case)
    with ladder.stage_derivation(case, control, "S1") as derived:
        from intelligence.services.research_tool_registry import UnknownResearchTool

        registry = ladder.stage_registry_with_fixture_runners(
            derived.registry,
            case.as_of,
        )
        assert registry.names() == derived.registry.names()
        with pytest.raises(UnknownResearchTool):
            registry.execute(
                "news_search",
                {"query": "越权调用"},
                context=derived.context,
                step_id="seam-ladder-offline-unauthorized",
            )


def test_offline_artifact_records_scripted_provenance(tmp_path: Path) -> None:
    artifact = ladder.run_offline_ladder(FIXTURE)
    assert artifact["artifact_kind"] == "episode_seam_ladder"
    assert artifact["mode"] == "offline"
    assert artifact["schema_version"] == 1
    assert artifact["generated_at"].endswith("+00:00")
    assert artifact["fixture"]["sha256"]
    assert artifact["source_revision"]
    # Offline provenance must never be dressed up as a production provider.
    assert artifact["runtime"]["provider"] == ladder.OFFLINE_PROVIDER
    assert artifact["runtime"]["model"] == ladder.OFFLINE_PROVIDER
    assert artifact["runtime"]["semantic_verifier"] == "offline_deterministic"
    stages = {stage["stage_id"]: stage for stage in artifact["stages"]}
    assert stages["S0"]["results"] == []
    assert [r["case_id"] for r in stages["S1"]["results"]] == [
        "next-session-index",
    ]
    assert len(stages["S3"]["results"]) == 3
    for stage_id in ("S1", "S2", "S3"):
        for record in stages[stage_id]["results"]:
            assert record["failure_class"] == "", (stage_id, record["case_id"])
            assert record["structural_status"] == "completed"


@pytest.mark.parametrize(
    ("exception", "expected"),
    [
        (ValueError("bad binding"), "contract_or_verifier"),
        (TimeoutError("provider timeout"), "provider_or_budget"),
        (RuntimeError("tool blew up"), "tool_or_data"),
    ],
)
def test_failures_are_attributed_to_the_component_that_owns_them(
    exception: BaseException,
    expected: str,
) -> None:
    failure_class, detail = ladder._classify_failure(exception)
    assert failure_class == expected
    assert type(exception).__name__ in detail


# --- live mode safety --------------------------------------------------------
#
# Live mode spends real provider budget and depends on a real market snapshot.
# It must be opt-in, must never be reached by default, and must refuse to run
# rather than emit a receipt that looks like evidence when its inputs are not
# actually ready.


class _Provider:
    """Minimal stand-in carrying only what a receipt may record."""

    def __init__(self, name: str, model: str) -> None:
        self.name = name
        self.model = model
        self.api_key = "must-never-be-recorded"
        self.base_url = "https://must-never-be-recorded.example"


def test_default_invocation_is_offline_and_never_resolves_a_provider(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Spending real budget must require an explicit flag."""

    def explode(*_args: object, **_kwargs: object):
        raise AssertionError("offline mode must not resolve providers")

    monkeypatch.setattr(ladder.llm_refine, "detect_providers", explode)
    monkeypatch.setattr(ladder, "GLMModelClient", explode)
    monkeypatch.setattr(ladder, "SemanticEpisodeVerifier", explode)

    exit_code = ladder.main(
        ("--questions", str(FIXTURE), "--output", str(tmp_path / "offline.json"))
    )
    assert exit_code == 0
    payload = json.loads((tmp_path / "offline.json").read_text(encoding="utf-8"))
    assert payload["mode"] == "offline"
    assert payload["runtime"]["provider"] == ladder.OFFLINE_PROVIDER


def test_live_receipts_must_stay_outside_the_repository(tmp_path: Path) -> None:
    """Receipts carry run-specific data and are not source; keep them out of Git."""

    with pytest.raises(ValueError):
        ladder.validate_live_output_path(tmp_path / "receipt.json")
    with pytest.raises(ValueError):
        ladder.validate_live_output_path(None)
    accepted = ladder.LIVE_RECEIPT_ROOT / "2026-08-09T00-00-00Z-abc1234.json"
    assert ladder.validate_live_output_path(accepted) == accepted


@pytest.mark.parametrize(
    ("environ", "providers", "latest", "expected"),
    [
        ({}, (_Provider("openai", "gpt-5.6"),), "2026-08-07", "continuous_mode"),
        (
            {"ASK_CONTINUOUS_RUNTIME": "canary"},
            (_Provider("openai", "gpt-5.6"),),
            "2026-08-07",
            "continuous_mode",
        ),
        ({"ASK_CONTINUOUS_RUNTIME": "on"}, (), "2026-08-07", "provider_chain"),
        (
            {"ASK_CONTINUOUS_RUNTIME": "on"},
            (_Provider("openai", "gpt-5.6"),),
            "2026-08-06",
            "market_data_freshness",
        ),
        (
            {"ASK_CONTINUOUS_RUNTIME": "on"},
            (_Provider("openai", "gpt-5.6"),),
            None,
            "market_data_freshness",
        ),
    ],
)
def test_preflight_refuses_an_unready_environment(
    environ: dict[str, str],
    providers: tuple[object, ...],
    latest: str | None,
    expected: str,
) -> None:
    preflight = ladder.live_preflight(
        ladder.load_cases(FIXTURE),
        providers=providers,
        latest_data_date=latest,
        environ=environ,
    )
    assert not preflight.ready
    assert any(expected in item for item in preflight.failures)


def test_preflight_passes_and_records_only_non_secret_identity() -> None:
    provider = _Provider("openai", "gpt-5.6-terra")
    preflight = ladder.live_preflight(
        ladder.load_cases(FIXTURE),
        providers=(provider,),
        latest_data_date="2026-08-08",
        environ={"ASK_CONTINUOUS_RUNTIME": "on"},
    )
    assert preflight.ready
    assert preflight.failures == ()
    assert preflight.provider == "openai"
    assert preflight.model == "gpt-5.6-terra"
    recorded = json.dumps(preflight.to_dict())
    assert provider.api_key not in recorded
    assert provider.base_url not in recorded


def test_failed_preflight_writes_a_receipt_and_fabricates_no_stage_results(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A blocked run must be legible as an environment fact, not a green rung."""

    receipt = tmp_path / "seam-ladder" / "blocked.json"
    monkeypatch.setattr(ladder, "validate_live_output_path", lambda path: path)
    monkeypatch.setattr(
        ladder.llm_refine,
        "detect_providers",
        lambda *_a, **_k: (),
    )
    monkeypatch.setattr(ladder, "latest_market_date", lambda *_a, **_k: "2026-08-08")
    monkeypatch.setattr(
        ladder,
        "GLMModelClient",
        lambda *_a, **_k: (_ for _ in ()).throw(
            AssertionError("must not build a live client after failed preflight")
        ),
    )

    exit_code = ladder.main(
        ("--live", "--questions", str(FIXTURE), "--output", str(receipt))
    )
    assert exit_code != 0
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert payload["mode"] == "live"
    assert payload["preflight"]["ready"] is False
    assert payload["preflight"]["failures"]
    assert payload["stages"] == []


def test_live_runs_only_the_two_designated_rungs() -> None:
    """Live is evidence, not a sweep: relay latency makes a full matrix wasteful."""

    assert ladder.LIVE_STAGE_CASES == (
        ("S1", "next-session-index"),
        ("S3", "weekly-market-cause"),
    )
    cases = {case.case_id for case in ladder.load_cases(FIXTURE)}
    for _stage_id, case_id in ladder.LIVE_STAGE_CASES:
        assert case_id in cases
