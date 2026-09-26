"""ARL-0003: a withheld value never exempts later assertions or adjacent periods."""
from dataclasses import replace

import pytest

from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier, recheck_material_public_delivery
from intelligence.services.research_contract import ResearchDeadline
from intelligence.services.research_delivery_checks import calculation_copy_findings, remove_findings
from intelligence.tests.test_episode_semantic_verifier import _structural
from intelligence.tests.test_research_delivery_checks import _financial_evidence

MARK = "〔比率对应关系待核对〕"


@pytest.mark.parametrize("hedge", ["待核对", "为待核对", "为**待核对**", "是`待核对`"])
@pytest.mark.parametrize("following", ["，实际为1.587", "，该值为1.587", "，实际为待核对，实际为1.587"])
def test_withheld_slot_does_not_exempt_later_ratio(hedge, following):
    draft = f"收入可核[E1]，2026中报含金量{hedge}{following}，2025中报含金量为0.289。"
    findings = calculation_copy_findings(draft, _financial_evidence())
    assert findings
    kept = remove_findings(draft, findings)
    assert "收入可核[E1]" in kept and "2025中报含金量为0.289" in kept
    assert "1.587" not in kept or MARK in kept
    assert remove_findings(kept, calculation_copy_findings(kept, _financial_evidence())) == kept


@pytest.mark.parametrize("ratio", [
    "2026中报含金量待核对，实际为1.587。",
    "2026中报含金量为待核对，实际为1.587。",
])
@pytest.mark.parametrize("mode", ["off", "llm"])
def test_hedge_failure_reaches_real_verifier_and_repair(monkeypatch, ratio, mode):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", mode)
    draft = "收入可核[E1]，" + ratio
    frame, structural = _structural(draft, detail="收入可核。")
    structural = replace(structural, outcome=replace(
        structural.outcome, evidence=(*structural.outcome.evidence, *_financial_evidence()),
    ))
    result = SemanticEpisodeVerifier(judge_fn=lambda request: {
        "passed": True, "rejected_sentence_indexes": [], "issues": [],
    }).verify(frame=frame, structurally_verified=structural, deadline=ResearchDeadline.from_timeout(10))
    assert result.status == "partial" and result.gap_output_ids and result.repair_output_ids
    assert result.delivery_repair_notes
    assert "1.587" not in result.public_answer or (
        MARK in result.public_answer and "不能视为已核算结论" in result.public_answer
    )
    assert "收入可核[E1]" in result.public_answer
    assert result.delivery_retained_evidence_hashes == (structural.outcome.evidence[0].content_hash,)
    assert result.verified.outcome == structural.outcome
    assert recheck_material_public_delivery(result) == result


@pytest.mark.parametrize("draft", [
    "2026中报含金量待核对。",
    "2026中报含金量为**待核对**，2025中报含金量为0.289。",
    "2026中报含金量为`待核对`，净利润123亿元[E1]。",
    "2026中报含金量为待核对，收入为123亿元[E1]。",
    "2026中报含金量3年最高，2025中报含金量为0.289。",
    "2026中报含金量的口径见附注3。",
    "2026中报含金量待核对，口径见附注3。",
    "比率同期对照：2026中报待核对 vs 2025中报0.289。",
    "含金量对照：2026中报 2025中报分别为待核对与0.289。",
    "2026中报含金量待核对，实际为1.588。",
    "2026中报含金量为1.588，实际为待核对。",
])
def test_ratio_scope_preserves_withheld_and_nonvalue_controls(draft):
    assert calculation_copy_findings(draft, _financial_evidence()) == ()


@pytest.mark.parametrize("ratio", [
    "2026中报含金量3年最高，为1.587",
    "**2026中报**含金量3年最高，为1.587",
    "2026中报含金量3年最高，为1.588",  # correct number, but mapping still explicitly unknown
])
def test_unlocated_marker_scopes_to_ratio_not_independent_fact(ratio):
    draft = f"**收入可核**[E1]，{ratio}，2025中报含金量为0.289。"
    findings = calculation_copy_findings(draft, _financial_evidence())
    assert findings and {f.code for f in findings} == {"calculation_value_unlocated"}
    kept = remove_findings(draft, findings)
    assert kept == f"**收入可核**[E1]，{MARK}{ratio}，2025中报含金量为0.289。"
    assert calculation_copy_findings(kept, _financial_evidence())
    assert remove_findings(kept, calculation_copy_findings(kept, _financial_evidence())) == kept


@pytest.mark.parametrize("draft", [
    "2026中报含金量待核对，实际为1.588，该值为1.587。",
    "2026中报含金量为1.588，另有1.587。",
    "2026中报含金量待核对，实际为1.588，另有1.587。",
    "含金量对照：2026中报 2025中报分别为待核对与0.289，实际为1.587。",
    "含金量对照：2026中报 2025中报分别为1.588与0.289，实际为1.587。",
])
def test_located_or_parallel_value_does_not_exempt_residual_numbers(draft):
    findings = calculation_copy_findings(draft, _financial_evidence())
    assert findings
    kept = remove_findings(draft, findings)
    assert "1.587" not in kept or MARK in kept
    assert remove_findings(kept, calculation_copy_findings(kept, _financial_evidence())) == kept


def test_each_unlocated_period_gets_its_own_marker():
    draft = f"收入可核[E1]，{MARK}2026中报含金量3年最高，为1.587，2025中报含金量3年最高，为0.288。"
    findings = calculation_copy_findings(draft, _financial_evidence())
    assert len(findings) == 2
    kept = remove_findings(draft, findings)
    assert kept.count(MARK) == 2
    assert kept.startswith("收入可核[E1]，")
    assert remove_findings(kept, calculation_copy_findings(kept, _financial_evidence())) == kept


def test_parallel_list_binding_survives_a_local_uncertainty_marker():
    draft = f"含金量对照：2026中报 {MARK}2025中报分别为1.588与0.289，实际为1.587。"
    findings = calculation_copy_findings(draft, _financial_evidence())
    assert findings and {f.code for f in findings} == {"calculation_value_unlocated"}
    assert remove_findings(draft, findings) == draft


def test_resolved_value_does_not_silently_discard_existing_uncertainty_marker():
    # A caller-supplied marker is still uncertainty, not authority to approve.
    draft = f"收入可核[E1]，{MARK}2026中报含金量为1.588。"
    findings = calculation_copy_findings(draft, _financial_evidence())
    assert findings and {f.code for f in findings} == {"calculation_value_unlocated"}
    assert remove_findings(draft, findings) == draft
