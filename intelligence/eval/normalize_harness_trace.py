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
        raw_case_id = str(record.get("case_id") or "").strip()
        case_id = raw_case_id if _SAFE_TOKEN.fullmatch(raw_case_id) else None
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


def _event_from_artifact(raw: object, index: int) -> NormalizedEvent:
    if not isinstance(raw, Mapping):
        raise NormalizedArtifactError(f"events[{index}] is not an object")
    expected = set(NormalizedEvent.__dataclass_fields__)
    missing = sorted(expected - set(raw))
    if missing:
        raise NormalizedArtifactError(f"events[{index}] is missing {missing}")
    step = raw["step"]
    if step != "unmapped" and step not in STEPS:
        raise NormalizedArtifactError(
            f"events[{index}] has step={step!r} outside {VOCABULARY}"
        )
    return NormalizedEvent(**{key: raw[key] for key in expected})


def _load_normalized_artifact(
    path: Path,
) -> tuple[dict[str, Any], list[NormalizedEvent]] | None:
    """Reuse our own single-input artifact, or return ``None`` for raw input.

    Detection is by ``schema_version``, so anything claiming to be this artifact
    is either accepted after validation or rejected with a reason -- never
    quietly re-mapped as if it were a raw harness trace.  The raw loader keeps
    returning plain records; the typed branch lives here.
    """

    if path.suffix.lower() == ".jsonl":
        return None
    try:
        value = json.loads(path.read_bytes().decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(value, Mapping) or "schema_version" not in value:
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

    events = [_event_from_artifact(item, index) for index, item in enumerate(events_raw)]
    payload = {
        "schema_version": _ARTIFACT_SCHEMA,
        "vocabulary": VOCABULARY,
        "source_kind": _string_token(value.get("source_kind")),
        "source_file": _string_token(value.get("source_file"), fallback="source-redacted"),
        # The artifact's own hash names the *original* trace.  Re-hashing the
        # artifact file would break provenance back to the raw input.
        "input_sha256": _string_token(value.get("input_sha256"), fallback="unknown"),
        "event_count": len(events),
        "unmapped_count": sum(event.step == "unmapped" for event in events),
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
