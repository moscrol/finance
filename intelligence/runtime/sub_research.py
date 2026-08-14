"""Bounded, read-only sub-research coordination for approved deep episodes."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from contextvars import copy_context
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, replace
from threading import RLock
from typing import Literal, Protocol

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.evidence_ledger import BranchEvidenceSink
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import (
    ResearchDeadline,
    ResearchPolicy,
    ResearchRunContext,
    RootBudgetLedger,
)
from intelligence.services.research_tool_registry import ResearchToolRegistry
from intelligence.services.task_frame import TaskFrame


BranchStatus = Literal["completed", "partial", "failed"]
_BRANCH_STATUSES = frozenset({"completed", "partial", "failed"})
MAX_SUB_RESEARCH_BRANCHES = 3
MAX_CALLS_PER_BRANCH = 8
MAX_SECONDS_PER_BRANCH = 60.0


def _clean_goals(values: Iterable[str]) -> tuple[str, ...]:
    goals: list[str] = []
    for raw in values:
        goal = str(raw or "").strip()
        if not goal:
            raise ValueError("branch goals must be non-empty")
        if goal not in goals:
            goals.append(goal)
    if len(goals) > MAX_SUB_RESEARCH_BRANCHES:
        raise ValueError("sub-research supports at most three unique goals")
    return tuple(goals)


class _BranchBudgetView:
    """A non-minting child view whose consumption debits one parent ledger."""

    def __init__(
        self,
        *,
        parent: RootBudgetLedger,
        episode_id: str,
        calls: int,
        seconds: float,
    ) -> None:
        if calls <= 0 or seconds <= 0:
            raise ValueError("branch budget must be positive")
        self._parent = parent
        self.episode_id = str(episode_id or "").strip()
        if not self.episode_id:
            raise ValueError("branch episode_id must be non-empty")
        self.initial_calls = int(calls)
        self.hard_calls_cap = int(calls)
        self.initial_seconds = float(seconds)
        self.hard_seconds_cap = float(seconds)
        self.remaining_calls = int(calls)
        self.remaining_seconds = float(seconds)
        self._lock = RLock()

    @property
    def allocated_calls(self) -> int:
        return self.initial_calls

    @property
    def allocated_seconds(self) -> float:
        return self.initial_seconds

    def grant(self, grant: object) -> bool:
        del grant
        return False

    def promote_caps(
        self,
        *,
        episode_id: str,
        promotion_id: str,
        hard_calls_cap: int,
        hard_seconds_cap: float,
    ) -> bool:
        del episode_id, promotion_id, hard_calls_cap, hard_seconds_cap
        return False

    def consume_call(self, *, seconds: float) -> None:
        if seconds <= 0:
            raise ValueError("consumed call seconds must be positive")
        with self._lock:
            if self.remaining_calls <= 0:
                raise ValueError("branch call budget exhausted")
            if seconds > self.remaining_seconds + 1e-9:
                raise ValueError("branch seconds budget exhausted")
            self._parent.consume_call(seconds=seconds)
            self.remaining_calls -= 1
            self.remaining_seconds = max(0.0, self.remaining_seconds - seconds)

    def consume_seconds(self, *, seconds: float) -> None:
        if seconds < 0:
            raise ValueError("consumed seconds must be non-negative")
        with self._lock:
            if seconds > self.remaining_seconds + 1e-9:
                raise ValueError("branch seconds budget exhausted")
            self._parent.consume_seconds(seconds=seconds)
            self.remaining_seconds = max(0.0, self.remaining_seconds - seconds)

    def settle_seconds(self, *, seconds: float) -> float:
        """Clamp against this branch's share, then debit the parent, and report
        what the parent actually took.

        Settling finished work cannot be undone, so this never raises on
        overdraft. Clamping inside ``self._lock`` is what keeps concurrent
        settling from losing a debit; the parent is debited first so a child
        balance never claims seconds the root has not released. The parent may
        take *less* than asked (it clamps too), so its return value -- not the
        locally clamped request -- is what gets deducted here and returned.
        """

        try:
            requested = float(seconds)
        except (TypeError, ValueError) as exc:
            raise ValueError("settled seconds must be numeric") from exc
        if requested < 0:
            raise ValueError("settled seconds must be non-negative")
        with self._lock:
            claimed = min(requested, max(0.0, self.remaining_seconds))
            parent_settle = getattr(self._parent, "settle_seconds", None)
            if callable(parent_settle):
                settled = float(parent_settle(seconds=claimed))
            else:
                # Parent predates the Protocol method (third-party/test stub).
                # Fall back to the strict debit, treating a rejection as "the
                # parent released nothing" rather than silently crediting this
                # branch for seconds the root never gave up.
                try:
                    self._parent.consume_seconds(seconds=claimed)
                except (TypeError, ValueError):
                    return 0.0
                settled = claimed
            self.remaining_seconds = max(0.0, self.remaining_seconds - settled)
            return settled

    def to_dict(self) -> dict[str, object]:
        with self._lock:
            return {
                "episode_id": self.episode_id,
                "initial_calls": self.initial_calls,
                "hard_calls_cap": self.hard_calls_cap,
                "initial_seconds": self.initial_seconds,
                "hard_seconds_cap": self.hard_seconds_cap,
                "remaining_calls": self.remaining_calls,
                "remaining_seconds": self.remaining_seconds,
            }


@dataclass(frozen=True)
class BranchRequest:
    branch_id: str
    goal: str
    task_frame: TaskFrame
    context: ResearchRunContext
    registry: ResearchToolRegistry
    evidence_sink: BranchEvidenceSink
    is_cancelled: Callable[[], bool]


@dataclass(frozen=True)
class BranchResult:
    branch_id: str
    goal: str
    status: BranchStatus
    evidence: tuple[AgentEvidence, ...]
    traces: tuple[ProviderTrace, ...]
    gaps: tuple[str, ...]
    llm_calls: int
    tool_calls: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    error: str = ""

    def __post_init__(self) -> None:
        if self.status not in _BRANCH_STATUSES:
            raise ValueError("unsupported branch status")
        if not self.branch_id.strip() or not self.goal.strip():
            raise ValueError("branch identity and goal must be non-empty")
        if any(not isinstance(item, AgentEvidence) for item in self.evidence):
            raise TypeError("branch evidence must contain AgentEvidence values")
        if any(not isinstance(item, ProviderTrace) for item in self.traces):
            raise TypeError("branch traces must contain ProviderTrace values")
        for field_name in ("llm_calls", "tool_calls"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"branch {field_name} must be non-negative")
        for field_name in ("input_tokens", "output_tokens"):
            value = getattr(self, field_name)
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 0
            ):
                raise ValueError(f"branch {field_name} must be non-negative")


@dataclass(frozen=True)
class SubResearchResult:
    branches: tuple[BranchResult, ...]
    refused_reason: str = ""

    @property
    def tool_calls(self) -> int:
        return sum(item.tool_calls for item in self.branches)

    @property
    def llm_calls(self) -> int:
        return sum(item.llm_calls for item in self.branches)

    @property
    def input_tokens(self) -> int | None:
        values = tuple(
            item.input_tokens for item in self.branches if item.input_tokens is not None
        )
        return sum(values) if values else None

    @property
    def output_tokens(self) -> int | None:
        values = tuple(
            item.output_tokens
            for item in self.branches
            if item.output_tokens is not None
        )
        return sum(values) if values else None

    @property
    def evidence(self) -> tuple[AgentEvidence, ...]:
        return tuple(item for branch in self.branches for item in branch.evidence)

    @property
    def traces(self) -> tuple[ProviderTrace, ...]:
        return tuple(item for branch in self.branches for item in branch.traces)


class SubResearchWorker(Protocol):
    def run(self, request: BranchRequest) -> BranchResult: ...


class SubResearchCoordinator:
    """Validate and run explicit branch goals without owning research strategy."""

    def __init__(
        self,
        worker: SubResearchWorker,
        *,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> None:
        self._worker = worker
        self._is_cancelled = is_cancelled or (lambda: False)

    def run(
        self,
        *,
        goals: Iterable[str],
        task_frame: TaskFrame,
        context: ResearchRunContext,
        registry: ResearchToolRegistry,
        evidence_sink_factory: Callable[[str], BranchEvidenceSink],
    ) -> SubResearchResult:
        normalized = _clean_goals(goals)
        if not normalized:
            return SubResearchResult(())
        if context.policy.tier != "deep":
            return SubResearchResult((), "deep_mode_required")
        root = context.root_budget
        if root is None:
            return SubResearchResult((), "root_budget_required")
        if self._is_cancelled():
            return SubResearchResult((), "cancelled")
        if root.remaining_calls <= 0 or root.remaining_seconds <= 0:
            return SubResearchResult((), "root_budget_exhausted")
        if context.deadline.remaining() <= 0.0:
            return SubResearchResult((), "deadline_exhausted")

        branch_count = len(normalized)
        calls_per_branch = max(
            1,
            min(MAX_CALLS_PER_BRANCH, root.remaining_calls // branch_count),
        )
        seconds_per_branch = max(
            0.001,
            min(
                MAX_SECONDS_PER_BRANCH,
                context.deadline.remaining(),
                root.remaining_seconds / branch_count,
            ),
        )
        requests = tuple(
            self._request(
                index=index,
                goal=goal,
                task_frame=task_frame,
                context=context,
                registry=registry,
                evidence_sink_factory=evidence_sink_factory,
                root=root,
                calls=calls_per_branch,
                seconds=seconds_per_branch,
            )
            for index, goal in enumerate(normalized, start=1)
        )
        results: dict[str, BranchResult] = {}
        with ThreadPoolExecutor(
            max_workers=min(MAX_SUB_RESEARCH_BRANCHES, branch_count),
            thread_name_prefix="sub-research",
        ) as executor:
            futures: dict[Future[BranchResult], BranchRequest] = {
                executor.submit(
                    copy_context().run,
                    self._run_one,
                    request,
                ): request
                for request in requests
            }
            for future in as_completed(futures):
                request = futures[future]
                try:
                    result = future.result()
                except Exception as exc:  # failure isolation at the worker seam
                    result = BranchResult(
                        branch_id=request.branch_id,
                        goal=request.goal,
                        status="failed",
                        evidence=(),
                        traces=(),
                        gaps=("分支研究未完成",),
                        llm_calls=0,
                        tool_calls=self._consumed_tool_calls(request),
                        error=f"branch_worker_exception:{type(exc).__name__}",
                    )
                results[request.branch_id] = result
        return SubResearchResult(
            tuple(results[request.branch_id] for request in requests)
        )

    def _request(
        self,
        *,
        index: int,
        goal: str,
        task_frame: TaskFrame,
        context: ResearchRunContext,
        registry: ResearchToolRegistry,
        evidence_sink_factory: Callable[[str], BranchEvidenceSink],
        root: RootBudgetLedger,
        calls: int,
        seconds: float,
    ) -> BranchRequest:
        branch_id = f"branch-{index}"
        budget = _BranchBudgetView(
            parent=root,
            episode_id=f"{context.contract.task_id}:{branch_id}",
            calls=calls,
            seconds=seconds,
        )
        branch_context = replace(
            context,
            deadline=ResearchDeadline.from_timeout(seconds),
            policy=ResearchPolicy("quick", calls, seconds, 0.0),
            trace_parent_id=f"{context.trace_parent_id}:{branch_id}",
            root_budget=budget,
        )
        return BranchRequest(
            branch_id=branch_id,
            goal=goal,
            task_frame=task_frame,
            context=branch_context,
            registry=registry,
            evidence_sink=evidence_sink_factory(branch_id),
            is_cancelled=self._is_cancelled,
        )

    def _run_one(self, request: BranchRequest) -> BranchResult:
        if request.is_cancelled():
            return BranchResult(
                branch_id=request.branch_id,
                goal=request.goal,
                status="failed",
                evidence=(),
                traces=(),
                gaps=("分支研究已取消",),
                llm_calls=0,
                tool_calls=0,
                error="cancelled",
            )
        result = self._worker.run(request)
        if result.branch_id != request.branch_id or result.goal != request.goal:
            raise ValueError("branch worker changed branch identity")
        result = replace(
            result,
            tool_calls=self._consumed_tool_calls(request),
        )
        request.evidence_sink.append(result.evidence)
        owners = dict(request.evidence_sink.snapshot().evidence_branch_owners)
        accepted_evidence = tuple(
            item
            for item in result.evidence
            if owners.get(item.content_hash) == request.branch_id
        )
        return replace(result, evidence=accepted_evidence)

    @staticmethod
    def _consumed_tool_calls(request: BranchRequest) -> int:
        budget = request.context.root_budget
        if budget is None:
            return 0
        return max(0, int(budget.initial_calls) - int(budget.remaining_calls))


__all__ = [
    "BranchRequest",
    "BranchResult",
    "BranchStatus",
    "MAX_SUB_RESEARCH_BRANCHES",
    "SubResearchCoordinator",
    "SubResearchResult",
    "SubResearchWorker",
]
