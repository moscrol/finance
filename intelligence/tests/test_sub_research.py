from __future__ import annotations

from dataclasses import replace
from datetime import date
from contextvars import ContextVar
from threading import Barrier, Lock, Thread, enumerate as thread_enumerate
import json
import time

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
    BranchBatch,
    BranchBudgetReceipt,
    BranchResult,
    BranchRequest,
    SubResearchCoordinator,
    _BranchBudgetView,
    branch_batches_from_events,
)
from intelligence.services.agent_runtime import EpisodeEvent
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


def test_cancelled_coordinator_does_not_launch_workers() -> None:
    worker = ScriptedWorker()
    result = SubResearchCoordinator(worker, is_cancelled=lambda: True).run(
        goals=("核验公司兑现", "查找反方驱动"),
        task_frame=_frame(),
        context=_context(),
        registry=ResearchToolRegistry(()),
        evidence_sink_factory=EvidenceLedger().branch_sink,
    )

    assert result.branches == ()
    assert result.refused_reason == "cancelled"
    assert worker.calls == []


def test_cancelled_branch_start_does_not_call_worker() -> None:
    worker = ScriptedWorker()
    context = _context()
    assert context.root_budget is not None
    coordinator = SubResearchCoordinator(worker, is_cancelled=lambda: True)
    request = coordinator._request(
        index=1,
        goal="核验公司兑现",
        task_frame=_frame(),
        context=context,
        registry=ResearchToolRegistry(()),
        evidence_sink_factory=EvidenceLedger().branch_sink,
        root=context.root_budget,
        calls=1,
        seconds=2.0,
    )

    result = coordinator._run_one(request)

    assert result.status == "failed"
    assert result.error == "cancelled"
    assert worker.calls == []
    assert result.evidence == ()


def test_coordinator_run_does_not_return_while_branch_threads_are_alive() -> None:
    """分支晚到隔离靠同步排空：run 返回时 sub-research 线程必须已经结束。

    不在协调器上另造 QueryPublishGuard。卡住的分支会拖住本次调用，
    这是排空与 deadline 收敛之间的取舍，见 P3 收据。
    """

    class SlowWorker(ScriptedWorker):
        def run(self, request: BranchRequest) -> BranchResult:
            time.sleep(0.08)
            return super().run(request)

    SubResearchCoordinator(SlowWorker()).run(
        goals=("核验公司兑现", "查找反方驱动"),
        task_frame=_frame(),
        context=_context(),
        registry=ResearchToolRegistry(()),
        evidence_sink_factory=EvidenceLedger().branch_sink,
    )

    live = [
        thread.name
        for thread in thread_enumerate()
        if thread.is_alive() and thread.name.startswith("sub-research")
    ]
    assert live == []


# ---------------------------------------------------------------------------
# 分支级 trace：逐批派发账 + 预算账（2026-09-07 四遍读数的 L6 缺口）
# ---------------------------------------------------------------------------


def _event(sequence: int, kind: str, **payload: object) -> EpisodeEvent:
    return EpisodeEvent(sequence, kind, payload)


