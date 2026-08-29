"""INV-2 工具预算耗尽强制收工。

预算 N=1（root 账本 hard_calls_cap=1 + policy.max_steps=1），脚本请求
2 次工具调用 → 第 2 次不执行、落显式拒绝收据；后端进入 finalization /
如实的 stop_reason，不静默吞掉超额请求。

root 账本走「预占」而不是事后计数（AGENTS.md 已确立原则第 1 条），四个
后端与网关共用同一本账，本夹具因此能跨后端统一预算语义。
"""

from __future__ import annotations

import pytest

from intelligence.services.research_contract import InMemoryRootBudgetLedger
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

INV = "INV-2"

# 同一不变量在不同后端的收据词表：continuous/sdk 走 slots/root 账本码；
# codex/stub 走网关，预算收工的码是 research_stage_closed（首跑实测，
# 网关同时发 finalization 事件 + must_finalize 预算面）。语义相同、码不同，
# 这正是套件要显式化的后端差异，不是缺口。
_BUDGET_REJECTIONS = {
    "tool_budget_exhausted",
    "root_budget_exhausted",
    "research_stage_closed",
}


def _scenario() -> tuple[ScriptedTurn, ...]:
    return (
        ScriptedTurn(
            tool_calls=(
                ScriptedToolCall(AUTHORIZED_TOOL, "第一问：市场宽度"),
                ScriptedToolCall(AUTHORIZED_TOOL, "第二问：超预算的那次"),
            ),
        ),
        ScriptedTurn(finish=completed_finish()),
        # continuous 的 finalization 轮如果多要一轮，兜底再给一次合法收尾。
        ScriptedTurn(finish=completed_finish()),
    )


def _budget(task_id: str) -> InMemoryRootBudgetLedger:
    return InMemoryRootBudgetLedger(
        episode_id=task_id,
        initial_calls=1,
        hard_calls_cap=1,
        initial_seconds=30.0,
        hard_seconds_cap=30.0,
    )


@pytest.mark.parametrize("backend", BACKENDS, ids=lambda item: item.name)
def test_budget_exhaustion_forces_finalization(
    backend: BackendDescriptor,
    request: pytest.FixtureRequest,
) -> None:
    ratchet(request, INV, backend.name)
    verdict = backend.verdict(INV)
    if verdict is Verdict.NOT_APPLICABLE:
        pytest.skip(f"declared not applicable: {backend.note(INV)}")

    probe = ScenarioProbe()
    frame = make_frame()
    task_id = f"conf-inv2-{backend.name}"
    context = make_context(
        frame,
        task_id=task_id,
        max_steps=1,
        root_budget=_budget(task_id),
    )
    registry = make_registry(probe)
    run = backend.build_driver().run(
        initial=_scenario(),
        frame=frame,
        context=context,
        registry=registry,
        probe=probe,
    )

    # 第 N+1 次不执行：runner 恰好跑了 1 次。
    assert len(probe.executed) == 1, (
        f"{backend.name} 预算 1 却执行了 {len(probe.executed)} 次：{probe.executed}"
    )

    # 超额那次要有显式拒绝收据，不能静默消失。
    explicit_rejections: list[str] = []
    for event in run.outcome.events:
        if event.kind != "tool_error":
            continue
        error = str(event.payload.get("error") or "")
        if error in _BUDGET_REJECTIONS:
            explicit_rejections.append(error)
    for observation in probe.sdk_observations:
        error = str(observation.get("error") or "")
        if error in _BUDGET_REJECTIONS:
            explicit_rejections.append(error)
    for result in probe.codex_tool_results:
        error = str(result.get("error") or "")
        if error in _BUDGET_REJECTIONS:
            explicit_rejections.append(error)
    assert explicit_rejections, (
        f"{backend.name} 超预算调用没有显式拒绝收据"
        f"（events/observations 均无 {_BUDGET_REJECTIONS}）"
    )

    # stop_reason 如实：预算收工要么走 finalization 后 model_finish，要么
    # 显式说预算耗尽——不允许出现「像是正常研究完成」以外的静默形状。
    assert run.outcome.stop_reason, "stop_reason 为空"

    if backend.name == "continuous_glm":
        # 强制收工的可观测面：finalization 轮模型工具面必须为空。
        assert probe.visible_tools, "没有捕获到模型可见工具面"
        assert probe.visible_tools[-1] == (), (
            f"finalization 轮模型仍看得到工具：{probe.visible_tools[-1]}"
        )
