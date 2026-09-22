"""OPT-08: a durable write failure fences new effects, not the in-memory draft."""
from __future__ import annotations

from dataclasses import replace

import pytest

from intelligence.runtime.agent_episode import ContinuousAgentEpisode
from intelligence.tests.conformance.fixtures import (
    ScenarioProbe, ScriptedModelClient, make_context, make_frame, make_registry,
)
from intelligence.tests.conformance.oracle import WriteOrderOracle
from intelligence.tests.conformance.races._drive import build_rig, tool_then_finish


class FailingStore(WriteOrderOracle):
    def __init__(self, boundary: str, *, occurrence: int = 1):
        super().__init__()
        self.boundary = boundary
        self.remaining = occurrence
        self.failed = False
        self.writes_after_failure = 0

    def _check(self, boundary):
        if self.failed:
            self.writes_after_failure += 1
        elif boundary == self.boundary:
            self.remaining -= 1
            if self.remaining == 0:
                self.failed = True
                raise OSError("disk full")

    def append(self, episode_id, events, *, sync=False):
        for event in events:
            self._check(event.kind)
        super().append(episode_id, events, sync=sync)

    def put_state(self, episode_id, state):
        self._check(f"state:{state.phase}")
        super().put_state(episode_id, state)


@pytest.mark.parametrize(("boundary", "model_calls", "tool_calls"), [
    ("configure", 0, 0), ("task", 0, 0), ("prompt_assembled", 0, 0),
    ("state:planning", 0, 0), ("model_intent", 0, 0),
    ("state:model_pending", 0, 0), ("model_turn", 1, 0),
    ("tool_request", 1, 0), ("state:tools_pending", 1, 0),
    ("tool_result", 1, 1), ("finish", 2, 1), ("state:done", 2, 1),
])
def test_failed_write_stops_new_effects(boundary, model_calls, tool_calls):
    store = FailingStore(boundary)
    rig = build_rig(f"failure-{boundary.replace(':', '-')}", store=store)
    emitted = []
    rig.episode._event_sink = emitted.append
    rig.start()
    outcome = rig.finish()
    assert store.failed, "failure injection must actually be reached"
    assert outcome.status == "failed"
    assert outcome.stop_reason == "storage_failed"
    assert outcome.persistence == "failed"
    assert rig.model.calls == model_calls
    assert outcome.usage.llm_calls == model_calls
    assert outcome.usage.tool_calls == tool_calls
    assert store.writes_after_failure == 0
    assert any(e.kind == "persistence_failed" for e in outcome.events)
    from intelligence.services.episode_progress import project_episode_progress
    failure = next(e for e in emitted if e.kind == "persistence_failed")
    assert project_episode_progress(failure).status == "failed"
    assert not any(e.kind == "finish" and e.payload["status"] == "completed" for e in emitted)
    # Durable data remains an unchanged prefix, even if done-state failed AFTER finish append.
    stored, _state = store.load(rig.task_id)
    assert stored == outcome.events[:len(stored)]
    if boundary in {"finish", "state:done"}:
        assert outcome.draft, "saving failure must not discard an already admitted draft"
    assert tuple(e.sequence for e in outcome.events) == tuple(range(1, len(outcome.events) + 1))


def test_successful_durable_completion_is_explicit_and_flushed():
    rig = build_rig("durable-completion")
    rig.start()
    outcome = rig.finish()
    assert outcome.persistence == "durable"
    assert outcome.status == "completed"
    assert rig.stored_events() == outcome.events
    assert rig.stored_state().phase == "done"
    finish_writes = [t for t in rig.oracle.timeline if t.kind == "append" and t.label == "finish"]
    assert finish_writes and all(t.sync for t in finish_writes)


def test_ephemeral_mode_and_broken_progress_sink_are_not_storage_failures():
    probe = ScenarioProbe()
    frame = make_frame()
    def broken_sink(_event):
        raise OSError("UI disconnected")
    episode = ContinuousAgentEpisode(
        ScriptedModelClient(tool_then_finish(), probe), event_sink=broken_sink,
    )
    outcome = episode.run(task_frame=frame, context=make_context(frame), registry=make_registry(probe))
    assert outcome.status == "completed"
    assert outcome.persistence == "ephemeral"
    assert outcome.events[0].payload["persistence_mode"] == "ephemeral"


