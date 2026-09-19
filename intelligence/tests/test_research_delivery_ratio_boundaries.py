"""ARL-0004 original cases plus paired role/unit/period controls (no live judge)."""
from dataclasses import replace

import pytest

from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier, recheck_material_public_delivery
from intelligence.services.research_contract import ResearchDeadline
from intelligence.services.research_delivery_checks import calculation_copy_findings, remove_findings
from intelligence.tests.test_episode_semantic_verifier import _structural
from intelligence.tests.test_research_delivery_checks import TRACE, _financial_evidence

MARK = "〔比率对应关系待核对〕"
# Verbatim original probe inputs; do not fix the question to fix the checker.
ORIGINAL_CASES = [
    ("2026中报含金量为1.588，行业排名第3。", None),
    ("2026中报含金量为1.588，同期经营现金流1,234.56亿元[E1]。", None),
    ("2026中报含金量为1.588，2025中报的含金量为0.289。", None),
    ("2026中报含金量为1.587元/元。", "1.587"),
    ("2026中报含金量实际为158.7个百分点。", "158.7"),
    ("收入可核[E1]，2026中报含金量待核对；实际为1.587。", "1.587"),
]


@pytest.mark.parametrize("draft,wrong", ORIGINAL_CASES)
@pytest.mark.parametrize("mode", ["off", "llm"])
def test_original_boundary_cases_through_public_exit(monkeypatch, draft, wrong, mode):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", mode)
    frame, structural = _structural(draft, detail="收入可核。", traces=(TRACE,))
    structural = replace(structural, outcome=replace(
        structural.outcome, evidence=(*structural.outcome.evidence, *_financial_evidence()),
    ))
    findings = calculation_copy_findings(draft, structural.outcome.evidence)
    result = SemanticEpisodeVerifier(judge_fn=lambda request: {
        "passed": True, "rejected_sentence_indexes": [], "issues": [],
    }).verify(frame=frame, structurally_verified=structural, deadline=ResearchDeadline.from_timeout(10))
    assert result.verified.outcome == structural.outcome
    assert recheck_material_public_delivery(result) == result
    if "[E1]" in draft:
        assert "[E1]" in result.public_answer
    if wrong is None:
        assert not findings
        assert result.status == "completed" and result.public_answer == draft
        assert not result.gap_output_ids and not result.repair_output_ids and not result.delivery_repair_notes
    else:
        assert findings
        assert result.status == "partial" and result.gap_output_ids and result.repair_output_ids
        assert result.delivery_repair_notes
        assert wrong not in result.public_answer


@pytest.mark.parametrize("neighbor", [
    "行业排名第3", "行业排名第123", "排名3", "位列3", "第3", "行业排名第3,收入123亿元[E1]",
    "同期经营现金流1,234.56亿元[E1]", "收入12,345,678元[E1]", "净利润-1,234.56万元[E1]",
    "同比增加158.7个百分点[E1]", "收入为158.7亿元[E1]", "口径见附注3",
])
@pytest.mark.parametrize("slot", ["为1.588", "为待核对", "为1.587"])
def test_independent_numeric_roles_survive_without_waiving_ratio(neighbor, slot):
    draft = f"2026中报含金量{slot}，{neighbor}。"
    findings = calculation_copy_findings(draft, _financial_evidence())
    assert bool(findings) == (slot == "为1.587")
    kept = remove_findings(draft, findings)
    assert kept == draft.replace("为1.587", "为待核对")
    assert calculation_copy_findings(kept, _financial_evidence()) == ()


@pytest.mark.parametrize("unit", ["元/元", "元／元", "元 / 元", "倍", "%"])
@pytest.mark.parametrize("markup", ["{}", "**{}**", "`{}`"])
def test_explicit_units_roundtrip_without_unit_fragments(unit, markup):
    for raw, wrong in (("158.7" if unit == "%" else "1.587", True),
                       ("158.8" if unit == "%" else "1.588", False)):
        token = markup.format(raw + unit)
        draft = f"收入可核[E1]，2026中报含金量为{token}，2025中报的含金量为0.289。"
        findings = calculation_copy_findings(draft, _financial_evidence())
        assert bool(findings) == wrong
        assert all(f.code == "calculation_value_mismatch" for f in findings)
        kept = remove_findings(draft, findings)
        assert kept == (draft.replace(token, markup.format("待核对")) if wrong else draft)
        assert calculation_copy_findings(kept, _financial_evidence()) == ()


@pytest.mark.parametrize("raw", ["1.588", "158.8", "158.7"])
def test_percentage_points_cannot_certify_absolute_ratio(raw):
    # Even a matching scalar is the wrong dimension: points measure a difference.
    draft = f"2026中报含金量实际为{raw}个百分点，利润123亿元[E1]。"
    findings = calculation_copy_findings(draft, _financial_evidence())
    assert findings and all(f.code == "calculation_value_mismatch" for f in findings)
    assert remove_findings(draft, findings) == "2026中报含金量实际为待核对，利润123亿元[E1]。"


@pytest.mark.parametrize("first,second", [("1.588", "0.289"), ("1.587", "0.289"),
                                         ("1.588", "0.288"), ("0.289", "1.588")])
