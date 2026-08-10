from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
from threading import Event, Lock

import pytest

import intelligence.runtime.agent_episode as agent_episode_module
import intelligence.runtime.episode_tool_batch as episode_tool_batch_module
import intelligence.services.research_contract as research_contract_module
from intelligence.runtime.agent_episode import ContinuousAgentEpisode
from intelligence.runtime.glm_agent_runtime import GLMAgentRuntime
from intelligence.services.agent_research import AgentEvidence, AgentToolContext
from intelligence.services.agent_runtime import (
    ModelToolCall,
    ModelTurn,
)
from intelligence.services.evidence_capabilities import EvidencePlan
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.mode_governor import ModeSignals
from intelligence.services.repair_coordinator import CoverageDelta, RepairGoal
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
from intelligence.runtime.sub_research import BranchResult, SubResearchResult
from intelligence.services.task_frame import TaskFrame


def _plan_turn(*, revision: int = 1, **overrides: object) -> ModelTurn:
    payload: dict[str, object] = {
        "kind": "PLAN",
        "task_summary": "判断市场主线并给出反方",
        "answer_elements": ["direct_assessment", "counterpoint"],
        "hypotheses": ["半导体可能是持续主线"],
        "evidence_needs": ["同日主线与持续性"],
        "candidate_actions": ["market_data"],
        "open_gaps": ["缺少反方证据"],
        "requested_mode": "quick",
        "revision": revision,
    }
    payload.update(overrides)
    return ModelTurn(json.dumps(payload, ensure_ascii=False), (), "scripted", "")


class ScriptedModel:
    def __init__(self, turns: list[ModelTurn | Exception]) -> None:
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
        effect = next(self._turns)
        if isinstance(effect, Exception):
            raise effect
        return effect


def _frame(required_outputs: tuple[str, ...] = ("direct_assessment",)) -> TaskFrame:
    return TaskFrame(
        raw_question="目前市场怎么看",
        user_goal="判断当前市场结构",
        question_type="market_forecast",
        subject="A股市场",
        subject_kind="market_pattern",
        market_scope="A股",
        timeframe="最近交易日",
        required_outputs=required_outputs,
        assumptions=("按A股市场理解",),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="current_market_scenarios",
        confidence=0.95,
    )


