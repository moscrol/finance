import json
from pathlib import Path

import pytest

from intelligence.services import query_understanding
from intelligence.services.entity_anchor import EntityAnchor
from intelligence.services.query_understanding import understand_query
from intelligence.services.research_contract import build_turn_intent


GENERIC_LIFECYCLE_QUERY = (
    "如果一个A股题材连续上涨，但板块成交占比开始下降，我应该怎么判断"
    "它是健康分歧还是行情高潮？"
)


def test_generic_market_pattern_has_no_invented_subject() -> None:
    envelope = understand_query(GENERIC_LIFECYCLE_QUERY)

    assert envelope.subject_kind == "market_pattern"
    assert envelope.subject is None
    assert envelope.question_type == "general_finance_qa"
    assert envelope.decision_goal == "区分健康分歧与行情高潮"


def test_weekly_market_cause_has_window_and_causal_output() -> None:
    envelope = understand_query("这一周行情下跌的主要原因你认为是什么")

    assert envelope.question_type == "market_cause"
    assert envelope.subject_kind == "market_pattern"
    assert envelope.subject is None
    assert envelope.timeframe == "这一周"
    assert envelope.time_horizon == "short"
    assert envelope.operators == ("cause_attribution",)
    assert envelope.required_outputs == ("cause_attribution",)


@pytest.mark.parametrize(
    "query",
    (
        "能否帮我把复盘导出成 PDF",
        "能不能把今天的涨停股导出成表格",
        "能否解释一下什么是 PE",
    ),
)
def test_request_prefix_does_not_add_scenario_contract(query: str) -> None:
    """祈使请求不得被追加 scenario_tree 验收项。

    「能否/能不能」曾在 `_SCENARIO_TERMS` 里做裸子串匹配，一句「能否帮我导出」
    就会被判成推演题并追加 `scenario_tree` 这一格 required_output；而导出请求
    永远填不上它，最终由契约门如实拒答，表面症状却是「证据不足」。
    这条断言锁在 envelope 层：命中与否要落到 required_outputs 上才算真的没伤到契约。
    """
    envelope = understand_query(query)

    assert "scenario_tree" not in envelope.operators
    assert "scenario_tree" not in envelope.required_outputs


def test_feasibility_question_keeps_scenario_contract() -> None:
    """真·可行性推演仍要拿到 scenario_tree，否决权不能扩成一刀切。"""
    envelope = understand_query("厦门钨业正极能否扭亏")

    assert "scenario_tree" in envelope.operators
    assert "scenario_tree" in envelope.required_outputs


def test_known_alias_and_entity_are_explicit_subjects() -> None:
    theme = understand_query("液冷题材连续上涨但成交占比下降，怎么看？")
    new_theme = understand_query("请研究空芯光纤题材的产业链")
    company = understand_query(
        "英维克怎么看",
        anchor=EntityAnchor(
            entity="英维克",
            ticker="002837.SZ",
            concepts=("液冷",),
        ),
    )

    assert (theme.subject_kind, theme.subject, theme.matched_by) == (
        "theme",
        "液冷",
        "alias",
    )
    assert (new_theme.subject_kind, new_theme.subject, new_theme.matched_by) == (
        "theme",
        "空芯光纤",
        "explicit",
    )
    assert (company.subject_kind, company.subject, company.matched_by) == (
        "company",
        "英维克",
        "entity",
    )


def test_compositional_theme_intent_preserves_horizon_and_required_outputs() -> None:
    envelope = understand_query(
        "研究信创未来3到6个月的中期赔率，"
        "用历史类似窗口和情景树说明升级、降级与证伪条件"
    )

    assert envelope.subject_kind == "theme"
    assert envelope.subject == "信创"
    assert envelope.question_type == "theme_analysis"
    assert envelope.research_mode == "theme_research"
    assert envelope.time_horizon == "3_to_6_months"
    assert envelope.operators == (
        "history_analog",
        "scenario_tree",
        "counterevidence",
    )
    assert envelope.required_outputs == (
        "historical_analogs",
        "scenario_tree",
        "falsification_conditions",
    )
    intent = build_turn_intent(
        "研究信创未来3到6个月的中期赔率，"
        "用历史类似窗口和情景树说明升级、降级与证伪条件",
        envelope,
    )
    assert intent.answer_owner == "theme-research"
    assert intent.time_horizon == "3_to_6_months"
    assert intent.required_outputs == envelope.required_outputs


def test_entity_anchor_still_precedes_compositional_theme_intent() -> None:
    envelope = understand_query(
        "研究英维克未来3到6个月的中期赔率，"
        "用历史类似窗口和情景树说明证伪条件",
        anchor=EntityAnchor(
            entity="英维克",
            ticker="002837.SZ",
            concepts=("液冷",),
        ),
    )

    assert envelope.subject_kind == "company"
    assert envelope.subject == "英维克"
    assert envelope.question_type == "stock_deep_dive"
    assert envelope.research_mode == "deep_dive"
    assert envelope.time_horizon == "3_to_6_months"
    assert envelope.operators == (
        "history_analog",
        "scenario_tree",
        "counterevidence",
    )