@pytest.mark.parametrize("boundary", ["model_turn", "state:model_pending", "tool_menu"])
def test_failure_on_second_turn_keeps_cost_and_existing_evidence(boundary):
    store = FailingStore(boundary, occurrence=2)
    rig = build_rig("second-turn-failure", store=store)
    rig.start()
    outcome = rig.finish()
    assert outcome.persistence == "failed"
    assert len(outcome.evidence) == 1
    assert outcome.usage.tool_calls == 1
    assert rig.model.calls == (2 if boundary == "model_turn" else 1)
    if boundary == "model_turn":
        assert outcome.draft and outcome.bindings


@pytest.mark.parametrize("boundary", ["model_intent", "model_turn", "finish", "state:done"])
def test_repair_write_failure_keeps_previous_draft_and_fences_further_resume(boundary):
    from intelligence.runtime.glm_agent_runtime import GLMAgentRuntime
    from intelligence.services.agent_runtime import ModelTurn
    from intelligence.services.episode_session import EpisodeSessionError
    from intelligence.tests.test_agent_episode import (
        ScriptedModel, _frame, _context, _tool_turn, _finish_turn,
        _market_registry, _successful_runner,
    )
    from intelligence.tests.test_episode_session import _goal

    frame = _frame(("direct_assessment", "counterpoint"))
    context = _context(frame, max_steps=2)
    model = ScriptedModel([
        _tool_turn("市场"), _finish_turn(status="partial", gap="缺少反方证据"),
        ModelTurn("", (), error="TimeoutError"),
    ])
    store = FailingStore("not-yet")
    session = GLMAgentRuntime(client=model, episode_store=store).start(
        frame, context=context, registry=_market_registry(_successful_runner),
    )
    previous = session.outcome
    assert previous.draft and previous.persistence == "durable"
    store.boundary = boundary
    updated = session.resume(_goal(context.contract.task_id))
    assert updated.persistence == "failed" and updated.status == "failed"
    assert updated.draft == previous.draft
    assert updated.events[:len(previous.events)] == previous.events
    assert store.failed and store.writes_after_failure == 0
    if boundary in {"model_intent", "model_turn"}:
        assert len(model.calls) == (2 if boundary == "model_intent" else 3)
    with pytest.raises(EpisodeSessionError, match="persistence failed"):
        session.resume(_goal(context.contract.task_id))


@pytest.mark.parametrize(("boundary", "occurrence", "expected_calls"), [
    ("finalization_recovery_started", 1, 2), ("prompt_assembled", 2, 2),
    ("model_turn", 3, 3), ("finalization_recovery_outcome", 1, 3),
])
def test_compact_finalizer_obeys_the_same_persistence_fence(boundary, occurrence, expected_calls):
    from intelligence.services.agent_runtime import ModelTurn
    from intelligence.tests.test_agent_episode import (
        ScriptedModel, _frame, _context, _tool_turn, _finish_turn,
        _market_registry, _successful_runner,
    )
    frame = _frame()
    model = ScriptedModel([_tool_turn("市场"), ModelTurn("", (), error="provider unavailable"), _finish_turn()])
    store = FailingStore(boundary, occurrence=occurrence)
    outcome = ContinuousAgentEpisode(model, store=store).run(
        task_frame=frame, context=_context(frame, max_steps=1),
        registry=_market_registry(_successful_runner),
    )
    assert store.failed
    assert outcome.persistence == "failed" and outcome.status == "failed"
    assert len(model.calls) == expected_calls == outcome.usage.llm_calls
    if expected_calls == 3:
        assert outcome.draft


@pytest.mark.parametrize("during_repair", [False, True])
def test_workbench_does_not_judge_or_retry_a_storage_failure(during_repair):
    from intelligence.runtime.continuous_turn_adapter import ContinuousTurnAdapter
    from intelligence.tests.test_continuous_turn_adapter import (
        _progress_repair_fixture, _resumable_runtime, _SemanticThatRaises,
    )
    frame, control, context, initial, repaired = _progress_repair_fixture()
    failed = replace(
        repaired if during_repair else initial,
        status="failed", stop_reason="storage_failed", persistence="failed",
    )
    goals = []
    result = ContinuousTurnAdapter(
        runtime=_resumable_runtime(initial if during_repair else failed, failed, goals),
        semantic_verifier=_SemanticThatRaises(), runtime_name="continuous_glm", mode="on",
        context_factory=lambda *_a, **_kw: context,
        registry_factory=lambda *_a, **_kw: "registry",
    ).handle(frame=frame, control=control)
    assert result.status == "failed"
    assert "保存失败" in result.answer
    assert len(goals) == int(during_repair)
    assert result.private_artifact["learning_eligible"] is False
    assert result.private_artifact["outcome"]["draft"] == failed.draft
    assert failed.draft not in result.answer


