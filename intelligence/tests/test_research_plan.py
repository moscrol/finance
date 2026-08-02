from __future__ import annotations

import json

import pytest

from intelligence.services.research_plan import (
    parse_research_plan,
    plan_to_public_dict,
    validate_plan_revision,
)


def _plan_json(**overrides: object) -> str:
    payload: dict[str, object] = {
        "kind": "PLAN",
        "task_summary": "判断市场主线并给出反方",
        "answer_elements": ["direct_assessment", "counterpoint"],
        "hypotheses": ["半导体可能是持续主线"],
        "evidence_needs": ["同日主线与持续性"],
        "candidate_actions": ["market_snapshot", "news_search"],
        "open_gaps": ["缺少反方证据"],
        "requested_mode": "quick",
        "revision": 1,
    }
    payload.update(overrides)
    return json.dumps(payload, ensure_ascii=False)


def test_parse_research_plan_returns_bounded_deduplicated_public_contract() -> None:
    plan = parse_research_plan(
        _plan_json(
            answer_elements=[
                " direct_assessment ",
                "counterpoint",
                "direct_assessment",
            ],
            candidate_actions=["market_snapshot", "news_search", "news_search"],
        )
    )

    assert plan.answer_elements == ("direct_assessment", "counterpoint")
    assert plan.candidate_actions == ("market_snapshot", "news_search")
    assert plan.open_gaps == ("缺少反方证据",)
    assert plan.branch_goals == ()
    assert plan.requested_mode == "quick"
    assert plan_to_public_dict(plan) == {
        "task_summary": "判断市场主线并给出反方",
        "answer_elements": ["direct_assessment", "counterpoint"],
        "hypotheses": ["半导体可能是持续主线"],
        "evidence_needs": ["同日主线与持续性"],
        "candidate_actions": ["market_snapshot", "news_search"],
        "open_gaps": ["缺少反方证据"],
        "requested_mode": "quick",
        "revision": 1,
        "branch_goals": [],
    }


def test_research_plan_accepts_at_most_three_explicit_branch_goals() -> None:
    plan = parse_research_plan(
        _plan_json(
            requested_mode="deep",
            branch_goals=["核验公司兑现", "查找反方驱动"],
        )
    )

    assert plan.branch_goals == ("核验公司兑现", "查找反方驱动")
    assert plan_to_public_dict(plan)["branch_goals"] == [
        "核验公司兑现",
        "查找反方驱动",
    ]


@pytest.mark.parametrize(
    "branch_goals",
    [
        ["分支一", "分支二", "分支三", "分支四"],
        ["重复分支", "重复分支"],
        [""],
    ],
)
def test_research_plan_rejects_invalid_branch_goals(
    branch_goals: list[str],
) -> None:
    with pytest.raises(ValueError, match="branch_goals"):
        parse_research_plan(_plan_json(branch_goals=branch_goals))


@pytest.mark.parametrize(
    "overrides, match",
    [
        ({"tool": "market_snapshot"}, "unknown plan fields"),
        ({"budget": 8}, "unknown plan fields"),
        ({"evidence_hashes": ["made-up"]}, "unknown plan fields"),
        ({"status": "completed"}, "unknown plan fields"),
        ({"answer_elements": []}, "answer_elements"),
        ({"answer_elements": [str(index) for index in range(9)]}, "answer_elements"),
        ({"hypotheses": [str(index) for index in range(5)]}, "hypotheses"),
        ({"evidence_needs": [str(index) for index in range(9)]}, "evidence_needs"),
        ({"candidate_actions": [str(index) for index in range(9)]}, "candidate_actions"),
        ({"open_gaps": [str(index) for index in range(9)]}, "open_gaps"),
        ({"requested_mode": "auto"}, "requested_mode"),
        ({"kind": "plan"}, "kind"),
        ({"revision": 0}, "revision"),
    ],
)
def test_parse_research_plan_rejects_malformed_or_authoritative_fields(
    overrides: dict[str, object],
    match: str,
) -> None:
    with pytest.raises(ValueError, match=match):
        parse_research_plan(_plan_json(**overrides))


def test_plan_revision_must_increase_and_preserve_task_identity() -> None:
    first = parse_research_plan(_plan_json(revision=1))
    second = parse_research_plan(_plan_json(revision=2))

    validate_plan_revision(
        first,
        second,
        original_task_id="task-1",
        current_task_id="task-1",
    )
    with pytest.raises(ValueError, match="revision"):
        validate_plan_revision(
            second,
            first,
            original_task_id="task-1",
            current_task_id="task-1",
        )
    with pytest.raises(ValueError, match="task identity"):
        validate_plan_revision(
            first,
            second,
            original_task_id="task-1",
            current_task_id="task-2",
        )


def test_plan_revision_can_add_but_cannot_remove_answer_elements() -> None:
    first = parse_research_plan(
        _plan_json(answer_elements=["direct_assessment"], revision=1)
    )
    expanded = parse_research_plan(
        _plan_json(
            answer_elements=["direct_assessment", "counterpoint"],
            revision=2,
        )
    )
    shrunk = parse_research_plan(
        _plan_json(answer_elements=["counterpoint"], revision=3)
    )

    validate_plan_revision(
        first,
        expanded,
        original_task_id="task-1",
        current_task_id="task-1",
    )
    with pytest.raises(ValueError, match="remove answer elements"):
        validate_plan_revision(
            expanded,
            shrunk,
            original_task_id="task-1",
            current_task_id="task-1",
        )


def test_plan_revision_cannot_remove_an_already_published_branch_goal() -> None:
    first = parse_research_plan(
        _plan_json(branch_goals=["核验公司兑现"], revision=1)
    )
    expanded = parse_research_plan(
        _plan_json(
            branch_goals=["核验公司兑现", "查找反方驱动"],
            revision=2,
        )
    )
    removed = parse_research_plan(
        _plan_json(branch_goals=["查找反方驱动"], revision=3)
    )

    validate_plan_revision(
        first,
        expanded,
        original_task_id="task-1",
        current_task_id="task-1",
    )
    with pytest.raises(ValueError, match="remove branch goals"):
        validate_plan_revision(
            expanded,
            removed,
            original_task_id="task-1",
            current_task_id="task-1",
        )
