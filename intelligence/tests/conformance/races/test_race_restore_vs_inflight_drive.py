"""竞态⑧：restore vs 仍在飞的驱动（INV-R6 / INV-R3）。

P2 的决定：``restore`` 只给 ``ResumePlan``，不重新驱动、不写一字。所以它与在飞驱动的两序
都安全**由构造保证**——本条把这个保证钉成测试：驱动停在 model_pending 时调 restore（A），
或驱动结束后调 restore（B），两序里 restore 都零写入，且该 turn_id 恰一条结算。
"""

from __future__ import annotations

from intelligence.runtime.agent_episode import ContinuousAgentEpisode
from intelligence.tests.conformance.races._drive import (
    assert_no_orphan_intents,
    assert_store_mirrors_outcome,
    build_rig,
    model_pairs,
    only,
)


def test_order_a_restore_while_drive_is_paused_at_model_pending() -> None:
    rig = build_rig("race-restore-a")
    rig.start()
    point = rig.run_until("model_pending")
    assert point is not None
    stored_before = rig.stored_events()
    state_before = rig.stored_state()
    assert state_before is not None and state_before.phase == "model_pending"

    result = ContinuousAgentEpisode.restore(rig.task_id, rig.oracle)

    # restore 看到的是「意图有、结算无」：给 retry_model，指向同一个 turn_id。
    assert result.disposition == "resumable"
    assert result.plan is not None
    assert result.plan.action == "retry_model" and result.plan.turn_id == point.turn_id
    assert result.synthesized == ()
    # 一字不写：事件数与状态都没动。
    assert rig.stored_events() == stored_before
    assert rig.stored_state() == state_before

    outcome = rig.finish()

    # 在飞驱动照常结算：该 turn_id 恰一条结算，终态 done，store 与 outcome 同形。
    settlements = [e for e in only(outcome.events, "model_turn") if e.payload["turn_id"] == point.turn_id]
    assert len(settlements) == 1
    intent, settlement = model_pairs(outcome.events)[point.turn_id]
    assert settlement == settlements[0].sequence > intent
    assert outcome.status == "completed"
    assert_no_orphan_intents(outcome.events)
    rig.oracle.assert_sandwich()
    assert_store_mirrors_outcome(rig, outcome)


def test_restore_lists_unclaimed_inbox_messages_and_clears_them_once_claimed() -> None:
    """P3 遗留、P4 收：崩溃现场里入箱未认领的话由 restore 列出（只列不认领）。"""

    rig = build_rig("race-restore-inbox")
    rig.start()
    assert rig.run_until("model_pending") is not None
    receipt = rig.episode.steer("补一句：只看主板", target="next_step")
    assert receipt.accepted

    paused = ContinuousAgentEpisode.restore(rig.task_id, rig.oracle)
    assert paused.pending_inbox == (receipt.message_id,)
    assert paused.to_dict()["pending_inbox"] == [receipt.message_id]

    outcome = rig.finish()
    assert outcome.status == "completed"
    # 下一次请求前认领了它：终态里没有未决的话。
    assert [e.kind for e in only(outcome.events, "inbox_claimed")] == ["inbox_claimed"]
    assert ContinuousAgentEpisode.restore(rig.task_id, rig.oracle).pending_inbox == ()


def test_order_b_restore_after_drive_finished() -> None:
    rig = build_rig("race-restore-b")
    rig.start()
    outcome = rig.finish()
    assert outcome.status == "completed"
    stored_before = rig.stored_events()

    result = ContinuousAgentEpisode.restore(rig.task_id, rig.oracle)

    assert result.disposition == "already_terminal"
    assert result.plan is None
    assert result.synthesized == ()
    assert rig.stored_events() == stored_before
    assert rig.oracle.list_open() == ()
    assert_store_mirrors_outcome(rig, outcome)
