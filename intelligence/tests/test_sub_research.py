from __future__ import annotations

from dataclasses import replace
from datetime import date
from contextvars import ContextVar
from threading import Barrier, Lock, Thread
import json

import pytest

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import ModelToolCall, ModelTurn
from intelligence.runtime.continuous_sub_research import ContinuousSubResearchWorker
from intelligence.services.evidence_ledger import EvidenceLedger
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import (
    InformationCutoff,
    InMemoryRootBudgetLedger,
    ResearchDeadline,
    ResearchPolicy,
    ResearchRunContext,
    ResearchTaskContract,
)
from intelligence.services.research_tool_registry import (
    ResearchToolRegistry,
    ToolSpec,
)
from intelligence.runtime.sub_research import (
    BranchResult,
    BranchRequest,
    SubResearchCoordinator,
    _BranchBudgetView,
)
from intelligence.services.task_frame import TaskFrame


def _frame() -> TaskFrame:
    return TaskFrame(
        raw_question="比较市场主线与反方驱动",
        user_goal="比较市场主线与反方驱动",
        question_type="general_finance_qa",
        subject="A股市场",
        subject_kind="market",
        market_scope="A股",
        timeframe="本周",
        required_outputs=("direct_assessment",),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="general_finance_evidence",
        confidence=0.9,
    )


def _context(*, tier: str = "deep", calls: int = 24) -> ResearchRunContext:
    policy = ResearchPolicy.for_tier(tier)
    episode_id = f"sub-research-{tier}-{calls}"
    return ResearchRunContext(
        contract=ResearchTaskContract(
            task_id=episode_id,
            question="比较市场主线与反方驱动",
            subject="A股市场",
            subject_kind="market",
            question_type="general_finance_qa",
            required_outputs=(),
            allowed_capabilities=("news_search",),
            research_tier=tier,
        ),
        deadline=ResearchDeadline.from_timeout(
            policy.total_seconds,
            synthesis_reserve=policy.synthesis_reserve,
        ),
        policy=policy,
        trace_parent_id=episode_id,
        information_cutoff=InformationCutoff(date(2026, 7, 24), "requested"),
        root_budget=InMemoryRootBudgetLedger(
            episode_id=episode_id,
            initial_calls=calls,
            hard_calls_cap=calls,
            initial_seconds=policy.total_seconds - policy.synthesis_reserve,
            hard_seconds_cap=policy.total_seconds,
        ),
    )


def _evidence(branch_id: str) -> AgentEvidence:
    return AgentEvidence(
        tool="news_search",
        title=f"{branch_id}证据",
        detail="分支返回的可核验事实",
        source=f"source-{branch_id}",
        source_date="2026-07-20",
        independent_key=f"family-{branch_id}",
        content_hash=f"hash-{branch_id}",
    )


class ScriptedWorker:
    def __init__(self, *, fail_goal: str = "") -> None:
        self.calls: list[BranchRequest] = []
        self.fail_goal = fail_goal
        self._lock = Lock()

    def run(self, request: BranchRequest) -> BranchResult:
        with self._lock:
            self.calls.append(request)
        if request.goal == self.fail_goal:
            raise RuntimeError("branch provider failed")
        request.context.root_budget.consume_call(seconds=1.0)  # type: ignore[union-attr]
        evidence = _evidence(request.branch_id)
        request.evidence_sink.append(evidence)
        return BranchResult(
            branch_id=request.branch_id,
            goal=request.goal,
            status="completed",
            evidence=(evidence,),
            traces=(
                ProviderTrace(
                    provider=f"branch:{request.branch_id}",
                    capability="news_search",
                    status="success",
                    result_count=1,
                ),
            ),
            gaps=(),
            llm_calls=1,
            tool_calls=1,
        )


def test_deep_coordinator_runs_explicit_goals_on_one_root_budget() -> None:
    context = _context()
    ledger = EvidenceLedger(information_cutoff=date(2026, 7, 24))
    worker = ScriptedWorker()

    result = SubResearchCoordinator(worker).run(
        goals=("核验公司兑现", "查找反方驱动"),
        task_frame=_frame(),
        context=context,
        registry=ResearchToolRegistry(()),
        evidence_sink_factory=ledger.branch_sink,
    )

    assert [branch.branch_id for branch in result.branches] == [
        "branch-1",
        "branch-2",
    ]
    assert result.tool_calls == 2
    assert context.root_budget is not None
    assert context.root_budget.remaining_calls == 22
    assert dict(ledger.snapshot().evidence_branch_owners) == {
        "hash-branch-1": "branch-1",
        "hash-branch-2": "branch-2",
    }
    assert all(not hasattr(branch, "answer") for branch in result.branches)


