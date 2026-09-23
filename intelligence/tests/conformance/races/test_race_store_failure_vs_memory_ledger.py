"""竞态⑦：store.append 失败 vs 内存 ledger（INV-R6 / INV-R2 / INV-R3）。

OPT-08 改变旧合同：必需保存失败停止新效果，不再按 completed 返回。
store 在意图（A）或结算（B）写入失败：内存保留已发生结果，durable 留严格前缀，
后续零写入、零新派发。B 序最后只有意图，restore 仍可能建议 retry_model——这是
磁盘无法保存故障时不可消除的不确定性，尚未授权自动恢复驱动，不得视为免费重试。
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
    assert outcome.status == "failed"
    assert outcome.stop_reason == "storage_failed"
    assert outcome.persistence == "failed"
    assert rig.model.calls == (0 if store.fail_on == "model_intent" else 1)
    assert outcome.usage.tool_calls == 0
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

    # Current authority comes from the fixture, not the saved snapshot.
    # An absent intent still does not prove zero cost or authorize execution.
    result = ContinuousAgentEpisode.restore(rig.task_id, store, context=rig.context, registry=rig.registry)
    assert result.disposition == "resumable"
    assert result.plan is not None and result.plan.action == "model_turn"
    assert result.synthesized == ()
    assert len(rig.stored_events()) == store.failed_sequence - 1, "restore 一字不写"


def test_order_b_store_fails_on_a_settlement_append() -> None:
    rig, store, outcome = _run("race-store-b", fail_on="model_turn")
    _assert_prefix_and_receipt(rig, store, outcome)

    # store 最后一条是意图、结算丢了：只给 retry_model 判定，不保证前次未计费或可安全重试。
    stored = rig.stored_events()
    assert stored[-1].kind == "model_intent"
    result = ContinuousAgentEpisode.restore(rig.task_id, store, context=rig.context, registry=rig.registry)
    assert result.disposition == "resumable"
    assert result.plan is not None and result.plan.action == "retry_model"
    assert result.plan.turn_id == stored[-1].payload["turn_id"]
    # 「不保证前次未计费」不再只是这句注释：那段未知窗口落成一条凭证。恢复仍不写
    # **结算**、不推进位置；它写的是一个答不了的问题，而不是一个方便的假设。
    after = rig.stored_events()
    assert [e.kind for e in after[len(stored):]] == ["effects_unknown"]
    assert [e.reserved_id for e in result.unreconciled_effects] == [stored[-1].payload["turn_id"]]
    assert result.unreconciled_effects[0].disposition == "retry_proposed"
