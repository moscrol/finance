"""Citation IDs are metadata, not numeric thresholds or supporting quantities.

Regression from the frozen 8792 run_20260917_203230_060027, sentence index 20.
All judgments below use an offline passing stub; they test the mechanical gate,
not whether the financial claim is semantically supported.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from intelligence.services.agent_runtime import OutputEvidenceBinding
from intelligence.services.episode_protocol import cited_evidence_ordinals
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


@pytest.mark.usefixtures("numeric_delete_mode")
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

    assert result.judge_status == "repaired"
    assert result.public_answer == safe
    assert unsupported not in result.verified.outcome.draft
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

    assert result.public_answer == safe
    assert "unresolved_evidence_ordinal" in " ".join(result.issues)
    assert "numeric_condition" not in " ".join(result.issues)


@pytest.mark.usefixtures("numeric_delete_mode")
@pytest.mark.parametrize("field", ["title", "detail", "source"])
@pytest.mark.parametrize("citation", ["E27", "e27", "（E27）"])
def test_evidence_citation_cannot_authorize_a_real_threshold(field, citation):
    frame, structural = _structural(
        "市场仍需观察。若评分低于27则降级。",
        **{field: f"参考{citation}，仅说明定性规则。"},
    )

    assert numeric_condition_unsupported(structural) is True
    result = _verify(frame, structural)

    assert result.public_answer == "市场仍需观察。"


@pytest.mark.parametrize("token", ["PE10", "1.5E8", "E0", "E027", "E1000"])
def test_non_citation_numeric_tokens_are_not_exempted(token):
    _, structural = _structural(f"若指标达到{token}则降级。")
    assert numeric_condition_unsupported(structural) is True


def test_letter_prefixed_e_token_is_a_name_not_a_citation():
    """``CE4`` 是认证名：既不是引用 E4，也不是阈值 4。

    原先与 PE10 同列「不豁免」，那时数字门只有「剥成引用」一种豁免。2026-09-25 起
    字母紧贴数字的代号（CPU1000、H100）按名字掩掉，CE4 同类；引用语法左界仍由上面的
    PE10 钉住，这里直接钉 CE4 不被读成 E4。
    """
    draft = "若指标达到CE4则降级。"
    assert cited_evidence_ordinals(draft) == ()
    _, structural = _structural(draft)
    assert numeric_condition_unsupported(structural) is False
