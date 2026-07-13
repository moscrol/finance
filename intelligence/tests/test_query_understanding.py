import json
from pathlib import Path

import pytest

from intelligence.services import query_understanding
from intelligence.services.entity_anchor import EntityAnchor
from intelligence.services.query_understanding import understand_query


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


def test_empty_or_unknown_query_never_becomes_a_theme() -> None:
    assert understand_query("").subject is None
    assert understand_query("帮我看看这个").subject is None


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

    assert envelope.subject_kind == "unknown"
    assert envelope.subject is None


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
