from __future__ import annotations

import re
import time
from dataclasses import asdict, dataclass, field
from typing import Literal, TypeAlias, cast

from intelligence.services.query_resolution import (
    QueryResolution,
    classify_reference,
)
from intelligence.services.query_understanding import QueryEnvelope
from intelligence.services.route_table import owner_skills_from_route_table
from intelligence.services.evidence_capabilities import EvidencePlan, EvidenceRequirement
from intelligence.services.task_frame import TaskFrame

AnswerOwner: TypeAlias = Literal[
    "stock-deep-dive",
    "financial-analysis",
    "news-impact",
    "theme-research",
]
OwnerExecutionMode: TypeAlias = Literal["inline", "subtask"]
ClaimType: TypeAlias = Literal["fact", "inference", "expectation"]
StageStatus: TypeAlias = Literal[
    "pending",
    "completed",
    "partial",
    "timeout",
    "failed",
    "skipped",
]

RESEARCH_OWNER_IDS = frozenset(
    {
        "stock-deep-dive",
        "financial-analysis",
        "news-impact",
        "theme-research",
    }
)
QUESTION_OWNER_SKILLS: dict[str, AnswerOwner] = {
    question_type: cast(AnswerOwner, owner)
    for question_type, owner in owner_skills_from_route_table().items()
    if owner in RESEARCH_OWNER_IDS
}
OWNER_RETRIEVAL_STAGES: dict[AnswerOwner, tuple[str, ...]] = {
    "stock-deep-dive": (
        "company_master",
        "company_evidence",
        "financial_transmission",
        "market_choice",
        "counterevidence",
    ),
    "financial-analysis": (
        "report_period",
        "financial_metrics",
        "segment_disclosure",
        "prior_period_comparison",
    ),
    "news-impact": (
        "original_disclosure",
        "event_facts",
        "external_news",
        "impact_transmission",
        "substitutes_and_harmed_directions",
    ),
    "theme-research": (
        "definition",
        "chain_stages",
        "company_mapping",
        "market_lifecycle",
        "historical_analogs",
        "scenario_tree",
        "counterevidence",
    ),
}


@dataclass(frozen=True)
class OwnerWorkflowSpec:
    owner: AnswerOwner
    label: str
    execution_mode: OwnerExecutionMode
    preset: str
    required_skill_ids: tuple[str, ...]
    retrieval_stages: tuple[str, ...]
    output_schema: str
    presentation_kind: str
    max_wall_time_seconds: int

    def __post_init__(self) -> None:
        if self.execution_mode not in {"inline", "subtask"}:
            raise ValueError("unsupported owner execution mode")
        if self.max_wall_time_seconds <= 0:
            raise ValueError("owner workflow wall time must be positive")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


OWNER_WORKFLOW_SPECS: dict[AnswerOwner, OwnerWorkflowSpec] = {
    "stock-deep-dive": OwnerWorkflowSpec(
        owner="stock-deep-dive",
        label="个股深挖",
        execution_mode="inline",
        preset="finance-researcher",
        required_skill_ids=("finance-mode", "stock-deep-dive"),
        retrieval_stages=OWNER_RETRIEVAL_STAGES["stock-deep-dive"],
        output_schema="AnswerSpec",
        presentation_kind="theme_research",
        max_wall_time_seconds=240,
    ),
    "financial-analysis": OwnerWorkflowSpec(
        owner="financial-analysis",
        label="财务分析",
        execution_mode="inline",
        preset="finance-financial-analyst",
        required_skill_ids=("finance-mode", "financial-analysis"),
        retrieval_stages=OWNER_RETRIEVAL_STAGES["financial-analysis"],
        output_schema="AnswerSpec",
        presentation_kind="base_finance",
        max_wall_time_seconds=240,
    ),
    "news-impact": OwnerWorkflowSpec(
        owner="news-impact",
        label="消息与公告冲击",
        execution_mode="inline",
        preset="finance-event-analyst",
        required_skill_ids=("finance-mode", "news-impact"),
        retrieval_stages=OWNER_RETRIEVAL_STAGES["news-impact"],
        output_schema="AnswerSpec",
        presentation_kind="theme_research",
        max_wall_time_seconds=240,
    ),
    "theme-research": OwnerWorkflowSpec(
        owner="theme-research",
        label="题材研究",
        execution_mode="inline",
        preset="finance-theme-researcher",
        required_skill_ids=("finance-mode", "theme-research"),
        retrieval_stages=OWNER_RETRIEVAL_STAGES["theme-research"],
        output_schema="AnswerSpec",
        presentation_kind="theme_research",
        max_wall_time_seconds=240,
    ),
}

