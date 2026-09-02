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
halt_after_tool_batch afterToolCall.terminate     tools/post-execute → block
retrieval_complete   shouldStopAfterTurn          —
admit_finish         **—（pi 没有）**              **—（dsh 没有）**
===================  ===========================  ==============================

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

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import EpisodeStatus, OutputEvidenceBinding
from intelligence.services.episode_protocol import (
    RejectionResponse,
    expand_episode_snapshot_bindings,
    finish_rejection_fields,
    rejection_response,
    split_episode_prompt,
    validate_episode_finish,
)
from intelligence.services.forecast_residual_budget import (
    forecast_residual_halt_reason,
)
from intelligence.services.research_contract import ResearchRunContext
from intelligence.services.research_tool_registry import ResearchToolRegistry
from intelligence.services.task_frame import TaskFrame

__all__ = [
    "FinanceResearchHarness",
    "FinishAdmission",
    "ResearchHarness",
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
