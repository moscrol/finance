from __future__ import annotations

from datetime import date
from threading import Lock

import pytest

from intelligence.services.agent_research import AgentEvidence
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
from intelligence.services.research_tool_registry import ResearchToolRegistry
from intelligence.services.sub_research import (
    BranchResult,
    BranchRequest,
    SubResearchCoordinator,
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