_COMPARISON_PATTERN = re.compile(r"(?:比较|对比|相比|和.+比|与.+比)")
_CONTEXT_DEPENDENT_RESEARCH_PATTERN = re.compile(
    r"(?:原因|为什么|证伪|反证|弹性|赔率|空间|受益|一阶|二阶|"
    r"历史类似|历史类比|真实订单|订单|验证清单|验证路径|下周|"
    r"催化|风险|毛利率|净利率|收入|利润|现金流|兑现|替代标的|"
    r"哪个更|分别是谁|怎么看|如何验证|"
    r"(?:这个|那个|这次|那次)(?:反弹|修复))"
)
_CONTEXT_DEPENDENT_RESEARCH_PREFIX_PATTERN = re.compile(
    r"^(?:毛利率|净利率|收入|营收|利润|现金流|原因|为什么|"
    r"历史类似|历史类比|真实订单|订单|验证清单|验证路径|"
    r"下周|一阶|二阶|哪些反证|哪些风险)"
)
_EXPLICIT_SWITCH_PATTERN = re.compile(
    r"(?:改看|换成|切换到|另外看|再分析|重新分析|转向)"
)
_TASK_SWITCH_PATTERNS: dict[str, re.Pattern[str]] = {
    "financial_analysis": re.compile(
        r"(财报|年报|季报|中报|收入|营收|利润|毛利率|净利率|现金流)"
    ),
    "news_impact": re.compile(r"(公告|新闻|消息|事件).{0,12}(影响|冲击|利好|利空)"),
    "stock_deep_dive": re.compile(
        r"(个股深挖|公司深挖|上涨空间|后续空间|还能涨|估值|贵不贵)"
    ),
    "theme_analysis": re.compile(r"(题材|产业链|板块).{0,12}(研究|分析|梳理|深挖)"),
}


@dataclass(frozen=True)
class TurnIntent:
    primary_subject: str | None
    secondary_topics: tuple[str, ...]
    question_type: str
    answer_owner: AnswerOwner | None
    comparison_entities: tuple[str, ...]
    inherited_from_turn: str | None
    evidence_atom_ids: tuple[str, ...] = ()
    skill_ids: tuple[str, ...] = ()
    stage_artifact_ids: tuple[str, ...] = ()
    time_horizon: str = "unspecified"
    operators: tuple[str, ...] = ()
    required_outputs: tuple[str, ...] = ()
    timeframe: str | None = None
    task_frame_hash: str = ""
    pending_task_frame: dict[str, object] | None = None
    clarification_rounds: int = 0

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: object) -> TurnIntent | None:
        if not isinstance(value, dict):
            return None
        try:
            primary_subject = value.get("primary_subject")
            question_type = value["question_type"]
            answer_owner = value.get("answer_owner")
            inherited_from_turn = value.get("inherited_from_turn")
            secondary_topics = value.get("secondary_topics", ())
            comparison_entities = value.get("comparison_entities", ())
            evidence_atom_ids = value.get("evidence_atom_ids", ())
            skill_ids = value.get("skill_ids", ())
            stage_artifact_ids = value.get("stage_artifact_ids", ())
            time_horizon = value.get("time_horizon", "unspecified")
            operators = value.get("operators", ())
            required_outputs = value.get("required_outputs", ())
            timeframe = value.get("timeframe")
            task_frame_hash = value.get("task_frame_hash", "")
            pending_task_frame = value.get("pending_task_frame")
            clarification_rounds = value.get("clarification_rounds", 0)
        except KeyError:
            return None
        if primary_subject is not None and not isinstance(primary_subject, str):
            return None
        if not isinstance(question_type, str):
            return None
        if answer_owner is not None and answer_owner not in RESEARCH_OWNER_IDS:
            return None
        if inherited_from_turn is not None and not isinstance(inherited_from_turn, str):
            return None
        if not isinstance(time_horizon, str):
            return None
        if timeframe is not None and not isinstance(timeframe, str):
            return None
        if not isinstance(task_frame_hash, str):
            return None
        if pending_task_frame is not None and not isinstance(
            pending_task_frame,
            dict,
        ):
            return None
        if (
            isinstance(clarification_rounds, bool)
            or not isinstance(clarification_rounds, int)
            or clarification_rounds < 0
        ):
            return None
        for items in (
            secondary_topics,
            comparison_entities,
            evidence_atom_ids,
            skill_ids,
            stage_artifact_ids,
            operators,
            required_outputs,
        ):
            if not isinstance(items, (list, tuple)) or any(
                not isinstance(item, str) for item in items
            ):
                return None
        return cls(
            primary_subject=primary_subject,
            secondary_topics=tuple(secondary_topics),
            question_type=question_type,
            answer_owner=answer_owner,
            comparison_entities=tuple(comparison_entities),
            inherited_from_turn=inherited_from_turn,
            evidence_atom_ids=tuple(evidence_atom_ids),
            skill_ids=tuple(skill_ids),
            stage_artifact_ids=tuple(stage_artifact_ids),
            time_horizon=time_horizon,
            operators=tuple(operators),
            required_outputs=tuple(required_outputs),
            timeframe=timeframe,
            task_frame_hash=task_frame_hash,
            pending_task_frame=pending_task_frame,
            clarification_rounds=clarification_rounds,
        )


