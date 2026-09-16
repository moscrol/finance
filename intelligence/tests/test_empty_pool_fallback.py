"""D3：空池恰好一次换口径。输入加法，不改发布门。"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import date
import json
from types import SimpleNamespace

from intelligence.runtime.agent_episode import ContinuousAgentEpisode
from intelligence.runtime.harness_reference_loop import HarnessReferenceLoop
from intelligence.services.agent_research import AgentEvidence, StructuredObservation
from intelligence.services.agent_runtime import ModelToolCall, ModelTurn
from intelligence.services.empty_pool_fallback import (
    FALLBACK_CALL_ID,
    EmptyToolCall,
    apply_fallback_backfill_mutex,
    fallback_already_attempted,
    prefetch_pool_is_empty,
    propose_empty_pool_fallback,
)
from intelligence.services.research_harness import FallbackCall, FinanceResearchHarness
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
    context = SimpleNamespace(contract=SimpleNamespace(subject_kind="company"))
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


def _undeclared_wire_tool_ids(wire_messages) -> list[str]:
    """线格式上的同一条规则：每条 tool 消息的 tool_call_id 必须被前面某条 assistant.tool_calls 声明。
    没声明的就是 2026-09-09 M3 / M6 让 OpenAI 兼容接口回 400 的那条消息。"""

    declared: set[str] = set()
    orphans: list[str] = []
    for message in wire_messages:
        if message.get("role") == "assistant":
            declared.update(str(call["id"]) for call in message.get("tool_calls") or ())
        elif message.get("role") == "tool" and message.get("tool_call_id") not in declared:
            orphans.append(str(message.get("tool_call_id")))
    return orphans


def _assert_fallback_declared_on_the_wire(model: _ScriptedModel, events) -> None:
    """补的那一枪进入下一次请求前必须有 assistant.tool_calls 声明，声明紧贴它的 tool 消息；
    durable 侧恰好一条 application_tool_call，且落在回退 tool_request 之前。"""

    assert len(model.calls) >= 2
    for request in model.calls:
        assert _undeclared_wire_tool_ids(request["messages"]) == []
    second = model.calls[1]["messages"]
    index = next(
        i
        for i, m in enumerate(second)
        if m.get("role") == "assistant"
        and any(call["id"] == FALLBACK_CALL_ID for call in m.get("tool_calls") or ())
    )
    assert second[index]["content"] == ""
    assert second[index]["tool_calls"][0]["function"]["name"] == "finance_query"
    assert second[index + 1]["role"] == "tool"
    assert second[index + 1]["tool_call_id"] == FALLBACK_CALL_ID
    declarations = [e for e in events if e.kind == "application_tool_call"]
    assert len(declarations) == 1
    assert declarations[0].payload["call_id"] == FALLBACK_CALL_ID
    assert declarations[0].payload["source"] == "empty_pool_fallback"
    fallback_request = next(
        e for e in events if e.kind == "tool_request" and e.payload.get("fallback_query")
    )
    assert declarations[0].sequence < fallback_request.sequence


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
    _assert_fallback_declared_on_the_wire(model, outcome.events)
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


# ── 接缝：fallback_after_empty_batch（2026-09-02-empty-pool-fallback-state-machine.md §4）──
#
# 该不该补、补什么，从 loop 搬进 harness。loop 只递自己拥有的事实（本批结果 / 可派工具集 /
# 事件流 / 阶段），领域从 context / registry / events 读其余。下面四条对应 spec §4 的四条验收。


@dataclass(frozen=True)
class _Outcome:
    """ToolCallOutcome 的最小结构体：接缝只看 (call, status)。"""

    call: ModelToolCall
    status: str


def _plain(value):
    """事件 payload 与 ModelToolCall 参数会被冻成 mappingproxy / tuple；比对前展平。"""

    if isinstance(value, Mapping):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


def _first_batch(*, empty: bool) -> tuple[_Outcome, ...]:
    return (_Outcome(_empty_sector_turn().tool_calls[0], "empty" if empty else "success"),)


def test_default_fallback_seam_equals_direct_proposal() -> None:
    """等价：默认 harness 的产物与直接调 propose_empty_pool_fallback 逐字段相同（四种形状）。"""

    harness = FinanceResearchHarness()
    frame = _theme_frame()
    context = _theme_context(frame)
    registry = _finance_registry(_empty_then_amount_runner([]))
    authorized = frozenset({"finance_query"})

    def direct(*, question_type, prefetch, batch, events=()):
        cutoff = context.information_cutoff
        return propose_empty_pool_fallback(
            question_type=question_type,
            as_of=cutoff.as_of_date.isoformat(),
            cutoff_source=cutoff.source,
            prefetch_empty=prefetch_pool_is_empty(prefetch),
            first_results=tuple(
                EmptyToolCall(
                    name=item.call.name,
                    arguments=dict(item.call.arguments),
                    empty=item.status == "empty",
                )
                for item in batch
            ),
            authorized_tools=authorized,
            already_attempted=fallback_already_attempted(events),
            in_repair=False,
            backfill_plan=None,
        )

    # 1. 空池命中
    hit = harness.fallback_after_empty_batch(
        _first_batch(empty=True),
        context=context,
        registry=registry,
        authorized_tools=authorized,
        events=(),
        in_repair=False,
    )
    expected = direct(question_type=frame.question_type, prefetch=(), batch=_first_batch(empty=True))
    assert hit is not None and expected is not None
    assert hit.call.call_id == expected.call_id == FALLBACK_CALL_ID
    assert hit.call.name == expected.tool == "finance_query"
    # ModelToolCall 把参数冻成 tuple / mappingproxy，展平后逐字段比。
    assert _plain(hit.call.arguments) == _plain(expected.fallback_arguments)
    assert hit.request_extras == expected.request_extras()
    assert hit.request_extras["fallback_query"] is True

    # 2. 首轮有行 → 都不补
    assert (
        harness.fallback_after_empty_batch(
            _first_batch(empty=False),
            context=context,
            registry=registry,
            authorized_tools=authorized,
            events=(),
            in_repair=False,
        )
        is None
        is direct(question_type=frame.question_type, prefetch=(), batch=_first_batch(empty=False))
    )

    # 3. 预取有行 → 都不补
    prefetch = (
        AgentEvidence(
            tool="finance_query",
            title="预取",
            detail="已有观察",
            source="本地行情",
            source_date="2026-08-18",
            content_hash="prefetch-1",
            observations=(StructuredObservation("创新药", "2026-08-18", "amount", 10.0),),
        ),
    )
    assert (
        harness.fallback_after_empty_batch(
            _first_batch(empty=True),
            context=context,
            registry=_finance_registry(_empty_then_amount_runner([]), opening_prefetch=prefetch),
            authorized_tools=authorized,
            events=(),
            in_repair=False,
        )
        is None
        is direct(question_type=frame.question_type, prefetch=prefetch, batch=_first_batch(empty=True))
    )

    # 4. 已经补过一次 / 修复轮 → 都不补
    already = (
        SimpleNamespace(kind="tool_request", payload={"call_id": FALLBACK_CALL_ID, "fallback_query": True}),
    )
    assert (
        harness.fallback_after_empty_batch(
            _first_batch(empty=True),
            context=context,
            registry=registry,
            authorized_tools=authorized,
            events=already,
            in_repair=False,
        )
        is None
    )
    assert (
        harness.fallback_after_empty_batch(
            _first_batch(empty=True),
            context=context,
            registry=registry,
            authorized_tools=authorized,
            events=(),
            in_repair=True,
        )
        is None
    )


class _NeverFallsBack(FinanceResearchHarness):
    def fallback_after_empty_batch(self, batch, **_kwargs):
        del batch
        return None


class _RewritesFallback(FinanceResearchHarness):
    """领域改主意：空池时不排成交额，改排涨幅——模型看到的补查参数随之变。"""

    def fallback_after_empty_batch(self, batch, **kwargs):
        proposal = super().fallback_after_empty_batch(batch, **kwargs)
        if proposal is None:
            return None
        arguments = dict(proposal.call.arguments)
        arguments["order_by"] = [{"field": "return_pct", "direction": "desc"}]
        return FallbackCall(
            call=ModelToolCall(proposal.call.call_id, proposal.call.name, arguments),
            request_extras={**proposal.request_extras, "rewritten": True},
        )


def test_fallback_seam_has_teeth_on_the_episode() -> None:
    """有牙：换 harness，Episode 补不补 / 补什么随之变（看事件与 runner 真收到的参数）。"""

    frame = _theme_frame()

    seen_default: list[object] = []
    default_outcome = ContinuousAgentEpisode(
        _ScriptedModel([_empty_sector_turn(), _finish_turn(hashes=("amount-1",))])
    ).run(
        task_frame=frame,
        context=_theme_context(frame),
        registry=_finance_registry(_empty_then_amount_runner(seen_default)),
    )
    assert len(seen_default) == 2
    assert len(_fallback_requests(default_outcome.events)) == 1

    seen_never: list[object] = []
    never_outcome = ContinuousAgentEpisode(
        _ScriptedModel([_empty_sector_turn(), _finish_turn()]),
        harness=_NeverFallsBack(),
    ).run(
        task_frame=frame,
        context=_theme_context(frame),
        registry=_finance_registry(_empty_then_amount_runner(seen_never)),
    )
    assert len(seen_never) == 1
    assert _fallback_requests(never_outcome.events) == []

    seen_rewritten: list[object] = []
    rewritten_outcome = ContinuousAgentEpisode(
        _ScriptedModel([_empty_sector_turn(), _finish_turn()]),
        harness=_RewritesFallback(),
    ).run(
        task_frame=frame,
        context=_theme_context(frame),
        registry=_finance_registry(_empty_then_amount_runner(seen_rewritten)),
    )
    assert len(seen_rewritten) == 2
    assert seen_rewritten[-1]["order_by"] == [{"field": "return_pct", "direction": "desc"}]
    tagged = _fallback_requests(rewritten_outcome.events)
    assert len(tagged) == 1 and tagged[0]["rewritten"] is True


def _strip_runtime_budget(message: dict[str, object]) -> dict[str, object]:
    if message.get("role") != "tool":
        return message
    payload = json.loads(str(message["content"]))
    if isinstance(payload, dict) and "runtime_budget" in payload:
        payload = dict(payload)
        payload.pop("runtime_budget")
        return {**message, "content": json.dumps(payload, ensure_ascii=False)}
    return message


def test_reference_loop_runs_the_same_fallback_as_the_episode() -> None:
    """第二条 loop（spec §4 第 4 条）：同一空池脚本下，两条 loop 补的那一枪、模型看到的消息、
    outcome 一致。参考 loop 文首「无空池回退」那条差从此消掉。"""

    frame = _theme_frame()
    script = [_empty_sector_turn(), _finish_turn(hashes=("amount-1",))]

    seen_episode: list[object] = []
    episode_model = _ScriptedModel(list(script))
    episode = ContinuousAgentEpisode(episode_model).run(
        task_frame=frame,
        context=_theme_context(frame),
        registry=_finance_registry(_empty_then_amount_runner(seen_episode)),
    )

    seen_reference: list[object] = []
    reference_model = _ScriptedModel(list(script))
    reference = HarnessReferenceLoop(reference_model).run(
        task_frame=frame,
        context=_theme_context(frame),
        registry=_finance_registry(_empty_then_amount_runner(seen_reference)),
    )

    # runner 真收到的两次参数（原查询 + 补查）逐字段相同。
    assert seen_episode == seen_reference and len(seen_reference) == 2
    # 补查那条 tool_request 的领域投影（调用身份 + 三个回退标记）相同；Episode 另盖的
    # task_frame_hash / at / 派发时钟（batch_grant_asked 等）是底座的账，不在比对面里。
    domain_keys = ("call_id", "name", "arguments", "fallback_query", "original_arguments", "as_of")

    def tagged(outcome):
        return [
            {k: _plain(p).get(k) for k in domain_keys}
            for p in _fallback_requests(outcome.events)
        ]

    assert tagged(episode) == tagged(reference)
    assert tagged(reference)[0]["call_id"] == FALLBACK_CALL_ID
    assert tagged(reference)[0]["fallback_query"] is True
    # 两条 loop 都先声明再派发：下一次请求里没有孤儿 tool 消息。
    _assert_fallback_declared_on_the_wire(episode_model, episode.events)
    _assert_fallback_declared_on_the_wire(reference_model, reference.events)
    # 模型看到的消息一致（只差 Episode 的 runtime_budget 键）。
    assert len(episode_model.calls) == len(reference_model.calls) == 2
    for a, b in zip(episode_model.calls, reference_model.calls):
        assert a["tools"] == b["tools"]
        assert [_strip_runtime_budget(m) for m in a["messages"]] == [
            _strip_runtime_budget(m) for m in b["messages"]
        ]
    assert (episode.status, episode.draft, episode.stop_reason) == (
        reference.status,
        reference.draft,
        reference.stop_reason,
    )
    assert episode.usage.tool_calls == reference.usage.tool_calls == 2
    assert [b.to_dict() for b in episode.bindings] == [b.to_dict() for b in reference.bindings]
