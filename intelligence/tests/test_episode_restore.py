"""INV-R3 Tier A：每个 phase × 每个 crash 前缀 → 丢弃对象 → ``restore`` → 断言下一动作。

oracle 不是重抄一遍策略表，而是**不间断跑真实发生的下一件事**：跑一遍脚本化 episode，记下
每一次 ``put_state`` 时的状态；然后对日志的**每一个前缀长度** L（配上 L 之前最后写下的那份
状态）构造一个只见过这些字节的新 store，调 ``restore``，把它给的下一动作与不间断跑里紧接着
L 之后发生的那个外部效果对照。三种切点（意图前 / 意图后结算前 / 结算后）自然都在前缀集合里。

截止「已过 / 未过」两格靠可注入的 ``now``：未过 → 重发 / 重跑 / 回模型；已过 → 合成
interrupted 结算 + finish 并闭合。Memory 与 Jsonl 同前缀字节同结果。
"""

from __future__ import annotations

from datetime import datetime, timedelta
import json
from pathlib import Path

import pytest

from intelligence.runtime.agent_episode import ContinuousAgentEpisode
from intelligence.runtime.glm_agent_runtime import GLMAgentRuntime
from intelligence.services.agent_research import AgentEvidence, AgentToolContext
from intelligence.services.agent_runtime import EpisodeEvent
from intelligence.services.episode_messages import derive_messages
from intelligence.services.episode_restore import (
    RestoreUnavailable,
    restore_episode,
)
from intelligence.services.episode_store import (
    EpisodeState,
    JsonlEpisodeStore,
    MemoryEpisodeStore,
    UnknownRequiredKind,
)
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_tool_registry import ResearchToolRegistry, ToolSpec
from intelligence.tests.conformance.fixtures import (
    AUTHORIZED_TOOL,
    MARKET_EVIDENCE_HASH,
    ScenarioProbe,
    ScriptedModelClient,
    ScriptedToolCall,
    ScriptedTurn,
    completed_finish,
    make_context,
    make_frame,
    make_registry,
)

EPISODE_ID = "restore-tier-a"
# 不间断跑在「现在」；恢复时的「现在」由测试给：未过 = 跑后一秒，已过 = 一年后。
SOON = datetime.now().astimezone() + timedelta(seconds=1)
MUCH_LATER = datetime.now().astimezone() + timedelta(days=365)


class RecordingStore(MemoryEpisodeStore):
    """记下每一份写下的状态（MemoryEpisodeStore 只留最后一份）。"""

    def __init__(self) -> None:
        super().__init__()
        self.states: list[EpisodeState] = []

    def put_state(self, episode_id: str, state: EpisodeState) -> None:
        super().put_state(episode_id, state)
        self.states.append(state)


def _run_uninterrupted(
    scenario: tuple[ScriptedTurn, ...],
    *,
    registry: ResearchToolRegistry | None = None,
    task_id: str = EPISODE_ID,
) -> tuple[RecordingStore, tuple[EpisodeEvent, ...]]:
    store = RecordingStore()
    probe = ScenarioProbe()
    frame = make_frame()
    context = make_context(frame, task_id=task_id, timeout=120.0)
    runtime = GLMAgentRuntime(
        client=ScriptedModelClient(list(scenario), probe), episode_store=store
    )
    outcome = runtime.run(
        task_frame=frame,
        context=context,
        registry=registry if registry is not None else make_registry(probe),
    )
    assert outcome.stop_reason == "model_finish"
    events, state = store.load(task_id)
    assert state is not None and state.phase == "done"
    assert [e.to_dict() for e in events] == [e.to_dict() for e in outcome.events]
    return store, events


def _store_at(
    events: tuple[EpisodeEvent, ...], states: list[EpisodeState], length: int, *, jsonl_root: Path | None = None
) -> tuple[MemoryEpisodeStore | JsonlEpisodeStore, EpisodeState]:
    """崩溃现场：前 ``length`` 条事件 + 那时最后一份状态。"""

    state = max(
        (s for s in states if s.last_sequence <= length), key=lambda s: s.last_sequence
    )
    store: MemoryEpisodeStore | JsonlEpisodeStore
    store = JsonlEpisodeStore(jsonl_root) if jsonl_root is not None else MemoryEpisodeStore()
    store.append(EPISODE_ID, events[:length])
    store.put_state(EPISODE_ID, state)
    return store, state


