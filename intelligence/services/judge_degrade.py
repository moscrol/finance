"""Split degrade into ``judge_unavailable`` vs ``content_degraded``.

W2 Phase 1. Names match W3 ``gate_receipt`` counters so a later merge is
additive. Ask-engine ``not_applicable`` is not a judge outage (W7 trap).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

NOT_APPLICABLE = "not_applicable"
JUDGE_UNAVAILABLE = "judge_unavailable"
CONTENT_DEGRADED = "content_degraded"


def classify_degrade_counts(
    *,
    judge_status: str | None,
    extra_degrade_count: int = 0,
    exc_class: str | None = None,
    timeout_asked: float | None = None,
) -> tuple[int, int]:
    """Return ``(judge_unavailable_count, content_degraded_count)``.

    Rules:
    * ``not_applicable`` never increments the judge class.
    * ``judge_status == "unavailable"`` (with or without timeout/exc) is
      ``judge_unavailable``.
    * Any remaining degrade count is ``content_degraded``.
    """

    del exc_class, timeout_asked  # kept for W3-compatible call sites
    extra = max(0, int(extra_degrade_count))
    if judge_status == NOT_APPLICABLE:
        return 0, extra
    judge_count = 1 if judge_status == "unavailable" else 0
    if judge_count and extra:
        extra = max(0, extra - 1)
    return judge_count, extra


def degrade_class_for_status(judge_status: str | None) -> str | None:
    if judge_status == "unavailable":
        return JUDGE_UNAVAILABLE
    return None


def extract_judge_status(*payloads: Mapping[str, Any] | None) -> str | None:
    """Read judge_status from report / summary / semantic artifact shapes."""

    paths = (
        ("judge_status",),
        ("semantic_verifier", "judge_status"),
        ("gate_receipt", "judge_status"),
        ("private_artifact", "judge_status"),
        ("private_artifact", "semantic_verifier", "judge_status"),
    )
    for payload in payloads:
        if not isinstance(payload, Mapping):
            continue
        for path in paths:
            current: Any = payload
            for key in path:
                if not isinstance(current, Mapping):
                    current = None
                    break
                current = current.get(key)
            if isinstance(current, str) and current:
                return current
    return None


def split_degrade_from_payloads(
    degrades: Any,
    *payloads: Mapping[str, Any] | None,
) -> dict[str, int]:
    extra = len(degrades) if isinstance(degrades, list) else 0
    judge_status = extract_judge_status(*payloads)
    semantic = None
    for payload in payloads:
        if isinstance(payload, Mapping):
            block = payload.get("semantic_verifier")
            if isinstance(block, Mapping):
                semantic = block
                break
    ju, cd = classify_degrade_counts(
        judge_status=judge_status,
        extra_degrade_count=extra,
        exc_class=(
            str(semantic.get("exc_class"))
            if isinstance(semantic, Mapping) and semantic.get("exc_class")
            else None
        ),
        timeout_asked=(
            float(semantic["timeout_asked"])
            if isinstance(semantic, Mapping)
            and isinstance(semantic.get("timeout_asked"), (int, float))
            else None
        ),
    )
    return {
        "judge_unavailable_count": ju,
        "content_degraded_count": cd,
    }
