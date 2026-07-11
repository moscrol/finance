from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, TypeAlias

from intelligence.services.run_store import RunStore, redact

JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]


def redact_json(value: JsonValue) -> JsonValue:
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, list):
        return [redact_json(item) for item in value]
    if isinstance(value, dict):
        return {key: redact_json(item) for key, item in value.items()}
    return value


@dataclass(frozen=True)
class SkillDefinition:
    skill_id: str
    name: str
    description: str
    version: str
    triggers: tuple[str, ...]
    input_schema: JsonObject
    permissions: tuple[str, ...]
    timeout_seconds: int


@dataclass
class SkillOutput:
    skill_id: str
    modules: list[JsonObject]
    citations: list[JsonObject]
    warnings: list[str]
    as_of: str | None
    raw_result_ref: str | None


@dataclass(frozen=True)
class SkillExecutionContext:
    query: str
    task_type: str
    user_id: str
    run_id: str
    conversation_id: str | None
    repo_root: Path
    run_store: RunStore


class SkillExecutor(Protocol):
    skill_id: str

    def execute(self, context: SkillExecutionContext) -> SkillOutput: ...
