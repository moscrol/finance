"""Choose existing research observations for bounded recovery; never mint facts."""

from __future__ import annotations

import json

from intelligence.services.agent_research import AgentEvidence

_SAMPLE_FIELDS = frozenset({
    "features", "sector", "stock", "comparison_state", "forward_return_pct",
    "feature_differences", "distance",
})


def recovery_evidence_priority(evidence: tuple[AgentEvidence, ...]) -> tuple[str, ...]:
    """Keep a recent sample's values, unknowns and definitions together.

    Query recency, not return sign or completeness, chooses the leading group.
    Empty catalog attempts cannot displace a later substantive observation.
    The runtime owns capacity, tool coverage and the full evidence ordinal table.
    """
    groups: dict[str, list[tuple[AgentEvidence, dict]]] = {}
    for item in evidence:
        if item.tool not in {"history_query", "read_history_result"} or not item.content_hash:
            continue
        try:
            value = json.loads(item.detail)
        except (TypeError, ValueError):
            continue
        if not isinstance(value, dict):
            continue
        identity = item.independent_key or item.internal_locator
        if identity:
            groups.setdefault(identity, []).append((item, value))

    result: list[str] = []

    def remember(rows):
        for item, _ in rows:
            if item.content_hash not in result:
                result.append(item.content_hash)

    for rows in reversed(tuple(groups.values())):
        samples = [(item, value) for item, value in rows if _SAMPLE_FIELDS.intersection(value)]
        if not samples:
            continue
        first = samples[0][1]
        identity_keys = ("sample", "entity_code", "trade_date", "start", "end", "role")
        bundle = [
            row for row in samples
            if all(row[1].get(key) == first.get(key) for key in identity_keys)
        ]
        # Preserve null/status cards alongside successful metrics of this sample.
        remember(bundle)
        features = {name for _, value in bundle for name in value.get("features", {})}
        remember(row for row in rows if row[1].get("feature") in features)
        remember(row for row in rows if any(key in row[1] for key in (
            "condition", "outcome_definition", "four_cells", "missing", "immature",
            "window_days", "matching_use", "operation", "pit_grade",
        )))
        remember(samples)
        remember(rows)
        if len(result) >= 12:
            break
    return tuple(result[:12])
