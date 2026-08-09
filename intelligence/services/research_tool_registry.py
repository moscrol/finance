"""GenericResearchOwner 的类型化工具白名单。

工具仍复用已有 agent runner；本模块只负责能力声明、参数边界、去重和
公开 observation，避免第二套数据源实现。
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
import json
from types import MappingProxyType
from typing import Literal

from intelligence.services import agent_research, closed_loop_retrieval, query_ledger
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import (
    InformationCutoff,
    ResearchRunContext,
)


# 第四个字段 ``produces`` 声明该工具能贡献哪些 output_id（词表来自 task_frame.py
# 题型映射 + query_understanding.py operator 映射）。**保守声明，宁缺勿滥**——只
# 填能从 runner 代码路径确认的；拿不准就留空 frozenset()。
#
# ``produces`` 不改变路由，不改变工具可用性。它只服务于事前可满足性预检：
# 「这套授权工具在理论上能不能产出某个 required_output」。预检 fail-open——
# 声明不全只会漏抓，不会误拦（详见 ``check_satisfiability``）。
_DEFAULT_TOOL_METADATA: dict[str, tuple[str, str, str, frozenset[str]]] = {
    "finance_query": (
        "finance_query",
        "按语义数据集、指标、维度、筛选和时间范围查询本地结构化金融数据",
        "current",
        # risk_signals：实测 market_watch 回合里由 duckdb_semantic_query 绑定并判
        # fulfilled（3 例），不是推测。见 TestProducesMatchesHistory。
        #
        # ⚠️ 可复现性：证据来自 ~/tmp 和 ~/agent-memory/.foresight 下的
        # continuous-episode.json（gitignored、随清理消失）。观测时（2026-08-06）
        # 全部 45 份存在且可读，但这不可在 CI 里复验。将来对账发现这条可疑时，
        # 重跑 /tmp/check_produces_vs_history.py 的逻辑确认 episode 文件是否仍在。
        frozenset(
            {"supporting_evidence", "data_date", "market_change", "risk_signals"}
        ),
    ),
    "evidence_search": (
        "evidence_search",
        "对本地知识证据执行窄口径、宽口径和反方闭环检索",
        "current",
        frozenset({"supporting_evidence", "counterpoint"}),
    ),
    "kb_search": (
        "kb_search",
        "本地知识库检索",
        "stable",
        frozenset({"supporting_evidence", "direct_definition", "direct_explanation", "direct_answer"}),
    ),
    "web_search": (
        "web_search",
        "全网网页检索",
        "current",
        frozenset({"supporting_evidence", "event_facts", "impact_transmission"}),
    ),
    "news_search": (
        "news_search",
        "财经新闻检索",
        "current",
        frozenset({"supporting_evidence", "event_facts", "impact_transmission"}),
    ),
    "graph_lookup": (
        "graph_lookup",
        "知识图谱实体与关系",
        "stable",
        frozenset({"chain_mapping", "company_mapping", "relation_map"}),
    ),
    "evidence_lookup": (
        "evidence_lookup",
        "本地证据索引",
        "stable",
        frozenset({"supporting_evidence"}),
    ),
    "memory_lookup": (
        "memory_lookup",
        "用户自己过去的判断与纠偏原则（历史先验，不是市场事实）",
        "stable",
        # 有意留空：produces 词表里的 id 全是市场事实类产出，而本工具按定义只回
        # 历史先验。没有 episode 证据支持它 fulfill 过任何一项，按 fail-open
        # 约定空集只让它退出预检（漏抓），不会误拦。将来实测到再补。
        frozenset(),
    ),
    "l3_lookup": (
        "l3_lookup",
        "官方公告与互动证据",
        "current",
        frozenset({"supporting_evidence", "fact_value"}),
    ),
    "market_data": (
        "market_data",
        "结构化行情与市场时序",
        "current",
        frozenset({"current_baseline", "market_summary", "supporting_evidence", "data_date"}),
    ),
    "financial_data": (
        "financial_data",
        "结构化逐季财务指标",
        "current",
        frozenset({"financial_assessment", "metric_evidence", "supporting_evidence"}),
    ),
    "mainline_context": (
        "mainline_context",
        "同日主线与板块结构",
        "current",
        frozenset({"mainline_structure", "supporting_evidence"}),
    ),
}
DEFAULT_RESEARCH_CAPABILITIES = tuple(
    dict.fromkeys(
        capability
        for capability, _description, _freshness, _produces in _DEFAULT_TOOL_METADATA.values()
    )
)


class UnknownResearchTool(ValueError):
    """LLM 选择了未注册工具。"""


class InvalidResearchToolArguments(ValueError):
    """模型给出的工具参数不满足该工具自己的接口。"""

    def __init__(self, message: str, *, code: str = "invalid_arguments") -> None:
        super().__init__(message)
        self.code = code


QUERY_TOOL_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {"query": {"type": "string", "minLength": 1}},
    "required": ["query"],
    "additionalProperties": False,
}
EMPTY_TOOL_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}


ToolInput = object
ToolArgumentParser = Callable[
    [Mapping[str, object]],
    tuple[ToolInput, str],
]
def parse_query_arguments(
    arguments: Mapping[str, object],
) -> tuple[str, str]:
    if set(arguments) != {"query"}:
        raise InvalidResearchToolArguments("expected one query argument")
    query = arguments.get("query")
    if not isinstance(query, str) or not query.strip():
        raise InvalidResearchToolArguments(
            "query must be a non-empty string",
            code="invalid_query",
        )
    cleaned = query.strip()
    return cleaned, cleaned


def parse_snapshot_arguments(
    arguments: Mapping[str, object],
) -> tuple[str, str]:
    if arguments:
        raise InvalidResearchToolArguments("snapshot tool accepts no arguments")
    return "", "snapshot"


@dataclass(frozen=True)
class PreparedToolArguments:
    tool: str
    raw: Mapping[str, object]
    runner_input: ToolInput
    normalized_key: str
    display_query: str


ToolCutoffResolver = Callable[
    [PreparedToolArguments, ResearchRunContext],
    InformationCutoff,
]


@dataclass(frozen=True)
class ToolRunResult:
    evidence: tuple[agent_research.AgentEvidence, ...]
    observation: str
    trace: ProviderTrace
    gaps: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        evidence = tuple(self.evidence)
        if any(not isinstance(item, agent_research.AgentEvidence) for item in evidence):
            raise TypeError("tool evidence must contain AgentEvidence values")
        if not isinstance(self.trace, ProviderTrace):
            raise TypeError("tool trace must be a ProviderTrace")
        object.__setattr__(self, "evidence", evidence)
        object.__setattr__(self, "observation", str(self.observation or ""))
        object.__setattr__(
            self,
            "gaps",
            tuple(
                dict.fromkeys(
                    str(item).strip() for item in self.gaps if str(item).strip()
                )
            ),
        )


class ToolRunnerAdapter:
    """Normalize legacy tuple runners into the registry's one true result type."""

    def __init__(self, runner: agent_research.ToolRunner) -> None:
        self._runner = runner

    def __call__(
        self,
        value: ToolInput,
        context: agent_research.AgentToolContext,
    ) -> ToolRunResult:
        raw = agent_research._run_tool(self._runner, value, context)
        if isinstance(raw, ToolRunResult):
            return raw
        if not isinstance(raw, tuple):
            raise TypeError("research tool runner must return ToolRunResult")
        if len(raw) == 3:
            evidence, observation, trace = raw
            gaps: tuple[str, ...] = ()
        elif len(raw) == 4:
            evidence, observation, trace, raw_gaps = raw
            gaps = tuple(raw_gaps)
        else:
            raise TypeError("legacy research tool runner returned invalid result")
        return ToolRunResult(
            evidence=tuple(evidence),
            observation=str(observation or ""),
            trace=trace,
            gaps=gaps,
        )


