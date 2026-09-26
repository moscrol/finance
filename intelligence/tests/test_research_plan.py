from __future__ import annotations

import json
from pathlib import Path

import pytest

from intelligence.services.research_plan import (
    parse_plan_candidate,
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


@pytest.mark.parametrize("language", ["json", "JSON", ""])
def test_plan_accepts_one_complete_json_code_fence(language: str) -> None:
    raw = _plan_json()
    fenced = f"```{language}\n{raw}\n```"
    expected = parse_research_plan(raw)
    assert parse_research_plan(fenced) == expected
    assert parse_plan_candidate(fenced).plan == expected


@pytest.mark.parametrize("wrap", [
    "Explanation\\n```json\\n%s\\n```",
    "```json\\n%s\\n```\\n```json\\n{}\\n```",
    "```json\\n%s\\n",
    "```python\\n%s\\n```",
    "%s\\n{}",
    "%s\\ntrue",
    "%s\\n2",
    "%s\\n\"second\"",
])
def test_plan_fence_support_does_not_extract_embedded_objects(wrap: str) -> None:
    raw = (wrap % _plan_json()).replace("\\n", "\n")
    result = parse_plan_candidate(raw)
    assert result.plan is None and result.error
    with pytest.raises(ValueError):
        parse_research_plan(raw)


@pytest.mark.parametrize("fenced", [False, True])
def test_plan_allows_plain_suffix_without_changing_validated_payload(fenced: bool) -> None:
    raw = _plan_json()
    content = f"```json\n{raw}\n```" if fenced else raw
    result = parse_plan_candidate(content + "\n\nPLAN repaired; continue collecting evidence.")
    assert result.plan == parse_research_plan(raw) and not result.error


@pytest.mark.parametrize("fenced", [False, True])
def test_complete_plan_without_kind_is_rejected_as_plan_not_finish(fenced: bool) -> None:
    payload = json.loads(_plan_json())
    del payload["kind"]
    raw = json.dumps(payload)
    content = f"```json\n{raw}\n```" if fenced else raw

    result = parse_plan_candidate(content)

    assert result.plan is None, "recognition must not silently admit the plan"
    assert result.error == "missing plan fields: kind"
    with pytest.raises(ValueError, match="missing plan fields: kind"):
        parse_research_plan(content)


def test_live_k3_missing_kind_response_uses_plan_validation() -> None:
    # run_20260921_192812_245529, model_turn sequence=6; exact content bytes.
    content = (Path(__file__).parent / "fixtures" / "k3_missing_plan_kind.json").read_text(
        encoding="utf-8"
    )
    result = parse_plan_candidate(content)
    assert result.plan is None
    assert result.error == "missing plan fields: kind"


@pytest.mark.parametrize("field", ["budget", "tool", "evidence_hashes"])
def test_missing_kind_does_not_hide_unknown_plan_fields(field: str) -> None:
    payload = json.loads(_plan_json())
    del payload["kind"]
    payload[field] = "not authorized"
    result = parse_plan_candidate(json.dumps(payload))
    assert result.plan is None
    assert result.error == f"unknown plan fields: {field}"


@pytest.mark.parametrize("field", ["status", "draft", "gaps", "bindings", "render_from_claims"])
def test_untagged_plan_shaped_payload_with_finish_fields_stays_in_finish_lane(field: str) -> None:
    payload = json.loads(_plan_json())
    del payload["kind"]
    payload[field] = None  # Even an invalid terminal value is terminal intent.
    result = parse_plan_candidate(json.dumps(payload))
    assert result.plan is None
    assert result.error == ""


@pytest.mark.parametrize("content", [
    "", "null", "[]", "not JSON", "{}",
    '{"task_summary":"ordinary response"}',
    '{"requested_mode":"quick","revision":1}',
    '{"status":"partial","draft":"not enough evidence","gaps":[],"bindings":[]}',
])
def test_non_plan_output_is_not_inferred_from_text_or_partial_shape(content: str) -> None:
    result = parse_plan_candidate(content)
    assert result.plan is None
    assert result.error == ""


def test_fenced_plan_still_rejects_authoritative_fields() -> None:
    result = parse_plan_candidate("```json\n" + _plan_json(budget=999) + "\n```")
    assert result.plan is None and "unknown plan fields" in result.error


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
