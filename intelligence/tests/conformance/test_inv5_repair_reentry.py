"""INV-5 判官缺口 → 修复续跑，或显式报告不支持。

声明支持的后端：session.resume(goal) 真的续跑（事件前缀保持 + 新 model_turn，
不重启研究）。声明不支持的后端（codex）：链路上游的判官照跑，修复缺席必须
在可观测面显式说出来——静默跳过判红。**本条对 codex 预期红并入 baseline，
是套件有效性的阳性对照**（continuous_turn_adapter._resume_for_gap 对无
resume 的 session 返回 None，零收据）。
"""

from __future__ import annotations

import pytest

from intelligence.tests.conformance.backends import BACKENDS, BackendDescriptor, Verdict
from intelligence.tests.conformance.baseline import ratchet
from intelligence.tests.conformance.fixtures import (
    AUTHORIZED_TOOL,
    ScenarioProbe,
    ScriptedToolCall,
    ScriptedTurn,
    completed_finish,
    explicit_repair_unsupported_markers,
    make_context,
    make_frame,
    make_registry,
    make_repair_goal,
    partial_finish,
)

INV = "INV-5"


def _initial_with_gap() -> tuple[ScriptedTurn, ...]:
    """产出一个必然带缺口的 outcome：证据在手，finish 却留 gap。"""

    return (
        ScriptedTurn(
            tool_calls=(ScriptedToolCall(AUTHORIZED_TOOL, "市场宽度"),),
        ),
        ScriptedTurn(finish=partial_finish()),
    )


@pytest.mark.parametrize("backend", BACKENDS, ids=lambda item: item.name)
def test_gap_triggers_resume_or_an_explicit_unsupported_receipt(
    backend: BackendDescriptor,
    request: pytest.FixtureRequest,
) -> None:
    ratchet(request, INV, backend.name)
    verdict = backend.verdict(INV)
    if verdict is Verdict.NOT_APPLICABLE:
        pytest.skip(f"declared not applicable: {backend.note(INV)}")

    probe = ScenarioProbe()
    frame = make_frame()
    task_id = f"conf-inv5-{backend.name}"
    context = make_context(frame, task_id=task_id)
    registry = make_registry(probe)
    driver = backend.build_driver()

    if verdict is Verdict.UNSUPPORTED_EXPLICIT:
        # 判官在 adapter 层照跑，修复对本后端不可用——那么「不可用」必须
        # 是显式收据（事件 / gap / stop_reason 任一可观测面），否则事后
        # 分诊看到的是「判官给了缺口，然后什么都没发生」。
        run = driver.run(
            initial=_initial_with_gap(),
            frame=frame,
            context=context,
            registry=registry,
            probe=probe,
        )
        markers = explicit_repair_unsupported_markers(run.outcome)
        assert markers, (
            f"{backend.name} 声明不支持修复，但缺席是静默的：outcome 的事件/"
            "gaps/stop_reason 里没有任何 repair-unsupported 类显式标记"
            "（_resume_for_gap 对无 resume 的 session 返回 None，零收据）"
        )
        return

    run = driver.start(
        initial=_initial_with_gap(),
        repairs=((ScriptedTurn(finish=completed_finish()),),),
        frame=frame,
        context=context,
        registry=registry,
        probe=probe,
    )
    try:
        assert run.session is not None, f"{backend.name} 声明支持修复却没有会话"
        previous = run.session.outcome
        updated = run.session.resume(make_repair_goal(task_id))
    finally:
        run.close()

    assert updated.events[: len(previous.events)] == previous.events, (
        "修复续跑改写了历史前缀（应续跑而不是重启）"
    )
    new_events = updated.events[len(previous.events) :]
    assert any(event.kind == "model_turn" for event in new_events), (
        "修复轮没有产生新的 model_turn"
    )
