"""D3：空池恰好一次换口径。输入加法，不改发布门。"""

from __future__ import annotations

from copy import deepcopy
from datetime import date
import json

from intelligence.runtime.agent_episode import ContinuousAgentEpisode
from intelligence.services.agent_research import AgentEvidence, StructuredObservation
from intelligence.services.agent_runtime import ModelToolCall, ModelTurn
from intelligence.services.empty_pool_fallback import (
    EmptyToolCall,
    apply_fallback_backfill_mutex,
    prefetch_pool_is_empty,
    propose_empty_pool_fallback,
)
from intelligence.services.episode_issues import (
    BackfillPlan,
    Issue,
    IssueCode,
    plan_issue_backfill,
)
from intelligence.services.evidence_capabilities import EvidencePlan
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import (
    InformationCutoff,
    RequiredOutput,
    ResearchDeadline,
    ResearchPolicy,
    ResearchRunContext,
    ResearchTaskContract,
)
from intelligence.services.research_tool_registry import (
    ResearchToolRegistry,
    ToolSpec,
)
from intelligence.services.task_frame import TaskFrame


def _sector_daily(*, empty: bool, **overrides: object) -> EmptyToolCall:
    arguments: dict[str, object] = {
        "dataset": "sector_daily",
        "metrics": ["return_pct", "marginal_volume_pct"],
        "dimensions": ["trade_date", "sector_name"],
        "filters": [{"field": "sector_name", "op": "eq", "value": "创新药"}],
        "time_range": {"start": "2026-08-18", "end": "2026-08-18"},
        "limit": 20,
    }
    arguments.update(overrides)
    return EmptyToolCall(
        name="finance_query",
        arguments=arguments,
        empty=empty,
    )


def test_empty_sector_daily_proposes_same_day_amount_rank() -> None:
    proposal = propose_empty_pool_fallback(
        question_type="theme_analysis",
        as_of="2026-08-18",
        cutoff_source="requested",
        prefetch_empty=True,
        first_results=(_sector_daily(empty=True),),
        authorized_tools=frozenset({"finance_query", "market_data"}),
        already_attempted=False,
        in_repair=False,
        backfill_plan=None,
    )

    assert proposal is not None
    assert proposal.tool == "finance_query"
    assert proposal.fallback_arguments["dataset"] == "sector_daily"
    assert proposal.fallback_arguments["time_range"] == {
        "start": "2026-08-18",
        "end": "2026-08-18",
    }
    assert proposal.fallback_arguments["order_by"] == [
        {"field": "amount", "direction": "desc"}
    ]
    assert "amount" in proposal.fallback_arguments["metrics"]
    assert proposal.fallback_arguments.get("filters") in ((), [], None)
    assert int(proposal.fallback_arguments["limit"]) <= 8
    assert proposal.as_of == "2026-08-18"
    assert proposal.fallback_arguments != proposal.original_arguments


def test_first_round_with_rows_does_not_fallback() -> None:
    assert (
        propose_empty_pool_fallback(
            question_type="theme_analysis",
            as_of="2026-08-18",
            cutoff_source="requested",
            prefetch_empty=True,
            first_results=(_sector_daily(empty=False),),
            authorized_tools=frozenset({"finance_query"}),
            already_attempted=False,
            in_repair=False,
            backfill_plan=None,
        )
        is None
    )


def test_prefetch_rows_block_fallback() -> None:
    assert (
        propose_empty_pool_fallback(
            question_type="theme_analysis",
            as_of="2026-08-18",
            cutoff_source="requested",
            prefetch_empty=False,
            first_results=(_sector_daily(empty=True),),
            authorized_tools=frozenset({"finance_query"}),
            already_attempted=False,
            in_repair=False,
            backfill_plan=None,
        )
        is None
    )


def test_historical_as_of_clamps_leaking_end_date() -> None:
    proposal = propose_empty_pool_fallback(
        question_type="theme_analysis",
        as_of="2026-08-18",
        cutoff_source="requested",
        prefetch_empty=True,
        first_results=(
            _sector_daily(
                empty=True,
                time_range={"start": "2026-08-18", "end": "2026-08-19"},
            ),
        ),
        authorized_tools=frozenset({"finance_query"}),
        already_attempted=False,
        in_repair=False,
        backfill_plan=None,
    )

    assert proposal is not None
    assert proposal.fallback_arguments["time_range"]["end"] == "2026-08-18"
    assert proposal.fallback_arguments["time_range"]["start"] <= "2026-08-18"


def test_query_window_wins_over_runtime_default_cutoff() -> None:
    proposal = propose_empty_pool_fallback(
        question_type="theme_analysis",
        as_of="2026-08-24",
        cutoff_source="runtime_default",
        prefetch_empty=True,
        first_results=(_sector_daily(empty=True),),
        authorized_tools=frozenset({"finance_query"}),
        already_attempted=False,
        in_repair=False,
        backfill_plan=None,
    )

    assert proposal is not None
    assert proposal.as_of == "2026-08-18"
    assert proposal.fallback_arguments["time_range"]["end"] == "2026-08-18"


