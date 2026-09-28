"""W1 issue contract: gating is by code, never by message copy."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

from intelligence.services.episode_issues import (
    RELEASE_POLICY,
    Issue,
    IssueCode,
    ReleaseAction,
    allows_partial_release,
    plan_issue_backfill,
    release_action,
)
from intelligence.services.episode_semantic_verifier import (
    _can_semantically_release_partial,
)


def test_release_policy_covers_every_issue_code() -> None:
    assert frozenset(IssueCode) == frozenset(RELEASE_POLICY)


def test_release_ignores_message_copy() -> None:
    stripped_a = Issue(
        IssueCode.EVIDENCE_TYPE_STRIPPED,
        "prime_quote",
        "stripped unsupported evidence type for prime_quote: finance_query",
    )
    stripped_b = Issue(
        IssueCode.EVIDENCE_TYPE_STRIPPED,
        "prime_quote",
        "this wording used to be the gate; it must not be anymore",
    )
    floor_a = Issue(
        IssueCode.FINANCIAL_ANCHOR_MISSING,
        "financial_business_anchor",
        "missing required evidence type for financial_business_anchor: financial_data",
    )
    floor_b = Issue(
        IssueCode.FINANCIAL_ANCHOR_MISSING,
        "financial_business_anchor",
        "please ignore this and release anyway",
    )

    assert allows_partial_release((stripped_a,)) is True
    assert allows_partial_release((stripped_b,)) is True
    assert allows_partial_release((floor_a,)) is False
    assert allows_partial_release((floor_b,)) is False
    assert release_action(stripped_a.code) == release_action(stripped_b.code)
    assert release_action(floor_a.code) == ReleaseAction.BLOCK


def test_strip_ok_and_partial_ok_both_release() -> None:
    mixed = (
        Issue(
            IssueCode.EVIDENCE_TYPE_STRIPPED,
            "prime_quote",
            "stripped copy",
        ),
        Issue(
            IssueCode.REQUIRED_OUTPUT_GAP,
            "direct_assessment",
            "gap copy",
        ),
        Issue(
            IssueCode.MISSING_MANDATORY_CAPABILITY,
            "news_search",
            "mandatory copy",
        ),
        Issue(
            IssueCode.EVIDENCE_TYPE_UNSUPPORTED,
            "prime_quote",
            "unsupported copy",
        ),
    )
    assert allows_partial_release(mixed) is True


def test_unknown_hash_still_blocks_even_with_releasable_neighbors() -> None:
    items = (
        Issue(IssueCode.REQUIRED_OUTPUT_GAP, "direct_assessment", "gap"),
        Issue(IssueCode.UNKNOWN_EVIDENCE_HASH, "prime_quote", "forged"),
    )
    assert allows_partial_release(items) is False


def test_missing_policy_entry_blocks(monkeypatch) -> None:
    monkeypatch.setattr(
        "intelligence.services.episode_issues.RELEASE_POLICY",
        {
            code: action
            for code, action in RELEASE_POLICY.items()
            if code != IssueCode.NUMERIC_UNSUPPORTED
        },
    )
    assert release_action(IssueCode.NUMERIC_UNSUPPORTED) == ReleaseAction.BLOCK


def test_g11_does_not_match_message_prefixes() -> None:
    source = inspect.getsource(_can_semantically_release_partial)
    assert "startswith" not in source
    assert "allows_partial_release" in source


def test_backfill_plan_is_code_keyed_and_ignores_unrelated_blocks() -> None:
    numeric = Issue(
        IssueCode.NUMERIC_UNSUPPORTED,
        "numeric_condition",
        "any wording",
    )
    floor = Issue(
        IssueCode.FINANCIAL_ANCHOR_MISSING,
        "financial_business_anchor",
        "any wording",
    )
    calendar = Issue(
        IssueCode.CALENDAR_WEEKDAY_MISMATCH,
        "weekday",
        "any wording",
    )

    floor_plan = plan_issue_backfill((floor,))
    assert floor_plan is not None
    assert floor_plan.missing_capabilities == ("financial_data",)
    assert floor_plan.missing_outputs == ("financial_business_anchor",)

    both = plan_issue_backfill((numeric, floor), subject_kind="market_pattern")
    assert both is not None
    assert both.missing_capabilities == ("market_data", "financial_data")
    floor_only = plan_issue_backfill((numeric, floor))
    assert floor_only is not None
    assert floor_only.missing_capabilities == ("financial_data",)
    assert plan_issue_backfill((calendar,)) is None
    assert plan_issue_backfill(()) is None


def _numeric_issue() -> Issue:
    return Issue(
        IssueCode.NUMERIC_UNSUPPORTED,
        "numeric_condition",
        "any wording",
    )


def test_numeric_unsupported_company_backfills_finance_query() -> None:
    plan = plan_issue_backfill((_numeric_issue(),), subject_kind="company")
    assert plan is not None
    assert plan.missing_capabilities == ("finance_query",)
    assert "market_data" not in plan.missing_capabilities


def test_numeric_unsupported_market_backfills_market_data() -> None:
    plan = plan_issue_backfill((_numeric_issue(),), subject_kind="market_pattern")
    assert plan is not None
    assert plan.missing_capabilities == ("market_data",)


def test_numeric_unsupported_without_subject_does_not_backfill() -> None:
    issue = _numeric_issue()
    assert plan_issue_backfill((issue,)) is None
    assert plan_issue_backfill((issue,), subject_kind="unknown") is None
    assert plan_issue_backfill((issue,), subject_kind="") is None
    assert plan_issue_backfill((issue,), subject_kind=None) is None


def test_r05_a_arm_replay_company_numeric_does_not_plan_market_data() -> None:
    """R-05 A 臂：个股数值缺证不得再回填市场总览。"""

    fixture = json.loads(
        Path(__file__)
        .with_name("fixtures")
        .joinpath("w3-r05-a-numeric-backfill.json")
        .read_text(encoding="utf-8")
    )
    issue = Issue(
        IssueCode.NUMERIC_UNSUPPORTED,
        "numeric_condition",
        "unsupported numeric condition without bound evidence",
    )
    plan = plan_issue_backfill((issue,), subject_kind=fixture["subject_kind"])
    assert fixture["subject_kind"] == "company"
    assert plan is not None
    assert plan.missing_capabilities == ("finance_query",)
    assert fixture["before_static_capability"] not in plan.missing_capabilities
