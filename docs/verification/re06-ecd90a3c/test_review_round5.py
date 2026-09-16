"""Independent RE06 round-5 probes at 99d6e193 (code ecd90a3c).

Temporary synthetic users, real HTTP endpoints/domain/stores/writer; deterministic
executors only. Never touches production users, models or market sources.
"""
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


def fail_turn(**kwargs):
    kwargs["run_store"].finish_run(kwargs["run_id"], "failed", error="deterministic failure")


def post_message(world, content):
    response = world.client.post(
        f"/api/conversations/{world.conversation_id}/messages",
        json={"user": fx.OWNER, "content": content, "skill_mode": "hybrid"},
    )
    assert response.status_code == 202, response.text
    return response.json()["run_id"]


def observer_for(world):
    return ObservingRunStore(
        user_id=fx.OWNER, evolution_root=world.user_root / "research_evolution",
        maintenance_folder=lambda run_id: world.service.fold_run_terminal(
            ctx=OwnerContext.for_owner(fx.OWNER), run_id=run_id,
        ),
    )


def cancel(world, item_id, key):
    args = world.link_args(item_id)
    args["action"] = "cancel_rejudge"
    world.act(idempotency_key=key, **args).raise_for_status()


def test_old_ordinary_message_cannot_be_compensated_into_new_request(world, monkeypatch):
    monkeypatch.setattr(app_module, "_run_conversation_turn", fail_turn)
    old_run = post_message(world, "请解释市盈率是什么。")
    world.wait_terminal(old_run)
    # This user message and run predate even the creation of the maintenance request.
    item = world.seed_rejudged_item()
    response = world.act(idempotency_key="old-chat-as-new-rejudge", run_id=old_run, **world.link_args(item["id"]))
    after = world.current_item(item["id"])
    links = EvolutionStore(world.user_root / "research_evolution", fx.OWNER).list_run_links(item_id=item["id"])
    print("OLD_CHAT_COMPENSATION", response.status_code, response.json(), "AFTER", after["status"], after["management_revision"], "LINKS", links)
    assert response.status_code in {400, 404, 409}, "An old unrelated user message is not proof of this newly created request"
    assert after["management_revision"] == item["management_revision"]
    assert not links


def test_cancelled_request_launch_text_cannot_claim_replacement_generation(world, monkeypatch):
    world.track_judgment().raise_for_status()
    item = world.open_item()
    first = world.rejudge(item, key="request-A")
    old_prompt = first["continuation"]["full_prompt"]
    request_a = world.current_item(item["id"])["management"]["rejudgment"]["request_event_id"]
    cancel(world, item["id"], "cancel-A")
    world.clock.advance(seconds=1)
    second = world.rejudge(world.current_item(item["id"]), key="request-B")
    before = world.current_item(item["id"])
    assert before["management"]["rejudgment"]["request_event_id"] != request_a
    print("LAUNCH_TEXT_EQUAL_ACROSS_GENERATIONS", old_prompt == second["continuation"]["full_prompt"])
    monkeypatch.setattr(app_module, "_run_conversation_turn", fail_turn)
    # A tab sends its saved request-A response after another tab has cancelled A and requested B.
    run_id = post_message(world, old_prompt)
    world.wait_terminal(run_id)
    # Also invoke the real folder synchronously so assertions don't race its async callback.
    world.service.fold_run_terminal(ctx=OwnerContext.for_owner(fx.OWNER), run_id=run_id)
    after = world.current_item(item["id"])
    links = EvolutionStore(world.user_root / "research_evolution", fx.OWNER).list_run_links(item_id=item["id"])
    print("DELAYED_A_MESSAGE", "BEFORE", before["status"], before["management_revision"], "AFTER", after["status"], after["management_revision"], "LINKS", links)
    assert after["management_revision"] == before["management_revision"], "Request A's delayed message must not be assigned request B's current identity"
    assert not links


