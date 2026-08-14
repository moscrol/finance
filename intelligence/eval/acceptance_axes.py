"""Deterministic delivery, information, and credibility projections."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from intelligence.eval.acceptance_verdict import (
    CaseVerdict,
    OperationalState,
    VerdictState,
)


class AxisState(str, Enum):
    PASS = "pass"
    PARTIAL = "partial"
    FAIL = "fail"
    UNJUDGEABLE = "unjudgeable"
    NOT_EVALUATED = "not_evaluated"
    NOT_RUN = "not_run"


class InformationComparison(str, Enum):
    WORKBENCH_WINS = "workbench_wins"
    TIE = "tie"
    KNEVO_WINS = "knevo_wins"


@dataclass(frozen=True)
class AxisVerdict:
    state: AxisState
    reason: str
    comparison: InformationComparison | None = None


@dataclass(frozen=True)
class AcceptanceAxes:
    delivery: AxisVerdict
    information: AxisVerdict
    credibility: AxisVerdict


def _project_delivery(state: OperationalState, reason: str) -> AxisVerdict:
    mapping = {
        OperationalState.NOT_RUN: AxisState.NOT_RUN,
        OperationalState.BLOCKED: AxisState.FAIL,
        OperationalState.FAILED: AxisState.FAIL,
        OperationalState.DEGRADED: AxisState.PARTIAL,
        OperationalState.COMPLETED: AxisState.PASS,
    }
    return AxisVerdict(mapping[state], reason)


def _project_credibility(state: VerdictState) -> AxisVerdict:
    mapping = {
        VerdictState.NOT_RUN: AxisState.NOT_RUN,
        VerdictState.PASS: AxisState.PASS,
        VerdictState.FAIL: AxisState.FAIL,
        VerdictState.UNJUDGEABLE: AxisState.UNJUDGEABLE,
    }
    reasons = {
        VerdictState.NOT_RUN: "case has not run",
        VerdictState.PASS: "all evaluated truth rules passed",
        VerdictState.FAIL: "one or more required truth rules failed",
        VerdictState.UNJUDGEABLE: "required truth evidence is not judgeable",
    }
    return AxisVerdict(mapping[state], reasons[state])


def _project_information(
    observation: Mapping[str, Any] | None,
    *,
    case_not_run: bool,
) -> AxisVerdict:
    if case_not_run:
        return AxisVerdict(AxisState.NOT_RUN, "case has not run")
    if observation is None:
        return AxisVerdict(
            AxisState.NOT_EVALUATED,
            "independent information comparison not supplied",
        )

    raw_state = str(observation.get("state") or "")
    reason = str(observation.get("reason") or "information comparison supplied")
    if raw_state == "not_evaluated":
        return AxisVerdict(AxisState.NOT_EVALUATED, reason)
    mapping = {
        "workbench_wins": (AxisState.PASS, InformationComparison.WORKBENCH_WINS),
        "tie": (AxisState.PARTIAL, InformationComparison.TIE),
        "knevo_wins": (AxisState.FAIL, InformationComparison.KNEVO_WINS),
    }
    projected = mapping.get(raw_state)
    if projected is None:
        raise ValueError(f"unknown information comparison state: {raw_state!r}")
    state, comparison = projected
    return AxisVerdict(state, reason, comparison)


def project_axes(
    verdict: CaseVerdict,
    information: Mapping[str, Any] | None = None,
) -> AcceptanceAxes:
    """Project three orthogonal axes without changing the canonical verdict."""

    return AcceptanceAxes(
        delivery=_project_delivery(
            verdict.operational.state,
            verdict.operational.reason,
        ),
        information=_project_information(
            information,
            case_not_run=verdict.operational.state is OperationalState.NOT_RUN,
        ),
        credibility=_project_credibility(verdict.truth.state),
    )
