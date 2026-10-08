from __future__ import annotations

import json
from dataclasses import replace
from datetime import date

import pytest

from intelligence.adapters.knowledge import KnowledgeAdapter
from intelligence.services.research_contract import TurnIntent
from intelligence.services.temporal_contract import compile_temporal_contract
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
                    "长电科技": {"codes": ["600584.SH"], "concepts": {}},
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


def test_controller_researches_candidate_entity_instead_of_asking(tmp_path) -> None:
    """2026-10-06：候选主体不再先追问，交给研究去核实（同题对照里「天工量子科技」
    被截成一句反问、一次没查）。R13-A3 的教训照旧：不硬锚任何候选，主体留空，
    候选原样写进歧义说明，由模型查完再答。"""

    decision = decide_turn(
        "立新能源怎么看",
        llm_complete=_no_llm,
        resolver=_theme_lexicon_resolver(tmp_path),
    )

    assert decision.lane == "research"
    assert decision.needs_retrieval
    assert decision.clarification_questions == ()
    assert decision.subject is None
    frame = decision.task_frame
    assert frame is not None
    assert frame.clarification_question is None
    assert frame.subject is None
    ambiguity = " ".join(frame.ambiguities)
    assert "立新能源" in ambiguity and "新能源" in ambiguity
    assert any("不反问用户" in item for item in frame.assumptions)
    assert decision.turn_intent is not None
    assert decision.turn_intent.pending_task_frame is None


