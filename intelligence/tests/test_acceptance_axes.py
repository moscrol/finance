from __future__ import annotations

import pytest

from intelligence.eval.acceptance_axes import (
    AxisState,
    InformationComparison,
    project_axes,
)
from intelligence.eval.acceptance_verdict import (
    CaseVerdict,
    OperationalState,
    OperationalVerdict,
    TruthVerdict,
    VerdictState,
)


def _verdict(
    *,
    operational: OperationalState,
    truth: VerdictState,
) -> CaseVerdict:
    return CaseVerdict(
        case_id="A1-market-overview",
        operational=OperationalVerdict(operational, "operational reason"),
        truth=TruthVerdict(truth, ()),
    )


def test_delivery_does_not_claim_truth() -> None:
    axes = project_axes(
        _verdict(
            operational=OperationalState.COMPLETED,
            truth=VerdictState.FAIL,
        )
    )

    assert axes.delivery.state is AxisState.PASS
    assert axes.credibility.state is AxisState.FAIL


def test_degraded_delivery_is_partial() -> None:
    axes = project_axes(
        _verdict(
            operational=OperationalState.DEGRADED,
            truth=VerdictState.PASS,
        )
    )

    assert axes.delivery.state is AxisState.PARTIAL


def test_missing_information_observation_is_not_evaluated() -> None:
    axes = project_axes(
        _verdict(
            operational=OperationalState.COMPLETED,
            truth=VerdictState.PASS,
        )
    )

    assert axes.information.state is AxisState.NOT_EVALUATED
    assert axes.information.comparison is None


def test_unreproducible_truth_remains_unjudgeable() -> None:
    axes = project_axes(
        _verdict(
            operational=OperationalState.COMPLETED,
            truth=VerdictState.UNJUDGEABLE,
        )
    )

    assert axes.credibility.state is AxisState.UNJUDGEABLE


@pytest.mark.parametrize(
    ("raw_state", "axis_state", "comparison"),
    [
        ("workbench_wins", AxisState.PASS, InformationComparison.WORKBENCH_WINS),
        ("tie", AxisState.PARTIAL, InformationComparison.TIE),
        ("knevo_wins", AxisState.FAIL, InformationComparison.KNEVO_WINS),
        ("not_evaluated", AxisState.NOT_EVALUATED, None),
    ],
)
def test_information_comparison_mapping(
    raw_state: str,
    axis_state: AxisState,
    comparison: InformationComparison | None,
) -> None:
    axes = project_axes(
        _verdict(
            operational=OperationalState.COMPLETED,
            truth=VerdictState.PASS,
        ),
        information={"state": raw_state, "reason": "comparison reason"},
    )

    assert axes.information.state is axis_state
    assert axes.information.comparison is comparison
    assert axes.information.reason == "comparison reason"


def test_unknown_information_state_fails_closed() -> None:
    with pytest.raises(ValueError, match="unknown information comparison state"):
        project_axes(
            _verdict(
                operational=OperationalState.COMPLETED,
                truth=VerdictState.PASS,
            ),
            information={"state": "better-ish", "reason": "invalid"},
        )
