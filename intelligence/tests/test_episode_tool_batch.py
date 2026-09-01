from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
from dataclasses import replace
from pathlib import Path
from threading import Barrier, Event, Lock
import json
import time

import pytest

from intelligence.runtime import episode_tool_batch
from intelligence.services import agent_research, query_ledger
from intelligence.services.agent_runtime import ModelToolCall
from intelligence.runtime.episode_tool_batch import (
    NOT_DISPATCHED_DETAIL,
    ToolBatchExecutor,
    ToolCallResult,
    tool_batch_timeout_seconds,
)
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
from intelligence.services.research_tool_registry import (
    QUERY_TOOL_PARAMETERS,
    ResearchToolRegistry,
    ToolObservation,
    ToolSpec,
    default_registry,
)


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
    trace_parent_id: str = "tool-batch-test",
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
        trace_parent_id=trace_parent_id,
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


def test_tool_definitions_use_each_specs_own_json_schema() -> None:
    typed_schema = {
        "type": "object",
        "properties": {
            "dataset": {"type": "string"},
            "limit": {"type": "integer"},
        },
        "required": ["dataset"],
        "additionalProperties": False,
    }
    registry = ResearchToolRegistry(
        (
            ToolSpec(
                name="kb_search",
                capability="kb_search",
                description="query tool",
                cost="local",
                freshness="stable",
                runner=lambda query, _context: _evidence_result(
                    "kb_search", str(query)
                ),
            ),
            ToolSpec(
                name="finance_query",
                capability="finance_query",
                description="typed tool",
                cost="local",
                freshness="current",
                runner=lambda value, _context: _evidence_result(
                    "finance_query", str(value)
                ),
                parameters=typed_schema,
                parse_arguments=lambda arguments: (
                    dict(arguments),
                    str(arguments["dataset"]),
                ),
            ),
        )
    )

    definitions = registry.tool_definitions()
    by_name = {
        item["function"]["name"]: item["function"]["parameters"]
        for item in definitions
    }

    # 断言的是「用了 spec 自己的 schema」，不是 schema 的具体内容——
    # 手抄一份字面量会让每次改参数描述都无谓地变红（2026-08-12 就这么红过 3 条）。
    # 比对真本源（BUILD 模式 6：单一真本源，且生成而非手抄）。
    assert [item["function"]["name"] for item in definitions] == [
        "finance_query",
        "kb_search",
    ]
    assert by_name["kb_search"] == QUERY_TOOL_PARAMETERS
    assert by_name["finance_query"] == typed_schema


def test_tool_spec_deep_freezes_its_schema_contract() -> None:
    schema = {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
        "additionalProperties": False,
    }
    registry = ResearchToolRegistry(
        (
            ToolSpec(
                name="kb_search",
                capability="kb_search",
                description="query tool",
                cost="local",
                freshness="stable",
                runner=lambda query, _context: _evidence_result(
                    "kb_search", str(query)
                ),
                parameters=schema,
            ),
        )
    )
    schema["properties"]["query"]["type"] = "integer"

    definition = registry.tool_definitions()[0]["function"]["parameters"]

    assert definition["properties"]["query"]["type"] == "string"
    definition["properties"]["query"]["type"] = "number"
    assert registry.tool_definitions()[0]["function"]["parameters"][
        "properties"
    ]["query"]["type"] == "string"


def test_snapshot_tool_schema_is_honestly_no_argument() -> None:
    built = default_registry(
        {
            "market_data": lambda query, _context: _evidence_result(
                "market_data", str(query)
            )
        }
    )

    definition = built.tool_definitions()[0]["function"]
    assert definition["parameters"] == {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    }

    result = ToolBatchExecutor().execute(
        (ModelToolCall("snapshot-1", "market_data", {"query": "ignored"}),),
        registry=built,
        context=_context(allowed=("market_data",)),
        remaining_slots=1,
    )
    assert result.items[0].status == "rejected"
    assert result.items[0].error == "invalid_arguments"


