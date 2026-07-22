from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
from threading import Barrier, Event, Lock
import time

from intelligence.services import agent_research, episode_tool_batch, query_ledger
from intelligence.services.agent_runtime import ModelToolCall
from intelligence.services.episode_tool_batch import ToolBatchExecutor
from intelligence.services.evidence_capabilities import (
    EvidencePlan,
    EvidenceRequirement,
)
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import (
    RequiredOutput,
    ResearchDeadline,
    ResearchPolicy,
    ResearchRunContext,
    ResearchTaskContract,
)
from intelligence.services.research_tool_registry import ResearchToolRegistry, ToolSpec


Runner = Callable[
    [str, agent_research.AgentToolContext],
    tuple[list[agent_research.AgentEvidence], str, ProviderTrace],
]


def _context(
    *,
    question_type: str = "valuation_estimate",
    mandatory: tuple[str, ...] = ("market_data",),
    timeout: float = 2.0,
    allowed: tuple[str, ...] = ("web_search", "kb_search", "market_data"),
) -> ResearchRunContext:
    contract = ResearchTaskContract(
        task_id="tool-batch-test",
        question="某公司估值怎么看",
        subject="某公司",
        subject_kind="company",
        question_type=question_type,
        required_outputs=(
            RequiredOutput("direct_assessment", "直接判断", allowed, True),
        ),
        allowed_capabilities=allowed,
        research_tier="quick",
        evidence_plan=EvidencePlan(
            requirements=tuple(
                EvidenceRequirement(name, name, True) for name in mandatory
            )
        ),
    )
    return ResearchRunContext(
        contract=contract,
        deadline=ResearchDeadline.from_timeout(timeout),
        policy=ResearchPolicy("quick", 4, timeout, 0.0),
        trace_parent_id="tool-batch-test",
    )


def _evidence_result(
    tool: str,
    query: str,
) -> tuple[list[agent_research.AgentEvidence], str, ProviderTrace]:
    return (
        [
            agent_research.AgentEvidence(
                tool=tool,
                title=f"{tool} evidence",
                detail=query,
                source=f"test:{tool}",
                content_hash=f"{tool}:{query}",
            )
        ],
        f"{tool} observation",
        ProviderTrace(
            provider=f"test:{tool}",
            capability=tool,
            status="success",
            result_count=1,
        ),
    )


def _registry(**overrides: Runner) -> ResearchToolRegistry:
    def default_runner(
        query: str,
        _context: agent_research.AgentToolContext,
    ) -> tuple[list[agent_research.AgentEvidence], str, ProviderTrace]:
        return _evidence_result("fallback", query)

    return ResearchToolRegistry(
        tuple(
            ToolSpec(
                name=name,
                capability=name,
                description=f"test {name}",
                cost="external" if name == "web_search" else "local",
                freshness="current" if name != "kb_search" else "stable",
                runner=overrides.get(name, default_runner),
            )
            for name in ("web_search", "kb_search", "market_data")
        )
    )


def test_mandatory_market_call_starts_while_slow_web_is_listed_first() -> None:
    market_started = Event()

    def slow_web_runner(
        query: str,
        _context: agent_research.AgentToolContext,
    ) -> tuple[list[agent_research.AgentEvidence], str, ProviderTrace]:
        assert market_started.wait(1.0), "market_data was serialized behind web_search"
        return _evidence_result("web_search", query)

    def market_runner(
        query: str,
        _context: agent_research.AgentToolContext,
    ) -> tuple[list[agent_research.AgentEvidence], str, ProviderTrace]:
        market_started.set()
        return _evidence_result("market_data", query)

    result = ToolBatchExecutor().execute(
        (
            ModelToolCall("web-1", "web_search", {"query": "slow web"}),
            ModelToolCall("market-1", "market_data", {"query": "valuation"}),
        ),
        registry=_registry(
            web_search=slow_web_runner,
            market_data=market_runner,
        ),
        context=_context(),
        remaining_slots=2,
    )

    assert market_started.is_set()
    assert [item.call.call_id for item in result.items] == ["web-1", "market-1"]
    assert [item.status for item in result.items] == ["success", "success"]
    assert result.executed_count == 2