def _fallback_event() -> object:
    return type(
        "Event",
        (),
        {
            "kind": "tool_request",
            "payload": {
                "fallback_query": True,
                "name": "finance_query",
                "call_id": "empty-pool-fallback-1",
            },
        },
    )()


def test_backfill_after_fallback_drops_finance_query() -> None:
    """P1：事后补枪必须看见已经打过的 fallback，不能只测反方向。"""

    events = (_fallback_event(),)
    plan = plan_issue_backfill(
        (
            Issue(
                IssueCode.NUMERIC_UNSUPPORTED,
                "numeric_condition",
                "unsupported numeric condition without bound evidence",
            ),
        ),
        subject_kind="company",
        events=events,
    )
    assert plan is None


def test_backfill_after_fallback_keeps_unrelated_financial_data() -> None:
    events = (_fallback_event(),)
    plan = plan_issue_backfill(
        (
            Issue(
                IssueCode.FINANCIAL_ANCHOR_MISSING,
                "financial_business_anchor",
                "any wording",
            ),
        ),
        events=events,
    )
    assert plan is not None
    assert plan.missing_capabilities == ("financial_data",)


def test_adapter_backfill_plan_uses_outcome_events(monkeypatch) -> None:
    from types import SimpleNamespace

    from intelligence.runtime.continuous_turn_adapter import _issue_backfill_plan

    monkeypatch.setattr(
        "intelligence.runtime.continuous_turn_adapter.numeric_condition_unsupported",
        lambda _verified: False,
    )
    structural = SimpleNamespace(
        issue_items=(
            Issue(
                IssueCode.NUMERIC_UNSUPPORTED,
                "numeric_condition",
                "unsupported numeric condition without bound evidence",
            ),
        )
    )
    context = SimpleNamespace(
        contract=SimpleNamespace(subject_kind="company", subject="宁德时代")
    )
    assert (
        _issue_backfill_plan(structural, context, events=(_fallback_event(),))
        is None
    )
    untouched = _issue_backfill_plan(structural, context, events=())
    assert untouched is not None
    assert untouched.missing_capabilities == ("finance_query",)


def test_adapter_call_site_passes_outcome_events() -> None:
    from pathlib import Path

    from intelligence.runtime import continuous_turn_adapter as adapter

    text = Path(adapter.__file__).read_text(encoding="utf-8")
    assert "events=outcome.events" in text


def test_apply_mutex_is_noop_without_fallback() -> None:
    plan = BackfillPlan(
        codes=(IssueCode.NUMERIC_UNSUPPORTED,),
        missing_outputs=("direct_assessment",),
        missing_capabilities=("finance_query",),
    )
    assert apply_fallback_backfill_mutex(plan, ()) is plan


def test_backfill_plan_mutex_skips_same_capability() -> None:
    plan = BackfillPlan(
        codes=(IssueCode.NUMERIC_UNSUPPORTED,),
        missing_outputs=("direct_assessment",),
        missing_capabilities=("finance_query",),
    )
    assert (
        propose_empty_pool_fallback(
            question_type="theme_analysis",
            as_of="2026-08-18",
            cutoff_source="requested",
            prefetch_empty=True,
            first_results=(_sector_daily(empty=True),),
            authorized_tools=frozenset({"finance_query"}),
            already_attempted=False,
            in_repair=False,
            backfill_plan=plan,
        )
        is None
    )


def test_repair_reentry_does_not_fallback() -> None:
    assert (
        propose_empty_pool_fallback(
            question_type="theme_analysis",
            as_of="2026-08-18",
            cutoff_source="requested",
            prefetch_empty=True,
            first_results=(_sector_daily(empty=True),),
            authorized_tools=frozenset({"finance_query"}),
            already_attempted=False,
            in_repair=True,
            backfill_plan=None,
        )
        is None
    )


def test_market_watch_is_out_of_scope() -> None:
    assert (
        propose_empty_pool_fallback(
            question_type="market_watch",
            as_of="2026-08-18",
            cutoff_source="requested",
            prefetch_empty=True,
            first_results=(_sector_daily(empty=True),),
            authorized_tools=frozenset({"finance_query"}),
            already_attempted=False,
            in_repair=False,
            backfill_plan=None,
        )
        is None
    )


def test_already_attempted_is_once_only() -> None:
    assert (
        propose_empty_pool_fallback(
            question_type="theme_analysis",
            as_of="2026-08-18",
            cutoff_source="requested",
            prefetch_empty=True,
            first_results=(_sector_daily(empty=True),),
            authorized_tools=frozenset({"finance_query"}),
            already_attempted=True,
            in_repair=False,
            backfill_plan=None,
        )
        is None
    )


