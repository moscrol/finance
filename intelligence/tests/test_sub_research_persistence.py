"""P1a: real parent/child assembly, independent JSONL logs and shared failure fence.

External model/tools are scripted; the runtime, coordinator, ledgers and disk
roundtrip are real. These tests do NOT claim process-restart recovery works.
"""
from __future__ import annotations

from dataclasses import replace
import json
from threading import Event, Lock, Thread

import pytest

from intelligence.runtime.glm_agent_runtime import GLMAgentRuntime
from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import ModelToolCall, ModelTurn
from intelligence.services.episode_inbox import spool_dir_for
from intelligence.services.episode_messages import derive_messages, to_provider
from intelligence.services.episode_store import (
    EpisodeStoreFailed,
    FencedEpisodeStore,
    JsonlEpisodeStore,
    MemoryEpisodeStore,
)
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import release_root_budget
from intelligence.services.research_tool_registry import ResearchToolRegistry, ToolSpec
from intelligence.tests.test_sub_research_tool import _context, _frame


class ObservedStore(JsonlEpisodeStore):
    def __init__(self, root, *, fail_kind="", fail_child=True, fail_after_write=False):
        super().__init__(root)
        self.fail_kind = fail_kind
        self.fail_child = fail_child
        self.fail_after_write = fail_after_write
        self.failed = Event()
        self.writes_after_failure = 0
        self.sync_events = set()
        self.child_ids = set()

    def append(self, episode_id, events, *, sync=False):
        with self._lock:
            if self.failed.is_set():
                self.writes_after_failure += 1
            is_child = episode_id.startswith("branches-")
            if is_child:
                self.child_ids.add(episode_id)
            should_fail = is_child == self.fail_child and any(e.kind == self.fail_kind for e in events)
            if should_fail and not self.fail_after_write:
                self.failed.set()
                raise OSError("injected child-tree storage failure")
            super().append(episode_id, events, sync=sync)
            if sync:
                self.sync_events.update((episode_id, e.sequence) for e in events)
            if should_fail:
                self.failed.set()
                raise OSError("write acknowledgement lost")


class TreeModel:
    def __init__(self, store, parent_id, *, rounds=1, goals=("核验甲",), before_child=None, plan=False):
        self.store = store
        self.parent_id = parent_id
        self.rounds = rounds
        self.goals = goals
        self.before_child = before_child
        self.plan = plan
        self.parent_calls = 0
        self.child_calls = 0
        self.child_messages = []
        self._lock = Lock()

    def complete(self, *, messages, tools, timeout):
        is_child = "branch_findings" in json.dumps(messages[:2], ensure_ascii=False)
        if is_child:
            with self._lock:
                self.child_calls += 1
            parent_events, _ = self.store.load(self.parent_id)
            starts = [e for e in parent_events if e.kind == "branch_started"]
            assert starts, "child model must not run before its parent start record"
            assert all((self.parent_id, e.sequence) in self.store.sync_events for e in starts)
            assert "sub_research" not in [tool["function"]["name"] for tool in tools]
            self.child_messages.append(messages)
            if self.before_child is not None:
                self.before_child(messages)
            if not any(m["role"] == "tool" for m in messages):
                goal = str(messages[1]["content"])
                return ModelTurn("", (ModelToolCall("child-tool", "market_data", {"query": goal}),),
                                 input_tokens=11, output_tokens=7)
            return ModelTurn(json.dumps({
                "status": "completed", "draft": "子稿不得公开。", "gaps": [],
                "bindings": [{"output_id": "branch_findings", "evidence_hashes": ["E1"], "basis": "evidence"}],
            }, ensure_ascii=False), (), input_tokens=13, output_tokens=5)
        self.parent_calls += 1
        if self.parent_calls == 1 and self.plan:
            from intelligence.tests.test_agent_episode import _plan_turn
            return _plan_turn(requested_mode="deep", branch_goals=list(self.goals))
        if self.parent_calls <= self.rounds:
            goals = list(self.goals) if self.rounds == 1 else [f"核验第{self.parent_calls}批"]
            return ModelTurn("", (ModelToolCall(f"branches-{self.parent_calls}", "sub_research", {"goals": goals}),),
                             input_tokens=17, output_tokens=3)
        return ModelTurn(json.dumps({
            "status": "partial", "draft": "父稿：证据仍不足。", "gaps": ["待核验"], "bindings": [],
        }, ensure_ascii=False), (), input_tokens=19, output_tokens=2)


