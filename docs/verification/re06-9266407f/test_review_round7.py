"""RE06 round7: real API/domain/writer; synthetic users, deterministic executor."""
from __future__ import annotations

import threading

import pytest

import intelligence.tests.research_evolution_fixtures as fx
from intelligence.api import app as app_module
from intelligence.services import judgments
from intelligence.services.conversation_store import ConversationStore
from intelligence.services.research_evolution.access import OwnerContext
from intelligence.services.research_evolution.store import EvolutionStore
from intelligence.tests.test_research_evolution_rework import World


@pytest.fixture
def world(tmp_path, monkeypatch):
    fx.install_env(monkeypatch, tmp_path)
    return World(tmp_path / "users", monkeypatch)


def post_message(world, content, continuation=None):
    body = {"user": fx.OWNER, "content": content, "skill_mode": "hybrid"}
    if continuation:
        body["maintenance_launch"] = {
            "item_id": continuation["maintenance_item_id"],
            "request_event_id": continuation["request_event_id"],
        }
    return world.client.post(f"/api/conversations/{world.conversation_id}/messages", json=body)


def two_items(world):
    world.track_judgment().raise_for_status()
    _, old_b = judgments.record_judgment(
        world.user_root / "judgments.jsonl", memo="独立原判断 B",
        themes=[fx.ENTITY], session_id=world.conversation_id, ts="2026-09-03T20:00:00+08:00",
    )
    ref_b = f"judgments.jsonl:{old_b['id']}"
    object_b = next(t["object_ref"] for t in world.view()["inputs"]["trackable_objects"] if t["object_ref"]["ref"] == ref_b)
    world.bind_at(fx.BIND_DAY, object_ref=object_b).raise_for_status()
    items = [i for i in world.view()["maintenance"]["items"] if i["status"] == "open"]
    return (next(i for i in items if i["object_ref"]["ref"] != ref_b),
            next(i for i in items if i["object_ref"]["ref"] == ref_b))


def test_x1_sole_rejudge_cannot_autopick_ordinary_chat_judgment(world, monkeypatch):
    world.track_judgment().raise_for_status()
    item = world.open_item()
    request = world.rejudge(item)
    store = EvolutionStore(world.user_root / "research_evolution", fx.OWNER)
    unrelated = []

    def ordinary_turn(**kwargs):
        _, row = judgments.record_judgment(
            world.user_root / "judgments.jsonl", memo="普通聊天产生的独立观点：银行息差，不是制冷剂复核成果",
            themes=["银行"], session_id=world.conversation_id, ts=world.clock().isoformat(),
        )
        unrelated.append(row)
        kwargs["run_store"].finish_run(kwargs["run_id"], "completed")

    world.clock.advance(seconds=1)
    monkeypatch.setattr(app_module, "_run_conversation_turn", ordinary_turn)
    ordinary = post_message(world, "先放下制冷剂复核，记录另一个银行观点。")
    assert ordinary.status_code == 202, ordinary.text
    ordinary_id = ordinary.json()["run_id"]
    world.wait_terminal(ordinary_id)
    assert unrelated and not store.list_run_links()
    assert len([r for r in store.list_action_records() if r["action"] == "rejudge"]) == 1
    before = world.current_item(item["id"])

    def no_judgment_turn(**kwargs):
        kwargs["run_store"].finish_run(kwargs["run_id"], "completed")

    monkeypatch.setattr(app_module, "_run_conversation_turn", no_judgment_turn)
    maintenance = post_message(world, request["continuation"]["full_prompt"], request["continuation"])
    assert maintenance.status_code == 202, maintenance.text
    maintenance_id = maintenance.json()["run_id"]
    world.wait_terminal(maintenance_id)
    # Deterministically wait for the observer transaction, or execute its idempotent recovery.
    world.service.fold_run_terminal(ctx=OwnerContext.for_owner(fx.OWNER), run_id=maintenance_id)
    after = world.current_item(item["id"])
    print("X1", "ordinary_run", ordinary_id, "ordinary_judgment", unrelated[0]["id"],
          "maintenance_run", maintenance_id, "before", before["status"], before["management_revision"],
          "after", after["status"], after["management_revision"], after["management"])
    assert after["status"] == "rejudgment_requested", "one rejudge record is not proof that all same-session judgments belong to it"
    assert after["management_revision"] == before["management_revision"]


def test_x2_accept_registration_must_respect_existing_run_owner(world, monkeypatch):
    a, b = two_items(world)
    request_a = world.rejudge(a, key="request-a")
    world.rejudge(b, key="request-b")
    before_b = world.current_item(b["id"])
    at_message = threading.Event()
    continue_message = threading.Event()
    responses = []
    original_append = ConversationStore.append_message

    def delayed_append(self, conversation_id, role, content, **kwargs):
        if role == "user" and kwargs.get("maintenance_launch"):
            at_message.set()
            assert continue_message.wait(10)
        return original_append(self, conversation_id, role, content, **kwargs)

    def failure(**kwargs):
        kwargs["run_store"].finish_run(kwargs["run_id"], "failed", error="deterministic failure")

    monkeypatch.setattr(ConversationStore, "append_message", delayed_append)
    monkeypatch.setattr(app_module, "_run_conversation_turn", failure)
    thread = threading.Thread(target=lambda: responses.append(post_message(world, request_a["continuation"]["full_prompt"], request_a["continuation"])))
    thread.start()
    try:
        assert at_message.wait(10)
        # Run exists and is externally readable before its source message is persisted.
        observed = world.client.get("/api/runs", params={"user": fx.OWNER})
        assert observed.status_code == 200, observed.text
        visible = [r for r in observed.json() if r["session_id"] == world.conversation_id]
        assert len(visible) == 1
        run_id = visible[0]["run_id"]
        claimed = world.act(idempotency_key="claim-as-b-before-message", run_id=run_id, **world.link_args(b["id"]))
        assert claimed.status_code == 200, claimed.text
    finally:
        continue_message.set()
        thread.join(15)
    assert not thread.is_alive() and responses[0].status_code == 202
    world.wait_terminal(run_id)
    world.service.fold_run_terminal(ctx=OwnerContext.for_owner(fx.OWNER), run_id=run_id)
    store = EvolutionStore(world.user_root / "research_evolution", fx.OWNER)
    links = [r for r in store.list_run_links() if r["run_id"] == run_id]
    # B still pending after observer chooses the last (A) link; explicit B fold now trusts B's first link.
    late = world.act(idempotency_key="fold-as-b-after-source", run_id=run_id, **world.link_args(b["id"]))
    after_b = world.current_item(b["id"])
    print("X2", "links", links, "B_fold", late.status_code, late.json(),
          "B", before_b["status"], before_b["management_revision"], "->", after_b["status"], after_b["management_revision"])
    assert len(links) <= 1, "accept-side registration must not append a contradictory second owner"
    assert after_b["management_revision"] == before_b["management_revision"]