def test_two_independent_read_only_tools_overlap_in_wall_clock_time() -> None:
    both_entered = Barrier(2)
    entered: set[str] = set()
    entered_lock = Lock()

    def blocking_runner(tool: str) -> Runner:
        def run(
            query: str,
            _context: agent_research.AgentToolContext,
        ) -> tuple[list[agent_research.AgentEvidence], str, ProviderTrace]:
            with entered_lock:
                entered.add(tool)
            both_entered.wait(timeout=1.0)
            return _evidence_result(tool, query)

        return run

    result = ToolBatchExecutor().execute(
        (
            ModelToolCall("web-1", "web_search", {"query": "web"}),
            ModelToolCall("kb-1", "kb_search", {"query": "knowledge"}),
        ),
        registry=_registry(
            web_search=blocking_runner("web_search"),
            kb_search=blocking_runner("kb_search"),
        ),
        context=_context(mandatory=()),
        remaining_slots=2,
    )

    assert entered == {"web_search", "kb_search"}
    assert [item.status for item in result.items] == ["success", "success"]


def test_each_worker_has_a_distinct_copied_context_with_one_shared_query_ledger() -> (
    None
):
    worker_label: ContextVar[str] = ContextVar("worker_label", default="unset")
    parent_token = worker_label.set("parent")
    both_changed_local_context = Barrier(2)
    observations: dict[str, tuple[str, str, query_ledger.QueryLedger | None]] = {}
    observations_lock = Lock()

    def context_runner(tool: str) -> Runner:
        def run(
            query: str,
            _context: agent_research.AgentToolContext,
        ) -> tuple[list[agent_research.AgentEvidence], str, ProviderTrace]:
            inherited = worker_label.get()
            worker_label.set(tool)
            both_changed_local_context.wait(timeout=1.0)
            with observations_lock:
                observations[tool] = (
                    inherited,
                    worker_label.get(),
                    query_ledger.current_query_ledger(),
                )
            return _evidence_result(tool, query)

        return run

    try:
        with query_ledger.query_ledger_scope() as ledger:
            result = ToolBatchExecutor().execute(
                (
                    ModelToolCall("web-1", "web_search", {"query": "web"}),
                    ModelToolCall("kb-1", "kb_search", {"query": "knowledge"}),
                ),
                registry=_registry(
                    web_search=context_runner("web_search"),
                    kb_search=context_runner("kb_search"),
                ),
                context=_context(mandatory=()),
                remaining_slots=2,
            )
    finally:
        worker_label.reset(parent_token)

    assert [item.status for item in result.items] == ["success", "success"]
    assert observations["web_search"][:2] == ("parent", "web_search")
    assert observations["kb_search"][:2] == ("parent", "kb_search")
    assert observations["web_search"][2] is ledger
    assert observations["kb_search"][2] is ledger


