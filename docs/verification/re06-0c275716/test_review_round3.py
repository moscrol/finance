"""Independent correct-contract probes for 0c275716; synthetic users only.

Run from the candidate repository with the workbench interpreter and PYTHONPATH=.
No live model, network data source or production user state is used.
"""
from __future__ import annotations

import pytest

import intelligence.tests.research_evolution_fixtures as fx
from intelligence.services.conversation_store import ConversationStore
from intelligence.services.research_evolution.access import OwnerContext
from intelligence.services.research_evolution.run_observer import ObservingRunStore
from intelligence.services.research_evolution.store import SUMMARIES_DIR, EvolutionStore
from intelligence.tests.test_research_evolution_rework import World


@pytest.fixture
def world(tmp_path, monkeypatch):
    fx.install_env(monkeypatch, tmp_path)
    return World(tmp_path / "users", monkeypatch)


def test_fast_failed_run_can_be_reconciled_after_message_response(world, monkeypatch):
    """The real UI posts link_run only after POST messages returns, without a turn gate."""
    from intelligence.api import app as app_module

    def fail_turn(**kwargs):
        kwargs["run_store"].finish_run(kwargs["run_id"], "failed", error="model unavailable")

    monkeypatch.setattr(app_module, "_run_conversation_turn", fail_turn)
    item = world.seed_rejudged_item()
    # 第五轮 QC 纠偏：消息携带服务端生成的请求实例坐标（首轮也能带，不依赖 origin run），
    # 不再用裸文案充当请求身份；核心断言（快速终态可收尾）不变。
    launch = {"item_id": item["id"], "request_event_id": item["management"]["rejudgment"]["request_event_id"]}
    posted = world.client.post(
        f"/api/conversations/{world.conversation_id}/messages",
        json={"user": fx.OWNER, "content": "继续核查", "skill_mode": "hybrid", "maintenance_launch": launch},
    )
    assert posted.status_code == 202, posted.text
    run_id = posted.json()["run_id"]
    world.wait_terminal(run_id)
    # Model/service can finish before the browser's second request arrives.
    response = world.act(
        idempotency_key=f"link_run:{item['id']}:{run_id}",
        run_id=run_id,
        **world.link_args(item["id"]),
    )
    print("FAST_TERMINAL", response.status_code, response.json(), world.current_item(item["id"])["status"])
    assert response.status_code == 200, "A real accepted run must have a durable association even when it finishes before the second HTTP request"


def test_old_registered_run_must_not_fold_a_new_rejudge_request(world):
    item = world.seed_rejudged_item()
    observer = ObservingRunStore(
        user_id=fx.OWNER,
        evolution_root=world.user_root / "research_evolution",
        maintenance_folder=lambda run_id: world.service.fold_run_terminal(
            ctx=OwnerContext.for_owner(fx.OWNER), run_id=run_id
        ),
    )
    old_run = observer.create_run(question="first maintenance attempt", task_type="research", session_id=world.conversation_id)
    world.act(idempotency_key="register-old-attempt", run_id=old_run.run_id, **world.link_args(item["id"])).raise_for_status()
    cancel_args = world.link_args(item["id"])
    cancel_args["action"] = "cancel_rejudge"
    world.act(idempotency_key="cancel-first-request", **cancel_args).raise_for_status()
    world.clock.advance(seconds=1)
    world.rejudge(world.current_item(item["id"]), key="second-request")
    before = world.current_item(item["id"])
    # A response-lost request / old worker can still terminate after the recovery action.
    observer.finish_run(old_run.run_id, "failed", error="late failure of first attempt")
    after = world.current_item(item["id"])
    print("LATE_OLD_RUN", before["management"], after["status"], after["management"])
    assert after["status"] == "rejudgment_requested", "A run registered for request A must not reset pending request B"
    assert after["management_revision"] == before["management_revision"]


def test_select_task_first_turn_keeps_structured_sources(world):
    world.track_judgment().raise_for_status()
    task_id = world.view()["priority"]["selected"][0]["task_id"]
    selected = world.act(action="select_task", idempotency_key="select-first", task_id=task_id)
    selected.raise_for_status()
    continuation = selected.json()["continuation"]
    assert continuation["click_payload"]["source_refs"]
    # Match App.tsx: only attach continuation when it contains an origin run_id.
    body = {"user": fx.OWNER, "content": continuation["full_prompt"], "skill_mode": "hybrid"}
    if continuation.get("run_id"):
        body["continuation"] = continuation
    posted = world.client.post(f"/api/conversations/{world.conversation_id}/messages", json=body)
    assert posted.status_code == 202, posted.text
    world.wait_terminal(posted.json()["run_id"])
    message = next(
        m for m in ConversationStore(user_id=fx.OWNER).load_messages(world.conversation_id)
        if m.run_id == posted.json()["run_id"] and m.role == "user"
    )
    print("FIRST_TURN_SOURCES", continuation["click_payload"], "saved", message.continuation)
    assert message.continuation and message.continuation.get("click_payload") == continuation["click_payload"]


def test_summary_without_id_reads_latest_version_not_lexical_hash(world):
    store = EvolutionStore(world.user_root / "research_evolution", fx.OWNER)
    store.publish_immutable(SUMMARIES_DIR, "sum-ffff", {
        "summary_id": "sum-ffff", "generated_at": "2026-09-14T01:00:00Z", "supersedes": None,
    })
    store.publish_immutable(SUMMARIES_DIR, "sum-0000", {
        "summary_id": "sum-0000", "generated_at": "2026-09-14T02:00:00Z", "supersedes": "sum-ffff",
    })
    response = world.act(action="read_receipt", idempotency_key="read-latest", kind="pilot_summary")
    response.raise_for_status()
    print("LATEST_SUMMARY", response.json())
    assert response.json()["receipt"]["summary_id"] == "sum-0000"


def test_failed_lockfile_open_releases_process_lock(tmp_path, monkeypatch):
    """An OS error during telemetry must not permanently poison the owner lock."""
    import os

    from intelligence.services.research_evolution.store import LOCK_FILE, StoreLockTimeout

    store = EvolutionStore(tmp_path / "evolution", "default")
    real_open = os.open

    def fail_lock_open(path, *args, **kwargs):
        if str(path).endswith(LOCK_FILE):
            raise PermissionError("injected transient lockfile open failure")
        return real_open(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(os, "open", fail_lock_open)
        with pytest.raises(PermissionError):
            with store.try_transaction(timeout=0.02):
                pass
    try:
        with store.try_transaction(timeout=0.02):
            pass
    except StoreLockTimeout:
        pytest.fail("os.open failed after acquiring the process lock; that lock was never released")
