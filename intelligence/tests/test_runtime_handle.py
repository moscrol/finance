"""RuntimeHandle 六态生命周期（spec §7.3，实施顺序第 4 步 2/2）。

上半部验状态机本体：只进不退、close 幂等、取消只挡未派发的工作、
上游信号惰性折叠、收据不说谎。

下半部经真实入口（GLMAgentRuntime.start / CallbackEpisodeSession）验四类
验收场景的事件收据：取消、超时、Provider 失败、进程重启；并验三条负面
不变量：无 orphan tool call、被拒工作不结算 budget、close 后无新事件。
"""

from __future__ import annotations

from dataclasses import replace
from threading import Event

import pytest

import intelligence.runtime.agent_episode as agent_episode_module
import intelligence.services.research_contract as research_contract_module
from intelligence.runtime.glm_agent_runtime import GLMAgentRuntime
from intelligence.services.agent_runtime import EpisodeEvent
from intelligence.services.episode_scope import EpisodeScope
from intelligence.services.episode_session import (
    CallbackEpisodeSession,
    EpisodeSessionError,
)
from intelligence.services.repair_coordinator import CoverageDelta, RepairGoal
from intelligence.services.research_contract import InMemoryRootBudgetLedger
from intelligence.services.runtime_handle import (
    RuntimeHandle,
    RuntimeHandleCancelled,
    RuntimeHandleClosed,
)
from intelligence.tests.test_agent_episode import (
    ScriptedModel,
    _context as _episode_context,
    _finish_turn,
    _frame,
    _market_registry,
    _successful_runner,
    _tool_turn,
)


def _handle(**overrides: object) -> RuntimeHandle:
    kwargs: dict[str, object] = {"episode_id": "handle-test", "task_frame_hash": "h-1"}
    kwargs.update(overrides)
    return RuntimeHandle(**kwargs)  # type: ignore[arg-type]


def _transition_states(handle: RuntimeHandle) -> list[str]:
    return [
        str(row["state"])
        for row in handle.dump()["receipts"]  # type: ignore[union-attr]
        if row["kind"] == "transition"
    ]


def _note_events(handle: RuntimeHandle) -> list[str]:
    return [
        str(row["event"])
        for row in handle.dump()["receipts"]  # type: ignore[union-attr]
        if row["kind"] == "note"
    ]


def _repair_goal(episode_id: str, **overrides: object) -> RepairGoal:
    payload: dict[str, object] = {
        "episode_id": episode_id,
        "repair_goal_id": "repair-handle-test-1",
        "cycle": 1,
        "missing_answer_elements": ("direct_assessment",),
        "unsupported_claims": (),
        "missing_evidence_modes": (),
        "attempted_actions": (),
        "evidence_progress": CoverageDelta(1, 0, 1),
        "remaining_calls": 1,
        "remaining_seconds": 8.0,
    }
    payload.update(overrides)
    return RepairGoal(**payload)  # type: ignore[arg-type]


# ── 状态机本体 ─────────────────────────────────────────────────────────


def test_lifecycle_chain_records_receipts_in_order() -> None:
    handle = _handle()
    handle.mark_started()
    handle.mark_running()
    handle.begin_work("session_resume")
    handle.request_cancel("user_abort")
    handle.end_work("session_resume")
    handle.close("test_done")

    assert _transition_states(handle) == [
        "created",
        "started",
        "running",
        "cancel_requested",
        "draining",
        "closed",
    ]
    dumped = handle.dump()
    assert dumped["state"] == "closed"
    assert dumped["cancel_reason"] == "user_abort"
    assert dumped["close_reason"] == "test_done"
    assert "drained" in _note_events(handle)
    elapsed = [row["elapsed_ms"] for row in dumped["receipts"]]  # type: ignore[union-attr]
    assert elapsed == sorted(elapsed), "收据时间必须单调不减"


def test_close_is_idempotent() -> None:
    handle = _handle()
    handle.close("first")
    receipts_after_first = list(handle.dump()["receipts"])  # type: ignore[arg-type]
    handle.close("second")

    assert handle.is_closed()
    assert handle.dump()["close_reason"] == "first"
    assert list(handle.dump()["receipts"]) == receipts_after_first  # type: ignore[arg-type]


