from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal, TypeAlias, cast

from intelligence.services import llm_refine
from intelligence.services.query_understanding import (
    QueryEnvelope,
    is_dated_market_review,
    is_market_watch_query,
)
from intelligence.services.research_contract import (
    AnswerOwner,
    RESEARCH_OWNER_IDS,
)
from intelligence.services.run_store import redact
from intelligence.workbench_skills.contracts import JsonValue, SkillDefinition
from intelligence.workbench_skills.registry import SKILL_REGISTRY

SkillMode: TypeAlias = Literal["manual", "auto", "hybrid"]
SkillSelectionSource: TypeAlias = Literal["manual", "rule", "llm"]
LLMComplete: TypeAlias = Callable[
    [list[dict[str, str]]], tuple[str | None, object | None, str]
]
@dataclass(frozen=True)
class SkillSelection:
    skill_id: str
    selection_source: SkillSelectionSource
    reason: str


@dataclass(frozen=True)
class SkillRouteResult:
    selections: tuple[SkillSelection, ...]
    fallback_to_ask: bool
    base_finance_fallback: bool = False


def _dedupe(values: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _rule_candidates(
    query: str, task_type: str, registry: Mapping[str, SkillDefinition]
) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    query_folded = query.casefold()
    task_folded = task_type.casefold()
    for skill_id in sorted(registry):
        matched = next(
            (
                trigger.strip()
                for trigger in registry[skill_id].triggers
                if trigger.strip()
                and (
                    trigger.strip().casefold() in query_folded
                    or trigger.strip().casefold() == task_folded
                )
            ),
            None,
        )
        if matched is not None:
            candidates.append((skill_id, f"规则匹配触发词“{redact(matched)}”"))
    return candidates


def _parse_llm_selection(
    content: str, registry: Mapping[str, SkillDefinition]
) -> list[SkillSelection] | None:
    try:
        value: JsonValue = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(value, dict) or set(value) != {"skill_ids", "reasons"}:
        return None
    skill_ids = value["skill_ids"]
    reasons = value["reasons"]
    if not isinstance(skill_ids, list) or not isinstance(reasons, dict):
        return None
    if any(not isinstance(skill_id, str) for skill_id in skill_ids):
        return None
    typed_ids = cast(list[str], skill_ids)
    if any(skill_id not in registry for skill_id in typed_ids):
        return None
    if set(reasons) != set(typed_ids):
        return None
    if any(
        not isinstance(reasons[skill_id], str) or not reasons[skill_id].strip()
        for skill_id in typed_ids
    ):
        return None
    return [
        SkillSelection(skill_id, "llm", redact(cast(str, reasons[skill_id])))
        for skill_id in _dedupe(typed_ids)
    ]


def route_skills(
    query: str,
    task_type: str,
    skill_mode: SkillMode,
    selected_skill_ids: Sequence[str],
    *,
    registry: Mapping[str, SkillDefinition] | None = None,
    llm_complete: LLMComplete | None = None,
    query_envelope: QueryEnvelope | None = None,
    answer_owner: AnswerOwner | None = None,
    inherited_skill_ids: Sequence[str] = (),
    excluded_skill_ids: Sequence[str] = (),
    execution_feedback: Sequence[Mapping[str, str]] = (),
) -> SkillRouteResult:
    active_registry = SKILL_REGISTRY if registry is None else registry
    complete = llm_refine.complete if llm_complete is None else llm_complete
    if skill_mode not in ("manual", "auto", "hybrid"):
        raise ValueError("Unknown skill mode")
    manual_ids = _dedupe(selected_skill_ids)
    unknown = [skill_id for skill_id in manual_ids if skill_id not in active_registry]
    if unknown:
        raise ValueError("Unknown skill id")
    if len(manual_ids) > 3:
        raise ValueError("manual skill selection supports at most 3 distinct ids")
    excluded = set(excluded_skill_ids)
    inherited_ids = [
        skill_id
        for skill_id in _dedupe(inherited_skill_ids)
        if skill_id in active_registry
        and skill_id not in excluded
        and (
            answer_owner is None
            or skill_id not in RESEARCH_OWNER_IDS
            or skill_id == answer_owner
        )
    ]

    manual = [
        SkillSelection(skill_id, "manual", "用户手动选择")
        for skill_id in manual_ids
        if answer_owner is None
        or skill_id not in RESEARCH_OWNER_IDS
        or skill_id == answer_owner
    ]
    owner_selection = (
        SkillSelection(answer_owner, "rule", "Controller 指定唯一答案 owner")
        if answer_owner is not None
        and answer_owner in active_registry
        and answer_owner not in excluded
        else None
    )
    if skill_mode == "manual":
        return SkillRouteResult(
            tuple(_unique_selections(manual)),
            fallback_to_ask=False,
            base_finance_fallback=not manual,
        )
    inherited = [
        SkillSelection(skill_id, "rule", "继承上一轮研究工具上下文")
        for skill_id in inherited_ids
    ]

    if query_envelope is not None and query_envelope.question_type in {
        "external_market",
        "concept_definition",
    }:
        automatic_registry: Mapping[str, SkillDefinition] = {}
    elif (
        query_envelope is not None
        and query_envelope.subject_kind == "market_pattern"
    ):
        automatic_registry = {
            skill_id: definition
            for skill_id, definition in active_registry.items()
            if skill_id != "theme-research"
        }
    else:
        automatic_registry = active_registry
    automatic_registry = {
        skill_id: definition
        for skill_id, definition in automatic_registry.items()
        if skill_id not in excluded and skill_id not in RESEARCH_OWNER_IDS
    }
    rules = _rule_candidates(query, task_type, automatic_registry)
    if (
        "daily-review" in automatic_registry
        and query_envelope is not None
        and is_dated_market_review(query, query_envelope)
        and all(skill_id != "daily-review" for skill_id, _reason in rules)
    ):
        rules.insert(0, ("daily-review", "规则识别指定日期行情复盘"))
    elif (
        "daily-review" in automatic_registry
        and is_market_watch_query(query)
        and all(skill_id != "daily-review" for skill_id, _reason in rules)
    ):
        rules.insert(0, ("daily-review", "规则识别当日盘面关注提问"))
    automatic = [SkillSelection(skill_id, "rule", reason) for skill_id, reason in rules]
    reserved_ids = {
        selection.skill_id
        for selection in (
            *([owner_selection] if owner_selection is not None else []),
            *([] if skill_mode == "auto" else manual),
            *inherited,
        )
    }
    available_slots = max(0, 3 - len(reserved_ids))
    if automatic_registry and available_slots > 0:
        rule_ids = {skill_id for skill_id, _ in rules}
        candidates = [
            {
                "skill_id": skill_id,
                "name": automatic_registry[skill_id].name,
                "description": automatic_registry[skill_id].description,
                "triggers": list(automatic_registry[skill_id].triggers),
                "rule_priority": skill_id in rule_ids,
            }
            for skill_id in sorted(automatic_registry)
        ]
        messages = [
            {
                "role": "system",
                "content": (
                    "Select zero or more semantically relevant skills from the full registry. "
                    "Rule-priority candidates are hints, not an allowlist. "
                    "Return strict JSON only: "
                    '{"skill_ids":[...],"reasons":{"id":"human reason"}}.'
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "query": query,
                        "task_type": task_type,
                        "max_skill_count": available_slots,
                        "candidates": candidates,
                        "prior_tool_attempts": [
                            {
                                "skill_id": str(item.get("skill_id") or ""),
                                "status": str(item.get("status") or ""),
                                "failure_reason": redact(
                                    str(item.get("failure_reason") or "")
                                ),
                            }
                            for item in execution_feedback
                        ],
                    },
                    ensure_ascii=False,
                ),
            },
        ]
        try:
            content, _provider, _failure_reason = complete(messages)
        except Exception:
            content = None
        if content is not None:
            llm_selection = _parse_llm_selection(content, automatic_registry)
            if llm_selection is not None:
                automatic = llm_selection

    manual_prefix = [] if skill_mode == "auto" else manual
    combined = [
        *([owner_selection] if owner_selection is not None else []),
        *manual_prefix,
        *inherited,
        *automatic,
    ]
    selected: list[SkillSelection] = []
    seen: set[str] = set()
    for selection in combined:
        if selection.skill_id not in seen:
            selected.append(selection)
            seen.add(selection.skill_id)
        if len(selected) == 3:
            break
    return SkillRouteResult(
        tuple(selected),
        fallback_to_ask=False,
        base_finance_fallback=not selected,
    )


def _unique_selections(
    selections: Sequence[SkillSelection],
) -> list[SkillSelection]:
    unique: list[SkillSelection] = []
    seen: set[str] = set()
    for selection in selections:
        if selection.skill_id not in seen:
            unique.append(selection)
            seen.add(selection.skill_id)
    return unique
