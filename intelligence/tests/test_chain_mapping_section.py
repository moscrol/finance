"""brief 点名了产业链映射而正文没写时，确定性补上这一节。

这条链上的取舍依据来自实测：凡是靠提示词驱动的都失败了——owner 的 output_contract
根本不进 composer 的提示词；composer 自己的「chain_mapping 非空时必须逐个写出」
被无视（brief 里 12 家公司俱全，正文 919 字一家不提）。凡是确定性收口的都成功了
——事实行预算轮转、brief 的 claim 家族选定。必需输出不该依赖模型遵从。

这不是放宽门禁：正文里确实缺产业链段落是事实，这里补的是已经在 AnswerSpec 里、
已经被 brief 点名的证据，不是把缺的判成有。层级原样保留，候选仍写候选。
"""
from __future__ import annotations

from intelligence.services.answer_model import (
    AnswerSpec,
    ClaimStatus,
    CompanyAssessment,
    CompanyTier,
    DecisionBrief,
    ensure_chain_mapping_section,
    make_claim,
    present_grounded_composer_answer,
    resolve_answer_profile,
)

COMPANIES = ("东方锆业", "中一科技")


def _claims():
    return tuple(
        make_claim(
            claim_id=f"company:{name}:G2",
            text=f"{name}与固态电池存在公司级映射。",
            claim_type="fact",
            theme="固态电池",
            status=ClaimStatus.CANDIDATE,
            evidence_ids=("G2",),
            company=name,
        )
        for name in COMPANIES
    )


def _spec(with_table: bool = True) -> AnswerSpec:
    table = (
        (
            CompanyAssessment(
                company="东方锆业",
                ticker="002167",
                chain_stage="材料",
                directness="core",
                tier=CompanyTier.CANDIDATE,
                claims=(),
                evidence_gaps=("候选资料需公告、年报、订单或客户证据确认",),
            ),
        )
        if with_table
        else ()
    )
    return AnswerSpec(
        research_spec=resolve_answer_profile("固态电池现在怎么看"),
        summary=(),
        verified_facts=(),
        company_table=table,
        counter_evidence=(),
        gaps=(),
        triggers=(),
        next_actions=(),
        sources=(),
        system_notices=(),
        candidate_facts=_claims(),
    )


def _brief() -> DecisionBrief:
    return DecisionBrief(
        direct_answer="a",
        core_tension="b",
        supports=("x",),
        chain_mapping=tuple(c.claim_id for c in _claims()),
    )


def test_missing_section_is_appended_with_bindable_markers() -> None:
    out = ensure_chain_mapping_section("固态电池盘面转强。", _spec(), _brief())

    assert "产业链映射" in out
    for name in COMPANIES:
        assert name in out
    # 门禁靠 claim 文本出现在正文里绑定，marker 让 claim_id 可回查。
    assert "claim_ids=company:东方锆业:G2" in out
    assert "claim_type=candidate" in out


def test_tier_and_gap_are_carried_not_upgraded() -> None:
    out = ensure_chain_mapping_section("正文。", _spec(), _brief())

    assert "候选" in out
    assert "材料" in out
    assert "缺候选资料需公告" in out
    assert "核心" not in out.split("产业链映射")[1]


def test_answer_that_already_names_them_is_left_alone() -> None:
    already = "东方锆业与固态电池存在公司级映射。这是正文原有内容。"

    assert ensure_chain_mapping_section(already, _spec(), _brief()) == already


def test_no_chain_mapping_means_no_section() -> None:
    empty = DecisionBrief(direct_answer="a", core_tension="b", supports=("x",))

    assert ensure_chain_mapping_section("正文。", _spec(), empty) == "正文。"
    assert ensure_chain_mapping_section("正文。", _spec(), None) == "正文。"


def test_ids_absent_from_the_registry_are_skipped() -> None:
    brief = DecisionBrief(
        direct_answer="a",
        core_tension="b",
        supports=("x",),
        chain_mapping=("company:查无此司:G2",),
    )

    assert ensure_chain_mapping_section("正文。", _spec(), brief) == "正文。"


def test_section_survives_presentation_with_markers_stripped() -> None:
    spec = _spec()
    out = ensure_chain_mapping_section("正文。", spec, _brief())

    presented = present_grounded_composer_answer(out, spec)

    assert "东方锆业" in presented
    assert "claim_ids=" not in presented
    assert "<!--" not in presented


def test_works_without_a_company_table() -> None:
    """没有公司表时仍要列出公司，只是不带环节与缺口。"""
    out = ensure_chain_mapping_section("正文。", _spec(with_table=False), _brief())

    for name in COMPANIES:
        assert name in out
