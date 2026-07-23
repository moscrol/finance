from __future__ import annotations

from dataclasses import replace
import json
import time

import pytest

from intelligence.services import answer_model, llm_refine
from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import (
    AgentOutcome,
    AgentUsage,
    EpisodeEvent,
    ModelTurn,
    OutputEvidenceBinding,
)
from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier
from intelligence.services.episode_verifier import verify_episode_outcome
from intelligence.services.evidence_capabilities import EvidencePlan
from intelligence.services.research_contract import (
    RequiredOutput,
    ResearchPolicy,
    ResearchRunContext,
    ResearchTaskContract,
)
from intelligence.services.research_contract import ResearchDeadline
from intelligence.services.task_frame import TaskFrame


def _frame() -> TaskFrame:
    return TaskFrame(
        raw_question="当前市场怎么看？",
        user_goal="判断当前市场结构",
        question_type="market_forecast",
        subject="A股市场",
        subject_kind="market_pattern",
        market_scope="A股",
        timeframe="当前",
        required_outputs=("direct_assessment",),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="current_market_scenarios",
        confidence=0.95,
    )


def _structural(
    draft: str,
    *,
    detail: str = "市场成交额与结构观察",
    title: str = "A股市场快照",
    source: str = "行情快照",
    gaps: tuple[str, ...] = (),
):
    frame = _frame()
    evidence = AgentEvidence(
        tool="market_data",
        title=title,
        detail=detail,
        source=source,
        source_date="2026-07-22",
        content_hash="HASH_PRIVATE_SENTINEL",
    )
    contract = ResearchTaskContract(
        task_id="semantic-test",
        question=frame.raw_question,
        subject=frame.subject,
        subject_kind=frame.subject_kind,
        question_type=frame.question_type,
        required_outputs=(
            RequiredOutput("direct_assessment", "直接判断", ("market_data",), True),
        ),
        allowed_capabilities=("market_data",),
        evidence_plan=EvidencePlan(),
        task_frame_hash=frame.task_frame_hash,
    )
    outcome = AgentOutcome(
        task_frame_hash=frame.task_frame_hash,
        status="completed",
        draft=draft,
        evidence=(evidence,),
        traces=(),
        gaps=gaps,
        stop_reason="model_finish",
        events=(
            EpisodeEvent(
                1,
                "task",
                {"task_frame_hash": frame.task_frame_hash},
            ),
        ),
        bindings=(
            OutputEvidenceBinding("direct_assessment", (evidence.content_hash,)),
        ),
        usage=AgentUsage(llm_calls=1, tool_calls=1),
    )
    return frame, verify_episode_outcome(contract, outcome)


def _judge(
    passed: bool, *, rejected: tuple[int, ...] = (), issues: tuple[str, ...] = ()
):
    calls: list[dict[str, object]] = []

    def run(request):
        calls.append(request)
        if calls.__len__() > 1:
            return {"passed": True, "rejected_sentence_indexes": [], "issues": []}
        return {
            "passed": passed,
            "rejected_sentence_indexes": list(rejected),
            "issues": list(issues),
        }

    run.calls = calls  # type: ignore[attr-defined]
    return run


