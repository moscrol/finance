from __future__ import annotations

from intelligence.services.query_understanding import understand_query
from intelligence.services.theme_modules import (
    MODULE_BRIEF,
    MODULE_REPLAY,
    route_modules,
)
from intelligence.workbench_skills.contracts import SkillDefinition
from intelligence.workbench_skills.router import route_skills


def _skill(skill_id: str, trigger: str) -> SkillDefinition:
    return SkillDefinition(
        skill_id=skill_id,
        name=skill_id,
        description=skill_id,
        version="1.0.0",
        triggers=(trigger,),
        input_schema={"type": "object"},
        permissions=("local_read",),
        timeout_seconds=30,
    )


def test_external_market_never_auto_routes_theme_modules() -> None:
    assert route_modules(
        "昨天美股复盘及走势",
        question_type="external_market",
        subject_kind="external_market",
    ) == []


def test_unknown_query_has_no_default_theme_modules() -> None:
    assert route_modules(
        "帮我看看这个",
        question_type="general_finance_qa",
        subject_kind="unknown",
    ) == []


def test_explicit_theme_module_selection_is_preserved() -> None:
    assert route_modules(
        "昨天美股复盘",
        [MODULE_REPLAY, MODULE_BRIEF],
        question_type="external_market",
        subject_kind="external_market",
    ) == [MODULE_BRIEF, MODULE_REPLAY]


def test_external_market_disables_automatic_skill_selection() -> None:
    registry = {
        "daily-review": _skill("daily-review", "昨天"),
        "theme-research": _skill("theme-research", "走势"),
    }
    result = route_skills(
        "昨天美股的涨跌情况",
        "ask",
        "auto",
        (),
        registry=registry,
        llm_complete=lambda messages: (
            '{"skill_ids":["daily-review"],"reasons":{"daily-review":"fixture"}}',
            None,
            "",
        ),
        query_envelope=understand_query("昨天美股的涨跌情况"),
    )

    assert result.selections == ()
    assert result.base_finance_fallback is True


def test_manual_skill_selection_is_preserved_for_external_market() -> None:
    registry = {"daily-review": _skill("daily-review", "昨天")}
    result = route_skills(
        "昨天美股的涨跌情况",
        "ask",
        "manual",
        ("daily-review",),
        registry=registry,
        query_envelope=understand_query("昨天美股的涨跌情况"),
    )

    assert [selection.skill_id for selection in result.selections] == [
        "daily-review"
    ]