def registry(executed):
    def runner(query, _ctx):
        executed.append(query)
        evidence = AgentEvidence(
            tool="market_data", title="分支事实", detail="同窗可核验事实", source="fixture",
            source_date="2026-07-21", content_hash=f"hash:{query}",
        )
        return [evidence], "分支事实", ProviderTrace(provider="fixture", capability="market_data", status="success")
    return ResearchToolRegistry((ToolSpec(
        name="market_data", capability="market_data", description="行情", cost="local", freshness="current", runner=runner,
    ),))


def run_tree(store, *, rounds=1, goals=("核验甲",), before_child=None, plan=False):
    from intelligence.services.mode_governor import ModeSignals
    context = _context("max", allowed=("market_data", "sub_research"))
    model = TreeModel(store, context.contract.task_id, rounds=rounds, goals=goals, before_child=before_child, plan=plan)
    executed = []
    runtime = GLMAgentRuntime(
        client=model, episode_store=store,
        mode_signals=lambda *_: ModeSignals(user_mode="deep"),
    )
    try:
        initial_calls = context.root_budget.remaining_calls
        outcome = runtime.run(task_frame=_frame(), context=context, registry=registry(executed))
        spent = initial_calls - context.root_budget.remaining_calls
        return outcome, model, executed, spent, runtime
    finally:
        release_root_budget(context.contract.task_id)


def test_real_runtime_persists_children_with_bidirectional_refs_and_unique_repeat_ids(tmp_path):
    store = ObservedStore(tmp_path)
    outcome, model, executed, spent, _ = run_tree(store, rounds=2)
    assert outcome.persistence == "durable" and outcome.status == "partial"
    starts = [e for e in outcome.events if e.kind == "branch_started"]
    ends = [e for e in outcome.events if e.kind == "branch_completed"]
    assert len(starts) == len(ends) == 2
    refs = [dict(e.payload["episode_ref"]) for e in starts]
    assert [ref["branch_id"] for ref in refs] == ["branch-1", "branch-1"]
    assert len({ref["episode_id"] for ref in refs}) == 2
    assert len({ref["invocation_id"] for ref in refs}) == 2
    assert len(executed) == 2 and spent == 4  # parent two dispatch slots + two child tools
    assert model.parent_calls == 3 and model.child_calls == 4
    assert outcome.usage.llm_calls == 7 and outcome.usage.tool_calls == 4
    assert "子稿不得公开" not in outcome.draft
    reopened = JsonlEpisodeStore(tmp_path)
    for ref, end in zip(refs, ends):
        assert dict(end.payload["episode_ref"]) == ref
        assert end.payload["persistence"] == "durable"
        events, state = reopened.load(ref["episode_id"])
        assert state is not None and state.terminal
        assert dict(events[0].payload["branch_parent"]) == ref
        assert dict(state.contract_snapshot["branch_parent"]) == ref
        assert [e.sequence for e in events] == list(range(1, len(events) + 1))
        assert any(e.kind == "model_intent" for e in events)
        assert any(e.kind == "tool_result" for e in events)
        assert any(e.kind == "model_turn" and "子稿不得公开" in str(e.payload) for e in events)
        assert to_provider(derive_messages(events))  # full private model-visible history survives disk
    assert store.writes_after_failure == 0
    from intelligence.services.episode_projection import project_durable_events
    # Removing the second terminal must not be masked by the first branch-1.
    projection = project_durable_events([e for e in outcome.events if e is not ends[1]])
    assert projection.unpaired_branch_ids == (refs[1]["episode_id"],)
    assert not project_durable_events(outcome.events).has_anomalies


