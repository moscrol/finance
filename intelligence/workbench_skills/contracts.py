from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol, TypeAlias

from intelligence.services import answer_model
from intelligence.services.research_contract import ResearchDeadline
from intelligence.services.run_store import RunStore, redact

JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]
SkillResultStatus: TypeAlias = Literal[
    "completed",
    "partial",
    "degraded",
    "failed",
]


def redact_json(value: JsonValue) -> JsonValue:
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, list):
        return [redact_json(item) for item in value]
    if isinstance(value, dict):
        return {key: redact_json(item) for key, item in value.items()}
    return value


@dataclass(frozen=True)
class SkillDefinition:
    skill_id: str
    name: str
    description: str
    version: str
    triggers: tuple[str, ...]
    input_schema: JsonObject
    permissions: tuple[str, ...]
    timeout_seconds: int


@dataclass
class SkillOutput:
    skill_id: str
    modules: list[JsonObject]
    citations: list[JsonObject]
    warnings: list[str]
    as_of: str | None
    raw_result_ref: str | None
    answer_contract: SkillAnswerContract | None = None
    stage_artifacts: list[JsonObject] = field(default_factory=list)
    status: SkillResultStatus | None = None


@dataclass(frozen=True)
class SkillAnswerContract:
    retrieval_plan: tuple[str, ...]
    output_contract: tuple[str, ...]
    answer_spec: answer_model.AnswerSpec
    question_type: str | None = None


def build_module_answer_contract(
    *,
    skill_id: str,
    title: str,
    modules: list[JsonObject],
    citations: list[JsonObject],
    warnings: list[str],
    as_of: str | None,
    retrieval_plan: tuple[str, ...],
    output_contract: tuple[str, ...],
) -> SkillAnswerContract | None:
    facts = _module_fact_lines(modules)
    if not facts or not citations:
        return None
    sources = tuple(
        answer_model.EvidenceRef(
            evidence_id=f"K{index}",
            source=str(citation.get("title") or citation.get("source") or title),
            detail=str(citation.get("source") or ""),
            tier=str(citation.get("evidence_layer") or ""),
            source_date=str(citation.get("as_of") or as_of or "") or None,
        )
        for index, citation in enumerate(citations, start=1)
    )
    evidence_ids = tuple(source.evidence_id for source in sources)
    verified = tuple(
        answer_model.make_claim(
            claim_id=f"{skill_id}:fact:{index}",
            text=line,
            claim_type="skill_fact",
            theme=title,
            status=answer_model.ClaimStatus.VERIFIED,
            evidence_tier=sources[0].tier if sources else "skill_output",
            evidence_ids=evidence_ids,
        )
        for index, line in enumerate(facts[:16], start=1)
    )
    summary = (
        answer_model.make_claim(
            claim_id=f"{skill_id}:summary",
            text=f"截至 {as_of}，{facts[0]}" if as_of else facts[0],
            claim_type="skill_summary",
            theme=title,
            status=answer_model.ClaimStatus.VERIFIED,
            evidence_tier=sources[0].tier if sources else "skill_output",
            evidence_ids=evidence_ids,
        ),
    )
    gaps = tuple(
        answer_model.make_claim(
            claim_id=f"{skill_id}:gap:{index}",
            text=warning,
            claim_type="skill_gap",
            theme=title,
            status=answer_model.ClaimStatus.MISSING,
        )
        for index, warning in enumerate(warnings, start=1)
    ) or (
        answer_model.make_claim(
            claim_id=f"{skill_id}:gap:scope",
            text="当前结论只覆盖本轮专项资料，未覆盖的信息保持未知。",
            claim_type="skill_gap",
            theme=title,
            status=answer_model.ClaimStatus.MISSING,
        ),
    )
    actions = tuple(_module_actions(modules)) or (
        "下一验证窗口复核核心指标、风险项和资料日期是否发生变化。",
    )
    triggers = (
        answer_model.make_claim(
            claim_id=f"{skill_id}:trigger",
            text="若核心指标、风险项或资料日期出现反向变化，当前判断应降级。",
            claim_type="skill_trigger",
            theme=title,
            status=answer_model.ClaimStatus.INFERRED,
            evidence_ids=evidence_ids,
        ),
    )
    spec = answer_model.AnswerSpec(
        research_spec=answer_model.resolve_theme_research_spec(title, title),
        summary=summary,
        verified_facts=verified,
        company_table=(),
        counter_evidence=(),
        gaps=gaps,
        triggers=triggers,
        next_actions=actions,
        sources=sources,
        system_notices=(),
        prompt_constraints=(
            *(f"检索计划：{item}" for item in retrieval_plan),
            *(f"输出契约：{item}" for item in output_contract),
        ),
        presentation_kind="base_finance",
        presentation_title=title,
    )
    return SkillAnswerContract(
        retrieval_plan=retrieval_plan,
        output_contract=output_contract,
        answer_spec=answer_model.finalize_answer_spec(spec),
    )


def _module_fact_lines(modules: list[JsonObject]) -> list[str]:
    lines: list[str] = []
    for module in modules:
        for key in ("summary", "content"):
            value = module.get(key)
            if isinstance(value, str) and value.strip():
                lines.append(value.strip())
        metrics = module.get("metrics")
        if isinstance(metrics, list):
            for metric in metrics:
                if not isinstance(metric, dict):
                    continue
                label = metric.get("label")
                value = metric.get("value")
                if isinstance(label, str) and value is not None:
                    lines.append(f"{label}：{value}")
        items = module.get("items")
        if isinstance(items, list):
            for item in items:
                if not isinstance(item, dict):
                    continue
                item_title = item.get("title")
                item_summary = item.get("summary")
                if isinstance(item_summary, str) and item_summary.strip():
                    prefix = (
                        f"{item_title}："
                        if isinstance(item_title, str) and item_title.strip()
                        else ""
                    )
                    lines.append(f"{prefix}{item_summary.strip()}")
    return list(dict.fromkeys(lines))


def _module_actions(modules: list[JsonObject]) -> list[str]:
    actions: list[str] = []
    for module in modules:
        items = module.get("items")
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            action = item.get("next_action")
            if isinstance(action, str) and action.strip():
                actions.append(action.strip())
    return list(dict.fromkeys(actions))


@dataclass(frozen=True)
class SkillExecutionContext:
    query: str
    task_type: str
    user_id: str
    run_id: str
    conversation_id: str | None
    repo_root: Path
    run_store: RunStore
    conversation_context: str = ""
    turn_intent: JsonObject | None = None
    research_plan: JsonObject | None = None
    inherited_answer_spec: JsonObject | None = None
    inherited_stage_artifacts: tuple[JsonObject, ...] = ()
    inherited_evidence_atoms: tuple[JsonObject, ...] = ()
    deadline: ResearchDeadline | None = None
    retrieval_cache: dict[str, object] = field(default_factory=dict)


class SkillExecutor(Protocol):
    skill_id: str

    def execute(self, context: SkillExecutionContext) -> SkillOutput: ...
