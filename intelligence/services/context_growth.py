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

Two readings need two kind sets.  ``agent_episode._token_usage_from_events``
counts both ``model_turn`` and ``branch_completed`` because a token *bill* pays
for sub-agent calls too.  A context-*size* reading must not: a branch runs in an
isolated context (layer 0 of the layered-rebuild roadmap), so its tokens never
enter the parent's window.  Counting them here would let a sub-agent aggregate
(``SubResearchResult.input_tokens`` is a sum over up to
``MAX_CALLS_PER_BRANCH`` calls per branch) masquerade as one parent turn,
inflating ``max_turn_input_tokens``, skewing ``growth_ratio``, and reading
branch count as turn count — all while ``provenance`` still claims
``per_turn``.  Sub-agent tokens are therefore reported in their own field with
its own provenance, never merged into ``per_turn_input_tokens``.

Observation only.  Nothing here gates delivery or resizes a budget; Phase 1 of
the layered-rebuild roadmap is explicitly 先量后改, and there is no distribution
yet to size a compaction policy against.
"""

from __future__ import annotations

from typing import Any, Iterable, Literal, Mapping

ContextProvenance = Literal["per_turn", "run_aggregated", "unavailable"]
SubAgentProvenance = Literal["branch_aggregated", "unavailable"]

# Kinds that carry one provider call each, so their token counts are per-turn.
# Deliberately excludes ``branch_completed``: see the module docstring.
PER_TURN_EVENT_KINDS = frozenset({"model_turn"})
# Kinds whose tokens were spent in an isolated sub-agent context, already summed
# across that branch's calls.  Billable, but never part of the parent window.
SUB_AGENT_EVENT_KINDS = frozenset({"branch_completed"})
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
    sub_agent: list[int] = []
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
        if kind in SUB_AGENT_EVENT_KINDS:
            value = _count(payload.get("input_tokens"))
            if value is not None:
                sub_agent.append(value)
            continue
        if kind in RUN_AGGREGATE_EVENT_KINDS:
            value = _count(payload.get("input_tokens"))
            if value is None:
                continue
            run_totals.append(value)
            attempts = _count(payload.get("provider_attempts"))
            run_requests.append(attempts if attempts else 1)

    # Reported alongside every reading, never folded into it.  ``branch_count``
    # is a branch count, not a turn count.
    sub_agent_reading: dict[str, object] = {
        "sub_agent_provenance": "branch_aggregated" if sub_agent else "unavailable",
        "sub_agent_branch_count": len(sub_agent),
        "sub_agent_input_tokens": sum(sub_agent) if sub_agent else None,
    }

    if per_turn:
        return {
            **sub_agent_reading,
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
            **sub_agent_reading,
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
        **sub_agent_reading,
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
    "SUB_AGENT_EVENT_KINDS",
    "ContextProvenance",
    "SubAgentProvenance",
    "summarize_context_growth",
]
