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


def test_event_forecast_state_tracks_each_event_output_as_a_hypothesis() -> None:
    contract = ResearchTaskContract(
        task_id="event-state-test",
        question="如果政策落地，哪些方向受益，如何验证或证伪？",
        subject="政策事件",
        subject_kind="event",
        question_type="event_forecast",
        required_outputs=(
            RequiredOutput("event_facts", "事件事实", ("web_search",), True),
            RequiredOutput("event_transmission", "传导链", ("web_search",), True),
            RequiredOutput("verification_window", "验证窗口", ("web_search",), True),
            RequiredOutput("falsification_window", "证伪窗口", ("web_search",), True),
            RequiredOutput("counter_evidence", "反证", ("web_search",), True),
        ),
        allowed_capabilities=("web_search",),
    )

    hypotheses = {
        item.hypothesis_id: item.kind
        for item in ResearchState.from_contract(contract).hypotheses
    }

    assert hypotheses == {
        "event_facts": "scenario",
        "event_transmission": "causal",
        "verification_window": "scenario",
        "falsification_window": "falsifier",
        "counter_evidence": "counterpoint",
    }


def test_state_summary_preserves_cognitive_relationships() -> None:
    block = _market_mechanism_state().summary_for_agent()
    assert "候选假设" in block
    assert "支持/反驳关系" in block
    assert "未解决缺口" in block
    assert "external_trigger" in block


def _forecast_state():
    from intelligence.services import conversation_orchestrator as co

    contract = co._build_generic_research_contract(
        "你觉得a股明天会怎么走",
        task_id="stale-gap",
        turn_intent=co.TurnIntent(
            primary_subject=None,
            secondary_topics=(),
            question_type="market_forecast",
            answer_owner=None,
            comparison_entities=(),
            inherited_from_turn=None,
        ),
    )
    state = ResearchState.from_contract(contract)
    state.add_evidence(
        EvidenceObservation(
            evidence_id="m1",
            tool="market_data",
            title="广度",
            detail="涨停/跌停 52/74",
            source="local",
        )
    )
    state.set_assessment("基准判断：震荡磨底。反弹情景…继续下跌情景…失效条件…")
    for hypothesis_id in ("rebound_case", "decline_case", "invalidation"):
        state.bind_hypothesis_evidence(hypothesis_id, ("m1",))
    blocked = tuple(item.output_id for item in contract.required_outputs)
    state.add_gap("market_data_prefetch", "结构化行情预取失败", blocks=blocked)
    return state, blocked


def test_a_gap_stops_blocking_once_everything_it_blocks_is_delivered() -> None:
    """gap 只追加、无法解除，一条早期临时缺口会永久压住 coverage。

    往下传导就是 status=partial → business_status=gap →
    prepare_existing_answer 关掉 synthesize，整轮拿不到自然语言合成。实测本机
    79 条 run 里 68 条根本没有 composer 记录。「阻塞」的定义是「有东西因它交付
    不了」——它列的 output 全交付了，它就不再阻塞任何东西。
    """
    state, blocked = _forecast_state()

    completion = state.evaluate_completion(fulfilled_outputs=frozenset(blocked))

    assert completion.task_coverage == "fulfilled"
    assert completion.status == "completed"


def test_a_gap_keeps_blocking_while_any_of_its_outputs_is_undelivered() -> None:
    state, blocked = _forecast_state()

    completion = state.evaluate_completion(
        fulfilled_outputs=frozenset(blocked[:-1])
    )

    assert completion.task_coverage == "partial"


def test_default_call_keeps_the_previous_blocking_behaviour() -> None:
    """不传 fulfilled_outputs 的调用方行为不变。"""
    state, _blocked = _forecast_state()

    assert state.evaluate_completion().task_coverage == "partial"


def test_a_named_capability_must_actually_arrive_before_its_gap_clears() -> None:
    """「结构化行情预取失败」不能靠网页来源凑齐 output 就算解除。

    那条 gap 说的就是本轮没拿到结构化盘面真值；用别的来源把它阻塞的 output
    填满，并不代表缺陷被解决。
    """
    from intelligence.services import conversation_orchestrator as co

    contract = co._build_generic_research_contract(
        "你觉得a股明天会怎么走",
        task_id="named-capability",
        turn_intent=co.TurnIntent(
            primary_subject=None,
            secondary_topics=(),
            question_type="market_forecast",
            answer_owner=None,
            comparison_entities=(),
            inherited_from_turn=None,
        ),
    )
    blocked = tuple(item.output_id for item in contract.required_outputs)

    def coverage(tool: str) -> str:
        state = ResearchState.from_contract(contract)
        state.add_evidence(
            EvidenceObservation(
                evidence_id="e1",
                tool=tool,
                title="来源",
                detail="正文",
                source="local",
            )
        )
        state.set_assessment("基准判断…反弹情景…继续下跌情景…失效条件…")
        for hypothesis_id in ("rebound_case", "decline_case", "invalidation"):
            state.bind_hypothesis_evidence(hypothesis_id, ("e1",))
        state.add_gap(
            "market_data_prefetch",
            "结构化行情预取失败",
            blocks=blocked,
            suggested_capabilities=("market_data",),
        )
        return state.evaluate_completion(
            fulfilled_outputs=frozenset(blocked)
        ).task_coverage

    assert coverage("web_search") == "partial"
    assert coverage("market_data") == "fulfilled"