def test_quick_mode_and_excess_goals_fail_closed_without_launching_workers() -> None:
    worker = ScriptedWorker()
    ledger = EvidenceLedger()
    quick = SubResearchCoordinator(worker).run(
        goals=("不应执行",),
        task_frame=_frame(),
        context=_context(tier="standard", calls=8),
        registry=ResearchToolRegistry(()),
        evidence_sink_factory=ledger.branch_sink,
    )
    assert quick.branches == ()
    assert quick.refused_reason == "deep_mode_required"
    assert worker.calls == []

    with pytest.raises(ValueError, match="three"):
        SubResearchCoordinator(worker).run(
            goals=("一", "二", "三", "四"),
            task_frame=_frame(),
            context=_context(),
            registry=ResearchToolRegistry(()),
            evidence_sink_factory=ledger.branch_sink,
        )


def test_duplicate_goals_are_deduplicated_and_one_failure_isolated() -> None:
    context = _context()
    ledger = EvidenceLedger(information_cutoff=date(2026, 7, 24))
    worker = ScriptedWorker(fail_goal="查找反方驱动")

    result = SubResearchCoordinator(worker).run(
        goals=("核验公司兑现", "核验公司兑现", "查找反方驱动"),
        task_frame=_frame(),
        context=context,
        registry=ResearchToolRegistry(()),
        evidence_sink_factory=ledger.branch_sink,
    )

    assert len(result.branches) == 2
    assert result.branches[0].status == "completed"
    assert result.branches[1].status == "failed"
    assert result.branches[1].error == "branch_worker_exception:RuntimeError"
    assert ledger.snapshot().evidence_ids == ("hash-branch-1",)


def test_branch_budget_view_cannot_grant_or_promote_caps() -> None:
    context = _context()
    ledger = EvidenceLedger()
    worker = ScriptedWorker()
    result = SubResearchCoordinator(worker).run(
        goals=("核验公司兑现",),
        task_frame=_frame(),
        context=context,
        registry=ResearchToolRegistry(()),
        evidence_sink_factory=ledger.branch_sink,
    )

    request = worker.calls[0]
    assert request.context.root_budget is not None
    branch_budget = request.context.root_budget
    assert branch_budget.grant(object()) is False
    assert (
        branch_budget.promote_caps(
            episode_id=request.branch_id,
            promotion_id="nested",
            hard_calls_cap=24,
            hard_seconds_cap=240.0,
        )
        is False
    )
    assert result.tool_calls == 1


def test_continuous_branch_worker_returns_evidence_but_no_publishable_answer() -> None:
    class BranchModel:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def complete(self, *, messages, tools, timeout):
            self.calls.append(
                {"messages": messages, "tools": tools, "timeout": timeout}
            )
            if len(self.calls) == 1:
                return ModelTurn(
                    "",
                    (
                        ModelToolCall(
                            "branch-call-1",
                            "news_search",
                            {"query": "反方驱动 同一窗口"},
                        ),
                    ),
                    "scripted",
                    "",
                )
            return ModelTurn(
                json.dumps(
                    {
                        "status": "completed",
                        "draft": "这段分支草稿不得成为公开答案。",
                        "gaps": [],
                        "bindings": [],
                    },
                    ensure_ascii=False,
                ),
                (),
                "scripted",
                "",
            )

    def runner(query, _tool_context):
        evidence = AgentEvidence(
            tool="news_search",
            title="同窗反方证据",
            detail=f"{query} 返回反方事实",
            source="公开来源",
            source_date="2026-07-20",
            independent_key="branch-worker-family",
            content_hash="branch-worker-evidence",
        )
        return (
            [evidence],
            "branch observation",
            ProviderTrace(
                provider="test:branch-worker",
                capability="news_search",
                status="success",
                result_count=1,
            ),
        )

    model = BranchModel()
    worker = ContinuousSubResearchWorker(model)
    context = _context()
    ledger = EvidenceLedger(information_cutoff=date(2026, 7, 24))
    registry = ResearchToolRegistry(
        (
            ToolSpec(
                name="news_search",
                capability="news_search",
                description="财经新闻检索",
                cost="remote",
                freshness="current",
                runner=runner,
            ),
        )
    )

    result = SubResearchCoordinator(worker).run(
        goals=("查找反方驱动",),
        task_frame=_frame(),
        context=context,
        registry=registry,
        evidence_sink_factory=ledger.branch_sink,
    )

    assert result.branches[0].status == "completed"
    assert result.branches[0].llm_calls == 2
    assert result.branches[0].tool_calls == 1
    assert result.branches[0].evidence[0].content_hash == "branch-worker-evidence"
    assert not hasattr(result.branches[0], "answer")
    assert "这段分支草稿" not in str(result)
    assert "查找反方驱动" in str(model.calls[0]["messages"])
    assert context.root_budget is not None
    assert context.root_budget.remaining_calls == 23


