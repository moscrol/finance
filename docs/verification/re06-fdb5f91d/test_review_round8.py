"""Round 8 review: real API and writers, synthetic users and executor."""
from __future__ import annotations

import threading

import pytest

import intelligence.tests.research_evolution_fixtures as fx
from intelligence.services.conversation_store import ConversationStore
from intelligence.services.research_evolution.access import OwnerContext
from intelligence.services.research_evolution.store import EvolutionStore
from intelligence.services.run_store import RunStore
from intelligence.tests.test_research_evolution_rework import World


@pytest.fixture
def world(tmp_path, monkeypatch):
    fx.install_env(monkeypatch, tmp_path)
    return World(tmp_path / "users", monkeypatch)


def two_items(world):
    from intelligence.services import judgments

    world.track_judgment().raise_for_status()
    _, old_b = judgments.record_judgment(
        world.user_root / "judgments.jsonl", memo="Independent original B",
        themes=[fx.ENTITY], session_id=world.conversation_id,
        ts="2026-09-03T20:00:00+08:00",
    )
    ref_b = f"judgments.jsonl:{old_b['id']}"
    object_b = next(t["object_ref"] for t in world.view()["inputs"]["trackable_objects"] if t["object_ref"]["ref"] == ref_b)
    world.bind_at(fx.BIND_DAY, object_ref=object_b).raise_for_status()
    items = [i for i in world.view()["maintenance"]["items"] if i["status"] == "open"]
    return (next(i for i in items if i["object_ref"]["ref"] != ref_b),
            next(i for i in items if i["object_ref"]["ref"] == ref_b))


def test_y1_cancel_before_source_persistence_cannot_fold_other_item(world, monkeypatch):
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
            assert continue_message.wait(15)
        return original_append(self, conversation_id, role, content, **kwargs)

    monkeypatch.setattr(ConversationStore, "append_message", delayed_append)
    continuation = request_a["continuation"]
    body = {
        "user": fx.OWNER, "content": continuation["full_prompt"], "skill_mode": "hybrid",
        "maintenance_launch": {
            "item_id": continuation["maintenance_item_id"],
            "request_event_id": continuation["request_event_id"],
        },
    }
    thread = threading.Thread(target=lambda: responses.append(world.client.post(
        f"/api/conversations/{world.conversation_id}/messages", json=body,
    )))
    thread.start()
    try:
        assert at_message.wait(10)
        visible = world.client.get("/api/runs", params={"user": fx.OWNER})
        visible.raise_for_status()
        runs = [r for r in visible.json() if r["session_id"] == world.conversation_id]
        assert len(runs) == 1
        run_id = runs[0]["run_id"]
        claimed = world.act(idempotency_key="claim-window-b", run_id=run_id, **world.link_args(b["id"]))
        assert claimed.status_code == 200, claimed.text
        cancelled = world.client.post(f"/api/runs/{run_id}/cancel", params={"user": fx.OWNER})
        assert cancelled.status_code == 200, cancelled.text
        assert cancelled.json()["status"] == "cancelled", cancelled.text
        world.service.fold_run_terminal(ctx=OwnerContext.for_owner(fx.OWNER), run_id=run_id)
        during_b = world.current_item(b["id"])
    finally:
        continue_message.set()
        thread.join(20)
    assert not thread.is_alive()
    assert responses and responses[0].status_code == 202, [r.text for r in responses]
    messages = world.service.res.conversation_store_for(fx.OWNER).load_messages(world.conversation_id)
    source = next(m for m in messages if m.role == "user" and m.run_id == run_id)
    assert source.maintenance_launch["item_id"] == a["id"]
    after_b = world.current_item(b["id"])
    store = EvolutionStore(world.user_root / "research_evolution", fx.OWNER)
    rows = [r for r in store.list_action_records() if r["item_id"] == b["id"] and r.get("event")]
    print("Y1", "cancel", cancelled.json(), "source", source.maintenance_launch,
          "before", before_b["status"], before_b["management_revision"],
          "during", during_b["status"], during_b["management_revision"],
          "after", after_b["status"], after_b["management_revision"],
          "events", [r["event"]["kind"] for r in rows])
    assert after_b["management_revision"] == before_b["management_revision"], "A's cancellation before message persistence must not consume B's request"
    assert after_b["status"] == "rejudgment_requested"


def test_y2_unreadable_source_cannot_activate_conflicting_link(world, monkeypatch):
    a, b = two_items(world)
    request_a = world.rejudge(a, key="request-a")
    world.rejudge(b, key="request-b")
    before_b = world.current_item(b["id"])
    run_store = RunStore(user_id=fx.OWNER)
    run = run_store.create_run(question="Maintenance A", task_type="research", session_id=world.conversation_id)
    registered = world.act(idempotency_key="claim-b", run_id=run.run_id, **world.link_args(b["id"]))
    assert registered.status_code == 200, registered.text
    conversation = world.service.res.conversation_store_for(fx.OWNER)
    conversation.append_message(
        world.conversation_id, "user", request_a["continuation"]["full_prompt"],
        run_id=run.run_id, maintenance_launch={
            "item_id": a["id"], "request_event_id": request_a["continuation"]["request_event_id"],
        },
    )
    run_store.finish_run(run.run_id, status="failed", error="deterministic failure")
    ctx = OwnerContext.for_owner(fx.OWNER)
    assert world.service.fold_run_terminal(ctx=ctx, run_id=run.run_id) is None
    assert world.current_item(b["id"])["management_revision"] == before_b["management_revision"]

    def unreadable(self, conversation_id):
        raise OSError("source reader temporarily unavailable")

    with monkeypatch.context() as unavailable:
        unavailable.setattr(ConversationStore, "load_messages", unreadable)
        result = world.service.fold_run_terminal(ctx=ctx, run_id=run.run_id)
    after_b = world.current_item(b["id"])
    print("Y2", "registration", registered.status_code, "fault_fold", result,
          "before", before_b["status"], before_b["management_revision"],
          "after", after_b["status"], after_b["management_revision"])
    assert after_b["management_revision"] == before_b["management_revision"], "Source read failure must preserve B's pending request"
    assert after_b["status"] == "rejudgment_requested"
