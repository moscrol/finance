"""06 返修合同测试：把 QC 探针（research-evolution-06-qc-20260913）钉住的缺陷转成正确合同断言。

覆盖 review.md 的 S1–S3 / R1–R10。探针本身指向 QC 副本（返修后应失败），
本文件是仓内可重复执行的正确行为合同——探针的每一条攻击在这里都有对应的正向断言。
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

import intelligence.services.run_store as rs
import intelligence.tests.research_evolution_fixtures as fx
from intelligence.api import app as app_module
from intelligence.services.conversation_store import ConversationStore
from intelligence.services.research_evolution import ResearchEvolutionService, Resources
from intelligence.services.research_evolution.access import OwnerContext
from intelligence.services.research_evolution.adapters import RiverEvidenceSource
from intelligence.services.research_evolution.contracts import ApiError
from intelligence.services.research_evolution.store import RECEIPTS_DIR, SUMMARIES_DIR, EvolutionStore
from intelligence.services.run_store import RunStore
from intelligence.tests.test_research_evolution_api import CONDITION_DOWNGRADE, World as BaseWorld

SH = ZoneInfo("Asia/Shanghai")


class World(BaseWorld):
    """在既有 World 上加三件事：把 turn 执行器换成直接完成的假实现；等 run 终态 / 事件落盘的轮询；
    turn 闸门——测试可以 hold 住 turn 线程，在 run 到终态之前先登记维护关联（Q3 合同的前提时序）。"""

    def __init__(self, users: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.turn_gate = threading.Event()
        self.turn_gate.set()

        def fake_turn(**kwargs: object) -> None:
            self.turn_gate.wait(15)
            store = kwargs["run_store"]
            run_id = kwargs["run_id"]
            assert isinstance(store, RunStore) and isinstance(run_id, str)
            store.append_step(run_id, step_id="s01", name="fake_turn", status="completed", tokens=120)
            store.finish_run(run_id, rs.STATUS_COMPLETED)

        monkeypatch.setattr(app_module, "_run_conversation_turn", fake_turn)
        super().__init__(users)

    def wait_terminal(self, run_id: str, timeout: float = 10.0) -> dict:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            run = self.client.get(f"/api/runs/{run_id}", params={"user": fx.OWNER}).json()
            if run["status"] in ("completed", "failed", "cancelled"):
                return run
            time.sleep(0.05)
        raise AssertionError("run 未在超时内到终态")

    def wait_product_events(self, count: int, timeout: float = 10.0) -> list[dict]:
        """run 终态与事件落盘之间有毫秒级窗口（事件在 claim 之后追加）——轮询消费这个最终一致。"""
        ledger = self.user_root / "research_evolution" / "product_value_events.jsonl"
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if ledger.exists():
                rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]
                if len(rows) >= count:
                    return rows
            time.sleep(0.02)
        raise AssertionError(f"product_value 事件未在超时内达到 {count} 条")

    def current_item(self, item_id: str) -> dict:
        return next(i for i in self.view()["maintenance"]["items"] if i["id"] == item_id)

    def wait_item_status(self, item_id: str, status: str, timeout: float = 10.0) -> dict:
        """观察器终态收尾与 run 状态可见之间有毫秒级窗口（claim 先落 run 状态、后折回）——轮询消费它。"""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                item = self.current_item(item_id)
            except StopIteration:
                time.sleep(0.05)
                continue
            if item["status"] == status:
                return item
            time.sleep(0.05)
        raise AssertionError(f"维护项 {item_id} 未在超时内到 {status}：{self.current_item(item_id)['status']}")

    def link_args(self, item_id: str) -> dict:
        """link_run / cancel_rejudge 也要过版本闸（与 i08 同合同）：带上当前项的期望版本。"""
        current = self.current_item(item_id)
        return {
            "action": "link_run",
            "item_id": item_id,
            "expected_item_version": current["item_version"],
            "expected_management_revision": current["management_revision"],
        }

    def rejudge(self, item: dict, key: str = "k-rejudge") -> dict:
        response = self.act(
            action="rejudge",
            idempotency_key=key,
            item_id=item["id"],
            expected_management_revision=item["management_revision"],
            expected_item_version=item["item_version"],
        )
        assert response.status_code == 200, response.text
        return response.json()

    def seed_rejudged_item(self) -> dict:
        """既有夹具场景：绑定在修订之前 → 打开维护项 → 发起复核。返回 rejudgment_requested 的当前项。"""
        self.track_judgment().raise_for_status()
        item = self.open_item()
        self.rejudge(item)
        return self.current_item(item["id"])


@pytest.fixture()
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> World:
    fx.install_env(monkeypatch, tmp_path)
    return World(tmp_path / "users", monkeypatch)


# --------------------------------------------------------------------------- #
# S1：写侧竞态——两把不同的钥匙、同一份期望版本，只能赢一把
# --------------------------------------------------------------------------- #
def test_s1_concurrent_actions_with_same_expected_revision_exactly_one_wins(world: World) -> None:
    """竞态在 store 层（读-判-写必须在一个锁里），所以直接并发打 service。

    QC 探针用 barrier 卡住 validate 证明旧实现「锁外校验」必双成功；修复后校验在锁内，
    同样的 barrier 会死锁——本测试断言正确合同：无论调度如何，每轮恰好一个 200、一个 409、
    台账恰好一条。
    """
    world.track_judgment().raise_for_status()
    item = world.open_item()
    ctx = OwnerContext.for_owner(fx.OWNER)

    for round_ in range(5):  # 多轮覆盖调度抖动
        current = world.current_item(item["id"])
        assert current["status"] == "open", f"第 {round_} 轮起点应为 open：{current['status']}"
        results: list[tuple[int, str]] = []

        def hit(key: str) -> None:
            try:
                body = world.service.apply_action(
                    ctx=ctx,
                    conversation_id=world.conversation_id,
                    body={
                        "action": "rejudge",
                        "idempotency_key": key,
                        "item_id": item["id"],
                        "expected_management_revision": current["management_revision"],
                        "expected_item_version": current["item_version"],
                    },
                )
                results.append((200, str(body.get("resulting_status") or "")))
            except ApiError as exc:
                results.append((exc.http_status, exc.code))

        threads = [threading.Thread(target=hit, args=(f"k-race-{round_}-{n}",)) for n in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert sorted(results) == [(200, "rejudgment_requested"), (409, "version_conflict")], f"第 {round_} 轮：{results}"

        # 收尾：取消复核回到 open，供下一轮（同时覆盖 cancel_rejudge 的正常路径）。
        current = world.current_item(item["id"])
        cancelled = world.act(
            action="cancel_rejudge",
            idempotency_key=f"k-race-cancel-{round_}",
            item_id=item["id"],
            expected_management_revision=current["management_revision"],
            expected_item_version=current["item_version"],
        )
        assert cancelled.status_code == 200, cancelled.text

    rows = [json.loads(line) for line in (world.user_root / "research_evolution" / "maintenance_actions.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len([r for r in rows if r["event"]["kind"] == "rejudgment_requested"]) == 5, "每轮并发只能落一条 rejudge（锁内复核，不是先写后报错）"
    assert len(rows) == 10, "5 次 rejudge + 5 次取消，各一条动作记录"


# --------------------------------------------------------------------------- #
# S2：import-events——整批与台账对账，冲突则零写入
# --------------------------------------------------------------------------- #
def test_s2_import_events_batch_conflicting_with_ledger_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    from intelligence.services.research_evolution import pilot_io
    from intelligence.tests.test_research_evolution_io import _run

    fx.install_env(monkeypatch, tmp_path)
    good = json.loads((fx.FIXTURE_DIR.parent / "05" / "complete_pair" / "events.jsonl").read_text(encoding="utf-8").splitlines()[0])

    pack1 = tmp_path / "p1.jsonl"
    pack1.write_text(json.dumps(good, ensure_ascii=False) + "\n", encoding="utf-8")
    code, _ = _run(pilot_io, ["--owner", fx.OWNER, "--apply", "import-events", "--events", str(pack1)], capsys)
    assert code == 0

    new_one = {**good, "event_id": "e-new-1"}
    tampered = {**good, "payload": {**good["payload"], "note": "tampered"}}
    pack2 = tmp_path / "p2.jsonl"
    pack2.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in (new_one, tampered)) + "\n", encoding="utf-8")
    code, body = _run(pilot_io, ["--owner", fx.OWNER, "--apply", "import-events", "--events", str(pack2)], capsys)
    assert code == 2, body
    assert body["ok"] is False and body["conflicts"], "同 id 异内容 → 整批拒绝"

    ledger = tmp_path / "users" / fx.OWNER / "research_evolution" / "product_value_events.jsonl"
    ids = [json.loads(line)["event_id"] for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert "e-new-1" not in ids, "整批冲突 → 零写入；同批新事件也不许落"
    assert ids.count(good["event_id"]) == 1


# --------------------------------------------------------------------------- #
# S3：study evaluate——dry-run 不落任何盘
# --------------------------------------------------------------------------- #
def test_s3_evaluate_dry_run_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    from intelligence.services.research_evolution import study_io
    from intelligence.tests.test_research_evolution_io import _run

    fx.install_env(monkeypatch, tmp_path)
    # io 测试的 _forward_protocol 日历只到 evaluation_end（够 dry-run）；apply 需要日历覆盖
    # evaluation_end +  horizon 的结算日，这里把日历延到 09-25。
    body = json.loads((fx.FIXTURE_DIR.parent / "03" / "forward_protocol_synthetic.json").read_text(encoding="utf-8"))
    body.pop("_comment", None)
    body["calendar"] = [f"2026-09-{day:02d}" for day in (1, 2, 3, 4, 7, 8, 9, 10, 11, 14, 15, 16, 17, 18, 21, 22, 23, 24, 25)]
    body["forward_start"] = "2026-09-15"
    body["evaluation_end"] = "2026-09-18"
    protocol_path = tmp_path / "forward.json"
    protocol_path.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
    code, body_out = _run(study_io, ["--owner", fx.OWNER, "--apply", "freeze", "--protocol", str(protocol_path)], capsys)
    assert code == 0, body_out
    study_id = body_out["study_id"]

    root = tmp_path / "users" / fx.OWNER / "research_validation"
    before = sorted(p.relative_to(root) for p in root.rglob("*") if p.is_file())
    code, body = _run(study_io, ["--owner", fx.OWNER, "evaluate", "--study-id", study_id], capsys)
    assert code == 0, body
    assert body["dry_run"] is True and body["would"] == "evaluate_study"
    after = sorted(p.relative_to(root) for p in root.rglob("*") if p.is_file())
    assert before == after, "dry-run 不落任何盘（曝光 / 收据 / 预测都不许多）"

    code, body = _run(study_io, ["--owner", fx.OWNER, "evaluate", "--study-id", "no-such-study"], capsys)
    assert code == 2 and body["dry_run"] is True and body["ok"] is False


# --------------------------------------------------------------------------- #
# R1：复核续研的消息闭环——发起 → 真实消息接受 → 关联登记 → 终态读取
# --------------------------------------------------------------------------- #
def test_r1_rejudge_message_acceptance_and_terminal_link(world: World) -> None:
    world.track_judgment().raise_for_status()
    item = world.open_item()

    # 1) 新会话没有已完成轮次 → continuation 不携带 run_id；纯文本消息必须被接受（不能 422）。
    rejudge = world.rejudge(item)
    continuation = rejudge["continuation"]
    assert "run_id" not in continuation, "没有已完成轮次时不伪造 run_id（从现在开始跟踪）"
    # 2) Q3 合同时序：run 未终态时先登记关联（hold 住 turn 制造这个窗口）。
    world.turn_gate.clear()
    posted = world.client.post(
        f"/api/conversations/{world.conversation_id}/messages",
        json={"user": fx.OWNER, "content": continuation["full_prompt"], "skill_mode": "hybrid"},
    )
    assert posted.status_code == 202, posted.text
    run_id = posted.json()["run_id"]
    registered = world.act(idempotency_key="k-r1-reg", run_id=run_id, **world.link_args(item["id"]))
    assert registered.status_code == 200 and registered.json()["status"] == "registered", registered.text

    # 3) 放行到终态：没有新判断 → 观察器自动收尾失败（诚实拒绝）→ 项停在 rejudgment_requested，可恢复。
    world.turn_gate.set()
    assert world.wait_terminal(run_id)["status"] == "completed"
    time.sleep(0.5)  # 给观察器收尾一个落窗（它若错误闭合，下一步断言会抓到）
    assert world.current_item(item["id"])["status"] == "rejudgment_requested", "缺新判断时自动收尾不许硬关"

    # 4) 原写入者补新判断（请求之后）→ 客户端恢复路径再 link_run → closed。
    from intelligence.services import judgments as judgments_svc

    _, new_judgment = judgments_svc.record_judgment(
        world.user_root / "judgments.jsonl",
        memo="复核后的新判断",
        themes=[fx.ENTITY],
        session_id=world.conversation_id,
        ts="2026-09-14T17:00:00+08:00",
    )
    closed = world.act(
        idempotency_key="k-r1-link-2",
        run_id=run_id,
        new_judgment_ref=f"judgments.jsonl:{new_judgment['id']}",
        **world.link_args(item["id"]),
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["reason_code"] == "rejudgment_linked"
    assert world.current_item(item["id"])["status"] == "closed"


def test_r1_continuation_carries_run_id_once_a_completed_round_exists(world: World) -> None:
    """第二轮起 continuation 必须带可校验的 run_id，整条透传进消息体必须被接受。"""
    world.track_judgment().raise_for_status()
    item = world.open_item()

    posted = world.client.post(f"/api/conversations/{world.conversation_id}/messages", json={"user": fx.OWNER, "content": "先研究一轮制冷剂", "skill_mode": "hybrid"})
    assert posted.status_code == 202, posted.text
    first_run = posted.json()["run_id"]
    assert world.wait_terminal(first_run)["status"] == "completed"

    rejudge = world.rejudge(item)
    continuation = rejudge["continuation"]
    assert continuation.get("run_id") == first_run, "有已完成轮次 → 带上起源 run_id"
    assert continuation["inherits"]["maintenance_item_id"] == item["id"]

    posted2 = world.client.post(
        f"/api/conversations/{world.conversation_id}/messages",
        json={"user": fx.OWNER, "content": continuation["full_prompt"], "skill_mode": "hybrid", "continuation": continuation},
    )
    assert posted2.status_code == 202, f"整条 continuation（含 run_id）透传必须被接受；422 就是 R1 的那个 bug：{posted2.text}"


def test_r1_cancel_rejudge_recovers_from_message_rejection(world: World) -> None:
    item = world.seed_rejudged_item()
    cancelled = world.act(
        action="cancel_rejudge",
        idempotency_key="k-cancel",
        item_id=item["id"],
        expected_management_revision=item["management_revision"],
        expected_item_version=item["item_version"],
        reason="消息未被接受",
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["reason_code"] == "rejudgment_cancelled"
    current = world.current_item(item["id"])
    assert current["status"] == "open", "取消复核 → 回到 open，可重新发起"
    again = world.act(
        action="cancel_rejudge",
        idempotency_key="k-cancel-2",
        item_id=item["id"],
        expected_management_revision=current["management_revision"],
        expected_item_version=current["item_version"],
    )
    assert again.status_code == 400, "不在 rejudgment_requested 的条目不能取消"


# --------------------------------------------------------------------------- #
# R2：练习 submit 也是曝光点——先登记、后判分
# --------------------------------------------------------------------------- #
def test_r2_submit_exercise_registers_exposure_before_grading(world: World) -> None:
    world.register("diagnostics_policy", {"policy": fx.diagnostics_policy(), "provenance": "synthetic"})
    world.register("exercise_pack", {"pack": fx.exercise_pack(), "provenance": "synthetic"})
    world.record_receipt(fx.coverage_receipt())
    exercise = world.view()["diagnostics"]["exercise"]
    assert exercise is not None, "先出题再提交"
    exercise_id = exercise["id"]
    submitted = world.act(action="submit_exercise", idempotency_key="k-submit", exercise_id=exercise_id, selected_choices=[])
    assert submitted.status_code == 200, submitted.text
    from intelligence.services.research_validation import Repository

    repo = Repository(world.user_root / "research_validation", owner_user_id=fx.OWNER)
    rows = repo.list_exposures()
    assert len(rows) == 1, "submit 一次 → 恰好一条曝光（即使交白卷）"
    assert rows[0]["actor"] == "research_evolution.submit_exercise"
    assert rows[0]["stage"] == "practice_reveal"

    bad = world.act(action="submit_exercise", idempotency_key="k-submit-bad", exercise_id="no-such-exercise", selected_choices=["a"])
    assert bad.status_code == 400
    assert len(repo.list_exposures()) == 1, "练习不存在 → 拒绝提交且不登记曝光"


# --------------------------------------------------------------------------- #
# R3：服务端观察 run 生命周期——05 事件经同一 writer 落盘
# --------------------------------------------------------------------------- #
def test_r3_run_lifecycle_emits_product_value_events(world: World) -> None:
    posted = world.client.post(f"/api/conversations/{world.conversation_id}/messages", json={"user": fx.OWNER, "content": "制冷剂怎么看", "skill_mode": "hybrid"})
    assert posted.status_code == 202, posted.text
    run_id = posted.json()["run_id"]
    assert world.wait_terminal(run_id)["status"] == "completed"

    rows = world.wait_product_events(3)
    by_type: dict[str, list[dict]] = {}
    for row in rows:
        by_type.setdefault(row["event_type"], []).append(row)
    assert len(by_type.get("run_started", [])) == 1
    assert len(by_type.get("run_finished", [])) == 1
    started, finished = by_type["run_started"][0], by_type["run_finished"][0]
    for row in (started, finished):
        assert row["source_channel"] == "server", "服务端事件不冒充前端遥测"
        assert row["run_ids"] == [run_id]
        assert row["payload"]["run_id"] == run_id
        assert row["source_version"]["protocol_version"] == "workbench-self-use/v1"
        assert row["pilot_id"].startswith("workbench:"), "自用事件按会话前缀分区，混不进真人试点读数"
    assert finished["payload"]["status"] == "completed"
    costs = by_type.get("cost_recorded", [])
    assert len(costs) == 1, "trace 里有可核 token 用量 → 恰好一条 cost_recorded"
    item = costs[0]["payload"]["cost_item"]
    assert item["certainty"] == "unknown" and item["quantity"] == 120 and item["unit"] == "tokens"
    assert item["amount"] is None, "没有费率就不许编金额"

    ids = [r["event_id"] for r in rows]
    assert len(ids) == len(set(ids)), "同一 run 不写重复 event_id（double-claim 安全）"


# --------------------------------------------------------------------------- #
# R7：link_run 的攻击面——无关会话 / 原判断引用 / 跨会话判断 / 时间倒挂 全部拒绝
# --------------------------------------------------------------------------- #
def test_r7_link_run_rejects_laundering_attempts(world: World) -> None:
    item = world.seed_rejudged_item()
    args = world.link_args(item["id"])

    other = world.client.post("/api/conversations", json={"user": fx.OWNER}).json()
    other_id = other["conversation_id"]
    run_store = RunStore(user_id=fx.OWNER)
    foreign_run = run_store.create_run(question="无关问题", task_type="research", session_id=other_id)
    run_store.finish_run(foreign_run.run_id, "completed")
    foreign = world.act(idempotency_key="k-r7-foreign", run_id=foreign_run.run_id, **args)
    assert foreign.status_code == 400 and foreign.json()["detail"]["code"] == "run_binding_mismatch"

    # 合法前提：本会话的 run 在**运行中**登记关联，再走完终态。之后的攻击都打在这个已登记 run 上。
    own_run = run_store.create_run(question="随便", task_type="research", session_id=world.conversation_id)
    registered = world.act(idempotency_key="k-r7-reg", run_id=own_run.run_id, **args)
    assert registered.status_code == 200 and registered.json()["status"] == "registered", registered.text
    run_store.finish_run(own_run.run_id, "completed")

    original_ref = str(item["object_ref"]["ref"])
    original = world.act(idempotency_key="k-r7-original", run_id=own_run.run_id, new_judgment_ref=original_ref, **args)
    assert original.status_code == 400 and original.json()["detail"]["code"] == "invalid_transition", "原判断引用不是新判断"

    from intelligence.services import judgments as judgments_svc

    _, other_session = judgments_svc.record_judgment(
        world.user_root / "judgments.jsonl",
        memo="别的会话里写的判断",
        themes=[fx.ENTITY],
        session_id=other_id,
        ts="2026-09-14T17:00:00+08:00",
    )
    cross = world.act(idempotency_key="k-r7-cross", run_id=own_run.run_id, new_judgment_ref=f"judgments.jsonl:{other_session['id']}", **args)
    assert cross.status_code == 400 and cross.json()["detail"]["code"] == "run_binding_mismatch", "别的会话的判断不算本会话复核的成果"

    _, stale = judgments_svc.record_judgment(
        world.user_root / "judgments.jsonl",
        memo="复核请求之前写下的旧判断",
        themes=[fx.ENTITY],
        session_id=world.conversation_id,
        ts="2026-09-13T10:00:00+08:00",
    )
    stale_link = world.act(idempotency_key="k-r7-stale", run_id=own_run.run_id, new_judgment_ref=f"judgments.jsonl:{stale['id']}", **args)
    assert stale_link.status_code == 400 and stale_link.json()["detail"]["code"] == "dependency_missing", "请求之前的判断不算这次复核的成果"

    assert world.current_item(item["id"])["status"] == "rejudgment_requested", "全部攻击失败 → 条目状态不变"


def test_q3_unregistered_same_session_run_cannot_fold(world: World) -> None:
    """QC Q3 探针移植：同会话的无关 run / 旧失败 run 没登记过关联 → 一律 400，项保持 rejudgment_requested。"""
    item = world.seed_rejudged_item()
    args = world.link_args(item["id"])
    run_store = RunStore(user_id=fx.OWNER)

    unrelated = run_store.create_run(question="同会话无关 run", task_type="research", session_id=world.conversation_id)
    run_store.finish_run(unrelated.run_id, "completed")
    from intelligence.services import judgments as judgments_svc

    _, new_judgment = judgments_svc.record_judgment(
        world.user_root / "judgments.jsonl",
        memo="攻击者判断",
        themes=[fx.ENTITY],
        session_id=world.conversation_id,
        ts="2026-09-14T17:00:00+08:00",
    )
    attack = world.act(
        idempotency_key="k-q3-attack",
        run_id=unrelated.run_id,
        new_judgment_ref=f"judgments.jsonl:{new_judgment['id']}",
        **args,
    )
    assert attack.status_code == 400 and attack.json()["detail"]["code"] == "run_binding_mismatch"
    assert world.current_item(item["id"])["status"] == "rejudgment_requested"

    old_failed = run_store.create_run(question="同会话旧失败 run", task_type="research", session_id=world.conversation_id)
    run_store.finish_run(old_failed.run_id, "failed")
    attack2 = world.act(idempotency_key="k-q3-attack2", run_id=old_failed.run_id, **args)
    assert attack2.status_code == 400 and attack2.json()["detail"]["code"] == "run_binding_mismatch"
    assert world.current_item(item["id"])["status"] == "rejudgment_requested", "失败 run 不许把项弹回 open"


def test_r7_link_run_registers_association_before_terminal(world: World) -> None:
    """消息刚被接受、run 还在跑：link_run 登记关联并返回 registered，不冒充闭环。"""
    item = world.seed_rejudged_item()
    run_store = RunStore(user_id=fx.OWNER)
    pending_run = run_store.create_run(question="复核", task_type="research", session_id=world.conversation_id)

    registered = world.act(idempotency_key="k-r7-reg", run_id=pending_run.run_id, **world.link_args(item["id"]))
    assert registered.status_code == 200, registered.text
    body = registered.json()
    assert body["status"] == "registered" and body["reason_code"] == "run_registered"
    assert world.current_item(item["id"])["status"] == "rejudgment_requested", "登记不推进条目状态"

    run_store.finish_run(pending_run.run_id, "completed")
    from intelligence.services import judgments as judgments_svc

    _, new_judgment = judgments_svc.record_judgment(
        world.user_root / "judgments.jsonl",
        memo="新判断",
        themes=[fx.ENTITY],
        session_id=world.conversation_id,
        ts="2026-09-14T17:00:00+08:00",
    )
    closed = world.act(
        idempotency_key="k-r7-close",
        new_judgment_ref=f"judgments.jsonl:{new_judgment['id']}",
        **world.link_args(item["id"]),
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["reason_code"] == "rejudgment_linked"
    assert closed.json()["link"]["association"] == "registered", "终态后不带 run_id → 由登记的关联解析"


# --------------------------------------------------------------------------- #
# R8：时钟推进后的重试 = duplicate / 复用，不是 conflict / 第二条
# --------------------------------------------------------------------------- #
def test_r8_duplicate_event_with_advanced_clock_is_duplicate_not_conflict(world: World) -> None:
    # 与 i08 同形状的前端允许事件。
    event = {
        "event_type": "recheck_viewed",
        "event_id": "e-clock-1",
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
    assert first.json()["accepted"] == ["e-clock-1"]
    world.clock.advance(hours=2)
    retry = world.events([event])
    assert retry.status_code == 202
    assert retry.json()["duplicates"] == ["e-clock-1"], "客户端没给 event_at → 用台账里的原件时间，内容一致 → duplicate"
    assert retry.json()["rejected"] == []


def test_r8_recreate_same_binding_with_advanced_clock_reuses_record(world: World) -> None:
    first = world.track_judgment()
    assert first.status_code == 201, first.text
    world.clock.advance(days=1)  # 第二天重试
    again = world.bind(object_ref=world.judgment_object_ref())
    assert again.status_code == 201, again.text
    assert again.json()["binding_id"] == first.json()["binding_id"]
    assert again.json()["created"] is False, "业务载荷一致 → 复用已落盘记录，不新建第二份基线"
    assert again.json()["created_at"] == first.json()["created_at"]
    assert again.json()["baseline_cutoff"] == first.json()["baseline_cutoff"]
    store = EvolutionStore(world.user_root / "research_evolution", fx.OWNER)
    assert len(store.list_bindings()) == 1


def test_r8_same_natural_key_with_changed_payload_is_409(world: World) -> None:
    """binding_id 是自然键（对象+引用+实体+切片日）：同键不同业务载荷 → 409，不静默复用也不新建。"""
    from intelligence.tests.test_research_evolution_api import CONDITION_DOWNGRADE

    first = world.track_judgment()
    assert first.status_code == 201, first.text
    changed = world.bind(object_ref=world.judgment_object_ref(), conditions=CONDITION_DOWNGRADE)
    assert changed.status_code == 409, changed.text
    assert changed.json()["detail"]["code"] == "idempotency_payload_mismatch"


# --------------------------------------------------------------------------- #
# R9：当前来源读不动 → unknown，不许报「无需复核」；回看式 cutoff 的台账可读
# --------------------------------------------------------------------------- #
def test_r9_unreadable_current_source_reports_unknown_not_unchanged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """生产证据源（无 DuckDB）：绑定基线在、当前读不动 → maintenance 必须 unknown，且不出绑定清单。"""
    fx.install_env(monkeypatch, tmp_path)
    users = tmp_path / "users"
    service = ResearchEvolutionService(
        Resources(
            evidence_source=RiverEvidenceSource(),
            conversation_store_for=lambda user: ConversationStore(user_id=user),
            run_store_for=lambda user: RunStore(user_id=user),
            clock=fx.FakeClock(),
        )
    )
    ctx = OwnerContext.for_owner(fx.OWNER)
    conversation = ConversationStore(user_id=fx.OWNER).create_conversation("R9")
    fx.seed_legacy_ledgers(users / fx.OWNER, session_id=conversation.conversation_id)
    # 绑定当天的基线也读不到（无 db）→ create_binding 应拒绝；改用「绑定可读、当前读不动」的两段式：
    # 先用静态源绑定，再换生产源读 view。
    static_service = ResearchEvolutionService(
        Resources(
            evidence_source=fx.evidence_source(),
            conversation_store_for=lambda user: ConversationStore(user_id=user),
            run_store_for=lambda user: RunStore(user_id=user),
            clock=fx.FakeClock(),
        )
    )
    view = static_service.view(ctx=ctx, conversation_id=conversation.conversation_id)
    trackable = next(t for t in view["inputs"]["trackable_objects"] if t["kind"] == "judgment")
    static_service.create_binding(
        ctx=ctx,
        conversation_id=conversation.conversation_id,
        body={
            "entity": fx.ENTITY,
            "as_of": fx.SLICE_DAY,
            "object_ref": trackable["object_ref"],
            "evidence_refs": [fx.REF_SECTOR, fx.REF_REPORT],
        },
    )
    view = service.view(ctx=ctx, conversation_id=conversation.conversation_id)
    maintenance_module = view["module_status"]["maintenance"]
    assert maintenance_module["status"] == "unknown", "当前来源读不动 → unknown，不报 ok"
    assert maintenance_module["reason"] == "current_source_unreadable"
    assert view["maintenance"] is None, "读不动时不许出「无逾期」的空清单（那会被读成无需复核）"
    gap_reasons = [g["reason"] for g in view["gaps"]]
    assert any(r.startswith("evidence_source_") for r in gap_reasons), f"读不动要留下可追查的 gap：{gap_reasons}"


def test_r9_hindsight_cutoff_passes_allow_hindsight(monkeypatch: pytest.MonkeyPatch) -> None:
    """回看式知识截止晚于 as_of：以允许回看的口径读源（pit 永不 strict），不伪造 400。"""
    from intelligence.services import river

    calls: list[dict] = []

    def fake_slice_river(*args, **kwargs):  # noqa: ANN001
        calls.append(kwargs)
        raise FileNotFoundError("no db in test")

    monkeypatch.setattr(river, "slice_river", fake_slice_river)
    monkeypatch.delenv("MARKET_FEATURE_STORE_DB", raising=False)
    source = RiverEvidenceSource()
    catalog = source.catalog(owner_user_id=fx.OWNER, entity=fx.ENTITY, as_of="2026-09-10", knowledge_cutoff="2026-09-10")
    assert catalog.available is False and catalog.reason == "market_db_unavailable"
    assert calls[-1]["allow_hindsight"] is False, "正常请求不开回看"

    catalog = source.catalog(owner_user_id=fx.OWNER, entity=fx.ENTITY, as_of="2026-09-10", knowledge_cutoff="2026-09-13")
    assert catalog.reason == "market_db_unavailable", "db 缺席仍明确报不可用，但不伪造 invalid_slice_request"
    assert calls[-1]["allow_hindsight"] is True, "回看式 cutoff → 允许回看读源（pit 永不 strict）"


# --------------------------------------------------------------------------- #
# R10：会话级幂等域——跨会话重放同一把钥匙 → 409
# --------------------------------------------------------------------------- #
def test_r10_cross_conversation_replay_is_rejected(world: World) -> None:
    world.track_judgment().raise_for_status()
    item = world.open_item()
    payload = {
        "action": "rejudge",
        "user": fx.OWNER,
        "idempotency_key": "k-cross",
        "item_id": item["id"],
        "expected_management_revision": item["management_revision"],
        "expected_item_version": item["item_version"],
    }
    first = world.client.post(f"/api/conversations/{world.conversation_id}/research-evolution/actions", json=payload)
    assert first.status_code == 200, first.text

    replay = world.client.post(f"/api/conversations/{world.conversation_id}/research-evolution/actions", json=payload)
    assert replay.status_code == 200 and replay.json()["replayed"] is True, "同会话同键同载荷 → 幂等命中"

    other = world.client.post("/api/conversations", json={"user": fx.OWNER}).json()
    cross = world.client.post(f"/api/conversations/{other['conversation_id']}/research-evolution/actions", json=payload)
    assert cross.status_code == 409, cross.text
    assert cross.json()["detail"]["code"] == "idempotency_payload_mismatch"


# --------------------------------------------------------------------------- #
# R5：read_receipt 动作——三类收据走各自真源
# --------------------------------------------------------------------------- #
def test_r5_read_receipt_action(world: World) -> None:
    store = EvolutionStore(world.user_root / "research_evolution", fx.OWNER)
    store.publish_immutable(RECEIPTS_DIR, "rc-1", {"id": "rc-1", "empirical_status": "supported", "counts": {"n": 3}})

    ok = world.act(action="read_receipt", idempotency_key="k-rr-1", receipt_kind="measurement_receipt", receipt_id="rc-1")
    assert ok.status_code == 200, ok.text
    assert ok.json()["receipt"]["empirical_status"] == "supported"

    missing = world.act(action="read_receipt", idempotency_key="k-rr-2", receipt_kind="measurement_receipt", receipt_id="nope")
    assert missing.status_code == 404 and missing.json()["detail"]["code"] == "not_found"

    no_study = world.act(action="read_receipt", idempotency_key="k-rr-3", receipt_kind="method_validation_receipt")
    assert no_study.status_code == 400 and no_study.json()["detail"]["code"] == "invalid_request", "03 收据必须给 study_id"

    no_receipt = world.act(action="read_receipt", idempotency_key="k-rr-3b", receipt_kind="method_validation_receipt", study_id="no-such-study")
    assert no_receipt.status_code == 404, "不存在的 study → 明确错误，不伪造收据"

    bad_kind = world.act(action="read_receipt", idempotency_key="k-rr-4", receipt_kind="weird")
    assert bad_kind.status_code == 400 and bad_kind.json()["detail"]["code"] == "invalid_request"


# --------------------------------------------------------------------------- #
# 第二轮（复审 ba10747d，Q1–Q9）：把复审探针钉住的缺陷转成仓内正确合同
# --------------------------------------------------------------------------- #
def test_q1_binding_form_ref_string_accepted(world: World) -> None:
    """表单 / 探针只给 object_ref 字符串 → 服务端按受控清单解析全字段，不再 422。"""
    response = world.bind(object_ref=world.judgment_object_ref()["ref"])
    assert response.status_code == 201, response.text
    binding = response.json()["binding"]
    assert isinstance(binding["object_ref"], dict) and binding["object_ref"]["kind"] == "judgment"


def test_q2_terminal_completed_run_waits_for_explicit_outcome_confirmation(world: World) -> None:
    """过渡合同（QC 第七轮 X1 调整）：注册 → 终态 → 观察器**不再**自动收尾闭合。

    writer 无归属坐标时，「同会话 + 时间较新 + 历史唯一」都证明不了判断属于本轮；
    无身份成果一律保持待复核，显式 link_run 带 new_judgment_ref 才闭环（面板「确认成果」）。
    """
    world.track_judgment().raise_for_status()
    item = world.open_item()
    rejudge = world.rejudge(item)
    world.turn_gate.clear()
    posted = world.client.post(
        f"/api/conversations/{world.conversation_id}/messages",
        json={"user": fx.OWNER, "content": rejudge["continuation"]["full_prompt"], "skill_mode": "hybrid"},
    )
    assert posted.status_code == 202, posted.text
    run_id = posted.json()["run_id"]
    reg_args = world.link_args(item["id"])
    registered = world.act(idempotency_key="k-q2-reg", run_id=run_id, **reg_args)
    assert registered.status_code == 200 and registered.json()["status"] == "registered", registered.text

    from intelligence.services import judgments as judgments_svc

    _, new_judgment = judgments_svc.record_judgment(
        world.user_root / "judgments.jsonl",
        memo="复核后的新判断",
        themes=[fx.ENTITY],
        session_id=world.conversation_id,
        ts="2026-09-14T17:00:00+08:00",
    )
    world.turn_gate.set()
    assert world.wait_terminal(run_id)["status"] == "completed"
    # 观察器收尾与内联恢复都必须拒绝自动关闭：无身份成果不是本轮成果。
    world.service.fold_run_terminal(ctx=OwnerContext.for_owner(fx.OWNER), run_id=run_id)
    held = world.current_item(item["id"])
    assert held["status"] == "rejudgment_requested", "无身份成果不许自动关闭（X1：数量不是归属证明）"
    rows = [json.loads(line) for line in (world.user_root / "research_evolution" / "maintenance_actions.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    linked = [r for r in rows if isinstance(r.get("event"), dict) and r["event"]["kind"] == "rejudgment_linked"]
    assert not linked, "未确认前不许落闭环事件"

    # 显式确认成果 → 闭环，恰好一条；同键重试 = 重放（载荷逐字节相同，模拟响应丢失）。
    confirm_args = world.link_args(item["id"])
    confirm_ref = f"judgments.jsonl:{new_judgment['id']}"
    closed = world.act(
        idempotency_key="k-q2-confirm",
        run_id=run_id,
        new_judgment_ref=confirm_ref,
        **confirm_args,
    )
    assert closed.status_code == 200 and closed.json()["reason_code"] == "rejudgment_linked", closed.text
    assert world.current_item(item["id"])["status"] == "closed"
    rows = [json.loads(line) for line in (world.user_root / "research_evolution" / "maintenance_actions.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    linked = [r for r in rows if isinstance(r.get("event"), dict) and r["event"]["kind"] == "rejudgment_linked"]
    assert len(linked) == 1, f"rejudgment_linked 应恰好一条：{len(linked)}"
    retry = world.act(
        idempotency_key="k-q2-confirm",
        run_id=run_id,
        new_judgment_ref=confirm_ref,
        **confirm_args,
    )
    assert retry.status_code == 200 and retry.json()["replayed"] is True


def test_x1_sole_rejudge_cannot_autopick_ordinary_chat_judgment(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    """X1：本会话历史唯一一次复核，也不能认领普通聊天产生的同会话判断——
    复核请求历史唯一 ≠ 判断生产者唯一。"""
    from intelligence.services import judgments as judgments_svc

    world.track_judgment().raise_for_status()
    item = world.open_item()
    request = world.rejudge(item)
    store = EvolutionStore(world.user_root / "research_evolution", fx.OWNER)

    def ordinary_turn(**kwargs: object) -> None:
        judgments_svc.record_judgment(
            world.user_root / "judgments.jsonl",
            memo="普通聊天产生的独立观点：银行息差，不是复核成果",
            themes=["银行"],
            session_id=world.conversation_id,
            ts=world.clock().isoformat(),
        )
        kwargs["run_store"].finish_run(kwargs["run_id"], "completed")  # type: ignore[attr-defined]

    world.clock.advance(seconds=1)
    monkeypatch.setattr(app_module, "_run_conversation_turn", ordinary_turn)
    ordinary = world.client.post(
        f"/api/conversations/{world.conversation_id}/messages",
        json={"user": fx.OWNER, "content": "先放下复核，记录另一个银行观点。", "skill_mode": "hybrid"},
    )
    assert ordinary.status_code == 202, ordinary.text
    world.wait_terminal(ordinary.json()["run_id"])
    assert not store.list_run_links()
    before = world.current_item(item["id"])

    def no_judgment_turn(**kwargs: object) -> None:
        kwargs["run_store"].finish_run(kwargs["run_id"], "completed")  # type: ignore[attr-defined]

    monkeypatch.setattr(app_module, "_run_conversation_turn", no_judgment_turn)
    maintenance = world.client.post(
        f"/api/conversations/{world.conversation_id}/messages",
        json={
            "user": fx.OWNER,
            "content": request["continuation"]["full_prompt"],
            "skill_mode": "hybrid",
            "maintenance_launch": {
                "item_id": request["continuation"]["maintenance_item_id"],
                "request_event_id": request["continuation"]["request_event_id"],
            },
        },
    )
    assert maintenance.status_code == 202, maintenance.text
    maintenance_id = maintenance.json()["run_id"]
    world.wait_terminal(maintenance_id)
    world.service.fold_run_terminal(ctx=OwnerContext.for_owner(fx.OWNER), run_id=maintenance_id)
    after = world.current_item(item["id"])
    assert after["status"] == "rejudgment_requested", "历史唯一请求也不是成果来源证明"
    assert after["management_revision"] == before["management_revision"]


def test_q5_running_link_retry_replays_not_conflicts(world: World) -> None:
    """Q5：运行中登记的同键重试 = 重放首个注册结果（registered_at 不漂）；同键异 run = 409。"""
    item = world.seed_rejudged_item()
    run_store = RunStore(user_id=fx.OWNER)
    run_a = run_store.create_run(question="a", task_type="research", session_id=world.conversation_id)
    key = "k-q5-same"
    first = world.act(idempotency_key=key, run_id=run_a.run_id, **world.link_args(item["id"]))
    assert first.status_code == 200 and first.json()["status"] == "registered", first.text
    world.clock.advance(hours=1)
    retry = world.act(idempotency_key=key, run_id=run_a.run_id, **world.link_args(item["id"]))
    assert retry.status_code == 200, retry.text
    body = retry.json()
    assert body["replayed"] is True and body["status"] == "registered"
    assert body["link"]["registered_at"] == first.json()["link"]["registered_at"], "重试重放首次登记时刻，不随重试时钟漂"

    run_b = run_store.create_run(question="b", task_type="research", session_id=world.conversation_id)
    conflict = world.act(idempotency_key=key, run_id=run_b.run_id, **world.link_args(item["id"]))
    assert conflict.status_code == 409 and conflict.json()["detail"]["code"] == "idempotency_payload_mismatch"

    # 同 (item, run) 不同键：复用已登记行，不重复追加。
    again = world.act(idempotency_key="k-q5-other-key", run_id=run_a.run_id, **world.link_args(item["id"]))
    assert again.status_code == 200 and again.json()["link"]["link_created"] is False, again.text
    store = EvolutionStore(world.user_root / "research_evolution", fx.OWNER)
    assert len(store.list_run_links()) == 1


def test_q6_select_task_replay_and_conflict(world: World) -> None:
    """Q6：同键同任务 → 重放（含原 continuation）；同键异任务 → 409；事件恰好一条。"""
    world.track_judgment().raise_for_status()
    view = world.view()
    task_id = view["priority"]["selected"][0]["task_id"]
    first = world.act(action="select_task", idempotency_key="k-q6", task_id=task_id, client_at="2026-09-14T09:00:00+08:00")
    assert first.status_code == 200, first.text
    world.clock.advance(hours=1)
    retry = world.act(action="select_task", idempotency_key="k-q6", task_id=task_id, client_at="2026-09-14T10:00:00+08:00")
    assert retry.status_code == 200, retry.text
    assert retry.json()["replayed"] is True
    assert retry.json()["continuation"] == first.json()["continuation"], "重放首次选择时的 continuation，不随重试漂"

    other_task = view["priority"]["selected"][1]["task_id"] if len(view["priority"]["selected"]) > 1 else f"{task_id}-other"
    conflict = world.act(action="select_task", idempotency_key="k-q6", task_id=other_task)
    assert conflict.status_code == 409 and conflict.json()["detail"]["code"] == "idempotency_payload_mismatch"

    ledger = world.user_root / "research_evolution" / "product_value_events.jsonl"
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len([r for r in rows if r["event_type"] == "task_selected"]) == 1, "两次同键调用只能落一条 task_selected"


def test_q7_select_task_refs_survive_message_boundary(world: World) -> None:
    """Q7：select_task 的 source/object/version refs 装在 continuation.click_payload 里，随消息落盘。"""
    world.track_judgment().raise_for_status()
    # 先完成一轮真实对话，select_task 的 continuation 才带可校验的 run_id（消息合同要求）。
    posted0 = world.client.post(f"/api/conversations/{world.conversation_id}/messages", json={"user": fx.OWNER, "content": "先研究一轮", "skill_mode": "hybrid"})
    assert posted0.status_code == 202, posted0.text
    assert world.wait_terminal(posted0.json()["run_id"])["status"] == "completed"

    task_id = world.view()["priority"]["selected"][0]["task_id"]
    selected = world.act(action="select_task", idempotency_key="k-q7", task_id=task_id)
    assert selected.status_code == 200, selected.text
    continuation = selected.json()["continuation"]
    payload = continuation.get("click_payload") or {}
    refs = payload.get("source_refs") or []
    assert refs, "任务卡的 click_payload 必须带 source_refs"

    posted = world.client.post(
        f"/api/conversations/{world.conversation_id}/messages",
        json={"user": fx.OWNER, "content": str(continuation.get("full_prompt") or "研究这个"), "skill_mode": "hybrid", "continuation": continuation},
    )
    assert posted.status_code == 202, posted.text
    from intelligence.services import research_project

    messages = ConversationStore(user_id=fx.OWNER).load_messages(world.conversation_id)
    saved = research_project.continuation_for_run(messages, posted.json()["run_id"])
    assert saved is not None, "用户消息上必须落 continuation"
    assert (saved.get("click_payload") or {}).get("source_refs"), f"click_payload.source_refs 必须穿过消息边界：{saved}"


def test_q8_read_receipt_all_three_kinds(world: World, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Q8：三类收据原件都能经动作层读出；pilot_summary 无 id 时读最新一份。"""
    from intelligence.services.research_evolution import study_io
    from intelligence.tests.test_research_evolution_io import _run

    # 1) method_validation_receipt：按 study_id 读。
    protocol = json.loads((fx.FIXTURE_DIR.parent / "03" / "forward_protocol_synthetic.json").read_text(encoding="utf-8"))
    protocol.pop("_comment", None)
    protocol["calendar"] = [f"2026-09-{day:02d}" for day in (1, 2, 3, 4, 7, 8, 9, 10, 11, 14, 15, 16, 17, 18, 21, 22, 23, 24, 25)]
    protocol["forward_start"] = "2026-09-15"
    protocol["evaluation_end"] = "2026-09-18"
    protocol_path = tmp_path / "forward.json"
    protocol_path.write_text(json.dumps(protocol, ensure_ascii=False), encoding="utf-8")
    code, frozen = _run(study_io, ["--owner", fx.OWNER, "--apply", "freeze", "--protocol", str(protocol_path)], capsys)
    assert code == 0, frozen
    study_id = frozen["study_id"]
    code, _ = _run(study_io, ["--owner", fx.OWNER, "--apply", "evaluate", "--study-id", study_id], capsys)
    assert code == 0
    method = world.act(action="read_receipt", idempotency_key="k-q8-method", kind="method_validation_receipt", study_id=study_id)
    assert method.status_code == 200 and method.json()["receipt"]["study_id"] == study_id, method.text

    # 2) measurement_receipt：按 receipt_id 读。
    receipt = fx.coverage_receipt()
    world.record_receipt(receipt)
    measurement = world.act(action="read_receipt", idempotency_key="k-q8-measure", kind="measurement_receipt", receipt_id=receipt["receipt_id"])
    assert measurement.status_code == 200 and measurement.json()["receipt"]["receipt_id"] == receipt["receipt_id"], measurement.text

    # 3) pilot_summary：receipt_id / study_id 都不给 → 最新一份。先经单 writer 播种一份总结。
    store = EvolutionStore(world.user_root / "research_evolution", fx.OWNER)
    with store.transaction() as txn:
        txn.publish_immutable(SUMMARIES_DIR, "sum-q8", {"summary_id": "sum-q8", "protocol_hash": "ph-q8", "engineering_status": "ok", "field_status": "ok", "commercial_status": "unknown"})
    summary = world.act(action="read_receipt", idempotency_key="k-q8-summary", kind="pilot_summary")
    assert summary.status_code == 200, summary.text
    assert summary.json()["receipt"].get("protocol_hash") == "ph-q8", summary.text
    # summary_id 寻址也收（前端视图只给 summary_id）。
    by_id = world.act(action="read_receipt", idempotency_key="k-q8-summary-2", kind="pilot_summary", summary_id="sum-q8")
    assert by_id.status_code == 200 and by_id.json()["receipt"]["summary_id"] == "sum-q8", by_id.text