@pytest.mark.parametrize("cancel_first", [True, False])
def test_cancel_and_save_failure_preserve_first_cause_without_new_dispatch(cancel_first):
    store = FailingStore("model_turn")
    rig = build_rig("cancel-and-store-failure", store=store)
    if cancel_first:
        rig.model.on_call[1] = lambda: rig.signal.request("user", "user stop")
    rig.start()
    rig.run_until("model_settled")
    if not cancel_first:
        rig.signal.request("user", "late stop")
    outcome = rig.finish()
    assert rig.signal.cause == ("user" if cancel_first else "hook")
    assert outcome.persistence == "failed" and outcome.stop_reason == "storage_failed"
    assert rig.model.calls == 1 and outcome.usage.tool_calls == 0


@pytest.mark.parametrize("failure_kind", ["append_after_write", "state_after_write"])
def test_write_then_raise_is_uncertain_not_rolled_back(tmp_path, failure_kind):
    from intelligence.services.episode_store import JsonlEpisodeStore

    class AmbiguousStore(JsonlEpisodeStore):
        def append(self, episode_id, events, *, sync=False):
            super().append(episode_id, events, sync=sync)
            if failure_kind == "append_after_write" and any(e.kind == "finish" for e in events):
                raise OSError("flush acknowledgement lost")

        def put_state(self, episode_id, state):
            super().put_state(episode_id, state)
            if failure_kind == "state_after_write" and state.terminal:
                raise OSError("checkpoint acknowledgement lost")

    store = AmbiguousStore(tmp_path)
    probe = ScenarioProbe()
    frame = make_frame()
    context = make_context(frame, task_id=f"ambiguous-{failure_kind}")
    outcome = ContinuousAgentEpisode(ScriptedModelClient(tool_then_finish(), probe), store=store).run(
        task_frame=frame, context=context, registry=make_registry(probe),
    )
    assert outcome.persistence == "failed" and outcome.draft
    events, state = store.load(context.contract.task_id)
    assert events == outcome.events[:len(events)]
    assert events[-1].kind == "finish"
    assert state.terminal is (failure_kind == "state_after_write")
    assert outcome.events[-1].payload["recovery"] == "uncertain"


def test_failed_artifact_uses_the_same_prompt_projection():
    from intelligence.runtime.continuous_turn_adapter import ContinuousTurnAdapter
    from intelligence.services.agent_runtime import EpisodeEvent
    from intelligence.tests.test_continuous_turn_adapter import _progress_repair_fixture, _SemanticThatRaises

    _frame, _control, context, initial, _repaired = _progress_repair_fixture()
    failed = replace(
        initial, status="failed", persistence="failed",
        events=(*initial.events, EpisodeEvent(3, "prompt_assembled", {"system": "PRIVATE_PROMPT", "user": "PRIVATE_INPUT"})),
    )
    result = ContinuousTurnAdapter(runtime=None, semantic_verifier=_SemanticThatRaises())._storage_failed_result(failed, context)
    projected = result.private_artifact["events"][-1]["payload"]
    assert "system" not in projected and "user" not in projected
    assert projected["system_chars"] == len("PRIVATE_PROMPT")


@pytest.mark.parametrize("transport", ["memory", "spool"])
def test_failed_inbox_write_is_not_acknowledged_or_deleted(tmp_path, transport):
    from intelligence.services.episode_inbox import SpoolRecord, write_spool_record

    store = FailingStore("inbox_inserted")
    # Memory oracle exposes a disk spool only for this test; runtime events stay in the oracle.
    store.episode_dir = lambda _episode_id: tmp_path
    rig = build_rig(f"inbox-failure-{transport}", store=store)
    rig.start()
    rig.run_until("model_pending")
    if transport == "memory":
        receipt = rig.episode.steer("新补充")
        assert not receipt.accepted and receipt.reason == "storage_failed"
    else:
        path = write_spool_record(tmp_path / "inbox-spool", SpoolRecord("msg1", "新补充"))
        assert rig.episode.inbox.ingest_spool() == 0
        assert path.exists()
    outcome = rig.finish()
    assert outcome.persistence == "failed"
    assert rig.model.calls == 0
    if transport == "spool":
        assert path.exists(), "finish cleanup must not delete a message that never reached durable storage"


