"""Permanent guards for episode-session and evidence-cutoff invariants.

Encodes review findings so the class of defect cannot return. These assert the
specification: a red test means the invariant is violated.

Provenance:
  ARL-0014 finding 1 -> test_resume_rejects_rewritten_history
  ARL-0014 finding 2 -> test_resume_rejects_replayed_outcome_without_model_turn
  ARL-0014 finding 2 -> test_resume_rejects_tool_only_continuation
  ARL-0014 finding 8 -> test_undated_evidence_is_not_silently_cutoff_valid
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import AgentOutcome, AgentUsage, EpisodeEvent
from intelligence.services.episode_session import (
    CallbackEpisodeSession,
    EpisodeSessionError,
)
from intelligence.services.evidence_ledger import EvidenceLedger
from intelligence.services.repair_coordinator import CoverageDelta, RepairGoal


def _outcome() -> AgentOutcome:
    return AgentOutcome(
        task_frame_hash="frame-1",
        status="partial",
        draft="缺少反方证据",
        evidence=(),
        traces=(),
        gaps=("counterpoint",),
        stop_reason="model_finish",
        events=(EpisodeEvent(1, "task", {"task_frame_hash": "frame-1"}),),
        bindings=(),
        usage=AgentUsage(llm_calls=1),
    )


def _goal(episode_id: str = "episode-1") -> RepairGoal:
    return RepairGoal(
        episode_id=episode_id,
        repair_goal_id="repair-1",
        cycle=1,
        missing_answer_elements=("counterpoint",),
        unsupported_claims=(),
        missing_evidence_modes=("news_search",),
        attempted_actions=("market_data:A股",),
        evidence_progress=CoverageDelta(1, 0, 1),
        remaining_calls=2,
        remaining_seconds=20,
    )


def _session(callback) -> CallbackEpisodeSession:
    return CallbackEpisodeSession(
        episode_id="episode-1",
        outcome=_outcome(),
        resume_callback=callback,
    )


# --- ARL-0014 finding 2: repair must execute a new model-owned action ---


def test_resume_rejects_replayed_outcome_without_model_turn() -> None:
    """Returning the prior outcome unchanged is not repair.

    Renaming a fallback must not satisfy re-entry: identity, task frame and
    event count all match, so only an explicit new-action requirement catches
    it.
    """

    session = _session(lambda previous, _goal: previous)
    with pytest.raises(EpisodeSessionError):
        session.resume(_goal())
    assert session.resume_count == 0


def test_resume_rejects_tool_only_continuation() -> None:
    """Appending tool events without a model turn is not a model-owned action."""

    def tool_only(previous, _goal):
        return replace(
            previous,
            events=previous.events
            + (EpisodeEvent(2, "tool_result", {"tool": "market_data"}),),
        )

    session = _session(tool_only)
    with pytest.raises(EpisodeSessionError):
        session.resume(_goal())
    assert session.resume_count == 0


# --- ARL-0014 finding 1: history must be an exact prefix ---


def test_resume_rejects_rewritten_history() -> None:
    """Equal-or-longer history is not enough; the old prefix must survive.

    A length-only guard lets a continuation silently replace what actually
    happened, which would destroy the audit trail the verdict relies on.
    """

    def rewrite(previous, _goal):
        return replace(
            previous,
            events=(
                EpisodeEvent(1, "task", {"task_frame_hash": "frame-1", "x": "changed"}),
                EpisodeEvent(2, "model_turn", {"phase": "repair"}),
            ),
        )

    session = _session(rewrite)
    with pytest.raises(EpisodeSessionError):
        session.resume(_goal())
    assert session.resume_count == 0


def test_empty_and_inconsistent_history_is_unconstructible() -> None:
    """The outcome type already forbids these, which is stronger than a check.

    Recording it so a future refactor that relaxes ``AgentOutcome`` cannot
    quietly move the burden onto the session guard alone.
    """

    base = _outcome()
    with pytest.raises(ValueError):
        replace(base, events=())
    with pytest.raises(ValueError):
        replace(base, task_frame_hash="frame-2")


def test_resume_rejects_discarded_history() -> None:
    """A shorter, still self-consistent history must be refused."""

    two_events = replace(
        _outcome(),
        events=(
            EpisodeEvent(1, "task", {"task_frame_hash": "frame-1"}),
            EpisodeEvent(2, "model_turn", {"phase": "first"}),
        ),
    )
    session = CallbackEpisodeSession(
        episode_id="episode-1",
        outcome=two_events,
        resume_callback=lambda previous, _goal: replace(
            previous,
            events=(EpisodeEvent(1, "task", {"task_frame_hash": "frame-1"}),),
        ),
    )
    with pytest.raises(EpisodeSessionError):
        session.resume(_goal())


def test_resume_rejects_changed_task_frame() -> None:
    """A self-consistent but different frame must still be refused.

    The continuation is internally valid, so only the session's identity check
    can catch that it is no longer the same task.
    """

    def reframe(previous, _goal):
        return replace(
            previous,
            task_frame_hash="frame-2",
            events=(
                EpisodeEvent(1, "task", {"task_frame_hash": "frame-2"}),
                EpisodeEvent(2, "model_turn", {"phase": "repair"}),
            ),
        )

    with pytest.raises(EpisodeSessionError):
        _session(reframe).resume(_goal())


def test_resume_rejects_foreign_episode_goal() -> None:
    def ok(previous, _goal):
        return replace(
            previous,
            events=previous.events
            + (EpisodeEvent(2, "model_turn", {"phase": "repair"}),),
        )

    with pytest.raises(EpisodeSessionError):
        _session(ok).resume(_goal(episode_id="episode-2"))


def test_valid_repair_is_accepted() -> None:
    """The positive case must still pass, so the guards are not vacuous."""

    def repair(previous, _goal):
        return replace(
            previous,
            events=previous.events
            + (EpisodeEvent(2, "model_turn", {"phase": "repair"}),),
            draft="已执行同一 episode 的修复动作",
        )

    session = _session(repair)
    updated = session.resume(_goal())
    assert session.resume_count == 1
    assert updated.events[0] == _outcome().events[0]
    assert updated.events[-1].kind == "model_turn"


# --- ARL-0014 finding 8: as-of must filter, and undated must be visible ---


def _evidence(content_hash: str, source_date: str | None) -> AgentEvidence:
    return AgentEvidence(
        tool="news_search",
        title="标题",
        detail="摘要",
        source="https://example.com/a",
        source_date=source_date,
        independent_key=f"key-{content_hash}",
        content_hash=content_hash,
    )


def test_future_dated_evidence_is_refused_by_cutoff() -> None:
    ledger = EvidenceLedger(information_cutoff=date(2026, 7, 24))
    assert ledger.append(_evidence("h-future", "2026-07-25")) == ()
    assert ledger.snapshot().evidence_ids == ()


def test_malformed_date_is_fail_closed() -> None:
    ledger = EvidenceLedger(information_cutoff=date(2026, 7, 24))
    assert ledger.append(_evidence("h-bad", "not-a-date")) == ()


def test_undated_evidence_is_not_silently_cutoff_valid() -> None:
    """An undated item must be distinguishable from a cutoff-verified one.

    ``_valid_for_cutoff`` returns True when ``source_date`` is missing, so
    undated evidence is admitted. That is defensible, but the snapshot must
    record which items were actually date-checked, otherwise a verifier cannot
    tell "published on or before as_of" from "no date available" and an undated
    item can silently support a dated claim.
    """

    ledger = EvidenceLedger(information_cutoff=date(2026, 7, 24))
    added = ledger.append(_evidence("h-undated", None))
    assert added == ("h-undated",), "undated evidence is admitted today"

    snapshot = ledger.snapshot()
    assert hasattr(snapshot, "evidence_cutoff_status"), (
        "snapshot must expose a per-item cutoff verdict so undated evidence is "
        "not indistinguishable from cutoff-verified evidence"
    )
    assert dict(snapshot.evidence_cutoff_status)["h-undated"] == "undated"


def test_reappend_is_idempotent_and_append_only() -> None:
    ledger = EvidenceLedger(information_cutoff=date(2026, 7, 24))
    first = ledger.append(_evidence("h1", "2026-07-20"))
    second = ledger.append(_evidence("h1", "2026-07-20"))
    assert first == ("h1",)
    assert second == (), "re-appending a known hash must add nothing"
    assert ledger.snapshot().evidence_ids == ("h1",)


def test_coverage_cannot_be_asserted_without_existing_evidence() -> None:
    ledger = EvidenceLedger(information_cutoff=date(2026, 7, 24))
    ledger.append(_evidence("h1", "2026-07-20"))
    assert ledger.mark_output_covered("conclusion", evidence_ids=("h-missing",)) is False
    assert ledger.snapshot().covered_outputs == ()
    assert ledger.mark_output_covered("conclusion", evidence_ids=("h1",)) is True
