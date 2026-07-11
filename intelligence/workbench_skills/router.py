from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal, TypeAlias, cast

from intelligence.services import llm_refine
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
    content: str, allowlist: set[str], registry: Mapping[str, SkillDefinition]
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
    if any(skill_id not in registry or skill_id not in allowlist for skill_id in typed_ids):
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

    manual = [SkillSelection(skill_id, "manual", "用户手动选择") for skill_id in manual_ids]
    if skill_mode == "manual":
        return SkillRouteResult(tuple(manual), not manual)

    rules = _rule_candidates(query, task_type, active_registry)
    automatic = [SkillSelection(skill_id, "rule", reason) for skill_id, reason in rules]
    available_slots = 3 if skill_mode == "auto" else 3 - len(manual)
    if rules and available_slots > 0:
        allowlist = {skill_id for skill_id, _ in rules}
        candidates = [
            {
                "skill_id": skill_id,
                "name": active_registry[skill_id].name,
                "description": active_registry[skill_id].description,
                "triggers": list(active_registry[skill_id].triggers),
            }
            for skill_id in sorted(allowlist)
        ]
        messages = [
            {
                "role": "system",
                "content": (
                    "Select zero or more skills from the allowlist. Return strict JSON only: "
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
            llm_selection = _parse_llm_selection(content, allowlist, active_registry)
            if llm_selection is not None:
                automatic = llm_selection

    combined = ([] if skill_mode == "auto" else manual) + automatic
    selected: list[SkillSelection] = []
    seen: set[str] = set()
    for selection in combined:
        if selection.skill_id not in seen:
            selected.append(selection)
            seen.add(selection.skill_id)
        if len(selected) == 3:
            break
    return SkillRouteResult(tuple(selected), not selected)
