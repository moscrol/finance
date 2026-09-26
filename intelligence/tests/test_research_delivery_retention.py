"""Deletion is narrower than detection context; real exits must retain good claims."""

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


@pytest.mark.parametrize(
    "draft,good,bad",
    [
        (
            "中报原文披露了收入[E1]，但查询返回空白，因此公司没有公告。",
            ("中报原文披露了收入[E1]", "查询返回空白"),
            ("因此公司没有公告",),
        ),
        (
            "收入已披露[E1],但查询为空,所以公司没有公告,利润可核[E2]。",
            ("收入已披露[E1]", "查询为空", "利润可核[E2]"),
            ("所以公司没有公告",),
        ),
        (
            "查询空白因此没有公告[E9]，收入已披露[E1]。",
            ("收入已披露[E1]",),
            ("没有公告", "[E9]"),
        ),
        (
            "收入已披露[E1]但窗口内无新公告即无新增官方信息差。",
            ("收入已披露[E1]",),
            ("窗口内无新公告",),
        ),
        (
            "收入已披露[E1]但是窗口内无新公告即无新增官方信息差。",
            ("收入已披露[E1]",),
            ("窗口内无新公告",),
        ),
        (
            "但查询空白因此没有公告[E9]。",
            (),
            ("但", "没有公告", "[E9]", "。"),
        ),
        (
            "但是窗口内无新公告即无新增官方信息差，利润可核[E1]。",
            ("利润可核[E1]",),
            ("窗口内无新公告", "是利润"),
        ),
        (
            "**收入**已披露[E1]，查询空白，因此__公司没有公告__[E9]，利润仍可核[E2]。",
            ("**收入**已披露[E1]", "利润仍可核[E2]"),
            ("公司没有公告", "[E9]", "__"),
        ),
        (
            "收入可核[E1]，查询空白，因此没有公告，所以尚未兑现。",
            ("收入可核[E1]", "查询空白"),
            ("因此没有公告", "所以尚未兑现"),
        ),
        (
            "因此没有公告，查询空白，所以尚未兑现，利润可核[E2]。",
            ("查询空白", "利润可核[E2]"),
            ("因此没有公告", "所以尚未兑现"),
        ),
        (
            "无法完整查询，但窗口内无新公告即无新增官方信息差，利润可核[E1]。",
            ("无法完整查询", "利润可核[E1]"),
            ("窗口内无新公告即",),
        ),
        (
            "查询空白，因此没有公告，不能据此证明尚未兑现。",
            ("查询空白", "不能据此证明尚未兑现"),
            ("因此没有公告",),
        ),
    ],
)
def test_disclosure_edit_spans_preserve_unrelated_raw_text(draft, good, bad):
    findings = disclosure_absence_findings(draft, (TRACE,))
    assert findings
    kept = remove_findings(draft, findings)
    assert all(item in kept for item in good)
    assert all(item not in kept for item in bad)
    assert not kept.endswith(("，", ",", "但", "但是"))
    assert disclosure_absence_findings(kept, (TRACE,)) == ()
    # Only spans reported by the detector are ever changed.
    assert all(0 <= f.start < f.end <= len(draft) for f in findings)


@pytest.mark.parametrize(
    "draft",
    [
        "收入已披露[E1]，查询为空，但不能证明公司没有公告。",
        "‘查询空白即可证明没有公告’是错误推断，不成立。",
        "若公司确实无新公告，则研究重点转向已披露信息。",
        "收入已披露[E1]，无法完整查询，不能据此断言公司尚未兑现。",
    ],
)
def test_honest_qualifiers_still_survive(draft):
    assert disclosure_absence_findings(draft, (TRACE,)) == ()
    assert remove_findings(draft, ()) == draft


