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
    input_tokens: int | None = None
    output_tokens: int | None = None
    # 响应体自报的 model（生效值）。三态：``None`` = 这一回合没有到达 provider
    # （预算/截止在适配器之前拒掉）；``""`` = provider 回了响应但没带 model 字段
    # （中转常见，记「未回」）；非空 = 对端实际服务的模型名。**永不**用配置的
    # ``provider.model`` 回填——A/B 读数要靠它分辨「模型没真的切过去」（§3.5.4）。
    served_model: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.content, str):
            raise ValueError("model content must be a string")
        if not isinstance(self.provider_name, str):
            raise ValueError("provider_name must be a stable string")
        if not isinstance(self.error, str):
            raise ValueError("model error must be a string")
        if self.served_model is not None and not isinstance(self.served_model, str):
            raise ValueError("served_model must be a string or None")
        if (
            isinstance(self.provider_attempts, bool)
            or not isinstance(self.provider_attempts, int)
            or self.provider_attempts < 0
        ):
            raise ValueError("provider_attempts must be a non-negative integer")
        for field_name in ("input_tokens", "output_tokens"):
            value = getattr(self, field_name)
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 0
            ):
                raise ValueError(f"{field_name} must be a non-negative integer")
        calls = tuple(self.tool_calls)
        if any(not isinstance(call, ModelToolCall) for call in calls):
            raise ValueError("tool_calls must contain ModelToolCall values")
        object.__setattr__(self, "tool_calls", calls)
        object.__setattr__(self, "provider_name", self.provider_name.strip())
        object.__setattr__(self, "error", self.error.strip())
        if self.served_model is not None:
            object.__setattr__(self, "served_model", self.served_model.strip())

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "content": self.content,
            "tool_calls": [call.to_dict() for call in self.tool_calls],
            "provider_name": self.provider_name,
            "error": self.error,
            "provider_attempts": self.provider_attempts,
        }
        if self.input_tokens is not None:
            payload["input_tokens"] = self.input_tokens
        if self.output_tokens is not None:
            payload["output_tokens"] = self.output_tokens
        if self.served_model is not None:
            # 空串也写：那是「provider 未回 model 字段」的收据，与字段缺席不同。
            payload["served_model"] = self.served_model
        return payload


# 瞬态模型/provider 错误的判据（单一真本源）。provider 适配器
# （glm_agent_runtime）用它决定链内换 provider 重试，episode 修复轮用它决定
# harness 层是否补救一次。两处共用同一份标记，避免「适配器认为可重试、
# 修复轮认为致命」这种口径漂移。
TRANSIENT_MODEL_ERROR_MARKERS = (
    "TimeoutError",
    "RemoteDisconnected",
    "URLError",
    # cockpit gateway round-robin 偶发：池里某账号坏掉时返回 502/503，
    # 下一轮 round-robin 通常会打到健康账号。一次重试代价极低（<1s），
    # 而不重试会让单次决证直接报 model_unavailable，误导性极强。
    "HTTP 502",
    "HTTP 503",
    # 网关超时是 TimeoutError 的 HTTP 形态；适配器窗口烧穿时返回
    # ``model deadline exhausted`` 而不是 TimeoutError 这个类名。
    "HTTP 504",
    "model deadline exhausted",
)


def is_transient_model_error(reason: object) -> bool:
    """这个模型错误是不是「再试一次大概率就好」的瞬态故障。

    命中判据是子串匹配：错误串可能被包装（如 ``LLM 调用失败（TimeoutError）``），
    只要瞬态标记出现就算。配置错误（缺 key）、预算拒绝等确定性失败不在此列。
    """

    return isinstance(reason, str) and any(
        marker in reason for marker in TRANSIENT_MODEL_ERROR_MARKERS
    )


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
    input_tokens: int | None = None
    output_tokens: int | None = None

    def __post_init__(self) -> None:
        for name in ("llm_calls", "tool_calls", "invalid_actions"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")

        for name in ("input_tokens", "output_tokens"):
            value = getattr(self, name)
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 0
            ):
                raise ValueError(f"{name} must be a non-negative integer")

    def to_dict(self) -> dict[str, int]:
        payload = {
            "llm_calls": self.llm_calls,
            "tool_calls": self.tool_calls,
            "invalid_actions": self.invalid_actions,
        }
        if self.input_tokens is not None:
            payload["input_tokens"] = self.input_tokens
        if self.output_tokens is not None:
            payload["output_tokens"] = self.output_tokens
        return payload


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

        # Every outcome must stay anchored to a task frame.  `configure` is the
        # pre-run assembly landmark and is the only kind allowed to precede it:
        # forcing `configure` after `task` would make this runtime emit
        # `intent -> configure` while the workbench emits `configure -> intent`,
        # manufacturing a divergence at ordinal 0 out of event ordering alone.
        anchor = next(
            (index for index, event in enumerate(events) if event.kind == "task"),
            None,
        )
        if anchor is None or any(
            event.kind != "configure" for event in events[:anchor]
        ):
            raise ValueError(
                "first episode event must be the task (only configure may precede it)"
            )
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
    """Legacy-compatible one-shot runtime during the session migration."""

    def run(
        self,
        *,
        task_frame: TaskFrame,
        context: ResearchRunContext,
        registry: ResearchToolRegistry,
    ) -> AgentOutcome: ...


@runtime_checkable
class ResumableAgentRuntime(AgentRuntime, Protocol):
    """Production candidate that can continue one provider history."""

    def start(
        self,
        task_frame: TaskFrame,
        *,
        context: ResearchRunContext,
        registry: ResearchToolRegistry,
    ) -> EpisodeSession: ...


__all__ = [
    "AgentModelClient",
    "AgentOutcome",
    "AgentRuntime",
    "ResumableAgentRuntime",
    "AgentUsage",
    "EpisodeEvent",
    "EpisodeStatus",
    "ModelToolCall",
    "ModelTurn",
    "OutputEvidenceBinding",
    "public_agent_evidence",
]
