"""ResearchHarness：底座 loop 调领域门的接缝。

来源：``docs/superpowers/specs/2026-09-02-research-harness-loop-decouple-design.md``。

--------------------------------------------------------------------------
它解决什么
--------------------------------------------------------------------------

「金融题怎样才算答完」这组规则——FINAL_JSON 契约、证据绑定展开、驳回分类、
批后停机——此前**手焊在三条 loop 里**（``agent_episode`` 5 处、
``openai_agents_runtime`` 2 处、``codex_headless_runtime`` 3 处）。改一次口径要改
十处，漏一处不会红；换一条 loop 就得把这十处重抄一遍。

本模块把这些规则收成一个 Protocol。loop 只管「调模型、派工具、算超时」，
到了要判「这答案能不能发」「还要不要继续查」的时候，问 harness。

--------------------------------------------------------------------------
与 pi / dsh 的对应（原文，不是转述）
--------------------------------------------------------------------------

===================  ===========================  ==============================
本模块                pi ``AgentLoopConfig``       dsh 扩展点
===================  ===========================  ==============================
assemble_prompt      transformContext             system-prompt spine
steering_message     transformContext（注入）      agent/pre-step → enter(messages)
interpret_plan       **—（pi 没有）**              **—（dsh 没有）**
govern_mode          **—（pi 没有）**              **—（dsh 没有）**
project_tool_result  afterToolCall.content        tools/result（definition-owned finalizeContent）
project_tool_error   afterToolCall.isError+content tools/post-execute → block(feedback)
halt_after_tool_batch afterToolCall.terminate     tools/post-execute → block
fallback_after_empty_batch **—（pi 没有）**       **—（dsh 没有）**
retrieval_complete   shouldStopAfterTurn          —
admit_finish         **—（pi 没有）**              **—（dsh 没有）**
classify_repair_need **—（pi 没有）**              **—（dsh 没有）**
warrant_repair       **—（pi 没有）**              **—（dsh 没有）**
downgrade_unreachable **—（pi 没有）**             **—（dsh 没有）**
repair_goal_message  transformContext（注入）      agent/pre-step → enter(messages)
admit_repair_result  **—（pi 没有）**              **—（dsh 没有）**
===================  ===========================  ==============================

修复轮（`2026-09-02-repair-policy-state-machine.md`）两家也没有——它们的 loop 停下就是
停下，没有「验证驳回后再来一轮」。五个方法按修复轮的时序：``classify_repair_need``
（这次失败该修什么、属哪类、要补几个格、要不要重开工具）与 ``warrant_repair``（这个
tier 还容忍这一轮吗、上一轮有进展吗）是**申请**，底座 ``runtime/repair_budget`` 据此
铸窗或拒绝——领域不碰账本；``downgrade_unreachable`` 判哪些必填格这一轮结构性补不上
（没工具就变不出新证据），把契约与模型侧目标一起降级；``repair_goal_message`` 是修复轮
开场对模型说的话（REPAIR_GOAL 正文 + 工具开/关两套指令）；``admit_repair_result`` 判
「修完算不算进步」（换了稿或绑定才算，没动手也没改就是 stop）。「付不付得起、几个格折
几次调用」是预算，不在这里。

``govern_mode``（研究该做多深：quick / deep）也是两家没有的：它们的 loop 不分档。
深度裁决读的是任务框架与 PLAN（领域）；裁决落到 context 上的是预算上限（底座会计），
由 loop 拿着 ``decision`` 调 ``runtime/tier_promotion.apply_mode_promotion``——本方法
只出裁决与话，不碰账本，与修复轮「领域申请、底座授予」同形。

PLAN 是本领域的研究协议（先出计划再动手），两家都没有；它和 ``admit_finish``
一样只能是领域方法。``steering_message`` 是领域在驳回 / 关闭研究阶段时对模型说的
话——第二条 loop 若要「是同一台机器」，这些字节必须来自同一处。
``project_tool_result`` 决定一次工具观察**审计留什么、模型看什么**：审计底稿全量
（含 hash / telemetry），模型视图去重、预算、去 hash 只留 E<n>——这条边界是
2026-08 B1/B7 零绑定事故（模型誊抄 16-hex）之后立的，不能因为换 loop 而漂。

``fallback_after_empty_batch``（`2026-09-02-empty-pool-fallback-state-machine.md`）两家也没有：
一批工具跑完、下一次问模型之前，loop 替模型**自己补发**一次查询——某个 ``sector_daily`` 池开场
预取空表且首轮 0 行时换同窗成交额前排，恰好一次。该不该补、补什么、什么叫「池空」、as-of
怎么取，全是领域（九道判定，`services/empty_pool_fallback`）；剩余槛够不够、怎么派、记哪笔账
是底座。loop 递它拥有的事实（本批结果、可派工具集、事件流、阶段），领域返回一条要派的调用或
``None``。

两家的 loop 都在「模型不再调工具」处停。我们多一道终局准入：模型说完了，
还要过契约与证据绑定。它挂不上任何一家的现成钩子——这是 08-15 §14 第一刀
（通用底座不管对错）的**正确结果**，不是缺陷，所以它只能是领域 Harness 的方法。

--------------------------------------------------------------------------
纪律
--------------------------------------------------------------------------

- ``FinanceResearchHarness`` 是对既有函数的**纯委托**：没有新判定。改口径改
  ``episode_protocol`` / ``forecast_residual_budget``，不改这里。
- harness **不持有 loop 状态**。四个方法都是（context, evidence, registry）→ 值。
- 本模块只 import ``services.*``（``scripts/layer_audit.py``：领域层不得依赖底座）。
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Set
from dataclasses import dataclass, replace
import json
from typing import Literal, Protocol, runtime_checkable

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import (
    AgentOutcome,
    EpisodeStatus,
    ModelToolCall,
    OutputEvidenceBinding,
    public_agent_evidence,
)
from intelligence.services.episode_messages import EpisodeMessage
from intelligence.services.empty_pool_fallback import (
    EmptyToolCall,
    fallback_already_attempted,
    prefetch_pool_is_empty,
    propose_empty_pool_fallback,
)
from intelligence.services.episode_protocol import (
    RejectionResponse,
    attach_evidence_ordinals,
    evidence_ordinal_table,
    expand_episode_snapshot_bindings,
    finish_rejection_fields,
    rejection_response,
    split_episode_prompt,
    strip_hashes_for_model,
    validate_episode_finish,
)
from intelligence.services.forecast_residual_budget import (
    forecast_residual_halt_reason,
)
from intelligence.services.mode_governor import (
    ModeDecision,
    ModeGovernor,
    ModeSignals,
)
from intelligence.services.episode_verifier import VerifiedEpisodeOutcome
from intelligence.services.mandatory_satisfiability import (
    apply_unreachable_downgrade,
    evidence_required_output_ids,
)
from intelligence.services.repair_coordinator import (
    ProgressSnapshot,
    RepairGoal,
    RepairNeed,
    RepairWarrant,
    classify_repair_need,
    unreachable_repair_goal,
    warrant_repair,
)
from intelligence.services.track_contract import TRACK_CONTRACT_OUTPUT_ID_SET
from intelligence.services.research_contract import (
    ResearchRunContext,
    ResearchTaskContract,
)
from intelligence.services.research_plan import (
    PlanParseResult,
    ResearchPlan,
    parse_plan_candidate,
    validate_plan_revision,
)
from intelligence.services.research_tool_registry import (
    ResearchToolRegistry,
    ToolObservation,
)
from intelligence.services.task_frame import TaskFrame
from intelligence.services.tool_observation_noise import prune_tool_observation
from intelligence.services.tool_result_budget import (
    budget_tool_observation,
    lean_observation_enabled,
    lean_tool_observation,
)

__all__ = [
    "BranchOutcome",
    "FallbackCall",
    "FinanceResearchHarness",
    "FinishAdmission",
    "ModeGovernance",
    "ModeSignalsFactory",
    "RepairDowngrade",
    # 值类型：修复轮五个方法的签名都收 / 发它。第二条 loop 只从本模块取名字，
    # 所以它也是 harness 公开面的一部分。
    "RepairGoal",
    "RepairVerdict",
    "ResearchHarness",
    "SteeringKind",
    "ToolCallOutcome",
    "ToolResultProjection",
    "default_mode_signals",
]


class BranchOutcome(Protocol):
    """一条只读子研究分支回来的东西——按结构声明，不 import runtime。

    ``intelligence.runtime.sub_research.BranchResult`` 天然满足它。领域层不能依赖
    底座（``scripts/layer_audit.py``），所以这里只写「长什么样」，不写「是谁」。
    """

    @property
    def branch_id(self) -> str: ...

    @property
    def goal(self) -> str: ...

    @property
    def status(self) -> str: ...

    @property
    def evidence(self) -> tuple[AgentEvidence, ...]: ...

    @property
    def gaps(self) -> tuple[str, ...]: ...

class ToolCallOutcome(Protocol):
    """一批工具里的一条结果——按结构声明，不 import runtime。

    ``intelligence.runtime.episode_tool_batch.ToolCallResult`` 天然满足它。空池回退只看
    「哪个工具、什么参数、结果是不是空」，不看观察正文。
    """

    @property
    def call(self) -> ModelToolCall: ...

    @property
    def status(self) -> str: ...


@dataclass(frozen=True)
class FallbackCall:
    """loop 在本批之后、下一次问模型之前，替模型补发的一次工具调用。

    ``call`` 交给批次执行器原样派发；``request_extras`` 是领域要盖在 ``tool_request`` 事件上的
    标记（``fallback_query`` / ``original_arguments`` / ``as_of``）——「恰好一次」靠扫这个标记
    判定，所以它必须进 durable 事件，不能只留在内存。
    """

    call: ModelToolCall
    request_extras: dict[str, object]


ModeSignalsFactory = Callable[[TaskFrame, ResearchPlan], ModeSignals]


def default_mode_signals(task_frame: TaskFrame, plan: ResearchPlan) -> ModeSignals:
    """从任务框架与 PLAN 读出可观测的深度信号（原 agent_episode._default_mode_signals）。"""

    user_task = task_frame.to_user_task()
    return ModeSignals(
        independent_entities=len(user_task.subjects),
        separable_branches=len(plan.branch_goals),
        evidence_domains=plan.evidence_needs,
        uncovered_answer_elements=len(plan.open_gaps),
    )

# loop 在四个时点需要对模型说一段领域的话。做成 Literal 而不是四个方法：
# 每段话的**时点**是底座的事（什么时候驳回、什么时候关研究阶段、修复动作
# 跑完什么时候收口），**内容**是领域的事；一个方法一个枚举，时点和内容的边界
# 正好落在参数上。``repair_finalize`` 没有 detail，传空串。
SteeringKind = Literal[
    "invalid_plan", "invalid_finish", "begin_finalization", "repair_finalize"
]


@dataclass(frozen=True)
class FinishAdmission:
    """终局准入的结果——把「异常驱动的控制流」改成值。

    此前 loop 在五个地方各写一遍 ``try: validate … except ValueError: 分类 / 分流``。
    做成值之后 loop 只问 ``accepted``，驳回时要记进事件的字段全在这里，
    不必再从异常对象上 ``getattr`` 一层层挖。

    接受时：``status`` / ``draft`` / ``bindings`` / ``gaps`` / ``caveat_slips`` 已是
    **最终值**——bindings 做过 snapshot 与比较集展开，gaps 已合并声明 gap 与
    绑定 gap。loop 不再自己拼这两步。``rejection`` 是无拒收的占位字段
    （``code=none``），可直接 ``**`` 进 finish 事件。

    ``declared_gaps`` 是模型在 FINAL_JSON 里**自己声明**的 gap，未与绑定 gap 合并。
    三条 loop 的 gap 口径不同：``agent_episode`` 用合并后的 ``gaps``；
    ``openai_agents_runtime`` / ``codex_headless_runtime`` 只并入声明 gap
    （各自再叠 snapshot gap / issue）。两者都从这一个值对象取，谁也不用再解析一遍。
    统一口径是 P1b 之后的事，本值对象先把两种事实都摆出来。

    驳回时：``reason`` 是原异常文本；``kind`` 是 ``RejectionKind.value`` 或
    ``"unclassified"``；``response`` 是该类别的处置（回灌 / 恢复 / 停因）；
    ``rejection`` 是 ``finish_rejection_fields(exc)``。
    """

    accepted: bool
    status: EpisodeStatus | None
    draft: str
    bindings: tuple[OutputEvidenceBinding, ...]
    gaps: tuple[str, ...]
    caveat_slips: int
    rejection: dict[str, str]
    declared_gaps: tuple[str, ...] = ()
    reason: str = ""
    kind: str = ""
    response: RejectionResponse | None = None

    def __post_init__(self) -> None:
        if self.accepted:
            if self.status is None:
                raise ValueError("接受的终局必须带 status")
            if self.response is not None or self.reason:
                raise ValueError("接受的终局不应带驳回处置")
        else:
            if self.response is None or not self.reason.strip():
                raise ValueError("驳回必须带处置与理由")


@dataclass(frozen=True)
class ToolResultProjection:
    """一次成功工具观察的两个出口。

    ``audit_payload``：进 durable ``tool_result`` 事件的底稿——全量，含 hash、
    ``evidence_ids``、``telemetry``。loop 再叠 ``call_id`` 与计时（那是底座的账）。

    ``model_content``：``role=tool`` 消息正文——已去重叙述、按预算截断、去掉 hash
    只留 ``E<n>``。**这两份不是同一份 dict 的两次序列化**：审计要全量、模型要够用，
    同一份事实两个出口，边界由领域定。

    ``seen_prose``：观察叙述去重账本的新状态。loop 保存，下一次原样传回。
    """

    audit_payload: dict[str, object]
    model_content: str
    seen_prose: frozenset[str]


@dataclass(frozen=True)
class RepairDowngrade:
    """修复轮开场前的裁决：哪些必填格这一轮结构性补不上，契约与目标随之降级。

    ``unreachable`` 为空时 ``contract`` / ``goal`` 就是传进来的原对象（loop 用 ``is``
    判有没有降级，这一点是合同）。非空时 ``contract`` 是降级后的契约（那些格不再
    必填、evidence 要求不再 mandatory），``goal`` 是去掉不可达格的模型侧目标；
    观测用的原始 goal 由 loop 自己继续投递。
    """

    unreachable: tuple[str, ...]
    contract: ResearchTaskContract
    goal: RepairGoal


@dataclass(frozen=True)
class RepairVerdict:
    """修复轮终局过了 ``admit_finish`` 之后，领域对「修完算不算数」的裁决。

    ``progressed``：真动了手（跑了工具）或没动手但把稿 / 绑定改成了 completed。
    没动手也没改的一轮不算修复——``status`` 压回 ``partial``，``gaps`` 没写就补一条
    「未执行新的取证动作」。loop 按 ``progressed`` 定 stop_reason
    （``repair_model_finish`` / ``repair_model_stop``），那是底座的词表。
    """

    status: EpisodeStatus
    gaps: tuple[str, ...]
    progressed: bool


@dataclass(frozen=True)
class ModeGovernance:
    """一次深度裁决的两个产物。

    ``decision``：进 ``mode_decision`` 事件的值，也是 loop 拿去
    ``runtime/tier_promotion.apply_mode_promotion`` 落账的申请。``message``：给模型看的
    ``MODE_DECISION`` 正文（user 角色）。裁决落到预算合同上（提 caps / 铸 grant /
    换 policy）是底座的账，不在这里——与修复轮「领域申请、底座授予」同形。
    """

    decision: ModeDecision
    message: str


@runtime_checkable
class ResearchHarness(Protocol):
    """底座 loop 在四个时点问领域的四个问题。

    全部是纯判定：不持有 loop 状态，不改 context，不发事件。事件由 loop 按
    返回值记——事件 payload 的键与顺序是 loop 的合同，harness 不碰。
    """

    def assemble_prompt(
        self,
        task_frame: TaskFrame,
        context: ResearchRunContext,
        registry: ResearchToolRegistry,
    ) -> tuple[str, str]:
        """开场 ``(system, user)``。system 在一次 episode 内字节稳定。"""
        ...

    def steering_message(self, kind: SteeringKind, *, detail: str) -> str:
        """loop 在驳回 / 关闭研究阶段时注入给模型的那段话（user 角色正文）。"""
        ...

    def interpret_plan(
        self,
        content: str,
        *,
        previous_plan: ResearchPlan | None,
        task_id: str,
    ) -> PlanParseResult:
        """这条模型输出是不是一份合法 PLAN（含相对上一份的修订合法性）。

        三种返回：``plan`` 非空 = 合法 PLAN；``plan`` 空且 ``error`` 非空 =
        写坏的 PLAN 或非法修订；两者皆空 = 根本不是 PLAN（交给终局门或工具）。
        """
        ...

    def govern_mode(
        self,
        *,
        task_frame: TaskFrame,
        plan: ResearchPlan,
        context: ResearchRunContext,
        can_branch: bool,
    ) -> ModeGovernance:
        """PLAN 到手后裁研究深度：出裁决值与一段给模型的话。

        ``can_branch`` 是底座能力（有没有子研究协调器）：没有就不能批 deep 的
        分支依赖——这是 loop 告诉领域「我能做什么」，不是领域自己猜。裁决落到
        预算合同上由 loop 调 ``runtime/tier_promotion.apply_mode_promotion``。
        """
        ...

    def project_sub_research(
        self,
        *,
        branches: Iterable[BranchOutcome],
        refused_reason: str,
        evidence: tuple[AgentEvidence, ...],
    ) -> str:
        """子研究分支回来后给主 episode 模型看的那段话（``SUB_RESEARCH_RESULTS``）。

        分支怎么起、怎么排空、怎么记事件是底座的事；分支证据怎样呈现给模型
        （序号、去 hash、措辞）是领域的事。``evidence`` 是主 episode 至今累计的
        证据（含分支并入的），序号 ``E<n>`` 从它算。
        """
        ...

    def project_tool_result(
        self,
        observation: ToolObservation,
        *,
        evidence_so_far: tuple[AgentEvidence, ...],
        seen_prose: Set[str],
    ) -> ToolResultProjection:
        """一次成功观察：审计留什么、模型看什么。

        ``evidence_so_far`` 是 episode 至今累计的证据（**含**本次新增），序号
        ``E<n>`` 按首次出现顺序从它算——所以 loop 必须先合并证据再来问。
        """
        ...

    def project_tool_error(
        self, *, tool: str, error: str, detail: str
    ) -> dict[str, object]:
        """一次失败 / 被拒 / 超时的工具调用给模型看的结构化结果。"""
        ...

    def halt_after_tool_batch(
        self,
        *,
        context: ResearchRunContext,
        batch_errors: Iterable[str | None],
    ) -> str | None:
        """一批工具跑完后是否立刻停止研究。返回停机理由；``None`` = 继续。"""
        ...

    def fallback_after_empty_batch(
        self,
        batch: Iterable[ToolCallOutcome],
        *,
        context: ResearchRunContext,
        registry: ResearchToolRegistry,
        authorized_tools: frozenset[str],
        events: Iterable[object],
        in_repair: bool,
    ) -> FallbackCall | None:
        """一批工具跑完、下一次问模型之前：要不要替模型补发一次查询，补什么。

        ``authorized_tools`` 是底座此刻真能派的工具集；``events`` 是 durable 事件流（领域从中
        判「已经补过」）；``in_repair`` 是底座报的阶段。剩余槛够不够由 loop 在调用前自己判——
        领域只说想不想补。返回 ``None`` = 不补。
        """
        ...

    def retrieval_complete(
        self,
        *,
        context: ResearchRunContext,
        registry: ResearchToolRegistry,
        successful_tools: set[str],
    ) -> bool:
        """已授权的取证面是否全部拿到——是则不必再派工具，可以进合成。"""
        ...

    def admit_finish(
        self,
        content: object,
        *,
        context: ResearchRunContext,
        evidence: tuple[AgentEvidence, ...],
        registry: ResearchToolRegistry,
    ) -> FinishAdmission:
        """模型的终局输出能不能发。"""
        ...

    def classify_repair_need(
        self,
        outcome: AgentOutcome,
        structural: VerifiedEpisodeOutcome,
        *,
        rejected_claims: tuple[str, ...],
        semantic_gap_outputs: tuple[str, ...],
    ) -> RepairNeed:
        """主轮终局过完结构 / 语义验证之后：这次失败该修什么、属于哪一类。

        不看预算、不看 cycle。底座拿它去 ``admit_repair``——给不给窗、给多大，
        是底座的事。
        """
        ...

    def warrant_repair(
        self,
        *,
        progress: ProgressSnapshot,
        cycle: int,
        research_tier: str,
    ) -> RepairWarrant:
        """这个 tier 还容忍第 ``cycle`` 轮吗；上一轮有没有独立证据进展。不看预算。"""
        ...

    def downgrade_unreachable(
        self,
        goal: RepairGoal,
        *,
        contract: ResearchTaskContract,
    ) -> RepairDowngrade:
        """授予已定、开场之前：哪些 evidence 口径的必填格这一轮结构性补不上。

        不放宽任何限制、不加任何预算——只把「不可能」显式化，让 loop 不必空转
        再发残稿。``goal.reopen_tools`` 为真（底座批了重开工具）就没有不可达。
        """
        ...

    def repair_goal_message(self, goal: RepairGoal, *, tools_open: bool) -> str:
        """修复轮开场给模型的那段话（``REPAIR_GOAL`` 正文，user 角色）。

        ``goal`` 是裁决后的模型侧目标（不可达格已降级）；``tools_open`` 是底座
        告诉领域「这一轮能不能派工具」——两套指令按它分叉。
        """
        ...

    def admit_repair_result(
        self,
        *,
        admission: FinishAdmission,
        previous: AgentOutcome,
        performed_tool_action: bool,
    ) -> RepairVerdict:
        """修复轮的终局已被 ``admit_finish`` 接受——那它算不算修好了。"""
        ...

    def admit_inbox_message(self, message: EpisodeMessage) -> bool:
        """收件箱（INV-R5）里这句话收不收——终态稿 §5 第 2 条、本 Protocol 唯一新增的接触点。

        ``send`` 时判定：True 入队待认领；False 落 ``inbox_discarded{reason=rejected_by_harness}``，
        模型永远看不到它。判的是**内容**（例：拒收含个股买卖指令的 steer），不是来源——
        loop 内部的回灌（``source="sub_research"``）同样经过这里，领域要放行就看 ``source``。
        纯判定：不持状态、不发事件、不抛（抛了按拒收处理）。
        """
        ...


class FinanceResearchHarness:
    """金融领域的默认 harness——对既有函数的纯委托。

    ``mode_governor`` / ``mode_signals`` 是深度裁决的两个可注入件（原先挂在
    ``ContinuousAgentEpisode`` 构造器上）。它们搬到这里是因为「研究该做多深」是
    领域判断；loop 只需要知道自己能不能开分支。
    """

    def __init__(
        self,
        *,
        mode_governor: ModeGovernor | None = None,
        mode_signals: ModeSignalsFactory | None = None,
    ) -> None:
        self._mode_governor = mode_governor if mode_governor is not None else ModeGovernor()
        self._mode_signals: ModeSignalsFactory = (
            mode_signals if mode_signals is not None else default_mode_signals
        )

    def assemble_prompt(
        self,
        task_frame: TaskFrame,
        context: ResearchRunContext,
        registry: ResearchToolRegistry,
    ) -> tuple[str, str]:
        return split_episode_prompt(task_frame, context, registry)

    def steering_message(self, kind: SteeringKind, *, detail: str) -> str:
        # 三段文案逐字搬自 agent_episode（run() 两处回灌 + _begin_finalization）。
        if kind == "invalid_plan":
            return (
                "上一条 PLAN 无效。请保留最初任务与当前 episode，"
                "只修复为闭合的 PLAN JSON，或直接调用已授权工具；"
                "PLAN 不能授权工具、预算、证据或完成状态。"
                f"错误：{detail}"
            )
        if kind == "invalid_finish":
            return (
                "上一条终止输出无效。请保留当前任务和全部观察，"
                "不要重启研究；修复后只输出 FINAL_JSON。"
                f"错误：{detail}"
            )
        if kind == "begin_finalization":
            return (
                "研究阶段已关闭，不得再调用工具。请保留最初任务和全部"
                "原始观察，立即基于已有证据序号 E1、E2… 输出 FINAL_JSON；"
                "证据不足的 required output 必须标 partial 并写明 gap。"
                "不要逐条复述全部观察，只保留最关键依据；条件写相对变化，"
                "不得新增证据中没有的数值阈值。若用户要求预测，只保留一个"
                "明确标注的主观基准区间及其不确定性。每个保留的精确数字"
                "必须把直接证据序号放入对应 output binding，否则删去数字。"
                "每条被正文使用的观察事实也必须把其直接证据序号加入对应 "
                "output binding；不得用同一次工具返回的另一条证据代替。"
                "原因归因若没有同一时间窗口的 news_search 证据，不得用普通 "
                "web_search 摘要补成已核验因果，应保留盘面事实并把原因写 gap。"
                "为保证 FINAL_JSON 完整，draft 控制在 1000 汉字以内；这是传输预算，"
                "不要求固定标题、段数或措辞。"
                f"关闭原因：{detail}"
            )
        if kind == "repair_finalize":
            # 逐字搬自 agent_episode.resume()：修复轮工具批跑完后的收口指令。
            return (
                "修复动作已执行。不得再调用工具；请基于同一 episode 的"
                "全部观察输出 FINAL_JSON，未补齐项继续明确写 gap。"
            )
        raise ValueError(f"unknown steering kind: {kind!r}")

    def interpret_plan(
        self,
        content: str,
        *,
        previous_plan: ResearchPlan | None,
        task_id: str,
    ) -> PlanParseResult:
        result = parse_plan_candidate(content)
        if result.plan is None or previous_plan is None:
            return result
        try:
            validate_plan_revision(
                previous_plan,
                result.plan,
                original_task_id=task_id,
                current_task_id=task_id,
            )
        except ValueError as exc:
            return PlanParseResult(None, str(exc))
        return result

    def govern_mode(
        self,
        *,
        task_frame: TaskFrame,
        plan: ResearchPlan,
        context: ResearchRunContext,
        can_branch: bool,
    ) -> ModeGovernance:
        # 逐字搬自 ContinuousAgentEpisode._decide_mode + _append_mode_decision_message。
        signals = self._mode_signals(task_frame, plan)
        if not isinstance(signals, ModeSignals):
            raise TypeError("mode_signals must return ModeSignals")
        if context.root_budget is None and signals.dependencies_available:
            signals = replace(signals, dependencies_available=False)
        if plan.branch_goals and not can_branch and signals.dependencies_available:
            signals = replace(signals, dependencies_available=False)
        decision = self._mode_governor.decide(plan, signals)
        message = json.dumps(
            {
                "kind": "MODE_DECISION",
                **decision.to_dict(),
                "instruction": (
                    "研究深度与总预算已由运行时裁决。保留原计划，"
                    "继续自主选择查询、工具顺序和停止时点；"
                    "不得把预算或内部裁决文本写入最终答案。"
                ),
            },
            ensure_ascii=False,
        )
        return ModeGovernance(decision=decision, message=message)

    def project_sub_research(
        self,
        *,
        branches: Iterable[BranchOutcome],
        refused_reason: str,
        evidence: tuple[AgentEvidence, ...],
    ) -> str:
        # 逐字搬自 ContinuousAgentEpisode._append_sub_research_message。
        ordinals = evidence_ordinal_table(evidence)
        return json.dumps(
            {
                "kind": "SUB_RESEARCH_RESULTS",
                "branches": [
                    {
                        "branch_id": branch.branch_id,
                        "goal": branch.goal,
                        "status": branch.status,
                        "evidence": strip_hashes_for_model(
                            {
                                "evidence": attach_evidence_ordinals(
                                    [
                                        public_agent_evidence(item)
                                        for item in branch.evidence
                                    ],
                                    ordinals,
                                )
                            }
                        )["evidence"],
                        "gaps": list(branch.gaps),
                    }
                    for branch in branches
                ],
                "refused_reason": refused_reason,
                "instruction": (
                    "这些是只读分支返回的公开证据观察，不是最终答案。"
                    "主 episode 仍需自行比较证据、处理冲突并决定停止；"
                    "绑定用证据序号 E1、E2…，不得把分支状态或内部标识写入公开答案。"
                ),
            },
            ensure_ascii=False,
        )

    def project_tool_result(
        self,
        observation: ToolObservation,
        *,
        evidence_so_far: tuple[AgentEvidence, ...],
        seen_prose: Set[str],
    ) -> ToolResultProjection:
        # 逐字搬自 _EpisodeToolAccumulator.consume 的成功分支。
        ordinals = evidence_ordinal_table(tuple(evidence_so_far))
        audit: dict[str, object] = {
            "ok": True,
            "tool": observation.tool,
            "query": observation.query,
            "observation": observation.observation,
            "evidence": attach_evidence_ordinals(
                [public_agent_evidence(item) for item in observation.evidence],
                ordinals,
            ),
            "evidence_hashes": list(observation.evidence_hashes),
            "evidence_ids": [
                ordinals[digest]
                for digest in observation.evidence_hashes
                if digest in ordinals
            ],
            "gaps": list(observation.gaps),
            "dataset": observation.dataset,
            "caliber": observation.caliber,
            "payload_field_names": list(observation.payload_field_names),
            "payload_sha256": observation.payload_sha256,
        }
        telemetry = dict(getattr(observation, "telemetry", None) or {})
        if telemetry:
            # 控制面收据：只进 ledger，不进模型上下文。
            audit["telemetry"] = telemetry
        # 审计留档拿全量（含 hash），模型上下文拿预算后的副本并去掉 hash，
        # 只留 E1..En——誊抄 16-hex 是 B1/B7 零绑定的根因。
        model_view = dict(audit)
        model_view.pop("telemetry", None)
        pruned, seen = prune_tool_observation(model_view, seen_prose=seen_prose)
        budgeted = budget_tool_observation(pruned)
        if lean_observation_enabled():
            # 空值与 independent_key 不进模型上下文（−21%）；开关缺省关，关时逐字节同前。
            budgeted = lean_tool_observation(budgeted)
        content = json.dumps(strip_hashes_for_model(budgeted), ensure_ascii=False)
        return ToolResultProjection(
            audit_payload=audit,
            model_content=content,
            seen_prose=frozenset(seen),
        )

    def project_tool_error(
        self, *, tool: str, error: str, detail: str
    ) -> dict[str, object]:
        return {
            "ok": False,
            "tool": tool,
            "error": error,
            # 分类码之外还要给可操作的原因——``error`` 只说「参数不合法」，
            # 模型据此改不了任何东西。详见 ToolCallResult.detail 的注释。
            "detail": str(detail or "")[:400],
        }

    def halt_after_tool_batch(
        self,
        *,
        context: ResearchRunContext,
        batch_errors: Iterable[str | None],
    ) -> str | None:
        return forecast_residual_halt_reason(
            question_type=context.contract.question_type,
            research_tier=context.contract.research_tier,
            batch_errors=tuple(batch_errors),
        )

    def fallback_after_empty_batch(
        self,
        batch: Iterable[ToolCallOutcome],
        *,
        context: ResearchRunContext,
        registry: ResearchToolRegistry,
        authorized_tools: frozenset[str],
        events: Iterable[object],
        in_repair: bool,
    ) -> FallbackCall | None:
        # 原 agent_episode._maybe_execute_empty_pool_fallback 凑输入那段逐字搬入：领域判定
        # 的输入由领域自己从 context / registry / events 读，loop 只递它拥有的事实。
        cutoff = context.information_cutoff
        proposal = propose_empty_pool_fallback(
            question_type=context.contract.question_type,
            as_of=cutoff.as_of_date.isoformat(),
            cutoff_source=cutoff.source,
            prefetch_empty=prefetch_pool_is_empty(
                getattr(registry, "opening_prefetch", ()) or ()
            ),
            first_results=tuple(
                EmptyToolCall(
                    name=item.call.name,
                    arguments=dict(item.call.arguments),
                    empty=item.status == "empty",
                )
                for item in batch
            ),
            authorized_tools=authorized_tools,
            already_attempted=fallback_already_attempted(events),
            in_repair=in_repair,
            backfill_plan=None,
        )
        if proposal is None:
            return None
        return FallbackCall(
            call=ModelToolCall(
                proposal.call_id, proposal.tool, proposal.fallback_arguments
            ),
            request_extras=proposal.request_extras(),
        )

    def retrieval_complete(
        self,
        *,
        context: ResearchRunContext,
        registry: ResearchToolRegistry,
        successful_tools: set[str],
    ) -> bool:
        specs = registry.authorized_specs(context.contract.allowed_capabilities)
        return bool(specs) and all(
            spec.query_scope == "episode" and spec.name in successful_tools
            for spec in specs
        )

    def admit_finish(
        self,
        content: object,
        *,
        context: ResearchRunContext,
        evidence: tuple[AgentEvidence, ...],
        registry: ResearchToolRegistry,
    ) -> FinishAdmission:
        try:
            finish = validate_episode_finish(
                content,
                context=context,
                evidence=evidence,
            )
        except ValueError as exc:
            return FinishAdmission(
                accepted=False,
                status=None,
                draft="",
                bindings=(),
                gaps=(),
                caveat_slips=0,
                rejection=finish_rejection_fields(exc),
                reason=str(exc),
                kind=getattr(getattr(exc, "kind", None), "value", "unclassified"),
                response=rejection_response(exc),
            )
        bindings = expand_episode_snapshot_bindings(
            bindings=finish.bindings,
            evidence=evidence,
            registry=registry,
            draft=finish.draft,
        )
        return FinishAdmission(
            accepted=True,
            status=finish.status,
            draft=finish.draft,
            bindings=bindings,
            gaps=_merge_gaps(finish.gaps, bindings),
            caveat_slips=finish.caveat_slips,
            rejection=finish_rejection_fields(),
            declared_gaps=tuple(finish.gaps),
        )

    def classify_repair_need(
        self,
        outcome: AgentOutcome,
        structural: VerifiedEpisodeOutcome,
        *,
        rejected_claims: tuple[str, ...],
        semantic_gap_outputs: tuple[str, ...],
    ) -> RepairNeed:
        return classify_repair_need(
            outcome,
            structural,
            rejected_claims=rejected_claims,
            semantic_gap_outputs=semantic_gap_outputs,
        )

    def warrant_repair(
        self,
        *,
        progress: ProgressSnapshot,
        cycle: int,
        research_tier: str,
    ) -> RepairWarrant:
        return warrant_repair(progress, cycle=cycle, research_tier=research_tier)

    def downgrade_unreachable(
        self,
        goal: RepairGoal,
        *,
        contract: ResearchTaskContract,
    ) -> RepairDowngrade:
        # 原 agent_episode.resume() 的两步：先算不可达格（进 trace），再降级契约 / 目标。
        unreachable = unreachable_repair_goal(
            goal,
            evidence_output_ids=evidence_required_output_ids(contract),
        )
        downgraded, prompt_goal = apply_unreachable_downgrade(contract, goal)
        return RepairDowngrade(
            unreachable=unreachable,
            contract=downgraded,
            goal=prompt_goal,
        )

    def repair_goal_message(self, goal: RepairGoal, *, tools_open: bool) -> str:
        # 逐字搬自 agent_episode.resume()：REPAIR_GOAL 正文 + 工具开/关两套指令。
        payload: dict[str, object] = {
            "kind": "REPAIR_GOAL",
            **goal.to_dict(),
            "instruction": (
                "保留最初任务、全部原始观察和当前工具账本。"
                + (
                    "自主选择一个新的、未重复的动作补齐缺口；"
                    if tools_open
                    else "研究工具已关闭，只能基于已有观察修复措辞或证据绑定；"
                )
                + "不得重启研究或改写用户问题。"
            ),
        }
        # 跟踪题的表达槽以合成 id 混在 missing_answer_elements 里；不说明的话模型会把它们
        # 当 output 去绑（2026-09-07 两轮 theme_track 修复 2/2 因此被 unknown_output 硬拒）。
        # 只在真有表达槽时加这一键：其它修复轮的消息逐字节不变。
        expression_slots = tuple(
            item for item in goal.missing_answer_elements if item in TRACK_CONTRACT_OUTPUT_ID_SET
        )
        if expression_slots:
            payload["expression_elements_note"] = (
                "以下缺件是正文表达要求，写进 draft 即可，不要作为 bindings 的 output_id："
                + "、".join(expression_slots)
                + "（track_ttl → 一行「复核期限：YYYY-MM-DD」；track_next_watch → 一段「下期关注：…」；"
                "track_quad_or_baseline → 四态对照或「无上期基线」声明）"
            )
        return json.dumps(payload, ensure_ascii=False)

    def admit_repair_result(
        self,
        *,
        admission: FinishAdmission,
        previous: AgentOutcome,
        performed_tool_action: bool,
    ) -> RepairVerdict:
        # 逐字搬自 agent_episode.resume()：repair_progressed 三元判定 + 兜底 gap。
        if admission.status is None:
            raise ValueError("admit_repair_result 只裁已被 admit_finish 接受的终局")
        revised_without_tool = (
            admission.draft.strip() != previous.draft.strip()
            or admission.bindings != previous.bindings
        )
        completed_without_tool = (
            not performed_tool_action
            and admission.status == "completed"
            and revised_without_tool
        )
        progressed = performed_tool_action or completed_without_tool
        gaps = admission.gaps
        if not progressed and not gaps:
            gaps = ("修复轮未执行新的取证动作，缺口仍未补齐",)
        return RepairVerdict(
            status=admission.status if progressed else "partial",
            gaps=gaps,
            progressed=progressed,
        )

    def admit_inbox_message(self, message: EpisodeMessage) -> bool:
        # 默认恒 True（终态稿 §5 第 2 条）：金融领域今天没有「不许递进来的话」这条规则；
        # 要加（例：拒收含个股买卖指令的 steer）就改这里，loop 一行不动。
        # 「有牙」由 conformance test_inv_r5_inbox 守：换一个拒收实现，模型看不到那句话。
        del message
        return True


def _merge_gaps(
    declared_gaps: tuple[str, ...],
    bindings: tuple[OutputEvidenceBinding, ...],
) -> tuple[str, ...]:
    """只投影当前仍未解决的 gap；历史留在事件里。

    原 ``ContinuousAgentEpisode._finish_gaps`` 逐字搬来：声明 gap 在前、绑定 gap
    在后，去空、去重、保序。
    """

    values = (*declared_gaps, *(item.gap for item in bindings))
    return tuple(
        dict.fromkeys(
            cleaned for value in values if (cleaned := str(value or "").strip())
        )
    )
