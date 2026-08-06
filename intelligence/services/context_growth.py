"""Per-turn context growth observation for agent episodes.

Why this exists as its own reading instead of reusing ``AgentUsage``:
``AgentUsage.input_tokens`` sums the input tokens of every model turn.  An
agent loop resends the whole history each turn, so that sum is neither the
context size nor a token bill — turn 1's 30K plus turn 2's 45K is 75K, while
the context never exceeded 45K.  The number that answers "how close are we to
the window" is the **maximum single turn**, and the number that answers "is it
growing" is the per-turn sequence.  Both are lost by addition.

Provenance is a first-class field because the answer differs by backend, and
that difference is structural rather than a defect:

- ``continuous_glm`` runs the loop inside ``agent_episode``, which records one
  ``model_turn`` event per provider call.  Per-turn values are exact.
- ``sdk_glm`` / ``sdk_gpt`` hand the loop to the OpenAI Agents SDK.  At the
  adapter boundary only ``context_wrapper.usage`` is visible, and that object
  has already summed the SDK's internal turns (``usage.requests`` may exceed
  1).  Per-turn values are unavailable; a mean is the best honest reduction.

Collapsing those two into one field would make a coarse backend look identical
to a precise one.  That is the same failure mode as reporting "no marker
vocabulary" as "answer missing the slot": an instrument gap read as a finding.

Observation only.  Nothing here gates delivery or resizes a budget; Phase 1 of
the layered-rebuild roadmap is explicitly 先量后改, and there is no distribution
yet to size a compaction policy against.
"""

from __future__ import annotations

from typing import Any, Iterable, Literal, Mapping

ContextProvenance = Literal["per_turn", "run_aggregated", "unavailable"]

# Kinds that carry one provider call each, so their token counts are per-turn.
PER_TURN_EVENT_KINDS = frozenset({"model_turn", "branch_completed"})
# Kinds that carry a whole runtime run, already summed by the provider SDK.
RUN_AGGREGATE_EVENT_KINDS = frozenset({"runtime_result"})


def _event_kind(event: object) -> str:
    if isinstance(event, Mapping):
        return str(event.get("kind") or "")
    return str(getattr(event, "kind", "") or "")


def _event_payload(event: object) -> Mapping[str, Any]:
    raw = (
        event.get("payload")
        if isinstance(event, Mapping)
        else getattr(event, "payload", None)
    )
    return raw if isinstance(raw, Mapping) else {}


def _count(value: object) -> int | None:
    """Accept only real non-negative ints; ``bool`` is not a token count."""

    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if value >= 0 else None


def summarize_context_growth(events: Iterable[object]) -> dict[str, object]:
    """Reduce an episode's events into a context-size reading.

    Accepts either ``EpisodeEvent`` objects or the plain dicts stored in the
    private episode artifact, so the same reading can be taken at the adapter
    boundary or later from a persisted run.
    """

    per_turn: list[int] = []
    run_totals: list[int] = []
    run_requests: list[int] = []
    for event in events:
        kind = _event_kind(event)
        payload = _event_payload(event)
        if kind in PER_TURN_EVENT_KINDS:
            value = _count(payload.get("input_tokens"))
            if value is not None:
                per_turn.append(value)
            continue
        if kind in RUN_AGGREGATE_EVENT_KINDS:
            value = _count(payload.get("input_tokens"))
            if value is None:
                continue
            run_totals.append(value)
            attempts = _count(payload.get("provider_attempts"))
            run_requests.append(attempts if attempts else 1)

    if per_turn:
        return {
            "provenance": "per_turn",
            "turn_count": len(per_turn),
            "per_turn_input_tokens": list(per_turn),
            # The window-pressure number: the largest single request, not the sum.
            "max_turn_input_tokens": max(per_turn),
            # Kept and named as cumulative so it is never read as context size.
            "cumulative_input_tokens": sum(per_turn),
            # Whether context is still growing at the end of the episode.
            "growth_ratio": (
                round(per_turn[-1] / per_turn[0], 3)
                if len(per_turn) >= 2 and per_turn[0] > 0
                else None
            ),
            "observation_only": True,
        }

    if run_totals:
        total = sum(run_totals)
        turns = sum(run_requests)
        return {
            "provenance": "run_aggregated",
            # Provider-reported request count, not a harness-observed turn list.
            "turn_count": turns,
            "per_turn_input_tokens": None,
            # Unknown, and deliberately not guessed: the max is somewhere
            # between the mean and the total, and the SDK does not say where.
            "max_turn_input_tokens": None,
            "cumulative_input_tokens": total,
            "mean_turn_input_tokens": (total // turns) if turns > 0 else None,
            "growth_ratio": None,
            "observation_only": True,
        }

    return {
        "provenance": "unavailable",
        "turn_count": 0,
        "per_turn_input_tokens": None,
        "max_turn_input_tokens": None,
        "cumulative_input_tokens": None,
        "growth_ratio": None,
        "observation_only": True,
    }


__all__ = [
    "PER_TURN_EVENT_KINDS",
    "RUN_AGGREGATE_EVENT_KINDS",
    "ContextProvenance",
    "summarize_context_growth",
]
