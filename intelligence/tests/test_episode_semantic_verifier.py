from __future__ import annotations

import json

import pytest

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


def _structural(draft: str, *, detail: str = "市场成交额与结构观察"):
    frame = _frame()
    evidence = AgentEvidence(
        tool="market_data",
        title="A股市场快照",
        detail=detail,
        source="行情快照",
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
        gaps=(),
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
    assert repair.calls == 1
    assert len(judge.calls) == 2  # type: ignore[attr-defined]


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