def test_q9_observer_never_blocks_run_on_evolution_lock(world: World, capsys: pytest.CaptureFixture[str]) -> None:
    """Q9：测量锁被占满时 create_run 不得被堵——有界等待超时后跳过测量，stderr 留痕。"""
    from intelligence.services.research_evolution.run_observer import ObservingRunStore

    store = EvolutionStore(world.user_root / "research_evolution", fx.OWNER)
    observer = ObservingRunStore(user_id=fx.OWNER, evolution_root=world.user_root / "research_evolution")
    entered = threading.Event()
    release = threading.Event()
    blocker_elapsed: list[float] = []

    def hold() -> None:
        with store.transaction():
            entered.set()
            release.wait(5)

    holder = threading.Thread(target=hold)
    holder.start()
    assert entered.wait(5), "持锁线程没起来"

    def timed_create() -> None:
        start = time.perf_counter()
        observer.create_run(question="x", task_type="research", session_id=world.conversation_id)
        blocker_elapsed.append(time.perf_counter() - start)

    try:
        timed_create()
    finally:
        release.set()
        holder.join(timeout=5)
    assert blocker_elapsed[0] < 0.3 + 1.0, f"run 被测量锁堵了 {blocker_elapsed[0]:.2f}s（阈值内应立刻返回）"
    assert "跳过" in capsys.readouterr().err, "锁被占必须 stderr 留痕（事件丢失可见），不是静默"


