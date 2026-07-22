from intelligence.services.answer_model import (
    Claim,
    ClaimStatus,
    EvidenceRef,
)
from intelligence.services.research_contract import RequiredOutput
from intelligence.services.task_fulfillment import (
    evaluate_answer_spec_fulfillment,
    evaluate_task_fulfillment,
    fail_closed_answer_spec,
)
from intelligence.services import answer_model


def _claim(
    claim_id: str,
    text: str,
    evidence_ids: tuple[str, ...] = ("G1",),
) -> Claim:
    return Claim(
        claim_id=claim_id,
        text=text,
        claim_type="summary",
        theme="market",
        evidence_ids=evidence_ids,
        status=ClaimStatus.INFERRED,
    )


def _source(detail: str, evidence_id: str = "G1") -> EvidenceRef:
    return EvidenceRef(
        evidence_id=evidence_id,
        source="market-feature-store",
        detail=detail,
        source_date="2026-07-21",
        freshness="current",
    )


def test_mainline_requires_direct_assessment_and_supporting_evidence():
    verdict = evaluate_task_fulfillment(
        question="目前市场的主线是什么，给我你的判断依据",
        required_outputs=(
            RequiredOutput(
                "direct_assessment",
                "当前市场主线判断",
                ("market_data", "mainline_context"),
            ),
            RequiredOutput(
                "supporting_evidence",
                "同日市场结构依据",
                ("market_data", "mainline_context"),
            ),
        ),
        answer_text="当前主线偏向人工智能，依据是同日盘面强度与涨停集中度。",
        claims=(
            _claim(
                "generic:summary",
                "当前主线偏向人工智能，依据是同日盘面强度与涨停集中度。",
            ),
            _claim("generic:verified:1", "人工智能同日涨停 10 只。"),
        ),
        sources=(_source("2026-07-21 人工智能同日涨停 10 只，盘面强度居前"),),
    )

    assert verdict.status == "complete"
    assert {item.output_id for item in verdict.items if item.status == "fulfilled"} == {
        "direct_assessment",
        "supporting_evidence",
    }


def test_forecast_requires_baseline_both_scenarios_and_invalidation():
    required = tuple(
        RequiredOutput(output_id, output_id, ("market_data",))
        for output_id in ("direct_assessment", "rebound_case", "decline_case", "invalidation")
    )
    claims = tuple(
        _claim(f"generic:{output_id}", text)
        for output_id, text in (
            ("summary", "基准判断：更偏向继续下跌。"),
            ("rebound_case", "反弹情景：成交和上涨家数同步修复。"),
            ("decline_case", "继续下跌情景：跌停扩散且成交继续恶化。"),
            ("invalidation", "失效条件：市场宽度重新转强。"),
        )
    )
    verdict = evaluate_task_fulfillment(
        question="明天是反弹还是继续下跌，分别给出理由",
        required_outputs=required,
        answer_text=(
            "基准判断：更偏向继续下跌。\n"
            "反弹情景：成交和上涨家数同步修复。\n"
            "继续下跌情景：跌停扩散且成交继续恶化。\n"
            "失效条件：市场宽度重新转强。"
        ),
        claims=claims,
        sources=(_source("2026-07-21 市场宽度与成交结构数据"),),
    )

    assert verdict.status == "complete"


def test_unrelated_evidence_cannot_complete_arbitrary_assessment():
    verdict = evaluate_task_fulfillment(
        question="目前市场的主线是什么",
        required_outputs=(RequiredOutput("direct_assessment", "当前主线判断", ("market_data",)),),
        answer_text="当前主线是量子计算。",
        claims=(_claim("generic:summary", "当前主线是量子计算。"),),
        sources=(_source("2019 年白酒行业回顾，贵州茅台收入增长"),),
    )

    assert verdict.status != "complete"
    assert verdict.items[0].status in {"partial", "missing"}


def test_candidate_source_list_is_not_a_direct_answer():
    verdict = evaluate_task_fulfillment(
        question="目前市场的主线是什么",
        required_outputs=(RequiredOutput("direct_assessment", "当前主线判断", ("market_data",)),),
        answer_text="本轮只展示候选来源，仍缺少针对用户问题的直接判断。",
        claims=(),
        sources=(_source("2025 年全年市场回顾"),),
    )

    assert verdict.status == "missing"


