"""Public source meanings, separate from evidence, authority and result ownership.

Only source owners supply these fields. A missing envelope stays missing; prose,
counter names and a successful transport cannot create calculation eligibility.
"""

from collections.abc import Mapping
import json

from intelligence.services.provider_observability import provider_result_error


SCHEMA = "research_source_context_v1"
_FIELDS = frozenset({
    "schema", "role", "result_status", "execution_scope", "metric_semantics",
    "qualifications", "method_sources",
})


def source_context(
    *, role: str, status: str, execution_scope: Mapping[str, object],
    metric_semantics: Mapping[str, object], method_sources: tuple[dict[str, str], ...] = (),
) -> dict[str, object]:
    """Build an informational envelope without certifying any derived claim."""
    return copy_source_context({
        "schema": SCHEMA,
        "role": role,
        "result_status": status,
        "execution_scope": dict(execution_scope),
        "metric_semantics": dict(metric_semantics),
        "qualifications": {
            "calendar_continuity": "unknown",
            "unique_stock_count": "unknown",
            "group_disjointness": "unknown",
            "concentration_from_group_sum": "unknown",
            "index_contribution": "unknown",
            "capital_cause": "unknown",
        },
        "method_sources": list(method_sources),
    }, status=status)


def copy_source_context(value: Mapping[str, object], *, status: str) -> dict[str, object]:
    """Copy safe JSON; legacy/unknown schemas acquire no inferred qualification."""
    if not value or value.get("schema") != SCHEMA:
        return {}
    if set(value) - _FIELDS:
        raise ValueError("source context contains undeclared public fields")
    # Deep-copy rather than retaining a producer's mutable nested values. JSON
    # rejects physical Python objects and non-finite numeric pseudo-values.
    copied = json.loads(json.dumps(dict(value), ensure_ascii=False, allow_nan=False))
    copied["result_status"] = (
        "unknown_provider_status" if provider_result_error(status) == "unknown_provider_status" else status
    )
    return copied
