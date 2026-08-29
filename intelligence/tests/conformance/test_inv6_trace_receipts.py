"""INV-6 trace / 收据对账。

model_turn / tool_request / tool_result(tool_error) 在 durable 事件流里
成对完整、投影无异常（全后端）；接了 RuntimeHandle 的臂，六态生命周期
收据合法（只进不退、scope_attached 与声明一致、close 落终态）。
"""

from __future__ import annotations

import pytest

from intelligence.services.episode_projection import project_durable_events
from intelligence.services.runtime_handle import _STATE_ORDER
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
    tool_event_pairs,
)

INV = "INV-6"


def _scenario() -> tuple[ScriptedTurn, ...]:
    return (
        ScriptedTurn(
            tool_calls=(ScriptedToolCall(AUTHORIZED_TOOL, "市场宽度"),),
        ),
        ScriptedTurn(finish=completed_finish()),
    )


@pytest.mark.parametrize("backend", BACKENDS, ids=lambda item: item.name)
def test_tool_events_pair_up_and_projection_is_clean(
    backend: BackendDescriptor,
    request: pytest.FixtureRequest,
) -> None:
    ratchet(request, INV, backend.name)
    verdict = backend.verdict(INV)
    if verdict is Verdict.NOT_APPLICABLE:
        pytest.skip(f"declared not applicable: {backend.note(INV)}")

    probe = ScenarioProbe()
    frame = make_frame()
    context = make_context(frame, task_id=f"conf-inv6-{backend.name}")
    registry = make_registry(probe)
    run = backend.build_driver().run(
        initial=_scenario(),
        frame=frame,
        context=context,
        registry=registry,
        probe=probe,
    )

    requests, results, errors = tool_event_pairs(run.outcome)
    assert requests, f"{backend.name} 工具执行没有留下 tool_request 事件"
    assert len(requests) == len(results) + len(errors), (
        f"{backend.name} 工具事件不成对：request={len(requests)} "
        f"result={len(results)} error={len(errors)}"
    )
    request_ids = [
        str(payload.get("request_id") or payload.get("call_id") or "")
        for payload in requests
    ]
    close_ids = [
        str(payload.get("request_id") or payload.get("call_id") or "")
        for payload in (*results, *errors)
    ]
    if any(request_ids):
        assert sorted(request_ids) == sorted(close_ids), (
            f"{backend.name} 工具事件 id 配不上：{request_ids} vs {close_ids}"
        )

    projection = project_durable_events(run.outcome.events)
    assert not projection.has_anomalies, (
        f"{backend.name} durable 事件投影有异常：{projection.anomalies_to_dict()}"
    )


@pytest.mark.parametrize("backend", BACKENDS, ids=lambda item: item.name)
def test_runtime_handle_receipts_are_monotonic_when_attached(
    backend: BackendDescriptor,
    request: pytest.FixtureRequest,
) -> None:
    ratchet(request, INV, backend.name)
    verdict = backend.verdict(INV)
    if verdict is Verdict.NOT_APPLICABLE:
        pytest.skip(f"declared not applicable: {backend.note(INV)}")
    if not backend.attaches_runtime_handle:
        pytest.skip(
            f"declared no runtime handle seam: {backend.note(INV) or backend.name}"
        )

    probe = ScenarioProbe()
    frame = make_frame()
    task_id = f"conf-inv6-handle-{backend.name}"
    context = make_context(frame, task_id=task_id)
    registry = make_registry(probe)
    run = backend.build_driver().start(
        initial=_scenario(),
        frame=frame,
        context=context,
        registry=registry,
        probe=probe,
    )
    assert run.session is not None
    handle = getattr(run.session, "runtime_handle", None)
    assert handle is not None, f"{backend.name} 声明接 Handle 但 session 没带"

    live = handle.dump()
    assert live["episode_id"] == task_id
    assert live["state"] == "running"
    # 收据必须如实反映 Scope 声明：SDK 档不构造 Scope，scope_attached
    # 「如实为假」是设计决定，不是缺口（openai_agents_runtime.start 注释）。
    assert live["scope_attached"] is backend.attaches_scope

    run.close()
    closed = handle.dump()
    assert closed["state"] == "closed"
    transitions = [
        str(row["state"])
        for row in closed["receipts"]
        if row.get("kind") == "transition"
    ]
    orders = [_STATE_ORDER[state] for state in transitions]
    assert orders == sorted(orders), f"六态收据出现回退：{transitions}"
    assert len(set(transitions)) == len(transitions), (
        f"六态收据出现原地重复转移：{transitions}"
    )