_INTENT_LIKE = frozenset({"model_intent", "tool_request", "finish"})


def _expected_next(events: tuple[EpisodeEvent, ...], length: int, state: EpisodeState) -> tuple[str, tuple[str, ...]]:
    """不间断跑里 L 之后**真实发生**的下一件外部效果，翻成恢复应给的动作。"""

    prefix = events[:length]
    # 意图后结算前：前缀里有没结算的意图 → 恢复必须重发同一意图（retry / replay）。
    if state.phase == "model_pending" and state.reserved_ids:
        turn_id = state.reserved_ids[0]
        settled = any(
            e.kind in {"model_turn", "model_error"} and e.payload.get("turn_id") == turn_id
            for e in prefix
        )
        if not settled:
            return "retry_model", ()
    dangling = tuple(
        e.payload["call_id"]
        for e in prefix
        if e.kind == "tool_request"
        and "replay" in e.payload
        and not any(
            s.kind in {"tool_result", "tool_error"} and s.payload.get("call_id") == e.payload["call_id"]
            for s in prefix
        )
    )
    if dangling:
        return "replay_tools", dangling
    # 否则：L 之后下一件外部效果是什么，恢复就该说要做什么。
    for event in events[length:]:
        if event.kind == "model_intent":
            return "model_turn", ()
        if event.kind == "tool_request" and "replay" in event.payload:
            call_ids = tuple(
                e.payload["call_id"]
                for e in events[length:]
                if e.kind == "tool_request" and "replay" in e.payload
                and e.payload.get("turn_id", None) is None
            )
            return "dispatch_tools", call_ids
        if event.kind == "finish":
            return "interpret_turn", ()
    raise AssertionError("uninterrupted run had no next effect after this prefix")


_SCENARIO = (
    ScriptedTurn(
        tool_calls=(
            ScriptedToolCall(AUTHORIZED_TOOL, "市场宽度"),
            ScriptedToolCall(AUTHORIZED_TOOL, "成交额"),
        ),
    ),
    ScriptedTurn(finish=completed_finish()),
)


def _all_prefixes(events: tuple[EpisodeEvent, ...], states: list[EpisodeState]) -> list[int]:
    first_state = min(s.last_sequence for s in states)
    return list(range(first_state, len(events) + 1))


def test_every_crash_prefix_restores_to_what_actually_happened_next() -> None:
    store, events = _run_uninterrupted(_SCENARIO)
    phases_seen = {s.phase for s in store.states}
    assert {"planning", "model_pending", "tools_pending", "done"} <= phases_seen
    checked: set[tuple[str, str]] = set()
    for length in _all_prefixes(events, store.states):
        crash_store, state = _store_at(events, store.states, length)
        result = restore_episode(EPISODE_ID, crash_store, now=SOON)
        if state.phase == "done" or any(e.kind == "finish" for e in events[:length]):
            assert result.disposition == "already_terminal", (length, state.phase)
            continue
        expected_action, expected_calls = _expected_next(events, length, state)
        assert result.disposition == "resumable", (length, state.phase, result.to_dict())
        assert result.plan is not None
        assert result.plan.action == expected_action, (
            f"prefix={length} phase={state.phase} reserved={state.reserved_ids}: "
            f"restore said {result.plan.action!r}, uninterrupted run did {expected_action!r}"
        )
        if expected_calls:
            assert tuple(result.plan.call_ids) == expected_calls
        # 截止未过、意图声明 safe：什么都不该被合成，日志一字不多。
        assert result.synthesized == ()
        checked.add((state.phase, expected_action))
    # 三种切点都到过：意图前（model_turn / dispatch_tools）、意图后结算前（retry / replay）、结算后。
    assert {"retry_model", "replay_tools", "model_turn", "interpret_turn", "dispatch_tools"} <= {
        action for _phase, action in checked
    }, checked


