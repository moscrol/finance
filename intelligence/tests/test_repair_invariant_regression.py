"""Permanent guards for repair/budget/session invariants found by review.

Each test encodes one finding from verdicts ARL-0014 and ARL-0015 so the class
of defect cannot return. These assert the specification, not current behaviour:
a red test here means the invariant is violated, not that the test is stale.

Provenance:
  ARL-0014 finding 1  -> test_resume_rejects_rewritten_history
  ARL-0014 finding 2  -> test_resume_rejects_replayed_outcome_without_model_turn
  ARL-0014 finding 3  -> test_repair_cycles_are_capped_by_tier_not_by_goal
  ARL-0014 finding 4  -> test_root_budget_rejects_foreign_episode_grant
  ARL-0014 finding 5  -> test_progress_without_provenance_is_not_progress
  ARL-0014 finding 7  -> test_consume_call_rejects_zero_seconds
  ARL-0015 finding 2  -> test_root_budget_requires_explicit_episode_binding
  ARL-0015 finding 3  -> test_second_ledger_for_live_episode_is_refused
"""

from __future__ import annotations

import pytest

from intelligence.services.repair_coordinator import (
    ProgressSnapshot,
    build_repair_goal,
    grant_for_progress,
    max_repair_cycles_for_tier,
)
from intelligence.services.research_contract import (
    InMemoryRootBudgetLedger,
    ResearchPolicy,
    root_budget_for_policy,
)


def _deep_policy() -> ResearchPolicy:
    return ResearchPolicy.for_tier("deep")


def _progress(
    *,
    new_id: str = "h2",
    family: str = "fam-b",
    target: str = "conclusion",
    with_provenance: bool = True,
) -> ProgressSnapshot:
    """One new independent item that closes a previously open gap."""

    kwargs: dict[str, object] = {
        "before_evidence_ids": ("h1",),
        "after_evidence_ids": ("h1", new_id),
        "before_covered_outputs": (),
        "after_covered_outputs": (target,),
        "before_open_gaps": ("gap-1",),
        "after_open_gaps": (),
        "independent_source_families": ("fam-a", family),
    }
    if with_provenance:
        kwargs["before_evidence_source_families"] = (("h1", "fam-a"),)
        kwargs["after_evidence_source_families"] = (("h1", "fam-a"), (new_id, family))
        kwargs["before_evidence_targets"] = (("h1", ()),)
        kwargs["after_evidence_targets"] = (("h1", ()), (new_id, (target,)))
    return ProgressSnapshot(**kwargs)  # type: ignore[arg-type]


def _goal(*, cycle: int, episode_id: str = "ep-1"):
    return build_repair_goal(
        episode_id=episode_id,
        missing_outputs=("conclusion",),
        previous_progress=_progress(),
        remaining_calls=8,
        remaining_seconds=60.0,
        cycle=cycle,
    )


def _ledger(*, episode_id: str = "ep-1") -> InMemoryRootBudgetLedger:
    return InMemoryRootBudgetLedger(
        episode_id=episode_id,
        initial_calls=8,
        hard_calls_cap=24,
        initial_seconds=60.0,
        hard_seconds_cap=180.0,
    )


# --- ARL-0014 finding 3: cycle bound must come from the tier, not the goal ---


def test_tier_owns_repair_cycle_cap() -> None:
    assert max_repair_cycles_for_tier("quick") == 1
    assert max_repair_cycles_for_tier("standard") == 1
    assert max_repair_cycles_for_tier("deep") == 3
    with pytest.raises(ValueError):
        max_repair_cycles_for_tier("unbounded")


@pytest.mark.parametrize(
    ("tier", "last_allowed_cycle"),
    (("quick", 1), ("standard", 1), ("deep", 3)),
)
def test_repair_cycles_are_capped_by_tier_not_by_goal(
    tier: str,
    last_allowed_cycle: int,
) -> None:
    """A goal must not be able to authorise its own extra cycle.

    Regression for the phantom ``max_cycles=goal.cycle`` bound, where the
    ceiling check could never fail because it was compared against itself.
    """

    granted = grant_for_progress(
        _goal(cycle=last_allowed_cycle),
        _progress(),
        root_budget=_ledger(),
        research_tier=tier,
    )
    assert granted is not None, "the final in-tier cycle must still be grantable"

    refused = grant_for_progress(
        _goal(cycle=last_allowed_cycle + 1),
        _progress(),
        root_budget=_ledger(),
        research_tier=tier,
    )
    assert refused is None, (
        f"{tier} tier must refuse cycle {last_allowed_cycle + 1} even when the "
        "goal claims that cycle and progress is real"
    )