@pytest.mark.parametrize(
    ("query", "question_type", "subject"),
    (
        ("瑞华泰还有上涨空间吗？", "stock_deep_dive", "瑞华泰"),
        (
            "请个股深挖英维克的液冷业务，收入和利润都要覆盖",
            "stock_deep_dive",
            "英维克",
        ),
        ("分析英维克最新财报", "financial_analysis", "英维克"),
        ("英维克最新液冷公告有什么影响", "news_impact", "英维克"),
    ),
)
def test_explicit_company_cues_precede_theme_aliases(
    query: str,
    question_type: str,
    subject: str,
) -> None:
    envelope = understand_query(query)

    assert envelope.question_type == question_type
    assert envelope.subject_kind == "company"
    assert envelope.subject == subject
    assert envelope.matched_by == "explicit"


@pytest.mark.parametrize(
    ("query", "subject"),
    (
        ("贵州茅台估值怎么看", "贵州茅台"),
        ("帮我拍估值：寒武纪现在贵不贵", "寒武纪"),
    ),
)
def test_valuation_query_preserves_company_subject(
    query: str,
    subject: str,
) -> None:
    envelope = understand_query(query)

    assert envelope.question_type == "valuation_estimate"
    assert envelope.subject_kind == "company"
    assert envelope.subject == subject
    assert envelope.matched_by == "explicit"


def test_generic_or_theme_valuation_query_does_not_invent_company() -> None:
    generic = understand_query("某公司估值怎么看")
    theme = understand_query("液冷估值怎么看")

    assert generic.subject_kind == "unknown"
    assert generic.subject is None
    assert (theme.subject_kind, theme.subject) == ("theme", "液冷")


def test_empty_or_unknown_query_never_becomes_a_theme() -> None:
    assert understand_query("").subject is None
    assert understand_query("帮我看看这个").subject is None


@pytest.mark.parametrize(
    "query",
    (
        "昨天美股的涨跌情况",
        "昨日道指、纳指、标普涨跌",
    ),
)
def test_external_market_queries_have_dedicated_intent(query: str) -> None:
    envelope = understand_query(query)

    assert envelope.question_type == "external_market"
    assert envelope.subject_kind == "external_market"
    assert envelope.subject == "美国股市"
    assert envelope.matched_by == "market_anchor"
    assert envelope.confidence == 0.98


@pytest.mark.parametrize(
    "query",
    (
        # 2026-08-26 blk-d17 实测原话：被外盘报价车道接走后只回了美股指数
        "隔夜美股AI算力板块走强，对A股哪些板块有映射",
        "昨晚纳指涨了，对标A股哪些板块",
    ),
)
def test_overnight_mapping_questions_do_not_enter_external_quote_lane(query: str) -> None:
    """混合题的交付物是 A 股映射（D17 块在研究通道），不是海外收盘价。

    映射意图以 overnight_map.parse_overnight_intent 为单一真本源；
    这里同时钉住「D17 意图命中」与「外盘报价题型未命中」两侧，
    防止任何一侧词表漂移后重新遮蔽。
    """
    from intelligence.services.overnight_map import parse_overnight_intent

    assert parse_overnight_intent(query), "前提：D17 自己的意图必须命中"
    envelope = understand_query(query)
    assert envelope.question_type != "external_market"


def test_definition_query_is_not_confused_with_model_meta_question() -> None:
    definition = understand_query("卫星互联网是什么")
    meta = understand_query("你好，你是什么模型")

    assert definition.question_type == "concept_definition"
    assert definition.subject == "卫星互联网"
    assert definition.matched_by == "definition"
    assert meta.question_type == "general_finance_qa"
    assert meta.subject is None


@pytest.mark.parametrize(
    "query",
    (
        "编排层为什么会导致模板化？",
        "RAG 怎么做才能兼顾召回率和准确率？",
        "Agent 工具调用与 verifier 应该如何分层？",
    ),
)
def test_methodology_question_is_not_mapped_to_financial_retrieval(query: str) -> None:
    envelope = understand_query(query)

    assert envelope.question_type == "methodology_discussion"
    assert envelope.subject_kind == "unknown"
    assert envelope.subject is None
    assert envelope.research_mode == "methodology"


def test_financial_cause_is_not_overmatched_as_methodology() -> None:
    envelope = understand_query("这一周市场下跌为什么")

    assert envelope.question_type == "market_cause"


def test_company_customer_confirmation_is_fact_check() -> None:
    envelope = understand_query(
        "中际旭创和英伟达是否已确认合作？",
        anchor=EntityAnchor(entity="中际旭创", matched_by="name"),
    )

    assert envelope.question_type == "fact_check"
    assert envelope.subject == "中际旭创"
    assert envelope.operators == ("relation",)
    assert "官方证据" in envelope.decision_goal