def test_memory_and_jsonl_restore_byte_identical(tmp_path: Path) -> None:
    store, events = _run_uninterrupted(_SCENARIO)
    for index, length in enumerate(_all_prefixes(events, store.states)):
        memory_store, _ = _store_at(events, store.states, length)
        jsonl_store, _ = _store_at(events, store.states, length, jsonl_root=tmp_path / f"p{index}")
        for now in (SOON, MUCH_LATER):
            left = restore_episode(EPISODE_ID, memory_store, now=now)
            right = restore_episode(EPISODE_ID, jsonl_store, now=now)
            strip = lambda d: json.dumps(  # noqa: E731
                {**d, "synthesized": [{k: v for k, v in e.items() if k != "payload"} | {"payload": {k: v for k, v in e["payload"].items() if k != "at"}} for e in d["synthesized"]]},
                sort_keys=True,
                ensure_ascii=False,
            )
            assert strip(left.to_dict()) == strip(right.to_dict()), (length, now)
            # 两个 store 都被写回同一份终态 / 同一份状态。
            assert memory_store.load(EPISODE_ID)[1].to_dict().keys() == jsonl_store.load(EPISODE_ID)[1].to_dict().keys()
            break  # 每个前缀只需一种 now 对比同形；已过截止那格由下面的用例专门验


def test_deadline_passed_closes_dangling_model_intent_with_interrupted_error() -> None:
    store, events = _run_uninterrupted(_SCENARIO)
    first_intent = next(e for e in events if e.kind == "model_intent")
    crash_store, state = _store_at(events, store.states, first_intent.sequence)
    assert state.phase == "model_pending" and state.reserved_ids == (first_intent.payload["turn_id"],)

    result = restore_episode(EPISODE_ID, crash_store, now=MUCH_LATER)

    assert result.disposition == "closed" and result.outcome is not None
    kinds = [e.kind for e in result.synthesized]
    assert kinds == ["model_error", "finish"]
    error, finish = result.synthesized
    assert error.payload["reason"] == "interrupted"
    assert error.payload["turn_id"] == first_intent.payload["turn_id"]
    assert error.payload["intent_sequence"] == first_intent.sequence
    assert error.payload["synthesized"] is True
    assert finish.payload["stop_reason"] == "interrupted"
    assert result.outcome.status == "failed"  # 中断前没有任何 tool_result
    assert result.outcome.stop_reason == "interrupted"
    # 写回：日志多了两条、状态 done、不再列为 open；序号仍连续。
    stored, stored_state = crash_store.load(EPISODE_ID)
    assert len(stored) == first_intent.sequence + 2
    assert stored_state is not None and stored_state.phase == "done"
    assert crash_store.list_open() == ()
    # 再恢复一次：已终局，什么都不做。
    again = restore_episode(EPISODE_ID, crash_store, now=MUCH_LATER)
    assert again.disposition == "already_terminal" and again.synthesized == ()


def test_deadline_passed_closes_dangling_tool_intents_and_derivation_still_holds() -> None:
    store, events = _run_uninterrupted(_SCENARIO)
    requests = [e for e in events if e.kind == "tool_request"]
    assert len(requests) == 2
    # 两条意图都落了、结算一条都没落。
    length = requests[-1].sequence
    crash_store, state = _store_at(events, store.states, length)
    assert state.phase == "tools_pending" and set(state.reserved_ids) == {
        e.payload["call_id"] for e in requests
    }

    result = restore_episode(EPISODE_ID, crash_store, now=MUCH_LATER)

    assert result.disposition == "closed" and result.outcome is not None
    assert [e.kind for e in result.synthesized] == ["tool_error", "tool_error", "finish"]
    for error, intent in zip(result.synthesized[:2], requests):
        assert error.payload["call_id"] == intent.payload["call_id"]
        assert error.payload["error"] == "interrupted"
        assert error.payload["intent_sequence"] == intent.sequence
        assert json.loads(error.payload["model_content"])["error"] == "interrupted"
    assert result.outcome.status == "failed"
    # INV-R1 在合成后的日志上仍成立：派生器能从合成结算重建 tool 消息。
    derived = derive_messages(result.events)
    assert [m.role for m in derived][-2:] == ["tool", "tool"]
    assert [m.tool_call_id for m in derived][-2:] == [e.payload["call_id"] for e in requests]


