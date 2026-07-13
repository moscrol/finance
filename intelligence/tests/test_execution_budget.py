from __future__ import annotations

from unittest.mock import patch

import pytest

from intelligence.services.execution_budget import ExecutionBudget


def test_start_uses_monotonic_clock_and_exact_total_seconds() -> None:
    with patch(
        "intelligence.services.execution_budget.time.monotonic",
        return_value=12.5,
    ) as monotonic:
        budget = ExecutionBudget.start(7.5)

    assert budget == ExecutionBudget(started_at=12.5, deadline_at=20.0)
    monotonic.assert_called_once_with()


def test_remaining_seconds_uses_injected_now_and_clamps_at_zero() -> None:
    budget = ExecutionBudget(started_at=10.0, deadline_at=20.0)

    assert budget.remaining_seconds(now=13.25) == 6.75
    assert budget.remaining_seconds(now=20.0) == 0.0
    assert budget.remaining_seconds(now=25.0) == 0.0


def test_remaining_seconds_defaults_to_monotonic_clock() -> None:
    budget = ExecutionBudget(started_at=10.0, deadline_at=20.0)

    with patch(
        "intelligence.services.execution_budget.time.monotonic",
        return_value=17.0,
    ) as monotonic:
        assert budget.remaining_seconds() == 3.0

    monotonic.assert_called_once_with()


@pytest.mark.parametrize(
    ("requested", "reserve", "now", "expected"),
    [
        (8.0, 2.0, 13.0, 5.0),
        (4.0, 2.0, 13.0, 4.0),
        (8.0, 7.0, 13.0, 0.0),
        (8.0, 2.0, 20.0, 0.0),
        (0.0, 2.0, 13.0, 0.0),
    ],
)
def test_child_timeout_is_bounded_by_request_and_remaining_reserve(
    requested: float,
    reserve: float,
    now: float,
    expected: float,
) -> None:
    budget = ExecutionBudget(started_at=10.0, deadline_at=20.0)

    assert budget.child_timeout(requested, reserve=reserve, now=now) == expected


def test_exhausted_includes_exact_deadline_boundary() -> None:
    budget = ExecutionBudget(started_at=10.0, deadline_at=20.0)

    assert budget.exhausted(now=19.999) is False
    assert budget.exhausted(now=20.0) is True
    assert budget.exhausted(now=25.0) is True


@pytest.mark.parametrize(
    "total_seconds",
    [-0.001, -1.0, float("nan"), float("inf"), float("-inf")],
)
def test_start_rejects_non_finite_or_negative_total_seconds(
    total_seconds: float,
) -> None:
    with pytest.raises(ValueError, match="total_seconds"):
        ExecutionBudget.start(total_seconds)


@pytest.mark.parametrize(
    ("requested", "reserve", "field_name"),
    [
        (-0.001, 0.0, "requested"),
        (float("nan"), 0.0, "requested"),
        (float("inf"), 0.0, "requested"),
        (float("-inf"), 0.0, "requested"),
        (1.0, -0.001, "reserve"),
        (1.0, float("nan"), "reserve"),
        (1.0, float("inf"), "reserve"),
        (1.0, float("-inf"), "reserve"),
    ],
)
def test_child_timeout_rejects_non_finite_or_negative_inputs(
    requested: float,
    reserve: float,
    field_name: str,
) -> None:
    budget = ExecutionBudget(started_at=10.0, deadline_at=20.0)

    with pytest.raises(ValueError, match=field_name):
        budget.child_timeout(requested, reserve=reserve, now=13.0)
