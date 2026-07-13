from __future__ import annotations

from collections.abc import Mapping, MutableMapping

from intelligence.workbench_skills.contracts import SkillDefinition, SkillExecutor

SKILL_REGISTRY: dict[str, SkillDefinition] = {}
SKILL_EXECUTORS: dict[str, SkillExecutor] = {}


class SkillRegistry:
    def __init__(
        self,
        definitions: Mapping[str, SkillDefinition] | None = None,
        executors: Mapping[str, SkillExecutor] | None = None,
    ) -> None:
        self.definitions = dict(definitions or {})
        self.executors = dict(executors or {})

    def register(
        self, definition: SkillDefinition, executor: SkillExecutor
    ) -> None:
        register_skill(
            definition,
            executor,
            registry=self.definitions,
            executors=self.executors,
        )


def builtin_skill_registry() -> SkillRegistry:
    return SkillRegistry(SKILL_REGISTRY, SKILL_EXECUTORS)


def register_skill(
    definition: SkillDefinition,
    executor: SkillExecutor,
    *,
    registry: MutableMapping[str, SkillDefinition] | None = None,
    executors: MutableMapping[str, SkillExecutor] | None = None,
) -> None:
    target_registry = SKILL_REGISTRY if registry is None else registry
    target_executors = SKILL_EXECUTORS if executors is None else executors
    if not definition.skill_id.strip():
        raise ValueError("skill id must be nonblank")
    if definition.skill_id in target_registry or definition.skill_id in target_executors:
        raise ValueError("duplicate skill id")
    if not isinstance(executor.skill_id, str) or not executor.skill_id.strip():
        raise ValueError("executor skill id must be nonblank")
    if executor.skill_id != definition.skill_id:
        raise ValueError("executor id mismatch")
    if any(
        not isinstance(value, str) or not value.strip()
        for value in (definition.name, definition.description, definition.version)
    ):
        raise ValueError("skill metadata must be nonblank")
    if not isinstance(definition.triggers, tuple) or any(
        not isinstance(trigger, str) or not trigger.strip()
        for trigger in definition.triggers
    ):
        raise ValueError("skill triggers must be nonblank strings")
    if not isinstance(definition.input_schema, dict):
        raise ValueError("skill input_schema must be an object")
    if definition.permissions != ("local_read",):
        raise ValueError("skill permissions must be exactly ('local_read',)")
    if (
        not isinstance(definition.timeout_seconds, int)
        or isinstance(definition.timeout_seconds, bool)
        or definition.timeout_seconds <= 0
    ):
        raise ValueError("skill timeout must be positive")
    target_registry[definition.skill_id] = definition
    target_executors[definition.skill_id] = executor


def _register_builtin_skills() -> None:
    from intelligence.workbench_skills.daily_agent import DailyAgentSkill
    from intelligence.workbench_skills.daily_review import DailyReviewSkill

    register_skill(
        SkillDefinition(
            skill_id="daily-review",
            name="每日复盘",
            description="把本地正式日报整理为原生结构化消息块。",
            version="1.0.0",
            triggers=(
                "复盘",
                "市场总览",
                "今日行情",
                "市场怎么样",
                "daily_review",
            ),
            input_schema={"type": "object", "additionalProperties": False},
            permissions=("local_read",),
            timeout_seconds=30,
        ),
        DailyReviewSkill(),
    )
    register_skill(
        SkillDefinition(
            skill_id="daily-agent",
            name="Daily Agent",
            description="把 canonical 日常研究雷达投影为候选、行动和证据模块。",
            version="1.0.0",
            triggers=("研究雷达", "研究队列", "今天研究什么", "daily_agent"),
            input_schema={"type": "object", "additionalProperties": False},
            permissions=("local_read",),
            timeout_seconds=30,
        ),
        DailyAgentSkill(),
    )


_register_builtin_skills()