def test_duplicate_and_unauthorized_calls_never_reach_runners() -> None:
    runner_calls = {"web_search": 0, "kb_search": 0, "market_data": 0}

    def counting_runner(tool: str) -> Runner:
        def run(
            query: str,
            _context: agent_research.AgentToolContext,
        ) -> tuple[list[agent_research.AgentEvidence], str, ProviderTrace]:
            runner_calls[tool] += 1
            return _evidence_result(tool, query)

        return run

    registry = _registry(
        web_search=counting_runner("web_search"),
        kb_search=counting_runner("kb_search"),
        market_data=counting_runner("market_data"),
    )
    session = ToolBatchExecutor().new_session()
    seed = session.execute(
        (ModelToolCall("seed", "market_data", {"query": "Seed"}),),
        registry=registry,
        context=_context(),
        remaining_slots=1,
    )
    assert seed.items[0].status == "success"
    runner_calls["market_data"] = 0

    result = session.execute(
        (
            ModelToolCall("unknown", "shell", {"query": "do not run"}),
            ModelToolCall("unauthorized", "web_search", {"query": "do not run"}),
            ModelToolCall("bad-query", "kb_search", {"query": 42}),
            ModelToolCall("old-duplicate", "market_data", {"query": " seed "}),
            ModelToolCall("kb-first", "kb_search", {"query": "Same    KB"}),
            ModelToolCall("kb-duplicate", "kb_search", {"query": " same kb "}),
        ),
        registry=registry,
        context=_context(allowed=("kb_search", "market_data")),
        remaining_slots=4,
    )

    assert [item.status for item in result.items] == [
        "rejected",
        "rejected",
        "rejected",
        "rejected",
        "success",
        "rejected",
    ]
    assert [item.error for item in result.items] == [
        "unknown_or_unauthorized_tool",
        "unknown_or_unauthorized_tool",
        "invalid_query",
        "duplicate_query",
        "",
        "duplicate_query",
    ]
    assert runner_calls == {"web_search": 0, "kb_search": 1, "market_data": 0}
    assert result.executed_count == 1
    assert result.normalized_queries == (("kb_search", "same kb"),)


def test_same_session_dedupes_across_batches() -> None:
    runner_calls = 0

    def runner(
        query: str,
        _context: agent_research.AgentToolContext,
    ) -> tuple[list[agent_research.AgentEvidence], str, ProviderTrace]:
        nonlocal runner_calls
        runner_calls += 1
        return _evidence_result("market_data", query)

    session = ToolBatchExecutor().new_session()
    first = session.execute(
        (ModelToolCall("first", "market_data", {"query": " Same query "}),),
        registry=_registry(market_data=runner),
        context=_context(),
        remaining_slots=1,
    )
    second = session.execute(
        (ModelToolCall("second", "market_data", {"query": "same QUERY"}),),
        registry=_registry(market_data=runner),
        context=_context(),
        remaining_slots=1,
    )

    assert first.items[0].status == "success"
    assert second.items[0].status == "rejected"
    assert second.items[0].error == "duplicate_query"
    assert runner_calls == 1


def test_same_session_serializes_concurrent_duplicate_admission() -> None:
    runner_started = Event()
    release_runner = Event()
    runner_calls = 0

    def runner(
        query: str,
        _context: agent_research.AgentToolContext,
    ) -> tuple[list[agent_research.AgentEvidence], str, ProviderTrace]:
        nonlocal runner_calls
        runner_calls += 1
        runner_started.set()
        release_runner.wait(timeout=2.0)
        return _evidence_result("market_data", query)

    registry = _registry(market_data=runner)
    context = _context(timeout=2.0)
    session = ToolBatchExecutor().new_session()
    pool = ThreadPoolExecutor(max_workers=2)
    first = pool.submit(
        session.execute,
        (ModelToolCall("first", "market_data", {"query": "same"}),),
        registry=registry,
        context=context,
        remaining_slots=1,
    )
    assert runner_started.wait(timeout=1.0)
    second = pool.submit(
        session.execute,
        (ModelToolCall("second", "market_data", {"query": " SAME "}),),
        registry=registry,
        context=context,
        remaining_slots=1,
    )
    release_runner.set()
    results = [first.result(timeout=2), second.result(timeout=2)]
    pool.shutdown()

    assert [result.items[0].status for result in results] == [
        "success",
        "rejected",
    ]
    assert results[1].items[0].error == "duplicate_query"
    assert runner_calls == 1


def test_new_sessions_isolate_episode_seen_queries() -> None:
    runner_calls = 0

    def runner(
        query: str,
        _context: agent_research.AgentToolContext,
    ) -> tuple[list[agent_research.AgentEvidence], str, ProviderTrace]:
        nonlocal runner_calls
        runner_calls += 1
        return _evidence_result("market_data", query)

    executor = ToolBatchExecutor()
    results = [
        executor.new_session().execute(
            (ModelToolCall(f"call-{index}", "market_data", {"query": "same"}),),
            registry=_registry(market_data=runner),
            context=_context(),
            remaining_slots=1,
        )
        for index in range(2)
    ]

    assert [result.items[0].status for result in results] == ["success", "success"]
    assert runner_calls == 2