class _Repair:
    def __init__(self, draft: str):
        self.draft = draft
        self.calls = 0

    def repair(self, **_kwargs):
        self.calls += 1
        return ModelTurn(
            json.dumps(
                {
                    "status": "completed",
                    "draft": self.draft,
                    "gaps": [],
                    "bindings": [
                        {
                            "output_id": "direct_assessment",
                            "evidence_hashes": ["HASH_PRIVATE_SENTINEL"],
                            "gap": "",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            (),
            "primary",
            "",
        )


class _OutcomeRepair:
    def __init__(self, structural, *, add_evidence: bool = False):
        self.structural = structural
        self.add_evidence = add_evidence
        self.calls = 0

    def repair(self, **_kwargs):
        self.calls += 1
        original = self.structural.outcome
        evidence = original.evidence
        if self.add_evidence:
            evidence = (
                *evidence,
                AgentEvidence(
                    tool="web_search",
                    title="NEW_PRIVATE_EVIDENCE",
                    detail="repair invented detail",
                    source="repair provider",
                    content_hash="new-repair-hash",
                ),
            )
        return AgentOutcome(
            task_frame_hash=original.task_frame_hash,
            status="completed",
            draft="修复后的保守判断。",
            evidence=evidence,
            traces=original.traces,
            gaps=original.gaps,
            stop_reason="semantic_repair",
            events=original.events,
            bindings=original.bindings,
            usage=original.usage,
        )


class _TypeErrorRepair:
    def __init__(self):
        self.calls = 0

    def repair(self, **_kwargs):
        self.calls += 1
        raise TypeError("internal provider type error")


class _ContextRecordingRepair(_Repair):
    def __init__(self, draft: str):
        super().__init__(draft)
        self.contexts: list[ResearchRunContext] = []

    def repair(self, **kwargs):
        self.contexts.append(kwargs["context"])
        return super().repair(**kwargs)


def test_unsupported_causality_is_rejected_and_not_publicly_completed() -> None:
    frame, structural = _structural("市场下跌。政策变化导致了下跌。")
    judge = _judge(False, rejected=(2,), issues=("因果证据不足",))
    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert result.status == "partial"
    assert result.judge_status == "rejected"
    assert "政策变化导致了下跌" not in result.public_answer


def test_shared_hash_semantics_are_rejected_only_by_semantic_judge() -> None:
    frame = replace(
        _frame(),
        required_outputs=("direct_assessment", "evidence_boundary"),
    )
    evidence = AgentEvidence(
        tool="market_data",
        title="A股市场快照",
        detail="仅包含市场涨跌事实，不支持完整证据边界说明",
        source="行情快照",
        content_hash="shared-market-hash",
    )
    contract = ResearchTaskContract(
        task_id="shared-hash-semantic-test",
        question=frame.raw_question,
        subject=frame.subject,
        subject_kind=frame.subject_kind,
        question_type=frame.question_type,
        required_outputs=(
            RequiredOutput("direct_assessment", "直接判断", ("market_data",), True),
            RequiredOutput("evidence_boundary", "证据边界", ("market_data",), True),
        ),
        allowed_capabilities=("market_data",),
        evidence_plan=EvidencePlan(),
        task_frame_hash=frame.task_frame_hash,
    )
    outcome = AgentOutcome(
        task_frame_hash=frame.task_frame_hash,
        status="completed",
        draft="市场下跌。现有证据已完整覆盖判断边界。",
        evidence=(evidence,),
        traces=(),
        gaps=(),
        stop_reason="model_finish",
        events=(EpisodeEvent(1, "task", {"task_frame_hash": frame.task_frame_hash}),),
        bindings=(
            OutputEvidenceBinding("direct_assessment", (evidence.content_hash,)),
            OutputEvidenceBinding("evidence_boundary", (evidence.content_hash,)),
        ),
        usage=AgentUsage(llm_calls=1, tool_calls=1),
    )
    structural = verify_episode_outcome(contract, outcome)
    assert structural.verified_status == "completed"

    result = SemanticEpisodeVerifier(
        judge_fn=_judge(False, rejected=(2,), issues=("重复证据不支持证据边界",))
    ).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.status == "partial"
    assert result.judge_status == "rejected"
    assert "现有证据已完整覆盖判断边界" not in result.public_answer


@pytest.mark.parametrize(
    "draft",
    [
        "这是另一主体的结论。",
        "当前数据已经过时但仍代表现在。",
        "市场一定上涨 9999 点。",
    ],
)
def test_semantic_rejection_downgrades_subject_time_and_number_claims(
    draft: str,
) -> None:
    frame, structural = _structural(draft)
    judge = _judge(False, rejected=(1,), issues=("证据与句子不一致",))
    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.status == "partial"
    assert result.judge_status == "rejected"


def test_one_repair_and_two_judge_calls() -> None:
    frame, structural = _structural("市场下跌。政策变化导致了下跌。")
    judge = _judge(False, rejected=(2,), issues=("因果证据不足",))
    repair = _Repair("市场下跌，当前证据不足以确认政策因果。")
    result = SemanticEpisodeVerifier(judge_fn=judge, finalizer=repair).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.status == "completed"
    assert result.judge_status == "repaired"
    assert result.correlated_judge is True
    assert repair.calls == 1
    assert len(judge.calls) == 2  # type: ignore[attr-defined]


def test_injected_passing_judge_records_correlated_limit() -> None:
    frame, structural = _structural("市场当前偏弱。")
    result = SemanticEpisodeVerifier(judge_fn=_judge(True)).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.status == "completed"
    assert result.correlated_judge is True


def test_independent_judge_provider_records_uncorrelated(monkeypatch) -> None:
    frame, structural = _structural("市场当前偏弱。")
    provider = llm_refine.LLMProvider("judge", "secret", "https://judge.invalid", "j")
    monkeypatch.setattr(llm_refine, "judge_provider", lambda: provider)
    monkeypatch.setattr(
        llm_refine,
        "complete",
        lambda *_args, **_kwargs: (
            '{"passed":true,"rejected_sentence_indexes":[],"issues":[]}',
            provider,
            "",
        ),
    )
    result = SemanticEpisodeVerifier().verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.status == "completed"
    assert result.correlated_judge is False


def test_independent_judge_provider_takes_priority_over_injected_judge(
    monkeypatch,
) -> None:
    frame, structural = _structural("市场当前偏弱。")
    provider = llm_refine.LLMProvider("judge", "secret", "https://judge.invalid", "j")
    independent_calls: list[object] = []
    injected_calls: list[object] = []
    monkeypatch.setattr(llm_refine, "judge_provider", lambda: provider)

    def independent(*_args, **_kwargs):
        independent_calls.append(object())
        return (
            '{"passed":true,"rejected_sentence_indexes":[],"issues":[]}',
            provider,
            "",
        )

    monkeypatch.setattr(llm_refine, "complete", independent)
    result = SemanticEpisodeVerifier(
        judge_fn=lambda request: injected_calls.append(request)
    ).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.status == "completed"
    assert result.correlated_judge is False
    assert len(independent_calls) == 1
    assert injected_calls == []


def test_repair_cannot_add_or_replace_episode_evidence() -> None:
    frame, structural = _structural("市场下跌。政策变化导致了下跌。")
    judge = _judge(False, rejected=(2,), issues=("因果证据不足",))
    repair = _OutcomeRepair(structural, add_evidence=True)
    result = SemanticEpisodeVerifier(judge_fn=judge, finalizer=repair).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert repair.calls == 1
    assert result.status == "partial"
    assert result.judge_status == "rejected"
    assert result.verified.outcome.evidence == structural.outcome.evidence
    assert "NEW_PRIVATE_EVIDENCE" not in result.public_answer
    assert "new-repair-hash" not in result.public_answer


def test_repair_rejects_agent_outcome_even_when_evidence_is_unchanged() -> None:
    frame, structural = _structural("市场下跌。政策变化导致了下跌。")
    judge = _judge(False, rejected=(2,), issues=("因果证据不足",))
    repair = _OutcomeRepair(structural)
    result = SemanticEpisodeVerifier(judge_fn=judge, finalizer=repair).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert repair.calls == 1
    assert len(judge.calls) == 1  # type: ignore[attr-defined]
    assert result.status == "partial"
    assert result.judge_status == "rejected"


def test_repair_internal_type_error_is_not_retried() -> None:
    frame, structural = _structural("市场下跌。政策变化导致了下跌。")
    repair = _TypeErrorRepair()
    result = SemanticEpisodeVerifier(
        judge_fn=_judge(False, rejected=(2,), issues=("因果证据不足",)),
        finalizer=repair,
    ).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert repair.calls == 1
    assert result.status == "partial"


def test_judge_outage_is_partial_and_never_exposes_raw_draft() -> None:
    frame, structural = _structural(
        "RAW_PROVIDER_SENTINEL market_data HASH_PRIVATE_SENTINEL。"
    )

    def outage(_request):
        raise TimeoutError("RAW_PROVIDER_SENTINEL")

    result = SemanticEpisodeVerifier(judge_fn=outage).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.status == "partial"
    assert result.public_answer != structural.outcome.draft
    assert "RAW_PROVIDER_SENTINEL" not in result.public_answer
    assert "HASH_PRIVATE_SENTINEL" not in result.public_answer
    assert "market_data" not in result.public_answer


def test_late_judge_pass_is_unavailable_and_cannot_complete() -> None:
    frame, structural = _structural("市场当前偏弱。")

    def late_pass(_request):
        time.sleep(0.02)
        return {"passed": True, "rejected_sentence_indexes": [], "issues": []}

    result = SemanticEpisodeVerifier(judge_fn=late_pass).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(0.005),
    )
    assert result.status == "partial"
    assert result.judge_status == "unavailable"
    assert any("deadline" in issue for issue in result.issues)


def test_late_rejudge_pass_is_unavailable_and_cannot_complete() -> None:
    frame, structural = _structural("市场下跌。政策变化导致了下跌。")
    calls = 0

    def reject_then_late_pass(_request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return {
                "passed": False,
                "rejected_sentence_indexes": [2],
                "issues": ["因果证据不足"],
            }
        time.sleep(0.03)
        return {"passed": True, "rejected_sentence_indexes": [], "issues": []}

    result = SemanticEpisodeVerifier(
        judge_fn=reject_then_late_pass,
        finalizer=_Repair("市场下跌，政策因果仍待核验。"),
    ).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(0.02),
    )
    assert calls == 2
    assert result.status == "partial"
    assert result.judge_status == "unavailable"
    assert any("deadline" in issue for issue in result.issues)


def test_repair_rebuilds_context_with_current_deadline_and_exact_contract() -> None:
    frame, structural = _structural("市场下跌。政策变化导致了下跌。")
    assert structural.contract is not None
    injected_context = ResearchRunContext(
        contract=replace(
            structural.contract,
            task_id="stale-context",
            task_frame_hash="stale-context-hash",
        ),
        deadline=ResearchDeadline.from_timeout(999),
        policy=ResearchPolicy.for_tier("quick"),
        trace_parent_id="stale-trace-parent",
        today="2026-07-23",
        latest_data_date="2026-07-22",
    )
    verify_deadline = ResearchDeadline.from_timeout(5)
    repair = _ContextRecordingRepair("市场下跌，政策因果仍待核验。")
    result = SemanticEpisodeVerifier(
        judge_fn=_judge(False, rejected=(2,), issues=("因果证据不足",)),
        finalizer=repair,
        context=injected_context,
    ).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=verify_deadline,
    )
    assert result.status == "completed"
    assert len(repair.contexts) == 1
    repair_context = repair.contexts[0]
    assert repair_context.deadline is verify_deadline
    assert repair_context.contract is structural.contract
    assert repair_context.today == "2026-07-23"
    assert repair_context.latest_data_date == "2026-07-22"


@pytest.mark.parametrize(
    "wrapped",
    [
        'I think {"passed":true,"rejected_sentence_indexes":[],"issues":[]}',
        '```json\n{"passed":true,"rejected_sentence_indexes":[],"issues":[]}\n```',
        '{"passed":true,"rejected_sentence_indexes":[],"issues":[]} trailing',
    ],
)
def test_judge_requires_one_unwrapped_json_object(wrapped: str) -> None:
    frame, structural = _structural("市场当前偏弱。")
    result = SemanticEpisodeVerifier(judge_fn=lambda _request: wrapped).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.status == "partial"
    assert result.judge_status == "unavailable"


@pytest.mark.parametrize(
    "invalid",
    [
        {"passed": True, "rejected_sentence_indexes": []},
        {"passed": True, "rejected_sentence_indexes": [], "issues": "none"},
        answer_model.GroundingJudgeReport(False, (), ()),
        {
            "passed": True,
            "rejected_sentence_indexes": [],
            "issues": {object()},
        },
    ],
)
def test_invalid_judge_shape_fails_closed_without_raising(invalid: object) -> None:
    frame, structural = _structural("市场当前偏弱。")
    result = SemanticEpisodeVerifier(judge_fn=lambda _request: invalid).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.status == "partial"
    assert result.judge_status == "unavailable"


def test_clean_strict_json_report_is_accepted() -> None:
    frame, structural = _structural("市场当前偏弱。")
    result = SemanticEpisodeVerifier(
        judge_fn=lambda _request: (
            '{"passed":true,"rejected_sentence_indexes":[],"issues":[]}'
        )
    ).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.status == "completed"


def test_empty_public_projection_preserves_passed_judge_status() -> None:
    frame, structural = _structural("provider=OpenAI。")
    result = SemanticEpisodeVerifier(judge_fn=_judge(True)).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.status == "partial"
    assert result.judge_status == "passed"
    assert "public projection empty" in result.issues


def test_empty_repaired_projection_preserves_repaired_judge_status() -> None:
    frame, structural = _structural("市场下跌。政策变化导致了下跌。")
    judge = _judge(False, rejected=(2,), issues=("因果证据不足",))
    result = SemanticEpisodeVerifier(
        judge_fn=judge,
        finalizer=_Repair("provider=OpenAI。"),
    ).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.status == "partial"
    assert result.judge_status == "repaired"
    assert "public projection empty" in result.issues


def test_public_projection_filters_casefolded_private_tokens_everywhere() -> None:
    frame, structural = _structural(
        "市场当前偏弱。\nprovider=OpenAI。\nprovider_attempt=2。\n"
        "_provider_trace=Zhipu。\nendpoint=https://private。\n"
        "system_prompt=PRIVATE。\nhash=PRIVATE。\nMARKET_DATA。\n"
        "hash_private_sentinel。"
    )
    result = SemanticEpisodeVerifier(judge_fn=_judge(True)).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.status == "completed"
    for sentinel in (
        "provider=",
        "provider_attempt",
        "_provider_trace",
        "endpoint=",
        "system_prompt",
        "hash=",
        "market_data",
        "hash_private_sentinel",
    ):
        assert sentinel.casefold() not in result.public_answer.casefold()


def test_public_sanitizer_keeps_provider_brand_in_financial_fact() -> None:
    frame, structural = _structural(
        "OpenAI资本开支上升，带动光模块需求；当前 drawdown（最大回撤）仍需观察。"
    )
    result = SemanticEpisodeVerifier(judge_fn=_judge(True)).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.status == "completed"
    assert "OpenAI资本开支上升" in result.public_answer
    assert "drawdown" in result.public_answer


def test_public_sanitizer_keeps_raw_material_and_valuation_model_facts() -> None:
    frame, structural = _structural(
        "Raw material prices rose 8%。\n估值 model=DCF，折现率9%。"
    )
    result = SemanticEpisodeVerifier(judge_fn=_judge(True)).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.status == "completed"
    assert "Raw material prices rose 8%" in result.public_answer
    assert "估值 model=DCF，折现率9%" in result.public_answer


def test_public_citation_keeps_business_brand_but_filters_provider_diagnostic() -> None:
    frame, structural = _structural(
        "市场当前偏弱。",
        title="OpenAI公司公告",
        source="公开来源",
    )
    result = SemanticEpisodeVerifier(judge_fn=_judge(True)).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.status == "completed"
    assert "市场当前偏弱" in result.public_answer
    assert "OpenAI公司公告" in result.public_answer

    frame, structural = _structural(
        "市场当前偏弱。",
        title="provider=OpenAI",
        source="_provider_trace=Zhipu",
    )
    diagnostic = SemanticEpisodeVerifier(judge_fn=_judge(True)).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert diagnostic.status == "completed"
    assert "provider=" not in diagnostic.public_answer
    assert "_provider_trace" not in diagnostic.public_answer


def test_structural_gap_filters_private_control_tokens_case_insensitively() -> None:
    frame, structural = _structural(
        "未核验草稿。",
        gaps=("system_prompt=PRIVATE OpenAI HASH_PRIVATE_SENTINEL MARKET_DATA",),
    )
    original = structural.outcome
    partial_outcome = AgentOutcome(
        task_frame_hash=original.task_frame_hash,
        status="partial",
        draft=original.draft,
        evidence=original.evidence,
        traces=original.traces,
        gaps=original.gaps,
        stop_reason=original.stop_reason,
        events=original.events,
        bindings=(),
        usage=original.usage,
    )
    assert structural.contract is not None
    partial = verify_episode_outcome(structural.contract, partial_outcome)
    result = SemanticEpisodeVerifier(judge_fn=_judge(True)).verify(
        frame=frame,
        structurally_verified=partial,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.status == "partial"
    for sentinel in ("system_prompt", "OpenAI", "hash_private", "market_data"):
        assert sentinel.casefold() not in result.public_answer.casefold()


def test_public_gap_never_projects_business_context_free_text() -> None:
    frame, structural = _structural(
        "未核验草稿。",
        gaps=("OpenAI资本开支证据仍缺",),
    )
    original = structural.outcome
    partial_outcome = AgentOutcome(
        task_frame_hash=original.task_frame_hash,
        status="partial",
        draft=original.draft,
        evidence=original.evidence,
        traces=original.traces,
        gaps=original.gaps,
        stop_reason=original.stop_reason,
        events=original.events,
        bindings=(),
        usage=original.usage,
    )
    assert structural.contract is not None
    partial = verify_episode_outcome(structural.contract, partial_outcome)
    result = SemanticEpisodeVerifier().verify(
        frame=frame,
        structurally_verified=partial,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.status == "partial"
    assert "OpenAI资本开支证据仍缺" not in result.public_answer
    assert "直接判断" in result.public_answer


def test_public_gap_never_includes_internal_semantic_repair_issues() -> None:
    frame, structural = _structural("市场下跌。政策变化导致了下跌。")
    result = SemanticEpisodeVerifier(
        judge_fn=_judge(False, rejected=(2,), issues=("因果证据不足",))
    ).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.status == "partial"
    assert "semantic" not in result.public_answer.casefold()
    assert "judge" not in result.public_answer.casefold()
    assert "repair unavailable" not in result.public_answer.casefold()


@pytest.mark.parametrize("judge_mode", ["rejected", "unavailable"])
def test_public_gap_never_projects_adversarial_outcome_gap(judge_mode: str) -> None:
    poisoned = "政策变化导致了下跌 PRIVATE_GAP_SENTINEL"
    frame, structural = _structural("市场下跌。", gaps=(poisoned,))
    if judge_mode == "rejected":
        judge_fn = _judge(False, rejected=(1,), issues=("证据不足",))
    else:

        def judge_fn(_request):
            return "invalid"

    result = SemanticEpisodeVerifier(judge_fn=judge_fn).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.status == "partial"
    assert poisoned not in result.public_answer
    assert "PRIVATE_GAP_SENTINEL" not in result.public_answer
    assert "直接判断" in result.public_answer


def test_public_gap_never_projects_adversarial_binding_gap() -> None:
    poisoned = "政策变化导致了下跌 PRIVATE_BINDING_SENTINEL"
    frame, structural = _structural("未核验草稿。")
    original = structural.outcome
    partial_outcome = AgentOutcome(
        task_frame_hash=original.task_frame_hash,
        status="partial",
        draft=original.draft,
        evidence=original.evidence,
        traces=original.traces,
        gaps=(poisoned,),
        stop_reason=original.stop_reason,
        events=original.events,
        bindings=(OutputEvidenceBinding("direct_assessment", (), poisoned),),
        usage=original.usage,
    )
    assert structural.contract is not None
    partial = verify_episode_outcome(structural.contract, partial_outcome)
    result = SemanticEpisodeVerifier().verify(
        frame=frame,
        structurally_verified=partial,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.status == "partial"
    assert "PRIVATE_BINDING_SENTINEL" not in result.public_answer
    assert "直接判断" in result.public_answer


def test_structural_partial_is_not_upgraded_or_judged() -> None:
    frame, structural = _structural("市场下跌。")
    # Remove the only required binding by verifying a partial outcome.
    partial_outcome = AgentOutcome(
        task_frame_hash=structural.outcome.task_frame_hash,
        status="partial",
        draft=structural.outcome.draft,
        evidence=structural.outcome.evidence,
        traces=structural.outcome.traces,
        gaps=structural.outcome.gaps,
        stop_reason=structural.outcome.stop_reason,
        events=structural.outcome.events,
        bindings=(),
        usage=structural.outcome.usage,
    )
    contract = structural.contract
    assert contract is not None
    partial = verify_episode_outcome(contract, partial_outcome)
    calls: list[object] = []
    result = SemanticEpisodeVerifier(
        judge_fn=lambda request: calls.append(request)
    ).verify(
        frame=frame,
        structurally_verified=partial,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.status == "partial"
    assert not calls


def test_missing_structural_contract_fails_closed_without_judge() -> None:
    frame, structural = _structural("市场当前偏弱。")
    calls: list[object] = []
    result = SemanticEpisodeVerifier(
        judge_fn=lambda request: calls.append(request)
    ).verify(
        frame=frame,
        structurally_verified=replace(structural, contract=None),
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.status == "partial"
    assert result.judge_status == "unavailable"
    assert calls == []
    assert "当前市场怎么看" in result.public_answer
    assert any("contract" in issue for issue in result.issues)


def test_cross_turn_frame_hash_mismatch_never_reuses_a_share_outcome() -> None:
    _market_frame, structural = _structural("A股市场当前偏弱。")
    stock_frame = replace(
        _frame(),
        raw_question="瑞华泰怎么看？",
        user_goal="判断瑞华泰当前逻辑",
        subject="瑞华泰",
        subject_kind="company",
    )
    calls: list[object] = []
    result = SemanticEpisodeVerifier(
        judge_fn=lambda request: calls.append(request)
    ).verify(
        frame=stock_frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.status == "partial"
    assert result.judge_status == "unavailable"
    assert calls == []
    assert "瑞华泰怎么看" in result.public_answer
    assert "A股市场当前偏弱" not in result.public_answer
    assert any("hash mismatch" in issue for issue in result.issues)


def test_contract_hash_mismatch_fails_closed_without_judge() -> None:
    frame, structural = _structural("市场当前偏弱。")
    assert structural.contract is not None
    mismatched = replace(
        structural,
        contract=replace(structural.contract, task_frame_hash="other-contract-hash"),
    )
    calls: list[object] = []
    result = SemanticEpisodeVerifier(
        judge_fn=lambda request: calls.append(request)
    ).verify(
        frame=frame,
        structurally_verified=mismatched,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.status == "partial"
    assert calls == []
    assert any("hash mismatch" in issue for issue in result.issues)
