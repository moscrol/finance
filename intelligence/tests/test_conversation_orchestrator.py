import io
import json
import time
import urllib.error
from collections.abc import Callable
from dataclasses import asdict, replace
from threading import BoundedSemaphore, Event, Thread, current_thread

import pytest

from intelligence import userspace
from intelligence.services import llm_refine
from intelligence.services import perspective_lab
from intelligence.services import conversation_orchestrator as orchestrator_module
from intelligence.services.ask import AskOptions, AskResult
from intelligence.services.conversation_orchestrator import (
    ConversationContext,
    TurnOrchestrator,
    build_conversation_context,
    contextualize_follow_up_query,
    sanitize_conversation_answer,
    sanitize_user_visible_artifact_text,
)
from intelligence.services.conversation_store import ConversationStore
from intelligence.services.execution_budget import ExecutionBudget
from intelligence.services.query_understanding import QueryEnvelope
from intelligence.services.run_store import RunStore
from intelligence.services.runtime_inputs import RuntimeResearchInputs
from intelligence.workbench_skills.contracts import (
    SkillDefinition,
    SkillExecutionContext,
    SkillOutput,
    build_module_answer_contract,
)
from intelligence.workbench_skills.registry import (
    SkillRegistry,
    builtin_skill_registry,
)
from intelligence.workbench_skills.router import (
    SkillRouteResult,
    SkillSelection,
    route_skills,
)


class _FixedBudget:
    def __init__(self, remaining: float) -> None:
        self.remaining = remaining
        self.child_calls: list[tuple[float, float]] = []

    def remaining_seconds(self, now: float | None = None) -> float:
        return self.remaining

    def child_timeout(
        self,
        requested: float,
        reserve: float = 0,
        now: float | None = None,
    ) -> float:
        self.child_calls.append((requested, reserve))
        return min(requested, max(0.0, self.remaining - reserve))

    def exhausted(self, now: float | None = None) -> bool:
        return self.remaining <= 0


def _ask_result(
    query: str,
    *,
    synthesis: str | None = None,
    llm_provider: str | None = None,
    llm_attempted: bool | None = None,
    llm_fallback_reason: str | None = None,
) -> AskResult:
    return AskResult(
        query=query,
        trade_date="2026-07-11",
        matched_theme="测试题材",
        candidate_tier="A",
        priority_score=1.0,
        sections={"结论": [f"本轮检索：{query}"], "引用来源": ["[S1] fixture"]},
        found_market=True,
        synthesis=synthesis,
        llm_attempted=(
            llm_provider is not None
            if llm_attempted is None
            else llm_attempted
        ),
        llm_provider=llm_provider,
        llm_fallback_reason=llm_fallback_reason,
    )


def _prepare_turn(
    conversation_store: ConversationStore,
    run_store: RunStore,
    conversation_id: str,
    query: str,
    *,
    selected_skill_ids: list[str] | None = None,
) -> tuple[str, str]:
    conversation = conversation_store.load_conversation(conversation_id)
    run = run_store.create_run(
        query,
        "ask",
        session_id=conversation_id,
        parent_run_id=conversation.last_run_id,
    )
    conversation_store.append_message(
        conversation_id,
        "user",
        query,
        run_id=run.run_id,
        selected_skill_ids=selected_skill_ids,
    )
    assistant = conversation_store.append_message(
        conversation_id,
        "assistant",
        "",
        status="pending",
        run_id=run.run_id,
    )
    conversation_store.update_summary(
        conversation_id,
        conversation.summary,
        last_run_id=run.run_id,
    )
    return run.run_id, assistant.message_id


def test_three_turns_retrieve_fresh_and_include_bounded_context(tmp_path) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation("三轮测试")
    calls: list[AskOptions] = []
    runtime_inputs = RuntimeResearchInputs.from_roots(
        code_root=tmp_path / "code-worktree",
        data_root=tmp_path / "canonical-data",
        users_root=tmp_path / "users",
        knowledge_wiki=tmp_path / "knowledge" / "wiki",
        vector_index_dir=tmp_path / "knowledge" / ".rag_index",
    )

    def answer_spy(options: AskOptions) -> AskResult:
        calls.append(options)
        return _ask_result(options.query)

    parent_run_id = None
    run_ids: list[str] = []
    for query in ("第一轮：液冷怎么样？", "第二轮：证据够硬吗？", "第三轮：下一步看什么？"):
        run_id, assistant_message_id = _prepare_turn(
            conversation_store, run_store, conversation.conversation_id, query
        )
        TurnOrchestrator(
            repo_root=runtime_inputs.code_root,
            runtime_inputs=runtime_inputs,
            conversation_store=conversation_store,
            run_store=run_store,
            answer_query_fn=answer_spy,
            skill_registry=SkillRegistry(),
        ).run_turn(
            conversation_id=conversation.conversation_id,
            run_id=run_id,
            assistant_message_id=assistant_message_id,
            query=query,
            skill_mode="auto",
            selected_skill_ids=[],
        )
        run = run_store.load_run(run_id)
        assert run.session_id == conversation.conversation_id
        assert run.parent_run_id == parent_run_id
        parent_run_id = run_id
        run_ids.append(run_id)

    assert [call.query for call in calls] == [
        "第一轮：液冷怎么样？",
        "第二轮：证据够硬吗？",
        "第三轮：下一步看什么？",
    ]
    assert len(calls) == 3
    assert calls[0].perspective_mode == "neutral"
    assert calls[0].perspective_ids == ()
    assert calls[0].include_memory_block is True
    assert calls[0].include_recall_block is True
    assert calls[0].market_db_path == runtime_inputs.market_db_path
    assert calls[0].exports_dir == runtime_inputs.exports_dir
    assert calls[0].kb_wiki == runtime_inputs.knowledge_wiki
    assert calls[0].wiki_rag_index_dir == runtime_inputs.vector_index_dir
    assert "较早消息摘要" in calls[1].conversation_context
    assert "第一轮：液冷怎么样？" in calls[1].conversation_context
    assert "第二轮：证据够硬吗？" not in calls[1].conversation_context
    assert "第一轮：液冷怎么样？" in calls[2].conversation_context
    assert "第二轮：证据够硬吗？" in calls[2].conversation_context
    assert [run_store.load_run(run_id).status for run_id in run_ids] == [
        "completed",
        "completed",
        "completed",
    ]
    assistant = conversation_store.load_messages(conversation.conversation_id)[-1]
    assert assistant.content.startswith("当前视角：数据中立")


def test_turn_shares_one_sixty_second_budget_with_router_skill_and_ask(
    tmp_path,
) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "预算透传",
        selected_skill_ids=["fixture"],
    )
    budget = ExecutionBudget.start(60)
    routed_budgets: list[object] = []
    skill_budgets: list[object] = []
    ask_budgets: list[object] = []

    def budget_factory() -> ExecutionBudget:
        return budget

    def route_spy(*args: object, **kwargs: object) -> SkillRouteResult:
        routed_budgets.append(kwargs["execution_budget"])
        assert kwargs["llm_timeout"] <= 5
        return SkillRouteResult(
            (SkillSelection("fixture", "manual", "fixture"),),
            fallback_to_ask=False,
        )

    class CaptureSkill:
        skill_id = "fixture"

        def execute(self, context: SkillExecutionContext) -> SkillOutput:
            skill_budgets.append(context.execution_budget)
            return SkillOutput(skill_id=self.skill_id)

    registry = SkillRegistry()
    registry.register(
        SkillDefinition(
            skill_id="fixture",
            name="Fixture",
            description="fixture",
            version="1.0.0",
            triggers=(),
            input_schema={"type": "object"},
            permissions=("local_read",),
            timeout_seconds=10,
        ),
        CaptureSkill(),
    )

    def answer_spy(options: AskOptions) -> AskResult:
        ask_budgets.append(options.execution_budget)
        return _ask_result(options.query)

    TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=answer_spy,
        route_skills_fn=route_spy,
        skill_registry=registry,
        budget_factory=budget_factory,
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="预算透传",
        skill_mode="manual",
        selected_skill_ids=["fixture"],
    )

    assert budget.deadline_at - budget.started_at == pytest.approx(60.0)
    assert routed_budgets == [budget]
    assert skill_budgets == [budget]
    assert ask_budgets == [budget]


