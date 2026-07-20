from __future__ import annotations

from intelligence.services.research_contract import RequiredOutput, ResearchTaskContract
from intelligence.services.research_state import EvidenceObservation, ResearchState


def _contract(*, causal: bool = False) -> ResearchTaskContract:
    outputs = [
        RequiredOutput("direct_assessment", "直接判断", ("market_data",), True),
        RequiredOutput("supporting_evidence", "支持证据", ("market_data",), True),
    ]
    if causal:
        outputs.append(
            RequiredOutput(
                "cause_attribution",
                "原因归因",
                ("market_data", "web_search"),
                True,
            )
        )
    return ResearchTaskContract(
        task_id="state-test",
        question="这一周行情下跌的主要原因是什么" if causal else "最近怎么看",
        subject="A股市场",
        subject_kind="market",
        question_type="market_cause" if causal else "general_finance_qa",
        required_outputs=tuple(outputs),
        allowed_capabilities=("market_data", "web_search"),
    )


def _market_mechanism_state() -> ResearchState:
    state = ResearchState.from_contract(_contract(causal=True))
    state.add_hypothesis("h1", "风险偏好收缩是周内下跌机制", kind="mechanism")
    state.add_evidence(
        EvidenceObservation(
            evidence_id="e1",
            tool="market_data",
            title="周窗口",
            detail="五个交易日中四天下跌",
            source="local",
            source_date="2026-07-17",
            evidence_tier="L4",
            supports=("h1",),
        )
    )
    state.set_assessment("盘面显示风险偏好收缩，但外部触发因素尚未核验。")
    state.add_gap(
        "external_trigger",
        "宏观、外盘或资金事件仍未对齐",
        blocks=("cause_attribution",),
        suggested_capabilities=("web_search",),
    )
    return state


def test_state_tracks_hypothesis_support_and_gap() -> None:
    state = _market_mechanism_state()
    hypothesis = next(item for item in state.hypotheses if item.hypothesis_id == "h1")
    assert hypothesis.supporting_evidence == ["e1"]
    assert state.gaps[0].gap_id == "external_trigger"
    assert state.revision >= 4


def test_causal_question_is_partial_when_external_trigger_is_missing() -> None:
    report = _market_mechanism_state().evaluate_completion()
    assert report.factual_grounding == "fulfilled"
    assert report.causal_adequacy == "partial"
    assert report.task_coverage == "partial"
    assert report.status == "partial"


def test_causal_completion_ignores_dated_but_unrelated_news() -> None:
    state = ResearchState.from_contract(_contract(causal=True))
    state.add_evidence(
        EvidenceObservation(
            "m1",
            "market_data",
            "本周指数",
            "指数放量下跌",
            "market",
            source_date="2026-07-17",
        )
    )
    state.add_evidence(
        EvidenceObservation(
            "n1",
            "news_search",
            "某公司发布新品",
            "新产品进入内测",
            "news",
            source_date="2026-07-17",
        )
    )
    state.set_assessment("风险偏好收缩是主要机制。")
    assert state.evaluate_completion().causal_adequacy == "partial"


def test_noncausal_grounded_assessment_can_complete() -> None:
    state = ResearchState.from_contract(_contract())
    state.add_evidence(
        EvidenceObservation(
            evidence_id="e1",
            tool="market_data",
            title="行情",
            detail="当前行情事实",
            source="local",
        )
    )
    state.set_assessment("当前判断有一条结构化行情支持。")
    report = state.evaluate_completion()
    assert report.factual_grounding == "fulfilled"
    assert report.causal_adequacy == "fulfilled"
    assert report.task_coverage == "fulfilled"
    assert report.status == "completed"


def test_state_summary_preserves_cognitive_relationships() -> None:
    block = _market_mechanism_state().summary_for_agent()
    assert "候选假设" in block
    assert "支持/反驳关系" in block
    assert "未解决缺口" in block
    assert "external_trigger" in block