def test_inbox_ack_flushes_insert_before_deleting_spool(tmp_path):
    from intelligence.services.episode_inbox import SpoolRecord, write_spool_record
    rig = build_rig("inbox-flush")
    rig.oracle.episode_dir = lambda _: tmp_path
    rig.start()
    rig.run_until("model_pending")
    path = write_spool_record(tmp_path / "inbox-spool", SpoolRecord("msg1", "补充"))
    assert rig.episode.inbox.ingest_spool() == 1 and not path.exists()
    writes = [t for t in rig.oracle.timeline if t.kind == "append" and t.label == "inbox_inserted"]
    assert writes and all(t.sync for t in writes)
    rig.finish()


@pytest.mark.parametrize("boundary", ["inbox_claimed", "inbox_discarded"])
def test_failed_inbox_settlement_preserves_pending_for_diagnosis(boundary):
    store = FailingStore(boundary)
    rig = build_rig("inbox-settlement-" + boundary, store=store)
    rig.start()
    rig.run_until("model_pending")
    assert rig.episode.steer("未决消息").accepted
    inbox = rig.episode.inbox
    if boundary == "inbox_claimed":
        assert inbox.claim("next_step") == []
    else:
        assert inbox.discard_all(reason="episode_finished") == 0
    assert store.failed and inbox.pending() == 1
    assert rig.finish().persistence == "failed"


@pytest.mark.parametrize("providers", [None, True])
def test_inflight_model_settles_usage_and_draft_after_inbox_save_failure(providers):
    from intelligence.runtime.glm_agent_runtime import GLMAgentRuntime
    from intelligence.tests.test_glm_agent_runtime import _provider
    import json
    from intelligence.tests.conformance.fixtures import completed_finish

    # First obtain evidence; second model request fails a concurrent inbox write.
    store = FailingStore("inbox_inserted")
    frame = make_frame()
    calls = []
    def complete(**_kwargs):
        calls.append(1)
        if len(calls) == 1:
            from intelligence.tests.test_model_turn_completion_boundary import envelope
            message = envelope("tool_calls")
        else:
            assert not runtime.steer("在飞请求中插话").accepted
            message = {
                "content": json.dumps(completed_finish()), "_finish_reason": "stop",
                "_usage": {"prompt_tokens": 31, "completion_tokens": 17},
            }
        return message, _provider("fake"), ""

    probe = ScenarioProbe()
    runtime = GLMAgentRuntime(
        providers=(_provider("fake"),) if providers else None,
        complete_fn=complete, episode_store=store,
    )
    outcome = runtime.run(
        task_frame=frame, context=make_context(frame, task_id=f"inflight-{providers}"),
        registry=make_registry(probe),
    )
    assert store.failed and outcome.persistence == "failed"
    assert outcome.draft
    assert len(calls) == outcome.usage.llm_calls == 2
    assert outcome.usage.input_tokens == 41 and outcome.usage.output_tokens == 37