def test_branch_workers_inherit_parent_contextvars() -> None:
    marker: ContextVar[str] = ContextVar("branch_test_marker", default="missing")
    token = marker.set("parent-ledger")
    observed: list[str] = []

    class ContextWorker:
        def run(self, request: BranchRequest) -> BranchResult:
            observed.append(marker.get())
            return BranchResult(
                branch_id=request.branch_id,
                goal=request.goal,
                status="partial",
                evidence=(),
                traces=(),
                gaps=("测试分支",),
                llm_calls=0,
                tool_calls=0,
            )

    try:
        SubResearchCoordinator(ContextWorker()).run(
            goals=("分支一", "分支二"),
            task_frame=_frame(),
            context=_context(),
            registry=ResearchToolRegistry(()),
            evidence_sink_factory=EvidenceLedger().branch_sink,
        )
    finally:
        marker.reset(token)

    assert observed == ["parent-ledger", "parent-ledger"]


def test_expired_parent_deadline_never_launches_a_branch() -> None:
    context = replace(_context(), deadline=ResearchDeadline.from_timeout(0.0))
    worker = ScriptedWorker()

    result = SubResearchCoordinator(worker).run(
        goals=("不应执行",),
        task_frame=_frame(),
        context=context,
        registry=ResearchToolRegistry(()),
        evidence_sink_factory=EvidenceLedger().branch_sink,
    )

    assert result.branches == ()
    assert result.refused_reason == "deadline_exhausted"
    assert worker.calls == []


def test_branch_usage_comes_from_child_budget_not_worker_claims() -> None:
    class LyingWorker:
        def run(self, request: BranchRequest) -> BranchResult:
            return BranchResult(
                branch_id=request.branch_id,
                goal=request.goal,
                status="partial",
                evidence=(),
                traces=(),
                gaps=("未执行工具",),
                llm_calls=0,
                tool_calls=99,
            )

    result = SubResearchCoordinator(LyingWorker()).run(
        goals=("核验工具计量",),
        task_frame=_frame(),
        context=_context(),
        registry=ResearchToolRegistry(()),
        evidence_sink_factory=EvidenceLedger().branch_sink,
    )

    assert result.tool_calls == 0


def test_branch_view_settles_concurrent_seconds_without_losing_a_debit() -> None:
    """Two settlements racing for the last of a branch's share must both land.

    Without clamping inside the view's own lock, both callers read the same
    ``remaining_seconds``, both pass the check, and the second debit either
    over-draws the parent or raises and gets dropped.
    """

    parent = InMemoryRootBudgetLedger(
        episode_id="branch-settle-race",
        initial_calls=4,
        hard_calls_cap=4,
        initial_seconds=10.0,
        hard_seconds_cap=10.0,
    )
    view = _BranchBudgetView(
        parent=parent,
        episode_id="branch-settle-race:branch-0",
        calls=2,
        seconds=1.0,
    )
    # Each settlement claims most of the branch share, so one must be clamped.
    requested_each = 0.9
    start = Barrier(2, timeout=10.0)
    settled: list[float] = []
    settled_lock = Lock()
    errors: list[BaseException] = []

    def settle() -> None:
        try:
            start.wait()
            amount = view.settle_seconds(seconds=requested_each)
            with settled_lock:
                settled.append(amount)
        except BaseException as exc:  # pragma: no cover - surfaced via assert
            errors.append(exc)

    threads = [Thread(target=settle) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15.0)
        assert not thread.is_alive()

    assert errors == []
    # The branch cannot pay out more than its own share...
    assert sum(settled) == pytest.approx(view.initial_seconds)
    assert view.remaining_seconds == pytest.approx(0.0, abs=1e-9)
    # ...and every second the branch reported must have left the parent too,
    # which is the invariant a lost debit would break.
    assert parent.initial_seconds - parent.remaining_seconds == pytest.approx(
        sum(settled)
    )
    assert sorted(settled) == [
        pytest.approx(view.initial_seconds - requested_each),
        pytest.approx(requested_each),
    ]


def test_branch_view_settlement_follows_the_parent_not_its_own_clamp() -> None:
    """When the root has less than the branch thinks, the root's answer wins.

    The branch share is carved out up front, so a parent drained by a sibling
    can release less than this view would locally allow. Deducting the local
    clamp instead of the parent's return value would credit the branch with
    seconds the root never gave up.
    """

    parent = InMemoryRootBudgetLedger(
        episode_id="branch-parent-clamp",
        initial_calls=4,
        hard_calls_cap=4,
        initial_seconds=5.0,
        hard_seconds_cap=5.0,
    )
    view = _BranchBudgetView(
        parent=parent,
        episode_id="branch-parent-clamp:branch-0",
        calls=2,
        seconds=4.0,
    )
    # A sibling drains the root below this branch's remaining share.
    parent.consume_seconds(seconds=4.5)
    assert parent.remaining_seconds == pytest.approx(0.5)

    settled = view.settle_seconds(seconds=3.0)

    # The parent only had 0.5 left, so that -- not the locally clamped 3.0 --
    # is what was spent and what the branch balance drops by.
    assert settled == pytest.approx(0.5)
    assert parent.remaining_seconds == pytest.approx(0.0, abs=1e-9)
    assert view.remaining_seconds == pytest.approx(3.5)