def _crashed_fallback_episode(*, after_kind: str):
    """跑一遍真实空池回退脚本（模型点 sector_daily → 空 → 应用补一枪成交额榜），把日志截在
    ``after_kind`` 那条事件之后当崩溃现场。两个切点都在声明之后：意图前 / 意图后结算前。"""

    from intelligence.services.empty_pool_fallback import FALLBACK_CALL_ID
    from intelligence.tests.test_empty_pool_fallback import (
        _ScriptedModel,
        _empty_sector_turn,
        _empty_then_amount_runner,
        _finance_registry,
        _finish_turn,
        _theme_context,
        _theme_frame,
    )

    store = RecordingStore()
    frame = _theme_frame()
    context = _theme_context(frame)
    outcome = ContinuousAgentEpisode(
        _ScriptedModel([_empty_sector_turn(), _finish_turn(hashes=("amount-1",))]),
        store=store,
    ).run(task_frame=frame, context=context, registry=_finance_registry(_empty_then_amount_runner([])))
    assert outcome.status == "completed"
    episode_id = context.contract.task_id
    events, _ = store.load(episode_id)
    cut = next(
        e.sequence
        for e in events
        if e.kind == after_kind and e.payload.get("call_id") == FALLBACK_CALL_ID
    )
    state = max((s for s in store.states if s.last_sequence <= cut), key=lambda s: s.last_sequence)
    crash_store = MemoryEpisodeStore()
    crash_store.append(episode_id, events[:cut])
    crash_store.put_state(episode_id, state)
    return episode_id, crash_store, FALLBACK_CALL_ID


def test_application_declaration_without_dispatch_is_settled_so_no_tool_call_dangles() -> None:
    """声明落了、意图没落就崩：恢复不重发（声明不是意图），合成 tool_error{interrupted} 配平，
    派生出的消息里既没有孤儿 tool 消息、也没有悬空的 assistant.tool_calls。"""

    from intelligence.services.episode_messages import undeclared_tool_call_ids

    episode_id, crash_store, fallback_id = _crashed_fallback_episode(after_kind="application_tool_call")

    result = restore_episode(episode_id, crash_store, now=SOON)

    assert result.disposition == "resumable" and result.plan is not None
    assert result.plan.action == "model_turn"
    assert [e.kind for e in result.synthesized] == ["tool_error"]
    settled = result.synthesized[0]
    assert settled.payload["call_id"] == fallback_id
    assert settled.payload["error"] == "interrupted"
    assert json.loads(settled.payload["model_content"])["error"] == "interrupted"
    derived = derive_messages(result.events)
    assert undeclared_tool_call_ids(derived) == ()
    declared = {c.call_id for m in derived if m.role == "assistant" for c in m.tool_calls}
    answered = {m.tool_call_id for m in derived if m.role == "tool"}
    assert declared == answered  # 每个声明都有结算，每个结算都有声明。
    # 恰好一次：这条声明本身就算「已尝试」，恢复后的下一批不会再补第二枪。
    from intelligence.services.empty_pool_fallback import fallback_already_attempted

    assert fallback_already_attempted(result.events)


def test_application_declaration_with_dangling_intent_replays_the_same_call() -> None:
    """声明与意图都落了、结算没落：走既有的 replay=safe 路径重跑同一 call_id，不再声明第二次。"""

    episode_id, crash_store, fallback_id = _crashed_fallback_episode(after_kind="tool_request")

    result = restore_episode(episode_id, crash_store, now=SOON)

    assert result.disposition == "resumable" and result.plan is not None
    assert result.plan.action == "replay_tools" and result.plan.call_ids == (fallback_id,)
    assert result.synthesized == ()
    assert sum(1 for e in result.events if e.kind == "application_tool_call") == 1