def test_no_progress_refuses_grant_regardless_of_tier() -> None:
    """Budget extension is earned by observable gap progress, never by tier."""

    stalled = ProgressSnapshot(
        before_evidence_ids=("h1",),
        after_evidence_ids=("h1",),
        before_covered_outputs=(),
        after_covered_outputs=(),
        before_open_gaps=("gap-1",),
        after_open_gaps=("gap-1",),
        independent_source_families=("fam-a",),
        before_evidence_source_families=(("h1", "fam-a"),),
        after_evidence_source_families=(("h1", "fam-a"),),
    )
    assert stalled.coverage_delta.progressed is False
    assert (
        grant_for_progress(
            _goal(cycle=1),
            stalled,
            root_budget=_ledger(),
            research_tier="deep",
        )
        is None
    )


# --- ARL-0014 finding 5: a bare new hash must not unlock repair budget ---


def test_same_source_family_is_not_independent_progress() -> None:
    same_family = _progress(new_id="h2", family="fam-a")
    assert same_family.effective_new_evidence == 0
    assert same_family.coverage_delta.progressed is False


def test_evidence_for_already_covered_output_is_not_progress() -> None:
    covered = ProgressSnapshot(
        before_evidence_ids=("h1",),
        after_evidence_ids=("h1", "h2"),
        before_covered_outputs=("conclusion",),
        after_covered_outputs=("conclusion",),
        before_open_gaps=(),
        after_open_gaps=(),
        independent_source_families=("fam-a", "fam-b"),
        before_evidence_source_families=(("h1", "fam-a"),),
        after_evidence_source_families=(("h1", "fam-a"), ("h2", "fam-b")),
        before_evidence_targets=(("h1", ("conclusion",)),),
        after_evidence_targets=(("h1", ("conclusion",)), ("h2", ("conclusion",))),
    )
    assert covered.effective_new_evidence == 0


def test_progress_without_provenance_is_not_progress() -> None:
    """Omitting the provenance tuples must not re-enable raw hash counting.

    ``ProgressSnapshot`` defaults the family/target tuples to ``()``. If the
    guards are skipped when those are empty, any caller that forgets them gets
    the forbidden "a new content hash alone is progress" semantics.
    """

    bare = _progress(with_provenance=False)
    assert bare.effective_new_evidence == 0, (
        "a snapshot carrying no source-family or target provenance must not "
        "count new hashes as independent progress"
    )


# --- ARL-0014 finding 4 / ARL-0015 findings 2-3: root budget authority ---


def test_root_budget_rejects_foreign_episode_grant() -> None:
    ledger = _ledger(episode_id="ep-1")
    granted = grant_for_progress(
        _goal(cycle=1, episode_id="ep-1"),
        _progress(),
        root_budget=ledger,
        research_tier="deep",
    )
    assert granted is not None

    foreign = grant_for_progress(
        _goal(cycle=1, episode_id="ep-2"),
        _progress(),
        root_budget=ledger,
        research_tier="deep",
    )
    assert foreign is None, "one ledger must not fund a different episode"


def test_duplicate_grant_and_cap_overflow_are_refused() -> None:
    ledger = _ledger()
    grant = grant_for_progress(
        _goal(cycle=1),
        _progress(),
        root_budget=ledger,
        research_tier="deep",
    )
    assert grant is not None
    assert ledger.grant(grant) is False, "replaying a grant id must be refused"

    class _Oversized:
        grant_id = "grant-oversized"
        episode_id = "ep-1"
        calls_granted = 999
        seconds_granted = 1.0

    assert ledger.grant(_Oversized()) is False


def test_root_budget_requires_explicit_episode_binding() -> None:
    """An unbound ledger must not silently fund whatever asks.

    ``episode_id`` defaults to ``""`` and the guard short-circuits on a falsy
    value, so a ledger built without the keyword enforces nothing. The safe
    default is to refuse construction rather than to accept every episode.
    """

    with pytest.raises(ValueError):
        InMemoryRootBudgetLedger(
            initial_calls=8,
            hard_calls_cap=24,
            initial_seconds=60.0,
            hard_seconds_cap=180.0,
        )


def test_second_ledger_for_live_episode_is_refused() -> None:
    """Two ledgers for one episode means two independent hard caps."""

    first = root_budget_for_policy(_deep_policy(), episode_id="ep-live")
    assert first.episode_id == "ep-live"
    with pytest.raises(ValueError):
        root_budget_for_policy(_deep_policy(), episode_id="ep-live")


def test_consume_call_rejects_zero_seconds() -> None:
    """Real elapsed time must not be bookable as free.

    A zero-second charge lets a batch consume a call slot while spending
    nothing against ``hard_seconds_cap``.
    """

    ledger = _ledger()
    with pytest.raises(ValueError):
        ledger.consume_call(seconds=0.0)
