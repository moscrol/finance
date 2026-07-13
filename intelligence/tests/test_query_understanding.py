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
