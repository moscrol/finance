"""Stable, non-secret identity and attempt contracts for one execution.

The module deliberately contains no persistence code.  ``RunStore`` owns the
append-only file; this module owns the bounded values that may be written to it.
Keeping the validation seam separate prevents the acceptance client from
inventing a second meaning for runtime identity.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
import re
from typing import Final


EXECUTION_PATHS: Final[frozenset[str]] = frozenset(
    {
        "continuous_episode",
        "continuous_fast_path",
        "continuous_clarification",
        "legacy_direct",
    }
)
ATTEMPT_EVENT_TYPES: Final[frozenset[str]] = frozenset(
    {"attempt.started", "execution.bound", "attempt.finished"}
)
ATTEMPT_TERMINAL_STATUSES: Final[frozenset[str]] = frozenset(
    {"completed", "failed", "cancelled", "abandoned"}
)
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,160}$")


def _required_id(value: object, field_name: str) -> str:
    cleaned = str(value or "").strip()
    if _ID_RE.fullmatch(cleaned) is None:
        raise ValueError(f"{field_name} must be a bounded identifier")
    return cleaned


def _required_text(value: object, field_name: str) -> str:
    cleaned = str(value or "").strip()
    if not cleaned or len(cleaned) > 512:
        raise ValueError(f"{field_name} must be non-empty and bounded")
    return cleaned


def validate_execution_path(value: object) -> str:
    cleaned = str(value or "").strip()
    if cleaned not in EXECUTION_PATHS:
        raise ValueError(f"unsupported execution path: {cleaned}")
    return cleaned


def validate_attempt_status(value: object) -> str:
    cleaned = str(value or "").strip()
    if cleaned not in ATTEMPT_TERMINAL_STATUSES:
        raise ValueError(f"unsupported attempt terminal status: {cleaned}")
    return cleaned


def validate_hash(value: object, field_name: str) -> str:
    cleaned = str(value or "").strip().lower()
    if _HASH_RE.fullmatch(cleaned) is None:
        raise ValueError(f"{field_name} must be a lowercase sha256")
    return cleaned


def normalize_contributors(values: Sequence[object]) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        cleaned = _required_id(value, "contributor")
        if cleaned not in result:
            result.append(cleaned)
    if not result:
        raise ValueError("contributors must contain at least one identifier")
    return tuple(result)


@dataclass(frozen=True)
class RuntimeExecutionIdentity:
    runtime_instance_id: str
    source_revision: str
    source_dirty: bool
    code_root: str
    import_root: str
    python_executable: str
    backend: str
    model: str
    provider_label: str
    provider_protocol: str
    endpoint_fingerprint: str

    @classmethod
    def from_runtime_payload(
        cls,
        payload: Mapping[str, object],
    ) -> "RuntimeExecutionIdentity":
        agent_runtime = payload.get("agent_runtime")
        if not isinstance(agent_runtime, Mapping):
            raise ValueError("runtime payload missing agent_runtime")
        source_dirty = payload.get("source_dirty")
        if not isinstance(source_dirty, bool):
            raise ValueError("runtime payload source_dirty must be boolean")
        revision = _required_text(payload.get("source_revision"), "source_revision")
        if len(revision) != 40 or re.fullmatch(r"[0-9a-f]{40}", revision) is None:
            raise ValueError("source_revision must be a 40-character git sha")
        endpoint = validate_hash(
            agent_runtime.get("endpoint_fingerprint"),
            "endpoint_fingerprint",
        )
        return cls(
            runtime_instance_id=_required_id(
                payload.get("runtime_instance_id"), "runtime_instance_id"
            ),
            source_revision=revision,
            source_dirty=source_dirty,
            code_root=_required_text(payload.get("code_root"), "code_root"),
            import_root=_required_text(payload.get("import_root"), "import_root"),
            python_executable=_required_text(
                payload.get("python_executable"), "python_executable"
            ),
            backend=_required_id(agent_runtime.get("backend"), "backend"),
            model=_required_id(agent_runtime.get("model"), "model"),
            provider_label=_required_id(
                agent_runtime.get("provider_label"), "provider_label"
            ),
            provider_protocol=_required_id(
                agent_runtime.get("provider_protocol"), "provider_protocol"
            ),
            endpoint_fingerprint=endpoint,
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ExecutionAttempt:
    attempt_id: str
    attempt_index: int

    def __post_init__(self) -> None:
        _required_id(self.attempt_id, "attempt_id")
        if isinstance(self.attempt_index, bool) or self.attempt_index < 1:
            raise ValueError("attempt_index must be a positive integer")


__all__ = [
    "ATTEMPT_EVENT_TYPES",
    "ATTEMPT_TERMINAL_STATUSES",
    "EXECUTION_PATHS",
    "ExecutionAttempt",
    "RuntimeExecutionIdentity",
    "normalize_contributors",
    "validate_attempt_status",
    "validate_execution_path",
    "validate_hash",
]