@dataclass(frozen=True)
class ResearchPlan:
    primary_subject: str | None
    question_type: str
    answer_owner: AnswerOwner | None
    retrieval_stages: tuple[str, ...]
    comparison_entities: tuple[str, ...] = ()
    inherited_from_turn: str | None = None
    evidence_atom_ids: tuple[str, ...] = ()
    skill_ids: tuple[str, ...] = ()
    stage_artifact_ids: tuple[str, ...] = ()
    time_horizon: str = "unspecified"
    operators: tuple[str, ...] = ()
    required_outputs: tuple[str, ...] = ()
    timeframe: str | None = None
    task_frame_hash: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_intent(cls, intent: TurnIntent) -> ResearchPlan:
        stages = (
            OWNER_WORKFLOW_SPECS[intent.answer_owner].retrieval_stages
            if intent.answer_owner is not None
            else ()
        )
        return cls(
            primary_subject=intent.primary_subject,
            question_type=intent.question_type,
            answer_owner=intent.answer_owner,
            retrieval_stages=stages,
            comparison_entities=intent.comparison_entities,
            inherited_from_turn=intent.inherited_from_turn,
            evidence_atom_ids=intent.evidence_atom_ids,
            skill_ids=intent.skill_ids,
            stage_artifact_ids=intent.stage_artifact_ids,
            time_horizon=intent.time_horizon,
            operators=intent.operators,
            required_outputs=intent.required_outputs,
            timeframe=intent.timeframe,
            task_frame_hash=intent.task_frame_hash,
        )


@dataclass(frozen=True)
class ResearchDeadline:
    expires_at: float
    # P0：为最终合成保留的硬预算（秒）。前置检索阶段的 stage_timeout 不得
    # 消费这段时间，避免检索耗尽预算后合成剩 0ms 只能降级为模板。
    synthesis_reserve: float = 0.0

    @classmethod
    def from_timeout(
        cls,
        timeout: float,
        *,
        synthesis_reserve: float = 0.0,
    ) -> ResearchDeadline:
        return cls(
            time.monotonic() + max(0.0, float(timeout)),
            synthesis_reserve=max(0.0, float(synthesis_reserve)),
        )

    def remaining(self) -> float:
        return max(0.0, self.expires_at - time.monotonic())

    def stage_timeout(self, configured_limit: float) -> float:
        available = max(0.0, self.remaining() - self.synthesis_reserve)
        return max(0.0, min(float(configured_limit), available))

    def synthesis_timeout(self, configured_limit: float) -> float:
        """合成阶段可用全部剩余时间（含保留段）。"""
        return max(0.0, min(float(configured_limit), self.remaining()))

    @property
    def expired(self) -> bool:
        return self.remaining() <= 0.0


