"""06 全链验收：真实 API + 真实 01–05 业务函数 + 临时用户态（spec §7 的 I01–I16）。

市场取数与服务端时钟是**注入的资源**（固定输入），01/02/04/05 的判定全是真函数；
台账由现役写入者写。LLM 不参与——本轨不以它替代原材料题 PK。

三项反向证伪在 ``test_research_evolution_falsification.py``。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from intelligence.api.app import create_app  # noqa: E402
from intelligence.tests import research_evolution_fixtures as fx  # noqa: E402

@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    return fx.install_env(monkeypatch, tmp_path)


class World:
    """一个装好的世界：客户端、会话、用户根、可推进的时钟。"""

    def __init__(self, users: Path, *, revised: bool = True, market_stage: str = "反弹") -> None:
        self.clock = fx.FakeClock()
        self.evidence = fx.evidence_source(revised=revised, market_stage=market_stage)
        self.app = create_app(research_evolution_evidence=self.evidence, research_evolution_clock=self.clock)
        self.client = TestClient(self.app)
        response = self.client.post("/api/conversations", json={"title": "制冷剂配额", "user": fx.OWNER})
        response.raise_for_status()
        self.conversation_id = response.json()["conversation_id"]
        self.user_root = users / fx.OWNER
        self.seed = fx.seed_legacy_ledgers(self.user_root, session_id=self.conversation_id)
        self.service = fx.service_with(self.evidence, self.clock)

    # --- 便捷调用 --------------------------------------------------------- #
    def view(self, **params: object) -> dict:
        response = self.client.get(
            f"/api/conversations/{self.conversation_id}/research-evolution",
            params={"user": fx.OWNER, **params},
        )
        response.raise_for_status()
        return response.json()

    def raw_view(self, **params: object):
        return self.client.get(
            f"/api/conversations/{self.conversation_id}/research-evolution",
            params={"user": fx.OWNER, **params},
        )

    def catalog(self, entity: str = fx.ENTITY, as_of: str = fx.SLICE_DAY, **params: object):
        return self.client.get(
            f"/api/conversations/{self.conversation_id}/research-evolution/evidence-catalog",
            params={"user": fx.OWNER, "entity": entity, "as_of": as_of, **params},
        )

    def bind(self, **body: object):
        payload = {
            "user": fx.OWNER,
            "entity": fx.ENTITY,
            "as_of": fx.SLICE_DAY,
            "evidence_refs": [fx.REF_SECTOR, fx.REF_REPORT],
            **body,
        }
        return self.client.post(
            f"/api/conversations/{self.conversation_id}/research-evolution/bindings", json=payload
        )

    def bind_at(self, day: str, **body: object):
        """在 ``day`` 当天建立绑定，然后把时钟拨回来。

        绑定基线永远是**绑定那一刻可知**的版本。今天绑定就以今天的版本为基线，
        那时还没发生的修订当然不会被算成变化——要让「先跟踪、后被改」这条线成立，
        必须真的在修订之前绑定，而不是把后来的版本塞进基线。
        """
        from datetime import datetime as _dt

        previous = self.clock.moment
        self.clock.moment = _dt.fromisoformat(f"{day}T16:00:00+08:00")
        try:
            return self.bind(**body)
        finally:
            self.clock.moment = previous

    def track_judgment(self, **body: object):
        """默认场景：在 09-12 的修订**之前**跟踪这条判断。"""
        return self.bind_at(fx.BIND_DAY, object_ref=self.judgment_object_ref(), **body)

    def act(self, **body: object):
        return self.client.post(
            f"/api/conversations/{self.conversation_id}/research-evolution/actions",
            json={"user": fx.OWNER, **body},
        )

    def events(self, events: list[dict]):
        return self.client.post(
            f"/api/conversations/{self.conversation_id}/research-evolution/events",
            json={"user": fx.OWNER, "events": events},
        )

    def register(self, kind: str, value: dict) -> None:
        from intelligence.services.research_evolution.access import OwnerContext

        self.service.register_artifact(ctx=OwnerContext.for_owner(fx.OWNER), kind=kind, value=value)

    def record_receipt(self, receipt: dict) -> dict:
        from intelligence.services.research_evolution.access import OwnerContext

        return self.service.record_process_receipt(ctx=OwnerContext.for_owner(fx.OWNER), receipt=receipt)

    def judgment_object_ref(self) -> dict:
        for item in self.view()["inputs"]["trackable_objects"]:
            if item["kind"] == "judgment":
                return item["object_ref"]
        raise AssertionError("清单里没有判断对象")

    def open_item(self) -> dict:
        maintenance = self.view()["maintenance"]
        assert maintenance is not None, "维护段不可用"
        items = [i for i in maintenance["items"] if i["status"] == "open"]
        assert items, f"没有待复核项：{[(i['change_type'], i['status']) for i in maintenance['items']]}"
        return items[0]


@pytest.fixture
def world(env: Path) -> World:
    return World(env)


# --------------------------------------------------------------------------- #
# I01 已有判断缺证据绑定 → 从现在跟踪
# --------------------------------------------------------------------------- #
def test_i01_binding_keeps_original_timestamp_and_never_backfills_strict(world: World) -> None:
    before = fx.ledger_hashes(world.user_root)
    view = world.view()
    assert view["module_status"]["maintenance"]["status"] == "unknown"
    assert view["module_status"]["maintenance"]["reason"] == "no_bindings"
    tracked = {t["object_ref"]["ref"]: t for t in view["inputs"]["trackable_objects"]}
    assert tracked, "旧对象应出现在可跟踪清单里"
    checkpoint = next(t for t in tracked.values() if t["kind"] == "checkpoint")
    assert checkpoint["bound"] is False
    assert any(g["reason"] == "dependency_unbound" for g in checkpoint["gaps"]), "原记录没有完整依据必须说出来"

    response = world.track_judgment()
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["created"] is True
    # 绑定时刻是**绑定那一刻**，基线截止是当天：不追溯补成原判断当天已知。
    assert body["created_at"].startswith(fx.BIND_DAY)
    assert body["baseline_cutoff"] == fx.BIND_DAY
    assert body["binding"]["binding_origin"] == "user_confirmed"
    assert body["binding"]["baseline_source_hashes"][fx.REF_SECTOR] == "h-sector-v1"

    # 原判断行一个字节没动。
    assert fx.ledger_hashes(world.user_root) == before
    raw = [json.loads(line) for line in (world.user_root / "judgments.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert raw[0]["ts"] == "2026-09-02T20:00:00+08:00"

    after = world.view()
    assert after["module_status"]["maintenance"]["status"] == "ok"
    assert after["inputs"]["bindings"] == 1


def test_i01_evidence_refs_must_come_from_the_controlled_catalog(world: World) -> None:
    response = world.bind(object_ref=world.judgment_object_ref(), evidence_refs=["fact_market_daily:9999-01-01"])
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "ref_unresolvable"


def test_i01_catalog_hides_versions_recorded_after_the_cutoff(world: World) -> None:
    """目录按知识截止过滤：09-12 那版新哈希在 09-10 的截止下**不该**出现。"""
    late = world.catalog(knowledge_cutoff=fx.BIND_DAY).json()
    assert {v["source_hash"] for v in late["versions"]} == {"h-sector-v1", "h-report-v1"}
    now = world.catalog(knowledge_cutoff=fx.TODAY).json()
    assert "h-sector-v2" in {v["source_hash"] for v in now["versions"]}


# --------------------------------------------------------------------------- #
# I02 来源哈希变 → 待复核 → 判断未变
# --------------------------------------------------------------------------- #
def test_i02_hash_change_is_needs_review_not_refuted_and_close_leaves_judgment_untouched(world: World) -> None:
    world.track_judgment().raise_for_status()
    item = world.open_item()
    assert item["change_type"] == "content_changed"
    assert item["reason_code"] == "hash_changed"
    assert item["epistemic_state"] == "requires_review"
    assert item["action"] == "review_evidence"
    blob = json.dumps(world.view(), ensure_ascii=False)
    assert "已证伪" not in blob and "refuted" not in blob

    before = fx.ledger_hashes(world.user_root)
    response = world.act(
        action="reviewed_no_change",
        idempotency_key="k-review-1",
        item_id=item["id"],
        expected_item_version=item["item_version"],
        expected_management_revision=item["management_revision"],
    )
    assert response.status_code == 200, response.text
    assert response.json()["resulting_status"] == "closed"
    # 关闭的是维护项，不是原判断。
    assert fx.ledger_hashes(world.user_root) == before

    closed = next(i for i in world.view()["maintenance"]["items"] if i["id"] == item["id"])
    assert closed["status"] == "closed"
    assert closed["management"]["closure"]


# --------------------------------------------------------------------------- #
# I03 条件触发 → 排序置前 → 继续核查
# --------------------------------------------------------------------------- #
CONDITION_DOWNGRADE = [
    {
        "condition_id": "cond-stage-downgrade",
        "role": "downgrade",
        "expression": {"all": [{"label": "market_stage", "op": "in", "value": ["反弹"]}]},
        "entity_id": "",
        "label_version": None,
    }
]


def test_i03_triggered_condition_ranks_first_and_rejudge_carries_scope_into_a_real_turn(world: World) -> None:
    world.track_judgment(conditions=CONDITION_DOWNGRADE).raise_for_status()
    view = world.view()
    maintenance = view["maintenance"]
    triggered = [i for i in maintenance["items"] if i["change_type"] == "condition_evaluated" and i["condition_result"] == "true"]
    assert triggered, [(i["change_type"], i["condition_result"]) for i in maintenance["items"]]
    item = triggered[0]
    assert item["condition_role"] == "downgrade"
    assert item["action"] == "rejudge"

    # 01 的真实项进了 02，并排在第一组。
    priority = view["priority"]
    assert priority is not None and priority["selected"], priority["summary"]
    first = priority["selected"][0]
    assert item["id"] in first["维护项"], f"触发项应进第一组：{first}"
    assert "第 1 组" in first["组"]
    payload = first["click_payload"]
    assert payload["conversation_id"] == world.conversation_id
    assert payload["task_id"] == first["task_id"]

    response = world.act(
        action="rejudge",
        idempotency_key="k-rejudge-1",
        item_id=item["id"],
        expected_item_version=item["item_version"],
        expected_management_revision=item["management_revision"],
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["resulting_status"] == "rejudgment_requested"
    continuation = body["continuation"]
    assert continuation["conversation_id"] == world.conversation_id
    assert continuation["maintenance_item_id"] == item["id"]
    assert continuation["object_ref"]["ref"].startswith("judgments.jsonl:")
    assert continuation["source_versions"], "continuation 必须带来源版本"

    # 请求被接受 ≠ 研究完成：项停在 rejudgment_requested，不是 closed。
    after = next(i for i in world.view()["maintenance"]["items"] if i["id"] == item["id"])
    assert after["status"] == "rejudgment_requested"


def test_i03_task_selection_records_the_click_without_changing_any_verdict(world: World) -> None:
    world.track_judgment(conditions=CONDITION_DOWNGRADE).raise_for_status()
    view = world.view()
    task_id = view["priority"]["selected"][0]["task_id"]
    response = world.act(action="select_task", idempotency_key="k-select-1", task_id=task_id)
    assert response.status_code == 200, response.text
    assert response.json()["click_payload"]["task_id"] == task_id
    # 判定不因点击改变。
    assert world.view()["view_digest"] == view["view_digest"]


# --------------------------------------------------------------------------- #
# I04 幂等与版本冲突
# --------------------------------------------------------------------------- #
def test_i04_same_key_replays_once_and_stale_page_gets_409(world: World) -> None:
    world.track_judgment().raise_for_status()
    item = world.open_item()
    args = {
        "action": "claim",
        "idempotency_key": "k-claim-1",
        "item_id": item["id"],
        "expected_item_version": item["item_version"],
        "expected_management_revision": item["management_revision"],
    }
    first = world.act(**args)
    second = world.act(**args)
    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["replayed"] is False
    assert second.json()["replayed"] is True
    assert second.json()["resulting_management_revision"] == first.json()["resulting_management_revision"]

    ledger = (world.user_root / "research_evolution" / "maintenance_actions.jsonl").read_text(encoding="utf-8")
    assert ledger.strip().count("\n") == 0, "同一幂等键只能落一条"

    # 旧页面拿着过期版本再点：409，不关闭新变化。
    stale = world.act(**{**args, "idempotency_key": "k-claim-2", "action": "reviewed_no_change"})
    assert stale.status_code == 409, stale.text
    assert stale.json()["detail"]["code"] == "version_conflict"

    # 同键换载荷：也是 409，幂等键不得复用。
    reused = world.act(**{**args, "action": "rejudge"})
    assert reused.status_code == 409
    assert reused.json()["detail"]["code"] == "idempotency_payload_mismatch"


def test_i04_snooze_expires_back_to_open_without_losing_the_item(world: World) -> None:
    world.track_judgment().raise_for_status()
    item = world.open_item()
    response = world.act(
        action="snooze",
        idempotency_key="k-snooze-1",
        item_id=item["id"],
        expected_item_version=item["item_version"],
        expected_management_revision=item["management_revision"],
        snooze_until="2026-09-15T09:00:00+08:00",
    )
    assert response.status_code == 200, response.text
    assert response.json()["resulting_status"] == "snoozed"
    assert next(i for i in world.view()["maintenance"]["items"] if i["id"] == item["id"])["status"] == "snoozed"
    world.clock.advance(days=2)
    assert next(i for i in world.view()["maintenance"]["items"] if i["id"] == item["id"])["status"] == "open"


# --------------------------------------------------------------------------- #
# I05 资料未到 / 缺轨 / 条件未知 → 保留 gap，不出现「0」「已解除」
# --------------------------------------------------------------------------- #
def test_i05_missing_inputs_stay_unknown_and_never_collapse_to_zero(env: Path) -> None:
    world = World(env, revised=False, market_stage="")
    world.track_judgment(conditions=CONDITION_DOWNGRADE).raise_for_status()
    view = world.view()
    maintenance = view["maintenance"]
    condition_items = [i for i in maintenance["items"] if i["change_type"] == "condition_evaluated"]
    assert condition_items, "缺观测也要出一条「未知」的条件项"
    assert condition_items[0]["condition_result"] == "unknown"
    assert condition_items[0]["epistemic_state"] == "unknown"
    assert condition_items[0]["action"] == "none"
    assert condition_items[0]["gaps"], "未知必须带原因"

    statuses = view["module_status"]
    assert statuses["diagnostics"]["status"] == "unknown"
    assert statuses["validation_receipts"]["status"] == "unknown"
    assert statuses["product_value_receipts"]["status"] == "unknown"
    reasons = {g["reason"] for g in view["gaps"]}
    assert "diagnostics_policy_missing" in reasons
    assert "no_forward_study" in reasons
    blob = json.dumps(view, ensure_ascii=False)
    assert "已解除" not in blob


# --------------------------------------------------------------------------- #
# I06 归属与越界
# --------------------------------------------------------------------------- #
def test_i06_unauthenticated_mode_refuses_arbitrary_user_switch(world: World) -> None:
    response = world.client.get(
        f"/api/conversations/{world.conversation_id}/research-evolution", params={"user": "mallory"}
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "owner_forbidden"
    assert "mallory" not in response.text or "不允许" in response.text


def test_i06_other_users_conversation_is_not_found_not_forbidden(world: World, env: Path) -> None:
    """不泄漏他人对象是否存在：同一个 ``not_found``。"""
    other = world.client.post("/api/conversations", json={"title": "别人的", "user": "alice"})
    other.raise_for_status()
    foreign_id = other.json()["conversation_id"]
    response = world.client.get(
        f"/api/conversations/{foreign_id}/research-evolution", params={"user": fx.OWNER}
    )
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "not_found"
    missing = world.client.get(
        "/api/conversations/conv_doesnotexist/research-evolution", params={"user": fx.OWNER}
    )
    assert missing.status_code == 404
    assert missing.json()["detail"] == response.json()["detail"]


@pytest.mark.parametrize("suffix", ["", "/evidence-catalog", "/bindings", "/actions", "/events"])
def test_i06_path_traversal_is_rejected_without_leaking_paths(world: World, suffix: str) -> None:
    path = f"/api/conversations/..%2Falice/research-evolution{suffix}"
    response = (
        world.client.get(path, params={"user": fx.OWNER, "entity": fx.ENTITY, "as_of": fx.SLICE_DAY})
        if suffix in ("", "/evidence-catalog")
        else world.client.post(path, json={"user": fx.OWNER, "action": "claim", "idempotency_key": "k", "events": [{}], "object_ref": {}, "entity": "x", "as_of": "2026-09-01", "evidence_refs": ["a"]})
    )
    assert response.status_code in (400, 403, 404, 422), response.text
    assert "/Users/" not in response.text


def test_i06_allowlist_lets_an_explicitly_permitted_user_through(env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RESEARCH_EVOLUTION_ALLOWED_USERS", "alice")
    world = World(env)
    alice = world.client.post("/api/conversations", json={"title": "alice 的", "user": "alice"}).json()
    response = world.client.get(
        f"/api/conversations/{alice['conversation_id']}/research-evolution", params={"user": "alice"}
    )
    assert response.status_code == 200
    assert response.json()["owner_user_id"] == "alice"


# --------------------------------------------------------------------------- #
# I07 前向实验未到期 → 仍 pending，普通面板无概率承诺
# --------------------------------------------------------------------------- #
def test_i07_no_probability_promise_on_the_default_panel(world: World) -> None:
    view = world.view()
    assert view["module_status"]["validation_receipts"]["status"] == "unknown"
    assert view["receipt_refs"]["validation"] == []
    blob = json.dumps(view, ensure_ascii=False)
    for banned in ("方法已验证", "Brier", "胜率", "概率优势"):
        assert banned not in blob, f"普通面板不得出现 {banned}"


# --------------------------------------------------------------------------- #
# I08 真实点击 / 失败 run / 重试 → 05 事件，失败保留分母
# --------------------------------------------------------------------------- #
def test_i08_frontend_events_are_stamped_by_the_server_and_deduped(world: World) -> None:
    event = {
        "event_type": "recheck_viewed",
        "event_id": "e-view-1",
        "payload": {
            "object_ref": {"kind": "judgment", "id": "j1", "namespace": "judgments", "version_or_hash": "content_sha256:" + "0" * 64, "scope": None},
            "verdict_ref": None,
            "action_id": None,
            "evidence_refs": [],
            "initiator": "user",
            "assistance_source": "workbench",
        },
    }
    first = world.events([event])
    assert first.status_code == 202, first.text
    assert first.json()["accepted"] == ["e-view-1"], first.json()
    again = world.events([event])
    assert again.json()["duplicates"] == ["e-view-1"]
    assert again.json()["accepted"] == []

    rows = [json.loads(line) for line in (world.user_root / "research_evolution" / "product_value_events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 1
    stored = rows[0]
    assert stored["source_channel"] == "frontend"
    assert stored["provenance"]["kind"] == "observed"
    assert stored["owner_user_id"] == fx.OWNER
    assert stored["recorded_at"].startswith("2026-09-14")


def test_i08_frontend_cannot_self_report_success_quality_or_money(world: World) -> None:
    rejected = world.events(
        [
            {"event_type": "task_completed", "event_id": "e-x1", "payload": {"task_id": "t1", "completion_evidence_refs": [], "terminal_reason": "done", "initiator": "user", "assistance_source": "workbench"}},
            {"event_type": "quality_reviewed", "event_id": "e-x2", "payload": {}},
            {"event_type": "payment_recorded", "event_id": "e-x3", "payload": {}},
            {"event_type": "cost_recorded", "event_id": "e-x4", "payload": {}},
        ]
    )
    assert rejected.status_code == 202
    body = rejected.json()
    assert body["accepted"] == []
    assert {r["code"] for r in body["rejected"]} == {"source_not_allowed"}, body["rejected"]
    assert len(body["rejected"]) == 4, "拒收信息必须逐条回给客户端，不静默丢"
    assert not (world.user_root / "research_evolution" / "product_value_events.jsonl").exists()


def test_i08_failed_run_cannot_be_laundered_into_a_closed_item(world: World) -> None:
    world.track_judgment(conditions=CONDITION_DOWNGRADE).raise_for_status()
    item = next(i for i in world.view()["maintenance"]["items"] if i["action"] == "rejudge")
    world.act(
        action="rejudge",
        idempotency_key="k-rj",
        item_id=item["id"],
        expected_item_version=item["item_version"],
        expected_management_revision=item["management_revision"],
    ).raise_for_status()

    from intelligence.services.run_store import RunStore

    store = RunStore(user_id=fx.OWNER)
    run = store.create_run(question="重判", task_type="research", session_id=world.conversation_id)
    # Q3 合同：运行中先登记「本次维护请求发起了这个 run」。
    current = next(i for i in world.view()["maintenance"]["items"] if i["id"] == item["id"])
    registered = world.act(
        action="link_run",
        idempotency_key="k-link-fail-reg",
        item_id=item["id"],
        run_id=run.run_id,
        expected_item_version=current["item_version"],
        expected_management_revision=current["management_revision"],
    )
    assert registered.status_code == 200 and registered.json()["status"] == "registered", registered.text
    store.finish_run(run.run_id, status="failed", error="上游超时")

    response = world.act(
        action="link_run",
        idempotency_key="k-link-fail",
        item_id=item["id"],
        run_id=run.run_id,
        expected_item_version=current["item_version"],
        expected_management_revision=current["management_revision"],
    )
    assert response.status_code == 200, response.text
    assert response.json()["reason_code"] == "rejudgment_failed"
    # 失败退回 open，不是 closed。
    assert next(i for i in world.view()["maintenance"]["items"] if i["id"] == item["id"])["status"] == "open"


def test_i08_completed_run_without_a_new_judgment_cannot_close_the_item(world: World) -> None:
    world.track_judgment(conditions=CONDITION_DOWNGRADE).raise_for_status()
    item = next(i for i in world.view()["maintenance"]["items"] if i["action"] == "rejudge")
    world.act(
        action="rejudge",
        idempotency_key="k-rj2",
        item_id=item["id"],
        expected_item_version=item["item_version"],
        expected_management_revision=item["management_revision"],
    ).raise_for_status()

    from intelligence.services.run_store import RunStore

    store = RunStore(user_id=fx.OWNER)
    run = store.create_run(question="重判", task_type="research", session_id=world.conversation_id)
    current = next(i for i in world.view()["maintenance"]["items"] if i["id"] == item["id"])
    args = {
        "action": "link_run",
        "item_id": item["id"],
        "run_id": run.run_id,
        "expected_item_version": current["item_version"],
        "expected_management_revision": current["management_revision"],
    }
    registered = world.act(idempotency_key="k-link-nojudgment-reg", **args)
    assert registered.status_code == 200 and registered.json()["status"] == "registered", registered.text
    store.finish_run(run.run_id, status="completed")
    missing = world.act(idempotency_key="k-link-nojudgment", **args)
    assert missing.status_code == 400
    assert missing.json()["detail"]["code"] == "dependency_missing"

    forged = world.act(idempotency_key="k-link-forged", new_judgment_ref="judgments.jsonl:not-a-real-row", **args)
    assert forged.status_code == 400
    assert forged.json()["detail"]["code"] == "ref_unresolvable"

    # 真的写了新判断（原写入者写的）之后才能关联。
    # 时间戳必须晚于复核请求（R7 生成时序闸）：显式给请求之后的时刻，不用真实墙钟——
    # 测试时钟停在 2026-09-14，墙钟比它早，混用会被正确拒绝。
    from intelligence.services import judgments as judgments_svc

    _, new_judgment = judgments_svc.record_judgment(
        world.user_root / "judgments.jsonl",
        memo="配额落地后价格中枢下修",
        themes=["制冷剂"],
        session_id=world.conversation_id,
        ts="2026-09-14T16:30:00+08:00",
    )
    linked = world.act(idempotency_key="k-link-ok", new_judgment_ref=f"judgments.jsonl:{new_judgment['id']}", **args)
    assert linked.status_code == 200, linked.text
    assert linked.json()["reason_code"] == "rejudgment_linked"
    assert next(i for i in world.view()["maintenance"]["items"] if i["id"] == item["id"])["status"] == "closed"


# --------------------------------------------------------------------------- #
# I09 / I16 诊断与练习：曝光先登记，再揭示
# --------------------------------------------------------------------------- #
def _register_diagnostics(world: World, *, coverage: bool = True) -> None:
    world.register("diagnostics_policy", {"policy": fx.diagnostics_policy(), "provenance": "synthetic"})
    world.register("exercise_pack", {"pack": fx.exercise_pack(), "provenance": "synthetic"})
    if coverage:
        world.record_receipt(fx.coverage_receipt())


def test_i09_diagnostics_needs_a_registered_policy_and_marks_synthetic(world: World) -> None:
    assert world.view()["module_status"]["diagnostics"] == {"status": "unknown", "reason": "policy_not_registered", "synthetic": False}
    _register_diagnostics(world)
    status = world.view()["module_status"]["diagnostics"]
    assert status["status"] == "ok"
    assert status["synthetic"] is True, "合成策略必须标出来，不能冒充生产判定"
    report = world.view()["diagnostics"]
    assert report["schema_version"] == "research-diagnostics/v1"
    assert report["policy_id"] == "pol-synthetic-06-v1"


def test_i16_reveal_records_exposure_before_returning_the_answer(world: World) -> None:
    _register_diagnostics(world)
    report = world.view()["diagnostics"]
    exercise = report["exercise"]
    assert exercise is not None, (
        "有 coverage 声明 + 到期未回检 = 有证据的流程问题，必须配出一题："
        f"findings={[(f['kind'], f['classification']) for f in report['findings']]}"
    )
    body = world.act(action="reveal_exercise", idempotency_key="k-reveal", exercise_id=exercise["id"])
    assert body.status_code == 200, body.text
    payload = body.json()
    assert payload["exposure_id"], "必须先登记曝光"

    from intelligence.services.research_validation import Repository

    repo = Repository(world.user_root / "research_validation", owner_user_id=fx.OWNER)
    exposures = repo.list_exposures()
    assert len(exposures) == 1
    assert exposures[0]["stage"] == "practice_reveal"
    assert exposures[0]["actor"] == "research_evolution.reveal_exercise"

    # 再揭示一次：同意图返回原件，不重复登记。
    world.act(action="reveal_exercise", idempotency_key="k-reveal-2", exercise_id=exercise["id"]).raise_for_status()
    assert len(repo.list_exposures()) == 1

    # 曝光收据进了 04 的输入，题从此标记为「已见」。
    after = world.view()["diagnostics"]["exercise"]
    if after is not None:
        assert after["learner_exposure_grade"] == "seen_or_repeated"


def test_i09_answer_key_is_not_in_the_default_projection(world: World) -> None:
    _register_diagnostics(world)
    view = world.view()
    blob = json.dumps(view, ensure_ascii=False)
    pack = fx.exercise_pack()
    for case in pack["cases"]:
        for choice in case["answer_key"]["expected_choices"]:
            assert f'"{choice}"' not in blob, f"揭示前不得出现答案项 {choice}"


# --------------------------------------------------------------------------- #
# I10 重启、缓存、局部异常
# --------------------------------------------------------------------------- #
def test_i10_bindings_and_actions_survive_a_restart(world: World, env: Path) -> None:
    world.track_judgment().raise_for_status()
    item = world.open_item()
    world.act(
        action="claim",
        idempotency_key="k-restart",
        item_id=item["id"],
        expected_item_version=item["item_version"],
        expected_management_revision=item["management_revision"],
    ).raise_for_status()
    before = world.view()

    restarted = create_app(research_evolution_evidence=world.evidence, research_evolution_clock=world.clock)
    client = TestClient(restarted)
    after = client.get(
        f"/api/conversations/{world.conversation_id}/research-evolution", params={"user": fx.OWNER}
    ).json()
    assert after["view_digest"] == before["view_digest"], "重启后同内容必须同摘要"
    assert next(i for i in after["maintenance"]["items"] if i["id"] == item["id"])["status"] == "claimed"


def test_i10_one_broken_module_does_not_blank_the_others(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    world.track_judgment().raise_for_status()
    from intelligence.services import research_priority

    def boom(*_args: object, **_kwargs: object) -> None:
        raise research_priority.ContractError("invalid_policy", "注入故障")

    monkeypatch.setattr("intelligence.services.research_priority.prioritize", boom)
    view = world.view()
    assert view["module_status"]["priority"]["status"] == "error"
    assert view["module_status"]["priority"]["reason"] == "invalid_policy"
    assert view["priority"] is None, "错误不能被空数组掩盖"
    assert view["module_status"]["maintenance"]["status"] == "ok", "其余模块照常给有效结果"
    assert view["maintenance"]["items"]


def test_i10_view_digest_is_stable_but_tracks_content(world: World) -> None:
    first = world.view()
    world.clock.advance(minutes=7)
    second = world.view()
    assert first["view_digest"] == second["view_digest"]
    assert first["generated_at"] != second["generated_at"]
    world.track_judgment().raise_for_status()
    assert world.view()["view_digest"] != first["view_digest"], "内容变了摘要必须变"


# --------------------------------------------------------------------------- #
# I11 关掉使用测量后核心研究照常
# --------------------------------------------------------------------------- #
def test_i11_core_flow_works_with_no_measurement_events_at_all(world: World) -> None:
    world.track_judgment().raise_for_status()
    item = world.open_item()
    world.act(
        action="claim",
        idempotency_key="k-nomeasure",
        item_id=item["id"],
        expected_item_version=item["item_version"],
        expected_management_revision=item["management_revision"],
    ).raise_for_status()
    view = world.view()
    assert view["module_status"]["maintenance"]["status"] == "ok"
    assert view["module_status"]["product_value_receipts"]["status"] == "unknown"
    assert view["module_status"]["product_value_receipts"]["reason"] == "no_measurement_yet"
    assert not (world.user_root / "research_evolution" / "product_value_events.jsonl").exists()
    reasons = {g["reason"] for g in view["gaps"]}
    assert "no_product_value_receipt" in reasons, "缺测范围要说出来，不能宣称用户没用过"


# --------------------------------------------------------------------------- #
# I12 既有入口回归
# --------------------------------------------------------------------------- #
def test_i12_existing_research_project_endpoint_is_unchanged(world: World) -> None:
    response = world.client.get(
        f"/api/conversations/{world.conversation_id}/research-project", params={"user": fx.OWNER}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["conversation_id"] == world.conversation_id
    assert "triggers" in body and "next_questions" in body and "completed_rounds" in body


def test_i12_the_whole_flow_leaves_every_legacy_ledger_byte_identical(world: World) -> None:
    before = fx.ledger_hashes(world.user_root)
    world.track_judgment(conditions=CONDITION_DOWNGRADE).raise_for_status()
    _register_diagnostics(world)
    item = world.open_item()
    world.act(
        action="claim",
        idempotency_key="k-i12",
        item_id=item["id"],
        expected_item_version=item["item_version"],
        expected_management_revision=item["management_revision"],
    )
    world.events([{"event_type": "task_exposed", "event_id": "e-i12", "payload": {"task_id": "t", "policy_version": "research-priority-policy/v1", "view_id": "v", "client_at": "2026-09-14T16:00:00+08:00", "initiator": "user", "assistance_source": "workbench"}}])
    world.view()
    assert fx.ledger_hashes(world.user_root) == before
    # 新写入全部落在本批自己的目录里。
    written = sorted(p.name for p in (world.user_root / "research_evolution").iterdir())
    assert "dependency_bindings.jsonl" in written
    assert "maintenance_actions.jsonl" in written


# --------------------------------------------------------------------------- #
# I17：A → 歧义 B → 复现 A（01 交接给 06 的明确验收项，QC round-11）。
# 旧 snooze / reviewed_no_change 绑历史节点 id：折归时必须逐条 rejected，
# 复现节点保持 open、独立身份，替代链线性无环、历史节点不丢，API 暴露真实反馈。
# --------------------------------------------------------------------------- #


def _recurrence_slice_catalog() -> fx.EvidenceCatalog:
    """SLICE_DAY 目录：A（09-01 基线）→ B（09-12 明确时刻修订）→ C（同 A 哈希、纯日期 09-13 记录、当日过期）。

    B 的记录时刻严格更晚 → A 被同 ref 隐式更正退场；C 纯日期与 B 不可比 → 歧义；
    C 过期 → 歧义消解、B 的状态签名复现 → 复现节点（J12 独立身份，不入原历史链）。
    """
    base_a = {
        "ref": fx.REF_SECTOR,
        "source_hash": "h-sector-v1",
        "valid_from": fx.SLICE_DAY,
        "valid_to": None,
        "recorded_at": f"{fx.SLICE_DAY}T18:00:00+08:00",
        "derivation": "deterministic",
        "namespace": "market_feature_store",
        "_track": "theme",
        "_object_type": "label",
        "_entity_id": "866006.FP",
    }
    report_v = {**base_a, "ref": fx.REF_REPORT, "source_hash": "h-report-v1", "_track": "opinion", "_object_type": "event"}
    revised_b = {**base_a, "source_hash": "h-sector-v2", "recorded_at": "2026-09-12T18:00:00+08:00"}
    interloper = {**base_a, "recorded_at": "2026-09-13", "expired_at": "2026-09-14T10:00:00+08:00"}
    return fx.EvidenceCatalog(
        entity=fx.ENTITY,
        as_of=fx.SLICE_DAY,
        knowledge_cutoff=fx.TODAY,
        versions=(base_a, report_v, revised_b, interloper),
        observations=(),
        gaps=(),
        pit_grade="strict",
        available=True,
    )


@pytest.mark.parametrize("old_action", ["snooze", "reviewed_no_change"])
def test_i17_recurrence_keeps_old_actions_on_the_historical_node(world: World, old_action: str) -> None:
    world.evidence.catalogs[(fx.ENTITY, fx.SLICE_DAY)] = _recurrence_slice_catalog()
    world.track_judgment().raise_for_status()

    # 复现发生前（as_of=09-12）：当前项是 B 的变更节点 N1，旧动作合法落在它身上。
    before = world.view(as_of="2026-09-12", knowledge_cutoff="2026-09-12")["maintenance"]
    open_then = [i for i in before["items"] if i["status"] == "open"]
    assert len(open_then) == 1, [(i["change_type"], i["status"]) for i in before["items"]]
    n1 = open_then[0]
    payload: dict[str, object] = {
        "action": old_action,
        "idempotency_key": f"k-old-{old_action}",
        "item_id": n1["id"],
        "expected_item_version": n1["item_version"],
        "expected_management_revision": n1["management_revision"],
        "as_of": "2026-09-12",
        "knowledge_cutoff": "2026-09-12",
    }
    if old_action == "snooze":
        payload["snooze_until"] = "2026-09-15T09:00:00+08:00"
    accepted = world.act(**payload)
    assert accepted.status_code == 200, accepted.text

    # 复现后（今天）：N1 已被替代；复现节点是独立身份的 open 项，不继承旧动作。
    today = world.view()["maintenance"]
    items = {i["id"]: i for i in today["items"]}
    live_now = [i for i in today["items"] if i["status"] not in ("closed", "superseded")]
    assert len(live_now) == 1, [(i["id"], i["status"]) for i in today["items"]]
    recur = live_now[0]
    assert recur["status"] == "open"
    # J12 独立身份：id 由 dedup_key + "#recur:<day>" 盐派生——公开面上 id 不同、
    # dedup_key 不变（跨报告归并语义不动），而不是 id 里含字面标记。
    assert recur["id"] != n1["id"]
    assert recur["dedup_key"] == n1["dedup_key"]

    # 替代链线性无环、历史节点不丢：recur → … → N1 → 无。
    chain: list[str] = []
    pointer = recur["id"]
    while pointer:
        assert pointer not in chain, "supersedes 成环"
        chain.append(pointer)
        pointer = items[pointer].get("supersedes_item_id")
    assert n1["id"] in chain and len(items) >= 3

    # 歧义提示留在审计轨迹；旧动作事件逐条 rejected 且归属历史节点——API 可见的真实反馈。
    assert "ambiguous_version_order" in json.dumps(today, ensure_ascii=False)
    outcomes = today["management_log"]["outcomes"]
    old = [o for o in outcomes if o["item_id"] == n1["id"]]
    assert len(old) == 1 and old[0]["outcome"] == "rejected", outcomes
    assert not any(o["item_id"] == recur["id"] for o in outcomes), "旧动作不得触碰复现节点"

    # 复现项仍进入排序段（01→02 接缝不断）。
    assert recur["id"] in json.dumps(world.view()["priority"]["selected"], ensure_ascii=False)

    # 迟到动作一：拿历史节点再操作 → 明确拒绝（终态），反馈带原因。
    late = world.act(
        action="reviewed_no_change",
        idempotency_key=f"k-late-{old_action}",
        item_id=n1["id"],
        expected_item_version=items[n1["id"]]["item_version"],
        expected_management_revision=items[n1["id"]]["management_revision"],
    )
    assert late.status_code == 400, late.text
    body = late.json()["detail"]
    assert body["code"] == "action_rejected" and body["detail"]["reason_code"] == "terminal_state", body

    # 迟到动作二：复现节点自身的版本闸仍然有效——错误预期修订号 → 409，不关闭新变化。
    # （item_version 是证据/绑定/条件快照哈希：复现节点与 N1 同证据同绑定，内容版相同，
    #   「拿 N1 旧令牌戳复现节点」与节点真实状态一致时接受是正确行为；真实旧页面只知道
    #   N1 的 id，该情形由上面的 terminal_state 拒绝覆盖。）
    stale = world.act(
        action="reviewed_no_change",
        idempotency_key="k-stale-page",
        item_id=recur["id"],
        expected_item_version=recur["item_version"],
        expected_management_revision=99,
    )
    assert stale.status_code == 409 and stale.json()["detail"]["code"] == "version_conflict", stale.text
    still_open = next(i for i in world.view()["maintenance"]["items"] if i["id"] == recur["id"])
    assert still_open["status"] == "open"
