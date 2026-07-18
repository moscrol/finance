from __future__ import annotations

from intelligence.services.research_contract import (
    QUESTION_OWNER_SKILLS,
    RESEARCH_OWNER_IDS,
)
from intelligence.services.route_table import (
    ROUTE_TABLE,
    render_route_table_prompt,
    route_by_id,
)


def test_route_ids_are_unique() -> None:
    route_ids = [row.route_id for row in ROUTE_TABLE]

    assert len(route_ids) == len(set(route_ids))


def test_every_row_has_description_and_examples() -> None:
    for row in ROUTE_TABLE:
        assert row.description.strip(), row.route_id
        assert row.examples, row.route_id


def test_owner_rows_are_research_lane_with_valid_owner() -> None:
    for row in ROUTE_TABLE:
        if row.answer_owner is not None:
            assert row.lane == "research", row.route_id
            assert row.answer_owner in RESEARCH_OWNER_IDS, row.route_id
            assert row.needs_retrieval is True, row.route_id


def test_question_owner_skills_derive_from_route_table() -> None:
    expected = {
        row.question_type: row.answer_owner
        for row in ROUTE_TABLE
        if row.question_type is not None and row.answer_owner is not None
    }

    assert QUESTION_OWNER_SKILLS == expected
    assert QUESTION_OWNER_SKILLS["stock_deep_dive"] == "stock-deep-dive"
    assert QUESTION_OWNER_SKILLS["valuation_estimate"] == "stock-deep-dive"
    assert QUESTION_OWNER_SKILLS["theme_analysis"] == "theme-research"
    assert QUESTION_OWNER_SKILLS["news_impact"] == "news-impact"
    assert QUESTION_OWNER_SKILLS["financial_analysis"] == "financial-analysis"


def test_route_by_id_returns_none_for_unknown_route() -> None:
    assert route_by_id("made_up_route") is None


def test_prompt_rendering_lists_every_route() -> None:
    prompt = render_route_table_prompt()

    for row in ROUTE_TABLE:
        assert row.route_id in prompt
        assert row.examples[0] in prompt