def test_turn_work_seconds_reserves_terminalization_window() -> None:
    assert orchestrator_module._turn_work_seconds(60) == 55.0
    assert orchestrator_module._turn_work_seconds(3) == 1.0


def test_default_turn_budget_excludes_terminalization_reserve(tmp_path) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "默认预算",
    )
    captured_budgets: list[object] = []

    def route_spy(*args: object, **kwargs: object) -> SkillRouteResult:
        captured_budgets.append(kwargs["execution_budget"])
        return SkillRouteResult((), False, True)

    TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=lambda options: _ask_result(options.query),
        route_skills_fn=route_spy,
        skill_registry=SkillRegistry(),
        answer_deadline_seconds=60,
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="默认预算",
        skill_mode="auto",
        selected_skill_ids=[],
    )

    budget = captured_budgets[0]
    assert isinstance(budget, ExecutionBudget)
    assert budget.deadline_at - budget.started_at == pytest.approx(55.0)


def test_budget_exhaustion_degrades_to_nonempty_deterministic_answer(tmp_path) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "题材生命周期怎么看",
    )
    budget = _FixedBudget(2.5)
    captured: list[AskOptions] = []

    def answer_spy(options: AskOptions) -> AskResult:
        captured.append(options)
        return _ask_result(options.query)

    result = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=answer_spy,
        route_skills_fn=lambda *args, **kwargs: SkillRouteResult((), False, True),
        skill_registry=SkillRegistry(),
        budget_factory=lambda: budget,
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="题材生命周期怎么看",
        skill_mode="auto",
        selected_skill_ids=[],
    )

    assert result.status == "completed"
    assert result.content.strip()
    assert captured[0].use_wiki_rag is False
    assert captured[0].use_modules is False
    assert captured[0].compose is False
    assert captured[0].synthesize is False
    assert captured[0].execution_budget is budget
    assistant = conversation_store.load_messages(conversation.conversation_id)[-1]
    assert "workbench_time_budget_exhausted_template_answer" in assistant.degrades


def test_skill_is_not_submitted_when_budget_reserve_is_unavailable(tmp_path) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "预算不足",
        selected_skill_ids=["fixture"],
    )
    called = Event()

    class ForbiddenSkill:
        skill_id = "fixture"

        def execute(self, context: SkillExecutionContext) -> SkillOutput:
            called.set()
            raise AssertionError("budget-starved skill must not start")

    registry = SkillRegistry()
    registry.register(
        SkillDefinition(
            skill_id="fixture",
            name="Fixture",
            description="fixture",
            version="1.0.0",
            triggers=(),
            input_schema={"type": "object"},
            permissions=("local_read",),
            timeout_seconds=10,
        ),
        ForbiddenSkill(),
    )
    result = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=lambda options: _ask_result(options.query),
        route_skills_fn=lambda *args, **kwargs: SkillRouteResult(
            (SkillSelection("fixture", "manual", "fixture"),), False
        ),
        skill_registry=registry,
        budget_factory=lambda: _FixedBudget(19),  # type: ignore[return-value]
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="预算不足",
        skill_mode="manual",
        selected_skill_ids=["fixture"],
    )

    assert result.status == "completed"
    assert called.is_set() is False
    assistant = conversation_store.load_messages(conversation.conversation_id)[-1]
    assert assistant.invoked_skill_ids == []
    assert any("时间预算不足" in warning for warning in assistant.degrades)


def test_timed_out_skill_cannot_persist_artifact_after_turn_continues(tmp_path) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "慢技能",
        selected_skill_ids=["slow"],
    )
    release = Event()
    finished = Event()
    worker_daemon: list[bool] = []

    class SlowSkill:
        skill_id = "slow"

        def execute(self, context: SkillExecutionContext) -> SkillOutput:
            worker_daemon.append(current_thread().daemon)
            release.wait(timeout=1)
            context.run_store.add_artifact(
                context.run_id,
                "late.json",
                "{}",
                renderer="json",
                title="late",
            )
            finished.set()
            return SkillOutput(skill_id=self.skill_id)

    registry = SkillRegistry()
    registry.register(
        SkillDefinition(
            skill_id="slow",
            name="Slow",
            description="slow",
            version="1.0.0",
            triggers=(),
            input_schema={"type": "object"},
            permissions=("local_read",),
            timeout_seconds=1,
        ),
        SlowSkill(),
    )
    result = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=lambda options: _ask_result(options.query),
        route_skills_fn=lambda *args, **kwargs: SkillRouteResult(
            (SkillSelection("slow", "manual", "slow"),), False
        ),
        skill_registry=registry,
        budget_factory=lambda: _FixedBudget(25.01),  # type: ignore[return-value]
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="慢技能",
        skill_mode="manual",
        selected_skill_ids=["slow"],
    )
    release.set()

    assert result.status == "completed"
    assert finished.wait(timeout=1)
    assert worker_daemon == [True]
    assert not (run_store.run_dir(run_id) / "late.json").exists()
    assert all(
        artifact["path"] != "late.json"
        for artifact in run_store.load_run(run_id).artifacts
    )


def test_timed_out_owner_progress_is_revoked_before_late_callback(tmp_path) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "慢owner",
        selected_skill_ids=["owner"],
    )
    release = Event()
    finished = Event()

    class SlowOwnerSkill:
        skill_id = "owner"

        def execute(self, context: SkillExecutionContext) -> SkillOutput:
            assert context.progress_callback is not None
            context.progress_callback("synthesis", "running")
            release.wait(timeout=1)
            context.progress_callback("synthesis", "completed")
            finished.set()
            return SkillOutput(skill_id=self.skill_id)

    registry = SkillRegistry()
    registry.register(
        SkillDefinition(
            skill_id="owner",
            name="Owner",
            description="slow owner",
            version="1.0.0",
            triggers=(),
            input_schema={"type": "object"},
            permissions=("local_read",),
            timeout_seconds=1,
        ),
        SlowOwnerSkill(),
    )
    result = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=lambda options: _ask_result(options.query),
        route_skills_fn=lambda *args, **kwargs: SkillRouteResult(
            (SkillSelection("owner", "manual", "owner"),), False
        ),
        skill_registry=registry,
        budget_factory=lambda: _FixedBudget(25.05),  # type: ignore[return-value]
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="慢owner",
        skill_mode="manual",
        selected_skill_ids=["owner"],
    )
    before_release = [
        event
        for event in run_store.load_stream_events(run_id)
        if event["event_type"] == "stage.progress"
        and event["payload"]["stage"] == "synthesis"
    ]
    release.set()

    assert result.status == "completed"
    assert [event["payload"]["status"] for event in before_release] == [
        "running",
        "degraded",
    ]
    assert finished.wait(timeout=1)
    after_release = [
        event
        for event in run_store.load_stream_events(run_id)
        if event["event_type"] == "stage.progress"
        and event["payload"]["stage"] == "synthesis"
    ]
    assert after_release == before_release


