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
    allowed_permission_sets = {
        ("local_read",),
        ("local_read", "network_read"),
    }
    if definition.permissions not in allowed_permission_sets:
        raise ValueError("skill permissions contain unsupported values")
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
    from intelligence.workbench_skills.research_owner import (
        FINANCIAL_ANALYSIS,
        NEWS_IMPACT,
        STOCK_DEEP_DIVE,
        THEME_RESEARCH,
        ResearchOwnerSkill,
    )
    from intelligence.workbench_skills.us_ai_drawdown import UsAiDrawdownSkill

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
    register_skill(
        SkillDefinition(
            skill_id="us-ai-drawdown",
            name="美股 AI 回撤榜",
            description="抓取 Alpaca 复权日线，生成美股 AI 阵营最大回撤峰谷排序。",
            version="1.0.0",
            triggers=(
                "美股 AI 回撤",
                "美股AI回撤",
                "美股回撤榜",
                "AI 阵营回撤",
                "AI阵营回撤",
                "最大回撤排序",
            ),
            input_schema={"type": "object", "additionalProperties": False},
            permissions=("local_read", "network_read"),
            timeout_seconds=30,
        ),
        UsAiDrawdownSkill(),
    )
    for config, name, description, triggers in (
        (
            STOCK_DEEP_DIVE,
            "个股深挖",
            "围绕公司本体、硬证据、市场选择、生命周期与反证形成专项答案。",
            (
                "个股深挖",
                "深挖",
                "深度分析个股",
                "这只股怎么看",
                "股票怎么看",
                "上涨空间",
                "后续空间",
            ),
        ),
        (
            THEME_RESEARCH,
            "题材研究",
            "拆解题材定义、产业链、核心公司、市场阶段与反方线索。",
            (
                "题材研究",
                "题材雷达",
                "新词雷达",
                "题材",
                "板块",
                "产业链",
                "细分方向",
            ),
        ),
        (
            NEWS_IMPACT,
            "消息与公告冲击",
            "核对消息事实，推导产业链冲击、受益受损分层与证伪条件。",
            (
                "消息冲击",
                "公告冲击",
                "公告",
                "新闻",
                "事件影响",
                "催化",
                "传导",
            ),
        ),
        (
            FINANCIAL_ANALYSIS,
            "财报分析",
            "核对逐季财务与公告证据，判断增长质量、兑现节奏和后续验证。",
            (
                "财报分析",
                "财务分析",
                "业绩分析",
                "财报",
                "业绩兑现",
                "营收",
                "净利润",
                "毛利率",
                "净利率",
            ),
        ),
    ):
        register_skill(
            SkillDefinition(
                skill_id=config.skill_id,
                name=name,
                description=description,
                version="1.0.0",
                triggers=triggers,
                input_schema={"type": "object", "additionalProperties": False},
                permissions=("local_read",),
                timeout_seconds=240,
            ),
            ResearchOwnerSkill(config),
        )


_register_builtin_skills()
