"""Thin, immutable user semantics for the adaptive research runtime."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from intelligence.services.task_frame import TaskFrame


RESOLUTION_SOURCES = frozenset(
    {"explicit", "inherited", "product_default", "inferred"}
)


def _trimmed_strings(values: object, *, field_name: str) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)):
        raise ValueError(f"{field_name} must contain strings")
    normalized: list[str] = []
    for value in values:
        if not isinstance(value, str):
            raise ValueError(f"{field_name} must contain strings")
        item = value.strip()
        if item and item not in normalized:
            normalized.append(item)
    return tuple(normalized)


def _freeze_json(value: object, *, path: str = "time_window") -> object:
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} must be JSON-safe")
        return value
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple)):
        return tuple(
            _freeze_json(item, path=f"{path}[]")
            for item in value
        )
    if isinstance(value, Mapping):
        frozen: dict[str, object] = {}
        for raw_key, item in value.items():
            if not isinstance(raw_key, str) or not raw_key.strip():
                raise ValueError(f"{path} must be JSON-safe")
            key = raw_key.strip()
            if key in frozen:
                raise ValueError(f"{path} contains duplicate keys")
            frozen[key] = _freeze_json(item, path=f"{path}.{key}")
        return MappingProxyType(frozen)
    raise ValueError(f"{path} must be JSON-safe")


def _thaw_json(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


@dataclass(frozen=True)
class ResolvedValue:
    value: str
    source: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise ValueError("resolved value must be a string")
        value = self.value.strip()
        if not value:
            raise ValueError("resolved value must be non-empty")
        if not isinstance(self.source, str):
            raise ValueError("unsupported resolution source")
        source = self.source.strip()
        if source not in RESOLUTION_SOURCES:
            raise ValueError("unsupported resolution source")
        object.__setattr__(self, "value", value)
        object.__setattr__(self, "source", source)

    def to_dict(self) -> dict[str, str]:
        return {"value": self.value, "source": self.source}


@dataclass(frozen=True)
class UserTask:
    raw_question: str
    conversation_context: str
    subjects: tuple[ResolvedValue, ...]
    market_scope: ResolvedValue | None
    time_window: Mapping[str, object] | None
    assumptions: tuple[str, ...]
    ambiguities: tuple[str, ...]
    user_premises: tuple[str, ...]
    task_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.raw_question, str) or not self.raw_question.strip():
            raise ValueError("raw_question must be non-empty")
        if not isinstance(self.conversation_context, str):
            raise ValueError("conversation_context must be a string")
        if not isinstance(self.task_id, str) or not self.task_id.strip():
            raise ValueError("task_id must be non-empty")
        if not isinstance(self.subjects, (list, tuple)) or any(
            not isinstance(item, ResolvedValue) for item in self.subjects
        ):
            raise ValueError("subjects must contain ResolvedValue values")
        if self.market_scope is not None and not isinstance(
            self.market_scope, ResolvedValue
        ):
            raise ValueError("market_scope must be a ResolvedValue")
        if self.time_window is not None and not isinstance(
            self.time_window, Mapping
        ):
            raise ValueError("time_window must be a JSON-safe mapping")

        subjects: list[ResolvedValue] = []
        seen_subjects: set[str] = set()
        for subject in self.subjects:
            key = subject.value.casefold()
            if key in seen_subjects:
                continue
            seen_subjects.add(key)
            subjects.append(subject)

        object.__setattr__(
            self,
            "conversation_context",
            self.conversation_context.strip(),
        )
        object.__setattr__(self, "subjects", tuple(subjects))
        object.__setattr__(
            self,
            "time_window",
            (
                _freeze_json(self.time_window)
                if self.time_window is not None
                else None
            ),
        )
        object.__setattr__(
            self,
            "assumptions",
            _trimmed_strings(self.assumptions, field_name="assumptions"),
        )
        object.__setattr__(
            self,
            "ambiguities",
            _trimmed_strings(self.ambiguities, field_name="ambiguities"),
        )
        object.__setattr__(
            self,
            "user_premises",
            _trimmed_strings(self.user_premises, field_name="user_premises"),
        )
        object.__setattr__(self, "task_id", self.task_id.strip())

    def to_dict(self) -> dict[str, object]:
        return {
            "raw_question": self.raw_question,
            "conversation_context": self.conversation_context,
            "subjects": [item.to_dict() for item in self.subjects],
            "market_scope": (
                self.market_scope.to_dict()
                if self.market_scope is not None
                else None
            ),
            "time_window": (
                _thaw_json(self.time_window)
                if self.time_window is not None
                else None
            ),
            "assumptions": list(self.assumptions),
            "ambiguities": list(self.ambiguities),
            "user_premises": list(self.user_premises),
            "task_id": self.task_id,
        }

    @classmethod
    def from_task_frame(
        cls,
        frame: TaskFrame,
        context: Mapping[str, object] | str | None = None,
    ) -> UserTask:
        if context is None:
            values: Mapping[str, object] = {}
        elif isinstance(context, str):
            values = {"conversation_context": context}
        elif isinstance(context, Mapping):
            values = context
        else:
            raise ValueError("context must be a mapping or string")

        def resolution_source(field: str, default: str) -> str:
            raw = values.get(f"{field}_source", default)
            if not isinstance(raw, str):
                raise ValueError("unsupported resolution source")
            return raw

        assumptions = tuple(frame.assumptions)
        market_is_product_default = (
            frame.market_scope == "A股"
            and any("用户未明确市场范围" in item for item in assumptions)
        )
        subject_source = resolution_source("subject", "inferred")
        subjects = (
            (ResolvedValue(frame.subject, subject_source),)
            if frame.subject and frame.subject.strip()
            else ()
        )
        market_scope = (
            ResolvedValue(
                frame.market_scope,
                resolution_source(
                    "market_scope",
                    "product_default" if market_is_product_default else "inferred",
                ),
            )
            if frame.market_scope and frame.market_scope.strip()
            else None
        )
        time_window = (
            {
                "value": frame.timeframe,
                "source": resolution_source("time_window", "inferred"),
            }
            if frame.timeframe and frame.timeframe.strip()
            else None
        )
        conversation = values.get("conversation_context", "")
        if not isinstance(conversation, str):
            raise ValueError("conversation_context must be a string")
        raw_premises = values.get("user_premises", ())
        if not isinstance(raw_premises, (list, tuple)):
            raise ValueError("user_premises must contain strings")
        task_id = values.get("task_id", frame.task_frame_hash)
        if not isinstance(task_id, str):
            raise ValueError("task_id must be a string")
        return cls(
            raw_question=frame.raw_question,
            conversation_context=conversation,
            subjects=subjects,
            market_scope=market_scope,
            time_window=time_window,
            assumptions=assumptions,
            ambiguities=tuple(frame.ambiguities),
            user_premises=tuple(raw_premises),
            task_id=task_id,
        )


__all__ = ["RESOLUTION_SOURCES", "ResolvedValue", "UserTask"]