def test_timed_out_owner_uses_fast_base_ask_without_repeating_research(
    tmp_path,
) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "深挖英维克",
        selected_skill_ids=["owner"],
    )
    release = Event()
    captured: list[AskOptions] = []
    budget = _FixedBudget(25.05)

    class BlockingOwner:
        skill_id = "owner"

        def execute(self, context: SkillExecutionContext) -> SkillOutput:
            release.wait(timeout=1)
            return SkillOutput(skill_id=self.skill_id)

    registry = SkillRegistry()
    registry.register(
        SkillDefinition(
            skill_id="owner",
            name="Owner",
            description="blocking owner",
            version="1.0.0",
            triggers=("深挖",),
            input_schema={"type": "object"},
            permissions=("local_read",),
            timeout_seconds=1,
        ),
        BlockingOwner(),
    )

    def answer_spy(options: AskOptions) -> AskResult:
        captured.append(options)
        return _ask_result(options.query)

    started = time.monotonic()
    result = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=answer_spy,
        route_skills_fn=lambda *args, **kwargs: SkillRouteResult(
            (SkillSelection("owner", "manual", "owner"),), False
        ),
        skill_registry=registry,
        budget_factory=lambda: budget,  # type: ignore[return-value]
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="深挖英维克",
        skill_mode="manual",
        selected_skill_ids=["owner"],
    )
    elapsed = time.monotonic() - started
    release.set()

    assert result.status == "completed"
    assert elapsed < 0.5
    assert len(captured) == 1
    assert captured[0].compose is True
    assert captured[0].synthesize is True
    assert captured[0].use_modules is False
    assert captured[0].use_wiki_rag is False
    assert (1, orchestrator_module.SKILL_RESERVE_SECONDS) in budget.child_calls
    assert (
        orchestrator_module.SYNTHESIS_RESERVE_SECONDS,
        orchestrator_module.FINALIZATION_RESERVE_SECONDS,
    ) in budget.child_calls
    run = run_store.load_run(run_id)
    assert run.status == "completed"
    assert "executor_timeout" not in run.degrades
    report = json.loads(
        (run_store.run_dir(run_id) / "report.json").read_text(encoding="utf-8")
    )
    assert report["status"] == "completed"
    assert any("执行超时" in warning for warning in report["warnings"])


def test_guard_stop_and_terminal_state_serialize_against_artifact_write(tmp_path) -> None:
    entered = Event()
    release = Event()

    class BlockingRunStore(RunStore):
        def add_artifacts_if_active(self, *args, **kwargs):
            entered.set()
            release.wait(timeout=1)
            return super().add_artifacts_if_active(*args, **kwargs)

    store = BlockingRunStore("alice", root=tmp_path / "runs")
    run = store.create_run("q", "ask")
    guard = orchestrator_module._SkillRunStoreGuard(store, lambda: False)
    guard.add_artifact(
        run.run_id,
        "racy.json",
        "{}",
        renderer="json",
        title="racy",
    )
    writer = Thread(target=guard.commit)
    stopper = Thread(target=guard.stop)
    writer.start()
    assert entered.wait(timeout=1)
    stopper.start()
    stopper.join(timeout=0.1)
    assert not stopper.is_alive()
    store.finish_run(run.run_id, "cancelled")
    release.set()
    writer.join(timeout=1)
    stopper.join(timeout=1)

    assert not writer.is_alive()
    assert not (store.run_dir(run.run_id) / "racy.json").exists()
    assert store.load_run(run.run_id).artifacts == []


def test_skill_guard_stages_in_memory_and_only_success_commit_touches_disk(
    tmp_path,
) -> None:
    store = RunStore("alice", root=tmp_path / "runs")
    run = store.create_run("q", "ask")
    guard = orchestrator_module._SkillRunStoreGuard(store, lambda: False)
    artifact = guard.add_artifact(
        run.run_id,
        "staged.json",
        "{}",
        renderer="json",
        title="staged",
    )

    assert artifact.sha256
    assert artifact.bytes == 2
    assert not (store.run_dir(run.run_id) / "staged.json").exists()
    assert guard.commit() is True
    assert (store.run_dir(run.run_id) / "staged.json").read_text() == "{}"


def test_skill_guard_stop_discards_staging_without_waiting_for_store_io(
    tmp_path,
) -> None:
    class ForbiddenStore(RunStore):
        def add_artifacts_if_active(self, *args, **kwargs):
            raise AssertionError("stopped staging must not touch disk")

    store = ForbiddenStore("alice", root=tmp_path / "runs")
    run = store.create_run("q", "ask")
    guard = orchestrator_module._SkillRunStoreGuard(store, lambda: False)
    guard.add_artifact(
        run.run_id,
        "discarded.json",
        "{}",
        renderer="json",
        title="discarded",
    )

    started = time.monotonic()
    guard.stop()

    assert time.monotonic() - started < 0.1
    assert guard.commit() is False
    assert not (store.run_dir(run.run_id) / "discarded.json").exists()


def test_skill_worker_capacity_exhaustion_skips_without_starting_thread(
    tmp_path, monkeypatch
) -> None:
    slots = BoundedSemaphore(1)
    assert slots.acquire(blocking=False)
    monkeypatch.setattr(orchestrator_module, "_SKILL_WORKER_SLOTS", slots)
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "容量耗尽",
        selected_skill_ids=["fixture"],
    )
    called = Event()

    class ForbiddenSkill:
        skill_id = "fixture"

        def execute(self, context: SkillExecutionContext) -> SkillOutput:
            called.set()
            return SkillOutput(skill_id=self.skill_id)

    registry = SkillRegistry()
    registry.register(
        SkillDefinition(
            skill_id="fixture",
            name="Fixture",
            description="fixture",
            version="1.0.0",
            triggers=(),
            input_schema={"type": "object"},
            permissions=("local_read",),
            timeout_seconds=1,
        ),
        ForbiddenSkill(),
    )
    try:
        result = TurnOrchestrator(
            repo_root=tmp_path,
            conversation_store=conversation_store,
            run_store=run_store,
            answer_query_fn=lambda options: _ask_result(options.query),
            route_skills_fn=lambda *args, **kwargs: SkillRouteResult(
                (SkillSelection("fixture", "manual", "fixture"),), False
            ),
            skill_registry=registry,
        ).run_turn(
            conversation_id=conversation.conversation_id,
            run_id=run_id,
            assistant_message_id=assistant_message_id,
            query="容量耗尽",
            skill_mode="manual",
            selected_skill_ids=["fixture"],
        )
    finally:
        slots.release()

    assert result.status == "completed"
    assert not called.is_set()
    assistant = conversation_store.load_messages(conversation.conversation_id)[-1]
    assert any("并发容量" in warning for warning in assistant.degrades)


def test_router_default_llm_gets_timeout_and_injected_one_arg_double_still_works(
    monkeypatch,
) -> None:
    registry = {
        "fixture": SkillDefinition(
            skill_id="fixture",
            name="Fixture",
            description="fixture",
            version="1.0.0",
            triggers=(),
            input_schema={"type": "object"},
            permissions=("local_read",),
            timeout_seconds=1,
        )
    }
    timeouts: list[int] = []

    def default_complete(messages: list[dict[str, str]], *, timeout: int):
        timeouts.append(timeout)
        return None, None, "fixture"

    monkeypatch.setattr(llm_refine, "complete", default_complete)
    route_skills("q", "ask", "auto", [], registry=registry, llm_timeout=4.9)
    injected_calls: list[list[dict[str, str]]] = []
    route_skills(
        "q",
        "ask",
        "auto",
        [],
        registry=registry,
        llm_timeout=2,
        llm_complete=lambda messages: (
            injected_calls.append(messages) and None,
            None,
            "fixture",
        ),
    )

    assert timeouts == [4]
    assert len(injected_calls) == 1


@pytest.mark.parametrize(
    ("llm_timeout", "budget"),
    [
        (0.0, _FixedBudget(60)),
        (5.0, _FixedBudget(0)),
    ],
)
def test_router_skips_llm_when_timeout_or_shared_budget_is_exhausted(
    llm_timeout: float,
    budget: _FixedBudget,
) -> None:
    calls = 0

    def forbidden_complete(messages: list[dict[str, str]]):
        nonlocal calls
        calls += 1
        return None, None, "must not run"

    result = route_skills(
        "q",
        "ask",
        "auto",
        [],
        registry={
            "fixture": SkillDefinition(
                skill_id="fixture",
                name="Fixture",
                description="fixture",
                version="1.0.0",
                triggers=("q",),
                input_schema={"type": "object"},
                permissions=("local_read",),
                timeout_seconds=1,
            )
        },
        llm_timeout=llm_timeout,
        execution_budget=budget,  # type: ignore[arg-type]
        llm_complete=forbidden_complete,
    )

    assert calls == 0
    assert [selection.skill_id for selection in result.selections] == ["fixture"]


