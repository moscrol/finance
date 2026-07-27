from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from threading import Event
from uuid import UUID

import duckdb
import pytest

import intelligence.services.continuous_turn_adapter as adapter_module
from intelligence.services import ask_synthesis, episode_tools, llm_refine
from intelligence.services.agent_research import AgentEvidence, AgentToolContext
from intelligence.services.agent_runtime import (
    AgentOutcome,
    AgentUsage,
    EpisodeEvent,
    ModelToolCall,
    ModelTurn,
    OutputEvidenceBinding,
)
from intelligence.services.continuous_turn_adapter import ContinuousTurnAdapter
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.episode_progress import EpisodeProgress
from intelligence.services.glm_agent_runtime import GLMAgentRuntime
from intelligence.services.openai_agents_runtime import (
    AgentsSdkRequest,
    AgentsSdkResult,
    OpenAIAgentsRuntime,
)
from intelligence.services.episode_semantic_verifier import (
    DEFAULT_JUDGE_TIMEOUT_SECONDS,
    SemanticEpisodeOutcome,
)
from intelligence.services.episode_session import CallbackEpisodeSession
from intelligence.services.episode_verifier import (
    VerifiedEpisodeOutcome,
    verify_episode_outcome,
)
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.kb_rag import RetrievalTelemetry, WikiHit, WikiRagResult
from intelligence.services.research_contract import (
    InMemoryRootBudgetLedger,
    RequiredOutput,
)
from intelligence.services.research_tool_registry import (
    ResearchToolRegistry,
    ToolSpec,
)
from intelligence.services.task_frame import TaskFrame
from intelligence.services.turn_control_core import TurnControlResult


def _frame(
    *,
    question_type: str = "market_forecast",
    required_outputs: tuple[str, ...] = ("direct_assessment",),
    clarification_question: str | None = None,
) -> TaskFrame:
    return TaskFrame(
        raw_question="目前市场怎么看",
        user_goal="判断当前市场结构",
        question_type=question_type,
        subject="A股市场",
        subject_kind="market_pattern",
        market_scope="A股",
        timeframe="最近交易日",
        required_outputs=required_outputs,
        assumptions=(),
        ambiguities=(),
        clarification_question=clarification_question,
        evidence_policy="current_market_scenarios",
        confidence=0.95,
    )


def _control(
    frame: TaskFrame,
    *,
    terminal_kind: str = "research",
    capabilities: tuple[str, ...] = ("market_data",),
    clarification_questions: tuple[str, ...] = (),
) -> TurnControlResult:
    return TurnControlResult(
        task_frame=frame,
        execution_route=(
            "clarify" if terminal_kind == "clarification" else frame.question_type
        ),
        terminal_kind=terminal_kind,  # type: ignore[arg-type]
        needs_retrieval=terminal_kind == "research",
        capabilities=capabilities,
        contract_required=terminal_kind == "research",
        clarification_questions=clarification_questions,
    )


class _RuntimeThatRaises:
    def run(self, **_kwargs):
        raise AssertionError("disabled adapter must not call runtime")


def _raises(*_args, **_kwargs):
    raise AssertionError("dependency must not be called")


class _SemanticThatRaises:
    def verify(self, **_kwargs):
        raise AssertionError("semantic verifier must not be called")


def _scripted_episode_result(
    *,
    semantic_status: str,
    public_answer: str,
    evidence: tuple[AgentEvidence, ...],
    bindings: tuple[OutputEvidenceBinding, ...],
    outcome_status: str = "completed",
    draft: str = "当前更接近条件化修复。",
    traces: tuple[ProviderTrace, ...] = (),
    latest_data_date: str | None = None,
    event_payload: dict[str, object] | None = None,
    judge_status: str | None = None,
    required_outputs: tuple[str, ...] = ("direct_assessment",),
    gap_output_ids: tuple[str, ...] = (),
    runtime_name: str = "continuous_glm",
    progress_sink=None,
):
    frame = _frame(required_outputs=required_outputs)
    capabilities = tuple(dict.fromkeys(item.tool for item in evidence)) or (
        "market_data",
    )
    control = _control(frame, capabilities=capabilities)
    context = build_episode_context(
        frame,
        task_id="adapter-scripted",
        capabilities=control.capabilities,
        timeout=30.0,
        latest_data_date=latest_data_date,
    )
    outcome = AgentOutcome(
        task_frame_hash=frame.task_frame_hash,
        status=outcome_status,  # type: ignore[arg-type]
        draft=draft,
        evidence=evidence,
        traces=traces,
        gaps=(),
        stop_reason="model_finish",
        events=(
            EpisodeEvent(
                1,
                "task",
                event_payload or {"task_frame_hash": frame.task_frame_hash},
            ),
        ),
        bindings=bindings,
        usage=AgentUsage(llm_calls=1, tool_calls=len(evidence)),
    )

    class Runtime:
        def run(self, **_kwargs):
            return outcome

    class Semantic:
        def verify(self, *, frame, structurally_verified, deadline):
            del frame, deadline
            return SemanticEpisodeOutcome(
                verified=structurally_verified,
                status=semantic_status,  # type: ignore[arg-type]
                public_answer=public_answer,
                judge_status=(
                    judge_status
                    or ("passed" if semantic_status == "completed" else "rejected")
                ),
                gap_output_ids=gap_output_ids,
            )

    return ContinuousTurnAdapter(
        runtime=Runtime(),
        runtime_name=runtime_name,
        mode="on",
        context_factory=lambda *_args, **_kwargs: context,
        registry_factory=lambda *_args, **_kwargs: "registry",
        semantic_verifier=Semantic(),
        progress_sink=progress_sink,
    ).handle(frame=frame, control=control)


def test_live_progress_sink_replaces_posthoc_events_at_real_phase_boundaries() -> None:
    frame = _frame()
    control = _control(frame)
    context = build_episode_context(
        frame,
        task_id="adapter-live-progress",
        capabilities=control.capabilities,
        timeout=30.0,
        latest_data_date="2026-07-26",
    )
    evidence = AgentEvidence(
        tool="market_data",
        title="市场结构",
        detail="上涨家数改善，成交保持活跃",
        source="本地行情",
        source_date="2026-07-26",
        content_hash="live-progress-evidence",
    )
    outcome = AgentOutcome(
        task_frame_hash=frame.task_frame_hash,
        status="completed",
        draft="当前市场处于修复阶段。",
        evidence=(evidence,),
        traces=(),
        gaps=(),
        stop_reason="model_finish",
        events=(
            EpisodeEvent(
                1,
                "task",
                {"task_frame_hash": frame.task_frame_hash},
            ),
        ),
        bindings=(
            OutputEvidenceBinding(
                "direct_assessment",
                (evidence.content_hash,),
            ),
        ),
        usage=AgentUsage(llm_calls=1, tool_calls=1),
    )
    progress: list[EpisodeProgress] = []

    class Runtime:
        def run(self, **_kwargs):
            assert [item.stage for item in progress] == ["understanding"]
            return outcome

    class Semantic:
        def verify(self, *, frame, structurally_verified, deadline):
            del frame, deadline
            assert progress[-1].stage == "verification"
            return SemanticEpisodeOutcome(
                verified=structurally_verified,
                status="completed",
                public_answer=structurally_verified.outcome.draft,
                judge_status="passed",
            )

    result = ContinuousTurnAdapter(
        runtime=Runtime(),
        semantic_verifier=Semantic(),
        mode="on",
        context_factory=lambda *_args, **_kwargs: context,
        registry_factory=lambda *_args, **_kwargs: "registry",
        progress_sink=progress.append,
    ).handle(frame=frame, control=control)

    assert result.status == "completed"
    assert result.events == ()
    assert [item.stage for item in progress] == [
        "understanding",
        "verification",
        "finalizing",
    ]


def test_verifier_gap_reenters_same_session_without_second_runtime_run() -> None:
    frame = _frame(required_outputs=("direct_assessment", "counterpoint"))
    control = _control(frame, capabilities=("market_data",))
    context = build_episode_context(
        frame,
        task_id="adapter-resume",
        capabilities=control.capabilities,
        timeout=60.0,
    )
    evidence = AgentEvidence(
        tool="market_data",
        title="市场结构",
        detail="上涨家数修复但反方仍待确认",
        source="本地行情",
        source_date="2026-07-26",
        content_hash="resume-evidence-1",
        supports=("direct_assessment", "counterpoint"),
        independent_key="market",
    )
    initial_events = (
        EpisodeEvent(1, "task", {"task_frame_hash": frame.task_frame_hash}),
        EpisodeEvent(2, "model_turn", {"task_frame_hash": frame.task_frame_hash}),
    )
    initial = AgentOutcome(
        task_frame_hash=frame.task_frame_hash,
        status="partial",
        draft="当前偏修复，但反方证据仍缺。",
        evidence=(evidence,),
        traces=(),
        gaps=("counterpoint",),
        stop_reason="model_finish",
        events=initial_events,
        bindings=(
            OutputEvidenceBinding("direct_assessment", ("resume-evidence-1",), ""),
            OutputEvidenceBinding("counterpoint", (), "缺少反方证据"),
        ),
        usage=AgentUsage(1, 1, 0),
    )
    repaired = AgentOutcome(
        task_frame_hash=frame.task_frame_hash,
        status="completed",
        draft="当前偏修复，但量能回落构成反方约束。",
        evidence=(evidence,),
        traces=(),
        gaps=(),
        stop_reason="model_finish",
        events=(*initial_events, EpisodeEvent(3, "model_turn", {"task_frame_hash": frame.task_frame_hash})),
        bindings=(
            OutputEvidenceBinding("direct_assessment", ("resume-evidence-1",), ""),
            OutputEvidenceBinding("counterpoint", ("resume-evidence-1",), ""),
        ),
        usage=AgentUsage(2, 1, 0),
    )
    calls = {"start": 0, "resume": 0, "run": 0}

    class Runtime:
        def run(self, **_kwargs):
            calls["run"] += 1
            raise AssertionError("resumable runtime must not receive a second run")

        def start(self, task_frame, *, context, registry):
            del task_frame, registry
            calls["start"] += 1

            def resume(previous, goal):
                assert previous is initial
                assert goal.episode_id == context.contract.task_id
                calls["resume"] += 1
                return repaired

            return CallbackEpisodeSession(
                episode_id=context.contract.task_id,
                outcome=initial,
                resume_callback=resume,
            )

    class Semantic:
        def verify(self, *, frame, structurally_verified, deadline):
            del frame, deadline
            return SemanticEpisodeOutcome(
                verified=structurally_verified,
                status="completed",
                public_answer=structurally_verified.outcome.draft,
                judge_status="passed",
            )

    result = ContinuousTurnAdapter(
        runtime=Runtime(),
        semantic_verifier=Semantic(),
        runtime_name="continuous_glm",
        mode="on",
        context_factory=lambda *_args, **_kwargs: context,
        registry_factory=lambda *_args, **_kwargs: "registry",
    ).handle(frame=frame, control=control)

    assert result.status == "completed"
    assert calls == {"start": 1, "resume": 1, "run": 0}
    assert result.private_artifact["repair_cycles"] == 1


