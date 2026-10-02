"""Output obligation identity shared by TaskFrame and research contracts.

Origins are assigned by trusted producers, not by model proposals. They describe
where a requirement came from, not proof that a natural-language interpretation
is correct. Legacy payloads keep their exact shape and effective required bit.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Literal, TypeAlias

GroundingMode: TypeAlias = Literal["evidence", "user_premise", "model_reasoning"]
OutputOrigin: TypeAlias = Literal[
    "legacy", "user_request", "runtime", "heuristic", "research_program",
    "model_plan", "method",
]
_ORIGINS = frozenset({
    "legacy", "user_request", "runtime", "heuristic", "research_program", "model_plan", "method",
})


@dataclass(frozen=True)
class RequiredOutput:
    output_id: str
    description: str
    evidence_types: tuple[str, ...] = ()
    required: bool = True
    grounding_mode: GroundingMode = "evidence"
    preplaced_gap: str = ""
    allowed_history_operations: tuple[str, ...] = ()
    origin: OutputOrigin = "legacy"
    # When aliases coalesce, retain all producer identities, not just the one
    # supplying the stronger obligation. Empty means only ``origin``.
    merged_origins: tuple[OutputOrigin, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.origin, str) or self.origin not in _ORIGINS:
            raise ValueError("unknown output origin")
        if type(self.required) is not bool:
            raise ValueError("output required must be boolean")
        if (
            not isinstance(self.merged_origins, tuple)
            or any(not isinstance(item, str) or item not in _ORIGINS for item in self.merged_origins)
            or tuple(sorted(set(self.merged_origins))) != self.merged_origins
            or (self.merged_origins and self.origin not in self.merged_origins)
        ):
            raise ValueError("merged output origins must be canonical and include origin")
        if "user_request" in (self.origin, *self.merged_origins) and not self.required:
            raise ValueError("user request cannot be optional")

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        if self.origin == "legacy":
            payload.pop("origin")
        if not self.merged_origins:
            payload.pop("merged_origins")
        return payload

    @classmethod
    def from_dict(cls, value: object) -> RequiredOutput:
        if not isinstance(value, dict):
            raise ValueError("required output must be an object")
        if set(value) - set(cls.__dataclass_fields__):
            raise ValueError("unknown required output fields")
        evidence = value.get("evidence_types", ())
        operations = value.get("allowed_history_operations", ())
        if not isinstance(evidence, (list, tuple)) or not isinstance(operations, (list, tuple)):
            raise ValueError("output evidence/operations must be lists")
        origins = value.get("merged_origins", ())
        if not isinstance(origins, (list, tuple)) or any(not isinstance(item, str) for item in origins):
            raise ValueError("merged output origins must be a list of strings")
        origin = value.get("origin", "legacy")
        required = value.get("required", True)
        grounding = value.get("grounding_mode", "evidence")
        if not isinstance(grounding, str) or grounding not in {"evidence", "user_premise", "model_reasoning"}:
            raise ValueError("invalid output grounding mode")
        if not isinstance(origin, str):
            raise ValueError("output origin must be a string")
        return cls(
            output_id=str(value.get("output_id") or ""),
            description=str(value.get("description") or ""),
            evidence_types=tuple(str(item) for item in evidence),
            required=required,
            grounding_mode=grounding,
            preplaced_gap=str(value.get("preplaced_gap") or ""),
            allowed_history_operations=tuple(str(item) for item in operations),
            origin=origin,
            merged_origins=tuple(origins),
        )


def merge_output_requirement(existing: RequiredOutput, incoming: RequiredOutput) -> RequiredOutput:
    """Coalesce one execution slot; a suggestion cannot erase a hard obligation.

    Execution evidence/grounding remains with the target slot. An incoming hard
    requirement owns its identity; otherwise retain the stronger existing one.
    """
    # Explicit user identity must not be overwritten by another required alias.
    def rank(item: RequiredOutput) -> tuple[bool, bool, bool]:
        return (item.required, item.origin == "user_request", item.origin == "runtime")

    owner = incoming if rank(incoming) >= rank(existing) else existing
    origins = tuple(sorted(set((
        existing.origin, *existing.merged_origins, incoming.origin, *incoming.merged_origins,
    ))))
    return replace(
        existing, required=existing.required or incoming.required, origin=owner.origin,
        merged_origins=origins if len(origins) > 1 else (),
    )