@pytest.mark.parametrize(
    ("remaining", "expected_compose", "expected_timeout"),
    [
        (8.0, False, 1),
        (9.0, True, 4),
        (13.0, True, 8),
    ],
)
def test_generic_ask_reserves_finalization_time(
    tmp_path,
    remaining: float,
    expected_compose: bool,
    expected_timeout: int,
) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "预算边界",
    )
    budget = _FixedBudget(remaining)
    captured: list[AskOptions] = []

    def answer_spy(options: AskOptions) -> AskResult:
        captured.append(options)
        return _ask_result(options.query)

    TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=answer_spy,
        route_skills_fn=lambda *args, **kwargs: SkillRouteResult((), False, True),
        skill_registry=SkillRegistry(),
        budget_factory=lambda: budget,  # type: ignore[return-value]
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="预算边界",
        skill_mode="auto",
        selected_skill_ids=[],
    )

    options = captured[0]
    assert options.compose is expected_compose
    assert options.use_wiki_rag is expected_compose
    assert options.use_modules is expected_compose
    assert options.llm_timeout == expected_timeout
    allowance = budget.child_timeout(
        orchestrator_module.SYNTHESIS_RESERVE_SECONDS,
        reserve=orchestrator_module.FINALIZATION_RESERVE_SECONDS,
    )
    if expected_compose:
        assert options.llm_timeout <= allowance
    else:
        assistant = conversation_store.load_messages(conversation.conversation_id)[-1]
        assert "workbench_time_budget_exhausted_template_answer" in assistant.degrades


def test_turn_streams_collision_free_progress_with_public_payloads(tmp_path) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "液冷怎么看",
    )
    callbacks: list[Callable[[str, str], None]] = []

    def answer_spy(options: AskOptions) -> AskResult:
        assert options.progress_callback is not None
        callbacks.append(options.progress_callback)
        options.progress_callback("deterministic_recall", "running")
        options.progress_callback("deterministic_recall", "completed")
        options.progress_callback("evidence_gate", "running")
        options.progress_callback("evidence_gate", "completed")
        options.progress_callback("synthesis", "running")
        options.progress_callback("synthesis", "completed")
        return _ask_result(options.query, synthesis="阶段回答")

    TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=answer_spy,
        route_skills_fn=lambda *args, **kwargs: SkillRouteResult((), False, True),
        skill_registry=SkillRegistry(),
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="液冷怎么看",
        skill_mode="auto",
        selected_skill_ids=[],
    )

    events = [
        event
        for event in run_store.load_stream_events(run_id)
        if event["event_type"] == "stage.progress"
    ]
    assert [(event["payload"]["stage"], event["payload"]["status"]) for event in events] == [
        ("understanding", "running"),
        ("understanding", "completed"),
        ("deterministic_recall", "running"),
        ("deterministic_recall", "completed"),
        ("evidence_gate", "running"),
        ("evidence_gate", "completed"),
        ("synthesis", "running"),
        ("synthesis", "completed"),
    ]
    assert [event["event_id"] for event in events] == [
        f"stage:{event['payload']['stage']}:{index:02d}"
        for index, event in enumerate(events, start=1)
    ]
    assert all(set(event["payload"]) == {"stage", "status", "elapsed_ms"} for event in events)
    assert all(isinstance(event["payload"]["elapsed_ms"], int) for event in events)
    callbacks[0]("synthesis", "completed")
    assert len(
        [
            event
            for event in run_store.load_stream_events(run_id)
            if event["event_type"] == "stage.progress"
        ]
    ) == len(events)


def test_turn_degrades_a_running_stage_before_failure(tmp_path) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "失败边界",
    )

    def answer_spy(options: AskOptions) -> AskResult:
        assert options.progress_callback is not None
        options.progress_callback("synthesis", "running")
        raise RuntimeError("fixture")

    result = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=answer_spy,
        route_skills_fn=lambda *args, **kwargs: SkillRouteResult((), False, True),
        skill_registry=SkillRegistry(),
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="失败边界",
        skill_mode="auto",
        selected_skill_ids=[],
    )

    assert result.status == "failed"
    synthesis = [
        (event["payload"]["stage"], event["payload"]["status"])
        for event in run_store.load_stream_events(run_id)
        if event["event_type"] == "stage.progress"
        and event["payload"]["stage"] == "synthesis"
    ]
    assert synthesis == [
        ("synthesis", "running"),
        ("synthesis", "degraded"),
    ]


def test_progress_producers_track_the_same_stage_independently() -> None:
    events: list[tuple[str, str, int]] = []
    progress = orchestrator_module._TurnProgressEmitter(
        can_emit=lambda: True,
        emit_event=lambda stage, status, sequence: events.append(
            (stage, status, sequence)
        ),
    )
    first = progress.producer("skill:first")
    second = progress.producer("skill:second")

    first("semantic_recall", "running")
    second("semantic_recall", "running")
    first("semantic_recall", "completed")
    first.revoke()
    second.revoke()

    assert events == [
        ("semantic_recall", "running", 1),
        ("semantic_recall", "running", 2),
        ("semantic_recall", "completed", 3),
        ("semantic_recall", "degraded", 4),
    ]


def test_progress_producer_revoke_blocks_late_events_and_close_finishes_leftovers() -> None:
    events: list[tuple[str, str, int]] = []
    progress = orchestrator_module._TurnProgressEmitter(
        can_emit=lambda: True,
        emit_event=lambda stage, status, sequence: events.append(
            (stage, status, sequence)
        ),
    )
    timed_out = progress.producer("skill:owner")
    base = progress.producer("turn:base")
    timed_out("synthesis", "running")
    timed_out.revoke()
    timed_out("synthesis", "completed")
    base("deterministic_recall", "running")
    progress.close()
    base("deterministic_recall", "completed")

    assert events == [
        ("synthesis", "running", 1),
        ("synthesis", "degraded", 2),
        ("deterministic_recall", "running", 3),
        ("deterministic_recall", "degraded", 4),
    ]


def test_single_perspective_is_forwarded_and_labels_final_answer(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))

    perspective_lab.init_perspective(
        userspace.user_space("alice"),
        "fengyuan94",
        display_name="风远94",
        ptype="blogger",
    )
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "怎么看 AI 硬件",
    )
    calls: list[AskOptions] = []

    def answer_spy(options: AskOptions) -> AskResult:
        calls.append(options)
        return _ask_result(options.query)

    TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=answer_spy,
        skill_registry=SkillRegistry(),
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="怎么看 AI 硬件",
        skill_mode="auto",
        selected_skill_ids=[],
        perspective_mode="single",
        selected_perspective_ids=["fengyuan94"],
    )

    assert calls[0].perspective_mode == "single"
    assert calls[0].perspective_ids == ("fengyuan94",)
    assistant = conversation_store.load_messages(conversation.conversation_id)[-1]
    assert assistant.content.startswith("当前视角：风远94")


def test_context_keeps_six_recent_messages_and_summarizes_older(tmp_path) -> None:
    store = ConversationStore("alice", root=tmp_path)
    conversation = store.create_conversation()
    for index in range(10):
        store.append_message(
            conversation.conversation_id,
            "user" if index % 2 == 0 else "assistant",
            f"message-{index}",
            run_id=f"run-{index}",
        )

    context = build_conversation_context(
        conversation,
        store.load_messages(conversation.conversation_id),
        current_run_id="run-current",
    )

    assert [message.content for message in context.recent_messages] == [
        "message-4",
        "message-5",
        "message-6",
        "message-7",
        "message-8",
        "message-9",
    ]
    assert "message-0" in context.summary
    assert "message-3" in context.summary
    assert "message-4" not in context.summary