def test_branch_batches_are_cut_at_model_turns_and_classify_every_tool_error() -> None:
    """一条 model_turn 开一批；requested 恒等于五类结果之和；无工具的模型轮不算批。"""

    clock = {
        "remaining_slots_at_dispatch": 8,
        "stage_timeout_granted": 120.0,
        "episode_remaining_at_dispatch": 140.0,
    }
    events = (
        _event(1, "task"),
        _event(2, "prefetch", count=1),  # model_turn 之前的事件不归任何批
        _event(3, "model_turn", phase="research"),
        *(
            _event(4 + i, "tool_request", name=f"tool_{i}", call_id=f"c{i}", **clock)
            for i in range(6)
        ),
        _event(10, "tool_result", tool="tool_0", call_id="c0"),
        _event(11, "tool_result", tool="tool_1", call_id="c1"),
        _event(12, "tool_result", tool="tool_2", call_id="c2"),
        _event(13, "tool_result", tool="tool_3", call_id="c3"),
        _event(14, "tool_error", tool="tool_4", error="tool_budget_exhausted", call_id="c4"),
        _event(15, "tool_error", tool="tool_5", error="tool_budget_exhausted", call_id="c5"),
        _event(16, "model_turn", phase="research"),
        _event(17, "tool_request", name="tool_a", call_id="ca", remaining_slots_at_dispatch=4),
        _event(18, "tool_request", name="tool_b", call_id="cb", remaining_slots_at_dispatch=4),
        _event(19, "tool_request", name="tool_c", call_id="cc", remaining_slots_at_dispatch=4),
        _event(20, "tool_error", tool="tool_a", error="tool_timeout", call_id="ca"),
        _event(21, "tool_error", tool="tool_b", error="duplicate_query", call_id="cb"),
        _event(22, "tool_error", tool="tool_c", error="tool_exception", call_id="cc"),
        _event(23, "model_turn", phase="research"),  # finish 轮：没点工具
        _event(24, "finish", status="partial"),
    )

    batches = branch_batches_from_events(events)

    assert len(batches) == 2
    first, second = batches
    assert (first.index, first.requested, first.succeeded, first.rejected_by_cap) == (1, 6, 4, 2)
    assert (first.timed_out, first.errored, first.rejected_other) == (0, 0, 0)
    assert first.tools == tuple(f"tool_{i}" for i in range(6))
    assert (
        first.remaining_slots_at_dispatch,
        first.stage_timeout_granted,
        first.episode_remaining_at_dispatch,
    ) == (8, 120.0, 140.0)
    assert (second.index, second.requested, second.succeeded) == (2, 3, 0)
    assert (second.timed_out, second.rejected_other, second.errored) == (1, 1, 1)
    # 没测到的时钟字段留 None，to_dict 不写键——不把缺席伪装成 0。
    assert second.stage_timeout_granted is None
    assert "stage_timeout_granted" not in second.to_dict()
    assert second.to_dict()["remaining_slots_at_dispatch"] == 4
    for batch in batches:
        assert batch.requested == (
            batch.succeeded
            + batch.rejected_by_cap
            + batch.timed_out
            + batch.errored
            + batch.rejected_other
        )
    # 分支撞 deadline 时事件流常以一批工具收尾、后面没有再来一条 model_turn：
    # 最后一批也必须入账（变异：去掉末尾 flush，本条必红）。
    truncated = events[:15]  # 到第一批最后一条 tool_error 为止，后面没有 model_turn
    assert [batch.requested for batch in branch_batches_from_events(truncated)] == [6]
    assert branch_batches_from_events(()) == ()


