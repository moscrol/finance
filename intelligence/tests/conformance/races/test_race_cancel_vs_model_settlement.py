"""竞态①：cancel vs model_turn 结算（INV-R6 / INV-R4）。

两序：取消在模型请求在飞时到达（意图已 durable、结算未落），或在结算落账之后到达。
两种合法历史都要求：结算仍落账（意图不留孤儿）、finish 带类型化取消原因、写序三明治成立。
"""

from __future__ import annotations

from intelligence.tests.conformance.races._drive import (
    assert_no_orphan_intents,
    assert_store_mirrors_outcome,
    build_rig,
    finish_event,
    kinds,
    model_pairs,
    only,
)


def test_order_a_cancel_arrives_while_model_request_is_in_flight() -> None:
    rig = build_rig("race-cancel-model-a")
    rig.start()
    point = rig.run_until("model_pending")
    assert point is not None and point.turn_id
    # 意图已 durable、结算未落——这一刻取消到达。
    assert rig.signal.request("user", "cancel while model in flight")

    outcome = rig.finish()

    finish = finish_event(outcome.events)
    assert outcome.status == "failed" and outcome.stop_reason == "cancelled"
    assert finish.payload["stop_reason"] == "cancelled"
    assert finish.payload["cancel_cause"] == "user"
    # 结算照落：同一个 turn_id 的 model_turn 在 finish 之前；没有第二条意图。
    pairs = model_pairs(outcome.events)
    assert list(pairs) == [point.turn_id]
    intent, settlement = pairs[point.turn_id]
    assert settlement is not None and intent < settlement < finish.sequence
    # 模型点了工具，但取消先于派发：没有任何 tool_request。
    assert only(outcome.events, "tool_request") == []
    assert rig.model.calls == 1
    assert_no_orphan_intents(outcome.events)
    rig.oracle.assert_sandwich()
    assert_store_mirrors_outcome(rig, outcome)


def test_order_b_cancel_arrives_after_model_settlement_and_tool_batch() -> None:
    rig = build_rig("race-cancel-model-b")
    rig.start()
    point = rig.run_until("tools_settled")
    assert point is not None
    assert rig.signal.request("user", "cancel after settlement")

    outcome = rig.finish()

    finish = finish_event(outcome.events)
    assert outcome.stop_reason == "cancelled"
    assert finish.payload["cancel_cause"] == "user"
    # 与 A 序的差别：这一序工具批次完整结算并入账，之后才取消；模型没被再问。
    assert kinds(outcome.events, "tool_request", "tool_result") == ["tool_request", "tool_result"]
    assert len(only(outcome.events, "model_intent")) == 1 == len(only(outcome.events, "model_turn"))
    assert rig.model.calls == 1
    assert outcome.evidence, "结算过的证据不因随后的取消而丢"
    assert_no_orphan_intents(outcome.events)
    rig.oracle.assert_sandwich()
    assert_store_mirrors_outcome(rig, outcome)
