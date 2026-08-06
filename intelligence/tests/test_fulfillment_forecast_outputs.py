"""前瞻题（market_forecast）的三个必需输出必须能真的完成。

实测 run_20260731_024144_312047「你觉得a股明天会怎么走」：composer 产出了一份
1,934 字、claim 与 evidence_atom 内联绑定的可用答案（核心矛盾：放量下跌与外部利好
的博弈；指数 -0.62%、成交 23425.75 亿、仅 1768 家上涨、跌停 74 家；盘后近 20 家公司
披露回购增持、费城半导体涨 9%），然后被整份换成「请补充数据源或稍后重试」。

三个各自独立的原因：

1. ``evidence_boundary`` 没有任何生产者。预测题里 ask.py 写出的每条 claim 都在
   ``generic:`` 命名空间下，命名空间映射零区分度；能承担这个输出的是
   ``claim_type="evidence_gap"`` 那条 claim。
2. ``invalidation`` 只差措辞：claim 绑上了，但 composer 的 judge 判掉了写着失效
   条件的那句、repair 把它删了。确定性收口本该补回来，却挂在前瞻路径走不到的位置。
3. ``scenario_tree`` 与 ``rebound_case`` + ``decline_case`` 完全重复，而后两者都已
   完成——它要求的是同一份内容在 registry 里出现第二次。

这些测试断言生产者实际写进 Claim 的值（``evidence_gap``），不是 marker 注释里显示的
``gap``——上一轮就是照显示值写测试，测试过了而线上照旧坏着。
"""
from __future__ import annotations

from intelligence.services import answer_model as am
from intelligence.services import ask_synthesis
from intelligence.services.ask_types import AskResult
from intelligence.runtime.conversation_orchestrator import _merge_frame_outputs
from intelligence.services.research_contract import RequiredOutput
from intelligence.services.task_frame import TaskFrame
from intelligence.services.task_fulfillment import (
    _claim_candidates,
    evaluate_task_fulfillment,
)

QUERY = "你觉得a股明天会怎么走"

# ask.py `_market_forecast_fallback_assessment` 的原文。
REBOUND = (
    "反弹情景：若下一交易日跌停家数明显收缩、上涨家数扩大，且成交没有在指数上行时萎缩，"
    "则技术性修复更可信；若只有权重拉指数、个股广度不改善，只算弱反抽。"
)
DECLINE = (
    "继续下跌情景：若跌停继续扩散、上涨家数重新收缩，或放量但指数和主线同步走弱，"
    "说明卖压尚未出清，弱势延续的解释更占优。"
)
INVALIDATION = (
    "失效条件：开盘后涨跌停结构、成交和指数方向与上述触发条件相反时，"
    "本轮基准判断失效，必须用下一交易日的新盘面重算。"
)
# ask.py 在 forecast profile 下写的边界 claim。
BOUNDARY = "未取得可直接预测下一交易日方向的独立证据；以上仅为条件化情景，不给出概率。"

MARKET_DETAIL = (
    "2026-07-30：指数 -0.62%；成交 23425.75 亿；上涨 1768 家；涨停/跌停 52/74。"
)


def _scenario_claim(claim_id: str, text: str) -> am.Claim:
    return am.make_claim(
        claim_id=claim_id,
        text=text,
        claim_type="expectation",
        theme="A股市场",
        status=am.ClaimStatus.INFERRED,
        evidence_tier="L4_structured",
        evidence_ids=("G1",),
    )


def _boundary_claim() -> am.Claim:
    return am.make_claim(
        claim_id="generic:gap:1",
        text=BOUNDARY,
        # 生产者写的是 evidence_gap；marker 注释里显示成 gap。
        claim_type="evidence_gap",
        theme="A股市场",
        status=am.ClaimStatus.MISSING,
    )


def _market_claim() -> am.Claim:
    return am.make_claim(
        claim_id="generic:verified:1",
        text=MARKET_DETAIL,
        claim_type="supporting_fact",
        theme="A股市场",
        status=am.ClaimStatus.VERIFIED,
        evidence_tier="L4_structured",
        evidence_ids=("G1",),
    )


def _sources() -> tuple[am.EvidenceRef, ...]:
    return (
        am.EvidenceRef(
            evidence_id="G1",
            source="本地市场数据 · 预测盘面窗口",
            detail=MARKET_DETAIL,
            tier="L4_structured",
            source_date="2026-07-30",
        ),
    )


