"""未知效果对账（``intelligence/services/episode_effects.py``）。

被测的核心命题只有一句：**未知效果双向保守——对证据按「没发生」处理，对成本按「已发生」
处理。** 本文件验证成本那一半（证据那一半在 ``test_episode_restore.py``：合成
``interrupted`` 结算、绝不伪造结果），外加三条不让这个机制自己变成新 bug 的性质：

1. 重复恢复不得让清单膨胀（否则将来对账会按重启次数重复扣费——把少记账换成多记账）；
2. 热路径检查点不得抹掉凭证（否则下一个 ``put_state`` 就把「有笔账没对」静默改写成无账可对）；
3. 未派发的声明不得进清单（虚报与漏报同样是错）——那条在 ``test_episode_restore.py``。
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from intelligence.services import research_contract as budgets
from intelligence.services.agent_runtime import EpisodeEvent
from intelligence.services.episode_effects import (
    UnknownEffect,
    charge_unknown_effects,
    merge_unknown_effects,
    unknown_effects_from_payload,
    unknown_effects_payload,
)
from intelligence.services.episode_restore import restore_episode
from intelligence.services.episode_store import EpisodeState, JsonlEpisodeStore, MemoryEpisodeStore
from intelligence.services.research_contract import ResearchPolicy, release_root_budget, root_budget_for_policy


def _model_effect(**overrides: object) -> UnknownEffect:
    base: dict[str, object] = {
        "effect": "model",
        "reserved_id": "turn-1",
        "intent_sequence": 2,
        "disposition": "settled_interrupted",
        "cost": "external",
        "io_effect": "external_or_mixed",
    }
    base.update(overrides)
    return UnknownEffect(**base)  # type: ignore[arg-type]


# ── 凭证本身 ───────────────────────────────────────────────────────────────


def test_corrupt_receipt_raises_instead_of_being_skipped() -> None:
    """读不懂的凭证要炸，不能跳过。

    跳过一条读不懂的未清记录，等于把「有笔账没对」降级成「没有账要对」——那正是这个
    模块要堵的那类静默假设，用它自己的读取器再犯一次就太讽刺了。
    """

    good = _model_effect().to_dict()
    for damaged in (
        {**good, "effect": "database"},
        {**good, "disposition": "probably_fine"},
        {**good, "intent_sequence": 0},
        {**good, "reserved_id": ""},
        {**good, "intent_sequence": True},  # bool 是 int 的子类，必须单独挡
        {**good, "settled": "yes"},  # 本读者不认识的键可能承载着对账语义
    ):
        with pytest.raises(ValueError):
            unknown_effects_from_payload([damaged])

    with pytest.raises(ValueError):
        unknown_effects_from_payload({"effect": "model"})  # 单个对象不是清单


def test_unrecognised_declarations_count_as_possibly_billed() -> None:
    """``unknown`` 一律按「可能已计费」算：fail closed 的方向是多记账，不是少记账。"""

    assert _model_effect().may_have_been_billed is True  # 模型轮一律算
    assert UnknownEffect(
        effect="tool", reserved_id="c1", intent_sequence=3,
        disposition="settled_interrupted", name="quote",
    ).may_have_been_billed is True  # 默认全 unknown → 可能已计费
    assert UnknownEffect(
        effect="tool", reserved_id="c1", intent_sequence=3,
        disposition="settled_interrupted", name="cache", cost="local", io_effect="local_read",
    ).may_have_been_billed is False  # 只有两项都声明为本地读才算不花钱
    assert UnknownEffect(
        effect="tool", reserved_id="c1", intent_sequence=3,
        disposition="settled_interrupted", name="cache", cost="local", io_effect="unknown",
    ).may_have_been_billed is True  # 一项说不清就算说不清


def test_merge_is_idempotent_and_keeps_the_first_observation() -> None:
    """并集必须幂等：同一段窗口被观察 N 次仍只有一条。

    后来的恢复决定改变不了「这段窗口没对账」这个事实，所以首次记录不被覆盖。
    """

    first = _model_effect(disposition="retry_proposed")
    later = _model_effect(disposition="settled_interrupted")
    other = _model_effect(reserved_id="turn-2", intent_sequence=7)

    merged = merge_unknown_effects([first], [later, other])
    assert [e.reserved_id for e in merged] == ["turn-1", "turn-2"]  # 按意图序号排
    assert merged[0].disposition == "retry_proposed"  # 首次观察胜出
    assert merge_unknown_effects(merged, merged) == merged  # 幂等


# ── 保守扣账 ───────────────────────────────────────────────────────────────


def _snapshot(episode: str, *, calls: int = 3) -> dict[str, object]:
    root = root_budget_for_policy(ResearchPolicy("quick", calls, 30, 10), episode_id=episode)
    try:
        return root.to_snapshot()
    finally:
        release_root_budget(episode)


def test_charge_debits_call_slots_only_and_never_invents_a_negative_balance() -> None:
    """扣格不扣秒；格数不够就如实记，不记成负余额。

    不扣秒不是偷懒：崩溃到重启之间的挂钟时间与那次调用的真实耗时毫无关系，
    编一个数字是在伪造测量值。一条意图至多一次调用，这个上界才是硬的。
    """

    snapshot = _snapshot(f"charge-{uuid4().hex}", calls=3)
    before_seconds = snapshot["remaining_seconds"]

    debited, receipt = charge_unknown_effects(snapshot, (_model_effect(), _model_effect(reserved_id="t2")))
    assert receipt == {"effects": 2, "slots_charged": 2, "slots_unavailable": 0, "possibly_billed": 2}
    assert debited["remaining_calls"] == 1
    assert debited["remaining_seconds"] == before_seconds  # 秒一字未动
    assert snapshot["remaining_calls"] == 3  # 纯函数：入参不被就地改写

    # 余额兜不住：扣到 0 为止，剩下的如实记成扣不动，绝不写出负余额。
    overdrawn, receipt2 = charge_unknown_effects(
        debited, tuple(_model_effect(reserved_id=f"t{i}") for i in range(4))
    )
    assert receipt2["slots_charged"] == 1 and receipt2["slots_unavailable"] == 3
    assert overdrawn["remaining_calls"] == 0


def test_reconciling_without_a_snapshot_refuses_rather_than_writing_off_the_debt() -> None:
    """旧日志没有预算快照时拒绝，而不是返回一份「已对账」的空快照把账销掉。"""

    with pytest.raises(ValueError, match="without a budget snapshot"):
        charge_unknown_effects(None, (_model_effect(),))


# ── 花钱前的闸 ─────────────────────────────────────────────────────────────


def test_spending_an_unreconciled_balance_is_refused_and_the_list_is_the_dedup_token() -> None:
    """闸：未对账不放行；对账后清单为空，重复对账在结构上不可能发生。

    去重凭证放在状态而不是预算快照里，是这道闸唯一的实现代价来源——放对了地方，
    「对账 = 扣账 + 清空」就是一次原子跃迁，不需要另造一套 dedup identity。
    """

    episode = f"gate-{uuid4().hex}"
    snapshot = _snapshot(episode, calls=3)
    effects = (_model_effect(),)

    with pytest.raises(ValueError, match="unreconciled"):
        budgets.restore_root_budget(
            snapshot, episode_id=episode, unreconciled_effects=unknown_effects_payload(effects),
        )

    debited, _ = charge_unknown_effects(snapshot, effects)
    try:
        ledger = budgets.restore_root_budget(debited, episode_id=episode, unreconciled_effects=())
        assert ledger.remaining_calls == 2  # 3 − 1 格
    finally:
        release_root_budget(episode)


def test_the_gate_has_no_default_so_a_forgetful_caller_cannot_slip_through() -> None:
    """``unreconciled_effects`` 是必填的。

    给它一个 ``()`` 默认值等于让「忘了传」自动变成「没有账要对」——与入口身份那轮同一条
    纪律：缺席不能被任何一方替对方填上。
    """

    episode = f"required-{uuid4().hex}"
    snapshot = _snapshot(episode)
    with pytest.raises(TypeError):
        budgets.restore_root_budget(snapshot, episode_id=episode)  # type: ignore[call-arg]


# ── 两条防自伤性质 ─────────────────────────────────────────────────────────


def _dangling_model_episode(tmp_path, *, retries: int):
    """一条只落了 ``model_intent`` 就崩的 episode；``retries>0`` 走 retry_model 那条路。"""

    from intelligence.services.episode_authorization import capture_authorization_snapshot
    from intelligence.services.evidence_ledger import EvidenceLedger
    from intelligence.tests.conformance.fixtures import ScenarioProbe, make_context, make_frame, make_registry

    episode = f"dangling-{uuid4().hex}"
    context = make_context(make_frame(), task_id=episode)
    context = replace(context, contract=replace(context.contract, task_frame_hash="tf"))
    registry = make_registry(ScenarioProbe())
    evidence = EvidenceLedger(
        information_cutoff=context.information_cutoff.as_of_date
    ).to_recovery_snapshot(episode_id=episode, presented_evidence=())
    now = datetime(2026, 9, 18, tzinfo=timezone.utc)
    store = JsonlEpisodeStore(tmp_path)
    store.append(
        episode,
        (
            EpisodeEvent(1, "task", {"task_frame_hash": "tf"}),
            EpisodeEvent(2, "model_intent", {"turn_id": "turn-1"}),
        ),
        sync=True,
    )
    store.put_state(
        episode,
        EpisodeState(
            episode_id=episode, phase="model_pending", reserved_ids=("turn-1",),
            deadline_at=(now + timedelta(minutes=2)).isoformat(), retry={"remaining": retries},
            last_sequence=2,
            authorization_snapshot=capture_authorization_snapshot(context, registry),
            evidence_snapshot=evidence, evidence_snapshot_sequence=2,
        ),
    )
    return episode, store, context, registry, now


def test_repeated_restore_does_not_inflate_the_unreconciled_list(tmp_path) -> None:
    """同一段窗口被恢复 N 次仍只登记一次。

    ``retry_model`` 不合成任何结算，所以那条悬空意图下一次恢复照样看得见。若每次都追一条，
    清单会随重启次数线性膨胀，将来对账就按重启次数重复扣费——把一个少记账的 bug 换成一个
    多记账的 bug，同样是错账。
    """

    episode, store, context, registry, now = _dangling_model_episode(tmp_path, retries=2)

    first = restore_episode(episode, store, now=now, context=context, registry=registry)
    assert first.plan is not None and first.plan.action == "retry_model"
    # 此前这条路径在任何记录落地前就 return 了——它恰恰是最危险的一条（主动提议再付一次）。
    assert [e.kind for e in first.synthesized] == ["effects_unknown"]
    assert [e.reserved_id for e in first.unreconciled_effects] == ["turn-1"]
    assert first.unreconciled_effects[0].disposition == "retry_proposed"

    for _ in range(3):
        again = restore_episode(episode, store, now=now, context=context, registry=registry)
        assert again.plan == first.plan
        assert again.synthesized == ()  # 旧窗口不重复登记
        assert len(again.unreconciled_effects) == 1

    # 落盘的那份也只有一条，且跨进程读回来仍在。
    reread = JsonlEpisodeStore(tmp_path).load(episode)[1]
    assert reread is not None and len(reread.unreconciled_effects) == 1


def test_live_checkpoint_carries_unreconciled_receipts_forward() -> None:
    """热路径不产生未知效果，但也没资格抹掉上一次恢复留下的凭证。

    只有对账能清空这份清单。不带它往下传，等于用下一个检查点把「有笔账没对」静默改写成
    「无账可对」——恰好是本模块要堵的那个方向。
    """

    from intelligence.runtime.agent_episode import _EpisodeLedger
    from intelligence.tests.conformance.fixtures import make_frame

    episode = f"carry-{uuid4().hex}"
    store = MemoryEpisodeStore()
    ledger = _EpisodeLedger(make_frame(), episode_id=episode, store=store)
    receipts = tuple(unknown_effects_payload((_model_effect(),)))
    ledger.state = EpisodeState(
        episode_id=episode, phase="model_pending", reserved_ids=("turn-1",),
        last_sequence=0, unreconciled_effects=receipts,
    )

    after = ledger.put_state(phase="planning")

    assert [dict(item) for item in after.unreconciled_effects] == [dict(item) for item in receipts]
    stored = store.load(episode)[1]
    assert stored is not None and len(stored.unreconciled_effects) == 1


def test_state_round_trip_preserves_receipts_and_rejects_damaged_ones() -> None:
    """凭证跟着检查点走 JSON 往返；损坏的检查点在构造处就炸，不留半懂的状态。"""

    receipts = unknown_effects_payload((_model_effect(), _model_effect(reserved_id="t2", intent_sequence=5)))
    state = EpisodeState(episode_id="ep", phase="tools_pending", unreconciled_effects=tuple(receipts))
    assert EpisodeState.from_dict(state.to_dict()).unreconciled_effects == state.unreconciled_effects
    assert state.to_dict()["unreconciled_effects"] == receipts

    # 同一段窗口写进去两次 → 状态层去重，重复恢复不可能让它膨胀。
    doubled = EpisodeState(
        episode_id="ep", phase="tools_pending",
        unreconciled_effects=(receipts[0], dict(receipts[0])),
    )
    assert len(doubled.unreconciled_effects) == 1

    with pytest.raises(ValueError):
        EpisodeState(
            episode_id="ep", phase="tools_pending",
            unreconciled_effects=({**receipts[0], "effect": "nonsense"},),
        )
