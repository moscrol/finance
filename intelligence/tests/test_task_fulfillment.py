from intelligence.services.answer_model import (
    Claim,
    ClaimStatus,
    EvidenceRef,
)
from intelligence.services.research_contract import RequiredOutput
from intelligence.services.task_fulfillment import (
    answer_has_output_marker,
    evaluate_answer_spec_fulfillment,
    evaluate_marker_coverage,
    evaluate_task_fulfillment,
    fail_closed_answer_spec,
    output_marker_is_checkable,
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


def test_direct_definition_is_claimable_from_the_summary_namespace():
    # 定义题的定义句和别的结论一样落在 summary: 下。没有这条映射时 direct_definition
    # 取不到任何候选，恒判 no_candidate_claim，把已写出定义的答案整份 fail-closed。
    definition = "英维克的液冷业务指的是面向数据中心的冷板与 CDU 温控系统。"
    verdict = evaluate_task_fulfillment(
        question="英维克的液冷业务是什么",
        required_outputs=(
            RequiredOutput("direct_definition", "概念定义", ("kb_search",)),
        ),
        answer_text=definition,
        claims=(_claim("summary:company", definition),),
        sources=(_source("英维克 液冷 冷板 CDU 数据中心 温控 产品资料"),),
    )

    assert verdict.status == "complete"
    item = next(item for item in verdict.items if item.output_id == "direct_definition")
    assert item.status == "fulfilled"
    assert item.reason_code == ""


def test_direct_definition_still_fails_when_the_prose_omits_it():
    # 上一条不能退化成无条件放行：候选取到了但正文没写，仍须判缺。
    verdict = evaluate_task_fulfillment(
        question="英维克的液冷业务是什么",
        required_outputs=(
            RequiredOutput("direct_definition", "概念定义", ("kb_search",)),
        ),
        answer_text="本轮没有可回查的公司材料。",
        claims=(
            _claim(
                "summary:company",
                "英维克的液冷业务指的是面向数据中心的冷板与 CDU 温控系统。",
            ),
        ),
        sources=(_source("英维克 液冷 冷板 CDU 数据中心 温控 产品资料"),),
    )

    assert verdict.status == "missing"
    item = next(item for item in verdict.items if item.output_id == "direct_definition")
    assert item.reason_code == "text_absent"


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


def test_fail_closed_projection_keeps_evidence_bound_facts() -> None:
    """契约未完成 ≠ 查到的东西都是假的。

    原先一律清空 verified_facts / company_table / sources，于是一个缺失的措辞
    标记（counterpoint 只要求正文出现 反证/风险/相反/但/除非 之一）就把整张
    公司表和全部已核验事实一起丢掉——C5 那道纯查价题就是这么变成一句失败桩的。
    缺口仍要排在最前、仍切 evidence_gap 渲染，但已绑定证据的事实必须留下。
    """
    fact = Claim(
        claim_id="fact:1",
        text="立新能源 2026-07-21 收盘 8.15 元。",
        claim_type="supporting_fact",
        theme="market",
        evidence_ids=("S1",),
        status=ClaimStatus.VERIFIED,
    )
    unbound = Claim(
        claim_id="fact:2",
        text="没有出处的推断。",
        claim_type="supporting_fact",
        theme="market",
        evidence_ids=(),
        status=ClaimStatus.VERIFIED,
    )
    spec = answer_model.finalize_answer_spec(
        answer_model.AnswerSpec(
            research_spec=answer_model.resolve_answer_profile(
                "立新能源收盘价多少", profile="general"
            ),
            summary=(_claim("s:1", "收盘价如下。", evidence_ids=("S1",)),),
            verified_facts=(fact, unbound),
            company_table=(),
            counter_evidence=(),
            gaps=(),
            triggers=(),
            next_actions=(),
            sources=(
                answer_model.EvidenceRef(evidence_id="S1", source="fact_stock_daily", detail=""),
                answer_model.EvidenceRef(evidence_id="ZZ", source="用不到的来源", detail=""),
            ),
            system_notices=(),
            presentation_kind="generic_research",
        )
    )
    verdict = evaluate_task_fulfillment(
        question="立新能源收盘价多少",
        required_outputs=(RequiredOutput("counterpoint", "反证", ("market_data",)),),
        answer_text="立新能源 2026-07-21 收盘 8.15 元。",
        claims=spec.summary,
        sources=(),
    )

    projected = fail_closed_answer_spec(spec, verdict)

    assert projected.presentation_kind == "evidence_gap"
    assert projected.summary[0].status == answer_model.ClaimStatus.MISSING
    # 有出处的留下，没出处的丢掉
    assert [c.claim_id for c in projected.verified_facts] == ["fact:1"]
    # 来源只保留被留存事实真正引用到的那些
    assert [s.evidence_id for s in projected.sources] == ["S1"]


def test_marker_checkability_separates_no_vocabulary_from_absent_prose():
    # 有 marker 词表且正文命中
    assert output_marker_is_checkable("direct_assessment") is True
    assert answer_has_output_marker(
        "direct_assessment",
        "当前主线是资金回流权重。",
    ) is True

    # 有 marker 词表但正文没写：这才是真正的「缺」
    assert output_marker_is_checkable("evidence_boundary") is True
    assert answer_has_output_marker("evidence_boundary", "随便一句话。") is False

    # 没有 marker 词表：answer_has_output_marker 同样返回 False，但含义完全不同。
    # 观测调用点必须靠 output_marker_is_checkable 把这两种 False 分开，
    # 否则「没法检」会被统计成「答案漏写」。
    assert output_marker_is_checkable("definition") is False
    assert answer_has_output_marker("definition", "卫星互联网是一种…") is False


def test_marker_checkability_is_case_insensitive_like_the_gate():
    # 判定用 casefold，和 evaluate_task_fulfillment 里 output_id 的归一方式一致，
    # 免得同一个槽位在门禁里可检、在观测里被记成 uncheckable。
    assert output_marker_is_checkable("DIRECT_ASSESSMENT") is True


def test_marker_coverage_is_shared_by_both_engines():
    """两个引擎共用同一个判定，覆盖数才能互相比较。"""

    coverage = evaluate_marker_coverage(
        ("direct_assessment", "evidence_boundary"),
        "当前主线是资金回流权重。数据截至 2026-08-07。",
    )

    assert coverage["present"] == ["direct_assessment", "evidence_boundary"]
    assert coverage["absent"] == []
    assert coverage["uncheckable"] == []
    assert coverage["checked_count"] == 2
    assert coverage["marker_coverage"] == "complete"
    # 观测标记必须在 payload 里自述，否则下游会把它当成门禁判定来用。
    assert coverage["observation_only"] is True


def test_marker_coverage_separates_uncheckable_from_absent():
    # direct_definition 无 marker 词表（不可检）；evidence_boundary 有但正文没写（真缺）。
    coverage = evaluate_marker_coverage(
        ("direct_definition", "evidence_boundary"),
        "卫星互联网是一种通过低轨卫星提供接入的通信方式。",
    )

    assert coverage["uncheckable"] == ["direct_definition"]
    assert coverage["absent"] == ["evidence_boundary"]
    assert coverage["present"] == []
    assert coverage["checked_count"] == 1
    assert coverage["required_output_count"] == 2
    assert coverage["marker_coverage"] == "incomplete"


def test_marker_coverage_gives_no_verdict_when_nothing_is_checkable():
    # 全不可检时给 None，而不是把「没得检」报成「检过且通过」——
    # 那正是 answer_status 无条件 complete 的毛病。
    coverage = evaluate_marker_coverage(("direct_definition",), "随便什么正文")

    assert coverage["uncheckable"] == ["direct_definition"]
    assert coverage["checked_count"] == 0
    assert coverage["marker_coverage"] is None


def test_marker_coverage_dedupes_and_drops_blank_output_ids():
    coverage = evaluate_marker_coverage(
        ("direct_assessment", "direct_assessment", "", "  "),
        "当前主线是资金回流权重。",
    )

    assert coverage["required_output_count"] == 1
    assert coverage["present"] == ["direct_assessment"]


def test_marker_coverage_with_no_required_outputs_gives_no_verdict():
    coverage = evaluate_marker_coverage((), "任意正文")

    assert coverage["required_output_count"] == 0
    assert coverage["checked_count"] == 0
    assert coverage["marker_coverage"] is None


def test_marker_coverage_rejects_uncheckable_direct_answer_when_only_boundary_remains():
    """direct_answer 无词表被记 uncheckable，只剩证据边界时不得再报 complete。

    生产 run_20260816_103318：present=[evidence_boundary]、
    uncheckable=[direct_answer]、marker_coverage=complete。判断正文已被剥光，
    诚实闸却读成检过且通过。
    """

    coverage = evaluate_marker_coverage(
        ("direct_answer", "evidence_boundary"),
        "证据边界：可用最新行情日期为2026-08-14，不构成收益预测或投资建议。",
    )

    assert coverage["uncheckable"] == ["direct_answer"]
    assert coverage["present"] == ["evidence_boundary"]
    assert coverage["marker_coverage"] != "complete"
    assert coverage["observation_only"] is False
    assert "uncheckable_judgment_empty" in coverage.get("warnings", [])


def test_marker_coverage_keeps_uncheckable_direct_answer_when_judgment_body_remains():
    coverage = evaluate_marker_coverage(
        ("direct_answer", "evidence_boundary"),
        "周一更值得观察有色金属的资金承接。证据边界：数据截至 2026-08-14。",
    )

    assert coverage["uncheckable"] == ["direct_answer"]
    assert coverage["present"] == ["evidence_boundary"]
    assert coverage["marker_coverage"] == "complete"
    assert coverage["observation_only"] is True
    assert coverage.get("warnings", []) == []


def test_l01_gap_template_does_not_trigger_uncheckable_judgment_empty() -> None:
    """缺口模板整篇 uncheckable（R-19），且仍不响 layer 4 空判断闸。

    原文形状取自 2026-08-16 L01 ``run_20260816_131941_597875/answer.md``。
    R-20260816-04 钉的是旧探测器（``marker_coverage=complete``）；改探测器是
    R-19 观测台，不回写那一行。
    """

    answer = (
        "关于“基于8.15的行情现状，你认为周一的机会在哪”，现有证据不足，暂不能可靠回答。"
        "仍需核验：直接回答用户问题、说明证据覆盖范围、数据日期与缺口。"
        "本轮已取得 60 条证据，但未完成核验绑定，暂不能引用；可直接重试。"
        "证据数据截至 2026-08-14；缺口补齐后可复验。"
    )
    coverage = evaluate_marker_coverage(
        ("direct_answer", "evidence_boundary"),
        answer,
    )
    assert coverage["warnings"] == []
    assert coverage["marker_coverage"] is None
    assert coverage["observation_only"] is True
    assert coverage["present"] == []
    assert coverage["absent"] == []
    assert coverage["uncheckable"] == ["direct_answer", "evidence_boundary"]


def test_gap_template_counterpoint_is_uncheckable_not_present() -> None:
    """R-19 / R-15-03：缺口模板里的「反证」不得把 counterpoint 标成 present。

    22:18 形：structural 判 counterpoint missing，coverage 却因描述子串
    「提供主要反证」报 present。整篇 uncheckable 后不再有静默分歧。
    """

    answer = (
        "关于“主题题”，现有证据不足，暂不能可靠回答。"
        "仍需核验：直接回答用户问题并说明判断强度、chain_mapping、"
        "提供主要反证或竞争性解释。"
    )
    coverage = evaluate_marker_coverage(
        ("direct_assessment", "chain_mapping", "counterpoint"),
        answer,
    )
    structural_missing = {
        "direct_assessment",
        "chain_mapping",
        "counterpoint",
    }
    assert coverage["present"] == []
    assert set(coverage["uncheckable"]) == structural_missing
    assert not (set(coverage["present"]) & structural_missing)
    assert coverage["marker_coverage"] is None


def test_real_counterpoint_answer_stays_present() -> None:
    coverage = evaluate_marker_coverage(
        ("direct_assessment", "counterpoint"),
        "当前主线是国产算力仍在发酵期。主要反证是出口订单若连续两季下滑则判断失效。",
    )
    assert coverage["present"] == ["direct_assessment", "counterpoint"]
    assert coverage["uncheckable"] == []
    assert coverage["marker_coverage"] == "complete"


def test_model_unavailable_gap_template_is_wholly_uncheckable() -> None:
    answer = (
        "关于“主题题”，模型服务不可用，暂不能可靠回答。"
        "仍需核验：提供主要反证或竞争性解释。"
    )
    coverage = evaluate_marker_coverage(("counterpoint",), answer)
    assert coverage["present"] == []
    assert coverage["uncheckable"] == ["counterpoint"]
