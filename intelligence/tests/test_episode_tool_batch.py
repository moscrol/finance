from __future__ import annotations

from collections.abc import Callable
from contextvars import ContextVar
from threading import Barrier, Event, Lock
import time

from intelligence.services import agent_research, query_ledger
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
    executor = ToolBatchExecutor()
    seed = executor.execute(
        (ModelToolCall("seed", "market_data", {"query": "Seed"}),),
        registry=registry,
        context=_context(),
        remaining_slots=1,
    )
    assert seed.items[0].status == "success"
    runner_calls["market_data"] = 0

    result = executor.execute(
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
    assert (
        result.items[0].observation.trace.step_id == "tool-batch-test:episode:batch:1"
    )
    assert result.items[1].error == "tool_budget_exhausted"
    assert result.items[2].observation is not None
    assert (
        result.items[2].observation.trace.step_id == "tool-batch-test:episode:batch:3"
    )
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
