from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REGISTRY_PATH = Path(__file__).resolve().parents[1] / "routing" / "path_registry.json"


@dataclass(frozen=True)
class PathSpec:
    id: str
    label: str
    kind: str
    description: str
    triggers: tuple[str, ...]
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    command_template: str
    auto_execute: bool
    risk_level: str
    notes: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PathSpec":
        return cls(
            id=str(data["id"]),
            label=str(data.get("label") or data["id"]),
            kind=str(data.get("kind") or "known_workflow"),
            description=str(data.get("description") or ""),
            triggers=tuple(str(x) for x in data.get("triggers", [])),
            inputs=tuple(str(x) for x in data.get("inputs", [])),
            outputs=tuple(str(x) for x in data.get("outputs", [])),
            command_template=str(data.get("command_template") or ""),
            auto_execute=bool(data.get("auto_execute", False)),
            risk_level=str(data.get("risk_level") or "medium"),
            notes=str(data.get("notes") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "kind": self.kind,
            "description": self.description,
            "triggers": list(self.triggers),
            "inputs": list(self.inputs),
            "outputs": list(self.outputs),
            "command_template": self.command_template,
            "auto_execute": self.auto_execute,
            "risk_level": self.risk_level,
            "notes": self.notes,
        }


def load_registry(path: Path | None = None) -> list[PathSpec]:
    registry_path = path or REGISTRY_PATH
    data = json.loads(registry_path.read_text(encoding="utf-8"))
    return [PathSpec.from_dict(item) for item in data.get("paths", [])]


def registry_by_id(path: Path | None = None) -> dict[str, PathSpec]:
    return {spec.id: spec for spec in load_registry(path)}

