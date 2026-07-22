"""Validate, schedule, and execute one model-requested read-only tool batch."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Executor, Future, ThreadPoolExecutor, wait
from contextvars import copy_context
from dataclasses import dataclass
from functools import partial
from threading import Lock
from time import monotonic
from typing import Literal, cast

from intelligence.services import query_ledger
from intelligence.services.agent_runtime import ModelToolCall
from intelligence.services.episode_policy import tool_priority
from intelligence.services.research_contract import ResearchRunContext
from intelligence.services.research_tool_registry import (
    ResearchToolRegistry,
    ToolObservation,
    ToolSpec,
)


ToolCallStatus = Literal["success", "empty", "rejected", "timeout", "error"]
MAX_BATCH_TOOL_CALLS = 4
MAX_GLOBAL_TOOL_WORKERS = 8
_SHARED_TOOL_EXECUTOR = ThreadPoolExecutor(
    max_workers=MAX_GLOBAL_TOOL_WORKERS,
    thread_name_prefix="episode-tool",
)


@dataclass(frozen=True)
class ToolCallResult:
    call: ModelToolCall
    status: ToolCallStatus
    observation: ToolObservation | None = None
    error: str = ""


@dataclass(frozen=True)
class ToolBatchResult:
    items: tuple[ToolCallResult, ...]
    executed_count: int
    normalized_queries: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class _Candidate:
    index: int
    call: ModelToolCall
    query: str
    normalized_query: str
    spec: ToolSpec

    @property
    def key(self) -> tuple[str, str]:
        return (self.call.name, self.normalized_query)


def _run_with_publish_guard(
    guard: query_ledger.QueryPublishGuard,
    operation: Callable[[], ToolObservation],
) -> ToolObservation:
    with query_ledger.query_publish_guard_scope(guard):
        return operation()


class EpisodeToolBatchSession:
    """Own episode query state and execute independent tool calls concurrently."""

    def __init__(self, *, executor: Executor | None = None) -> None:
        self._seen_queries: set[tuple[str, str]] = set()
        self._lock = Lock()
        self._next_call_sequence = 1
        self._executor = executor if executor is not None else _SHARED_TOOL_EXECUTOR

    def execute(
        self,
        calls: tuple[ModelToolCall, ...],
        *,
        registry: ResearchToolRegistry,
        context: ResearchRunContext,
        remaining_slots: int,
    ) -> ToolBatchResult:
        with self._lock:
            return self._execute_locked(
                calls,
                registry=registry,
                context=context,
                remaining_slots=remaining_slots,
            )

    def _execute_locked(
        self,
        calls: tuple[ModelToolCall, ...],
        *,
        registry: ResearchToolRegistry,
        context: ResearchRunContext,
        remaining_slots: int,
    ) -> ToolBatchResult:
        ordered_calls = tuple(calls)
        items: list[ToolCallResult | None] = [None] * len(ordered_calls)
        authorized_specs = {
            spec.name: spec
            for spec in registry.authorized_specs(context.contract.allowed_capabilities)
        }

        candidates: list[_Candidate] = []
        batch_queries: set[tuple[str, str]] = set()
        batch_call_ids: set[str] = set()
        for index, call in enumerate(ordered_calls):
            if call.call_id in batch_call_ids:
                items[index] = ToolCallResult(
                    call,
                    "rejected",
                    error="duplicate_call_id",
                )
                continue
            batch_call_ids.add(call.call_id)

            spec = authorized_specs.get(call.name)
            if spec is None:
                items[index] = ToolCallResult(
                    call,
                    "rejected",
                    error="unknown_or_unauthorized_tool",
                )
                continue
            if set(call.arguments) != {"query"}:
                items[index] = ToolCallResult(
                    call,
                    "rejected",
                    error="invalid_arguments",
                )
                continue
            query = call.arguments["query"]
            if not isinstance(query, str) or not query.strip():
                items[index] = ToolCallResult(
                    call,
                    "rejected",
                    error="invalid_query",
                )
                continue

            normalized = query_ledger.normalize_query(query)
            key = (call.name, normalized)
            if key in self._seen_queries or key in batch_queries:
                items[index] = ToolCallResult(
                    call,
                    "rejected",
                    error="duplicate_query",
                )
                continue
            batch_queries.add(key)
            candidates.append(_Candidate(index, call, query, normalized, spec))

        selected = self._select(
            candidates,
            context=context,
            remaining_slots=remaining_slots,
        )
        selected_indexes = {candidate.index for candidate in selected}
        for candidate in candidates:
            if candidate.index not in selected_indexes:
                items[candidate.index] = ToolCallResult(
                    candidate.call,
                    "rejected",
                    error="tool_budget_exhausted",
                )

        selected_in_model_order = tuple(sorted(selected, key=lambda item: item.index))
        timeout = context.deadline.stage_timeout(30.0)
        if selected and timeout <= 0.0:
            for candidate in selected:
                items[candidate.index] = ToolCallResult(
                    candidate.call,
                    "timeout",
                    error="tool_timeout",
                )
            return self._result(items, executed_count=0, normalized_queries=())

        step_ids: dict[int, str] = {}
        for candidate in selected_in_model_order:
            step_ids[candidate.index] = (
                f"{context.trace_parent_id}:episode:tool:{self._next_call_sequence}"
            )
            self._next_call_sequence += 1
        self._seen_queries.update(candidate.key for candidate in selected)
        normalized_queries = tuple(
            candidate.key for candidate in selected_in_model_order
        )
        if selected:
            self._dispatch(
                selected,
                items=items,
                registry=registry,
                context=context,
                step_ids=step_ids,
                timeout=timeout,
            )

        return self._result(
            items,
            executed_count=len(selected),
            normalized_queries=normalized_queries,
        )

    @staticmethod
    def _result(
        items: list[ToolCallResult | None],
        *,
        executed_count: int,
        normalized_queries: tuple[tuple[str, str], ...],
    ) -> ToolBatchResult:
        if any(item is None for item in items):
            raise RuntimeError("tool batch did not produce one result per call")
        return ToolBatchResult(
            items=tuple(cast(ToolCallResult, item) for item in items),
            executed_count=executed_count,
            normalized_queries=normalized_queries,
        )

    @staticmethod
    def _select(
        candidates: list[_Candidate],
        *,
        context: ResearchRunContext,
        remaining_slots: int,
    ) -> tuple[_Candidate, ...]:
        budget = min(MAX_BATCH_TOOL_CALLS, max(0, int(remaining_slots)))
        priority = tool_priority(
            context.contract.question_type,
            context.contract.evidence_plan.mandatory_capabilities,
        )
        ranks = {name: index for index, name in enumerate(priority)}
        default_rank = len(ranks)

        def rank(candidate: _Candidate) -> tuple[int, int]:
            return (
                min(
                    ranks.get(candidate.call.name, default_rank),
                    ranks.get(candidate.spec.capability, default_rank),
                ),
                candidate.index,
            )

        return tuple(sorted(candidates, key=rank)[:budget])

    def _dispatch(
        self,
        selected: tuple[_Candidate, ...],
        *,
        items: list[ToolCallResult | None],
        registry: ResearchToolRegistry,
        context: ResearchRunContext,
        step_ids: dict[int, str],
        timeout: float,
    ) -> None:
        publish_cutoff = monotonic() + timeout
        publish_guard = query_ledger.QueryPublishGuard(
            publish_cutoff=publish_cutoff,
            monotonic=monotonic,
        )
        future_candidates: dict[Future[ToolObservation], _Candidate] = {}
        try:
            for candidate in selected:
                operation = partial(
                    registry.execute,
                    candidate.call.name,
                    candidate.query,
                    context=context,
                    step_id=step_ids[candidate.index],
                )
                worker_context = copy_context()
                guarded_operation = partial(
                    _run_with_publish_guard,
                    publish_guard,
                    operation,
                )
                future = self._executor.submit(worker_context.run, guarded_operation)
                future_candidates[future] = candidate

            completed, unfinished = wait(
                tuple(future_candidates),
                timeout=max(0.0, publish_cutoff - monotonic()),
            )
            publish_guard.close()
            for future in unfinished:
                future.cancel()
                candidate = future_candidates[future]
                items[candidate.index] = ToolCallResult(
                    candidate.call,
                    "timeout",
                    error="tool_timeout",
                )
            for future in completed:
                candidate = future_candidates[future]
                try:
                    observation = future.result()
                except TimeoutError:
                    items[candidate.index] = ToolCallResult(
                        candidate.call,
                        "timeout",
                        error="tool_timeout",
                    )
                    continue
                except Exception as exc:
                    detail = f"{type(exc).__name__}: {str(exc)[:160]}"
                    items[candidate.index] = ToolCallResult(
                        candidate.call,
                        "error",
                        error=detail,
                    )
                    continue
                items[candidate.index] = ToolCallResult(
                    candidate.call,
                    "success" if observation.evidence else "empty",
                    observation=observation,
                )
        finally:
            publish_guard.close()


class ToolBatchExecutor:
    """Stateless factory for episode-scoped tool batch sessions."""

    def __init__(self, *, executor: Executor | None = None) -> None:
        self._executor = executor if executor is not None else _SHARED_TOOL_EXECUTOR

    def new_session(self) -> EpisodeToolBatchSession:
        return EpisodeToolBatchSession(executor=self._executor)

    def execute(
        self,
        calls: tuple[ModelToolCall, ...],
        *,
        registry: ResearchToolRegistry,
        context: ResearchRunContext,
        remaining_slots: int,
    ) -> ToolBatchResult:
        """Execute one batch in a fresh ephemeral session.

        Multi-batch Episodes must create one session with :meth:`new_session`
        and reuse that session explicitly.
        """

        return self.new_session().execute(
            calls,
            registry=registry,
            context=context,
            remaining_slots=remaining_slots,
        )


__all__ = [
    "EpisodeToolBatchSession",
    "ToolBatchExecutor",
    "ToolBatchResult",
    "ToolCallResult",
    "ToolCallStatus",
]
