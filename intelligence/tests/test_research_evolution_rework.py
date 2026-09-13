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
from intelligence.tests.test_research_evolution_api import World as BaseWorld

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


def test_q2_terminal_auto_close_without_second_link(world: World) -> None:
    """放行条件 #2：注册 → 终态 → 观察器自动收尾闭合，不再需要第二次 link_run。"""
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
    # 终态 claim 与观察器收尾在同一线程，但 run 状态先可见——轮询等折回落地。
    world.wait_item_status(item["id"], "closed")
    # 终态动作恰好一条（观察器与客户端路径共用幂等键，双触发不双写）。
    rows = [json.loads(line) for line in (world.user_root / "research_evolution" / "maintenance_actions.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    linked = [r for r in rows if isinstance(r.get("event"), dict) and r["event"]["kind"] == "rejudgment_linked"]
    assert len(linked) == 1, f"rejudgment_linked 应恰好一条：{len(linked)}"

    # 客户端同键重试（响应丢失场景，载荷逐字节相同）：返回折回结果的重放，不再假装是新注册。
    retry = world.act(idempotency_key="k-q2-reg", run_id=run_id, **reg_args)
    assert retry.status_code == 200, retry.text
    assert retry.json()["replayed"] is True and retry.json()["reason_code"] == "rejudgment_linked"


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
def test_t1_run_terminal_before_second_request_still_reconciles(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    """T1：run 在浏览器第二个请求（link_run）之前到终态——消息接受侧已登记可信关联，收尾不卡死。

    真实 UI 次序是「先 POST messages 拿 run_id，再 POST link_run」，模型可以在此之前就失败。
    修复：create_message 在启动执行器前把 run 登记到本会话唯一待复核项（带 request_event_id 代际）。
    """
    def fail_turn(**kwargs: object) -> None:
        kwargs["run_store"].finish_run(kwargs["run_id"], "failed", error="model unavailable")  # type: ignore[attr-defined]

    monkeypatch.setattr(app_module, "_run_conversation_turn", fail_turn)
    item = world.seed_rejudged_item()
    posted = world.client.post(
        f"/api/conversations/{world.conversation_id}/messages",
        json={"user": fx.OWNER, "content": "继续核查", "skill_mode": "hybrid"},
    )
    assert posted.status_code == 202, posted.text
    run_id = posted.json()["run_id"]
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