def test_adapter_uses_production_sdk_runtime_same_episode_repair() -> None:
    frame = _frame(required_outputs=("direct_assessment", "counterpoint"))
    control = _control(
        frame,
        capabilities=("market_data", "news_search"),
    )
    context = build_episode_context(
        frame,
        task_id="adapter-sdk-runtime-resume",
        capabilities=control.capabilities,
        timeout=60.0,
    )

    def evidence(
        *,
        tool: str,
        title: str,
        detail: str,
        content_hash: str,
        supports: tuple[str, ...],
    ) -> AgentEvidence:
        return AgentEvidence(
            tool=tool,
            title=title,
            detail=detail,
            source="测试数据",
            source_date="2026-07-26",
            content_hash=content_hash,
            supports=supports,
            independent_key=tool,
        )

    def market_runner(_query: str, _context: AgentToolContext):
        item = evidence(
            tool="market_data",
            title="市场结构",
            detail="上涨家数修复。",
            content_hash="sdk-adapter-market",
            supports=("direct_assessment",),
        )
        return (
            [item],
            item.detail,
            ProviderTrace("test:market", "market_data", "success"),
        )

    def news_runner(_query: str, _context: AgentToolContext):
        item = evidence(
            tool="news_search",
            title="反方约束",
            detail="量能回落会削弱修复持续性。",
            content_hash="sdk-adapter-news",
            supports=("counterpoint",),
        )
        return (
            [item],
            item.detail,
            ProviderTrace("test:news", "news_search", "success"),
        )

    registry = ResearchToolRegistry(
        (
            ToolSpec(
                name="market_data",
                capability="market_data",
                description="市场结构",
                cost="local",
                freshness="current",
                runner=market_runner,
            ),
            ToolSpec(
                name="news_search",
                capability="news_search",
                description="市场反证",
                cost="network",
                freshness="current",
                runner=news_runner,
            ),
        )
    )
    provider_history = object()
    runner_calls = 0

    def sdk_runner(request: AgentsSdkRequest) -> AgentsSdkResult:
        nonlocal runner_calls
        runner_calls += 1
        tools = {tool.name: tool for tool in request.tools}
        if runner_calls == 1:
            observed = tools["market_data"].invoke("当前市场")
            finish = {
                "status": "partial",
                "draft": "当前偏修复，但反方证据仍缺。",
                "gaps": ["缺少反方证据"],
                "bindings": [
                    {
                        "output_id": "direct_assessment",
                        "evidence_hashes": observed["evidence_hashes"],
                        "gap": "",
                    },
                    {
                        "output_id": "counterpoint",
                        "evidence_hashes": [],
                        "gap": "缺少反方证据",
                    },
                ],
            }
        else:
            assert request._continuation_input is provider_history
            observed = tools["news_search"].invoke("市场修复反证")
            finish = {
                "status": "completed",
                "draft": "当前偏修复，但量能回落会削弱持续性。",
                "gaps": [],
                "bindings": [
                    {
                        "output_id": "direct_assessment",
                        "evidence_hashes": ["sdk-adapter-market"],
                        "gap": "",
                    },
                    {
                        "output_id": "counterpoint",
                        "evidence_hashes": observed["evidence_hashes"],
                        "gap": "",
                    },
                ],
            }
        return AgentsSdkResult(
            json.dumps(finish, ensure_ascii=False),
            1,
            continuation_input=provider_history,
        )

    class Semantic:
        def verify(self, *, frame, structurally_verified, deadline):
            del frame, deadline
            return SemanticEpisodeOutcome(
                verified=structurally_verified,
                status="completed",
                public_answer=structurally_verified.outcome.draft,
                judge_status="passed",
            )

    result = ContinuousTurnAdapter(
        runtime=OpenAIAgentsRuntime(
            runner=sdk_runner,
            backend="sdk_gpt",
            model_name="gpt-5.6-sol",
        ),
        semantic_verifier=Semantic(),
        runtime_name="sdk_gpt",
        mode="on",
        context_factory=lambda *_args, **_kwargs: context,
        registry_factory=lambda *_args, **_kwargs: registry,
    ).handle(frame=frame, control=control)

    assert result.status == "completed"
    assert result.private_artifact["repair_cycles"] == 1
    assert runner_calls == 2
    events = result.private_artifact["events"]
    assert any(event["kind"] == "repair_goal" for event in events)
    assert any(event["kind"] == "repair_reentry" for event in events)