def test_controller_still_resumes_a_legacy_entity_tristate_clarification(tmp_path) -> None:
    """升级前已经挂起的「公司还是板块」追问：用户答了之后仍按公司收口。"""

    first = decide_turn(
        "立新能源怎么看",
        llm_complete=_no_llm,
        resolver=_theme_lexicon_resolver(tmp_path),
    )
    assert first.task_frame is not None and first.turn_intent is not None
    pending = replace(
        first.task_frame,
        clarification_question="你问的是立新能源还是新能源板块？",
    )
    legacy_intent = replace(
        first.turn_intent,
        pending_task_frame=pending.to_dict(),
        clarification_rounds=1,
        task_frame_hash=pending.task_frame_hash,
    )

    resumed = decide_turn(
        "立新能源",
        previous_intent=legacy_intent,
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


_MATERIAL_REPORT = (
    "【卖方摘要｜2026-08-28】固态电池：硫化物路线进入中试放量期\n\n"
    "一、核心观点\n公司 A 硫化物电解质中试线 2026 年 8 月投产，规划产能 200 吨/年，"
    "预计 2027 年一季度满产。管理层在电话会中表示下游两家电池厂已完成 A 样验证。\n\n"
    "二、关键数据\n2026 年上半年新签订单 12 亿元，同比增长 40%；毛利率 31.5%（去年同期 27.2%）。\n\n"
    "三、我们的判断\n我们认为硫化物路线将在 2027 年替代氧化物成为主流，公司 A 是最大受益者，目标价上调 30%。"
)
_EMPTY_PROMPT_BLOCK = (
    "## 较早消息（原文，超预算时从最早处截断）\n（无较早消息）\n\n"
    "## 最近消息原文\n（无历史消息）"
)


def test_decide_turn_binds_material_reference_to_conversation_context() -> None:
    """B05-1：决策层必须把对话块传给 build_task_frame，「这篇」才绑得到上一轮材料。"""

    from intelligence.services.user_task import material_id_for

    block = (
        "## 较早消息（原文，超预算时从最早处截断）\n（无较早消息）\n\n"
        "## 最近消息原文\n"
        f"user: {_MATERIAL_REPORT}\n\n这篇研报的核心逻辑站得住吗？\n"
        "assistant: 硬事实有三条……"
    )
    decision = decide_turn(
        "这篇里提到的产能数字有官方来源吗",
        context=block,
        llm_complete=_no_llm,
    )

    assert decision.task_frame is not None
    assert decision.task_frame.referenced_material_ids == (
        material_id_for(_MATERIAL_REPORT),
    )
    assert decision.lane != "clarify"


def test_decide_turn_asks_for_material_when_known_context_has_none() -> None:
    """B05-1：对话块已知且无材料时，引用材料的题确定性追问一次，不编原文。"""

    from intelligence.services.task_frame import MISSING_MATERIAL_CLARIFICATION

    decision = decide_turn(
        "2026-07-23 把这份卖方材料提纯一下，哪些是硬事实、哪些只能进图谱、哪些只能进观察列表",
        context=_EMPTY_PROMPT_BLOCK,
        llm_complete=_no_llm,
    )

    assert decision.lane == "clarify"
    assert MISSING_MATERIAL_CLARIFICATION in decision.clarification_questions
    # 对话块未知（旧调用方）时保持旧行为：不追问。
    legacy = decide_turn(
        "2026-07-23 把这份卖方材料提纯一下，哪些是硬事实、哪些只能进图谱、哪些只能进观察列表",
        llm_complete=_no_llm,
    )
    assert legacy.lane != "clarify"


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


def _grid_theme_resolver(tmp_path) -> QueryResolver:
    """密封知识库：只登记概念名，实体名不得出现在电网/液冷问句里。"""

    relations = tmp_path / "relations"
    relations.mkdir()
    (relations / "entity_exposures.json").write_text(
        json.dumps(
            {
                "entities": {
                    "测试暴露公司甲": {
                        "codes": [],
                        "concepts": {"电网设备": {}, "液冷温控": {}},
                    }
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


def _boom_llm(_messages: list[dict[str, str]]):
    raise AssertionError("market_cause 确定性路由不得为了分类去调 LLM")


def test_weekly_weakness_word_order_stays_research_not_knowledge() -> None:
    decision = decide_turn(
        "近一周大盘为什么走弱",
        llm_complete=_boom_llm,
    )

    assert decision.lane == "research"
    assert decision.question_type == "market_cause"
    assert decision.task_frame is not None
    assert "causal_chain" in decision.task_frame.required_outputs


def test_aluminum_sector_cause_turn_is_market_cause() -> None:
    decision = decide_turn(
        "2026-07-23 A股铝板块为什么涨，给出证据来源",
        llm_complete=_boom_llm,
    )

    assert decision.lane == "research"
    assert decision.question_type == "market_cause"
    assert decision.task_frame is not None
    assert decision.task_frame.subject == "铝"
    assert "causal_chain" in decision.task_frame.required_outputs


def test_grid_equipment_cause_turn_uses_matched_theme(tmp_path) -> None:
    decision = decide_turn(
        "2026-07-23 电网设备为什么涨，给出证据来源",
        llm_complete=_boom_llm,
        resolver=_grid_theme_resolver(tmp_path),
    )

    assert decision.lane == "research"
    assert decision.question_type == "market_cause"
    assert decision.task_frame is not None
    assert decision.task_frame.subject == "电网设备"
    assert "causal_chain" in decision.task_frame.required_outputs


def test_liquid_cooling_cause_turn_allows_canonical_subject() -> None:
    decision = decide_turn(
        "液冷板块今天为什么涨",
        llm_complete=_boom_llm,
    )

    assert decision.lane == "research"
    assert decision.question_type == "market_cause"
    assert decision.task_frame is not None
    assert decision.task_frame.subject in {"液冷", "液冷温控"}
    assert "causal_chain" in decision.task_frame.required_outputs


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
        temporal_contract=compile_temporal_contract('科创50你认为反弹空间有多少', today=date(2026, 10, 7)),
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
        temporal_contract=compile_temporal_contract('请深挖英维克的客户和订单证据', today=date(2026, 10, 7)),
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
        temporal_contract=compile_temporal_contract('请深挖立讯精密的AI服务器客户订单', today=date(2026, 10, 7)),
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
        temporal_contract=compile_temporal_contract('请深挖中际旭创的光模块客户订单', today=date(2026, 10, 7)),
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
        temporal_contract=compile_temporal_contract('请复盘A股市场', today=date(2026, 10, 7)),
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
        temporal_contract=compile_temporal_contract('请深挖英维克的客户和订单证据', today=date(2026, 10, 7)),
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
        temporal_contract=compile_temporal_contract('请分析液冷题材', today=date(2026, 10, 7)),
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
        temporal_contract=compile_temporal_contract('请深挖英维克的客户和订单证据', today=date(2026, 10, 7)),
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


def _canonical_reply(**changes: object) -> str:
    payload: dict[str, object] = {
        "route_id": "chat",
        "confidence": 0.91,
        "reason": "评估请求",
        "user_goal": "判断产业趋势是否成立",
        "assumptions": ["先按未来五个交易日观察"],
        "ambiguities": ["观察窗口未明确，先声明假设"],
    }
    payload.update(changes)
    return json.dumps(payload, ensure_ascii=False)


@pytest.mark.parametrize(
    ("query", "subject", "subject_kind"),
    (
        (
            "请查询长电科技（600584.SH）在本地行情库最新交易日的收盘价、涨跌幅和成交额，"
            "注明交易日、数据来源及证据边界。",
            "长电科技", "company",
        ),
        ("请列出宁德时代最新交易日的收盘价、涨跌幅和成交额。", "宁德时代", "company"),
        ("请给出中际旭创最近交易日的换手率和收盘价。", "中际旭创", "company"),
        ("固态电池最新交易日的成交额，请列出来。", "固态电池", "theme"),
        ("请查长电科技2026-09-24的收盘价和成交额。", "长电科技", "company"),
        ("长电科技最新收盘价多少？", "长电科技", "company"),
    ),
)
def test_resolved_subject_leaves_natural_fact_intent_to_controller(
    tmp_path, query: str, subject: str, subject_kind: str,
) -> None:
    calls: list[list[dict[str, str]]] = []

    def complete(messages: list[dict[str, str]]):
        calls.append(messages)
        return _canonical_reply(
            route_id="quick_fact", user_goal="查询已发生的行情数值",
            assumptions=[], ambiguities=[],
        ), object(), ""

    decision = decide_turn(query, resolver=_semantic_resolver(tmp_path), llm_complete=complete)

    assert len(calls) == 1
    candidate = json.loads(calls[0][1]["content"])["task_frame"]
    assert "任务类型只是候选" in calls[0][0]["content"]
    assert "已锁定主体、市场、时间和任务类型" not in calls[0][0]["content"]
    assert decision.lane == "research"
    assert decision.question_type == "quick_fact"
    assert decision.needs_retrieval is True
    assert decision.needs_template is False
    assert "market_quote" in decision.capabilities
    assert decision.llm_failure_reason == decision.llm_failure_detail == ""
    assert decision.task_frame is not None
    frame = decision.task_frame
    assert frame.subject == candidate["subject"] == subject
    assert frame.subject_kind == candidate["subject_kind"] == subject_kind
    assert frame.market_scope == candidate["market_scope"]
    assert frame.timeframe == candidate["timeframe"]
    assert json.loads(json.dumps(frame.to_dict())).get("material_contract") == candidate.get("material_contract")
    assert frame.required_outputs == ("fact_value", "as_of_date", "evidence_boundary")
    assert decision.turn_intent is not None
    assert decision.turn_intent.question_type == frame.question_type == "quick_fact"
    assert decision.turn_intent.answer_owner is None
    assert decision.turn_intent.required_outputs == frame.required_outputs
    if "2026-09-24" in query:
        assert frame.timeframe == "2026-09-24"


@pytest.mark.parametrize(
    "query",
    (
        "请深挖长电科技的客户证据、竞争壁垒和风险。",
        "请列出长电科技最新交易日的收盘价和成交额，再判断上涨是否有订单支撑。",
        "长电科技的股价多少，客户和订单证据能支持进一步上涨吗？请深挖。",
        "长电科技最新股价多少？同时判断上涨是否有订单支撑。",
        "长电科技最新收盘价多少？同时解释为什么上涨。",
    ),
)
def test_resolved_company_research_is_not_reduced_to_fact_lookup(tmp_path, query: str) -> None:
    calls: list[list[dict[str, str]]] = []

    def complete(messages):
        calls.append(messages)
        return _canonical_reply(
            route_id="stock_deep_dive", user_goal="研究客户证据和上涨逻辑",
            assumptions=[], ambiguities=[],
        ), object(), ""

    decision = decide_turn(query, resolver=_semantic_resolver(tmp_path), llm_complete=complete)

    assert len(calls) == 1
    assert decision.lane == "research"
    assert decision.question_type == "stock_deep_dive"
    assert decision.needs_retrieval and decision.needs_template
    assert decision.task_frame is not None
    assert decision.task_frame.subject == "长电科技"
    assert "counterpoint" in decision.task_frame.required_outputs
    assert "fact_value" not in decision.task_frame.required_outputs
    assert decision.turn_intent is not None
    assert decision.turn_intent.answer_owner == "stock-deep-dive"


@pytest.mark.parametrize(
    ("query", "controller_calls"),
    (
        ("那请给出它最新交易日的收盘价和成交额。", 1),
        ("那它最新交易日的收盘价和成交额分别是多少？", 1),
    ),
)
def test_inherited_company_can_switch_from_research_to_natural_fact_lookup(
    tmp_path, query: str, controller_calls: int,
) -> None:
    resolver = _semantic_resolver(tmp_path)
    previous = decide_turn(
        "请深挖长电科技的客户证据、竞争壁垒和风险。", resolver=resolver,
        llm_complete=lambda _messages: (
            _canonical_reply(route_id="stock_deep_dive", assumptions=[], ambiguities=[]), object(), "",
        ),
    )
    calls: list[list[dict[str, str]]] = []

    def complete(messages):
        calls.append(messages)
        return _canonical_reply(
            route_id="quick_fact", user_goal="查询已发生的行情数值",
            assumptions=[], ambiguities=[],
        ), object(), ""

    decision = decide_turn(
        query, resolver=resolver,
        previous_intent=previous.turn_intent, previous_turn_id="company-research",
        llm_complete=complete,
    )

    assert len(calls) == controller_calls
    assert decision.lane == "research"
    assert decision.question_type == "quick_fact"
    assert decision.needs_retrieval and not decision.needs_template
    assert decision.subject == "长电科技"
    assert decision.task_frame is not None
    assert decision.task_frame.subject_kind == "company"
    assert decision.task_frame.timeframe == "最新可用交易日"
    assert decision.task_frame.required_outputs == ("fact_value", "as_of_date", "evidence_boundary")
    assert decision.turn_intent is not None
    assert decision.turn_intent.answer_owner is None
    assert decision.turn_intent.inherited_from_turn == "company-research"
    assert decision.turn_intent.required_outputs == decision.task_frame.required_outputs


@pytest.mark.parametrize("unavailable", (False, True))
def test_research_followup_preserves_inherited_contract_and_failure_provenance(
    tmp_path, unavailable: bool,
) -> None:
    resolver = _semantic_resolver(tmp_path)
    reply = _canonical_reply(
        route_id="stock_deep_dive", user_goal="核实客户证据与竞争壁垒",
        assumptions=[], ambiguities=[],
    )
    previous = decide_turn(
        "请深挖长电科技的客户证据、竞争壁垒和风险。", resolver=resolver,
        llm_complete=lambda _messages: (reply, object(), ""),
    )
    assert previous.turn_intent is not None
    previous_intent = replace(previous.turn_intent, evidence_atom_ids=("customer-evidence",))
    calls: list[list[dict[str, str]]] = []

    def complete(messages):
        calls.append(messages)
        return (None, None, "provider unavailable") if unavailable else (reply, object(), "")

    decision = decide_turn(
        "那它的客户和订单还缺哪些证据？", resolver=resolver,
        previous_intent=previous_intent, previous_turn_id="company-research",
        llm_complete=complete,
    )

    assert len(calls) == 1
    assert decision.lane == "research"
    assert decision.question_type == "stock_deep_dive"
    assert decision.needs_retrieval and decision.needs_template
    assert decision.subject == "长电科技"
    assert decision.task_frame is not None
    assert set(previous_intent.required_outputs) <= set(decision.task_frame.required_outputs)
    assert decision.turn_intent is not None
    assert decision.turn_intent.answer_owner == "stock-deep-dive"
    assert decision.turn_intent.inherited_from_turn == "company-research"
    assert decision.turn_intent.evidence_atom_ids == ("customer-evidence",)
    if unavailable:
        assert decision.llm_failure_reason
        assert decision.llm_failure_detail == "provider unavailable"
        assert json.loads(json.dumps(decision.task_frame.to_model_dict())) == json.loads(calls[0][1]["content"])["task_frame"]
    else:
        assert decision.llm_failure_reason == decision.llm_failure_detail == ""


@pytest.mark.parametrize("failure", ("unavailable", "exception", "malformed"))
@pytest.mark.parametrize(
    ("query", "subject", "question_type"),
    (
        ("请查长电科技2026-09-24的收盘价和成交额。", "长电科技", "stock_deep_dive"),
        ("固态电池最新交易日的成交额，请列出来。", "固态电池", "theme_analysis"),
    ),
)
def test_controller_failure_preserves_resolved_research_floor(
    tmp_path, failure: str, query: str, subject: str, question_type: str,
) -> None:
    calls: list[list[dict[str, str]]] = []

    def complete(messages):
        calls.append(messages)
        if failure == "exception":
            raise RuntimeError("fixture offline")
        if failure == "unavailable":
            return None, None, "provider unavailable"
        return _canonical_reply(route_id="invented", user_goal="不得写入此目标"), object(), ""

    decision = decide_turn(query, resolver=_semantic_resolver(tmp_path), llm_complete=complete)

    assert len(calls) == (2 if failure == "malformed" else 1)
    assert decision.lane == "research"
    assert decision.question_type == question_type
    assert decision.needs_retrieval and decision.needs_template
    assert {"memory", "market_quote", "graph"} <= set(decision.capabilities)
    assert decision.llm_failure_reason
    assert decision.llm_failure_detail
    if failure == "malformed":
        assert decision.llm_failure_reason == "unparsable_response"
    assert decision.task_frame is not None
    assert decision.task_frame.subject == subject
    assert json.loads(json.dumps(decision.task_frame.to_model_dict())) == json.loads(calls[0][1]["content"])["task_frame"]
    assert decision.turn_intent is not None
    assert decision.turn_intent.question_type == question_type


def test_legacy_route_reply_cannot_change_confirmed_identity_date_or_material_scope(tmp_path) -> None:
    calls: list[list[dict[str, str]]] = []

    def complete(messages):
        calls.append(messages)
        return json.dumps({
            "route_id": "quick_fact", "confidence": 0.95, "reason": "取值",
            "subject": "宁德时代", "timeframe": "2020-01-02",
        }), object(), ""

    decision = decide_turn(
        "请查长电科技2026-09-24的收盘价和成交额，本轮不要联网。",
        resolver=_semantic_resolver(tmp_path), llm_complete=complete,
    )

    assert len(calls) == 1
    assert decision.question_type == "quick_fact"
    assert decision.task_frame is not None
    assert decision.subject == decision.task_frame.subject == "长电科技"
    assert decision.timeframe == decision.task_frame.timeframe == "2026-09-24"
    assert decision.task_frame.market_scope == "A股"
    assert decision.task_frame.material_contract is not None
    assert decision.task_frame.material_contract.data_scope == "local_only"


def test_long_material_contract_precedes_semantic_task_selection(tmp_path) -> None:
    from intelligence.services.conversation_materials import ConversationMaterials

    calls: list[list[dict[str, str]]] = []

    def complete(messages):
        calls.append(messages)
        return _canonical_reply(route_id="quick_fact"), object(), ""

    query = (
        "只依据以下材料回答，不联网补现实事实。\n\n" + _MATERIAL_REPORT
        + "\n\n问题：材料里的订单额是多少？这些订单能支持利润增长判断吗？请说明缺口。"
    )
    decision = decide_turn(
        query, resolver=_semantic_resolver(tmp_path), llm_complete=complete,
        conversation_materials=ConversationMaterials(),
    )

    assert calls == []
    assert decision.lane == "research"
    assert decision.question_type not in {"quick_fact", "disclosure_scan"}
    assert decision.needs_retrieval is False
    assert decision.capabilities == ()
    assert decision.task_frame is not None
    assert decision.task_frame.material_contract is not None
    assert decision.task_frame.material_contract.data_scope == "material_only"


def test_canonical_six_field_reply_is_accepted_once_with_research_floor() -> None:
    calls: list[list[dict[str, str]]] = []

    def complete(messages: list[dict[str, str]]):
        calls.append(messages)
        return _canonical_reply(), object(), ""

    decision = decide_turn("帮我判断产业趋势", llm_complete=complete)

    assert len(calls) == 1
    assert "route_id,confidence,reason,user_goal,assumptions,ambiguities" in calls[0][0]["content"]
    assert decision.llm_failure_reason == decision.llm_failure_detail == ""
    assert decision.lane == "research" and decision.needs_retrieval
    assert decision.task_frame is not None
    assert decision.task_frame.user_goal == "判断产业趋势是否成立"


def test_valid_retry_aligns_only_accepted_reply() -> None:
    bad = _canonical_reply(route_id="invented_route", user_goal="错误目标", assumptions=["错误假设"])
    good = _canonical_reply(user_goal="正确目标", assumptions=["正确假设"])
    calls: list[list[dict[str, str]]] = []

    def complete(messages: list[dict[str, str]]):
        calls.append(messages)
        return (bad if len(calls) == 1 else good), object(), ""

    decision = decide_turn("帮我判断产业趋势", llm_complete=complete)

    assert len(calls) == 2
    assert calls[1][-2] == {"role": "assistant", "content": bad}
    assert "route_id,confidence,reason,user_goal,assumptions,ambiguities" in calls[1][-1]["content"]
    assert decision.llm_failure_reason == decision.llm_failure_detail == ""
    assert decision.needs_retrieval
    assert decision.task_frame is not None
    assert decision.task_frame.user_goal == "正确目标"
    assert "正确假设" in decision.task_frame.assumptions
    assert "错误假设" not in decision.task_frame.assumptions


def test_rejected_reply_cannot_poison_frame_or_force_clarification() -> None:
    baseline = decide_turn("帮我判断产业趋势", llm_complete=_no_llm)
    bad = _canonical_reply(
        route_id="invented_route",
        user_goal="错误目标",
        assumptions=["错误假设"],
        ambiguities=["市场不明可能改变结论"],
    )
    calls: list[int] = []

    def complete(_messages: list[dict[str, str]]):
        calls.append(1)
        return bad, object(), ""

    decision = decide_turn("帮我判断产业趋势", llm_complete=complete)

    assert len(calls) == 2
    assert decision.llm_failure_reason == "unparsable_response"
    assert decision.needs_retrieval
    assert decision.lane != "clarify"
    assert decision.task_frame is not None and baseline.task_frame is not None
    assert decision.task_frame.user_goal == baseline.task_frame.user_goal
    assert decision.task_frame.assumptions == baseline.task_frame.assumptions
    assert decision.task_frame.ambiguities == baseline.task_frame.ambiguities


def test_accepted_controller_ambiguity_still_clarifies() -> None:
    decision = decide_turn(
        "帮我判断产业趋势",
        llm_complete=lambda _messages: (
            _canonical_reply(ambiguities=["市场不明可能改变结论"]), object(), ""
        ),
    )

    assert decision.lane == "clarify"
    assert decision.clarification_questions == ("你希望我按 A 股、美股，还是其他市场来判断？",)
    assert decision.task_frame is not None
    assert "市场不明可能改变结论" in decision.task_frame.ambiguities


@pytest.mark.parametrize(
    "changes",
    (
        {"route_id": "invented_route"},
        {"confidence": True},
        {"assumptions": "不是数组"},
        {"ambiguities": ["正常", 3]},
        {"extra_key": "unexpected"},
        {"required_outputs": [3]},
    ),
)
def test_invalid_canonical_reply_retries_once_and_preserves_frame(changes: dict[str, object]) -> None:
    calls: list[int] = []
    invalid = _canonical_reply(**changes)
    baseline = decide_turn("帮我判断产业趋势", llm_complete=_no_llm)

    def complete(_messages: list[dict[str, str]]):
        calls.append(1)
        return invalid, object(), ""

    decision = decide_turn("帮我判断产业趋势", llm_complete=complete)

    assert len(calls) == 2
    assert decision.llm_failure_reason == "unparsable_response"
    assert decision.needs_retrieval
    assert decision.task_frame is not None and baseline.task_frame is not None
    assert decision.task_frame.user_goal == baseline.task_frame.user_goal
    assert decision.task_frame.assumptions == baseline.task_frame.assumptions


def test_missing_canonical_field_retries_once() -> None:
    payload = json.loads(_canonical_reply())
    del payload["user_goal"]
    calls: list[int] = []

    def complete(_messages: list[dict[str, str]]):
        calls.append(1)
        return json.dumps(payload), object(), ""

    decision = decide_turn("帮我判断产业趋势", llm_complete=complete)

    assert len(calls) == 2
    assert decision.llm_failure_reason == "unparsable_response"
    assert decision.needs_retrieval


def test_provider_unavailable_does_not_retry_and_keeps_research() -> None:
    calls: list[int] = []

    def complete(_messages: list[dict[str, str]]):
        calls.append(1)
        return None, None, "provider unavailable"

    decision = decide_turn("帮我判断产业趋势", llm_complete=complete)

    assert len(calls) == 1
    assert decision.llm_failure_reason
    assert decision.needs_retrieval
    assert decision.task_frame is not None
    assert decision.task_frame.subject != "帮我判断产业趋势"


def test_canonical_reply_keeps_ordinary_chat_without_retrieval() -> None:
    decision = decide_turn(
        "随便聊聊未来",
        llm_complete=lambda _messages: (_canonical_reply(), object(), ""),
    )

    assert decision.lane == "chat"
    assert decision.needs_retrieval is False
    assert decision.llm_failure_reason == ""


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
    """provider 回话了但我们没读懂，跟 provider 挂了是两回事，不能混成一类。

    detail 断言从「必须空」翻转为「必须留原文」（2026-08-27 P0 D6）：
    生产 39 个 run 里 4 个 unparsable，detail 全空——想验尸「LLM 到底回了
    什么形状」时零证据。粗标签留下、诊断载荷丢弃，与 judge 侧
    ``_stable_failure_reason`` 压扁类名是同一个反模式。
    """

    decision = decide_turn(
        "随便聊聊未来",
        llm_complete=lambda _messages: ('{"lane":"research"}', object(), ""),
    )

    assert decision.llm_failure_reason == "unparsable_response"
    assert '{"lane"' in decision.llm_failure_detail


def test_unparsable_retries_once_with_feedback_then_uses_second_answer() -> None:
    """解析失败不定案：把坏输出贴回去点名问题，再问一次。

    D6（run_20260827_184531_798332）三个 run 的 controller 输出一字不差地
    降级——一次解析失败就直接 ``_safe_fallback``，没有第二次机会。裸重发
    大概率换来同一种坏形状，所以重试消息必须携带第一次的原样输出。
    """

    bad = '{"lane":"research"}'
    good = json.dumps(
        {
            "route_id": "dated_market_review",
            "subject": None,
            "timeframe": "2026-07-22",
            "confidence": 0.9,
            "reason": "指定日期的连板梯队复盘",
        },
        ensure_ascii=False,
    )
    calls: list[list[dict[str, str]]] = []

    def _flaky(messages: list[dict[str, str]]):
        calls.append(messages)
        return (bad if len(calls) == 1 else good), object(), ""

    decision = decide_turn(
        "2026-07-22 高标股的晋级情况如何，有没有出现空档",
        llm_complete=_flaky,
    )

    assert len(calls) == 2
    # 重试不是裸重发：倒数第二条是第一次的原样输出，最后一条是纠错指令
    assert calls[1][-2] == {"role": "assistant", "content": bad}
    assert calls[1][-1]["role"] == "user"
    assert decision.question_type == "dated_market_review"
    assert decision.needs_retrieval is True
    # 第二次成功了，不该给 trace 留假的故障率
    assert decision.llm_failure_reason == ""
    assert decision.llm_failure_detail == ""


def test_unparsable_after_retry_records_original_payload_and_stops() -> None:
    """重试恰好一次（不递归），两次都读不懂时把首次原文留进 detail。"""

    calls: list[int] = []

    def _always_bad(_messages: list[dict[str, str]]):
        calls.append(1)
        return '{"lane":"research"}', object(), ""

    decision = decide_turn("随便聊聊未来", llm_complete=_always_bad)

    assert len(calls) == 2
    assert decision.llm_failure_reason == "unparsable_response"
    assert '{"lane"' in decision.llm_failure_detail


def test_unparsable_fallback_with_dated_question_keeps_retrieval() -> None:
    """D6 冻结形状的端到端钉：controller 双失后，带显式日期的题不得零检索。

    修前这条 run 的终态是 lane=chat / needs_retrieval=False /
    retrieval_stages=[] → 「我答不了，去看开盘啦」。task_frame 里
    timeframe=2026-07-22 一直都在——地板必须接住它。
    """

    calls: list[int] = []

    def complete(_messages: list[dict[str, str]]):
        calls.append(1)
        return '{"lane":"research"}', object(), ""

    decision = decide_turn(
        "2026-07-22 高标股的晋级情况如何，有没有出现空档",
        llm_complete=complete,
    )

    assert len(calls) == 2
    assert decision.needs_retrieval is True
    assert decision.lane != "chat"
    assert decision.timeframe == "2026-07-22"
    assert decision.task_frame is not None
    assert decision.task_frame.timeframe == "2026-07-22"
    assert decision.llm_failure_reason == "unparsable_response"
    assert '{"lane"' in decision.llm_failure_detail


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


_FROZEN_ANALOG = (
    "用spt和风远的结合视角，说一下目前的行情和之前的哪一段历史行情比较相似，个股怎么对标。"
)


def test_empty_manual_does_not_override_comparison_analog() -> None:
    decision = decide_turn(
        _FROZEN_ANALOG,
        skill_mode="manual",
        selected_skill_ids=(),
        llm_complete=_no_llm,
    )
    assert decision.question_type == "comparison_analog"
    assert decision.reason != "用户显式选择了工作流能力"
    assert decision.turn_intent is not None
    assert "history_analog" in decision.turn_intent.operators


def test_nonempty_manual_skill_still_counts_as_explicit_choice() -> None:
    decision = decide_turn(
        _FROZEN_ANALOG,
        skill_mode="manual",
        selected_skill_ids=("daily-agent",),
        llm_complete=_no_llm,
    )
    assert decision.reason == "用户显式选择了工作流能力"


def test_empty_manual_does_not_reroute_quick_fact() -> None:
    decision = decide_turn(
        "宁德时代今天收盘多少",
        skill_mode="manual",
        selected_skill_ids=(),
        llm_complete=lambda _messages: (
            _canonical_reply(route_id="quick_fact", assumptions=[], ambiguities=[]), object(), "",
        ),
    )
    assert decision.question_type == "quick_fact"


@pytest.mark.parametrize("route_id", ("concept_definition", "methodology_discussion"))
@pytest.mark.parametrize(
    ("query", "market_fact"),
    (
        ("请查宁德时代2026-09-24的收盘价和成交额。", True),
        ("请列出宁德时代最新交易日的收盘价、涨跌幅和成交额。", True),
        ("请查宁德时代2026-09-24的产能规模。", False),
        ("请给出宁德时代最近的产能规模。", False),
    ),
)
def test_semantic_knowledge_route_keeps_request_fact_retrieval_floor(
    tmp_path, route_id: str, query: str, market_fact: bool,
) -> None:
    from intelligence.runtime.turn_control_core import project_turn_decision
    from intelligence.services.task_frame import task_frame_requires_retrieval

    calls = []

    def complete(messages):
        calls.append(messages)
        return _canonical_reply(route_id=route_id, assumptions=[], ambiguities=[]), object(), ""

    decision = decide_turn(query, resolver=_semantic_resolver(tmp_path), llm_complete=complete)

    assert len(calls) == 1
    assert decision.question_type == route_id
    assert decision.needs_retrieval
    assert decision.lane == "research"
    frame = decision.task_frame
    assert frame is not None and task_frame_requires_retrieval(frame)
    assert frame.subject == "宁德时代"
    assert frame.evidence_policy not in {"stable_knowledge", "model_reasoning"}
    if "2026-09-24" in query:
        assert frame.timeframe == "2026-09-24"
    control = project_turn_decision(decision, task_frame=frame)
    assert control.terminal_kind == "research" and control.needs_retrieval
    assert control.contract_required and control.capabilities
    if market_fact:
        assert "market_quote" in decision.capabilities
        assert "market_data" in control.capabilities


@pytest.mark.parametrize(
    ("query", "route_id"),
    (
        ("宁德时代这个名字指什么", "concept_definition"),
        ("如何研究宁德时代的经营模式？", "methodology_discussion"),
        ("如何判断宁德时代当前股价是否合理？", "methodology_discussion"),
    ),
)
def test_resolved_company_identity_does_not_force_static_knowledge_retrieval(
    tmp_path, query: str, route_id: str,
) -> None:
    from intelligence.runtime.turn_control_core import project_turn_decision

    calls = []

    def complete(messages):
        calls.append(messages)
        return _canonical_reply(route_id=route_id, assumptions=[], ambiguities=[]), object(), ""

    decision = decide_turn(query, resolver=_semantic_resolver(tmp_path), llm_complete=complete)

    assert len(calls) == 1
    assert decision.question_type == route_id
    assert decision.lane == "knowledge" and not decision.needs_retrieval
    assert decision.capabilities == ()
    assert decision.task_frame is not None
    control = project_turn_decision(decision, task_frame=decision.task_frame)
    assert control.terminal_kind == "non_research"
    assert not control.needs_retrieval and control.capabilities == ()


@pytest.mark.parametrize("injected", (False, True))
@pytest.mark.parametrize(("seconds", "reserve"), ((0.0, 0.0), (2.0, 2.0)))
def test_semantic_controller_does_not_call_after_research_deadline(
    tmp_path, monkeypatch, injected: bool, seconds: float, reserve: float,
) -> None:
    from intelligence.services import llm_refine
    from intelligence.services.research_contract import ResearchDeadline

    calls = []

    def complete(messages, **kwargs):
        calls.append((messages, kwargs))
        return "not json", None, ""

    monkeypatch.setattr(llm_refine, "complete", complete)
    decision = decide_turn(
        "请查宁德时代2026-09-24的收盘价和成交额。",
        resolver=_semantic_resolver(tmp_path),
        llm_complete=complete if injected else None,
        deadline=ResearchDeadline.from_timeout(seconds, synthesis_reserve=reserve),
    )

    assert calls == []
    assert decision.question_type == "stock_deep_dive"
    assert decision.lane == "research" and decision.needs_retrieval
    assert decision.llm_failure_reason == "deadline_exhausted_local"
    assert "截止时间" in decision.llm_failure_detail
    assert decision.to_dict()["llm_failure_reason"] == "deadline_exhausted_local"


def test_semantic_controller_and_repair_share_remaining_stage_budget(tmp_path, monkeypatch) -> None:
    from intelligence.services import llm_refine
    from intelligence.services.research_contract import ResearchDeadline

    now = [100.0]
    monkeypatch.setattr("intelligence.services.turn_controller.time.monotonic", lambda: now[0])
    monkeypatch.setattr(llm_refine, "DEFAULT_LLM_TIMEOUT", 8)
    calls = []

    def complete(messages, **kwargs):
        calls.append((messages, kwargs))
        now[0] += 3
        if len(calls) == 1:
            return "not json", object(), ""
        return _canonical_reply(route_id="quick_fact", assumptions=[], ambiguities=[]), object(), ""

    monkeypatch.setattr(llm_refine, "complete", complete)
    deadline = ResearchDeadline.from_timeout(12, synthesis_reserve=2)
    decision = decide_turn(
        "请查宁德时代2026-09-24的收盘价和成交额。",
        resolver=_semantic_resolver(tmp_path), deadline=deadline,
    )

    assert len(calls) == 2
    assert calls[0][1]["timeout"] == 8
    assert calls[1][1]["timeout"] == 7
    assert calls[1][0][-2] == {"role": "assistant", "content": "not json"}
    assert deadline.expires_at == 112 and deadline.synthesis_reserve == 2
    assert decision.question_type == "quick_fact" and decision.needs_retrieval
    assert decision.llm_failure_reason == decision.llm_failure_detail == ""


@pytest.mark.parametrize("late_attempt", (1, 2))
@pytest.mark.parametrize("late_content", ("not json", "quick_fact"))
def test_semantic_controller_discards_late_primary_or_repair_reply(
    tmp_path, monkeypatch, late_attempt: int, late_content: str,
) -> None:
    from intelligence.services.research_contract import ResearchDeadline

    now = [100.0]
    monkeypatch.setattr("intelligence.services.turn_controller.time.monotonic", lambda: now[0])
    calls = []

    # Injected callbacks retain their one-argument API; deadline admission and
    # late-result rejection still apply at the real decide_turn boundary.
    def complete(messages):
        calls.append(messages)
        if len(calls) < late_attempt:
            return "not json", object(), ""
        now[0] = 110
        if late_content == "quick_fact":
            return _canonical_reply(route_id="quick_fact", assumptions=[], ambiguities=[]), object(), ""
        return late_content, object(), ""

    decision = decide_turn(
        "请查宁德时代2026-09-24的收盘价和成交额。",
        resolver=_semantic_resolver(tmp_path), llm_complete=complete,
        deadline=ResearchDeadline.from_timeout(10),
    )

    assert len(calls) == late_attempt
    assert decision.question_type == "stock_deep_dive"
    assert decision.lane == "research" and decision.needs_retrieval
    assert decision.llm_failure_reason == "deadline_exhausted_local"
    assert "截止时间" in decision.llm_failure_detail
    if late_attempt == 2:
        assert "首次输出：not json" in decision.llm_failure_detail


@pytest.mark.parametrize(
    "query",
    (
        "2026-08-19 全市场成交额排第三的板块是哪个，成交额多少",
        "07-21 全市成交额多少",
    ),
)
@pytest.mark.parametrize("failure", ("unavailable", "exception", "unparsable", "deadline"))
def test_failed_semantic_controller_keeps_known_fact_candidate(tmp_path, query: str, failure: str) -> None:
    from intelligence.services.research_contract import ResearchDeadline

    calls = []

    def complete(messages):
        calls.append(messages)
        if failure == "exception":
            raise RuntimeError("provider unavailable")
        if failure == "unparsable":
            return "not json", object(), ""
        return None, None, "fixture unavailable"

    decision = decide_turn(
        query, resolver=_semantic_resolver(tmp_path), llm_complete=complete,
        deadline=ResearchDeadline.from_timeout(0) if failure == "deadline" else None,
    )

    assert len(calls) == {"unavailable": 1, "exception": 1, "unparsable": 2, "deadline": 0}[failure]
    assert decision.question_type == "quick_fact"
    assert decision.lane == "research" and decision.needs_retrieval
    assert not decision.needs_template
    assert "market_quote" in decision.capabilities
    assert decision.task_frame is not None
    assert decision.task_frame.question_type == "quick_fact"
    assert decision.task_frame.required_outputs == ("fact_value", "as_of_date", "evidence_boundary")
    assert decision.task_frame.raw_question == query
    assert decision.llm_failure_reason and decision.llm_failure_detail


@pytest.mark.parametrize(
    "query",
    (
        "长电科技最新股价多少？同时判断上涨是否有订单支撑。",
        "长电科技最新收盘价多少？同时解释为什么上涨。",
    ),
)
def test_failed_semantic_controller_keeps_mixed_company_research_floor(tmp_path, query: str) -> None:
    from intelligence.runtime.turn_control_core import project_turn_decision

    calls = []

    def complete(messages):
        calls.append(messages)
        return None, None, "fixture unavailable"

    decision = decide_turn(query, resolver=_semantic_resolver(tmp_path), llm_complete=complete)

    assert len(calls) == 1
    assert decision.question_type != "quick_fact"
    assert decision.needs_retrieval
    assert decision.task_frame is not None
    candidate = json.loads(calls[0][1]["content"])["task_frame"]
    assert decision.task_frame.to_model_dict() == candidate
    control = project_turn_decision(decision, task_frame=decision.task_frame)
    assert control.terminal_kind == "research" and control.contract_required
    assert decision.llm_failure_detail == "fixture unavailable"
