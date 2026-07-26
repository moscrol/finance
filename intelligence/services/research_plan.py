"""Validated, provider-neutral research plans owned by the model."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Literal, cast


ResearchMode = Literal["quick", "deep"]

_PLAN_FIELDS = frozenset(
    {
        "kind",
        "task_summary",
        "answer_elements",
        "hypotheses",
        "evidence_needs",
        "candidate_actions",
        "open_gaps",
        "requested_mode",
        "revision",
    }
)
_MAX_SUMMARY_LENGTH = 500
_MAX_ITEM_LENGTH = 300


@dataclass(frozen=True)
class ResearchPlan:
    task_summary: str
    answer_elements: tuple[str, ...]
    hypotheses: tuple[str, ...]
    evidence_needs: tuple[str, ...]
    candidate_actions: tuple[str, ...]
    open_gaps: tuple[str, ...]
    requested_mode: ResearchMode
    revision: int = 1

    def __post_init__(self) -> None:
        requested_mode = self.requested_mode
        if requested_mode not in {"quick", "deep"}:
            raise ValueError("requested_mode must be quick or deep")
        if (
            isinstance(self.revision, bool)
            or not isinstance(self.revision, int)
            or self.revision < 1
        ):
            raise ValueError("revision must be a positive integer")
        object.__setattr__(
            self,
            "task_summary",
            _bounded_string(
                self.task_summary,
                field_name="task_summary",
                max_length=_MAX_SUMMARY_LENGTH,
            ),
        )
        for field_name, minimum, maximum in (
            ("answer_elements", 1, 8),
            ("hypotheses", 1, 4),
            ("evidence_needs", 1, 8),
            ("candidate_actions", 0, 8),
            ("open_gaps", 0, 8),
        ):
            object.__setattr__(
                self,
                field_name,
                _bounded_items(
                    getattr(self, field_name),
                    field_name=field_name,
                    minimum=minimum,
                    maximum=maximum,
                ),
            )


@dataclass(frozen=True)
class PlanParseResult:
    plan: ResearchPlan | None
    error: str = ""

    def __post_init__(self) -> None:
        if self.plan is not None and not isinstance(self.plan, ResearchPlan):
            raise ValueError("plan must be ResearchPlan or None")
        if not isinstance(self.error, str):
            raise ValueError("plan parse error must be a string")
        error = self.error.strip()
        if self.plan is not None and error:
            raise ValueError("plan parse result cannot contain plan and error")
        object.__setattr__(self, "error", error)


def _bounded_string(value: object, *, field_name: str, max_length: int) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    cleaned = value.strip()
    if not cleaned or len(cleaned) > max_length:
        raise ValueError(
            f"{field_name} must contain 1-{max_length} characters"
        )
    return cleaned


def _bounded_items(
    value: object,
    *,
    field_name: str,
    minimum: int,
    maximum: int,
) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name} must be an array")
    result: list[str] = []
    for item in value:
        cleaned = _bounded_string(
            item,
            field_name=f"{field_name} item",
            max_length=_MAX_ITEM_LENGTH,
        )
        if cleaned not in result:
            result.append(cleaned)
    if not minimum <= len(result) <= maximum:
        raise ValueError(
            f"{field_name} must contain {minimum}-{maximum} unique items"
        )
    return tuple(result)


def parse_research_plan(content: str) -> ResearchPlan:
    """Parse one closed PLAN object without granting execution authority."""

    if not isinstance(content, str):
        raise ValueError("plan content must be a string")
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError("PLAN must be one valid JSON object") from exc
    if not isinstance(payload, dict):
        raise ValueError("PLAN must be one JSON object")
    unknown = set(payload) - _PLAN_FIELDS
    missing = _PLAN_FIELDS - set(payload)
    if unknown:
        raise ValueError(f"unknown plan fields: {', '.join(sorted(unknown))}")
    if missing:
        raise ValueError(f"missing plan fields: {', '.join(sorted(missing))}")
    if payload["kind"] != "PLAN":
        raise ValueError("plan kind must be PLAN")

    return ResearchPlan(
        task_summary=cast(str, payload["task_summary"]),
        answer_elements=cast(tuple[str, ...], payload["answer_elements"]),
        hypotheses=cast(tuple[str, ...], payload["hypotheses"]),
        evidence_needs=cast(tuple[str, ...], payload["evidence_needs"]),
        candidate_actions=cast(tuple[str, ...], payload["candidate_actions"]),
        open_gaps=cast(tuple[str, ...], payload["open_gaps"]),
        requested_mode=cast(ResearchMode, payload["requested_mode"]),
        revision=cast(int, payload["revision"]),
    )


def parse_plan_candidate(content: str) -> PlanParseResult:
    """Recognize explicit PLAN output while leaving FINAL_JSON untouched."""

    try:
        payload = json.loads(content)
    except (TypeError, json.JSONDecodeError):
        if isinstance(content, str) and "PLAN" in content and "kind" in content:
            return PlanParseResult(None, "PLAN must be one valid JSON object")
        return PlanParseResult(None)
    if not isinstance(payload, dict) or "kind" not in payload:
        return PlanParseResult(None)
    try:
        return PlanParseResult(parse_research_plan(content))
    except ValueError as exc:
        return PlanParseResult(None, str(exc))


def validate_plan_revision(
    previous: ResearchPlan,
    current: ResearchPlan,
    *,
    original_task_id: str,
    current_task_id: str,
) -> None:
    if original_task_id != current_task_id:
        raise ValueError("plan revision must preserve task identity")
    if current.revision <= previous.revision:
        raise ValueError("plan revision must strictly increase")
    removed = tuple(
        item
        for item in previous.answer_elements
        if item not in set(current.answer_elements)
    )
    if removed:
        raise ValueError(
            "plan revision cannot remove answer elements: " + ",".join(removed)
        )


def plan_to_public_dict(plan: ResearchPlan) -> dict[str, object]:
    return {
        "task_summary": plan.task_summary,
        "answer_elements": list(plan.answer_elements),
        "hypotheses": list(plan.hypotheses),
        "evidence_needs": list(plan.evidence_needs),
        "candidate_actions": list(plan.candidate_actions),
        "open_gaps": list(plan.open_gaps),
        "requested_mode": plan.requested_mode,
        "revision": plan.revision,
    }


__all__ = [
    "PlanParseResult",
    "ResearchMode",
    "ResearchPlan",
    "parse_plan_candidate",
    "parse_research_plan",
    "plan_to_public_dict",
    "validate_plan_revision",
]