@dataclass(frozen=True)
class ResearchPolicy:
    """Generic owner 的确定性档位，不允许由 LLM 提高上限。"""

    tier: str
    max_steps: int
    total_seconds: float
    synthesis_reserve: float

    @classmethod
    def for_tier(cls, tier: str) -> "ResearchPolicy":
        policies = {
            "quick": cls("quick", 3, 30.0, 20.0),
            "standard": cls("standard", 6, 90.0, 20.0),
            "deep": cls("deep", 12, 240.0, 48.0),
        }
        return policies.get(tier, policies["standard"])


@dataclass(frozen=True)
class RequiredOutput:
    output_id: str
    description: str
    evidence_types: tuple[str, ...] = ()
    required: bool = True


@dataclass(frozen=True)
class OutputStatus:
    output_id: str
    status: Literal["fulfilled", "gap", "missing"]
    evidence_ids: tuple[str, ...] = ()
    gap: str = ""


class ResearchContractError(ValueError):
    """任务契约不满足 schema 或能力白名单。"""


@dataclass(frozen=True)
class ResearchTaskContract:
    task_id: str
    question: str
    subject: str | None
    subject_kind: str | None
    question_type: str
    required_outputs: tuple[RequiredOutput, ...]
    allowed_capabilities: tuple[str, ...]
    research_tier: str = "standard"
    presentation_profile: str = "general"
    freshness: str = "current"
    timeframe: str | None = None
    evidence_plan: EvidencePlan = field(default_factory=EvidencePlan)
    contract_version: str = "1"
    task_frame_hash: str = ""

    def __post_init__(self) -> None:
        # Backwards compatibility for callers that expand ``to_dict()`` into
        # the constructor (older tests/integrations predate EvidencePlan).
        if isinstance(self.evidence_plan, dict):
            raw_requirements = self.evidence_plan.get("requirements", ())
            requirements = tuple(
                EvidenceRequirement(
                    provider_name=str(item.get("provider_name") or ""),
                    capability=str(item.get("capability") or ""),
                    mandatory=bool(item.get("mandatory", False)),
                    freshness=str(item.get("freshness") or "current"),
                    reason=str(item.get("reason") or ""),
                )
                for item in raw_requirements
                if isinstance(item, dict)
            )
            object.__setattr__(
                self,
                "evidence_plan",
                EvidencePlan(
                    profile=str(self.evidence_plan.get("profile") or "general"),
                    requirements=requirements,
                    freshness=str(self.evidence_plan.get("freshness") or "current"),
                ),
            )
        if not self.task_id.strip() or not self.question.strip():
            raise ResearchContractError("task_id/question 不能为空")
        if self.research_tier not in {"quick", "standard", "deep"}:
            raise ResearchContractError(f"未知研究档位：{self.research_tier}")
        if any(not item.output_id.strip() for item in self.required_outputs):
            raise ResearchContractError("required output id 不能为空")
        for requirement in self.evidence_plan.requirements:
            if not requirement.provider_name.strip() or not requirement.capability.strip():
                raise ResearchContractError("evidence plan requirement 必须声明 provider/capability")
        mandatory = set(self.evidence_plan.mandatory_capabilities)
        if not mandatory.issubset(set(self.allowed_capabilities)):
            raise ResearchContractError(
                "evidence plan 的 mandatory capability 未被 allowed_capabilities 授权"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "question": self.question,
            "subject": self.subject,
            "subject_kind": self.subject_kind,
            "question_type": self.question_type,
            "required_outputs": [asdict(item) for item in self.required_outputs],
            "allowed_capabilities": list(self.allowed_capabilities),
            "research_tier": self.research_tier,
            "presentation_profile": self.presentation_profile,
            "freshness": self.freshness,
            "timeframe": self.timeframe,
            "evidence_plan": self.evidence_plan.to_dict(),
            "contract_version": self.contract_version,
            "task_frame_hash": self.task_frame_hash,
        }

    @classmethod
    def from_dict(cls, value: object) -> "ResearchTaskContract":
        if not isinstance(value, dict):
            raise ResearchContractError("任务契约必须是 object")
        raw_outputs = value.get("required_outputs")
        if not isinstance(raw_outputs, (list, tuple)):
            raise ResearchContractError("required_outputs 必须是 list")
        outputs: list[RequiredOutput] = []
        for raw in raw_outputs:
            if not isinstance(raw, dict):
                raise ResearchContractError("required output 必须是 object")
            evidence_types = raw.get("evidence_types", ())
            if not isinstance(evidence_types, (list, tuple)):
                raise ResearchContractError("evidence_types 必须是 list")
            outputs.append(
                RequiredOutput(
                    output_id=str(raw.get("output_id") or ""),
                    description=str(raw.get("description") or ""),
                    evidence_types=tuple(str(item) for item in evidence_types),
                    required=bool(raw.get("required", True)),
                )
            )
        capabilities = value.get("allowed_capabilities", ())
        if not isinstance(capabilities, (list, tuple)):
            raise ResearchContractError("allowed_capabilities 必须是 list")
        raw_plan = value.get("evidence_plan")
        if raw_plan is None:
            evidence_plan = EvidencePlan()
        elif isinstance(raw_plan, dict):
            raw_requirements = raw_plan.get("requirements", ())
            if not isinstance(raw_requirements, (list, tuple)):
                raise ResearchContractError("evidence_plan.requirements 必须是 list")
            requirements = tuple(
                EvidenceRequirement(
                    provider_name=str(item.get("provider_name") or ""),
                    capability=str(item.get("capability") or ""),
                    mandatory=bool(item.get("mandatory", False)),
                    freshness=str(item.get("freshness") or "current"),
                    reason=str(item.get("reason") or ""),
                )
                for item in raw_requirements
                if isinstance(item, dict)
            )
            evidence_plan = EvidencePlan(
                profile=str(raw_plan.get("profile") or "general"),
                requirements=requirements,
                freshness=str(raw_plan.get("freshness") or "current"),
            )
        else:
            raise ResearchContractError("evidence_plan 必须是 object")
        return cls(
            task_id=str(value.get("task_id") or ""),
            question=str(value.get("question") or ""),
            subject=(
                str(value["subject"]) if value.get("subject") is not None else None
            ),
            subject_kind=(
                str(value["subject_kind"])
                if value.get("subject_kind") is not None
                else None
            ),
            question_type=str(value.get("question_type") or "general_finance_qa"),
            required_outputs=tuple(outputs),
            allowed_capabilities=tuple(str(item) for item in capabilities),
            research_tier=str(value.get("research_tier") or "standard"),
            presentation_profile=str(value.get("presentation_profile") or "general"),
            freshness=str(value.get("freshness") or "current"),
            timeframe=(
                str(value["timeframe"]) if value.get("timeframe") is not None else None
            ),
            evidence_plan=evidence_plan,
            contract_version=str(value.get("contract_version") or "1"),
            task_frame_hash=str(value.get("task_frame_hash") or ""),
        )