def _freeze_json(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType(
            {str(key): _freeze_json(item) for key, item in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item) for item in value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError("tool schema must be JSON-compatible")


def _copy_json(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _copy_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_copy_json(item) for item in value]
    return value


def copy_tool_parameters(parameters: Mapping[str, object]) -> dict[str, object]:
    copied = _copy_json(parameters)
    if not isinstance(copied, dict):
        raise TypeError("tool parameters must be an object schema")
    return copied


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
    runner: agent_research.ToolRunner | ToolRunnerAdapter
    # 行为契约：什么时候该用它、怎样用才不误读、什么时候该换别的工具。
    #
    # ``description`` 只说「是什么」。马书 ch08 的结论是「优秀的工具提示词不是
    # 功能文档，而是行为契约」；ch27 模式六进一步给了理由——**时序对齐**：模型
    # 决定调用某工具时，该工具的约束正好在它的注意力焦点内，而写在系统提示词里
    # 的同一句话需要模型在数万 token 的上下文里「回忆」，长会话中不可靠。
    #
    # 空字符串合法：没有经过验证的契约就别写，编一句比不写更糟。
    contract: str = ""
    # ``episode`` means the tool returns one complete turn-scoped snapshot;
    # rewriting its query cannot produce a different evidence surface.
    query_scope: Literal["query", "episode"] = "query"
    parameters: Mapping[str, object] = field(
        default_factory=lambda: dict(QUERY_TOOL_PARAMETERS)
    )
    parse_arguments: ToolArgumentParser = parse_query_arguments
    cutoff_resolver: ToolCutoffResolver | None = None
    # 该工具能贡献哪些 output_id。声明式契约，服务于事前可满足性预检——
    # ``check_satisfiability`` 用它在工具真正运行前判断「这套工具理论上能否
    # 产出某 required_output」。空 frozenset 合法（保守声明：拿不准就留空，
    # 预检会 fail-open 放行，不会误拦）。
    produces: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if not isinstance(self.runner, ToolRunnerAdapter):
            object.__setattr__(self, "runner", ToolRunnerAdapter(self.runner))
        frozen_parameters = _freeze_json(self.parameters)
        if not isinstance(frozen_parameters, Mapping):
            raise TypeError("tool parameters must be an object schema")
        object.__setattr__(self, "parameters", frozen_parameters)
        if not isinstance(self.produces, frozenset):
            object.__setattr__(self, "produces", frozenset(self.produces))


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

    def authorized_specs(
        self,
        allowed: tuple[str, ...] | None = None,
    ) -> tuple[ToolSpec, ...]:
        """Return registered tools whose declared capability is authorized."""

        if allowed is None:
            return tuple(self._specs.values())
        allowed_set = set(allowed)
        return tuple(
            spec
            for spec in self._specs.values()
            if spec.capability in allowed_set
        )

    def tool_definitions(
        self,
        allowed: tuple[str, ...] | None = None,
    ) -> list[dict[str, object]]:
        """Expose the authorized read-only tools as function-call schemas."""

        return [
            {
                "type": "function",
                "function": {
                    "name": spec.name,
                    # 契约跟着工具描述走，而不是塞进系统提示词——见 ToolSpec.contract。
                    "description": (
                        f"{spec.description}\n{spec.contract}"
                        if spec.contract
                        else spec.description
                    ),
                    "parameters": copy_tool_parameters(spec.parameters),
                },
            }
            for spec in self.authorized_specs(allowed)
        ]

    def prepare(
        self,
        name: str,
        arguments: str | Mapping[str, object] | PreparedToolArguments,
    ) -> PreparedToolArguments:
        spec = self.resolve(name)
        if isinstance(arguments, PreparedToolArguments):
            if arguments.tool != spec.name:
                raise InvalidResearchToolArguments(
                    "prepared arguments belong to another tool"
                )
            return arguments
        if isinstance(arguments, str):
            raw: dict[str, object] = {"query": arguments}
        elif isinstance(arguments, Mapping):
            copied = _copy_json(arguments)
            if not isinstance(copied, dict):
                raise InvalidResearchToolArguments("tool arguments must be an object")
            raw = copied
        else:
            raise InvalidResearchToolArguments("tool arguments must be an object")
        try:
            runner_input, display_query = spec.parse_arguments(raw)
        except InvalidResearchToolArguments:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise InvalidResearchToolArguments(str(exc)) from exc
        try:
            canonical = json.dumps(
                raw,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        except (TypeError, ValueError) as exc:
            raise InvalidResearchToolArguments(
                "tool arguments must be JSON serializable"
            ) from exc
        normalized_key = (
            query_ledger.normalize_query(display_query)
            if set(raw) == {"query"} and isinstance(raw.get("query"), str)
            else canonical
        )
        return PreparedToolArguments(
            tool=spec.name,
            raw=raw,
            runner_input=runner_input,
            normalized_key=normalized_key,
            display_query=str(display_query or "").strip() or canonical,
        )

    def prompt_block(self, allowed: tuple[str, ...] | None = None) -> str:
        return "\n".join(
            f"- {spec.name}（{spec.capability}，{spec.cost}，{spec.freshness}）："
            f"{spec.description}"
            + (f"\n  · {spec.contract}" if spec.contract else "")
            for spec in self.authorized_specs(allowed)
        )

    def execute(
        self,
        name: str,
        arguments: str | Mapping[str, object] | PreparedToolArguments,
        *,
        context: ResearchRunContext,
        step_id: str,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> ToolObservation:
        spec = self.resolve(name)
        if spec.capability not in context.contract.allowed_capabilities:
            raise UnknownResearchTool(
                f"能力未授权：{spec.capability}（工具 {spec.name}）"
            )

        prepared = self.prepare(name, arguments)
        normalized = prepared.normalized_key
        effective_context = context
        if spec.cutoff_resolver is not None:
            requested_cutoff = spec.cutoff_resolver(prepared, context)
            if not isinstance(requested_cutoff, InformationCutoff):
                raise TypeError("tool cutoff resolver must return InformationCutoff")
            effective_context = replace(
                context,
                information_cutoff=InformationCutoff(
                    min(
                        context.information_cutoff.as_of_date,
                        requested_cutoff.as_of_date,
                    ),
                    requested_cutoff.source,
                ),
            )

        def fetch() -> ToolObservation:
            run_result = spec.runner(
                prepared.runner_input,
                agent_research.AgentToolContext(
                    effective_context.deadline,
                    is_cancelled or (lambda: False),
                    effective_context.information_cutoff,
                ),
            )
            evidence = list(run_result.evidence)
            observation = run_result.observation
            trace = run_result.trace
            gaps = run_result.gaps
            if is_cancelled is not None and is_cancelled():
                raise RuntimeError("agent tool cancelled")
            served_date = closed_loop_retrieval.latest_served_date(
                evidence,
                date_getter=lambda item: item.source_date,
            )
            if served_date is None:
                parsed_trade_date = closed_loop_retrieval.parse_source_date(
                    trace.source_trade_date
                )
                served_date = (
                    parsed_trade_date.isoformat()
                    if parsed_trade_date is not None
                    else None
                )
            evidence, rejected = closed_loop_retrieval.filter_future_dated(
                evidence,
                information_cutoff=effective_context.information_cutoff,
                date_getter=lambda item: item.source_date,
            )
            trace_trade_date = closed_loop_retrieval.parse_source_date(
                trace.source_trade_date
            )
            if (
                trace_trade_date is not None
                and trace_trade_date
                > effective_context.information_cutoff.as_of_date
                and evidence
                and not any(item.source_date for item in evidence)
            ):
                rejected.extend(evidence)
                evidence = []
            if rejected:
                observation = (
                    "；".join(
                        f"{item.title}：{item.detail[:80]}" for item in evidence
                    )
                    or "检索结果均因 future_of_cutoff 被过滤"
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
                status=(
                    "future_of_cutoff"
                    if rejected and not evidence
                    else trace.status
                ),
                detail=(
                    f"{trace.detail}; future_of_cutoff={len(rejected)}".strip("; ")
                    if rejected
                    else trace.detail
                ),
                result_count=len(evidence),
                parent_id=context.trace_parent_id,
                step_id=step_id,
                requested_date=(
                    trace.requested_date
                    or effective_context.information_cutoff.as_of_date.isoformat()
                ),
                served_date=served_date,
            )
            # The content hash is the stable identifier carried into
            # AgentOutcome/verifier. Do not mint a second observation-only ID.
            hashes = tuple(item.content_hash for item in evidence)
            return ToolObservation(
                tool=spec.name,
                query=prepared.display_query,
                evidence=tuple(evidence),
                observation=observation,
                trace=trace,
                gaps=gaps,
                evidence_hashes=hashes,
            )

        return query_ledger.executed(
            f"generic:{spec.name}",
            normalized,
            fetch,
            variant=(
                f"{spec.freshness};cutoff="
                f"{effective_context.information_cutoff.as_of_date.isoformat()}"
            ),
        )


# 行为契约（见 ``ToolSpec.contract``）。**只写验证过的**：每条要么来自线上实测的
# 失败模式，要么是复述 CLAUDE.md 里已有的红线。没有依据的宁可留空——工具提示词是
# 模型判断「该不该用、结果怎么读」的依据，编一句进去比不写更糟。
_TOOL_CONTRACTS: dict[str, str] = {
    "market_data": (
        "返回的是最近一个已收盘交易日的快照，不是实时也不一定是今天："
        "当日盘中或次日开盘前查询会回退到上一交易日，此时应明写数据截至日期，"
        "不要把它当作提问当天的行情。美股按北京时间 21:30→次日 04:00 跨日，"
        "北京时间凌晨查到的「前一天」通常是正在进行的那一场，不是数据过期。"
    ),
    "l3_lookup": (
        "查询成功不等于查到了证据：实测存在「company 查询成功但没有解析到可用证据」"
        "的情况。返回为空时只能说明本次没检索到，不能据此断言该公司没有相关公告，"
        "应写成明确的证据缺口而不是否定结论。"
    ),
    "web_search": (
        "网页与研报是二手材料，默认只能作为线索和上下文，不能直接当作公司级硬事实。"
        "订单/中标/产能/量产这类结论需要 l3_lookup 的公告或互动证据确认；"
        "只有网页来源时，写成「待验证线索」并点明缺的是哪一份一手材料。"
    ),
    "news_search": (
        "新闻是二手材料，同一条消息被多家转载不构成交叉验证。"
        "涉及公司经营事实时需要 l3_lookup 的公告确认；"
        "只有新闻来源时写成「待验证线索」，不要升级为既定事实。"
    ),
    # 依据在 ``market_financials`` 的块构造：口径行逐字写着「均为累计值（中报=上半年
    # 累计、三季报=前三季累计），本块不做单季还原」。而该模块的另一行「使用要求：…」
    # 会被 ``episode_tools._NON_EVIDENCE_PREFIXES`` 过滤掉，模型看不到——所以口径这条
    # 必须在工具契约里再说一次，不能指望它从证据正文里读到。
    "financial_data": (
        "返回的是已披露报告期的季报数据，不是当前状态：引用时必须带报告期，"
        "不要把「三季报净利」说成「当前净利」。数值为累计口径"
        "（中报=上半年累计、三季报=前三季累计），本工具不做单季还原；"
        "要单季必须显式声明是自己推算的。返回为空只说明这两个源没取到，"
        "应写成证据缺口，不得据此推断公司没有该项财务表现。"
    ),
    # memory_lookup 的 description 已声明「不是市场事实、不能当作证据引用」，这里只补
    # 它无法自述的那半条：空命中的含义。runner 的空分支返回「用户记忆无相关命中」，
    # 而「没查到用户说过」和「用户没有看法」是两件事。
    "memory_lookup": (
        "返回的是这位用户自己的历史判断与纠偏原则，属于先验而非市场事实，"
        "不能当作证据支撑当前世界的结论；绑定时用 user_premise。"
        "空命中只说明该主体此前没有留下记录，不等于用户没有看法，"
        "更不能反推市场事实——如实写「用户记忆无相关命中」即可。"
    ),
}


def default_registry(tools: dict[str, agent_research.ToolRunner]) -> ResearchToolRegistry:
    specs = tuple(
        ToolSpec(
            name=name,
            capability=name,
            description=description,
            contract=_TOOL_CONTRACTS.get(name, ""),
            cost="local" if freshness == "stable" else "external",
            freshness=freshness,
            runner=tools[name],
            query_scope=(
                "episode"
                if name in {"market_data", "financial_data", "mainline_context"}
                else "query"
            ),
            parameters=(
                EMPTY_TOOL_PARAMETERS
                if name in {"market_data", "financial_data", "mainline_context"}
                else QUERY_TOOL_PARAMETERS
            ),
            parse_arguments=(
                parse_snapshot_arguments
                if name in {"market_data", "financial_data", "mainline_context"}
                else parse_query_arguments
            ),
            produces=produces,
        )
        for name, (capability, description, freshness, produces) in _DEFAULT_TOOL_METADATA.items()
        if name in tools
    )
    return ResearchToolRegistry(specs)


# ---------------------------------------------------------------------------
# 事前可满足性预检（fail-open）
# ---------------------------------------------------------------------------

SatisfiabilityStatus = Literal["covered", "unknown", "suspicious"]


@dataclass(frozen=True)
class SatisfiabilityCheck:
    """单个 required_output 的事前可满足性判定结果。"""

    output_id: str
    status: SatisfiabilityStatus
    contributing_tools: tuple[str, ...] = ()
    reason: str = ""


def check_satisfiability(
    required_output_ids: tuple[str, ...] | list[str] | frozenset[str],
    authorized_specs: tuple[ToolSpec, ...] | list[ToolSpec],
    *,
    normalize: Callable[[str], str] | None = None,
) -> tuple[SatisfiabilityCheck, ...]:
    """事前预检：这套授权工具的 produces 并集能否覆盖每项 required_output。

    fail-open 判据：

    - ``covered``：至少一个工具声明了该 output_id → 放行
    - ``unknown``：没有工具声明过它 → 放行（未知≠不可能；声明不全只会漏抓）
    - ``suspicious``：所有相关工具（有非空 produces 的工具）都声明了、
      且都不含它 → 送裁定，不自动拦

    关键不变量：**声明不全只会漏抓，不会误拦**。一个不完整的 produces 表
    如果能造成误拦，它就成了新的静默失败源，比不做更糟。

    ``normalize`` 是 output_id 归一钩子（默认恒等）。契约侧与 produces 侧用的
    并非同一套字面 id：``evidence_boundary`` 在判缺时归一到 ``counterpoint``、
    ``direct_answer`` 归一到 ``direct_assessment``。不归一就比对，这两项会双双
    落到 ``suspicious``——实测 62 条真实 query 的 179 个 output 实例里，
    不归一 suspicious 占 53%，归一后 16%，**其中 65 个纯属字面差异**。
    归一表是 runtime 层的事实源（``_LEGACY_OUTPUT_ALIASES``），而本模块在
    services 层不得反向 import（``scripts/layer_audit.py`` 门禁），故以回调注入
    而非在此复制第二份。
    """

    def _identity(value: str) -> str:
        return value

    norm = normalize if callable(normalize) else _identity
    specs = tuple(authorized_specs)
    # 只看声明了非空 produces 的工具——空 produces 的工具（保守留空）不参与
    # 「全部声明了但都不含」的推理，因为它们没表态。
    declared_specs = tuple(spec for spec in specs if spec.produces)
    normalized_produces = {
        spec.name: frozenset(norm(item) for item in spec.produces) for spec in specs
    }
    all_declared: frozenset[str] = frozenset().union(
        *(normalized_produces[spec.name] for spec in declared_specs)
    ) if declared_specs else frozenset()

    results: list[SatisfiabilityCheck] = []
    for output_id in required_output_ids:
        normalized_id = norm(output_id)
        contributing = tuple(
            dict.fromkeys(
                spec.name
                for spec in specs
                if normalized_id in normalized_produces[spec.name]
            )
        )
        if contributing:
            results.append(
                SatisfiabilityCheck(
                    output_id=output_id,
                    status="covered",
                    contributing_tools=contributing,
                    reason=f"声明可产出该 output 的工具：{', '.join(contributing)}",
                )
            )
            continue
        # 没有任何工具声明它。区分两种情况：
        if not declared_specs:
            # 所有工具的 produces 都留空——完全未知，放行
            results.append(
                SatisfiabilityCheck(
                    output_id=output_id,
                    status="unknown",
                    reason="无工具声明了 produces，无法预判",
                )
            )
        else:
            # 有工具声明了 produces，但没人声明这个 output_id。
            # 如果它看起来像是一个已知词表里的 id（即在 all_declared 的「近邻」里），
            # 标为 suspicious；否则仍然 unknown（可能是声明表还没覆盖的新 id）。
            #
            # 判据保持保守：只要所有有声明的工具都没覆盖它，就标 suspicious 送裁定。
            # fail-open 的意思是「可疑项送裁定，不自动拦」——这里只是标记，不拦。
            results.append(
                SatisfiabilityCheck(
                    output_id=output_id,
                    status="suspicious",
                    reason=(
                        f"已声明的工具 produces 并集（{len(all_declared)} 项）"
                        f"不含此 output_id；可能需要额外工具或声明补充"
                    ),
                )
            )
    return tuple(results)
