"""Bounded no-tools finalization recovery for one research episode."""

from __future__ import annotations

from collections.abc import Callable, Mapping
import json

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import (
    AgentModelClient,
    ModelTurn,
    public_agent_evidence,
)
from intelligence.services.episode_protocol import (
    EPISODE_DRAFT_MAX_CHARS,
    attach_evidence_ordinals,
    evidence_ordinal_table,
    strip_hashes_for_model,
)
from intelligence.services.material_grounding import claim_finish_format, material_grounding_payload
from intelligence.services.material_answer_authoring import material_author_model_view
from intelligence.services.material_delivery import material_delivery_payload, material_question_outputs
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

_RECOVERY_GROUNDING_RULES = (
    "若输入带 material_grounding，按其原来源规则绑定用户材料/旧答坐标，材料事实无需工具序号；"
    "采用 bindings 的作者格式，其 basis 必须与 required_outputs 的 grounding_mode 一致；"
    "model_reasoning 与 user_premise 可以不带证据序号，但不得把它们伪装成 evidence。"
    "domain_materials 是领域提供的程序结果与输出合同，按其中规则交付，不得把题设结果升为事实证据。"
    "grounding_mode=evidence 的 required output 无证据覆盖时必须返回 partial 并填写 gap；不要输出代码围栏、"
    "解释、工具调用或 JSON 之外的文本。"
    "原因归因缺少同一时间窗口的新闻证据时，不得用普通网页摘要补成已核验因果，"
    "只能保留盘面事实并把网页内容标为外部观点候选。"
    f"最终正文先直接回答用户问题，再写清关键数据及其日期与来源，不超过{EPISODE_DRAFT_MAX_CHARS}字。"
    "若 required_outputs 包含 scenario_range，必须给出保守、中性、乐观三种"
    "条件化情景中的实际估值倍数或市值区间；不能把当前单一 PB、标题或空表当作"
    "情景区间。若包含 financial_business_anchor，其 binding 必须至少包含一个 "
    "financial_data 证据序号；KB 或业务材料只能作补充。无法满足时返回 partial 并写 gap。"
    "evidence 若含 PB 情景计算锚，逐字复用其三组数值，只补条件与风险，不得另造倍数。"
    "情景条件优先只使用 financial_data 的营收、净利、毛利率或净利率变化；"
    "没有直接 evidence 的项目、产能、客户和业务催化不得写入。"
)

_RECOVERY_SYSTEM_PROMPT = (
    "你是金融研究 Agent 的终局恢复器。研究与工具阶段已经永久关闭，不得请求或"
    "臆造任何新证据。只能使用用户 JSON 中 evidence 的序号 E1、E2…，严格"
    "回答原始 TaskFrame 与 required_outputs。只输出一个 FINAL_JSON 对象："
    '{"status":"completed|partial","draft":"自然语言回答",'
    '"gaps":["..."],"bindings":[{"output_id":"...",'
    '"evidence_hashes":["E1","E2"],"basis":"evidence|user_premise|model_reasoning",'
    '"gap":""}]}。'
    + _RECOVERY_GROUNDING_RULES
)

_AUTHOR_RECOVERY_SYSTEM_PROMPT = (
    "你是金融研究 Agent 的终局恢复器。研究与工具阶段已经永久关闭，不得请求或臆造任何新证据。"
    "按本集最初的 finish_format.wire_template 与 rule 提交一个完整终局 JSON，回答原始 TaskFrame 与 required_outputs。"
    "最终正文的结构、自由文字与是否选择已送达结果由作者决定；格式描述不授予来源、工具、预算或完成权限。"
    "工具事实只使用本次 evidence 序号；材料与旧答继续服从 material_grounding 的原来源规则。"
    "历史助手判断不是当前事实或数值输入，不恢复权限；缺少支持时明确 partial 与具体 gap，不得猜补。"
    "只输出JSON，不要代码围栏、解释或工具调用。"
    + _RECOVERY_GROUNDING_RULES
)


class _UnsetFinishFormat:
    """A caller omitted the optional argument, rather than saved its absence."""