def test_first_attempt_cannot_consume_other_items_judgment(world):
    world.track_judgment().raise_for_status()
    # Bind a distinct underlying judgment, not merely two changes of the same object.
    _, original_b = judgments_svc.record_judgment(
        world.user_root / "judgments.jsonl", themes=[fx.ENTITY], memo="下游制冷剂采购利润承压，是另一条独立判断",
        session_id=world.conversation_id, ts="2026-09-03T20:00:00+08:00",
    )
    ref_b = f"judgments.jsonl:{original_b['id']}"
    object_b = next(t["object_ref"] for t in world.view()["inputs"]["trackable_objects"] if t["object_ref"]["ref"] == ref_b)
    world.bind_at(fx.BIND_DAY, object_ref=object_b).raise_for_status()
    open_items = [i for i in world.view()["maintenance"]["items"] if i["status"] == "open"]
    item_b = next(i for i in open_items if i["object_ref"]["ref"] == ref_b)
    item_a = next(i for i in open_items if i["object_ref"]["ref"] != ref_b)
    items = [item_a, item_b]
    assert items[0]["object_ref"]["ref"] != items[1]["object_ref"]["ref"]
    observer = observer_for(world)
    for idx, item in enumerate(items[:2]):
        world.rejudge(item, key=f"request-item-{idx}")
    run_a = observer.create_run(question="复核维护项 A", task_type="research", session_id=world.conversation_id)
    run_b = observer.create_run(question="复核维护项 B", task_type="research", session_id=world.conversation_id)
    world.act(idempotency_key="register-item-A", run_id=run_a.run_id, **world.link_args(items[0]["id"])).raise_for_status()
    world.act(idempotency_key="register-item-B", run_id=run_b.run_id, **world.link_args(items[1]["id"])).raise_for_status()
    before = world.current_item(items[1]["id"])
    assert before["management"]["rejudgment"]["attempts"] == 1
    world.clock.advance(seconds=1)
    _, judgment_a = judgments_svc.record_judgment(
        world.user_root / "judgments.jsonl", themes=[fx.ENTITY], memo="仅维护项 A 的成果，不是 B 的成果",
        session_id=world.conversation_id, ts=world.clock().isoformat(),
    )
    observer.finish_run(run_a.run_id, "completed")
    observer.finish_run(run_b.run_id, "completed")  # B writes no judgment.
    after = world.current_item(items[1]["id"])
    print("OTHER_ITEM_JUDGMENT", judgment_a["id"], "BEFORE", before["status"], "AFTER", after["status"], after["management"])
    assert after["status"] == "rejudgment_requested", "First attempt of B is not evidence that the latest session judgment belongs to B"
    assert after["management_revision"] == before["management_revision"]


def test_running_old_request_cannot_be_reregistered_as_new_generation(world, monkeypatch):
    def delayed_failure(**kwargs):
        world.turn_gate.wait(10)
        fail_turn(**kwargs)

    monkeypatch.setattr(app_module, "_run_conversation_turn", delayed_failure)
    world.track_judgment().raise_for_status()
    item = world.open_item()
    first = world.rejudge(item, key="request-A")
    world.turn_gate.clear()
    try:
        old_run = post_message(world, first["continuation"]["full_prompt"])
        world.act(idempotency_key="register-A", run_id=old_run, **world.link_args(item["id"])).raise_for_status()
        cancel(world, item["id"], "cancel-A")
        world.clock.advance(seconds=1)
        world.rejudge(world.current_item(item["id"]), key="request-B")
        before = world.current_item(item["id"])
        response = world.act(idempotency_key="reregister-old-run", run_id=old_run, **world.link_args(item["id"]))
    finally:
        world.turn_gate.set()
    world.wait_terminal(old_run)
    world.service.fold_run_terminal(ctx=OwnerContext.for_owner(fx.OWNER), run_id=old_run)
    after = world.current_item(item["id"])
    print("RUNNING_OLD_REREGISTRATION", response.status_code, response.json(), "BEFORE", before["management_revision"], "AFTER", after["status"], after["management_revision"])
    assert response.status_code in {400, 404, 409}, "Generation validation must apply during registration, not only after terminal"
    assert after["management_revision"] == before["management_revision"]