def test_same_amount_rank_query_is_not_rewritten() -> None:
    call = _sector_daily(
        empty=True,
        metrics=["amount", "return_pct"],
        filters=[],
        order_by=[{"field": "amount", "direction": "desc"}],
        limit=8,
    )
    assert (
        propose_empty_pool_fallback(
            question_type="theme_analysis",
            as_of="2026-08-18",
            cutoff_source="requested",
            prefetch_empty=True,
            first_results=(call,),
            authorized_tools=frozenset({"finance_query"}),
            already_attempted=False,
            in_repair=False,
            backfill_plan=None,
        )
        is None
    )


def test_prefetch_without_observations_counts_as_empty() -> None:
    class _Item:
        observations = ()

    assert prefetch_pool_is_empty(()) is True
    assert prefetch_pool_is_empty((_Item(),)) is True

    class _Row:
        observations = (object(),)

    assert prefetch_pool_is_empty((_Row(),)) is False


class _ScriptedModel:
    def __init__(self, turns: list[ModelTurn]) -> None:
        self._turns = iter(turns)
        self.calls: list[dict[str, object]] = []

    def complete(self, *, messages, tools, timeout):
        self.calls.append(
            {
                "messages": deepcopy(messages),
                "tools": deepcopy(tools),
                "timeout": timeout,
            }
        )
        return next(self._turns)


def _theme_frame(*, question_type: str = "theme_analysis") -> TaskFrame:
    return TaskFrame(
        raw_question="创新药板块后续怎么看",
        user_goal="判断板块结构",
        question_type=question_type,
        subject="创新药",
        subject_kind="theme",
        market_scope="A股",
        timeframe="2026-08-18",
        required_outputs=("direct_assessment",),
        assumptions=("按问句日理解",),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="current_market_scenarios",
        confidence=0.95,
    )


def _theme_context(
    frame: TaskFrame,
    *,
    max_steps: int = 4,
    allowed_capabilities: tuple[str, ...] = ("finance_query",),
    cutoff: InformationCutoff | None = None,
) -> ResearchRunContext:
    contract = ResearchTaskContract(
        task_id="empty-pool-fallback-test",
        question=frame.raw_question,
        subject=frame.subject,
        subject_kind=frame.subject_kind,
        question_type=frame.question_type,
        required_outputs=tuple(
            RequiredOutput(item, item, ("finance_query",), True)
            for item in frame.required_outputs
        ),
        allowed_capabilities=allowed_capabilities,
        research_tier="quick",
        freshness="current",
        timeframe=frame.timeframe,
        evidence_plan=EvidencePlan(),
        task_frame_hash=frame.task_frame_hash,
    )
    return ResearchRunContext(
        contract=contract,
        deadline=ResearchDeadline.from_timeout(30.0),
        policy=ResearchPolicy("quick", max_steps, 30.0, 0.0),
        trace_parent_id="empty-pool-fallback-test",
        today="2026-08-18",
        latest_data_date="2026-08-18",
        information_cutoff=cutoff
        or InformationCutoff(date(2026, 8, 18), "requested"),
    )


def _parse_passthrough(arguments):
    raw = dict(arguments)
    return raw, json.dumps(raw, ensure_ascii=False, sort_keys=True)


def _empty_then_amount_runner(seen: list[object]):
    def runner(value: object, _context: object):
        seen.append(value)
        args = value if isinstance(value, dict) else {}
        order_by = args.get("order_by") or ()
        is_amount = (
            order_by
            and isinstance(order_by[0], dict)
            and order_by[0].get("field") == "amount"
        )
        if is_amount:
            evidence = AgentEvidence(
                tool="finance_query",
                title="板块成交额前排（2026-08-18）",
                detail="成交额前排观察",
                source="本地行情",
                source_date="2026-08-18",
                content_hash="amount-1",
                observations=(
                    StructuredObservation(
                        "半导体",
                        "2026-08-18",
                        "amount",
                        120.0,
                    ),
                ),
            )
            return (
                [evidence],
                "amount rank",
                ProviderTrace(
                    provider="test:finance",
                    capability="finance_query",
                    status="success",
                    result_count=1,
                    source_trade_date="2026-08-18",
                ),
            )
        return (
            [],
            "empty sector_daily",
            ProviderTrace(
                provider="test:finance",
                capability="finance_query",
                status="empty",
                result_count=0,
                source_trade_date="2026-08-18",
            ),
        )

    return runner


def _finance_registry(runner, *, opening_prefetch=()):
    return ResearchToolRegistry(
        (
            ToolSpec(
                name="finance_query",
                capability="finance_query",
                description="结构化板块查询",
                cost="local",
                freshness="current",
                runner=runner,
                parse_arguments=_parse_passthrough,
            ),
        ),
        opening_prefetch=opening_prefetch,
    )