# --------------------------------------------------------------------------- #
# 第三轮 QC（re06-0c275716）T1–T5：探针的正确合同固化。
# 探针本体在 docs/verification/re06-0c275716/test_review_round3.py；这里是仓内回归。
# --------------------------------------------------------------------------- #
def _launch_message(world: World, item: dict, content: str = "继续核查") -> str:
    """以真实客户端形状发启动消息：携带服务端生成的请求实例坐标（QC V2）。返回 run_id。"""
    launch = {"item_id": item["id"], "request_event_id": item["management"]["rejudgment"]["request_event_id"]}
    posted = world.client.post(
        f"/api/conversations/{world.conversation_id}/messages",
        json={"user": fx.OWNER, "content": content, "skill_mode": "hybrid", "maintenance_launch": launch},
    )
    assert posted.status_code == 202, posted.text
    return posted.json()["run_id"]


def test_t1_run_terminal_before_second_request_still_reconciles(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    """T1：run 在浏览器第二个请求（link_run）之前到终态——消息接受侧已登记可信关联，收尾不卡死。

    真实 UI 次序是「先 POST messages 拿 run_id，再 POST link_run」，模型可以在此之前就失败。
    修复：create_message 在启动执行器前按消息携带的**请求实例坐标**（QC V2：item_id +
    request_event_id，首轮也能携带）登记关联，服务端回查 rejudge 台账核验当前代际。
    """
    def fail_turn(**kwargs: object) -> None:
        kwargs["run_store"].finish_run(kwargs["run_id"], "failed", error="model unavailable")  # type: ignore[attr-defined]

    monkeypatch.setattr(app_module, "_run_conversation_turn", fail_turn)
    item = world.seed_rejudged_item()
    run_id = _launch_message(world, item)
    world.wait_terminal(run_id)

    # 关联在消息接受侧已落盘（不等客户端 link_run），且带本轮请求的代际身份。
    store = EvolutionStore(world.user_root / "research_evolution", fx.OWNER)
    links = [r for r in store.list_run_links(item_id=item["id"]) if str(r.get("run_id")) == run_id]
    assert len(links) == 1, f"接受侧必须登记恰好一条关联：{links}"
    assert links[0]["request_event_id"] == item["management"]["rejudgment"]["request_event_id"]
    assert links[0]["conversation_id"] == world.conversation_id

    # 迟到的客户端 link_run：观察器已折回 → 重放折回结果；观察器还没落地 → 内联折回。都必须 200。
    response = world.act(idempotency_key=f"link_run:{item['id']}:{run_id}", run_id=run_id, **world.link_args(item["id"]))
    assert response.status_code == 200, f"合法复核不许因「登记前终态」被拒：{response.text}"
    closed = world.wait_item_status(item["id"], "open")
    assert closed["management_revision"] == item["management_revision"] + 1, "失败折回恰好一次（观察器与客户端不双写）"
    assert closed["management"]["rejudgment"]["last_failure"]["kind"] == "rejudgment_failed"


def test_t1_accept_time_binding_scoped_to_requesting_conversation(world: World) -> None:
    """T1 边界：待复核是别会话发起的 → 本会话的消息不被认领，不产生关联行。"""
    item = world.seed_rejudged_item()
    other = world.client.post("/api/conversations", json={"user": fx.OWNER}).json()
    posted = world.client.post(
        f"/api/conversations/{other['conversation_id']}/messages",
        json={"user": fx.OWNER, "content": "别会话的普通消息", "skill_mode": "hybrid"},
    )
    assert posted.status_code == 202, posted.text
    world.wait_terminal(posted.json()["run_id"])
    store = EvolutionStore(world.user_root / "research_evolution", fx.OWNER)
    assert store.list_run_links(item_id=item["id"]) == [], "别会话的 run 不许被绑到本项"
    time.sleep(0.3)  # 观察器若误折回，下一行会抓到
    assert world.current_item(item["id"])["status"] == "rejudgment_requested"


def test_t2_late_terminal_of_old_request_does_not_fold_new_request(world: World) -> None:
    """T2：请求 A 的 run 迟到终态，只留旧请求审计，不迁移重新发起的请求 B 的状态。"""
    from intelligence.services.research_evolution.run_observer import ObservingRunStore

    item = world.seed_rejudged_item()
    observer = ObservingRunStore(
        user_id=fx.OWNER,
        evolution_root=world.user_root / "research_evolution",
        maintenance_folder=lambda run_id: world.service.fold_run_terminal(ctx=OwnerContext.for_owner(fx.OWNER), run_id=run_id),
    )
    old_run = observer.create_run(question="第一轮复核", task_type="research", session_id=world.conversation_id)
    world.act(idempotency_key="k-t2-reg", run_id=old_run.run_id, **world.link_args(item["id"])).raise_for_status()
    cancel_args = world.link_args(item["id"])
    cancel_args["action"] = "cancel_rejudge"
    world.act(idempotency_key="k-t2-cancel", **cancel_args).raise_for_status()
    world.clock.advance(seconds=1)
    world.rejudge(world.current_item(item["id"]), key="k-t2-second")
    before = world.current_item(item["id"])

    observer.finish_run(old_run.run_id, "failed", error="第一轮的迟到失败")
    after = world.current_item(item["id"])
    assert after["status"] == "rejudgment_requested", "旧请求的 run 不许折回新请求"
    assert after["management_revision"] == before["management_revision"]
    last_failure = after["management"]["rejudgment"].get("last_failure") or {}
    assert last_failure.get("kind") == "rejudgment_cancelled", "last_failure 仍属旧请求审计，不被迟到失败覆写"


def test_t3_first_turn_select_task_sources_reach_message(world: World) -> None:
    """T3：首轮 select_task（无起源 run）发纯文本消息，服务端把台账里的 continuation 水合落盘。"""
    world.track_judgment().raise_for_status()
    task_id = world.view()["priority"]["selected"][0]["task_id"]
    selected = world.act(action="select_task", idempotency_key="k-t3-select", task_id=task_id)
    assert selected.status_code == 200, selected.text
    continuation = selected.json()["continuation"]
    assert "run_id" not in continuation, "首轮没有已完成轮次，不伪造起源 run"
    assert continuation["click_payload"]["source_refs"]

    # 与 App 的真实分支一致：没有 run_id 的 continuation 不上消息体，只发 full_prompt。
    posted = world.client.post(
        f"/api/conversations/{world.conversation_id}/messages",
        json={"user": fx.OWNER, "content": continuation["full_prompt"], "skill_mode": "hybrid"},
    )
    assert posted.status_code == 202, posted.text
    world.wait_terminal(posted.json()["run_id"])
    message = next(
        m for m in ConversationStore(user_id=fx.OWNER).load_messages(world.conversation_id)
        if m.run_id == posted.json()["run_id"] and m.role == "user"
    )
    assert message.continuation, "首轮任务启动上下文必须随消息持久化"
    assert message.continuation.get("click_payload") == continuation["click_payload"]

    # 反向合同：内容对不上任何已记录选择的full_prompt → 普通消息，不硬塞上下文。
    plain = world.client.post(
        f"/api/conversations/{world.conversation_id}/messages",
        json={"user": fx.OWNER, "content": "随手问一句别的", "skill_mode": "hybrid"},
    )
    assert plain.status_code == 202, plain.text
    world.wait_terminal(plain.json()["run_id"])
    plain_message = next(
        m for m in ConversationStore(user_id=fx.OWNER).load_messages(world.conversation_id)
        if m.run_id == plain.json()["run_id"] and m.role == "user"
    )
    assert plain_message.continuation is None


def test_t4_summary_without_id_follows_generated_at_not_lexical_hash(world: World) -> None:
    """T4：无 id 读总结取 generated_at 最新一份；内容哈希的字典序不是版本顺序。"""
    store = EvolutionStore(world.user_root / "research_evolution", fx.OWNER)
    store.publish_immutable(SUMMARIES_DIR, "sum-ffff", {"summary_id": "sum-ffff", "generated_at": "2026-09-14T01:00:00Z", "supersedes": None})
    store.publish_immutable(SUMMARIES_DIR, "sum-0000", {"summary_id": "sum-0000", "generated_at": "2026-09-14T02:00:00Z", "supersedes": "sum-ffff"})
    response = world.act(action="read_receipt", idempotency_key="k-t4-latest", kind="pilot_summary")
    assert response.status_code == 200, response.text
    assert response.json()["receipt"]["summary_id"] == "sum-0000", "字典序最大 ≠ 最新；按 generated_at 取"


def test_t4_multiple_summary_chains_require_explicit_id(world: World) -> None:
    """T4 边界：多条版本链（不同 protocol_hash）在册 → 不猜，要求显式 summary_id。"""
    store = EvolutionStore(world.user_root / "research_evolution", fx.OWNER)
    store.publish_immutable(SUMMARIES_DIR, "sum-a", {"summary_id": "sum-a", "generated_at": "2026-09-14T01:00:00Z", "protocol_hash": "ph-a"})
    store.publish_immutable(SUMMARIES_DIR, "sum-b", {"summary_id": "sum-b", "generated_at": "2026-09-14T02:00:00Z", "protocol_hash": "ph-b"})
    ambiguous = world.act(action="read_receipt", idempotency_key="k-t4-ambig", kind="pilot_summary")
    assert ambiguous.status_code == 400, ambiguous.text
    by_id = world.act(action="read_receipt", idempotency_key="k-t4-by-id", kind="pilot_summary", summary_id="sum-a")
    assert by_id.status_code == 200 and by_id.json()["receipt"]["summary_id"] == "sum-a", by_id.text


def test_t5_failed_lockfile_open_releases_process_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """T5：锁文件 os.open 抛错时，已取得的进程锁必须释放——否则这个 owner 的有界事务永久超时。"""
    import os

    from intelligence.services.research_evolution.store import LOCK_FILE, StoreLockTimeout

    store = EvolutionStore(tmp_path / "evolution", "default")
    real_open = os.open

    def fail_lock_open(path: object, *args: object, **kwargs: object) -> int:
        if str(path).endswith(LOCK_FILE):
            raise PermissionError("injected transient lockfile open failure")
        return real_open(path, *args, **kwargs)  # type: ignore[arg-type]

    with monkeypatch.context() as patch:
        patch.setattr(os, "open", fail_lock_open)
        with pytest.raises(PermissionError):
            with store.try_transaction(timeout=0.02):
                pass
    try:
        with store.try_transaction(timeout=0.02):
            pass
    except StoreLockTimeout:
        pytest.fail("os.open 失败发生在取得进程锁之后；那把锁没被释放")


# --------------------------------------------------------------------------- #
# 第四轮 QC（re06-957e83f4）U1–U4：请求身份贯穿消息接受、成果选择与终态重放。
# 探针本体在 docs/verification/re06-957e83f4/test_review_round4.py；这里是仓内回归。
# --------------------------------------------------------------------------- #
def test_u1_plain_message_does_not_claim_pending_maintenance(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    """U1：内容不携带请求身份的普通消息不许被认领——零 run_links、零迁移。"""

    def fail_turn(**kwargs: object) -> None:
        kwargs["run_store"].finish_run(kwargs["run_id"], "failed", error="model unavailable")  # type: ignore[attr-defined]

    monkeypatch.setattr(app_module, "_run_conversation_turn", fail_turn)
    item = world.seed_rejudged_item()
    posted = world.client.post(
        f"/api/conversations/{world.conversation_id}/messages",
        json={"user": fx.OWNER, "content": "先不处理制冷剂复核。请解释市盈率是什么。", "skill_mode": "hybrid"},
    )
    assert posted.status_code == 202, posted.text
    world.wait_terminal(posted.json()["run_id"])
    store = EvolutionStore(world.user_root / "research_evolution", fx.OWNER)
    assert store.list_run_links(item_id=item["id"]) == [], "普通消息不许产生关联行"
    time.sleep(0.3)  # 任何异步折回若发生，下一行会抓到
    after = world.current_item(item["id"])
    assert after["status"] == "rejudgment_requested"
    assert after["management_revision"] == item["management_revision"]


def test_u2_two_pending_items_coordinate_binds_exact_item(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    """U2/V2：多条待复核时，请求实例坐标把 run 精确登记到被点名那一条；文案不再是身份
    （用户改写过的文案照绑不误；跨代逐字相同的文案见 V2 测试，不绑）。"""

    def fail_turn(**kwargs: object) -> None:
        kwargs["run_store"].finish_run(kwargs["run_id"], "failed", error="model unavailable")  # type: ignore[attr-defined]

    monkeypatch.setattr(app_module, "_run_conversation_turn", fail_turn)
    world.track_judgment(conditions=CONDITION_DOWNGRADE).raise_for_status()
    open_items = [i for i in world.view()["maintenance"]["items"] if i["status"] == "open"]
    assert len(open_items) == 2, f"夹具应给两条 open 项：{[(i['change_type'], i['status']) for i in world.view()['maintenance']['items']]}"
    first = world.rejudge(open_items[0], key="k-u2-first")
    second_item = world.current_item(open_items[1]["id"])
    world.rejudge(second_item, key="k-u2-second")
    second = world.current_item(second_item["id"])
    run_id = _launch_message(world, second, content="这条我自己复述了一遍，开跑")
    world.wait_terminal(run_id)

    # 接受侧按请求实例坐标精确绑定到第二项（带第二项当前代际）。
    store = EvolutionStore(world.user_root / "research_evolution", fx.OWNER)
    links = [r for r in store.list_run_links() if str(r.get("run_id")) == run_id]
    assert len(links) == 1 and links[0]["item_id"] == second["id"], links

    # 观察器终态收尾折回第二项；迟到的显式 link_run 重放；第一项不动。
    world.service.fold_run_terminal(ctx=OwnerContext.for_owner(fx.OWNER), run_id=run_id)
    assert world.current_item(second["id"])["status"] == "open"
    response = world.act(idempotency_key=f"link_run:{second['id']}:{run_id}", run_id=run_id, **world.link_args(second["id"]))
    assert response.status_code == 200, response.text
    assert response.json()["replayed"] is True
    assert world.current_item(first["item_id"])["status"] == "rejudgment_requested"
    assert world.current_item(second["id"])["status"] == "open"


def test_u3_cross_conversation_terminal_replay_is_rejected(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    """U3：终态重放不免授权——同主别的会话拿同一 (item, run) 来查，必须被拒且不迁移。"""

    def fail_turn(**kwargs: object) -> None:
        kwargs["run_store"].finish_run(kwargs["run_id"], "failed", error="model unavailable")  # type: ignore[attr-defined]

    monkeypatch.setattr(app_module, "_run_conversation_turn", fail_turn)
    item = world.seed_rejudged_item()
    run_id = _launch_message(world, item)
    world.wait_terminal(run_id)
    folded = world.wait_item_status(item["id"], "open")

    other = world.client.post("/api/conversations", json={"user": fx.OWNER, "title": "同主别的会话"}).json()
    response = world.client.post(
        f"/api/conversations/{other['conversation_id']}/research-evolution/actions",
        json={
            "user": fx.OWNER,
            "action": "link_run",
            "idempotency_key": "k-u3-cross",
            "item_id": item["id"],
            "run_id": run_id,
            "expected_item_version": item["item_version"],
            "expected_management_revision": item["management_revision"],
        },
    )
    assert response.status_code in {400, 404, 409}, f"跨会话终态重放必须拒：{response.status_code} {response.text}"
    after = world.current_item(item["id"])
    assert after["status"] == "open"
    assert after["management_revision"] == folded["management_revision"]


def test_u4_late_judgment_of_old_attempt_does_not_close_new_request(world: World) -> None:
    """U4：多代际下「同会话+时间较新」不能证明判断属于本轮——不得自动关闭，保持待复核。"""
    from intelligence.services import judgments as judgments_svc
    from intelligence.services.research_evolution.run_observer import ObservingRunStore

    observer = ObservingRunStore(
        user_id=fx.OWNER,
        evolution_root=world.user_root / "research_evolution",
        maintenance_folder=lambda run_id: world.service.fold_run_terminal(ctx=OwnerContext.for_owner(fx.OWNER), run_id=run_id),
    )
    first = world.seed_rejudged_item()
    run_a = observer.create_run(question="第一次尝试", task_type="research", session_id=world.conversation_id)
    world.act(idempotency_key="k-u4-reg-a", run_id=run_a.run_id, **world.link_args(first["id"])).raise_for_status()
    cancel_args = world.link_args(first["id"])
    cancel_args["action"] = "cancel_rejudge"
    world.act(idempotency_key="k-u4-cancel", **cancel_args).raise_for_status()
    world.clock.advance(seconds=1)
    world.rejudge(world.current_item(first["id"]), key="k-u4-second")
    run_b = observer.create_run(question="第二次尝试", task_type="research", session_id=world.conversation_id)
    world.act(idempotency_key="k-u4-reg-b", run_id=run_b.run_id, **world.link_args(first["id"])).raise_for_status()
    world.clock.advance(seconds=1)
    judgments_svc.record_judgment(
        world.user_root / "judgments.jsonl",
        memo="第一次尝试迟到的成果判断",
        themes=["制冷剂"],
        session_id=world.conversation_id,
        ts=world.clock().isoformat(),
    )

    observer.finish_run(run_a.run_id, rs.STATUS_COMPLETED)
    assert world.current_item(first["id"])["status"] == "rejudgment_requested", "旧请求的迟到终态不许折回新请求（T2）"

    before = world.current_item(first["id"])
    observer.finish_run(run_b.run_id, rs.STATUS_COMPLETED)
    time.sleep(0.3)  # 若误折回，下一行会抓到
    after = world.current_item(first["id"])
    assert after["status"] == "rejudgment_requested", "无法证明属于本轮的判断不许自动关闭本轮"
    assert after["management_revision"] == before["management_revision"]


def test_u2_degraded_accept_binding_recovers_via_explicit_link_run(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    """补偿登记正向（QC T1/V1）：接受侧绑定降级（锁超时等被吞掉）时，客户端显式 link_run
    凭源消息上的请求实例坐标补登当前代并折回——坐标是补偿唯一认可的启动身份，
    「run 有同会话消息」单独不算数（V1 负向见 test_v1）。"""
    monkeypatch.setattr(ResearchEvolutionService, "bind_pending_rejudge_run", lambda self, **kwargs: None)

    def fail_turn(**kwargs: object) -> None:
        kwargs["run_store"].finish_run(kwargs["run_id"], "failed", error="model unavailable")  # type: ignore[attr-defined]

    monkeypatch.setattr(app_module, "_run_conversation_turn", fail_turn)
    item = world.seed_rejudged_item()
    run_id = _launch_message(world, item, content="动手吧，按上面说的方向再查一遍")
    world.wait_terminal(run_id)

    # 接受侧绑定被降级吞掉 → 无关联；项保持待复核。
    store = EvolutionStore(world.user_root / "research_evolution", fx.OWNER)
    assert store.list_run_links(item_id=item["id"]) == []
    held = world.current_item(item["id"])
    assert held["status"] == "rejudgment_requested"

    # 显式 link_run 补偿登记：源消息携带该项当前代坐标 → 补登并折回。
    response = world.act(idempotency_key=f"link_run:{item['id']}:{run_id}", run_id=run_id, **world.link_args(item["id"]))
    assert response.status_code == 200, f"降级后显式点名的合法复核不许卡死：{response.text}"
    closed = world.wait_item_status(item["id"], "open")
    assert closed["management_revision"] == held["management_revision"] + 1
    assert closed["management"]["rejudgment"]["last_failure"]["kind"] == "rejudgment_failed"
    links = [r for r in store.list_run_links(item_id=item["id"]) if str(r.get("run_id")) == run_id]
    assert len(links) == 1
    assert links[0]["request_event_id"] == closed["management"]["rejudgment"]["request_event_id"]

def test_v1_old_ordinary_message_cannot_be_compensated_into_new_request(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    """V1：先于请求存在的普通聊天 run，显式 link_run 也不能补登成新请求的执行——
    「run 有同会话消息」单独不再充当因果证明，补偿只认源消息上的当前代坐标。"""

    def fail_turn(**kwargs: object) -> None:
        kwargs["run_store"].finish_run(kwargs["run_id"], "failed", error="model unavailable")  # type: ignore[attr-defined]

    monkeypatch.setattr(app_module, "_run_conversation_turn", fail_turn)
    posted = world.client.post(
        f"/api/conversations/{world.conversation_id}/messages",
        json={"user": fx.OWNER, "content": "请解释市盈率是什么。", "skill_mode": "hybrid"},
    )
    assert posted.status_code == 202, posted.text
    old_run = posted.json()["run_id"]
    world.wait_terminal(old_run)

    item = world.seed_rejudged_item()  # 复核请求在聊天 run 终态之后才出现
    response = world.act(idempotency_key="k-v1-old-chat", run_id=old_run, **world.link_args(item["id"]))
    assert response.status_code in {400, 404, 409}, f"旧聊天不许补登成新请求的执行：{response.status_code} {response.text}"
    after = world.current_item(item["id"])
    assert after["status"] == "rejudgment_requested" and after["management_revision"] == item["management_revision"]
    store = EvolutionStore(world.user_root / "research_evolution", fx.OWNER)
    assert not [r for r in store.list_run_links() if str(r.get("run_id")) == old_run]


def test_v2_cancelled_generation_prompt_cannot_claim_replacement(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    """V2：跨代 full_prompt 逐字相同也不绑——启动话语不再是任何身份；A 的迟到文案不产生关联、不迁移 B。"""
    world.track_judgment().raise_for_status()
    item = world.open_item()
    first = world.rejudge(item, key="k-v2-request-a")
    old_prompt = str(first["continuation"]["full_prompt"])
    assert old_prompt
    cancel_args = world.link_args(item["id"])
    cancel_args["action"] = "cancel_rejudge"
    world.act(idempotency_key="k-v2-cancel-a", **cancel_args).raise_for_status()
    world.clock.advance(seconds=1)
    world.rejudge(world.current_item(item["id"]), key="k-v2-request-b")
    before = world.current_item(item["id"])
    assert before["status"] == "rejudgment_requested"

    def fail_turn(**kwargs: object) -> None:
        kwargs["run_store"].finish_run(kwargs["run_id"], "failed", error="model unavailable")  # type: ignore[attr-defined]

    monkeypatch.setattr(app_module, "_run_conversation_turn", fail_turn)
    # 陈旧标签页在 B 代发出 A 的 full_prompt 原文——不带坐标的裸文案。
    posted = world.client.post(
        f"/api/conversations/{world.conversation_id}/messages",
        json={"user": fx.OWNER, "content": old_prompt, "skill_mode": "hybrid"},
    )
    assert posted.status_code == 202, posted.text
    run_id = posted.json()["run_id"]
    world.wait_terminal(run_id)
    world.service.fold_run_terminal(ctx=OwnerContext.for_owner(fx.OWNER), run_id=run_id)

    after = world.current_item(item["id"])
    assert after["status"] == "rejudgment_requested"
    assert after["management_revision"] == before["management_revision"], "旧代文案的失败不许迁移当前代"
    store = EvolutionStore(world.user_root / "research_evolution", fx.OWNER)
    assert not [r for r in store.list_run_links() if str(r.get("run_id")) == run_id], "裸文案不产生关联（U1 合同延伸至文本渠道）"


def test_v3_first_attempt_cannot_consume_other_items_judgment(world: World) -> None:
    """V3：两条不同原判断同会话首次复核——B 没有自身成果时，不得拿 A 的新判断自动关闭。"""
    from intelligence.services import judgments as judgments_svc
    from intelligence.services.research_evolution.run_observer import ObservingRunStore

    world.track_judgment().raise_for_status()
    # 挂一条底层不同的判断 B（同一对象的两次维护不算数，必须真两条）。
    _, original_b = judgments_svc.record_judgment(
        world.user_root / "judgments.jsonl",
        memo="下游制冷剂采购利润承压，是另一条独立判断",
        themes=[fx.ENTITY],
        stocks=[],
        session_id=world.conversation_id,
        ts="2026-09-03T20:00:00+08:00",
    )
    ref_b = f"judgments.jsonl:{original_b['id']}"
    object_b = next(t["object_ref"] for t in world.view()["inputs"]["trackable_objects"] if t["object_ref"]["ref"] == ref_b)
    world.bind_at(fx.BIND_DAY, object_ref=object_b).raise_for_status()
    open_items = [i for i in world.view()["maintenance"]["items"] if i["status"] == "open"]
    item_b = next(i for i in open_items if i["object_ref"]["ref"] == ref_b)
    item_a = next(i for i in open_items if i["object_ref"]["ref"] != ref_b)
    assert item_a["object_ref"]["ref"] != item_b["object_ref"]["ref"]
    world.rejudge(item_a, key="k-v3-rejudge-a")
    world.rejudge(world.current_item(item_b["id"]), key="k-v3-rejudge-b")

    observer = ObservingRunStore(
        user_id=fx.OWNER,
        evolution_root=world.user_root / "research_evolution",
        maintenance_folder=lambda run_id: world.service.fold_run_terminal(ctx=OwnerContext.for_owner(fx.OWNER), run_id=run_id),
    )
    run_a = observer.create_run(question="重新复核 A", task_type="research", session_id=world.conversation_id)
    world.act(idempotency_key="k-v3-reg-a", run_id=run_a.run_id, **world.link_args(item_a["id"])).raise_for_status()
    run_b = observer.create_run(question="重新复核 B", task_type="research", session_id=world.conversation_id)
    world.act(idempotency_key="k-v3-reg-b", run_id=run_b.run_id, **world.link_args(item_b["id"])).raise_for_status()
    world.clock.advance(seconds=1)
    _, judgment_a = judgments_svc.record_judgment(
        world.user_root / "judgments.jsonl",
        memo="对 A 的新判断",
        themes=["萤石"],
        stocks=[],
        session_id=world.conversation_id,
        ts=world.clock().isoformat(),
    )
    assert judgment_a["session_id"] == world.conversation_id

    observer.finish_run(run_a.run_id, rs.STATUS_COMPLETED)
    time.sleep(0.3)
    observer.finish_run(run_b.run_id, rs.STATUS_COMPLETED)
    time.sleep(0.3)

    item_a_after = world.current_item(item_a["id"])
    assert item_a_after["status"] == "rejudgment_requested" or (
        item_a_after["status"] == "closed"
        and ((item_a_after.get("management") or {}).get("rejudgment") or {}).get("new_judgment_ref") == f"judgments.jsonl:{judgment_a['id']}"
    ), "A 要么持守（多待复核下不自动认领），要么挂上自己的成果判断"
    item_b_after = world.current_item(item_b["id"])
    assert item_b_after["status"] == "rejudgment_requested", "B 没有自身成果时不得拿别的判断自动关闭"


def test_v4_running_registration_obeys_stale_generation_gate(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    """V4：运行中登记也过旧代闸——A 的 run 已登记，取消 A 发起 B 后不得转挂 B；A 的迟到失败只留 A 的审计。"""
    gate = threading.Event()

    def delayed_failure(**kwargs: object) -> None:
        gate.wait(timeout=10)
        kwargs["run_store"].finish_run(kwargs["run_id"], "failed", error="model unavailable")  # type: ignore[attr-defined]

    monkeypatch.setattr(app_module, "_run_conversation_turn", delayed_failure)
    world.track_judgment().raise_for_status()
    item = world.open_item()
    world.rejudge(item, key="k-v4-request-a")
    # 请求 A 的启动消息（运行中；裸消息接受侧不登记——运行中登记走显式 link_run，R7 合同）。
    posted = world.client.post(
        f"/api/conversations/{world.conversation_id}/messages",
        json={"user": fx.OWNER, "content": "继续核查", "skill_mode": "hybrid"},
    )
    assert posted.status_code == 202, posted.text
    run_id = posted.json()["run_id"]
    world.act(idempotency_key="link_run:request-a", run_id=run_id, **world.link_args(item["id"])).raise_for_status()

    cancel_args = world.link_args(item["id"])
    cancel_args["action"] = "cancel_rejudge"
    world.act(idempotency_key="k-v4-cancel-a", **cancel_args).raise_for_status()
    world.clock.advance(seconds=1)
    world.rejudge(world.current_item(item["id"]), key="k-v4-request-b")
    second = world.current_item(item["id"])
    response = world.act(idempotency_key="link_run:request-b", run_id=run_id, **world.link_args(second["id"]))
    assert response.status_code in {400, 404, 409}, f"已登记在 A 的运行中 run 不得转挂 B：{response.status_code} {response.text}"

    gate.set()
    world.wait_terminal(run_id)
    world.service.fold_run_terminal(ctx=OwnerContext.for_owner(fx.OWNER), run_id=run_id)
    current = world.current_item(item["id"])
    assert current["status"] == "rejudgment_requested" or current["management_revision"] == second["management_revision"]
    assert current["management_revision"] == second["management_revision"], "A 的迟到失败不许迁移 B"

def _two_items(world: World) -> tuple[dict, dict]:
    """两条底层不同的 open 维护项（与 QC 第六轮探针同形）。"""
    from intelligence.services import judgments as judgments_svc

    world.track_judgment().raise_for_status()
    _, original_b = judgments_svc.record_judgment(
        world.user_root / "judgments.jsonl",
        memo="另一条独立判断 B：下游成本承压",
        themes=[fx.ENTITY],
        stocks=[],
        session_id=world.conversation_id,
        ts="2026-09-03T20:00:00+08:00",
    )
    ref_b = f"judgments.jsonl:{original_b['id']}"
    object_b = next(t["object_ref"] for t in world.view()["inputs"]["trackable_objects"] if t["object_ref"]["ref"] == ref_b)
    world.bind_at(fx.BIND_DAY, object_ref=object_b).raise_for_status()
    items = [i for i in world.view()["maintenance"]["items"] if i["status"] == "open"]
    return (
        next(i for i in items if i["object_ref"]["ref"] != ref_b),
        next(i for i in items if i["object_ref"]["ref"] == ref_b),
    )


def test_w1_running_run_cannot_be_claimed_by_another_item(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    """W1：run 已有核验过的归属（接受侧坐标登记给 A），运行中显式 link_run 到 B 必须被拒。"""
    gate = threading.Event()

    def delayed_failure(**kwargs: object) -> None:
        gate.wait(timeout=10)
        kwargs["run_store"].finish_run(kwargs["run_id"], "failed", error="model unavailable")  # type: ignore[attr-defined]

    a, b = _two_items(world)
    world.rejudge(a, key="k-w1-request-a")
    world.rejudge(world.current_item(b["id"]), key="k-w1-request-b")
    monkeypatch.setattr(app_module, "_run_conversation_turn", delayed_failure)
    a_now = world.current_item(a["id"])
    run_a = _launch_message(world, a_now)
    store = EvolutionStore(world.user_root / "research_evolution", fx.OWNER)
    assert len(store.list_run_links(item_id=a["id"])) == 1

    before_b = world.current_item(b["id"])
    response = world.act(idempotency_key="k-w1-claim-a-as-b", run_id=run_a, **world.link_args(b["id"]))
    assert response.status_code in {400, 404, 409}, f"已有归属的 run 不许跨项转挂：{response.status_code} {response.text}"
    gate.set()
    world.wait_terminal(run_a)
    world.service.fold_run_terminal(ctx=OwnerContext.for_owner(fx.OWNER), run_id=run_a)
    after_b = world.current_item(b["id"])
    assert after_b["management_revision"] == before_b["management_revision"]
    assert not store.list_run_links(item_id=b["id"])


def test_w2_rejected_stale_message_cannot_gain_current_identity_while_running(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    """W2：接受侧已正确拒登的陈旧坐标消息，不能趁 run 运行中经显式 link 洗成当前代身份。"""
    gate = threading.Event()

    def delayed_failure(**kwargs: object) -> None:
        gate.wait(timeout=10)
        kwargs["run_store"].finish_run(kwargs["run_id"], "failed", error="model unavailable")  # type: ignore[attr-defined]

    world.track_judgment().raise_for_status()
    item = world.open_item()
    first = world.rejudge(item, key="k-w2-request-a")
    stale_launch = {
        "item_id": first["continuation"]["maintenance_item_id"],
        "request_event_id": first["continuation"]["request_event_id"],
    }
    cancel_args = world.link_args(item["id"])
    cancel_args["action"] = "cancel_rejudge"
    world.act(idempotency_key="k-w2-cancel-a", **cancel_args).raise_for_status()
    world.clock.advance(seconds=1)
    world.rejudge(world.current_item(item["id"]), key="k-w2-request-b")
    before = world.current_item(item["id"])

    monkeypatch.setattr(app_module, "_run_conversation_turn", delayed_failure)
    posted = world.client.post(
        f"/api/conversations/{world.conversation_id}/messages",
        json={"user": fx.OWNER, "content": "继续核查", "skill_mode": "hybrid", "maintenance_launch": stale_launch},
    )
    assert posted.status_code == 202, posted.text
    run_a = posted.json()["run_id"]
    store = EvolutionStore(world.user_root / "research_evolution", fx.OWNER)
    assert not store.list_run_links(item_id=item["id"]), "接受侧必须拒登陈旧坐标"

    response = world.act(idempotency_key="k-w2-stale-as-b", run_id=run_a, **world.link_args(before["id"]))
    assert response.status_code in {400, 404, 409}, f"被拒的陈旧坐标不许经运行中登记洗白：{response.status_code} {response.text}"
    gate.set()
    world.wait_terminal(run_a)
    world.service.fold_run_terminal(ctx=OwnerContext.for_owner(fx.OWNER), run_id=run_a)
    after = world.current_item(item["id"])
    assert after["management_revision"] == before["management_revision"]
    assert not store.list_run_links(item_id=item["id"])


def test_w3_cancelled_peers_late_judgment_cannot_close_sole_remaining(world: World) -> None:
    """W3：取消 A 后其迟到成果不能关闭唯一剩余的 B——「当前唯一 pending」不是因果唯一。"""
    from intelligence.services import judgments as judgments_svc
    from intelligence.services.research_evolution.run_observer import ObservingRunStore

    a, b = _two_items(world)
    world.rejudge(a, key="k-w3-request-a")
    world.rejudge(world.current_item(b["id"]), key="k-w3-request-b")
    observer = ObservingRunStore(
        user_id=fx.OWNER,
        evolution_root=world.user_root / "research_evolution",
        maintenance_folder=lambda run_id: world.service.fold_run_terminal(ctx=OwnerContext.for_owner(fx.OWNER), run_id=run_id),
    )
    run_a = observer.create_run(question="复核 A", task_type="research", session_id=world.conversation_id)
    world.act(idempotency_key="k-w3-reg-a", run_id=run_a.run_id, **world.link_args(a["id"])).raise_for_status()
    run_b = observer.create_run(question="复核 B", task_type="research", session_id=world.conversation_id)
    world.act(idempotency_key="k-w3-reg-b", run_id=run_b.run_id, **world.link_args(b["id"])).raise_for_status()
    cancel_args = world.link_args(a["id"])
    cancel_args["action"] = "cancel_rejudge"
    world.act(idempotency_key="k-w3-cancel-a", **cancel_args).raise_for_status()
    before = world.current_item(b["id"])
    world.clock.advance(seconds=1)
    judgments_svc.record_judgment(
        world.user_root / "judgments.jsonl",
        memo="仅 A 的迟到成果，B 没有成果",
        themes=[fx.ENTITY],
        stocks=[],
        session_id=world.conversation_id,
        ts=world.clock().isoformat(),
    )
    observer.finish_run(run_a.run_id, rs.STATUS_COMPLETED)
    observer.finish_run(run_b.run_id, rs.STATUS_COMPLETED)
    time.sleep(0.3)
    after = world.current_item(b["id"])
    assert after["status"] == "rejudgment_requested", "已取消同伴的迟到判断不许关闭唯一剩余项"
    assert after["management_revision"] == before["management_revision"]

def test_x2_accept_registration_must_respect_existing_run_owner(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    """X2：run 已创建、源消息尚未落盘的窗口期被显式登记给 B（R7 允许）——接受侧随后
    不得追加矛盾的 A 归属；错误的 B 链接不得驱动 B 的终态状态。"""
    a, b = _two_items(world)
    request_a = world.rejudge(a, key="k-x2-request-a")
    world.rejudge(world.current_item(b["id"]), key="k-x2-request-b")
    before_b = world.current_item(b["id"])
    at_message = threading.Event()
    continue_message = threading.Event()
    responses: list = []
    original_append = ConversationStore.append_message

    def delayed_append(self: ConversationStore, conversation_id: str, role: str, content: str, **kwargs: object) -> object:
        if role == "user" and kwargs.get("maintenance_launch"):
            at_message.set()
            assert continue_message.wait(10)
        return original_append(self, conversation_id, role, content, **kwargs)

    def failure(**kwargs: object) -> None:
        kwargs["run_store"].finish_run(kwargs["run_id"], "failed", error="deterministic failure")  # type: ignore[attr-defined]

    monkeypatch.setattr(ConversationStore, "append_message", delayed_append)
    monkeypatch.setattr(app_module, "_run_conversation_turn", failure)
    cont = request_a["continuation"]
    body = {
        "user": fx.OWNER,
        "content": cont["full_prompt"],
        "skill_mode": "hybrid",
        "maintenance_launch": {"item_id": cont["maintenance_item_id"], "request_event_id": cont["request_event_id"]},
    }
    thread = threading.Thread(
        target=lambda: responses.append(world.client.post(f"/api/conversations/{world.conversation_id}/messages", json=body))
    )
    thread.start()
    try:
        assert at_message.wait(10)
        observed = world.client.get("/api/runs", params={"user": fx.OWNER})
        assert observed.status_code == 200, observed.text
        visible = [r for r in observed.json() if r["session_id"] == world.conversation_id]
        assert len(visible) == 1
        run_id = visible[0]["run_id"]
        claimed = world.act(idempotency_key="k-x2-claim-as-b", run_id=run_id, **world.link_args(b["id"]))
        assert claimed.status_code == 200, claimed.text  # 窗口期裸 run 登记是 R7 合同的合法延伸
    finally:
        continue_message.set()
        thread.join(15)
    assert not thread.is_alive() and responses[0].status_code == 202
    world.wait_terminal(run_id)
    world.service.fold_run_terminal(ctx=OwnerContext.for_owner(fx.OWNER), run_id=run_id)
    store = EvolutionStore(world.user_root / "research_evolution", fx.OWNER)
    links = [r for r in store.list_run_links() if r["run_id"] == run_id]
    assert len(links) <= 1, "接受侧不许追加矛盾的第二归属"
    late = world.act(idempotency_key="k-x2-fold-as-b", run_id=run_id, **world.link_args(b["id"]))
    assert late.status_code in {400, 404, 409}, f"矛盾来源的登记不得驱动终态：{late.status_code} {late.text}"
    after_b = world.current_item(b["id"])
    assert after_b["management_revision"] == before_b["management_revision"], "B 不许被错误折回"