def test_contextualizes_pronoun_follow_up_with_previous_user_turn(tmp_path) -> None:
    store = ConversationStore("alice", root=tmp_path)
    conversation = store.create_conversation()
    previous = store.append_message(
        conversation.conversation_id,
        "user",
        "请个股深挖英维克的液冷业务",
        run_id="run-first",
    )
    context = ConversationContext(summary="", recent_messages=(previous,))

    assert contextualize_follow_up_query(
        "那它的主要风险和下一步验证是什么？",
        context,
    ) == (
        "请个股深挖英维克的液冷业务\n"
        "追问：那它的主要风险和下一步验证是什么？"
    )
    assert contextualize_follow_up_query("今天市场怎么样？", context) == (
        "今天市场怎么样？"
    )


def test_artifact_sanitizer_hides_credentials_paths_and_internal_terms() -> None:
    no_llm = sanitize_user_visible_artifact_text(
        "未配置 LLM key。设置 DEEPSEEK_API_KEY / HF_TOKEN 即可启用"
    )
    internal = sanitize_user_visible_artifact_text(
        "wiki-rag replay canonical ask_retrieval_pipeline deterministic_projection"
    )
    local_path = sanitize_user_visible_artifact_text(
        'File "/Users/a77/repo/module.py", line 12, in run'
    )
    retrieval_progress = sanitize_user_visible_artifact_text(
        "检索降级：Fetching 30 files: 100% | Loading weights: 100%"
    )
    internal_module = sanitize_user_visible_artifact_text(
        "模块·deep-dive（产业维 · radar.py --mode deep-dive 题材深拆）"
    )
    evidence_detail = sanitize_user_visible_artifact_text(
        "target=天阳科技 source=[[天阳科技_最新逻辑跟踪]]，质量 medium"
    )
    module_id = sanitize_user_visible_artifact_text("research_5_telemetry")
    no_llm_code = sanitize_user_visible_artifact_text(
        "llm_unavailable_template_answer"
    )
    answer_route = sanitize_user_visible_artifact_text(
        "answer-orchestrator：未高置信识别问题类型"
    )
    market_internals = sanitize_user_visible_artifact_text(
        "本地 DuckDB + snapshot/export；MarketAdapter.get_capacity_sectors；"
        "capacity_industry=True；来源=knowledge_evidence"
    )

    assert no_llm == "自然语言综合暂时不可用；已保留可核验数据与结构化产物。"
    assert "API_KEY" not in no_llm
    assert "TOKEN" not in no_llm
    assert "wiki-rag" not in internal
    assert "replay" not in internal
    assert "canonical" not in internal
    assert "ask_retrieval_pipeline" not in internal
    assert "deterministic_projection" not in internal
    assert "/Users/" not in local_path
    assert "module.py" not in local_path
    assert retrieval_progress == "外部语义检索当前不可用或受限，未使用其结果。"
    assert internal_module == "外部语义检索当前不可用或受限，未使用其结果。"
    assert evidence_detail == "对象=天阳科技；来源=天阳科技_最新逻辑跟踪，质量中等"
    assert module_id == "资料覆盖情况"
    assert no_llm_code == "自然语言综合暂时不可用；已保留可核验数据与结构化产物。"
    assert answer_route == "问题理解：未高置信识别问题类型"
    assert market_internals == (
        "本地市场数据 + 历史盘面快照；本地盘面数据；"
        "成交容量居前=是；来源=知识库候选资料"
    )


def test_market_question_automatically_selects_daily_review() -> None:
    registry = builtin_skill_registry()

    route = route_skills(
        "今天市场怎么样？",
        "ask",
        "auto",
        [],
        registry=registry.definitions,
        llm_complete=lambda _: (None, None, "fixture no llm"),
    )

    assert [selection.skill_id for selection in route.selections] == [
        "daily-review"
    ]


def test_turn_routes_with_query_envelope_and_records_it_in_trace(tmp_path) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    query = "指数上涨但涨停家数减少，是否背离？"
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        query,
    )
    routed: list[QueryEnvelope] = []

    def route_spy(
        routed_query: str,
        task_type: str,
        skill_mode: str,
        selected_skill_ids: list[str],
        *,
        registry: dict[str, SkillDefinition],
        query_envelope: QueryEnvelope,
        llm_timeout: float,
        execution_budget: ExecutionBudget,
    ) -> SkillRouteResult:
        assert routed_query == query
        assert task_type == "ask"
        assert skill_mode == "auto"
        assert selected_skill_ids == []
        assert registry == {}
        assert llm_timeout <= 5
        assert execution_budget.remaining_seconds() <= 60
        routed.append(query_envelope)
        return SkillRouteResult((), fallback_to_ask=False, base_finance_fallback=True)

    TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=lambda options: _ask_result(options.query),
        route_skills_fn=route_spy,
        skill_registry=SkillRegistry(),
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query=query,
        skill_mode="auto",
        selected_skill_ids=[],
    )

    assert len(routed) == 1
    assert routed[0].subject_kind == "market_pattern"
    route_step = next(
        step for step in run_store.load_trace(run_id) if step["name"] == "route_skills"
    )
    route_output = json.loads(route_step["output_summary"])
    assert route_output["query_envelope"] == routed[0].to_dict()


class _FailingSkill:
    skill_id = "broken"

    def execute(self, context: SkillExecutionContext) -> SkillOutput:
        raise RuntimeError("token=must-not-leak")


class _SuccessfulSkill:
    skill_id = "fixture"

    def execute(self, context: SkillExecutionContext) -> SkillOutput:
        return SkillOutput(
            skill_id=self.skill_id,
            modules=[
                {
                    "module_id": "fixture_metric",
                    "title": "Fixture metric",
                    "kind": "metrics",
                    "status": "complete",
                    "summary": None,
                    "content": None,
                    "metrics": [{"label": "涨家数", "value": 3210}],
                    "items": [],
                    "table": None,
                    "warnings": [],
                    "provenance": {
                        "source": "canonical-fixture",
                        "as_of": "2026-07-11",
                    },
                }
            ],
            citations=[
                {
                    "source": "canonical-fixture",
                    "evidence_layer": "canonical",
                }
            ],
            warnings=[],
            as_of="2026-07-11",
            raw_result_ref="fixture.json",
        )


def test_current_skill_output_is_injected_as_current_turn_evidence(tmp_path) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "结合日报回答",
        selected_skill_ids=["fixture"],
    )
    registry = SkillRegistry()
    registry.register(
        SkillDefinition(
            skill_id="fixture",
            name="Fixture",
            description="fixture",
            version="1.0.0",
            triggers=("日报",),
            input_schema={"type": "object"},
            permissions=("local_read",),
            timeout_seconds=1,
        ),
        _SuccessfulSkill(),
    )
    calls: list[AskOptions] = []

    def answer_spy(options: AskOptions) -> AskResult:
        calls.append(options)
        return _ask_result(options.query)

    TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=answer_spy,
        skill_registry=registry,
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="结合日报回答",
        skill_mode="manual",
        selected_skill_ids=["fixture"],
    )

    assert len(calls) == 1
    assert "指标：涨家数=3210" in calls[0].supplemental_evidence
    assert '"value": 3210' not in calls[0].supplemental_evidence
    assistant = conversation_store.load_messages(conversation.conversation_id)[-1]
    assert assistant.selected_skill_ids == ["fixture"]
    assert assistant.invoked_skill_ids == ["fixture"]
    assert assistant.citations[0]["evidence_layer"] == "canonical"


