"""Counterexamples from ARL-0001 plus controls; the first review remains immutable."""

from dataclasses import replace

import pytest

from intelligence.services.episode_semantic_verifier import (
    SemanticEpisodeVerifier,
    recheck_material_public_delivery,
)
from intelligence.services.research_contract import ResearchDeadline
from intelligence.services.research_delivery_checks import (
    calculation_copy_findings,
    disclosure_absence_findings,
    remove_findings,
)
from intelligence.tests.test_episode_semantic_verifier import _structural
from intelligence.tests.test_research_delivery_checks import TRACE, _financial_evidence


DISCLOSURE_CASES = [
    (
        "收入可核[E1]，公告检索接口返回空白，因此可以认定没有新公告，即公司无新增公告。",
        ("收入可核[E1]", "公告检索接口返回空白"),
        ("可以认定", "即公司无新增公告"),
    ),
    (
        "收入可核[E1]，查询空白，因此没有公告，公司无新增公告[E9]。",
        ("收入可核[E1]", "查询空白"),
        ("因此没有公告", "公司无新增公告", "[E9]"),
    ),
    (
        "收入可核[E1]，查询返回空白，但因此没有公告，利润可核[E2]。",
        ("收入可核[E1]", "查询返回空白，利润可核[E2]"),
        ("因此没有公告", "但利润"),
    ),
    (
        "查询空白即可证明没有公告，据此建议观望，收入可核[E1]。",
        ("收入可核[E1]",),
        ("查询空白即可证明没有公告", "据此建议观望"),
    ),
    (
        "收入可核[E1]，查询空白因此没有公告，官方公告称公司尚未兑现某项安排[E2]。",
        ("收入可核[E1]", "官方公告称公司尚未兑现某项安排[E2]"),
        ("因此没有公告",),
    ),
    (
        "收入可核[E1]，查询空白因此没有公告，若公司确实无新公告，则研究重点转向已披露信息。",
        ("收入可核[E1]", "若公司确实无新公告", "则研究重点转向已披露信息"),
        ("因此没有公告",),
    ),
    (
        "收入可核[E1]，公告检索接口返回空白，因此可以认定没有公告，即公司无新增公告。",
        ("收入可核[E1]", "公告检索接口返回空白"),
        ("可以认定", "即公司无新增公告"),
    ),
    (
        "公司无新增公告，收入可核[E1]，查询返回空白，因此可以认定没有公告，利润可核[E2]，即公司无新增公告。",
        ("收入可核[E1]", "利润可核[E2]", "查询返回空白"),
        ("可以认定", "公司无新增公告"),
    ),
    (
        "收入可核[E1]，查询空白，因此没有公告，不能据此证明公司无新增公告。",
        ("收入可核[E1]", "不能据此证明公司无新增公告"),
        ("因此没有公告",),
    ),
    (
        "收入可核[E1]，查询空白，因此没有公告，官方公告称，截至该日公司尚未兑现某项安排[E2]。",
        ("收入可核[E1]", "官方公告称，截至该日公司尚未兑现某项安排[E2]"),
        ("因此没有公告",),
    ),
]


@pytest.mark.parametrize("draft,good,bad", DISCLOSURE_CASES)
def test_review_disclosure_residue_is_not_republished(draft, good, bad):
    findings = disclosure_absence_findings(draft, (TRACE,))
    assert findings
    kept = remove_findings(draft, findings)
    assert all(item in kept for item in good)
    assert all(item not in kept for item in bad)
    assert disclosure_absence_findings(kept, (TRACE,)) == ()


@pytest.mark.parametrize("separator", ["——", "—", "--", "、", "而", "然而", "不过", " ", "  "])
def test_review_more_joiners_preserve_raw_fact(separator):
    draft = f"**收入可核**[E1]{separator}查询返回空白因此公司没有公告。"
    findings = disclosure_absence_findings(draft, (TRACE,))
    assert findings
    kept = remove_findings(draft, findings)
    assert "**收入可核**[E1]" in kept
    assert "因此公司没有公告" not in kept
    assert disclosure_absence_findings(kept, (TRACE,)) == ()


