from __future__ import annotations

from intelligence.services.research_policy import (
    ResearchExecutionBudget,
    ResearchExecutionPolicy,
)


def test_research_budget_stops_after_configured_call_count() -> None:
    budget = ResearchExecutionBudget(
        ResearchExecutionPolicy(max_skill_calls=2, max_elapsed_seconds=60)
    )

    assert budget.can_start() is True
    budget.record(
        "first",
        input_summary="query",
        provider="registry",
        status="completed",
        elapsed_ms=10,
    )
    assert budget.can_start() is True
    budget.record(
        "second",
        input_summary="query",
        provider="registry",
        status="failed",
        elapsed_ms=20,
        failure_reason="empty",
    )

    assert budget.can_start() is False
    trace = budget.to_trace()
    assert trace["call_count"] == 2
    assert trace["attempt_count"] == 2
    assert trace["attempts"][1]["failure_reason"] == "empty"
    assert trace["max_retries_per_skill"] == 0


def test_research_budget_stops_when_elapsed_budget_is_exhausted() -> None:
    budget = ResearchExecutionBudget(
        ResearchExecutionPolicy(max_skill_calls=3, max_elapsed_seconds=0)
    )

    assert budget.can_start() is False
