"""``sub_research`` 作为模型可点的工具：把既有 ``SubResearchCoordinator`` 包成一个 ToolSpec 的 runner。

来源：``docs/superpowers/specs/2026-09-03-subagent-tool-design.md``。抄 dsh ``tool-subagent`` 的
形状（前台同步、只有 completed 算成功、深度上限、失败保留部分产物），账本用我们的：
分支证据经 ``EvidenceLedger.branch_sink`` append 进**父账本**、hash 由父账本铸，模型拿到的是
带 E 号的证据条目，父臂结论只能绑到这些证据上——dsh「Success contains only the child's final
text」那条**不抄**，回文本进不了 ``admit_finish``。

为什么在 ``runtime`` 层绑：runner 要协调器（跑分支的线程池 + 同步排空不变量）与父证据账本，
两样都只在 episode 期才有；``services`` 层的 ``build_episode_registry`` 没有 runner 就不挂
``sub_research``（没源不挂），由 ``ContinuousAgentEpisode.run`` 在起步时把绑好的 spec 并进
注册表。

深度 = 1 由三道保证：① 传给协调器的分支注册表 ``without("sub_research")``；② 分支契约的
``allowed_capabilities`` 去掉它，schema 里看不见；③ 分支 worker 起的嵌套 Episode 本来就
``sub_research_coordinator=None``，不会再绑。

预算：分支的墙钟以**本批工具窗**为界（``tool_batch_timeout_seconds`` 的同一套算术），不是
episode deadline——批执行器等的是那个窗，超了会把本调用记成 ``tool_timeout`` 而线程照跑；
先把协调器的 deadline 收进窗里，分支就不会在父臂走掉之后还在往账本里写。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
import json

from intelligence.runtime.episode_tool_batch import tool_batch_timeout_seconds
from intelligence.runtime.sub_research import (
    BranchResult,
    SubResearchCoordinator,
    SubResearchResult,
)
from intelligence.services.agent_research import AgentToolContext
from intelligence.services.evidence_ledger import EvidenceLedger
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import (
    ResearchDeadline,
    ResearchRunContext,
)
from intelligence.services.research_tool_registry import (
    ResearchToolRegistry,
    ToolRunResult,
    ToolSpec,
    sub_research_tool_spec,
)
from intelligence.services.task_frame import TaskFrame

SUB_RESEARCH_TOOL = "sub_research"
# 协调器要在批执行器的等待窗**之内**返回；留一成余量给分支收口与账本结算。
_WINDOW_SAFETY_FRACTION = 0.9


def bind_sub_research_tool(
    *,
    coordinator: SubResearchCoordinator,
    task_frame: TaskFrame,
    current_context: Callable[[], ResearchRunContext],
    base_registry: ResearchToolRegistry,
    evidence_ledger: EvidenceLedger,
    on_result: Callable[[tuple[str, ...], SubResearchResult], None] | None = None,
) -> ToolSpec:
    """绑出这一个 episode 的 ``sub_research`` ToolSpec。

    ``current_context`` 是可调用而不是值：PLAN 升档会换掉 loop 手里的 context，
    分支要按换过之后的档位与账本跑。``on_result`` 给 loop 记 ``branch_*`` 事件用，
    runner 自己不碰 episode 台账（它在批执行器的工作线程里跑）。
    """

    branch_registry = base_registry.without(SUB_RESEARCH_TOOL)

    def runner(goals_json: str, tool_context: AgentToolContext) -> ToolRunResult:
        goals = tuple(json.loads(goals_json))
        parent = current_context()
        window = tool_context.deadline.stage_timeout(
            tool_batch_timeout_seconds(parent.policy)
        )
        bounded = replace(
            parent,
            contract=replace(
                parent.contract,
                allowed_capabilities=tuple(
                    capability
                    for capability in parent.contract.allowed_capabilities
                    if capability != SUB_RESEARCH_TOOL
                ),
            ),
            deadline=ResearchDeadline.from_timeout(
                max(0.0, window * _WINDOW_SAFETY_FRACTION)
            ),
        )
        result = coordinator.run(
            goals=goals,
            task_frame=task_frame,
            context=bounded,
            registry=branch_registry,
            evidence_sink_factory=evidence_ledger.branch_sink,
        )
        if on_result is not None:
            on_result(goals, result)
        return tool_result_from_branches(goals, result)

    return sub_research_tool_spec(runner)


def _branch_line(branch: BranchResult) -> str:
    text = f"{branch.branch_id}「{branch.goal}」：{branch.status}，证据 {len(branch.evidence)} 条"
    if branch.status == "failed":
        text += f"，失败原因 {branch.error or 'unknown'}——该子问题未被研究，不是没有答案"
    elif not branch.evidence:
        text += "——该方向本轮未找到可绑定证据，是缺口不是否定结论"
    if branch.gaps:
        text += "；分支自报缺口：" + "；".join(branch.gaps[:3])
    return text


def _branch_gaps(branch: BranchResult) -> tuple[str, ...]:
    if branch.status == "failed":
        return (
            f"子研究分支「{branch.goal}」未完成（{branch.error or 'unknown'}），该子问题未被研究",
            *branch.gaps,
        )
    if not branch.evidence:
        return (f"子研究分支「{branch.goal}」本轮未找到可绑定证据", *branch.gaps)
    return tuple(branch.gaps)


def tool_result_from_branches(
    goals: tuple[str, ...],
    result: SubResearchResult,
) -> ToolRunResult:
    """把协调器的结果翻成注册表的一份 ``ToolRunResult``（spec §3 三条契约在这里落）。

    - 证据 = 各分支被父账本接纳的证据条目（hash 已铸、tier / as_of 继承自分支里的工具）。
    - 协调器整体拒绝（deep_mode_required / root_budget_exhausted / …）→ ``error`` 带原因，
      不静默回空。
    - 全部分支 failed → ``error``；有证据 → ``success``；跑完了但一条都没有 → ``empty``。
    """

    if result.refused_reason:
        reason = result.refused_reason
        return ToolRunResult(
            evidence=(),
            observation=(
                f"子研究未执行：{reason}。这不是「没有答案」，是本轮预算或档位不允许起分支；"
                "可以直接调用具体工具取证。"
            ),
            trace=ProviderTrace(
                provider=SUB_RESEARCH_TOOL,
                capability=SUB_RESEARCH_TOOL,
                status="error",
                detail=f"refused={reason}; goals={len(goals)}",
            ),
            gaps=tuple(f"子研究分支「{goal}」未执行（{reason}）" for goal in goals),
            telemetry={"refused_reason": reason, "branches": []},
        )

    branches = result.branches
    evidence = result.evidence
    all_failed = bool(branches) and all(b.status == "failed" for b in branches)
    if evidence:
        status = "success"
    elif all_failed:
        status = "error"
    else:
        status = "empty"
    observation = "子研究返回：" + "；".join(_branch_line(b) for b in branches)
    if evidence:
        observation += f"。共 {len(evidence)} 条证据已并入本轮证据表，结论请绑到这些证据上。"
    gaps = tuple(gap for branch in branches for gap in _branch_gaps(branch))
    return ToolRunResult(
        evidence=evidence,
        observation=observation,
        trace=ProviderTrace(
            provider=SUB_RESEARCH_TOOL,
            capability=SUB_RESEARCH_TOOL,
            status=status,
            detail=(
                "branches="
                + ",".join(f"{b.branch_id}:{b.status}:{len(b.evidence)}" for b in branches)
                + f"; tool_calls={result.tool_calls}; llm_calls={result.llm_calls}"
            ),
            result_count=len(evidence),
        ),
        gaps=gaps,
        telemetry={
            "refused_reason": "",
            "branches": [branch_telemetry(b) for b in branches],
        },
    )


def branch_telemetry(branch: BranchResult) -> dict[str, object]:
    """一支分支进收据的全部读数：合计数 + 终局理由 + 预算账 + 逐批派发账。

    同一份 dict 进两处：``sub_research`` 的 ``tool_result.telemetry``（审计底稿）与
    durable 的 ``branch_completed`` 事件。两处此前各写一份、字段已经漂开
    （事件里有 tokens、telemetry 里没有）；收成一个函数，改一处两处同时变。
    预算账与派发账没有就不写键——分支被取消 / worker 抛异常时它们确实不存在，
    写空值会把「没测到」伪装成「测到是零」。
    """

    payload: dict[str, object] = {
        "branch_id": branch.branch_id,
        "goal": branch.goal,
        "status": branch.status,
        "error": branch.error,
        "stop_reason": branch.stop_reason,
        "evidence_count": len(branch.evidence),
        "gap_count": len(branch.gaps),
        "llm_calls": branch.llm_calls,
        "tool_calls": branch.tool_calls,
        "input_tokens": branch.input_tokens,
        "output_tokens": branch.output_tokens,
    }
    if branch.budget is not None:
        payload["budget"] = branch.budget.to_dict()
    if branch.batches:
        payload["batches"] = [batch.to_dict() for batch in branch.batches]
    return payload


__all__ = [
    "SUB_RESEARCH_TOOL",
    "bind_sub_research_tool",
    "branch_telemetry",
    "tool_result_from_branches",
]