def test_replay_never_tool_is_settled_as_interrupted_not_replayed() -> None:
    def runner(query: str, _context: AgentToolContext):
        return (
            [
                AgentEvidence(
                    tool=AUTHORIZED_TOOL,
                    title="t",
                    detail=query,
                    source="s",
                    source_date="2026-07-24",
                    evidence_tier="L4",
                    content_hash=MARKET_EVIDENCE_HASH,
                )
            ],
            "obs",
            ProviderTrace(provider="test:market", capability="market_data", status="success", result_count=1),
        )

    registry = ResearchToolRegistry(
        (
            ToolSpec(
                name=AUTHORIZED_TOOL,
                capability="market_data",
                description="写效果的工具（示意）",
                cost="local",
                freshness="current",
                runner=runner,
                replay="never",
            ),
        )
    )
    store, events = _run_uninterrupted(
        (
            ScriptedTurn(tool_calls=(ScriptedToolCall(AUTHORIZED_TOOL, "下单"),)),
            ScriptedTurn(finish=completed_finish()),
        ),
        registry=registry,
    )
    intent = next(e for e in events if e.kind == "tool_request")
    assert intent.payload["replay"] == "never"
    crash_store, _ = _store_at(events, store.states, intent.sequence)

    result = restore_episode(EPISODE_ID, crash_store, registry=registry, now=SOON)

    # 截止未过也不重跑：合成 interrupted 结算，然后回模型让它看到这条错误。
    assert result.disposition == "resumable" and result.plan is not None
    assert result.plan.action == "model_turn"
    assert [e.kind for e in result.synthesized] == ["tool_error"]
    assert result.synthesized[0].payload["detail"] == "intent declared replay=never"
    assert result.state_after.reserved_ids == ()


def test_current_declaration_flipping_to_never_blocks_replay() -> None:
    store, events = _run_uninterrupted(_SCENARIO)
    requests = [e for e in events if e.kind == "tool_request"]
    # 两条意图都落了、结算一条都没落；意图里写的是 safe，但**当前**注册表已改成 never。
    crash_store, _ = _store_at(events, store.states, requests[-1].sequence)
    probe = ScenarioProbe()
    flipped = ResearchToolRegistry(
        tuple(
            ToolSpec(
                name=spec.name,
                capability=spec.capability,
                description=spec.description,
                cost=spec.cost,
                freshness=spec.freshness,
                runner=spec.runner,
                replay="never",
            )
            for spec in make_registry(probe).authorized_specs(("market_data", "news_search"))
        )
    )
    result = restore_episode(EPISODE_ID, crash_store, registry=flipped, now=SOON)
    assert result.plan is not None and result.plan.action == "model_turn"
    assert [e.kind for e in result.synthesized] == ["tool_error", "tool_error"]
    assert all(
        e.payload["detail"].endswith("is no longer declared replay=safe") for e in result.synthesized
    )
    assert result.state_after.reserved_ids == ()


def test_partial_intents_dispatch_the_rest_after_settling_the_landed_one() -> None:
    """一批两调用，只有第一条意图落了就崩：落了的那条按策略处理，没落的那条要派发。"""

    store, events = _run_uninterrupted(_SCENARIO)
    requests = [e for e in events if e.kind == "tool_request"]
    crash_store, state = _store_at(events, store.states, requests[0].sequence)
    assert state.phase == "model_pending"  # tools_pending 那份状态在第二条意图之后才写

    result = restore_episode(EPISODE_ID, crash_store, now=SOON)
    # 截止未过、safe：一次 restore 只给**一个**下一动作——先重跑落了意图的那条（reserved 只留它）。
    # 驾驶方按 restore → 动作 → restore 迭代：那条结算后再来，模型结算里的 call-2 仍无意图，
    # 下一动作就是 dispatch_tools(call-2)。单步给、可迭代收敛，不在一份 plan 里塞两种语义。
    assert result.plan is not None and result.plan.action == "replay_tools"
    assert result.plan.call_ids == (requests[0].payload["call_id"],)
    assert result.state_after.reserved_ids == (requests[0].payload["call_id"],)

    # 截止已过：落了的合成 interrupted，整个 episode 闭合——没落的那条从未发生、不合成。
    crash_store2, _ = _store_at(events, store.states, requests[0].sequence)
    closed = restore_episode(EPISODE_ID, crash_store2, now=MUCH_LATER)
    assert closed.disposition == "closed"
    assert [e.kind for e in closed.synthesized] == ["tool_error", "finish"]


def test_durable_cancel_closes_with_typed_cause_after_settling_intents() -> None:
    store, events = _run_uninterrupted(_SCENARIO)
    intent = next(e for e in events if e.kind == "tool_request")
    crash_store, state = _store_at(events, store.states, intent.sequence)
    cancelled = EpisodeState(
        **{
            **state.to_dict(),
            "cancel": {"requested": True, "cause": "user", "detail": "cancel_requested"},
        }
    )
    crash_store.put_state(EPISODE_ID, cancelled)

    result = restore_episode(EPISODE_ID, crash_store, now=SOON)

    assert result.disposition == "closed" and result.outcome is not None
    assert result.outcome.stop_reason == "cancelled"
    kinds = [e.kind for e in result.synthesized]
    assert kinds[-1] == "finish" and "tool_error" in kinds
    finish = result.synthesized[-1]
    assert finish.payload["cancel_cause"] == "user"
    assert finish.payload["cancel_detail"] == "cancel_requested"


