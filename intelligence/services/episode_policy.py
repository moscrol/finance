"""Deterministic scheduling policy for one continuous research episode."""

from __future__ import annotations


_QUESTION_TOOL_PRIORITY: dict[str, tuple[str, ...]] = {
    "valuation_estimate": (
        "market_data",
        "financial_data",
        "l3_lookup",
        "evidence_lookup",
        "kb_search",
        "graph_lookup",
        "news_search",
        "web_search",
    ),
}


def tool_priority(
    question_type: str,
    mandatory: tuple[str, ...],
) -> tuple[str, ...]:
    """Return mandatory capabilities first, then canonical question policy."""

    return tuple(
        dict.fromkeys((*mandatory, *_QUESTION_TOOL_PRIORITY.get(question_type, ())))
    )


__all__ = ["tool_priority"]