@pytest.mark.parametrize("separator", ["。", "；", "，", ",", "但", "但是"])
@pytest.mark.parametrize("mode", ["off", "llm"])
def test_real_verifier_retains_fact_and_citation_for_equivalent_punctuation(
    monkeypatch, separator, mode
):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", mode)
    draft = f"中报原文披露了收入[E1]{separator}窗口内无新公告即无新增官方信息差。"
    frame, structural = _structural(
        draft, detail="中报原文披露了收入。", traces=(TRACE,)
    )
    result = SemanticEpisodeVerifier(
        judge_fn=lambda request: {
            "passed": True, "rejected_sentence_indexes": [], "issues": [],
        }
    ).verify(
        frame=frame, structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(10),
    )
    assert "中报原文披露了收入[E1]" in result.public_answer
    assert "窗口内无新公告即" not in result.public_answer
    assert result.status == "partial" and result.gap_output_ids
    assert result.delivery_retained_evidence_hashes == (
        structural.outcome.evidence[0].content_hash,
    )
    assert result.verified.outcome.draft == draft
    assert result.verified.outcome.evidence == structural.outcome.evidence
    assert recheck_material_public_delivery(result) == result


@pytest.mark.parametrize(
    "draft,expected",
    [
        (
            "收入可核[E1]，2026中报含金量为1.587，2025中报含金量为0.289。",
            "收入可核[E1]，2026中报含金量为待核对，2025中报含金量为0.289。",
        ),
        (
            "**收入可核**[E1]，**2026中报**含金量为**1.587**，利润可核[E2]。",
            "**收入可核**[E1]，**2026中报**含金量为**待核对**，利润可核[E2]。",
        ),
        (
            "收入可核[E1]，2026中报含金量为**158.7**%，利润可核[E2]。",
            "收入可核[E1]，2026中报含金量为**待核对**，利润可核[E2]。",
        ),
        (
            "收入可核[E1]，2026中报含金量为`1.587倍`，利润可核[E2]。",
            "收入可核[E1]，2026中报含金量为`待核对`，利润可核[E2]。",
        ),
        (
            "比率同期对照：2026中报1.587 vs 2025中报0.289，收入可核[E1]。",
            "比率同期对照：2026中报待核对 vs 2025中报0.289，收入可核[E1]。",
        ),
        (
            "比率同期对照：2026中报1.587 vs 2025中报0.288，收入可核[E1]。",
            "比率同期对照：2026中报待核对 vs 2025中报待核对，收入可核[E1]。",
        ),
        (
            "收入可核[E1]，2026中报含**金量**为1.587。\n其他事实可核[E2]。",
            "收入可核[E1]，2026中报含**金量**为待核对。\n其他事实可核[E2]。",
        ),
    ],
)
def test_ratio_prose_replaces_only_bad_value_not_its_neighbors(draft, expected):
    findings = calculation_copy_findings(draft, _financial_evidence())
    assert findings
    kept = remove_findings(draft, findings)
    assert kept == expected
    assert calculation_copy_findings(kept, _financial_evidence()) == ()


@pytest.mark.parametrize("mode", ["off", "llm"])
def test_ratio_prose_retention_reaches_verifier_exit(monkeypatch, mode):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", mode)
    draft = "收入可核[E1]，2026中报含金量为1.587，2025中报含金量为0.289。"
    frame, structural = _structural(draft)
    structural = replace(
        structural,
        outcome=replace(
            structural.outcome,
            evidence=(*structural.outcome.evidence, *_financial_evidence()),
        ),
    )
    result = SemanticEpisodeVerifier(
        judge_fn=lambda request: {
            "passed": True, "rejected_sentence_indexes": [], "issues": [],
        }
    ).verify(
        frame=frame, structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(10),
    )
    assert "收入可核[E1]" in result.public_answer
    assert "2025中报含金量为0.289" in result.public_answer
    assert "待核对" in result.public_answer and "1.587" not in result.public_answer
    assert result.status == "partial" and result.gap_output_ids
    assert result.delivery_retained_evidence_hashes == (
        structural.outcome.evidence[0].content_hash,
    )
    assert result.verified.outcome.evidence == structural.outcome.evidence
    assert recheck_material_public_delivery(result) == result
