from __future__ import annotations

import json

import pytest

from intelligence.services.research_contract import TurnIntent
from intelligence.services.query_resolution import QueryResolution
from intelligence.services.query_understanding import understand_query
from intelligence.services.turn_controller import decide_turn


def _no_llm(_messages: list[dict[str, str]]):
    return None, None, "fixture unavailable"


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


def test_greeting_is_chat_without_tools_or_memory() -> None:
    decision = decide_turn("你好", llm_complete=_no_llm)

    assert decision.lane == "chat"
    assert decision.needs_retrieval is False
    assert decision.needs_memory is False
    assert decision.needs_template is False
    assert decision.capabilities == ()


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


def test_broad_market_question_clarifies_scope() -> None:
    decision = decide_turn("今天市场怎么样", llm_complete=_no_llm)

    assert decision.lane == "clarify"
    assert "A 股" in decision.clarification_questions[0]
    assert decision.needs_retrieval is False


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
            "lane": "chat",
            "needs_retrieval": True,
            "needs_memory": True,
            "needs_template": True,
            "question_type": None,
            "subject": None,
            "timeframe": None,
            "confidence": 0.91,
            "reason": "普通交流",
            "capabilities": ["web_search", "memory"],
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


def test_llm_decision_accepts_json_code_fence() -> None:
    content = """```json
{"lane":"knowledge","needs_retrieval":false,"needs_memory":false,
"needs_template":false,"question_type":"general_knowledge","subject":"测试",
"timeframe":null,"confidence":0.9,"reason":"概念问题","capabilities":[]}
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
            "lane": "research",
            "needs_retrieval": True,
            "needs_memory": False,
            "needs_template": True,
            "question_type": None,
            "subject": None,
            "timeframe": None,
            "confidence": 0.42,
            "reason": "不确定",
            "capabilities": ["web_search"],
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
