"""INV-4 取消语义。

起跑前已取消 → 不碰 registry、outcome 显式携带取消终态；批次执行中置取消
→ 未完成调用落 rejected/cancelled、无新派发（批次层，后端无关）。
"""

from __future__ import annotations

import pytest

from intelligence.runtime.episode_tool_batch import EpisodeToolBatchSession
from intelligence.services.agent_runtime import ModelToolCall
from intelligence.tests.conformance.backends import BACKENDS, BackendDescriptor, Verdict
from intelligence.tests.conformance.baseline import ratchet
from intelligence.tests.conformance.fixtures import (
    AUTHORIZED_TOOL,
    ScenarioProbe,
    ScriptedToolCall,
    ScriptedTurn,
    completed_finish,
    make_context,
    make_frame,
    make_registry,
)

INV = "INV-4"

_CANCELLED_STOP_REASONS = {"cancelled"}


@pytest.mark.parametrize("backend", BACKENDS, ids=lambda item: item.name)
def test_pre_dispatch_cancellation_is_honest_and_touches_nothing(
    backend: BackendDescriptor,
    request: pytest.FixtureRequest,
) -> None:
    ratchet(request, INV, backend.name)
    verdict = backend.verdict(INV)
    if verdict is Verdict.NOT_APPLICABLE:
        pytest.skip(f"declared not applicable: {backend.note(INV)}")

    probe = ScenarioProbe()
    frame = make_frame()
    context = make_context(frame, task_id=f"conf-inv4-{backend.name}")
    registry = make_registry(probe)
    run = backend.build_driver().run(
        initial=(
            ScriptedTurn(
                tool_calls=(ScriptedToolCall(AUTHORIZED_TOOL, "市场宽度"),),
            ),
            ScriptedTurn(finish=completed_finish()),
        ),
        frame=frame,
        context=context,
        registry=registry,
        probe=probe,
        is_cancelled=lambda: True,
    )

    assert probe.executed == [], (
        f"{backend.name} 已取消仍执行了工具：{probe.executed}"
    )
    assert run.outcome.stop_reason in _CANCELLED_STOP_REASONS, (
        f"{backend.name} 取消后的 stop_reason 不诚实：{run.outcome.stop_reason!r}"
    )
    assert run.outcome.status in {"failed", "partial"}
    assert run.outcome.evidence == ()


def test_mid_batch_cancellation_rejects_pending_calls_without_dispatch() -> None:
    """批次层（后端无关）：执行前置取消 → 全部 rejected/cancelled、零派发。"""

    probe = ScenarioProbe()
    frame = make_frame()
    context = make_context(frame, task_id="conf-inv4-batch")
    registry = make_registry(probe)
    session = EpisodeToolBatchSession()

    batch = session.execute(
        (
            ModelToolCall("cancel-1", AUTHORIZED_TOOL, {"query": "第一问"}),
            ModelToolCall("cancel-2", AUTHORIZED_TOOL, {"query": "第二问"}),
        ),
        registry=registry,
        context=context,
        remaining_slots=4,
        is_cancelled=lambda: True,
    )

    assert batch.executed_count == 0
    assert probe.executed == []
    assert [item.status for item in batch.items] == ["rejected", "rejected"]
    assert {item.error for item in batch.items} == {"cancelled"}


# ── INV-R4（运行底座终态稿 §3）：取消类型化；未派发 ≠ 超时 ────────────────────

INV_R4 = "INV-R4"


def _finish_payloads(outcome) -> list[dict[str, object]]:
    return [
        dict(event.payload) for event in outcome.events if event.kind == "finish"
    ]


@pytest.mark.parametrize("backend", BACKENDS, ids=lambda item: item.name)
def test_cancelled_finish_carries_a_typed_cause(
    backend: BackendDescriptor,
    request: pytest.FixtureRequest,
) -> None:
    """``stop_reason=cancelled`` ⇔ 终局带 ``cancel_cause ∈ CancelCause``。

    裸谓词上游（API 取消端点那种）默认记 ``user``。非适用臂只验「确实不在场」：
    有人给它加了 cancel_cause 却不改声明表，这里会红，逼人先改声明。
    """

    from intelligence.services.cancel_signal import CANCEL_CAUSES

    ratchet(request, INV_R4, backend.name)
    verdict = backend.verdict(INV_R4)
    if verdict is Verdict.NOT_APPLICABLE:
        pytest.skip(f"declared not applicable: {backend.note(INV_R4)}")

    probe = ScenarioProbe()
    frame = make_frame()
    context = make_context(frame, task_id=f"conf-inv-r4-{backend.name}")
    run = backend.build_driver().run(
        initial=(
            ScriptedTurn(
                tool_calls=(ScriptedToolCall(AUTHORIZED_TOOL, "市场宽度"),),
            ),
            ScriptedTurn(finish=completed_finish()),
        ),
        frame=frame,
        context=context,
        registry=make_registry(probe),
        probe=probe,
        is_cancelled=lambda: True,
    )
    finishes = _finish_payloads(run.outcome)
    assert run.outcome.stop_reason == "cancelled"

    if verdict is Verdict.SUPPORTED:
        assert finishes, f"{backend.name} 取消后没有 finish 事件"
        last = finishes[-1]
        assert last.get("stop_reason") == "cancelled"
        assert last.get("cancel_cause") in CANCEL_CAUSES, (
            f"{backend.name} 取消终局缺类型化原因：{last!r}"
        )
        assert last.get("cancel_cause") == "user", "裸谓词上游默认记 user"
        assert "cancel_detail" in last
    else:
        # 非适用臂：取消可能只体现在 outcome 上（sdk / codex 起跑前取消不发 finish 事件；
        # 词表也不同——README「差异不是缺口」）。只验「确实不在场」。
        assert all("cancel_cause" not in payload for payload in finishes), (
            f"{backend.name} 声明 {verdict.value} 却带了 cancel_cause——先改 backends.py 声明表"
        )