def test_ticker_timeframe_and_serialization_contract() -> None:
    for ticker in ("002837", "600000.SH", "002837.SZ", "430047.BJ"):
        envelope = understand_query(f"分析 2026-07-13 的 {ticker}")

        assert envelope.subject_kind == "company"
        assert envelope.subject == ticker
        assert envelope.matched_by == "ticker"
        assert envelope.timeframe == "2026-07-13"
        assert envelope.to_dict()["subject"] == ticker


def test_deterministic_precedence_prefers_anchor_then_candidate() -> None:
    anchor = EntityAnchor(entity="英维克", matched_by="name")

    anchored = understand_query("液冷题材", matched_theme="空芯光纤", anchor=anchor)
    candidate = understand_query("液冷题材", matched_theme="空芯光纤")

    assert (anchored.subject, anchored.matched_by) == ("英维克", "entity")
    assert (candidate.subject, candidate.matched_by) == ("空芯光纤", "candidate")


def test_market_pattern_requires_two_terms_and_explains_divergence() -> None:
    one_term = understand_query("市场出现背离，怎么看？")
    two_terms = understand_query("指数上涨但涨停家数减少，是否背离？")

    assert one_term.subject_kind == "unknown"
    assert two_terms.subject_kind == "market_pattern"
    assert two_terms.decision_goal == "解释市场背离"


def test_market_outlook_is_not_generic_unknown() -> None:
    envelope = understand_query(
        "我希望你基于目前的市场数据，展望一下后面市场会怎么演绎"
    )

    assert envelope.question_type == "market_forecast"
    assert envelope.matched_by == "market_anchor"
    assert envelope.confidence >= 0.9


def test_next_day_rebound_or_decline_is_market_forecast() -> None:
    envelope = understand_query("明天你觉得是反弹还是继续下跌，分别给出理由")

    assert envelope.question_type == "market_forecast"
    assert envelope.matched_by == "market_anchor"


def test_ticker_and_date_match_next_to_chinese_text() -> None:
    bare_ticker = understand_query("分析002837怎么看")
    suffixed_ticker = understand_query("600000.SH怎么看")
    dated_theme = understand_query("分析2026年7月13日的液冷题材")

    assert (bare_ticker.subject_kind, bare_ticker.subject, bare_ticker.matched_by) == (
        "company",
        "002837",
        "ticker",
    )
    assert suffixed_ticker.subject == "600000.SH"
    assert dated_theme.timeframe == "2026年7月13日"


def test_ticker_and_explicit_theme_precede_market_pattern() -> None:
    ticker = understand_query("分析002837的液冷业务", matched_theme="液冷")
    explicit = understand_query("研究空芯光纤题材连续上涨、成交占比下降")

    assert (ticker.subject_kind, ticker.subject, ticker.matched_by) == (
        "company",
        "002837",
        "ticker",
    )
    assert (explicit.subject_kind, explicit.subject, explicit.matched_by) == (
        "theme",
        "空芯光纤",
        "explicit",
    )


def test_explicit_theme_cleans_prompt_date_and_generic_references() -> None:
    prompted = understand_query("研究一下空芯光纤题材")
    dated = understand_query("分析2026年空芯光纤产业链")

    assert (prompted.subject, prompted.matched_by) == ("空芯光纤", "explicit")
    assert (dated.subject, dated.matched_by, dated.timeframe) == (
        "空芯光纤",
        "explicit",
        "2026年",
    )
    for query in ("帮我看看这个板块", "深挖某个方向"):
        envelope = understand_query(query)
        assert envelope.subject_kind == "unknown"
        assert envelope.subject is None


def test_explicit_theme_strips_as_of_date_prefix() -> None:
    envelope = understand_query("分析截至2026年7月13日的空芯光纤产业链")

    assert (envelope.subject_kind, envelope.subject, envelope.matched_by) == (
        "theme",
        "空芯光纤",
        "explicit",
    )
    assert envelope.timeframe == "2026年7月13日"


def test_explicit_theme_strips_prompt_and_spaced_a_share_prefix() -> None:
    envelope = understand_query("请分析一下 A股空芯光纤题材")

    assert (envelope.subject_kind, envelope.subject, envelope.matched_by) == (
        "theme",
        "空芯光纤",
        "explicit",
    )


def test_explicit_theme_strips_a_share_prefix_without_space() -> None:
    envelope = understand_query("深挖A股空芯光纤方向")

    assert (envelope.subject, envelope.matched_by) == ("空芯光纤", "explicit")


def test_explicit_theme_prefers_longest_prompt_filler() -> None:
    envelope = understand_query("帮我分析一下子空芯光纤题材")

    assert (envelope.subject, envelope.matched_by) == ("空芯光纤", "explicit")


def test_explicit_theme_strips_repeated_intent_prefixes() -> None:
    envelope = understand_query("请分析一下 我想了解空芯光纤题材")

    assert (envelope.subject_kind, envelope.subject, envelope.matched_by) == (
        "theme",
        "空芯光纤",
        "explicit",
    )


def test_explicit_theme_strips_question_prefix() -> None:
    envelope = understand_query("分析一下 什么是空芯光纤题材")

    assert (envelope.subject_kind, envelope.subject, envelope.matched_by) == (
        "theme",
        "空芯光纤",
        "explicit",
    )