def test_real_workbench_entry_reports_failed_not_completed(tmp_path, monkeypatch):
    """Real HTTP/assembly/adapter/runtime; only provider/tools/storage are doubles."""
    import json
    from pathlib import Path
    from fastapi.testclient import TestClient
    from intelligence.api import app as app_module
    from intelligence.tests.test_glm_agent_runtime import _provider
    from intelligence.tests.test_continuous_turn_adapter import _SemanticThatRaises
    from intelligence.tests.test_workbench_conversation_integration import (
        _send, _wait_message_terminal, _stream_payloads,
    )

    repo_root = Path(__file__).parent / "fixtures" / "chat_workbench_repo"
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))
    monkeypatch.setenv("FINANCE_WS", str(repo_root))
    monkeypatch.setenv("KB_VAULT", str(repo_root / "wiki"))
    monkeypatch.setenv("ASK_CONTINUOUS_RUNTIME", "on")
    monkeypatch.setenv("AGENT_RUNTIME_BACKEND", "continuous_glm")
    monkeypatch.setenv("FINANCE_NEWS_FETCH", "0")
    monkeypatch.setenv("FINANCE_WEB_SEARCH", "0")
    monkeypatch.setattr(app_module.SessionLLMSettings, "runtime_providers_for", lambda *_a: (_provider("fake"),))
    monkeypatch.setattr(app_module, "SemanticEpisodeVerifier", lambda **_: _SemanticThatRaises())
    store = FailingStore("state:done")
    probe = ScenarioProbe()
    calls = []

    def complete(**_kwargs):
        from intelligence.tests.test_model_turn_completion_boundary import envelope
        calls.append(1)
        assert len(calls) <= 2, "storage failure must not invoke judge/repair"
        # A valid partial finish for the real product contract (not the narrower
        # conformance contract). Persistence failure must also fence its repair.
        message = envelope("tool_calls") if len(calls) == 1 else {
            "content": json.dumps({"status": "partial", "draft": "私有草稿：资料还不完整，暂不能判断。", "gaps": ["缺证据"], "bindings": []}),
            "_finish_reason": "stop",
        }
        return message, _provider("fake"), ""

    monkeypatch.setattr(app_module.llm_refine, "chat_with_tools", complete)
    monkeypatch.setattr(app_module, "JsonlEpisodeStore", lambda *_a: store)
    monkeypatch.setattr(app_module, "_memory_bound_registry_factory", lambda *_a, **_kw: lambda *_: make_registry(probe))
    with TestClient(app_module.create_app(repo_root=repo_root)) as client:
        conversation_id = client.post(
            "/api/conversations", json={"title": "保存失败验收", "user": "alice"},
        ).json()["conversation_id"]
        created, run = _send(client, conversation_id, "明天A股怎么看，给出判断依据和风险条件")
        assert store.failed and run["status"] == "failed", run
        message = _wait_message_terminal(client, conversation_id)[-1]
        assert message["status"] == "failed" and "保存失败" in message["content"]
        stream = client.get(f"/api/runs/{created['run_id']}/events", params={"user": "alice"})
        payloads = _stream_payloads(stream.text)
        assert any(p["event_type"] == "message.error" for p in payloads), stream.text
        assert not any(p["event_type"] in {"message.completed", "message.complete"} for p in payloads)
        # Private draft remains available for diagnosis, not as a public answer or learning sample.
        artifacts = list((tmp_path / "users").rglob("continuous-episode.json"))
        assert len(artifacts) == 1
        artifact = json.loads(artifacts[0].read_text())
        assert artifact["learning_eligible"] is False
        assert artifact["outcome"]["persistence"] == "failed"
        assert artifact["outcome"]["draft"]
        assert len(calls) == 2 and len(probe.executed) == 1


def test_real_assembly_shares_local_failure_with_inflight_model(tmp_path, monkeypatch):
    import json
    from threading import Event
    from intelligence.api import app as app_module
    from intelligence.tests.test_glm_agent_runtime import _provider
    from intelligence.tests.conformance.fixtures import completed_finish

    store = FailingStore("inbox_inserted")
    monkeypatch.setenv("AGENT_RUNTIME_BACKEND", "continuous_glm")
    monkeypatch.setattr(app_module, "JsonlEpisodeStore", lambda *_: store)
    user_cancel = Event()
    calls = []

    def complete(**_kwargs):
        from intelligence.tests.test_model_turn_completion_boundary import envelope
        calls.append(1)
        if len(calls) == 1:
            return envelope("tool_calls"), _provider("fake"), ""
        receipt = adapter._runtime.steer("模型请求期间写失败")
        assert not receipt.accepted
        signal = adapter._runtime._episode._model._is_cancelled
        assert signal() and signal.cause == "hook" and signal.detail == "storage_failed"
        assert not user_cancel.is_set(), "local failure must not impersonate a user cancel"
        return {
            "content": json.dumps(completed_finish()), "_finish_reason": "stop",
            "_usage": {"prompt_tokens": 31, "completion_tokens": 17},
        }, _provider("fake"), ""

    monkeypatch.setattr(app_module.llm_refine, "chat_with_tools", complete)
    adapter = app_module._build_continuous_turn_adapter(
        providers=(_provider("fake"),), run_id="assembly", assistant_message_id="message",
        is_cancelled=user_cancel.is_set,
    )
    frame, probe = make_frame(), ScenarioProbe()
    outcome = adapter._runtime.run(task_frame=frame, context=make_context(frame), registry=make_registry(probe))
    assert outcome.persistence == "failed" and outcome.draft
    assert len(calls) == 2 and outcome.usage.input_tokens == 41 and outcome.usage.output_tokens == 37