def test_skill_answer_owner_bypasses_generic_ask_and_renders_its_contract(
    tmp_path,
    monkeypatch,
) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "使用专项研究",
        selected_skill_ids=["owner"],
    )

    class OwnerSkill:
        skill_id = "owner"

        def execute(self, context: SkillExecutionContext) -> SkillOutput:
            modules = [
                {
                    "type": "summary",
                    "summary": "专项资料显示需求保持扩张",
                    "metrics": [{"label": "订单覆盖", "value": "80%"}],
                    "items": [
                        {
                            "title": "验证",
                            "summary": "仍需复核新增订单",
                            "next_action": "下一窗口复核新增订单。",
                        }
                    ],
                }
            ]
            citations = [
                {
                    "source": "owner.json",
                    "title": "专项正式资料",
                    "evidence_layer": "canonical",
                    "as_of": "2026-07-11",
                }
            ]
            contract = build_module_answer_contract(
                skill_id=self.skill_id,
                title="个股深挖",
                modules=modules,
                citations=citations,
                warnings=[],
                as_of="2026-07-11",
                retrieval_plan=("读取专项正式资料",),
                output_contract=("输出五元素裁决",),
            )
            assert contract is not None
            answer_spec = replace(
                contract.answer_spec,
                research_spec=replace(
                    contract.answer_spec.research_spec,
                    theme="英维克",
                ),
                presentation_title="个股深挖",
            )
            return SkillOutput(
                skill_id=self.skill_id,
                modules=modules,
                citations=citations,
                warnings=[],
                as_of="2026-07-11",
                raw_result_ref=None,
                answer_contract=replace(contract, answer_spec=answer_spec),
            )

    registry = SkillRegistry()
    registry.register(
        SkillDefinition(
            skill_id="owner",
            name="Owner",
            description="answer owner",
            version="1.0.0",
            triggers=("专项",),
            input_schema={"type": "object"},
            permissions=("local_read",),
            timeout_seconds=1,
        ),
        OwnerSkill(),
    )

    def forbidden_answer_query(options: AskOptions) -> AskResult:
        raise AssertionError("answer owner must bypass generic Ask")

    synthesis_calls = 0
    captured_prompt = ""

    def synthesize_once(messages, **kwargs):
        nonlocal captured_prompt, synthesis_calls
        synthesis_calls += 1
        captured_prompt = "\n".join(str(message["content"]) for message in messages)
        return (
            llm_refine.SynthesisResult(
                answer=(
                    "# 专项研究\n"
                    "**直接定性：** 需求保持扩张。\n"
                    "**最强证据：** 专项正式资料。\n"
                    "**主要风险：** 新增订单待复核。\n"
                    "**条件边界：** 仅限当前资料。\n"
                    "**下一步验证：** 下一窗口复核新增订单。（非投资建议）"
                ),
                provider="zhipu",
                model="glm-5.2",
            ),
            "",
        )

    monkeypatch.setattr(llm_refine, "detect_provider", lambda *_: object())
    monkeypatch.setattr(llm_refine, "synthesize_messages", synthesize_once)
    monkeypatch.setattr(
        "intelligence.services.ask.answer_model.validate_llm_answer",
        lambda *_: [],
    )

    result = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=forbidden_answer_query,
        skill_registry=registry,
        llm_configured=True,
        llm_model="glm-5.2",
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="使用专项研究",
        skill_mode="manual",
        selected_skill_ids=["owner"],
    )

    assert result.status == "completed"
    assert "# 专项研究" in result.content
    assert "**直接定性：**" in result.content
    assert "**最强证据：**" in result.content
    assert synthesis_calls == 1
    assert "命中主题：英维克" in captured_prompt
    assert "阶段判断：" in captured_prompt
    assistant = conversation_store.load_messages(conversation.conversation_id)[-1]
    assert "llm_unavailable_template_answer" not in assistant.degrades
    retrieval = next(
        step["retrieval"]
        for step in run_store.load_trace(run_id)
        if step["name"] == "ask_retrieve_compose"
    )
    assert retrieval["citations"][0]["source"] == "专项正式资料"
    assert retrieval["citation_counts"] == {"K": 1}


def test_skill_answer_owner_skips_provider_when_synthesis_budget_is_too_low(
    tmp_path,
    monkeypatch,
) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "预算不足的专项研究",
        selected_skill_ids=["owner"],
    )
    modules = [
        {
            "type": "summary",
            "summary": "保留确定性专项结论",
            "metrics": [{"label": "资料覆盖", "value": "80%"}],
            "items": [
                {
                    "title": "验证",
                    "summary": "仍需复核新增订单",
                    "next_action": "下一窗口复核新增订单。",
                }
            ],
        }
    ]
    citations = [
        {
            "source": "owner.json",
            "title": "专项正式资料",
            "evidence_layer": "canonical",
            "as_of": "2026-07-11",
        }
    ]

    class OwnerSkill:
        skill_id = "owner"

        def execute(self, context: SkillExecutionContext) -> SkillOutput:
            return SkillOutput(
                skill_id=self.skill_id,
                modules=modules,
                citations=citations,
                warnings=[],
                as_of="2026-07-11",
                raw_result_ref=None,
                answer_contract=build_module_answer_contract(
                    skill_id=self.skill_id,
                    title="专项研究",
                    modules=modules,
                    citations=citations,
                    warnings=[],
                    as_of="2026-07-11",
                    retrieval_plan=("读取专项正式资料",),
                    output_contract=("输出五元素裁决",),
                ),
            )

    registry = SkillRegistry()
    registry.register(
        SkillDefinition(
            skill_id="owner",
            name="Owner",
            description="answer owner",
            version="1.0.0",
            triggers=("专项",),
            input_schema={"type": "object"},
            permissions=("local_read",),
            timeout_seconds=1,
        ),
        OwnerSkill(),
    )

    class OwnerBudget(_FixedBudget):
        def child_timeout(
            self,
            requested: float,
            reserve: float = 0,
            now: float | None = None,
        ) -> float:
            if requested == 20 and reserve == 5:
                return 3.0
            return super().child_timeout(requested, reserve, now)

    def forbidden_synthesis(*args, **kwargs):
        raise AssertionError("budget exhausted owner must not call provider")

    monkeypatch.setattr(
        orchestrator_module,
        "synthesize_existing_answer_spec",
        forbidden_synthesis,
    )

    TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=lambda options: pytest.fail("owner must not retrieve again"),
        skill_registry=registry,
        llm_configured=True,
        llm_model="glm-5.2",
        budget_factory=lambda: OwnerBudget(60),
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="预算不足的专项研究",
        skill_mode="manual",
        selected_skill_ids=["owner"],
    )

    report = json.loads(
        (run_store.run_dir(run_id) / "report.json").read_text(encoding="utf-8")
    )
    assert report["llm"] == {
        "configured": True,
        "attempted": False,
        "used": False,
        "provider": None,
        "model": None,
        "fallback_reason": "budget_exhausted",
    }


def test_skill_failure_degrades_only_its_module_and_ask_still_completes(tmp_path) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "继续检索",
        selected_skill_ids=["broken"],
    )
    registry = SkillRegistry()
    registry.register(
        definition=SkillDefinition(
            skill_id="broken",
            name="Broken",
            description="fixture",
            version="1.0.0",
            triggers=("broken",),
            input_schema={"type": "object"},
            permissions=("local_read",),
            timeout_seconds=1,
        ),
        executor=_FailingSkill(),
    )

    TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=lambda options: _ask_result(options.query),
        skill_registry=registry,
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="继续检索",
        skill_mode="manual",
        selected_skill_ids=["broken"],
    )

    run = run_store.load_run(run_id)
    assistant = conversation_store.load_messages(conversation.conversation_id)[-1]
    skill_result = next(
        event
        for event in run_store.load_stream_events(run_id)
        if event["event_type"] == "skill.result"
    )
    assert run.status == "completed"
    assert assistant.status == "completed"
    assert assistant.invoked_skill_ids == ["broken"]
    assert any("broken" in warning for warning in assistant.degrades)
    assert "must-not-leak" not in json.dumps(asdict(assistant), ensure_ascii=False)
    assert skill_result["payload"]["status"] == "degraded"


