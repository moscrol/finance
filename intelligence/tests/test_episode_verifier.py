from __future__ import annotations

import pytest

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import (
    AgentOutcome,
    AgentUsage,
    EpisodeEvent,
    OutputEvidenceBinding,
)
from intelligence.services.episode_verifier import verify_episode_outcome
from intelligence.services.evidence_capabilities import (
    EvidencePlan,
    EvidenceRequirement,
)
from intelligence.services.research_contract import RequiredOutput, ResearchTaskContract


TASK_HASH = "task-frame-hash"


def _contract(
    *,
    outputs: tuple[RequiredOutput, ...] | None = None,
    evidence_plan: EvidencePlan | None = None,
) -> ResearchTaskContract:
    return ResearchTaskContract(
        task_id="episode-test",
        question="市场怎么看",
        subject="A股市场",
        subject_kind="market_pattern",
        question_type="market_forecast",
        required_outputs=outputs
        or (
            RequiredOutput(
                "direct_assessment",
                "直接判断",
                ("market_data", "news_search"),
            ),
            RequiredOutput(
                "evidence_boundary",
                "证据边界",
                ("market_data", "news_search"),
            ),
        ),
        allowed_capabilities=("market_data", "news_search", "mainline_context"),
        evidence_plan=evidence_plan or EvidencePlan(),
        task_frame_hash=TASK_HASH,
    )


def _evidence(tool: str, content_hash: str) -> AgentEvidence:
    return AgentEvidence(
        tool=tool,
        title=f"{tool} evidence",
        detail="可核验事实",
        source="test-source",
        content_hash=content_hash,
    )


def _outcome(
    *,
    status: str = "completed",
    draft: str = "基于证据，当前只能做条件化判断。",
    evidence: tuple[AgentEvidence, ...] = (),
    bindings: tuple[OutputEvidenceBinding, ...] = (),
    task_hash: str = TASK_HASH,
) -> AgentOutcome:
    return AgentOutcome(
        task_frame_hash=task_hash,
        status=status,  # type: ignore[arg-type]
        draft=draft,
        evidence=evidence,
        traces=(),
        gaps=(),
        stop_reason="model_finish",
        events=(
            EpisodeEvent(
                1,
                "task",
                {"task_frame_hash": task_hash, "question": "市场怎么看"},
            ),
        ),
        bindings=bindings,
        usage=AgentUsage(llm_calls=2, tool_calls=1),
    )


def test_valid_evidence_bindings_complete_the_episode() -> None:
    market = _evidence("market_data", "market-1")
    outcome = _outcome(
        evidence=(market,),
        bindings=(
            OutputEvidenceBinding("direct_assessment", ("market-1",)),
            OutputEvidenceBinding("evidence_boundary", ("market-1",)),
        ),
    )

    verified = verify_episode_outcome(_contract(), outcome)

    assert verified.verified_status == "completed"
    assert verified.completion.business_status == "complete"
    assert {item.status for item in verified.completion.outputs} == {"fulfilled"}
    assert verified.issues == ()


def test_shared_hash_is_structural_only_and_does_not_overload_supports() -> None:
    market = _evidence("market_data", "market-1")
    outcome = _outcome(
        evidence=(market,),
        bindings=(
            OutputEvidenceBinding("direct_assessment", ("market-1",)),
            OutputEvidenceBinding("evidence_boundary", ("market-1",)),
        ),
    )

    verified = verify_episode_outcome(_contract(), outcome)

    assert verified.verified_status == "completed"
    assert all(item.status == "fulfilled" for item in verified.completion.outputs)


def test_missing_required_output_downgrades_completed_outcome() -> None:
    market = _evidence("market_data", "market-1")
    outcome = _outcome(
        evidence=(market,),
        bindings=(OutputEvidenceBinding("direct_assessment", ("market-1",)),),
    )

    verified = verify_episode_outcome(_contract(), outcome)

    assert verified.verified_status == "partial"
    assert verified.completion.missing_required[0].output_id == "evidence_boundary"


def test_unknown_evidence_hash_fails_closed() -> None:
    market = _evidence("market_data", "market-1")
    outcome = _outcome(
        evidence=(market,),
        bindings=(
            OutputEvidenceBinding("direct_assessment", ("unknown",)),
            OutputEvidenceBinding("evidence_boundary", ("market-1",)),
        ),
    )

    verified = verify_episode_outcome(_contract(), outcome)

    assert verified.verified_status == "partial"
    assert any("unknown evidence hash" in issue for issue in verified.issues)


def test_wrong_tool_type_cannot_launder_a_required_output() -> None:
    web = _evidence("web_search", "web-1")
    outcome = _outcome(
        evidence=(web,),
        bindings=(
            OutputEvidenceBinding("direct_assessment", ("web-1",)),
            OutputEvidenceBinding("evidence_boundary", ("web-1",)),
        ),
    )

    verified = verify_episode_outcome(_contract(), outcome)

    assert verified.verified_status == "partial"
    assert any("evidence type" in issue for issue in verified.issues)


def test_explicit_gap_is_partial_not_fake_completed() -> None:
    outcome = _outcome(
        status="partial",
        draft="目前无法确认。",
        bindings=(
            OutputEvidenceBinding(
                "direct_assessment",
                (),
                "仍缺同日市场数据",
            ),
            OutputEvidenceBinding(
                "evidence_boundary",
                (),
                "仍缺同日市场数据",
            ),
        ),
    )

    verified = verify_episode_outcome(_contract(), outcome)

    assert verified.verified_status == "partial"
    assert all(item.status == "missing" for item in verified.completion.outputs)


def test_fulfilled_bindings_override_partial_model_confidence() -> None:
    market = _evidence("market_data", "market-1")
    outcome = _outcome(
        status="partial",
        evidence=(market,),
        bindings=(
            OutputEvidenceBinding("direct_assessment", ("market-1",)),
            OutputEvidenceBinding("evidence_boundary", ("market-1",)),
        ),
    )

    verified = verify_episode_outcome(_contract(), outcome)

    assert verified.verified_status == "completed"
    assert verified.completion.business_status == "complete"


def test_missing_mandatory_evidence_capability_downgrades_completion() -> None:
    contract = _contract(
        outputs=(
            RequiredOutput(
                "direct_assessment",
                "直接判断",
                ("market_data", "mainline_context"),
            ),
        ),
        evidence_plan=EvidencePlan(
            "current_mainline",
            (
                EvidenceRequirement("MARKET_DAILY", "market_data", True),
                EvidenceRequirement("D4", "mainline_context", True),
            ),
        ),
    )
    market = _evidence("market_data", "market-1")
    outcome = _outcome(
        evidence=(market,),
        bindings=(OutputEvidenceBinding("direct_assessment", ("market-1",)),),
    )

    verified = verify_episode_outcome(contract, outcome)

    assert verified.verified_status == "partial"
    assert any("mandatory capability" in issue for issue in verified.issues)


def test_contract_and_outcome_task_hash_must_match() -> None:
    outcome = _outcome(status="partial", task_hash="different-hash")

    with pytest.raises(ValueError, match="task frame hash"):
        verify_episode_outcome(_contract(), outcome)