def test_tool_intent_rejection_never_submits_to_executor():
    from intelligence.runtime.episode_tool_batch import ToolBatchExecutor
    from intelligence.services.agent_runtime import ModelToolCall

    class NeverSubmit:
        def submit(self, *_args, **_kwargs):
            pytest.fail("unpersisted intent reached executor")

    session = ToolBatchExecutor(executor=NeverSubmit()).new_session()
    session.on_dispatch = lambda _intent: False
    frame, probe = make_frame(), ScenarioProbe()
    result = session.execute(
        (ModelToolCall("t1", "market_data", {"query": "market"}),),
        registry=make_registry(probe), context=make_context(frame), remaining_slots=1,
    )
    assert result.executed_count == 0 and result.items[0].error == "storage_failed"
    assert not probe.executed


def test_parallel_failure_keeps_received_result_and_fences_queued_runner():
    """A completed future is retained; its queued sibling never calls runner()."""
    from concurrent.futures import Future
    from intelligence.runtime.episode_tool_batch import ToolBatchExecutor
    from intelligence.services import query_ledger
    from intelligence.tests.conformance.fixtures import ScriptedTurn, ScriptedToolCall

    class HeldExecutor:
        def __init__(self):
            self.held = None

        def submit(self, fn, *args):
            future = Future()
            if self.held is None:
                future.set_result(fn(*args))
                self.held = False
            else:
                # Worker has entered, but has not reached the registry/runner.
                assert future.set_running_or_notify_cancel()
                self.held = (future, fn, args)
                assert not episode.steer("并发保存失败").accepted
            return future

    store, probe, frame, executor = FailingStore("inbox_inserted"), ScenarioProbe(), make_frame(), HeldExecutor()
    model = ScriptedModelClient((ScriptedTurn(tool_calls=(
        ScriptedToolCall("market_data", "已收到"), ScriptedToolCall("market_data", "队列中"),
    )),), probe)
    episode = ContinuousAgentEpisode(model, store=store, tool_executor=ToolBatchExecutor(executor=executor))
    with query_ledger.query_ledger_scope() as queries:
        outcome = episode.run(task_frame=frame, context=make_context(frame), registry=make_registry(probe))
        assert outcome.persistence == "failed" and len(outcome.evidence) == 1
        assert outcome.usage.tool_calls == 2  # reserved/dispatched slots are not refunded
        assert probe.executed == [("market_data", "已收到")]
        errors = [e for e in outcome.events if e.kind == "tool_error"]
        assert any(e.payload["error"] == "storage_failed_inflight" for e in errors)
        assert queries.summary()["executed_count"] == 0, "failure must roll back shared-cache publication"
        future, fn, args = executor.held
        # Once the delayed worker reaches the effect boundary it must stop, even
        # though Python cannot forcibly kill an already-running thread.
        with pytest.raises(RuntimeError, match="cancelled before execution"):
            fn(*args)
        future.set_exception(RuntimeError("cancelled before execution"))
        assert probe.executed == [("market_data", "已收到")]
        assert store.writes_after_failure == 0


def test_inflight_tool_received_after_failure_is_retained_but_not_published():
    from concurrent.futures import Future
    from intelligence.runtime.episode_tool_batch import ToolBatchExecutor
    from intelligence.services import query_ledger
    from intelligence.tests.conformance.fixtures import ScriptedTurn, ScriptedToolCall

    class ImmediateExecutor:
        def submit(self, fn, *args):
            future = Future()
            future.set_result(fn(*args))
            return future

    frame, probe, store = make_frame(), ScenarioProbe(), FailingStore("inbox_inserted")
    registry = make_registry(probe)
    original = registry.resolve("market_data")

    def runner(query, context):
        assert not episode.steer("工具执行中保存失败").accepted
        assert context.cancelled
        return original.runner(query, context)

    from intelligence.services.research_tool_registry import ResearchToolRegistry
    registry = ResearchToolRegistry((replace(original, runner=runner),))
    episode = ContinuousAgentEpisode(
        ScriptedModelClient((ScriptedTurn(tool_calls=(ScriptedToolCall("market_data", "收到的结果"),)),), probe),
        store=store, tool_executor=ToolBatchExecutor(executor=ImmediateExecutor()),
    )
    with query_ledger.query_ledger_scope() as queries:
        outcome = episode.run(task_frame=frame, context=make_context(frame), registry=registry)
        assert outcome.persistence == "failed" and len(outcome.evidence) == 1
        assert outcome.usage.tool_calls == 1 and len(probe.executed) == 1
        assert queries.summary()["executed_count"] == 0
