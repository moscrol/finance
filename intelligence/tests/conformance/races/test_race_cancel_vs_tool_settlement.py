"""竞态②：cancel vs tool_result 结算（INV-R6 / INV-R2）。

两序：取消在工具执行中到达（runner 里翻信号），或在批次结算落账之后到达。
两种合法历史都要求：每条 tool_request 意图都有结算（无孤儿），随后 finish{cancelled}。
"""

from __future__ import annotations

from intelligence.services.cancel_signal import CancelSignal
from intelligence.tests.conformance.races._drive import (
    TOOL_SETTLEMENTS,
    assert_no_orphan_intents,
    assert_store_mirrors_outcome,
    build_rig,
    finish_event,
    only,
    tool_pairs,
)


def test_order_a_cancel_arrives_while_tool_is_executing() -> None:
    holder: dict[str, CancelSignal] = {}

    def flip_during_tool() -> None:
        assert holder["signal"].request("user", "cancel during tool")

    rig = build_rig("race-cancel-tool-a", during_tool=flip_during_tool)
    holder["signal"] = rig.signal
    rig.start()

    outcome = rig.finish()

    finish = finish_event(outcome.events)
    assert outcome.stop_reason == "cancelled" and finish.payload["cancel_cause"] == "user"
    pairs = tool_pairs(outcome.events)
    assert len(pairs) == 1
    (intent, settlement), = pairs.values()
    assert settlement is not None and intent < settlement < finish.sequence
    settled_kind = next(e.kind for e in outcome.events if e.sequence == settlement)
    assert settled_kind in TOOL_SETTLEMENTS
    # 取消是在批次里被观测到的：模型不再被问第二次。
    assert rig.model.calls == 1
    assert_no_orphan_intents(outcome.events)
    rig.oracle.assert_sandwich()
    assert_store_mirrors_outcome(rig, outcome)


def test_order_b_cancel_arrives_after_tool_batch_settled() -> None:
    rig = build_rig("race-cancel-tool-b")
    rig.start()
    point = rig.run_until("tools_settled")
    assert point is not None and point.tool_calls == 1
    assert rig.signal.request("user", "cancel after batch")

    outcome = rig.finish()

    finish = finish_event(outcome.events)
    assert outcome.stop_reason == "cancelled"
    # 与 A 序的差别：结算是 tool_result（成功），证据已入账，取消在其后。
    assert [e.kind for e in only(outcome.events, "tool_result")] == ["tool_result"]
    assert outcome.evidence and outcome.evidence[0].tool == "market_data"
    (intent, settlement), = tool_pairs(outcome.events).values()
    assert settlement is not None and settlement < finish.sequence
    assert rig.model.calls == 1
    assert_no_orphan_intents(outcome.events)
    rig.oracle.assert_sandwich()
    assert_store_mirrors_outcome(rig, outcome)