@pytest.mark.parametrize("backend", BACKENDS, ids=lambda item: item.name)
def test_uncancelled_finish_does_not_carry_cancel_fields(
    backend: BackendDescriptor,
    request: pytest.FixtureRequest,
) -> None:
    """反向：正常终局不带 cancel_* 键。带了就是把「没取消」写成了一种取消。"""

    ratchet(request, INV_R4, backend.name)
    if backend.verdict(INV_R4) is Verdict.NOT_APPLICABLE:
        pytest.skip(f"declared not applicable: {backend.note(INV_R4)}")

    probe = ScenarioProbe()
    frame = make_frame()
    context = make_context(frame, task_id=f"conf-inv-r4-neg-{backend.name}")
    run = backend.build_driver().run(
        initial=(
            ScriptedTurn(
                tool_calls=(ScriptedToolCall(AUTHORIZED_TOOL, "市场宽度"),),
            ),
            ScriptedTurn(finish=completed_finish()),
        ),
        frame=frame,
        context=context,
        registry=make_registry(probe),
        probe=probe,
    )
    for payload in _finish_payloads(run.outcome):
        assert payload.get("stop_reason") != "cancelled"
        assert "cancel_cause" not in payload and "cancel_detail" not in payload


def test_not_dispatched_and_real_timeout_are_distinct_codes() -> None:
    """批次层（后端无关）：零授权未派发 → ``tool_not_dispatched``；真跑超时 →
    ``tool_timeout``；取消 → ``cancelled``。三者互斥。

    09-01 之前前两者共用 tool_timeout，模型被骗去换工具（形态对齐收据「尝试 4 更正」）。
    """

    from intelligence.services.agent_research import AgentToolContext
    from intelligence.services.research_tool_registry import ResearchToolRegistry, ToolSpec

    probe = ScenarioProbe()
    frame = make_frame()

    zero_grant = EpisodeToolBatchSession().execute(
        (ModelToolCall("zg-1", AUTHORIZED_TOOL, {"query": "第一问"}),),
        registry=make_registry(probe),
        context=make_context(frame, task_id="conf-inv-r4-zero", timeout=0.0),
        remaining_slots=4,
    )
    assert zero_grant.executed_count == 0 and probe.executed == []
    assert [item.status for item in zero_grant.items] == ["timeout"]
    assert [item.error for item in zero_grant.items] == ["tool_not_dispatched"]

    def timing_out_runner(_query: str, _context: AgentToolContext):
        raise TimeoutError("provider deadline")

    slow_registry = ResearchToolRegistry(
        (
            ToolSpec(
                name=AUTHORIZED_TOOL,
                capability="market_data",
                description="慢工具",
                cost="local",
                freshness="current",
                runner=timing_out_runner,
            ),
        )
    )
    real_timeout = EpisodeToolBatchSession().execute(
        (ModelToolCall("rt-1", AUTHORIZED_TOOL, {"query": "第二问"}),),
        registry=slow_registry,
        context=make_context(frame, task_id="conf-inv-r4-real", timeout=30.0),
        remaining_slots=4,
    )
    assert [item.status for item in real_timeout.items] == ["timeout"]
    assert [item.error for item in real_timeout.items] == ["tool_timeout"]

    cancelled = EpisodeToolBatchSession().execute(
        (ModelToolCall("cx-1", AUTHORIZED_TOOL, {"query": "第三问"}),),
        registry=make_registry(probe),
        context=make_context(frame, task_id="conf-inv-r4-cancel", timeout=30.0),
        remaining_slots=4,
        is_cancelled=lambda: True,
    )
    assert [item.error for item in cancelled.items] == ["cancelled"]
