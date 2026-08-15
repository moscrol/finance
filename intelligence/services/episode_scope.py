"""EpisodeScope 与 ToolPipeline：通用底座的两个接缝。

来源：``docs/superpowers/specs/2026-08-15-agent-base-dsh-absorption-design.md``
§7.1（显式工具流水线）与 §7.2（EpisodeScope 与能力可达性），实施顺序第 2 步。

本模块**只定义接缝，不改变任何现有行为**：没有任何现役调用方被改写，
registry / tool_batch / agent_episode 仍走原路径。接线是第 3 步的事。

--------------------------------------------------------------------------
为什么需要它
--------------------------------------------------------------------------

一个工具可能「定义了但没注册」「注册了但没授权」「授权了但模型看不见」
或者「看得见但入口分支根本不调」。这四段状态目前**没有任何一个地方能一次说清**：
``contract.allowed_capabilities`` 在 runtime/ 与 services/ 的十几处各读各的
（registry、episode_tool_batch、episode_tools、conversation_orchestrator、
headless_tool_gateway、codex_headless_runtime、openai_agents_runtime、
generic_research_owner、ask ……）。每处都自己判一次，就会各自漂移，
而漂移的时候没有任何断言会红——这正是 memory_lookup 那类「能力明明在，
但这一轮就是没被调用」的失败形状。

--------------------------------------------------------------------------
与 spec 字面的两处偏离（有意为之）
--------------------------------------------------------------------------

1. **不复制 ResearchRunContext 的字段。** spec §7.2 列了 policy / root_budget /
   information_cutoff 等字段，但这些**已经在** ``ResearchRunContext`` 上。
   照字面再抄一份会造出第二个事实源：两边都能改，改歪了没人知道是哪边。
   所以 Scope **持有** context 并派生，只自己拥有 context 里没有的东西
   （episode_id / user_id / registry / ledger / event_sink）。

2. **复用既有类型名，不引入平行词表。** spec 的 Protocol 写作
   ``PreparedTool`` / ``PublicToolResult``，但仓里已有
   ``PreparedToolArguments`` / ``ToolObservation`` 承担同样职责。
   两套名字并存会逼着每个读代码的人做一次心算翻译，且迟早有人把它们当成
   两种东西。dsh 阶段名与本仓类型名的对应关系记在 spec §7.1 的注记里。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, Protocol, runtime_checkable

from intelligence.services.research_tool_registry import (
    PreparedToolArguments,
    ResearchToolRegistry,
    ToolObservation,
    ToolRunResult,
    UnknownResearchTool,
)

if TYPE_CHECKING:  # pragma: no cover - 仅供类型检查，避免运行期循环 import
    from intelligence.services.evidence_ledger import EvidenceLedger
    from intelligence.services.research_contract import (
        InformationCutoff,
        ResearchPolicy,
        ResearchRunContext,
        RootBudgetLedger,
    )


# 可达性链条断裂的位置。做成 Literal 而不是裸字符串：这四个值会进 dump() 收据、
# 被分诊侧按值分支，裸串一旦拼错就是静默走空分支。
ReachabilityStage = Literal[
    "not_defined",
    "not_authorized",
    "not_model_visible",
    "not_invoked",
]


@runtime_checkable
class EventSink(Protocol):
    """Durable/Live 事件的出口。

    只声明「事件往哪去」，不规定事件怎么存——第 5 步做 Durable/Live 分类和
    Projection 时，实现方替换即可，Scope 这一侧不用动。
    """

    def emit(self, kind: str, payload: Mapping[str, object]) -> None: ...


@dataclass(frozen=True)
class ToolRequest:
    """模型发起的一次工具调用请求（尚未解析参数）。

    这是流水线的输入端。``tool_call_id`` 由调用方给定并**贯穿全流水线**：
    spec §7.1 验收要求「每次工具调用都有唯一 tool_call_id 和完整阶段事件」，
    没有它就无法把 Trace、UI 和评测 artifact 三者对账。
    """

    tool: str
    arguments: str | Mapping[str, object]
    tool_call_id: str


@dataclass(frozen=True)
class Authorization:
    """授权判定结果。

    刻意做成**值**而不是「抛异常 / 返回 bool」：
    - 抛异常（registry.execute 当前的做法）会把「未授权」和「工具不存在」
      压成同一个 ``UnknownResearchTool``，事后分诊分不出是哪种；
    - 裸 bool 带不走理由，而拒绝理由正是要写进阶段事件的东西。
    """

    allowed: bool
    tool: str
    # ``None`` 表示「这个工具压根没注册，谈不上能力」——与「注册了但能力未授权」
    # 是两回事。用空串当哨兵会让下游 `if not capability` 把两种情况又压回一起，
    # 而区分它们正是本类存在的理由。
    capability: str | None
    reason: str = ""

    def __post_init__(self) -> None:
        if self.allowed and self.reason:
            raise ValueError("授权通过时不应带拒绝理由")
        if not self.allowed and not self.reason.strip():
            raise ValueError("拒绝授权必须给出理由")
        if self.allowed and self.capability is None:
            raise ValueError("授权通过的工具必须有能力名")


@dataclass(frozen=True)
class ToolReachability:
    """一个工具在本次 Episode 里的可达性四段状态。

    四段是**递进**的：定义 → 授权 → 模型可见 → 实际调用。
    任何一段断掉，后面都不可能发生；断在哪一段决定了该去修哪一层，
    这是 ``dump()`` 存在的全部意义。
    """

    name: str
    capability: str
    defined: bool
    authorized: bool
    model_visible: bool
    invoked: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "capability": self.capability,
            "defined": self.defined,
            "authorized": self.authorized,
            "model_visible": self.model_visible,
            "invoked": self.invoked,
            "broken_at": self.broken_at(),
        }

    def broken_at(self) -> ReachabilityStage | None:
        """返回链条断在哪一段；``None`` 表示一路走到了实际调用。

        注意「未调用」不等于故障：模型有权不选某个工具。所以最后一段返回的是
        ``not_invoked`` 而不是 ``failed``——判读留给调用方，这里只陈述事实。
        """

        if not self.defined:
            return "not_defined"
        if not self.authorized:
            return "not_authorized"
        if not self.model_visible:
            return "not_model_visible"
        if not self.invoked:
            return "not_invoked"
        return None


@dataclass(frozen=True)
class EpisodeScope:
    """一次 Episode 的能力边界与派生视图的单一入口。

    ``registry`` / ``model-visible schemas`` / ``execution authorization`` /
    ``evidence context`` 都由它一次派生，调用方不再各自判一遍
    ``contract.allowed_capabilities``。
    """

    episode_id: str
    user_id: str
    context: ResearchRunContext
    registry: ResearchToolRegistry
    evidence_ledger: EvidenceLedger | None = None
    event_sink: EventSink | None = None
    # 本次实际发生过调用的工具名。可达性四段里的最后一段靠它填；
    # 由调用方在执行后登记（第 3 步接线时才有写入方，第 2 步只读）。
    invoked_tools: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if not str(self.episode_id).strip():
            raise ValueError("episode scope 必须携带 episode_id")
        if not isinstance(self.invoked_tools, frozenset):
            object.__setattr__(self, "invoked_tools", frozenset(self.invoked_tools))

    # ── 派生视图：以下全部从 context + registry 算出，不另存一份 ──────────

    @property
    def task_frame_hash(self) -> str:
        return self.context.contract.task_frame_hash

    @property
    def allowed_capabilities(self) -> tuple[str, ...]:
        return tuple(self.context.contract.allowed_capabilities)

    @property
    def trace_parent_id(self) -> str:
        """Trace 上下文。

        spec §7.2 要求 Scope 一次性派生 trace context；它就在 ``context`` 上，
        但此前没有从 Scope 这一侧暴露出来，``dump()`` 也看不到——于是「这次
        Episode 的事件挂在哪条 trace 下」在 Scope 的收据里是空白的。
        """

        return self.context.trace_parent_id

    @property
    def information_cutoff(self) -> InformationCutoff:
        return self.context.information_cutoff

    @property
    def root_budget(self) -> RootBudgetLedger | None:
        return self.context.root_budget

    @property
    def policy(self) -> ResearchPolicy:
        return self.context.policy

    def allowed_tools(self) -> tuple[str, ...]:
        """本次授权可用的工具名。"""

        return tuple(
            spec.name
            for spec in self.registry.authorized_specs(self.allowed_capabilities)
        )

    def model_visible_definitions(self) -> list[dict[str, object]]:
        """发给模型的 function-call schema。

        与 ``allowed_tools()`` 走的是同一个 ``authorized_specs``，所以
        「授权了但模型看不见」在当前实现下不可能发生。这不是废话——
        它把这条不变量**钉在一个地方**，将来谁想给模型单独过滤一层，
        就必须先改这里，改动会立刻暴露在 ``dump()`` 里。
        """

        return self.registry.tool_definitions(self.allowed_capabilities)

    def model_visible_names(self) -> frozenset[str]:
        """从**实际发给模型的那份 schema** 里读出工具名。

        刻意不走 ``authorized_specs``：那样这个集合就恒等于 ``allowed_tools()``，
        「授权了但模型看不见」这条不变量的检查会变成一句同义反复。要检查的正是
        schema 生成过程有没有把某个工具漏掉。

        schema 形状不合预期时 **fail closed**（抛错），不是跳过——认不出来就
        当作故障，否则漏掉的工具会静默从可见集合里消失，而那与「工具本来就
        不该可见」在收据上长得一模一样。
        """

        names: set[str] = set()
        for item in self.model_visible_definitions():
            function = item.get("function")
            if not isinstance(function, Mapping):
                raise TypeError("tool definition 缺少 function 段")
            name = function.get("name")
            if not isinstance(name, str) or not name:
                raise TypeError("tool definition 的 function.name 不是非空字符串")
            names.add(name)
        return frozenset(names)

    def authorize(self, tool: str) -> Authorization:
        """判定单个工具是否被本次 contract 授权。

        与 ``registry.execute`` 内联那次判定的差别只在**形态**（返回值 vs 抛异常），
        判据完全一致：``spec.capability in contract.allowed_capabilities``。
        第 3 步接线时由这里取代内联判定，语义不变。
        """

        try:
            spec = self.registry.resolve(tool)
        except UnknownResearchTool:
            # 只捕这一个。此前写的是裸 ``except Exception``，会把 registry 内部的
            # 真 bug（比如 spec 构造抛 TypeError）一律误诊成「工具未注册」——
            # 那恰好是本类要消灭的那种分诊压扁，只是换了个地方重演。
            return Authorization(
                allowed=False,
                tool=str(tool),
                capability=None,
                reason="工具未注册",
            )
        if spec.capability not in self.allowed_capabilities:
            return Authorization(
                allowed=False,
                tool=spec.name,
                capability=spec.capability,
                reason=f"能力未授权：{spec.capability}",
            )
        return Authorization(allowed=True, tool=spec.name, capability=spec.capability)

    def reachability(self) -> tuple[ToolReachability, ...]:
        """全注册表逐工具的四段状态。"""

        visible = self.model_visible_names()
        rows = []
        for name in self.registry.names():
            spec = self.registry.resolve(name)
            authorized = self.authorize(name).allowed
            rows.append(
                ToolReachability(
                    name=spec.name,
                    capability=spec.capability,
                    defined=True,
                    authorized=authorized,
                    model_visible=spec.name in visible,
                    invoked=spec.name in self.invoked_tools,
                )
            )
        return tuple(rows)

    def dump(self) -> dict[str, object]:
        """spec §7.2 验收要求的那份收据。

        故意包含 ``evidence_ledger`` / ``event_sink`` 的**挂载与否**而不是它们的
        内容：内容属于 Evidence Ledger 自己的账本，这里只回答「这次 Episode 有没有
        接上账本和事件出口」——两者为 None 时证据和事件会静默去不到任何地方，
        而那正是最难发现的一类故障。
        """

        return {
            "episode_id": self.episode_id,
            "user_id": self.user_id,
            "task_frame_hash": self.task_frame_hash,
            "trace_parent_id": self.trace_parent_id,
            "allowed_capabilities": list(self.allowed_capabilities),
            "allowed_tools": list(self.allowed_tools()),
            "evidence_ledger_attached": self.evidence_ledger is not None,
            "event_sink_attached": self.event_sink is not None,
            "root_budget_attached": self.root_budget is not None,
            "information_cutoff": self._cutoff_dict(),
            "policy_present": self.policy is not None,
            "invoked_tools": sorted(self.invoked_tools),
            "tools": [row.to_dict() for row in self.reachability()],
        }

    def _cutoff_dict(self) -> dict[str, str]:
        return self.information_cutoff.to_dict()


@runtime_checkable
class ToolPipeline(Protocol):
    """领域无关的工具执行流水线。

    金融层通过 Adapter 注入领域规则（截止日、查询语义、证据来源、hash、
    freshness、gaps、output binding），流水线本身不认识它们。

    与 dsh 阶段的对应关系（spec §7.1）：
    ``prepare``/``authorize``/``pre_execute`` 合并承担 dsh 的 ``tools/pre-execute``
    与 Guard；``execute``/``post_execute`` 对应同名阶段；``project_result``
    覆盖 dsh 中 definition-owned ``finalizeContent`` 与 ``tools/result`` 两段。

    ``project_result`` 单独成段而不是并进 ``post_execute``，是因为两者的
    受众不同：``post_execute`` 的产物进 Evidence Ledger（内部、可含 locator），
    ``project_result`` 的产物回模型和 UI（公开、不得含私有路径与凭证）。
    压成一段就没有地方安放这条边界。

    **阶段失败的归属（spec §7.1 验收：「任意阶段失败都转为结构化 Tool Result，
    不让结算代码成为新的失败源」）：不在本 Protocol 上。** 各阶段照常抛异常，
    由第 3 步接线的 runner 统一兜住并转成结构化结果。理由是现有的
    ``ToolRunResult`` / ``ToolObservation`` **都没有 status/error 位**，
    要让阶段自己返回结构化失败，得先给这两个类型加字段——那是改变现有行为，
    超出第 2 步「不改变现有行为」的边界。在此之前，实现方不要自行吞异常：
    吞掉就等于把失败静默成一次空结果。
    """

    def prepare(
        self, request: ToolRequest, scope: EpisodeScope
    ) -> PreparedToolArguments: ...

    def authorize(
        self, prepared: PreparedToolArguments, scope: EpisodeScope
    ) -> Authorization: ...

    def pre_execute(
        self, prepared: PreparedToolArguments, scope: EpisodeScope
    ) -> None: ...

    def execute(
        self, prepared: PreparedToolArguments, scope: EpisodeScope
    ) -> ToolRunResult: ...

    def post_execute(
        self, result: ToolRunResult, scope: EpisodeScope
    ) -> ToolRunResult: ...

    def project_result(
        self, result: ToolRunResult, scope: EpisodeScope
    ) -> ToolObservation: ...
