"""竞态③：cancel vs finish（INV-R6 / INV-R4）。

两序：取消在模型给出终局之后、准入之前到达；或在终局已获准入、finish 将落那一刻到达。
两种合法历史都只允许**恰一条** finish；差别在 stop_reason：前者 cancelled，后者 model_finish。
"""

from __future__ import annotations

from intelligence.tests.conformance.races._drive import (
    assert_no_orphan_intents,
    assert_store_mirrors_outcome,
    build_rig,
    finish_event,
    only,
)


def test_order_a_cancel_arrives_after_final_answer_before_admission() -> None:
    rig = build_rig("race-cancel-finish-a")
    rig.start()
    assert rig.run_until("model_settled") is not None  # 第一轮：点工具
    second = rig.run_until("model_settled")  # 第二轮：模型给出终局
    assert second is not None and second.llm_calls == 2
    assert rig.signal.request("user", "cancel before admission")

    outcome = rig.finish()

    finish = finish_event(outcome.events)
    assert outcome.status == "failed" and outcome.stop_reason == "cancelled"
    assert finish.payload["stop_reason"] == "cancelled"
    assert finish.payload["cancel_cause"] == "user"
    # 模型写好的终局留在历史里，但没有被采纳成 completed。
    assert outcome.draft == "" or outcome.status != "completed"
    assert len(only(outcome.events, "model_turn")) == 2
    assert_no_orphan_intents(outcome.events)
    rig.oracle.assert_sandwich()
    assert_store_mirrors_outcome(rig, outcome)


def test_order_b_cancel_arrives_after_admission_as_finish_is_written() -> None:
    rig = build_rig("race-cancel-finish-b")
    rig.start()
    point = rig.run_until("before_finish")
    assert point is not None and point.llm_calls == 2
    assert rig.signal.request("user", "cancel too late")

    outcome = rig.finish()

    finish = finish_event(outcome.events)
    # 终局已准入：取消来晚了，finish 照落且不带取消原因。
    assert outcome.status == "completed" and outcome.stop_reason == "model_finish"
    assert finish.payload["stop_reason"] == "model_finish"
    assert "cancel_cause" not in finish.payload
    assert outcome.draft
    assert rig.signal.requested, "信号本身仍记着取消——只是 episode 已经结束"
    assert_no_orphan_intents(outcome.events)
    rig.oracle.assert_sandwich()
    assert_store_mirrors_outcome(rig, outcome)
