"""KC-08：独立来源按文档去重；结论性单源 claim 呈现层标「单源」。"""
from __future__ import annotations

from intelligence.services import answer_model, llm_refine
from intelligence.services.answer_model import (
    AnswerSpec,
    ClaimStatus,
    EvidenceRef,
    make_claim,
    present_llm_answer,
    render_answer_spec,
    resolve_theme_research_spec,
)
from intelligence.services.recall_audit import count_independent_sources


def test_same_document_counts_as_one() -> None:
    assert (
        count_independent_sources(
            (
                "营收增长（年报, 2026-08-01, 质量 high） [R1]",
                "利润改善（年报, 2026-08-10, 质量 high） [R2]",
            )
        )
        == 1
    )


def test_wiki_page_and_paren_source_are_the_same_document() -> None:
    assert (
        count_independent_sources(
            (
                "深科技：5 月 26 日公告第二轮扩产（[[深科技_000021_个股逻辑卡_20260603]], 2026-06-03, 质量 high） [R1]",
            )
        )
        == 1
    )


def test_different_documents_count_as_n() -> None:
    assert (
        count_independent_sources(
            (
                "营收增长（年报, 2026-08-01, 质量 high） [R1]",
                "中标扩产（公告, 2026-08-10, 质量 high） [R2]",
                "订单饱满（研报, 2026-08-12, 质量 high） [R3]",
            )
        )
        == 3
    )


def test_make_claim_records_independent_source_count() -> None:
    one = make_claim(
        claim_id="c1",
        text="英维克：中标液冷集采（公司公告, 2026-07-01, 质量 high） [R1]",
        claim_type="company_evidence",
        theme="液冷服务器",
        status=ClaimStatus.VERIFIED,
        evidence_ids=("R1",),
    )
    many = make_claim(
        claim_id="c2",
        text="英维克：中标（公司公告, 2026-07-01, 质量 high）；研报跟进（券商研报, 2026-07-02, 质量 high）",
        claim_type="company_evidence",
        theme="液冷服务器",
        status=ClaimStatus.VERIFIED,
        evidence_ids=("R1", "R2"),
    )
    assert one.independent_source_count == 1
    assert many.independent_source_count == 2
    assert one.to_dict()["independent_source_count"] == 1


def _spec_with_company_fact(text: str) -> AnswerSpec:
    spec = resolve_theme_research_spec("液冷服务器题材怎么看")
    fact = make_claim(
        claim_id="fact-1",
        text=text,
        claim_type="company_evidence",
        theme=spec.theme,
        status=ClaimStatus.VERIFIED,
        evidence_tier="L3",
        company="英维克",
        evidence_ids=("R1",),
    )
    return AnswerSpec(
        research_spec=spec,
        summary=(),
        verified_facts=(fact,),
        company_table=(),
        counter_evidence=(),
        gaps=(),
        triggers=(),
        next_actions=(),
        sources=(
            EvidenceRef(
                evidence_id="R1",
                source="knowledge-base · wiki/relations/evidence_index.json",
                detail="target=英维克 source=公司公告",
            ),
        ),
        system_notices=(),
    )


def _bound_answer(spec: AnswerSpec) -> str:
    claim = spec.verified_facts[0]
    atoms = answer_model.evidence_atoms_from_answer_spec(spec)
    atom_ids = ",".join(atom.atom_id for atom in atoms)
    return (
        f"- {claim.text}"
        f"<!-- claim_id={claim.claim_id}; "
        f"evidence_atom_ids={atom_ids}; claim_type=fact -->"
    )


def test_single_source_conclusive_claim_is_marked_in_presenter() -> None:
    spec = _spec_with_company_fact(
        "英维克：中标液冷集采（公司公告, 2026-07-01, 质量 high） [R1]"
    )
    rendered = render_answer_spec(spec)
    assert answer_model.SINGLE_SOURCE_NOTE in rendered
    assert "中标液冷集采" in rendered


def test_multi_source_claim_is_not_marked() -> None:
    spec = _spec_with_company_fact(
        "英维克：中标（公司公告, 2026-07-01, 质量 high）；研报跟进（券商研报, 2026-07-02, 质量 high）"
    )
    rendered = render_answer_spec(spec)
    assert answer_model.SINGLE_SOURCE_NOTE not in rendered


def test_single_source_note_shares_present_llm_pipeline() -> None:
    spec = _spec_with_company_fact(
        "英维克：中标液冷集采（公司公告, 2026-07-01, 质量 high） [R1]"
    )
    presented = present_llm_answer(_bound_answer(spec), spec)
    assert "中标液冷集采" in presented
    assert answer_model.SINGLE_SOURCE_NOTE in presented
    assert llm_refine.SYNTHESIS_PROMPT_TEACHES_CLAIM_MARKERS is False


def test_market_or_unextractable_source_is_not_marked() -> None:
    spec = resolve_theme_research_spec("液冷服务器题材怎么看")
    market = make_claim(
        claim_id="m1",
        text="涨幅与边际成交同步转强：板块连续两日放量上涨 [S1]",
        claim_type="market_signal",
        theme=spec.theme,
        status=ClaimStatus.VERIFIED,
        evidence_tier="L4",
        evidence_ids=("S1",),
    )
    mapping = make_claim(
        claim_id="g1",
        text="英维克与液冷服务器存在公司级映射。",
        claim_type="company_evidence",
        theme=spec.theme,
        status=ClaimStatus.VERIFIED,
        evidence_tier="l3",
        company="英维克",
        evidence_ids=("G2",),
    )
    answer = AnswerSpec(
        research_spec=spec,
        summary=(),
        verified_facts=(market, mapping),
        company_table=(),
        counter_evidence=(),
        gaps=(),
        triggers=(),
        next_actions=(),
        sources=(),
        system_notices=(),
    )
    rendered = render_answer_spec(answer)
    assert answer_model.SINGLE_SOURCE_NOTE not in rendered
    assert mapping.independent_source_count == 0