def test_structured_arguments_reach_runner_and_deduplicate_canonical_objects() -> None:
    received: list[dict[str, object]] = []

    def runner(value: object, _context: agent_research.AgentToolContext):
        assert isinstance(value, dict)
        received.append(value)
        return _evidence_result("finance_query", str(value))

    registry = ResearchToolRegistry(
        (
            ToolSpec(
                name="finance_query",
                capability="finance_query",
                description="typed query",
                cost="local",
                freshness="current",
                runner=runner,
                parameters={
                    "type": "object",
                    "properties": {
                        "dataset": {"type": "string"},
                        "limit": {"type": "integer"},
                    },
                    "required": ["dataset", "limit"],
                    "additionalProperties": False,
                },
                parse_arguments=lambda arguments: (
                    dict(arguments),
                    str(arguments["dataset"]),
                ),
            ),
        )
    )
    context = _context(
        allowed=("finance_query",),
        mandatory=("finance_query",),
    )

    result = ToolBatchExecutor().execute(
        (
            ModelToolCall(
                "typed-1",
                "finance_query",
                {"dataset": "market_daily", "limit": 10},
            ),
            ModelToolCall(
                "typed-2",
                "finance_query",
                {"limit": 10, "dataset": "market_daily"},
            ),
        ),
        registry=registry,
        context=context,
        remaining_slots=2,
    )

    assert received == [{"dataset": "market_daily", "limit": 10}]
    assert result.items[0].status == "success"
    assert result.items[1].status == "rejected"
    assert result.items[1].error == "duplicate_query"