def test_continuous_branch_worker_reports_per_batch_dispatch_and_the_cap_that_bit() -> None:
    """分支上下文带 quick 标签 → 每批帽 4：模型一轮点 5 个，第 5 个必须记成 rejected_by_cap。

    这正是 09-07 收据 §5 想量而量不到的数：分支 150s 仍 9/9 partial，候选原因是
    每批帽——现在它出现在 BranchResult.batches 里，而不是靠人翻日志。
    """

    class FiveToolModel:
        def __init__(self) -> None:
            self.calls = 0

        def complete(self, *, messages, tools, timeout):
            self.calls += 1
            if self.calls == 1:
                return ModelTurn(
                    "",
                    tuple(
                        ModelToolCall(f"branch-call-{i}", "news_search", {"query": f"反方驱动 线索{i}"})
                        for i in range(5)
                    ),
                    "scripted",
                    "",
                )
            return ModelTurn(
                json.dumps(
                    {"status": "completed", "draft": "分支草稿", "gaps": [], "bindings": []},
                    ensure_ascii=False,
                ),
                (),
                "scripted",
                "",
            )

    def runner(query, _tool_context):
        evidence = AgentEvidence(
            tool="news_search",
            title=f"{query} 标题",
            detail=f"{query} 返回反方事实",
            source="公开来源",
            source_date="2026-07-20",
            independent_key=f"family-{query}",
            content_hash=f"hash-{query}",
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
    context = _context(tier="max", calls=40)

    result = SubResearchCoordinator(ContinuousSubResearchWorker(FiveToolModel())).run(
        goals=("查找反方驱动",),
        task_frame=_frame(),
        context=context,
        registry=registry,
        evidence_sink_factory=EvidenceLedger(information_cutoff=date(2026, 7, 24)).branch_sink,
    )

    branch = result.branches[0]
    assert branch.status == "completed"
    assert branch.stop_reason  # partial / completed 一样带终局理由，不再只有 failed 才有 error
    assert [batch.to_dict() for batch in branch.batches] == [
        {
            "index": 1,
            "requested": 5,
            "succeeded": 4,
            "rejected_by_cap": 1,
            "timed_out": 0,
            "errored": 0,
            "rejected_other": 0,
            "tools": ["news_search"] * 5,
            # 分支拿到 max 档的 10 次；派发时 5 个候选里选 min(帽 4, 剩余 10) = 4。
            "remaining_slots_at_dispatch": 10,
            "stage_timeout_granted": pytest.approx(branch.batches[0].stage_timeout_granted),
            "episode_remaining_at_dispatch": pytest.approx(
                branch.batches[0].episode_remaining_at_dispatch
            ),
        }
    ]
    assert branch.budget is not None
    assert (branch.budget.allocated_calls, branch.budget.consumed_calls) == (10, 4)
    assert branch.budget.batch_call_cap == 4  # quick 标签的帽，不是 max 的 8
    assert branch.budget.allocated_seconds == pytest.approx(150.0)
    assert 0.0 <= branch.budget.remaining_seconds <= branch.budget.allocated_seconds
    assert branch.tool_calls == branch.budget.consumed_calls == 4


def test_branch_budget_receipt_comes_from_child_ledger_not_worker_claims() -> None:
    """worker 自报的预算账被协调器用子账本真值覆盖——与 tool_calls 同一条纪律。"""

    class LyingWorker:
        def run(self, request: BranchRequest) -> BranchResult:
            request.context.root_budget.consume_call(seconds=2.0)  # type: ignore[union-attr]
            return BranchResult(
                branch_id=request.branch_id,
                goal=request.goal,
                status="partial",
                evidence=(),
                traces=(),
                gaps=("只用了一次",),
                llm_calls=1,
                tool_calls=99,
                budget=BranchBudgetReceipt(
                    allocated_calls=99,
                    consumed_calls=99,
                    allocated_seconds=9999.0,
                    remaining_seconds=0.0,
                    batch_call_cap=99,
                ),
            )

    result = SubResearchCoordinator(LyingWorker()).run(
        goals=("核验预算账",),
        task_frame=_frame(),
        context=_context(tier="deep", calls=24),
        registry=ResearchToolRegistry(()),
        evidence_sink_factory=EvidenceLedger().branch_sink,
    )

    budget = result.branches[0].budget
    assert budget is not None
    assert (budget.allocated_calls, budget.consumed_calls) == (8, 1)
    assert budget.allocated_seconds == pytest.approx(60.0)
    assert budget.remaining_seconds == pytest.approx(58.0)
    assert budget.batch_call_cap == 4
    assert result.branches[0].tool_calls == 1


def test_failed_or_cancelled_branches_carry_no_budget_or_batches() -> None:
    """worker 抛异常 / 分支被取消时没有分支 Episode 可读：账不存在就不写，不伪造零值。"""

    result = SubResearchCoordinator(ScriptedWorker(fail_goal="会炸的分支")).run(
        goals=("会炸的分支",),
        task_frame=_frame(),
        context=_context(),
        registry=ResearchToolRegistry(()),
        evidence_sink_factory=EvidenceLedger().branch_sink,
    )

    failed = result.branches[0]
    assert failed.status == "failed"
    assert failed.budget is None and failed.batches == ()
    with pytest.raises(TypeError):
        BranchResult(
            branch_id="branch-1",
            goal="类型守门",
            status="partial",
            evidence=(),
            traces=(),
            gaps=(),
            llm_calls=0,
            tool_calls=0,
            batches=({"index": 1},),  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError):
        BranchBatch(
            index=0, requested=1, succeeded=1, rejected_by_cap=0,
            timed_out=0, errored=0, rejected_other=0, tools=(),
        )
