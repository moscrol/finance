"""Bounded no-tools finalization recovery for one research episode."""

from __future__ import annotations

import json

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
_FAILURE_REASON_CODES = frozenset(
    {
        "deadline_exhausted",
        "finalization_recovery_exception",
        "invalid_model_finish",
        "model_exception",
        "provider_error",
        "semantic_rejection",
        "tool_call_during_finalization",
        "unknown_failure",
    }
)

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

_DRAFT_REPAIR_SYSTEM_PROMPT = (
    "你是金融研究 Agent 的措辞修复器。事实、证据、绑定、缺口与完成状态已经冻结，"
    "你无权修改它们，也不得请求工具。只能在原草稿内删除、收窄或加限定语，以解决"
    "被拒绝句子和 judge issues。issue 点名为无据或矛盾的事实、数字、阈值、日期、"
    "因果或建议必须删除，不得把被拒绝内容改写成“证据给出”或换句复述。用户明确"
    "要求预测、持续时间、空间或估值时，可以保留一个明确标注为“我的判断/主观估计”"
    "的条件性结论；不要把该估计冒充来源事实，其理由只能沿用未被拒绝的原稿事实。"
    "若 issue 只指出内部工具名、provider 或哈希泄漏，可把它改成自然语言过程描述，"
    "但不得改变原有的成功、空结果或失败状态。"
    "不得新增事实、因果、数字、阈值、日期、主体、证据、哈希或绑定。优先删减，"
    "不要扩写。只输出一个严格 JSON 对象，字段必须且只能是 "
    '{"draft":"修订后的自然语言回答"}；不要输出解释、工具调用或 JSON 之外的文本。'
)


def _stable_failure_reason(value: object) -> str:
    """Keep provider/parser details out of the compact recovery prompt."""

    text = str(value or "")
    cleaned = "".join(
        char if ord(char) >= 32 and ord(char) != 127 else " " for char in text
    ).strip()
    cleaned = " ".join(cleaned.split())[:240]
    if cleaned in _FAILURE_REASON_CODES:
        return cleaned
    if cleaned.startswith("model_exception"):
        return "model_exception"
    if cleaned.startswith("finalization_recovery_exception"):
        return "finalization_recovery_exception"
    if cleaned.startswith("tool_call_during_finalization"):
        return "tool_call_during_finalization"
    if "deadline" in cleaned or "timeout" in cleaned:
        return "deadline_exhausted"
    if (
        "invalid" in cleaned
        or cleaned.startswith("finish")
        or "evidence hash" in cleaned
    ):
        return "invalid_model_finish"
    if "provider" in cleaned or "transport" in cleaned:
        return "provider_error"
    if "semantic" in cleaned or "judge" in cleaned:
        return "semantic_rejection"
    return "unknown_failure"


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

        payload = self._payload(
            task_frame=task_frame,
            context=context,
            evidence=evidence,
            gaps=gaps,
            failure_reason=failure_reason,
        )
        return self._complete(
            system_prompt=_RECOVERY_SYSTEM_PROMPT,
            payload=payload,
            context=context,
        )

    def repair_draft(
        self,
        *,
        task_frame: TaskFrame,
        context: ResearchRunContext,
        draft: str,
        rejected_sentences: tuple[str, ...],
        judge_issues: tuple[str, ...],
    ) -> ModelTurn:
        """Repair wording only; truth-plane state never enters the model output."""

        payload: dict[str, object] = {
            "task_frame": task_frame.to_dict(),
            "required_outputs": [
                {
                    "output_id": item.output_id,
                    "description": item.description,
                    "required": item.required,
                }
                for item in context.contract.required_outputs
            ],
            "draft": str(draft),
            "rejected_sentences": [
                {"index": index, "sentence": sentence}
                for index, sentence in enumerate(rejected_sentences, start=1)
            ],
            "judge_issues": list(judge_issues),
        }
        return self._complete(
            system_prompt=_DRAFT_REPAIR_SYSTEM_PROMPT,
            payload=payload,
            context=context,
        )

    def _complete(
        self,
        *,
        system_prompt: str,
        payload: dict[str, object],
        context: ResearchRunContext,
    ) -> ModelTurn:
        timeout = context.deadline.synthesis_timeout(self._llm_timeout)
        if timeout <= 0.0:
            raise TimeoutError("finalization deadline exhausted")
        return self._model.complete(
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
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
            "failure_reason": _stable_failure_reason(failure_reason),
        }


__all__ = [
    "DEFAULT_FINALIZER_TIMEOUT",
    "EpisodeFinalizer",
    "MIN_FINALIZATION_RECOVERY_SECONDS",
]