def test_cooperative_cancellation_preserves_completed_skill_events(tmp_path) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store, run_store, conversation.conversation_id, "取消本轮"
    )
    cancelled = Event()

    def route_then_cancel(*args: object, **kwargs: object) -> SkillRouteResult:
        cancelled.set()
        return SkillRouteResult(
            selections=(SkillSelection("daily-review", "rule", "fixture"),),
            fallback_to_ask=False,
        )

    TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=lambda options: pytest.fail("取消后不应检索"),
        route_skills_fn=route_then_cancel,
        is_cancelled=cancelled.is_set,
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="取消本轮",
        skill_mode="auto",
        selected_skill_ids=[],
    )

    assistant = conversation_store.load_messages(conversation.conversation_id)[-1]
    assert run_store.load_run(run_id).status == "cancelled"
    assert assistant.status == "cancelled"
    assert any(
        event["event_type"] == "message.error"
        and event["payload"]["status"] == "cancelled"
        for event in run_store.load_stream_events(run_id)
    )


def test_template_answer_is_saved_and_streamed_once_without_llm(tmp_path) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "无 key 也要回答",
    )

    TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=lambda options: _ask_result(options.query),
        skill_registry=SkillRegistry(),
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="无 key 也要回答",
        skill_mode="auto",
        selected_skill_ids=[],
    )

    text_events = [
        event
        for event in run_store.load_stream_events(run_id)
        if event["event_type"] == "text.delta"
    ]
    run = run_store.load_run(run_id)
    assert len(text_events) == 1
    assert "自然语言综合暂时不可用" in text_events[0]["payload"]["delta"]
    assert "命中主题" not in text_events[0]["payload"]["delta"]
    assert [artifact["path"] for artifact in run.artifacts] == [
        "answer.md",
        "report.json",
    ]
    assert "llm_unavailable_template_answer" in run.degrades


def test_successful_llm_report_persists_selected_model(tmp_path) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "真实模型回答",
    )

    TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=lambda options: _ask_result(
            options.query,
            synthesis="真实模型输出",
            llm_provider="zhipu",
        ),
        skill_registry=SkillRegistry(),
        llm_configured=True,
        llm_model="glm-4-flash",
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="真实模型回答",
        skill_mode="auto",
        selected_skill_ids=[],
    )

    report = json.loads(
        (run_store.run_dir(run_id) / "report.json").read_text(encoding="utf-8")
    )
    assert report["llm"] == {
        "configured": True,
        "attempted": True,
        "used": True,
        "provider": "zhipu",
        "model": "glm-4-flash",
        "fallback_reason": None,
    }


def test_attempted_llm_fallback_persists_only_stable_reason(tmp_path) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "模型超时",
    )

    TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=lambda options: _ask_result(
            options.query,
            llm_attempted=True,
            llm_fallback_reason="provider_timeout",
        ),
        skill_registry=SkillRegistry(),
        llm_configured=True,
        llm_model="must-not-be-recorded",
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="模型超时",
        skill_mode="auto",
        selected_skill_ids=[],
    )

    report = json.loads(
        (run_store.run_dir(run_id) / "report.json").read_text(encoding="utf-8")
    )
    assert report["llm"] == {
        "configured": True,
        "attempted": True,
        "used": False,
        "provider": None,
        "model": None,
        "fallback_reason": "provider_timeout",
    }


def test_recovered_turn_prefixes_event_ids_to_avoid_replay_collisions(
    tmp_path,
) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "恢复后继续",
    )

    TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=lambda options: _ask_result(options.query),
        skill_registry=SkillRegistry(),
        event_id_prefix="recovery:2:",
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="恢复后继续",
        skill_mode="auto",
        selected_skill_ids=[],
    )

    events = run_store.load_stream_events(run_id)
    assert events
    assert all(
        event["event_id"].startswith("recovery:2:")
        for event in events
    )


def test_completed_stream_persists_human_readable_answer(tmp_path) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "今日复盘",
    )
    raw_answer = (
        "**数据截至 2026-07-10。**\n\n"
        "以下基于 Daily Review 确定性投影数据。盘面 L4 信号待确认，"
        "replay 发酵信号也未匹配到任何主题，wiki 向量检索无可用命中。"
        "公司只有 graph_only/低置信暴露，整体证据层分布为 "
        "L1×6、L2×6、L4×1，尚缺 L3 硬证据。[D4]"
        "本轮未命中任何 L3硬证据硬证据。优先走 L3 证据工具补查。"
        "本轮检索完全未命中任何 L3硬证据的硬证据。"
        "8 个被 daily-agent 标记需要补证据的方向。"
        "当前属于 high/L1_L3_candidate，L1/L2 认知完整但 "
        "分析基于 local Daily Review 确定性投影，知识图谱命中的概念。"
        "证据以 L1行业资料和 L2公司基础资料为主，也有 L2基础资料。"
        "未取到 L3公告/订单/认证/量产等硬证据，盘面 L4盘面信号待确认。"
        "当日日报指标来自本地数据库的确定性投影。"
        "cycle_status 仍需确认，RAG检索的wiki向量源降级未接入。"
    )

    def answer_spy(options: AskOptions) -> AskResult:
        assert options.stream_text_delta is not None
        options.stream_text_delta(raw_answer)
        return _ask_result(
            options.query,
            synthesis=raw_answer,
            llm_provider="zhipu",
        )

    TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=answer_spy,
        skill_registry=SkillRegistry(),
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="今日复盘",
        skill_mode="auto",
        selected_skill_ids=[],
    )

    assistant = conversation_store.load_messages(conversation.conversation_id)[-1]
    assert assistant.content == (
        "当前视角：数据中立\n"
        "来源范围：数据提供方、公开来源与本轮检索证据\n\n"
        f"{sanitize_conversation_answer(raw_answer)}"
    )
    assert "2026-07-10" in assistant.content
    assert "本地复盘数据" in assistant.content
    assert "历史发酵信号" in assistant.content
    assert "知识库没有提供可用补充" in assistant.content
    assert "候选资料，需公告或年报确认" in assistant.content
    assert "L1_L3_candidate" not in assistant.content
    assert "行业资料/公司基础资料" in assistant.content
    assert "阶段状态" in assistant.content
    assert "知识库资料没有提供可用补充" in assistant.content
    assert "公告等硬证据工具" in assistant.content
    assert "硬证据证据" not in assistant.content
    assert "硬证据硬证据" not in assistant.content
    assert "公告等硬证据的硬证据" not in assistant.content
    assert "每日复盘流程标记需要补证据" in assistant.content
    assert "本地复盘数据" in assistant.content
    assert "知识图谱关联到的概念" in assistant.content
    assert "local" not in assistant.content.lower()
    assert "确定性投影" not in assistant.content
    assert "知识知识图谱" not in assistant.content
    assert "行业资料行业资料" not in assistant.content
    assert "公司基础资料公司基础资料" not in assistant.content
    assert "公司基础资料基础资料" not in assistant.content
    assert "公告等硬证据公告" not in assistant.content
    assert "盘面信号盘面信号" not in assistant.content
    assert "盘面盘面信号" not in assistant.content
    assert "证据以行业资料和公司基础资料为主" in assistant.content
    assert "也有公司基础资料" in assistant.content
    assert "未取到公告/订单/认证/量产等硬证据" in assistant.content
    assert "当日日报指标来自本地数据库的数据" in assistant.content
    for internal in (
        "Daily Review",
        "daily-agent",
        "L1",
        "L2",
        "L3",
        "L4",
        "replay",
        "wiki",
        "graph_only",
        "high/L1_L3_candidate",
        "cycle_status",
        "RAG",
        "[D4]",
    ):
        assert internal not in assistant.content


