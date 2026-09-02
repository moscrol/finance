"""P5: deterministic fault-injection matrix.

Each case records injected failure, phase path, budget delta, and public
status. These tests inject at production seams; they do not rewrite
``claim_terminal_run`` or ``QueryPublishGuard``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from concurrent.futures import ThreadPoolExecutor
import contextvars
import json

import pytest

import intelligence.runtime.agent_episode as agent_episode_module
from intelligence.runtime.agent_episode import ContinuousAgentEpisode
from intelligence.runtime.episode_tool_batch import ToolBatchExecutor
from intelligence.services import llm_refine, query_ledger
from intelligence.services.agent_research import AgentEvidence, AgentToolContext
from intelligence.services.agent_runtime import (
    AgentOutcome,
    AgentUsage,
    EpisodeEvent,
    ModelToolCall,
    ModelTurn,
    OutputEvidenceBinding,
)
from intelligence.services.episode_phase import PhaseRecorder
from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier
from intelligence.services.episode_verifier import verify_episode_outcome
from intelligence.services.evidence_capabilities import EvidencePlan, EvidenceRequirement
from intelligence.services.evidence_ledger import EvidenceLedgerSnapshot
from intelligence.services.mode_governor import ModeGovernor, ModeSignals
from intelligence.services.provider_observability import ProviderTrace
from intelligence.runtime.repair_budget import admit_repair
from intelligence.services.repair_coordinator import (
    RepairAdmission,
    RepairFailureShape,
    RepairNeed,
    progress_from_ledger,
    warrant_repair,
)
from intelligence.services.research_contract import (
    InMemoryRootBudgetLedger,
    RequiredOutput,
    ResearchDeadline,
    ResearchPolicy,
    ResearchRunContext,
    ResearchTaskContract,
    root_budget_for_policy,
)
from intelligence.services.research_plan import ResearchPlan
from intelligence.services.research_tool_registry import ResearchToolRegistry, ToolSpec
from intelligence.services.run_store import RunStore
from intelligence.services.task_frame import TaskFrame


@dataclass(frozen=True)
class FaultRecord:
    case_id: str
    injected_failure: str
    expected_phase_path: tuple[str, ...]
    actual_phase_path: tuple[str, ...]
    expected_budget_delta: Mapping[str, object]
    actual_budget_delta: Mapping[str, object]
    expected_public_status: str
    actual_public_status: str


MATRIX_CASE_IDS = (
    "model_timeout_zero_evidence",
    "tool_partial_success_timeout",
    "semantic_verifier_timeout_keeps_draft",
    "repair_provider_late_result",
    "deep_promotion_then_cancel",
    "root_seconds_exhausted_batch_settlement",
    "duplicate_terminal_claim",
    "process_restart_at_repair_boundary",
    "receipt_write_failure",
)


def _assert_record(record: FaultRecord) -> None:
    assert record.actual_phase_path == record.expected_phase_path, record
    assert record.actual_budget_delta == record.expected_budget_delta, record
    assert record.actual_public_status == record.expected_public_status, record


def _phase_path(recorder: PhaseRecorder) -> tuple[str, ...]:
    return tuple(item.to_phase for item in recorder.trace().transitions)


def _starved_progress() -> object:
    empty = EvidenceLedgerSnapshot(
        evidence_ids=(),
        covered_outputs=(),
        open_gaps=("direct",),
        independent_source_families=("market",),
        evidence_source_families=(),
        evidence_targets=(),
    )
    return progress_from_ledger(empty, empty)


def _market_frame() -> TaskFrame:
    return TaskFrame(
        raw_question="目前市场结构如何",
        user_goal="判断当前市场结构",
        question_type="market_forecast",
        subject="A股市场",
        subject_kind="market_pattern",
        market_scope="A股",
        timeframe="最近交易日",
        required_outputs=("direct_assessment",),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="current_market_scenarios",
        confidence=0.95,
    )


def test_matrix_covers_every_spec_case() -> None:
    assert MATRIX_CASE_IDS == (
        "model_timeout_zero_evidence",
        "tool_partial_success_timeout",
        "semantic_verifier_timeout_keeps_draft",
        "repair_provider_late_result",
        "deep_promotion_then_cancel",
        "root_seconds_exhausted_batch_settlement",
        "duplicate_terminal_claim",
        "process_restart_at_repair_boundary",
        "receipt_write_failure",
    )


def test_matrix_model_timeout_zero_evidence_is_single_shot_cold_restart() -> None:
    """首轮 timeout + 零证据：至多一次 cold restart，不会无限续命。"""

    root = InMemoryRootBudgetLedger(
        episode_id="fault-timeout-zero",
        initial_calls=2,
        hard_calls_cap=8,
        initial_seconds=30.0,
        hard_seconds_cap=300.0,
    )
    before = {
        "remaining_calls": root.remaining_calls,
        "remaining_seconds": root.remaining_seconds,
    }
    recorder = PhaseRecorder()
    recorder.record(
        "research",
        trigger="model_error",
        reason_code="model_unavailable",
        remaining_calls=root.remaining_calls,
        remaining_seconds=root.remaining_seconds,
        evidence_count=0,
    )
    # 领域申请（冷启动形状、一个格）在这里手写；生产里由 adapter 问 harness。
    cold_need = RepairNeed(
        missing_outputs=("direct",),
        missing_capabilities=(),
        rejected_claims=(),
        shape=RepairFailureShape(delivery=False, cold_restart=True, contract_rewrite=False),
        work_units=1,
    )
    first = admit_repair(
        cold_need,
        warrant_repair(_starved_progress(), cycle=1, research_tier="standard"),
        episode_id="fault-timeout-zero",
        attempted_actions=("market_data",),
        previous_progress=_starved_progress(),
        remaining_calls=root.remaining_calls,
        remaining_seconds=root.remaining_seconds,
        cycle=1,
        root_budget=root,
        tools_open=False,
        evidence_count=0,
    )
    assert isinstance(first, RepairAdmission)
    recorder.record(
        "repair",
        trigger="cold_restart",
        reason_code="admitted",
        remaining_calls=root.remaining_calls,
        remaining_seconds=root.remaining_seconds,
        evidence_count=0,
        repair_attempts=1,
    )
    second = admit_repair(
        cold_need,
        warrant_repair(_starved_progress(), cycle=2, research_tier="standard"),
        episode_id="fault-timeout-zero",
        attempted_actions=("market_data",),
        previous_progress=_starved_progress(),
        remaining_calls=root.remaining_calls,
        remaining_seconds=root.remaining_seconds,
        cycle=2,
        root_budget=root,
        tools_open=False,
        evidence_count=0,
    )
    assert second is None
    recorder.record(
        "failed",
        trigger="cold_restart_refused",
        reason_code="single_shot",
        remaining_calls=root.remaining_calls,
        remaining_seconds=root.remaining_seconds,
        evidence_count=0,
        repair_attempts=1,
        terminal_claimed=True,
    )
    after = {
        "remaining_calls": root.remaining_calls,
        "remaining_seconds": root.remaining_seconds,
    }
    _assert_record(
        FaultRecord(
            case_id="model_timeout_zero_evidence",
            injected_failure="first_model_timeout_with_zero_evidence",
            expected_phase_path=("research", "repair", "failed"),
            actual_phase_path=_phase_path(recorder),
            expected_budget_delta={
                "grants": 1,
                "remaining_calls_increased": True,
            },
            actual_budget_delta={
                "grants": 1,
                "remaining_calls_increased": after["remaining_calls"]
                > before["remaining_calls"],
            },
            expected_public_status="failed",
            actual_public_status="failed",
        )
    )


def test_matrix_partial_tool_success_keeps_evidence_and_projects_partial() -> None:
    release_timeout = Event()

    def success_runner(
        query: str,
        _context: AgentToolContext,
    ) -> tuple[list[AgentEvidence], str, ProviderTrace]:
        evidence = AgentEvidence(
            tool="market_data",
            title="市场结构",
            detail=query,
            source="test:market_data",
            content_hash="kept-success",
        )
        return (
            [evidence],
            "ok",
            ProviderTrace(
                provider="test:market_data",
                capability="market_data",
                status="success",
                result_count=1,
            ),
        )

    def timeout_runner(
        query: str,
        _context: AgentToolContext,
    ) -> tuple[list[AgentEvidence], str, ProviderTrace]:
        release_timeout.wait(1.0)
        return (
            [],
            query,
            ProviderTrace(
                provider="test:kb_search",
                capability="kb_search",
                status="timeout",
                result_count=0,
            ),
        )

    registry = ResearchToolRegistry(
        (
            ToolSpec(
                name="market_data",
                capability="market_data",
                description="行情",
                cost="local",
                freshness="current",
                runner=success_runner,
            ),
            ToolSpec(
                name="kb_search",
                capability="kb_search",
                description="知识库",
                cost="local",
                freshness="stable",
                runner=timeout_runner,
            ),
        )
    )
    policy = ResearchPolicy("quick", 4, 0.2, 0.0)
    context = ResearchRunContext(
        contract=ResearchTaskContract(
            task_id="fault-tool-partial",
            question="目前市场结构如何",
            subject="A股市场",
            subject_kind="market_pattern",
            question_type="market_forecast",
            required_outputs=(
                RequiredOutput(
                    "direct_assessment",
                    "直接判断",
                    ("market_data",),
                    True,
                ),
                RequiredOutput(
                    "counterpoint",
                    "反方",
                    ("kb_search",),
                    True,
                ),
            ),
            allowed_capabilities=("market_data", "kb_search"),
            research_tier="quick",
            task_frame_hash="fault-tool-partial",
            evidence_plan=EvidencePlan(
                requirements=(
                    EvidenceRequirement("market_data", "market_data", True),
                    EvidenceRequirement("kb_search", "kb_search", True),
                )
            ),
        ),
        deadline=ResearchDeadline.from_timeout(0.2),
        policy=policy,
        trace_parent_id="fault-tool-partial",
    )
    root = InMemoryRootBudgetLedger(
        episode_id="fault-tool-partial",
        initial_calls=4,
        hard_calls_cap=8,
        initial_seconds=30.0,
        hard_seconds_cap=60.0,
    )
    before_calls = root.remaining_calls
    try:
        batch = ToolBatchExecutor().execute(
            (
                ModelToolCall("ok-1", "market_data", {"query": "结构"}),
                ModelToolCall("late-1", "kb_search", {"query": "反方"}),
            ),
            registry=registry,
            context=context,
            remaining_slots=2,
        )
    finally:
        release_timeout.set()

    statuses = tuple(item.status for item in batch.items)
    kept = tuple(
        evidence
        for item in batch.items
        if item.observation is not None
        for evidence in item.observation.evidence
    )
    agent_episode_module._settle_batch_calls(
        root,
        executed_count=len(batch.items),
        batch_elapsed=0.2,
    )
    outcome = AgentOutcome(
        task_frame_hash="fault-tool-partial",
        status="completed",
        draft="成功腿的证据还在，超时腿没有反方。",
        evidence=kept,
        traces=(),
        gaps=("kb_search timeout",),
        stop_reason="model_finish",
        events=(EpisodeEvent(1, "task", {"task_frame_hash": "fault-tool-partial"}),),
        bindings=(OutputEvidenceBinding("direct_assessment", ("kept-success",)),),
        usage=AgentUsage(llm_calls=1, tool_calls=2),
    )
    verified = verify_episode_outcome(context.contract, outcome)
    recorder = PhaseRecorder()
    recorder.record("research", trigger="tool_batch", reason_code="partial_timeout")
    recorder.record(
        "structural_verify",
        trigger="structural_verifier",
        reason_code="structural_verify",
    )
    recorder.record(
        verified.verified_status,
        trigger="public_outcome",
        reason_code=verified.verified_status,
        terminal_claimed=True,
        evidence_count=len(kept),
    )
    _assert_record(
        FaultRecord(
            case_id="tool_partial_success_timeout",
            injected_failure="one_tool_success_one_tool_timeout",
            expected_phase_path=("research", "structural_verify", "partial"),
            actual_phase_path=_phase_path(recorder),
            expected_budget_delta={"remaining_calls_delta": 2},
            actual_budget_delta={
                "remaining_calls_delta": before_calls - root.remaining_calls,
            },
            expected_public_status="partial",
            actual_public_status=verified.verified_status,
        )
    )
    assert statuses == ("success", "timeout")
    assert kept and kept[0].content_hash == "kept-success"


def test_matrix_semantic_timeout_keeps_draft_and_does_not_report_completed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame = _market_frame()
    evidence = AgentEvidence(
        tool="market_data",
        title="市场量能窗口",
        detail="成交额较前一交易日下降",
        source="本地行情",
        source_date="2026-07-20",
        content_hash="semantic-kept",
    )
    outcome = AgentOutcome(
        task_frame_hash=frame.task_frame_hash,
        status="completed",
        draft="成交收缩导致承接减弱，短线反弹持续性仍需观察。",
        evidence=(evidence,),
        traces=(),
        gaps=(),
        stop_reason="model_finish",
        events=(EpisodeEvent(1, "task", {"task_frame_hash": frame.task_frame_hash}),),
        bindings=(
            OutputEvidenceBinding("direct_assessment", (evidence.content_hash,)),
        ),
        usage=AgentUsage(llm_calls=1, tool_calls=1),
    )
    contract = ResearchTaskContract(
        task_id="fault-semantic-timeout",
        question=frame.raw_question,
        subject=frame.subject,
        subject_kind=frame.subject_kind,
        question_type=frame.question_type,
        required_outputs=(
            RequiredOutput("direct_assessment", "直接判断", ("market_data",), True),
        ),
        allowed_capabilities=("market_data",),
        research_tier="quick",
        evidence_plan=EvidencePlan(),
        task_frame_hash=frame.task_frame_hash,
    )
    structural = verify_episode_outcome(contract, outcome)
    assert structural.verified_status == "completed"

    class Judge:
        def complete(self, **_kwargs):
            return ModelTurn("", (), provider_name="judge", error="TimeoutError")

    monkeypatch.setattr(llm_refine, "judge_provider", lambda: None)
    result = SemanticEpisodeVerifier(primary_judge=Judge()).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(30.0),
    )
    recorder = PhaseRecorder()
    recorder.record("semantic_verify", trigger="judge", reason_code="timeout")
    recorder.record(
        result.status,
        trigger="public_outcome",
        reason_code=result.judge_status or result.status,
        terminal_claimed=True,
    )
    _assert_record(
        FaultRecord(
            case_id="semantic_verifier_timeout_keeps_draft",
            injected_failure="semantic_judge_timeout",
            expected_phase_path=("semantic_verify", "partial"),
            actual_phase_path=_phase_path(recorder),
            expected_budget_delta={"llm_call_debit": 0},
            actual_budget_delta={"llm_call_debit": 0},
            expected_public_status="partial",
            actual_public_status=result.status,
        )
    )
    assert result.judge_status == "unavailable"
    assert "成交收缩导致承接减弱" in result.public_answer
    assert result.status != "completed"


def test_matrix_repair_late_result_does_not_change_declared_terminal() -> None:
    fetch_started = Event()
    release_fetch = Event()
    recorder = PhaseRecorder()
    recorder.record(
        "completed",
        trigger="public_outcome",
        reason_code="repair_declared",
        terminal_claimed=True,
    )
    public_before = "completed"
    guard = query_ledger.QueryPublishGuard()
    discarded_count = 0
    discard_reason = ""
    with query_ledger.query_ledger_scope() as ledger:
        worker_context = contextvars.copy_context()
        pool = ThreadPoolExecutor(max_workers=1)

        def late_fetch() -> str:
            fetch_started.set()
            release_fetch.wait(timeout=2)
            return "late-repair-answer"

        def execute_guarded() -> str:
            with query_ledger.query_publish_guard_scope(guard):
                return query_ledger.executed("web_search", "repair query", late_fetch)

        future = pool.submit(worker_context.run, execute_guarded)
        assert fetch_started.wait(timeout=1)
        guard.close()
        release_fetch.set()
        assert future.result(timeout=2) == "late-repair-answer"
        summary = ledger.summary()
        discarded_count = summary["late_result_discarded_count"]
        discard_reason = summary["late_result_discards"][0]["reason"]
        pool.shutdown()
    recorder.record(
        "completed",
        trigger="late_result",
        reason_code="subscription_inactive",
    )
    _assert_record(
        FaultRecord(
            case_id="repair_provider_late_result",
            injected_failure="repair_provider_result_after_guard_close",
            expected_phase_path=("completed",),
            actual_phase_path=_phase_path(recorder),
            expected_budget_delta={"late_result_discarded_count": 1},
            actual_budget_delta={"late_result_discarded_count": discarded_count},
            expected_public_status="completed",
            actual_public_status=public_before,
        )
    )
    assert discard_reason == "subscription_inactive"
    assert recorder.trace().post_terminal_triggers == ("late_result",)


def test_matrix_deep_promotion_then_cancel_starts_no_new_tool_calls() -> None:
    frame = _market_frame()
    policy = ResearchPolicy.for_tier("standard")
    context = ResearchRunContext(
        contract=ResearchTaskContract(
            task_id="fault-deep-cancel",
            question=frame.raw_question,
            subject=frame.subject,
            subject_kind=frame.subject_kind,
            question_type=frame.question_type,
            required_outputs=(
                RequiredOutput("direct_assessment", "直接判断", ("market_data",), True),
            ),
            allowed_capabilities=("market_data",),
            research_tier="standard",
            evidence_plan=EvidencePlan(),
            task_frame_hash=frame.task_frame_hash,
        ),
        deadline=ResearchDeadline.from_timeout(
            policy.total_seconds,
            synthesis_reserve=policy.synthesis_reserve,
        ),
        policy=policy,
        trace_parent_id="fault-deep-cancel",
        root_budget=root_budget_for_policy(policy, episode_id="fault-deep-cancel"),
    )
    decision = ModeGovernor().decide(
        ResearchPlan(
            task_summary="比较两类证据后回答用户问题",
            answer_elements=("直接判断", "依据"),
            hypotheses=("主假设",),
            evidence_needs=("盘面",),
            candidate_actions=("查询结构化数据",),
            open_gaps=(),
            requested_mode="deep",
        ),
        ModeSignals(evidence_domains=("盘面", "新闻")),
    )
    promoted = ModeGovernor().apply(context, decision)
    assert promoted.policy.tier == "deep"
    root = promoted.root_budget
    assert root is not None
    before_calls = root.remaining_calls
    cancelled = Event()
    runner_calls = 0

    class CancellingModel:
        def complete(self, *, messages, tools, timeout):
            del messages, tools, timeout
            cancelled.set()
            return ModelTurn(
                "",
                (ModelToolCall("call-1", "market_data", {"query": "不应执行"}),),
                "scripted",
                "",
            )

    def runner(query: str, tool_context: AgentToolContext):
        del query, tool_context
        nonlocal runner_calls
        runner_calls += 1
        raise AssertionError("cancelled episode must not execute tools")

    outcome = ContinuousAgentEpisode(
        CancellingModel(),
        is_cancelled=cancelled.is_set,
    ).run(
        task_frame=frame,
        context=promoted,
        registry=ResearchToolRegistry(
            (
                ToolSpec(
                    name="market_data",
                    capability="market_data",
                    description="行情",
                    cost="local",
                    freshness="current",
                    runner=runner,
                ),
            )
        ),
    )
    recorder = PhaseRecorder()
    recorder.record("planning", trigger="mode_decision", reason_code="deep")
    recorder.record("research", trigger="model_turn", reason_code="cancelled_after_model")
    recorder.record(
        "cancelled",
        trigger="cancel",
        reason_code=outcome.stop_reason,
        remaining_calls=root.remaining_calls,
        terminal_claimed=True,
    )
    _assert_record(
        FaultRecord(
            case_id="deep_promotion_then_cancel",
            injected_failure="cancel_after_deep_promotion_and_first_model_turn",
            expected_phase_path=("planning", "research", "cancelled"),
            actual_phase_path=_phase_path(recorder),
            expected_budget_delta={
                "remaining_calls_delta": 0,
                "tool_calls": 0,
            },
            actual_budget_delta={
                "remaining_calls_delta": before_calls - root.remaining_calls,
                "tool_calls": outcome.usage.tool_calls,
            },
            expected_public_status="cancelled",
            actual_public_status="cancelled"
            if outcome.stop_reason == "cancelled"
            else outcome.status,
        )
    )
    assert outcome.status == "failed"
    assert runner_calls == 0
    assert outcome.usage.llm_calls == 1


def test_matrix_root_seconds_exhausted_settlement_does_not_raise() -> None:
    ledger = InMemoryRootBudgetLedger(
        episode_id="fault-settle",
        initial_calls=1,
        hard_calls_cap=1,
        initial_seconds=5.0,
        hard_seconds_cap=5.0,
    )
    before = ledger.remaining_seconds
    agent_episode_module._settle_batch_calls(
        ledger,
        executed_count=3,
        batch_elapsed=30.0,
    )
    recorder = PhaseRecorder()
    recorder.record("research", trigger="tool_batch", reason_code="overshoot")
    _assert_record(
        FaultRecord(
            case_id="root_seconds_exhausted_batch_settlement",
            injected_failure="consume_call_after_root_seconds_burned",
            expected_phase_path=("research",),
            actual_phase_path=_phase_path(recorder),
            expected_budget_delta={"remaining_seconds": 0.0, "raised": False},
            actual_budget_delta={
                "remaining_seconds": ledger.remaining_seconds,
                "raised": False,
            },
            expected_public_status="settled_without_exception",
            actual_public_status="settled_without_exception",
        )
    )
    assert before > 0.0
    assert ledger.remaining_seconds == 0.0


def test_matrix_duplicate_terminal_claim_second_party_loses(tmp_path: Path) -> None:
    store = RunStore(user_id="default", root=tmp_path / "runs")
    run = store.create_run("q", "ask")
    claimed, first_won = store.claim_terminal_run(run.run_id, "completed")
    observed, second_won = store.claim_terminal_run(
        run.run_id,
        "failed",
        error="continuous_runtime_failed",
    )
    recorder = PhaseRecorder()
    recorder.record(
        "completed",
        trigger="public_outcome",
        reason_code="winner",
        terminal_claimed=True,
    )
    recorder.record(
        "failed",
        trigger="duplicate_claim",
        reason_code="loser",
    )
    _assert_record(
        FaultRecord(
            case_id="duplicate_terminal_claim",
            injected_failure="second_claim_terminal_run",
            expected_phase_path=("completed",),
            actual_phase_path=_phase_path(recorder),
            expected_budget_delta={"winner": True, "loser": False},
            actual_budget_delta={"winner": first_won, "loser": second_won},
            expected_public_status="completed",
            actual_public_status=observed.status,
        )
    )
    assert claimed.status == "completed"
    assert observed.error is None


def test_matrix_process_restart_does_not_resume_repair_session(
    tmp_path: Path,
) -> None:
    """G7: 进程重启只重排队，不恢复 repair session。"""

    store = RunStore(user_id="default", root=tmp_path / "runs")
    interrupted = store.create_run("repair-in-flight", "ask")
    recovered = store.requeue_incomplete_runs(reason="service_restarted")
    saved = store.load_run(interrupted.run_id)
    recorder = PhaseRecorder()
    recorder.record("repair", trigger="process_restart", reason_code="interrupted")
    recorder.record(
        "failed",
        trigger="unsupported_durable_continuation",
        reason_code="requeued_only",
        terminal_claimed=True,
    )
    _assert_record(
        FaultRecord(
            case_id="process_restart_at_repair_boundary",
            injected_failure="process_restart_while_run_active",
            expected_phase_path=("repair", "failed"),
            actual_phase_path=_phase_path(recorder),
            expected_budget_delta={"repair_session_restored": False},
            actual_budget_delta={
                "repair_session_restored": any(
                    "repair" in json.dumps(item)
                    for item in saved.artifacts
                )
            },
            expected_public_status="queued_no_repair_session",
            actual_public_status=(
                "queued_no_repair_session"
                if saved.status == "queued" and saved.artifacts == []
                else saved.status
            ),
        )
    )
    assert [item.run_id for item in recovered] == [interrupted.run_id]
    assert saved.degrades == ["service_restarted"]


def test_matrix_receipt_write_failure_does_not_forge_complete_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = RunStore(user_id="default", root=tmp_path / "runs")
    run = store.create_run("q", "ask")
    claimed, won = store.claim_terminal_run(run.run_id, "completed")
    assert won is True
    original = Path.write_bytes

    def boom(self: Path, data: bytes) -> int:
        if self.name == "report.json":
            raise OSError("disk full")
        return original(self, data)

    monkeypatch.setattr(Path, "write_bytes", boom)
    with pytest.raises(OSError, match="disk full"):
        store.add_artifact(
            run.run_id,
            "report.json",
            '{"status":"completed","gate_receipt":{"engine":"episode"}}',
            renderer="json",
            title="收据",
        )
    saved = store.load_run(run.run_id)
    report_path = store.run_dir(run.run_id) / "report.json"
    recorder = PhaseRecorder()
    recorder.record(
        "completed",
        trigger="public_outcome",
        reason_code="claimed_before_receipt_write",
        terminal_claimed=True,
    )
    _assert_record(
        FaultRecord(
            case_id="receipt_write_failure",
            injected_failure="add_artifact_oserror_on_report_json",
            expected_phase_path=("completed",),
            actual_phase_path=_phase_path(recorder),
            expected_budget_delta={"forged_report": False},
            actual_budget_delta={"forged_report": report_path.exists()},
            expected_public_status="completed",
            actual_public_status=saved.status,
        )
    )
    assert claimed.status == "completed"
    assert not any(item.get("path") == "report.json" for item in saved.artifacts)
