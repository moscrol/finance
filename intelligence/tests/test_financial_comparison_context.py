"""Finite #835 counterexamples: a ratio comparison must carry its own period.

Scripted verifier/public-projection consumers, not natural model acceptance.
No report retrieval, production state, or model calls are permitted here.
"""
from dataclasses import replace

import pytest

from intelligence.services import llm_refine
from intelligence.services.episode_semantic_verifier import (
    SemanticEpisodeOutcome,
    SemanticEpisodeVerifier,
    recheck_material_public_delivery,
)
from intelligence.services.episode_verifier import verify_episode_outcome
from intelligence.services.research_contract import ResearchDeadline
from intelligence.tests.test_episode_semantic_verifier import _judge
from intelligence.tests.test_financial_delivery_integration import _metric_only
from intelligence.tests.test_financial_r6_regressions import SAFE


BAD_COMPARISONS = (
    "2026中报净现比0.132，较2025全年净现比1.009走弱。",
    "2026中报净现比0.132，较2025全年1.009走弱。",
    "2026中报净现比0.132，与全年不可直接比较，但较2025全年净现比1.009明显恶化。",
    "2026中报含金量0.132，相较于2025全年含金量1.009明显走弱。",
    "2026中报净现比0.132，较2026一季报0.587走弱。",
    "2025全年净现比1.009，较2026中报0.132明显改善。",
)
GOOD_CONTROLS = (
    "2026中报净现比0.132，较2025中报净现比0.806走弱。",
    "2026中报净现比0.132，较2025中报0.806走弱。",
    "2026中报净现比0.132，2025全年净现比1.009，仅分别列示，不能直接比较。",
    "2026中报净现比0.132，较2025全年1.009走弱的结论不能成立，不能直接比较。",
    "2026中报净现比0.132，2025全年仅作历史参考，2025中报净现比0.806，同比走弱。",
    "2026中报净现比0.132，存货较2025全年126.81亿元上升。",
    "2026中报净现比0.132，较2025全年存货126.81亿元上升。",
    "2026中报净现比0.132，2025全年存货126.81亿元，较2026中报198.26亿元降低。",
    "2026中报净现比0.132。较2025全年1.009走弱。",
    "2026中报存货198.26亿元，较2025全年净现比1.009走弱。",
    # No '较': whose level weakened is ambiguous, so neither reading is asserted.
    "2026中报净现比0.132，2025全年净现比1.009走弱。",
    # A bare number cannot anchor the later comparison to a specific metric.
    "2026中报净现比0.132，2025全年1.009，较2026一季报0.587走弱。",
    "2026中报净现比同比增长13.2%，较2025全年1.009走弱。",
    "2026中报净现比0.132，2025全年收入仅供参考，较2026一季报0.587走弱。",
    "2026中报净现比0.132，较2025全年净现比1.009仅分别列示，不据此判断恶化。",
)
# Some controls are ambiguous, not certified financial statements. The finite
# duration checker must defer them rather than guess another metric's context.


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    attempts = []

    def denied(*args, **kwargs):
        attempts.append((args, kwargs))
        raise AssertionError("comparison regression attempted network IO")

    for name in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection"):
        monkeypatch.setattr(name, denied)
    monkeypatch.setattr(llm_refine, "judge_provider", lambda: None)
    yield
    assert attempts == []


@pytest.mark.parametrize("mode", ["off", "llm"])
@pytest.mark.parametrize("claim", BAD_COMPARISONS)
def test_relative_ratio_comparison_reopens_metric_debt_and_preserves_citation(monkeypatch, mode, claim):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", mode)
    draft = SAFE + "[E1]。\n" + claim
    frame, verified = _metric_only(draft)
    verifier = SemanticEpisodeVerifier(judge_fn=_judge(True))
    result = verifier.verify(frame=frame, structurally_verified=verified, deadline=ResearchDeadline.from_timeout(5))
    assert claim not in result.public_answer
    assert SAFE in result.public_answer and "[E1]" in result.public_answer
    assert result.status == "partial"
    assert result.gap_output_ids == result.repair_output_ids == ("metric_evidence",)
    assert any("financial_claim_mismatch" in row["reasons"] for row in result.sentence_verdicts)
    # The verifier returns a filtered copy; the original input and evidence
    # remain intact. Projection rechecks below additionally keep outcome identity.
    assert result.verified.outcome.evidence == verified.outcome.evidence
    assert any(claim in row["sentence"] for row in result.sentence_verdicts)
    assert verified.outcome.draft == draft
    assert recheck_material_public_delivery(result) == result

    corrected_claim = GOOD_CONTROLS[0]
    corrected = verify_episode_outcome(verified.contract, replace(
        verified.outcome, draft=SAFE + "[E1]。\n" + corrected_claim,
    ))
    fixed = verifier.verify(frame=frame, structurally_verified=corrected, deadline=ResearchDeadline.from_timeout(5))
    assert fixed.status == "completed"
    assert corrected_claim in fixed.public_answer
    assert fixed.gap_output_ids == fixed.repair_output_ids == ()


@pytest.mark.parametrize("mode", ["off", "llm"])
@pytest.mark.parametrize("claim", GOOD_CONTROLS)
def test_relative_comparison_does_not_borrow_other_metric_or_sentence(monkeypatch, mode, claim):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", mode)
    frame, verified = _metric_only(SAFE + "[E1]。\n" + claim)
    result = SemanticEpisodeVerifier(judge_fn=_judge(True)).verify(
        frame=frame, structurally_verified=verified, deadline=ResearchDeadline.from_timeout(5),
    )
    assert claim in result.public_answer
    assert SAFE in result.public_answer and "[E1]" in result.public_answer
    assert result.status == "completed"
    assert result.gap_output_ids == result.repair_output_ids == ()


@pytest.mark.parametrize("claim", BAD_COMPARISONS)
def test_relative_comparison_is_rechecked_at_public_projection(claim):
    _, verified = _metric_only(SAFE + "[E1]。")
    initial = SemanticEpisodeOutcome(
        verified=verified, status="completed", public_answer=verified.outcome.draft, judge_status="passed",
    )
    result = recheck_material_public_delivery(initial, projected=initial.public_answer + "\n" + claim)
    assert claim not in result.public_answer
    assert SAFE in result.public_answer and "[E1]" in result.public_answer
    assert result.status == "partial"
    assert result.gap_output_ids == result.repair_output_ids == ("metric_evidence",)
    assert result.verified.outcome == initial.verified.outcome