def test_backward_and_repeated_transitions_raise() -> None:
    handle = _handle()
    handle.mark_started()
    with pytest.raises(RuntimeError, match="只能从 created 出发"):
        handle.mark_started()
    handle.mark_running()
    with pytest.raises(RuntimeError, match="只能从 started 出发"):
        handle.mark_running()

    fresh = _handle()
    with pytest.raises(RuntimeError, match="只能从 started 出发"):
        fresh.mark_running()


def test_begin_work_after_close_is_denied_with_receipt() -> None:
    handle = _handle()
    handle.close("done")
    with pytest.raises(RuntimeHandleClosed):
        handle.begin_work("session_resume")
    assert "work_denied_closed" in _note_events(handle)


def test_cancel_blocks_new_work_but_allows_the_draining_unit() -> None:
    handle = _handle()
    handle.mark_started()
    handle.mark_running()
    handle.request_cancel("upstream")
    # 无在飞工作：不制造虚构的 draining 态
    assert handle.state == "cancel_requested"

    with pytest.raises(RuntimeHandleCancelled):
        handle.begin_work("session_resume")
    assert "work_denied_cancelled" in _note_events(handle)

    # 被排空的那一个工作单元仍可进出，并把状态推进 draining
    handle.begin_work("initial_run", allow_during_cancel=True)
    assert handle.state == "draining"
    handle.end_work("initial_run")
    assert "drained" in _note_events(handle)


def test_cancel_with_inflight_work_enters_draining_immediately() -> None:
    handle = _handle()
    handle.mark_started()
    handle.begin_work("initial_run", allow_during_cancel=True)
    handle.request_cancel("mid_flight")
    assert _transition_states(handle) == [
        "created",
        "started",
        "cancel_requested",
        "draining",
    ]
    handle.end_work("initial_run")
    assert "drained" in _note_events(handle)


def test_upstream_signal_is_folded_exactly_once() -> None:
    fired = Event()
    handle = _handle(upstream_cancelled=fired.is_set)
    handle.mark_started()
    assert handle.is_cancel_requested() is False

    fired.set()
    assert handle.is_cancel_requested() is True
    assert handle.is_cancel_requested() is True  # 再次观测不重复记账
    assert _transition_states(handle).count("cancel_requested") == 1
    assert handle.dump()["cancel_reason"] == "upstream_signal"


def test_broken_upstream_predicate_is_not_treated_as_cancel() -> None:
    def broken() -> bool:
        raise RuntimeError("signal backend down")

    handle = _handle(upstream_cancelled=broken)
    handle.mark_started()
    assert handle.is_cancel_requested() is False
    assert handle.state == "started"


def test_mark_running_is_suppressed_when_cancel_arrived_first() -> None:
    handle = _handle()
    handle.mark_started()
    handle.request_cancel("early_abort")
    handle.mark_running()
    assert handle.state == "cancel_requested"
    assert "session_live_suppressed" in _note_events(handle)


def test_cancel_after_close_is_a_note_not_a_transition() -> None:
    handle = _handle()
    handle.close("done")
    handle.request_cancel("late")
    assert handle.state == "closed"
    assert handle.dump()["cancel_reason"] is None
    assert "cancel_after_close" in _note_events(handle)


def test_end_work_without_begin_raises() -> None:
    handle = _handle()
    with pytest.raises(RuntimeError, match="没有对应的 begin_work"):
        handle.end_work("session_resume")


def test_empty_episode_id_is_rejected() -> None:
    with pytest.raises(ValueError, match="episode_id"):
        RuntimeHandle(episode_id="   ")


def test_attach_scope_requires_matching_identity() -> None:
    frame = _frame()
    context = _episode_context(frame)
    registry = _market_registry(_successful_runner)
    handle = RuntimeHandle(episode_id=context.contract.task_id)

    foreign = EpisodeScope(
        episode_id="someone-else",
        user_id="",
        context=context,
        registry=registry,
    )
    with pytest.raises(ValueError, match="episode_id 不一致"):
        handle.attach_scope(foreign)

    matching = EpisodeScope(
        episode_id=context.contract.task_id,
        user_id="",
        context=context,
        registry=registry,
    )
    handle.attach_scope(matching)
    dumped = handle.dump()
    assert dumped["scope_attached"] is True
    assert dumped["scope"]["episode_id"] == context.contract.task_id  # type: ignore[index]


# ── 会话集成 ───────────────────────────────────────────────────────────


