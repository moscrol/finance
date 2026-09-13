"""Independent correct-contract probes, b481804c / code 957e83f4.

Real API and real domain/store code; temporary synthetic users and deterministic
executors only. No model, production user state, or market source is accessed.
"""
from __future__ import annotations

import pytest

import intelligence.tests.research_evolution_fixtures as fx
from intelligence.api import app as app_module
from intelligence.services.research_evolution.store import EvolutionStore
from intelligence.tests.test_research_evolution_api import CONDITION_DOWNGRADE
from intelligence.tests.test_research_evolution_rework import World


@pytest.fixture
def world(tmp_path, monkeypatch):
    fx.install_env(monkeypatch, tmp_path)
    return World(tmp_path / "users", monkeypatch)


def fail_turn(**kwargs):
    kwargs["run_store"].finish_run(kwargs["run_id"], "failed", error="deterministic fast failure")


def post_message(world, content, continuation=None):
    body = {"user": fx.OWNER, "content": content, "skill_mode": "hybrid"}
    if continuation and continuation.get("run_id"):
        body["continuation"] = continuation
    response = world.client.post(f"/api/conversations/{world.conversation_id}/messages", json=body)
    assert response.status_code == 202, response.text
    return response.json()["run_id"]


def test_plain_message_does_not_claim_pending_maintenance(world, monkeypatch):
    item = world.seed_rejudged_item()
    monkeypatch.setattr(app_module, "_run_conversation_turn", fail_turn)
    run_id = post_message(world, "先不处理制冷剂复核。请解释市盈率是什么。")
    world.wait_terminal(run_id)
    links = EvolutionStore(world.user_root / "research_evolution", fx.OWNER).list_run_links(item_id=item["id"])
    after = world.current_item(item["id"])
    print("PLAIN_MESSAGE_LINKS", links, "BEFORE", item["status"], "AFTER", after["status"], after["management_revision"])
    assert not links, "A pending item in the same conversation is not evidence that an unrelated message starts its rejudge run"
    assert world.current_item(item["id"])["management_revision"] == item["management_revision"]


def test_two_pending_items_fast_terminal_can_reconcile_selected_item(world, monkeypatch):
    world.track_judgment(conditions=CONDITION_DOWNGRADE).raise_for_status()
    items = [i for i in world.view()["maintenance"]["items"] if i["status"] == "open"]
    assert len(items) >= 2, "real 01 fixture must generate two distinct maintenance items"
    world.rejudge(items[0], key="request-first-item")
    second = world.rejudge(world.current_item(items[1]["id"]), key="request-second-item")
    before = world.current_item(items[1]["id"])
    continuation = second["continuation"]
    monkeypatch.setattr(app_module, "_run_conversation_turn", fail_turn)
    run_id = post_message(world, continuation["full_prompt"], continuation)
    world.wait_terminal(run_id)
    response = world.act(
        action="link_run", idempotency_key=f"link_run:{before['id']}:{run_id}",
        item_id=before["id"], run_id=run_id,
        expected_item_version=before["item_version"],
        expected_management_revision=before["management_revision"],
    )
    print("MULTI_PENDING_FAST_TERMINAL", response.status_code, response.json())
    assert response.status_code == 200, "An explicit selected item must remain recoverable when two requests are pending"
    world.wait_item_status(before["id"], "open")


def test_terminal_global_replay_still_checks_conversation(world, monkeypatch):
    item = world.seed_rejudged_item()
    monkeypatch.setattr(app_module, "_run_conversation_turn", fail_turn)
    run_id = post_message(world, "继续核查")
    world.wait_terminal(run_id)
    world.wait_item_status(item["id"], "open")
    other = world.client.post("/api/conversations", json={"user": fx.OWNER}).json()["conversation_id"]
    response = world.client.post(
        f"/api/conversations/{other}/research-evolution/actions",
        json={"user": fx.OWNER, "action": "link_run", "idempotency_key": "cross-session-terminal-replay",
              "item_id": item["id"], "run_id": run_id,
              "expected_item_version": item["item_version"],
              "expected_management_revision": item["management_revision"]},
    )
    print("CROSS_SESSION_TERMINAL_REPLAY", response.status_code, response.json())
    assert response.status_code in {400, 404, 409}, "Terminal replay is not an exemption from the original conversation scope"


def test_old_attempt_judgment_cannot_close_new_attempt(world):
    from intelligence.services import judgments as judgments_svc
    from intelligence.services.research_evolution.access import OwnerContext
    from intelligence.services.research_evolution.run_observer import ObservingRunStore

    item = world.seed_rejudged_item()
    observer = ObservingRunStore(
        user_id=fx.OWNER, evolution_root=world.user_root / "research_evolution",
        maintenance_folder=lambda run_id: world.service.fold_run_terminal(ctx=OwnerContext.for_owner(fx.OWNER), run_id=run_id),
    )
    old = observer.create_run(question="first attempt", task_type="research", session_id=world.conversation_id)
    world.act(idempotency_key="register-A", run_id=old.run_id, **world.link_args(item["id"])).raise_for_status()
    cancel = world.link_args(item["id"])
    cancel["action"] = "cancel_rejudge"
    world.act(idempotency_key="cancel-A", **cancel).raise_for_status()
    world.clock.advance(seconds=1)
    world.rejudge(world.current_item(item["id"]), key="request-B")
    new = observer.create_run(question="second attempt", task_type="research", session_id=world.conversation_id)
    world.act(idempotency_key="register-B", run_id=new.run_id, **world.link_args(item["id"])).raise_for_status()
    before = world.current_item(item["id"])
    world.clock.advance(seconds=1)
    # A is allowed to finish after cancellation of the maintenance request.
    # Its writer produces a late judgment; B produces no judgment of its own.
    _, judgment = judgments_svc.record_judgment(
        world.user_root / "judgments.jsonl", themes=[fx.ENTITY],
        memo="第一轮请求 A 的迟到判断，不是 B 的成果",
        session_id=world.conversation_id, ts=world.clock().isoformat(),
    )
    observer.finish_run(old.run_id, "completed")
    assert world.current_item(item["id"])["management_revision"] == before["management_revision"]
    observer.finish_run(new.run_id, "completed")
    after = world.current_item(item["id"])
    print("LATE_JUDGMENT", judgment["id"], "BEFORE", before["status"], "AFTER", after["status"], after["management"])
    assert after["status"] == "rejudgment_requested", "Request B cannot close using a late result produced by cancelled request A"
    assert after["management_revision"] == before["management_revision"]
