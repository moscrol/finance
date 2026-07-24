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
MAX_RECOVERY_EVIDENCE = 12
MAX_RECOVERY_DETAIL_CHARS = 360
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
    "原因归因缺少同一时间窗口的新闻证据时，不得用普通网页摘要补成已核验因果，"
    "只能保留盘面事实并把网页内容标为外部观点候选。"
    "draft 先直接回答用户问题、只保留决定性依据且不超过1200字。"
    "若 required_outputs 包含 scenario_range，必须给出保守、中性、乐观三种"
    "条件化情景中的实际估值倍数或市值区间；不能把当前单一 PB、标题或空表当作"
    "情景区间。若包含 financial_business_anchor，其 binding 必须至少包含一个 "
    "financial_data 哈希；KB 或业务材料只能作补充。无法满足时返回 partial 并写 gap。"
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
            "evidence": _compact_evidence(evidence),
            "gaps": list(gaps),
            "today": context.today,
            "latest_data_date": context.latest_data_date,
            "failure_reason": _stable_failure_reason(failure_reason),
        }


def _compact_evidence(
    evidence: tuple[AgentEvidence, ...],
) -> list[dict[str, object]]:
    """Select a bounded, tool-balanced view while retaining original hashes."""

    grouped: dict[str, list[AgentEvidence]] = {}
    for item in evidence:
        grouped.setdefault(item.tool, []).append(item)

    selected: list[AgentEvidence] = []
    index = 0
    while len(selected) < MAX_RECOVERY_EVIDENCE:
        added = False
        for items in grouped.values():
            if index >= len(items):
                continue
            selected.append(items[index])
            added = True
            if len(selected) >= MAX_RECOVERY_EVIDENCE:
                break
        if not added:
            break
        index += 1

    projected: list[dict[str, object]] = []
    for item in selected:
        public = public_agent_evidence(item)
        detail = str(public.get("detail") or "")
        if len(detail) > MAX_RECOVERY_DETAIL_CHARS:
            public["detail"] = (
                detail[: MAX_RECOVERY_DETAIL_CHARS - 3].rstrip() + "..."
            )
        projected.append(public)
    return projected


__all__ = [
    "DEFAULT_FINALIZER_TIMEOUT",
    "EpisodeFinalizer",
    "MAX_RECOVERY_DETAIL_CHARS",
    "MAX_RECOVERY_EVIDENCE",
    "MIN_FINALIZATION_RECOVERY_SECONDS",
]