def test_cancellation_between_text_deltas_marks_run_cancelled(tmp_path) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "流式取消",
    )
    cancelled = Event()

    def answer_spy(options: AskOptions) -> AskResult:
        assert options.stream_text_delta is not None
        options.stream_text_delta("已完成片段")
        cancelled.set()
        options.stream_text_delta("不应落盘")
        return _ask_result(options.query, synthesis="已完成片段不应落盘")

    TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=answer_spy,
        skill_registry=SkillRegistry(),
        is_cancelled=cancelled.is_set,
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="流式取消",
        skill_mode="auto",
        selected_skill_ids=[],
    )

    assistant = conversation_store.load_messages(conversation.conversation_id)[-1]
    assert run_store.load_run(run_id).status == "cancelled"
    assert assistant.content == "已完成片段"
    assert assistant.status == "cancelled"


class _StreamingResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args: object) -> None:
        return None


def test_openai_compatible_stream_forwards_real_provider_deltas(monkeypatch) -> None:
    provider = llm_refine.LLMProvider("fixture", "key", "https://llm.invalid/v1", "model")
    body = (
        b'data: {"choices":[{"delta":{"content":"real "}}]}\n\n'
        b'data: {"choices":[{"delta":{"content":"delta"}}]}\n\n'
        b"data: [DONE]\n\n"
    )
    monkeypatch.setattr(llm_refine, "detect_provider", lambda *_: provider)
    monkeypatch.setattr(
        llm_refine.urllib.request,
        "urlopen",
        lambda *args, **kwargs: _StreamingResponse(body),
    )
    deltas: list[str] = []

    result, reason = llm_refine.synthesize_messages_stream(
        [{"role": "user", "content": "question"}],
        on_delta=deltas.append,
    )

    assert reason == ""
    assert result is not None
    assert result.answer == "real delta"
    assert deltas == ["real ", "delta"]


def test_openai_stream_checks_cancellation_between_provider_deltas(
    monkeypatch,
) -> None:
    provider = llm_refine.LLMProvider("fixture", "key", "https://llm.invalid/v1", "model")
    body = (
        b'data: {"choices":[{"delta":{"content":"first"}}]}\n\n'
        b'data: {"choices":[{"delta":{"content":"second"}}]}\n\n'
        b"data: [DONE]\n\n"
    )
    monkeypatch.setattr(llm_refine, "detect_provider", lambda *_: provider)
    monkeypatch.setattr(
        llm_refine.urllib.request,
        "urlopen",
        lambda *args, **kwargs: _StreamingResponse(body),
    )
    cancelled = Event()
    deltas: list[str] = []

    def on_delta(delta: str) -> None:
        deltas.append(delta)
        cancelled.set()

    with pytest.raises(llm_refine.LLMStreamCancelled):
        llm_refine.synthesize_messages_stream(
            [{"role": "user", "content": "question"}],
            on_delta=on_delta,
            is_cancelled=cancelled.is_set,
        )

    assert deltas == ["first"]


def test_stream_unsupported_falls_back_to_one_complete_delta(monkeypatch) -> None:
    provider = llm_refine.LLMProvider("fixture", "key", "https://llm.invalid/v1", "model")
    monkeypatch.setattr(llm_refine, "detect_provider", lambda *_: provider)
    unsupported = urllib.error.HTTPError(
        "https://llm.invalid/v1/chat/completions",
        422,
        "stream unsupported",
        {},
        None,
    )
    monkeypatch.setattr(
        llm_refine,
        "_post_chat_stream",
        lambda *args, **kwargs: (_ for _ in ()).throw(unsupported),
    )
    monkeypatch.setattr(llm_refine, "_post_chat", lambda *args, **kwargs: "whole answer")
    deltas: list[str] = []

    result, reason = llm_refine.synthesize_messages_stream(
        [{"role": "user", "content": "question"}],
        on_delta=deltas.append,
    )

    assert reason == ""
    assert result is not None
    assert result.answer == "whole answer"
    assert deltas == ["whole answer"]


@pytest.mark.parametrize("terminal", ["completed", "cancelled", "failed"])
def test_worker_persists_run_terminal_before_message_and_terminal_events(
    tmp_path,
    monkeypatch,
    terminal: str,
) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        f"终态顺序-{terminal}",
    )
    order: list[str] = []
    original_finish = run_store.finish_run
    original_finalize = run_store.finish_run_with_artifacts
    original_revise = conversation_store.revise_message
    original_event = run_store.append_stream_event

    def finish_spy(run_id: str, status: str, *, error: str | None = None):
        order.append(f"run:{status}")
        return original_finish(run_id, status, error=error)

    def finalize_spy(run_id: str, status: str, payloads, *, error: str | None = None):
        order.append(f"run:{status}")
        return original_finalize(run_id, status, payloads, error=error)

    def revise_spy(*args, **kwargs):
        order.append(f"message:{kwargs['status']}")
        return original_revise(*args, **kwargs)

    def event_spy(*args, **kwargs):
        if kwargs["event_type"] in {
            "report.complete",
            "message.complete",
            "report.error",
            "message.error",
        }:
            order.append(f"event:{kwargs['event_type']}")
        return original_event(*args, **kwargs)

    monkeypatch.setattr(run_store, "finish_run", finish_spy)
    monkeypatch.setattr(run_store, "finish_run_with_artifacts", finalize_spy)
    monkeypatch.setattr(conversation_store, "revise_message", revise_spy)
    monkeypatch.setattr(run_store, "append_stream_event", event_spy)

    def answer(options: AskOptions) -> AskResult:
        if terminal == "failed":
            raise RuntimeError("fixture")
        return _ask_result(options.query)

    result = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=answer,
        skill_registry=SkillRegistry(),
        is_cancelled=(lambda: terminal == "cancelled"),
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query=f"终态顺序-{terminal}",
        skill_mode="auto",
        selected_skill_ids=[],
    )

    assert result.status == terminal
    run_index = order.index(f"run:{terminal}")
    assert run_index < order.index(f"message:{terminal}")
    assert all(
        run_index < index
        for index, item in enumerate(order)
        if item.startswith("event:")
    )


def test_unexpected_finish_status_does_not_write_completed_message_or_events(
    tmp_path,
    monkeypatch,
) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "终态冲突",
    )
    original_finish = run_store.finish_run

    def conflicting_finish(run_id: str, status: str, payloads, *, error: str | None = None):
        assert status == "completed"
        return original_finish(run_id, "cancelled", error="external winner")

    monkeypatch.setattr(run_store, "finish_run_with_artifacts", conflicting_finish)
    result = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=lambda options: _ask_result(options.query),
        skill_registry=SkillRegistry(),
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="终态冲突",
        skill_mode="auto",
        selected_skill_ids=[],
    )

    assistant = conversation_store.load_messages(conversation.conversation_id)[-1]
    terminal_events = {
        event["event_type"] for event in run_store.load_stream_events(run_id)
    }
    assert result.status == "cancelled"
    assert assistant.status == "pending"
    assert "message.complete" not in terminal_events
    assert "report.complete" not in terminal_events
    assert run_store.load_run(run_id).artifacts == []
    assert not (run_store.run_dir(run_id) / "answer.md").exists()
    assert not (run_store.run_dir(run_id) / "report.json").exists()


def test_message_revision_keeps_jsonl_append_only_but_loads_latest_state(tmp_path) -> None:
    store = ConversationStore("alice", root=tmp_path)
    conversation = store.create_conversation()
    pending = store.append_message(
        conversation.conversation_id,
        "assistant",
        "",
        status="pending",
        run_id="run-1",
    )

    completed = store.revise_message(
        conversation.conversation_id,
        pending.message_id,
        content="最终回答",
        status="completed",
        invoked_skill_ids=["daily-review"],
    )

    assert store.load_messages(conversation.conversation_id) == [completed]
    raw_lines = (
        tmp_path / conversation.conversation_id / "messages.jsonl"
    ).read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["message_id"] for line in raw_lines] == [
        pending.message_id,
        pending.message_id,
    ]