@pytest.mark.parametrize("separator", ["，", "；", ";", " vs "])
def test_genitive_neighbor_binds_its_own_value(first, second, separator):
    draft = f"**2026中报**含金量为{first}{separator}**2025中报**的含金量为{second}[E1]。"
    expected = f"**2026中报**含金量为{first if first == '1.588' else '待核对'}{separator}**2025中报**的含金量为{second if second == '0.289' else '待核对'}[E1]。"
    findings = calculation_copy_findings(draft, _financial_evidence())
    assert remove_findings(draft, findings) == expected
    assert calculation_copy_findings(expected, _financial_evidence()) == ()


@pytest.mark.parametrize("separator", ["，", ",", "；", ";"])
@pytest.mark.parametrize("slot", ["待核对", "为**待核对**", "为1.588"])
def test_explicit_continuation_checks_each_slot_across_punctuation(separator, slot):
    draft = f"收入可核[E1]，2026中报含金量{slot}{separator}实际为**1.587元/元**{separator}该值为待核对{separator}本期为158.7%{separator}比率为1.588。"
    findings = calculation_copy_findings(draft, _financial_evidence())
    assert len(findings) == 2 and {f.code for f in findings} == {"calculation_value_mismatch"}
    expected = draft.replace("1.587元/元", "待核对").replace("158.7%", "待核对")
    assert remove_findings(draft, findings) == expected
    assert calculation_copy_findings(expected, _financial_evidence()) == ()


@pytest.mark.parametrize("draft", [
    "2026中报含金量为2025中报的1.2倍。",
    "2026中报含金量为1.588，另有1.587元/元。",
    "2026中报含金量为1.588，另有158.7个百分点。",
    "2026中报含金量3年最高，为1.587，2025中报的含金量为0.289。",
    "2026中报含金量待核对，行业排名第3，另有1.587。",
])
def test_ambiguous_residue_still_unknown_without_deleting_independent_text(draft):
    findings = calculation_copy_findings(draft, _financial_evidence())
    assert findings and {f.code for f in findings} == {"calculation_value_unlocated"}
    kept = remove_findings(draft, findings)
    assert kept == MARK + draft
    assert remove_findings(kept, calculation_copy_findings(kept, _financial_evidence())) == kept


@pytest.mark.parametrize("draft", [
    "2026中报含金量为1.588；同期经营现金流1,234.56亿元[E1]。",
    "2026中报含金量为1.588；净利润为123亿元，实际为124亿元[E1]。",
    "2026中报含金量待核对。实际为1.587。",  # no cross-sentence implicit attribution
    "2026中报含金量待核对；同比增加158.7个百分点[E1]。",
])
def test_semicolon_continuation_does_not_capture_independent_claim(draft):
    assert calculation_copy_findings(draft, _financial_evidence()) == ()


@pytest.mark.parametrize("unit", ["元/元", "个百分点"])
def test_table_units_use_the_same_dimension_contract(unit):
    draft = f"| 报告期 | 含金量 | 经营现金流 |\n|---|---|---|\n| 2026中报 | 1.588{unit} | 1,234.56亿元 |"
    findings = calculation_copy_findings(draft, _financial_evidence())
    assert bool(findings) == (unit == "个百分点")
    assert "1,234.56亿元" in remove_findings(draft, findings)


@pytest.mark.parametrize("markup", ["**{}**", "`{}`", "**实际为**{}"])
def test_semicolon_markdown_keeps_continuation_scope(markup):
    token = markup.format("1.587") if "实际为" in markup else markup.format("实际为1.587")
    draft = f"2026中报含金量待核对；{token}，收入123亿元[E1]。"
    findings = calculation_copy_findings(draft, _financial_evidence())
    assert findings and {f.code for f in findings} == {"calculation_value_mismatch"}
    assert remove_findings(draft, findings) == draft.replace("1.587", "待核对")


@pytest.mark.parametrize("header", ["含金量（个百分点）", "含金量%"])
def test_table_header_unit_controls_unadorned_cell(header):
    draft = f"| 报告期 | {header} |\n|---|---|\n| 2026中报 | 158.8 |"
    findings = calculation_copy_findings(draft, _financial_evidence())
    assert bool(findings) == ("个百分点" in header)


@pytest.mark.parametrize("draft", [
    "2026中报的含金量为1.588元/元。",
    "2026中报含金量待核对；实际为158.8%。",
])
def test_new_syntax_still_requires_real_period_product(draft):
    findings = calculation_copy_findings(draft, _financial_evidence()[:1], calculation_required=True)
    assert findings and {f.code for f in findings} == {"calculation_value_unverified"}
    assert "待核对" in remove_findings(draft, findings)


def test_grouped_ratio_is_one_token_not_numeric_fragments():
    source, calc = _financial_evidence()
    evidence = (source, replace(calc, observations=(replace(calc.observations[0], value=1234.56),)))
    assert calculation_copy_findings("2026中报含金量为1,234.56元/元。", evidence) == ()
    draft = "2026中报含金量为1,234.55元/元，收入1,234.55亿元[E1]。"
    findings = calculation_copy_findings(draft, evidence)
    assert remove_findings(draft, findings) == "2026中报含金量为待核对，收入1,234.55亿元[E1]。"