def test_sdk_semantic_repair_uses_root_reserve_after_research_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The verifier reserve may repair wording, but may not reopen research."""

    clock = {"now": 0.0}
    monkeypatch.setattr(
        "intelligence.services.research_contract.time.monotonic",
        lambda: clock["now"],
    )
    frame = _frame(required_outputs=("direct_assessment",))
    control = _control(frame, capabilities=("market_data",))
    context = build_episode_context(
        frame,
        task_id="adapter-sdk-verifier-reserve",
        capabilities=control.capabilities,
        timeout=30.0,
    )
    context = replace(
        context,
        root_budget=InMemoryRootBudgetLedger(
            episode_id=context.contract.task_id,
            initial_calls=1,
            hard_calls_cap=2,
            initial_seconds=1.0,
            hard_seconds_cap=9.0,
        ),
    )
    monkeypatch.setattr(
        "intelligence.services.openai_agents_runtime.monotonic",
        lambda: 0.0,
    )
    registry = ResearchToolRegistry(
        (
            ToolSpec(
                name="market_data",
                capability="market_data",
                description="市场结构",
                cost="local",
                freshness="current",
                runner=lambda _query, _context: (
                    [
                        AgentEvidence(
                            tool="market_data",
                            title="市场结构",
                            detail="缩量下跌后上涨家数修复。",
                            source="测试行情",
                            source_date="2026-07-26",
                            content_hash="sdk-verifier-reserve-market",
                            supports=("direct_assessment",),
                            independent_key="market",
                        )
                    ],
                    "缩量下跌后上涨家数修复。",
                    ProviderTrace("test:market", "market_data", "success"),
                ),
            ),
        )
    )
    provider_history = object()
    runner_calls: list[AgentsSdkRequest] = []

    def sdk_runner(request: AgentsSdkRequest) -> AgentsSdkResult:
        runner_calls.append(request)
        if len(runner_calls) == 1:
            observed = request.tools[0].invoke("A股市场结构")
            assert context.root_budget is not None
            context.root_budget.consume_seconds(
                seconds=context.root_budget.remaining_seconds
            )
            assert context.root_budget.remaining_calls == 0
            assert context.root_budget.remaining_seconds == 0.0
            clock["now"] = 31.0
            finish = {
                "status": "completed",
                "draft": "本轮反弹可以持续，因为风险偏好已经全面回升。",
                "gaps": [],
                "bindings": [
                    {
                        "output_id": "direct_assessment",
                        "evidence_hashes": observed["evidence_hashes"],
                        "gap": "",
                    }
                ],
            }
        else:
            assert request._continuation_input is provider_history
            assert request.tools == ()
            finish = {
                "status": "completed",
                "draft": "当前更像缩量下跌后的修复，持续性仍取决于量能。",
                "gaps": [],
                "bindings": [
                    {
                        "output_id": "direct_assessment",
                        "evidence_hashes": ["sdk-verifier-reserve-market"],
                        "gap": "",
                    }
                ],
            }
        return AgentsSdkResult(
            json.dumps(finish, ensure_ascii=False),
            1,
            continuation_input=provider_history,
        )

    class Semantic:
        def __init__(self) -> None:
            self.calls = 0

        def verify(self, *, structurally_verified, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                return SemanticEpisodeOutcome(
                    verified=structurally_verified,
                    status="partial",
                    public_answer="结论包含未被证据支持的风险偏好因果。",
                    judge_status="rejected",
                    gap_output_ids=("direct_assessment",),
                    rejected_claim_indexes=(0,),
                )
            return SemanticEpisodeOutcome(
                verified=structurally_verified,
                status="completed",
                public_answer=structurally_verified.outcome.draft,
                judge_status="passed",
            )

    semantic = Semantic()
    result = ContinuousTurnAdapter(
        runtime=OpenAIAgentsRuntime(
            runner=sdk_runner,
            backend="sdk_gpt",
            model_name="gpt-5.6-sol",
        ),
        semantic_verifier=semantic,
        runtime_name="sdk_gpt",
        mode="on",
        context_factory=lambda *_args, **_kwargs: context,
        registry_factory=lambda *_args, **_kwargs: registry,
        timeout=120.0,
    ).handle(frame=frame, control=control)

    assert result.status == "completed"
    assert result.answer == "当前更像缩量下跌后的修复，持续性仍取决于量能。"
    assert len(runner_calls) == 2
    assert semantic.calls == 2
    assert result.private_artifact["repair_cycles"] == 1


def test_sdk_timeout_with_unbound_evidence_uses_tool_closed_delivery_repair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A timed-out research turn may still bind evidence in its reserved window."""

    clock = {"now": 0.0}
    monkeypatch.setattr(
        "intelligence.services.research_contract.time.monotonic",
        lambda: clock["now"],
    )
    monkeypatch.setattr(
        "intelligence.services.openai_agents_runtime.monotonic",
        lambda: 0.0,
    )
    frame = _frame(required_outputs=("direct_assessment",))
    control = _control(frame, capabilities=("market_data",))
    context = build_episode_context(
        frame,
        task_id="adapter-sdk-timeout-delivery-repair",
        capabilities=control.capabilities,
        timeout=30.0,
    )
    context = replace(
        context,
        root_budget=InMemoryRootBudgetLedger(
            episode_id=context.contract.task_id,
            initial_calls=1,
            hard_calls_cap=2,
            initial_seconds=1.0,
            hard_seconds_cap=9.0,
        ),
    )
    evidence_hash = "sdk-timeout-delivery-evidence"
    registry = ResearchToolRegistry(
        (
            ToolSpec(
                name="market_data",
                capability="market_data",
                description="市场结构",
                cost="local",
                freshness="current",
                runner=lambda _query, _context: (
                    [
                        AgentEvidence(
                            tool="market_data",
                            title="市场结构",
                            detail="周内先涨后跌，最后一个交易日出现放量回撤。",
                            source="测试行情",
                            source_date="2026-07-24",
                            content_hash=evidence_hash,
                            independent_key="market-window",
                        )
                    ],
                    "周内先涨后跌，最后一个交易日出现放量回撤。",
                    ProviderTrace("test:market", "market_data", "success"),
                ),
            ),
        )
    )
    runner_calls: list[AgentsSdkRequest] = []

    def sdk_runner(request: AgentsSdkRequest) -> AgentsSdkResult:
        runner_calls.append(request)
        if len(runner_calls) == 1:
            observed = request.tools[0].invoke("A股周内结构")
            assert observed["evidence_hashes"] == [evidence_hash]
            assert context.root_budget is not None
            context.root_budget.consume_seconds(
                seconds=context.root_budget.remaining_seconds
            )
            clock["now"] = 31.0
            raise TimeoutError("research turn exhausted")
        assert request.tools == ()
        assert request._continuation_input is None
        repair_input = json.loads(request.input)
        assert repair_input["kind"] == "REPAIR_GOAL"
        assert repair_input["evidence"][0]["content_hash"] == evidence_hash
        return AgentsSdkResult(
            json.dumps(
                {
                    "status": "completed",
                    "draft": "这一周并非单边下跌，更准确地说是周五回撤。",
                    "gaps": [],
                    "bindings": [
                        {
                            "output_id": "direct_assessment",
                            "evidence_hashes": [evidence_hash],
                            "gap": "",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            1,
        )

    class Semantic:
        def verify(self, *, structurally_verified, **_kwargs):
            return SemanticEpisodeOutcome(
                verified=structurally_verified,
                status="completed",
                public_answer=structurally_verified.outcome.draft,
                judge_status="passed",
            )

    result = ContinuousTurnAdapter(
        runtime=OpenAIAgentsRuntime(
            runner=sdk_runner,
            backend="sdk_gpt",
            model_name="gpt-5.6-sol",
        ),
        semantic_verifier=Semantic(),
        runtime_name="sdk_gpt",
        mode="on",
        context_factory=lambda *_args, **_kwargs: context,
        registry_factory=lambda *_args, **_kwargs: registry,
        timeout=120.0,
    ).handle(frame=frame, control=control)

    assert result.status == "completed"
    assert result.answer == "这一周并非单边下跌，更准确地说是周五回撤。"
    assert len(runner_calls) == 2
    assert result.private_artifact["repair_cycles"] == 1
    events = result.private_artifact["events"]
    assert any(event["kind"] == "repair_goal" for event in events)
    assert any(event["kind"] == "repair_reentry" for event in events)


def test_semantic_gap_reenters_same_session_and_rechecks_semantics() -> None:
    frame = _frame(required_outputs=("direct_assessment",))
    control = _control(frame, capabilities=("market_data",))
    context = build_episode_context(
        frame,
        task_id="adapter-semantic-resume",
        capabilities=control.capabilities,
        timeout=60.0,
    )
    evidence = AgentEvidence(
        tool="market_data",
        title="市场结构",
        detail="上涨家数修复但持续性仍需语义核对",
        source="本地行情",
        source_date="2026-07-26",
        content_hash="semantic-resume-evidence",
        supports=("direct_assessment",),
        independent_key="market",
    )
    initial_events = (
        EpisodeEvent(1, "task", {"task_frame_hash": frame.task_frame_hash}),
        EpisodeEvent(2, "model_turn", {"task_frame_hash": frame.task_frame_hash}),
    )
    initial = AgentOutcome(
        task_frame_hash=frame.task_frame_hash,
        status="completed",
        draft="当前偏修复。",
        evidence=(evidence,),
        traces=(),
        gaps=(),
        stop_reason="model_finish",
        events=initial_events,
        bindings=(
            OutputEvidenceBinding(
                "direct_assessment",
                (evidence.content_hash,),
            ),
        ),
        usage=AgentUsage(1, 1, 0),
    )
    repaired = replace(
        initial,
        draft="当前偏修复，但持续性取决于量能。",
        events=(
            *initial_events,
            EpisodeEvent(3, "model_turn", {"task_frame_hash": frame.task_frame_hash}),
        ),
        usage=AgentUsage(2, 1, 0),
    )
    resume_goals = []

    class Runtime:
        def start(self, _frame, *, context, registry):
            del registry

            def resume(previous, goal):
                assert previous is initial
                resume_goals.append(goal)
                return repaired

            return CallbackEpisodeSession(
                episode_id=context.contract.task_id,
                outcome=initial,
                resume_callback=resume,
            )

    class Semantic:
        def __init__(self) -> None:
            self.calls = 0

        def verify(self, *, frame, structurally_verified, deadline):
            del frame, deadline
            self.calls += 1
            if self.calls == 1:
                return SemanticEpisodeOutcome(
                    verified=structurally_verified,
                    status="partial",
                    public_answer="语义核验发现直接判断仍有缺口。",
                    judge_status="rejected",
                    gap_output_ids=("direct_assessment",),
                    rejected_claim_indexes=(0,),
                )
            return SemanticEpisodeOutcome(
                verified=structurally_verified,
                status="completed",
                public_answer=structurally_verified.outcome.draft,
                judge_status="passed",
            )

    semantic = Semantic()
    result = ContinuousTurnAdapter(
        runtime=Runtime(),
        semantic_verifier=semantic,
        runtime_name="continuous_glm",
        mode="on",
        context_factory=lambda *_args, **_kwargs: context,
        registry_factory=lambda *_args, **_kwargs: "registry",
    ).handle(frame=frame, control=control)

    assert result.status == "completed"
    assert semantic.calls == 2
    assert len(resume_goals) == 1
    assert resume_goals[0].unsupported_claims == ("claim_index:0",)
    assert result.private_artifact["repair_cycles"] == 1


def test_real_episode_rewrites_typed_query_error_and_repairs_in_same_history(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    finance_root = tmp_path / "finance"
    db_path = finance_root / "db" / "market_feature_store.duckdb"
    db_path.parent.mkdir(parents=True)
    connection = duckdb.connect(str(db_path))
    connection.execute(
        """
        create table fact_market_daily(
            trade_date date,
            market_stage varchar,
            total_amount double,
            sh_index_pct_chg double
        )
        """
    )
    connection.execute(
        "insert into fact_market_daily values ('2026-07-24', '反弹阶段', 22000, 1.2)"
    )
    connection.close()
    wiki_root = tmp_path / "wiki"
    wiki_root.mkdir()

    def retrieve(query: str, *_args, **_kwargs) -> WikiRagResult:
        is_counter = "风险" in query or "反方" in query
        key = "counter" if is_counter else "support"
        hit = WikiHit(
            page_id=key,
            file_path=f"wiki/sources/{key}.md",
            title="市场反方证据" if is_counter else "市场结构支持证据",
            score=0.9,
            excerpt=(
                "量能回落会削弱反弹持续性"
                if is_counter
                else "成交与指数同步修复支持阶段性反弹"
            ),
            best_chunk_id=f"{key}::0",
            content_hash=f"{key}-content-hash",
            source_date="2026-07-24",
        )
        return WikiRagResult(
            ok=True,
            hits=[hit],
            telemetry=RetrievalTelemetry(status="ok", hit_count=1),
            command=query,
        )

    monkeypatch.setattr(episode_tools.kb_rag, "retrieve", retrieve)

    frame = replace(
        _frame(
            question_type="comparison",
            required_outputs=("direct_assessment", "counterpoint"),
        ),
        raw_question="比较阶段性反弹与趋势反转两种解释",
        user_goal="比较两种市场解释",
    )
    control = _control(frame, capabilities=())

    class SameHistoryModel:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []
            self.saw_typed_gap_before_rewrite = False

        @staticmethod
        def _tool_payloads(messages) -> list[dict[str, object]]:
            return [
                json.loads(message["content"])
                for message in messages
                if message.get("role") == "tool"
            ]

        @staticmethod
        def _hashes_by_tool(messages) -> dict[str, list[str]]:
            hashes: dict[str, list[str]] = {}
            for payload in SameHistoryModel._tool_payloads(messages):
                if not payload.get("ok"):
                    continue
                hashes.setdefault(str(payload["tool"]), []).extend(
                    str(item) for item in payload.get("evidence_hashes", [])
                )
            return hashes

        def complete(self, *, messages, tools, timeout):
            del timeout
            self.calls.append({"messages": messages, "tools": tools})
            call_number = len(self.calls)
            if call_number == 1:
                return ModelTurn(
                    "",
                    (
                        ModelToolCall(
                            "invalid-finance",
                            "finance_query",
                            {
                                "dataset": "market_daily",
                                "metrics": ["not_a_public_metric"],
                                "dimensions": ["trade_date"],
                                "filters": [],
                                "group_by": [],
                                "order_by": [],
                                "limit": 5,
                            },
                        ),
                    ),
                    "scripted",
                    "",
                )
            if call_number == 2:
                payloads = self._tool_payloads(messages)
                self.saw_typed_gap_before_rewrite = any(
                    "结构化查询条件无效" in " ".join(payload.get("gaps", []))
                    and "not_a_public_metric" in str(payload.get("observation"))
                    for payload in payloads
                )
                return ModelTurn(
                    "",
                    (
                        ModelToolCall(
                            "valid-finance",
                            "finance_query",
                            {
                                "dataset": "market_daily",
                                "metrics": ["index_return_pct", "total_amount"],
                                "dimensions": ["trade_date", "market_stage"],
                                "filters": [],
                                "time_range": {
                                    "start": "2026-07-24",
                                    "end": "2026-07-24",
                                },
                                "group_by": [],
                                "order_by": [
                                    {"field": "trade_date", "direction": "asc"}
                                ],
                                "limit": 5,
                            },
                        ),
                        ModelToolCall(
                            "support-search",
                            "evidence_search",
                            {"query": "A股市场结构支持"},
                        ),
                    ),
                    "scripted",
                    "",
                )
            hashes = self._hashes_by_tool(messages)
            if call_number == 3:
                direct_hashes = [
                    *hashes.get("finance_query", []),
                    *hashes.get("evidence_search", []),
                ]
                return ModelTurn(
                    json.dumps(
                        {
                            "status": "partial",
                            "draft": "当前判断偏阶段性修复，但反方证据仍缺。",
                            "gaps": ["缺少反方证据"],
                            "bindings": [
                                {
                                    "output_id": "direct_assessment",
                                    "evidence_hashes": direct_hashes,
                                    "gap": "",
                                },
                                {
                                    "output_id": "counterpoint",
                                    "evidence_hashes": [],
                                    "gap": "缺少反方证据",
                                },
                            ],
                        },
                        ensure_ascii=False,
                    ),
                    (),
                    "scripted",
                    "",
                )
            if call_number == 4:
                assert any(
                    '"kind": "REPAIR_GOAL"' in str(message.get("content"))
                    and '"episode_id": "integration-episode"'
                    in str(message.get("content"))
                    for message in messages
                )
                return ModelTurn(
                    "",
                    (
                        ModelToolCall(
                            "counter-search",
                            "evidence_search",
                            {"query": "A股市场风险反方"},
                        ),
                    ),
                    "scripted",
                    "",
                )
            if call_number == 5:
                evidence_hashes = hashes.get("evidence_search", [])
                return ModelTurn(
                    json.dumps(
                        {
                            "status": "completed",
                            "draft": (
                                "当前判断偏阶段性修复；主要反证是量能回落会削弱持续性。"
                            ),
                            "gaps": [],
                            "bindings": [
                                {
                                    "output_id": "direct_assessment",
                                    "evidence_hashes": [
                                        *hashes.get("finance_query", []),
                                        evidence_hashes[0],
                                    ],
                                    "gap": "",
                                },
                                {
                                    "output_id": "counterpoint",
                                    "evidence_hashes": [evidence_hashes[-1]],
                                    "gap": "",
                                },
                            ],
                        },
                        ensure_ascii=False,
                    ),
                    (),
                    "scripted",
                    "",
                )
            raise AssertionError("unexpected model call")

    class PassingSemanticVerifier:
        def verify(self, *, frame, structurally_verified, deadline):
            del frame, deadline
            return SemanticEpisodeOutcome(
                verified=structurally_verified,
                status=structurally_verified.verified_status,
                public_answer=structurally_verified.outcome.draft,
                judge_status="passed",
            )

    model = SameHistoryModel()
    result = ContinuousTurnAdapter(
        runtime=GLMAgentRuntime(client=model),
        semantic_verifier=PassingSemanticVerifier(),
        runtime_name="continuous_glm",
        mode="on",
        context_factory=build_episode_context,
        registry_factory=lambda frame, context: episode_tools.build_episode_registry(
            frame,
            context,
            finance_root=finance_root,
            knowledge_wiki=wiki_root,
            l3_runner=None,
            evidence_search_judge=lambda *_args: None,
        ),
        task_id_factory=lambda: "integration-episode",
        timeout=60.0,
        verification_reserve=0.0,
        today="2026-07-24",
        latest_data_date="2026-07-24",
    ).handle(frame=frame, control=control)

    assert result.status == "completed"
    assert model.saw_typed_gap_before_rewrite is True
    assert result.private_artifact is not None
    assert result.private_artifact["repair_cycles"] == 1
    outcome = result.private_artifact["outcome"]
    finance_traces = [
        trace
        for trace in result.private_artifact["traces"]
        if trace["capability"] == "finance_query"
    ]
    tool_events = [
        event
        for event in result.private_artifact["events"]
        if event["kind"] in {"tool_request", "tool_result", "tool_error"}
        and (
            event["payload"].get("name") == "finance_query"
            or event["payload"].get("tool") == "finance_query"
        )
    ]
    finance_event_summary = [
        (
            event["kind"],
            event["payload"].get("error"),
            event["payload"].get("query"),
            event["payload"].get("gaps"),
        )
        for event in tool_events
    ]
    assert any(
        trace["status"] == "success" for trace in finance_traces
    ), finance_event_summary
    assert {item["tool"] for item in outcome["evidence"]} == {
        "finance_query",
        "evidence_search",
    }, result.private_artifact["traces"]
    assert all(binding["evidence_hashes"] for binding in outcome["bindings"])
    assert outcome["gaps"] == []
    events = result.private_artifact["events"]
    requested_tools = [
        event["payload"]["name"]
        for event in events
        if event["kind"] == "tool_request"
    ]
    assert requested_tools == [
        "finance_query",
        "finance_query",
        "evidence_search",
        "evidence_search",
    ]
    repair_goal = next(event for event in events if event["kind"] == "repair_goal")
    repair_reentry = next(
        event for event in events if event["kind"] == "repair_reentry"
    )
    assert repair_goal["payload"]["episode_id"] == "integration-episode"
    assert repair_goal["payload"]["missing_answer_elements"] == ["counterpoint"]
    assert repair_reentry["payload"]["episode_id"] == "integration-episode"
    assert (
        repair_reentry["payload"]["repair_goal_id"]
        == repair_goal["payload"]["repair_goal_id"]
    )
    assert repair_reentry["payload"]["cycle"] == 1


def test_repair_deadline_stop_prevents_another_repair_or_semantic_cycle() -> None:
    frame = _frame(
        required_outputs=(
            "direct_assessment",
            "counterpoint",
            "invalidation_conditions",
        )
    )
    control = _control(frame, capabilities=("market_data",))
    context = build_episode_context(
        frame,
        task_id="adapter-repair-deadline",
        capabilities=control.capabilities,
        tier="deep",
        timeout=120.0,
    )
    base_evidence = AgentEvidence(
        tool="market_data",
        title="市场结构",
        detail="上涨家数修复",
        source="本地行情",
        source_date="2026-07-26",
        content_hash="deadline-evidence-1",
        supports=("direct_assessment",),
        independent_key="market",
    )
    added_evidence = replace(
        base_evidence,
        tool="news_search",
        title="补充线索",
        content_hash="deadline-evidence-2",
        independent_key="news",
        supports=("invalidation_conditions",),
    )
    initial_events = (
        EpisodeEvent(1, "task", {"task_frame_hash": frame.task_frame_hash}),
        EpisodeEvent(2, "model_turn", {"task_frame_hash": frame.task_frame_hash}),
    )
    initial = AgentOutcome(
        task_frame_hash=frame.task_frame_hash,
        status="partial",
        draft="当前偏修复，反方仍缺。",
        evidence=(base_evidence,),
        traces=(),
        gaps=("counterpoint",),
        stop_reason="model_finish",
        events=initial_events,
        bindings=(
            OutputEvidenceBinding("direct_assessment", (base_evidence.content_hash,)),
            OutputEvidenceBinding("counterpoint", (), "缺少反方证据"),
            OutputEvidenceBinding("invalidation_conditions", (), "缺少失效条件"),
        ),
        usage=AgentUsage(1, 1, 0),
    )
    exhausted = replace(
        initial,
        evidence=(base_evidence, added_evidence),
        bindings=(
            OutputEvidenceBinding("direct_assessment", (base_evidence.content_hash,)),
            OutputEvidenceBinding("counterpoint", (), "缺少反方证据"),
            OutputEvidenceBinding(
                "invalidation_conditions",
                (added_evidence.content_hash,),
            ),
        ),
        stop_reason="repair_deadline_exhausted",
        events=(
            *initial_events,
            EpisodeEvent(3, "model_turn", {"task_frame_hash": frame.task_frame_hash}),
        ),
        usage=AgentUsage(2, 2, 0),
    )
    resume_calls = 0

    class Runtime:
        def start(self, _frame, *, context, registry):
            del registry

            def resume(_previous, _goal):
                nonlocal resume_calls
                resume_calls += 1
                if resume_calls > 1:
                    raise AssertionError("deadline stop must terminate repair reentry")
                return exhausted

            return CallbackEpisodeSession(
                episode_id=context.contract.task_id,
                outcome=initial,
                resume_callback=resume,
            )

    class Semantic:
        def __init__(self) -> None:
            self.calls = 0

        def verify(self, *, frame, structurally_verified, deadline):
            del frame, deadline
            self.calls += 1
            return SemanticEpisodeOutcome(
                verified=structurally_verified,
                status="partial",
                public_answer="修复额度耗尽，反方仍缺。",
                judge_status="passed",
            )

    semantic = Semantic()
    result = ContinuousTurnAdapter(
        runtime=Runtime(),
        semantic_verifier=semantic,
        runtime_name="continuous_glm",
        mode="on",
        context_factory=lambda *_args, **_kwargs: context,
        registry_factory=lambda *_args, **_kwargs: "registry",
    ).handle(frame=frame, control=control)

    assert result.status in {"partial", "degraded"}
    assert resume_calls == 1
    assert semantic.calls == 1
    assert result.private_artifact["repair_cycles"] == 0
    assert result.private_artifact["semantic_verifier_stale"] is False


def test_episode_deadline_expiry_still_uses_root_semantic_reserve() -> None:
    frame = _frame()
    control = _control(frame)
    base_context = build_episode_context(
        frame,
        task_id="adapter-root-semantic-reserve",
        capabilities=control.capabilities,
        timeout=60.0,
    )

    class ExpiredEpisodeDeadline:
        synthesis_reserve = 0.0

        @property
        def expired(self) -> bool:
            return True

        def remaining(self) -> float:
            return 0.0

    context = replace(base_context, deadline=ExpiredEpisodeDeadline())
    evidence = AgentEvidence(
        tool="market_data",
        title="市场结构",
        detail="上涨家数修复",
        source="本地行情",
        source_date="2026-07-26",
        content_hash="root-reserve-evidence",
        supports=("direct_assessment",),
        independent_key="market",
    )
    outcome = AgentOutcome(
        task_frame_hash=frame.task_frame_hash,
        status="completed",
        draft="当前偏修复。",
        evidence=(evidence,),
        traces=(),
        gaps=(),
        stop_reason="model_finish",
        events=(EpisodeEvent(1, "task", {"task_frame_hash": frame.task_frame_hash}),),
        bindings=(OutputEvidenceBinding("direct_assessment", (evidence.content_hash,)),),
        usage=AgentUsage(1, 1, 0),
    )

    class Runtime:
        def run(self, *, task_frame, context, registry):
            del task_frame, context, registry
            return outcome

    class Semantic:
        calls = 0

        def verify(self, *, frame, structurally_verified, deadline):
            del frame
            self.calls += 1
            assert deadline.remaining() > 0
            return SemanticEpisodeOutcome(
                verified=structurally_verified,
                status="completed",
                public_answer=structurally_verified.outcome.draft,
                judge_status="passed",
            )

    semantic = Semantic()
    result = ContinuousTurnAdapter(
        runtime=Runtime(),
        semantic_verifier=semantic,
        runtime_name="continuous_glm",
        mode="on",
        context_factory=lambda *_args, **_kwargs: context,
        registry_factory=lambda *_args, **_kwargs: "registry",
        timeout=60.0,
        verification_reserve=15.0,
    ).handle(frame=frame, control=control)

    assert result.status == "completed"
    assert semantic.calls == 1


def test_root_deadline_expiry_prevents_semantic_verification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame = _frame()
    control = _control(frame)
    context = build_episode_context(
        frame,
        task_id="adapter-expired-root-deadline",
        capabilities=control.capabilities,
        timeout=60.0,
    )
    evidence = AgentEvidence(
        tool="market_data",
        title="市场结构",
        detail="上涨家数修复",
        source="本地行情",
        source_date="2026-07-26",
        content_hash="expired-root-evidence",
        supports=("direct_assessment",),
        independent_key="market",
    )
    outcome = AgentOutcome(
        task_frame_hash=frame.task_frame_hash,
        status="completed",
        draft="当前偏修复。",
        evidence=(evidence,),
        traces=(),
        gaps=(),
        stop_reason="model_finish",
        events=(EpisodeEvent(1, "task", {"task_frame_hash": frame.task_frame_hash}),),
        bindings=(OutputEvidenceBinding("direct_assessment", (evidence.content_hash,)),),
        usage=AgentUsage(1, 1, 0),
    )

    class ExpiredRootDeadline:
        @property
        def expired(self) -> bool:
            return True

        def remaining(self) -> float:
            return 0.0

    monkeypatch.setattr(
        adapter_module.ResearchDeadline,
        "from_timeout",
        staticmethod(lambda *_args, **_kwargs: ExpiredRootDeadline()),
    )

    class Runtime:
        def run(self, *, task_frame, context, registry):
            del task_frame, context, registry
            return outcome

    class Semantic:
        def verify(self, **_kwargs):
            raise AssertionError("expired root deadline must skip semantic verification")

    result = ContinuousTurnAdapter(
        runtime=Runtime(),
        semantic_verifier=Semantic(),
        runtime_name="continuous_glm",
        mode="on",
        context_factory=lambda *_args, **_kwargs: context,
        registry_factory=lambda *_args, **_kwargs: "registry",
        timeout=60.0,
    ).handle(frame=frame, control=control)

    assert result.status == "degraded"
    assert result.private_artifact["failure"]["type"] == "TimeoutError"


def test_cancellation_during_repair_prevents_a_second_cycle() -> None:
    frame = _frame(
        required_outputs=(
            "direct_assessment",
            "counterpoint",
            "invalidation_conditions",
        )
    )
    control = _control(frame, capabilities=("market_data",))
    context = build_episode_context(
        frame,
        task_id="adapter-repair-cancelled",
        capabilities=control.capabilities,
        tier="deep",
        timeout=120.0,
    )
    cancelled = Event()
    evidence = AgentEvidence(
        tool="market_data",
        title="市场结构",
        detail="上涨家数修复",
        source="本地行情",
        source_date="2026-07-26",
        content_hash="cancel-repair-evidence",
        supports=("direct_assessment",),
        independent_key="market",
    )
    initial_events = (
        EpisodeEvent(1, "task", {"task_frame_hash": frame.task_frame_hash}),
        EpisodeEvent(2, "model_turn", {"task_frame_hash": frame.task_frame_hash}),
    )
    initial = AgentOutcome(
        task_frame_hash=frame.task_frame_hash,
        status="partial",
        draft="当前偏修复，反方仍缺。",
        evidence=(evidence,),
        traces=(),
        gaps=("counterpoint",),
        stop_reason="model_finish",
        events=initial_events,
        bindings=(
            OutputEvidenceBinding("direct_assessment", (evidence.content_hash,)),
            OutputEvidenceBinding("counterpoint", (), "缺少反方证据"),
            OutputEvidenceBinding("invalidation_conditions", (), "缺少失效条件"),
        ),
        usage=AgentUsage(1, 1, 0),
    )
    added_evidence = replace(
        evidence,
        tool="news_search",
        title="补充线索",
        content_hash="cancel-repair-evidence-2",
        independent_key="news",
        supports=("invalidation_conditions",),
    )
    repaired = replace(
        initial,
        evidence=(evidence, added_evidence),
        bindings=(
            OutputEvidenceBinding("direct_assessment", (evidence.content_hash,)),
            OutputEvidenceBinding("counterpoint", (), "缺少反方证据"),
            OutputEvidenceBinding(
                "invalidation_conditions",
                (added_evidence.content_hash,),
            ),
        ),
        events=(
            *initial_events,
            EpisodeEvent(3, "model_turn", {"task_frame_hash": frame.task_frame_hash}),
        ),
        usage=AgentUsage(2, 1, 0),
    )
    resume_calls = 0

    class Runtime:
        def start(self, _frame, *, context, registry):
            del registry

            def resume(_previous, _goal):
                nonlocal resume_calls
                resume_calls += 1
                cancelled.set()
                if resume_calls > 1:
                    raise AssertionError("cancelled repair must not reenter")
                return repaired

            return CallbackEpisodeSession(
                episode_id=context.contract.task_id,
                outcome=initial,
                resume_callback=resume,
            )

    result = ContinuousTurnAdapter(
        runtime=Runtime(),
        semantic_verifier=_SemanticThatRaises(),
        runtime_name="continuous_glm",
        mode="on",
        context_factory=lambda *_args, **_kwargs: context,
        registry_factory=lambda *_args, **_kwargs: "registry",
        is_cancelled=cancelled.is_set,
    ).handle(frame=frame, control=control)

    assert result.status == "failed"
    assert result.private_artifact is None
    assert resume_calls == 1


def test_private_artifact_records_runtime_backend_without_public_leak() -> None:
    evidence = AgentEvidence(
        tool="market_data",
        title="市场状态",
        detail="指数处于反弹修复",
        source="市场快照",
        source_date="2026-07-24",
        content_hash="runtime-identity-evidence",
    )

    result = _scripted_episode_result(
        semantic_status="completed",
        public_answer="当前更接近短周期修复。",
        evidence=(evidence,),
        bindings=(
            OutputEvidenceBinding(
                "direct_assessment",
                (evidence.content_hash,),
            ),
        ),
        runtime_name="sdk_glm",
    )

    assert result.private_artifact is not None
    assert result.private_artifact["runtime_backend"] == "sdk_glm"
    assert "sdk_glm" not in result.answer
    assert result.llm_provider == "zhipu"


def test_sdk_gpt_runtime_reports_openai_provider_without_model_turn_event() -> None:
    evidence = AgentEvidence(
        tool="market_data",
        title="市场状态",
        detail="指数处于反弹修复",
        source="市场快照",
        source_date="2026-07-24",
        content_hash="sdk-gpt-provider-evidence",
    )

    result = _scripted_episode_result(
        semantic_status="completed",
        public_answer="当前更接近短周期修复。",
        evidence=(evidence,),
        bindings=(
            OutputEvidenceBinding(
                "direct_assessment",
                (evidence.content_hash,),
            ),
        ),
        runtime_name="sdk_gpt",
    )

    assert result.llm_provider == "openai"


def test_semantic_gap_output_does_not_project_its_citation_or_as_of() -> None:
    assessment = AgentEvidence(
        tool="market_data",
        title="市场状态",
        detail="指数处于反弹修复",
        source="市场快照",
        source_date="2026-07-23",
        content_hash="assessment-evidence",
    )
    invalidation = AgentEvidence(
        tool="market_data",
        title="失效阈值",
        detail="未经核验的失效阈值",
        source="阈值快照",
        source_date="2026-07-24",
        content_hash="invalidation-evidence",
    )

    result = _scripted_episode_result(
        semantic_status="partial",
        judge_status="repaired",
        public_answer=(
            "预计本轮反弹还能持续1-3个交易日。"
            "证据缺口：失效条件中的未核验阈值已删除。"
        ),
        evidence=(assessment, invalidation),
        bindings=(
            OutputEvidenceBinding(
                "direct_assessment",
                (assessment.content_hash,),
            ),
            OutputEvidenceBinding(
                "invalidation_conditions",
                (invalidation.content_hash,),
            ),
        ),
        required_outputs=("direct_assessment", "invalidation_conditions"),
        gap_output_ids=("invalidation_conditions",),
    )

    assert result.status == "partial"
    assert result.citations == (
        {
            "title": "市场状态",
            "source": "市场快照",
            "date": "2026-07-23",
        },
    )
    assert result.as_of == "2026-07-23"


def test_gap_only_semantic_result_has_no_citation_or_as_of_fallback() -> None:
    evidence = AgentEvidence(
        tool="market_data",
        title="已删除判断的行情",
        detail="只绑定到已转为缺口的判断",
        source="市场快照",
        source_date="2026-07-24",
        content_hash="gap-only-evidence",
    )

    result = _scripted_episode_result(
        semantic_status="partial",
        judge_status="repaired",
        public_answer="证据缺口：直接判断中的未核验表述已删除。",
        evidence=(evidence,),
        bindings=(
            OutputEvidenceBinding(
                "direct_assessment",
                (evidence.content_hash,),
            ),
        ),
        gap_output_ids=("direct_assessment",),
        latest_data_date="2026-07-24",
    )

    assert result.status == "partial"
    assert result.citations == ()
    assert result.as_of is None


def test_off_mode_always_declines_without_running_anything() -> None:
    frame = _frame()

    result = ContinuousTurnAdapter(
        runtime=_RuntimeThatRaises(),
        mode="off",
        context_factory=_raises,
        registry_factory=_raises,
        fast_path_runner=_raises,
        structural_verifier=_raises,
        semantic_verifier=_SemanticThatRaises(),
    ).handle(frame=frame, control=_control(frame))

    assert result.handled is False
    assert result.answer == ""
    assert result.private_artifact is None


def test_constructor_requires_callable_semantic_verifier() -> None:
    with pytest.raises(TypeError):
        ContinuousTurnAdapter(runtime=_RuntimeThatRaises())

    with pytest.raises(TypeError, match="semantic verifier.*verify"):
        ContinuousTurnAdapter(
            runtime=_RuntimeThatRaises(),
            semantic_verifier=None,
        )

    with pytest.raises(TypeError, match="semantic verifier.*verify"):
        ContinuousTurnAdapter(
            runtime=_RuntimeThatRaises(),
            semantic_verifier=object(),
        )


def test_cross_frame_control_fails_closed_before_any_dependency() -> None:
    market_frame = _frame()
    financial_frame = TaskFrame(
        raw_question="瑞华泰最新财报怎么看",
        user_goal="分析瑞华泰最新财务表现",
        question_type="financial_analysis",
        subject="瑞华泰",
        subject_kind="company",
        market_scope="A股",
        timeframe="最新报告期",
        required_outputs=(
            "financial_assessment",
            "metric_evidence",
            "counterpoint",
        ),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="company_financial_evidence",
        confidence=0.95,
    )
    financial_control = _control(
        financial_frame,
        capabilities=("evidence_lookup", "l3_lookup"),
    )
    dependency_calls: list[str] = []

    def forbidden(name):
        def call(*_args, **_kwargs):
            dependency_calls.append(name)
            raise AssertionError(f"{name} must not be called")

        return call

    class Runtime:
        run = forbidden("runtime")

    class Semantic:
        verify = forbidden("semantic")

    result = ContinuousTurnAdapter(
        runtime=Runtime(),
        mode="on",
        context_factory=forbidden("context"),
        registry_factory=forbidden("registry"),
        fast_path_runner=forbidden("fast_path"),
        structural_verifier=forbidden("structural"),
        semantic_verifier=Semantic(),
    ).handle(frame=market_frame, control=financial_control)

    assert dependency_calls == []
    assert result.handled is True
    assert result.status == "failed"
    assert result.answer == ""
    assert result.private_artifact == {
        "schema_version": 1,
        "execution_kind": "continuous_episode",
        "runtime_backend": "continuous_glm",
        "failure": {"code": "control_frame_mismatch"},
    }
    assert result.events[-1]["status"] == "failed"
    public = str(
        {
            "answer": result.answer,
            "citations": result.citations,
            "warnings": result.warnings,
            "events": result.events,
        }
    )
    assert market_frame.task_frame_hash not in public
    assert financial_frame.task_frame_hash not in public


def test_clarification_returns_without_registry_model_or_retrieval() -> None:
    frame = _frame(clarification_question="你希望按 A 股还是美股判断？")
    control = _control(
        frame,
        terminal_kind="clarification",
        capabilities=(),
        clarification_questions=("你希望按 A 股还是美股判断？",),
    )

    result = ContinuousTurnAdapter(
        runtime=_RuntimeThatRaises(),
        mode="on",
        context_factory=_raises,
        registry_factory=_raises,
        fast_path_runner=_raises,
        structural_verifier=_raises,
        semantic_verifier=_SemanticThatRaises(),
    ).handle(frame=frame, control=control)

    assert result.handled is True
    assert result.status == "completed"
    assert result.answer == "你希望按 A 股还是美股判断？"
    assert result.citations == ()


def test_market_technical_uses_zero_llm_fast_path() -> None:
    frame = _frame(
        question_type="market_technical",
        required_outputs=("technical_levels", "invalidation_conditions", "data_date"),
    )
    calls: list[str] = []

    def run_fast_path(_frame, *, timeout):
        del timeout
        calls.append("fast_path")
        assert _frame is frame
        return {
            "execution_kind": "deterministic_fast_path",
            "status": "completed",
            "answer": "截至 2026-07-22，科创50上方压力区为 1100~1120。",
            "as_of": "2026-07-22",
            "gaps": [],
            "traces": [
                {
                    "provider": "RAW_PROVIDER_SENTINEL",
                    "capability": "market_data",
                    "status": "success",
                    "source_trade_date": "2026-07-22",
                }
            ],
            "llm_calls": 0,
            "tool_calls": 1,
        }

    result = ContinuousTurnAdapter(
        runtime=_RuntimeThatRaises(),
        mode="on",
        context_factory=_raises,
        registry_factory=_raises,
        fast_path_runner=run_fast_path,
        structural_verifier=_raises,
        semantic_verifier=_SemanticThatRaises(),
    ).handle(frame=frame, control=_control(frame))

    assert calls == ["fast_path"]
    assert result.handled is True
    assert result.status == "completed"
    assert result.as_of == "2026-07-22"
    assert result.private_artifact is not None
    assert result.private_artifact["outcome"]["llm_calls"] == 0
    assert result.private_artifact["metrics"] == {
        "provider_attempts": 0,
        "tool_calls": 1,
        "duplicate_queries": 0,
        "structural_status": "completed",
        "semantic_status": "passed",
    }
    assert "RAW_PROVIDER_SENTINEL" not in str(result.events)


@pytest.mark.parametrize(
    "question_type",
    ("external_market", "quick_fact", "dated_market_review"),
)
def test_legacy_deterministic_owner_types_are_declined_without_dependencies(
    question_type: str,
) -> None:
    frame = _frame(question_type=question_type)
    calls: list[str] = []

    def forbidden(name):
        def call(*_args, **_kwargs):
            calls.append(name)
            raise AssertionError(f"{name} must not be called")

        return call

    class Runtime:
        run = forbidden("runtime")

    class Semantic:
        verify = forbidden("semantic")

    result = ContinuousTurnAdapter(
        runtime=Runtime(),
        mode="on",
        context_factory=forbidden("context"),
        registry_factory=forbidden("registry"),
        fast_path_runner=forbidden("fast_path"),
        structural_verifier=forbidden("structural"),
        semantic_verifier=Semantic(),
    ).handle(frame=frame, control=_control(frame))

    assert calls == []
    assert result.handled is False
    assert result.answer == ""
    assert result.private_artifact is None
    assert "支撑位或压力位" not in result.answer


def test_market_technical_gap_hides_provider_diagnostic() -> None:
    frame = _frame(
        question_type="market_technical",
        required_outputs=("technical_levels", "invalidation_conditions", "data_date"),
    )

    result = ContinuousTurnAdapter(
        runtime=_RuntimeThatRaises(),
        semantic_verifier=_SemanticThatRaises(),
        mode="on",
        fast_path_runner=lambda *_args, **_kwargs: {
            "status": "partial",
            "answer": "缺口原因：provider_unsupported。",
            "llm_calls": 0,
            "tool_calls": 1,
            "traces": [],
        },
    ).handle(frame=frame, control=_control(frame))

    assert result.status == "degraded"
    assert "provider" not in result.answer.casefold()
    assert "暂不能可靠给出支撑位或压力位" in result.answer


def test_market_technical_as_of_uses_only_valid_iso_dates() -> None:
    frame = _frame(
        question_type="market_technical",
        required_outputs=("technical_levels", "invalidation_conditions", "data_date"),
    )

    result = ContinuousTurnAdapter(
        runtime=_RuntimeThatRaises(),
        semantic_verifier=_SemanticThatRaises(),
        mode="on",
        fast_path_runner=lambda *_args, **_kwargs: {
            "status": "completed",
            "answer": "科创50支撑区间为 980~1000。",
            "as_of": "Authorization: Bearer private-date-token",
            "llm_calls": 0,
            "tool_calls": 1,
            "traces": [
                {"source_trade_date": "2026-02-30"},
                {"source_trade_date": "2026-07-21"},
                {"source_trade_date": "2026-07-22"},
            ],
        },
    ).handle(frame=frame, control=_control(frame))

    assert result.status == "completed"
    assert result.as_of == "2026-07-22"
    assert "private-date-token" not in str(result)


def test_long_tail_runs_gates_without_calling_legacy_presenter(
    monkeypatch,
) -> None:
    frame = _frame()
    control = _control(frame)
    context = build_episode_context(
        frame,
        task_id="adapter-order",
        capabilities=control.capabilities,
        timeout=30.0,
    )
    evidence = AgentEvidence(
        tool="market_data",
        title="A股市场总览",
        detail="上涨家数增加，成交保持活跃",
        source="本地行情",
        internal_locator="/private/market/window.json",
        source_date="2026-07-22",
        evidence_tier="L4",
        content_hash="PRIVATE_HASH_SENTINEL",
    )
    outcome = AgentOutcome(
        task_frame_hash=frame.task_frame_hash,
        status="completed",
        draft="当前更接近条件化修复，持续性取决于量能。",
        evidence=(evidence,),
        traces=(),
        gaps=(),
        stop_reason="model_finish",
        events=(
            EpisodeEvent(
                1,
                "task",
                {"task_frame_hash": frame.task_frame_hash},
            ),
        ),
        bindings=(
            OutputEvidenceBinding("direct_assessment", ("PRIVATE_HASH_SENTINEL",)),
        ),
        usage=AgentUsage(llm_calls=2, tool_calls=1),
    )
    calls: list[str] = []
    presenter_calls: list[str] = []

    def legacy_presenter(*_args, **_kwargs):
        presenter_calls.append("legacy_presenter")
        raise AssertionError("Episode-owned answer must not enter legacy presenter")

    monkeypatch.setattr(
        ask_synthesis,
        "synthesize_prepared_answer",
        legacy_presenter,
    )

    class Runtime:
        def run(self, *, task_frame, context, registry):
            calls.append("runtime")
            assert task_frame is frame
            assert context is not None
            assert registry == "registry"
            return outcome

    def structural(contract, candidate):
        calls.append("structural")
        assert contract is context.contract
        assert candidate is outcome
        return verify_episode_outcome(contract, candidate)

    class Semantic:
        def verify(self, *, frame, structurally_verified, deadline):
            calls.append("semantic")
            assert frame is not None
            assert isinstance(structurally_verified, VerifiedEpisodeOutcome)
            assert deadline.remaining() > context.deadline.remaining()
            return SemanticEpisodeOutcome(
                verified=structurally_verified,
                status="completed",
                public_answer="当前更接近条件化修复，持续性取决于量能。",
                judge_status="passed",
            )

    result = ContinuousTurnAdapter(
        runtime=Runtime(),
        mode="on",
        context_factory=lambda *_args, **_kwargs: context,
        registry_factory=lambda *_args, **_kwargs: "registry",
        structural_verifier=structural,
        semantic_verifier=Semantic(),
    ).handle(frame=frame, control=control)

    assert calls == ["runtime", "structural", "semantic"]
    assert presenter_calls == []
    assert result.status == "completed"
    assert result.answer.startswith("当前更接近条件化修复")
    assert result.citations == (
        {
            "title": "A股市场总览",
            "source": "本地行情",
            "date": "2026-07-22",
        },
    )
    assert result.private_artifact is not None
    assert result.private_artifact["outcome"]["draft"].startswith("当前更接近")
    assert (
        result.private_artifact["outcome"]["evidence"][0]["internal_locator"]
        == "/private/market/window.json"
    )
    assert result.private_artifact["events"] == [
        {
            "sequence": 1,
            "kind": "task",
            "payload": {"task_frame_hash": frame.task_frame_hash},
        }
    ]
    assert result.private_artifact["traces"] == []
    assert "structural_verifier" in result.private_artifact
    assert "semantic_verifier" in result.private_artifact
    assert "PRIVATE_HASH_SENTINEL" not in str(result.events)


def test_episode_reserves_root_deadline_for_semantic_verification() -> None:
    frame = _frame()
    control = _control(frame)
    captured: dict[str, float] = {}

    def context_factory(candidate, **kwargs):
        captured["runtime_timeout"] = float(kwargs["timeout"])
        captured["synthesis_reserve"] = float(kwargs["synthesis_reserve"])
        return build_episode_context(candidate, **kwargs)

    class Runtime:
        def run(self, *, task_frame, context, registry):
            del registry
            evidence = AgentEvidence(
                tool="market_data",
                title="A股市场总览",
                detail="市场结构已更新",
                source="本地行情",
                source_date="2026-07-22",
                content_hash="deadline-reserve-evidence",
            )
            return AgentOutcome(
                task_frame_hash=task_frame.task_frame_hash,
                status="completed",
                draft="当前市场结构已更新。",
                evidence=(evidence,),
                traces=(),
                gaps=(),
                stop_reason="model_finish",
                events=(
                    EpisodeEvent(
                        1,
                        "task",
                        {"task_frame_hash": task_frame.task_frame_hash},
                    ),
                ),
                bindings=(
                    OutputEvidenceBinding(
                        "direct_assessment",
                        ("deadline-reserve-evidence",),
                    ),
                ),
                usage=AgentUsage(llm_calls=1, tool_calls=1),
            )

    class Semantic:
        def verify(self, *, structurally_verified, deadline, **_kwargs):
            captured["semantic_remaining"] = deadline.remaining()
            return SemanticEpisodeOutcome(
                verified=structurally_verified,
                status="completed",
                public_answer="当前市场结构已更新。",
                judge_status="passed",
            )

    result = ContinuousTurnAdapter(
        runtime=Runtime(),
        semantic_verifier=Semantic(),
        mode="on",
        context_factory=context_factory,
        registry_factory=lambda *_args, **_kwargs: "registry",
        synthesis_reserve_for_task=(
            lambda *, tier, question_type: (
                60.0
                if tier == "standard" and question_type == "market_forecast"
                else 0.0
            )
        ),
        timeout=120.0,
        verification_reserve=30.0,
    ).handle(frame=frame, control=control)

    assert result.status == "completed"
    assert captured["runtime_timeout"] == pytest.approx(90.0, abs=0.1)
    assert captured["synthesis_reserve"] == 60.0
    assert captured["semantic_remaining"] > 119.0


def test_default_episode_budget_leaves_judge_timeout_plus_transport_grace() -> None:
    """Slow OpenAI-compatible transports must not consume the judge reserve."""

    frame = _frame()
    control = _control(frame)
    captured: dict[str, float] = {}

    def context_factory(candidate, **kwargs):
        captured["runtime_timeout"] = float(kwargs["timeout"])
        return build_episode_context(candidate, **kwargs)

    class Runtime:
        def run(self, *, task_frame, context, registry):
            del context, registry
            evidence = AgentEvidence(
                tool="market_data",
                title="A股市场总览",
                detail="市场结构已更新",
                source="本地行情",
                source_date="2026-07-22",
                content_hash="default-deadline-reserve-evidence",
            )
            return AgentOutcome(
                task_frame_hash=task_frame.task_frame_hash,
                status="completed",
                draft="当前市场结构已更新。",
                evidence=(evidence,),
                traces=(),
                gaps=(),
                stop_reason="model_finish",
                events=(
                    EpisodeEvent(
                        1,
                        "task",
                        {"task_frame_hash": task_frame.task_frame_hash},
                    ),
                ),
                bindings=(
                    OutputEvidenceBinding(
                        "direct_assessment",
                        ("default-deadline-reserve-evidence",),
                    ),
                ),
                usage=AgentUsage(llm_calls=1, tool_calls=1),
            )

    class Semantic:
        def verify(self, *, structurally_verified, **_kwargs):
            return SemanticEpisodeOutcome(
                verified=structurally_verified,
                status="completed",
                public_answer="当前市场结构已更新。",
                judge_status="passed",
            )

    result = ContinuousTurnAdapter(
        runtime=Runtime(),
        semantic_verifier=Semantic(),
        mode="on",
        context_factory=context_factory,
        registry_factory=lambda *_args, **_kwargs: "registry",
        timeout=120.0,
    ).handle(frame=frame, control=control)

    assert result.status == "completed", result.private_artifact
    assert captured["runtime_timeout"] <= (
        120.0 - DEFAULT_JUDGE_TIMEOUT_SECONDS - 10.0 + 0.1
    )


def test_private_artifact_counts_physical_attempts_and_duplicate_queries() -> None:
    frame = _frame()
    control = _control(frame)
    context = build_episode_context(
        frame,
        task_id="adapter-physical-metrics",
        capabilities=control.capabilities,
        timeout=30.0,
    )
    evidence = AgentEvidence(
        tool="market_data",
        title="A股市场总览",
        detail="上涨家数增加，成交保持活跃",
        source="本地行情",
        source_date="2026-07-22",
        content_hash="physical-metrics-evidence",
    )
    outcome = AgentOutcome(
        task_frame_hash=frame.task_frame_hash,
        status="completed",
        draft="当前更接近条件化修复。",
        evidence=(evidence,),
        traces=(),
        gaps=(),
        stop_reason="model_finish",
        events=(
            EpisodeEvent(
                1,
                "task",
                {"task_frame_hash": frame.task_frame_hash},
            ),
            EpisodeEvent(
                2,
                "tool_error",
                {"error": "duplicate_query"},
            ),
        ),
        bindings=(
            OutputEvidenceBinding(
                "direct_assessment",
                ("physical-metrics-evidence",),
            ),
        ),
        usage=AgentUsage(llm_calls=2, tool_calls=1),
    )

    def record_provider_attempt(caller: str) -> None:
        ledger = llm_refine.current_call_ledger()
        assert ledger is not None
        ledger.record(
            llm_refine.LLMCallRecord(
                caller=caller,
                provider="test-provider",
                model="test-model",
                status="success",
                elapsed_ms=1,
            )
        )

    class Runtime:
        def run(self, **_kwargs):
            record_provider_attempt("chat_tools")
            record_provider_attempt("chat_tools")
            return outcome

    class Semantic:
        def verify(self, *, structurally_verified, **_kwargs):
            record_provider_attempt("chat")
            return SemanticEpisodeOutcome(
                verified=structurally_verified,
                status="completed",
                public_answer="当前更接近条件化修复。",
                judge_status="passed",
            )

    with llm_refine.call_ledger_scope():
        result = ContinuousTurnAdapter(
            runtime=Runtime(),
            semantic_verifier=Semantic(),
            mode="on",
            context_factory=lambda *_args, **_kwargs: context,
            registry_factory=lambda *_args, **_kwargs: "registry",
        ).handle(frame=frame, control=control)

    assert result.status == "completed"
    assert result.private_artifact is not None
    assert result.private_artifact["metrics"] == {
        "provider_attempts": 3,
        "tool_calls": 1,
        "duplicate_queries": 1,
        "structural_status": "completed",
        "semantic_status": "passed",
    }


def test_structural_verifier_failure_degrades_from_bound_runtime_evidence() -> None:
    frame = _frame()
    control = _control(frame)
    context = build_episode_context(
        frame,
        task_id="adapter-structural-failure",
        capabilities=control.capabilities,
        timeout=30.0,
        latest_data_date="2026-07-20",
    )
    evidence = AgentEvidence(
        tool="market_data",
        title="A股市场总览",
        detail="上涨家数增加，成交保持活跃",
        source="本地行情",
        source_date="2026-07-22",
        content_hash="structural-failure-evidence",
    )
    outcome = AgentOutcome(
        task_frame_hash=frame.task_frame_hash,
        status="completed",
        draft="当前更接近条件化修复。",
        evidence=(evidence,),
        traces=(),
        gaps=(),
        stop_reason="model_finish",
        events=(
            EpisodeEvent(
                1,
                "task",
                {"task_frame_hash": frame.task_frame_hash},
            ),
        ),
        bindings=(
            OutputEvidenceBinding(
                "direct_assessment",
                ("structural-failure-evidence",),
            ),
        ),
        usage=AgentUsage(llm_calls=1, tool_calls=1),
    )

    class Runtime:
        def run(self, **_kwargs):
            return outcome

    class Semantic:
        def verify(self, **_kwargs):
            raise AssertionError("semantic verifier must not run")

    def structural(*_args, **_kwargs):
        raise RuntimeError("structural verifier unavailable")

    result = ContinuousTurnAdapter(
        runtime=Runtime(),
        semantic_verifier=Semantic(),
        mode="on",
        context_factory=lambda *_args, **_kwargs: context,
        registry_factory=lambda *_args, **_kwargs: "registry",
        structural_verifier=structural,
    ).handle(frame=frame, control=control)

    assert result.status == "degraded"
    assert result.answer
    assert "A股市场" in result.answer
    assert "直接回答用户问题" in result.answer
    assert result.as_of is None
    assert result.citations == ()
    assert result.private_artifact is not None
    assert result.private_artifact["failure"]["type"] == "RuntimeError"
    assert result.private_artifact["outcome"]["draft"]
    assert "structural_verifier" in result.private_artifact


def test_semantic_verifier_failure_reuses_structural_contract_and_evidence() -> None:
    frame = _frame()
    control = _control(frame)
    context = build_episode_context(
        frame,
        task_id="adapter-semantic-failure",
        capabilities=control.capabilities,
        timeout=30.0,
        latest_data_date="2026-07-20",
    )
    evidence = AgentEvidence(
        tool="market_data",
        title="市场量能窗口",
        detail="量能较前一交易日增加",
        source="本地行情",
        source_date="2026-07-21",
        content_hash="semantic-failure-evidence",
    )
    outcome = AgentOutcome(
        task_frame_hash=frame.task_frame_hash,
        status="completed",
        draft="当前量能支持修复，但持续性待验证。",
        evidence=(evidence,),
        traces=(),
        gaps=(),
        stop_reason="model_finish",
        events=(
            EpisodeEvent(
                1,
                "task",
                {"task_frame_hash": frame.task_frame_hash},
            ),
        ),
        bindings=(
            OutputEvidenceBinding(
                "direct_assessment",
                ("semantic-failure-evidence",),
            ),
        ),
        usage=AgentUsage(llm_calls=1, tool_calls=1),
    )

    class Runtime:
        def run(self, **_kwargs):
            return outcome

    class Semantic:
        def verify(self, **_kwargs):
            raise TimeoutError("semantic verifier timed out")

    result = ContinuousTurnAdapter(
        runtime=Runtime(),
        semantic_verifier=Semantic(),
        mode="on",
        context_factory=lambda *_args, **_kwargs: context,
        registry_factory=lambda *_args, **_kwargs: "registry",
    ).handle(frame=frame, control=control)

    assert result.status == "degraded"
    assert "A股市场" in result.answer
    assert "直接回答用户问题" in result.answer
    assert result.as_of == "2026-07-21"
    assert result.citations == (
        {
            "title": "市场量能窗口",
            "source": "本地行情",
            "date": "2026-07-21",
        },
    )
    assert result.private_artifact is not None
    assert result.private_artifact["failure"]["type"] == "TimeoutError"
    assert result.private_artifact["outcome"]["draft"]
    assert result.private_artifact["structural_verifier"]["verified_status"] == (
        "completed"
    )


def test_valuation_contract_requires_current_anchor_scenarios_and_assumptions() -> None:
    frame = TaskFrame(
        raw_question="瑞华泰的合理估值是多少",
        user_goal="估算瑞华泰当前合理估值区间",
        question_type="valuation_estimate",
        subject="瑞华泰",
        subject_kind="company",
        market_scope="A股",
        timeframe="当前",
        required_outputs=(
            "valuation_assessment",
            "scenario_range",
            "evidence_boundary",
        ),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="company_valuation_evidence",
        confidence=0.95,
    )
    control = _control(frame, capabilities=("evidence_lookup",))
    captured: dict[str, object] = {}

    class InspectingRuntime:
        def run(self, *, task_frame, context, registry):
            del task_frame, registry
            captured["contract"] = context.contract
            raise RuntimeError("stop after inspecting the contract")

    result = ContinuousTurnAdapter(
        runtime=InspectingRuntime(),
        semantic_verifier=_SemanticThatRaises(),
        mode="on",
        registry_factory=lambda *_args, **_kwargs: "registry",
    ).handle(frame=frame, control=control)

    assert result.status == "failed"
    contract = captured["contract"]
    outputs = {item.output_id: item.description for item in contract.required_outputs}
    assert {
        "valuation_assessment",
        "financial_business_anchor",
        "scenario_range",
        "evidence_boundary",
        "invalidation_conditions",
    }.issubset(outputs)
    assert "当前市场锚点" in outputs["valuation_assessment"]
    assert "方法" in outputs["valuation_assessment"]
    assert "假设" in outputs["valuation_assessment"]
    assert "market_data" in contract.allowed_capabilities
    assert "financial_data" in contract.allowed_capabilities
    assert set(contract.evidence_plan.mandatory_capabilities) == {
        "market_data",
        "financial_data",
    }
    financial_anchor = next(
        item
        for item in contract.required_outputs
        if item.output_id == "financial_business_anchor"
    )
    assert financial_anchor.evidence_types[0] == "financial_data"
    assert "evidence_lookup" in financial_anchor.evidence_types
    assert "market_data" not in financial_anchor.evidence_types
    assert "web_search" not in financial_anchor.evidence_types


def test_semantically_verified_partial_is_first_class_not_degraded() -> None:
    evidence = AgentEvidence(
        tool="market_data",
        title="A股市场总览",
        detail="当前数据只覆盖最近交易日",
        source="本地行情",
        source_date="2026-07-22",
        content_hash="market-gap-1",
    )

    result = _scripted_episode_result(
        semantic_status="partial",
        public_answer="现有证据只支持最近交易日，持续性仍需补量能验证。",
        evidence=(evidence,),
        bindings=(OutputEvidenceBinding("direct_assessment", ("market-gap-1",)),),
        judge_status="repaired",
    )

    assert result.status == "partial"
    assert "持续性仍需补量能验证" in result.answer
    assert result.warnings == ()


def test_structural_partial_artifact_exports_missing_output_reasons() -> None:
    result = _scripted_episode_result(
        semantic_status="partial",
        public_answer="现有证据不足以完成直接判断。",
        evidence=(),
        bindings=(
            OutputEvidenceBinding(
                "direct_assessment",
                (),
                gap="仍缺同一窗口的结构化市场数据",
            ),
        ),
        outcome_status="partial",
        draft="现有证据不足以完成直接判断。",
        judge_status="passed",
    )

    assert result.private_artifact is not None
    assert result.private_artifact["metrics"]["structural_status"] == "partial"
    structural = result.private_artifact["structural_verifier"]
    assert structural["missing_outputs"] == ["direct_assessment"]
    assert structural["completion"]["outputs"][0]["gap"] == (
        "仍缺同一窗口的结构化市场数据"
    )


def test_no_answer_and_no_evidence_returns_failed() -> None:
    result = _scripted_episode_result(
        semantic_status="failed",
        public_answer="",
        evidence=(),
        bindings=(
            OutputEvidenceBinding(
                "direct_assessment",
                (),
                gap="仍缺最新市场证据",
            ),
        ),
        outcome_status="failed",
        draft="",
    )

    assert result.status == "failed"
    assert result.answer == ""
    assert result.citations == ()


def test_public_projection_hides_control_plane_fields_and_private_tokens() -> None:
    evidence = AgentEvidence(
        tool="market_data",
        title="A股市场总览",
        detail="上涨家数增加",
        source="本地行情",
        source_date="2026-07-22",
        content_hash="PRIVATE_HASH_SENTINEL",
    )
    trace = ProviderTrace(
        provider="RAW_PROVIDER_SENTINEL",
        capability="market_data",
        status="success",
        result_count=1,
    )

    result = _scripted_episode_result(
        semantic_status="completed",
        public_answer=(
            "可公开结论。\n"
            "content_hash=PRIVATE_HASH_SENTINEL\n"
            "provider=RAW_PROVIDER_SENTINEL\n"
            "system_prompt=PRIVATE_PROMPT_SENTINEL\n"
            "market_data"
        ),
        evidence=(evidence,),
        bindings=(
            OutputEvidenceBinding("direct_assessment", ("PRIVATE_HASH_SENTINEL",)),
        ),
        traces=(trace,),
        draft="api_key=sk-abcdefghijk",
    )

    public_payload = {
        "answer": result.answer,
        "citations": result.citations,
        "warnings": result.warnings,
        "events": result.events,
    }
    assert result.answer == "可公开结论。"
    for sentinel in (
        "PRIVATE_HASH_SENTINEL",
        "RAW_PROVIDER_SENTINEL",
        "PRIVATE_PROMPT_SENTINEL",
        "market_data",
    ):
        assert sentinel not in str(public_payload)
    assert result.private_artifact is not None
    assert "sk-abcdefghijk" not in str(result.private_artifact)
    assert "[REDACTED]" in str(result.private_artifact)


def test_public_projection_removes_engineering_hash_keys_and_frame_hash() -> None:
    actual_frame_hash = _frame().task_frame_hash
    safe = AgentEvidence(
        tool="market_data",
        title="A股市场总览",
        detail="上涨家数增加",
        source="本地行情",
        source_date="2026-07-22",
        content_hash="safe-citation-1",
    )
    poisoned_title = AgentEvidence(
        tool="market_data",
        title="task_frame_hash=abc123",
        detail="控制面字段不得公开",
        source="公开来源",
        source_date="2026-07-22",
        content_hash="poison-title-1",
    )
    poisoned_source = AgentEvidence(
        tool="market_data",
        title="估值材料",
        detail="控制面字段不得公开",
        source="hash=OTHER_HASH",
        source_date="2026-07-22",
        content_hash="poison-source-1",
    )

    result = _scripted_episode_result(
        semantic_status="completed",
        public_answer=(
            "可公开结论。\n"
            "task_frame_hash=abc123\n"
            "hash=OTHER_HASH\n"
            "任务帧哈希：中文控制值\n"
            f"{actual_frame_hash}"
        ),
        evidence=(safe, poisoned_title, poisoned_source),
        bindings=(
            OutputEvidenceBinding(
                "direct_assessment",
                ("safe-citation-1", "poison-title-1", "poison-source-1"),
            ),
        ),
    )

    assert result.answer == "可公开结论。"
    assert result.citations == (
        {
            "title": "A股市场总览",
            "source": "本地行情",
            "date": "2026-07-22",
        },
    )
    public = str(
        {
            "answer": result.answer,
            "citations": result.citations,
            "warnings": result.warnings,
            "events": result.events,
        }
    )
    for sentinel in (
        "task_frame_hash",
        "OTHER_HASH",
        "任务帧哈希",
        actual_frame_hash,
    ):
        assert sentinel not in public


def test_public_projection_preserves_financial_hash_rate_language() -> None:
    evidence = AgentEvidence(
        tool="market_data",
        title="比特币哈希率月报",
        detail="全网哈希率环比上升 8%",
        source="公开矿业数据",
        source_date="2026-07-22",
        content_hash="hash-rate-evidence-1",
    )

    result = _scripted_episode_result(
        semantic_status="completed",
        public_answer="比特币网络哈希率上升 8%，矿工收入仍取决于币价与难度。",
        evidence=(evidence,),
        bindings=(
            OutputEvidenceBinding(
                "direct_assessment",
                ("hash-rate-evidence-1",),
            ),
        ),
    )

    assert result.status == "completed"
    assert "哈希率上升 8%" in result.answer
    assert result.citations == (
        {
            "title": "比特币哈希率月报",
            "source": "公开矿业数据",
            "date": "2026-07-22",
        },
    )


def test_public_projection_preserves_business_provider_language_only() -> None:
    evidence = AgentEvidence(
        tool="market_data",
        title="Cloud service provider 行业月报",
        detail="云基础设施需求同比增长",
        source="Cloud service provider 行业协会",
        source_date="2026-07-22",
        content_hash="provider-business-evidence",
    )

    result = _scripted_episode_result(
        semantic_status="completed",
        public_answer=(
            "Cloud service provider 行业需求保持增长。\n"
            "provider=glm\n"
            "provider_trace: retry\n"
            "provider_attempts=2\n"
            "endpoint=https://private.invalid"
        ),
        evidence=(evidence,),
        bindings=(
            OutputEvidenceBinding(
                "direct_assessment",
                ("provider-business-evidence",),
            ),
        ),
    )

    assert result.answer == "Cloud service provider 行业需求保持增长。"
    assert result.citations == (
        {
            "title": "Cloud service provider 行业月报",
            "source": "Cloud service provider 行业协会",
            "date": "2026-07-22",
        },
    )
    public = str((result.answer, result.citations))
    for control_key in (
        "provider=",
        "provider_trace",
        "provider_attempts",
        "endpoint=",
    ):
        assert control_key not in public


def test_public_projection_preserves_business_name_equal_to_trace_provider() -> None:
    evidence = AgentEvidence(
        tool="market_data",
        title="OpenAI 行业跟踪",
        detail="企业级需求保持增长",
        source="OpenAI 公开材料",
        source_date="2026-07-22",
        content_hash="openai-business-evidence",
    )

    result = _scripted_episode_result(
        semantic_status="completed",
        public_answer="OpenAI 是本轮研究主体，Cloud service provider 需求仍在增长。",
        evidence=(evidence,),
        bindings=(
            OutputEvidenceBinding(
                "direct_assessment",
                ("openai-business-evidence",),
            ),
        ),
        traces=(
            ProviderTrace(
                provider="openai",
                capability="llm",
                status="success",
            ),
        ),
    )

    assert "OpenAI 是本轮研究主体" in result.answer
    assert result.citations == (
        {
            "title": "OpenAI 行业跟踪",
            "source": "OpenAI 公开材料",
            "date": "2026-07-22",
        },
    )


def test_public_and_private_projection_remove_complete_secret_values() -> None:
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhYmMifQ.jwtSignature123"
    secrets = (
        "public-auth-token-123",
        jwt,
        "public-api-key-123",
        "public-token-123",
        "private-auth-token-123",
        "private-api-key-123",
        "private-keyed-token-123",
    )
    evidence = AgentEvidence(
        tool="market_data",
        title="A股市场总览",
        detail=(f"Authorization: Bearer {secrets[4]}\napi_key={secrets[5]}"),
        source="本地行情",
        source_date="2026-07-22",
        content_hash="secret-redaction-evidence",
    )

    result = _scripted_episode_result(
        semantic_status="completed",
        public_answer=(
            "可公开结论。\n"
            f"Authorization: Bearer {secrets[0]}\n"
            f"Bearer {secrets[1]}\n"
            f"api_key={secrets[2]}\n"
            f"token={secrets[3]}"
        ),
        evidence=(evidence,),
        bindings=(
            OutputEvidenceBinding(
                "direct_assessment",
                ("secret-redaction-evidence",),
            ),
        ),
        draft=(f"Authorization: Bearer {secrets[4]}\napi_key={secrets[5]}"),
        event_payload={
            "task_frame_hash": _frame().task_frame_hash,
            "token": secrets[6],
        },
    )

    assert result.answer == "可公开结论。"
    public = str((result.answer, result.citations, result.warnings, result.events))
    private = str(result.private_artifact)
    for secret in secrets:
        assert secret not in public
        assert secret not in private


def test_episode_as_of_uses_only_bound_valid_iso_evidence_dates() -> None:
    evidence = (
        AgentEvidence(
            tool="market_data",
            title="绑定行情",
            detail="有效绑定日期",
            source="本地行情",
            source_date="2026-07-20",
            content_hash="bound-valid-date",
        ),
        AgentEvidence(
            tool="market_data",
            title="未绑定未来材料",
            detail="不得影响 as_of",
            source="外部材料",
            source_date="2099-12-31",
            content_hash="unbound-future-date",
        ),
        AgentEvidence(
            tool="market_data",
            title="绑定非法日期",
            detail="不得影响 as_of",
            source="错误材料",
            source_date="2026-02-30",
            content_hash="bound-invalid-date",
        ),
    )

    result = _scripted_episode_result(
        semantic_status="completed",
        public_answer="当前结论仅截至已绑定的有效行情日。",
        evidence=evidence,
        bindings=(
            OutputEvidenceBinding(
                "direct_assessment",
                ("bound-valid-date", "bound-invalid-date"),
            ),
        ),
        latest_data_date="2026-07-19",
    )

    assert result.as_of == "2026-07-20"


def test_episode_as_of_falls_back_when_bound_dates_are_invalid() -> None:
    evidence = AgentEvidence(
        tool="market_data",
        title="日期异常材料",
        detail="日期无法解析",
        source="本地行情",
        source_date="not-an-iso-date",
        content_hash="bound-invalid-only",
    )

    result = _scripted_episode_result(
        semantic_status="completed",
        public_answer="当前结论按上下文最新日期展示。",
        evidence=(evidence,),
        bindings=(
            OutputEvidenceBinding(
                "direct_assessment",
                ("bound-invalid-only",),
            ),
        ),
        latest_data_date="2026-07-18",
    )

    assert result.as_of == "2026-07-18"


def test_same_frame_uses_a_unique_default_task_id_for_each_turn() -> None:
    frame = _frame()
    control = _control(frame)
    task_ids: list[str] = []

    def context_factory(candidate, **kwargs):
        task_ids.append(kwargs["task_id"])
        return build_episode_context(candidate, **kwargs)

    adapter = ContinuousTurnAdapter(
        runtime=_RuntimeThatRaises(),
        semantic_verifier=_SemanticThatRaises(),
        mode="on",
        context_factory=context_factory,
        registry_factory=lambda *_args, **_kwargs: "registry",
    )

    first = adapter.handle(frame=frame, control=control)
    second = adapter.handle(frame=frame, control=control)

    assert first.status == "failed"
    assert second.status == "failed"
    assert len(task_ids) == 2
    assert task_ids[0] != task_ids[1]
    assert all(str(UUID(task_id)) == task_id for task_id in task_ids)
    assert all(frame.task_frame_hash not in task_id for task_id in task_ids)


def test_task_id_factory_can_inject_the_real_turn_identity() -> None:
    frame = _frame()
    captured: list[str] = []

    def context_factory(candidate, **kwargs):
        captured.append(kwargs["task_id"])
        return build_episode_context(candidate, **kwargs)

    result = ContinuousTurnAdapter(
        runtime=_RuntimeThatRaises(),
        semantic_verifier=_SemanticThatRaises(),
        mode="on",
        context_factory=context_factory,
        registry_factory=lambda *_args, **_kwargs: "registry",
        task_id_factory=lambda: "turn-run-identity-42",
    ).handle(frame=frame, control=_control(frame))

    assert result.status == "failed"
    assert captured == ["turn-run-identity-42"]


@pytest.mark.parametrize("bad_stage", ("runtime", "structural"))
def test_wrong_dependency_result_type_fails_closed_without_secondary_exception(
    bad_stage: str,
) -> None:
    frame = _frame()
    control = _control(frame)
    context = build_episode_context(
        frame,
        task_id="bad-result-type",
        capabilities=control.capabilities,
        timeout=30.0,
    )
    valid_outcome = AgentOutcome(
        task_frame_hash=frame.task_frame_hash,
        status="failed",
        draft="",
        evidence=(),
        traces=(),
        gaps=(),
        stop_reason="invalid_fixture",
        events=(
            EpisodeEvent(
                1,
                "task",
                {"task_frame_hash": frame.task_frame_hash},
            ),
        ),
        bindings=(),
        usage=AgentUsage(),
    )

    class Runtime:
        def run(self, **_kwargs):
            return object() if bad_stage == "runtime" else valid_outcome

    def structural(*_args, **_kwargs):
        return object() if bad_stage == "structural" else _args[-1]

    result = ContinuousTurnAdapter(
        runtime=Runtime(),
        semantic_verifier=_SemanticThatRaises(),
        mode="on",
        context_factory=lambda *_args, **_kwargs: context,
        registry_factory=lambda *_args, **_kwargs: "registry",
        structural_verifier=structural,
    ).handle(frame=frame, control=control)

    assert result.status == "failed"
    assert result.answer == ""
    assert result.private_artifact is not None
    assert result.private_artifact["failure"]["type"] == "TypeError"


def test_verification_failure_gap_passes_through_public_sanitizer() -> None:
    frame = _frame()
    control = _control(frame)
    base_context = build_episode_context(
        frame,
        task_id="unsafe-contract-gap",
        capabilities=control.capabilities,
        timeout=30.0,
    )
    unsafe_contract = replace(
        base_context.contract,
        required_outputs=(
            RequiredOutput(
                "unsafe_gap",
                "api_key=LEAK_SENTINEL",
                ("market_data",),
                True,
            ),
        ),
    )
    context = replace(
        base_context,
        contract=unsafe_contract,
    )
    evidence = AgentEvidence(
        tool="market_data",
        title="安全标题",
        detail="安全证据",
        source="本地行情",
        source_date="2026-07-22",
        content_hash="safe-gap-evidence",
    )
    outcome = AgentOutcome(
        task_frame_hash=frame.task_frame_hash,
        status="completed",
        draft="候选结论",
        evidence=(evidence,),
        traces=(),
        gaps=(),
        stop_reason="model_finish",
        events=(
            EpisodeEvent(
                1,
                "task",
                {"task_frame_hash": frame.task_frame_hash},
            ),
        ),
        bindings=(OutputEvidenceBinding("unsafe_gap", ("safe-gap-evidence",)),),
        usage=AgentUsage(llm_calls=1, tool_calls=1),
    )

    class Runtime:
        def run(self, **_kwargs):
            return outcome

    class Semantic:
        def verify(self, **_kwargs):
            raise TimeoutError("judge timeout")

    result = ContinuousTurnAdapter(
        runtime=Runtime(),
        semantic_verifier=Semantic(),
        mode="on",
        context_factory=lambda *_args, **_kwargs: context,
        registry_factory=lambda *_args, **_kwargs: "registry",
    ).handle(frame=frame, control=control)

    assert result.status == "degraded"
    assert result.answer
    assert "LEAK_SENTINEL" not in result.answer
    assert "api_key" not in result.answer


def test_structural_hash_mismatch_never_projects_cross_task_evidence() -> None:
    frame = _frame()
    control = _control(frame)
    context = build_episode_context(
        frame,
        task_id="cross-task-outcome",
        capabilities=control.capabilities,
        timeout=30.0,
        latest_data_date="2026-07-22",
    )
    evidence = AgentEvidence(
        tool="market_data",
        title="另一任务材料",
        detail="不得进入公共投影",
        source="wrong source",
        source_date="2099-12-31",
        content_hash="cross-task-evidence",
    )
    outcome = AgentOutcome(
        task_frame_hash="f" * 64,
        status="completed",
        draft="另一任务的结论",
        evidence=(evidence,),
        traces=(),
        gaps=(),
        stop_reason="model_finish",
        events=(
            EpisodeEvent(
                1,
                "task",
                {"task_frame_hash": "f" * 64},
            ),
        ),
        bindings=(
            OutputEvidenceBinding(
                "direct_assessment",
                ("cross-task-evidence",),
            ),
        ),
        usage=AgentUsage(llm_calls=1, tool_calls=1),
    )

    class Runtime:
        def run(self, **_kwargs):
            return outcome

    result = ContinuousTurnAdapter(
        runtime=Runtime(),
        semantic_verifier=_SemanticThatRaises(),
        mode="on",
        context_factory=lambda *_args, **_kwargs: context,
        registry_factory=lambda *_args, **_kwargs: "registry",
    ).handle(frame=frame, control=control)

    assert result.status == "degraded"
    assert result.answer
    assert result.as_of is None
    assert result.citations == ()
    public = str((result.answer, result.as_of, result.citations, result.events))
    assert "另一任务材料" not in public
    assert "wrong source" not in public
    assert "2099-12-31" not in public
    assert result.private_artifact is not None
    assert "另一任务材料" in str(result.private_artifact)


@pytest.mark.parametrize("invalid_kind", ("unknown_binding", "wrong_evidence_type"))
def test_structurally_invalid_bindings_never_project_public_evidence(
    invalid_kind: str,
) -> None:
    frame = _frame()
    control = _control(frame)
    base_context = build_episode_context(
        frame,
        task_id=f"invalid-binding:{invalid_kind}",
        capabilities=control.capabilities,
        timeout=30.0,
        latest_data_date="2026-07-22",
    )
    context = replace(
        base_context,
        contract=replace(
            base_context.contract,
            required_outputs=(
                RequiredOutput(
                    "direct_assessment",
                    "直接判断",
                    ("market_data",),
                    True,
                ),
            ),
        ),
    )
    evidence = AgentEvidence(
        tool="kb_search" if invalid_kind == "wrong_evidence_type" else "market_data",
        title="无效绑定材料",
        detail="不得进入公共引用",
        source="invalid source",
        source_date="2099-12-31",
        content_hash=f"invalid-binding-{invalid_kind}",
    )
    binding_output_id = (
        "unknown_output" if invalid_kind == "unknown_binding" else "direct_assessment"
    )
    outcome = AgentOutcome(
        task_frame_hash=frame.task_frame_hash,
        status="completed",
        draft="无效绑定结论",
        evidence=(evidence,),
        traces=(),
        gaps=(),
        stop_reason="model_finish",
        events=(
            EpisodeEvent(
                1,
                "task",
                {"task_frame_hash": frame.task_frame_hash},
            ),
        ),
        bindings=(
            OutputEvidenceBinding(
                binding_output_id,
                (evidence.content_hash,),
            ),
        ),
        usage=AgentUsage(llm_calls=1, tool_calls=1),
    )

    class Runtime:
        def run(self, **_kwargs):
            return outcome

    class Semantic:
        def verify(self, **_kwargs):
            raise TimeoutError("semantic verifier unavailable")

    result = ContinuousTurnAdapter(
        runtime=Runtime(),
        semantic_verifier=Semantic(),
        mode="on",
        context_factory=lambda *_args, **_kwargs: context,
        registry_factory=lambda *_args, **_kwargs: "registry",
    ).handle(frame=frame, control=control)

    assert result.status == "degraded"
    assert result.citations == ()
    assert result.as_of is None
    public = str((result.answer, result.as_of, result.citations, result.events))
    assert "无效绑定材料" not in public
    assert "invalid source" not in public
    assert "2099-12-31" not in public


def test_foreign_structural_contract_never_contaminates_public_gap() -> None:
    frame = _frame()
    control = _control(frame)
    context = build_episode_context(
        frame,
        task_id="current-contract-gap",
        capabilities=control.capabilities,
        timeout=30.0,
    )
    evidence = AgentEvidence(
        tool="market_data",
        title="当前任务候选材料",
        detail="只用于触发证据保留降级",
        source="本地行情",
        source_date="2026-07-22",
        content_hash="current-contract-evidence",
    )
    outcome = AgentOutcome(
        task_frame_hash=frame.task_frame_hash,
        status="completed",
        draft="当前任务候选结论",
        evidence=(evidence,),
        traces=(),
        gaps=(),
        stop_reason="model_finish",
        events=(
            EpisodeEvent(
                1,
                "task",
                {"task_frame_hash": frame.task_frame_hash},
            ),
        ),
        bindings=(
            OutputEvidenceBinding(
                "direct_assessment",
                ("current-contract-evidence",),
            ),
        ),
        usage=AgentUsage(llm_calls=1, tool_calls=1),
    )
    foreign_frame = replace(
        frame,
        raw_question="白酒的另一任务怎么看",
        user_goal="判断白酒",
        subject="白酒",
    )
    foreign_context = build_episode_context(
        foreign_frame,
        task_id="foreign-contract-gap",
        capabilities=control.capabilities,
        timeout=30.0,
    )
    foreign_contract = replace(
        foreign_context.contract,
        required_outputs=(
            RequiredOutput(
                "foreign_output",
                "另一任务白酒结论",
                ("market_data",),
                True,
            ),
        ),
    )
    foreign_outcome = AgentOutcome(
        task_frame_hash=foreign_frame.task_frame_hash,
        status="partial",
        draft="",
        evidence=(),
        traces=(),
        gaps=("缺少白酒证据",),
        stop_reason="evidence_gap",
        events=(
            EpisodeEvent(
                1,
                "task",
                {"task_frame_hash": foreign_frame.task_frame_hash},
            ),
        ),
        bindings=(),
        usage=AgentUsage(),
    )
    foreign_structural = verify_episode_outcome(
        foreign_contract,
        foreign_outcome,
    )

    class Runtime:
        def run(self, **_kwargs):
            return outcome

    class Semantic:
        def verify(self, **_kwargs):
            raise TimeoutError("semantic verifier unavailable")

    result = ContinuousTurnAdapter(
        runtime=Runtime(),
        semantic_verifier=Semantic(),
        mode="on",
        context_factory=lambda *_args, **_kwargs: context,
        registry_factory=lambda *_args, **_kwargs: "registry",
        structural_verifier=lambda *_args, **_kwargs: foreign_structural,
    ).handle(frame=frame, control=control)

    assert result.status == "degraded"
    assert result.answer
    assert "另一任务白酒结论" not in result.answer
    assert "白酒" not in result.answer
    assert "直接回答用户问题" in result.answer
    assert result.citations == ()
    assert result.as_of is None


def test_canary_requires_isolated_runtime_identifier(
    monkeypatch,
) -> None:
    monkeypatch.setenv("ASK_CONTINUOUS_RUNTIME", "canary")
    monkeypatch.delenv("CONTINUOUS_RUNTIME_CANARY_ID", raising=False)
    frame = _frame()

    result = ContinuousTurnAdapter(
        runtime=_RuntimeThatRaises(),
        semantic_verifier=_SemanticThatRaises(),
        mode="canary",
    ).handle(frame=frame, control=_control(frame))

    assert result.handled is False
    assert result.answer == ""


def test_canary_handles_only_with_matching_environment_and_identifier(
    monkeypatch,
) -> None:
    frame = _frame(clarification_question="请确认市场。")
    control = _control(
        frame,
        terminal_kind="clarification",
        capabilities=(),
        clarification_questions=("请确认市场。",),
    )
    monkeypatch.setenv("CONTINUOUS_RUNTIME_CANARY_ID", "candidate-sha")
    monkeypatch.setenv("ASK_CONTINUOUS_RUNTIME", "off")

    mismatched = ContinuousTurnAdapter(
        runtime=_RuntimeThatRaises(),
        semantic_verifier=_SemanticThatRaises(),
        mode="canary",
    ).handle(frame=frame, control=control)

    assert mismatched.handled is False

    monkeypatch.setenv("ASK_CONTINUOUS_RUNTIME", "canary")
    adapter = ContinuousTurnAdapter(
        runtime=_RuntimeThatRaises(),
        semantic_verifier=_SemanticThatRaises(),
    )
    handled = adapter.handle(frame=frame, control=control)

    assert adapter.mode == "canary"
    assert adapter.canary_id == "candidate-sha"
    assert handled.handled is True
    assert handled.answer == "请确认市场。"
