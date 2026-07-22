"""GenericResearchOwner 的类型化工具白名单。

工具仍复用已有 agent runner；本模块只负责能力声明、参数边界、去重和
公开 observation，避免第二套数据源实现。
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from intelligence.services import agent_research, query_ledger
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import ResearchRunContext


_DEFAULT_TOOL_METADATA: dict[str, tuple[str, str, str]] = {
    "kb_search": ("kb_search", "本地知识库检索", "stable"),
    "web_search": ("web_search", "全网网页检索", "current"),
    "news_search": ("news_search", "财经新闻检索", "current"),
    "graph_lookup": ("graph_lookup", "知识图谱实体与关系", "stable"),
    "evidence_lookup": ("evidence_lookup", "本地证据索引", "stable"),
    "l3_lookup": ("l3_lookup", "官方公告与互动证据", "current"),
    "market_data": ("market_data", "结构化行情与市场时序", "current"),
    "mainline_context": ("mainline_context", "同日主线与板块结构", "current"),
}
DEFAULT_RESEARCH_CAPABILITIES = tuple(
    dict.fromkeys(
        capability
        for capability, _description, _freshness in _DEFAULT_TOOL_METADATA.values()
    )
)


class UnknownResearchTool(ValueError):
    """LLM 选择了未注册工具。"""


@dataclass(frozen=True)
class ToolObservation:
    tool: str
    query: str
    evidence: tuple[agent_research.AgentEvidence, ...]
    observation: str
    trace: ProviderTrace
    gaps: tuple[str, ...] = ()
    evidence_hashes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ToolSpec:
    name: str
    capability: str
    description: str
    cost: str
    freshness: str
    runner: agent_research.ToolRunner


class ResearchToolRegistry:
    def __init__(self, specs: tuple[ToolSpec, ...]) -> None:
        self._specs = {spec.name: spec for spec in specs}

    def resolve(self, name: str) -> ToolSpec:
        spec = self._specs.get(str(name).strip())
        if spec is None:
            raise UnknownResearchTool(str(name))
        return spec

    def names(self) -> tuple[str, ...]:
        return tuple(self._specs)

    def capabilities(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(spec.capability for spec in self._specs.values()))

    def authorized_specs(self, allowed: tuple[str, ...] = ()) -> tuple[ToolSpec, ...]:
        """Return registered tools whose declared capability is authorized."""

        allowed_set = set(allowed)
        return tuple(
            spec
            for spec in self._specs.values()
            if not allowed_set or spec.capability in allowed_set
        )

    def tool_definitions(
        self,
        allowed: tuple[str, ...] = (),
    ) -> list[dict[str, object]]:
        """Expose the authorized read-only tools as function-call schemas."""

        return [
            {
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                        "additionalProperties": False,
                    },
                },
            }
            for spec in self.authorized_specs(allowed)
        ]

    def prompt_block(self, allowed: tuple[str, ...] = ()) -> str:
        return "\n".join(
            f"- {spec.name}（{spec.capability}，{spec.cost}，{spec.freshness}）：{spec.description}"
            for spec in self.authorized_specs(allowed)
        )

    def execute(
        self,
        name: str,
        query: str,
        *,
        context: ResearchRunContext,
        step_id: str,
    ) -> ToolObservation:
        spec = self.resolve(name)
        if (
            context.contract.allowed_capabilities
            and spec.capability not in context.contract.allowed_capabilities
        ):
            raise UnknownResearchTool(
                f"能力未授权：{spec.capability}（工具 {spec.name}）"
            )

        normalized = query_ledger.normalize_query(query)

        def fetch() -> ToolObservation:
            evidence, observation, trace = agent_research._run_tool(
                spec.runner,
                query,
                agent_research.AgentToolContext(context.deadline),
            )
            evidence = [
                item
                if item.content_hash
                else replace(
                    item,
                    content_hash=agent_research.evidence_content_hash(item),
                )
                for item in evidence
            ]
            trace = replace(
                trace,
                parent_id=context.trace_parent_id,
                step_id=step_id,
            )
            # The content hash is the stable identifier carried into
            # AgentOutcome/verifier. Do not mint a second observation-only ID.
            hashes = tuple(item.content_hash for item in evidence)
            return ToolObservation(
                tool=spec.name,
                query=normalized,
                evidence=tuple(evidence),
                observation=observation,
                trace=trace,
                evidence_hashes=hashes,
            )

        return query_ledger.executed(
            f"generic:{spec.name}",
            normalized,
            fetch,
            variant=spec.freshness,
        )


def default_registry(tools: dict[str, agent_research.ToolRunner]) -> ResearchToolRegistry:
    specs = tuple(
        ToolSpec(
            name=name,
            capability=name,
            description=description,
            cost="local" if freshness == "stable" else "external",
            freshness=freshness,
            runner=tools[name],
        )
        for name, (capability, description, freshness) in _DEFAULT_TOOL_METADATA.items()
        if name in tools
    )
    return ResearchToolRegistry(specs)