def _context(
    frame: TaskFrame,
    *,
    max_steps: int = 3,
    allowed_capabilities: tuple[str, ...] = ("market_data",),
) -> ResearchRunContext:
    contract = ResearchTaskContract(
        task_id="episode-test",
        question=frame.raw_question,
        subject=frame.subject,
        subject_kind=frame.subject_kind,
        question_type=frame.question_type,
        required_outputs=tuple(
            RequiredOutput(item, item, ("market_data",), True)
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
        trace_parent_id="episode-test",
        today="2026-07-22",
        latest_data_date="2026-07-21",
    )


def _market_registry(runner) -> ResearchToolRegistry:
    return ResearchToolRegistry(
        (
            ToolSpec(
                name="market_data",
                capability="market_data",
                description="结构化行情与市场时序",
                cost="local",
                freshness="current",
                runner=runner,
            ),
        )
    )


def _successful_runner(
    query: str,
    _context: AgentToolContext,
):
    evidence = AgentEvidence(
        tool="market_data",
        title="A股市场总览",
        detail=f"{query}：上涨家数增加，成交保持活跃",
        source="本地行情",
        source_date="2026-07-21",
        evidence_tier="L4",
        content_hash="evidence-1",
    )
    return (
        [evidence],
        "raw market observation",
        ProviderTrace(
            provider="test:market",
            capability="market_data",
            status="success",
            source_trade_date="2026-07-21",
            result_count=1,
        ),
    )


def _tool_turn(
    query: str, *, call_id: str = "call-1", name: str = "market_data"
) -> ModelTurn:
    return ModelTurn(
        "",
        (ModelToolCall(call_id, name, {"query": query}),),
        "scripted",
        "",
    )


def test_cancellation_after_model_turn_prevents_tool_execution() -> None:
    cancelled = Event()
    runner_calls = 0

    class CancellingModel:
        def complete(self, *, messages, tools, timeout):
            del messages, tools, timeout
            cancelled.set()
            return _tool_turn("不应执行")

    def runner(query: str, context: AgentToolContext):
        del query, context
        nonlocal runner_calls
        runner_calls += 1
        raise AssertionError("cancelled episode must not execute tools")

    frame = _frame()
    outcome = ContinuousAgentEpisode(
        CancellingModel(),
        is_cancelled=cancelled.is_set,
    ).run(
        task_frame=frame,
        context=_context(frame),
        registry=_market_registry(runner),
    )

    assert outcome.status == "failed"
    assert outcome.stop_reason == "cancelled"
    assert outcome.usage.llm_calls == 1
    assert outcome.usage.tool_calls == 0
    assert runner_calls == 0


def _finish_turn(
    *,
    status: str = "completed",
    draft: str = "当前更接近条件化修复，持续性取决于量能。",
    hashes: tuple[str, ...] = ("evidence-1",),
    gap: str = "",
) -> ModelTurn:
    return ModelTurn(
        json.dumps(
            {
                "status": status,
                "draft": draft,
                "gaps": [gap] if gap else [],
                "bindings": [
                    {
                        "output_id": "direct_assessment",
                        "evidence_hashes": list(hashes),
                        "gap": gap,
                    }
                ],
            },
            ensure_ascii=False,
        ),
        (),
        "scripted",
        "",
    )


def test_progress_sink_observes_append_only_events_before_and_during_model_work() -> None:
    observed = []

    class ProgressAwareModel(ScriptedModel):
        def complete(self, *, messages, tools, timeout):
            if not self.calls:
                assert [event.kind for event in observed] == ["task"]
            return super().complete(messages=messages, tools=tools, timeout=timeout)

    frame = _frame()
    model = ProgressAwareModel(
        [
            _plan_turn(),
            _tool_turn("当前市场结构"),
            _finish_turn(),
        ]
    )

    outcome = ContinuousAgentEpisode(model, event_sink=observed.append).run(
        task_frame=frame,
        context=_context(frame),
        registry=_market_registry(_successful_runner),
    )

    assert outcome.status == "completed"
    observed_kinds = [event.kind for event in observed]
    assert observed_kinds == [event.kind for event in outcome.events]
    assert observed_kinds.index("plan") < observed_kinds.index("tool_request")
    assert observed_kinds.index("tool_request") < observed_kinds.index("tool_result")
    assert observed_kinds.index("tool_result") < observed_kinds.index("finish")


def test_glm_episode_session_resume_keeps_original_model_history() -> None:
    frame = _frame()
    context = _context(frame, max_steps=1, allowed_capabilities=())
    model = ScriptedModel(
        [
            _finish_turn(status="partial", hashes=(), gap="缺少行情证据"),
            _finish_turn(status="partial", hashes=(), gap="仍缺少行情证据"),
        ]
    )
    observed = []
    runtime = GLMAgentRuntime(client=model, event_sink=observed.append)

    session = runtime.start(
        frame,
        context=context,
        registry=ResearchToolRegistry(()),
    )
    before_events = session.outcome.events
    updated = session.resume(
        RepairGoal(
            episode_id=context.contract.task_id,
            repair_goal_id="repair-episode-test-1",
            cycle=1,
            missing_answer_elements=("direct_assessment",),
            unsupported_claims=(),
            missing_evidence_modes=(),
            attempted_actions=(),
            evidence_progress=CoverageDelta(1, 0, 1),
            remaining_calls=1,
            remaining_seconds=8.0,
        )
    )

    assert updated.events[: len(before_events)] == before_events
    assert any(event.kind == "model_turn" for event in updated.events[len(before_events) :])
    assert updated.status == "partial"
    assert updated.stop_reason == "repair_model_stop"
    second_messages = model.calls[1]["messages"]
    assert any("缺少行情证据" in str(message.get("content")) for message in second_messages)
    assert any("repair-episode-test-1" in str(message.get("content")) for message in second_messages)
    observed_kinds = [event.kind for event in observed]
    assert "repair_goal" in observed_kinds
    assert "repair_reentry" in observed_kinds


def test_glm_resume_uses_existing_evidence_after_research_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A closed research window forbids tools, not a bounded wording repair."""

    clock = {"now": 0.0}
    monkeypatch.setattr(
        research_contract_module.time,
        "monotonic",
        lambda: clock["now"],
    )
    monkeypatch.setattr(
        agent_episode_module,
        "monotonic",
        lambda: clock["now"],
    )
    frame = _frame()
    base_context = _context(frame, max_steps=1)
    root_budget = InMemoryRootBudgetLedger(
        episode_id=base_context.contract.task_id,
        initial_calls=2,
        hard_calls_cap=4,
        initial_seconds=20.0,
        hard_seconds_cap=30.0,
    )
    context = replace(base_context, root_budget=root_budget)
    model = ScriptedModel(
        [
            _plan_turn(answer_elements=["direct_assessment"]),
            _tool_turn("当前市场结构"),
            _finish_turn(draft="本轮反弹可以持续，因为风险偏好已经全面回升。"),
            _finish_turn(draft="当前更像阶段性修复，持续性仍取决于量能。"),
        ]
    )
    session = GLMAgentRuntime(client=model).start(
        frame,
        context=context,
        registry=_market_registry(_successful_runner),
    )
    clock["now"] = 31.0

    updated = session.resume(
        RepairGoal(
            episode_id=context.contract.task_id,
            repair_goal_id="repair-after-research-deadline",
            cycle=1,
            missing_answer_elements=("direct_assessment",),
            unsupported_claims=("claim_index:0",),
            missing_evidence_modes=(),
            attempted_actions=("market_data:test",),
            evidence_progress=CoverageDelta(1, 1, 1),
            remaining_calls=1,
            remaining_seconds=8.0,
        )
    )

    assert updated.status == "completed"
    assert updated.stop_reason == "repair_model_finish"
    assert updated.draft == "当前更像阶段性修复，持续性仍取决于量能。"
    assert model.calls[-1]["tools"] == []
    assert updated.usage.tool_calls == 1


def test_episode_session_resume_bounds_every_action_by_granted_seconds() -> None:
    frame = _frame()
    context = _context(frame, max_steps=1)
    model = ScriptedModel(
        [
            _finish_turn(status="partial", hashes=(), gap="缺少行情证据"),
            _tool_turn("补齐行情证据", call_id="repair-call"),
            _finish_turn(),
        ]
    )
    observed_tool_seconds: list[float] = []

    def bounded_runner(query: str, tool_context: AgentToolContext):
        observed_tool_seconds.append(tool_context.deadline.remaining())
        return _successful_runner(query, tool_context)

    session = GLMAgentRuntime(client=model).start(
        frame,
        context=context,
        registry=_market_registry(bounded_runner),
    )
    updated = session.resume(
        RepairGoal(
            episode_id=context.contract.task_id,
            repair_goal_id="repair-episode-test-budget",
            cycle=1,
            missing_answer_elements=("direct_assessment",),
            unsupported_claims=(),
            missing_evidence_modes=("market_data",),
            attempted_actions=(),
            evidence_progress=CoverageDelta(1, 0, 1),
            remaining_calls=1,
            remaining_seconds=2.5,
        )
    )

    assert updated.stop_reason == "repair_model_finish"
    assert 0.0 < model.calls[1]["timeout"] <= 2.5
    assert observed_tool_seconds and 0.0 < observed_tool_seconds[0] <= 2.5
    assert 0.0 < model.calls[2]["timeout"] <= 2.5


def test_failed_repair_keeps_the_draft_it_was_meant_to_improve() -> None:
    """A repair that dies on the provider must not be worse than no repair.

    2026-08-10 的生产线收据（``judge30-run1/run2``）里 ``draft_chars=0``，但同一条
    trajectory 明确走过 ``finalization -> model_turn -> finish``——草稿是生出来过的，
    是 repair 重入超时后 ``_stopped_outcome`` 用空草稿把它顶掉了，
    ``continuous_turn_adapter`` 又无条件接受了这个更差的结果。

    修复轮是 fix-forward，不是重跑：拿不到更好的答案时，最坏也要保住原来那份。
    """

    frame = _frame(("direct_assessment", "counterpoint"))
    context = _context(frame, max_steps=2)
    model = ScriptedModel(
        [
            _tool_turn("今日市场结构"),
            _finish_turn(status="partial", gap="缺少反方证据"),
            ModelTurn("", (), "scripted", "LLM 调用失败（TimeoutError）"),
        ]
    )
    session = GLMAgentRuntime(client=model).start(
        frame,
        context=context,
        registry=_market_registry(_successful_runner),
    )
    previous_draft = session.outcome.draft
    previous_bindings = session.outcome.bindings
    assert previous_draft.strip(), "前提：这一轮确实产出过草稿"
    assert previous_bindings, "前提：这一轮确实产出过绑定"

    updated = session.resume(
        RepairGoal(
            episode_id=context.contract.task_id,
            repair_goal_id="repair-episode-test-model-error",
            cycle=1,
            missing_answer_elements=("counterpoint",),
            unsupported_claims=(),
            missing_evidence_modes=("market_data",),
            attempted_actions=(),
            evidence_progress=CoverageDelta(1, 0, 1),
            remaining_calls=1,
            remaining_seconds=5.0,
        )
    )

    assert updated.stop_reason == "repair_model_unavailable"
    assert updated.draft == previous_draft
    assert updated.bindings == previous_bindings
    # 失败本身仍要可见，只是不能以丢答案为代价。
    assert any("TimeoutError" in gap for gap in updated.gaps)


def test_episode_session_resume_does_not_dispatch_after_grant_expires(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame = _frame()
    context = _context(frame, max_steps=1)
    now = [context.deadline.expires_at - 29.0]

    def monotonic() -> float:
        return now[0]

    monkeypatch.setattr(agent_episode_module, "monotonic", monotonic)
    monkeypatch.setattr(research_contract_module.time, "monotonic", monotonic)
    calls: list[dict[str, object]] = []

    class OverrunningRepairModel:
        def complete(self, *, messages, tools, timeout):
            calls.append({"messages": messages, "tools": tools, "timeout": timeout})
            if len(calls) == 1:
                return _finish_turn(status="partial", hashes=(), gap="缺少行情证据")
            now[0] += float(timeout) + 0.1
            return _tool_turn("不得执行", call_id="late-repair-call")

    def runner(_query: str, _tool_context: AgentToolContext):
        raise AssertionError("expired repair grant must prevent tool dispatch")

    session = GLMAgentRuntime(client=OverrunningRepairModel()).start(
        frame,
        context=context,
        registry=_market_registry(runner),
    )
    updated = session.resume(
        RepairGoal(
            episode_id=context.contract.task_id,
            repair_goal_id="repair-episode-test-expired-budget",
            cycle=1,
            missing_answer_elements=("direct_assessment",),
            unsupported_claims=(),
            missing_evidence_modes=("market_data",),
            attempted_actions=(),
            evidence_progress=CoverageDelta(1, 0, 1),
            remaining_calls=1,
            remaining_seconds=1.0,
        )
    )

    assert updated.stop_reason == "repair_deadline_exhausted"
    assert updated.usage.tool_calls == 0
    assert len(calls) == 2


def test_episode_session_resume_debits_model_and_tool_wall_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame = _frame()
    base_context = _context(frame, max_steps=1)
    root_budget = InMemoryRootBudgetLedger(
        episode_id=base_context.contract.task_id,
        initial_calls=2,
        hard_calls_cap=4,
        initial_seconds=10.0,
        hard_seconds_cap=20.0,
    )
    context = replace(base_context, root_budget=root_budget)
    now = [context.deadline.expires_at - 29.0]

    def monotonic() -> float:
        return now[0]

    monkeypatch.setattr(agent_episode_module, "monotonic", monotonic)
    monkeypatch.setattr(episode_tool_batch_module, "monotonic", monotonic)
    monkeypatch.setattr(research_contract_module.time, "monotonic", monotonic)
    calls = 0

    class TimedRepairModel:
        def complete(self, *, messages, tools, timeout):
            del messages, tools, timeout
            nonlocal calls
            calls += 1
            if calls == 1:
                return _finish_turn(status="partial", hashes=(), gap="缺少行情证据")
            if calls == 2:
                now[0] += 0.4
                return _tool_turn("补齐行情证据", call_id="timed-repair-call")
            now[0] += 0.6
            return _finish_turn()

    def timed_runner(query: str, tool_context: AgentToolContext):
        now[0] += 0.5
        return _successful_runner(query, tool_context)

    session = GLMAgentRuntime(client=TimedRepairModel()).start(
        frame,
        context=context,
        registry=_market_registry(timed_runner),
    )
    episode_evidence_ledger = session.evidence_ledger
    assert episode_evidence_ledger.snapshot().evidence_ids == ()
    assert session.initial_evidence_snapshot.open_gaps == ("direct_assessment",)
    updated = session.resume(
        RepairGoal(
            episode_id=context.contract.task_id,
            repair_goal_id="repair-episode-test-ledger-time",
            cycle=1,
            missing_answer_elements=("direct_assessment",),
            unsupported_claims=(),
            missing_evidence_modes=("market_data",),
            attempted_actions=(),
            evidence_progress=CoverageDelta(1, 0, 1),
            remaining_calls=1,
            remaining_seconds=2.5,
        )
    )

    assert updated.stop_reason == "repair_model_finish"
    assert session.evidence_ledger is episode_evidence_ledger
    assert episode_evidence_ledger.snapshot().evidence_ids == (
        "evidence-1",
    )
    assert root_budget.remaining_calls == 1
    assert root_budget.remaining_seconds == pytest.approx(8.5)


def test_initial_episode_debits_model_and_tool_wall_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame = _frame()
    base_context = _context(frame, max_steps=1)
    root_budget = InMemoryRootBudgetLedger(
        episode_id=base_context.contract.task_id,
        initial_calls=1,
        hard_calls_cap=1,
        initial_seconds=10.0,
        hard_seconds_cap=10.0,
    )
    context = replace(base_context, root_budget=root_budget)
    now = [context.deadline.expires_at - 29.0]

    def monotonic() -> float:
        return now[0]

    monkeypatch.setattr(agent_episode_module, "monotonic", monotonic)
    monkeypatch.setattr(episode_tool_batch_module, "monotonic", monotonic)
    monkeypatch.setattr(research_contract_module.time, "monotonic", monotonic)
    calls = 0

    class TimedInitialModel:
        def complete(self, *, messages, tools, timeout):
            del messages, tools, timeout
            nonlocal calls
            calls += 1
            if calls == 1:
                now[0] += 0.4
                return _tool_turn("检查行情", call_id="initial-timed-call")
            now[0] += 0.6
            return _finish_turn()

    def timed_runner(query: str, tool_context: AgentToolContext):
        now[0] += 0.5
        return _successful_runner(query, tool_context)

    outcome = GLMAgentRuntime(client=TimedInitialModel()).run(
        task_frame=frame,
        context=context,
        registry=_market_registry(timed_runner),
    )

    assert outcome.status == "completed"
    assert root_budget.remaining_calls == 0
    assert root_budget.remaining_seconds == pytest.approx(8.5)


class _ScriptedDeadline:
    """Deterministic time boundary for recovery cutoff behavior."""

    def __init__(self, stage_timeouts: tuple[float, ...], synthesis: float) -> None:
        self._stage_timeouts = iter(stage_timeouts)
        self._synthesis = synthesis
        self.synthesis_reserve = 0.0

    def stage_timeout(self, configured_limit: float) -> float:
        return min(configured_limit, next(self._stage_timeouts, self._synthesis))

    def synthesis_timeout(self, configured_limit: float) -> float:
        return min(configured_limit, self._synthesis)

    def remaining(self) -> float:
        return self._synthesis

    @property
    def expired(self) -> bool:
        return self._synthesis <= 0.0


class _LateRecoveryDeadline:
    """Keep recovery eligible, then close the deadline before parsing its turn."""

    def __init__(self) -> None:
        self._synthesis_calls = 0
        self.synthesis_reserve = 0.0

    def stage_timeout(self, configured_limit: float) -> float:
        return min(configured_limit, 30.0)

    def synthesis_timeout(self, configured_limit: float) -> float:
        self._synthesis_calls += 1
        remaining = 30.0 if self._synthesis_calls < 4 else 0.0
        return min(configured_limit, remaining)

    def remaining(self) -> float:
        return 30.0 if self._synthesis_calls < 4 else 0.0

    @property
    def expired(self) -> bool:
        return self.remaining() <= 0.0


class _RaisingFinalizer:
    def recover(self, **_kwargs):
        raise RuntimeError("recovery transport unavailable")


def test_second_model_turn_keeps_first_action_and_raw_tool_observation() -> None:
    frame = _frame()
    model = ScriptedModel([_tool_turn("A股 最新行情"), _finish_turn()])

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(frame),
        registry=_market_registry(_successful_runner),
    )

    first_messages = model.calls[0]["messages"]
    second_messages = model.calls[1]["messages"]
    assert second_messages[:2] == first_messages[:2]
    assert second_messages[2]["role"] == "assistant"
    assert second_messages[2]["tool_calls"][0]["function"]["name"] == "market_data"
    assert second_messages[3]["role"] == "tool"
    tool_payload = json.loads(second_messages[3]["content"])
    assert tool_payload["observation"] == "raw market observation"
    assert tool_payload["evidence_hashes"] == ["evidence-1"]
    assert outcome.status == "completed"
    assert outcome.usage.llm_calls == 2
    assert outcome.usage.tool_calls == 1
    assert outcome.evidence[0].content_hash == "evidence-1"
    assert all(
        event.payload["task_frame_hash"] == frame.task_frame_hash
        for event in outcome.events
    )


def test_plan_only_first_turn_is_observable_without_granting_or_using_tools() -> None:
    frame = _frame()
    original_hash = frame.task_frame_hash
    model = ScriptedModel(
        [_plan_turn(), _tool_turn("A股 最新行情"), _finish_turn()]
    )

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(frame),
        registry=_market_registry(_successful_runner),
    )

    assert frame.task_frame_hash == original_hash
    assert outcome.task_frame_hash == original_hash
    assert outcome.plan is not None
    assert outcome.plan.revision == 1
    assert outcome.plan.answer_elements == ("direct_assessment", "counterpoint")
    assert outcome.usage.tool_calls == 1
    assert outcome.usage.invalid_actions == 0
    plan_events = [event for event in outcome.events if event.kind == "plan"]
    assert len(plan_events) == 1
    assert plan_events[0].payload["revision"] == 1


def test_plan_only_turn_does_not_consume_the_first_tool_budget_slot() -> None:
    frame = _frame()
    model = ScriptedModel(
        [_plan_turn(), _tool_turn("A股 最新行情"), _finish_turn()]
    )

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(frame, max_steps=1),
        registry=_market_registry(_successful_runner),
    )

    assert outcome.status == "completed"
    assert outcome.stop_reason == "model_finish"
    assert outcome.usage.tool_calls == 1
    assert len(model.calls) == 3
    assert model.calls[1]["tools"]
    assert model.calls[2]["tools"] == []


def test_latest_valid_plan_revision_is_retained() -> None:
    frame = _frame()
    model = ScriptedModel(
        [_plan_turn(), _plan_turn(revision=2, open_gaps=[]), _finish_turn()]
    )

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(frame),
        registry=_market_registry(_successful_runner),
    )

    assert outcome.plan is not None
    assert outcome.plan.revision == 2
    assert outcome.plan.open_gaps == ()
    assert outcome.usage.tool_calls == 0
    assert [event.kind for event in outcome.events].count("plan") == 2


def test_plan_cannot_authorize_unknown_tool_or_weaken_invalid_action_count() -> None:
    frame = _frame()
    plan_with_call = ModelTurn(
        _plan_turn(candidate_actions=["shell_exec"]).content,
        (ModelToolCall("call-unsafe", "shell_exec", {"query": "do it"}),),
        "scripted",
        "",
    )
    model = ScriptedModel(
        [
            plan_with_call,
            _finish_turn(
                status="partial",
                draft="未执行未授权工具。",
                hashes=(),
                gap="缺少可用证据",
            ),
        ]
    )

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(frame),
        registry=_market_registry(_successful_runner),
    )

    assert outcome.plan is not None
    assert outcome.usage.tool_calls == 0
    assert outcome.usage.invalid_actions == 1
    assert any(event.kind == "tool_error" for event in outcome.events)


def test_malformed_plan_gets_one_same_episode_repair_without_tool_use() -> None:
    frame = _frame()
    model = ScriptedModel(
        [
            _plan_turn(status="completed"),
            _plan_turn(),
            _finish_turn(
                status="partial",
                draft="计划已修复，当前仍缺证据。",
                hashes=(),
                gap="缺少市场证据",
            ),
        ]
    )

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(frame),
        registry=_market_registry(_successful_runner),
    )

    repair_message = model.calls[1]["messages"][-1]
    assert repair_message["role"] == "user"
    assert "PLAN" in repair_message["content"]
    assert outcome.plan is not None
    assert outcome.usage.tool_calls == 0
    assert outcome.usage.invalid_actions == 1


def test_initial_plan_can_express_answer_elements_without_contract_ids() -> None:
    frame = _frame()
    model = ScriptedModel(
        [
            _plan_turn(answer_elements=["当前市场判断", "主要反证"]),
            _finish_turn(
                status="partial",
                draft="当前仍缺市场证据。",
                hashes=(),
                gap="缺少市场证据",
            ),
        ]
    )

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(frame),
        registry=_market_registry(_successful_runner),
    )

    assert outcome.plan is not None
    assert outcome.plan.answer_elements == ("当前市场判断", "主要反证")
    assert outcome.usage.invalid_actions == 0
    assert len(model.calls) == 2


def test_tool_batch_completes_in_reverse_but_returns_original_transcript_order() -> (
    None
):
    first_started = Event()
    second_finished = Event()
    completion_order: list[str] = []
    completion_lock = Lock()

    def result(tool: str, query: str, content_hash: str):
        evidence = AgentEvidence(
            tool=tool,
            title=f"{tool} evidence",
            detail=query,
            source=f"test:{tool}",
            content_hash=content_hash,
        )
        return (
            [evidence],
            f"{tool} observation",
            ProviderTrace(
                provider=f"test:{tool}",
                capability=tool,
                status="success",
                result_count=1,
            ),
        )

    def first_runner(query: str, _context: AgentToolContext):
        first_started.set()
        assert second_finished.wait(timeout=1.0)
        with completion_lock:
            completion_order.append("call-1")
        return result("web_search", query, "web-evidence")

    def second_runner(query: str, _context: AgentToolContext):
        assert first_started.wait(timeout=1.0)
        with completion_lock:
            completion_order.append("call-2")
        second_finished.set()
        return result("market_data", query, "market-evidence")

    registry = ResearchToolRegistry(
        (
            ToolSpec(
                name="web_search",
                capability="web_search",
                description="网页检索",
                cost="external",
                freshness="current",
                runner=first_runner,
            ),
            ToolSpec(
                name="market_data",
                capability="market_data",
                description="结构化行情",
                cost="local",
                freshness="current",
                runner=second_runner,
            ),
        )
    )
    frame = _frame()
    model = ScriptedModel(
        [
            ModelTurn(
                "",
                (
                    ModelToolCall(
                        "call-1",
                        "web_search",
                        {"query": "市场背景"},
                    ),
                    ModelToolCall(
                        "call-2",
                        "market_data",
                        {"query": "市场行情"},
                    ),
                ),
                "scripted",
                "",
            ),
            _finish_turn(hashes=("market-evidence",)),
        ]
    )

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(
            frame,
            allowed_capabilities=("web_search", "market_data"),
        ),
        registry=registry,
    )

    assert completion_order == ["call-2", "call-1"]
    second_messages = model.calls[1]["messages"]
    tool_messages = second_messages[3:5]
    assert [item["tool_call_id"] for item in tool_messages] == [
        "call-1",
        "call-2",
    ]
    assert json.loads(tool_messages[0]["content"])["tool"] == "web_search"
    assert json.loads(tool_messages[1]["content"])["tool"] == "market_data"
    assert [event.sequence for event in outcome.events] == list(
        range(1, len(outcome.events) + 1)
    )
    assert all(
        event.payload["task_frame_hash"] == frame.task_frame_hash
        for event in outcome.events
    )
    assert [
        event.kind
        for event in outcome.events
        if event.kind in {"tool_request", "tool_result", "tool_error"}
    ] == ["tool_request", "tool_result", "tool_request", "tool_result"]


def test_model_contract_separates_output_gaps_from_answer_caveats() -> None:
    frame = _frame()
    model = ScriptedModel(
        [
            _finish_turn(
                status="partial",
                draft="当前证据不足，先说明边界。",
                hashes=(),
                gap="仍缺市场数据",
            )
        ]
    )

    ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(frame),
        registry=_market_registry(_successful_runner),
    )

    system_prompt = model.calls[0]["messages"][0]["content"]
    assert "binding.gap 只在该 required output 无法回答时填写" in system_prompt
    assert "限制条件写入顶层 gaps 或 draft" in system_prompt


def test_model_contract_keeps_compact_reasoning_and_public_boundary_rules() -> None:
    frame = _frame()
    model = ScriptedModel(
        [
            _finish_turn(
                status="partial",
                draft="当前证据不足，先说明边界。",
                hashes=(),
                gap="仍缺市场数据",
            )
        ]
    )

    ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(frame),
        registry=_market_registry(_successful_runner),
    )

    system_prompt = model.calls[0]["messages"][0]["content"]
    assert "观察事实与分析判断分开" in system_prompt
    assert "不得编造精确数值阈值" in system_prompt
    assert "不得在答案中暴露内部工具名、provider 或哈希" in system_prompt
    assert "阶段第N天”只是数据提供方的阶段标签" in system_prompt
    assert "必须给出一个明确标注的基准判断" in system_prompt
    assert "每个精确数字事实" in system_prompt
    assert "每条被正文使用的观察事实" in system_prompt
    assert "直接证据哈希加入对应 output binding" in system_prompt
    assert "公开网页中的预测或观点" in system_prompt
    assert "news_search 未返回同一时间窗口证据" in system_prompt
    assert "不得用普通 web_search 摘要补成已核验因果" in system_prompt
    assert "不得为了耗尽步数调用非必需工具" in system_prompt
    assert "1000 汉字以内" in system_prompt


def test_valuation_model_contract_explains_scenario_and_financial_bindings() -> None:
    frame = TaskFrame(
        raw_question="瑞华泰的合理估值",
        user_goal="估算瑞华泰合理估值区间",
        question_type="valuation_estimate",
        subject="瑞华泰",
        subject_kind="company",
        market_scope="A股",
        timeframe="当前",
        required_outputs=("scenario_range",),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="company_valuation_evidence",
        confidence=0.95,
    )
    finish = ModelTurn(
        json.dumps(
            {
                "status": "partial",
                "draft": "当前无法可靠给出估值情景区间。",
                "gaps": ["缺少估值锚"],
                "bindings": [
                    {
                        "output_id": "scenario_range",
                        "evidence_hashes": [],
                        "gap": "缺少估值锚",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        (),
        "scripted",
        "",
    )
    model = ScriptedModel([finish])

    ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(frame),
        registry=_market_registry(_successful_runner),
    )

    system_prompt = model.calls[0]["messages"][0]["content"]
    assert "scenario_range" in system_prompt
    assert "保守、中性、乐观" in system_prompt
    assert "financial_data" in system_prompt
    assert "补充证据" in system_prompt
    assert "PB 情景计算锚" in system_prompt
    assert "不得另造倍数" in system_prompt
    assert "没有直接 evidence 的项目" in system_prompt


def test_finalization_reminder_prefers_decisive_evidence_without_new_thresholds() -> None:
    frame = _frame()
    model = ScriptedModel([_tool_turn("A股 最新行情"), _finish_turn()])

    ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(frame, max_steps=1),
        registry=_market_registry(_successful_runner),
    )

    finalization_messages = model.calls[1]["messages"]
    reminder = finalization_messages[-1]["content"]
    assert "不要逐条复述全部观察" in reminder
    assert "只保留最关键依据" in reminder
    assert "条件写相对变化" in reminder
    assert "不得新增证据中没有的数值阈值" in reminder
    assert "一个明确标注的主观基准区间" in reminder
    assert "每个保留的精确数字" in reminder
    assert "每条被正文使用的观察事实" in reminder
    assert "1000 汉字以内" in reminder


def test_finish_parser_accepts_one_stray_quote_after_strict_json_fence() -> None:
    frame = _frame()
    finish = _finish_turn()
    fenced = ModelTurn(
        f"```json\n{finish.content}\n```\"",
        (),
        "scripted",
        "",
    )
    model = ScriptedModel([_tool_turn("A股 最新行情"), fenced])

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(frame, max_steps=1),
        registry=_market_registry(_successful_runner),
    )

    assert outcome.status == "completed"
    assert outcome.draft == "当前更接近条件化修复，持续性取决于量能。"
    assert outcome.stop_reason == "model_finish"


def test_finish_parser_uses_last_complete_fenced_object_after_preamble() -> None:
    frame = _frame()
    first = json.loads(_finish_turn().content)
    first["draft"] = "较早的重复草稿。"
    final = dict(first)
    final["draft"] = "最终有效草稿。"
    noisy = ModelTurn(
        "我已经完成研究，下面给出结果。\n"
        f"```json\n{json.dumps(first, ensure_ascii=False)}\n```\n"
        "让我再规范一次。\n"
        f"```json\n{json.dumps(final, ensure_ascii=False)}\n```",
        (),
        "scripted",
        "",
    )
    model = ScriptedModel([_tool_turn("A股 最新行情"), noisy])

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(frame, max_steps=1),
        registry=_market_registry(_successful_runner),
    )

    assert outcome.status == "completed"
    assert outcome.draft == "最终有效草稿。"
    assert outcome.stop_reason == "model_finish"
    assert outcome.usage.invalid_actions == 0
    assert len(model.calls) == 2


def test_unknown_tool_error_returns_to_same_episode_without_runner_call() -> None:
    calls: list[str] = []

    def runner(query: str, context: AgentToolContext):
        calls.append(query)
        return _successful_runner(query, context)

    frame = _frame()
    model = ScriptedModel(
        [
            _tool_turn("rm -rf /", name="shell_exec"),
            _finish_turn(
                status="partial",
                draft="未执行未授权工具，当前无法完成判断。",
                hashes=(),
                gap="未授权工具不能执行",
            ),
        ]
    )

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(frame),
        registry=_market_registry(runner),
    )

    assert calls == []
    assert outcome.status == "partial"
    assert outcome.usage.tool_calls == 0
    assert outcome.usage.invalid_actions == 1
    second_messages = model.calls[1]["messages"]
    assert second_messages[-1]["role"] == "tool"
    assert "unknown_or_unauthorized_tool" in second_messages[-1]["content"]


def test_two_unauthorized_calls_keep_distinct_session_owned_gate_step_ids() -> None:
    frame = _frame()
    model = ScriptedModel(
        [
            ModelTurn(
                "",
                (
                    ModelToolCall(
                        "forbidden-1",
                        "shell_exec",
                        {"query": "do not run"},
                    ),
                    ModelToolCall(
                        "forbidden-2",
                        "write_file",
                        {"query": "do not run"},
                    ),
                ),
                "scripted",
                "",
            ),
            _finish_turn(
                status="partial",
                draft="未执行未授权工具，当前无法完成判断。",
                hashes=(),
                gap="未授权工具不能执行",
            ),
        ]
    )

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(frame),
        registry=_market_registry(_successful_runner),
    )

    assert outcome.usage.tool_calls == 0
    assert outcome.usage.invalid_actions == 2
    assert [trace.step_id for trace in outcome.traces] == [
        "episode-test:episode:tool:1",
        "episode-test:episode:tool:2",
    ]
    assert len({trace.step_id for trace in outcome.traces}) == 2
    assert all(trace.provider == "episode:tool_gate" for trace in outcome.traces)
    assert all(trace.status == "disabled" for trace in outcome.traces)
    assert all(trace.step_id != "episode-test:episode:gate" for trace in outcome.traces)
    assert [
        event.kind
        for event in outcome.events
        if event.kind in {"tool_request", "tool_result", "tool_error"}
    ] == ["tool_request", "tool_error", "tool_request", "tool_error"]
    tool_messages = [
        message for message in model.calls[1]["messages"] if message["role"] == "tool"
    ]
    assert [message["tool_call_id"] for message in tool_messages] == [
        "forbidden-1",
        "forbidden-2",
    ]


def test_duplicate_normalized_query_is_rejected_without_second_execution() -> None:
    calls: list[str] = []

    def runner(query: str, context: AgentToolContext):
        calls.append(query)
        return _successful_runner(query, context)

    frame = _frame()
    model = ScriptedModel(
        [
            _tool_turn("A股 最新行情", call_id="call-1"),
            _tool_turn("  a股   最新行情 ", call_id="call-2"),
            _finish_turn(status="partial"),
        ]
    )

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(frame),
        registry=_market_registry(runner),
    )

    assert calls == ["A股 最新行情"]
    assert outcome.usage.tool_calls == 1
    assert outcome.usage.invalid_actions == 1
    assert "duplicate_query" in model.calls[2]["messages"][-1]["content"]


def test_tool_exception_is_traced_and_model_can_finish_same_episode() -> None:
    def broken_runner(_query: str, _context: AgentToolContext):
        raise RuntimeError("provider unavailable")

    frame = _frame()
    model = ScriptedModel(
        [
            _tool_turn("A股 最新行情"),
            _finish_turn(
                status="partial",
                draft="行情工具不可用，本轮只能报告证据缺口。",
                hashes=(),
                gap="行情工具暂不可用",
            ),
        ]
    )

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(frame),
        registry=_market_registry(broken_runner),
    )

    assert outcome.status == "partial"
    assert outcome.usage.tool_calls == 1
    assert outcome.traces[0].status == "request_error"
    assert outcome.traces[0].detail == "tool_exception"
    assert outcome.traces[0].step_id == "episode-test:episode:tool:1"
    assert "tool_exception" in model.calls[1]["messages"][-1]["content"]
    assert "provider unavailable" not in json.dumps(
        {
            "outcome": outcome.to_dict(),
            "tool_message": model.calls[1]["messages"][-1],
        },
        ensure_ascii=False,
    )


def test_tool_timeout_uses_public_error_code_without_raw_exception_detail() -> None:
    def timed_out_runner(_query: str, _context: AgentToolContext):
        raise TimeoutError("RAW_TIMEOUT_EXCEPTION_SENTINEL")

    frame = _frame()
    model = ScriptedModel(
        [
            _tool_turn("A股 最新行情"),
            _finish_turn(
                status="partial",
                draft="行情工具超时，本轮只能报告证据缺口。",
                hashes=(),
                gap="行情工具暂不可用",
            ),
        ]
    )

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(frame),
        registry=_market_registry(timed_out_runner),
    )

    assert outcome.usage.tool_calls == 1
    assert outcome.traces[0].status == "request_error"
    assert outcome.traces[0].detail == "tool_timeout"
    assert outcome.traces[0].step_id == "episode-test:episode:tool:1"
    tool_message = model.calls[1]["messages"][-1]
    assert json.loads(tool_message["content"])["error"] == "tool_timeout"
    assert "RAW_TIMEOUT_EXCEPTION_SENTINEL" not in json.dumps(
        {
            "outcome": outcome.to_dict(),
            "tool_message": tool_message,
        },
        ensure_ascii=False,
    )


def test_reusing_episode_starts_a_fresh_tool_session_for_each_run() -> None:
    calls: list[str] = []

    def runner(query: str, context: AgentToolContext):
        calls.append(query)
        return _successful_runner(query, context)

    frame = _frame()
    model = ScriptedModel(
        [
            _tool_turn("A股 最新行情", call_id="first-run"),
            _finish_turn(),
            _tool_turn("A股 最新行情", call_id="second-run"),
            _finish_turn(),
        ]
    )
    episode = ContinuousAgentEpisode(model)

    outcomes = [
        episode.run(
            task_frame=frame,
            context=_context(frame),
            registry=_market_registry(runner),
        )
        for _index in range(2)
    ]

    assert calls == ["A股 最新行情", "A股 最新行情"]
    assert [outcome.usage.tool_calls for outcome in outcomes] == [1, 1]
    assert [outcome.usage.invalid_actions for outcome in outcomes] == [0, 0]


def test_invalid_completed_finish_gets_one_repair_turn_in_same_history() -> None:
    frame = _frame()
    invalid_finish = ModelTurn(
        json.dumps(
            {
                "status": "completed",
                "draft": "已经完成。",
                "gaps": [],
                "bindings": [],
            },
            ensure_ascii=False,
        ),
        (),
        "scripted",
        "",
    )
    model = ScriptedModel([_tool_turn("A股 最新行情"), invalid_finish, _finish_turn()])

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(frame),
        registry=_market_registry(_successful_runner),
    )

    assert outcome.status == "completed"
    assert outcome.usage.invalid_actions == 1
    repair_messages = model.calls[2]["messages"]
    assert repair_messages[-1]["role"] == "user"
    assert "required output" in repair_messages[-1]["content"]
    assert any(event.kind == "invalid_action" for event in outcome.events)


def test_empty_scenario_finish_gets_one_repair_turn_in_same_history() -> None:
    frame = TaskFrame(
        raw_question="瑞华泰的合理估值",
        user_goal="估算瑞华泰合理估值区间",
        question_type="valuation_estimate",
        subject="瑞华泰",
        subject_kind="company",
        market_scope="A股",
        timeframe="当前",
        required_outputs=("scenario_range",),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="company_valuation_evidence",
        confidence=0.95,
    )
    empty_scenario = ModelTurn(
        json.dumps(
            {
                "status": "completed",
                "draft": (
                    "### 情景区间\n"
                    "| 情景 | 关键条件 | 隐含PB |\n"
                    "|---|---|---|"
                ),
                "gaps": [],
                "bindings": [
                    {
                        "output_id": "scenario_range",
                        "evidence_hashes": ["evidence-1"],
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
    repaired_scenario = ModelTurn(
        json.dumps(
            {
                "status": "completed",
                "draft": (
                    "估值区间：保守情景3.5倍、中性情景4.5倍、"
                    "乐观情景5.5倍。"
                ),
                "gaps": [],
                "bindings": [
                    {
                        "output_id": "scenario_range",
                        "evidence_hashes": ["evidence-1"],
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
    model = ScriptedModel(
        [_tool_turn("瑞华泰估值快照"), empty_scenario, repaired_scenario]
    )

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(frame),
        registry=_market_registry(_successful_runner),
    )

    assert outcome.status == "completed"
    assert "保守情景3.5倍" in outcome.draft
    assert outcome.usage.invalid_actions == 1
    assert len(model.calls) == 3
    repair_instruction = model.calls[2]["messages"][-1]["content"]
    assert "scenario_range" in repair_instruction


def test_second_invalid_finish_returns_partial_without_template_fallback() -> None:
    frame = _frame()
    model = ScriptedModel(
        [
            ModelTurn("not json", (), "scripted", ""),
            ModelTurn("still not json", (), "scripted", ""),
        ]
    )

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(frame),
        registry=_market_registry(_successful_runner),
    )

    assert outcome.status == "partial"
    assert outcome.stop_reason == "invalid_model_finish"
    assert outcome.draft == ""
    assert outcome.usage.invalid_actions == 2
    assert "模型未能返回可验证的结构化终止结果" in outcome.gaps


def test_finish_tolerates_unescaped_newlines_and_quotes_only_inside_draft() -> None:
    frame = _frame()
    malformed = ModelTurn(
        '{"status":"partial","draft":"第一行\n含"未转义引号"的第二行",'
        '"gaps":["仍缺市场数据"],"bindings":['
        '{"output_id":"direct_assessment","evidence_hashes":[],'
        '"gap":"仍缺市场数据"}]}',
        (),
        "scripted",
        "",
    )
    model = ScriptedModel([malformed])

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(frame),
        registry=_market_registry(_successful_runner),
    )

    assert outcome.status == "partial"
    assert outcome.stop_reason == "model_finish"
    assert outcome.draft == '第一行\n含"未转义引号"的第二行'
    assert outcome.bindings[0].gap == "仍缺市场数据"


def test_finish_normalizes_literal_newline_escapes_in_natural_language_draft() -> (
    None
):
    frame = _frame()
    escaped_layout = ModelTurn(
        json.dumps(
            {
                "status": "partial",
                "draft": "第一段。\\n\\n【条件】\\n1）量能回升。",
                "gaps": ["仍缺市场数据"],
                "bindings": [
                    {
                        "output_id": "direct_assessment",
                        "evidence_hashes": [],
                        "gap": "仍缺市场数据",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        (),
        "scripted",
        "",
    )
    model = ScriptedModel([escaped_layout])

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(frame),
        registry=_market_registry(_successful_runner),
    )

    assert outcome.draft == "第一段。\n\n【条件】\n1）量能回升。"


def test_tool_step_exhaustion_preserves_an_extra_finalization_turn() -> None:
    frame = _frame()
    model = ScriptedModel(
        [
            _tool_turn("A股 行情 1", call_id="call-1"),
            _tool_turn("A股 行情 2", call_id="call-2"),
            _tool_turn("A股 行情 3", call_id="call-3"),
            _finish_turn(),
        ]
    )

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(frame, max_steps=3),
        registry=_market_registry(_successful_runner),
    )

    assert outcome.status == "completed"
    assert outcome.stop_reason == "model_finish"
    assert outcome.evidence
    assert outcome.usage.llm_calls == 4
    assert outcome.usage.tool_calls == 3
    assert model.calls[-1]["tools"] == []


def test_tool_observation_exposes_root_budget_after_consumption() -> None:
    frame = _frame()
    base_context = _context(frame, max_steps=1)
    context = ResearchRunContext(
        contract=base_context.contract,
        deadline=base_context.deadline,
        policy=base_context.policy,
        trace_parent_id=base_context.trace_parent_id,
        today=base_context.today,
        latest_data_date=base_context.latest_data_date,
        root_budget=InMemoryRootBudgetLedger(
            episode_id=base_context.contract.task_id,
            initial_calls=1,
            hard_calls_cap=1,
            initial_seconds=30,
            hard_seconds_cap=30,
        ),
    )
    model = ScriptedModel([_tool_turn("A股 最新行情"), _finish_turn()])

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=context,
        registry=_market_registry(_successful_runner),
    )

    assert outcome.usage.tool_calls == 1
    tool_message = next(
        message
        for message in model.calls[1]["messages"]
        if message.get("role") == "tool"
    )
    payload = json.loads(tool_message["content"])
    assert payload["runtime_budget"]["remaining_tool_calls"] == 0


def test_complete_episode_snapshot_surface_forces_immediate_finalization() -> None:
    frame = _frame()

    def snapshot_runner(
        tool: str,
        content_hash: str,
    ):
        def run(query: str, _context: AgentToolContext):
            evidence = AgentEvidence(
                tool=tool,
                title=f"{tool} snapshot",
                detail=f"{query} snapshot",
                source="本地快照",
                source_date="2026-07-23",
                content_hash=content_hash,
            )
            return (
                [evidence],
                f"{tool} observation",
                ProviderTrace(
                    provider=f"test:{tool}",
                    capability=tool,
                    status="success",
                    result_count=1,
                ),
            )

        return run

    registry = ResearchToolRegistry(
        (
            ToolSpec(
                "market_data",
                "market_data",
                "行情快照",
                "local",
                "current",
                snapshot_runner("market_data", "evidence-1"),
                query_scope="episode",
            ),
            ToolSpec(
                "mainline_context",
                "mainline_context",
                "主线快照",
                "local",
                "current",
                snapshot_runner("mainline_context", "evidence-2"),
                query_scope="episode",
            ),
        )
    )
    model = ScriptedModel(
        [
            ModelTurn(
                "",
                (
                    ModelToolCall(
                        "market-call",
                        "market_data",
                        {"query": "最新行情"},
                    ),
                    ModelToolCall(
                        "mainline-call",
                        "mainline_context",
                        {"query": "最新主线"},
                    ),
                ),
                "scripted",
                "",
            ),
            _finish_turn(),
        ]
    )

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(
            frame,
            allowed_capabilities=("market_data", "mainline_context"),
        ),
        registry=registry,
    )

    assert outcome.status == "completed"
    assert outcome.usage.tool_calls == 2
    assert len(model.calls) == 2
    assert model.calls[1]["tools"] == []
    finalization = next(
        event for event in outcome.events if event.kind == "finalization"
    )
    assert finalization.payload["reason"] == "snapshot_surface_satisfied"


def test_next_model_turn_sees_dynamic_tools_and_remaining_budget() -> None:
    frame = _frame()
    registry = ResearchToolRegistry(
        (
            ToolSpec(
                name="market_data",
                capability="market_data",
                description="行情快照",
                cost="local",
                freshness="current",
                runner=_successful_runner,
                query_scope="episode",
            ),
            ToolSpec(
                name="web_search",
                capability="web_search",
                description="网页检索",
                cost="external",
                freshness="current",
                runner=_successful_runner,
            ),
        )
    )
    model = ScriptedModel(
        [
            _tool_turn("最新行情"),
            _finish_turn(),
        ]
    )

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(
            frame,
            max_steps=2,
            allowed_capabilities=("market_data", "web_search"),
        ),
        registry=registry,
    )

    first_tools = {
        item["function"]["name"] for item in model.calls[0]["tools"]
    }
    second_tools = {
        item["function"]["name"] for item in model.calls[1]["tools"]
    }
    assert first_tools == {"market_data", "web_search"}
    assert second_tools == {"web_search"}
    assert model.calls[1]["messages"][-1]["role"] == "tool"
    budget_payload = json.loads(model.calls[1]["messages"][-1]["content"])
    assert budget_payload["runtime_budget"]["remaining_tool_calls"] == 1
    assert outcome.status == "completed"
    assert outcome.usage.invalid_actions == 0


def test_episode_snapshot_binding_expands_to_the_complete_atomic_snapshot() -> None:
    frame = _frame()

    def snapshot_runner(query: str, _context: AgentToolContext):
        evidence = (
            AgentEvidence(
                tool="market_data",
                title="市场基线",
                detail=f"{query}：指数上涨",
                source="本地快照",
                content_hash="evidence-1",
            ),
            AgentEvidence(
                tool="market_data",
                title="涨跌结构",
                detail="涨停47家",
                source="本地快照",
                content_hash="evidence-2",
            ),
        )
        return (
            list(evidence),
            "complete market snapshot",
            ProviderTrace(
                provider="test:market",
                capability="market_data",
                status="success",
                result_count=2,
            ),
        )

    registry = ResearchToolRegistry(
        (
            ToolSpec(
                "market_data",
                "market_data",
                "完整行情快照",
                "local",
                "current",
                snapshot_runner,
                query_scope="episode",
            ),
        )
    )
    model = ScriptedModel(
        [
            _tool_turn("最新行情"),
            _finish_turn(
                draft="市场上涨，涨停47家。",
                hashes=("evidence-1",),
            ),
        ]
    )

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(frame),
        registry=registry,
    )

    assert outcome.status == "completed"
    assert outcome.bindings[0].evidence_hashes == ("evidence-1", "evidence-2")


def test_query_scoped_evidence_binding_remains_atomically_opt_in() -> None:
    frame = _frame()

    def search_runner(query: str, _context: AgentToolContext):
        return (
            [
                AgentEvidence(
                    tool="web_search",
                    title="直接来源",
                    detail=query,
                    source="网页A",
                    content_hash="evidence-1",
                ),
                AgentEvidence(
                    tool="web_search",
                    title="相邻但未引用的来源",
                    detail="另一网页",
                    source="网页B",
                    content_hash="evidence-2",
                ),
            ],
            "search results",
            ProviderTrace(
                provider="test:web",
                capability="web_search",
                status="success",
                result_count=2,
            ),
        )

    registry = ResearchToolRegistry(
        (
            ToolSpec(
                "web_search",
                "market_data",
                "查询型网页证据",
                "external",
                "current",
                search_runner,
                query_scope="query",
            ),
        )
    )
    model = ScriptedModel(
        [
            _tool_turn("直接来源", name="web_search"),
            _finish_turn(hashes=("evidence-1",)),
        ]
    )

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(frame),
        registry=registry,
    )

    assert outcome.status == "completed"
    assert outcome.bindings[0].evidence_hashes == ("evidence-1",)


def test_model_unavailable_before_evidence_fails_honestly() -> None:
    frame = _frame()
    model = ScriptedModel([ModelTurn("", (), "glm", "provider unavailable")])

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(frame),
        registry=_market_registry(_successful_runner),
    )

    assert outcome.status == "failed"
    assert outcome.stop_reason == "model_unavailable"
    assert outcome.draft == ""
    assert "provider unavailable" in outcome.gaps
    assert len(model.calls) == 1
    assert not any(
        event.kind == "finalization_recovery_started" for event in outcome.events
    )


@pytest.mark.parametrize(
    "failure,expected_llm_calls",
    [
        (RuntimeError("transport unavailable"), 3),
        (ModelTurn("", (), "glm", "provider unavailable"), 3),
    ],
    ids=("exception", "provider_error"),
)
def test_planning_failure_after_evidence_closes_research_then_finalizes_continuously(
    failure: Exception | ModelTurn,
    expected_llm_calls: int,
) -> None:
    frame = _frame()
    model = ScriptedModel(
        [
            _tool_turn("A股 最新行情"),
            failure,
            _finish_turn(),
        ]
    )

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(frame),
        registry=_market_registry(_successful_runner),
    )

    assert outcome.status == "completed"
    assert outcome.stop_reason == "model_finish"
    assert len(model.calls) == 3
    assert model.calls[-1]["tools"] == []
    assert outcome.usage.llm_calls == expected_llm_calls
    finalization_events = [
        event
        for event in outcome.events
        if event.kind == "finalization"
    ]
    assert len(finalization_events) == 1
    assert finalization_events[0].payload["reason"] == "planning_model_unavailable"
    assert not any(
        event.kind == "finalization_recovery_started" for event in outcome.events
    )


def test_model_failure_after_tools_close_gets_exactly_one_compact_recovery() -> None:
    frame = _frame()
    model = ScriptedModel(
        [
            _tool_turn("A股 最新行情"),
            ModelTurn("", (), "glm", "provider unavailable"),
            _finish_turn(),
        ]
    )

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(frame, max_steps=1),
        registry=_market_registry(_successful_runner),
    )

    assert outcome.status == "completed"
    assert outcome.stop_reason == "finalization_recovered"
    assert len(model.calls) == 3
    assert model.calls[1]["tools"] == []
    assert model.calls[2]["tools"] == []
    assert [event.kind for event in outcome.events].count(
        "finalization_recovery_started"
    ) == 1


def test_invalid_finish_after_normal_repair_recovers_only_once() -> None:
    frame = _frame()
    model = ScriptedModel(
        [
            _tool_turn("A股 最新行情"),
            ModelTurn("not json", (), "scripted", ""),
            ModelTurn("still not json", (), "scripted", ""),
            _finish_turn(),
        ]
    )

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(frame),
        registry=_market_registry(_successful_runner),
    )

    assert outcome.status == "completed"
    assert outcome.stop_reason == "finalization_recovered"
    assert len(model.calls) == 4
    assert [event.kind for event in outcome.events].count(
        "finalization_recovery_started"
    ) == 1


def test_last_planning_round_invalid_gets_repair_before_compact_recovery() -> None:
    frame = _frame()
    model = ScriptedModel(
        [
            _tool_turn("A股 最新行情 1", call_id="research-call-1"),
            _tool_turn("A股 最新行情 2", call_id="research-call-2"),
            ModelTurn("not json", (), "scripted", ""),
            ModelTurn("still not json", (), "scripted", ""),
            _finish_turn(),
        ]
    )

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(frame, max_steps=3),
        registry=_market_registry(_successful_runner),
    )

    assert outcome.status == "completed"
    assert outcome.stop_reason == "finalization_recovered"
    assert len(model.calls) == 5
    repair_call = model.calls[3]
    assert any(
        message["role"] == "user" and "上一条终止输出无效" in message["content"]
        for message in repair_call["messages"]
    )
    assert model.calls[4]["tools"] == []
    assert [event.kind for event in outcome.events].count(
        "finalization_recovery_started"
    ) == 1


def test_first_invalid_finish_after_tools_close_uses_compact_recovery() -> None:
    frame = _frame()
    model = ScriptedModel(
        [
            _tool_turn("A股 最新行情"),
            ModelTurn("not json", (), "scripted", ""),
            _finish_turn(),
        ]
    )

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(frame, max_steps=1),
        registry=_market_registry(_successful_runner),
    )

    assert outcome.status == "completed"
    assert outcome.stop_reason == "finalization_recovered"
    assert len(model.calls) == 3
    assert model.calls[1]["tools"] == []
    assert model.calls[2]["tools"] == []


def test_tool_call_after_finalization_closed_uses_compact_recovery() -> None:
    frame = _frame()
    model = ScriptedModel(
        [
            _tool_turn("A股 最新行情", call_id="research-call"),
            _tool_turn("不应执行", call_id="closed-call"),
            _finish_turn(),
        ]
    )

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(frame, max_steps=1),
        registry=_market_registry(_successful_runner),
    )

    assert outcome.status == "completed"
    assert outcome.stop_reason == "finalization_recovered"
    assert outcome.usage.tool_calls == 1
    assert outcome.usage.invalid_actions == 1
    assert len(model.calls) == 3
    assert model.calls[1]["tools"] == []
    assert model.calls[2]["tools"] == []


def test_plan_after_finalization_enters_terminal_recovery_instead_of_being_accepted() -> None:
    frame = _frame()
    model = ScriptedModel(
        [
            _tool_turn("A股 最新行情", call_id="research-call"),
            _plan_turn(),
            _finish_turn(),
        ]
    )

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(frame, max_steps=1),
        registry=_market_registry(_successful_runner),
    )

    assert outcome.status == "completed"
    assert outcome.stop_reason == "finalization_recovered"
    assert outcome.plan is None
    assert outcome.usage.tool_calls == 1
    assert outcome.usage.invalid_actions == 1
    assert any(
        event.kind == "finalization_recovery_started" for event in outcome.events
    )
    assert model.calls[1]["tools"] == []
    assert model.calls[2]["tools"] == []


def test_compact_recovery_is_not_called_with_less_than_one_second_left() -> None:
    frame = _frame()
    base_context = _context(frame)
    context = ResearchRunContext(
        contract=base_context.contract,
        deadline=_ScriptedDeadline((20.0, 20.0, 0.5), 0.5),  # type: ignore[arg-type]
        policy=base_context.policy,
        trace_parent_id=base_context.trace_parent_id,
        today=base_context.today,
        latest_data_date=base_context.latest_data_date,
    )
    model = ScriptedModel(
        [
            _tool_turn("A股 最新行情"),
            ModelTurn("", (), "glm", "provider unavailable"),
            _finish_turn(),
        ]
    )

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=ResearchRunContext(
            contract=context.contract,
            deadline=context.deadline,
            policy=ResearchPolicy("quick", 1, 30.0, 0.0),
            trace_parent_id=context.trace_parent_id,
            today=context.today,
            latest_data_date=context.latest_data_date,
        ),
        registry=_market_registry(_successful_runner),
    )

    assert outcome.status == "partial"
    assert outcome.stop_reason == "model_unavailable"
    assert len(model.calls) == 2
    assert not any(
        event.kind == "finalization_recovery_started" for event in outcome.events
    )


def test_late_recovery_turn_is_rejected_after_deadline_closes() -> None:
    frame = _frame()
    base_context = _context(frame)
    context = ResearchRunContext(
        contract=base_context.contract,
        deadline=_LateRecoveryDeadline(),  # type: ignore[arg-type]
        policy=base_context.policy,
        trace_parent_id=base_context.trace_parent_id,
        today=base_context.today,
        latest_data_date=base_context.latest_data_date,
    )
    model = ScriptedModel(
        [
            _tool_turn("A股 最新行情"),
            ModelTurn("", (), "glm", "provider unavailable"),
            _finish_turn(),
        ]
    )

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=ResearchRunContext(
            contract=context.contract,
            deadline=context.deadline,
            policy=ResearchPolicy("quick", 1, 30.0, 0.0),
            trace_parent_id=context.trace_parent_id,
            today=context.today,
            latest_data_date=context.latest_data_date,
        ),
        registry=_market_registry(_successful_runner),
    )

    assert outcome.status == "partial"
    assert outcome.stop_reason == "finalization_recovery_failed"
    assert outcome.draft == ""
    assert len(model.calls) == 3
    recovery_outcome = next(
        event
        for event in outcome.events
        if event.kind == "finalization_recovery_outcome"
    )
    # 剔除 ``at``（事件挂钟时刻）后再比：其余字段仍要求逐字相等，
    # 但断言本身不能依赖时钟，否则每次跑都不一样。
    assert {
        key: value
        for key, value in recovery_outcome.payload.items()
        if key != "at"
    } == {
        "task_frame_hash": frame.task_frame_hash,
        "status": "failed",
        "reason": "finalization_recovery_deadline_exhausted",
    }


def test_recovery_usage_counts_returned_provider_attempts() -> None:
    frame = _frame()
    finish = _finish_turn()
    recovery = ModelTurn(
        finish.content,
        finish.tool_calls,
        finish.provider_name,
        finish.error,
        provider_attempts=3,
    )
    model = ScriptedModel(
        [
            _tool_turn("A股 最新行情"),
            ModelTurn("", (), "glm", "provider unavailable"),
            recovery,
        ]
    )

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(frame),
        registry=_market_registry(_successful_runner),
    )

    assert outcome.status == "completed"
    assert outcome.usage.llm_calls == 5


def test_recovery_exception_without_attempt_metadata_adds_zero_llm_calls() -> None:
    frame = _frame()
    model = ScriptedModel(
        [
            _tool_turn("A股 最新行情"),
            ModelTurn("", (), "glm", "provider unavailable"),
        ]
    )

    outcome = ContinuousAgentEpisode(
        model,
        finalizer=_RaisingFinalizer(),  # type: ignore[arg-type]
    ).run(
        task_frame=frame,
        context=_context(frame, max_steps=1),
        registry=_market_registry(_successful_runner),
    )

    assert outcome.status == "partial"
    assert outcome.stop_reason == "finalization_recovery_failed"
    assert outcome.usage.llm_calls == 2
    assert any(
        event.kind == "finalization_recovery_outcome"
        and event.payload["status"] == "failed"
        for event in outcome.events
    )


def test_recovered_unknown_evidence_hash_is_rejected_without_recursive_retry() -> None:
    frame = _frame()
    invalid_recovery = _finish_turn(hashes=("invented-hash",))
    model = ScriptedModel(
        [
            _tool_turn("A股 最新行情"),
            ModelTurn("not json", (), "scripted", ""),
            ModelTurn("still not json", (), "scripted", ""),
            invalid_recovery,
            _finish_turn(),
        ]
    )

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(frame),
        registry=_market_registry(_successful_runner),
    )

    assert outcome.status == "partial"
    assert outcome.stop_reason == "finalization_recovery_failed"
    assert outcome.draft == ""
    assert len(model.calls) == 4
    assert [event.kind for event in outcome.events].count(
        "finalization_recovery_started"
    ) == 1
    assert any(
        event.kind == "invalid_action"
        and "unknown evidence hash" in str(event.payload.get("reason"))
        for event in outcome.events
    )
    recovery_outcome = next(
        event
        for event in outcome.events
        if event.kind == "finalization_recovery_outcome"
    )
    assert recovery_outcome.payload["status"] == "failed"


def test_episode_usage_counts_adapter_provider_attempts() -> None:
    frame = _frame()
    finish = _finish_turn(
        status="partial",
        hashes=(),
        gap="缺少可绑定的行情证据",
    )
    model = ScriptedModel(
        [
            ModelTurn(
                finish.content,
                finish.tool_calls,
                finish.provider_name,
                finish.error,
                provider_attempts=2,
            )
        ]
    )

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(frame),
        registry=_market_registry(_successful_runner),
    )

    assert outcome.usage.llm_calls == 2


def test_episode_usage_preserves_zero_pre_adapter_attempts() -> None:
    frame = _frame()
    finish = _finish_turn(
        status="partial",
        hashes=(),
        gap="模型预算在 provider 前耗尽",
    )
    model = ScriptedModel(
        [
            ModelTurn(
                finish.content,
                finish.tool_calls,
                finish.provider_name,
                finish.error,
                provider_attempts=0,
            )
        ]
    )

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(frame),
        registry=_market_registry(_successful_runner),
    )

    assert outcome.usage.llm_calls == 0


def test_multiple_tool_calls_cannot_bypass_total_step_budget() -> None:
    calls: list[str] = []

    def runner(query: str, context: AgentToolContext):
        calls.append(query)
        return _successful_runner(query, context)

    frame = _frame()
    batched_turn = ModelTurn(
        "",
        tuple(
            ModelToolCall(f"call-{index}", "market_data", {"query": f"行情 {index}"})
            for index in range(1, 4)
        ),
        "scripted",
        "",
    )
    model = ScriptedModel([batched_turn, _finish_turn()])

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(frame, max_steps=2),
        registry=_market_registry(runner),
    )

    assert calls == ["行情 1", "行情 2"]
    assert outcome.usage.tool_calls == 2
    assert outcome.usage.invalid_actions == 1
    assert "tool_budget_exhausted" in model.calls[1]["messages"][-1]["content"]


def test_first_model_plan_can_promote_the_same_episode_to_deep_mode() -> None:
    frame = _frame()
    base = _context(frame, max_steps=6)
    root_budget = InMemoryRootBudgetLedger(
        episode_id=base.contract.task_id,
        initial_calls=6,
        hard_calls_cap=8,
        initial_seconds=70.0,
        hard_seconds_cap=90.0,
    )
    context = replace(
        base,
        contract=replace(base.contract, research_tier="standard"),
        policy=ResearchPolicy.for_tier("standard"),
        deadline=ResearchDeadline.from_timeout(90.0, synthesis_reserve=20.0),
        root_budget=root_budget,
    )
    turns = [
        _plan_turn(
            requested_mode="deep",
            evidence_needs=["盘面结构", "新闻驱动"],
            open_gaps=["缺少反方证据"],
        ),
        *[
            _tool_turn(f"深度查询 {index}", call_id=f"deep-call-{index}")
            for index in range(1, 8)
        ],
        _finish_turn(hashes=("deep-evidence-7",)),
    ]
    model = ScriptedModel(turns)

    def runner(query: str, tool_context: AgentToolContext):
        suffix = query.rsplit(" ", 1)[-1]
        evidence = AgentEvidence(
            tool="market_data",
            title=f"深度证据 {suffix}",
            detail=f"{query} 返回可核验事实",
            source="本地行情",
            source_date="2026-07-21",
            evidence_tier="L4",
            content_hash=f"deep-evidence-{suffix}",
        )
        return (
            [evidence],
            f"observation {suffix}",
            ProviderTrace(
                provider="test:deep",
                capability="market_data",
                status="success",
                source_trade_date="2026-07-21",
                result_count=1,
            ),
        )

    continuation = []
    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=context,
        registry=_market_registry(runner),
        _continuation_sink=continuation,
    )

    assert outcome.status == "completed"
    assert outcome.usage.tool_calls == 7
    assert outcome.plan is not None
    assert outcome.plan.requested_mode == "deep"
    kinds = [event.kind for event in outcome.events]
    assert kinds.count("mode_decision") == 1
    plan_index = kinds.index("plan")
    assert kinds[plan_index + 1] == "mode_decision"
    decision_event = outcome.events[plan_index + 1]
    assert decision_event.payload["effective_mode"] == "deep"
    assert decision_event.payload["tool_call_cap"] == 24
    assert continuation[0].context.policy.tier == "deep"
    assert continuation[0].context.root_budget is root_budget
    assert root_budget.hard_calls_cap == 24
    final_history = model.calls[-1]["messages"]
    assert final_history[:2] == model.calls[0]["messages"][:2]
    for index in range(1, 8):
        assert f"深度查询 {index}" in str(final_history)


def test_deep_plan_without_observable_complexity_keeps_standard_budget() -> None:
    frame = _frame()
    base = _context(frame, max_steps=6)
    root_budget = InMemoryRootBudgetLedger(
        episode_id=base.contract.task_id,
        initial_calls=6,
        hard_calls_cap=8,
        initial_seconds=70.0,
        hard_seconds_cap=90.0,
    )
    context = replace(
        base,
        contract=replace(base.contract, research_tier="standard"),
        policy=ResearchPolicy.for_tier("standard"),
        deadline=ResearchDeadline.from_timeout(90.0, synthesis_reserve=20.0),
        root_budget=root_budget,
    )
    model = ScriptedModel(
        [
            _plan_turn(
                requested_mode="deep",
                evidence_needs=["盘面结构"],
                open_gaps=[],
            ),
            *[
                _tool_turn(f"标准查询 {index}", call_id=f"quick-call-{index}")
                for index in range(1, 8)
            ],
        ]
    )
    calls: list[str] = []

    def runner(query: str, tool_context: AgentToolContext):
        calls.append(query)
        return _successful_runner(query, tool_context)

    outcome = ContinuousAgentEpisode(
        model,
        mode_signals=lambda _frame, _plan: ModeSignals(),
    ).run(
        task_frame=frame,
        context=context,
        registry=_market_registry(runner),
    )

    assert len(calls) == 6
    assert outcome.usage.tool_calls == 6
    assert root_budget.hard_calls_cap == 8
    decision = next(event for event in outcome.events if event.kind == "mode_decision")
    assert decision.payload["effective_mode"] == "quick"
    assert decision.payload["reason"] == "no_observable_deep_condition"


def test_approved_branch_results_return_to_the_same_primary_history() -> None:
    frame = _frame()
    base = _context(frame, max_steps=6)
    root_budget = InMemoryRootBudgetLedger(
        episode_id=base.contract.task_id,
        initial_calls=6,
        hard_calls_cap=8,
        initial_seconds=70.0,
        hard_seconds_cap=90.0,
    )
    context = replace(
        base,
        contract=replace(base.contract, research_tier="standard"),
        policy=ResearchPolicy.for_tier("standard"),
        deadline=ResearchDeadline.from_timeout(90.0, synthesis_reserve=20.0),
        root_budget=root_budget,
    )
    branch_evidence = AgentEvidence(
        tool="news_search",
        title="反方驱动证据",
        detail="同一窗口存在反向资金流证据",
        source="公开来源",
        source_date="2026-07-21",
        evidence_tier="L3",
        content_hash="branch-evidence-1",
    )

    class StubCoordinator:
        def run(self, **kwargs):
            sink = kwargs["evidence_sink_factory"]("branch-1")
            sink.append(branch_evidence)
            return SubResearchResult(
                (
                    BranchResult(
                        branch_id="branch-1",
                        goal="查找反方驱动",
                        status="completed",
                        evidence=(branch_evidence,),
                        traces=(
                            ProviderTrace(
                                provider="branch:test",
                                capability="news_search",
                                status="success",
                                result_count=1,
                            ),
                        ),
                        gaps=(),
                        llm_calls=2,
                        tool_calls=1,
                    ),
                )
            )

    model = ScriptedModel(
        [
            _plan_turn(
                requested_mode="deep",
                evidence_needs=["盘面结构"],
                open_gaps=[],
                branch_goals=["查找反方驱动"],
            ),
            _finish_turn(hashes=("branch-evidence-1",)),
        ]
    )

    observed = []
    outcome = ContinuousAgentEpisode(
        model,
        sub_research_coordinator=StubCoordinator(),
        event_sink=observed.append,
    ).run(
        task_frame=frame,
        context=context,
        registry=_market_registry(_successful_runner),
    )

    assert outcome.status == "completed"
    assert outcome.usage.llm_calls == 4
    assert outcome.usage.tool_calls == 1
    kinds = [event.kind for event in outcome.events]
    assert kinds.index("plan") < kinds.index("mode_decision")
    assert kinds.index("mode_decision") < kinds.index("branch_started")
    assert kinds.index("branch_started") < kinds.index("branch_completed")
    assert model.calls[1]["messages"][:2] == model.calls[0]["messages"][:2]
    assert "SUB_RESEARCH_RESULTS" in str(model.calls[1]["messages"][-1])
    assert "反方驱动证据" in str(model.calls[1]["messages"][-1])
    assert "branch draft" not in str(model.calls[1]["messages"])
    observed_kinds = [event.kind for event in observed]
    assert observed_kinds.index("branch_started") < observed_kinds.index(
        "branch_completed"
    )


def test_continuous_episode_aggregates_optional_token_usage() -> None:
    frame = _frame()
    context = _context(frame, max_steps=1, allowed_capabilities=())
    model = ScriptedModel(
        [
            replace(_plan_turn(), input_tokens=11, output_tokens=5),
            replace(
                _finish_turn(status="partial", hashes=(), gap="缺少行情证据"),
                input_tokens=7,
                output_tokens=3,
            ),
        ]
    )

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=context,
        registry=ResearchToolRegistry(()),
    )

    assert outcome.usage.input_tokens == 18
    assert outcome.usage.output_tokens == 8
    runtime_event = next(
        event for event in outcome.events if event.kind == "runtime_result"
    )
    assert runtime_event.payload["input_tokens"] == 18
    assert runtime_event.payload["output_tokens"] == 8


def test_model_can_finalize_inside_the_reserved_synthesis_window() -> None:
    frame = _frame()
    base_context = _context(frame, max_steps=1)
    context = ResearchRunContext(
        contract=base_context.contract,
        deadline=ResearchDeadline.from_timeout(5.0, synthesis_reserve=5.0),
        policy=base_context.policy,
        trace_parent_id=base_context.trace_parent_id,
    )
    model = ScriptedModel(
        [
            _finish_turn(
                status="partial",
                draft="当前证据不足，先报告缺口。",
                hashes=(),
                gap="仍缺市场数据",
            )
        ]
    )

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=context,
        registry=_market_registry(_successful_runner),
    )

    assert outcome.status == "partial"
    assert outcome.stop_reason == "model_finish"
    assert outcome.usage.llm_calls == 1
    assert model.calls[0]["tools"] == []


def test_planning_turn_cannot_spend_the_reserved_finalization_budget() -> None:
    frame = _frame()
    base_context = _context(frame, max_steps=1)
    context = ResearchRunContext(
        contract=base_context.contract,
        deadline=ResearchDeadline.from_timeout(15.0, synthesis_reserve=4.0),
        policy=ResearchPolicy("quick", 1, 15.0, 4.0),
        trace_parent_id=base_context.trace_parent_id,
    )
    model = ScriptedModel([_tool_turn("A股 最新行情"), _finish_turn()])

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=context,
        registry=_market_registry(_successful_runner),
    )

    assert outcome.status == "completed"
    assert len(model.calls) == 2
    assert 0.0 < model.calls[0]["timeout"] <= 11.0
    assert model.calls[0]["tools"]
    assert model.calls[1]["timeout"] > 3.0
    assert model.calls[1]["tools"] == []


def _borrow_context(
    frame: TaskFrame,
    *,
    total: float,
    reserve: float,
) -> ResearchRunContext:
    base_context = _context(frame, max_steps=3)
    return ResearchRunContext(
        contract=base_context.contract,
        deadline=ResearchDeadline.from_timeout(total, synthesis_reserve=reserve),
        policy=ResearchPolicy("standard", 6, total, reserve),
        trace_parent_id=base_context.trace_parent_id,
    )


class TestOpeningCallBorrowsOnlyTheSurplus:
    """首轮向 ``synthesis_reserve`` 借余量——这段算术此前一行测试都没有。

    它保护的是一个已发生的生产事故（``_opening_planning_timeout`` 的 docstring
    记着 run 8792）：预扣整段 reserve 会让**唯一能启动检索的那次调用**拿到低于
    provider P50 的窗口，三个 run 全部 ``TimeoutError`` → 零 binding → 模板答案。

    断言落在「两个数之间的关系」而不是某个具体秒数，所以将来谁改
    ``MIN_SYNTHESIS_RESERVE_FLOOR_SECONDS`` 或切法，红的是这里而不是线上。
    """

    def test_opening_window_reproduces_the_run_8792_arithmetic(self) -> None:
        # docstring 里记录的现场：effective 80s / reserve 53.33s / P50 28s。
        episode = ContinuousAgentEpisode(ScriptedModel([]), llm_timeout=75.0)
        context = _borrow_context(_frame(), total=80.0, reserve=53.33)

        baseline = context.deadline.stage_timeout(75.0)
        opening = episode._opening_planning_timeout(context)

        # 修复前首轮只有 ~26.67s，低于 provider P50；借入后 ~60s。
        assert baseline == pytest.approx(26.67, abs=0.5)
        assert opening == pytest.approx(60.0, abs=0.5)

    def test_borrowed_amount_never_eats_into_one_synthesis(self) -> None:
        """借走的只能是超出「跑一次合成」的余量，不是整段 reserve。"""

        episode = ContinuousAgentEpisode(ScriptedModel([]), llm_timeout=75.0)
        floor = agent_episode_module.MIN_SYNTHESIS_RESERVE_FLOOR_SECONDS
        context = _borrow_context(_frame(), total=80.0, reserve=53.33)

        baseline = episode._opening_planning_timeout(context)
        remaining_for_synthesis = context.deadline.remaining() - baseline

        assert remaining_for_synthesis >= floor - 0.5

    def test_reserve_at_or_below_the_floor_lends_nothing(self) -> None:
        """reserve 本身只够一次合成时无余量可借，首轮与常规切法一致。"""

        episode = ContinuousAgentEpisode(ScriptedModel([]), llm_timeout=75.0)
        floor = agent_episode_module.MIN_SYNTHESIS_RESERVE_FLOOR_SECONDS
        context = _borrow_context(_frame(), total=60.0, reserve=floor)

        assert episode._opening_planning_timeout(context) == pytest.approx(
            context.deadline.stage_timeout(75.0), abs=0.5
        )

    def test_borrowing_stays_under_the_provider_timeout_ceiling(self) -> None:
        """上界是 provider 特性（``llm_timeout``），与总窗口解耦。"""

        episode = ContinuousAgentEpisode(ScriptedModel([]), llm_timeout=75.0)
        context = _borrow_context(_frame(), total=300.0, reserve=200.0)

        assert episode._opening_planning_timeout(context) == pytest.approx(
            75.0, abs=0.5
        )

    def test_only_the_opening_call_borrows(self) -> None:
        """第二次调用已经有证据要保护，必须回到常规切法。"""

        frame = _frame()
        context = _borrow_context(frame, total=80.0, reserve=53.33)
        model = ScriptedModel([_tool_turn("查当日行情"), _finish_turn()])

        outcome = ContinuousAgentEpisode(model, llm_timeout=75.0).run(
            task_frame=frame,
            context=context,
            registry=_market_registry(_successful_runner),
        )

        assert outcome.status == "completed"
        assert len(model.calls) == 2
        opening, follow_up = (
            float(model.calls[0]["timeout"]),
            float(model.calls[1]["timeout"]),
        )
        assert opening == pytest.approx(60.0, abs=1.0)
        assert follow_up == pytest.approx(26.67, abs=1.0)
        assert opening > follow_up


def test_tiny_planning_window_skips_tools_and_starts_finalization() -> None:
    frame = _frame()
    base_context = _context(frame, max_steps=3)
    context = ResearchRunContext(
        contract=base_context.contract,
        deadline=ResearchDeadline.from_timeout(6.0, synthesis_reserve=4.0),
        policy=ResearchPolicy("quick", 3, 6.0, 4.0),
        trace_parent_id=base_context.trace_parent_id,
    )
    model = ScriptedModel([_finish_turn(status="partial")])

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=context,
        registry=_market_registry(_successful_runner),
    )

    assert outcome.status == "partial"
    assert len(model.calls) == 1
    assert model.calls[0]["tools"] == []
    assert model.calls[0]["timeout"] > 3.0
    finalization = next(
        event for event in outcome.events if event.kind == "finalization"
    )
    assert finalization.payload["reason"] == "retrieval_deadline_closed"