RATIO_CASES = [
    (
        "收入可核[E1]，2026中报含金量3年新高，实际为1.587，利润可核[E2]。",
        "收入可核[E1]，2026中报含金量3年新高，实际为待核对，利润可核[E2]。",
    ),
    (
        "含金量对照：2026中报 2025中报分别为1.587与0.289，收入可核[E1]。",
        "含金量对照：2026中报 2025中报分别为待核对与0.289，收入可核[E1]。",
    ),
    (
        "含金量对照：**2026中报**、**2025中报**分别为**1.587**与`0.288`，收入可核[E1]。",
        "含金量对照：**2026中报**、**2025中报**分别为**待核对**与`待核对`，收入可核[E1]。",
    ),
    (
        "收入可核[E1]，2026中报含金量为1.**587**，利润可核[E2]。",
        "收入可核[E1]，2026中报含金量为待核对，利润可核[E2]。",
    ),
    (
        "收入可核[E1]，2026中报含金量为**1.5**87，利润可核[E2]。",
        "收入可核[E1]，2026中报含金量为待核对，利润可核[E2]。",
    ),
]


@pytest.mark.parametrize("draft,expected", RATIO_CASES)
def test_review_ratio_locates_value_not_year_or_period(draft, expected):
    findings = calculation_copy_findings(draft, _financial_evidence())
    assert findings
    kept = remove_findings(draft, findings)
    assert kept == expected
    assert calculation_copy_findings(kept, _financial_evidence()) == ()


@pytest.mark.parametrize("draft", [
    "2026中报含金量3年新高，实际为1.588。",
    "2026中报含金量创3年新高。",
    "2026中报含金量3年新高。",
    "2026中报含金量提升至第3位，收入123亿元。",
    "2026中报含金量缺少可核验计算，收入为123亿元[E1]。",
    "含金量对照：2026中报 2025中报分别为1.588与0.289。",
    "含金量同比增速：2026中报 2025中报分别为449.8%与28.9%。",
])
def test_review_ratio_does_not_revoke_qualifiers_or_other_metrics(draft):
    assert calculation_copy_findings(draft, _financial_evidence()) == ()


@pytest.mark.parametrize("mode", ["off", "llm"])
@pytest.mark.parametrize("draft,good,bad", [
    DISCLOSURE_CASES[0],
    DISCLOSURE_CASES[3],
    DISCLOSURE_CASES[7],
    ("收入可核[E1]--查询返回空白因此公司没有公告。", ("收入可核[E1]",), ("因此公司没有公告",)),
    ("收入可核[E1]——查询返回空白因此公司没有公告。", ("收入可核[E1]",), ("因此公司没有公告",)),
    (RATIO_CASES[0][0], ("收入可核[E1]", "2026中报", "3年新高"), ("1.587",)),
    (RATIO_CASES[1][0], ("收入可核[E1]", "2026中报", "2025中报", "0.289"), ("1.587",)),
])
def test_review_counterexamples_reach_real_public_exit(monkeypatch, mode, draft, good, bad):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", mode)
    frame, structural = _structural(draft, detail="收入可核。", traces=(TRACE,))
    structural = replace(structural, outcome=replace(
        structural.outcome, evidence=(*structural.outcome.evidence, *_financial_evidence()),
    ))
    result = SemanticEpisodeVerifier(judge_fn=lambda request: {
        "passed": True, "rejected_sentence_indexes": [], "issues": [],
    }).verify(frame=frame, structurally_verified=structural, deadline=ResearchDeadline.from_timeout(10))
    assert all(item in result.public_answer for item in good)
    assert all(item not in result.public_answer for item in bad)
    assert result.status == "partial" and result.gap_output_ids
    assert result.delivery_retained_evidence_hashes == (structural.outcome.evidence[0].content_hash,)
    assert result.verified.outcome.draft == draft
    assert result.verified.outcome.evidence == structural.outcome.evidence
    assert recheck_material_public_delivery(result) == result


@pytest.mark.parametrize("draft", [
    "2026中报含金量3年新高，实际为1.587。",
    "2026中报含金量12个月新高，实际为1.587。",
    "2026中报含金量30年新高，本期为1.587。",
    "2026中报含金量创3年低点，比率为1.587。",
])
def test_review_ratio_preface_does_not_hide_bad_value(draft):
    kept = remove_findings(draft, calculation_copy_findings(draft, _financial_evidence()))
    assert "1.587" not in kept
    assert "2026中报" in kept and "待核对" in kept
