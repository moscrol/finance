"""Forward integration: financial debt cannot erase main's independent guards."""
from dataclasses import replace

import pytest

from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier
from intelligence.services.research_contract import ResearchDeadline
from intelligence.tests.test_financial_delivery_integration import BAD, GOOD, _metric_only
from intelligence.tests.test_financial_r6_regressions import SAFE
from intelligence.tests.test_judge_reason_codes import _coded_judge


@pytest.mark.parametrize("known_code", [False, True])
def test_financial_rejection_and_stock_code_partition_remain_independent(monkeypatch, known_code):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", "llm")
    claim = "相关个股包括白银有色（601212）。"
    frame, verified = _metric_only(SAFE.rstrip("。") + "[E1]。\n" + claim + "\n" + BAD)
    if known_code:
        first, *rest = verified.outcome.evidence
        verified = replace(verified, outcome=replace(verified.outcome, evidence=(
            replace(first, detail=first.detail + "白银有色601212。"), *rest,
        )))
    # The model rejects the code sentence; R6 must independently reject the bad
    # arithmetic even though the model did not flag it. Known codes retain the
    # main slot rule instead of being reclassified as mechanically fabricated.
    judge = _coded_judge((2,), ("第2句的股票代码证据里没有。",), None)
    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame, structurally_verified=verified, deadline=ResearchDeadline.from_timeout(5),
    )
    reasons = {reason for row in result.sentence_verdicts for reason in row["reasons"]}
    assert "financial_claim_mismatch" in reasons
    assert ("unknown_stock_code" in reasons) is not known_code
    assert BAD not in result.public_answer
    assert SAFE.rstrip("。") in result.public_answer and "[E1]" in result.public_answer
    assert ("601212" in result.public_answer) is known_code
    assert "metric_evidence" in result.repair_output_ids
    assert result.status == "partial"


def test_financial_numeric_gate_keeps_bound_short_date_and_citation_ordinal(monkeypatch):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", "off")
    frame, verified = _metric_only("8/22：" + SAFE + "[E1]。\n" + GOOD + "\n" + BAD)
    assert verified.outcome.evidence[0].source_date == "2026-08-22"
    result = SemanticEpisodeVerifier().verify(
        frame=frame, structurally_verified=verified, deadline=ResearchDeadline.from_timeout(5),
    )
    assert "8/22" in result.public_answer and "[E1]" in result.public_answer
    assert SAFE in result.public_answer and GOOD in result.public_answer
    assert BAD not in result.public_answer
    assert result.status == "partial" and "metric_evidence" in result.repair_output_ids