def test_explicit_market_question_never_invents_generic_subject() -> None:
    envelope = understand_query("研究为什么一个板块连续上涨、成交占比下降")

    assert envelope.subject_kind == "market_pattern"
    assert envelope.subject is None


def test_explicit_theme_uses_rightmost_valid_cue() -> None:
    for query in (
        "根据研究报告分析空芯光纤题材",
        "用技术分析看看空芯光纤题材",
        "请基于卖方研究分析空芯光纤题材",
    ):
        envelope = understand_query(query)
        assert (envelope.subject_kind, envelope.subject, envelope.matched_by) == (
            "theme",
            "空芯光纤",
            "explicit",
        )


def test_failed_explicit_cue_falls_through_to_market_pattern() -> None:
    envelope = understand_query(
        "从技术分析角度看，指数上涨但涨停家数减少，是否背离？"
    )

    assert envelope.subject_kind == "market_pattern"
    assert envelope.subject is None
    assert envelope.matched_by == "generic"


def test_theme_alias_config_rejects_malformed_collection_types(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    malformed_docs = (
        [],
        {"packs": None},
        {"packs": [None]},
        {"packs": [{"aliases": None}]},
        {"packs": [{"aliases": "液冷"}]},
    )

    try:
        for index, doc in enumerate(malformed_docs):
            config_path = tmp_path / f"malformed-{index}.json"
            config_path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
            monkeypatch.setattr(query_understanding, "THEME_CONFIG_PATH", config_path)
            query_understanding._theme_aliases.cache_clear()

            assert query_understanding._theme_aliases() == ()
    finally:
        query_understanding._theme_aliases.cache_clear()


def test_news_event_impact_routes_to_news_impact_owner_chain() -> None:
    envelope = understand_query("英伟达新一代GPU发布对光模块板块的影响是什么")

    assert envelope.question_type == "news_impact"
    assert envelope.subject == "光模块"
    assert envelope.subject_kind == "theme"
    assert envelope.research_mode == "news_impact"


def test_related_news_topic_precedes_impact_object() -> None:
    envelope = understand_query(
        "请分析近期光模块相关消息对产业链和核心公司的影响，"
        "区分已证实事实、推断、受益与受损方向，并给反证。"
    )

    assert envelope.question_type == "news_impact"
    assert envelope.subject == "光模块"
    assert envelope.subject_kind == "theme"


def test_news_event_impact_variants_and_negatives() -> None:
    tariff = understand_query("美国加征关税对A股的影响")
    assert tariff.question_type == "news_impact"
    assert tariff.subject == "A股"

    definition = understand_query("光模块是什么")
    assert definition.question_type == "concept_definition"

    anchored = understand_query(
        "英伟达发布新GPU对中际旭创的影响",
        anchor=EntityAnchor(
            entity="中际旭创",
            ticker="300308.SZ",
            matched_by="name",
            concepts=(),
        ),
    )
    assert anchored.question_type == "news_impact"
    assert anchored.subject_kind == "company"
    assert anchored.subject == "中际旭创"


def test_market_watch_query_is_deterministically_recognized() -> None:
    assert query_understanding.is_market_watch_query("今天有什么值得关注的")
    assert query_understanding.is_market_watch_query("今日盘面有哪些看点")
    assert query_understanding.is_market_watch_query("今天市场怎么样")
    assert query_understanding.is_market_watch_query(
        "请做今日市场复盘：市场阶段、主线、赚钱效应和风险"
    )
    assert not query_understanding.is_market_watch_query("光模块怎么看")
    assert not query_understanding.is_market_watch_query(
        "今天光模块有什么值得关注的"
    )
    assert not query_understanding.is_market_watch_query("今日光模块复盘")
    assert not query_understanding.is_market_watch_query("明天有什么值得关注的")


def test_market_review_requested_date_resolves_full_dates() -> None:
    from datetime import date

    assert query_understanding.market_review_requested_date(
        "总结一下 2026-07-16 的行情",
        today=date(2026, 7, 16),
    ) == "2026-07-16"
    assert query_understanding.market_review_requested_date(
        "复盘 2026年7月16日 的A股市场",
        today=date(2026, 7, 16),
    ) == "2026-07-16"
    assert query_understanding.market_review_requested_date(
        "总结 2026-02-30 的行情",
        today=date(2026, 7, 16),
    ) is None


def test_market_review_requested_date_normalizes_yearless_dates() -> None:
    from datetime import date

    assert query_understanding.market_review_requested_date(
        "总结一下7.16的行情",
        today=date(2026, 7, 16),
    ) == "2026-07-16"
    assert query_understanding.market_review_requested_date(
        "复盘7月16日的盘面",
        today=date(2026, 7, 16),
    ) == "2026-07-16"
    assert query_understanding.market_review_requested_date(
        "总结一下12.24的行情",
        today=date(2026, 7, 16),
    ) == "2025-12-24"
    assert query_understanding.market_review_requested_date(
        "总结一下最近3.5个月的行情",
        today=date(2026, 7, 16),
    ) is None
    assert query_understanding.market_review_requested_date(
        "总结一下涨幅7.16%的板块",
        today=date(2026, 7, 16),
    ) is None
    assert query_understanding.market_review_requested_date(
        "总结一下13.40的行情",
        today=date(2026, 7, 16),
    ) is None


def test_yearless_dated_market_review_is_recognized() -> None:
    envelope = understand_query("总结一下7.16的行情")

    assert query_understanding.is_dated_market_review(
        "总结一下7.16的行情",
        envelope,
    )
    assert query_understanding.is_dated_market_review(
        "复盘7月16日的A股行情",
        understand_query("复盘7月16日的A股行情"),
    )
    assert not query_understanding.is_dated_market_review(
        "总结一下7.16的美股行情",
        understand_query("总结一下7.16的美股行情"),
    )


def test_dated_market_analysis_phrasings_are_recognized() -> None:
    for query in (
        "7.16的行情你分析一下",
        "分析一下7.16的行情",
        "帮我分析下7月16日行情",
    ):
        assert query_understanding.is_dated_market_review(
            query,
            understand_query(query),
        ), query


def test_function_words_are_not_company_subjects() -> None:
    envelope = understand_query("7.16的行情你分析一下")

    assert envelope.subject != "一下"
    assert envelope.question_type != "stock_deep_dive"


def test_index_rebound_space_is_a_structured_technical_question() -> None:
    envelope = understand_query("科创50你认为反弹空间有多少")

    assert envelope.question_type == "market_technical"
    assert envelope.subject_kind == "index"
    assert envelope.subject == "科创50"


def test_anchored_company_reasonable_valuation_keeps_valuation_semantics() -> None:
    envelope = understand_query(
        "瑞华泰的合理估值",
        anchor=EntityAnchor(
            entity="瑞华泰",
            ticker="688323.SH",
            matched_by="name",
        ),
    )

    assert envelope.question_type == "valuation_estimate"
    assert envelope.subject_kind == "company"
    assert envelope.subject == "瑞华泰"


def test_current_market_mainline_is_not_a_static_definition() -> None:
    envelope = understand_query("目前市场的主线是什么")

    assert envelope.question_type == "market_watch"
    assert envelope.subject_kind == "market_pattern"


def test_market_watch_recall_widening_covers_workorder_variants() -> None:
    """工单 2026-08-27-market-watch-recall-workorder：表内 5 变体全召回。

    前两条是既有行为锚；后三条是本单放宽（插词 / 语序反 / 本周入时间词表）。
    """

    assert query_understanding.is_market_watch_query("目前市场的主线是什么")
    assert query_understanding.is_market_watch_query("现在市场的主线方向有哪些")
    assert query_understanding.is_market_watch_query("当前A股最强的主线是哪条")
    # 空格排版变体由 is_market_watch_query 的空白归一化吃掉
    assert query_understanding.is_market_watch_query("当前 A 股最强的主线是哪条")
    assert query_understanding.is_market_watch_query("市场资金现在在围绕什么主线交易")
    assert query_understanding.is_market_watch_query("本周市场主线有没有发生切换")


def test_market_watch_recall_widening_does_not_swallow_theme_questions() -> None:
    """防吞题材回归——identifier 注释里的两条历史伤疤 + 新分支的边界。

    放宽召回的每一步都必须保住：题材问句不得被送去跑全市场日报。
    """

    assert not query_understanding.is_market_watch_query("固态电池市场处于什么阶段")
    assert not query_understanding.is_market_watch_query("固态电池现在处于什么阶段")
    assert not query_understanding.is_market_watch_query("固态电池当前主线逻辑是什么")
    # 新增「市场资金…主线」分支锚在分句首：题材名开头的问句不得命中
    assert not query_understanding.is_market_watch_query("液冷市场资金在追什么主线")
    # 「本周」进时间词表后，后面必须紧跟市场名词才算盘面题
    assert not query_understanding.is_market_watch_query("本周固态电池主线有没有切换")


def test_recalled_mainline_variants_route_to_market_watch_envelope() -> None:
    for question in (
        "当前A股最强的主线是哪条",
        "市场资金现在在围绕什么主线交易",
        "本周市场主线有没有发生切换",
    ):
        envelope = understand_query(question)
        assert envelope.question_type == "market_watch", question


# --- 带日期的盘面细分题必须进 daily-review（2026-08-01 A 组基线根因）-----------
#
# A 组 10 道验收题首跑 0/10，7 道没产出可用答案。根因是 _DATED_MARKET_REVIEW_RE
# 要求「日期 + 市场/盘面 + 总结/复盘/回顾/梳理/分析」——对 10 道真实问题 0 命中。
# 而 market_review_requested_date 对其中 8 道**已经正确解析出日期**，只是这个
# 结果被 and 到那条 0 命中的正则上，白解析了。
# 实测后果：A4 用「特斯拉 Optimus 人形机器人」答双红，A9 用外汇/期货/债券新闻答
# 市场情绪，A6 谎称「2026-07-23 是未来的时间」——而 2026-07-23-daily-review.md
# 就在磁盘上，里面有专章「## 5. 双红题材」「## 2. 市场情绪」和 4 次「立新能源」。


def test_dated_board_subtopics_route_to_daily_review() -> None:
    """线上验收题的真实措辞。修复前这 6 条全是 False。"""
    for query in (
        "2026-07-23 哪些板块是双红",
        "2026-07-23 涨停集中在哪些题材",
        "2026-07-23 连板梯队什么情况，有没有断层",
        "2026-07-21 当天主线是什么",
        "2026-07-23 的市场情绪怎么解读",
        "2026-07-21 的新高家数结构说明什么",
    ):
        assert query_understanding.is_dated_market_review(
            query,
            understand_query(query),
        ), f"带日期的盘面细分题没进 daily-review：{query}"


def test_board_subtopic_without_date_is_not_routed() -> None:
    """没有日期就没有可读的复盘导出——不能因为出现「涨停」就硬路由。"""
    for query in ("涨停集中在哪些题材", "哪些板块是双红"):
        assert not query_understanding.is_dated_market_review(
            query,
            understand_query(query),
        ), query


def test_dated_theme_research_is_not_hijacked_by_daily_review() -> None:
    """题材研究题带日期也不该被盘面复盘抢走——它问的是产业链不是当日盘面。"""
    query = "2026-07-23 固态电池产业链走到哪一步了"
    assert not query_understanding.is_dated_market_review(
        query,
        understand_query(query),
    )


def test_dated_overseas_board_subtopic_still_excluded() -> None:
    """external_market 的排除不能被新增的主题词绕过。"""
    query = "2026-07-23 美股涨停情况怎么样"
    assert not query_understanding.is_dated_market_review(
        query,
        understand_query(query),
    )


# --- 「比较」是程度副词时不能算 comparison（run_20260805_194911_490256 根因）------
#
# _COMPARISON_RE 原来裸匹配「比较|对比|相比」。但「比较」在中文里同时是程度副词
# （「比较有机会」＝「相当有机会」），「相比」还常只带时间参照（「相比之前」）。
# 裸词命中把程度副词读成了动词，question_type 被置成 comparison，契约随即要求
# 四个没有工具能满足的输出（拿不到 B 就填不了对比矩阵），门只能如实拒答——
# 表面症状是「证据不足」，真因在这一行正则。
# 实测：普通选股题修复前 7 条 degrades + 拒答模板，修复后 0 条 degrades。


def test_degree_adverb_bijiao_is_not_a_comparison() -> None:
    """程度副词用法：问的是「哪个更好」而不是「A 和 B 差在哪」，没有可比对象。"""
    for query in (
        "哪只个股比较有机会",
        "哪个方向比较强",
        "现在比较看好什么",
        "这个位置比较危险吗",
        "最近相比之前怎么样",
        "我比较关注半导体",
        "分析当前行情",
    ):
        envelope = understand_query(query)
        assert "comparison" not in envelope.operators, query
        assert envelope.question_type != "comparison", query


def test_real_comparison_questions_still_match() -> None:
    """真给出了两个可比对象或显式比较落点的，仍然要走 comparison。"""
    for query in (
        "比较一下瑞华泰和中际旭创",
        "光模块和PCB哪个更强",
        "CPO与液冷的差异在哪",
    ):
        envelope = understand_query(query)
        assert "comparison" in envelope.operators, query


def test_dated_stock_picking_question_is_not_comparison() -> None:
    """线上原题（run_20260805_194911_490256）：修复前 question_type=comparison。"""
    query = (
        "以 2026-08-04 收盘数据为准，分析当前行情，"
        "你认为哪个方向、哪只个股比较有机会？"
    )
    envelope = understand_query(query)

    assert "comparison" not in envelope.operators
    assert envelope.question_type != "comparison"


# --- 2026-08-20 market_cause 板块归因入口（路由稿 §5 / §7） ---

_ALUMINUM_CAUSE = "2026-07-23 A股铝板块为什么涨，给出证据来源"
_GRID_CAUSE = "2026-07-23 电网设备为什么涨，给出证据来源"


def test_weekly_market_cause_word_order_variants() -> None:
    """F1：归因在涨跌之前也必须命中。现役有序正则会把这三句判否。"""

    for query in (
        "大盘为什么下跌",
        "行情为什么走弱",
        "近一周大盘为什么走弱",
    ):
        envelope = understand_query(query)
        assert envelope.question_type == "market_cause", query
        assert envelope.subject is None, query
        assert envelope.matched_by == "market_anchor", query


def test_aluminum_sector_cause_envelope_is_market_cause() -> None:
    envelope = understand_query(_ALUMINUM_CAUSE)

    assert envelope.question_type == "market_cause"
    assert envelope.subject == "铝"
    assert envelope.subject_kind == "theme"
    assert envelope.matched_by == "explicit"
    assert envelope.task_frame is not None
    assert "causal_chain" in envelope.task_frame.required_outputs
    assert envelope.task_frame.subject == "铝"


def test_grid_equipment_cause_envelope_without_matched_theme_may_miss() -> None:
    """F2/F3：信封层不带参允许不命中；禁止把电网设备写进题材包别名。"""

    envelope = understand_query(_GRID_CAUSE)

    assert envelope.question_type != "market_cause"
    assert "电网设备" not in query_understanding._theme_aliases()


def test_grid_equipment_cause_envelope_with_matched_theme() -> None:
    envelope = understand_query(_GRID_CAUSE, matched_theme="电网设备")

    assert envelope.question_type == "market_cause"
    assert envelope.subject == "电网设备"
    assert envelope.matched_by == "candidate"
    assert envelope.task_frame is not None
    assert "causal_chain" in envelope.task_frame.required_outputs


def test_liquid_cooling_sector_cause_envelope_uses_alias() -> None:
    envelope = understand_query("液冷板块今天为什么涨")

    assert envelope.question_type == "market_cause"
    assert envelope.subject == "液冷"
    assert envelope.matched_by == "alias"


def test_market_cause_does_not_steal_non_move_or_stock_queries() -> None:
    """§5.2：两层都不得是 market_cause。信封层只锁「不是因果」。"""

    cases = (
        "固态电池为什么是主线",
        "立新能源为什么涨",
        "液冷怎么看",
        "电网设备怎么看",
        "液冷服务器题材：产业链怎么拆解",
        "2026-02-17 涨停家数多少",
        "什么是双红，现在哪些板块双红",
        "2026-07-23 铝为什么涨，给出证据来源",
        "2026-07-23 收盘，盛新锂能怎么看",
    )
    for query in cases:
        envelope = understand_query(query)
        assert envelope.question_type != "market_cause", query

    assert understand_query("液冷怎么看").question_type == "theme_analysis"
    assert (
        understand_query("电网设备怎么看", matched_theme="电网设备").question_type
        == "theme_analysis"
    )


MONDAY_TECH_MED_QUERY = (
    "站在spt视角下，你认为周一科技和医药板块的走势会怎么样，需要观察哪些个股的反馈"
)
YSJS_XIA_QUERY = (
    "用spt的视角，分析下有色金属板块后续的走势，以及板块内有机会的个股有哪些"
)


def test_monday_tech_med_honors_dual_subject_and_stock_slot() -> None:
    """P0-C §5.1：问句已点名科技+医药和观察个股，信封必须认领。"""

    envelope = understand_query(MONDAY_TECH_MED_QUERY)
    subject = envelope.subject or ""
    compact = subject.replace(" ", "")

    assert "scenario_tree" in envelope.operators
    assert "company_mapping" in envelope.operators
    assert "company_mapping" in envelope.required_outputs
    assert "科技" in compact
    assert "医药" in compact
    assert envelope.question_type == "general_finance_qa"


def test_ysjs_spoken_xia_is_not_part_of_subject() -> None:
    """P0-C §5.2：分析下有色金属 → 有色金属，不得吃成「下有色金属」。"""

    envelope = understand_query(YSJS_XIA_QUERY)

    assert envelope.subject == "有色金属"
    assert envelope.subject_kind == "theme"
    assert not str(envelope.subject).startswith("下")
    assert "company_mapping" in envelope.operators
    assert "company_mapping" in envelope.required_outputs


def test_downstream_chemicals_keeps_xia_compound() -> None:
    """剥「下」的真实坏结果是「游化工」，不是「下游」。"""

    envelope = understand_query("分析下游化工板块的机会")

    assert envelope.subject == "下游化工"
    assert envelope.subject != "游化工"


def test_board_mention_without_forecast_and_names_does_not_invent_subject() -> None:
    """无 cue、单算子的「X板块」不得开始产出 subject（§6.3 先窄后宽）。"""

    envelope = understand_query("复盘今天的科技板块")

    assert envelope.subject != "科技"


FORWARD_OPINION_JOINT_QUERY = (
    "站在spt视角下，科技和医药板块接下来的走势怎么看，需要观察哪些个股的反馈"
)


def test_forward_opinion_joint_board_fills_subject() -> None:
    """R-20260825-07 §7#1：「怎么看」词形的联合板块题不得落 0.4 兜底。

    同句换「会怎么样」已能抽到主语（scenario_tree 门），词形不该是分水岭。
    """

    envelope = understand_query(FORWARD_OPINION_JOINT_QUERY)
    compact = (envelope.subject or "").replace(" ", "")

    assert "科技" in compact
    assert "医药" in compact
    assert envelope.subject_kind == "theme"
    # P0 只填主语不动题型；升 theme_analysis 另立（spec §1.2）。
    assert envelope.question_type == "general_finance_qa"


def test_forward_opinion_single_board_fills_subject() -> None:
    """R-20260825-07 §7#2/#3：单题材 × 前瞻观点词形，主语必须落格。"""

    assert understand_query("医药板块接下来的走势怎么看").subject == "医药"
    assert understand_query("科技板块后续怎么走").subject == "科技"
    assert understand_query("接下来医药板块怎么看").subject == "医药"
    assert understand_query("下游化工板块接下来怎么看").subject == "下游化工"


def test_forward_opinion_does_not_steal_cue_or_market_level() -> None:
    """R-20260825-07 §7#4/#5/#6：cue 路与市场级判定原样。"""

    ysjs = understand_query(YSJS_XIA_QUERY)
    assert ysjs.question_type == "theme_analysis"
    assert ysjs.subject == "有色金属"

    assert understand_query("接下来大盘怎么走").subject_kind != "theme"
    assert understand_query("今天市场怎么样").subject_kind != "theme"
    # 变异锁（spec §7）：本句真命中 _MARKET_FORECAST_RE（展望…后市）。
    # 新路若被挪到 forecast 判定之前，「科技板块」会把主语抢走——必红。
    mixed = understand_query("展望后市，科技板块接下来的走势怎么看")
    assert mixed.question_type == "market_forecast"
    assert mixed.subject_kind != "theme"


def test_forward_opinion_requires_board_suffix() -> None:
    """R-20260825-07 §7#7：无「板块/题材」后缀不得发明主语。"""

    envelope = understand_query("下游产业链接下来怎么看")

    assert envelope.subject is None


# --- 输入理解层（2026-09-09，05 单）：真实问法的路由 -------------------------------

from datetime import date as _date  # noqa: E402

_REPORT_TEXT = (
    "【卖方摘要｜2026-08-28】固态电池：硫化物路线进入中试放量期\n\n"
    "一、核心观点\n公司 A 硫化物电解质中试线 2026 年 8 月投产，规划产能 200 吨/年。\n\n"
    "二、关键数据\n2026 年上半年新签订单 12 亿元，同比增长 40%；毛利率 31.5%。"
)


def test_yearless_dated_review_gets_iso_timeframe() -> None:
    # 真实流量（2026-08，linxiaoqi5111）：「8.18的复盘数据你怎么解读」此前落通用检索、timeframe None。
    envelope = understand_query("8.18的复盘数据你怎么解读")

    assert envelope.question_type == "dated_market_review"
    assert envelope.timeframe is not None and envelope.timeframe.endswith("-08-18")
    assert int(envelope.timeframe[:4]) <= _date.today().year
    assert envelope.task_frame is not None
    assert envelope.task_frame.timeframe == envelope.timeframe


def test_yearless_follow_up_carries_its_own_date() -> None:
    envelope = understand_query("那8.19呢")
    assert envelope.timeframe is not None and envelope.timeframe.endswith("-08-19")


def test_quantity_before_a_dot_number_is_not_a_date() -> None:
    assert understand_query("涨幅8.5的板块有哪些").timeframe is None
    assert understand_query("跌了2.3个点").timeframe is None


def test_dated_single_metric_question_is_not_a_dated_review() -> None:
    # turn_controller 的守卫：「2026-08-14涨停家数多少」要的是一个数，不是一份复盘。
    envelope = understand_query("2026-08-14涨停家数多少")
    assert envelope.question_type != "dated_market_review"
    assert understand_query("2026-07-23 哪些板块是双红").question_type != "dated_market_review"


def test_wave_reference_names_the_theme() -> None:
    envelope = understand_query("这一波农业是怎么走出来的？请事后复盘，找出值得进一步检验的特征")

    assert envelope.question_type == "theme_analysis"
    assert envelope.subject == "农业"
    assert envelope.subject_kind == "theme"


def test_next_day_operation_question_is_market_forecast() -> None:
    envelope = understand_query("基于周五的行情，周一该怎么操作")

    assert envelope.question_type == "market_forecast"
    assert envelope.task_frame is not None
    assert envelope.task_frame.subject == "A股市场"


def test_pasted_material_does_not_hijack_routing() -> None:
    with_question = understand_query(f"{_REPORT_TEXT}\n\n这篇研报的核心逻辑站得住吗？帮我分开哪些是硬事实、哪些只是推测")
    assert with_question.question_type == "kol_review"
    assert with_question.task_frame is not None
    assert len(with_question.task_frame.materials) == 1

    material_only = understand_query(_REPORT_TEXT)
    assert material_only.question_type == "kol_review"
    assert material_only.task_frame is not None
    assert material_only.task_frame.materials[0].material_id == with_question.task_frame.materials[0].material_id

    # 同一段材料单独作为题材问题出现时，路由不受影响（对照）。
    assert understand_query("固态电池现在怎么看").question_type == "theme_analysis"


def test_company_nicknames_resolve_in_comparison_and_single_form() -> None:
    pair = understand_query("宁王和迪王现在谁的估值更贵")
    assert pair.question_type == "comparison"
    assert pair.subject == "宁德时代、比亚迪"
    assert pair.subject_kind == "company"

    single = understand_query("宁王现在贵不贵")
    assert single.question_type == "valuation_estimate"
    assert single.subject == "宁德时代"
    assert single.matched_by == "alias"