def test_explicit_question_bound_gap_is_partial_not_fabricated_complete():
    verdict = evaluate_task_fulfillment(
        question="目前市场的主线是什么",
        required_outputs=(RequiredOutput("direct_assessment", "当前主线判断", ("market_data",)),),
        answer_text="当前主线判断：仍缺少同日盘面数据，暂不下结论。",
        claims=(),
        sources=(),
    )

    assert verdict.status == "partial"
    assert verdict.items[0].gap


def test_no_required_outputs_keeps_deterministic_head_unaffected():
    verdict = evaluate_task_fulfillment(
        question="科创50的支撑点位在哪",
        required_outputs=(),
        answer_text="支撑区 1821.68，失效条件为跌破区间并放量。",
        claims=(),
        sources=(),
    )

    assert verdict.status == "complete"


def test_canonical_chain_mapping_requires_public_grounded_answer() -> None:
    chain_claim = _claim(
        "generic:chain_mapping",
        "产业链映射：上游是电池材料，中游是电芯制造，下游是整车。",
    )
    spec = answer_model.finalize_answer_spec(
        answer_model.AnswerSpec(
            research_spec=answer_model.resolve_answer_profile(
                "固态电池产业链怎么分",
                profile="general",
            ),
            summary=(chain_claim,),
            verified_facts=(),
            company_table=(),
            counter_evidence=(),
            gaps=(),
            triggers=(),
            next_actions=(),
            sources=(
                _source(
                    "固态电池上游电池材料、中游电芯制造、下游整车的产业链资料"
                ),
            ),
            system_notices=(),
            presentation_kind="generic_research",
        )
    )
    required = (
        RequiredOutput(
            "chain_mapping",
            "产业链层级与关键环节",
            ("graph_lookup", "kb_search"),
        ),
    )

    answered = evaluate_answer_spec_fulfillment(
        question="固态电池产业链怎么分",
        required_outputs=required,
        answer_text=chain_claim.text,
        answer_spec=spec,
    )
    omitted = evaluate_answer_spec_fulfillment(
        question="固态电池产业链怎么分",
        required_outputs=required,
        answer_text="当前只说明题材热度。",
        answer_spec=spec,
    )

    assert answered.status == "complete"
    assert answered.items[0].status == "fulfilled"
    assert omitted.status == "missing"
    assert omitted.items[0].status == "missing"


def test_new_contract_output_can_fulfill_via_exact_grounded_claim() -> None:
    claim = _claim(
        "generic:novel_metric_breakdown",
        "新增指标拆解：液冷业务收入同比增长 30%。",
    )
    verdict = evaluate_task_fulfillment(
        question="拆解液冷业务指标",
        required_outputs=(
            RequiredOutput(
                "novel_metric_breakdown",
                "新增指标拆解",
                ("financials",),
            ),
        ),
        answer_text=claim.text,
        claims=(claim,),
        sources=(_source("液冷业务收入同比增长 30%"),),
    )

    assert verdict.status == "complete"
    assert verdict.items[0].status == "fulfilled"


def test_fail_closed_projection_removes_candidate_answer() -> None:
    spec = answer_model.finalize_answer_spec(
        answer_model.AnswerSpec(
            research_spec=answer_model.resolve_answer_profile(
                "目前市场的主线是什么",
                profile="general",
            ),
            summary=(
                _claim("generic:summary", "本轮只展示候选来源。", evidence_ids=()),
            ),
            verified_facts=(),
            company_table=(),
            counter_evidence=(),
            gaps=(),
            triggers=(),
            next_actions=(),
            sources=(),
            system_notices=(),
            presentation_kind="generic_research",
        )
    )
    verdict = evaluate_task_fulfillment(
        question="目前市场的主线是什么",
        required_outputs=(RequiredOutput("direct_assessment", "当前主线判断", ("market_data",)),),
        answer_text="本轮只展示候选来源。",
        claims=spec.summary,
        sources=(),
    )

    projected = fail_closed_answer_spec(spec, verdict)

    assert projected.presentation_kind == "evidence_gap"
    assert projected.candidate_facts == ()
    assert projected.summary[0].status == answer_model.ClaimStatus.MISSING