@dataclass(frozen=True)
class ResearchRunContext:
    contract: ResearchTaskContract
    deadline: ResearchDeadline
    policy: ResearchPolicy
    trace_parent_id: str
    # Prompt context only: never treated as evidence. Appending defaults keeps
    # positional construction in older integrations backwards compatible.
    today: str | None = None
    latest_data_date: str | None = None


@dataclass(frozen=True)
class EvidenceAtom:
    atom_id: str
    claim_text: str
    entity_id: str | None
    metric: str | None
    value: str | int | float | None
    unit: str | None
    period: str | None
    evidence_tier: str
    source_id: str
    source_date: str | None
    provenance: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: object) -> EvidenceAtom | None:
        if not isinstance(value, dict):
            return None
        try:
            return cls(
                atom_id=str(value["atom_id"]),
                claim_text=str(value["claim_text"]),
                entity_id=(
                    str(value["entity_id"])
                    if value.get("entity_id") is not None
                    else None
                ),
                metric=(
                    str(value["metric"])
                    if value.get("metric") is not None
                    else None
                ),
                value=value.get("value"),
                unit=(
                    str(value["unit"])
                    if value.get("unit") is not None
                    else None
                ),
                period=(
                    str(value["period"])
                    if value.get("period") is not None
                    else None
                ),
                evidence_tier=str(value["evidence_tier"]),
                source_id=str(value["source_id"]),
                source_date=(
                    str(value["source_date"])
                    if value.get("source_date") is not None
                    else None
                ),
                provenance=(
                    dict(value["provenance"])
                    if isinstance(value.get("provenance"), dict)
                    else {}
                ),
            )
        except KeyError:
            return None