def _empty_sector_turn() -> ModelTurn:
    return ModelTurn(
        "",
        (
            ModelToolCall(
                "call-1",
                "finance_query",
                {
                    "dataset": "sector_daily",
                    "metrics": ["return_pct", "marginal_volume_pct"],
                    "dimensions": ["trade_date", "sector_name"],
                    "filters": [
                        {"field": "sector_name", "op": "eq", "value": "创新药"}
                    ],
                    "time_range": {"start": "2026-08-18", "end": "2026-08-18"},
                    "limit": 20,
                },
            ),
        ),
        "scripted",
        "",
    )


def _finish_turn(*, hashes: tuple[str, ...] = ()) -> ModelTurn:
    return ModelTurn(
        json.dumps(
            {
                "status": "completed",
                "draft": "空池后改看成交额前排。",
                "gaps": [],
                "bindings": [
                    {
                        "output_id": "direct_assessment",
                        "evidence_hashes": list(hashes),
                        "gap": "",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        (),
        "scripted",
        "",
    )


def _fallback_requests(events) -> list[dict[str, object]]:
    return [
        event.payload
        for event in events
        if event.kind == "tool_request" and event.payload.get("fallback_query")
    ]


def test_episode_empty_sector_daily_runs_one_amount_fallback() -> None:
    seen: list[object] = []
    frame = _theme_frame()
    model = _ScriptedModel([_empty_sector_turn(), _finish_turn(hashes=("amount-1",))])

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_theme_context(frame),
        registry=_finance_registry(_empty_then_amount_runner(seen)),
    )

    tagged = _fallback_requests(outcome.events)
    assert outcome.status == "completed"
    assert len(seen) == 2
    assert len(tagged) == 1
    assert tagged[0]["as_of"] == "2026-08-18"
    assert tagged[0]["arguments"]["time_range"] == {
        "start": "2026-08-18",
        "end": "2026-08-18",
    }
    order_by = list(tagged[0]["arguments"]["order_by"])
    assert dict(order_by[0]) == {"field": "amount", "direction": "desc"}
    assert tagged[0]["original_arguments"]["filters"]
    after = plan_issue_backfill(
        (
            Issue(
                IssueCode.NUMERIC_UNSUPPORTED,
                "numeric_condition",
                "unsupported numeric condition without bound evidence",
            ),
        ),
        subject_kind="company",
        events=outcome.events,
    )
    assert after is None


def test_episode_market_watch_does_not_fallback() -> None:
    seen: list[object] = []
    frame = _theme_frame(question_type="market_watch")
    model = _ScriptedModel([_empty_sector_turn(), _finish_turn()])

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_theme_context(frame),
        registry=_finance_registry(_empty_then_amount_runner(seen)),
    )

    assert len(seen) == 1
    assert _fallback_requests(outcome.events) == []


def test_episode_prefetch_rows_block_fallback() -> None:
    seen: list[object] = []
    frame = _theme_frame()
    prefetch = (
        AgentEvidence(
            tool="finance_query",
            title="预取双红",
            detail="已有观察",
            source="本地行情",
            source_date="2026-08-18",
            content_hash="prefetch-1",
            observations=(
                StructuredObservation("创新药", "2026-08-18", "amount", 10.0),
            ),
        ),
    )
    model = _ScriptedModel([_empty_sector_turn(), _finish_turn()])

    ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_theme_context(frame),
        registry=_finance_registry(
            _empty_then_amount_runner(seen),
            opening_prefetch=prefetch,
        ),
    )

    assert len(seen) == 1


def test_episode_historical_cutoff_does_not_leak_later_day() -> None:
    seen: list[object] = []
    frame = _theme_frame()
    leak_turn = ModelTurn(
        "",
        (
            ModelToolCall(
                "call-1",
                "finance_query",
                {
                    "dataset": "sector_daily",
                    "metrics": ["return_pct"],
                    "dimensions": ["trade_date", "sector_name"],
                    "filters": [
                        {"field": "sector_name", "op": "eq", "value": "创新药"}
                    ],
                    "time_range": {"start": "2026-08-18", "end": "2026-08-19"},
                    "limit": 20,
                },
            ),
        ),
        "scripted",
        "",
    )
    model = _ScriptedModel([leak_turn, _finish_turn(hashes=("amount-1",))])

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_theme_context(frame),
        registry=_finance_registry(_empty_then_amount_runner(seen)),
    )

    tagged = _fallback_requests(outcome.events)
    assert len(tagged) == 1
    assert tagged[0]["arguments"]["time_range"]["end"] == "2026-08-18"
    assert seen[-1]["time_range"]["end"] == "2026-08-18"
    assert seen[-1]["time_range"]["end"] != "2026-08-19"
