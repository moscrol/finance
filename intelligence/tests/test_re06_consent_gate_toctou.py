"""RE06 同意门的 TOCTOU：门在锁外读台账，从「读到」到「写下」之间撤回可能已经落账。

窗口是真的：``_record`` 先无锁读一遍同意记录决定写不写，再构造事件、跑 05 校验，
最后才去抢测量锁。这中间 API 侧（用户点撤回）完全可以往同一份台账追加一条
``consent_changed``。老实现不会再看一眼，于是撤回之后仍写进一条测量事件，而 05 读侧
按事件自己的 ``event_at`` 判定同意——那条事件会被照常算进读数。

修法是锁内复核同一个谓词（``transaction()`` 的合同是「锁内读到的台账就是提交时的
台账」）。**不改时间语义**：仍按事件自身时刻 ``now`` 判定，未来生效的撤回不追溯。
"""
from __future__ import annotations

from datetime import timedelta

import pytest

import intelligence.services.product_value as PV
from intelligence.services.research_evolution.store import EvolutionStore
from intelligence.services.research_evolution.run_observer import ObservingRunStore
from intelligence.tests.test_re06_consent_fold_shared import OWNER, at, consent_event

NOW = at(60)


def observing_store(tmp_path, consents: list[dict], clock=None) -> ObservingRunStore:
    store = ObservingRunStore(
        user_id=OWNER, root=tmp_path / "runs", evolution_root=tmp_path / "evolution",
        clock=clock or (lambda: NOW), code_sha="toctou-test",
    )
    write_consents(tmp_path, consents)
    return store


def write_consents(tmp_path, consents: list[dict]) -> None:
    ledger = EvolutionStore(tmp_path / "evolution", OWNER)
    with ledger.transaction() as txn:
        for event in consents:
            result = PV.validate_event(event)
            assert result.ok, [i.code for i in result.issues]
            txn.append_product_value_event(result.normalized or event, content_hash=result.content_hash or "")


def measurement_events(store: ObservingRunStore) -> list[str]:
    return [e["event_type"] for e in store._evolution_store.list_product_value_events()
            if e["event_type"] != "consent_changed"]


def inject_between_gate_and_append(monkeypatch, tmp_path, consents: list[dict]) -> None:
    """05 校验正好落在「门之后、抢锁之前」，拿它当注入点模拟并发撤回。"""
    real = PV.validate_event
    fired: list[bool] = []

    def once(event, **kwargs):
        if not fired:
            fired.append(True)
            write_consents(tmp_path, consents)
        return real(event, **kwargs)

    monkeypatch.setattr(PV, "validate_event", once)


@pytest.fixture
def granted(tmp_path):
    return observing_store(tmp_path, [
        consent_event(0, "grant", ["research", "logging"], participant=OWNER, tag="grant"),
    ])


def test_measurement_is_written_when_consent_holds_through_the_window(granted):
    """守恒：没有并发撤回时照写。少了这条，「干脆永远不写」也能让下一条变绿。"""
    run = granted.create_run("consent holds", "research", session_id="s-toctou-ok")
    assert measurement_events(granted) == ["run_started"]
    assert run.run_id


def test_withdraw_landing_between_gate_and_append_is_not_written(granted, tmp_path, monkeypatch):
    inject_between_gate_and_append(monkeypatch, tmp_path, [
        consent_event(30, "withdraw", ["logging"], participant=OWNER, tag="race"),
    ])
    granted.create_run("withdraw races the append", "research", session_id="s-toctou-race")
    assert measurement_events(granted) == []


def test_future_dated_withdraw_in_the_window_does_not_retract_the_current_event(granted, tmp_path, monkeypatch):
    """时间语义不变：生效时刻还没到的撤回不追溯本轮事件，否则锁内复核会悄悄改口径。"""
    future = at(60) + timedelta(minutes=5)
    withdraw = consent_event(30, "withdraw", ["logging"], participant=OWNER, tag="future")
    withdraw["payload"]["effective_at"] = future.isoformat()
    inject_between_gate_and_append(monkeypatch, tmp_path, [withdraw])
    granted.create_run("future withdraw", "research", session_id="s-toctou-future")
    assert measurement_events(granted) == ["run_started"]


def test_recheck_judges_at_event_time_not_at_write_time(tmp_path, monkeypatch):
    """复核按**事件自身时刻**判定，落盘那一刻的时钟不参与。

    两种口径只在「事件时刻之后、落盘之前生效」的撤回上分叉。选事件时语义是为了与 05
    读侧一致——读侧按 ``event_at`` 判定；改成写时语义会让门比读侧更严，变成凭写入延迟
    决定要不要丢事件，同一个 ``event_at`` 早 1ms 落盘就能进、晚一点就没。属产品判断，
    改口径请先改这条测试的说明。
    """
    ticks = iter([NOW, *[NOW + timedelta(minutes=10)] * 8])
    store = observing_store(tmp_path, [
        consent_event(0, "grant", ["research", "logging"], participant=OWNER, tag="grant"),
    ], clock=lambda: next(ticks))
    withdraw = consent_event(30, "withdraw", ["logging"], participant=OWNER, tag="mid")
    withdraw["payload"]["effective_at"] = (NOW + timedelta(minutes=5)).isoformat()
    inject_between_gate_and_append(monkeypatch, tmp_path, [withdraw])
    store.create_run("clock moves during write", "research", session_id="s-toctou-clock")
    assert measurement_events(store) == ["run_started"]


def test_closed_gate_never_contends_for_the_measurement_lock(tmp_path, monkeypatch):
    """同意关着时根本不去抢锁：测量绝不把被测 run 堵在锁上（QC Q9）。

    只留锁内复核在行为上等价，但会让每一条本就不写的事件都去等一把 0.2s 的锁。
    """
    store = observing_store(tmp_path, [
        consent_event(0, "grant", ["research"], participant=OWNER, tag="partial"),  # 缺 logging → 门关
    ])
    real = EvolutionStore.try_transaction
    attempts: list[float] = []

    def counted(self, timeout: float = 0.25):
        attempts.append(timeout)
        return real(self, timeout)

    monkeypatch.setattr(EvolutionStore, "try_transaction", counted)
    store.create_run("gate closed", "research", session_id="s-toctou-nolock")
    assert measurement_events(store) == []
    assert attempts == [], "门关着还去抢了测量锁"


def test_authoritative_recheck_happens_inside_the_lock(granted, monkeypatch):
    """复核必须读锁内视图：锁外再读一遍只是把窗口缩小，不是关上。"""
    real = ObservingRunStore._measurement_consented
    in_txn: list[bool] = []

    def spy(self, when, **kwargs):
        in_txn.append(bool(getattr(self._evolution_store, "_in_txn", False)))
        return real(self, when, **kwargs)

    monkeypatch.setattr(ObservingRunStore, "_measurement_consented", spy)
    granted.create_run("lock view", "research", session_id="s-toctou-lock")
    assert in_txn and in_txn[-1] is True, f"最后一次同意判定不在事务内：{in_txn}"
