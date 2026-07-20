"""未命中专项 Skill 时的受约束通用研究 Owner。

该模块只负责任务契约、循环控制和完成度裁决；事实仍来自白名单工具，
最终措辞仍交给现有 AnswerSpec/Grounded Presenter。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable

from intelligence.services import agent_research, research_tool_registry
from intelligence.services.research_contract import (
    OutputStatus,
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
            "gaps": list(self.gaps),
        }


def _evidence_ids(
    evidence: tuple[agent_research.AgentEvidence, ...],
) -> tuple[str, ...]:
    return tuple(
        f"agent:{index}:{item.tool}"
        for index, item in enumerate(evidence, start=1)
    )


def _matches_output(
    output_id: str,
    evidence: tuple[agent_research.AgentEvidence, ...],
    loop: agent_research.AgentLoopResult,
) -> bool:
    if not evidence:
        return False
    normalized = output_id.casefold()
    if normalized in {"direct_assessment", "answer", "conclusion"}:
        # 历史通用契约的 finish 仍向后兼容；原因归因题另由
        # cause_attribution 强制要求带文字的判断，避免一次升级破坏旧长尾。
        return loop.sufficient is True
    if normalized in {"cause_attribution", "causal_explanation"}:
        tools = {item.tool for item in evidence}
        return (
            loop.sufficient is True
            and bool(loop.assessment.strip())
            and "market_data" in tools
        )
    if normalized in {"external_cause_evidence", "event_evidence", "funding_evidence"}:
        return bool({item.tool for item in evidence}.intersection({"news_search", "web_search"}))
    if normalized in {"counterpoint", "risk", "counter_evidence"}:
        return len(evidence) >= 2 or bool(loop.gaps)
    return True


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
    ids = _evidence_ids(evidence)
    outputs: list[OutputStatus] = []
    for required in contract.required_outputs:
        if _matches_output(required.output_id, evidence, loop):
            outputs.append(OutputStatus(required.output_id, "fulfilled", ids))
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
    )
