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
