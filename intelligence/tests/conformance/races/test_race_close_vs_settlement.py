"""竞态⑤：close vs 结算（INV-R6）。

会话层 ``RuntimeHandle.close()`` 与 episode 账本里的结算是两层：Handle 不拥有执行，
close 只挡新工作。两序：close 在结算落账前到达（工作单元在飞）→ 结算照落、收据记
``closed_with_inflight``；close 在结算之后到达 → 结算照落、收据无该 note。
"""

from __future__ import annotations

from intelligence.services.runtime_handle import RuntimeHandle
from intelligence.tests.conformance.races._drive import (
    assert_no_orphan_intents,
    assert_store_mirrors_outcome,
    build_rig,
    model_pairs,
)


def _notes(handle: RuntimeHandle) -> list[str]:
    return [str(row["event"]) for row in handle.dump()["receipts"] if row["kind"] == "note"]


def test_order_a_close_arrives_while_settlement_is_pending() -> None:
    rig = build_rig("race-close-a")
    handle = RuntimeHandle(episode_id=rig.task_id, task_frame_hash=rig.frame.task_frame_hash)
    handle.mark_started()
    handle.mark_running()
    handle.begin_work("run")
    rig.start()
    point = rig.run_until("model_pending")
    assert point is not None

    handle.close("client_gone")  # 结算未落，工作单元在飞
    assert handle.state == "closed"
    assert "closed_with_inflight" in _notes(handle)

    outcome = rig.finish()
    handle.end_work("run")

    # Handle 关了不等于结算丢了：意图有结算，episode 走到 done。
    intent, settlement = model_pairs(outcome.events)[point.turn_id]
    assert settlement is not None and settlement > intent
    assert outcome.status == "completed"
    assert handle.dump()["in_flight"] == 0
    assert "work_ended" in _notes(handle)
    assert_no_orphan_intents(outcome.events)
    rig.oracle.assert_sandwich()
    assert_store_mirrors_outcome(rig, outcome)


def test_order_b_close_arrives_after_settlement() -> None:
    rig = build_rig("race-close-b")
    handle = RuntimeHandle(episode_id=rig.task_id, task_frame_hash=rig.frame.task_frame_hash)
    handle.mark_started()
    handle.mark_running()
    handle.begin_work("run")
    rig.start()
    point = rig.run_until("model_settled")
    assert point is not None

    outcome = rig.finish()
    handle.end_work("run")
    handle.close("done")

    assert handle.state == "closed"
    assert "closed_with_inflight" not in _notes(handle)
    intent, settlement = model_pairs(outcome.events)[point.turn_id]
    assert settlement is not None and settlement > intent
    assert outcome.status == "completed"
    assert_no_orphan_intents(outcome.events)
    rig.oracle.assert_sandwich()
    assert_store_mirrors_outcome(rig, outcome)
