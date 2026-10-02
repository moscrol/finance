"""Validated, provider-neutral research plans owned by the model."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Literal, cast


ResearchMode = Literal["quick", "deep"]

_REQUIRED_PLAN_FIELDS = frozenset(
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
_PLAN_FIELDS = frozenset((*_REQUIRED_PLAN_FIELDS, "branch_goals", "perspectives", "base_revision", "revision_reason"))
_MAX_SUMMARY_LENGTH = 500
_MAX_ITEM_LENGTH = 300


@dataclass(frozen=True)
class ResearchPerspective:
    perspective_id: str
    question: str
    status: Literal["open", "supported", "contested", "blocked", "not_relevant"]
    supporting_evidence: tuple[str, ...] = ()
    contradicting_evidence: tuple[str, ...] = ()
    assessment: str = ""
    next_check: str = ""

    def __post_init__(self) -> None:
        for name, maximum in (("perspective_id", 64), ("question", 300)):
            object.__setattr__(self, name, _bounded_string(
                getattr(self, name), field_name=name, max_length=maximum,
            ))
        if not isinstance(self.status, str) or self.status not in {"open", "supported", "contested", "blocked", "not_relevant"}:
            raise ValueError("invalid perspective status")
        for name in ("supporting_evidence", "contradicting_evidence"):
            values = _bounded_items(getattr(self, name), field_name=name, minimum=0, maximum=8)
            if any(re.fullmatch(r"E[1-9][0-9]{0,2}", item) is None for item in values):
                raise ValueError(f"{name} must contain evidence ordinals such as E1")
            object.__setattr__(self, name, values)
        for name in ("assessment", "next_check"):
            value = getattr(self, name)
            if not isinstance(value, str) or len(value.strip()) > _MAX_ITEM_LENGTH:
                raise ValueError(f"{name} must be a string of at most {_MAX_ITEM_LENGTH} characters")
            object.__setattr__(self, name, value.strip())
        if self.status == "supported" and not self.supporting_evidence:
            raise ValueError("supported perspective requires supporting_evidence")
        if self.status == "contested" and not self.contradicting_evidence:
            raise ValueError("contested perspective requires contradicting_evidence")
        if self.status in {"blocked", "not_relevant"} and not self.assessment:
            raise ValueError("blocked/not_relevant perspective requires assessment")


def perspective_to_dict(item: ResearchPerspective) -> dict[str, object]:
    return {
        "perspective_id": item.perspective_id,
        "question": item.question,
        "status": item.status,
        "supporting_evidence": list(item.supporting_evidence),
        "contradicting_evidence": list(item.contradicting_evidence),
        "assessment": item.assessment,
        "next_check": item.next_check,
    }


def _perspectives(value: object) -> tuple[ResearchPerspective, ...]:
    if not isinstance(value, (list, tuple)) or len(value) > 8:
        raise ValueError("perspectives must be an array of at most 8 items")
    result = []
    for item in value:
        if not isinstance(item, ResearchPerspective):
            if not isinstance(item, dict):
                raise ValueError("perspective must be an object")
            try:
                item = ResearchPerspective(**item)
            except TypeError as exc:
                raise ValueError("invalid perspective fields") from exc
        result.append(item)
    if len({item.perspective_id for item in result}) != len(result):
        raise ValueError("perspective_id must be unique")
    return tuple(result)


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
    branch_goals: tuple[str, ...] = ()
    perspectives: tuple[ResearchPerspective, ...] = ()
    # None retains the legacy additive protocol; 0 explicitly starts a revision chain.
    # This versions a model-owned plan, never the task/authorization contract.
    base_revision: int | None = None
    revision_reason: str = ""

    def __post_init__(self) -> None:
        if self.base_revision is not None and (
            type(self.base_revision) is not int or self.base_revision < 0
        ):
            raise ValueError("base_revision must be a non-negative integer")
        if not isinstance(self.revision_reason, str) or len(self.revision_reason.strip()) > _MAX_ITEM_LENGTH:
            raise ValueError("revision_reason must be a string of at most 300 characters")
        object.__setattr__(self, "revision_reason", self.revision_reason.strip())
        if self.revision_reason and self.base_revision is None:
            raise ValueError("revision_reason requires base_revision")
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
            ("answer_elements", 0 if self.base_revision is not None else 1, 8),
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
        object.__setattr__(
            self,
            "branch_goals",
            _bounded_branch_goals(self.branch_goals),
        )
        object.__setattr__(self, "perspectives", _perspectives(self.perspectives))


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


def _bounded_branch_goals(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError("branch_goals must be an array")
    result = _bounded_items(
        value,
        field_name="branch_goals",
        minimum=0,
        maximum=3,
    )
    if len(result) != len(value):
        raise ValueError("branch_goals must not contain duplicates")
    return result


def _decode_plan(content: str) -> object:
    fenced = re.fullmatch(
        r"\s*```(?:json)?\s*(\{.*\})\s*```(.*)", content, re.DOTALL | re.IGNORECASE,
    )
    raw = fenced.group(1) if fenced else content.lstrip()
    decoder = json.JSONDecoder()
    payload, end = decoder.raw_decode(raw)
    suffix = (raw[end:] + (fenced.group(2) if fenced else "")).strip()
    # Accept ordinary commentary, never another structured value or code block.
    if suffix:
        if any(char in suffix for char in "{}[]`"):
            raise json.JSONDecodeError("unexpected structured PLAN suffix", raw, end)
        try:
            decoder.raw_decode(suffix)
        except json.JSONDecodeError:
            pass
        else:
            raise json.JSONDecodeError("multiple PLAN values", raw, end)
    return payload


def parse_research_plan(content: str) -> ResearchPlan:
    """Parse one closed PLAN object without granting execution authority."""

    if not isinstance(content, str):
        raise ValueError("plan content must be a string")
    try:
        payload = _decode_plan(content)
    except json.JSONDecodeError as exc:
        raise ValueError("PLAN must be one valid JSON object") from exc
    if not isinstance(payload, dict):
        raise ValueError("PLAN must be one JSON object")
    unknown = set(payload) - _PLAN_FIELDS
    missing = _REQUIRED_PLAN_FIELDS - set(payload)
    if unknown:
        raise ValueError(f"unknown plan fields: {', '.join(sorted(unknown))}")
    if missing:
        raise ValueError(f"missing plan fields: {', '.join(sorted(missing))}")
    if payload["kind"] != "PLAN":
        raise ValueError("plan kind must be PLAN")
    if "base_revision" in payload and payload["base_revision"] is None:
        raise ValueError("base_revision must be a non-negative integer, not null")

    return ResearchPlan(
        task_summary=cast(str, payload["task_summary"]),
        answer_elements=cast(tuple[str, ...], payload["answer_elements"]),
        hypotheses=cast(tuple[str, ...], payload["hypotheses"]),
        evidence_needs=cast(tuple[str, ...], payload["evidence_needs"]),
        candidate_actions=cast(tuple[str, ...], payload["candidate_actions"]),
        open_gaps=cast(tuple[str, ...], payload["open_gaps"]),
        requested_mode=cast(ResearchMode, payload["requested_mode"]),
        revision=cast(int, payload["revision"]),
        branch_goals=cast(tuple[str, ...], payload.get("branch_goals", ())),
        perspectives=_perspectives(payload.get("perspectives", ())),
        base_revision=cast(int | None, payload.get("base_revision")),
        revision_reason=cast(str, payload.get("revision_reason", "")),
    )


def parse_plan_candidate(content: str) -> PlanParseResult:
    """Recognize PLAN candidates for validation, never infer execution authority."""

    try:
        payload = _decode_plan(content)
    except (TypeError, json.JSONDecodeError):
        if isinstance(content, str) and "PLAN" in content and "kind" in content:
            return PlanParseResult(None, "PLAN must be one valid JSON object")
        return PlanParseResult(None)
    if not isinstance(payload, dict):
        return PlanParseResult(None)
    if "kind" not in payload:
        # A complete plan body with only its discriminator missing still needs
        # PLAN repair, not the finish steering that asks the model to stop.
        # Do not insert kind or admit it: the strict parser must reject it.
        # Terminal fields win for untagged objects, even with invalid values;
        # ambiguous or merely partial shapes remain the finish lane's concern.
        plan_body = _REQUIRED_PLAN_FIELDS - {"kind"}
        terminal_fields = {"status", "draft", "gaps", "bindings", "render_from_claims"}
        if not plan_body <= payload.keys() or terminal_fields & payload.keys():
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
    if current.base_revision is not None:
        if current.base_revision != previous.revision:
            raise ValueError(f"base_revision must match accepted plan revision {previous.revision}")
        retracted = (
            set(previous.answer_elements) - set(current.answer_elements)
            or set(previous.branch_goals) - set(current.branch_goals)
            or {item.perspective_id for item in previous.perspectives}
            - {item.perspective_id for item in current.perspectives}
        )
        if retracted and not current.revision_reason:
            raise ValueError("retracting model-owned steps requires revision_reason")
        return
    if previous.base_revision is not None:
        raise ValueError("base_revision cannot be omitted after an explicitly based plan")
    removed = tuple(
        item
        for item in previous.answer_elements
        if item not in set(current.answer_elements)
    )
    if removed:
        raise ValueError(
            "plan revision cannot remove answer elements: " + ",".join(removed)
        )
    removed_branches = tuple(
        goal for goal in previous.branch_goals if goal not in set(current.branch_goals)
    )
    if removed_branches:
        raise ValueError(
            "plan revision cannot remove branch goals: "
            + ",".join(removed_branches)
        )
    removed_perspectives = {item.perspective_id for item in previous.perspectives} - {
        item.perspective_id for item in current.perspectives
    }
    if removed_perspectives:
        raise ValueError(
            "plan revision cannot remove perspectives; retain as not_relevant with assessment: "
            + ",".join(sorted(removed_perspectives))
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
        "branch_goals": list(plan.branch_goals),
        **({"perspectives": [perspective_to_dict(item) for item in plan.perspectives]}
           if plan.perspectives or plan.base_revision is not None else {}),
        **({"base_revision": plan.base_revision, "revision_reason": plan.revision_reason}
           if plan.base_revision is not None else {}),
    }


__all__ = [
    "PlanParseResult",
    "ResearchMode",
    "ResearchPlan",
    "ResearchPerspective",
    "perspective_to_dict",
    "parse_plan_candidate",
    "parse_research_plan",
    "plan_to_public_dict",
    "validate_plan_revision",
]
