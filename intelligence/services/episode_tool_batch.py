"""Validate, schedule, and execute one model-requested read-only tool batch."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, wait
from contextvars import copy_context
from dataclasses import dataclass
from functools import partial
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


class ToolBatchExecutor:
    """Own episode query state and execute independent tool calls concurrently."""

    def __init__(self) -> None:
        self._seen_queries: set[tuple[str, str]] = set()

    def execute(
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
        for index, call in enumerate(ordered_calls):
            spec = authorized_specs.get(call.name)
            query = call.arguments.get("query")
            if spec is None:
                items[index] = ToolCallResult(
                    call,
                    "rejected",
                    error="unknown_or_unauthorized_tool",
                )
                continue
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
            )

        if any(item is None for item in items):
            raise RuntimeError("tool batch did not produce one result per call")
        return ToolBatchResult(
            items=tuple(cast(ToolCallResult, item) for item in items),
            executed_count=len(selected),
            normalized_queries=normalized_queries,
        )

    @staticmethod
    def _select(
        candidates: list[_Candidate],
        *,
        context: ResearchRunContext,
        remaining_slots: int,
    ) -> tuple[_Candidate, ...]:
        budget = max(0, int(remaining_slots))
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

    @staticmethod
    def _dispatch(
        selected: tuple[_Candidate, ...],
        *,
        items: list[ToolCallResult | None],
        registry: ResearchToolRegistry,
        context: ResearchRunContext,
    ) -> None:
        timeout = context.deadline.stage_timeout(30.0)
        executor = ThreadPoolExecutor(
            max_workers=min(4, len(selected)),
            thread_name_prefix="episode-tool",
        )
        future_candidates: dict[Future[ToolObservation], _Candidate] = {}
        try:
            for candidate in selected:
                step_id = (
                    f"{context.trace_parent_id}:episode:batch:{candidate.index + 1}"
                )
                operation = partial(
                    registry.execute,
                    candidate.call.name,
                    candidate.query,
                    context=context,
                    step_id=step_id,
                )
                worker_context = copy_context()
                future = executor.submit(worker_context.run, operation)
                future_candidates[future] = candidate

            completed, unfinished = wait(
                tuple(future_candidates),
                timeout=timeout,
            )
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
            executor.shutdown(wait=False, cancel_futures=True)


__all__ = [
    "ToolBatchExecutor",
    "ToolBatchResult",
    "ToolCallResult",
    "ToolCallStatus",
]