@pytest.mark.parametrize("fail_after_write", [False, True])
def test_child_storage_failure_fences_parent_and_keeps_received_usage(tmp_path, fail_after_write):
    store = ObservedStore(tmp_path, fail_kind="model_turn", fail_after_write=fail_after_write)
    outcome, model, executed, spent, runtime = run_tree(store)
    assert store.failed.is_set()
    assert outcome.persistence == "failed" and outcome.stop_reason == "storage_failed"
    assert model.parent_calls == 1 and model.child_calls == 1
    assert executed == [] and spent == 1  # submitted parent slot is not refunded
    assert outcome.usage.input_tokens == 28 and outcome.usage.output_tokens == 10
    assert outcome.usage.llm_calls == 2
    assert runtime._upstream_cancelled.cause == "hook"
    assert runtime._upstream_cancelled.detail == "storage_failed"
    assert store.writes_after_failure == 0
    assert len(store.child_ids) == 1
    events, _state = store.load(next(iter(store.child_ids)))
    assert bool([e for e in events if e.kind == "model_turn"]) == fail_after_write
    failed = next(e for e in outcome.events if e.kind == "branch_failed")
    assert failed.payload["persistence"] == "failed"
    from intelligence.services.episode_progress import project_episode_progress
    assert project_episode_progress(failed).status == "failed"
    assert "主研究继续" not in project_episode_progress(failed).message


def test_sibling_failure_between_parent_intent_and_model_dispatch_stops_model(tmp_path):
    from intelligence.runtime.agent_episode import ContinuousAgentEpisode
    from intelligence.services.agent_runtime import EpisodeEvent

    class Model:
        calls = 0

        def complete(self, **kwargs):
            self.calls += 1
            return ModelTurn(json.dumps({"status": "partial", "draft": "不应调用", "gaps": ["待查"], "bindings": []}), ())

    context = _context("max", allowed=("market_data",))
    store = FencedEpisodeStore(ObservedStore(tmp_path, fail_kind="task"))
    model = Model()
    episode = ContinuousAgentEpisode(model, store=store)
    try:
        drive = episode.manual_drive(task_frame=_frame(), context=context, registry=registry([]))
        assert drive.run_until("model_pending").phase == "model_pending"
        parent_prefix = store.load(context.contract.task_id)
        with pytest.raises(OSError):
            store.append("branches-sibling", (EpisodeEvent(1, "task", {}),))
        # Parent has not attempted another write. Its health must still reflect
        # the child's failure before dispatch, not only after a store rejection.
        assert store.load(context.contract.task_id) == parent_prefix
        outcome = drive.run_to_end()
        assert model.calls == 0 and outcome.usage.llm_calls == 0
        assert outcome.persistence == "failed"
        assert store.load(context.contract.task_id) == parent_prefix
    finally:
        release_root_budget(context.contract.task_id)


def test_parent_branch_start_ack_failure_starts_no_child(tmp_path):
    store = ObservedStore(tmp_path, fail_kind="branch_started", fail_child=False, fail_after_write=True)
    outcome, model, executed, _spent, _runtime = run_tree(store)
    assert outcome.persistence == "failed"
    assert model.parent_calls == 1 and model.child_calls == 0 and executed == []
    assert store.child_ids == set() and store.writes_after_failure == 0
    assert len([e for e in outcome.events if e.kind == "branch_started"]) == 1


