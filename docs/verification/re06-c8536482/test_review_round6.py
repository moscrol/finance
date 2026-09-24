"""RE06 round-6 independent probes. Synthetic users; real messages/actions/domain/writer."""
from __future__ import annotations

import pytest

import intelligence.tests.research_evolution_fixtures as fx
from intelligence.api import app as app_module
from intelligence.services import judgments as judgments_svc
from intelligence.services.research_evolution.access import OwnerContext
from intelligence.services.research_evolution.run_observer import ObservingRunStore
from intelligence.services.research_evolution.store import EvolutionStore
from intelligence.tests.test_research_evolution_rework import World


@pytest.fixture
def world(tmp_path, monkeypatch):
    fx.install_env(monkeypatch, tmp_path)
    return World(tmp_path / "users", monkeypatch)


def cancel(world, item_id, key):
    args = world.link_args(item_id)
    args["action"] = "cancel_rejudge"
    world.act(idempotency_key=key, **args).raise_for_status()


def two_items(world):
    world.track_judgment().raise_for_status()
    _, original_b = judgments_svc.record_judgment(
        world.user_root / "judgments.jsonl", themes=[fx.ENTITY], memo="另一条独立判断 B：下游成本承压",
        session_id=world.conversation_id, ts="2026-09-03T20:00:00+08:00",
    )
    ref_b = f"judgments.jsonl:{original_b['id']}"
    object_b = next(t["object_ref"] for t in world.view()["inputs"]["trackable_objects"] if t["object_ref"]["ref"] == ref_b)
    world.bind_at(fx.BIND_DAY, object_ref=object_b).raise_for_status()
    items = [i for i in world.view()["maintenance"]["items"] if i["status"] == "open"]
    return (next(i for i in items if i["object_ref"]["ref"] != ref_b),
            next(i for i in items if i["object_ref"]["ref"] == ref_b))


def launch(world, continuation):
    response = world.client.post(
        f"/api/conversations/{world.conversation_id}/messages",
        json={"user": fx.OWNER, "content": continuation["full_prompt"], "skill_mode": "hybrid",
              "maintenance_launch": {"item_id": continuation["maintenance_item_id"],
                                     "request_event_id": continuation["request_event_id"]}},
    )
    assert response.status_code == 202, response.text
    return response.json()["run_id"]


def delayed_failure(world):
    def run(**kwargs):
        world.turn_gate.wait(15)
        kwargs["run_store"].finish_run(kwargs["run_id"], "failed", error="deterministic failure")
    return run


def test_w1_running_run_cannot_be_claimed_by_another_item(world, monkeypatch):
    a, b = two_items(world)
    first = world.rejudge(a, key="request-A")
    world.rejudge(b, key="request-B")
    monkeypatch.setattr(app_module, "_run_conversation_turn", delayed_failure(world))
    world.turn_gate.clear()
    try:
        run_a = launch(world, first["continuation"])
        store = EvolutionStore(world.user_root / "research_evolution", fx.OWNER)
        assert len(store.list_run_links(item_id=a["id"])) == 1
        before_b = world.current_item(b["id"])
        response = world.act(idempotency_key="claim-A-as-B", run_id=run_a, **world.link_args(b["id"]))
    finally:
        world.turn_gate.set()
    world.wait_terminal(run_a)
    world.service.fold_run_terminal(ctx=OwnerContext.for_owner(fx.OWNER), run_id=run_a)
    after_b = world.current_item(b["id"])
    print("W1", response.status_code, response.json(), "B", before_b["status"], before_b["management_revision"], "->", after_b["status"], after_b["management_revision"], "LINKS", store.list_run_links())
    assert response.status_code in {400, 404, 409}, "run already has A's verified coordinate; linking it to B must be rejected"
    assert after_b["management_revision"] == before_b["management_revision"]
    assert not store.list_run_links(item_id=b["id"])


def test_w2_rejected_stale_message_cannot_gain_current_identity_while_running(world, monkeypatch):
    world.track_judgment().raise_for_status()
    item = world.open_item()
    first = world.rejudge(item, key="request-A")
    cancel(world, item["id"], "cancel-A")
    world.clock.advance(seconds=1)
    world.rejudge(world.current_item(item["id"]), key="request-B")
    before = world.current_item(item["id"])
    monkeypatch.setattr(app_module, "_run_conversation_turn", delayed_failure(world))
    world.turn_gate.clear()
    try:
        # Send A's coordinate only after B exists. Accept-side correctly refuses to bind it.
        run_a = launch(world, first["continuation"])
        store = EvolutionStore(world.user_root / "research_evolution", fx.OWNER)
        assert not store.list_run_links(item_id=item["id"])
        response = world.act(idempotency_key="stale-message-as-B", run_id=run_a, **world.link_args(item["id"]))
    finally:
        world.turn_gate.set()
    world.wait_terminal(run_a)
    world.service.fold_run_terminal(ctx=OwnerContext.for_owner(fx.OWNER), run_id=run_a)
    after = world.current_item(item["id"])
    print("W2", response.status_code, response.json(), "ITEM", before["status"], before["management_revision"], "->", after["status"], after["management_revision"], "LINKS", store.list_run_links())
    assert response.status_code in {400, 404, 409}, "rejected stale launch must not be laundered through explicit running registration"
    assert after["management_revision"] == before["management_revision"]
    assert not store.list_run_links(item_id=item["id"])


def test_w3_cancelled_other_item_is_still_a_possible_late_judgment_producer(world):
    a, b = two_items(world)
    world.rejudge(a, key="request-A")
    world.rejudge(b, key="request-B")
    observer = ObservingRunStore(
        user_id=fx.OWNER, evolution_root=world.user_root / "research_evolution",
        maintenance_folder=lambda run_id: world.service.fold_run_terminal(
            ctx=OwnerContext.for_owner(fx.OWNER), run_id=run_id),
    )
    run_a = observer.create_run(question="复核 A", task_type="research", session_id=world.conversation_id)
    run_b = observer.create_run(question="复核 B", task_type="research", session_id=world.conversation_id)
    for item, run, key in ((a, run_a, "register-A"), (b, run_b, "register-B")):
        world.act(idempotency_key=key, run_id=run.run_id, **world.link_args(item["id"])).raise_for_status()
    cancel(world, a["id"], "cancel-A")
    before = world.current_item(b["id"])
    assert before["management"]["rejudgment"]["attempts"] == 1
    assert len([i for i in world.view()["maintenance"]["items"] if i["status"] == "rejudgment_requested"]) == 1
    world.clock.advance(seconds=1)
    _, judgment_a = judgments_svc.record_judgment(
        world.user_root / "judgments.jsonl", themes=[fx.ENTITY], memo="仅 A 的迟到成果，B 没有成果",
        session_id=world.conversation_id, ts=world.clock().isoformat(),
    )
    observer.finish_run(run_a.run_id, "completed")
    observer.finish_run(run_b.run_id, "completed")
    after = world.current_item(b["id"])
    print("W3", "A_JUDGMENT", judgment_a["id"], "B", before["status"], before["management_revision"], "->", after["status"], after["management_revision"], after["management"])
    assert after["status"] == "rejudgment_requested", "one pending item does not prove ownership of an unconsumed judgment from a cancelled peer"
    assert after["management_revision"] == before["management_revision"]
