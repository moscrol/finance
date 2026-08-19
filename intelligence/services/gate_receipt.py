"""Unified gate_receipt block for ask and episode persisted artifacts.

Failure shape this module closes: ``POST /api/runs`` (ask) and
``POST /api/conversations`` (episode) wrote differently shaped reports, so
``live_probe`` and ``smoke_workbench_self_use`` could not be compared
side-by-side.  Both engines now stamp the same key set; a dict diff on
``gate_receipt`` is the comparison.

W1 will later code-ify ``issues[]`` into ``IssueCode`` entries.  Until that
lands, issues remain strings.  Do not wait for W1 and do not invent enums
here.

Ask has no structural verifier and no semantic judge.  Callers must pass
``not_applicable`` (or JSON null) for those fields — never fake
``verified_status=completed`` or ``judge_status=passed``.

``correlated_judge`` is L6 observation, not a delivery status.  Episode
copies the semantic verifier's bool when present; missing / ask / junk
stay JSON null.  Never write ``false`` to mean "ask has no judge" —
that would look like an independent judge ran.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from intelligence.services.judge_degrade import (
    classify_degrade_counts as classify_degrade_counts_canonical,
)
from intelligence.services.runtime_provenance import _git_output

SCHEMA_VERSION = 1
ENGINE_ASK = "ask"
ENGINE_EPISODE = "episode"
NOT_APPLICABLE = "not_applicable"

# Frozen key order so a dict diff is stable across engines.
RECEIPT_KEYS = (
    "schema_version",
    "engine",
    "rev",
    "verified_status",
    "judge_status",
    "issues",
    "judge_unavailable_count",
    "content_degraded_count",
    "timings",
    "correlated_judge",
)
TIMING_KEYS = (
    "elapsed_seconds",
    "retrieve_seconds",
    "judge_seconds",
    "timeout_asked",
)
TABLE_COLUMNS = (
    "engine",
    "rev",
    "verified_status",
    "judge_status",
    "issue_count",
    "judge_unavailable_count",
    "content_degraded_count",
    "elapsed_seconds",
    "retrieve_seconds",
    "judge_seconds",
    "correlated_judge",
)

_VERIFIED_STATUSES = frozenset(
    {"completed", "partial", "clarification", "failed", NOT_APPLICABLE}
)
_JUDGE_STATUSES = frozenset(
    {"passed", "repaired", "rejected", "unavailable", NOT_APPLICABLE}
)
_REV_CACHE: dict[str, str] = {}


def source_revision(code_root: Path | str | None = None) -> str:
    """Cheap ``git rev-parse HEAD`` (not the full provenance tree walk)."""

    root = (
        Path(code_root).expanduser().resolve()
        if code_root is not None
        else Path(__file__).resolve().parents[2]
    )
    key = str(root)
    cached = _REV_CACHE.get(key)
    if cached is not None:
        return cached
    revision = _git_output(root, "rev-parse", "HEAD") or "unknown"
    _REV_CACHE[key] = revision
    return revision


def normalize_timings(raw: Mapping[str, Any] | None) -> dict[str, float | None]:
    timings: dict[str, float | None] = {key: None for key in TIMING_KEYS}
    if not isinstance(raw, Mapping):
        return timings
    for key in TIMING_KEYS:
        value = raw.get(key)
        if isinstance(value, bool) or value is None:
            continue
        if isinstance(value, (int, float)):
            timings[key] = float(value)
    return timings


def classify_degrade_counts(
    *,
    judge_status: str | None,
    exc_class: str | None,
    timeout_asked: float | None,
    extra_degrade_count: int,
) -> tuple[int, int]:
    """Same buckets as W2 ``judge_degrade.classify_degrade_counts``.

    Only explicit ``judge_status == "unavailable"`` increments the judge
    class. Missing status plus timeout/exc is not an outage: production
    writes ``unavailable`` when the provider actually failed. Ask uses
    ``not_applicable`` and never increments the judge class.
    """

    return classify_degrade_counts_canonical(
        judge_status=judge_status,
        extra_degrade_count=extra_degrade_count,
        exc_class=exc_class,
        timeout_asked=timeout_asked,
    )


def optional_bool(value: object) -> bool | None:
    """Only a real bool counts. Missing / strings / 0 stay unknown."""

    return value if isinstance(value, bool) else None


def _issues_list(issues: Sequence[object] | None) -> list[str]:
    out: list[str] = []
    if not issues:
        return out
    for item in issues:
        if isinstance(item, str) and item:
            out.append(item)
    return out


def build_gate_receipt(
    *,
    engine: str,
    rev: str,
    verified_status: str | None,
    judge_status: str | None,
    issues: Sequence[str] | None = None,
    extra_degrade_count: int = 0,
    timings: Mapping[str, Any] | None = None,
    judge_exc_class: str | None = None,
    timeout_asked: float | None = None,
    correlated_judge: bool | None = None,
) -> dict[str, Any]:
    """Single builder.  Both engines call this; do not fork the key set."""

    if engine not in {ENGINE_ASK, ENGINE_EPISODE}:
        raise ValueError(f"unknown gate_receipt engine: {engine!r}")
    if verified_status is not None and verified_status not in _VERIFIED_STATUSES:
        raise ValueError(f"unknown verified_status: {verified_status!r}")
    if judge_status is not None and judge_status not in _JUDGE_STATUSES:
        raise ValueError(f"unknown judge_status: {judge_status!r}")
    correlated = optional_bool(correlated_judge)
    if engine == ENGINE_ASK:
        if verified_status in {"completed", "partial", "clarification", "failed"}:
            raise ValueError("ask engine must not fake a structural verified_status")
        if judge_status in {"passed", "repaired", "rejected", "unavailable"}:
            raise ValueError("ask engine must not fake a semantic judge_status")
        if correlated is not None:
            raise ValueError("ask engine must not fake a correlated_judge")
        verified_status = verified_status if verified_status is not None else NOT_APPLICABLE
        judge_status = judge_status if judge_status is not None else NOT_APPLICABLE

    normalized_timings = normalize_timings(timings)
    asked = timeout_asked
    if asked is None:
        asked = normalized_timings.get("timeout_asked")
    elif normalized_timings.get("timeout_asked") is None:
        normalized_timings["timeout_asked"] = float(asked)

    judge_count, content_count = classify_degrade_counts(
        judge_status=judge_status,
        exc_class=judge_exc_class,
        timeout_asked=asked,
        extra_degrade_count=extra_degrade_count,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "engine": engine,
        "rev": rev or "unknown",
        "verified_status": verified_status,
        "judge_status": judge_status,
        "issues": _issues_list(issues),
        "judge_unavailable_count": judge_count,
        "content_degraded_count": content_count,
        "timings": normalized_timings,
        "correlated_judge": correlated,
    }


def build_ask_receipt(
    *,
    rev: str,
    issues: Sequence[str] | None = None,
    extra_degrade_count: int = 0,
    timings: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return build_gate_receipt(
        engine=ENGINE_ASK,
        rev=rev,
        verified_status=NOT_APPLICABLE,
        judge_status=NOT_APPLICABLE,
        issues=issues,
        extra_degrade_count=extra_degrade_count,
        timings=timings,
    )


def _as_mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def build_episode_receipt(
    *,
    rev: str,
    private_artifact: Mapping[str, Any] | None = None,
    extra_degrade_count: int = 0,
    timings: Mapping[str, Any] | None = None,
    issues: Sequence[str] | None = None,
) -> dict[str, Any]:
    artifact = _as_mapping(private_artifact)
    structural = _as_mapping(artifact.get("structural_verifier"))
    semantic = _as_mapping(artifact.get("semantic_verifier"))

    verified = structural.get("verified_status")
    if verified not in _VERIFIED_STATUSES:
        verified = NOT_APPLICABLE

    if semantic:
        judge = semantic.get("judge_status")
        if judge not in _JUDGE_STATUSES:
            judge = None
    else:
        judge = NOT_APPLICABLE

    merged_issues = list(issues or ())
    merged_issues.extend(_issues_list(structural.get("issues")))
    merged_issues.extend(_issues_list(semantic.get("issues")))

    exc_class = semantic.get("exc_class")
    timeout_asked = semantic.get("timeout_asked")
    asked: float | None = None
    if isinstance(timeout_asked, (int, float)) and not isinstance(timeout_asked, bool):
        asked = float(timeout_asked)

    merged_timings = dict(timings or {})
    if merged_timings.get("timeout_asked") is None and asked is not None:
        merged_timings["timeout_asked"] = asked

    return build_gate_receipt(
        engine=ENGINE_EPISODE,
        rev=rev,
        verified_status=str(verified),
        judge_status=judge if isinstance(judge, str) or judge is None else NOT_APPLICABLE,
        issues=merged_issues,
        extra_degrade_count=extra_degrade_count,
        timings=merged_timings,
        judge_exc_class=str(exc_class) if exc_class else None,
        timeout_asked=asked,
        correlated_judge=optional_bool(semantic.get("correlated_judge")),
    )


def empty_receipt() -> dict[str, Any]:
    """Same keys as a real receipt; used when an old artifact lacks the block."""

    return {
        "schema_version": SCHEMA_VERSION,
        "engine": None,
        "rev": None,
        "verified_status": None,
        "judge_status": None,
        "issues": [],
        "judge_unavailable_count": None,
        "content_degraded_count": None,
        "timings": normalize_timings(None),
        "correlated_judge": None,
    }


def extract_gate_receipt(*payloads: Mapping[str, Any] | None) -> dict[str, Any]:
    """Read ``gate_receipt`` from report.json and/or summary.json payloads."""

    for payload in payloads:
        if not isinstance(payload, Mapping):
            continue
        block = payload.get("gate_receipt")
        if isinstance(block, Mapping):
            return _normalize_extracted(block)
    return empty_receipt()


def _normalize_extracted(block: Mapping[str, Any]) -> dict[str, Any]:
    issues = _issues_list(block.get("issues") if isinstance(block.get("issues"), list) else None)
    timings = normalize_timings(
        block.get("timings") if isinstance(block.get("timings"), Mapping) else None
    )
    return {
        "schema_version": block.get("schema_version", SCHEMA_VERSION),
        "engine": block.get("engine"),
        "rev": block.get("rev"),
        "verified_status": block.get("verified_status"),
        "judge_status": block.get("judge_status"),
        "issues": issues,
        "judge_unavailable_count": block.get("judge_unavailable_count"),
        "content_degraded_count": block.get("content_degraded_count"),
        "timings": timings,
        "correlated_judge": optional_bool(block.get("correlated_judge")),
    }


def table_row(receipt: Mapping[str, Any] | None) -> dict[str, Any]:
    """Same table shape for live_probe and smoke_workbench_self_use."""

    block = _normalize_extracted(receipt) if isinstance(receipt, Mapping) else empty_receipt()
    timings = block["timings"] if isinstance(block.get("timings"), Mapping) else {}
    issues = block.get("issues") if isinstance(block.get("issues"), list) else []
    return {
        "engine": block.get("engine"),
        "rev": block.get("rev"),
        "verified_status": block.get("verified_status"),
        "judge_status": block.get("judge_status"),
        "issue_count": len(issues),
        "judge_unavailable_count": block.get("judge_unavailable_count"),
        "content_degraded_count": block.get("content_degraded_count"),
        "elapsed_seconds": timings.get("elapsed_seconds"),
        "retrieve_seconds": timings.get("retrieve_seconds"),
        "judge_seconds": timings.get("judge_seconds"),
        "correlated_judge": optional_bool(block.get("correlated_judge")),
    }


def attach_gate_receipt(payload: dict[str, Any], receipt: Mapping[str, Any]) -> dict[str, Any]:
    payload["gate_receipt"] = dict(receipt)
    return payload
