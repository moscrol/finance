"""Citation IDs are metadata, not numeric thresholds or supporting quantities.

Regression from the frozen 8792 run_20260917_203230_060027, sentence index 20.
All judgments below use an offline passing stub; they test the mechanical gate,
not whether the financial claim is semantically supported.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from intelligence.services.agent_runtime import OutputEvidenceBinding
from intelligence.services.episode_semantic_verifier import (
    SemanticEpisodeVerifier,
    numeric_condition_unsupported,
)
from intelligence.services.episode_verifier import verify_episode_outcome
from intelligence.services.research_contract import ResearchDeadline
from intelligence.tests.test_episode_semantic_verifier import _judge, _structural


_QUALITATIVE_CONDITION = (
    "储能链收跌但涨停家数高，是「涨停集中但板块指数走弱」的分歧组合，"
    "若后续出现利多不涨+连板高标走坏，按抱团踩踏前兆判读应降级"
)


def _with_known_citations(draft: str, *, detail: str = "市场成交额与结构观察"):
    frame, structural = _structural(draft, detail=detail)
    # E27 must actually resolve in the episode. Do not put the ordinal in the
    # evidence prose: that would accidentally make it an allowed quantity.
    evidence = tuple(
        replace(structural.outcome.evidence[0], content_hash=f"citation-{index}")
        for index in range(1, 28)
    )
    outcome = replace(
        structural.outcome,
        evidence=evidence,
        bindings=(OutputEvidenceBinding("direct_assessment", (evidence[-1].content_hash,)),),
    )
    return frame, verify_episode_outcome(structural.contract, outcome)


def _verify(frame, structural):
    return SemanticEpisodeVerifier(judge_fn=_judge(True)).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )


@pytest.mark.parametrize(
    "citation",
    ["", "（E27）", "(e27)", "[E27]", "【E27】", "E27", "（E1、E27）", "（E27，e2）"],
)
def test_citation_only_condition_survives_numeric_preflight_and_verifier(citation):
    draft = f"{_QUALITATIVE_CONDITION}{citation}；"
    frame, structural = _with_known_citations(draft)

    assert numeric_condition_unsupported(structural) is False
    result = _verify(frame, structural)

    assert result.judge_status == "passed"
    assert result.status == "completed"
    assert result.public_answer == draft
    assert result.verified.outcome.draft == draft


@pytest.mark.parametrize(
    "condition",
    [
        "主线连续2日走弱",
        "主线连续两日走弱",
        "涨幅达到100%",
        "指数跌破3870点",
        "上涨家数不足1500家",
        "评分低于27",
    ],
)
def test_real_novel_threshold_remains_rejected_beside_valid_citation(condition):
    safe = "市场仍需观察。"
    unsupported = f"若{condition}则降级（E27）。"
    frame, structural = _with_known_citations(safe + unsupported)

    assert numeric_condition_unsupported(structural) is True
    result = _verify(frame, structural)

    assert result.judge_status == "rejected"
    assert result.status == "partial"
    assert result.public_answer.startswith(safe + unsupported)
    assert result.verified.outcome.draft == safe + unsupported
    assert "核验批注" in result.public_answer
    assert result.sentence_verdicts[0]["decision"] == "demoted_to_issue"
    assert "numeric_condition" in " ".join(result.issues)


def test_evidence_supported_threshold_survives_with_citation():
    draft = "若指数跌破3870点则降级（E27）。"
    frame, structural = _with_known_citations(draft, detail="观察低点为3870点。")

    assert numeric_condition_unsupported(structural) is False
    result = _verify(frame, structural)

    assert result.judge_status == "passed"
    assert result.public_answer == draft


def test_unknown_citation_still_rejected_by_ordinal_gate_not_numeric_gate():
    safe = "市场仍需观察。"
    unresolved = "若主线走弱则降级（E99）。"
    frame, structural = _with_known_citations(safe + unresolved)

    assert numeric_condition_unsupported(structural) is False
    result = _verify(frame, structural)

    assert result.public_answer.startswith(safe + unresolved)
    assert result.judge_status == "rejected"
    assert "不能作为出处" in result.public_answer
    assert "unresolved_evidence_ordinal" in " ".join(result.issues)
    assert "numeric_condition" not in " ".join(result.issues)


@pytest.mark.parametrize("field", ["title", "detail", "source"])
@pytest.mark.parametrize("citation", ["E27", "e27", "（E27）"])
def test_evidence_citation_cannot_authorize_a_real_threshold(field, citation):
    frame, structural = _structural(
        "市场仍需观察。若评分低于27则降级。",
        **{field: f"参考{citation}，仅说明定性规则。"},
    )

    assert numeric_condition_unsupported(structural) is True
    result = _verify(frame, structural)

    assert result.public_answer.startswith(structural.outcome.draft)
    assert result.judge_status == "rejected"
    assert "numeric_condition" in " ".join(result.issues)
    assert "不能当作已验证阈值" in result.public_answer


@pytest.mark.parametrize("token", ["PE10", "1.5E8", "CE4", "E0", "E027", "E1000"])
def test_non_citation_numeric_tokens_are_not_exempted(token):
    _, structural = _structural(f"若指标达到{token}则降级。")
    assert numeric_condition_unsupported(structural) is True