@dataclass(frozen=True)
class StructuredClaim:
    claim_id: str
    claim: str
    evidence_atom_ids: tuple[str, ...]
    claim_type: ClaimType

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class StageArtifact:
    stage: str
    status: StageStatus
    elapsed_ms: int
    producer: str = ""
    input_hash: str = ""
    artifact_type: str = ""
    required_output: bool = False
    timeout_seconds: float = 0.0
    on_failure: str = ""
    evidence_atom_ids: tuple[str, ...] = ()
    payload: dict[str, object] = field(default_factory=dict)
    degrade_reason: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: object) -> StageArtifact | None:
        if not isinstance(value, dict):
            return None
        try:
            status = str(value["status"])
            if status not in {
                "pending",
                "completed",
                "partial",
                "timeout",
                "failed",
                "skipped",
            }:
                return None
            evidence_atom_ids = value.get("evidence_atom_ids", ())
            if not isinstance(evidence_atom_ids, (list, tuple)):
                return None
            return cls(
                stage=str(value["stage"]),
                status=cast(StageStatus, status),
                elapsed_ms=int(value.get("elapsed_ms") or 0),
                producer=str(value.get("producer") or ""),
                input_hash=str(value.get("input_hash") or ""),
                artifact_type=str(value.get("artifact_type") or ""),
                required_output=bool(value.get("required_output")),
                timeout_seconds=float(value.get("timeout_seconds") or 0.0),
                on_failure=str(value.get("on_failure") or ""),
                evidence_atom_ids=tuple(
                    str(item) for item in evidence_atom_ids if str(item)
                ),
                payload=(
                    dict(value["payload"])
                    if isinstance(value.get("payload"), dict)
                    else {}
                ),
                degrade_reason=(
                    str(value["degrade_reason"])
                    if value.get("degrade_reason") is not None
                    else None
                ),
            )
        except (KeyError, TypeError, ValueError):
            return None


def is_follow_up(query: str) -> bool:
    cleaned = query.strip()
    return bool(
        classify_reference(cleaned) != "none"
        or _COMPARISON_PATTERN.search(cleaned)
    )


def is_contextual_follow_up(
    query: str,
    envelope: QueryEnvelope,
    previous_intent: TurnIntent | None,
    *,
    resolution: QueryResolution | None = None,
) -> bool:
    if previous_intent is None:
        return False
    cleaned = query.strip()
    if is_follow_up(cleaned) or (
        resolution is not None and resolution.context_dependent
    ):
        return True
    if (
        not cleaned
        or len(cleaned) > 80
        or _EXPLICIT_SWITCH_PATTERN.search(cleaned)
        or not _CONTEXT_DEPENDENT_RESEARCH_PATTERN.search(cleaned)
    ):
        return False
    return (
        envelope.subject is None
        or envelope.subject == previous_intent.primary_subject
        or bool(_CONTEXT_DEPENDENT_RESEARCH_PREFIX_PATTERN.search(cleaned))
    )


def answer_owner_for_question_type(question_type: str) -> AnswerOwner | None:
    return QUESTION_OWNER_SKILLS.get(question_type)