def test_session_rejects_handle_with_foreign_identity() -> None:
    frame = _frame()
    context = _episode_context(frame)
    model = ScriptedModel([_tool_turn("A股 行情"), _finish_turn()])
    session = GLMAgentRuntime(client=model).start(
        frame,
        context=context,
        registry=_market_registry(_successful_runner),
    )
    with pytest.raises(ValueError, match="identity mismatch"):
        CallbackEpisodeSession(
            episode_id="another-episode",
            outcome=session.outcome,
            resume_callback=lambda previous, goal: previous,
            runtime_handle=RuntimeHandle(episode_id="handle-test"),
        )


# ── 四类验收场景（经真实入口）─────────────────────────────────────────


def test_cancel_scenario_receipts_no_orphan_work_no_budget_no_late_events() -> None:
    """取消场景：收据完整；无 orphan tool call；被拒工作不结算 budget；
    close 后无新事件。"""

    cancelled = Event()
    resume_model_calls: list[object] = []

    class CancellingModel:
        def complete(self, *, messages, tools, timeout):
            del tools, timeout
            resume_model_calls.append(messages)
            cancelled.set()
            return _tool_turn("不应执行")

    def forbidden_runner(query, tool_context):
        del query, tool_context
        raise AssertionError("取消后不得执行任何工具")

    frame = _frame()
    base_context = _episode_context(frame)
    root_budget = InMemoryRootBudgetLedger(
        episode_id=base_context.contract.task_id,
        initial_calls=2,
        hard_calls_cap=4,
        initial_seconds=20.0,
        hard_seconds_cap=30.0,
    )
    context = replace(base_context, root_budget=root_budget)
    session = GLMAgentRuntime(
        client=CancellingModel(),
        is_cancelled=cancelled.is_set,
    ).start(
        frame,
        context=context,
        registry=_market_registry(forbidden_runner),
    )

    assert session.outcome.stop_reason == "cancelled"
    assert session.outcome.usage.tool_calls == 0

    handle = session.runtime_handle
    assert handle is not None
    states = _transition_states(handle)
    # 上游信号在初始 run 收尾处被折叠观测：cancel_requested 时 run 仍在飞，
    # 所以必有 draining；mark_running 被取消压制。
    assert states[:2] == ["created", "started"]
    assert "cancel_requested" in states
    assert "draining" in states
    assert "running" not in states
    assert handle.dump()["cancel_reason"] == "upstream_signal"
    assert "session_live_suppressed" in _note_events(handle)
    assert "drained" in _note_events(handle)

    # 无 orphan tool call：能力收据与用量都说没有任何工具被调起
    assert handle.dump()["scope"]["invoked_tools"] == []  # type: ignore[index]

    # cancel 只挡未派发的工作：新 resume 被拒，且不触发模型调用、不结算预算
    events_before = session.outcome.events
    model_calls_before = len(resume_model_calls)
    allocated_before = root_budget.allocated_calls
    with pytest.raises(EpisodeSessionError, match="已请求取消"):
        session.resume(_repair_goal(context.contract.task_id))
    assert len(resume_model_calls) == model_calls_before
    assert root_budget.allocated_calls == allocated_before
    assert "work_denied_cancelled" in _note_events(handle)

    # close 幂等收口；close 后无新事件、再拒绝也有收据
    session.close()
    session.close()
    assert handle.is_closed()
    assert handle.dump()["close_reason"] == "session_closed:cancelled"
    with pytest.raises(EpisodeSessionError, match="already closed"):
        session.resume(_repair_goal(context.contract.task_id))
    assert session.outcome.events == events_before