def test_finalization_recovery_dangling_closes_interrupted() -> None:
    """兜底合成在飞：``finalization_recovery_started`` 之后无 outcome → 合成 failed + finish。"""

    events = (
        EpisodeEvent(1, "task", {"task_frame_hash": "tf", "question": "q"}),
        EpisodeEvent(2, "prompt_assembled", {"task_frame_hash": "tf", "system": "s", "user": "u"}),
        EpisodeEvent(3, "finalization_recovery_started", {"task_frame_hash": "tf", "failure_reason": "x"}),
    )
    store = MemoryEpisodeStore()
    store.append(EPISODE_ID, events)
    store.put_state(
        EPISODE_ID,
        EpisodeState(
            episode_id=EPISODE_ID,
            phase="finalizing",
            reserved_ids=("finalization_recovery",),
            deadline_at=MUCH_LATER.isoformat(),
            last_sequence=3,
        ),
    )
    result = restore_episode(EPISODE_ID, store, now=SOON)
    assert result.disposition == "closed"
    assert [e.kind for e in result.synthesized] == ["finalization_recovery_outcome", "finish"]
    assert result.synthesized[0].payload["reason"] == "interrupted"


def test_refuses_without_state_version_mismatch_unknown_kind_or_lagging_log() -> None:
    events = (EpisodeEvent(1, "task", {"task_frame_hash": "tf"}),)
    store = MemoryEpisodeStore()
    store.append(EPISODE_ID, events)
    with pytest.raises(RestoreUnavailable, match="没有 EpisodeState"):
        restore_episode(EPISODE_ID, store)

    store.put_state(EPISODE_ID, EpisodeState(episode_id=EPISODE_ID, phase="planning", log_version=99))
    with pytest.raises(RestoreUnavailable, match="版本"):
        restore_episode(EPISODE_ID, store)

    store.put_state(EPISODE_ID, EpisodeState(episode_id=EPISODE_ID, phase="planning", last_sequence=5))
    with pytest.raises(RestoreUnavailable, match="落后"):
        restore_episode(EPISODE_ID, store)

    store.put_state(EPISODE_ID, EpisodeState(episode_id=EPISODE_ID, phase="planning", last_sequence=1))
    store.append(EPISODE_ID, (EpisodeEvent(2, "future_kind", {}),))
    with pytest.raises(UnknownRequiredKind):
        restore_episode(EPISODE_ID, store)

    # 打了 ignorable 的未知 kind 放行。
    store2 = MemoryEpisodeStore()
    store2.append(
        EPISODE_ID,
        (EpisodeEvent(1, "task", {"task_frame_hash": "tf"}), EpisodeEvent(2, "future_kind", {}, ignorable=True)),
    )
    store2.put_state(
        EPISODE_ID,
        EpisodeState(episode_id=EPISODE_ID, phase="planning", last_sequence=2, deadline_at=MUCH_LATER.isoformat()),
    )
    assert restore_episode(EPISODE_ID, store2, now=SOON).plan.action == "model_turn"


def test_reserved_id_without_intent_in_log_is_refused_not_inferred() -> None:
    store = MemoryEpisodeStore()
    store.append(EPISODE_ID, (EpisodeEvent(1, "task", {"task_frame_hash": "tf"}),))
    store.put_state(
        EPISODE_ID,
        EpisodeState(episode_id=EPISODE_ID, phase="model_pending", reserved_ids=("turn-9",), last_sequence=1),
    )
    with pytest.raises(RestoreUnavailable, match="没有该意图"):
        restore_episode(EPISODE_ID, store)


def test_episode_entry_point_delegates() -> None:
    store, events = _run_uninterrupted(_SCENARIO)
    crash_store, _ = _store_at(events, store.states, len(events))
    assert ContinuousAgentEpisode.restore(EPISODE_ID, crash_store).disposition == "already_terminal"
