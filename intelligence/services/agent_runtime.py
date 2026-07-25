"""Provider-neutral contracts for one continuous research episode.

The runtime seam deliberately contains no GLM/OpenAI response objects. Model
adapters translate their provider payloads into :class:`ModelTurn`; episode
implementations return one immutable :class:`AgentOutcome` for verification.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import TYPE_CHECKING, Literal, Protocol, runtime_checkable

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_plan import ResearchPlan, plan_to_public_dict

if TYPE_CHECKING:
    from intelligence.services.episode_session import EpisodeSession
    from intelligence.services.repair_coordinator import RepairGoal
    from intelligence.services.research_contract import ResearchRunContext
    from intelligence.services.research_tool_registry import ResearchToolRegistry
    from intelligence.services.task_frame import TaskFrame


EpisodeStatus = Literal["completed", "partial", "clarification", "failed"]
_EPISODE_STATUSES = frozenset({"completed", "partial", "clarification", "failed"})
GroundingMode = Literal["evidence", "user_premise", "model_reasoning"]
_GROUNDING_MODES = frozenset({"evidence", "user_premise", "model_reasoning"})


def _json_copy(value: object, *, path: str) -> object:
    """Return a detached JSON-safe value or reject provider-owned objects."""

    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} must be JSON-safe")
        return value
    if isinstance(value, Mapping):
        result: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{path} must use string JSON keys")
            result[key] = _json_copy(item, path=f"{path}.{key}")
        return result
    if isinstance(value, (list, tuple)):
        return [
            _json_copy(item, path=f"{path}[{index}]")
            for index, item in enumerate(value)
        ]
    raise ValueError(f"{path} must be JSON-safe")


def _json_freeze(value: object, *, path: str) -> object:
    """Detach and recursively freeze a JSON value held by a frozen contract."""

    copied = _json_copy(value, path=path)
    if isinstance(copied, dict):
        return MappingProxyType(
            {
                key: _json_freeze(item, path=f"{path}.{key}")
                for key, item in copied.items()
            }
        )
    if isinstance(copied, list):
        return tuple(
            _json_freeze(item, path=f"{path}[{index}]")
            for index, item in enumerate(copied)
        )
    return copied


def _clean_string_tuple(values: object, *, field_name: str) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)):
        raise ValueError(f"{field_name} must be a sequence of strings")
    result: list[str] = []
    for value in values:
        if not isinstance(value, str):
            raise ValueError(f"{field_name} must be a sequence of strings")
        cleaned = value.strip()
        if cleaned and cleaned not in result:
            result.append(cleaned)
    return tuple(result)


@dataclass(frozen=True)
class ModelToolCall:
    call_id: str
    name: str
    arguments: Mapping[str, object]

    def __post_init__(self) -> None:
        if not isinstance(self.call_id, str) or not self.call_id.strip():
            raise ValueError("model tool call_id must be non-empty")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("model tool name must be non-empty")
        if not isinstance(self.arguments, Mapping):
            raise ValueError("model tool arguments must be an object")
        copied = _json_freeze(self.arguments, path="tool arguments")
        object.__setattr__(self, "call_id", self.call_id.strip())
        object.__setattr__(self, "name", self.name.strip())
        object.__setattr__(self, "arguments", copied)

    def to_dict(self) -> dict[str, object]:
        return {
            "call_id": self.call_id,
            "name": self.name,
            "arguments": _json_copy(self.arguments, path="tool arguments"),
        }


@dataclass(frozen=True)
class ModelTurn:
    content: str
    tool_calls: tuple[ModelToolCall, ...]
    provider_name: str = ""
    error: str = ""
    # Physical provider/HTTP attempts. Zero is valid when deadline or budget
    # rejects the turn before the adapter boundary.
    provider_attempts: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.content, str):
            raise ValueError("model content must be a string")
        if not isinstance(self.provider_name, str):
            raise ValueError("provider_name must be a stable string")
        if not isinstance(self.error, str):
            raise ValueError("model error must be a string")
        if (
            isinstance(self.provider_attempts, bool)
            or not isinstance(self.provider_attempts, int)
            or self.provider_attempts < 0
        ):
            raise ValueError("provider_attempts must be a non-negative integer")
        calls = tuple(self.tool_calls)
        if any(not isinstance(call, ModelToolCall) for call in calls):
            raise ValueError("tool_calls must contain ModelToolCall values")
        object.__setattr__(self, "tool_calls", calls)
        object.__setattr__(self, "provider_name", self.provider_name.strip())
        object.__setattr__(self, "error", self.error.strip())

    def to_dict(self) -> dict[str, object]:
        return {
            "content": self.content,
            "tool_calls": [call.to_dict() for call in self.tool_calls],
            "provider_name": self.provider_name,
            "error": self.error,
            "provider_attempts": self.provider_attempts,
        }


@runtime_checkable
class AgentModelClient(Protocol):
    """One provider adapter call; the episode owns continuity and policy."""

    def complete(
        self,
        *,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        timeout: float,
    ) -> ModelTurn: ...


@dataclass(frozen=True)
class OutputEvidenceBinding:
    output_id: str
    evidence_hashes: tuple[str, ...]
    gap: str = ""
    basis: GroundingMode = "evidence"

    def __post_init__(self) -> None:
        if not isinstance(self.output_id, str) or not self.output_id.strip():
            raise ValueError("output binding id must be non-empty")
        hashes = _clean_string_tuple(
            self.evidence_hashes,
            field_name="evidence_hashes",
        )
        if not isinstance(self.gap, str):
            raise ValueError("output binding gap must be a string")
        gap = self.gap.strip()
        if self.basis not in _GROUNDING_MODES:
            raise ValueError("unsupported grounding basis")
        if self.basis == "evidence" and not hashes and not gap:
            raise ValueError("output binding must contain evidence or a gap")
        object.__setattr__(self, "output_id", self.output_id.strip())
        object.__setattr__(self, "evidence_hashes", hashes)
        object.__setattr__(self, "gap", gap)
        object.__setattr__(self, "basis", self.basis)

    def to_dict(self) -> dict[str, object]:
        return {
            "output_id": self.output_id,
            "evidence_hashes": list(self.evidence_hashes),
            "gap": self.gap,
            "basis": self.basis,
        }


@dataclass(frozen=True)
class EpisodeEvent:
    sequence: int
    kind: str
    payload: Mapping[str, object]

    def __post_init__(self) -> None:
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int):
            raise ValueError("event sequence must be a positive integer")
        if self.sequence < 1:
            raise ValueError("event sequence must be a positive integer")
        if not isinstance(self.kind, str) or not self.kind.strip():
            raise ValueError("episode event kind must be non-empty")
        if not isinstance(self.payload, Mapping):
            raise ValueError("episode event payload must be an object")
        copied = _json_freeze(self.payload, path="event payload")
        object.__setattr__(self, "kind", self.kind.strip())
        object.__setattr__(self, "payload", copied)

    def to_dict(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "kind": self.kind,
            "payload": _json_copy(self.payload, path="event payload"),
        }


@dataclass(frozen=True)
class AgentUsage:
    llm_calls: int = 0
    tool_calls: int = 0
    invalid_actions: int = 0

    def __post_init__(self) -> None:
        for name in ("llm_calls", "tool_calls", "invalid_actions"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")

    def to_dict(self) -> dict[str, int]:
        return {
            "llm_calls": self.llm_calls,
            "tool_calls": self.tool_calls,
            "invalid_actions": self.invalid_actions,
        }


def public_agent_evidence(item: AgentEvidence) -> dict[str, object]:
    return {
        "tool": item.tool,
        "title": item.title,
        "detail": item.detail,
        "source": item.source,
        "source_date": item.source_date,
        "evidence_tier": item.evidence_tier,
        "supports": list(item.supports),
        "contradicts": list(item.contradicts),
        "independent_key": item.independent_key,
        "freshness": item.freshness,
        "content_hash": item.content_hash,
    }


@dataclass(frozen=True)
class AgentOutcome:
    task_frame_hash: str
    status: EpisodeStatus
    draft: str
    evidence: tuple[AgentEvidence, ...]
    traces: tuple[ProviderTrace, ...]
    gaps: tuple[str, ...]
    stop_reason: str
    events: tuple[EpisodeEvent, ...]
    bindings: tuple[OutputEvidenceBinding, ...]
    usage: AgentUsage
    plan: ResearchPlan | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.task_frame_hash, str)
            or not self.task_frame_hash.strip()
        ):
            raise ValueError("task frame hash must be non-empty")
        if self.status not in _EPISODE_STATUSES:
            raise ValueError("unsupported episode status")
        if not isinstance(self.draft, str):
            raise ValueError("episode draft must be a string")
        if not isinstance(self.stop_reason, str) or not self.stop_reason.strip():
            raise ValueError("episode stop_reason must be non-empty")

        evidence = tuple(self.evidence)
        traces = tuple(self.traces)
        events = tuple(self.events)
        bindings = tuple(self.bindings)
        if any(not isinstance(item, AgentEvidence) for item in evidence):
            raise ValueError("evidence must contain AgentEvidence values")
        if any(not isinstance(item, ProviderTrace) for item in traces):
            raise ValueError("traces must contain ProviderTrace values")
        if any(not isinstance(item, EpisodeEvent) for item in events):
            raise ValueError("events must contain EpisodeEvent values")
        if any(not isinstance(item, OutputEvidenceBinding) for item in bindings):
            raise ValueError("bindings must contain OutputEvidenceBinding values")
        if not isinstance(self.usage, AgentUsage):
            raise ValueError("usage must be AgentUsage")
        if self.plan is not None and not isinstance(self.plan, ResearchPlan):
            raise ValueError("plan must be ResearchPlan or None")
        gaps = _clean_string_tuple(self.gaps, field_name="gaps")

        if not events or events[0].kind != "task":
            raise ValueError("first episode event must be the task")
        event_hash = events[0].payload.get("task_frame_hash")
        if event_hash != self.task_frame_hash.strip():
            raise ValueError("task frame hash changed during the episode")
        if tuple(event.sequence for event in events) != tuple(
            range(1, len(events) + 1)
        ):
            raise ValueError("event sequence must be contiguous from 1")

        if self.status == "completed" and not self.draft.strip():
            raise ValueError("completed episode requires a non-empty draft")
        if self.status == "clarification" and (evidence or traces or bindings):
            raise ValueError("clarification cannot carry research evidence or bindings")
        output_ids = tuple(binding.output_id for binding in bindings)
        if len(output_ids) != len(set(output_ids)):
            raise ValueError("duplicate output binding")

        object.__setattr__(self, "task_frame_hash", self.task_frame_hash.strip())
        object.__setattr__(self, "draft", self.draft.strip())
        object.__setattr__(self, "evidence", evidence)
        object.__setattr__(self, "traces", traces)
        object.__setattr__(self, "gaps", gaps)
        object.__setattr__(self, "stop_reason", self.stop_reason.strip())
        object.__setattr__(self, "events", events)
        object.__setattr__(self, "bindings", bindings)

    def to_dict(self) -> dict[str, object]:
        return {
            "task_frame_hash": self.task_frame_hash,
            "status": self.status,
            "draft": self.draft,
            "evidence": [public_agent_evidence(item) for item in self.evidence],
            "traces": [trace.to_dict() for trace in self.traces],
            "gaps": list(self.gaps),
            "stop_reason": self.stop_reason,
            "events": [event.to_dict() for event in self.events],
            "bindings": [binding.to_dict() for binding in self.bindings],
            "usage": self.usage.to_dict(),
            "plan": plan_to_public_dict(self.plan) if self.plan is not None else None,
        }


@runtime_checkable
class AgentRuntime(Protocol):
    """Start one provider-neutral episode and expose same-history resume."""

    def start(
        self,
        task_frame: TaskFrame,
        *,
        context: ResearchRunContext,
        registry: ResearchToolRegistry,
    ) -> EpisodeSession: ...

    def run(
        self,
        *,
        task_frame: TaskFrame,
        context: ResearchRunContext,
        registry: ResearchToolRegistry,
    ) -> AgentOutcome: ...


__all__ = [
    "AgentModelClient",
    "AgentOutcome",
    "AgentRuntime",
    "AgentUsage",
    "EpisodeEvent",
    "EpisodeStatus",
    "ModelToolCall",
    "ModelTurn",
    "OutputEvidenceBinding",
    "public_agent_evidence",
]