def test_parent_batch_drains_received_child_result_inside_existing_window(tmp_path, monkeypatch):
    from concurrent.futures import FIRST_COMPLETED, ALL_COMPLETED, wait as real_wait
    from intelligence.runtime import episode_tool_batch, sub_research
    from intelligence.services.query_ledger import query_ledger_scope

    store = ObservedStore(tmp_path, fail_kind="model_turn")
    release_settlement = Event()
    drained_timeouts = []
    run_one = sub_research.SubResearchCoordinator._run_one

    def delayed_settlement(self, request):
        result = run_one(self, request)
        assert release_settlement.wait(3), "parent skipped the bounded branch drain"
        return result

    def controlled_wait(futures, *, timeout, return_when=ALL_COMPLETED):
        if return_when == FIRST_COMPLETED:
            assert store.failed.wait(3)
            return set(), set(futures)
        drained_timeouts.append(timeout)
        release_settlement.set()
        return real_wait(futures, timeout=timeout, return_when=return_when)

    monkeypatch.setattr(sub_research.SubResearchCoordinator, "_run_one", delayed_settlement)
    monkeypatch.setattr(episode_tool_batch, "wait", controlled_wait)
    with query_ledger_scope() as queries:
        outcome, model, _executed, _spent, _runtime = run_tree(store)
        assert queries.entries == {}  # failed results stay private, not cached
    assert drained_timeouts and 0 <= drained_timeouts[0] <= 540
    assert model.child_calls == 1 and outcome.usage.llm_calls == 2
    assert outcome.usage.input_tokens == 28
    assert any(e.kind == "branch_failed" for e in outcome.events)


@pytest.mark.parametrize("storage_failure", [False, True])
def test_child_beyond_parent_window_cannot_change_parent_events_or_evidence(tmp_path, monkeypatch, storage_failure):
    from concurrent.futures import FIRST_COMPLETED, ALL_COMPLETED, ThreadPoolExecutor, wait as real_wait
    from threading import current_thread, main_thread
    import time
    from intelligence.runtime import episode_tool_batch
    from intelligence.runtime.continuous_sub_research import ContinuousSubResearchWorker
    from intelligence.services.query_ledger import query_ledger_scope

    store = ObservedStore(tmp_path, fail_kind="model_turn" if storage_failure else "")
    ready, release = Event(), Event()
    captured = []
    clock = [time.monotonic()]
    original = ContinuousSubResearchWorker.run

    def late_worker(self, request):
        result = original(self, request)
        captured.append(request)
        ready.set()
        assert release.wait(5)
        # Simulate a received atom delivered only after the parent window closed.
        return replace(result, evidence=(AgentEvidence(
            tool="market_data", title="迟到事实", detail="不得改父账", source="fixture",
            source_date="2026-07-21", content_hash="late-atom",
        ),))

    def elapsed_wait(futures, *, timeout, return_when=ALL_COMPLETED):
        if current_thread() is not main_thread():
            return real_wait(futures, timeout=timeout, return_when=return_when)
        if return_when == FIRST_COMPLETED:
            assert ready.wait(3)
            clock[0] += 600  # deterministic expiry, not a sleep/race bet
        else:
            assert timeout == 0  # drain must not mint time after cutoff
        return set(), set(futures)

    pool = ThreadPoolExecutor(max_workers=3)
    monkeypatch.setattr(episode_tool_batch, "_SHARED_TOOL_EXECUTOR", pool)
    monkeypatch.setattr(episode_tool_batch, "monotonic", lambda: clock[0])
    monkeypatch.setattr(episode_tool_batch, "wait", elapsed_wait)
    monkeypatch.setattr(ContinuousSubResearchWorker, "run", late_worker)
    try:
        with query_ledger_scope() as queries:
            outcome, _model, _executed, _spent, runtime = run_tree(store)
            ledger = runtime._episode.inbox._ledger
            parent_id = captured[0].episode_ref.parent_episode_id
            before = (tuple(ledger.events), captured[0].evidence_sink.snapshot(), store.load(parent_id), outcome.to_dict())
            release.set()
            pool.shutdown(wait=True)
            after = (tuple(ledger.events), captured[0].evidence_sink.snapshot(), store.load(parent_id), outcome.to_dict())
            assert after == before
            assert not any(e.kind in {"branch_completed", "branch_failed"} for e in ledger.events)
            assert not any(key[0] == "generic:sub_research" for key in queries.entries)
            error = "storage_failed_inflight" if storage_failure else "tool_timeout"
            assert any(e.kind == "tool_error" and e.payload["error"] == error for e in outcome.events)
    finally:
        release.set()
        pool.shutdown(wait=True)