_UNSET_FINISH_FORMAT = _UnsetFinishFormat()


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
        on_prompt: Callable[[str, str], None] | None = None,
        evidence_priority: tuple[str, ...] = (),
        domain_materials: dict[str, object] | None = None,
        finish_format: Mapping[str, object] | None | _UnsetFinishFormat = _UNSET_FINISH_FORMAT,
    ) -> ModelTurn:
        """Return the provider turn unchanged after one no-tools recovery call.

        ``on_prompt(system, user)`` 在向模型开口之前收到这段独立 prompt 的正文——Episode 用它
        落 ``prompt_assembled{source: finalizer}``（模型可见即已落账，运行底座 P0 已知边界 a）。
        默认 None：不接线的调用方行为不变。
        """

        # Original direct callers already used the material owner's projection.
        # Runtime supplies an explicit saved descriptor or None; only an omitted
        # Python argument may select the original material owner's default.
        selected_format = (
            claim_finish_format(context.contract, prior_evidence=context.prior_evidence)
            if isinstance(finish_format, _UnsetFinishFormat) else finish_format
        )
        payload = self._payload(
            task_frame=task_frame,
            context=context,
            evidence=evidence,
            gaps=gaps,
            failure_reason=failure_reason,
            evidence_priority=evidence_priority,
            domain_materials=domain_materials,
            finish_format=selected_format,
        )
        return self._complete(
            system_prompt=_AUTHOR_RECOVERY_SYSTEM_PROMPT if selected_format is not None else _RECOVERY_SYSTEM_PROMPT,
            payload=payload,
            context=context,
            on_prompt=on_prompt,
        )

    def _complete(
        self,
        *,
        system_prompt: str,
        payload: dict[str, object],
        context: ResearchRunContext,
        on_prompt: Callable[[str, str], None] | None = None,
    ) -> ModelTurn:
        timeout = context.deadline.synthesis_timeout(self._llm_timeout)
        if timeout <= 0.0:
            raise TimeoutError("finalization deadline exhausted")
        user_content = json.dumps(payload, ensure_ascii=False)
        if on_prompt is not None:
            on_prompt(system_prompt, user_content)
        return self._model.complete(
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_content,
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
        evidence_priority: tuple[str, ...] = (),
        domain_materials: dict[str, object] | None = None,
        finish_format: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        selected = _compact_evidence(evidence, evidence_priority=evidence_priority)
        payload = {
            "task_frame": task_frame.to_model_dict(),
            "required_outputs": [
                {
                    "output_id": item.output_id,
                    "description": item.description,
                    "evidence_types": list(item.evidence_types),
                    "required": item.required,
                    "grounding_mode": item.grounding_mode,
                }
                for item in context.contract.required_outputs
            ],
            "evidence": selected,
            "gaps": list(gaps),
            "today": context.today,
            "latest_data_date": context.latest_data_date,
            "failure_reason": _stable_failure_reason(failure_reason),
        }
        if domain_materials:
            payload["domain_materials"] = domain_materials
        if finish_format is not None:
            payload["finish_format"] = dict(finish_format)
        if context.contract.material_contract is None:
            from intelligence.services.owned_results import _catalogue_from_context

            catalogue = _catalogue_from_context(context)
            if catalogue.blocks:
                payload["owned_results"] = {
                    "parts": catalogue.model_view(),
                    "instruction": "按本集最初的finish_format选择已实际送达的result_ref；引用与自由文字结构由作者决定，自由文字未获语义认证。",
                }
        grounding = material_grounding_payload(context.contract, prior_evidence=context.prior_evidence)
        if grounding is not None:
            if finish_format is None:
                grounding.pop("finish_format", None)
            payload["material_grounding"] = grounding
        if material_question_outputs(context.contract):
            payload["material_delivery"] = material_delivery_payload(context.contract)
        if len(selected) < len(evidence):
            tools = dict.fromkeys(item.tool for item in evidence)
            payload["evidence_selection"] = {
                "available": len(evidence),
                "selected": len(selected),
                "omitted": len(evidence) - len(selected),
                "by_tool": {
                    tool: {
                        "available": sum(item.tool == tool for item in evidence),
                        "selected": sum(item["tool"] == tool for item in selected),
                    }
                    for tool in tools
                },
                "instruction": (
                    "这是有条数上限的证据投影；未展示不等于数据缺失。"
                    "不得把展示条数当作原始样本数或覆盖范围；真实缺失只能依据gaps"
                    "及证据中明确的状态。未展示的信息不能据此断言不存在，证据不足须写明恢复投影边界。"
                ),
            }
        if finish_format is None:
            return payload
        projected = material_author_model_view(payload, context.contract, task_frame, prior_evidence=context.prior_evidence)
        grounding = projected.get("material_grounding")
        if isinstance(grounding, dict) and "finish_format" in grounding:
            # Source projection remains material-owned; its author description
            # still belongs to this episode's originally saved prompt.
            grounding["finish_format"] = dict(finish_format)
        return projected


def _compact_evidence(
    evidence: tuple[AgentEvidence, ...],
    *,
    evidence_priority: tuple[str, ...] = (),
) -> list[dict[str, object]]:
    """Select a bounded, tool-balanced view. IDs follow the full episode table."""

    grouped: dict[str, list[AgentEvidence]] = {}
    for item in evidence:
        grouped.setdefault(item.tool, []).append(item)

    available = {item.content_hash for item in evidence if item.content_hash}
    priority = tuple(dict.fromkeys(
        digest for digest in evidence_priority[:MAX_RECOVERY_EVIDENCE]
        if isinstance(digest, str) and digest in available
    ))
    rank = {digest: index for index, digest in enumerate(priority)}
    if priority:
        for items in grouped.values():
            items.sort(key=lambda item: rank.get(item.content_hash, len(rank)))

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
        if index == 1 and priority:
            # Keep one observation per tool before allocating remaining slots to
            # domain hints. Ordinary recovery retains its original round robin.
            for digest in priority:
                if len(selected) >= MAX_RECOVERY_EVIDENCE:
                    break
                item = next(item for item in evidence if item.content_hash == digest)
                if item not in selected:
                    selected.append(item)
            # Priority picks may be beyond the next round-robin cursor.
            for tool, items in grouped.items():
                grouped[tool] = [item for item in items if item not in selected]
            index = 0
            priority = ()

    ordinals = evidence_ordinal_table(evidence)
    projected: list[dict[str, object]] = []
    for item in selected:
        public = public_agent_evidence(item)
        detail = str(public.get("detail") or "")
        if len(detail) > MAX_RECOVERY_DETAIL_CHARS:
            public["detail"] = (
                detail[: MAX_RECOVERY_DETAIL_CHARS - 3].rstrip() + "..."
            )
        projected.append(public)
    facing = strip_hashes_for_model(
        {"evidence": attach_evidence_ordinals(projected, ordinals)}
    )
    return list(facing["evidence"])


__all__ = [
    "DEFAULT_FINALIZER_TIMEOUT",
    "EpisodeFinalizer",
    "MAX_RECOVERY_DETAIL_CHARS",
    "MAX_RECOVERY_EVIDENCE",
    "MIN_FINALIZATION_RECOVERY_SECONDS",
]
