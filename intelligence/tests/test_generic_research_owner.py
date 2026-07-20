"""GenericResearchOwner 的契约、白名单和 completion gate 回归。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from intelligence.services import (
    agent_research,
    answer_model,
    ask,
    generic_research_owner,
    query_ledger,
)
from intelligence.services import conversation_orchestrator
from intelligence.services.conversation_orchestrator import TurnOrchestrator
from intelligence.services.conversation_store import ConversationStore
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import (
    RequiredOutput,
    ResearchDeadline,
    ResearchPolicy,
    ResearchRunContext,
    ResearchTaskContract,
)
from intelligence.services.research_state import ResearchState
from intelligence.services.research_tool_registry import (
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


def test_partial_causal_result_with_grounded_facts_can_enter_presenter() -> None:
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
    assert prepared.result.prepared_synthesis_messages


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
    assert route_output["generic_owner_requested"] is True
    assert route_output["selected"] == []


def test_long_tail_fixture_keeps_head_and_owner_routes_out_of_generic_owner() -> None:
    fixture = Path(__file__).parent / "fixtures" / "long_tail_cases.json"
    cases = json.loads(fixture.read_text(encoding="utf-8"))
    for case in cases:
        decision = decide_turn(
            case["query"],
            llm_complete=lambda _messages: (None, None, "offline"),
        )
        intent = decision.turn_intent
        generic = bool(
            decision.lane == "research"
            and decision.question_type == "general_finance_qa"
            and intent is not None
            and intent.question_type == "general_finance_qa"
            and intent.answer_owner is None
        )
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
