"""QC 第九轮（候选 50074c76）：I11 自用测量同意门的反例探针。

审的是 ``run_observer.ObservingRunStore._measurement_consented``（9b92eac8 引入）。真 API、真 writer、
隔离临时用户目录；不调模型、不外呼、不碰生产数据。每条探针在 REVIEW.md 里归入三类之一：
修复前应红→修复后绿 / 修复前后都绿（合同守恒）/ 修复后仍红。

对照口径：05 读侧 ``measure._consent_timeline`` / ``_scopes_at`` 的折叠语义（排序键、未来截断、
grant/withdraw 集合运算、``REQUIRED_MEASUREMENT_SCOPES`` 子集判定）。读侧只认带 participant_id 的记录，
owner 自用记录 participant_id 为空，所以 ``_read_side_allows`` 把 owner 记录挂到 owner 名下再折叠——
比的是折叠算法是否同一份语义，不是身份谓词。
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta

import pytest

import intelligence.tests.research_evolution_fixtures as fx
from intelligence.api import app as app_module
from intelligence.services.product_value.contracts import REQUIRED_MEASUREMENT_SCOPES
from intelligence.services.product_value.measure import _consent_timeline, _scopes_at, measure_pair
from intelligence.services.research_evolution.contracts import SELF_USE_PROTOCOL_VERSION
from intelligence.services.research_evolution.store import EvolutionStore
from intelligence.tests.test_research_evolution_rework import World

OTHER_PARTICIPANT = "p-someone-else"
FULL_SET = ["cost_recorded", "run_finished", "run_started"]  # 假 turn 记 120 tokens → 终态多一条 cost_recorded


class R9World(World):
    """在 rework World 上加一个「turn 已返回」信号。

    fake_turn 里的 ``finish_run`` 同步走 ObservingRunStore.claim_terminal_run → 三次 ``_record``；
    turn 返回 == 该 run 终态的观察器写入已全部结束。负向断言（「不该写」）因此不用靠 sleep 赌窗口。
    """

    def __init__(self, users, monkeypatch: pytest.MonkeyPatch) -> None:
        super().__init__(users, monkeypatch)
        self.turn_done = threading.Event()
        inner = app_module._run_conversation_turn

        def signalled(**kwargs: object) -> None:
            try:
                inner(**kwargs)
            finally:
                self.turn_done.set()

        monkeypatch.setattr(app_module, "_run_conversation_turn", signalled)


@pytest.fixture
def world(tmp_path, monkeypatch):
    fx.install_env(monkeypatch, tmp_path)
    return R9World(tmp_path / "users", monkeypatch)


# --------------------------------------------------------------------------- #
# 助手：全部走真 API / 真 writer
# --------------------------------------------------------------------------- #
def _consent(
    world: R9World,
    action: str,
    scopes: list[str],
    tag: str,
    *,
    effective_at: str | None = None,
    participant_id: str | None = None,
    advance: bool = True,
) -> str:
    event_id = f"r9-consent-{tag}-{action}"
    body: dict = {
        "event_id": event_id,
        "event_type": "consent_changed",
        "payload": {
            "consent_version": "r9-consent-v1",
            "scopes": scopes,
            "effective_at": effective_at or world.clock().isoformat(),
            "action": action,
            "terms_hash": "sha256:" + "f" * 64,
            "initiator": "user",
            "assistance_source": "workbench",
        },
    }
    if participant_id:
        body["participant_id"] = participant_id
    response = world.events([body])
    response.raise_for_status()
    assert response.json()["accepted"] == [event_id], response.text
    if advance:
        world.clock.advance(seconds=1)
    return event_id


def _launch(world: R9World, text: str) -> str:
    world.turn_done.clear()
    launched = world.client.post(
        f"/api/conversations/{world.conversation_id}/messages",
        json={"user": fx.OWNER, "content": text, "skill_mode": "hybrid"},
    )
    assert launched.status_code == 202, launched.text
    return launched.json()["run_id"]


def _run_once(world: R9World, text: str) -> str:
    run_id = _launch(world, text)
    assert world.wait_terminal(run_id)["status"] == "completed"
    assert world.turn_done.wait(10), "turn 线程未在超时内返回"
    return run_id


def _ledger(world: R9World) -> list[dict]:
    return EvolutionStore(world.user_root / "research_evolution", fx.OWNER).list_product_value_events()


def _measurements_for(world: R9World, run_id: str) -> list[str]:
    return sorted(e["event_type"] for e in _ledger(world) if run_id in (e.get("run_ids") or []))


def _read_side_allows(world: R9World, at: datetime) -> bool | None:
    """05 读侧口径下 owner 在 ``at`` 时刻是否满足必需范围；None = 读侧「无记录」。"""
    rows = [
        {**e, "participant_id": fx.OWNER}
        for e in _ledger(world)
        if e.get("event_type") == "consent_changed" and e.get("participant_id") in (None, fx.OWNER)
    ]
    scopes = _scopes_at(_consent_timeline(rows), fx.OWNER, at)
    if scopes is None:
        return None
    return REQUIRED_MEASUREMENT_SCOPES <= scopes


def _append_raw_consent_row(world: R9World, *, event_id: str, action: str, scopes: list[str], effective_at: str, event_at: str) -> None:
    """经 EvolutionStore 真 writer 追加一条**跳过 05 校验**的 owner 同意行。

    API 路径进不来这种行（validate_event 要求 effective_at 为带时区 ISO、action 在白名单），
    它模拟的是受控导入 / 手改台账留下的坏时间——门对这类行的处置只能这样造出来看。
    """
    store = EvolutionStore(world.user_root / "research_evolution", fx.OWNER)
    row = {
        "schema_version": "product-value-event/v1",
        "event_id": event_id,
        "event_type": "consent_changed",
        "owner_user_id": fx.OWNER,
        "pilot_id": f"workbench:{world.conversation_id}",
        "participant_id": None,
        "task_id": None,
        "case_id": None,
        "case_version": None,
        "case_pair_id": None,
        "run_ids": [],
        "object_refs": [],
        "assistance_condition": None,
        "event_at": event_at,
        "recorded_at": event_at,
        "source_version": {"code_sha": "test", "protocol_version": SELF_USE_PROTOCOL_VERSION, "artifact_hash": None},
        "provenance": {"kind": "observed", "source_ref": "review:r9", "source_hash": None},
        "source_channel": "manual_import",
        "payload": {
            "consent_version": "r9-raw",
            "scopes": scopes,
            "effective_at": effective_at,
            "action": action,
            "terms_hash": "sha256:" + "f" * 64,
            "initiator": "user",
            "assistance_source": "workbench",
            "importer_id": "qc-r9",
            "evidence_ref": "review:r9",
            "evidence_hash": "sha256:" + "e" * 64,
        },
    }
    with store.transaction() as txn:
        txn.append_product_value_event(row, content_hash=f"r9-{event_id}")


# --------------------------------------------------------------------------- #
# 折叠语义：撤回哪一项、再授权、未来生效、同一时刻
# --------------------------------------------------------------------------- #
def test_r9_01_withdraw_research_stops_measurement(world: R9World) -> None:
    """原 I11 只撤 logging；撤 research 同样是必需范围之一，门也得关。"""
    _consent(world, "grant", ["research", "logging"], "t01")
    _consent(world, "withdraw", ["research"], "t01")
    run_id = _run_once(world, "研究照常，撤回的是 research 而不是 logging")
    assert _read_side_allows(world, world.clock()) is False
    assert _measurements_for(world, run_id) == []


def test_r9_02_regrant_after_withdraw_restores_measurement(world: R9World) -> None:
    _consent(world, "grant", ["research", "logging"], "t02a")
    _consent(world, "withdraw", ["logging"], "t02a")
    _consent(world, "grant", ["logging"], "t02b")
    run_id = _run_once(world, "再授权后测量恢复")
    assert _read_side_allows(world, world.clock()) is True
    assert _measurements_for(world, run_id) == FULL_SET


def test_r9_03_future_withdraw_is_not_applied_before_its_effective_at(world: R9World) -> None:
    _consent(world, "grant", ["research", "logging"], "t03")
    future = (world.clock() + timedelta(hours=1)).isoformat()
    _consent(world, "withdraw", ["research", "logging"], "t03", effective_at=future)
    run_id = _run_once(world, "预约撤回尚未生效")
    assert _read_side_allows(world, world.clock()) is True
    assert _measurements_for(world, run_id) == FULL_SET


def test_r9_04_future_withdraw_applies_once_clock_passes_effective_at(world: R9World) -> None:
    _consent(world, "grant", ["research", "logging"], "t04")
    future = (world.clock() + timedelta(hours=1)).isoformat()
    _consent(world, "withdraw", ["research", "logging"], "t04", effective_at=future)
    world.clock.advance(hours=2)
    run_id = _run_once(world, "预约撤回已到期")
    assert _read_side_allows(world, world.clock()) is False
    assert _measurements_for(world, run_id) == []


def test_r9_09_same_instant_grant_and_withdraw_withdraw_wins(world: R9World) -> None:
    """排序键 (effective_at, action)：'grant' < 'withdraw'，同刻撤回后生效——与 05 读侧同一口径。"""
    _consent(world, "grant", ["research", "logging"], "t09", advance=False)
    _consent(world, "withdraw", ["research", "logging"], "t09", advance=False)
    world.clock.advance(seconds=1)
    run_id = _run_once(world, "同一时刻的 grant 与 withdraw")
    assert _read_side_allows(world, world.clock()) is False
    assert _measurements_for(world, run_id) == []


# --------------------------------------------------------------------------- #
# 身份谓词：别人的记录、owner 自己带 participant_id 的记录
# --------------------------------------------------------------------------- #
def test_r9_05_other_participants_withdraw_does_not_gate_owner(world: R9World) -> None:
    _consent(world, "grant", ["research", "logging"], "t05")
    _consent(world, "withdraw", ["research", "logging"], "t05", participant_id=OTHER_PARTICIPANT)
    run_id = _run_once(world, "别人的撤回不影响 owner 自用测量")
    assert _measurements_for(world, run_id) == FULL_SET


def test_r9_06_other_participants_grant_does_not_reopen_owner_gate(world: R9World) -> None:
    _consent(world, "grant", ["research", "logging"], "t06")
    _consent(world, "withdraw", ["research"], "t06")
    _consent(world, "grant", ["research", "logging"], "t06-other", participant_id=OTHER_PARTICIPANT)
    run_id = _run_once(world, "别人的授权不能替 owner 打开门")
    assert _measurements_for(world, run_id) == []


def test_r9_18_consent_tagged_with_owner_participant_id_counts_as_owner(world: R9World) -> None:
    """门认 participant_id ∈ {None, owner}：owner 自己带 id 的撤回同样生效。"""
    _consent(world, "grant", ["research", "logging"], "t18")
    _consent(world, "withdraw", ["research", "logging"], "t18", participant_id=fx.OWNER)
    run_id = _run_once(world, "owner 带 participant_id 的撤回")
    assert _read_side_allows(world, world.clock()) is False
    assert _measurements_for(world, run_id) == []


def test_r9_19_withdraw_posted_in_another_conversation_gates_this_run(world: R9World) -> None:
    """同意是 owner 级的（台账按 owner 存，门不看 pilot_id）：在会话 B 撤回，会话 A 的 run 也不再测量。"""
    _consent(world, "grant", ["research", "logging"], "t19")
    other = world.client.post("/api/conversations", json={"title": "另一个会话", "user": fx.OWNER})
    other.raise_for_status()
    other_id = other.json()["conversation_id"]
    response = world.client.post(
        f"/api/conversations/{other_id}/research-evolution/events",
        json={
            "user": fx.OWNER,
            "events": [{
                "event_id": "r9-consent-t19-other-conv-withdraw",
                "event_type": "consent_changed",
                "payload": {
                    "consent_version": "r9-consent-v1",
                    "scopes": ["research", "logging"],
                    "effective_at": world.clock().isoformat(),
                    "action": "withdraw",
                    "terms_hash": "sha256:" + "f" * 64,
                    "initiator": "user",
                    "assistance_source": "workbench",
                },
            }],
        },
    )
    response.raise_for_status()
    assert response.json()["accepted"] == ["r9-consent-t19-other-conv-withdraw"], response.text
    world.clock.advance(seconds=1)
    run_id = _run_once(world, "在别的会话撤回后，本会话的 run")
    assert _read_side_allows(world, world.clock()) is False
    assert _measurements_for(world, run_id) == []


def test_r9_20_backdated_late_grant_cannot_reopen_a_later_withdraw(world: R9World) -> None:
    """按 effective_at 折叠而不是按台账顺序：晚到、但生效时刻早于撤回的 grant 排在撤回之前，门仍关。"""
    _consent(world, "grant", ["research", "logging"], "t20")
    between = world.clock().isoformat()  # T1：介于首次授权与撤回之间
    world.clock.advance(seconds=1)
    _consent(world, "withdraw", ["research", "logging"], "t20")  # T2
    _consent(world, "grant", ["research", "logging"], "t20-backdated", effective_at=between)  # 台账最后一条，生效在 T1
    run_id = _run_once(world, "倒填生效时刻的晚到授权")
    assert _read_side_allows(world, world.clock()) is False
    assert _measurements_for(world, run_id) == []


# --------------------------------------------------------------------------- #
# 部分授权：第一条同意记录就把「自用默认」翻掉
# --------------------------------------------------------------------------- #
def test_r9_07_grant_logging_only_closes_gate_in_step_with_read_side(world: R9World) -> None:
    """只授 logging、缺 research：05 读侧 {logging} ⊉ {research, logging} → consent_withdrawn 排除；写侧同判不写。"""
    _consent(world, "grant", ["logging"], "t07")
    run_id = _run_once(world, "只授权 logging，缺 research")
    assert _read_side_allows(world, world.clock()) is False
    assert _measurements_for(world, run_id) == []


def test_r9_08_first_grant_of_unrelated_scope_closes_gate(world: R9World) -> None:
    """产品后果：第一条同意记录哪怕只授 blind_review，也把此前「无记录=照写」的自用默认翻成不写。
    与 05 读侧一致（有记录但不覆盖必需范围 = 不进有效测量），但值得修复方在 UI 文案里说清。"""
    _consent(world, "grant", ["blind_review"], "t08")
    run_id = _run_once(world, "第一条同意记录只授权 blind_review")
    assert _read_side_allows(world, world.clock()) is False
    assert _measurements_for(world, run_id) == []


# --------------------------------------------------------------------------- #
# run 进行中撤回：有始无终的 attempt
# --------------------------------------------------------------------------- #
def test_r9_10_midrun_withdraw_writes_run_started_but_not_finish_or_cost(world: R9World) -> None:
    _consent(world, "grant", ["research", "logging"], "t10")
    world.turn_gate.clear()
    try:
        run_id = _launch(world, "run 进行中撤回同意")
        # run_started 在 create_run 内同步写、早于 202 返回——此时门还开着，它必须在。
        assert _measurements_for(world, run_id) == ["run_started"]
        world.clock.advance(seconds=1)
        _consent(world, "withdraw", ["logging"], "t10")
    finally:
        world.turn_gate.set()
    assert world.wait_terminal(run_id)["status"] == "completed"
    assert world.turn_done.wait(10)
    assert _measurements_for(world, run_id) == ["run_started"]


def test_r9_11_read_side_counts_start_only_attempt_as_gap_not_failure() -> None:
    """05 ``measure_pair`` 对「有 run_started、无 run_finished」的 attempt：计入 attempt 分母、不判失败、
    终态取自证据读取器（真实 RunStore），缺口以 timing_missing / cost_unknown 显式落在 limitations → incomplete。
    读侧代码不在本修复范围内，这条只钉住归类口径，供 I11「关闭前后的分母与缺口都可解释」对照。"""
    from intelligence.services.product_value.evidence import InMemoryEvidenceReader
    from intelligence.tests import product_value_fixtures as pv

    protocol = pv.build_protocol()
    p_hash = protocol["protocol_hash"]
    syn = pv.PROVENANCE_SYNTHETIC
    p, pair = "p01", "pair-01"
    o, a, co, ca, run = "t-r9-o", "t-r9-a", "case-fc-01", "case-fc-02", "r-r9-1"
    events = [
        pv._consent("e-r9-consent", p, pv.ts("09-14", "09:00:00"), ["research", "logging", "blind_review"], syn),
        pv._assignment("e-r9-assign-o", participant=p, task=o, case=co, pair=pair, condition="original", assigned_at=pv.ts("09-14", "10:00:00"), deadline=pv.ts("09-16", "18:00:00"), p_hash=p_hash, provenance=syn),
        pv._assignment("e-r9-assign-a", participant=p, task=a, case=ca, pair=pair, condition="assisted", assigned_at=pv.ts("09-14", "10:00:00"), deadline=pv.ts("09-16", "18:00:00"), p_hash=p_hash, provenance=syn),
        pv._interval("e-r9-o-int", at=pv.ts("09-15", "11:00:00"), channel=pv.SOURCE_MANUAL, participant=p, task=o, case=co, pair=pair, condition="original", interval_id="i-r9-o", start=pv.ts("09-15", "10:00:00"), end=pv.ts("09-15", "10:30:00"), activity="user_active", clock="manual_actual", provenance=syn),
        pv._terminal("task_completed", "e-r9-o-done", at=pv.ts("09-15", "10:30:00"), channel=pv.SOURCE_MANUAL, participant=p, task=o, case=co, pair=pair, condition="original", evidence=["doc:r9-o"], reason="delivered", provenance=syn),
        pv._run_event("run_started", "e-r9-a-run-start", at=pv.ts("09-15", "14:05:00"), participant=p, task=a, case=ca, pair=pair, run_id=run, attempt_id="a-r9-1", status="running", error_ref=None, provenance=syn),
        # 14:10 参与者撤回 research+logging → 写侧门关，14:12 的 run_finished / cost_recorded 永远不会落账
        pv.ev(
            "consent_changed",
            event_id="e-r9-withdraw",
            at=pv.ts("09-15", "14:10:00"),
            channel=pv.SOURCE_FRONTEND,
            participant=p,
            provenance=syn,
            payload={"consent_version": "consent-v1", "scopes": ["research", "logging"], "effective_at": pv.ts("09-15", "14:10:00"), "action": "withdraw", "terms_hash": "sha256:" + "f" * 64},
        ),
    ]
    evidence = {"runs": [{"owner_user_id": pv.OWNER, "run_id": run, "status": "completed", "error": None, "degrades": [], "artifacts": {}, "created_at": pv.ts("09-15", "14:05:00"), "finished_at": pv.ts("09-15", "14:12:00")}]}
    receipt = measure_pair(events, protocol, InMemoryEvidenceReader.from_json(evidence))

    assisted = receipt["tasks"]["assisted"]
    assert assisted["attempt_count"] == 1
    assert assisted["failed_attempt_count"] == 0
    attempt = assisted["attempts"][0]
    assert attempt["finished_at"] is None and attempt["reported_status"] is None
    assert attempt["effective_status"] == "completed"  # 来自证据读取器读真实 run，不来自测量事件
    assert attempt["failed"] is False
    assert f"timing_missing:{a}" in receipt["limitations"]
    assert any(item.startswith("cost_unknown:attempt:a-r9-1") for item in receipt["limitations"])
    assert receipt["status"] == "incomplete"
    assert receipt["denominator_ids"] == sorted([o, a])
    assert receipt["numerator_ids"] == [o]
    # 撤回前写下的 run_started 不被追溯排除
    assert not [x for x in receipt["exclusions"] if x["id"] == "e-r9-a-run-start"]
    assert receipt["invalid_reasons"] == []


# --------------------------------------------------------------------------- #
# 坏台账：坏 JSON 行、坏时间行
# --------------------------------------------------------------------------- #
def _corrupt_ledger(world: R9World) -> str:
    ledger = world.user_root / "research_evolution" / "product_value_events.jsonl"
    with ledger.open("a", encoding="utf-8") as handle:
        handle.write("{this is not json\n")
    return ledger.read_text(encoding="utf-8")


def test_r9_12_corrupt_ledger_line_keeps_research_usable_and_appends_nothing(world: R9World) -> None:
    """门的 docstring 说读失败「按未知处理（继续写）」；但 append_once 重读同一份台账同样 StoreCorrupt，
    净效果是**什么都没写**（fail-closed by accident）。研究照常完成才是这里唯一的硬合同。"""
    _consent(world, "grant", ["research", "logging"], "t12")
    corrupted = _corrupt_ledger(world)
    ledger = world.user_root / "research_evolution" / "product_value_events.jsonl"
    _run_once(world, "台账坏行时研究照常")
    assert ledger.read_text(encoding="utf-8") == corrupted


def test_r9_13_corrupt_ledger_gate_leaves_stderr_trace(world: R9World, capfd: pytest.CaptureFixture[str]) -> None:
    _consent(world, "grant", ["research", "logging"], "t13")
    _corrupt_ledger(world)
    _run_once(world, "台账坏行的 stderr 痕迹")
    err = capfd.readouterr().err
    assert "读同意记录失败" in err, err[-2000:]
    assert "落盘失败" in err, err[-2000:]


def test_r9_14_consent_row_with_unparseable_times_is_ignored_fail_open(world: R9World) -> None:
    """effective_at 与 event_at 都解析不出：门跳过该行（等同没这条撤回）→ 照写。只有绕过校验器的行才会这样；
    05 读侧 prepare_events 会把这种行整条拒收，两侧都「看不见它」，口径一致但方向是 fail-open。"""
    _consent(world, "grant", ["research", "logging"], "t14")
    _append_raw_consent_row(world, event_id="r9-raw-bad-withdraw", action="withdraw", scopes=["research", "logging"], effective_at="yesterday", event_at="2026-09-14 16:00")
    run_id = _run_once(world, "坏时间的撤回行被门跳过")
    assert _measurements_for(world, run_id) == FULL_SET


def test_r9_15_naive_effective_at_falls_back_to_event_at(world: R9World) -> None:
    _consent(world, "grant", ["research", "logging"], "t15")
    stamp = world.clock().isoformat()
    _append_raw_consent_row(world, event_id="r9-raw-naive-withdraw", action="withdraw", scopes=["logging"], effective_at=world.clock().replace(tzinfo=None).isoformat(), event_at=stamp)
    world.clock.advance(seconds=1)
    run_id = _run_once(world, "无时区的 effective_at 回退到 event_at")
    assert _read_side_allows(world, world.clock()) is False
    assert _measurements_for(world, run_id) == []


# --------------------------------------------------------------------------- #
# 终态家族：cancel 与 executor 失败两条路径也汇入同一个门
# --------------------------------------------------------------------------- #
def test_r9_16_cancel_path_is_gated_too(world: R9World) -> None:
    _consent(world, "grant", ["research", "logging"], "t16")
    _consent(world, "withdraw", ["research", "logging"], "t16")
    world.turn_gate.clear()
    try:
        run_id = _launch(world, "撤回后发起再取消")
        cancelled = world.client.post(f"/api/runs/{run_id}/cancel", params={"user": fx.OWNER})
        assert cancelled.status_code == 200, cancelled.text
        assert cancelled.json()["status"] == "cancelled"
    finally:
        world.turn_gate.set()
    # cancel 处理器里的 finish_run(cancelled) 同步经过观察器——返回即写完，无窗口。
    assert _measurements_for(world, run_id) == []


def test_r9_17_executor_failure_path_is_gated_too(world: R9World, monkeypatch: pytest.MonkeyPatch) -> None:
    _consent(world, "grant", ["research", "logging"], "t17")
    _consent(world, "withdraw", ["logging"], "t17")

    def exploding_turn(**kwargs: object) -> None:
        raise RuntimeError("r9: simulated executor failure")

    monkeypatch.setattr(app_module, "_run_conversation_turn", exploding_turn)
    run_id = _launch(world, "撤回后执行器失败")
    assert world.wait_terminal(run_id)["status"] == "failed"
    # claim_failed_run 在 future 的 done-callback 里：终态可见后观察器还有毫秒级窗口，等它稳定。
    time.sleep(0.5)
    first = _measurements_for(world, run_id)
    time.sleep(0.3)
    assert first == _measurements_for(world, run_id) == []
