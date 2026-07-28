from __future__ import annotations

from types import SimpleNamespace
from typing import Any
import asyncio
from dataclasses import asdict, replace
import json
import os
from pathlib import Path

import pytest

import intelligence.services.openai_agents_runtime as sdk_runtime_module

from intelligence.services.agent_research import AgentEvidence, AgentToolContext
from intelligence.services.repair_coordinator import CoverageDelta, RepairGoal
from intelligence.services.evidence_capabilities import (
    EvidencePlan,
    EvidenceRequirement,
)
from intelligence.services.episode_verifier import verify_episode_outcome
from intelligence.services.openai_agents_runtime import (
    AgentsSdkRequest,
    AgentsSdkResult,
    AgentsSdkTool,
    OpenAIAgentsRuntime,
    build_agents_model_settings,
    build_glm_sdk_model,
    build_glm_sdk_model_factory,
    build_gpt_sdk_model,
    build_gpt_sdk_model_factory,
    _run_openai_agents_sdk,
)
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import (
    InMemoryRootBudgetLedger,
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


def _frame() -> TaskFrame:
    return TaskFrame(
        raw_question="目前市场的主线是什么",
        user_goal="判断当前A股市场主线及依据",
        question_type="market_watch",
        subject="A股市场",
        subject_kind="market_pattern",
        market_scope="A股",
        timeframe="最近交易日",
        required_outputs=("direct_assessment",),
        assumptions=("按A股市场理解",),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="current_a_share_market",
        confidence=0.95,
    )


def _context(
    frame: TaskFrame,
    *,
    max_steps: int = 2,
    allowed_capabilities: tuple[str, ...] = ("mainline_context",),
    timeout: float = 30.0,
    synthesis_reserve: float = 0.0,
) -> ResearchRunContext:
    contract = ResearchTaskContract(
        task_id="sdk-runtime-test",
        question=frame.raw_question,
        subject=frame.subject,
        subject_kind=frame.subject_kind,
        question_type=frame.question_type,
        required_outputs=(
            RequiredOutput(
                "direct_assessment",
                "直接判断",
                ("mainline_context",),
                True,
            ),
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
        deadline=ResearchDeadline.from_timeout(
            timeout,
            synthesis_reserve=synthesis_reserve,
        ),
        policy=ResearchPolicy("quick", max_steps, timeout, synthesis_reserve),
        trace_parent_id="sdk-runtime-test",
        today="2026-07-25",
        latest_data_date="2026-07-24",
    )


def _registry(calls: list[str]) -> ResearchToolRegistry:
    def mainline_runner(query: str, _context: AgentToolContext):
        calls.append(query)
        evidence = AgentEvidence(
            tool="mainline_context",
            title="同日主线结构",
            detail="截至2026-07-24，医药是韧性核心，电力是轮动支线。",
            source="本地正式日报",
            source_date="2026-07-24",
            evidence_tier="L4",
            content_hash="mainline-hash",
        )
        return (
            [evidence],
            "医药是韧性核心，电力是轮动支线。",
            ProviderTrace(
                provider="test:mainline",
                capability="mainline_context",
                status="success",
                source_trade_date="2026-07-24",
                result_count=1,
            ),
        )

    def forbidden_runner(query: str, _context: AgentToolContext):
        calls.append(f"forbidden:{query}")
        return ([], "", None)

    def news_runner(query: str, _context: AgentToolContext):
        calls.append(f"news:{query}")
        return ([], "没有新增新闻", None)

    return ResearchToolRegistry(
        (
            ToolSpec(
                name="mainline_context",
                capability="mainline_context",
                description="同日主线与板块结构",
                cost="local",
                freshness="current",
                runner=mainline_runner,
                query_scope="episode",
            ),
            ToolSpec(
                name="forbidden_news",
                capability="news_search",
                description="未授权新闻",
                cost="network",
                freshness="current",
                runner=forbidden_runner,
            ),
            ToolSpec(
                name="market_news",
                capability="market_news",
                description="市场新闻",
                cost="network",
                freshness="current",
                runner=news_runner,
            ),
        )
    )


class SuccessfulFakeSdkRunner:
    def __init__(self) -> None:
        self.tool_names: set[str] = set()

    def __call__(self, request: AgentsSdkRequest) -> AgentsSdkResult:
        self.tool_names = {tool.name for tool in request.tools}
        observation = request.tools[0].invoke("A股 当前主线")
        finish = {
            "status": "completed",
            "draft": "截至2026-07-24，医药是韧性核心，电力是轮动支线。",
            "gaps": [],
            "bindings": [
                {
                    "output_id": "direct_assessment",
                    "evidence_hashes": observation["evidence_hashes"],
                    "gap": "",
                }
            ],
        }
        return AgentsSdkResult(
            final_output=json.dumps(finish, ensure_ascii=False),
            llm_calls=2,
            input_tokens=1200,
            output_tokens=240,
        )


def test_sdk_progress_sink_observes_tool_events_before_runner_returns() -> None:
    observed = []

    def progress_aware_runner(request: AgentsSdkRequest) -> AgentsSdkResult:
        observation = request.tools[0].invoke("A股 当前主线")
        assert [event.kind for event in observed] == [
            "task",
            "tool_request",
            "tool_result",
        ]
        finish = {
            "status": "completed",
            "draft": "截至2026-07-24，医药是韧性核心，电力是轮动支线。",
            "gaps": [],
            "bindings": [
                {
                    "output_id": "direct_assessment",
                    "evidence_hashes": observation["evidence_hashes"],
                    "gap": "",
                }
            ],
        }
        return AgentsSdkResult(
            json.dumps(finish, ensure_ascii=False),
            1,
        )

    outcome = OpenAIAgentsRuntime(
        runner=progress_aware_runner,
        backend="sdk_gpt",
        model_name="gpt-5.6-sol",
        event_sink=observed.append,
    ).run(
        task_frame=_frame(),
        context=_context(_frame()),
        registry=_registry([]),
    )

    assert outcome.status == "completed"
    assert [event.kind for event in observed] == [
        "task",
        "tool_request",
        "tool_result",
        "runtime_result",
        "finish",
    ]


def test_sdk_progress_sink_suppresses_events_after_cancellation() -> None:
    observed = []
    cancelled = {"value": False}

    def cancelled_after_research(request: AgentsSdkRequest) -> AgentsSdkResult:
        observation = request.tools[0].invoke("A股 当前主线")
        cancelled["value"] = True
        return AgentsSdkResult(
            json.dumps(
                {
                    "status": "completed",
                    "draft": "截至2026-07-24，医药是韧性核心。",
                    "gaps": [],
                    "bindings": [
                        {
                            "output_id": "direct_assessment",
                            "evidence_hashes": observation["evidence_hashes"],
                            "gap": "",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            1,
        )

    outcome = OpenAIAgentsRuntime(
        runner=cancelled_after_research,
        backend="sdk_gpt",
        model_name="gpt-5.6-sol",
        is_cancelled=lambda: cancelled["value"],
        event_sink=observed.append,
    ).run(
        task_frame=_frame(),
        context=_context(_frame()),
        registry=_registry([]),
    )

    assert outcome.status == "completed"
    assert [event.kind for event in observed] == [
        "task",
        "tool_request",
        "tool_result",
    ]


def test_sdk_tool_result_returns_only_evidence_new_to_the_episode() -> None:
    evidence = AgentEvidence(
        tool="news_search",
        title="同一篇市场收评",
        detail="2026-07-24 市场缩量回撤",
        source="https://example.test/market-review",
        source_date="2026-07-24",
        content_hash="same-news-hash",
        independent_key="market-review",
    )
    registry = ResearchToolRegistry(
        (
            ToolSpec(
                name="news_search",
                capability="news_search",
                description="市场新闻",
                cost="network",
                freshness="current",
                runner=lambda _query, _context: (
                    [evidence],
                    "同一篇市场收评",
                    ProviderTrace("test:news", "news_search", "success"),
                ),
            ),
        )
    )

    def repeated_evidence_runner(request: AgentsSdkRequest) -> AgentsSdkResult:
        tool = request.tools[0]
        first = tool.invoke("A股 7月24日 下跌原因")
        second = tool.invoke("换一种表述搜索 7月24日 A股回撤")
        assert first["status"] == "success"
        assert first["evidence_hashes"] == ["same-news-hash"]
        assert second["status"] == "duplicate_evidence"
        assert second["evidence"] == []
        assert second["evidence_hashes"] == []
        return AgentsSdkResult(
            json.dumps(
                {
                    "status": "completed",
                    "draft": "7月24日出现缩量回撤。",
                    "gaps": [],
                    "bindings": [
                        {
                            "output_id": "direct_assessment",
                            "evidence_hashes": ["same-news-hash"],
                            "gap": "",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            1,
        )

    frame = _frame()
    outcome = OpenAIAgentsRuntime(
        runner=repeated_evidence_runner,
        backend="sdk_gpt",
        model_name="gpt-5.6-sol",
    ).run(
        task_frame=frame,
        context=_context(
            frame,
            allowed_capabilities=("news_search",),
        ),
        registry=registry,
    )

    assert outcome.status == "completed"
    assert [item.content_hash for item in outcome.evidence] == ["same-news-hash"]


def test_sdk_tool_results_publish_mandatory_evidence_completion() -> None:
    frame = _frame()
    base_context = _context(
        frame,
        allowed_capabilities=("market_data", "financial_data"),
    )
    context = replace(
        base_context,
        contract=replace(
            base_context.contract,
            required_outputs=(
                RequiredOutput(
                    "direct_assessment",
                    "直接判断",
                    ("market_data", "financial_data"),
                    True,
                ),
            ),
            evidence_plan=EvidencePlan(
                profile="company_valuation",
                requirements=(
                    EvidenceRequirement(
                        "MARKET_DATA",
                        "market_data",
                        True,
                        reason="估值锚",
                    ),
                    EvidenceRequirement(
                        "FINANCIAL_DATA",
                        "financial_data",
                        True,
                        reason="盈利基础",
                    ),
                ),
            ),
        ),
    )

    def evidence_runner(name: str, content_hash: str):
        def run(_query: str, _context: AgentToolContext):
            evidence = AgentEvidence(
                tool=name,
                title=f"{name} evidence",
                detail=f"{name} direct evidence",
                source="local fixture",
                source_date="2026-07-24",
                content_hash=content_hash,
            )
            return (
                [evidence],
                evidence.detail,
                ProviderTrace(f"test:{name}", name, "success"),
            )

        return run

    registry = ResearchToolRegistry(
        (
            ToolSpec(
                name="market_data",
                capability="market_data",
                description="估值锚",
                cost="local",
                freshness="current",
                runner=evidence_runner("market_data", "market-evidence"),
            ),
            ToolSpec(
                name="financial_data",
                capability="financial_data",
                description="财务证据",
                cost="local",
                freshness="current",
                runner=evidence_runner("financial_data", "financial-evidence"),
            ),
        )
    )

    def mandatory_runner(request: AgentsSdkRequest) -> AgentsSdkResult:
        tools = {tool.name: tool for tool in request.tools}
        market = tools["market_data"].invoke("瑞华泰 当前估值")
        assert market["mandatory_missing_capabilities"] == ["financial_data"]
        assert "mandatory_evidence_complete" not in market
        financial = tools["financial_data"].invoke("瑞华泰 财务基础")
        assert financial["mandatory_missing_capabilities"] == []
        assert financial["mandatory_evidence_complete"] is True
        assert "绑定" in str(financial["finish_hint"])
        return AgentsSdkResult(
            json.dumps(
                {
                    "status": "completed",
                    "draft": "瑞华泰估值需要同时结合市值锚与盈利基础。",
                    "gaps": [],
                    "bindings": [
                        {
                            "output_id": "direct_assessment",
                            "evidence_hashes": [
                                *market["evidence_hashes"],
                                *financial["evidence_hashes"],
                            ],
                            "gap": "",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            1,
        )

    outcome = OpenAIAgentsRuntime(
        runner=mandatory_runner,
        backend="sdk_gpt",
        model_name="gpt-5.6-sol",
    ).run(task_frame=frame, context=context, registry=registry)

    assert outcome.status == "completed"
    assert {item.tool for item in outcome.evidence} == {
        "market_data",
        "financial_data",
    }


def test_sdk_runtime_resumes_with_same_provider_continuation() -> None:
    frame = _frame()
    context = _context(frame)
    private_marker = "PRIVATE_PROVIDER_HISTORY_MUST_NOT_LEAK"

    class OpaqueContinuation:
        def __repr__(self) -> str:
            return private_marker

    initial_continuation = OpaqueContinuation()
    requests: list[AgentsSdkRequest] = []
    resumed_tool_results: list[dict[str, object]] = []
    observed = []

    def resumable_runner(request: AgentsSdkRequest) -> AgentsSdkResult:
        requests.append(request)
        if len(requests) == 1:
            observation = request.tools[0].invoke("A股 当前主线")
            finish = {
                "status": "partial",
                "draft": "截至2026-07-24，医药是韧性核心，措辞仍需收束。",
                "gaps": ["直接判断措辞仍需收束"],
                "bindings": [
                    {
                        "output_id": "direct_assessment",
                        "evidence_hashes": observation["evidence_hashes"],
                        "gap": "",
                    }
                ],
            }
            return AgentsSdkResult(
                json.dumps(finish, ensure_ascii=False),
                2,
                input_tokens=100,
                output_tokens=20,
                continuation_input=initial_continuation,
            )
        assert request._continuation_input is initial_continuation
        assert [event.kind for event in observed[-2:]] == [
            "repair_goal",
            "repair_reentry",
        ]
        tools = {tool.name: tool for tool in request.tools}
        resumed_tool_results.extend(
            (
                tools["mainline_context"].invoke("A股 当前主线"),
                tools["mainline_context"].invoke("A股 当前主线 新措辞"),
            )
        )
        finish = {
            "status": "completed",
            "draft": "截至2026-07-24，医药是韧性核心，电力是轮动支线。",
            "gaps": [],
            "bindings": [
                {
                    "output_id": "direct_assessment",
                    "evidence_hashes": ["mainline-hash"],
                    "gap": "",
                }
            ],
        }
        return AgentsSdkResult(
            json.dumps(finish, ensure_ascii=False),
            1,
            input_tokens=30,
            output_tokens=10,
            continuation_input=object(),
        )

    runtime = OpenAIAgentsRuntime(
        runner=resumable_runner,
        backend="sdk_glm",
        model_name="glm-5.2",
        event_sink=observed.append,
    )
    session = runtime.start(
        frame,
        context=context,
        registry=_registry([]),
    )

    def forbid_one_shot_run(**_kwargs):
        raise AssertionError("resume must not restart the one-shot runtime")

    runtime.run = forbid_one_shot_run  # type: ignore[method-assign]
    previous = session.outcome
    repaired = session.resume(
        RepairGoal(
            episode_id=context.contract.task_id,
            repair_goal_id="repair-sdk-runtime-1",
            cycle=1,
            missing_answer_elements=("direct_assessment",),
            unsupported_claims=(),
            missing_evidence_modes=(),
            attempted_actions=("mainline_context:A股 当前主线",),
            evidence_progress=CoverageDelta(1, 1, 0),
            remaining_calls=1,
            remaining_seconds=10.0,
        )
    )

    assert session.episode_id == context.contract.task_id
    assert repaired.task_frame_hash == frame.task_frame_hash
    assert repaired.events[: len(previous.events)] == previous.events
    appended = repaired.events[len(previous.events) :]
    assert [event.sequence for event in repaired.events] == list(
        range(1, len(repaired.events) + 1)
    )
    assert appended[0].kind == "repair_goal"
    assert appended[0].payload["repair_goal_id"] == "repair-sdk-runtime-1"
    assert appended[0].payload["cycle"] == 1
    assert any(event.kind == "model_turn" for event in appended)
    assert tuple(repaired.evidence[: len(previous.evidence)]) == previous.evidence
    assert tuple(repaired.traces[: len(previous.traces)]) == previous.traces
    assert tuple(repaired.gaps[: len(previous.gaps)]) == previous.gaps
    assert repaired.usage.llm_calls == 3
    assert repaired.usage.input_tokens == 130
    assert repaired.usage.output_tokens == 30
    assert len(requests) == 2
    repair_input = json.loads(requests[1].input)
    assert repair_input["repair_goal_id"] == "repair-sdk-runtime-1"
    assert repair_input["cycle"] == 1
    assert requests[1].max_turns == 2
    assert 0.0 < requests[1].timeout <= 10.0
    assert [item["error"] for item in resumed_tool_results] == [
        "duplicate_query",
        "episode_snapshot_already_collected",
    ]
    assert private_marker not in repr(requests[1])
    assert private_marker not in repr(vars(requests[1]))
    assert private_marker not in json.dumps(vars(requests[1]), default=str)
    assert private_marker not in repr(session)
    assert private_marker not in json.dumps(repaired.to_dict(), ensure_ascii=False)
    assert [event.kind for event in observed] == [
        event.kind for event in repaired.events
    ]


def test_sdk_episode_debits_one_shared_root_tool_budget_across_resume() -> None:
    frame = _frame()

    class MutableResearchDeadline:
        synthesis_reserve = 0.0
        stage_limit = 30.0

        @property
        def expired(self) -> bool:
            return False

        def remaining(self) -> float:
            return 30.0

        def stage_timeout(self, configured_limit: float) -> float:
            return min(configured_limit, self.stage_limit)

        def bounded_stage(self, configured_limit: float) -> ResearchDeadline:
            return ResearchDeadline.from_timeout(
                self.stage_timeout(configured_limit)
            )

    deadline = MutableResearchDeadline()
    context = replace(
        _context(
            frame,
            max_steps=2,
            allowed_capabilities=("mainline_context", "market_news"),
        ),
        root_budget=InMemoryRootBudgetLedger(
            episode_id="sdk-runtime-test",
            initial_calls=2,
            hard_calls_cap=2,
            initial_seconds=30.0,
            hard_seconds_cap=30.0,
        ),
        deadline=deadline,
    )
    continuation = object()
    observations: list[dict[str, object]] = []

    def budgeted_runner(request: AgentsSdkRequest) -> AgentsSdkResult:
        tools = {tool.name: tool for tool in request.tools}
        if not observations:
            observation = tools["mainline_context"].invoke("A股 当前主线")
            observations.append(observation)
            status = "partial"
        else:
            assert request.max_turns == 2
            assert 0.0 < request.timeout <= 10.0
            assert request.tool_timeout is not None
            assert 0.0 < request.tool_timeout <= 0.05
            observation = tools["market_news"].invoke("A股 主线反证")
            observations.append(observation)
            status = "completed"
        return AgentsSdkResult(
            json.dumps(
                {
                    "status": status,
                    "draft": "截至2026-07-24，医药是韧性核心。",
                    "gaps": [] if status == "completed" else ["缺少反证"],
                    "bindings": [
                        {
                            "output_id": "direct_assessment",
                            "evidence_hashes": ["mainline-hash"],
                            "gap": "",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            1,
            continuation_input=continuation,
        )

    session = OpenAIAgentsRuntime(
        runner=budgeted_runner,
        backend="sdk_glm",
        model_name="glm-5.2",
    ).start(frame, context=context, registry=_registry([]))

    assert context.root_budget is not None
    assert context.root_budget.remaining_calls == 1
    deadline.stage_limit = 0.05
    session.resume(
        RepairGoal(
            episode_id="sdk-runtime-test",
            repair_goal_id="repair-shared-budget-1",
            cycle=1,
            missing_answer_elements=("counterpoint",),
            unsupported_claims=(),
            missing_evidence_modes=("market_news",),
            attempted_actions=("mainline_context:A股 当前主线",),
            evidence_progress=CoverageDelta(1, 1, 0),
            remaining_calls=5,
            remaining_seconds=10.0,
        )
    )

    assert context.root_budget.remaining_calls == 0
    assert [item["tool"] for item in observations] == [
        "mainline_context",
        "market_news",
    ]


@pytest.mark.parametrize("use_explicit_model_settings", (False, True))
def test_sdk_resume_keeps_tools_closed_after_original_research_window(
    use_explicit_model_settings: bool,
) -> None:
    frame = _frame()
    explicit_model_settings = object() if use_explicit_model_settings else None

    class ToggleDeadline:
        synthesis_reserve = 0.0
        closed = False

        @property
        def expired(self) -> bool:
            return False

        def remaining(self) -> float:
            return 2.0 if self.closed else 30.0

        def stage_timeout(self, configured_limit: float) -> float:
            return 0.0 if self.closed else configured_limit

        def bounded_stage(self, configured_limit: float) -> ResearchDeadline:
            return ResearchDeadline.from_timeout(
                self.stage_timeout(configured_limit)
            )

    deadline = ToggleDeadline()
    root_budget = InMemoryRootBudgetLedger(
        episode_id="sdk-runtime-test",
        initial_calls=2,
        hard_calls_cap=2,
        initial_seconds=2.0,
        hard_seconds_cap=2.0,
    )
    context = replace(
        _context(frame, max_steps=2),
        deadline=deadline,
        root_budget=root_budget,
    )
    requests: list[AgentsSdkRequest] = []
    continuation = object()

    def wording_repair_runner(request: AgentsSdkRequest) -> AgentsSdkResult:
        requests.append(request)
        if len(requests) == 1:
            observation = request.tools[0].invoke("A股 当前主线")
            status = "partial"
            gaps = ["措辞需要修复"]
            hashes = observation["evidence_hashes"]
        else:
            assert request.tools == ()
            assert request.max_turns == 1
            assert 0.0 < request.timeout <= 2.0
            if explicit_model_settings is not None:
                assert request.model_settings is explicit_model_settings
            else:
                assert request.model_settings.reasoning.effort == "low"
                assert request.model_settings.verbosity == "medium"
            status = "completed"
            gaps = []
            hashes = ["mainline-hash"]
        return AgentsSdkResult(
            json.dumps(
                {
                    "status": status,
                    "draft": "截至2026-07-24，医药是韧性核心。",
                    "gaps": gaps,
                    "bindings": [
                        {
                            "output_id": "direct_assessment",
                            "evidence_hashes": hashes,
                            "gap": "",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            1,
            continuation_input=continuation,
        )

    session = OpenAIAgentsRuntime(
        runner=wording_repair_runner,
        backend="sdk_gpt",
        model_name="gpt-5.6-sol",
        model_settings=explicit_model_settings,
    ).start(frame, context=context, registry=_registry([]))
    deadline.closed = True
    repaired = session.resume(
        RepairGoal(
            episode_id="sdk-runtime-test",
            repair_goal_id="repair-closed-research-1",
            cycle=1,
            missing_answer_elements=("direct_assessment",),
            unsupported_claims=(),
            missing_evidence_modes=(),
            attempted_actions=("mainline_context:A股 当前主线",),
            evidence_progress=CoverageDelta(1, 1, 0),
            remaining_calls=1,
            remaining_seconds=10.0,
        )
    )

    assert repaired.status == "completed"
    assert root_budget.remaining_calls == 1


def test_sdk_runtime_exposes_only_authorized_tools_and_returns_outcome() -> None:
    frame = _frame()
    calls: list[str] = []
    fake = SuccessfulFakeSdkRunner()

    outcome = OpenAIAgentsRuntime(
        runner=fake,
        backend="sdk_glm",
        model_name="glm-5.2",
    ).run(
        task_frame=frame,
        context=_context(frame),
        registry=_registry(calls),
    )

    assert fake.tool_names == {"mainline_context"}
    assert outcome.status == "completed"
    assert outcome.bindings[0].evidence_hashes == ("mainline-hash",)
    assert outcome.usage.llm_calls == 2
    assert outcome.usage.tool_calls == 1
    assert calls == ["A股 当前主线"]


def test_sdk_runtime_preserves_typed_tool_schema_and_arguments() -> None:
    frame = _frame()
    received: list[dict[str, object]] = []
    typed_schema = {
        "type": "object",
        "properties": {
            "dataset": {"type": "string"},
            "limit": {"type": "integer"},
        },
        "required": ["dataset", "limit"],
        "additionalProperties": False,
    }

    def runner(value: object, _context: AgentToolContext):
        assert isinstance(value, dict)
        received.append(value)
        evidence = AgentEvidence(
            tool="finance_query",
            title="市场结构",
            detail="截至2026-07-24，上证指数当日上涨1.2%。",
            source="本地结构化市场数据",
            source_date="2026-07-24",
            evidence_tier="L4_structured",
            content_hash="finance-query-hash",
        )
        return (
            [evidence],
            evidence.detail,
            ProviderTrace(
                provider="test:finance_query",
                capability="finance_query",
                status="success",
                result_count=1,
            ),
        )

    registry = ResearchToolRegistry(
        (
            ToolSpec(
                name="finance_query",
                capability="finance_query",
                description="结构化金融查询",
                cost="local",
                freshness="current",
                runner=runner,
                parameters=typed_schema,
                parse_arguments=lambda arguments: (
                    dict(arguments),
                    str(arguments["dataset"]),
                ),
            ),
        )
    )
    captured_schema: dict[str, object] = {}

    def sdk_runner(request: AgentsSdkRequest) -> AgentsSdkResult:
        tool = request.tools[0]
        captured_schema.update(tool.parameters)
        observation = tool.invoke({"dataset": "market_daily", "limit": 5})
        return AgentsSdkResult(
            final_output=json.dumps(
                {
                    "status": "completed",
                    "draft": "截至2026-07-24，上证指数当日上涨1.2%。",
                    "gaps": [],
                    "bindings": [
                        {
                            "output_id": "direct_assessment",
                            "evidence_hashes": observation["evidence_hashes"],
                            "gap": "",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            llm_calls=2,
        )

    OpenAIAgentsRuntime(
        runner=sdk_runner,
        backend="sdk_glm",
        model_name="glm-5.2",
    ).run(
        task_frame=frame,
        context=_context(
            frame,
            allowed_capabilities=("finance_query",),
        ),
        registry=registry,
    )

    assert captured_schema == typed_schema
    assert received == [{"dataset": "market_daily", "limit": 5}]


def test_sdk_runtime_reserves_part_of_synthesis_budget_for_verifier() -> None:
    frame = _frame()
    captured: list[float] = []
    successful = SuccessfulFakeSdkRunner()

    def capture_timeout(request: AgentsSdkRequest) -> AgentsSdkResult:
        captured.append(request.timeout)
        return successful(request)

    outcome = OpenAIAgentsRuntime(
        runner=capture_timeout,
        backend="sdk_gpt",
        model_name="gpt-5.6-sol",
    ).run(
        task_frame=frame,
        context=_context(frame, timeout=30.0, synthesis_reserve=10.0),
        registry=_registry([]),
    )

    assert outcome.status == "completed"
    assert len(captured) == 1
    assert 26.0 <= captured[0] < 27.0


def test_sdk_stage_close_instructs_finalization_without_public_gap() -> None:
    frame = _frame()
    observations: list[dict[str, object]] = []

    def stage_closed_runner(request: AgentsSdkRequest) -> AgentsSdkResult:
        observations.append(request.tools[0].invoke("A股 当前主线"))
        finish = {
            "status": "partial",
            "draft": "基于当前可用信息，暂不确认主线。",
            "gaps": ["仍缺少同日主线证据"],
            "bindings": [
                {
                    "output_id": "direct_assessment",
                    "evidence_hashes": [],
                    "gap": "仍缺少同日主线证据",
                }
            ],
        }
        return AgentsSdkResult(json.dumps(finish, ensure_ascii=False), 1)

    outcome = OpenAIAgentsRuntime(
        runner=stage_closed_runner,
        backend="sdk_gpt",
        model_name="gpt-5.6-sol",
    ).run(
        task_frame=frame,
        context=_context(frame, timeout=10.0, synthesis_reserve=10.0),
        registry=_registry([]),
    )

    assert observations == [
        {
            "status": "closed",
            "tool": "mainline_context",
            "error": "research_stage_closed",
            "instruction": "研究取证阶段已结束，请使用已有信息完成终止回答。",
        }
    ]
    assert "research_stage_closed" not in outcome.gaps
    assert outcome.status == "partial"


def test_sdk_delivery_reserve_closes_optional_tools_without_public_gap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame = _frame()

    class FakeClock:
        def __init__(self) -> None:
            self.value = 100.0

        def __call__(self) -> float:
            return self.value

        def advance(self, seconds: float) -> None:
            self.value += seconds

    clock = FakeClock()
    monkeypatch.setattr(sdk_runtime_module, "monotonic", clock)
    observations: list[dict[str, object]] = []

    def delivery_runner(request: AgentsSdkRequest) -> AgentsSdkResult:
        tools = {tool.name: tool for tool in request.tools}
        evidence = tools["mainline_context"].invoke("A股 当前主线")
        clock.advance(46.0)
        optional = tools["market_news"].invoke("A股 主线补充消息")
        observations.append(optional)
        assert optional["status"] == "closed"
        assert optional["error"] == "research_stage_closed"
        return AgentsSdkResult(
            json.dumps(
                {
                    "status": "completed",
                    "draft": "截至2026-07-24，医药是韧性核心。",
                    "gaps": [],
                    "bindings": [
                        {
                            "output_id": "direct_assessment",
                            "evidence_hashes": evidence["evidence_hashes"],
                            "gap": "",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            1,
        )

    outcome = OpenAIAgentsRuntime(
        runner=delivery_runner,
        backend="sdk_gpt",
        model_name="gpt-5.6-sol",
    ).run(
        task_frame=frame,
        context=_context(
            frame,
            max_steps=3,
            allowed_capabilities=("mainline_context", "market_news"),
            timeout=60.0,
        ),
        registry=_registry([]),
    )

    assert observations[0]["instruction"] == (
        "研究取证阶段已结束，请使用已有信息完成终止回答。"
    )
    assert outcome.status == "completed"
    assert "research_stage_closed" not in outcome.gaps


def test_sdk_runtime_turns_tool_budget_exhaustion_into_a_partial_gap() -> None:
    frame = _frame()
    tool_errors: list[str] = []

    def over_budget_runner(request: AgentsSdkRequest) -> AgentsSdkResult:
        tools = {tool.name: tool for tool in request.tools}
        first = tools["mainline_context"].invoke("A股 当前主线")
        second = tools["market_news"].invoke("A股 主线新闻")
        tool_errors.append(str(second.get("error") or ""))
        finish = {
            "status": "completed",
            "draft": "截至2026-07-24，医药是韧性核心。",
            "gaps": [],
            "bindings": [
                {
                    "output_id": "direct_assessment",
                    "evidence_hashes": first["evidence_hashes"],
                    "gap": "",
                }
            ],
        }
        return AgentsSdkResult(json.dumps(finish, ensure_ascii=False), 2)

    outcome = OpenAIAgentsRuntime(
        runner=over_budget_runner,
        backend="sdk_glm",
        model_name="glm-5.2",
    ).run(
        task_frame=frame,
        context=_context(
            frame,
            max_steps=1,
            allowed_capabilities=("mainline_context", "market_news"),
        ),
        registry=_registry([]),
    )

    assert tool_errors == ["tool_budget_exhausted"]
    assert outcome.status == "partial"
    assert "tool_budget_exhausted" in outcome.gaps
    assert outcome.usage.tool_calls == 1


def test_sdk_provider_factories_preserve_endpoint_specific_settings() -> None:
    glm_model = build_glm_sdk_model(
        api_key="test-key",
        base_url="https://open.bigmodel.cn/api/coding/paas/v4",
        model="glm-5.2",
        timeout=12.0,
    )
    glm_settings = build_agents_model_settings("sdk_glm")
    gpt_model = build_gpt_sdk_model("gpt-5.6-sol")
    gpt_settings = build_agents_model_settings("sdk_gpt")

    assert type(glm_model).__name__ == "OpenAIChatCompletionsModel"
    assert gpt_model == "gpt-5.6-sol"
    assert glm_settings.temperature == 0.0
    assert glm_settings.parallel_tool_calls is False
    assert glm_settings.extra_body == {"thinking": {"type": "disabled"}}
    assert gpt_settings.parallel_tool_calls is False
    assert gpt_settings.reasoning.effort == "high"
    assert gpt_settings.verbosity == "medium"
    assert gpt_settings.store is False


def test_gpt_sdk_factory_builds_explicit_responses_client() -> None:
    model_factory = build_gpt_sdk_model_factory(
        api_key="session-secret",
        base_url="http://localhost:57244/v1",
        model="gpt-5.6-sol",
        timeout=12.0,
    )

    model, close = model_factory()

    assert type(model).__name__ == "OpenAIResponsesModel"
    assert str(model._client.base_url) == "http://localhost:57244/v1/"
    assert callable(close)
    asyncio.run(close())


def test_default_sdk_runner_uses_local_tools_and_disables_trace_export(
    monkeypatch,
) -> None:
    from agents import Runner

    frame = _frame()
    seen: dict[str, Any] = {}
    model = "fake-sdk-model"
    model_settings = build_agents_model_settings("sdk_glm")
    close_calls = 0

    async def close_model() -> None:
        nonlocal close_calls
        close_calls += 1

    async def fake_run(
        agent,
        user_input,
        *,
        context,
        max_turns,
        run_config,
        **_kwargs,
    ):
        seen.update(
            {
                "agent": agent,
                "input": user_input,
                "context": context,
                "max_turns": max_turns,
                "run_config": run_config,
            }
        )
        raw = await agent.tools[0].on_invoke_tool(
            None,
            json.dumps({"query": "A股 当前主线"}, ensure_ascii=False),
        )
        observation = json.loads(raw)
        finish = {
            "status": "completed",
            "draft": "截至2026-07-24，医药是韧性核心。",
            "gaps": [],
            "bindings": [
                {
                    "output_id": "direct_assessment",
                    "evidence_hashes": observation["evidence_hashes"],
                    "gap": "",
                }
            ],
        }
        usage = SimpleNamespace(requests=2, input_tokens=900, output_tokens=180)
        return SimpleNamespace(
            final_output=json.dumps(finish, ensure_ascii=False),
            context_wrapper=SimpleNamespace(usage=usage),
        )

    monkeypatch.setattr(Runner, "run", fake_run)
    outcome = OpenAIAgentsRuntime(
        backend="sdk_glm",
        model_name="glm-5.2",
        model_settings=model_settings,
        model_factory=lambda: (model, close_model),
    ).run(
        task_frame=frame,
        context=_context(frame),
        registry=_registry([]),
    )

    assert outcome.status == "completed"
    assert seen["agent"].model == model
    assert seen["agent"].model_settings is model_settings
    assert seen["run_config"].tracing_disabled is True
    assert seen["run_config"].trace_include_sensitive_data is False
    assert seen["run_config"].tool_execution.max_function_tool_concurrency == 1
    assert outcome.usage.llm_calls == 2
    assert close_calls == 1


def test_default_sdk_runner_captures_and_appends_run_result_input_history(
    monkeypatch,
) -> None:
    from agents import Runner

    provider_history = [
        {"role": "user", "content": "original task"},
        {"role": "assistant", "content": "original answer"},
    ]
    provider_inputs: list[object] = []
    to_input_list_calls = 0

    class FakeRunResult:
        final_output = "done"
        context_wrapper = SimpleNamespace(
            usage=SimpleNamespace(requests=1, input_tokens=12, output_tokens=4)
        )

        def to_input_list(self):
            nonlocal to_input_list_calls
            to_input_list_calls += 1
            return provider_history

    async def fake_run(_agent, user_input, **_kwargs):
        provider_inputs.append(user_input)
        return FakeRunResult()

    monkeypatch.setattr(Runner, "run", fake_run)
    initial = _run_openai_agents_sdk(
        AgentsSdkRequest(
            instructions="Keep one finance episode.",
            input="original task",
            tools=(),
            max_turns=1,
            timeout=5.0,
            backend="sdk_glm",
            model_name="fake-model",
            model="fake-model",
            model_settings=build_agents_model_settings("sdk_glm"),
        )
    )
    continued = _run_openai_agents_sdk(
        AgentsSdkRequest(
            instructions="Keep one finance episode.",
            input="bounded repair goal",
            tools=(),
            max_turns=1,
            timeout=5.0,
            backend="sdk_glm",
            model_name="fake-model",
            model="fake-model",
            model_settings=build_agents_model_settings("sdk_glm"),
            continuation_input=initial._continuation_input,
        )
    )

    assert to_input_list_calls == 2
    assert provider_inputs == [
        "original task",
        [
            *provider_history,
            {"role": "user", "content": "bounded repair goal"},
        ],
    ]
    assert initial._continuation_input is provider_history
    assert continued._continuation_input is provider_history
    assert "original answer" not in repr(initial)
    assert "original answer" not in json.dumps(asdict(initial))


@pytest.mark.parametrize(
    ("backend", "expected_queries", "expected_dropped"),
    (
        ("sdk_gpt", ["first"], 1),
        ("sdk_glm", ["first", "second"], 0),
    ),
)
def test_sdk_provider_boundary_controls_batched_function_calls(
    backend: str,
    expected_queries: list[str],
    expected_dropped: int,
) -> None:
    from agents import Model, ModelResponse
    from agents.usage import Usage
    from openai.types.responses import (
        ResponseFunctionToolCall,
        ResponseOutputMessage,
        ResponseOutputText,
    )

    class BatchedToolModel(Model):
        def __init__(self) -> None:
            self.calls = 0
            self.inputs: list[object] = []

        async def get_response(
            self,
            system_instructions,
            input,
            model_settings,
            tools,
            output_schema,
            handoffs,
            tracing,
            **_kwargs,
        ) -> ModelResponse:
            del system_instructions, model_settings, tools, output_schema, handoffs, tracing
            self.calls += 1
            self.inputs.append(input)
            if self.calls == 1:
                output = [
                    ResponseFunctionToolCall(
                        arguments=json.dumps({"query": "first"}),
                        call_id="call-first",
                        name="market_news",
                        type="function_call",
                        status="completed",
                    ),
                    ResponseFunctionToolCall(
                        arguments=json.dumps({"query": "second"}),
                        call_id="call-second",
                        name="market_news",
                        type="function_call",
                        status="completed",
                    ),
                ]
            else:
                output = [
                    ResponseOutputMessage(
                        id="message-final",
                        content=[
                            ResponseOutputText(
                                annotations=[],
                                text="done",
                                type="output_text",
                            )
                        ],
                        role="assistant",
                        status="completed",
                        type="message",
                    )
                ]
            return ModelResponse(
                output=output,
                usage=Usage(requests=1),
                response_id=f"response-{self.calls}",
            )

        def stream_response(self, *_args, **_kwargs):
            async def empty_stream():
                if False:
                    yield None

            return empty_stream()

    model = BatchedToolModel()
    observed_queries: list[str] = []
    result = _run_openai_agents_sdk(
        AgentsSdkRequest(
            instructions="Use one finance tool at a time.",
            input="Explain the weekly market decline.",
            tools=(
                AgentsSdkTool(
                    name="market_news",
                    description="Search dated market news.",
                    parameters={
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                        "additionalProperties": False,
                    },
                    invoke=lambda arguments: observed_queries.append(
                        str(arguments["query"])
                    )
                    or {"status": "success"},
                ),
            ),
            max_turns=3,
            timeout=5.0,
            backend=backend,
            model_name="fake-gpt",
            model=model,
            model_settings=build_agents_model_settings(backend),
        )
    )

    assert result.final_output == "done"
    assert model.calls == 2
    assert observed_queries == expected_queries
    assert result.batched_tool_calls_dropped == expected_dropped
    assert json.dumps(model.inputs[1]).count("function_call_output") == len(
        expected_queries
    )


def test_default_sdk_runner_projects_provider_compatible_tool_schema(
    monkeypatch,
) -> None:
    from agents import Runner

    source_schema: dict[str, object] = {
        "type": "object",
        "properties": {
            "metrics": {
                "type": "array",
                "items": {"type": "string"},
                "uniqueItems": True,
            },
            "nested": {
                "type": "object",
                "properties": {
                    "values": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "uniqueItems": True,
                    },
                    "scalar": {"description": "字符串、数字、布尔值或这些标量的数组"},
                },
                "required": ["values", "scalar"],
                "additionalProperties": False,
            },
        },
        "required": ["metrics", "nested"],
        "additionalProperties": False,
    }
    original_schema = json.loads(json.dumps(source_schema))
    captured: dict[str, dict[str, object]] = {}
    captured_instructions: dict[str, str] = {}

    async def fake_run(
        agent,
        _user_input,
        *,
        context,
        max_turns,
        run_config,
        **_kwargs,
    ):
        request = context
        captured[request.backend] = json.loads(
            json.dumps(agent.tools[0].params_json_schema)
        )
        captured_instructions[request.backend] = str(agent.instructions)
        usage = SimpleNamespace(requests=1, input_tokens=10, output_tokens=5)
        return SimpleNamespace(
            final_output="{}", context_wrapper=SimpleNamespace(usage=usage)
        )

    monkeypatch.setattr(Runner, "run", fake_run)
    sdk_tool = AgentsSdkTool(
        name="finance_query",
        description="结构化金融查询",
        parameters=source_schema,
        invoke=lambda _arguments: {},
    )
    for backend in ("sdk_glm", "sdk_gpt"):
        _run_openai_agents_sdk(
            AgentsSdkRequest(
                instructions="Use the registered finance tool.",
                input="Inspect the current market.",
                tools=(sdk_tool,),
                max_turns=1,
                timeout=5.0,
                backend=backend,
                model_name="fake-model",
                model="fake-model",
                model_settings=build_agents_model_settings(backend),
            )
        )

    assert "uniqueItems" in json.dumps(captured["sdk_glm"])
    assert "uniqueItems" not in json.dumps(captured["sdk_gpt"])
    assert captured["sdk_glm"]["properties"]["nested"]["properties"]["scalar"] == {
        "description": "字符串、数字、布尔值或这些标量的数组"
    }
    assert captured["sdk_gpt"]["properties"]["nested"]["properties"]["scalar"] == {
        "description": "字符串、数字、布尔值或这些标量的数组",
        "type": "string",
    }
    assert "每次模型响应最多调用一个工具" in captured_instructions["sdk_gpt"]
    assert "每次模型响应最多调用一个工具" not in captured_instructions["sdk_glm"]
    assert source_schema == original_schema


def test_sdk_runtime_surfaces_invalid_finish_without_hidden_recovery() -> None:
    frame = _frame()
    runner_calls = 0
    research_calls: list[str] = []

    def repairing_runner(request: AgentsSdkRequest) -> AgentsSdkResult:
        nonlocal runner_calls
        runner_calls += 1
        request.tools[0].invoke("A股 当前主线")
        return AgentsSdkResult("not-json", 1, 500, 80, 1)

    outcome = OpenAIAgentsRuntime(
        runner=repairing_runner,
        backend="sdk_glm",
        model_name="glm-5.2",
    ).run(
        task_frame=frame,
        context=_context(frame),
        registry=_registry(research_calls),
    )

    assert runner_calls == 1
    assert research_calls == ["A股 当前主线"]
    assert outcome.status == "partial"
    assert outcome.stop_reason == "sdk_invalid_finish"
    assert outcome.usage.llm_calls == 1
    assert outcome.usage.tool_calls == 1
    assert outcome.usage.input_tokens == 500
    assert outcome.usage.output_tokens == 80


def test_sdk_runtime_translates_model_turn_limit_without_fallback() -> None:
    from agents.exceptions import MaxTurnsExceeded

    frame = _frame()

    def turn_limited(request: AgentsSdkRequest) -> AgentsSdkResult:
        request.tools[0].invoke("A股 当前主线")
        raise MaxTurnsExceeded("turn limit")

    outcome = OpenAIAgentsRuntime(
        runner=turn_limited,
        backend="sdk_glm",
        model_name="glm-5.2",
    ).run(
        task_frame=frame,
        context=_context(frame),
        registry=_registry([]),
    )

    assert outcome.status == "partial"
    assert outcome.stop_reason == "sdk_turn_limit"
    assert "sdk_turn_limit" in outcome.gaps
    assert outcome.evidence[0].content_hash == "mainline-hash"
    assert outcome.usage.tool_calls == 1


@pytest.mark.parametrize(
    ("message", "expected"),
    (
        ("auth_unavailable: no auth available", "sdk_auth_unavailable"),
        ("status code: 429 rate limit", "sdk_rate_limited"),
        ("status code: 503 service unavailable", "sdk_upstream_unavailable"),
        ("connection error", "sdk_transport_unavailable"),
    ),
)
def test_sdk_runtime_classifies_provider_infrastructure_failures(
    message: str,
    expected: str,
) -> None:
    frame = _frame()

    def unavailable(_request: AgentsSdkRequest) -> AgentsSdkResult:
        raise RuntimeError(message)

    outcome = OpenAIAgentsRuntime(
        runner=unavailable,
        backend="sdk_gpt",
        model_name="gpt-5.6-sol",
    ).run(
        task_frame=frame,
        context=_context(frame),
        registry=_registry([]),
    )

    assert outcome.status == "failed"
    assert outcome.stop_reason == expected
    assert outcome.gaps == (expected,)


def test_sdk_surfaces_invalid_reasoning_finish_without_hidden_recovery() -> None:
    frame = _frame()
    context = _context(frame, allowed_capabilities=())
    context = replace(
        context,
        contract=replace(
            context.contract,
            required_outputs=(
                RequiredOutput(
                    "direct_assessment",
                    "直接判断",
                    (),
                    True,
                    grounding_mode="model_reasoning",
                ),
            ),
            allowed_capabilities=(),
        ),
    )
    runner_calls = 0

    def repair_reasoning(request: AgentsSdkRequest) -> AgentsSdkResult:
        nonlocal runner_calls
        runner_calls += 1
        assert request.tools == ()
        return AgentsSdkResult("not-json", 1)

    outcome = OpenAIAgentsRuntime(
        runner=repair_reasoning,
        backend="sdk_glm",
        model_name="glm-5.2",
    ).run(
        task_frame=frame,
        context=context,
        registry=_registry([]),
    )

    assert runner_calls == 1
    assert outcome.status == "failed"
    assert outcome.stop_reason == "sdk_invalid_finish"
    assert outcome.usage.llm_calls == 1
    assert outcome.usage.tool_calls == 0
    assert outcome.bindings == ()


@pytest.mark.skipif(
    os.environ.get("RUN_OPENAI_AGENTS_LIVE") != "1",
    reason="real OpenAI Agents SDK smoke is opt-in",
)
def test_real_sdk_glm_smoke() -> None:
    api_key = os.environ["FORESIGHT_BUILTIN_LLM_API_KEY"]
    base_url = os.environ.get(
        "FORESIGHT_BUILTIN_LLM_BASE_URL",
        "https://open.bigmodel.cn/api/coding/paas/v4",
    )
    model_name = os.environ.get("FORESIGHT_BUILTIN_LLM_MODEL", "glm-5.2")
    frame = _frame()
    context = _context(frame, timeout=90.0)
    calls: list[str] = []
    model_factory = build_glm_sdk_model_factory(
        api_key=api_key,
        base_url=base_url,
        model=model_name,
        timeout=90.0,
    )
    outcome = OpenAIAgentsRuntime(
        backend="sdk_glm",
        model_name=model_name,
        model_factory=model_factory,
    ).run(
        task_frame=frame,
        context=context,
        registry=_registry(calls),
    )
    verified = verify_episode_outcome(context.contract, outcome)
    payload = {
        "runtime_backend": "sdk_glm",
        "verified_status": verified.verified_status,
        "outcome": outcome.to_dict(),
    }
    serialized = json.dumps(payload, ensure_ascii=False, indent=2)
    Path("/tmp/sdk-glm-smoke.json").write_text(serialized, encoding="utf-8")

    assert api_key not in serialized
    assert outcome.status in {"completed", "partial"}
    assert outcome.evidence
    assert outcome.stop_reason == "model_finish"
    assert calls
