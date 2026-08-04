"""Normalize heterogeneous harness events into the shared nine-step L1 profile.

The normalizer is intentionally deterministic and lossy.  It keeps enough
control-plane information to compare ordering and first divergence, while
discarding prompts, answers, command arguments, paths, and provider secrets.
Unknown events remain ``unmapped`` instead of being guessed into a semantic
step.

Two CLI shapes, both from the repository root (the package is imported as
``intelligence.eval.…``, so a different cwd needs ``PYTHONPATH`` set):

* one input  -> a single normalized artifact (``events`` + counts);
* ``--compare`` -> both sides plus a ``comparison`` block carrying
  ``pre_divergence_equivalence`` / ``first_divergence_step`` /
  ``first_divergence``.  Those values exist only in :func:`compare_sequences`;
  without this entry point a caller reading the single-input artifact finds no
  such fields and is tempted to invent them.

Either side may itself be a single-input artifact of this module: it is detected
by ``schema_version`` and reused as-is.  A v1 artifact or a foreign vocabulary
raises :class:`NormalizedArtifactError` instead of being re-fed through the raw
mapper, which would silently map every event to ``unmapped``.

Divergence contract (see :class:`FirstDivergence`): a mismatch carries a step on
*each* side, so the scalar ``first_divergence_step`` is ``null`` there and the
structured object must be read.  Only a strict-prefix divergence, where the extra
step exists on one side alone, keeps a scalar value.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

#: The shared step vocabulary is the ``agent-run-triage`` skill's fixed L1
#: pipeline, so a triage report's ``first_bad_step`` and this module's
#: ``first_divergence_step`` live in the same space and can be joined by
#: ``finding_id``.  Do not shorten it locally: dropping ``plan``/``tool`` (as
#: vocabulary v1 did) silently collapses two distinct L1 boundaries -- "did it
#: form the right steps" and "did it call the right tool correctly" -- into
#: ``route``/``retrieve``, and makes an L1=``tool`` finding inexpressible here.
VOCABULARY = "triage-l1-9"
_ARTIFACT_SCHEMA = "normalized-harness-trace-2"
STEPS = (
    "configure",
    "intent",
    "plan",
    "route",
    "retrieve",
    "tool",
    "observe",
    "synthesize",
    "stop",
)
KINDS = (
    "auto",
    "codex-rollout",
    "codex-exec",
    "workbench-trace",
    "runtime-benchmark",
)

_SAFE_TOKEN = re.compile(r"^[A-Za-z0-9_.:/-]{1,80}$")
_SAFE_TIMESTAMP_TEXT = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?$"
)
_TOKEN_LIKE = re.compile(r"(?i)(?:^sk-|^gh[pousr]_|^xox[a-z]-|^eyJ|^[^.\s]+\.[^.\s]+\.[^.\s]+$)")
_ABSOLUTE_PATH = re.compile(r"(?:^|[\s=(])(?:/Users/|/home/|/tmp/|/var/|[A-Za-z]:[\\/])")
#: ``C:/...`` / ``C:\...`` -- drive-qualified, i.e. a path, not an identity.
#: Used only by :func:`_safe_case_id`; ``_ABSOLUTE_PATH`` needs a leading
#: boundary and so misses a drive letter at position 0.
_WINDOWS_DRIVE = re.compile(r"^[A-Za-z]:[\\/]")
_SECRET = re.compile(
    r"(?i)(?:api[_-]?key|token|cookie|authorization|bearer|jwt|secret|password)"
    r"\s*[:=]\s*[^\s,;]+"
)
# Tool *results* in the rollout schema.  These must be tested before the tool
# *request* terms, because ``function_call_output`` also contains
# ``function_call``.  ``output_text`` is message content, not an observation,
# so match ``_call_output`` rather than a bare ``output``.
_CODEX_OBSERVE_TERMS = (
    "_call_output",
    "command_execution_output",
    "tool_output",
    "tool_result",
)

# Value domains for *our own* artifact, used when an artifact is fed back in via
# ``--compare``.  Reuse skips the mapper, so it also skips the mapper's
# sanitizers; without these the artifact path is a hole in the redaction
# guarantee documented in ``docs/trace-profile.md`` §6.  These are producer
# contracts, not guesses: each value below is one the mapper can actually emit.
_PROVENANCES = ("native", "normalized", "unmapped")
_EVENT_ROLES = ("control", "tool", "generation", "unknown")
_SOURCE_KINDS = tuple(kind for kind in KINDS if kind != "auto")
#: ``source_event_id`` may be a ``case_id:id`` composite truncated to 100 chars,
#: so it is wider than :data:`_SAFE_TOKEN` -- but not less strict per character.
_ARTIFACT_EVENT_ID = re.compile(r"^[A-Za-z0-9_.:/-]{1,100}$")
_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
_MAX_SUMMARY = 240


@dataclass(frozen=True)
class NormalizedEvent:
    sequence: int
    case_id: str | None
    step: str
    native_or_normalized: str
    source_event_id: str
    source_event_type: str
    event_role: str
    timestamp: str | int | float | None
    summary: str


@dataclass(frozen=True)
class FirstDivergence:
    """One divergence, carrying *both* sides.

    A single scalar cannot describe a mismatch: ``route`` vs ``tool`` at the same
    ordinal is one event with two step values.  Returning only the left one made
    the answer depend on which file was passed first.
    """

    ordinal: int
    relation: str
    left_step: str | None
    right_step: str | None


@dataclass(frozen=True)
class ComparisonResult:
    pre_divergence_equivalence: str
    first_divergence_step: str | None
    evidence: tuple[str, ...]
    first_divergence: FirstDivergence | None = None


def _string_token(value: object, *, fallback: str = "unknown") -> str:
    text = str(value or "").strip()
    return text if _SAFE_TOKEN.fullmatch(text) and not _TOKEN_LIKE.search(text) else fallback


def _safe_case_id(value: object) -> str | None:
    """Accept a hierarchical id (``suite/case-01``); reject path *shape*.

    ``_SAFE_TOKEN`` answers "which characters were used" and cannot answer
    "is this combination safe": ``../../etc/passwd`` satisfies it in full.  The
    case id is concatenated into ``source_event_id``, so a traversal shape would
    propagate into logs, path-like storage, and downstream parsers.

    Deliberately *not* fixed by tightening ``_SAFE_TOKEN``: ``source_event_id``
    and other fields use ``/`` and ``:`` legitimately, so a global character ban
    would break them while still not answering the structural question.

    Returns the canonical id, or ``None`` when it is unusable.  Callers differ on
    what to do with ``None``: the raw mapper degrades to ``None`` (tolerant, as
    with every other raw field), while the artifact validator raises, because an
    artifact *claims* to already satisfy this contract.
    """

    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or not _SAFE_TOKEN.fullmatch(text) or not _clean_text(text):
        return None
    # Absolute, drive-qualified, or backslash-separated: all path shape, never a
    # case identity.  (Backslash also fails `_SAFE_TOKEN`; checked here anyway so
    # the structural contract does not silently depend on that character list.)
    if text.startswith("/") or "\\" in text or _WINDOWS_DRIVE.match(text):
        return None
    # `.`/`..` segments traverse; an empty segment means `//`.
    if any(segment in ("", ".", "..") for segment in text.split("/")):
        return None
    return text


def _safe_timestamp(value: object) -> str | int | float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    text = str(value or "").strip()
    if (
        not _SAFE_TIMESTAMP_TEXT.fullmatch(text)
        or _ABSOLUTE_PATH.search(text)
        or _SECRET.search(text)
    ):
        return None
    return text[:64]


def _safe_summary(parts: Iterable[str]) -> str:
    # Summaries contain only controlled labels and small counts.  This final
    # guard protects us if a future mapper accidentally passes free text.
    summary = " ".join(part.strip() for part in parts if part.strip())
    summary = _SECRET.sub("[redacted]", summary)
    summary = _ABSOLUTE_PATH.sub(" [path-redacted]", summary)
    return summary[:240]


def _event_timestamp(record: Mapping[str, Any]) -> str | int | float | None:
    for key in ("timestamp", "created_at", "started_at", "finished_at", "time"):
        if key in record:
            return _safe_timestamp(record[key])
    payload = record.get("payload")
    if isinstance(payload, Mapping):
        for key in ("timestamp", "created_at", "started_at", "finished_at", "time"):
            if key in payload:
                return _safe_timestamp(payload[key])
    return None


def _record_type(record: Mapping[str, Any]) -> str:
    for key in ("type", "event_type", "kind", "name", "step_id"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "unknown"


def _status_sources(record: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    # Benchmark events keep the terminal state one level down in ``payload``;
    # the synthetic finish built by ``_load_records`` keeps it at the top.  Read
    # both so the normalized artifact can reproduce the terminal column instead
    # of degrading every event to ``status=unknown``.
    payload = record.get("payload")
    if isinstance(payload, Mapping):
        return (record, payload)
    return (record,)


def _lookup_token(record: Mapping[str, Any], keys: Sequence[str]) -> str | None:
    for source in _status_sources(record):
        for key in keys:
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                return _string_token(value)
    return None


def _status(record: Mapping[str, Any]) -> str:
    return _lookup_token(record, ("status", "stop_reason", "state")) or "unknown"


def _workbench_mapping(record: Mapping[str, Any]) -> tuple[str, str, str] | None:
    event_type = _record_type(record).lower()
    step_id = str(record.get("step_id") or "").lower()
    name = str(record.get("name") or "").lower()
    joined = f"{step_id} {name} {event_type}"
    # `configure` and `plan` must be tested before the generic branches below:
    # `turn_assembly` would otherwise fall through to unmapped, and
    # `research_plan` contains "research" and would be captured by `retrieve`.
    if "configure" in joined or "assembly" in joined:
        return "configure", "native", "control"
    if "plan" in joined:
        return "plan", "native", "control"
    if "controller" in joined or "intent" in joined:
        return "intent", "native", "control"
    if "route" in joined:
        return "route", "native", "control"
    if any(term in joined for term in ("observe", "validate", "budget", "ledger")):
        return "observe", "native", "control"
    if any(term in joined for term in ("retrieve", "skill", "research", "evidence")):
        return "retrieve", "native", "control"
    if any(term in joined for term in ("synth", "compose", "grounded", "shadow")):
        return "synthesize", "native", "generation"
    if any(term in joined for term in ("stop", "complete", "finish", "terminal", "error")):
        return "stop", "native", "control"
    return None


def _codex_mapping(record: Mapping[str, Any]) -> tuple[str, str, str] | None:
    event_type = _record_type(record).lower()
    item = record.get("item")
    item_type = (
        str(item.get("type") or "").lower() if isinstance(item, Mapping) else ""
    )
    joined = f"{event_type} {item_type}"
    if any(term in joined for term in ("thread.started", "session.started", "config")):
        return "configure", "normalized", "control"
    if "turn.started" in joined or "input" in joined:
        return "intent", "normalized", "control"
    if any(term in joined for term in _CODEX_OBSERVE_TERMS):
        return "observe", "normalized", "control"
    if any(term in joined for term in ("function_call", "command", "mcp", "tool")):
        return "tool", "normalized", "tool"
    if any(term in joined for term in ("message", "reasoning", "output_text", "generation")):
        return "synthesize", "normalized", "generation"
    if any(term in joined for term in ("turn.completed", "turn.failed", "error", "failed")):
        return "stop", "normalized", "control"
    return None


#: Every kind the benchmark artifact is allowed to persist
#: (``runtime_backend_benchmark._DIAGNOSTIC_EVENT_KINDS``) must have an entry
#: here, otherwise it silently drops out of the comparison.  The step for each
#: kind is taken from the runtime's own public semantics in
#: ``episode_progress._EVENT_PROJECTIONS`` (planning→plan, repair→plan,
#: research request→tool, branch start→retrieve, research outcome→observe,
#: finalizing→synthesize), not guessed from the kind's name.  The projection
#: table is the *source*; this mapping restates it in L1 terms, so when the two
#: disagree the runtime wins.
_BENCHMARK_STEPS: dict[str, tuple[str, str]] = {
    # pre-run assembly
    "configure": ("configure", "control"),
    # intent
    "task": ("intent", "control"),
    # planning: what steps, how deep, what to repair -- L1 `plan`
    "plan": ("plan", "control"),
    "mode_decision": ("plan", "control"),
    "repair_goal": ("plan", "control"),
    # deciding to widen the search is retrieval intent -- L1 `retrieve`
    "branch_started": ("retrieve", "control"),
    # actually invoking a tool with arguments -- L1 `tool`
    "tool_request": ("tool", "tool"),
    "tool_call": ("tool", "tool"),
    # observations, including rejected and failed attempts
    "tool_result": ("observe", "control"),
    "tool_error": ("observe", "control"),
    "observation": ("observe", "control"),
    "runtime_result": ("observe", "control"),
    "branch_completed": ("observe", "control"),
    "branch_failed": ("observe", "control"),
    "repair_outcome": ("observe", "control"),
    "invalid_action": ("observe", "control"),
    # answer construction
    "finalization": ("synthesize", "generation"),
    "finalization_recovery_started": ("synthesize", "generation"),
    # terminal
    "finish": ("stop", "control"),
    "turn.completed": ("stop", "control"),
    "turn.failed": ("stop", "control"),
    "error": ("stop", "control"),
}


def _benchmark_mapping(record: Mapping[str, Any]) -> tuple[str, str, str] | None:
    kind = str(record.get("kind") or record.get("event_type") or "").lower()
    mapped = _BENCHMARK_STEPS.get(kind)
    if mapped is None:
        return None
    step, role = mapped
    return step, "normalized", role


def _mapping(record: Mapping[str, Any], kind: str) -> tuple[str, str, str] | None:
    if kind == "workbench-trace":
        return _workbench_mapping(record)
    if kind in {"codex-rollout", "codex-exec"}:
        return _codex_mapping(record)
    if kind == "runtime-benchmark":
        return _benchmark_mapping(record)
    return _workbench_mapping(record) or _codex_mapping(record) or _benchmark_mapping(record)


def _summary(record: Mapping[str, Any], kind: str, mapping: tuple[str, str, str] | None) -> str:
    source_type = _string_token(_record_type(record))
    status = _status(record)
    parts = [f"source={source_type}", f"status={status}"]
    stop_reason = _lookup_token(record, ("stop_reason",))
    if stop_reason is not None and stop_reason != status:
        parts.append(f"stop_reason={stop_reason}")
    if mapping is not None:
        parts.append(f"role={mapping[2]}")
    if kind == "runtime-benchmark":
        for key in ("tool_calls", "llm_calls", "latency_seconds"):
            value = record.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                parts.append(f"{key}={value}")
    return _safe_summary(parts)


def normalize_records(records: Sequence[Mapping[str, Any]], *, kind: str) -> list[NormalizedEvent]:
    """Normalize source records without reading or copying free-form text."""

    normalized: list[NormalizedEvent] = []
    for index, record in enumerate(records):
        mapping = _mapping(record, kind)
        step, provenance, role = mapping if mapping else ("unmapped", "unmapped", "unknown")
        source_type = _string_token(_record_type(record))
        # Structural check, not just a character whitelist: the id is
        # concatenated into `source_event_id` below, so a traversal shape would
        # travel with it.  Raw input degrades to None like every other field.
        case_id = _safe_case_id(record.get("case_id"))
        source_id = _string_token(
            record.get("step_id")
            or record.get("id")
            or record.get("event_id")
            or record.get("sequence"),
            fallback=f"event-{index}",
        )
        if case_id is not None:
            source_id = f"{case_id}:{source_id}"[:100]
        normalized.append(
            NormalizedEvent(
                sequence=index,
                case_id=case_id,
                step=step,
                native_or_normalized=provenance,
                source_event_id=source_id,
                source_event_type=source_type,
                event_role=role,
                timestamp=_event_timestamp(record),
                summary=_summary(record, kind, mapping),
            )
        )
    return normalized


def compare_sequences(
    left: Sequence[NormalizedEvent], right: Sequence[NormalizedEvent]
) -> ComparisonResult:
    """Compare step order while distinguishing missing evidence from divergence."""

    left_steps = [event.step for event in left if event.step != "unmapped"]
    right_steps = [event.step for event in right if event.step != "unmapped"]
    if not left_steps or not right_steps:
        return ComparisonResult(
            "not_established",
            None,
            ("one side has no mapped semantic events",),
            None,
        )
    for index, (left_step, right_step) in enumerate(zip(left_steps, right_steps)):
        if left_step != right_step:
            # Both step values matter and neither is "the" divergence step, so
            # the scalar stays null; swapping the inputs only swaps the two
            # named fields.
            return ComparisonResult(
                "equivalent_before_divergence" if index else "not_established",
                None,
                (f"left={left_step}", f"right={right_step}", f"ordinal={index}"),
                FirstDivergence(index, "step_mismatch", left_step, right_step),
            )
    if len(left_steps) != len(right_steps):
        # One side is a strict prefix of the other.  Here the extra step exists
        # on exactly one side, so the scalar is unambiguous and is kept.
        common = min(len(left_steps), len(right_steps))
        left_longer = len(left_steps) > len(right_steps)
        longer = left_steps if left_longer else right_steps
        extra = longer[common]
        return ComparisonResult(
            "equivalent_before_divergence",
            extra,
            (
                f"mapped event counts differ: left={len(left_steps)} right={len(right_steps)}",
                f"continues_on={'left' if left_longer else 'right'}",
                f"ordinal={common}",
            ),
            FirstDivergence(
                common,
                "left_continues" if left_longer else "right_continues",
                extra if left_longer else None,
                None if left_longer else extra,
            ),
        )
    return ComparisonResult(
        "fully_equivalent", None, ("mapped step sequence matches",), None
    )


def _load_records(path: Path) -> tuple[list[Mapping[str, Any]], str]:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    text = raw.decode("utf-8")
    records: list[Mapping[str, Any]] = []
    if path.suffix.lower() == ".jsonl":
        for line in text.splitlines():
            if line.strip():
                value = json.loads(line)
                if isinstance(value, Mapping):
                    records.append(value)
        return records, digest
    value = json.loads(text)
    if isinstance(value, list):
        records.extend(item for item in value if isinstance(item, Mapping))
    elif isinstance(value, Mapping):
        if isinstance(value.get("events"), list):
            records.extend(item for item in value["events"] if isinstance(item, Mapping))
        elif isinstance(value.get("trace"), list):
            records.extend(item for item in value["trace"] if isinstance(item, Mapping))
        elif isinstance(value.get("cases"), list):
            for case in value["cases"]:
                if not isinstance(case, Mapping):
                    continue
                case_id = case.get("id") or case.get("case_id")
                for arm in case.get("arms", ()):
                    if not isinstance(arm, Mapping):
                        continue
                    diagnostics = arm.get("diagnostics")
                    events = diagnostics.get("events", ()) if isinstance(diagnostics, Mapping) else ()
                    for event in events:
                        if isinstance(event, Mapping):
                            records.append({"case_id": case_id, **event})
                    if not events:
                        records.append(
                            {
                                "case_id": case_id,
                                "kind": "finish",
                                "status": arm.get("status"),
                                "stop_reason": arm.get("stop_reason"),
                            }
                        )
    return records, digest


def _infer_kind(path: Path, records: Sequence[Mapping[str, Any]]) -> str:
    if path.suffix.lower() == ".jsonl":
        first = records[0] if records else {}
        if "step_id" in first or "started_at" in first:
            return "workbench-trace"
        return "codex-rollout"
    if any("case_id" in record for record in records):
        return "runtime-benchmark"
    return "codex-exec"


class NormalizedArtifactError(ValueError):
    """Raised when an input looks like our own artifact but cannot be reused.

    Failing loudly is the point.  A v1 artifact silently re-fed through the raw
    mapper yields ``mapped=0`` on both sides and a ``null`` verdict that reads
    like "no divergence found" instead of "this input was never compared".
    """


def _reject(index: int, field: str, value: object, reason: str) -> NormalizedArtifactError:
    # The offending value is summarized by type and length, never echoed: a
    # rejected `summary` is exactly the case where it may carry a credential.
    shape = f"{type(value).__name__}"
    if isinstance(value, str):
        shape += f"[len={len(value)}]"
    return NormalizedArtifactError(f"events[{index}].{field} {reason} (got {shape})")


def _clean_text(value: str) -> bool:
    """No credential, absolute path, or token-shaped text.

    The mapper runs every string through :func:`_safe_summary` /
    :func:`_string_token`, so a value failing this check cannot have been
    produced by this module.  Rejecting is therefore both a redaction guarantee
    and evidence that the artifact is not ours -- silently re-redacting here
    would instead launder a tampered artifact into a clean-looking one.
    """

    return not (_SECRET.search(value) or _ABSOLUTE_PATH.search(value) or _TOKEN_LIKE.search(value))


def _event_from_artifact(raw: object, index: int) -> NormalizedEvent:
    """Validate one event of our own artifact, field by field.

    Reuse bypasses the mapper, hence also its type coercion and sanitizers.
    Checking only presence and the ``step`` enum (as this did before) accepted
    ``sequence="not-an-int"``, a dict ``timestamp``, and a ``summary`` carrying
    ``authorization: ...`` plus an absolute path -- violating both the dataclass
    types and the redaction guarantee in ``docs/trace-profile.md`` §6.
    """

    if not isinstance(raw, Mapping):
        raise NormalizedArtifactError(f"events[{index}] is not an object")
    expected = set(NormalizedEvent.__dataclass_fields__)
    missing = sorted(expected - set(raw))
    if missing:
        raise NormalizedArtifactError(f"events[{index}] is missing {missing}")
    unexpected = sorted(set(raw) - expected)
    if unexpected:
        # `schema_version` gates evolution; unknown keys mean a foreign schema
        # rather than a newer one, and dropping them silently hides that.
        raise NormalizedArtifactError(f"events[{index}] has unexpected keys {unexpected}")

    sequence = raw["sequence"]
    if isinstance(sequence, bool) or not isinstance(sequence, int):
        raise _reject(index, "sequence", sequence, "must be an int")
    if sequence != index:
        # The mapper numbers events by position, so a mismatch means events were
        # reordered or dropped -- which would silently shift every ordinal in the
        # divergence verdict.
        raise _reject(index, "sequence", sequence, f"must equal its position {index}")

    case_id = raw["case_id"]
    # Same structural contract as the raw mapper, opposite failure mode: the raw
    # mapper degrades an unusable id to None, but an artifact *claims* to already
    # satisfy this contract, so a violation means it is not ours.
    if case_id is not None and _safe_case_id(case_id) != case_id:
        raise _reject(index, "case_id", case_id, "must be null or a non-traversing id")

    step = raw["step"]
    if step != "unmapped" and step not in STEPS:
        raise NormalizedArtifactError(
            f"events[{index}] has step={step!r} outside {VOCABULARY}"
        )

    provenance = raw["native_or_normalized"]
    if provenance not in _PROVENANCES:
        raise _reject(index, "native_or_normalized", provenance, f"must be one of {_PROVENANCES}")
    if (step == "unmapped") != (provenance == "unmapped"):
        # `unmapped` is a pair, not two independent flags: a mapped step with
        # `unmapped` provenance (or the reverse) would let an unmapped event be
        # counted as semantic evidence.
        raise NormalizedArtifactError(
            f"events[{index}] pairs step={step!r} with "
            f"native_or_normalized={provenance!r}; both must be 'unmapped' or neither"
        )

    source_id = raw["source_event_id"]
    if not (
        isinstance(source_id, str)
        and _ARTIFACT_EVENT_ID.fullmatch(source_id)
        and _clean_text(source_id)
    ):
        raise _reject(index, "source_event_id", source_id, "must be a safe id")

    source_type = raw["source_event_type"]
    if not (
        isinstance(source_type, str)
        and _SAFE_TOKEN.fullmatch(source_type)
        and _clean_text(source_type)
    ):
        raise _reject(index, "source_event_type", source_type, "must be a safe token")

    role = raw["event_role"]
    if role not in _EVENT_ROLES:
        raise _reject(index, "event_role", role, f"must be one of {_EVENT_ROLES}")

    timestamp = raw["timestamp"]
    if timestamp is not None:
        if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float, str)):
            raise _reject(index, "timestamp", timestamp, "must be null, a number, or a string")
        if isinstance(timestamp, str) and not (
            len(timestamp) <= 64
            and _SAFE_TIMESTAMP_TEXT.fullmatch(timestamp)
            and _clean_text(timestamp)
        ):
            raise _reject(index, "timestamp", timestamp, "must be an ISO-8601 instant")

    summary = raw["summary"]
    if not isinstance(summary, str):
        raise _reject(index, "summary", summary, "must be a string")
    if len(summary) > _MAX_SUMMARY:
        raise _reject(index, "summary", summary, f"must be at most {_MAX_SUMMARY} chars")
    if not _clean_text(summary):
        raise _reject(
            index, "summary", summary, "carries a credential, absolute path, or token"
        )

    return NormalizedEvent(**{key: raw[key] for key in expected})


def _load_normalized_artifact(
    path: Path,
) -> tuple[dict[str, Any], list[NormalizedEvent]] | None:
    """Reuse our own single-input artifact, or return ``None`` for raw input.

    Detection uses this artifact's own marker fields, not a bare
    ``schema_version``: raw benchmark artifacts also carry their independent
    integer schema version.  Once the marker set matches, accept after full
    validation or reject with a reason -- never quietly re-map a malformed
    normalized artifact as raw harness trace.
    """

    if path.suffix.lower() == ".jsonl":
        return None
    try:
        value = json.loads(path.read_bytes().decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(value, Mapping):
        return None
    claims_normalized_schema = "vocabulary" in value or all(
        key in value for key in ("source_kind", "input_sha256", "events")
    )
    if not claims_normalized_schema:
        return None

    schema = value.get("schema_version")
    if schema != _ARTIFACT_SCHEMA:
        raise NormalizedArtifactError(
            f"schema_version={schema!r} cannot be compared against "
            f"{_ARTIFACT_SCHEMA!r}; re-normalize the original trace"
        )
    vocabulary = value.get("vocabulary")
    if vocabulary != VOCABULARY:
        raise NormalizedArtifactError(
            f"vocabulary={vocabulary!r} is not {VOCABULARY!r}; "
            "step values are not comparable"
        )
    if "comparison" in value:
        raise NormalizedArtifactError(
            "this is a --compare output, not one side; pass the single-input artifacts"
        )
    events_raw = value.get("events")
    if not isinstance(events_raw, list):
        raise NormalizedArtifactError("events is missing or not a list")

    # `source_kind` and `input_sha256` are the provenance of the comparison
    # verdict.  Coercing them through `_string_token` (as this did) turned a
    # tampered or foreign value into `unknown` and kept going -- the artifact
    # then looked well-formed while naming no original trace at all.
    source_kind = value.get("source_kind")
    if source_kind not in _SOURCE_KINDS:
        raise NormalizedArtifactError(
            f"source_kind={source_kind!r} is not one of {_SOURCE_KINDS}"
        )
    digest = value.get("input_sha256")
    if not (isinstance(digest, str) and _SHA256_HEX.fullmatch(digest)):
        raise NormalizedArtifactError(
            "input_sha256 must be 64 lowercase hex chars naming the original "
            f"trace (got {type(digest).__name__})"
        )
    source_file = value.get("source_file")
    if not (
        isinstance(source_file, str)
        and _SAFE_TOKEN.fullmatch(source_file)
        and _clean_text(source_file)
    ):
        raise NormalizedArtifactError(
            f"source_file must be a safe token (got {type(source_file).__name__})"
        )

    events = [_event_from_artifact(item, index) for index, item in enumerate(events_raw)]
    unmapped_count = sum(event.step == "unmapped" for event in events)
    # The counts are derived, so a disagreement means the events were edited
    # after the fact.  Recomputing silently would erase that evidence.
    for field, actual in (("event_count", len(events)), ("unmapped_count", unmapped_count)):
        declared = value.get(field)
        if declared is not None and declared != actual:
            raise NormalizedArtifactError(
                f"{field}={declared!r} disagrees with the {actual} events present; "
                "the artifact was modified after it was written"
            )

    payload = {
        "schema_version": _ARTIFACT_SCHEMA,
        "vocabulary": VOCABULARY,
        "source_kind": source_kind,
        "source_file": source_file,
        # The artifact's own hash names the *original* trace.  Re-hashing the
        # artifact file would break provenance back to the raw input.
        "input_sha256": digest,
        "event_count": len(events),
        "unmapped_count": unmapped_count,
        "events": [asdict(event) for event in events],
        "reused_normalized_artifact": True,
    }
    return payload, events


def _build_side(path: Path, kind: str) -> tuple[dict[str, Any], list[NormalizedEvent]]:
    reused = _load_normalized_artifact(path)
    if reused is not None:
        return reused
    records, digest = _load_records(path)
    resolved_kind = _infer_kind(path, records) if kind == "auto" else kind
    events = normalize_records(records, kind=resolved_kind)
    payload = {
        "schema_version": _ARTIFACT_SCHEMA,
        "vocabulary": VOCABULARY,
        "source_kind": resolved_kind,
        "source_file": _string_token(path.name, fallback="source-redacted"),
        "input_sha256": digest,
        "event_count": len(events),
        "unmapped_count": sum(event.step == "unmapped" for event in events),
        "events": [asdict(event) for event in events],
    }
    return payload, events


def _build_output(path: Path, kind: str) -> dict[str, Any]:
    payload, _events = _build_side(path, kind)
    return payload


def _build_comparison_output(
    left_path: Path, left_kind: str, right_path: Path, right_kind: str
) -> dict[str, Any]:
    """Emit both normalized sides plus the divergence verdict.

    The caveats are part of the artifact on purpose: a bare
    ``first_divergence_step`` reads like a behavioural difference even when it is
    only a vocabulary gap or a one-sided instrumentation hole.
    """

    left_payload, left_events = _build_side(left_path, left_kind)
    right_payload, right_events = _build_side(right_path, right_kind)
    result = compare_sequences(left_events, right_events)

    unmapped = {
        "left": left_payload["unmapped_count"],
        "right": right_payload["unmapped_count"],
    }
    mapped = {
        "left": sum(event.step != "unmapped" for event in left_events),
        "right": sum(event.step != "unmapped" for event in right_events),
    }
    caveats: list[str] = []
    if unmapped["left"] or unmapped["right"]:
        caveats.append(
            "unmapped events present: first_divergence_step may be a vocabulary gap "
            "rather than a behavioural difference"
        )
    if result.pre_divergence_equivalence == "not_established":
        caveats.append(
            "pre_divergence_equivalence=not_established: the compared prefix is not "
            "evidence that the two sides agree; treat as insufficient trace, not as "
            "'no divergence'"
        )
    if mapped["left"] == 0 or mapped["right"] == 0:
        caveats.append("one side has no mapped semantic events: no comparison is possible")
    if (
        result.first_divergence is not None
        and result.first_divergence.relation == "step_mismatch"
    ):
        caveats.append(
            "first_divergence.relation=step_mismatch: the divergence has a step on "
            "each side, so first_divergence_step is null by contract; read "
            "first_divergence.left_step / right_step and do not collapse them into "
            "a single L1 value"
        )

    return {
        "schema_version": "normalized-harness-trace-2",
        "vocabulary": VOCABULARY,
        "comparison": {
            "pre_divergence_equivalence": result.pre_divergence_equivalence,
            "first_divergence_step": result.first_divergence_step,
            "first_divergence": (
                asdict(result.first_divergence)
                if result.first_divergence is not None
                else None
            ),
            "evidence": list(result.evidence),
            "mapped_event_counts": mapped,
            "unmapped_counts": unmapped,
            "interpretation_caveats": caveats,
        },
        "left": left_payload,
        "right": right_payload,
    }


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--kind", choices=KINDS, default="auto")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--compare",
        type=Path,
        help="second trace to compare against; adds the comparison block",
    )
    parser.add_argument("--compare-kind", choices=KINDS, default="auto")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    if args.compare is None:
        output = _build_output(args.input, args.kind)
    else:
        output = _build_comparison_output(
            args.input, args.kind, args.compare, args.compare_kind
        )
    rendered = json.dumps(output, ensure_ascii=False, indent=2) + "\n"
    if args.output is None:
        sys.stdout.write(rendered)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
