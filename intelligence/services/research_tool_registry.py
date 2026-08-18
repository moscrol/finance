"""GenericResearchOwner 的类型化工具白名单。

工具仍复用已有 agent runner；本模块只负责能力声明、参数边界、去重和
公开 observation，避免第二套数据源实现。
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from functools import partial
import json
from types import MappingProxyType
from typing import TYPE_CHECKING, Literal

from intelligence.services.tool_payload import tool_payload_meta

from intelligence.services import agent_research, closed_loop_retrieval, query_ledger
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import (
    InformationCutoff,
    ResearchRunContext,
)

if TYPE_CHECKING:  # pragma: no cover
    # 只在类型检查期 import：episode_scope 运行期 import 本模块，反向的运行期
    # import 会成环。执行路径上 scope 是鸭子类型用的，不需要真的拿到这个类。
    from intelligence.services.episode_scope import EpisodeScope


# 工具流水线的阶段事件名。与 dsh 的 tools/* 同形，但串留在本仓命名空间下：
# 事件名会进 Trace 与评测 artifact，跟 dsh 的字面串绑死，将来换底座就得改数据。
#
# 定义在本模块而不是 episode_scope，是因为发射点在这里，且本模块是它的下层——
# 反过来会成环。episode_scope 转出这三个名字，供事件消费方 import。
TOOL_PRE_EXECUTE = "tool/pre_execute"
TOOL_RESULT = "tool/result"
TOOL_ERROR = "tool/error"


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
    "properties": {
        "query": {
            "type": "string",
            "minLength": 1,
            # 「必须在工具描述中加以说明」那一半（ch4 参数传递的保真性）：
            # 另一半是 execute() 把代偿写进 observation。两半都要有，
            # 只做转换不声明就是书里点名的静默输入转换。
            #
            # 实测依据：551 次 query 类调用里 276 次（50%）把整个参数对象
            # 又 JSON 编码了一遍，kb_search 高达 83%。见
            # ``unwrap_double_encoded_query`` 的 docstring。
            "description": (
                "检索词本身，纯文本。"
                '例："瑞华泰 聚酰亚胺薄膜 产能"。'
                '不要再包一层 JSON——写成 "{\\"query\\": \\"…\\"}" 时，'
                "系统会拆掉外层并在返回里说明，但那一轮已经浪费了。"
            ),
        }
    },
    "required": ["query"],
    "additionalProperties": False,
}
EMPTY_TOOL_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}


# 逐工具的 query 形状提示。**只给形状确实不同的那几个**，其余用通用描述——
# 每个工具都写一句会稀释掉真正重要的差异。
#
# 依据是 2026-08-12 的历史对账 + 代码核对，不是猜的：
#   evidence_lookup  28/28 空手。``KnowledgeAdapter.get_evidence`` 是
#                    ``item.get("target") != target`` **精确字符串相等**，
#                    无归一、无分词、无模糊。实测「瑞华泰」→3 条，
#                    「瑞华泰 688323 估值 PB 情景 保守 中性 乐观」→0 条。
#                    **工具没坏，是被当成搜索引擎用了。**
#   graph_lookup     0% 空手。它走 ``get_concept_matches`` 的打分模糊匹配，
#                    所以长 query 也能命中——正是这个对照证明了上面那条是形状问题。
#
# ch4 §工具描述的艺术：「清晰列出工具的边界条件——做不到什么、不接受什么输入
# ——往往比描述能力本身更重要」。
_QUERY_PARAM_HINTS: dict[str, str] = {
    "evidence_lookup": (
        "**必须是索引里登记的实体或概念名本身**，单个词，"
        "按精确字符串匹配——多加一个词就会零命中。"
        '例："瑞华泰"、"3D打印"。'
        '不要传检索短语：写成 "瑞华泰 688323 估值 PB 情景" 必然查不到任何东西。'
        "不确定名字怎么登记的，先用 graph_lookup 找到准确名称再来查。"
    ),
}


def query_parameters(tool: str) -> dict[str, object]:
    """按工具生成 query 参数 schema：形状不同的给专属提示，其余用通用描述。"""

    hint = _QUERY_PARAM_HINTS.get(tool)
    if not hint:
        return dict(QUERY_TOOL_PARAMETERS)
    base = QUERY_TOOL_PARAMETERS["properties"]["query"]
    assert isinstance(base, Mapping)
    return {
        **QUERY_TOOL_PARAMETERS,
        "properties": {"query": {**base, "description": hint}},
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


def unwrap_double_encoded_query(
    raw: Mapping[str, object],
) -> tuple[dict[str, object], str]:
    """模型把整个参数对象又 JSON 编码了一遍时，拆回来并**说出来**。

    失败形状（2026-08-12 历史对账，扫 44564 份 run 产物）：模型发出的
    ``query`` 值本身又是一个 JSON 串，例如
    ``{"query": "{\\"query\\":\\"瑞华泰 688323 D5 PB 情景估值\\"}"}``，
    于是检索器拿着那串花括号去做全文检索，必然空手。
    **551 次 query 类调用里 276 次（50%）是这个形状**，kb_search 高达 83%。

    同工具内部的对照（聚合相关性会误导，必须按工具分开看）：

    | 工具 | 包了的空手率 | 没包的空手率 |
    |---|---|---|
    | evidence_search | 100% (14/14) | 37% (7/19) |
    | web_search | 100% (4/4) | 14% (4/28) |
    | news_search | 46% | 55% ← **无效应** |

    即：它确实打死了 evidence_search 与 web_search，但**解释不了 news_search**。
    别把它当成所有空手的原因。

    ⚠ **必须告知模型，不能静默改**。ai-agent-book ch4「参数传递的保真性」把
    静默输入转换列为比功能缺失更隐蔽的反模式（Cursor 静默转换弯引号那个案例），
    并明确要求「如果确实需要对输入进行规范化处理，必须在工具描述中加以说明，
    并在工具返回中明确告知模型」。本函数只负责拆 + 生成告知文本，
    ``execute`` 负责把它拼进 observation，参数描述里另有一句写明。
    仓内先例：``finance_query.normalize_spec`` 的日期代偿就是这么做的。

    只拆**单键 query** 这一种形状。多键或键名不同的一律原样退回——
    认不出来就别动（BUILD 模式 7），猜着拆会把模型真正想搜的内容改掉。
    """

    if set(raw) != {"query"}:
        return dict(raw), ""
    value = raw.get("query")
    if not isinstance(value, str):
        return dict(raw), ""
    text = value.strip()
    if not (text.startswith("{") and text.endswith("}")):
        return dict(raw), ""
    try:
        inner = json.loads(text)
    except (TypeError, ValueError):
        return dict(raw), ""
    if not isinstance(inner, dict) or set(inner) != {"query"}:
        return dict(raw), ""
    unwrapped = inner.get("query")
    if not isinstance(unwrapped, str) or not unwrapped.strip():
        return dict(raw), ""
    return (
        {"query": unwrapped.strip()},
        (
            "已自动拆掉多包的一层 JSON（本次实际检索的是内层的检索词）；"
            "后续 query 请直接传检索词本身，不要再包一层 {\"query\": ...}"
        ),
    )


@dataclass(frozen=True)
class PreparedToolArguments:
    tool: str
    raw: Mapping[str, object]
    runner_input: ToolInput
    normalized_key: str
    display_query: str
    # 输入被规范化时的告知文本，由 ``execute`` 拼进 observation 交回模型。
    # 空串表示没做任何转换——这是常态，别默认非空。
    normalization_note: str = ""


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
    dataset: str = "unknown"
    caliber: str = ""
    payload_field_names: tuple[str, ...] = ()
    payload_sha256: str = ""

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
        dataset, caliber, names, digest = tool_payload_meta(
            dataset=self.dataset,
            caliber=self.caliber,
            field_names=self.payload_field_names,
        )
        object.__setattr__(self, "dataset", dataset)
        object.__setattr__(self, "caliber", caliber)
        object.__setattr__(self, "payload_field_names", names)
        object.__setattr__(self, "payload_sha256", digest)


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
    dataset: str = "unknown"
    caliber: str = ""
    payload_field_names: tuple[str, ...] = ()
    payload_sha256: str = ""


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
        raw, normalization_note = unwrap_double_encoded_query(raw)
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
            normalization_note=normalization_note,
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
        scope: EpisodeScope | None = None,
        tool_call_id: str = "",
    ) -> ToolObservation:
        """执行一个工具。

        ``scope`` 缺省为 ``None``，此时行为与接线前**逐字节一致**：不发事件、
        不登记调用。这是刻意的——现存三十余个调用方一个都不用改，
        阶段事件是给愿意传 scope 的调用方的增量能力，不是所有人的新负担。
        """

        spec = self.resolve(name)
        if spec.capability not in context.contract.allowed_capabilities:
            # 错误契约保持不变（仍抛 UnknownResearchTool、消息逐字不变）：
            # ``unknown_or_unauthorized_tool`` 这个串有 4 个生产者、1 个分支消费者
            # （agent_episode.py:311），并且进了模型可见的消息文本。拆它是一次
            # 有意的错误契约变更，不该混在「接入阶段事件」里做。
            #
            # 但**区分**不用等：它落进阶段事件（新增，无存量消费者），
            # 于是诊断拿到了区分，契约一点没动。
            if scope is not None:
                decision = scope.authorize(name)
                scope.emit(
                    TOOL_ERROR,
                    {
                        "tool": spec.name,
                        "tool_call_id": tool_call_id,
                        "step_id": step_id,
                        "stage": "authorize",
                        # 与 wire 上那个压扁的串不同，这里是分开的
                        "reason": decision.reason,
                        "capability": decision.capability,
                    },
                )
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
            if scope is not None:
                # 登记必须在 runner 真的被调起时发生，不在「决定要调」时。
                # 这个闭包由 query_ledger.executed 决定跑不跑——被去重挡掉的调用
                # 根本不进这里，于是可达性收据里也就不会把它记成跑过了。
                scope.record_invocation(spec.name)
                scope.emit(
                    TOOL_PRE_EXECUTE,
                    {
                        "tool": spec.name,
                        "tool_call_id": tool_call_id,
                        "step_id": step_id,
                        "capability": spec.capability,
                        "query": prepared.display_query,
                        "cutoff": (
                            effective_context.information_cutoff.as_of_date.isoformat()
                        ),
                    },
                )
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
            # 代偿必须让模型看见：输入被改过而不说，模型下一轮还会照原样写，
            # 且它无法自行诊断为什么检索总是空手（ch4「参数传递的保真性」）。
            if prepared.normalization_note:
                observation = "；".join(
                    part for part in (observation, prepared.normalization_note) if part
                )
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
            if scope is not None:
                scope.emit(
                    TOOL_RESULT,
                    {
                        "tool": spec.name,
                        "tool_call_id": tool_call_id,
                        "step_id": step_id,
                        "status": trace.status,
                        "evidence_count": len(evidence),
                        # hash 是带进 AgentOutcome/verifier 的稳定标识，
                        # 事件里带上它，Trace/UI/评测三者才对得上账。
                        "evidence_hashes": list(hashes),
                        "gaps": list(gaps),
                        "dataset": run_result.dataset,
                        "caliber": run_result.caliber,
                        "payload_field_names": list(run_result.payload_field_names),
                        "payload_sha256": run_result.payload_sha256,
                    },
                )
            return ToolObservation(
                tool=spec.name,
                query=prepared.display_query,
                evidence=tuple(evidence),
                observation=observation,
                trace=trace,
                gaps=gaps,
                evidence_hashes=hashes,
                dataset=run_result.dataset,
                caliber=run_result.caliber,
                payload_field_names=run_result.payload_field_names,
                payload_sha256=run_result.payload_sha256,
            )

        ledger_call = partial(
            query_ledger.executed,
            f"generic:{spec.name}",
            normalized,
            fetch,
            variant=(
                f"{spec.freshness};cutoff="
                f"{effective_context.information_cutoff.as_of_date.isoformat()}"
            ),
        )
        if scope is None:
            return ledger_call()
        try:
            return ledger_call()
        except BaseException as exc:
            # 只观测，不改变传播：事件发完原样 raise。吞掉异常会把一次失败静默成
            # 一次空结果，那正是 ToolPipeline docstring 里禁止的做法。
            # 捕 BaseException 是为了让取消（可能以 BaseException 子类抛出）
            # 也留下收据；因为立即 re-raise，不存在吞掉控制流的风险。
            scope.emit(
                TOOL_ERROR,
                {
                    "tool": spec.name,
                    "tool_call_id": tool_call_id,
                    "step_id": step_id,
                    "stage": "execute",
                    "error_type": type(exc).__name__,
                    "reason": str(exc),
                },
            )
            raise


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
    # 三条依据都在 ``episode_tools`` 的 runner 里，且 description 一条都没说：
    # ① ``_AGENT_FINANCE_QUERY_MAX_ROWS = 25`` 会把 limit 压到 25 行，observation 事后
    #    追一句「已截断至 N 条」——但那是**拿到结果之后**才看得到的，模型下单时不知道，
    #    最危险的读法是把 25 行的截断结果当全集做「全市场最高/唯一」这类全称断言。
    # ② 未授权历史窗口时 runner **直接不执行**（返回 parse_error + 空证据），
    #    不是查了没有。③ 空结果的 gap 逐字是「没有结构化结果」，是缺口不是否定结论。
    # 跨 dataset 字段混用**刻意不写**：description 已带 dataset_field_hint，且
    # ``finance_query.validation_retry_hint`` 现在会跨 dataset 指出字段归属，重复即噪声。
    "finance_query": (
        "结果会按 Agent 上下文预算截断（当前上限 25 行），返回的是满足条件的前若干行"
        "而不一定是全集：不要据此写「全市场最高」「只有这些」这类全称断言，"
        "需要更完整的切片就加筛选、分组或排序后再查一次。"
        "日期要放进 time_range，不要写成 filters 条件。"
        "当前任务未授权历史窗口时，旧日期的查询不会被执行而是直接退回，"
        "此时按提示把时间窗调回截止日附近，不要反复重试同一个窗口。"
        "返回为空只说明该 dataset 在这组条件与时点下没有结构化结果，"
        "应写成证据缺口，不得据此推断事实不存在。"
        "新高家数/新高结构类问题用 stock_high_daily（表内只含当日创新高的个股，"
        "按 high_period/sw_l1 分组计数即新高结构）；"
        "sector_stock_daily.high_status 显示「非新高」是事实标注，不是数据缺失。"
    ),
    # 依据在 ``evidence_search._project_evidence``：它把 ``conclusion`` 与
    # ``counter_clues`` 合成同一个 evidence 列表，stance（"支持"/"反方"）**只出现在
    # observation 文本的方括号前缀里**，AgentEvidence 对象本身不带这个字段。
    # 模型若只从证据列表引用而不看 observation 的前缀，会把反证当成支持性证据——
    # 这是这个工具独有的、description 完全没警告的误读。
    # 成本那句来自 2026-08-10 实测：冷调用 28.2s，占满当时 30s 工具批次的 94%。
    "evidence_search": (
        "这是一次调用内跑 narrow→broad→counter 三轮的闭环检索，"
        "返回的证据列表**同时包含支持与反方两类**，立场只标在观察文本的"
        "[支持] / [反方] 前缀上，证据条目本身不带立场字段："
        "引用前必须回观察文本核对该条属于哪一方，不要把反证当成支持性证据。"
        "它也是最慢的工具（实测冷调用可达 28 秒），"
        "只在确实需要反证或替代解释时用；单纯找资料用 kb_search。"
    ),
    # 复述 CLAUDE.md 的 PDF ingest 分层红线。kb_search 命中的是 wiki 实体页/概念页正文，
    # 而那些页面按来源分层写在不同 section 里：券商材料只进「## 高信度研究线索」
    # （fact_hardness=review_candidate）或「## 观察列表」，只有一手公司事实才在
    # 「## 边际变化」。检索命中不区分 section，模型看不到这层分级。
    "kb_search": (
        "命中的是本地知识库页面正文，而这些页面按来源分层："
        "「边际变化」是公告/订单/中标这类一手公司事实，"
        "「高信度研究线索」是券商研报的待复核判断，「观察列表」更弱。"
        "检索结果不带这层标记，引用前先看命中片段落在哪一节："
        "券商来源的结论只能作为待验证线索，需要 l3_lookup 的公告确认后才能当硬事实。"
        # 「无命中」与「检索失败」是两件事，契约必须先把它们分开再谈怎么读，
        # 否则这句话会教模型把工具故障读成「知识库没回填」。2026-08-12 实测：
        # 历史 22 次 kb_search 全部无命中，逐条统计 14 error + 6 timeout + 2 真 empty。
        "返回文本明确说「检索未能执行完成」时那是工具故障，不是知识库为空，"
        "此时既不能写成证据缺口也不能下否定结论，应改写检索词重试或换工具；"
        "只有在确实「无命中」时，才说明知识库没有回填过，且仍不等于该事实不存在。"
    ),
    # 两条依据都直接来自 ``agent_research.build_graph_tools._graph_lookup`` 的构造：
    # 概念项 detail 逐字是 f"匹配分 {score}"（文本匹配分，不是业务关联度）；
    # 公司项 detail 逐字是 f"{concept}｜{strength}/{evidence_layer}"。
    # 而 CLAUDE.md 规定研报级产业链归类一律降级 graph_only（strength=peripheral,
    # fact_hardness=research_claim）——即图谱里本来就混着大量未经确认的映射。
    "graph_lookup": (
        "返回的是图谱里已登记的映射关系，不是经过确认的公司级事实。"
        "概念项的「匹配分」只是文本匹配强度，不代表业务关联强度，不要当作重要性排序。"
        "公司项后面的 strength/evidence_layer 是这条映射的可信度分级："
        "peripheral 或研报推断来源的产业链归类只能作为线索，"
        "要断言某公司确有该业务，需要 l3_lookup 的公告或 kb_search 的一手事实确认。"
        "图谱无命中说明尚未登记该映射，不等于不存在关联。"
    ),
    # 依据在 ``_evidence_lookup`` 的 detail 构造：每条逐字带
    # f"（{source}，{source_date or '无日期'}，质量 {confidence or '?'}）"。
    # 这三个标记已经在证据正文里了，但没人告诉模型它们该怎么用——尤其
    # CLAUDE.md 的 broker_research_high 不得直接升级为 hard_fact 这条红线。
    "evidence_lookup": (
        "查的是已回填的本地证据索引，每条自带来源、日期与质量标记，"
        "引用时要把这三项一起带出：券商研报来源的条目属二手材料，"
        "不能直接升级成公司级硬事实；标着「无日期」的条目不能用来支撑时效性结论。"
        "索引是回填产物、覆盖并不均匀，无命中只说明没有登记过相关证据，"
        "应写成证据缺口，不是否定结论。"
    ),
    # 覆盖缺口是 2026-08-10 实测的库内事实（不写死日期，日期会过期）：
    # fact_mainline_stock_daily / theme_daily 只有 35 个交易日、起点晚于
    # sector 表（88 天），早期日期查不到题材级主线。runner 另有两个空分支：
    # 结构化主线比市场快照旧时返回 stale 结果，block 含「当前交易日的题材级主线未知」
    # 时按空处理——两者都不是「当天没有主线」。
    "mainline_context": (
        "同日主线结构来自本地库的主线表，而这几张表的覆盖并不是每个交易日都齐全，"
        "题材与个股两张的起始日明显晚于板块表，较早的日期查不到。"
        "返回为空或提示「题材级主线未知」，说明该交易日没有回填主线数据，"
        "不能据此说当天没有主线；数据比行情快照旧时会退回并说明，"
        "此时应写出数据截至日期，不要当作提问当天的主线。"
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
                else query_parameters(name)
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
