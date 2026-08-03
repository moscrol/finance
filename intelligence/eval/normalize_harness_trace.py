"""Normalize heterogeneous harness events into the shared seven-step profile.

The normalizer is intentionally deterministic and lossy.  It keeps enough
control-plane information to compare ordering and first divergence, while
discarding prompts, answers, command arguments, paths, and provider secrets.
Unknown events remain ``unmapped`` instead of being guessed into a semantic
step.
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

STEPS = (
    "configure",
    "intent",
    "route",
    "retrieve",
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
class ComparisonResult:
    pre_divergence_equivalence: str
    first_divergence_step: str | None
    evidence: tuple[str, ...]


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


def _status(record: Mapping[str, Any]) -> str:
    for key in ("status", "stop_reason", "state"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return _string_token(value)
    return "unknown"


def _workbench_mapping(record: Mapping[str, Any]) -> tuple[str, str, str] | None:
    event_type = _record_type(record).lower()
    step_id = str(record.get("step_id") or "").lower()
    name = str(record.get("name") or "").lower()
    joined = f"{step_id} {name} {event_type}"
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
    if any(term in joined for term in ("function_call", "command", "mcp", "tool")):
        return "retrieve", "normalized", "tool"
    if any(term in joined for term in ("message", "reasoning", "output_text", "generation")):
        return "synthesize", "normalized", "generation"
    if any(term in joined for term in ("turn.completed", "turn.failed", "error", "failed")):
        return "stop", "normalized", "control"
    return None


def _benchmark_mapping(record: Mapping[str, Any]) -> tuple[str, str, str] | None:
    kind = str(record.get("kind") or record.get("event_type") or "").lower()
    if kind in {"tool_request", "tool_call"}:
        return "retrieve", "normalized", "tool"
    if kind in {"tool_result", "observation", "runtime_result"}:
        return "observe", "normalized", "control"
    if kind in {"finish", "turn.completed", "turn.failed", "error"}:
        return "stop", "normalized", "control"
    return None


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
        )
    for index, (left_step, right_step) in enumerate(zip(left_steps, right_steps)):
        if left_step != right_step:
            return ComparisonResult(
                "equivalent_before_divergence" if index else "not_established",
                left_step,
                (f"left={left_step}", f"right={right_step}", f"ordinal={index}"),
            )
    if len(left_steps) != len(right_steps):
        step = left_steps[min(len(left_steps), len(right_steps))]
        return ComparisonResult(
            "equivalent_before_divergence",
            step,
            (f"mapped event counts differ: left={len(left_steps)} right={len(right_steps)}",),
        )
    return ComparisonResult("fully_equivalent", None, ("mapped step sequence matches",))


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


def _build_output(path: Path, kind: str) -> dict[str, Any]:
    records, digest = _load_records(path)
    resolved_kind = _infer_kind(path, records) if kind == "auto" else kind
    events = normalize_records(records, kind=resolved_kind)
    return {
        "schema_version": "normalized-harness-trace-1",
        "source_kind": resolved_kind,
        "source_file": _string_token(path.name, fallback="source-redacted"),
        "input_sha256": digest,
        "event_count": len(events),
        "unmapped_count": sum(event.step == "unmapped" for event in events),
        "events": [asdict(event) for event in events],
    }


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--kind", choices=KINDS, default="auto")
    parser.add_argument("--output", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    output = _build_output(args.input, args.kind)
    rendered = json.dumps(output, ensure_ascii=False, indent=2) + "\n"
    if args.output is None:
        sys.stdout.write(rendered)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