def test_factory_execute_uses_a_fresh_ephemeral_session_per_call() -> None:
    runner_calls = 0

    def runner(
        query: str,
        _context: agent_research.AgentToolContext,
    ) -> tuple[list[agent_research.AgentEvidence], str, ProviderTrace]:
        nonlocal runner_calls
        runner_calls += 1
        return _evidence_result("market_data", query)

    executor = ToolBatchExecutor()
    results = [
        executor.execute(
            (ModelToolCall(f"call-{index}", "market_data", {"query": "same"}),),
            registry=_registry(market_data=runner),
            context=_context(),
            remaining_slots=1,
        )
        for index in range(2)
    ]

    assert [result.items[0].status for result in results] == ["success", "success"]
    assert runner_calls == 2


def test_step_ids_are_monotonic_across_batches_in_original_model_order() -> None:
    session = ToolBatchExecutor().new_session()
    first = session.execute(
        (
            ModelToolCall("web-first", "web_search", {"query": "web"}),
            ModelToolCall("market-second", "market_data", {"query": "market"}),
        ),
        registry=_registry(),
        context=_context(),
        remaining_slots=2,
    )
    second = session.execute(
        (ModelToolCall("kb-third", "kb_search", {"query": "kb"}),),
        registry=_registry(),
        context=_context(),
        remaining_slots=1,
    )

    assert [item.observation.trace.step_id for item in first.items] == [
        "tool-batch-test:episode:tool:1",
        "tool-batch-test:episode:tool:2",
    ]
    assert second.items[0].observation is not None
    assert second.items[0].observation.trace.step_id == (
        "tool-batch-test:episode:tool:3"
    )


def test_strict_arguments_and_duplicate_call_ids_are_rejected_before_dispatch() -> None:
    runner_calls = {"web_search": 0, "kb_search": 0, "market_data": 0}

    def runner(tool: str) -> Runner:
        def run(
            query: str,
            _context: agent_research.AgentToolContext,
        ) -> tuple[list[agent_research.AgentEvidence], str, ProviderTrace]:
            runner_calls[tool] += 1
            return _evidence_result(tool, query)

        return run

    result = (
        ToolBatchExecutor()
        .new_session()
        .execute(
            (
                ModelToolCall(
                    "extra",
                    "web_search",
                    {"query": "web", "limit": 5},
                ),
                ModelToolCall("missing", "web_search", {}),
                ModelToolCall("dup", "kb_search", {"query": "kb"}),
                ModelToolCall("dup", "market_data", {"query": "market"}),
                ModelToolCall("bad-query", "market_data", {"query": 7}),
            ),
            registry=_registry(
                web_search=runner("web_search"),
                kb_search=runner("kb_search"),
                market_data=runner("market_data"),
            ),
            context=_context(),
            remaining_slots=5,
        )
    )

    assert [item.status for item in result.items] == [
        "rejected",
        "rejected",
        "success",
        "rejected",
        "rejected",
    ]
    assert [item.error for item in result.items] == [
        "invalid_arguments",
        "invalid_arguments",
        "",
        "duplicate_call_id",
        "invalid_query",
    ]
    assert runner_calls == {"web_search": 0, "kb_search": 1, "market_data": 0}


def test_runner_timeout_error_maps_to_timeout_status() -> None:
    def runner(
        _query: str,
        _context: agent_research.AgentToolContext,
    ) -> tuple[list[agent_research.AgentEvidence], str, ProviderTrace]:
        raise TimeoutError("provider deadline")

    result = (
        ToolBatchExecutor()
        .new_session()
        .execute(
            (ModelToolCall("timeout", "market_data", {"query": "market"}),),
            registry=_registry(market_data=runner),
            context=_context(),
            remaining_slots=1,
        )
    )

    assert result.items[0].status == "timeout"
    assert result.items[0].error == "tool_timeout"
    assert result.items[0].observation is None
    assert result.executed_count == 1