def test_registry_preserves_runner_reported_coverage_gaps() -> None:
    registry = ResearchToolRegistry(
        (
            ToolSpec(
                name="evidence_search",
                capability="evidence_search",
                description="closed loop search",
                cost="local",
                freshness="current",
                runner=lambda query, _context: (
                    [],
                    f"{query} 无结果",
                    ProviderTrace(
                        provider="test:search",
                        capability="evidence_search",
                        status="empty",
                    ),
                    (f"尚未找到与“{query}”直接相关的可用证据",),
                ),
            ),
        )
    )
    context = _context(
        allowed=("evidence_search",),
        mandatory=("evidence_search",),
    )

    observation = registry.execute(
        "evidence_search",
        "陌生问题",
        context=context,
        step_id="gap-test:1",
    )

    assert observation.gaps == (
        "尚未找到与“陌生问题”直接相关的可用证据",
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


def test_cancelled_batch_does_not_submit_tool_runner() -> None:
    cancelled = Event()
    cancelled.set()
    runner_calls = 0

    def runner(
        query: str,
        context: agent_research.AgentToolContext,
    ) -> tuple[list[agent_research.AgentEvidence], str, ProviderTrace]:
        del query, context
        nonlocal runner_calls
        runner_calls += 1
        return _evidence_result("market_data", "unexpected")

    result = ToolBatchExecutor().execute(
        (ModelToolCall("market-1", "market_data", {"query": "valuation"}),),
        registry=_registry(market_data=runner),
        context=_context(),
        remaining_slots=1,
        is_cancelled=cancelled.is_set,
    )

    assert runner_calls == 0
    assert result.executed_count == 0
    assert result.items[0].status == "rejected"
    assert result.items[0].error == "cancelled"


def test_cancellation_during_wait_returns_without_waiting_for_tool_deadline() -> None:
    runner_started = Event()
    release_runner = Event()
    cancelled = Event()

    def runner(
        query: str,
        _context: agent_research.AgentToolContext,
    ) -> tuple[list[agent_research.AgentEvidence], str, ProviderTrace]:
        runner_started.set()
        release_runner.wait(timeout=2.0)
        return _evidence_result("market_data", query)

    caller = ThreadPoolExecutor(max_workers=1)
    future = caller.submit(
        ToolBatchExecutor().execute,
        (ModelToolCall("market-1", "market_data", {"query": "valuation"}),),
        registry=_registry(market_data=runner),
        context=_context(timeout=2.0),
        remaining_slots=1,
        is_cancelled=cancelled.is_set,
    )
    assert runner_started.wait(timeout=1.0)
    cancelled.set()
    try:
        result = future.result(timeout=0.4)
    finally:
        release_runner.set()
        caller.shutdown(wait=True, cancel_futures=True)

    assert result.executed_count == 1
    assert result.items[0].status == "rejected"
    assert result.items[0].error == "cancelled"


def test_cancellation_wins_when_tool_completes_in_same_wait_snapshot() -> None:
    cancelled = Event()

    def runner(
        query: str,
        context: agent_research.AgentToolContext,
    ) -> tuple[list[agent_research.AgentEvidence], str, ProviderTrace]:
        assert not context.cancelled
        cancelled.set()
        assert context.cancelled
        return _evidence_result("market_data", query)

    with query_ledger.query_ledger_scope() as ledger:
        result = ToolBatchExecutor().execute(
            (ModelToolCall("market-1", "market_data", {"query": "valuation"}),),
            registry=_registry(market_data=runner),
            context=_context(timeout=2.0),
            remaining_slots=1,
            is_cancelled=cancelled.is_set,
        )

    assert result.executed_count == 1
    assert result.items[0].status == "rejected"
    assert result.items[0].error == "cancelled"
    assert ledger.summary()["executed_count"] == 0


def test_cancel_rolls_back_result_published_in_completion_race() -> None:
    cancelled = Event()

    class CancelOnPublish(dict):
        def __setitem__(self, key, value) -> None:
            cancelled.set()
            super().__setitem__(key, value)

    def runner(
        query: str,
        _context: agent_research.AgentToolContext,
    ) -> tuple[list[agent_research.AgentEvidence], str, ProviderTrace]:
        return _evidence_result("market_data", query)

    with query_ledger.query_ledger_scope() as ledger:
        ledger.entries = CancelOnPublish()
        result = ToolBatchExecutor().execute(
            (ModelToolCall("market-1", "market_data", {"query": "valuation"}),),
            registry=_registry(market_data=runner),
            context=_context(timeout=2.0),
            remaining_slots=1,
            is_cancelled=cancelled.is_set,
        )

    assert result.items[0].status == "rejected"
    assert result.items[0].error == "cancelled"
    assert ledger.summary()["executed_count"] == 0


def test_cancel_rolls_back_nested_ledger_publications_owned_by_guard() -> None:
    cancelled = Event()

    class CancelOnPublish(dict):
        def __setitem__(self, key, value) -> None:
            cancelled.set()
            super().__setitem__(key, value)

    def runner(
        query: str,
        _context: agent_research.AgentToolContext,
    ) -> tuple[list[agent_research.AgentEvidence], str, ProviderTrace]:
        query_ledger.executed("inner", query, lambda: "nested result")
        return _evidence_result("market_data", query)

    with query_ledger.query_ledger_scope() as ledger:
        ledger.entries = CancelOnPublish()
        result = ToolBatchExecutor().execute(
            (ModelToolCall("market-1", "market_data", {"query": "valuation"}),),
            registry=_registry(market_data=runner),
            context=_context(timeout=2.0),
            remaining_slots=1,
            is_cancelled=cancelled.is_set,
        )

    assert result.items[0].status == "rejected"
    assert result.items[0].error == "cancelled"
    assert ledger.summary()["executed_count"] == 0


def test_cancel_does_not_remove_preexisting_nested_ledger_record() -> None:
    cancelled = Event()

    def runner(
        query: str,
        _context: agent_research.AgentToolContext,
    ) -> tuple[list[agent_research.AgentEvidence], str, ProviderTrace]:
        assert query_ledger.executed("inner", query, lambda: "unexpected") == "seed"
        cancelled.set()
        return _evidence_result("market_data", query)

    with query_ledger.query_ledger_scope() as ledger:
        assert query_ledger.executed("inner", "valuation", lambda: "seed") == "seed"
        result = ToolBatchExecutor().execute(
            (ModelToolCall("market-1", "market_data", {"query": "valuation"}),),
            registry=_registry(market_data=runner),
            context=_context(timeout=2.0),
            remaining_slots=1,
            is_cancelled=cancelled.is_set,
        )

    assert result.items[0].status == "rejected"
    assert result.items[0].error == "cancelled"
    assert ledger.summary()["executed_count"] == 1
    assert ledger.summary()["deduped_count"] == 1


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


def test_query_ledger_cache_hit_rebinds_trace_to_current_batch_call() -> None:
    runner_calls = 0

    def runner(
        query: str,
        _context: agent_research.AgentToolContext,
    ) -> tuple[list[agent_research.AgentEvidence], str, ProviderTrace]:
        nonlocal runner_calls
        runner_calls += 1
        return _evidence_result("market_data", query)

    registry = _registry(market_data=runner)
    old_context = _context(trace_parent_id="old-parent")
    current_context = _context(trace_parent_id="current-parent")

    with query_ledger.query_ledger_scope():
        cached = registry.execute(
            "market_data",
            "same query",
            context=old_context,
            step_id="old-parent:episode:tool:99",
        )
        result = (
            ToolBatchExecutor()
            .new_session()
            .execute(
                (
                    ModelToolCall(
                        "cache-hit",
                        "market_data",
                        {"query": "same query"},
                    ),
                ),
                registry=registry,
                context=current_context,
                remaining_slots=1,
            )
        )

    assert runner_calls == 1
    assert cached.trace.parent_id == "old-parent"
    assert cached.trace.step_id == "old-parent:episode:tool:99"
    assert result.items[0].step_id == "current-parent:episode:tool:1"
    assert result.items[0].observation is not None
    assert result.items[0].observation.trace.parent_id == "current-parent"
    assert result.items[0].observation.trace.step_id == result.items[0].step_id


def test_tool_call_result_rejects_unknown_runtime_status() -> None:
    with pytest.raises(ValueError, match="unsupported tool call status: corrupt"):
        ToolCallResult(
            call=ModelToolCall(
                "corrupt-status",
                "market_data",
                {"query": "must not publish"},
            ),
            status="corrupt",  # type: ignore[arg-type]
            observation=ToolObservation(
                tool="market_data",
                query="must not publish",
                evidence=(),
                observation="illegal observation",
                trace=ProviderTrace(
                    provider="illegal",
                    capability="market_data",
                    status="success",
                ),
            ),
        )


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
    assert [item.step_id for item in result.items] == [
        "tool-batch-test:episode:tool:2",
        "tool-batch-test:episode:tool:3",
        "tool-batch-test:episode:tool:4",
        "tool-batch-test:episode:tool:5",
        "tool-batch-test:episode:tool:6",
        "tool-batch-test:episode:tool:7",
    ]
    assert len({result.items[index].step_id for index in (0, 1)}) == 2
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


def test_empty_market_data_miss_does_not_block_backfill_retry() -> None:
    """W5 live：首轮 market_data 空结果（as_of 错日）不得占 duplicate 键。

    补证回合会再打同一 capability；若空结果也记成 seen，第二次必被
    ``duplicate_query`` 打死，预算帽白给。有证据的成功查询仍去重。
    """

    runner_calls = 0

    def runner(
        query: str,
        _context: agent_research.AgentToolContext,
    ) -> tuple[list[agent_research.AgentEvidence], str, ProviderTrace]:
        nonlocal runner_calls
        runner_calls += 1
        if runner_calls == 1:
            return (
                [],
                "结构化市场数据仅更新到 2026-08-18，早于当前所需 2026-08-19；"
                "旧数据未用于当前判断",
                ProviderTrace(
                    provider="test:market_data",
                    capability="market_data",
                    status="stale",
                    result_count=0,
                ),
            )
        return _evidence_result("market_data", query)

    session = ToolBatchExecutor().new_session()
    first = session.execute(
        (ModelToolCall("miss", "market_data", {"query": "snapshot"}),),
        registry=_registry(market_data=runner),
        context=_context(),
        remaining_slots=1,
    )
    second = session.execute(
        (ModelToolCall("backfill", "market_data", {"query": "snapshot"}),),
        registry=_registry(market_data=runner),
        context=_context(),
        remaining_slots=1,
    )

    assert first.items[0].status == "empty"
    assert second.items[0].status == "success"
    assert second.items[0].error != "duplicate_query"
    assert runner_calls == 2


def test_episode_scoped_snapshot_succeeds_only_once_across_rewritten_queries() -> (
    None
):
    runner_calls = 0

    def runner(
        query: str,
        _context: agent_research.AgentToolContext,
    ) -> tuple[list[agent_research.AgentEvidence], str, ProviderTrace]:
        nonlocal runner_calls
        runner_calls += 1
        return _evidence_result("market_data", query)

    registry = ResearchToolRegistry(
        (
            ToolSpec(
                name="market_data",
                capability="market_data",
                description="episode snapshot",
                cost="local",
                freshness="current",
                runner=runner,
                query_scope="episode",
            ),
        )
    )
    session = ToolBatchExecutor().new_session()
    first = session.execute(
        (ModelToolCall("first", "market_data", {"query": "瑞华泰 当前估值"}),),
        registry=registry,
        context=_context(allowed=("market_data",)),
        remaining_slots=2,
    )
    second = session.execute(
        (ModelToolCall("second", "market_data", {"query": "瑞华泰 最新股价"}),),
        registry=registry,
        context=_context(allowed=("market_data",)),
        remaining_slots=1,
    )

    assert first.items[0].status == "success"
    assert second.items[0].status == "rejected"
    assert second.items[0].error == "episode_snapshot_already_collected"
    assert second.executed_count == 0
    assert runner_calls == 1


def test_available_tool_names_remove_collected_episode_snapshot() -> None:
    registry = ResearchToolRegistry(
        (
            ToolSpec(
                name="market_data",
                capability="market_data",
                description="episode snapshot",
                cost="local",
                freshness="current",
                runner=lambda query, _context: _evidence_result(
                    "market_data",
                    query,
                ),
                query_scope="episode",
            ),
            ToolSpec(
                name="kb_search",
                capability="kb_search",
                description="query search",
                cost="local",
                freshness="stable",
                runner=lambda query, _context: _evidence_result(
                    "kb_search",
                    query,
                ),
            ),
        )
    )
    context = _context(allowed=("market_data", "kb_search"))
    session = ToolBatchExecutor().new_session()

    assert session.available_tool_names(
        registry=registry,
        context=context,
    ) == ("kb_search", "market_data")

    first = session.execute(
        (ModelToolCall("market", "market_data", {"query": "current"}),),
        registry=registry,
        context=context,
        remaining_slots=2,
    )

    assert first.items[0].status == "success"
    assert session.available_tool_names(
        registry=registry,
        context=context,
    ) == ("kb_search",)


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
    assert [result.items[0].step_id for result in results] == [
        "tool-batch-test:episode:tool:1",
        "tool-batch-test:episode:tool:1",
    ]
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
            ModelToolCall("rejected-second", "shell", {"query": "shell"}),
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

    assert [item.step_id for item in first.items] == [
        "tool-batch-test:episode:tool:1",
        "tool-batch-test:episode:tool:2",
        "tool-batch-test:episode:tool:3",
    ]
    assert first.items[1].status == "rejected"
    assert first.items[1].error == "unknown_or_unauthorized_tool"
    assert [
        item.observation.trace.step_id for item in (first.items[0], first.items[2])
    ] == [
        first.items[0].step_id,
        first.items[2].step_id,
    ]
    assert second.items[0].observation is not None
    assert second.items[0].step_id == "tool-batch-test:episode:tool:4"
    assert second.items[0].observation.trace.step_id == second.items[0].step_id


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
    assert [item.step_id for item in result.items] == [
        "tool-batch-test:episode:tool:1",
        "tool-batch-test:episode:tool:2",
        "tool-batch-test:episode:tool:3",
        "tool-batch-test:episode:tool:4",
        "tool-batch-test:episode:tool:5",
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


def test_expired_deadline_does_not_submit_or_consume_query() -> None:
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
    assert expired.items[0].step_id == "tool-batch-test:episode:tool:1"
    assert expired.executed_count == 0
    assert expired.normalized_queries == ()
    assert retried.items[0].status == "success"
    assert retried.items[0].observation is not None
    assert retried.items[0].step_id == "tool-batch-test:episode:tool:2"
    assert retried.items[0].observation.trace.step_id == retried.items[0].step_id
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


def test_calls_beyond_budget_preserve_model_submitted_order() -> None:
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

    assert ran == {"web_search", "kb_search"}
    assert [item.call.call_id for item in result.items] == [
        "web-1",
        "kb-1",
        "market-1",
    ]
    assert [item.status for item in result.items] == [
        "success",
        "success",
        "rejected",
    ]
    assert result.items[0].observation is not None
    assert result.items[0].observation.trace.step_id == "tool-batch-test:episode:tool:1"
    assert result.items[1].observation is not None
    assert result.items[1].observation.trace.step_id == "tool-batch-test:episode:tool:2"
    assert result.items[2].error == "tool_budget_exhausted"
    assert result.items[2].step_id == "tool-batch-test:episode:tool:3"
    assert result.executed_count == 2
    assert result.normalized_queries == (
        ("web_search", "public valuation"),
        ("kb_search", "local valuation"),
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
    assert [item.step_id for item in result.items] == [
        "tool-batch-test:episode:tool:1",
        "tool-batch-test:episode:tool:2",
        "tool-batch-test:episode:tool:3",
    ]
    assert result.items[0].error == "RuntimeError: provider exploded"
    assert result.items[0].observation is None
    assert result.items[1].error == "tool_timeout"
    assert result.items[1].observation is None
    assert result.items[2].error == ""
    assert result.items[2].observation is not None
    assert result.items[2].observation.trace.step_id == result.items[2].step_id
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

    def wait_at_deadline(futures, *, timeout, return_when=None):
        del timeout, return_when
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


def test_wait_snapshot_timeout_cannot_publish_after_batch_cutoff(monkeypatch) -> None:
    now = [100.0]
    runner_started = Event()
    release_runner = Event()

    def monotonic() -> float:
        return now[0]

    def fetch(
        query: str,
    ) -> tuple[list[agent_research.AgentEvidence], str, ProviderTrace]:
        runner_started.set()
        release_runner.wait(timeout=1.0)
        return _evidence_result("market_data", query)

    def runner(
        query: str,
        _context: agent_research.AgentToolContext,
    ) -> tuple[list[agent_research.AgentEvidence], str, ProviderTrace]:
        return query_ledger.executed(
            "market_data",
            query,
            lambda: fetch(query),
        )

    def wait_past_cutoff(futures, *, timeout, return_when=None):
        del timeout, return_when
        future_set = set(futures)
        assert runner_started.wait(timeout=1.0)
        now[0] = 102.0
        release_runner.set()
        for future in future_set:
            future.result(timeout=1.0)
        return set(), future_set

    monkeypatch.setattr(episode_tool_batch, "monotonic", monotonic, raising=False)
    monkeypatch.setattr(episode_tool_batch, "wait", wait_past_cutoff)

    with query_ledger.query_ledger_scope() as ledger:
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
    assert ledger.summary()["executed_count"] == 0


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


def test_rejection_carries_the_actionable_reason_not_just_the_code() -> None:
    """拒绝理由必须回灌给模型，否则它只能原样重试。

    ``error`` 是分类码（invalid_arguments），对模型没有可操作性——它不知道是哪个
    参数、错在哪。2026-08-12 实测：改前基线 15 次失败里 **14 次是同一个 order_by
    形状错误一模一样地重复**，因为模型收到的 tool 消息逐字是
    ``{"ok": false, "error": "invalid_arguments", "detail": ""}``。
    detail 字段早就在结构里，只是从没被填过。

    两族检索源都点名这条：族 A 官方 agent-sdk/custom-tools「Claude sees the message
    you compose … such as which request failed or what to try instead」；族 C
    ai-agent-book ch4「审批失败后不应简单重试，而应将拒绝理由作为工具调用结果
    加入 Agent 的轨迹」。族 A 的幸存蒸馏稿把它标为「最该抄的一条」。
    """

    built = default_registry({"market_data": lambda *a, **k: None})
    built.resolve("market_data").parameters  # 该工具不吃参数

    result = ToolBatchExecutor().execute(
        (ModelToolCall("snapshot-1", "market_data", {"query": "ignored"}),),
        registry=built,
        context=_context(allowed=("market_data",)),
        remaining_slots=1,
    )

    item = result.items[0]
    assert item.status == "rejected"
    assert item.error == "invalid_arguments"
    # 关键断言：具体原因必须在，不能是空串
    assert item.detail
    assert "snapshot tool accepts no arguments" in item.detail


_DISPATCH_CLOCK_KEYS = (
    "batch_grant_asked",
    "stage_timeout_granted",
    "episode_remaining_at_dispatch",
    "remaining_slots_at_dispatch",
    "turn_elapsed_at_dispatch",
)
_R13_FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "r13-evidence-starvation-732198.json"
)


def _standard_context(*, timeout: float) -> ResearchRunContext:
    """档位用 standard 表（批窗名义 70），deadline 单独控，才能把两闸拆开。"""

    return replace(
        _context(timeout=timeout),
        policy=ResearchPolicy.for_tier("standard"),
        deadline=ResearchDeadline.from_timeout(timeout),
    )


def _clock_payload(item: ToolCallResult) -> dict[str, object]:
    clock = item.dispatch_clock
    assert clock is not None
    return clock.to_payload()


def test_expired_standard_batch_stamps_time_gate_clock_without_running_tools() -> None:
    """时间闸：名义窗仍是 70，实授 ≤0，工具零执行。"""

    runner_calls = 0

    def runner(query: str, _context: agent_research.AgentToolContext):
        nonlocal runner_calls
        runner_calls += 1
        return _evidence_result("kb_search", query)

    context = _standard_context(timeout=0.0)
    result = ToolBatchExecutor().execute(
        (
            ModelToolCall("e1", "kb_search", {"query": "医药 催化 1"}),
            ModelToolCall("e2", "kb_search", {"query": "医药 催化 2"}),
            ModelToolCall("e3", "kb_search", {"query": "医药 催化 3"}),
            ModelToolCall("e4", "kb_search", {"query": "医药 催化 4"}),
        ),
        registry=_registry(kb_search=runner),
        context=context,
        remaining_slots=4,
        turn_elapsed_at_dispatch=60.0,
    )

    asked = tool_batch_timeout_seconds(context.policy)
    assert asked == 70.0
    assert runner_calls == 0
    assert result.executed_count == 0
    assert [item.error for item in result.items] == ["tool_timeout"] * 4
    assert [item.detail for item in result.items] == [NOT_DISPATCHED_DETAIL] * 4
    for item in result.items:
        clock = _clock_payload(item)
        assert set(_DISPATCH_CLOCK_KEYS) <= set(clock)
        assert clock["batch_grant_asked"] == 70.0
        assert clock["stage_timeout_granted"] == 0.0
        assert clock["episode_remaining_at_dispatch"] == 0.0
        assert clock["remaining_slots_at_dispatch"] == 4
        assert clock["turn_elapsed_at_dispatch"] == 60.0
        assert item.queued_ms is None
        assert item.elapsed_ms is None


def test_slot_gate_keeps_count_clock_while_time_window_still_open() -> None:
    """次数闸：实授 >0，落选者是 slot 耗尽，不是窗关了。"""

    context = _standard_context(timeout=30.0)
    result = ToolBatchExecutor().execute(
        (
            ModelToolCall("keep", "kb_search", {"query": "keep"}),
            ModelToolCall("drop", "market_data", {"query": "drop"}),
        ),
        registry=_registry(),
        context=context,
        remaining_slots=1,
        turn_elapsed_at_dispatch=12.5,
    )

    assert result.items[0].status == "success"
    assert result.items[1].error == "tool_budget_exhausted"
    kept = _clock_payload(result.items[0])
    dropped = _clock_payload(result.items[1])
    assert kept["batch_grant_asked"] == 70.0
    assert kept["stage_timeout_granted"] > 0.0
    assert kept["remaining_slots_at_dispatch"] == 1
    assert kept["turn_elapsed_at_dispatch"] == 12.5
    assert dropped == kept


def test_r13_frozen_starvation_shape_replays_two_distinct_gates() -> None:
    """夹具钉住 732198 的两闸形状；重放后五元组能把时间闸和次数闸分开。"""

    fixture = json.loads(_R13_FIXTURE.read_text())
    errors = [
        event["payload"]["error"]
        for event in fixture["events"]
        if event["kind"] == "tool_error"
    ]
    assert errors == [
        "tool_timeout",
        "tool_timeout",
        "tool_timeout",
        "tool_timeout",
        "tool_budget_exhausted",
    ]
    assert all(
        "batch_grant_asked" not in event["payload"]
        for event in fixture["events"]
        if event["kind"] in {"tool_request", "tool_error"}
    )

    context = _standard_context(timeout=0.0)
    result = ToolBatchExecutor().execute(
        (
            ModelToolCall("e1", "kb_search", {"query": "q1"}),
            ModelToolCall("e2", "kb_search", {"query": "q2"}),
            ModelToolCall("e3", "kb_search", {"query": "q3"}),
            ModelToolCall("e4", "kb_search", {"query": "q4"}),
            ModelToolCall("fq", "market_data", {"query": "q5"}),
        ),
        registry=_registry(),
        context=context,
        remaining_slots=4,
        turn_elapsed_at_dispatch=60.0,
    )

    assert [item.error for item in result.items] == errors
    time_gate = [item for item in result.items if item.error == "tool_timeout"]
    slot_gate = [item for item in result.items if item.error == "tool_budget_exhausted"]
    assert len(time_gate) == 4
    assert len(slot_gate) == 1
    assert all(_clock_payload(item)["stage_timeout_granted"] <= 0.0 for item in time_gate)
    assert _clock_payload(slot_gate[0])["remaining_slots_at_dispatch"] == 4
    assert _clock_payload(slot_gate[0])["batch_grant_asked"] == 70.0