def _required(*output_ids: str) -> tuple[RequiredOutput, ...]:
    descriptions = {
        "invalidation": "使当前判断失效的反证或关键监测指标",
        "evidence_boundary": "TaskFrame 要求的输出：evidence_boundary",
    }
    return tuple(
        RequiredOutput(output_id, descriptions.get(output_id, output_id), (), True)
        for output_id in output_ids
    )


def _task_frame() -> TaskFrame:
    return TaskFrame(
        raw_question=QUERY,
        user_goal="基于当前市场数据形成条件化后市推演",
        question_type="market_forecast",
        subject="A股市场",
        subject_kind="market_pattern",
        market_scope="A股",
        timeframe=None,
        required_outputs=(
            "direct_assessment",
            "scenario_paths",
            "continuation_conditions",
            "invalidation_conditions",
            "evidence_boundary",
            "scenario_tree",
        ),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="current_market_scenarios",
        confidence=0.92,
    )


# --- 1. evidence_boundary 按 claim_type 认领 -------------------------------


def test_evidence_boundary_claims_the_gap_claim_the_producer_writes() -> None:
    """命名空间在这里没有区分度，claim_type 才是生产者留下的语义标签。"""
    claims = (_market_claim(), _boundary_claim())

    assert [c.claim_id for c in _claim_candidates("evidence_boundary", claims)] == [
        "generic:gap:1"
    ]


def test_evidence_boundary_completes_without_requiring_a_source() -> None:
    """「本轮证据到哪为止」是关于证据集合的陈述，不是集合里的一条事实。

    要求它再绑一条出处是范畴错误——和 counterpoint 同一类。
    """
    answer = (
        "目前不存在可以直接预测下一交易日方向的独立证据，以上分析仅为条件化情景推演。\n"
        "上述盘面数据描述的是周内变化特征，不等同于外部因果关系。"
    )

    verdict = evaluate_task_fulfillment(
        question=QUERY,
        required_outputs=_required("evidence_boundary"),
        answer_text=answer,
        claims=(_market_claim(), _boundary_claim()),
        sources=_sources(),
    )

    assert verdict.status == "complete"


def test_evidence_boundary_stays_missing_when_the_answer_states_no_boundary() -> None:
    """不能靠放宽认领把「没说边界」也算完成。

    正文只有盘面复述、没有任何覆盖范围/数据日期/缺口的表述时，这条必须仍判缺。
    """
    answer = "最近一个交易日指数下跌 0.62%，成交放量至 23425.75 亿，跌停 74 家。"

    verdict = evaluate_task_fulfillment(
        question=QUERY,
        required_outputs=_required("evidence_boundary"),
        answer_text=answer,
        claims=(_market_claim(), _boundary_claim()),
        sources=_sources(),
    )

    assert verdict.status == "missing"


def test_evidence_boundary_marker_ignores_the_disclaimer_boilerplate() -> None:
    """「不构成投资建议」是免责模板，不是证据边界，不能当作满足条件。"""
    answer = "最近一个交易日指数下跌 0.62%，成交放量。（非投资建议，不构成任何操作依据）"

    verdict = evaluate_task_fulfillment(
        question=QUERY,
        required_outputs=_required("evidence_boundary"),
        answer_text=answer,
        claims=(_market_claim(), _boundary_claim()),
        sources=_sources(),
    )

    assert verdict.status == "missing"


# --- 2. invalidation：确定性收口补回被 composer 删掉的分支 -------------------


def _forecast_result(synthesis: str) -> AskResult:
    return AskResult(
        query=QUERY,
        trade_date="2026-07-30",
        matched_theme="A股市场",
        candidate_tier=None,
        priority_score=None,
        synthesis=synthesis,
        question_plan=type("Plan", (), {"question_type": "market_forecast"})(),
        answer_spec=am.AnswerSpec(
            research_spec=am.resolve_answer_profile(QUERY, "A股市场", "forecast"),
            candidate_facts=(
                _scenario_claim("generic:rebound_case", REBOUND),
                _scenario_claim("generic:decline_case", DECLINE),
                _scenario_claim("generic:invalidation", INVALIDATION),
            ),
            summary=(),
            verified_facts=(),
            company_table=(),
            counter_evidence=(),
            gaps=(),
            triggers=(),
            next_actions=(),
            sources=(),
            system_notices=(),
        ),
    )