def test_expired_deadline_does_not_submit_or_consume_query_and_step_id() -> None:
    runner_calls = 0
    release_runner = Event()

    def runner(
        query: str,
        _context: agent_research.AgentToolContext,
    ) -> tuple[list[agent_research.AgentEvidence], str, ProviderTrace]:
        nonlocal runner_calls
        runner_calls += 1
        release_runner.wait(timeout=1.0)
        return _evidence_result("market_data", query)

    session = ToolBatchExecutor().new_session()
    try:
        expired = session.execute(
            (ModelToolCall("expired", "market_data", {"query": "same"}),),
            registry=_registry(market_data=runner),
            context=_context(timeout=0.0),
            remaining_slots=1,
        )
    finally:
        release_runner.set()
    retried = session.execute(
        (ModelToolCall("retry", "market_data", {"query": "same"}),),
        registry=_registry(market_data=runner),
        context=_context(timeout=1.0),
        remaining_slots=1,
    )

    assert expired.items[0].status == "timeout"
    assert expired.executed_count == 0
    assert expired.normalized_queries == ()
    assert retried.items[0].status == "success"
    assert retried.items[0].observation is not None
    assert retried.items[0].observation.trace.step_id == (
        "tool-batch-test:episode:tool:1"
    )
    assert runner_calls == 1


def test_timed_out_runner_cannot_publish_late_query_ledger_result() -> None:
    release_runner = Event()
    registry_finished = Event()
    runner_calls = 0

    def runner(
        query: str,
        _context: agent_research.AgentToolContext,
    ) -> tuple[list[agent_research.AgentEvidence], str, ProviderTrace]:
        nonlocal runner_calls
        runner_calls += 1
        release_runner.wait(timeout=2.0)
        return _evidence_result("market_data", query)

    class NotifyingRegistry(ResearchToolRegistry):
        def execute(self, *args, **kwargs):
            try:
                return super().execute(*args, **kwargs)
            finally:
                registry_finished.set()

    base_registry = _registry(market_data=runner)
    registry = NotifyingRegistry(base_registry.authorized_specs())

    with query_ledger.query_ledger_scope() as ledger:
        try:
            timed_out = (
                ToolBatchExecutor()
                .new_session()
                .execute(
                    (ModelToolCall("slow", "market_data", {"query": "same"}),),
                    registry=registry,
                    context=_context(timeout=0.1),
                    remaining_slots=1,
                )
            )
        finally:
            release_runner.set()

        assert timed_out.items[0].status == "timeout"
        assert registry_finished.wait(timeout=1.0)
        assert ledger.summary()["executed_count"] == 0

        retried = (
            ToolBatchExecutor()
            .new_session()
            .execute(
                (ModelToolCall("retry", "market_data", {"query": "same"}),),
                registry=registry,
                context=_context(timeout=1.0),
                remaining_slots=1,
            )
        )

        assert retried.items[0].status == "success"
        assert ledger.summary()["executed_count"] == 1

    assert runner_calls == 2


