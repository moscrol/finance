"""Bounded no-tools finalization recovery for one research episode."""

from __future__ import annotations

import json
from typing import Literal

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import (
    AgentModelClient,
    ModelTurn,
    public_agent_evidence,
)
from intelligence.services.research_contract import ResearchRunContext
from intelligence.services.task_frame import TaskFrame


DEFAULT_FINALIZER_TIMEOUT = 20.0
MIN_FINALIZATION_RECOVERY_SECONDS = 1.0

_RECOVERY_SYSTEM_PROMPT = (
    "你是金融研究 Agent 的终局恢复器。研究与工具阶段已经永久关闭，不得请求或"
    "臆造任何新证据。只能使用用户 JSON 中 evidence 已存在的 content_hash，严格"
    "回答原始 TaskFrame 与 required_outputs。只输出一个 FINAL_JSON 对象："
    '{"status":"completed|partial","draft":"自然语言回答",'
    '"gaps":["..."],"bindings":[{"output_id":"...",'
    '"evidence_hashes":["..."],"gap":""}]}。'
    "证据不能覆盖 required output 时必须返回 partial 并填写 gap；不要输出代码围栏、"
    "解释、工具调用或 JSON 之外的文本。"
)

_REPAIR_SYSTEM_PROMPT = (
    "你是金融研究 Agent 的定向终局修复器。研究与工具阶段已经永久关闭，不得请求"
    "或臆造任何新证据。删除或改写用户 JSON 中被拒绝的句子，并逐项解决 judge "
    "issues；只能使用 evidence 已存在的 content_hash。严格回答原始 TaskFrame 与 "
    "required_outputs，只输出一个 FINAL_JSON 对象："
    '{"status":"completed|partial","draft":"自然语言回答",'
    '"gaps":["..."],"bindings":[{"output_id":"...",'
    '"evidence_hashes":["..."],"gap":""}]}。'
    "证据不能覆盖 required output 时必须返回 partial 并填写 gap；不要输出代码围栏、"
    "解释、工具调用或 JSON 之外的文本。"
)


class EpisodeFinalizer:
    """Make one compact model call without parsing or validating its response."""

    def __init__(
        self,
        model: AgentModelClient,
        *,
        llm_timeout: float = DEFAULT_FINALIZER_TIMEOUT,
    ) -> None:
        self._model = model
        self._llm_timeout = max(0.1, float(llm_timeout))

    def recover(
        self,
        *,
        task_frame: TaskFrame,
        context: ResearchRunContext,
        evidence: tuple[AgentEvidence, ...],
        gaps: tuple[str, ...],
        failure_reason: str,
    ) -> ModelTurn:
        """Return the provider turn unchanged after one no-tools recovery call."""

        return self._complete(
            mode="recover",
            task_frame=task_frame,
            context=context,
            evidence=evidence,
            gaps=gaps,
            failure_reason=failure_reason,
        )

    def repair(
        self,
        *,
        task_frame: TaskFrame,
        context: ResearchRunContext,
        evidence: tuple[AgentEvidence, ...],
        gaps: tuple[str, ...],
        failure_reason: str,
        rejected_sentences: tuple[str, ...],
        judge_issues: tuple[str, ...],
    ) -> ModelTurn:
        """Return one targeted semantic-repair turn without blessing its content."""

        return self._complete(
            mode="repair",
            task_frame=task_frame,
            context=context,
            evidence=evidence,
            gaps=gaps,
            failure_reason=failure_reason,
            rejected_sentences=rejected_sentences,
            judge_issues=judge_issues,
        )

    def _complete(
        self,
        *,
        mode: Literal["recover", "repair"],
        task_frame: TaskFrame,
        context: ResearchRunContext,
        evidence: tuple[AgentEvidence, ...],
        gaps: tuple[str, ...],
        failure_reason: str,
        rejected_sentences: tuple[str, ...] = (),
        judge_issues: tuple[str, ...] = (),
    ) -> ModelTurn:
        payload = self._payload(
            task_frame=task_frame,
            context=context,
            evidence=evidence,
            gaps=gaps,
            failure_reason=failure_reason,
        )
        if mode == "repair":
            payload["rejected_sentences"] = [
                {"index": index, "sentence": sentence}
                for index, sentence in enumerate(rejected_sentences, start=1)
            ]
            payload["judge_issues"] = list(judge_issues)
        timeout = context.deadline.synthesis_timeout(self._llm_timeout)
        if timeout <= 0.0:
            raise TimeoutError("finalization deadline exhausted")
        return self._model.complete(
            messages=[
                {
                    "role": "system",
                    "content": (
                        _RECOVERY_SYSTEM_PROMPT
                        if mode == "recover"
                        else _REPAIR_SYSTEM_PROMPT
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        payload,
                        ensure_ascii=False,
                    ),
                },
            ],
            tools=[],
            timeout=timeout,
        )

    @staticmethod
    def _payload(
        *,
        task_frame: TaskFrame,
        context: ResearchRunContext,
        evidence: tuple[AgentEvidence, ...],
        gaps: tuple[str, ...],
        failure_reason: str,
    ) -> dict[str, object]:
        return {
            "task_frame": task_frame.to_dict(),
            "required_outputs": [
                {
                    "output_id": item.output_id,
                    "description": item.description,
                    "evidence_types": list(item.evidence_types),
                    "required": item.required,
                }
                for item in context.contract.required_outputs
            ],
            "evidence": [public_agent_evidence(item) for item in evidence],
            "gaps": list(gaps),
            "today": context.today,
            "latest_data_date": context.latest_data_date,
            "failure_reason": str(failure_reason or "").strip(),
        }


__all__ = [
    "DEFAULT_FINALIZER_TIMEOUT",
    "EpisodeFinalizer",
    "MIN_FINALIZATION_RECOVERY_SECONDS",
]
