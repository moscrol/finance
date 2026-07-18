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


def test_definition_query_is_not_confused_with_model_meta_question() -> None:
    definition = understand_query("卫星互联网是什么")
    meta = understand_query("你好，你是什么模型")

    assert definition.question_type == "concept_definition"
    assert definition.subject == "卫星互联网"
    assert definition.matched_by == "definition"
    assert meta.question_type == "general_finance_qa"
    assert meta.subject is None


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
    assert not query_understanding.is_market_watch_query("光模块怎么看")
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
