"""竞态④：steer vs 模型停下（INV-R6 / INV-R5）。

INV-R5 套件（``test_inv_r5_inbox.py``）用模型钩子已钉过两序；这里用步点把同一条竞态
放进目录：话在请求前到达就在请求前认领（A），话在模型停下后到达就在停机点认领、再给一轮（B）。
两种历史都不丢话，且 ``inbox_claimed`` 先于把话送给模型的那条 ``model_intent``。
"""

from __future__ import annotations

from intelligence.tests.conformance.fixtures import ScriptedTurn, completed_finish
from intelligence.tests.conformance.races._drive import (
    assert_no_orphan_intents,
    assert_store_mirrors_outcome,
    build_rig,
    kinds,
    only,
    tool_then_finish,
)


def _claim_before_intent(events, *, claimed_index: int, intent_index: int) -> None:
    claimed = only(events, "inbox_claimed")[claimed_index]
    intent = only(events, "model_intent")[intent_index]
    assert claimed.sequence < intent.sequence


def test_order_a_steer_arrives_before_the_next_request() -> None:
    rig = build_rig("race-steer-a")
    rig.start()
    assert rig.run_until("tools_settled") is not None
    receipt = rig.episode.steer("补一句：只看主板", target="next_step")
    assert receipt.accepted

    outcome = rig.finish()

    assert outcome.status == "completed"
    assert kinds(outcome.events, "inbox_inserted", "inbox_claimed") == ["inbox_inserted", "inbox_claimed"]
    # 认领在第二次请求的意图之前：模型这一轮就看到话，不多开一轮。
    _claim_before_intent(outcome.events, claimed_index=0, intent_index=1)
    assert rig.model.calls == 2
    assert_no_orphan_intents(outcome.events)
    rig.oracle.assert_sandwich()
    assert_store_mirrors_outcome(rig, outcome)


def test_order_b_steer_arrives_after_the_model_stopped() -> None:
    turns = [*tool_then_finish(), ScriptedTurn(finish=completed_finish())]
    rig = build_rig("race-steer-b", turns=turns)
    rig.start()
    assert rig.run_until("model_settled") is not None  # 第一轮
    second = rig.run_until("model_settled")  # 第二轮：模型停下（给出终局）
    assert second is not None and second.llm_calls == 2
    receipt = rig.episode.steer("等一下，再核一次", target="next_turn")
    assert receipt.accepted

    outcome = rig.finish()

    assert outcome.status == "completed"
    assert kinds(outcome.events, "inbox_inserted", "inbox_claimed") == ["inbox_inserted", "inbox_claimed"]
    # 停机点认领、再给一轮：三次模型请求，认领在第三条意图之前、第二条结算之后。
    assert rig.model.calls == 3
    _claim_before_intent(outcome.events, claimed_index=0, intent_index=2)
    claimed = only(outcome.events, "inbox_claimed")[0]
    assert claimed.sequence > only(outcome.events, "model_turn")[1].sequence
    assert_no_orphan_intents(outcome.events)
    rig.oracle.assert_sandwich()
    assert_store_mirrors_outcome(rig, outcome)
