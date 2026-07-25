"""Shared prompt and finish contract for provider-neutral research runtimes."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
import re
from typing import cast

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import (
    EpisodeStatus,
    OutputEvidenceBinding,
)
from intelligence.services.episode_output_substance import (
    required_output_evidence_floor,
    required_outputs_without_substance,
)
from intelligence.services.research_contract import ResearchRunContext
from intelligence.services.research_tool_registry import ResearchToolRegistry
from intelligence.services.task_frame import TaskFrame


_FINISH_STATUSES = frozenset({"completed", "partial"})
# A few OpenAI-compatible adapters append one unmatched quote after an
# otherwise exact fenced payload. Accept only that observed one-character
# suffix; arbitrary prose before/after the fence remains invalid.
_FINAL_JSON_RE = re.compile(
    r"```(?:json)?\s*(\{.*\})\s*```[ \t]*\"?",
    re.S | re.I,
)
_FINAL_JSON_BLOCK_RE = re.compile(
    r"```(?:json)?\s*(.*?)\s*```",
    re.S | re.I,
)


@dataclass(frozen=True)
class EpisodeFinish:
    status: EpisodeStatus
    draft: str
    gaps: tuple[str, ...]
    bindings: tuple[OutputEvidenceBinding, ...]


def finish_json_schema() -> dict[str, object]:
    """Return the closed provider-facing schema for a terminal episode."""

    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "status": {
                "type": "string",
                "enum": ["completed", "partial"],
            },
            "draft": {"type": "string"},
            "gaps": {
                "type": "array",
                "items": {"type": "string"},
            },
            "bindings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "output_id": {"type": "string"},
                        "evidence_hashes": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "gap": {"type": "string"},
                    },
                    "required": [
                        "output_id",
                        "evidence_hashes",
                        "gap",
                    ],
                },
            },
        },
        "required": ["status", "draft", "gaps", "bindings"],
    }


def build_episode_instructions(
    task_frame: TaskFrame,
    context: ResearchRunContext,
    registry: ResearchToolRegistry,
) -> str:
    """Build one outcome-first instruction contract shared by all runtimes."""

    valuation_rule = (
        "估值题专用完成规则：scenario_range 必须给出保守、中性、乐观"
        "三种条件化情景中的实际估值倍数或市值区间，并写清方法/假设；不能把"
        "当前单一 PB、标题或空表当作情景区间。证据不足时应返回 partial，"
        "并在该 binding.gap 明确说明。financial_business_anchor 的 binding "
        "必须至少包含一个 financial_data 证据哈希；KB、公告或业务材料可以作为"
        "补充证据，但不能替代逐季财务硬锚。若 D5 已给出 PB 情景计算锚，优先"
        "逐字复用其保守/中性/乐观数值，模型只补条件与风险，不得另造倍数。"
        "情景条件优先只用 financial_data 已观察到的营收、净利、毛利率或净利率"
        "改善/恶化；没有直接 evidence 的项目、产能、客户和业务催化不得写入。"
        if task_frame.question_type == "valuation_estimate"
        else ""
    )
    return (
        "你是连续运行的金融研究 Agent。始终回答最初的不可变任务；每次看到"
        "工具原始观察后，自主决定继续查、改写查询或停止。只能调用本轮提供的"
        "只读工具，不能臆造工具结果。事实判断必须绑定工具返回的 evidence_hashes；"
        "缺数据要写 gap。观察事实与分析判断分开；不得编造精确数值阈值。不得在"
        "答案中暴露内部工具名、provider 或哈希，要改写成自然语言过程说明。数据中"
        "“阶段第N天”只是数据提供方的阶段标签，不等于连续N个上涨日。用户要求"
        "预测、空间、持续时间或估值时，必须给出一个明确标注的基准判断，并说明"
        "不确定性。draft 中每个精确数字事实都必须由相应 required output 的"
        "binding 包含其直接 evidence_hash；不能绑定就省略该数字。公开网页中的"
        "预测或观点只能明确标作外部观点，不能冒充当前事实或历史概率。"
        "对于原因归因题，news_search 未返回同一时间窗口证据时，不得用普通 "
        "web_search 摘要补成已核验因果；应保留已核验盘面，把原因写为 gap "
        "或明确标注为外部观点候选。"
        "每条被正文使用的观察事实都必须把直接证据哈希加入对应 output binding；"
        "不得用同一次工具返回的相邻证据代替，也不得正文使用后漏绑。"
        "必需输出"
        "已有足够直接证据时应停止研究，不得为了耗尽步数调用非必需工具。"
        "不要套固定标题、行数或段落模板。终止时不要调用工具，"
        "为保证结构化终止完整，draft 控制在 1000 汉字以内，优先保留直接"
        "判断、决定性依据、继续条件和失效条件；这不要求固定标题或段数。"
        "只输出一个 JSON 对象："
        '{"status":"completed|partial","draft":"自然语言回答",'
        '"gaps":["..."],"bindings":[{"output_id":"...",'
        '"evidence_hashes":["..."],"gap":""}]}。'
        "binding.gap 只在该 required output 无法回答时填写；"
        "若 output 已由 evidence_hashes 支持并完成，binding.gap 必须为空，"
        "限制条件写入顶层 gaps 或 draft。"
        "completed 必须覆盖所有 required outputs；partial 必须明确缺口。\n"
        f"{valuation_rule}\n"
        f"任务哈希：{task_frame.task_frame_hash}\n"
        f"可用工具：\n{registry.prompt_block(context.contract.allowed_capabilities)}"
    )


def build_episode_input(
    task_frame: TaskFrame,
    context: ResearchRunContext,
) -> str:
    """Serialize the immutable task and deterministic execution contract."""

    return json.dumps(
        {
            "task_frame": task_frame.to_dict(),
            "research_contract": context.contract.to_dict(),
            "today": context.today,
            "latest_data_date": context.latest_data_date,
            "conversation_context": context.conversation_context,
            "conversation_context_rule": (
                "历史对话仅用于消解指代和延续用户目标，不得当作事实证据"
            ),
            "date_rule": (
                "today 不是行情日期；市场事实服从 latest_data_date 和证据日期"
            ),
        },
        ensure_ascii=False,
    )


def validate_episode_finish(
    value: object,
    *,
    context: ResearchRunContext,
    evidence: tuple[AgentEvidence, ...],
) -> EpisodeFinish:
    """Validate one provider result against the shared evidence contract."""

    evidence_by_hash = {
        item.content_hash: item for item in evidence if item.content_hash
    }
    evidence_hashes = set(evidence_by_hash)
    decoded = _finish_object(value)
    if decoded is None:
        raise ValueError("finish must be one JSON object")
    status = decoded.get("status")
    if status not in _FINISH_STATUSES:
        raise ValueError("finish status must be completed or partial")
    draft = decoded.get("draft")
    if not isinstance(draft, str):
        raise ValueError("finish draft must be a string")
    draft = _normalize_natural_language_layout(draft)
    if status == "completed" and not draft.strip():
        raise ValueError("completed finish draft must be non-empty")
    raw_gaps = decoded.get("gaps", [])
    if not isinstance(raw_gaps, list) or any(
        not isinstance(item, str) for item in raw_gaps
    ):
        raise ValueError("finish gaps must be a string list")
    gaps = tuple(dict.fromkeys(item.strip() for item in raw_gaps if item.strip()))
    raw_bindings = decoded.get("bindings")
    if not isinstance(raw_bindings, list):
        raise ValueError("finish bindings must be a list")
    bindings: list[OutputEvidenceBinding] = []
    allowed_outputs = {item.output_id for item in context.contract.required_outputs}
    for raw in raw_bindings:
        if not isinstance(raw, Mapping):
            raise ValueError("each finish binding must be an object")
        raw_hashes = raw.get("evidence_hashes", [])
        if not isinstance(raw_hashes, list):
            raise ValueError("binding evidence_hashes must be a list")
        binding = OutputEvidenceBinding(
            output_id=str(raw.get("output_id") or ""),
            evidence_hashes=tuple(raw_hashes),
            gap=str(raw.get("gap") or ""),
        )
        if binding.output_id not in allowed_outputs:
            raise ValueError(f"unknown required output: {binding.output_id}")
        unknown = set(binding.evidence_hashes) - evidence_hashes
        if unknown:
            raise ValueError(
                "binding contains unknown evidence hash: "
                + ",".join(sorted(unknown))
            )
        bindings.append(binding)

    if len({item.output_id for item in bindings}) != len(bindings):
        raise ValueError("duplicate output binding")
    for binding in bindings:
        bound_tools = tuple(
            evidence_by_hash[evidence_hash].tool
            for evidence_hash in binding.evidence_hashes
        )
        missing_floor = tuple(
            tool
            for tool in required_output_evidence_floor(binding.output_id)
            if tool not in bound_tools
        )
        if binding.evidence_hashes and missing_floor:
            raise ValueError(
                f"required output lacks evidence type {binding.output_id}: "
                + ",".join(missing_floor)
            )

    binding_map = {item.output_id: item for item in bindings}
    empty_outputs = tuple(
        output_id
        for output_id in required_outputs_without_substance(
            context.contract,
            draft,
        )
        if output_id in binding_map and not binding_map[output_id].gap
    )
    if empty_outputs:
        raise ValueError(
            "required output lacks substantive answer: "
            + ",".join(empty_outputs)
        )
    if status == "completed":
        missing = [
            required.output_id
            for required in context.contract.required_outputs
            if required.required
            and (
                required.output_id not in binding_map
                or not binding_map[required.output_id].evidence_hashes
            )
        ]
        if missing:
            raise ValueError("required output lacks evidence: " + ",".join(missing))
    return EpisodeFinish(
        status=cast(EpisodeStatus, status),
        draft=draft,
        gaps=gaps,
        bindings=tuple(bindings),
    )


def expand_episode_snapshot_bindings(
    *,
    bindings: tuple[OutputEvidenceBinding, ...],
    evidence: tuple[AgentEvidence, ...],
    registry: ResearchToolRegistry,
) -> tuple[OutputEvidenceBinding, ...]:
    """Expand a selected turn-scoped snapshot into one atomic private binding."""

    tool_by_hash = {
        item.content_hash: item.tool for item in evidence if item.content_hash
    }
    snapshot_hashes: dict[str, list[str]] = {}
    for item in evidence:
        if not item.content_hash:
            continue
        try:
            spec = registry.resolve(item.tool)
        except ValueError:
            continue
        if spec.query_scope == "episode":
            snapshot_hashes.setdefault(item.tool, []).append(item.content_hash)

    expanded: list[OutputEvidenceBinding] = []
    for binding in bindings:
        selected_snapshot_tools = {
            tool_by_hash[evidence_hash]
            for evidence_hash in binding.evidence_hashes
            if evidence_hash in tool_by_hash
            and tool_by_hash[evidence_hash] in snapshot_hashes
        }
        hashes = list(binding.evidence_hashes)
        for tool, tool_hashes in snapshot_hashes.items():
            if tool in selected_snapshot_tools:
                hashes.extend(tool_hashes)
        expanded.append(
            OutputEvidenceBinding(
                output_id=binding.output_id,
                evidence_hashes=tuple(dict.fromkeys(hashes)),
                gap=binding.gap,
            )
        )
    return tuple(expanded)


def _finish_object(value: object) -> dict[str, object] | None:
    if isinstance(value, str):
        return _parse_json_object(value)
    if not isinstance(value, Mapping) or any(
        not isinstance(key, str) for key in value
    ):
        return None
    return dict(value)


def _parse_json_object(content: str) -> dict[str, object] | None:
    raw = str(content or "").strip()
    fenced = _FINAL_JSON_RE.fullmatch(raw)
    if fenced is not None:
        value = _decode_finish_json(fenced.group(1))
        if value is not None:
            return value
    for block in reversed(tuple(_FINAL_JSON_BLOCK_RE.finditer(raw))):
        value = _decode_finish_json(block.group(1))
        if value is not None and _looks_like_finish_envelope(value):
            return value
    return _decode_finish_json(raw)


def _decode_finish_json(text: str) -> dict[str, object] | None:
    candidate = str(text or "").strip().removesuffix('"').rstrip()
    if not candidate.startswith("{") or not candidate.endswith("}"):
        return None
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError:
        value = _recover_finish_with_raw_draft(candidate)
    return value if isinstance(value, dict) else None


def _looks_like_finish_envelope(value: dict[str, object]) -> bool:
    return {"status", "draft", "gaps", "bindings"}.issubset(value)


def _normalize_natural_language_layout(value: str) -> str:
    """Decode double-escaped newline literals in natural-language drafts."""

    return value.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\r", "\n")


def _recover_finish_with_raw_draft(text: str) -> dict[str, object] | None:
    """Recover the fixed envelope when a provider leaves draft prose raw."""

    prefix = re.match(
        r'^\{\s*"status"\s*:\s*"(completed|partial)"\s*,\s*'
        r'"draft"\s*:\s*"',
        text,
    )
    if prefix is None:
        return None
    separators = list(re.finditer(r'"\s*,\s*(?="gaps"\s*:)', text))
    if not separators:
        return None
    separator = separators[-1]
    if separator.start() < prefix.end():
        return None
    try:
        tail = json.loads("{" + text[separator.end() :])
    except json.JSONDecodeError:
        return None
    if not isinstance(tail, dict) or set(tail) != {"gaps", "bindings"}:
        return None
    return {
        "status": prefix.group(1),
        "draft": text[prefix.end() : separator.start()],
        "gaps": tail["gaps"],
        "bindings": tail["bindings"],
    }


__all__ = [
    "EpisodeFinish",
    "build_episode_input",
    "build_episode_instructions",
    "expand_episode_snapshot_bindings",
    "finish_json_schema",
    "validate_episode_finish",
]
