"""未命中专项 Skill 时的受约束通用研究 Owner。

该模块只负责任务契约、循环控制和完成度裁决；事实仍来自白名单工具，
最终措辞仍交给现有 AnswerSpec/Grounded Presenter。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Callable

from intelligence.services import (
    agent_research,
    research_task_planner,
    research_tool_registry,
)
from intelligence.services.evidence_window import is_time_aligned_evidence
from intelligence.services.research_contract import (
    OutputStatus,
    RequiredOutput,
    ResearchRunContext,
    ResearchTaskContract,
)
from intelligence.services.research_state import ResearchState, state_from_contract


@dataclass(frozen=True)
class CompletionReport:
    status: str
    outputs: tuple[OutputStatus, ...]
    factual_grounding: str = "unknown"
    causal_adequacy: str = "unknown"
    task_coverage: str = "unknown"

    @property
    def missing_required(self) -> tuple[OutputStatus, ...]:
        return tuple(item for item in self.outputs if item.status == "missing")

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "factual_grounding": self.factual_grounding,
            "causal_adequacy": self.causal_adequacy,
            "task_coverage": self.task_coverage,
            "outputs": [
                {
                    "output_id": item.output_id,
                    "status": item.status,
                    "evidence_ids": list(item.evidence_ids),
                    "gap": item.gap,
                }
                for item in self.outputs
            ],
        }


@dataclass(frozen=True)
class GenericResearchResult:
    run_id: str
    contract: ResearchTaskContract
    loop: agent_research.AgentLoopResult
    completion: CompletionReport
    evidence: tuple[agent_research.AgentEvidence, ...]
    task_plan: research_task_planner.TaskPlan | None = None

    @property
    def traces(self):
        return tuple(self.loop.traces)

    @property
    def gaps(self) -> tuple[str, ...]:
        return tuple(self.loop.gaps) + tuple(
            item.gap for item in self.completion.outputs if item.gap
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "contract": self.contract.to_dict(),
            "loop": self.loop.to_dict(),
            "completion": self.completion.to_dict(),
            "task_plan": self.task_plan.to_dict() if self.task_plan else None,
            "gaps": list(self.gaps),
        }


def _evidence_pairs(
    evidence: tuple[agent_research.AgentEvidence, ...],
) -> tuple[tuple[str, agent_research.AgentEvidence], ...]:
    return tuple(
        (f"agent:{index}:{item.tool}", item)
        for index, item in enumerate(evidence, start=1)
    )


def _causal_external_match(
    item: agent_research.AgentEvidence,
    evidence: tuple[agent_research.AgentEvidence, ...],
) -> bool:
    if item.tool not in {"news_search", "web_search"}:
        return False
    reference_dates: list[date] = []
    for value in evidence:
        if not value.source_date:
            continue
        try:
            reference_dates.append(
                date.fromisoformat(str(value.source_date)[:10].replace("/", "-"))
            )
        except ValueError:
            continue
    reference_date = reference_dates[-1] if reference_dates else None
    if not is_time_aligned_evidence(item, reference_date=reference_date):
        return False
    text = f"{item.title} {item.detail}"
    # 市场原因题不能把同日但无关的公司新闻当成外部触发证据。
    return any(
        term in text
        for term in ("指数", "股市", "资金", "政策", "美股", "市场", "A股", "外盘")
    )


def _matches_output(
    required: RequiredOutput,
    evidence: tuple[agent_research.AgentEvidence, ...],
    loop: agent_research.AgentLoopResult,
) -> tuple[agent_research.AgentEvidence, ...]:
    if not evidence:
        return ()
    normalized = required.output_id.casefold()
    if normalized in {"direct_assessment", "answer", "conclusion"}:
        # 历史通用契约的 finish 仍向后兼容；原因归因题另由
        # cause_attribution 强制要求带文字的判断，避免一次升级破坏旧长尾。
        return evidence if loop.sufficient is True and loop.assessment.strip() else ()
    if normalized in {"cause_attribution", "causal_explanation"}:
        if loop.sufficient is not True or not loop.assessment.strip():
            return ()
        return tuple(item for item in evidence if item.tool == "market_data")
    if normalized in {
        "external_cause_evidence",
        "event_evidence",
        "funding_evidence",
    }:
        return tuple(
            item
            for item in evidence
            if _causal_external_match(item, evidence)
        )
    if normalized in {"counterpoint", "risk", "counter_evidence"}:
        return evidence[:2] if len(evidence) >= 2 else ()
    if normalized in {"rebound_case", "decline_case", "invalidation"}:
        # 情景输出只接受 agent 明确绑定到对应 hypothesis 的证据；不能用
        # 同一条最新行情同时冒充反弹、下跌和失效条件。
        return tuple(
            item
            for item in evidence
            if normalized in item.supports or normalized in item.contradicts
        )
    if required.evidence_types:
        allowed = set(required.evidence_types)
        return tuple(item for item in evidence if item.tool in allowed)
    return evidence


def evaluate_completion(
    contract: ResearchTaskContract,
    loop: agent_research.AgentLoopResult,
) -> CompletionReport:
    state = loop.research_state
    if state is not None:
        completion = state.evaluate_completion()
    else:
        completion = None
    evidence = tuple(loop.evidence)
    evidence_pairs = _evidence_pairs(evidence)
    outputs: list[OutputStatus] = []
    for required in contract.required_outputs:
        matches = _matches_output(required, evidence, loop)
        if matches:
            match_ids = tuple(
                evidence_id
                for evidence_id, item in evidence_pairs
                if item in matches
            )
            outputs.append(OutputStatus(required.output_id, "fulfilled", match_ids))
            continue
        gap = "；".join(loop.gaps) or f"仍缺少：{required.description}"
        outputs.append(
            OutputStatus(
                required.output_id,
                "gap" if not required.required else "missing",
                (),
                gap,
            )
        )
    required_statuses = [
        status
        for required, status in zip(contract.required_outputs, outputs)
        if required.required
    ]
    if completion is not None:
        result_status = completion.status
    elif all(status.status == "fulfilled" for status in required_statuses):
        result_status = "completed"
    elif any(status.status == "missing" for status in required_statuses):
        result_status = "partial"
    else:
        result_status = "gap"
    return CompletionReport(
        result_status,
        tuple(outputs),
        factual_grounding=completion.factual_grounding if completion else "unknown",
        causal_adequacy=completion.causal_adequacy if completion else "unknown",
        task_coverage=completion.task_coverage if completion else "unknown",
    )


def run_generic_research(
    contract: ResearchTaskContract,
    *,
    context: ResearchRunContext,
    registry: research_tool_registry.ResearchToolRegistry,
    run_id: str,
    complete_fn: agent_research.CompleteFn | None = None,
    existing_evidence_summary: str = "",
    preloaded_evidence: tuple[agent_research.AgentEvidence, ...] = (),
    preloaded_traces: tuple[ProviderTrace, ...] = (),
    preloaded_observation: str = "",
    disabled_tools: tuple[str, ...] = (),
    task_plan: research_task_planner.TaskPlan | None = None,
) -> GenericResearchResult:
    """在契约、白名单和共享 deadline 内运行一个长尾研究闭环。"""

    step_counter = 0

    def wrapped_runner(name: str):
        def _runner(
            query: str,
            _agent_context: agent_research.AgentToolContext,
        ):
            nonlocal step_counter
            step_counter += 1
            observation = registry.execute(
                name,
                query,
                context=context,
                step_id=f"{run_id}:owner:{step_counter}",
            )
            return list(observation.evidence), observation.observation, observation.trace

        return _runner

    tools = {
        name: wrapped_runner(name)
        for name in registry.names()
        if name not in set(disabled_tools)
        if not context.contract.allowed_capabilities
        or registry.resolve(name).capability in context.contract.allowed_capabilities
    }
    instructions = json.dumps(
        {
            "required_outputs": [
                {
                    "id": item.output_id,
                    "description": item.description,
                    "evidence_types": list(item.evidence_types),
                    "required": item.required,
                }
                for item in contract.required_outputs
            ],
            "allowed_tools": list(tools),
            "presentation_profile": contract.presentation_profile,
            # 任务规划只是检索顺序参考；工具白名单、预算和 required outputs
            # 仍由上面的 contract/loop 硬约束决定。
            "task_plan": task_plan.to_dict() if task_plan else None,
        },
        ensure_ascii=False,
    )
    state = state_from_contract(contract)
    for index, item in enumerate(preloaded_evidence, start=1):
        state.add_evidence(
            item.to_observation(f"agent:preloaded:{index}:{item.tool}")
        )
    loop = agent_research.run_agent_loop(
        contract.question,
        tools=tools,
        existing_evidence_summary=(
            f"{existing_evidence_summary}\n{preloaded_observation}".strip()
        ),
        steps_budget=context.policy.max_steps,
        total_seconds=context.policy.total_seconds,
        deadline=context.deadline,
        complete_fn=complete_fn,
        task_instructions=instructions,
        research_state=state,
    )
    if preloaded_evidence:
        loop.evidence = [*preloaded_evidence, *loop.evidence]
    if preloaded_traces:
        loop.traces = [*preloaded_traces, *loop.traces]
    evidence = tuple(loop.evidence)
    return GenericResearchResult(
        run_id=run_id,
        contract=contract,
        loop=loop,
        completion=evaluate_completion(contract, loop),
        evidence=evidence,
        task_plan=task_plan,
    )