def test_calls_beyond_budget_are_rejected_after_mandatory_priority_selection() -> None:
    ran: set[str] = set()
    ran_lock = Lock()

    def recording_runner(tool: str) -> Runner:
        def run(
            query: str,
            _context: agent_research.AgentToolContext,
        ) -> tuple[list[agent_research.AgentEvidence], str, ProviderTrace]:
            with ran_lock:
                ran.add(tool)
            return _evidence_result(tool, query)

        return run

    result = ToolBatchExecutor().execute(
        (
            ModelToolCall("web-1", "web_search", {"query": "public valuation"}),
            ModelToolCall("kb-1", "kb_search", {"query": "local valuation"}),
            ModelToolCall("market-1", "market_data", {"query": "market valuation"}),
        ),
        registry=_registry(
            web_search=recording_runner("web_search"),
            kb_search=recording_runner("kb_search"),
            market_data=recording_runner("market_data"),
        ),
        context=_context(mandatory=("web_search",)),
        remaining_slots=2,
    )

    assert ran == {"web_search", "market_data"}
    assert [item.call.call_id for item in result.items] == [
        "web-1",
        "kb-1",
        "market-1",
    ]
    assert [item.status for item in result.items] == [
        "success",
        "rejected",
        "success",
    ]
    assert result.items[0].observation is not None
    assert result.items[0].observation.trace.step_id == "tool-batch-test:episode:tool:1"
    assert result.items[1].error == "tool_budget_exhausted"
    assert result.items[2].observation is not None
    assert result.items[2].observation.trace.step_id == "tool-batch-test:episode:tool:2"
    assert result.executed_count == 2
    assert result.normalized_queries == (
        ("web_search", "public valuation"),
        ("market_data", "market valuation"),
    )


def test_exception_timeout_and_empty_result_keep_original_call_order() -> None:
    empty_finished = Event()
    release_timeout = Event()
    timeout_finished = Event()
    completion_order: list[str] = []
    completion_lock = Lock()

    def error_runner(
        _query: str,
        _context: agent_research.AgentToolContext,
    ) -> tuple[list[agent_research.AgentEvidence], str, ProviderTrace]:
        assert empty_finished.wait(1.0)
        with completion_lock:
            completion_order.append("web_search")
        raise RuntimeError("provider exploded")

    def timeout_runner(
        query: str,
        _context: agent_research.AgentToolContext,
    ) -> tuple[list[agent_research.AgentEvidence], str, ProviderTrace]:
        release_timeout.wait(1.0)
        with completion_lock:
            completion_order.append("kb_search")
        timeout_finished.set()
        return _evidence_result("kb_search", query)

    def empty_runner(
        _query: str,
        _context: agent_research.AgentToolContext,
    ) -> tuple[list[agent_research.AgentEvidence], str, ProviderTrace]:
        with completion_lock:
            completion_order.append("market_data")
        empty_finished.set()
        return (
            [],
            "no evidence",
            ProviderTrace(
                provider="test:market_data",
                capability="market_data",
                status="empty",
                result_count=0,
            ),
        )

    started = time.monotonic()
    try:
        result = ToolBatchExecutor().execute(
            (
                ModelToolCall("error-1", "web_search", {"query": "error"}),
                ModelToolCall("timeout-1", "kb_search", {"query": "timeout"}),
                ModelToolCall("empty-1", "market_data", {"query": "empty"}),
            ),
            registry=_registry(
                web_search=error_runner,
                kb_search=timeout_runner,
                market_data=empty_runner,
            ),
            context=_context(timeout=0.2),
            remaining_slots=3,
        )
    finally:
        release_timeout.set()
    elapsed = time.monotonic() - started

    assert elapsed < 0.8
    assert [item.call.call_id for item in result.items] == [
        "error-1",
        "timeout-1",
        "empty-1",
    ]
    assert [item.status for item in result.items] == ["error", "timeout", "empty"]
    assert result.items[0].error == "RuntimeError: provider exploded"
    assert result.items[0].observation is None
    assert result.items[1].error == "tool_timeout"
    assert result.items[1].observation is None
    assert result.items[2].error == ""
    assert result.items[2].observation is not None
    assert result.items[2].observation.observation == "no evidence"
    assert result.items[2].observation.evidence == ()
    assert completion_order[:2] == ["market_data", "web_search"]
    assert timeout_finished.wait(1.0)
    assert completion_order == ["market_data", "web_search", "kb_search"]