def test_closure_restores_only_the_branch_the_composer_dropped() -> None:
    """composer 保留了反弹/走弱，判掉了失效条件那句——只补失效条件。

    整块重贴会把已经写好的两支情景再复述一遍，正文里出现两遍同样的内容。
    """
    composed = (
        "## 反弹情景的条件与验证框架\n"
        "反之，如果仅仅依靠权重股拉升指数、个股广度没有实质性改善，"
        "那只能界定为弱反抽，后续仍有再度走弱的风险。"
    )
    result = _forecast_result(composed)

    ask_synthesis.ensure_forecast_scenarios_visible(result)

    appended = result.synthesis[len(composed) :]
    assert "失效条件" in appended
    assert "反弹情景：" not in appended
    assert "继续下跌情景：" not in appended


def test_closure_is_a_noop_when_the_composer_kept_every_branch() -> None:
    composed = f"{REBOUND}\n{DECLINE}\n{INVALIDATION}"
    result = _forecast_result(composed)

    ask_synthesis.ensure_forecast_scenarios_visible(result)

    assert result.synthesis == composed


def test_closure_lets_the_gate_pass_on_the_real_composed_answer() -> None:
    """收口后，被丢弃的那份答案应当通过门禁而不是被 fail-closed。"""
    composed = (
        "# A股次日走势研判\n\n"
        "最近一个交易日市场承压明显，指数下跌0.62%的同时成交放量至23425.75亿，"
        "但全市场仅1768家上涨、跌停达74家，呈现典型的放量下跌格局。\n\n"
        "## 反弹情景的条件与验证框架\n"
        "反之，如果仅仅依靠权重股拉升指数、个股广度没有实质性改善，"
        "那只能界定为弱反抽，后续仍有再度走弱的风险。\n\n"
        "## 关键缺口与注意事项\n"
        "目前不存在可以直接预测下一交易日方向的独立证据，以上分析仅为条件化情景推演。"
    )
    result = _forecast_result(composed)
    ask_synthesis.ensure_forecast_scenarios_visible(result)

    verdict = evaluate_task_fulfillment(
        question=QUERY,
        required_outputs=_required(
            "rebound_case",
            "decline_case",
            "invalidation",
            "evidence_boundary",
        ),
        answer_text=result.synthesis,
        claims=(
            _market_claim(),
            _boundary_claim(),
            _scenario_claim("generic:rebound_case", REBOUND),
            _scenario_claim("generic:decline_case", DECLINE),
            _scenario_claim("generic:invalidation", INVALIDATION),
        ),
        sources=_sources(),
    )

    assert verdict.status == "complete"


# --- 3. scenario_tree 不再被重复登记 ---------------------------------------


def test_scenario_tree_is_not_required_twice_on_the_forecast_path() -> None:
    """rebound_case + decline_case 已经是情景树的两支。"""
    legacy = _required(
        "direct_assessment",
        "rebound_case",
        "decline_case",
        "invalidation",
        "supporting_evidence",
    )

    merged = _merge_frame_outputs(legacy, _task_frame(), ("market_data",))

    assert "scenario_tree" not in {item.output_id for item in merged}
    # 两支情景仍是硬要求，别名不等于放行。
    assert {"rebound_case", "decline_case"} <= {item.output_id for item in merged}


def test_scenario_tree_stays_required_without_a_scenario_branch_slot() -> None:
    """专项 owner 路径没有 rebound_case 槽位，它有自己的 scenario_tree 生产者。"""
    themed = _required("direct_assessment", "chain_mapping")

    merged = _merge_frame_outputs(themed, _task_frame(), ("kb_search",))

    assert "scenario_tree" in {item.output_id for item in merged}


def test_closure_keeps_the_disclaimer_as_the_last_line() -> None:
    """补的分支要插在「（非投资建议）」前面，不能落在它后面。"""
    composed = (
        "## 反弹情景\n"
        "若跌停收缩、上涨家数扩大，则技术性修复更可信。\n\n"
        "（非投资建议）"
    )
    result = _forecast_result(composed)

    ask_synthesis.ensure_forecast_scenarios_visible(result)

    assert result.synthesis.rstrip().endswith("（非投资建议）")
    assert "失效条件" in result.synthesis
    assert result.synthesis.index("失效条件") < result.synthesis.index("（非投资建议）")