def test_timeout_scenario_close_reason_carries_deadline_exhaustion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """超时场景：修复窗被模型轮烧穿，终态 repair_deadline_exhausted 进 close 收据。"""

    frame = _frame()
    context = _episode_context(frame, max_steps=1)
    now = [context.deadline.expires_at - 29.0]
    monkeypatch.setattr(agent_episode_module, "monotonic", lambda: now[0])
    monkeypatch.setattr(research_contract_module.time, "monotonic", lambda: now[0])

    class OverrunningRepairModel:
        def __init__(self) -> None:
            self.calls = 0

        def complete(self, *, messages, tools, timeout):
            del messages, tools
            self.calls += 1
            if self.calls == 1:
                return _finish_turn(status="partial", hashes=(), gap="缺少行情证据")
            now[0] += float(timeout) + 0.1
            return _tool_turn("不得执行", call_id="late-repair-call")

    def forbidden_runner(query, tool_context):
        del query, tool_context
        raise AssertionError("烧穿的修复窗不得派发工具")

    session = GLMAgentRuntime(client=OverrunningRepairModel()).start(
        frame,
        context=context,
        registry=_market_registry(forbidden_runner),
    )
    handle = session.runtime_handle
    assert handle is not None
    assert handle.state == "running"

    updated = session.resume(
        _repair_goal(context.contract.task_id, remaining_seconds=1.0)
    )
    assert updated.stop_reason == "repair_deadline_exhausted"
    # resume 工作单元有始有终，且未被误判为取消
    notes = _note_events(handle)
    assert notes.count("work_begun") >= 1
    assert notes.count("work_ended") == notes.count("work_begun")
    assert handle.dump()["cancel_requested"] is False

    session.close()
    assert handle.dump()["close_reason"] == "session_closed:repair_deadline_exhausted"


def test_provider_failure_scenario_close_reason_carries_model_unavailable() -> None:
    """Provider 失败场景：主路径模型不可用，终态 model_unavailable 进 close 收据。"""

    frame = _frame()
    context = _episode_context(frame)
    session = GLMAgentRuntime(
        client=ScriptedModel([RuntimeError("provider down")]),
    ).start(
        frame,
        context=context,
        registry=_market_registry(_successful_runner),
    )

    assert session.outcome.status == "failed"
    assert session.outcome.stop_reason == "model_unavailable"
    handle = session.runtime_handle
    assert handle is not None
    # Provider 失败不是取消：状态机走正常链，没有 cancel 两态
    assert _transition_states(handle) == ["created", "started", "running"]

    session.close()
    assert handle.dump()["close_reason"] == "session_closed:model_unavailable"
    assert _transition_states(handle)[-1] == "closed"


def test_process_restart_new_handle_keeps_identity_and_resume_invariants() -> None:
    """进程重启场景：同一 Episode 身份换新 Handle 续跑，五条 resume 不变量
    由既有会话机制继续把守，两份生命周期收据经 episode_id 对账。"""

    frame = _frame()
    context = _episode_context(frame)
    model = ScriptedModel([_tool_turn("A股 行情"), _finish_turn()])
    first_session = GLMAgentRuntime(client=model).start(
        frame,
        context=context,
        registry=_market_registry(_successful_runner),
    )
    assert first_session.outcome.status == "completed"
    first_session.close()
    first_handle = first_session.runtime_handle
    assert first_handle is not None
    assert first_handle.is_closed()
    first_receipts = list(first_handle.dump()["receipts"])  # type: ignore[arg-type]

    # 「重启」= 从留存的 outcome 重建会话：身份与事件前缀都来自上一进程
    survived_outcome = first_session.outcome
    restart_handle = RuntimeHandle(
        episode_id=context.contract.task_id,
        task_frame_hash=survived_outcome.task_frame_hash,
    )
    restart_handle.mark_started("process_restart_rehydration")
    restart_handle.mark_running("rehydrated_from_persisted_outcome")

    def rehydrated_resume(previous, goal):
        del goal
        next_sequence = len(previous.events) + 1
        return replace(
            previous,
            events=(
                *previous.events,
                EpisodeEvent(
                    next_sequence,
                    "model_turn",
                    {"task_frame_hash": previous.task_frame_hash},
                ),
            ),
        )

    restart_session = CallbackEpisodeSession(
        episode_id=context.contract.task_id,
        outcome=survived_outcome,
        resume_callback=rehydrated_resume,
        runtime_handle=restart_handle,
    )
    updated = restart_session.resume(_repair_goal(context.contract.task_id))

    # 不变量由既有机制把守：Episode ID、task frame hash、事件前缀全部未变
    assert updated.task_frame_hash == survived_outcome.task_frame_hash
    assert updated.events[: len(survived_outcome.events)] == survived_outcome.events
    # 两份收据同一身份、互不污染：重启前的收据在重启会话操作后一字未动
    assert restart_handle.dump()["episode_id"] == first_handle.dump()["episode_id"]
    assert list(first_handle.dump()["receipts"]) == first_receipts  # type: ignore[arg-type]
    assert restart_handle.state == "running"

    restart_session.close()
    assert restart_handle.dump()["close_reason"] == "session_closed:" + (
        survived_outcome.stop_reason or survived_outcome.status
    )