def test_failed_child_fences_an_already_inflight_sibling_without_losing_responses(tmp_path):
    sibling_entered = Event()
    store = ObservedStore(tmp_path, fail_kind="model_turn")

    def wait_for_failure(messages):
        if "核验乙" in str(messages[1]["content"]):
            sibling_entered.set()
            assert store.failed.wait(3), "first child never failed"
        else:
            # Wait at model IO, never while holding the store's write lock.
            assert sibling_entered.wait(3), "sibling never entered model"

    outcome, model, executed, _spent, runtime = run_tree(
        store, goals=("核验甲", "核验乙"), before_child=wait_for_failure,
    )
    assert outcome.persistence == "failed"
    assert model.parent_calls == 1 and model.child_calls == 2
    assert executed == [] and outcome.usage.llm_calls == 3
    assert outcome.usage.input_tokens == 39 and outcome.usage.output_tokens == 17
    assert len([e for e in outcome.events if e.kind == "branch_failed"]) == 2
    assert runtime._upstream_cancelled.cause == "hook"
    assert store.writes_after_failure == 0


def test_child_tool_result_saved_then_failed_is_retained_privately(tmp_path):
    store = ObservedStore(tmp_path, fail_kind="tool_result", fail_after_write=True)
    outcome, model, executed, spent, _runtime = run_tree(store)
    assert outcome.persistence == "failed" and outcome.status == "failed"
    assert model.parent_calls == 1 and model.child_calls == 1
    assert len(executed) == 1 and spent == 2 and outcome.usage.tool_calls == 2
    assert len(outcome.evidence) == 1
    assert outcome.evidence[0].source_date == "2026-07-21"
    events, _ = store.load(next(iter(store.child_ids)))
    assert events[-1].kind == "tool_result"
    assert store.writes_after_failure == 0


