"""GenericResearchOwner 的契约、白名单和 completion gate 回归。"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from intelligence.services import (
    agent_research,
    answer_model,
    ask,
    generic_research_owner,
    query_ledger,
)
from intelligence.runtime import conversation_orchestrator
from intelligence.runtime.conversation_orchestrator import TurnOrchestrator
from intelligence.services.conversation_store import ConversationStore
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import (
    RequiredOutput,
    ResearchDeadline,
    ResearchPolicy,
    ResearchRunContext,
    ResearchTaskContract,
)
from intelligence.services.research_state import (
    EvidenceObservation,
    ResearchGap,
    ResearchState,
)
from intelligence.services.research_tool_registry import (
    QUERY_TOOL_PARAMETERS,
    ResearchToolRegistry,
    ToolSpec,
    UnknownResearchTool,
)
from intelligence.services.run_store import RunStore
from intelligence.services.turn_controller import decide_turn


def _contract(*, required_direct: bool = True) -> ResearchTaskContract:
    return ResearchTaskContract(
        task_id="run-test",
        question="某公司最近怎么看",
        subject="某公司",
        subject_kind="company",
        question_type="general_finance_qa",
        required_outputs=(
            RequiredOutput(
                "direct_assessment",
                "直接判断",
                ("web_search",),
                required_direct,
            ),
            RequiredOutput(
                "supporting_evidence",
                "可回查来源",
                ("web_search",),
                True,
            ),
        ),
        allowed_capabilities=("web_search",),
        research_tier="quick",
    )


def test_market_forecast_contract_requires_two_scenarios_and_invalidation() -> None:
    intent = conversation_orchestrator.TurnIntent(
        primary_subject=None,
        secondary_topics=(),
        question_type="market_forecast",
        answer_owner=None,
        comparison_entities=(),
        inherited_from_turn=None,
    )
    contract = conversation_orchestrator._build_generic_research_contract(
        "明天是反弹还是继续下跌，分别给出理由",
        task_id="forecast-contract",
        turn_intent=intent,
    )
    assert contract.subject == "A股市场"
    assert [item.output_id for item in contract.required_outputs] == [
        "direct_assessment",
        "rebound_case",
        "decline_case",
        "invalidation",
        "supporting_evidence",
    ]
    assert contract.allowed_capabilities == ("market_data", "web_search", "news_search")


def test_event_forecast_contract_requires_event_specific_outputs() -> None:
    intent = conversation_orchestrator.TurnIntent(
        primary_subject=None,
        secondary_topics=(),
        question_type="event_forecast",
        answer_owner=None,
        comparison_entities=(),
        inherited_from_turn=None,
    )
    contract = conversation_orchestrator._build_generic_research_contract(
        "如果美联储下次降息，A股哪些方向可能受益，哪些证据会证伪？",
        task_id="event-contract",
        turn_intent=intent,
    )

    assert [item.output_id for item in contract.required_outputs] == [
        "direct_assessment",
        "event_facts",
        "event_transmission",
        "verification_window",
        "falsification_window",
        "supporting_evidence",
        "counter_evidence",
    ]
    assert {item.output_id for item in contract.required_outputs}.isdisjoint(
        {"rebound_case", "decline_case", "invalidation"}
    )
    assert contract.allowed_capabilities == (
        "web_search",
        "news_search",
        "kb_search",
        "graph_lookup",
        "evidence_lookup",
    )


def test_event_forecast_rule_plan_uses_event_semantics() -> None:
    contract = type(
        "EventContract",
        (),
        {"question_type": "event_forecast", "subject": "美联储降息"},
    )()
    plan = generic_research_owner.research_task_planner.plan_task(
        "如果美联储下次降息，A股哪些方向可能受益？",
        contract=contract,
        complete_fn=lambda *_args, **_kwargs: ("not-json", "test", ""),
    )

    assert plan.source == "rules"
    assert plan.reason == "planner_invalid_json"
    assert any("传导" in item for item in plan.subquestions)
    assert "验证" in "\n".join(plan.subquestions)
    assert "证伪" in "\n".join(plan.subquestions)
    assert all("反弹" not in item and "走弱" not in item for item in plan.hypotheses)


def test_market_prefetch_failure_is_traced_disabled_and_reported_to_owner(
    tmp_path,
    monkeypatch,
) -> None:
    intent = conversation_orchestrator.TurnIntent(
        primary_subject=None,
        secondary_topics=(),
        question_type="market_forecast",
        answer_owner=None,
        comparison_entities=(),
        inherited_from_turn=None,
    )
    contract = conversation_orchestrator._build_generic_research_contract(
        "明天是反弹还是继续下跌？",
        task_id="market-prefetch-failure",
        turn_intent=intent,
    )

    class FailingMarketRegistry:
        def names(self):
            return ("market_data", "web_search", "news_search")

        def execute(self, name, *_args, **_kwargs):
            assert name == "market_data"
            raise RuntimeError("duckdb unavailable")

    captured: dict[str, object] = {}

    def fake_run(passed_contract, **kwargs):
        captured.update(kwargs)
        state = ResearchState.from_contract(passed_contract)
        for gap in kwargs["preloaded_gaps"]:
            state.add_gap(
                gap.gap_id,
                gap.description,
                blocks=gap.blocks,
                suggested_capabilities=gap.suggested_capabilities,
            )
        loop = agent_research.AgentLoopResult(
            traces=list(kwargs["preloaded_traces"]),
            gaps=tuple(gap.description for gap in kwargs["preloaded_gaps"]),
            research_state=state,
        )
        return generic_research_owner.GenericResearchResult(
            run_id=passed_contract.task_id,
            contract=passed_contract,
            loop=loop,
            completion=generic_research_owner.evaluate_completion(passed_contract, loop),
            evidence=(),
            task_plan=kwargs["task_plan"],
        )

    monkeypatch.setattr(
        ask.research_tool_registry,
        "default_registry",
        lambda _tools: FailingMarketRegistry(),
    )
    monkeypatch.setattr(ask.generic_research_owner, "run_generic_research", fake_run)

    result = ask._answer_generic_owner(
        ask.AskOptions(
            query=contract.question,
            kb_wiki=tmp_path / "wiki",
            research_task_contract=contract,
            use_llm=False,
            compose=False,
        )
    )

    trace = captured["preloaded_traces"][0]
    assert trace.provider == "agent:market_data"
    assert trace.status == "request_error"
    assert trace.parent_id == contract.task_id
    assert trace.step_id == f"{contract.task_id}:owner:prefetch"
    assert captured["disabled_tools"] == ("market_data",)
    assert "结构化行情预取失败" in captured["preloaded_observation"]
    gap = captured["preloaded_gaps"][0]
    assert gap.gap_id == "market_data_prefetch"
    assert result.completion_report is not None
    assert result.completion_report["status"] == "partial"
    assert result.answer_spec is not None
    assert "结构化行情预取失败" in result.answer_spec.gaps[0].text


def test_current_mainline_prefetches_market_daily_and_d4_once(
    tmp_path,
    monkeypatch,
) -> None:
    """当前主线必须拿到两个事实能力，且固定预取后不再交给 loop 重查。"""

    intent = conversation_orchestrator.TurnIntent(
        primary_subject=None,
        secondary_topics=(),
        question_type="general_finance_qa",
        answer_owner=None,
        comparison_entities=(),
        inherited_from_turn=None,
    )
    contract = conversation_orchestrator._build_generic_research_contract(
        "你觉得目前市场的主线是什么，给我你的判断依据",
        task_id="mainline-prefetch",
        turn_intent=intent,
    )
    assert contract.presentation_profile == "mainline_current"
    monkeypatch.setattr(
        ask,
        "_daily_market_overview_block_for_llm",
        lambda _path: "## 总览\n- 截至 2026-07-20，上证涨跌幅 -1.2%",
    )
    monkeypatch.setattr(
        ask,
        "_market_review_mainline_context_block_for_llm",
        lambda *_args: "## 主线\n- 算力：涨停 8，强度高",
    )
    monkeypatch.setattr(ask, "_market_data_asof", lambda _path: "2026-07-20")
    monkeypatch.setattr(agent_research, "build_default_tools", lambda _retrieve: {})
    monkeypatch.setattr(agent_research, "build_graph_tools", lambda _knowledge: {})
    monkeypatch.setattr(ask.llm_refine, "detect_provider", lambda _model=None: None)

    def complete(messages, **_kwargs):
        prompt = messages[1]["content"]
        assert "mainline_context" in prompt
        assert "market_data" in prompt
        return (
            '{"tool":"finish","args":{"sufficient":true,'
            '"assessment":"当前主线偏向算力，盘面与主线结构均已核验。",'
            '"gaps":[]},"reason":"两项必需事实已取得"}',
            "fixture",
            "",
        )

    monkeypatch.setattr(agent_research.llm_refine, "complete", complete)
    result = ask._answer_generic_owner(
        ask.AskOptions(
            query=contract.question,
            kb_wiki=tmp_path / "wiki",
            market_db_path=tmp_path / "missing.duckdb",
            research_task_contract=contract,
            use_llm=False,
            compose=False,
        )
    )
    assert result.business_status == "complete", repr(result.completion_report)
    assert result.completion_report["business_status"] == "complete"
    assert {item.provider for item in result.provider_traces} >= {
        "agent:market_data",
        "agent:mainline_context",
    }


def test_current_mainline_boundary_only_cannot_complete_mainline_answer(
    tmp_path,
    monkeypatch,
) -> None:
    contract = conversation_orchestrator._build_generic_research_contract(
        "你觉得目前市场的主线是什么，给我你的判断依据",
        task_id="mainline-boundary-only",
        turn_intent=conversation_orchestrator.TurnIntent(
            primary_subject=None,
            secondary_topics=(),
            question_type="general_finance_qa",
            answer_owner=None,
            comparison_entities=(),
            inherited_from_turn=None,
        ),
    )
    monkeypatch.setattr(
        ask,
        "_daily_market_overview_block_for_llm",
        lambda _path: "## 总览\n- 市场数据截至 2026-07-21",
    )
    monkeypatch.setattr(
        ask,
        "_market_review_mainline_context_block_for_llm",
        lambda *_args: (
            "## 市场复盘主线数据边界\n"
            "- 当前交易日的题材级主线未知，禁止把旧题材名称写成当日事实。"
        ),
    )
    monkeypatch.setattr(agent_research, "build_default_tools", lambda _retrieve: {})
    monkeypatch.setattr(agent_research, "build_graph_tools", lambda _knowledge: {})
    monkeypatch.setattr(ask.llm_refine, "detect_provider", lambda _model=None: None)
    monkeypatch.setattr(
        agent_research.llm_refine,
        "complete",
        lambda *_args, **_kwargs: (None, None, "fixture unavailable"),
    )

    result = ask._answer_generic_owner(
        ask.AskOptions(
            query=contract.question,
            kb_wiki=tmp_path / "wiki",
            market_db_path=tmp_path / "missing.duckdb",
            research_task_contract=contract,
            use_llm=False,
            compose=False,
        )
    )

    assert result.business_status != "complete"
    assert result.completion_report["outputs"][0]["status"] != "fulfilled"


def test_mixed_double_red_question_combines_definition_and_current_fact(
    tmp_path,
    monkeypatch,
) -> None:
    contract = conversation_orchestrator._build_generic_research_contract(
        "什么是双红，现在哪些板块双红",
        task_id="mixed-double-red-owner",
        turn_intent=conversation_orchestrator.TurnIntent(
            primary_subject="双红",
            secondary_topics=(),
            question_type="concept_definition",
            answer_owner=None,
            comparison_entities=(),
            inherited_from_turn=None,
        ),
    )
    monkeypatch.setattr(
        ask.market_timeseries,
        "latest_double_red_snapshot_block_for_llm",
        lambda _path: (
            "## 当前双红板块快照 [D4]\n"
            "- 双红定义：题材涨幅为正、边际量大于 10 且成交额大于 500 亿。\n"
            "- 双红数据截至：2026-07-20；严格口径。\n"
            "- 当前双红板块：电力（涨幅 4.80%，边际量 28.12%，成交额 777.83 亿元）。"
        ),
    )
    monkeypatch.setattr(
        ask,
        "_market_review_mainline_context_block_for_llm",
        lambda *_args: "",
    )
    monkeypatch.setattr(agent_research, "build_default_tools", lambda _retrieve: {})
    monkeypatch.setattr(agent_research, "build_graph_tools", lambda _knowledge: {})
    monkeypatch.setattr(ask.llm_refine, "detect_provider", lambda _model=None: None)
    monkeypatch.setattr(
        agent_research.llm_refine,
        "complete",
        lambda *_args, **_kwargs: (None, None, "fixture unavailable"),
    )

    result = ask._answer_generic_owner(
        ask.AskOptions(
            query=contract.question,
            kb_wiki=tmp_path / "wiki",
            market_db_path=tmp_path / "missing.duckdb",
            research_task_contract=contract,
            use_llm=False,
            compose=False,
        )
    )

    assert result.business_status == "complete"
    assert result.trade_date == "2026-07-20"
    rendered = answer_model.render_answer_spec(result.answer_spec)
    assert "题材涨幅为正" in rendered
    assert "当前双红板块：电力" in rendered
    assert all(item.source != "模型常识" for item in result.citations)


def test_preloaded_market_gap_keeps_completion_partial_without_repeating_tool() -> None:
    calls: list[str] = []

    def web_runner(query: str, _context: agent_research.AgentToolContext):
        calls.append(query)
        return [
            agent_research.AgentEvidence(
                tool="web_search",
                title="事件背景",
                detail="公开来源给出事件背景。",
                source="https://example.test/event",
            )
        ], "网页证据已取得", ProviderTrace(
            provider="test:web",
            capability="web_search",
            status="success",
            result_count=1,
        )

    def market_runner(*_args, **_kwargs):
        raise AssertionError("failed prefetch tool must not be repeated in the agent loop")

    registry = ResearchToolRegistry(
        (
            ToolSpec("market_data", "market_data", "行情", "local", "current", market_runner),
            ToolSpec("web_search", "web_search", "网页", "external", "current", web_runner),
        )
    )
    contract = ResearchTaskContract(
        task_id="preloaded-market-gap",
        question="市场方向怎么看",
        subject="A股市场",
        subject_kind="market_pattern",
        question_type="market_forecast",
        required_outputs=(
            RequiredOutput("direct_assessment", "直接判断", ("web_search",), True),
            RequiredOutput("supporting_evidence", "可回查来源", ("web_search",), True),
        ),
        allowed_capabilities=("market_data", "web_search"),
        research_tier="quick",
    )
    actions = iter(
        [
            '{"tool":"web_search","args":{"query":"市场事件"},"reason":"改查可用网页来源"}',
            '{"tool":"finish","args":{"sufficient":true,"assessment":"仅形成部分判断","gaps":[]},"reason":"保留真值缺口"}',
        ]
    )

    def complete(messages, **_kwargs):
        assert "market_data" not in messages[0]["content"]
        return next(actions), "test", ""

    result = generic_research_owner.run_generic_research(
        contract,
        context=_context(contract),
        registry=registry,
        run_id=contract.task_id,
        complete_fn=complete,
        preloaded_traces=(
            ProviderTrace(
                provider="agent:market_data",
                capability="agent_loop",
                status="request_error",
                parent_id=contract.task_id,
                step_id=f"{contract.task_id}:owner:prefetch",
            ),
        ),
        preloaded_gaps=(
            ResearchGap(
                "market_data_prefetch",
                "结构化行情预取失败。",
                blocks=("direct_assessment", "supporting_evidence"),
                suggested_capabilities=("market_data",),
            ),
        ),
        preloaded_observation="结构化行情预取失败；继续使用网页来源。",
        disabled_tools=("market_data",),
    )

    assert calls == ["市场事件"]
    assert result.completion.status == "partial"
    assert result.traces[0].status == "request_error"
    assert "结构化行情预取失败。" in result.gaps
    assert result.loop.research_state is not None
    assert result.loop.research_state.gaps[0].gap_id == "market_data_prefetch"


def test_forecast_state_initializes_scenario_hypotheses() -> None:
    intent = conversation_orchestrator.TurnIntent(
        primary_subject=None,
        secondary_topics=(),
        question_type="market_forecast",
        answer_owner=None,
        comparison_entities=(),
        inherited_from_turn=None,
    )
    state = ResearchState.from_contract(
        conversation_orchestrator._build_generic_research_contract(
            "明天是反弹还是继续下跌",
            task_id="forecast-state",
            turn_intent=intent,
        )
    )
    assert {item.hypothesis_id for item in state.hypotheses} == {
        "rebound_case",
        "decline_case",
        "invalidation",
    }


def test_finish_true_is_delayed_until_forecast_hypotheses_are_covered() -> None:
    intent = conversation_orchestrator.TurnIntent(
        primary_subject=None,
        secondary_topics=(),
        question_type="market_forecast",
        answer_owner=None,
        comparison_entities=(),
        inherited_from_turn=None,
    )
    contract = conversation_orchestrator._build_generic_research_contract(
        "明天是反弹还是继续下跌",
        task_id="forecast-finish",
        turn_intent=intent,
    )
    actions = iter(
        [
            '{"tool":"finish","args":{"sufficient":true,"assessment":"暂偏弱","gaps":[]},"reason":"过早结束"}',
            '{"tool":"finish","args":{"sufficient":false,"assessment":"两种情景证据不足","gaps":["缺少反弹与下跌情景的独立验证"]},"reason":"如实报告缺口"}',
        ]
    )

    def complete(_messages, **_kwargs):
        return next(actions), "test", ""

    result = agent_research.run_agent_loop(
        contract.question,
        tools={},
        steps_budget=2,
        complete_fn=complete,
        research_state=ResearchState.from_contract(contract),
    )
    assert result.stop_reason == "agent finish"
    assert result.sufficient is False
    assert "完成请求被延迟" in result.steps[0].observation


def test_finish_true_is_delayed_until_event_hypotheses_are_covered() -> None:
    intent = conversation_orchestrator.TurnIntent(
        primary_subject=None,
        secondary_topics=(),
        question_type="event_forecast",
        answer_owner=None,
        comparison_entities=(),
        inherited_from_turn=None,
    )
    contract = conversation_orchestrator._build_generic_research_contract(
        "如果美联储下次降息，A股哪些方向可能受益？",
        task_id="event-finish",
        turn_intent=intent,
    )
    actions = iter(
        [
            '{"tool":"finish","args":{"sufficient":true,"assessment":"偏利好","gaps":[]},"reason":"过早结束"}',
            '{"tool":"finish","args":{"sufficient":false,"assessment":"事件事实与传导仍待核验","gaps":["缺少事件传导和反证的可回查证据"]},"reason":"如实报告缺口"}',
        ]
    )

    def complete(_messages, **_kwargs):
        return next(actions), "test", ""

    result = agent_research.run_agent_loop(
        contract.question,
        tools={},
        steps_budget=2,
        complete_fn=complete,
        research_state=ResearchState.from_contract(contract),
    )

    assert result.stop_reason == "agent finish"
    assert result.sufficient is False
    assert "完成请求被延迟" in result.steps[0].observation


def test_event_outputs_require_bound_evidence_and_counterevidence_requires_contradiction() -> None:
    contract = ResearchTaskContract(
        task_id="event-binding",
        question="如果政策落地，哪些方向受益？",
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
    unbound_evidence = [
        agent_research.AgentEvidence(
            tool="web_search",
            title="事件新闻",
            detail="事件相关材料",
            source="https://example.test/event",
        ),
        agent_research.AgentEvidence(
            tool="web_search",
            title="行业材料",
            detail="行业相关材料",
            source="https://example.test/industry",
            supports=("counter_evidence",),
        ),
    ]
    state = ResearchState.from_contract(contract)
    for index, item in enumerate(unbound_evidence, start=1):
        state.add_evidence(item.to_observation(f"unbound:{index}"))
    state.set_assessment("存在事件材料，但尚未绑定到事件命题。")
    unbound_report = generic_research_owner.evaluate_completion(
        contract,
        agent_research.AgentLoopResult(
            evidence=unbound_evidence,
            sufficient=True,
            assessment=state.assessment,
            research_state=state,
        ),
    )
    assert {
        item.output_id: item.status for item in unbound_report.outputs
    } == {
        "event_facts": "missing",
        "event_transmission": "missing",
        "verification_window": "missing",
        "falsification_window": "missing",
        "counter_evidence": "missing",
    }
    state.add_gap(
        "counterevidence_unavailable",
        "尚未找到可回查的反向传导证据。",
        blocks=("counter_evidence",),
    )
    gap_report = generic_research_owner.evaluate_completion(
        contract,
        agent_research.AgentLoopResult(
            evidence=unbound_evidence,
            sufficient=False,
            assessment=state.assessment,
            research_state=state,
        ),
    )
    assert next(
        item for item in gap_report.outputs if item.output_id == "counter_evidence"
    ).status == "gap"

    bound_evidence = [
        agent_research.AgentEvidence(
            tool="web_search",
            title="事件事实",
            detail="政策已公布具体时间表",
            source="https://example.test/fact",
            supports=("event_facts",),
        ),
        agent_research.AgentEvidence(
            tool="web_search",
            title="传导链",
            detail="政策通过融资成本影响行业需求",
            source="https://example.test/transmission",
            supports=("event_transmission",),
        ),
        agent_research.AgentEvidence(
            tool="web_search",
            title="验证窗口",
            detail="下次数据披露验证需求变化",
            source="https://example.test/verify",
            supports=("verification_window",),
        ),
        agent_research.AgentEvidence(
            tool="web_search",
            title="证伪窗口",
            detail="若需求数据走弱则推翻当前传导",
            source="https://example.test/falsify",
            contradicts=("falsification_window",),
        ),
        agent_research.AgentEvidence(
            tool="web_search",
            title="反向证据",
            detail="需求并未随政策改善",
            source="https://example.test/counter",
            contradicts=("counter_evidence",),
        ),
    ]
    state = ResearchState.from_contract(contract)
    for index, item in enumerate(bound_evidence, start=1):
        state.add_evidence(item.to_observation(f"bound:{index}"))
    state.set_assessment("政策可能改善需求，但应持续验证。")
    bound_report = generic_research_owner.evaluate_completion(
        contract,
        agent_research.AgentLoopResult(
            evidence=bound_evidence,
            sufficient=True,
            assessment=state.assessment,
            research_state=state,
        ),
    )

    assert bound_report.status == "completed"
    assert all(item.status == "fulfilled" for item in bound_report.outputs)


def test_premise_check_requires_explicitly_bound_evidence() -> None:
    contract = ResearchTaskContract(
        task_id="premise-binding",
        question="某厂商已停止所有供货，影响多大？",
        subject="某厂商",
        subject_kind="event",
        question_type="fact_check",
        required_outputs=(
            RequiredOutput(
                "premise_check",
                "确认、修正或否定问题前提",
                ("web_search",),
                True,
            ),
        ),
        allowed_capabilities=("web_search",),
    )
    unrelated = agent_research.AgentEvidence(
        tool="web_search",
        title="无关市场新闻",
        detail="这条材料没有核对供货前提。",
        source="https://example.test/unrelated",
    )
    unbound_state = ResearchState.from_contract(contract)
    unbound_state.add_evidence(unrelated.to_observation("premise:unbound"))
    unbound_state.set_assessment("现有网页不足以核对前提。")
    unbound = generic_research_owner.evaluate_completion(
        contract,
        agent_research.AgentLoopResult(
            evidence=[unrelated],
            sufficient=True,
            assessment=unbound_state.assessment,
            research_state=unbound_state,
        ),
    )
    assert unbound.outputs[0].status == "missing"
    assert unbound.status == "partial"

    corrected = agent_research.AgentEvidence(
        tool="web_search",
        title="官方供货范围说明",
        detail="官方材料明确修正了‘停止所有供货’的前提。",
        source="https://example.test/official",
        contradicts=("premise_check",),
    )
    bound_state = ResearchState.from_contract(contract)
    bound_state.add_evidence(corrected.to_observation("premise:bound"))
    bound_state.set_assessment("原前提过度扩大，需要修正。")
    bound = generic_research_owner.evaluate_completion(
        contract,
        agent_research.AgentLoopResult(
            evidence=[corrected],
            sufficient=True,
            assessment=bound_state.assessment,
            research_state=bound_state,
        ),
    )
    assert bound.outputs[0].status == "fulfilled"
    assert bound.status == "completed"


def test_fact_check_counterparty_and_official_relation_filter() -> None:
    assert (
        ask._fact_check_counterparty(
            "中际旭创和英伟达是否已确认合作？",
            "中际旭创",
        )
        == "英伟达"
    )
    matched = ask.l3_evidence.L3EvidenceItem(
        source_type="cninfo",
        title="关于与 NVIDIA 签署合作协议的公告",
        summary="双方确认供应合作。",
    )
    unrelated = ask.l3_evidence.L3EvidenceItem(
        source_type="cninfo",
        title="董事会决议公告",
        summary="审议现金管理事项。",
    )

    assert ask._official_relation_item_matches(matched, "英伟达") is True
    assert ask._official_relation_item_matches(unrelated, "英伟达") is False


def test_customer_fact_check_stops_after_mandatory_l3_gap(
    tmp_path,
    monkeypatch,
) -> None:
    """官方硬证据为空后不得再用普通网页“补”确认关系。"""

    contract = ResearchTaskContract(
        task_id="run-customer-gap",
        question="中际旭创和英伟达是否已确认合作？",
        subject="中际旭创",
        subject_kind="company",
        question_type="fact_check",
        required_outputs=(
            RequiredOutput(
                "direct_assessment",
                "针对用户问题的直接判断",
                ("kb_search", "web_search", "l3_lookup"),
                True,
            ),
            RequiredOutput(
                "customer_validation",
                "公告、合同、订单或双方官方披露",
                ("l3_lookup",),
                True,
            ),
        ),
        allowed_capabilities=("kb_search", "web_search", "l3_lookup"),
        research_tier="quick",
        presentation_profile="fact_check",
    )
    monkeypatch.setattr(
        ask.l3_evidence,
        "lookup_l3_evidence",
        lambda *args, **kwargs: ask.l3_evidence.L3EvidenceBundle(
            query=contract.question
        ),
    )

    def unexpected_soft_loop(*args, **kwargs):
        raise AssertionError("mandatory L3 gap must stop before soft agent loop")

    monkeypatch.setattr(
        ask.generic_research_owner,
        "run_generic_research",
        unexpected_soft_loop,
    )
    result = ask._answer_generic_owner(
        ask.AskOptions(
            query=contract.question,
            kb_wiki=tmp_path / "wiki",
            research_task_contract=contract,
            use_llm=False,
            compose=False,
        )
    )

    assert result.answer_spec is not None
    assert result.answer_spec.presentation_kind == "evidence_gap"
    assert result.provider_traces[0].provider == "agent:l3_lookup"
    assert result.provider_traces[0].status == "empty"
    assert len(result.answer_spec.gaps) == 1
    assert "缺少证据不等于合作不存在" in result.answer_spec.gaps[0].text


def _context(contract: ResearchTaskContract) -> ResearchRunContext:
    return ResearchRunContext(
        contract=contract,
        deadline=ResearchDeadline.from_timeout(30.0, synthesis_reserve=20.0),
        policy=ResearchPolicy.for_tier("quick"),
        trace_parent_id=contract.task_id,
    )


def _registry() -> ResearchToolRegistry:
    def web_runner(query: str, _context: agent_research.AgentToolContext):
        evidence = [
            agent_research.AgentEvidence(
                tool="web_search",
                title="官方近期披露",
                detail=f"与 {query} 相关的可回查摘要",
                source="https://example.test/source",
            )
        ]
        return evidence, "命中 1 条", ProviderTrace(
            provider="test:web",
            capability="web_search",
            status="success",
            result_count=1,
        )

    return ResearchToolRegistry(
        (
            ToolSpec(
                name="web_search",
                capability="web_search",
                description="测试网页工具",
                cost="external",
                freshness="current",
                runner=web_runner,
            ),
        )
    )


def test_research_task_contract_round_trips_required_outputs() -> None:
    contract = _contract()
    assert ResearchTaskContract.from_dict(contract.to_dict()) == contract


def test_provider_trace_parent_step_fields_are_backward_compatible() -> None:
    trace = ProviderTrace(
        provider="web",
        capability="web_search",
        status="success",
        parent_id="run-1",
        step_id="run-1:owner:1",
    )
    assert ProviderTrace.from_dict(trace.to_dict()).step_id == "run-1:owner:1"
    assert ProviderTrace.from_dict(
        {"provider": "web", "capability": "web_search", "status": "empty"}
    ).parent_id is None


def test_registry_rejects_unregistered_tool() -> None:
    with pytest.raises(UnknownResearchTool):
        _registry().resolve("shell_exec")


def test_registry_definitions_only_expose_authorized_capabilities() -> None:
    def runner(query: str, _context: agent_research.AgentToolContext):
        return [], query, ProviderTrace(
            provider="test",
            capability="test",
            status="empty",
        )

    registry = ResearchToolRegistry(
        (
            ToolSpec(
                "market_data",
                "market_data",
                "结构化行情",
                "local",
                "current",
                runner,
            ),
            ToolSpec(
                "web_search",
                "web_search",
                "全网检索",
                "external",
                "current",
                runner,
            ),
        )
    )

    definitions = registry.tool_definitions(("market_data",))

    assert [item["function"]["name"] for item in definitions] == ["market_data"]
    function = definitions[0]["function"]
    assert function["description"] == "结构化行情"
    # 比对真本源而非手抄字面量，见 BUILD 模式 6。
    assert function["parameters"] == QUERY_TOOL_PARAMETERS


def test_empty_capability_filter_exposes_no_tools() -> None:
    registry = _registry()

    assert registry.authorized_specs(()) == ()
    assert registry.tool_definitions(()) == []
    assert registry.authorized_specs() == (registry.resolve("web_search"),)


def test_empty_contract_capabilities_reject_tool_execution() -> None:
    contract = replace(_contract(), allowed_capabilities=())

    with pytest.raises(UnknownResearchTool, match="能力未授权"):
        _registry().execute(
            "web_search",
            "某公司最新公告",
            context=_context(contract),
            step_id="run-test:blocked",
        )


def test_registry_single_flight_dedupes_same_query_in_owner_context() -> None:
    calls = []

    def runner(query: str, _context: agent_research.AgentToolContext):
        calls.append(query)
        return [], "空", ProviderTrace(
            provider="test:web",
            capability="web_search",
            status="empty",
        )

    registry = ResearchToolRegistry(
        (
            ToolSpec(
                name="web_search",
                capability="web_search",
                description="测试网页工具",
                cost="external",
                freshness="current",
                runner=runner,
            ),
        )
    )
    contract = _contract()
    with query_ledger.query_ledger_scope():
        registry.execute(
            "web_search",
            "同一查询",
            context=_context(contract),
            step_id="run-test:1",
        )
        registry.execute(
            "web_search",
            " 同一查询 ",
            context=_context(contract),
            step_id="run-test:2",
        )
    assert calls == ["同一查询"]


def test_owner_completes_required_outputs_after_grounded_tool_observation() -> None:
    actions = iter(
        [
            '{"tool":"web_search","args":{"query":"某公司最新公告"},"reason":"先查当前事实"}',
                '{"tool":"finish","args":{"sufficient":true,"assessment":"当前判断有最新公告支持","gaps":[]},"reason":"必要输出已覆盖"}',
        ]
    )

    def complete(_messages, **_kwargs):
        return next(actions), "test", ""

    contract = _contract()
    result = generic_research_owner.run_generic_research(
        contract,
        context=_context(contract),
        registry=_registry(),
        run_id=contract.task_id,
        complete_fn=complete,
    )
    assert result.completion.status == "completed"
    assert all(item.status == "fulfilled" for item in result.completion.outputs)
    assert result.traces[0].parent_id == contract.task_id


def test_finish_true_cannot_hide_missing_required_output() -> None:
    actions = iter(
        ['{"tool":"finish","args":{"sufficient":true,"gaps":[]},"reason":"过早结束"}']
    )

    def complete(_messages, **_kwargs):
        return next(actions), "test", ""

    contract = _contract()
    result = generic_research_owner.run_generic_research(
        contract,
        context=_context(contract),
        registry=_registry(),
        run_id=contract.task_id,
        complete_fn=complete,
    )
    assert result.completion.status == "partial"
    assert any(item.status == "missing" for item in result.completion.outputs)


def test_second_finish_true_cannot_complete_when_nonhypothesis_output_is_missing() -> None:
    """一次重规划后仍缺必需 output 时，不能绕过完成门禁。"""

    contract = ResearchTaskContract(
        task_id="missing-output-after-retry",
        question="某公司最近怎么看",
        subject="某公司",
        subject_kind="company",
        question_type="general_finance_qa",
        required_outputs=(
            RequiredOutput("direct_assessment", "直接判断", ("web_search",), True),
            RequiredOutput("market_basis", "结构化行情依据", ("market_data",), True),
        ),
        allowed_capabilities=("web_search",),
        research_tier="quick",
    )
    actions = iter(
        [
            '{"tool":"web_search","args":{"query":"某公司公告"},"reason":"先查来源"}',
            '{"tool":"finish","args":{"sufficient":true,"assessment":"已有公告线索","gaps":[]},"reason":"首次过早结束"}',
            '{"tool":"finish","args":{"sufficient":true,"assessment":"已有公告线索","gaps":[]},"reason":"再次过早结束"}',
        ]
    )

    def complete(_messages, **_kwargs):
        return next(actions), "test", ""

    result = generic_research_owner.run_generic_research(
        contract,
        context=_context(contract),
        registry=_registry(),
        run_id=contract.task_id,
        complete_fn=complete,
    )

    assert result.loop.sufficient is False
    assert result.completion.status == "partial"
    missing = next(item for item in result.completion.outputs if item.output_id == "market_basis")
    assert missing.status == "missing"
    assert any("market_basis" in gap for gap in result.loop.gaps)


def test_contract_rejects_unknown_tier() -> None:
    payload = _contract().to_dict()
    payload["research_tier"] = "unbounded"
    with pytest.raises(ValueError):
        ResearchTaskContract.from_dict(payload)


def test_two_empty_observations_stop_on_no_information_gain() -> None:
    def empty_runner(query: str, _context: agent_research.AgentToolContext):
        return [], "无命中", ProviderTrace(
            provider="test:web",
            capability="web_search",
            status="empty",
        )

    registry = ResearchToolRegistry(
        (
            ToolSpec(
                name="web_search",
                capability="web_search",
                description="测试空结果工具",
                cost="external",
                freshness="current",
                runner=empty_runner,
            ),
        )
    )
    actions = iter(
        [
            '{"tool":"web_search","args":{"query":"一次"},"reason":"查证"}',
            '{"tool":"web_search","args":{"query":"二次"},"reason":"改写"}',
        ]
    )

    def complete(_messages, **_kwargs):
        return next(actions), "test", ""

    result = generic_research_owner.run_generic_research(
        _contract(),
        context=_context(_contract()),
        registry=registry,
        run_id="empty-run",
        complete_fn=complete,
    )
    assert result.loop.stop_reason == "no_information_gain"
    assert len(result.loop.steps) == 2


def test_ask_owner_path_skips_fixed_answer_template(monkeypatch) -> None:
    def fake_web(query: str, _context: agent_research.AgentToolContext):
        return [
            agent_research.AgentEvidence(
                tool="web_search",
                title="候选来源",
                detail=f"关于 {query} 的摘要",
                source="https://example.test/owner",
            )
        ], "命中候选来源", ProviderTrace(
            provider="test:web",
            capability="agent_loop",
            status="success",
            result_count=1,
        )

    actions = iter(
        [
            '{"tool":"web_search","args":{"query":"某公司最新公告"},"reason":"查当前事实"}',
            '{"tool":"finish","args":{"sufficient":true,"gaps":[]},"reason":"完成"}',
        ]
    )

    monkeypatch.setattr(
        agent_research,
        "build_default_tools",
        lambda _retrieve: {"web_search": fake_web},
    )
    monkeypatch.setattr(agent_research, "build_graph_tools", lambda _knowledge: {})
    monkeypatch.setattr(
        agent_research.llm_refine,
        "complete",
        lambda _messages, **_kwargs: (next(actions), "test", ""),
    )
    result = ask.answer_query(
        ask.AskOptions(
            query="某公司最近怎么看",
            clarify=False,
            synthesize=False,
            research_task_contract=_contract(),
        )
    )
    assert result.answer_spec is not None
    assert result.answer_spec.presentation_kind == "generic_research"
    rendered = answer_model.render_answer_spec(result.answer_spec)
    assert "题材怎么理解" not in rendered
    assert "公司证据" not in rendered
    assert "候选来源" in rendered
    assert "研究 Agent" not in rendered
    assert "本轮状态=" not in rendered


def test_incomplete_owner_result_cannot_enter_synthesis(monkeypatch) -> None:
    actions = iter(
        ['{"tool":"finish","args":{"sufficient":true,"gaps":[]},"reason":"过早结束"}']
    )
    monkeypatch.setattr(agent_research, "build_default_tools", lambda _retrieve: {})
    monkeypatch.setattr(agent_research, "build_graph_tools", lambda _knowledge: {})
    monkeypatch.setattr(
        agent_research.llm_refine,
        "complete",
        lambda _messages, **_kwargs: (next(actions), "test", ""),
    )
    options = ask.AskOptions(
        query="某公司最近怎么看",
        clarify=False,
        synthesize=True,
        research_task_contract=_contract(),
    )
    result = ask.answer_query(options)
    assert result.completion_report is not None
    assert result.completion_report["status"] == "partial"
    prepared = ask.prepare_existing_answer(options, result)
    assert prepared.result.prepared_synthesis_messages is None
    assert result.completion_report["business_status"] in {"partial", "gap"}


def test_completion_report_requires_bound_direct_assessment_for_business_complete() -> None:
    contract = _contract()
    evidence = agent_research.AgentEvidence(
        tool="web_search",
        title="当前公告",
        detail="与问题相关的可回查公告。",
        source="https://example.test/current",
    )
    loop = agent_research.AgentLoopResult(
        evidence=[evidence],
        sufficient=True,
        assessment="",
        research_state=ResearchState.from_contract(contract),
    )
    report = generic_research_owner.evaluate_completion(contract, loop)
    assert report.status == "partial"
    assert report.business_status in {"partial", "gap"}
    assert next(item for item in report.outputs if item.output_id == "direct_assessment").status == "missing"


def test_incomplete_generic_answer_projects_typed_gaps_to_business_validation(
    monkeypatch,
) -> None:
    """Completion 控制面必须翻译成用户可执行的验证，而非泄漏内部状态。"""

    monkeypatch.setattr(agent_research, "build_default_tools", lambda _retrieve: {})
    monkeypatch.setattr(agent_research, "build_graph_tools", lambda _knowledge: {})
    monkeypatch.setattr(
        agent_research.llm_refine,
        "complete",
        lambda _messages, **_kwargs: (
            '{"tool":"finish","args":{"sufficient":false,"gaps":["暂无可回查材料"]},'
            '"reason":"如实结束"}',
            "test",
            "",
        ),
    )

    result = ask.answer_query(
        ask.AskOptions(
            query="某公司最近怎么看",
            clarify=False,
            synthesize=False,
            research_task_contract=_contract(),
        )
    )

    assert result.answer_spec is not None
    gap_text = "\n".join(item.text for item in result.answer_spec.gaps)
    assert "直接判断" in gap_text
    assert "可回查来源" in gap_text
    assert len({item.text for item in result.answer_spec.gaps}) == len(result.answer_spec.gaps)
    assert result.answer_spec.next_actions
    assert result.answer_spec.next_actions[0].startswith("下一验证窗口：")
    rendered = answer_model.render_answer_spec(result.answer_spec)
    assert "required_outputs" not in rendered
    assert "task_coverage" not in rendered
    assert "研究 Agent" not in rendered


def test_incomplete_generic_answer_drops_control_plane_gap_text(
    monkeypatch,
) -> None:
    """Agent 生成的内部 completion 诊断不得进入展示面。"""

    monkeypatch.setattr(agent_research, "build_default_tools", lambda _retrieve: {})
    monkeypatch.setattr(agent_research, "build_graph_tools", lambda _knowledge: {})
    monkeypatch.setattr(
        agent_research.llm_refine,
        "complete",
        lambda _messages, **_kwargs: (
            '{"tool":"finish","args":{"sufficient":false,'
            '"gaps":["required_outputs 与 task_coverage 均未满足，请查 ProviderTrace"]},'
            '"reason":"如实结束"}',
            "test",
            "",
        ),
    )

    result = ask.answer_query(
        ask.AskOptions(
            query="某公司最近怎么看",
            clarify=False,
            synthesize=False,
            research_task_contract=_contract(),
        )
    )

    assert result.answer_spec is not None
    rendered = answer_model.render_answer_spec(result.answer_spec)
    for internal in ("required_outputs", "task_coverage", "ProviderTrace", "trace"):
        assert internal not in rendered
    assert "直接判断" in rendered
    assert "尚缺少可回查依据" in rendered


def test_business_contract_gap_is_not_over_sanitized(monkeypatch) -> None:
    """业务语义的 contract 不是控制面字段，应保留供用户核验。"""

    monkeypatch.setattr(agent_research, "build_default_tools", lambda _retrieve: {})
    monkeypatch.setattr(agent_research, "build_graph_tools", lambda _knowledge: {})
    monkeypatch.setattr(
        agent_research.llm_refine,
        "complete",
        lambda _messages, **_kwargs: (
            '{"tool":"finish","args":{"sufficient":false,'
            '"gaps":["客户 contract 金额尚未公开披露"]},'
            '"reason":"如实结束"}',
            "test",
            "",
        ),
    )

    result = ask.answer_query(
        ask.AskOptions(
            query="某公司最近怎么看",
            clarify=False,
            synthesize=False,
            research_task_contract=_contract(),
        )
    )

    assert result.answer_spec is not None
    assert "contract 金额尚未公开披露" in answer_model.render_answer_spec(
        result.answer_spec
    )


def test_partial_causal_result_with_grounded_facts_cannot_enter_presenter() -> None:
    claim = answer_model.make_claim(
        claim_id="cause:mechanism",
        text="周内四个交易日下跌，风险偏好收缩是可验证的盘面机制。",
        claim_type="cause_attribution",
        theme="A股市场",
        status=answer_model.ClaimStatus.INFERRED,
        evidence_ids=("G1",),
    )
    spec = answer_model.finalize_answer_spec(
        answer_model.AnswerSpec(
            research_spec=answer_model.resolve_answer_profile(
                "本周为什么下跌", None, "causal"
            ),
            summary=(claim,),
            verified_facts=(),
            company_table=(),
            counter_evidence=(),
            gaps=(
                answer_model.make_claim(
                    claim_id="cause:external-gap",
                    text="外部触发因素仍缺少时间对齐证据。",
                    claim_type="evidence_gap",
                    theme="A股市场",
                    status=answer_model.ClaimStatus.MISSING,
                ),
            ),
            triggers=(),
            next_actions=(),
            sources=(answer_model.EvidenceRef("G1", "本地周行情", "周窗口"),),
            system_notices=(),
            presentation_kind="generic_research",
            presentation_profile="causal",
        )
    )
    result = ask.AskResult(
        query="本周为什么下跌",
        trade_date=None,
        matched_theme=None,
        candidate_tier=None,
        priority_score=None,
        answer_spec=spec,
        completion_report={
            "status": "partial",
            "factual_grounding": "fulfilled",
            "causal_adequacy": "partial",
            "task_coverage": "partial",
            "outputs": [],
        },
        citations=[ask.Citation("G1", "本地周行情", "周窗口")],
    )
    prepared = ask.prepare_existing_answer(
        ask.AskOptions(query=result.query, compose=True, synthesize=False),
        result,
    )
    assert prepared.result.prepared_synthesis_messages is None
    assert prepared.options.synthesize is False


def test_unrelated_dated_news_does_not_fulfil_external_cause_output() -> None:
    contract = ResearchTaskContract(
        task_id="cause-test",
        question="本周 A 股为什么下跌",
        subject=None,
        subject_kind="market_pattern",
        question_type="market_cause",
        required_outputs=(
            RequiredOutput(
                "external_cause_evidence",
                "时间对齐的外部原因",
                ("web_search", "news_search"),
                False,
            ),
        ),
        allowed_capabilities=("market_data", "web_search"),
    )
    state = ResearchState.from_contract(contract)
    evidence = [
        agent_research.AgentEvidence(
            tool="market_data",
            title="本周指数",
            detail="本周指数下跌",
            source="local",
            source_date="2026-07-17",
        ),
        agent_research.AgentEvidence(
            tool="web_search",
            title="某公司发布新品",
            detail="某公司新品进入内测",
            source="web",
            source_date="2026-07-17",
        ),
    ]
    for index, item in enumerate(evidence, start=1):
        state.add_evidence(item.to_observation(f"e{index}"))
    state.set_assessment("风险偏好收缩是盘面机制。")
    loop = agent_research.AgentLoopResult(
        steps=[],
        evidence=evidence,
        traces=[],
        sufficient=True,
        assessment="风险偏好收缩是盘面机制。",
        research_state=state,
    )
    report = generic_research_owner.evaluate_completion(contract, loop)
    output = next(
        item
        for item in report.outputs
        if item.output_id == "external_cause_evidence"
    )
    assert output.status == "gap"
    assert not output.evidence_ids


def test_evidence_display_text_deduplicates_title_prefix() -> None:
    item = agent_research.AgentEvidence(
        tool="market_data",
        title="2026-07-17：指数 -3.05%",
        detail="2026-07-17：指数 -3.05%；跌停 193 家。",
        source="local",
    )
    assert agent_research.evidence_display_text(item) == item.detail


def test_market_block_lines_are_dated_structured_evidence() -> None:
    evidence, _ = agent_research.block_lines_to_evidence(
        "market_data",
        "2026-07-17：指数 -3.05%；跌停 193 家。",
        "本地 DuckDB",
    )
    assert evidence[0].source_date == "2026-07-17"
    assert evidence[0].evidence_tier == "L4_structured"


def test_market_window_evidence_uses_latest_date_on_same_line() -> None:
    evidence, _ = agent_research.block_lines_to_evidence(
        "market_data",
        "窗口：2026-07-14 ~ 2026-07-20，共 5 个交易日。",
        "本地 DuckDB",
    )
    assert evidence[0].source_date == "2026-07-20"


def test_structured_block_can_preserve_long_mainline_fact() -> None:
    long_line = "电力核心板块：" + "增量启动依据" * 80
    evidence, _ = agent_research.block_lines_to_evidence(
        "mainline_context",
        long_line,
        "本地 DuckDB",
        limit=10,
        detail_chars=1000,
    )
    assert len(evidence[0].detail) > 200
    assert evidence[0].detail.startswith("电力核心板块")


def test_forecast_fallback_makes_low_confidence_base_call() -> None:
    evidence = [
        agent_research.AgentEvidence(
            tool="market_data",
            title="阶段",
            detail="市场阶段：下跌阶段（第 6 天）；量能状态：正常量能。",
            source="local",
            source_date="2026-07-20",
        ),
        agent_research.AgentEvidence(
            tool="market_data",
            title="指数",
            detail="上证指数：3796.281 点，当日 0.85%。",
            source="local",
            source_date="2026-07-20",
        ),
        agent_research.AgentEvidence(
            tool="market_data",
            title="广度",
            detail="涨跌结构：上涨 1740 家；涨停 53 家；跌停 212 家。",
            source="local",
            source_date="2026-07-20",
        ),
    ]
    assessment, rebound, decline, invalidation = (
        ask._market_forecast_fallback_assessment(evidence)
    )
    assert "更偏向弱势延续或冲高回落" in assessment
    assert "反弹情景" in rebound
    assert "继续下跌情景" in decline
    assert "失效条件" in invalidation
    assert "不押注单一方向" not in assessment


def test_forecast_fallback_binds_all_conditional_scenarios_to_market_truth() -> None:
    state = ResearchState.from_contract(
        conversation_orchestrator._build_generic_research_contract(
            "明天是反弹还是继续下跌",
            task_id="forecast-bind",
            turn_intent=conversation_orchestrator.TurnIntent(
                primary_subject=None,
                secondary_topics=(),
                question_type="market_forecast",
                answer_owner=None,
                comparison_entities=(),
                inherited_from_turn=None,
            ),
        )
    )
    state.add_evidence(
        EvidenceObservation(
            evidence_id="m1",
            tool="market_data",
            title="广度",
            detail="涨跌停结构",
            source="local",
        )
    )

    for hypothesis_id in ("rebound_case", "decline_case", "invalidation"):
        state.bind_hypothesis_evidence(hypothesis_id, ("m1",))

    hypotheses = {
        item["hypothesis_id"]: item
        for item in state.to_dict()["hypotheses"]
    }
    assert all(
        hypotheses[hypothesis_id]["supporting_evidence"] == ["m1"]
        for hypothesis_id in ("rebound_case", "decline_case", "invalidation")
    )


def test_forecast_visible_answer_restores_dropped_required_scenarios() -> None:
    result = ask.AskResult(
        query="明天是反弹还是继续下跌，分别给出理由",
        trade_date="2026-07-20",
        matched_theme="A股市场",
        candidate_tier=None,
        priority_score=None,
        synthesis="当前盘面显示指数收涨，但个股分化明显。",
        question_plan=type(
            "Plan",
            (),
            {"question_type": "market_forecast"},
        )(),
        answer_spec=answer_model.AnswerSpec(
            research_spec=answer_model.resolve_answer_profile(
                "明天是反弹还是继续下跌，分别给出理由",
                "A股市场",
                "forecast",
            ),
                candidate_facts=(
                answer_model.make_claim(
                    claim_id="generic:rebound_case",
                    text="反弹情景：若跌停收缩则修复更可信。",
                    claim_type="expectation",
                    theme="A股市场",
                    status=answer_model.ClaimStatus.INFERRED,
                    evidence_ids=("G1",),
                ),
                answer_model.make_claim(
                    claim_id="generic:decline_case",
                    text="继续下跌情景：若跌停扩散则弱势延续。",
                    claim_type="expectation",
                    theme="A股市场",
                    status=answer_model.ClaimStatus.INFERRED,
                    evidence_ids=("G1",),
                ),
                answer_model.make_claim(
                    claim_id="generic:invalidation",
                    text="失效条件：新盘面与上述触发条件相反。",
                    claim_type="expectation",
                    theme="A股市场",
                    status=answer_model.ClaimStatus.INFERRED,
                        evidence_ids=("G1",),
                    ),
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

    ask._ensure_forecast_scenarios_visible(result)

    assert "反弹情景" in result.synthesis
    assert "继续下跌情景" in result.synthesis
    assert "失效条件" in result.synthesis


def test_current_window_filter_keeps_market_truth_and_drops_old_outlook() -> None:
    market = agent_research.AgentEvidence(
        tool="market_data",
        title="最新盘面",
        detail="市场数据截至 2026-07-20",
        source="local",
        source_date="2026-07-20",
    )
    current = agent_research.AgentEvidence(
        tool="news_search",
        title="7月20日市场消息",
        detail="当日市场消息",
        source="https://example.test/current",
        source_date="2026-07-20",
    )
    stale = agent_research.AgentEvidence(
        tool="web_search",
        title="2026 年度展望",
        detail="全年策略",
        source="https://example.test/stale",
        source_date="2026-03-04",
    )
    filtered = ask._filter_current_window_evidence(
        [stale, current, market],
        all_evidence=[stale, current, market],
    )
    assert filtered == [current, market]


@pytest.mark.parametrize("skill_mode", ["auto", "hybrid"])
def test_orchestrator_ownerless_turn_skips_skill_router_and_template(
    tmp_path,
    skill_mode: str,
) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    query = "某公司最近怎么看"
    run = run_store.create_run(
        query,
        "ask",
        session_id=conversation.conversation_id,
    )
    conversation_store.append_message(
        conversation.conversation_id,
        "user",
        query,
        run_id=run.run_id,
    )
    assistant = conversation_store.append_message(
        conversation.conversation_id,
        "assistant",
        "",
        status="pending",
        run_id=run.run_id,
    )
    conversation_store.update_summary(
        conversation.conversation_id,
        conversation.summary,
        last_run_id=run.run_id,
    )
    captured = []

    def controller(query: str, **kwargs):
        allowed = {
            key: kwargs[key]
            for key in (
                "context",
                "skill_mode",
                "selected_skill_ids",
                "previous_intent",
                "previous_turn_id",
            )
            if key in kwargs
        }
        return decide_turn(
            query,
            llm_complete=lambda _messages: (None, None, "offline"),
            **allowed,
        )

    def answer(options):
        captured.append(options)
        return ask.AskResult(
            query=options.query,
            trade_date=None,
            matched_theme=None,
            candidate_tier=None,
            priority_score=None,
            sections={"结论": ["仅测试输出"], "证据链": [], "引用来源": []},
            completion_report={"status": "partial", "outputs": []},
        )

    def forbidden_router(*_args, **_kwargs):
        raise AssertionError("ownerless long-tail must not enter skill router")

    result = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=answer,
        route_skills_fn=forbidden_router,
        turn_controller_fn=controller,
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run.run_id,
        assistant_message_id=assistant.message_id,
        query=query,
        skill_mode=skill_mode,
        selected_skill_ids=[],
    )

    assert result.status == "completed"
    assert len(captured) == 1
    assert captured[0].research_task_contract is not None
    assert "自然语言综合暂时不可用" not in result.content
    route_step = next(
        step
        for step in run_store.load_trace(run.run_id)
        if step["name"] == "route_skills"
    )
    route_output = json.loads(route_step["output_summary"])
    assert route_output["router_skipped"] is True
    assert route_output["generic_owner_requested"] is True
    assert route_output["selected"] == []


def test_long_tail_fixture_keeps_head_and_owner_routes_out_of_generic_owner() -> None:
    fixture = Path(__file__).parent / "fixtures" / "long_tail_cases.json"
    cases = json.loads(fixture.read_text(encoding="utf-8"))
    required_categories = {
        "t_plus_one_scenario",
        "open_event",
        "unfamiliar_theme",
        "two_hop_relation",
        "wrong_premise",
        "missing_key_number",
        "multi_object_comparison",
        "continuous_follow_up",
        "explicit_daily_workflow",
    }
    assert required_categories.issubset({case["id"] for case in cases})
    tier_rank = {"quick": 0, "standard": 1, "deep": 2}

    for case in cases:
        assert isinstance(case["required_evidence_types"], list)
        assert case["required_evidence_types"]
        assert isinstance(case["forbidden_templates"], list)
        assert case["forbidden_templates"]
        assert case["max_tier"] in {None, "quick", "standard", "deep"}
        previous_intent = None
        previous_turn_id = None
        if case.get("previous_query"):
            previous = decide_turn(
                case["previous_query"],
                llm_complete=lambda _messages: (None, None, "offline"),
            )
            previous_intent = previous.turn_intent
            previous_turn_id = "fixture:previous"
        decision = decide_turn(
            case["query"],
            llm_complete=lambda _messages: (None, None, "offline"),
            previous_intent=previous_intent,
            previous_turn_id=previous_turn_id,
        )
        intent = decision.turn_intent
        generic = bool(
            decision.lane == "research"
            and decision.question_type not in {"market_technical", "external_market"}
            and intent is not None
            and (
                intent.answer_owner is None
                or (
                    "relation" in intent.operators
                    and any(
                        term in case["query"]
                        for term in ("客户", "竞争对手", "供应商", "合作方")
                    )
                )
            )
        )
        assert decision.lane == case["expected_lane"]
        assert decision.question_type == case["expected_question_type"]
        assert (
            None if intent is None else intent.answer_owner
        ) == case["expected_owner"]
        assert generic is case["expected_generic_owner"]
        if generic:
            contract = conversation_orchestrator._build_generic_research_contract(
                case["query"],
                task_id=f"fixture:{case['id']}",
                turn_intent=intent,
            )
            assert [
                output.output_id for output in contract.required_outputs
            ] == case["required_outputs"]
            assert set(case["required_evidence_types"]).issubset(
                contract.allowed_capabilities
            )
            assert case["max_tier"] is not None
            assert tier_rank[contract.research_tier] <= tier_rank[case["max_tier"]]
        else:
            assert set(case["required_evidence_types"]).issubset(
                decision.capabilities
            )


def test_generic_fixture_forbidden_templates_on_real_owner_output(
    tmp_path,
    monkeypatch,
) -> None:
    """禁止模板必须对真实 GenericResearchOwner 输出断言，不手工指定 kind。"""

    from types import SimpleNamespace

    fixture = Path(__file__).parent / "fixtures" / "long_tail_cases.json"
    cases = json.loads(fixture.read_text(encoding="utf-8"))
    monkeypatch.setattr(agent_research, "build_default_tools", lambda _retrieve: {})
    monkeypatch.setattr(agent_research, "build_graph_tools", lambda _knowledge: {})
    monkeypatch.setattr(ask.llm_refine, "detect_provider", lambda _model=None: None)
    monkeypatch.setattr(
        ask.l3_evidence,
        "lookup_l3_evidence",
        lambda *_args, **_kwargs: SimpleNamespace(items=()),
    )
    monkeypatch.setattr(
        agent_research.llm_refine,
        "complete",
        lambda _messages, **_kwargs: (
            '{"tool":"finish","args":{"sufficient":false,'
            '"assessment":"","gaps":["尚无与问题直接相关的可回查证据"]},'
            '"reason":"如实报缺口"}',
            "fixture",
            "",
        ),
    )

    for case in cases:
        if not case["expected_generic_owner"]:
            continue
        previous_intent = None
        previous_turn_id = None
        if case.get("previous_query"):
            previous = decide_turn(
                case["previous_query"],
                llm_complete=lambda _messages: (None, None, "offline"),
            )
            previous_intent = previous.turn_intent
            previous_turn_id = "fixture:previous"
        decision = decide_turn(
            case["query"],
            previous_intent=previous_intent,
            previous_turn_id=previous_turn_id,
            llm_complete=lambda _messages: (None, None, "offline"),
        )
        assert decision.turn_intent is not None
        contract = conversation_orchestrator._build_generic_research_contract(
            case["query"],
            task_id=f"forbidden:{case['id']}",
            turn_intent=decision.turn_intent,
        )
        result = ask.answer_query(
            ask.AskOptions(
                query=case["query"],
                clarify=False,
                synthesize=False,
                kb_wiki=tmp_path / "wiki",
                market_db_path=tmp_path / "missing.duckdb",
                research_task_contract=contract,
            )
        )
        assert result.answer_spec is not None
        assert result.answer_spec.presentation_kind in {
            "generic_research",
            "evidence_gap",
        }
        rendered = answer_model.render_answer_spec(result.answer_spec)
        for forbidden in case["forbidden_templates"]:
            assert forbidden not in rendered, (
                f"{case['id']} 真实 owner 输出命中禁止模板 "
                f"{forbidden!r}: {rendered}"
            )


def test_relation_list_questions_use_relation_contract_not_l3_fact_check() -> None:
    for query in ("浪潮信息的合作方有哪些？", "浪潮信息的供应商有哪些？"):
        decision = decide_turn(
            query,
            llm_complete=lambda _messages: (None, None, "offline"),
        )
        contract = conversation_orchestrator._build_generic_research_contract(
            query,
            task_id="relation-list",
            turn_intent=decision.turn_intent,
        )
        assert contract.presentation_profile == "relation"
        assert [item.output_id for item in contract.required_outputs] == [
            "direct_assessment",
            "relation_map",
            "supporting_evidence",
        ]
        assert "graph_lookup" in contract.allowed_capabilities
        assert "l3_lookup" not in contract.allowed_capabilities


def test_generic_tier_deadline_is_clamped_once_and_keeps_reserve() -> None:
    root = ResearchDeadline.from_timeout(120.0, synthesis_reserve=20.0)
    contract = _contract()
    contract = ResearchTaskContract(
        **{
            **contract.to_dict(),
            "research_tier": "quick",
            "required_outputs": tuple(contract.required_outputs),
            "allowed_capabilities": tuple(contract.allowed_capabilities),
        }
    )
    deadline = conversation_orchestrator._generic_research_deadline(root, contract)
    assert deadline.synthesis_reserve == 20.0
    assert deadline.expires_at <= root.expires_at
    assert deadline.stage_timeout(999.0) <= 10.1


def test_comparison_follow_up_inherits_ownerless_research_lane() -> None:
    first = decide_turn(
        "液冷和风冷的竞争优势分别是什么？",
        llm_complete=lambda _messages: (None, None, "offline"),
    )
    follow_up = decide_turn(
        "那各自最关键的反证是什么？",
        previous_intent=first.turn_intent,
        previous_turn_id="comparison:first",
        llm_complete=lambda _messages: (None, None, "offline"),
    )
    assert follow_up.lane == "research"
    assert follow_up.question_type == "comparison"
    assert follow_up.turn_intent is not None
    assert follow_up.turn_intent.inherited_from_turn == "comparison:first"


def _forecast_owner_result(
    contract,
    *,
    market_evidence: bool,
) -> "generic_research_owner.GenericResearchResult":
    """A forecast run whose agent loop DID produce a usable assessment."""
    state = ResearchState.from_contract(contract)
    evidence: list[agent_research.AgentEvidence] = []
    if market_evidence:
        state.add_evidence(
            EvidenceObservation(
                evidence_id="m1",
                tool="market_data",
                title="广度",
                detail="2026-07-30：涨停/跌停 52/74；成交 23425.75 亿。",
                source="local",
            )
        )
        evidence.append(
            agent_research.AgentEvidence(
                tool="market_data",
                title="广度",
                detail="2026-07-30：涨停/跌停 52/74；成交 23425.75 亿。",
                source="local",
                source_date="2026-07-30",
                # agent loop 成功时确实会把盘面证据绑到三个情景上——契约层的
                # 逐项匹配因此判 fulfilled。缺的只是 ResearchState 那一侧的
                # 假设绑定，也就是本用例要覆盖的缺陷。
                supports=("rebound_case", "decline_case", "invalidation"),
            )
        )
    assessment = (
        "基准判断：震荡磨底。反弹情景：跌停收缩且广度扩大则修复可信。"
        "继续下跌情景：跌停继续扩散则弱势延续。失效条件：结构与触发条件相反时重算。"
    )
    state.set_assessment(assessment)
    loop = agent_research.AgentLoopResult(
        evidence=evidence,
        sufficient=True,
        assessment=assessment,
        research_state=state,
    )
    return generic_research_owner.GenericResearchResult(
        run_id=contract.task_id,
        contract=contract,
        loop=loop,
        completion=generic_research_owner.evaluate_completion(contract, loop),
        evidence=tuple(evidence),
        task_plan=None,
    )


def _forecast_contract(task_id: str):
    return conversation_orchestrator._build_generic_research_contract(
        "你觉得a股明天会怎么走",
        task_id=task_id,
        turn_intent=conversation_orchestrator.TurnIntent(
            primary_subject=None,
            secondary_topics=(),
            question_type="market_forecast",
            answer_owner=None,
            comparison_entities=(),
            inherited_from_turn=None,
        ),
    )


def _run_forecast_owner(contract, monkeypatch, tmp_path, *, market_evidence: bool):
    class StubRegistry:
        def names(self):
            return ("market_data", "web_search", "news_search")

        def execute(self, *_args, **_kwargs):
            raise RuntimeError("prefetch disabled in this test")

    monkeypatch.setattr(
        ask.research_tool_registry,
        "default_registry",
        lambda _tools: StubRegistry(),
    )
    monkeypatch.setattr(
        ask.generic_research_owner,
        "run_generic_research",
        lambda passed_contract, **_kwargs: _forecast_owner_result(
            passed_contract,
            market_evidence=market_evidence,
        ),
    )
    return ask._answer_generic_owner(
        ask.AskOptions(
            query=contract.question,
            kb_wiki=tmp_path / "wiki",
            research_task_contract=contract,
            use_llm=False,
            compose=False,
        )
    )


def test_successful_forecast_loop_still_binds_its_scenario_hypotheses(
    tmp_path,
    monkeypatch,
) -> None:
    """研究做得好不该反而关掉合成。

    情景假设的证据绑定原本只写在「agent loop 没能给出判断」的兜底分支里。loop 成功时
    三个假设一直是 uncovered，ResearchState 判 coverage=partial，
    evaluate_completion 汇总成 business_status=gap，prepare_existing_answer 据此把
    synthesize 关掉——六个必需输出全部 fulfilled，用户却拿到确定性模板。
    实测 run_20260731_031601_415738 就是这样，全程没有调用过 LLM。
    """
    contract = _forecast_contract("forecast-loop-success")

    result = _run_forecast_owner(contract, monkeypatch, tmp_path, market_evidence=True)

    assert result.completion_report is not None
    assert result.completion_report["task_coverage"] == "fulfilled"
    assert result.completion_report["business_status"] == "complete"


def test_forecast_without_market_truth_still_fails_closed(
    tmp_path,
    monkeypatch,
) -> None:
    """没有盘面真值就没有可绑的证据，仍然不许放行。"""
    contract = _forecast_contract("forecast-no-market")

    result = _run_forecast_owner(contract, monkeypatch, tmp_path, market_evidence=False)

    assert result.completion_report is not None
    assert result.completion_report["business_status"] != "complete"


def test_generic_owner_hands_its_contract_to_the_presentation_layer(
    tmp_path,
    monkeypatch,
) -> None:
    """必需输出要传到 AnswerSpec，composer 的 prompt 才拿得到验收标准。

    在此之前 GenericResearchOwner 这条路的 prompt_constraints 恒为空，于是
    brief/compose 的 prompt 里没有 required_outputs，而 task_fulfillment 又逐条
    按它判——模型在一张看不见的评分表上被打分。
    """
    contract = _forecast_contract("forecast-contract-to-spec")

    result = _run_forecast_owner(contract, monkeypatch, tmp_path, market_evidence=True)

    assert result.answer_spec is not None
    constraints = result.answer_spec.prompt_constraints
    assert constraints
    assert {item.split("：", 1)[0] for item in constraints} == {
        required.output_id
        for required in contract.required_outputs
        if required.required
    }
