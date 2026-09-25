"""Budget one tool observation before it enters the model's context.

This is layer 1 of the layered compaction design (see the roadmap's Phase 1
notes): large tool output is persisted in full, and the context keeps a bounded
preview plus a pointer back to the full record.

The precondition already holds here, which is why this layer is cheap for us:
``_EpisodeAccumulator`` hands the same ``public_observation`` to two sinks.

    ledger.add("tool_result", payload)   → continuous-episode.json  (audit)
    messages.append({"role": "tool"})    → the model's context      (budgeted)

So the full observation is already durable.  Only the context copy needs a
bound, and only the *prose* inside it: truncating identifiers would turn
compaction into evidence destruction.

Never truncated, because the roadmap's red line requires 来源 / 时点 / 状态 /
缺口 / 完整性 to survive any compaction:

- ``evidence_hashes`` and each item's ``content_hash`` — the model must put
  these into its output bindings at finalize time.  Dropping one does not make
  the answer shorter, it makes the binding gate unsatisfiable.
- ``source`` / ``source_date`` / ``freshness`` / ``evidence_tier`` — a claim
  without its time and tier is not a shorter claim, it is a different one.
- ``gaps`` — the thing the answer must disclose.
- ``supports`` / ``contradicts`` — dropping a contradiction silently upgrades
  a contested finding into a clean one.

Truncated: the free-text ``observation`` narrative and each evidence item's
``title`` / ``detail``.  Those are recoverable from the persisted artifact.

Deterministic on purpose.  The reduction is a pure function of its input, with
no model call, clock, or randomness, so the same observation always yields the
same bytes.  A provider's prompt cache keys on the exact prefix; a preview that
varied per call would invalidate the cache on every resume and cost more than
the tokens it saved.
"""

from __future__ import annotations

from typing import Any, Mapping

# Matches ``agent_research._MAX_OBSERVATION_CHARS`` so the two engines bound
# their context the same way.  Engine B has had this cap for a while; Engine A
# (the production research path) had none, which is the asymmetry this fixes.
MAX_OBSERVATION_CHARS = 900
MAX_EVIDENCE_DETAIL_CHARS = 240
MAX_EVIDENCE_TITLE_CHARS = 120

# Where a reader can recover what was elided.  Named, not a bare "truncated"
# flag: "there was more" without "and here is where it is" is not auditable.
FULL_RECORD_ARTIFACT = "continuous-episode.json"

_ELLIPSIS = "…"


def _clip(value: object, limit: int) -> tuple[object, int]:
    """Return the clipped value and how many characters were dropped.

    A non-``str`` value passes through untouched rather than becoming ``""``.
    Coercing it would delete data while reporting ``omitted_chars == 0``, so no
    ``context_budget`` marker would be attached and the model could not tell the
    field had been emptied — the exact failure this module exists to prevent.
    Same pass-through rule as a non-``Mapping`` evidence item.
    """

    if not isinstance(value, str):
        return value, 0
    text = value
    if len(text) <= limit:
        return text, 0
    # Reserve one character for the marker so the result never exceeds ``limit``
    # and a reader can see the value is partial without consulting metadata.
    kept = max(0, limit - 1)
    return text[:kept] + _ELLIPSIS, len(text) - kept


def budget_tool_observation(
    payload: Mapping[str, Any],
    *,
    max_observation_chars: int = MAX_OBSERVATION_CHARS,
    max_detail_chars: int = MAX_EVIDENCE_DETAIL_CHARS,
    max_title_chars: int = MAX_EVIDENCE_TITLE_CHARS,
) -> dict[str, Any]:
    """Bound the prose in one tool observation, preserving every identifier.

    Returns a new dict; the input is never mutated, so the caller can keep
    handing the untouched payload to its audit sink.

    When nothing exceeded its bound the result carries no completeness
    metadata, so an unbudgeted observation stays byte-identical to what the
    model saw before this layer existed.
    """

    budgeted = dict(payload)
    omitted_chars = 0

    observation, dropped = _clip(payload.get("observation"), max_observation_chars)
    omitted_chars += dropped
    if "observation" in payload:
        budgeted["observation"] = observation

    raw_evidence = payload.get("evidence")
    if isinstance(raw_evidence, list):
        items: list[Any] = []
        for item in raw_evidence:
            if not isinstance(item, Mapping):
                items.append(item)
                continue
            projected = dict(item)
            title, title_dropped = _clip(item.get("title"), max_title_chars)
            detail, detail_dropped = _clip(item.get("detail"), max_detail_chars)
            omitted_chars += title_dropped + detail_dropped
            if "title" in item:
                projected["title"] = title
            if "detail" in item:
                projected["detail"] = detail
            items.append(projected)
        budgeted["evidence"] = items

    if omitted_chars:
        # Tell the model it is reading a preview and that the elision was prose
        # only.  Without this it cannot distinguish "the tool found little" from
        # "the harness showed me little", and may re-run the same query.
        budgeted["context_budget"] = {
            "truncated": True,
            "omitted_chars": omitted_chars,
            "full_record_in": FULL_RECORD_ARTIFACT,
            "preserved": [
                "evidence_hashes",
                "content_hash",
                "source",
                "source_date",
                "evidence_tier",
                "freshness",
                "supports",
                "contradicts",
                "gaps",
            ],
            "instruction": (
                "叙述已按上下文预算截断，标识与证据哈希均完整。"
                "不要因为叙述变短而重复同一次查询；"
                "需要完整原文时以 evidence_hashes 为准。"
            ),
        }

    return budgeted


__all__ = [
    "FULL_RECORD_ARTIFACT",
    "MAX_EVIDENCE_DETAIL_CHARS",
    "MAX_EVIDENCE_TITLE_CHARS",
    "MAX_OBSERVATION_CHARS",
    "budget_tool_observation",
]