def build_turn_intent(
    query: str,
    envelope: QueryEnvelope,
    *,
    previous_intent: TurnIntent | None = None,
    previous_turn_id: str | None = None,
    resolution: QueryResolution | None = None,
    task_frame: TaskFrame | None = None,
) -> TurnIntent:
    cleaned = query.strip()
    follow_up = is_contextual_follow_up(
        cleaned,
        envelope,
        previous_intent,
        resolution=resolution,
    )
    explicit_task_type = _explicit_task_type(cleaned)
    explicit_task_switch = (
        explicit_task_type is not None
        and previous_intent is not None
        and explicit_task_type != previous_intent.question_type
    )
    explicit_subject_switch = bool(
        previous_intent is not None
        and envelope.subject
        and envelope.subject != previous_intent.primary_subject
        and _EXPLICIT_SWITCH_PATTERN.search(cleaned)
    )
    comparison_entities: tuple[str, ...] = ()
    if (
        previous_intent is not None
        and envelope.subject
        and envelope.subject != previous_intent.primary_subject
        and _COMPARISON_PATTERN.search(cleaned)
    ):
        comparison_entities = (envelope.subject,)

    if (
        follow_up
        and explicit_task_switch
        and previous_intent is not None
        and not explicit_subject_switch
    ):
        question_type = explicit_task_type or envelope.question_type
        return TurnIntent(
            primary_subject=previous_intent.primary_subject,
            secondary_topics=previous_intent.secondary_topics,
            question_type=question_type,
            answer_owner=answer_owner_for_question_type(question_type),
            comparison_entities=previous_intent.comparison_entities,
            inherited_from_turn=previous_turn_id,
            evidence_atom_ids=previous_intent.evidence_atom_ids,
            skill_ids=previous_intent.skill_ids,
            stage_artifact_ids=previous_intent.stage_artifact_ids,
            time_horizon=envelope.time_horizon,
            timeframe=envelope.timeframe,
            operators=envelope.operators,
            required_outputs=envelope.required_outputs,
            task_frame_hash=(
                task_frame.task_frame_hash if task_frame is not None else ""
            ),
        )

    inherit = follow_up and not explicit_task_switch and not explicit_subject_switch
    if inherit and previous_intent is not None:
        return TurnIntent(
            primary_subject=previous_intent.primary_subject,
            secondary_topics=_merge_topics(
                previous_intent.secondary_topics,
                _secondary_topics(envelope, previous_intent.primary_subject),
            ),
            question_type=previous_intent.question_type,
            answer_owner=previous_intent.answer_owner,
            comparison_entities=_merge_topics(
                previous_intent.comparison_entities,
                comparison_entities,
            ),
            inherited_from_turn=previous_turn_id,
            evidence_atom_ids=previous_intent.evidence_atom_ids,
            skill_ids=previous_intent.skill_ids,
            stage_artifact_ids=previous_intent.stage_artifact_ids,
            time_horizon=(
                envelope.time_horizon
                if envelope.time_horizon != "unspecified"
                else previous_intent.time_horizon
            ),
            timeframe=(
                envelope.timeframe
                if envelope.timeframe is not None
                else previous_intent.timeframe
            ),
            operators=_merge_topics(
                previous_intent.operators,
                envelope.operators,
            ),
            required_outputs=_merge_topics(
                previous_intent.required_outputs,
                envelope.required_outputs,
            ),
            task_frame_hash=(
                task_frame.task_frame_hash if task_frame is not None else ""
            ),
        )

    question_type = (
        task_frame.question_type if task_frame is not None else envelope.question_type
    )
    return TurnIntent(
        primary_subject=(
            task_frame.subject if task_frame is not None else envelope.subject
        ),
        secondary_topics=_secondary_topics(
            envelope,
            task_frame.subject if task_frame is not None else envelope.subject,
        ),
        question_type=question_type,
        answer_owner=answer_owner_for_question_type(question_type),
        comparison_entities=comparison_entities,
        inherited_from_turn=None,
        time_horizon=envelope.time_horizon,
        timeframe=(
            task_frame.timeframe if task_frame is not None else envelope.timeframe
        ),
        operators=envelope.operators,
        required_outputs=(
            task_frame.required_outputs
            if task_frame is not None
            else envelope.required_outputs
        ),
        task_frame_hash=(
            task_frame.task_frame_hash if task_frame is not None else ""
        ),
    )


def contextualize_intent_query(query: str, intent: TurnIntent) -> str:
    cleaned = query.strip()
    if intent.inherited_from_turn is None or not intent.primary_subject:
        return cleaned
    comparison = (
        "；比较对象：" + "、".join(intent.comparison_entities)
        if intent.comparison_entities
        else ""
    )
    return f"主体：{intent.primary_subject}{comparison}\n追问：{cleaned}"


def _explicit_task_type(query: str) -> str | None:
    for question_type, pattern in _TASK_SWITCH_PATTERNS.items():
        if pattern.search(query):
            return question_type
    return None


def _secondary_topics(
    envelope: QueryEnvelope,
    primary_subject: str | None,
) -> tuple[str, ...]:
    if envelope.subject and envelope.subject != primary_subject:
        return (envelope.subject,)
    return ()


def _merge_topics(*groups: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(item for group in groups for item in group if item))