def test_queued_sibling_is_not_started_after_child_storage_failure(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from intelligence.runtime import sub_research

    def serial_executor(**kwargs):
        return ThreadPoolExecutor(**{**kwargs, "max_workers": 1})

    monkeypatch.setattr(sub_research, "ThreadPoolExecutor", serial_executor)
    store = ObservedStore(tmp_path, fail_kind="model_turn")
    outcome, model, executed, _spent, _runtime = run_tree(store, goals=("核验甲", "核验乙"))
    assert outcome.persistence == "failed"
    assert model.child_calls == 1 and model.parent_calls == 1 and executed == []
    failed = [e for e in outcome.events if e.kind == "branch_failed"]
    assert len(failed) == 2 and failed[1].payload["llm_calls"] == 0
    assert failed[1].payload["error"] == "storage_failed"
    assert len(store.child_ids) == 1  # sibling has a reference, not a fabricated log
    assert store.writes_after_failure == 0


def test_raw_store_coordinator_shares_one_fence_and_absolute_deadline(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from intelligence.runtime import sub_research
    from intelligence.services.agent_runtime import EpisodeEvent
    from intelligence.services.evidence_ledger import EvidenceLedger
    from intelligence.tests.test_sub_research import _context as branch_context, _frame as branch_frame

    store = ObservedStore(tmp_path, fail_kind="task")
    context = branch_context()
    captured = []

    class Worker:
        def run(self, request):
            captured.append(request)
            assert request.context.deadline.expires_at <= context.deadline.expires_at - context.deadline.synthesis_reserve
            request.episode_store.append(request.episode_ref.episode_id, (EpisodeEvent(1, "task", {}),))
            raise AssertionError("store must fail first")

    monkeypatch.setattr(sub_research, "ThreadPoolExecutor", lambda **kw: ThreadPoolExecutor(**{**kw, "max_workers": 1}))
    result = sub_research.SubResearchCoordinator(Worker()).run(
        goals=("甲", "乙"), task_frame=branch_frame(), context=context,
        registry=registry([]), evidence_sink_factory=EvidenceLedger().branch_sink, episode_store=store,
    )
    assert len(captured) == 1
    assert isinstance(captured[0].episode_store, FencedEpisodeStore)
    assert all(b.persistence == "failed" and b.error == "storage_failed" for b in result.branches)
    assert result.branches[1].llm_calls == 0
    assert store.writes_after_failure == 0


def test_child_deadline_intersects_parent_even_after_admission_delay(monkeypatch):
    from intelligence.runtime.sub_research import SubResearchCoordinator
    from intelligence.services import research_contract
    from intelligence.services.evidence_ledger import EvidenceLedger
    from intelligence.tests.test_sub_research import _context as branch_context, _frame as branch_frame

    context = replace(branch_context(), deadline=research_contract.ResearchDeadline(100.0, 10.0))
    monkeypatch.setattr(research_contract.time, "monotonic", lambda: 80.0)
    request = SubResearchCoordinator(None)._request(
        index=1, goal="核验甲", task_frame=branch_frame(), context=context, registry=registry([]),
        evidence_sink_factory=EvidenceLedger().branch_sink, root=context.root_budget,
        calls=1, seconds=60.0,  # the earlier admission grant is stale by dispatch
    )
    assert request.context.deadline.expires_at == 90.0


def test_tool_result_scope_expiry_and_close_are_independent_of_thread_return():
    from intelligence.runtime.tool_result_scope import ToolResultScope
    clock = [1.0]
    scope = ToolResultScope(2.0, lambda: clock[0])
    with scope.accepting() as accepted:
        assert accepted
    clock[0] = 3.0
    with scope.accepting() as accepted:
        assert not accepted
    clock[0] = 1.0
    scope.close()
    with scope.accepting() as accepted:
        assert not accepted


def test_parent_storage_failure_fences_both_inflight_children(tmp_path):
    from threading import Barrier
    context = _context("max", allowed=("market_data", "sub_research"))
    store = ObservedStore(tmp_path, fail_kind="inbox_inserted", fail_child=False)
    entered = Barrier(2, timeout=3)

    def fail_parent(messages):
        entered.wait()
        if "核验甲" in str(messages[1]["content"]):
            assert not runtime.steer("补充研究约束").accepted
        else:
            assert store.failed.wait(3)

    model = TreeModel(store, context.contract.task_id, goals=("核验甲", "核验乙"), before_child=fail_parent)
    runtime = GLMAgentRuntime(client=model, episode_store=store)
    executed = []
    try:
        outcome = runtime.run(task_frame=_frame(), context=context, registry=registry(executed))
    finally:
        release_root_budget(context.contract.task_id)
    assert outcome.persistence == "failed" and model.parent_calls == 1
    assert model.child_calls == 2 and executed == []
    assert outcome.usage.llm_calls == 3 and outcome.usage.input_tokens == 39
    assert len([e for e in outcome.events if e.kind == "branch_failed"]) == 2
    assert store.writes_after_failure == 0


def test_ephemeral_children_remain_explicitly_ephemeral():
    from intelligence.runtime.continuous_sub_research import ContinuousSubResearchWorker
    from intelligence.runtime.sub_research import SubResearchCoordinator
    from intelligence.services.evidence_ledger import EvidenceLedger
    from intelligence.tests.test_sub_research import _context as branch_context, _frame as branch_frame

    class PartialModel:
        def complete(self, **kwargs):
            return ModelTurn(json.dumps({"status": "partial", "draft": "仍缺证据", "gaps": ["待查"], "bindings": []}), ())

    result = SubResearchCoordinator(ContinuousSubResearchWorker(PartialModel())).run(
        goals=("核验甲",), task_frame=branch_frame(), context=branch_context(),
        registry=registry([]), evidence_sink_factory=EvidenceLedger().branch_sink,
    )
    assert result.branches[0].persistence == "ephemeral"
    assert result.branches[0].episode_ref is not None


def test_child_scope_suppresses_real_glm_client_draft_stream_without_muting_parent(tmp_path):
    from intelligence.runtime.glm_agent_runtime import GLMModelClient
    from intelligence.services.cancel_signal import CancelSignal

    store = ObservedStore(tmp_path)
    context = _context("max", allowed=("market_data", "sub_research"))
    script = TreeModel(store, context.contract.task_id)
    public_deltas = []
    streamed_calls = []

    def complete(**kwargs):
        turn = script.complete(messages=kwargs["messages"], tools=kwargs["tools"], timeout=kwargs["timeout"])
        stream = kwargs.get("on_content_delta")
        if stream is not None:
            streamed_calls.append(turn.content)
            stream(turn.content)
        calls = [{"id": c.call_id, "type": "function", "function": {
            "name": c.name, "arguments": json.dumps(dict(c.arguments), ensure_ascii=False),
        }} for c in turn.tool_calls]
        return {"content": turn.content, "tool_calls": calls, "_finish_reason": "tool_calls" if calls else "stop"}, "fixture", ""

    cancel = CancelSignal()
    client = GLMModelClient(complete_fn=complete, is_cancelled=cancel, on_draft_delta=public_deltas.append)
    try:
        outcome = GLMAgentRuntime(client=client, is_cancelled=cancel, episode_store=store).run(
            task_frame=_frame(), context=context, registry=registry([]),
        )
    finally:
        release_root_budget(context.contract.task_id)
    assert outcome.persistence == "durable"
    assert "父稿" in "".join(public_deltas)
    assert "子稿不得公开" not in "".join(public_deltas)
    assert len(streamed_calls) == script.parent_calls == 2
    assert script.child_calls == 2


def test_cached_empty_branch_result_does_not_charge_child_usage_twice(tmp_path):
    from intelligence.services.query_ledger import query_ledger_scope
    context = _context("max", allowed=("market_data", "sub_research"))

    class Model:
        parent_calls = 0
        child_calls = 0

        def complete(self, *, messages, **kwargs):
            if "branch_findings" in json.dumps(messages[:2], ensure_ascii=False):
                self.child_calls += 1
                return ModelTurn(json.dumps({"status": "partial", "draft": "仍缺证据", "gaps": ["待查"], "bindings": []}), (), input_tokens=11, output_tokens=7)
            self.parent_calls += 1
            if self.parent_calls <= 2:
                return ModelTurn("", (ModelToolCall(str(self.parent_calls), "sub_research", {"goals": ["同一问题"]}),), input_tokens=17, output_tokens=3)
            return ModelTurn(json.dumps({"status": "partial", "draft": "仍缺证据", "gaps": ["待查"], "bindings": []}), (), input_tokens=19, output_tokens=2)

    model = Model()
    try:
        with query_ledger_scope() as queries:
            outcome = GLMAgentRuntime(client=model, episode_store=ObservedStore(tmp_path)).run(
                task_frame=_frame(), context=context, registry=registry([]),
            )
            cached = next(v for k, v in queries.entries.items() if k[0] == "generic:sub_research")
            assert cached.reuse_count == 1
    finally:
        release_root_budget(context.contract.task_id)
    assert model.parent_calls == 3 and model.child_calls == 1
    assert outcome.usage.llm_calls == 4 and outcome.usage.input_tokens == 64
    assert len([e for e in outcome.events if e.kind == "branch_started"]) == 1


def test_failure_callbacks_are_outside_the_store_lock(tmp_path):
    from intelligence.services.agent_runtime import EpisodeEvent
    store = FencedEpisodeStore(ObservedStore(tmp_path, fail_kind="task", fail_child=False))
    joined = []

    def callback():
        # A foreign thread can read health while this callback is running.
        observed = []
        thread = Thread(target=lambda: observed.append(store.failure))
        thread.start()
        thread.join(2)
        joined.append(not thread.is_alive() and bool(observed))

    store.on_failure(lambda: (_ for _ in ()).throw(ValueError("broken observer")))
    store.on_failure(callback)
    with pytest.raises(OSError):
        store.append("parent", (EpisodeEvent(1, "task", {}),))
    assert joined == [True]


@pytest.mark.parametrize("fail_start", [False, True])
def test_plan_branches_share_the_same_store_and_start_ack_fence(tmp_path, fail_start):
    store = ObservedStore(tmp_path, fail_kind="branch_started" if fail_start else "", fail_child=False)
    outcome, model, executed, _spent, _runtime = run_tree(store, plan=True)
    start = next(e for e in outcome.events if e.kind == "branch_started")
    ref = dict(start.payload["episode_ref"])
    assert ref["origin"] == "plan"
    if fail_start:
        assert outcome.persistence == "failed"
        assert model.parent_calls == 1 and model.child_calls == 0 and executed == []
    else:
        assert outcome.persistence == "durable"
        events, state = JsonlEpisodeStore(tmp_path).load(ref["episode_id"])
        assert state.terminal and dict(events[0].payload["branch_parent"]) == ref
        assert model.child_calls == 2 and len(executed) == 1


@pytest.mark.parametrize("ref_key", ["parent_episode_id", "episode_id"])
def test_linked_nonterminal_restore_refuses_without_mutating_logs(tmp_path, monkeypatch, ref_key):
    from datetime import datetime, timedelta
    from intelligence.runtime.agent_episode import _EpisodeLedger
    from intelligence.services.episode_authorization import validate_current_authorization
    from intelligence.services.episode_restore import RestoreUnavailable, restore_episode

    prefixes = {}
    store = ObservedStore(tmp_path)
    put_state = _EpisodeLedger.put_state

    def capture(ledger, **kwargs):
        state = put_state(ledger, **kwargs)
        if not state.terminal:
            # Retain the live caller inputs separately. Never self-authorize by
            # reconstructing context/registry from the saved declaration.
            current = kwargs.get("context") or ledger.active_context
            prefixes[ledger.episode_id] = (store.load(ledger.episode_id), current, ledger.active_registry)
        return state

    monkeypatch.setattr(_EpisodeLedger, "put_state", capture)
    outcome, _model, _executed, _spent, _runtime = run_tree(store)
    assert outcome.persistence == "durable"
    ref = dict(next(e for e in outcome.events if e.kind == "branch_started").payload["episode_ref"])
    episode_id = ref[ref_key]
    # Actual checkpoint prefix and separately retained authority. Otherwise the
    # later authorization gate masks removal of the linked-tree protection.
    (prefix, state), context, bound_registry = prefixes[episode_id]
    assert context is not None and bound_registry is not None
    assert len(prefix) == state.last_sequence
    validate_current_authorization(state.authorization_snapshot, context=context, registry=bound_registry)
    snapshot = MemoryEpisodeStore()
    snapshot.append(episode_id, prefix)
    snapshot.put_state(episode_id, state)
    before = snapshot.load(episode_id)
    with pytest.raises(RestoreUnavailable, match="child reconciliation"):
        restore_episode(
            episode_id, snapshot, context=context, registry=bound_registry,
            now=datetime.fromisoformat(state.deadline_at) - timedelta(seconds=1),
        )
    assert snapshot.load(episode_id) == before


def test_sub_research_is_not_blindly_replayable_after_an_interruption(tmp_path):
    from intelligence.services.research_tool_registry import sub_research_tool_spec
    assert sub_research_tool_spec(lambda *_: None).replay == "never"
    store = ObservedStore(tmp_path)
    outcome, _model, _executed, _spent, _runtime = run_tree(store)
    intent = next(e for e in outcome.events if e.kind == "tool_request")
    assert intent.payload["name"] == "sub_research" and intent.payload["replay"] == "never"


def test_fenced_store_preserves_optional_spool_and_read_only_diagnostics(tmp_path):
    from intelligence.services.agent_runtime import EpisodeEvent
    disk = ObservedStore(tmp_path, fail_kind="task", fail_child=False)
    fenced = FencedEpisodeStore(disk)
    assert spool_dir_for(fenced, "parent") == disk.episode_dir("parent") / "inbox-spool"
    assert spool_dir_for(FencedEpisodeStore(MemoryEpisodeStore()), "parent") is None
    with pytest.raises(OSError):
        fenced.append("parent", (EpisodeEvent(1, "task", {}),))
    with pytest.raises(EpisodeStoreFailed):
        fenced.append("sibling", (EpisodeEvent(1, "task", {}),))
    assert fenced.load("parent") == ((), None)
    assert disk.writes_after_failure == 0
    other = FencedEpisodeStore(MemoryEpisodeStore())
    other.append("unrelated", (EpisodeEvent(1, "task", {}),))
    assert not other.failure  # the fence is per tree, never process global
