"""竞态⑦：store.append 失败 vs 内存 ledger（INV-R6 / INV-R2 / INV-R3）。

既有契约（``test_inv_r2_write_order::test_store_failure_does_not_own_execution_but_is_receipted``）：
落盘失败不拥有执行，失败一次后不再写——半份日志比没有更会骗恢复。本条把它写成两序的
合法历史：store 在写**意图**时失败（A）或在写**结算**时失败（B）。两序都要求：内存账本
完整、episode 照常完成、store 只留失败前的严格前缀且此后零写入、finish 收据带失败序号；
且 durable 副本对 ``restore`` 仍自洽——B 序里 store 最后一条是意图，恢复读到「意图有、
结算无」给 ``retry_model``，不做任何别的猜测。
"""

from __future__ import annotations

from collections.abc import Sequence

from intelligence.runtime.agent_episode import ContinuousAgentEpisode
from intelligence.services.agent_runtime import EpisodeEvent
from intelligence.tests.conformance.oracle import WriteOrderOracle
from intelligence.tests.conformance.races._drive import (
    assert_no_orphan_intents,
    build_rig,
    finish_event,
)


class FailOnKindStore(WriteOrderOracle):
    """第一次遇到 ``fail_on`` 这种事件就抛；之后每次 append 都计数——契约要求这个数是 0。"""

    def __init__(self, fail_on: str) -> None:
        super().__init__()
        self.fail_on = fail_on
        self.failed_sequence: int | None = None
        self.appends_after_failure = 0

    def append(self, episode_id: str, events: Sequence[EpisodeEvent], *, sync: bool = False) -> None:
        if self.failed_sequence is not None:
            self.appends_after_failure += 1
        if self.failed_sequence is None and any(e.kind == self.fail_on for e in events):
            self.failed_sequence = events[0].sequence
            raise OSError("disk full")
        super().append(episode_id, events, sync=sync)


def _run(task_id: str, fail_on: str):
    store = FailOnKindStore(fail_on)
    rig = build_rig(task_id, store=store)
    rig.start()
    outcome = rig.finish()
    return rig, store, outcome


def _assert_prefix_and_receipt(rig, store: FailOnKindStore, outcome) -> None:
    assert outcome.status == "completed", "落盘失败不拥有执行"
    assert store.failed_sequence is not None
    assert store.appends_after_failure == 0, "失败后不得再写：半份日志会骗恢复"
    stored = rig.stored_events()
    memory = outcome.events
    assert [e.to_dict() for e in stored] == [e.to_dict() for e in memory[: store.failed_sequence - 1]]
    finish = finish_event(memory)
    assert list(finish.payload["store_failures"]) == [f"append#{store.failed_sequence}:OSError"]
    assert_no_orphan_intents(memory)
    # 重放 / 恢复读的是 store：它绝不能宣称 done。
    state = rig.stored_state()
    assert state is not None and state.phase != "done"
    assert rig.task_id in store.list_open()


def test_order_a_store_fails_on_an_intent_append() -> None:
    rig, store, outcome = _run("race-store-a", fail_on="model_intent")
    _assert_prefix_and_receipt(rig, store, outcome)

    # store 里连意图都没有：恢复从上一份完整状态出发，下一步是向模型开口，不是重试。
    result = ContinuousAgentEpisode.restore(rig.task_id, store)
    assert result.disposition == "resumable"
    assert result.plan is not None and result.plan.action == "model_turn"
    assert result.synthesized == ()
    assert len(rig.stored_events()) == store.failed_sequence - 1, "restore 一字不写"


def test_order_b_store_fails_on_a_settlement_append() -> None:
    rig, store, outcome = _run("race-store-b", fail_on="model_turn")
    _assert_prefix_and_receipt(rig, store, outcome)

    # store 最后一条是意图、结算丢了：恢复只给 retry_model（请求只读、可再问一次）。
    stored = rig.stored_events()
    assert stored[-1].kind == "model_intent"
    result = ContinuousAgentEpisode.restore(rig.task_id, store)
    assert result.disposition == "resumable"
    assert result.plan is not None and result.plan.action == "retry_model"
    assert result.plan.turn_id == stored[-1].payload["turn_id"]
    assert len(rig.stored_events()) == len(stored), "restore 一字不写"
