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
project_tool_result  afterToolCall.content        tools/result（definition-owned finalizeContent）
project_tool_error   afterToolCall.isError+content tools/post-execute → block(feedback)
halt_after_tool_batch afterToolCall.terminate     tools/post-execute → block
retrieval_complete   shouldStopAfterTurn          —
admit_finish         **—（pi 没有）**              **—（dsh 没有）**
===================  ===========================  ==============================

PLAN 是本领域的研究协议（先出计划再动手），两家都没有；它和 ``admit_finish``
一样只能是领域方法。``steering_message`` 是领域在驳回 / 关闭研究阶段时对模型说的
话——第二条 loop 若要「是同一台机器」，这些字节必须来自同一处。
``project_tool_result`` 决定一次工具观察**审计留什么、模型看什么**：审计底稿全量
（含 hash / telemetry），模型视图去重、预算、去 hash 只留 E<n>——这条边界是
2026-08 B1/B7 零绑定事故（模型誊抄 16-hex）之后立的，不能因为换 loop 而漂。

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

from collections.abc import Iterable, Set
from dataclasses import dataclass
import json
from typing import Literal, Protocol, runtime_checkable

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import (
    EpisodeStatus,
    OutputEvidenceBinding,
    public_agent_evidence,
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
from intelligence.services.research_contract import ResearchRunContext
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
from intelligence.services.tool_result_budget import budget_tool_observation

__all__ = [
    "FinanceResearchHarness",
    "FinishAdmission",
    "ResearchHarness",
    "SteeringKind",
    "ToolResultProjection",
]

# loop 在三个时点需要对模型说一段领域的话。做成 Literal 而不是三个方法：
# 三段话的**时点**是底座的事（什么时候驳回、什么时候关研究阶段），**内容**是
# 领域的事；一个方法一个枚举，时点和内容的边界正好落在参数上。
SteeringKind = Literal["invalid_plan", "invalid_finish", "begin_finalization"]


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


class FinanceResearchHarness:
    """金融领域的默认 harness——对既有函数的纯委托。"""

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
        content = json.dumps(
            strip_hashes_for_model(budget_tool_observation(pruned)),
            ensure_ascii=False,
        )
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