def test_call_unfinished_in_wait_snapshot_stays_timeout_after_late_completion(
    monkeypatch,
) -> None:
    runner_started = Event()
    release_runner = Event()

    def runner(
        query: str,
        _context: agent_research.AgentToolContext,
    ) -> tuple[list[agent_research.AgentEvidence], str, ProviderTrace]:
        runner_started.set()
        release_runner.wait(timeout=1.0)
        return _evidence_result("market_data", query)

    def wait_at_deadline(futures, *, timeout):
        del timeout
        future_set = set(futures)
        assert runner_started.wait(timeout=1.0)
        deadline_done: set = set()
        deadline_not_done = set(future_set)
        release_runner.set()
        for future in future_set:
            future.result(timeout=1.0)
        return deadline_done, deadline_not_done

    monkeypatch.setattr(episode_tool_batch, "wait", wait_at_deadline)

    result = (
        ToolBatchExecutor()
        .new_session()
        .execute(
            (ModelToolCall("late", "market_data", {"query": "market"}),),
            registry=_registry(market_data=runner),
            context=_context(timeout=1.0),
            remaining_slots=1,
        )
    )

    assert result.items[0].status == "timeout"
    assert result.items[0].error == "tool_timeout"
    assert result.items[0].observation is None


def test_timed_out_batches_share_one_bounded_executor() -> None:
    release_runners = Event()
    global_pool_full = Event()
    counts_lock = Lock()
    started_count = 0
    active_count = 0
    max_active = 0

    def runner(
        query: str,
        _context: agent_research.AgentToolContext,
    ) -> tuple[list[agent_research.AgentEvidence], str, ProviderTrace]:
        nonlocal active_count, max_active, started_count
        with counts_lock:
            started_count += 1
            active_count += 1
            max_active = max(max_active, active_count)
            if active_count == 2:
                global_pool_full.set()
        try:
            release_runners.wait(timeout=2.0)
            return _evidence_result("market_data", query)
        finally:
            with counts_lock:
                active_count -= 1

    shared_executor = ThreadPoolExecutor(max_workers=2)
    batch_executor = ToolBatchExecutor(executor=shared_executor)
    registry = _registry(market_data=runner)
    batches = ThreadPoolExecutor(max_workers=2)
    try:
        futures = [
            batches.submit(
                batch_executor.new_session().execute,
                (
                    ModelToolCall(
                        f"batch-{batch_index}-first",
                        "market_data",
                        {"query": f"query-{batch_index}-first"},
                    ),
                    ModelToolCall(
                        f"batch-{batch_index}-second",
                        "market_data",
                        {"query": f"query-{batch_index}-second"},
                    ),
                ),
                registry=registry,
                context=_context(timeout=0.2),
                remaining_slots=2,
            )
            for batch_index in range(2)
        ]
        assert global_pool_full.wait(timeout=1.0)
        results = [future.result(timeout=1.0) for future in futures]
    finally:
        release_runners.set()
        batches.shutdown(wait=True, cancel_futures=True)
        shared_executor.shutdown(wait=True, cancel_futures=True)

    assert [item.status for result in results for item in result.items] == [
        "timeout",
        "timeout",
        "timeout",
        "timeout",
    ]
    assert started_count == 2
    assert max_active == 2


def test_one_batch_submits_at_most_four_calls() -> None:
    ran: list[str] = []

    def runner(
        query: str,
        _context: agent_research.AgentToolContext,
    ) -> tuple[list[agent_research.AgentEvidence], str, ProviderTrace]:
        ran.append(query)
        return _evidence_result("market_data", query)

    result = (
        ToolBatchExecutor()
        .new_session()
        .execute(
            tuple(
                ModelToolCall(
                    f"call-{index}",
                    "market_data",
                    {"query": f"query-{index}"},
                )
                for index in range(5)
            ),
            registry=_registry(market_data=runner),
            context=_context(),
            remaining_slots=5,
        )
    )

    assert [item.status for item in result.items] == [
        "success",
        "success",
        "success",
        "success",
        "rejected",
    ]
    assert result.items[4].error == "tool_budget_exhausted"
    assert result.executed_count == 4
    assert set(ran) == {"query-0", "query-1", "query-2", "query-3"}
