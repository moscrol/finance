from __future__ import annotations

import json
from dataclasses import replace

import pytest

from intelligence.adapters.knowledge import KnowledgeAdapter
from intelligence.services.research_contract import TurnIntent
from intelligence.services.query_resolution import QueryResolution, QueryResolver
from intelligence.services.query_understanding import QueryEnvelope, understand_query
from intelligence.services.turn_controller import TurnDecision, _attach_turn_intent, decide_turn


def _no_llm(_messages: list[dict[str, str]]):
    return None, None, "fixture unavailable"


def _semantic_resolver(tmp_path) -> QueryResolver:
    relations = tmp_path / "relations"
    relations.mkdir()
    (relations / "entity_exposures.json").write_text(
        json.dumps(
            {
                "entities": {
                    "英维克": {"codes": ["002837.SZ"], "concepts": {}},
                    "中际旭创": {"codes": ["300308.SZ"], "concepts": {}},
                    "宁德时代": {
                        "codes": ["300750.SZ"],
                        "concepts": {"固态电池": {}},
                    },
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (relations / "aliases.json").write_text(
        json.dumps({"aliases": {}}, ensure_ascii=False),
        encoding="utf-8",
    )
    return QueryResolver(KnowledgeAdapter(wiki_root=tmp_path))


class _CountingResolver:
    def __init__(self) -> None:
        self.calls = 0

    def resolve(self, query: str) -> QueryResolution:
        self.calls += 1
        return QueryResolution(
            envelope=understand_query(query),
            anchor=None,
        )


def test_controller_resolves_each_turn_once() -> None:
    resolver = _CountingResolver()

    decide_turn("卫星互联网是什么", llm_complete=_no_llm, resolver=resolver)

    assert resolver.calls == 1


def _theme_lexicon_resolver(tmp_path) -> QueryResolver:
    relations = tmp_path / "relations"
    relations.mkdir(exist_ok=True)
    (relations / "entity_exposures.json").write_text(
        json.dumps(
            {
                "entities": {
                    "宁德时代": {
                        "codes": ["300750.SZ"],
                        "concepts": {"新能源": {}},
                    },
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (relations / "aliases.json").write_text(
        json.dumps({"aliases": {}}, ensure_ascii=False),
        encoding="utf-8",
    )
    return QueryResolver(KnowledgeAdapter(wiki_root=tmp_path))


def test_controller_asks_clarify_when_resolver_returns_candidate(tmp_path) -> None:
    decision = decide_turn(
        "立新能源怎么看",
        llm_complete=_no_llm,
        resolver=_theme_lexicon_resolver(tmp_path),
    )

    assert decision.lane == "clarify"
    question = " ".join(decision.clarification_questions)
    assert "立新能源" in question
    assert "新能源" in question
    assert decision.turn_intent is not None
    assert decision.turn_intent.pending_task_frame is not None


def test_controller_resumes_entity_tristate_clarification_as_company(tmp_path) -> None:
    first = decide_turn(
        "立新能源怎么看",
        llm_complete=_no_llm,
        resolver=_theme_lexicon_resolver(tmp_path),
    )

    resumed = decide_turn(
        "立新能源",
        previous_intent=first.turn_intent,
        previous_turn_id="msg-kc17",
        llm_complete=_no_llm,
        resolver=_theme_lexicon_resolver(tmp_path),
    )

    assert resumed.lane == "research"
    assert resumed.question_type == "stock_deep_dive"
    assert resumed.subject == "立新能源"
    assert resumed.clarification_questions == ()


@pytest.mark.parametrize(
    ("query", "subject_kind"),
    (
        ("英维克", "company"),
        ("固态电池", "theme"),
        ("中际旭创", "company"),
    ),
)
def test_controller_preserves_resolver_confirmed_bare_subject(
    tmp_path,
    query: str,
    subject_kind: str,
) -> None:
    decision = decide_turn(
        query,
        resolver=_semantic_resolver(tmp_path),
        llm_complete=_no_llm,
    )

    assert decision.task_frame is not None
    assert decision.task_frame.raw_question == query
    assert decision.task_frame.subject == query
    assert decision.task_frame.subject_kind == subject_kind
    assert decision.subject == query


def test_controller_rejects_unverified_whole_question_as_subject() -> None:
    query = "帮我判断产业趋势是否成立"

    class WholeQuestionResolver:
        def resolve(self, _query: str) -> QueryResolution:
            return QueryResolution(
                envelope=replace(
                    understand_query(query),
                    subject=query,
                    subject_kind="theme",
                    matched_by="explicit",
                ),
                anchor=None,
            )

    decision = decide_turn(
        query,
        resolver=WholeQuestionResolver(),  # type: ignore[arg-type]
        llm_complete=_no_llm,
    )

    assert decision.task_frame is not None
    assert decision.task_frame.subject is None
    assert decision.subject is None


def test_controller_subject_wins_when_question_type_is_unchanged() -> None:
    decision = TurnDecision(
        lane="research",
        needs_retrieval=True,
        needs_memory=False,
        needs_template=True,
        question_type="general_finance_qa",
        subject="科创50",
    )
    old_intent = TurnIntent(
        primary_subject="半导体",
        secondary_topics=(),
        question_type="general_finance_qa",
        answer_owner=None,
        comparison_entities=(),
        inherited_from_turn=None,
    )
    merged = _attach_turn_intent(decision, old_intent)
    assert merged.subject == "科创50"
    assert merged.turn_intent is not None
    assert merged.turn_intent.primary_subject == "科创50"


def test_greeting_is_chat_without_tools_or_memory() -> None:
    decision = decide_turn("你好", llm_complete=_no_llm)

    assert decision.lane == "chat"
    assert decision.needs_retrieval is False
    assert decision.needs_memory is False
    assert decision.needs_template is False
    assert decision.capabilities == ()


def test_unrelated_new_turn_does_not_inherit_previous_subject() -> None:
    previous = TurnIntent(
        primary_subject="宁德时代",
        secondary_topics=(),
        question_type="stock_deep_dive",
        answer_owner="stock-deep-dive",
        comparison_entities=(),
        inherited_from_turn=None,
    )

    decision = decide_turn(
        "你好",
        previous_intent=previous,
        previous_turn_id="msg-previous",
        llm_complete=_no_llm,
    )

    assert decision.lane == "chat"
    assert decision.subject is None
    assert decision.task_frame is not None
    assert decision.task_frame.subject is None


def test_model_question_is_meta_without_financial_routing() -> None:
    decision = decide_turn("你好，你是什么模型", llm_complete=_no_llm)

    assert decision.lane == "meta"
    assert decision.needs_retrieval is False
    assert decision.needs_template is False


def test_vague_request_clarifies_instead_of_defaulting_to_research() -> None:
    decision = decide_turn("帮我看看", llm_complete=_no_llm)

    assert decision.lane == "clarify"
    assert decision.clarification_questions
    assert decision.needs_retrieval is False


def test_vague_opinion_request_clarifies_when_controller_is_unavailable() -> None:
    decision = decide_turn("你怎么看", llm_complete=_no_llm)

    assert decision.lane == "clarify"
    assert decision.clarification_questions
    assert decision.needs_retrieval is False
    assert decision.needs_memory is False
    assert decision.needs_template is False


def test_static_concept_uses_knowledge_lane_without_retrieval() -> None:
    decision = decide_turn("卫星互联网是什么", llm_complete=_no_llm)

    assert decision.lane == "knowledge"
    assert decision.question_type == "concept_definition"
    assert decision.needs_retrieval is False
    assert decision.needs_memory is False
    assert decision.needs_template is False


def test_definition_plus_current_market_fact_uses_research_without_controller_llm() -> None:
    decision = decide_turn(
        "什么是双红，现在哪些板块双红",
        llm_complete=lambda _messages: pytest.fail(
            "mixed definition/current fact must use deterministic policy"
        ),
    )
    assert decision.lane == "research"
    assert decision.question_type == "concept_definition"
    assert decision.needs_retrieval is True
    assert decision.needs_template is True
    assert "market_quote" in decision.capabilities


def test_methodology_uses_model_native_lane_without_controller_llm_or_rag() -> None:
    def forbidden_llm(_messages: list[dict[str, str]]):
        raise AssertionError("deterministic methodology route must not call controller LLM")

    decision = decide_turn(
        "编排层为什么会导致模板化？",
        llm_complete=forbidden_llm,
    )

    assert decision.lane == "knowledge"
    assert decision.question_type == "methodology_discussion"
    assert decision.needs_retrieval is False
    assert decision.needs_memory is False
    assert decision.needs_template is False
    assert decision.capabilities == ()


def test_fresh_general_knowledge_requests_retrieval_without_finance_template() -> None:
    decision = decide_turn("PQC最新消息", llm_complete=_no_llm)

    assert decision.lane == "knowledge"
    assert decision.needs_retrieval is True
    assert decision.needs_template is False
    assert "web_search" in decision.capabilities


def test_external_market_uses_research_lane_and_quote_capability() -> None:
    decision = decide_turn("昨天美股的涨跌情况", llm_complete=_no_llm)

    assert decision.lane == "research"
    assert decision.question_type == "external_market"
    assert decision.needs_retrieval is True
    assert decision.needs_template is True
    assert "market_quote" in decision.capabilities


def test_weekly_market_cause_is_deterministic_and_skips_controller_llm() -> None:
    decision = decide_turn(
        "这一周行情下跌的主要原因你认为是什么",
        skill_mode="hybrid",
        llm_complete=lambda _messages: pytest.fail(
            "weekly market cause must use deterministic head routing"
        ),
    )

    assert decision.lane == "research"
    assert decision.question_type == "market_cause"
    assert decision.timeframe == "这一周"
    assert decision.needs_template is False
    assert {"market_quote", "market_news", "web_search"}.issubset(
        decision.capabilities
    )


@pytest.mark.parametrize(
    "query",
    (
        "总结一下 2026-07-16 的行情",
        "复盘 2026年7月16日 A股市场",
        "2026/7/16 的盘面回顾",
    ),
)
def test_dated_a_share_market_summary_uses_workflow_lane(query: str) -> None:
    decision = decide_turn(query, llm_complete=_no_llm)

    assert decision.lane == "workflow"
    assert decision.timeframe is not None
    assert decision.needs_retrieval is True
    assert decision.needs_template is True


@pytest.mark.parametrize(
    "query",
    (
        "总结一下7.16的行情",
        "复盘7月16日的A股市场",
    ),
)
def test_yearless_dated_market_summary_uses_workflow_lane(query: str) -> None:
    decision = decide_turn(query, llm_complete=_no_llm)

    assert decision.lane == "workflow"
    assert decision.needs_retrieval is True
    assert decision.needs_template is True


@pytest.mark.parametrize(
    "query",
    (
        "今天有什么值得关注的",
        "今日盘面有哪些看点",
        "今天的大盘怎么样",
    ),
)
def test_market_watch_query_uses_workflow_lane(query: str) -> None:
    decision = decide_turn(query, llm_complete=_no_llm)

    assert decision.lane == "workflow"
    assert decision.needs_retrieval is True
    assert decision.needs_template is True
    assert "market_quote" in decision.capabilities


def test_market_watch_head_route_canonicalizes_spurious_theme_resolution() -> None:
    query = "今天有什么值得关注的？请给出主线、观察清单、验证信号和风险。"

    class SpuriousThemeResolver:
        def resolve(self, _query: str) -> QueryResolution:
            return QueryResolution(
                envelope=QueryEnvelope(
                    question_type="theme_analysis",
                    subject_kind="theme",
                    subject="信号系统",
                    decision_goal="形成条件化判断",
                    timeframe="今天",
                    matched_by="candidate",
                    confidence=0.98,
                    research_mode="theme_research",
                    time_horizon="intraday",
                ),
                anchor=None,
            )

    decision = decide_turn(
        query,
        resolver=SpuriousThemeResolver(),
        llm_complete=lambda _messages: pytest.fail(
            "market-watch head route must not invoke the LLM controller"
        ),
    )

    assert decision.lane == "workflow"
    assert decision.question_type == "market_watch"
    assert decision.subject is None
    assert decision.turn_intent is not None
    assert decision.turn_intent.question_type == "market_watch"
    assert decision.turn_intent.primary_subject is None
    assert decision.turn_intent.answer_owner is None


def test_daily_review_head_route_canonicalizes_spurious_theme_resolution() -> None:
    query = "请做今日市场复盘：市场阶段、主线、赚钱效应、风险和验证信号。"

    class SpuriousThemeResolver:
        def resolve(self, _query: str) -> QueryResolution:
            return QueryResolution(
                envelope=QueryEnvelope(
                    question_type="theme_analysis",
                    subject_kind="theme",
                    subject="信号系统",
                    decision_goal="形成条件化判断",
                    timeframe="今日",
                    matched_by="candidate",
                    confidence=0.98,
                    research_mode="theme_research",
                    time_horizon="intraday",
                ),
                anchor=None,
            )

    decision = decide_turn(
        query,
        resolver=SpuriousThemeResolver(),
        llm_complete=lambda _messages: pytest.fail(
            "daily-review head route must not invoke the LLM controller"
        ),
    )

    assert decision.lane == "workflow"
    assert decision.question_type == "market_watch"
    assert decision.subject is None
    assert decision.turn_intent is not None
    assert decision.turn_intent.answer_owner is None


@pytest.mark.parametrize(
    ("query", "question_type"),
    (
        ("最近固态电池有什么新进展", "theme_analysis"),
        ("英伟达GPU发布对光模块板块的影响", "news_impact"),
    ),
)
def test_owner_question_types_use_research_lane(
    query: str, question_type: str
) -> None:
    decision = decide_turn(query, llm_complete=_no_llm)

    assert decision.lane == "research"
    assert decision.question_type == question_type
    assert decision.needs_retrieval is True


def test_unverified_subject_guess_does_not_force_research_lane() -> None:
    decision = decide_turn("PQC最新消息", llm_complete=_no_llm)

    assert decision.lane == "knowledge"
    assert decision.needs_retrieval is True


def _llm_chat_no_retrieval(_messages: list[dict[str, str]]):
    return (
        json.dumps(
            {
                "route_id": "chat",
                "subject": None,
                "timeframe": None,
                "confidence": 0.9,
                "reason": "闲聊",
            }
        ),
        None,
        "ok",
    )


def test_retrieval_floor_upgrades_chat_lane_with_market_signal() -> None:
    decision = decide_turn(
        "跟我随便聊聊大盘呗",
        llm_complete=_llm_chat_no_retrieval,
    )

    assert decision.lane == "knowledge"
    assert decision.needs_retrieval is True


def test_retrieval_floor_keeps_plain_chat_without_signals() -> None:
    decision = decide_turn(
        "给我讲个笑话",
        llm_complete=_llm_chat_no_retrieval,
    )

    assert decision.lane == "chat"
    assert decision.needs_retrieval is False


def test_safe_fallback_retrieves_when_market_signal_present() -> None:
    decision = decide_turn("聊聊今天大盘的情况呗", llm_complete=_no_llm)

    assert decision.lane in {"knowledge", "workflow"}
    assert decision.needs_retrieval is True


def test_dated_external_market_summary_does_not_use_a_share_workflow() -> None:
    decision = decide_turn(
        "总结一下 2026-07-16 的美股行情",
        llm_complete=_no_llm,
    )

    assert decision.lane == "research"
    assert decision.question_type == "external_market"


def test_month_only_market_summary_does_not_claim_daily_report() -> None:
    decision = decide_turn(
        "总结一下 2026年7月 的 A股行情",
        llm_complete=_no_llm,
    )

    assert decision.lane != "workflow"


def test_broad_daily_market_question_defaults_to_a_share_workflow() -> None:
    decision = decide_turn("今天市场怎么样", llm_complete=_no_llm)

    assert decision.lane == "workflow"
    assert decision.question_type == "market_watch"
    assert decision.needs_retrieval is True


def test_explicit_market_outlook_routes_to_forecast_without_clarifying() -> None:
    decision = decide_turn(
        "我希望你基于目前的市场数据，展望一下后面市场会怎么演绎",
        llm_complete=_no_llm,
    )

    assert decision.lane == "research"
    assert decision.question_type == "market_forecast"
    assert "market_quote" in decision.capabilities
    assert decision.clarification_questions == ()


def test_rebound_horizon_keeps_task_frame_semantics_without_llm() -> None:
    question = "昨天的反弹能持续多久"

    decision = decide_turn(
        question,
        llm_complete=lambda _messages: pytest.fail(
            "rebound-horizon head must not depend on the controller LLM"
        ),
    )

    assert decision.lane == "research"
    assert decision.question_type == "market_forecast"
    assert decision.subject == "A股市场"
    assert decision.timeframe == "最近交易日"
    assert decision.task_frame is not None
    assert decision.task_frame.raw_question == question
    assert decision.turn_intent is not None
    assert decision.turn_intent.task_frame_hash == decision.task_frame.task_frame_hash


def test_unbound_rebound_reference_clarifies_once_without_llm() -> None:
    decision = decide_turn(
        "这个反弹还能持续多久",
        llm_complete=lambda _messages: pytest.fail(
            "blocking rule ambiguity must be resolved before the controller LLM"
        ),
    )

    assert decision.lane == "clarify"
    assert decision.subject is None
    assert len(decision.clarification_questions) == 1
    assert decision.task_frame is not None
    assert decision.task_frame.raw_question == "这个反弹还能持续多久"
    assert decision.task_frame.clarification_question == (
        "你希望我围绕哪个明确主体继续判断？"
    )
    assert decision.clarification_questions == (
        decision.task_frame.clarification_question,
    )


def test_clarification_answer_resumes_pending_rebound_task_frame() -> None:
    question = "这个反弹还能持续多久"
    first = decide_turn(
        question,
        llm_complete=lambda _messages: pytest.fail(
            "blocking rule ambiguity must not call the controller LLM"
        ),
    )

    assert first.turn_intent is not None
    assert first.turn_intent.pending_task_frame is not None
    assert first.turn_intent.pending_task_frame["raw_question"] == question
    assert first.turn_intent.clarification_rounds == 1

    resumed = decide_turn(
        "这个反弹指A股",
        previous_intent=first.turn_intent,
        previous_turn_id="msg-clarification",
        llm_complete=lambda _messages: pytest.fail(
            "clarification answer must resume the deterministic forecast"
        ),
    )

    assert resumed.lane == "research"
    assert resumed.question_type == "market_forecast"
    assert resumed.subject == "A股市场"
    assert resumed.clarification_questions == ()
    assert resumed.task_frame is not None
    assert resumed.task_frame.raw_question == question
    assert resumed.task_frame.user_goal == first.task_frame.user_goal
    assert resumed.task_frame.required_outputs == first.task_frame.required_outputs
    assert resumed.turn_intent is not None
    assert resumed.turn_intent.pending_task_frame is None
    assert resumed.turn_intent.clarification_rounds == 1


def test_legacy_context_dependent_clarification_resumes_same_forecast_frame() -> None:
    question = "这个反弹还能持续多久"
    historical = replace(
        understand_query("昨天的反弹能持续多久"),
        subject="A股市场",
        subject_kind="market_pattern",
    )

    class HistoricalContextResolver:
        def resolve(self, _query: str) -> QueryResolution:
            return QueryResolution(
                envelope=historical,
                anchor=None,
                reference_kind="continuation",
                context_dependent=True,
            )

    first = decide_turn(
        question,
        resolver=HistoricalContextResolver(),  # type: ignore[arg-type]
        llm_complete=lambda _messages: pytest.fail(
            "legacy context-dependent clarification must not call the LLM"
        ),
    )

    assert first.lane == "clarify"
    assert first.task_frame is not None
    assert first.task_frame.raw_question == question
    assert first.task_frame.question_type == "market_forecast"
    assert first.turn_intent is not None
    assert first.turn_intent.pending_task_frame == first.task_frame.to_dict()
    assert first.turn_intent.clarification_rounds == 1

    resumed = decide_turn(
        "科创50",
        previous_intent=first.turn_intent,
        previous_turn_id="msg-legacy-clarification",
        llm_complete=lambda _messages: pytest.fail(
            "clarification answer must resume the stored forecast"
        ),
    )

    assert resumed.lane == "research"
    assert resumed.question_type == "market_forecast"
    assert resumed.subject == "科创50"
    assert resumed.task_frame is not None
    assert resumed.task_frame.raw_question == question
    assert resumed.task_frame.user_goal == first.task_frame.user_goal
    assert resumed.task_frame.required_outputs == first.task_frame.required_outputs
    assert resumed.turn_intent is not None
    assert resumed.turn_intent.pending_task_frame is None


def test_rebound_reference_inherits_subject_without_rewriting_raw_question() -> None:
    previous = TurnIntent(
        primary_subject="科创50",
        secondary_topics=(),
        question_type="market_forecast",
        answer_owner=None,
        comparison_entities=(),
        inherited_from_turn=None,
    )
    question = "这个反弹还能持续多久"

    decision = decide_turn(
        question,
        previous_intent=previous,
        previous_turn_id="msg-previous",
        llm_complete=lambda _messages: pytest.fail(
            "inherited rebound head must remain deterministic"
        ),
    )

    assert decision.lane == "research"
    assert decision.subject == "科创50"
    assert decision.clarification_questions == ()
    assert decision.task_frame is not None
    assert decision.task_frame.raw_question == question
    assert decision.task_frame.subject == "科创50"
    assert decision.task_frame.subject_kind == "market_pattern"


def test_company_valuation_uses_research_lane() -> None:
    decision = decide_turn("某公司估值怎么看", llm_complete=_no_llm)

    assert decision.lane == "research"
    assert decision.needs_retrieval is True
    assert "financials" in decision.capabilities


def test_company_upside_with_freshness_uses_research_lane() -> None:
    decision = decide_turn(
        "瑞华泰还有上涨空间吗？请按本地知识库和最新盘面判断。",
        llm_complete=_no_llm,
    )

    assert decision.lane == "research"
    assert decision.needs_retrieval is True
    assert decision.needs_template is True


@pytest.mark.parametrize(
    ("query", "owner"),
    (
        ("瑞华泰还有上涨空间吗？", "stock-deep-dive"),
        (
            "请个股深挖英维克的液冷业务，收入和利润都要覆盖",
            "stock-deep-dive",
        ),
        ("分析英维克最新财报", "financial-analysis"),
        ("英维克最新液冷公告有什么影响", "news-impact"),
    ),
)
def test_controller_is_unique_research_owner(query: str, owner: str) -> None:
    decision = decide_turn(query, llm_complete=_no_llm)

    assert decision.turn_intent is not None
    assert decision.turn_intent.answer_owner == owner


def test_follow_up_inherits_subject_owner_and_evidence_set() -> None:
    previous = TurnIntent(
        primary_subject="英维克",
        secondary_topics=("液冷",),
        question_type="stock_deep_dive",
        answer_owner="stock-deep-dive",
        comparison_entities=(),
        inherited_from_turn=None,
        evidence_atom_ids=("atom-1", "atom-2"),
    )

    decision = decide_turn(
        "那它的客户和订单呢？",
        previous_intent=previous,
        previous_turn_id="msg-previous",
        llm_complete=_no_llm,
    )

    assert decision.lane == "research"
    assert decision.subject == "英维克"
    assert decision.turn_intent is not None
    assert decision.turn_intent.answer_owner == "stock-deep-dive"
    assert decision.turn_intent.inherited_from_turn == "msg-previous"
    assert decision.turn_intent.evidence_atom_ids == ("atom-1", "atom-2")


@pytest.mark.parametrize(
    "query",
    (
        "毛利率下滑的原因是什么",
        "它和海光信息比，哪个弹性更大",
        "一阶受益和二阶受益分别是谁",
        "历史类似情况后来怎么演绎",
        "真实订单证据在哪里",
        "下周验证清单",
    ),
)
def test_financial_context_dependent_followups_inherit_research_gate(
    query: str,
) -> None:
    previous = TurnIntent(
        primary_subject="立讯精密",
        secondary_topics=("AI 服务器",),
        question_type="stock_deep_dive",
        answer_owner="stock-deep-dive",
        comparison_entities=(),
        inherited_from_turn=None,
        evidence_atom_ids=("atom-1",),
        skill_ids=("stock-deep-dive",),
        stage_artifact_ids=("owner:company_master:hash",),
    )

    decision = decide_turn(
        query,
        previous_intent=previous,
        previous_turn_id="msg-previous",
        llm_complete=_no_llm,
    )

    assert decision.lane == "research"
    assert decision.subject == "立讯精密"
    assert decision.turn_intent is not None
    assert decision.turn_intent.inherited_from_turn == "msg-previous"
    assert decision.turn_intent.skill_ids == ("stock-deep-dive",)
    assert decision.turn_intent.stage_artifact_ids == (
        "owner:company_master:hash",
    )


@pytest.mark.parametrize(
    ("query", "operator"),
    (
        ("这个逻辑呢", None),
        ("这个方向怎么看", None),
        ("这条链有哪些公司", "company_mapping"),
        ("边际变化呢", "market_change"),
    ),
)
def test_new_contextual_references_inherit_governed_owner(
    query: str,
    operator: str | None,
) -> None:
    previous = TurnIntent(
        primary_subject="中际旭创",
        secondary_topics=("光模块",),
        question_type="stock_deep_dive",
        answer_owner="stock-deep-dive",
        comparison_entities=(),
        inherited_from_turn=None,
        evidence_atom_ids=("atom-1",),
    )

    decision = decide_turn(
        query,
        previous_intent=previous,
        previous_turn_id="msg-previous",
        llm_complete=_no_llm,
    )

    assert decision.lane == "research"
    assert decision.subject == "中际旭创"
    assert decision.turn_intent is not None
    assert decision.turn_intent.answer_owner == "stock-deep-dive"
    assert decision.turn_intent.inherited_from_turn == "msg-previous"
    assert decision.turn_intent.evidence_atom_ids == ("atom-1",)
    if operator is not None:
        assert operator in decision.turn_intent.operators


def test_non_owner_skill_followup_cannot_fall_back_to_general_chat() -> None:
    previous = TurnIntent(
        primary_subject="今日复盘",
        secondary_topics=(),
        question_type="general",
        answer_owner=None,
        comparison_entities=(),
        inherited_from_turn=None,
        skill_ids=("daily-review",),
    )

    decision = decide_turn(
        "下周验证清单",
        previous_intent=previous,
        previous_turn_id="msg-daily",
        llm_complete=_no_llm,
    )

    assert decision.lane in {"research", "workflow"}
    assert decision.needs_retrieval is True
    assert decision.needs_template is True
    assert decision.turn_intent is not None
    assert decision.turn_intent.skill_ids == ("daily-review",)


def test_explicit_follow_up_task_switch_keeps_subject_and_changes_owner() -> None:
    previous = TurnIntent(
        primary_subject="英维克",
        secondary_topics=("液冷",),
        question_type="stock_deep_dive",
        answer_owner="stock-deep-dive",
        comparison_entities=(),
        inherited_from_turn=None,
    )

    decision = decide_turn(
        "再看一下最新财报",
        previous_intent=previous,
        previous_turn_id="msg-previous",
        llm_complete=_no_llm,
    )

    assert decision.subject == "英维克"
    assert decision.question_type == "financial_analysis"
    assert decision.turn_intent is not None
    assert decision.turn_intent.answer_owner == "financial-analysis"


def test_a04_comparison_inherits_theme_research_owner() -> None:
    previous = TurnIntent(
        primary_subject="液冷",
        secondary_topics=(),
        question_type="theme_analysis",
        answer_owner="theme-research",
        comparison_entities=(),
        inherited_from_turn=None,
    )

    decision = decide_turn(
        "强瑞技术和冰轮环境，谁的证据更硬？只按可核验事实比较。",
        previous_intent=previous,
        previous_turn_id="msg-previous",
        llm_complete=_no_llm,
    )

    assert decision.lane == "research"
    assert decision.subject == "液冷"
    assert decision.turn_intent is not None
    assert decision.turn_intent.answer_owner == "theme-research"


def test_a16_comparison_inherits_stock_deep_dive_owner() -> None:
    previous = TurnIntent(
        primary_subject="英维克",
        secondary_topics=("液冷",),
        question_type="stock_deep_dive",
        answer_owner="stock-deep-dive",
        comparison_entities=(),
        inherited_from_turn=None,
    )

    decision = decide_turn(
        "和高澜股份、申菱环境横向比，市场奖励谁、犹豫谁、抛弃谁？",
        previous_intent=previous,
        previous_turn_id="msg-a15",
        llm_complete=_no_llm,
    )

    assert decision.lane == "research"
    assert decision.subject == "英维克"
    assert decision.turn_intent is not None
    assert decision.turn_intent.answer_owner == "stock-deep-dive"
    assert decision.turn_intent.inherited_from_turn == "msg-a15"


@pytest.mark.parametrize(
    ("case_id", "query", "owner"),
    (
        (
            "A03",
            "液冷现在处于什么阶段？产业链和核心公司怎么分层？",
            "theme-research",
        ),
        (
            "A15",
            "请个股深挖英维克的液冷业务：公司本体、客户证据、"
            "收入传导、市场选择和风险都要覆盖。",
            "stock-deep-dive",
        ),
        (
            "A17",
            "分析英维克最新财报：收入、利润率、现金流和同比变化。",
            "financial-analysis",
        ),
        (
            "A18",
            "英维克最新液冷公告会产生什么一阶和二阶影响？",
            "news-impact",
        ),
    ),
)
def test_architecture_acceptance_fixture_owner(
    case_id: str,
    query: str,
    owner: str,
) -> None:
    decision = decide_turn(query, llm_complete=_no_llm)

    assert decision.lane == "research", case_id
    assert decision.turn_intent is not None, case_id
    assert decision.turn_intent.answer_owner == owner, case_id


def test_explicit_product_workflows_do_not_depend_on_llm_classification() -> None:
    for query in (
        "今天研究什么？按优先级列证据缺口、研究动作和可证伪点。",
        "美股AI回撤榜",
    ):
        decision = decide_turn(query, llm_complete=_no_llm)
        assert decision.lane == "workflow"
        assert decision.needs_retrieval is True
        assert decision.needs_template is True


def test_manual_skill_selection_forces_workflow_lane() -> None:
    decision = decide_turn(
        "按这个流程做",
        skill_mode="manual",
        selected_skill_ids=("daily-review",),
        llm_complete=_no_llm,
    )

    assert decision.lane == "workflow"
    assert decision.needs_retrieval is True
    assert decision.needs_memory is True
    assert decision.needs_template is True


def test_llm_decision_is_schema_validated_and_policy_constrained() -> None:
    content = json.dumps(
        {
            "route_id": "chat",
            "subject": None,
            "timeframe": None,
            "confidence": 0.91,
            "reason": "普通交流",
        },
        ensure_ascii=False,
    )
    decision = decide_turn(
        "你觉得这个解释清楚吗",
        llm_complete=lambda _messages: (content, object(), ""),
    )

    assert decision.lane == "chat"
    assert decision.needs_retrieval is False
    assert decision.needs_memory is False
    assert decision.needs_template is False
    assert decision.capabilities == ()


def test_controller_llm_supplements_task_frame_without_replacing_semantics() -> None:
    content = json.dumps(
        {
            "route_id": "chat",
            "confidence": 0.91,
            "reason": "普通交流",
            "user_goal": "判断产业趋势是否会改变市场持续性",
            "required_outputs": ["trend_signal"],
            "assumptions": ["先按未来五个交易日观察"],
            "ambiguities": ["观察窗口未明确，先声明假设"],
        },
        ensure_ascii=False,
    )
    calls: list[list[dict[str, str]]] = []

    def complete(messages: list[dict[str, str]]):
        calls.append(messages)
        return content, object(), ""

    decision = decide_turn(
        "帮我判断产业趋势",
        llm_complete=complete,
    )

    assert len(calls) == 1
    assert '"task_frame"' in calls[0][1]["content"]
    assert decision.lane == "research"
    assert decision.needs_retrieval is True
    assert decision.task_frame is not None
    assert decision.task_frame.market_scope == "A股"
    assert decision.task_frame.subject != "帮我判断产业趋势"
    assert decision.task_frame.user_goal == "判断产业趋势是否会改变市场持续性"
    assert "trend_signal" not in decision.task_frame.required_outputs
    assert "先按未来五个交易日观察" in decision.task_frame.assumptions


def test_llm_chat_route_cannot_disable_task_frame_retrieval() -> None:
    content = json.dumps(
        {
            "route_id": "chat",
            "confidence": 0.91,
            "reason": "错误地按普通交流处理",
            "user_goal": "判断产业趋势",
            "required_outputs": ["supporting_evidence"],
            "assumptions": [],
            "ambiguities": [],
        },
        ensure_ascii=False,
    )

    decision = decide_turn(
        "帮我判断这个产业趋势是否成立",
        llm_complete=lambda _messages: (content, object(), ""),
    )

    assert decision.task_frame is not None
    assert decision.task_frame.evidence_policy == "general_finance_evidence"
    assert decision.lane == "research"
    assert decision.needs_retrieval is True
    assert decision.needs_template is True
    assert "web_search" in decision.capabilities


def test_llm_decision_rejects_route_id_outside_table() -> None:
    content = json.dumps(
        {
            "route_id": "made_up_route",
            "subject": None,
            "timeframe": None,
            "confidence": 0.95,
            "reason": "臆造路由",
        },
        ensure_ascii=False,
    )
    decision = decide_turn(
        "你觉得这个解释清楚吗",
        llm_complete=lambda _messages: (content, object(), ""),
    )

    assert "Controller 不可用" in decision.reason or decision.lane in {
        "chat",
        "knowledge",
    }
    assert decision.lane != "made_up_route"


def test_llm_route_row_derives_owner_lane_and_capabilities() -> None:
    content = json.dumps(
        {
            "route_id": "stock_deep_dive",
            "subject": "中际旭创",
            "timeframe": None,
            "confidence": 0.88,
            "reason": "个股深度研究",
        },
        ensure_ascii=False,
    )
    decision = decide_turn(
        "英伟达值得入手吗",
        llm_complete=lambda _messages: (content, object(), ""),
    )

    assert decision.lane == "research"
    assert decision.needs_retrieval is True
    assert decision.needs_template is True
    assert "market_quote" in decision.capabilities


def test_llm_decision_accepts_json_code_fence() -> None:
    content = """```json
{"route_id":"concept_definition","subject":"测试",
"timeframe":null,"confidence":0.9,"reason":"概念问题"}
```"""
    decision = decide_turn(
        "请解释这个概念",
        llm_complete=lambda _messages: (content, object(), ""),
    )

    assert decision.lane == "knowledge"
    assert decision.needs_retrieval is False


def test_low_confidence_llm_decision_abstains_to_clarify() -> None:
    content = json.dumps(
        {
            "route_id": "stock_deep_dive",
            "subject": None,
            "timeframe": None,
            "confidence": 0.42,
            "reason": "不确定",
        },
        ensure_ascii=False,
    )
    decision = decide_turn(
        "那这个呢",
        llm_complete=lambda _messages: (content, object(), ""),
    )

    assert decision.lane == "clarify"
    assert decision.needs_retrieval is False
    assert decision.clarification_questions


def test_invalid_llm_payload_safely_falls_back_without_research() -> None:
    decision = decide_turn(
        "随便聊聊未来",
        llm_complete=lambda _messages: ('{"lane":"research"}', object(), ""),
    )

    assert decision.lane == "chat"
    assert decision.needs_retrieval is False


def _failing_llm(reason: str):
    def _complete(_messages: list[dict[str, str]]):
        return None, None, reason

    return _complete


def test_controller_failure_records_stable_reason_in_decision() -> None:
    """controller 挂掉时把「为什么挂」留在决策里——此前它被丢进 ``_reason``。"""

    decision = decide_turn(
        "随便聊聊未来",
        llm_complete=_failing_llm("LLM 调用 HTTP 429"),
    )

    assert decision.llm_failure_reason == "provider_rate_limited"
    assert "429" in decision.llm_failure_detail
    # trace 拿的是 to_dict()，字段必须真的流到那一层
    assert decision.to_dict()["llm_failure_reason"] == "provider_rate_limited"


def test_controller_exception_is_no_longer_swallowed_silently() -> None:
    """裸 except 曾经让异常零输出；枚举可能认不出，但原文必须留下类型。"""

    def _raising(_messages: list[dict[str, str]]):
        raise TimeoutError("provider gone")

    decision = decide_turn("随便聊聊未来", llm_complete=_raising)

    assert decision.llm_failure_reason  # 至少给出一个可聚合的枚举
    assert "TimeoutError" in decision.llm_failure_detail


def test_unparsable_controller_output_is_not_labelled_provider_outage() -> None:
    """provider 回话了但我们没读懂，跟 provider 挂了是两回事，不能混成一类。"""

    decision = decide_turn(
        "随便聊聊未来",
        llm_complete=lambda _messages: ('{"lane":"research"}', object(), ""),
    )

    assert decision.llm_failure_reason == "unparsable_response"
    assert decision.llm_failure_detail == ""


def test_successful_controller_turn_records_no_failure() -> None:
    """成功时两个字段必须留空，否则 trace 里会出现假的故障率。"""

    content = json.dumps(
        {
            "route_id": "chat",
            "subject": None,
            "timeframe": None,
            "confidence": 0.9,
            "reason": "闲聊",
        },
        ensure_ascii=False,
    )
    called: list[int] = []

    def _complete(_messages: list[dict[str, str]]):
        called.append(1)
        return content, object(), ""

    decision = decide_turn("随便聊聊未来", llm_complete=_complete)

    assert called, "这条断言只有在真调了 LLM 时才有意义"
    assert decision.llm_failure_reason == ""
    assert decision.llm_failure_detail == ""


def test_deterministic_route_records_no_failure() -> None:
    """确定性分支压根没调 LLM，空字段就是「没调过」的信号。"""

    decision = decide_turn(
        "你好",
        llm_complete=lambda _messages: pytest.fail("确定性分支不该调 LLM"),
    )

    assert decision.llm_failure_reason == ""
    assert decision.llm_failure_detail == ""
