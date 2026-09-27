"""Advisory-only runtime receipt; no model, database, or publication effects."""

from __future__ import annotations

import hashlib
import os
from typing import Any

from intelligence.services.answer_claim_scope import (
    ClaimEvidenceContext,
    review_answer_claims,
    scope_comparison_needed,
)
from intelligence.services.claim_scope_context import build_context

ENV_CLAIM_SCOPE = "ASK_CLAIM_SCOPE_REVIEW"


def claim_scope_mode() -> str:
    """Only the authorized observation tier is executable."""
    return "advisory" if os.environ.get(ENV_CLAIM_SCOPE, "off") == "advisory" else "off"


def claim_scope_requested() -> bool:
    return os.environ.get(ENV_CLAIM_SCOPE, "off") != "off"


def review_runtime_claims(
    *,
    answer: str,
    question: str,
    episode: dict[str, Any],
    scope_total: int | None = None,
    mapping_limits: tuple[str, ...] = (),
) -> dict[str, Any] | None:
    raw = os.environ.get(ENV_CLAIM_SCOPE, "off")
    if raw == "off":
        return None
    if raw != "advisory":
        key = "claim_scope_mode_unsupported" if raw in {"revise", "block"} else "claim_scope_mode_invalid"
        return {"mode": "off", key: raw}
    try:
        context, diagnostics = build_context({"question": question}, episode, scope_total)
    except (AttributeError, TypeError, ValueError) as exc:
        context = ClaimEvidenceContext(question=question, known_scope_total=scope_total)
        diagnostics = {"degraded": [f"context_mapping_failed:{type(exc).__name__}"]}
    degraded = list(diagnostics["degraded"])
    if scope_comparison_needed(answer):
        if scope_total is None:
            degraded.append("scope_total_not_provided")
        if context.compared_scope_count is None and not diagnostics["degraded"]:
            degraded.append("compared_scope_count_unavailable")
    degraded.extend(mapping_limits)
    diagnostics["degraded"] = list(dict.fromkeys(degraded))
    report = review_answer_claims(answer, context).to_dict()
    return {
        "mode": "advisory",
        **report,
        "clean": report["clean"] and not diagnostics["degraded"],
        "degraded": diagnostics["degraded"],
        "context_diagnostics": diagnostics,
        "answer_sha256": hashlib.sha256(answer.encode("utf-8")).hexdigest(),
        "checks": [
            {
                "name": "口径越界·" + issue["label"],
                "status": "WARN",
                "note": issue["quote"] + "——" + issue["reason"],
                "advisory_only": True,
            }
            for issue in report["issues"]
        ] + ([{
            "name": "口径越界·判据降级",
            "status": "WARN",
            "note": "; ".join(diagnostics["degraded"]),
            "advisory_only": True,
        }] if diagnostics["degraded"] else []),
    }
