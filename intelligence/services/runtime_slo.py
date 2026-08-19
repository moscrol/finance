"""P4: project SLO rates from existing receipts. Missing stays unevaluated.

This is a pull-based sidecar, not a second telemetry pipeline and not an
auto-rollback switch. ``gate_receipt`` stays the ask/episode dict-diff
contract; this module only aggregates what those artifacts already contain.

Unknown measurements are ``not_evaluated``, never a silent ``0``. An evaluated
cohort may still report ``0.0`` when the event genuinely did not happen.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

NOT_EVALUATED = "not_evaluated"
UNKNOWN = "unknown"

DIMENSIONS = (
    "source_revision",
    "runtime_backend",
    "provider",
    "model",
    "question_type",
    "research_tier",
    "status",
    "stop_reason",
)

RATE_FIELDS = (
    "completion_rate",
    "partial_rate",
    "degraded_rate",
    "failed_rate",
    "cancelled_rate",
    "repair_rate",
    "cold_restart_rate",
    "late_result_rate",
    "provider_error_rate",
    "tool_error_rate",
    "semantic_verifier_unavailable_rate",
    "budget_exhaustion_rate",
)

DEFAULT_CANARY_THRESHOLDS = {
    "degraded_rate": 0.25,
    "provider_error_rate": 0.20,
    "late_result_rate": 0.10,
}

RateValue = float | Literal["not_evaluated"]


@dataclass(frozen=True)
class RuntimeObservation:
    source_revision: str = UNKNOWN
    runtime_backend: str = UNKNOWN
    provider: str = UNKNOWN
    model: str = UNKNOWN
    question_type: str = UNKNOWN
    research_tier: str = UNKNOWN
    status: str = UNKNOWN
    stop_reason: str = UNKNOWN
    latency_seconds: float | None = None
    time_to_first_tool: float | None = None
    repaired: bool | None = None
    cold_restart: bool | None = None
    late_result_count: int | None = None
    provider_error: bool | None = None
    tool_error: bool | None = None
    semantic_verifier_unavailable: bool | None = None
    llm_calls: int | None = None
    tool_calls: int | None = None
    budget_exhausted: bool | None = None
    tools_paired: bool | None = None
    terminal_claim_conflict: bool | None = None


def _text(value: object) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return UNKNOWN


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _int_or_none(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _float_or_none(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _events(private: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    raw = private.get("events")
    if not isinstance(raw, list):
        return ()
    return tuple(item for item in raw if isinstance(item, Mapping))


def _tools_paired(events: Sequence[Mapping[str, Any]]) -> bool | None:
    if not events:
        return None
    requests = sum(1 for item in events if item.get("kind") == "tool_request")
    if requests == 0:
        return True
    settled = sum(
        1
        for item in events
        if item.get("kind") in {"tool_result", "tool_error"}
    )
    return settled >= requests


def observation_from_artifacts(
    *,
    run: Mapping[str, Any] | None = None,
    report: Mapping[str, Any] | None = None,
    private_artifact: Mapping[str, Any] | None = None,
) -> RuntimeObservation:
    """Best-effort extract. Gaps stay ``unknown`` / ``None``, never zero-filled."""

    run = _mapping(run)
    report = _mapping(report)
    private = _mapping(private_artifact)
    receipt = _mapping(report.get("gate_receipt"))
    outcome = _mapping(private.get("outcome"))
    contract = _mapping(private.get("contract"))
    usage = _mapping(outcome.get("usage"))
    metrics = _mapping(private.get("metrics"))
    timings = _mapping(receipt.get("timings"))
    events = _events(private)

    judge = _text(receipt.get("judge_status"))
    semantic_unavailable: bool | None
    if judge in {UNKNOWN, "not_applicable"}:
        semantic_unavailable = None
    else:
        semantic_unavailable = judge == "unavailable"

    stop = _text(outcome.get("stop_reason"))
    budget_exhausted: bool | None
    if stop == UNKNOWN:
        budget_exhausted = None
    else:
        budget_exhausted = stop in {
            "deadline_exhausted",
            "tool_budget_exhausted",
            "retrieval_deadline_closed",
        } or "budget" in stop

    repair_attempts = _int_or_none(private.get("repair_attempts"))
    repaired = None if repair_attempts is None else repair_attempts > 0

    late_count = _int_or_none(
        _mapping(report.get("query_ledger")).get("late_result_discarded_count")
    )
    if late_count is None:
        late_count = _int_or_none(private.get("late_result_discarded_count"))

    traces = private.get("traces")
    provider = UNKNOWN
    model = UNKNOWN
    if isinstance(traces, list):
        for item in traces:
            if not isinstance(item, Mapping):
                continue
            provider = _text(item.get("provider")) or provider
            if provider != UNKNOWN:
                break
    for event in events:
        if event.get("kind") != "model_turn":
            continue
        payload = _mapping(event.get("payload"))
        if provider == UNKNOWN:
            provider = _text(payload.get("provider_name"))
        if model == UNKNOWN:
            model = _text(payload.get("model"))

    provider_error = None
    tool_error = None
    if events:
        provider_error = any(
            item.get("kind") == "model_error" for item in events
        )
        tool_error = any(item.get("kind") == "tool_error" for item in events)

    cold = private.get("cold_restart")
    if not isinstance(cold, bool):
        cold = None

    claim_conflict = run.get("error") == "run terminal state already claimed"
    if not claim_conflict and isinstance(run.get("error"), str):
        claim_conflict = "terminal state already claimed" in str(run.get("error"))
    if run.get("error") in {None, ""} and "status" not in run and not private:
        claim_conflict_flag: bool | None = None
    else:
        claim_conflict_flag = bool(claim_conflict)

    status = _text(run.get("status"))
    if status == UNKNOWN:
        status = _text(outcome.get("status"))

    return RuntimeObservation(
        source_revision=_text(receipt.get("rev")),
        runtime_backend=_text(private.get("runtime_backend")),
        provider=provider,
        model=model,
        question_type=_text(contract.get("question_type")),
        research_tier=_text(contract.get("research_tier")),
        status=status,
        stop_reason=stop,
        latency_seconds=_float_or_none(timings.get("elapsed_seconds")),
        time_to_first_tool=None,
        repaired=repaired,
        cold_restart=cold,
        late_result_count=late_count,
        provider_error=provider_error,
        tool_error=tool_error,
        semantic_verifier_unavailable=semantic_unavailable,
        llm_calls=_int_or_none(usage.get("llm_calls"))
        if usage
        else _int_or_none(metrics.get("provider_attempts")),
        tool_calls=_int_or_none(usage.get("tool_calls"))
        if usage
        else _int_or_none(metrics.get("tool_calls")),
        budget_exhausted=budget_exhausted,
        tools_paired=_tools_paired(events),
        terminal_claim_conflict=claim_conflict_flag if run or private else None,
    )


def _rate(hits: int, denom: int) -> RateValue:
    if denom <= 0:
        return NOT_EVALUATED
    return hits / denom


def _bool_rate(flags: Sequence[bool | None]) -> RateValue:
    known = [flag for flag in flags if flag is not None]
    if not known:
        return NOT_EVALUATED
    return _rate(sum(1 for flag in known if flag), len(known))


def _status_rate(rows: Sequence[RuntimeObservation], status: str) -> RateValue:
    known = [row.status for row in rows if row.status != UNKNOWN]
    if not known:
        return NOT_EVALUATED
    return _rate(sum(1 for item in known if item == status), len(known))


def _cancelled_rate(rows: Sequence[RuntimeObservation]) -> RateValue:
    """Cancel is ``failed`` + ``stop_reason=cancelled`` (C1). Count the reason."""

    known = [
        row
        for row in rows
        if row.stop_reason != UNKNOWN or row.status == "cancelled"
    ]
    if not known:
        return NOT_EVALUATED
    hits = sum(
        1
        for row in known
        if row.stop_reason == "cancelled" or row.status == "cancelled"
    )
    return _rate(hits, len(known))


def _percentile(values: Sequence[float], p: float) -> RateValue:
    if not values:
        return NOT_EVALUATED
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (p / 100.0) * (len(ordered) - 1)
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _mean(values: Sequence[int]) -> RateValue:
    if not values:
        return NOT_EVALUATED
    return sum(values) / len(values)


def project_slo(observations: Sequence[RuntimeObservation]) -> dict[str, Any]:
    rows = tuple(observations)
    latencies = tuple(
        row.latency_seconds
        for row in rows
        if row.latency_seconds is not None
    )
    first_tool = tuple(
        row.time_to_first_tool
        for row in rows
        if row.time_to_first_tool is not None
    )
    llm = tuple(row.llm_calls for row in rows if row.llm_calls is not None)
    tools = tuple(row.tool_calls for row in rows if row.tool_calls is not None)
    late_flags = tuple(
        None if row.late_result_count is None else row.late_result_count > 0
        for row in rows
    )
    return {
        "n": len(rows),
        "dimensions": {
            name: sorted({getattr(row, name) for row in rows}) if rows else [UNKNOWN]
            for name in DIMENSIONS
        },
        "completion_rate": _status_rate(rows, "completed"),
        "partial_rate": _status_rate(rows, "partial"),
        "degraded_rate": _status_rate(rows, "degraded"),
        "failed_rate": _status_rate(rows, "failed"),
        "cancelled_rate": _cancelled_rate(rows),
        "p50_latency": _percentile(latencies, 50),
        "p95_latency": _percentile(latencies, 95),
        "p50_time_to_first_tool": _percentile(first_tool, 50),
        "p95_time_to_first_tool": _percentile(first_tool, 95),
        "repair_rate": _bool_rate(tuple(row.repaired for row in rows)),
        "cold_restart_rate": _bool_rate(tuple(row.cold_restart for row in rows)),
        "late_result_rate": _bool_rate(late_flags),
        "provider_error_rate": _bool_rate(
            tuple(row.provider_error for row in rows)
        ),
        "tool_error_rate": _bool_rate(tuple(row.tool_error for row in rows)),
        "semantic_verifier_unavailable_rate": _bool_rate(
            tuple(row.semantic_verifier_unavailable for row in rows)
        ),
        "average_llm_calls": _mean(llm),
        "average_tool_calls": _mean(tools),
        "budget_exhaustion_rate": _bool_rate(
            tuple(row.budget_exhausted for row in rows)
        ),
    }


def _check(
    name: str,
    ok: bool | None,
    detail: str,
) -> dict[str, str]:
    if ok is None:
        status = NOT_EVALUATED
    elif ok:
        status = "pass"
    else:
        status = "fail"
    return {"name": name, "status": status, "detail": detail}


def evaluate_release_gate(
    observations: Sequence[RuntimeObservation],
    *,
    expected_revision: str,
    regression_green: bool | None,
    canary_thresholds: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    """Offline/manual gate. Unknown measurements fail closed. No rollback."""

    rows = tuple(observations)
    slo = project_slo(rows)
    thresholds = dict(DEFAULT_CANARY_THRESHOLDS)
    if canary_thresholds:
        thresholds.update(
            {
                key: float(value)
                for key, value in canary_thresholds.items()
                if key in DEFAULT_CANARY_THRESHOLDS
                and isinstance(value, (int, float))
                and not isinstance(value, bool)
            }
        )
    expected = _text(expected_revision)
    revisions = {row.source_revision for row in rows}
    revision_ok: bool | None
    if not rows or expected == UNKNOWN:
        revision_ok = None
    else:
        revision_ok = revisions == {expected}

    identity_ok: bool | None
    if not rows:
        identity_ok = None
    else:
        identity_ok = all(
            row.runtime_backend != UNKNOWN
            and row.provider != UNKNOWN
            and row.model != UNKNOWN
            for row in rows
        )

    pairing_known = [row.tools_paired for row in rows if row.tools_paired is not None]
    pairing_ok: bool | None = None if not pairing_known else all(pairing_known)

    claim_known = [
        row.terminal_claim_conflict
        for row in rows
        if row.terminal_claim_conflict is not None
    ]
    claim_ok: bool | None = None if not claim_known else not any(claim_known)

    budget_known = [
        row.budget_exhausted for row in rows if row.budget_exhausted is not None
    ]
    # Exhaustion is a valid terminal; the gate asks that usage is accountable,
    # not that exhaustion never happens. Unevaluated budget fails closed.
    budget_ok: bool | None = None if not budget_known else True

    checks = [
        _check(
            "source_revision_matches_artifact",
            revision_ok,
            f"expected={expected} observed={sorted(revisions)}",
        ),
        _check(
            "runtime_identity_complete",
            identity_ok,
            "runtime_backend/provider/model must not be unknown",
        ),
        _check(
            "tool_request_result_paired",
            pairing_ok,
            "tool_request must have tool_result or tool_error",
        ),
        _check(
            "no_terminal_claim_conflict",
            claim_ok,
            "loser must not share the terminal claim",
        ),
        _check(
            "budget_usage_accountable",
            budget_ok,
            "stop_reason present so exhaustion is observable",
        ),
        _check(
            "deterministic_regression_green",
            regression_green,
            "caller supplies the pytest/receipt verdict",
        ),
    ]
    for field, ceiling in thresholds.items():
        value = slo[field]
        if value == NOT_EVALUATED:
            ok = None
            detail = f"{field}={NOT_EVALUATED}"
        else:
            ok = float(value) <= ceiling
            detail = f"{field}={value} ceiling={ceiling}"
        checks.append(_check(f"canary_{field}", ok, detail))

    passed = all(item["status"] == "pass" for item in checks)
    return {
        "passed": passed,
        "slo": slo,
        "checks": checks,
        "rollback": "manual",
    }
