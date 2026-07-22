"""Canonical, immutable semantics for one user turn.

``TaskFrame`` is deliberately smaller than the execution contract.  It records
what the user asked; lanes, owners, tools and budgets are projections and may
not write semantics back into this object.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, replace
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from intelligence.services.query_understanding import QueryEnvelope


LLMComplete = Callable[
    [list[dict[str, str]]], tuple[str | None, object | None, str]
]

_POLICY_BY_QUESTION_TYPE: dict[str, str] = {
    "concept_definition": "stable_knowledge",
    "methodology_discussion": "model_reasoning",
    "market_watch": "current_a_share_market",
    "dated_market_review": "dated_a_share_market",
    "market_forecast": "current_market_scenarios",
    "market_cause": "time_aligned_market_causal",
    "market_technical": "structured_market_technical",
    "external_market": "current_external_market",
    "stock_deep_dive": "company_multi_layer_evidence",
    "valuation_estimate": "company_valuation_evidence",
    "theme_analysis": "theme_multi_layer_evidence",
    "news_impact": "event_and_official_evidence",
    "financial_analysis": "company_financial_evidence",
    "quick_fact": "current_fact_evidence",
    "theme_track": "theme_tracking_evidence",
    "kol_review": "source_critique_evidence",
    "comparison_analog": "comparable_multi_source_evidence",
    "comparison": "comparable_multi_source_evidence",
    "trade_advice": "conditional_thesis_evidence",
    "event_forecast": "event_scenario_evidence",
    "fact_check": "claim_verification_evidence",
    "general_knowledge": "current_public_knowledge",
    "general_finance_qa": "general_finance_evidence",
}
_QUESTION_TYPE_BY_POLICY = {
    policy: question_type
    for question_type, policy in _POLICY_BY_QUESTION_TYPE.items()
}

_REBOUND_HORIZON_RE = re.compile(
    r"(?:反弹|修复).{0,12}(?:持续多久|能持续|持续性|延续多久|还能延续)"
)
_UNBOUND_REBOUND_REFERENCE_RE = re.compile(
    r"^(?:这个|那个|这次|那次)(?:反弹|修复)"
)
_QUESTION_LIKE_RE = re.compile(
    r"(?:什么|为何|为什么|怎么|如何|多少|多久|是否|能否|会不会|吗|呢|[？?])"
)
_EXPLICIT_DATE_RE = re.compile(
    r"(?<!\d)(20\d{2})(?:年|[-/.])(\d{1,2})(?:月|[-/.])(\d{1,2})日?(?!\d)"
)


@dataclass(frozen=True)
class TaskFrame:
    raw_question: str
    user_goal: str
    subject: str | None
    subject_kind: str
    market_scope: str
    timeframe: str | None
    required_outputs: tuple[str, ...]
    assumptions: tuple[str, ...]
    ambiguities: tuple[str, ...]
    clarification_question: str | None
    evidence_policy: str
    confidence: float

    @property
    def question_type(self) -> str:
        """Compatibility projection; the policy is authored with the frame."""

        if (
            self.evidence_policy == "comparable_multi_source_evidence"
            and "limits_of_analogy" in self.required_outputs
        ):
            return "comparison_analog"
        return _QUESTION_TYPE_BY_POLICY.get(
            self.evidence_policy,
            "general_finance_qa",
        )

    @property
    def task_frame_hash(self) -> str:
        encoded = json.dumps(
            asdict(self),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["required_outputs"] = list(self.required_outputs)
        payload["assumptions"] = list(self.assumptions)
        payload["ambiguities"] = list(self.ambiguities)
        payload["question_type"] = self.question_type
        payload["task_frame_hash"] = self.task_frame_hash
        return payload

    @classmethod
    def from_dict(cls, value: object) -> TaskFrame | None:
        if not isinstance(value, dict):
            return None
        try:
            required_outputs = value.get("required_outputs", ())
            assumptions = value.get("assumptions", ())
            ambiguities = value.get("ambiguities", ())
            if any(
                not isinstance(items, (list, tuple))
                or any(not isinstance(item, str) for item in items)
                for items in (required_outputs, assumptions, ambiguities)
            ):
                return None
            subject = value.get("subject")
            timeframe = value.get("timeframe")
            clarification = value.get("clarification_question")
            if any(
                item is not None and not isinstance(item, str)
                for item in (subject, timeframe, clarification)
            ):
                return None
            return cls(
                raw_question=str(value["raw_question"]),
                user_goal=str(value["user_goal"]),
                subject=subject,
                subject_kind=str(value["subject_kind"]),
                market_scope=str(value["market_scope"]),
                timeframe=timeframe,
                required_outputs=tuple(required_outputs),
                assumptions=tuple(assumptions),
                ambiguities=tuple(ambiguities),
                clarification_question=clarification,
                evidence_policy=str(value["evidence_policy"]),
                confidence=max(0.0, min(1.0, float(value["confidence"]))),
            )
        except (KeyError, TypeError, ValueError):
            return None


def build_task_frame(
    raw_question: str,
    envelope: QueryEnvelope,
    *,
    inherited_subject: str | None = None,
    llm_complete: LLMComplete | None = None,
) -> TaskFrame:
    """Compile rules first, then optionally merge one constrained LLM draft."""

    question = str(raw_question or "").strip()
    question_type = str(envelope.question_type or "general_finance_qa")
    market_scope, market_is_default = _market_scope(question)
    timeframe, timeframe_assumption = _timeframe(envelope.timeframe)
    subject = _safe_subject(
        envelope.subject,
        question,
        resolver_confirmed=envelope.matched_by
        in {"ticker", "entity", "candidate", "alias"},
    )
    subject_kind = str(envelope.subject_kind or "unknown")
    unbound_rebound_reference = bool(
        subject is None
        and not inherited_subject
        and _UNBOUND_REBOUND_REFERENCE_RE.search(question)
    )
    assumptions: list[str] = []
    if (
        market_is_default
        and _is_financial_task(question_type, question)
        and not unbound_rebound_reference
    ):
        assumptions.append("用户未明确市场范围，按A股市场理解")
    if timeframe_assumption:
        assumptions.append(timeframe_assumption)
    if subject is None and inherited_subject:
        subject = _safe_subject(inherited_subject, question)
    if subject is None and not unbound_rebound_reference and question_type in {
        "market_forecast",
        "market_cause",
        "market_technical",
    }:
        subject = "A股市场" if market_scope == "A股" else f"{market_scope}市场"
        subject_kind = "market_pattern"

    outputs = _merge_strings(
        _default_required_outputs(question_type, question),
        tuple(str(item) for item in envelope.required_outputs),
    )
    ambiguities = (
        ("“这个反弹”缺少可唯一绑定的主体，可能改变工具和结论",)
        if unbound_rebound_reference
        else ()
    )
    frame = TaskFrame(
        raw_question=question,
        user_goal=_user_goal(question_type, question, envelope.decision_goal),
        subject=subject,
        subject_kind=subject_kind,
        market_scope=market_scope,
        timeframe=timeframe,
        required_outputs=outputs,
        assumptions=tuple(assumptions),
        ambiguities=ambiguities,
        clarification_question=_clarification_for(ambiguities),
        evidence_policy=_POLICY_BY_QUESTION_TYPE.get(
            question_type,
            _POLICY_BY_QUESTION_TYPE["general_finance_qa"],
        ),
        confidence=max(0.0, min(1.0, float(envelope.confidence))),
    )
    if llm_complete is None:
        return frame
    try:
        content, _provider, _reason = llm_complete(_alignment_messages(frame))
    except Exception:
        return frame
    return align_task_frame(frame, content)


def align_task_frame(frame: TaskFrame, content: str | None) -> TaskFrame:
    """Merge only the three LLM-owned semantic supplements.

    Subject, market, time, evidence policy and confidence remain code-owned.
    Required outputs are also code/owner-contract owned: an alignment model may
    improve the goal or surface assumptions, but cannot enlarge the task gate.
    Malformed/unavailable output therefore leaves the rules-only frame usable.
    """

    if not content:
        return frame
    value = _json_object(content)
    if value is None:
        return frame
    goal = value.get("user_goal")
    assumptions = value.get("assumptions")
    ambiguities = value.get("ambiguities")
    if goal is not None and not isinstance(goal, str):
        goal = None
    valid_assumptions = _string_tuple(assumptions)
    valid_ambiguities = _string_tuple(ambiguities)
    merged_ambiguities = _merge_strings(frame.ambiguities, valid_ambiguities)
    clarification = _clarification_for(merged_ambiguities)
    return replace(
        frame,
        user_goal=(goal.strip() if isinstance(goal, str) and goal.strip() else frame.user_goal),
        assumptions=_merge_strings(frame.assumptions, valid_assumptions),
        ambiguities=merged_ambiguities,
        clarification_question=clarification,
    )


def rebase_task_frame(
    frame: TaskFrame,
    *,
    question_type: str,
    subject: str | None,
    subject_kind: str | None = None,
    timeframe: str | None = None,
    required_outputs: tuple[str, ...] = (),
) -> TaskFrame:
    """Apply validated conversation inheritance before downstream projection."""

    question_type_changed = question_type != frame.question_type
    canonical_outputs = (
        _default_required_outputs(question_type, frame.raw_question)
        if question_type_changed
        else ()
    )
    inherited_outputs = (
        tuple(
            item
            for item in frame.required_outputs
            if item
            not in _default_required_outputs(frame.question_type, frame.raw_question)
        )
        if question_type_changed
        else frame.required_outputs
    )
    return replace(
        frame,
        subject=_safe_subject(subject, frame.raw_question),
        subject_kind=subject_kind or frame.subject_kind,
        timeframe=timeframe if timeframe is not None else frame.timeframe,
        required_outputs=_merge_strings(
            inherited_outputs,
            canonical_outputs,
            required_outputs,
        ),
        evidence_policy=_POLICY_BY_QUESTION_TYPE.get(
            question_type,
            _POLICY_BY_QUESTION_TYPE["general_finance_qa"],
        ),
    )


def resolve_task_frame_clarification(
    frame: TaskFrame,
    answer: str,
) -> TaskFrame:
    """Merge one clarification answer into the pending frame, then continue.

    The online budget is one blocking round.  Even an unrecognised answer
    therefore resolves to the safest product default instead of starting a
    second interview loop.
    """

    cleaned = re.sub(r"\s+", "", str(answer or ""))
    if any(term in cleaned for term in ("美股", "美国股市", "纳指", "标普")):
        market_scope = "美股"
        subject = "美国股市"
    elif any(term in cleaned for term in ("港股", "恒生")):
        market_scope = "港股"
        subject = "港股市场"
    elif any(term in cleaned for term in ("A股", "a股", "大盘", "市场")):
        market_scope = "A股"
        subject = "A股市场"
    else:
        candidate = re.sub(
            r"^(?:这个|那个|这次|那次)?(?:反弹|修复)?(?:指的是|指的|指|是)?",
            "",
            str(answer or "").strip(),
        )
        subject = _safe_subject(candidate, frame.raw_question)
        market_scope = frame.market_scope
        if subject is None:
            subject = "A股市场"
            market_scope = "A股"
    assumption = (
        f"用户在唯一一次澄清中确认主体为{subject}"
        if cleaned
        else f"澄清预算已用尽，按安全默认主体{subject}继续"
    )
    return replace(
        frame,
        subject=subject,
        subject_kind="market_pattern",
        market_scope=market_scope,
        assumptions=_merge_strings(frame.assumptions, (assumption,)),
        ambiguities=(),
        clarification_question=None,
    )


def _alignment_messages(frame: TaskFrame) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "你只补全任务语义，不回答问题。规则已锁定主体、市场、日期、"
                "任务类型、required_outputs 和证据政策；不得修改这些字段。"
                "严格输出 JSON，键只能是 user_goal,assumptions,ambiguities。"
                "只有会改变主体、工具或结论的歧义才写入 ambiguities。"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(frame.to_dict(), ensure_ascii=False),
        },
    ]


def _json_object(content: str) -> dict[str, object] | None:
    text = content.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fence is not None:
        text = fence.group(1)
    elif not text.startswith("{"):
        braces = re.search(r"\{.*\}", text, re.DOTALL)
        if braces is not None:
            text = braces.group(0)
    try:
        value = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    return value if isinstance(value, dict) else None


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(
        text
        for item in value
        if isinstance(item, str) and (text := item.strip())
    )


def _clarification_for(ambiguities: tuple[str, ...]) -> str | None:
    blocking = next(
        (
            item
            for item in ambiguities
            if re.search(r"(?:主体|市场|数据源|工具|结论|对象).*(?:不明|冲突|改变|可能)", item)
            or re.search(r"(?:不明|冲突|改变).*(?:主体|市场|数据源|工具|结论|对象)", item)
        ),
        None,
    )
    if blocking is None:
        return None
    if "市场" in blocking:
        return "你希望我按 A 股、美股，还是其他市场来判断？"
    return "你希望我围绕哪个明确主体继续判断？"


def _market_scope(question: str) -> tuple[str, bool]:
    folded = re.sub(r"\s+", "", question).casefold()
    if any(term in folded for term in ("美股", "美国股市", "纳指", "道指", "标普", "soxx", "qqq")):
        return "美股", False
    if "港股" in folded or "恒生" in folded:
        return "港股", False
    if "全球市场" in folded:
        return "全球", False
    return "A股", not any(term in folded for term in ("a股", "沪市", "深市", "北交所"))


def _timeframe(raw_timeframe: str | None) -> tuple[str | None, str | None]:
    if raw_timeframe is None:
        return None, None
    raw = str(raw_timeframe).strip()
    if raw in {"昨天", "昨日"}:
        return (
            "最近交易日",
            f"“{raw}”按最近一个有数据的交易日解释，具体日期以后续证据日期为准",
        )
    if raw in {"今天", "今日", "最新"}:
        return (
            "最新可用交易日",
            f"“{raw}”按最新可用市场数据日解释，不以系统自然日冒充交易日",
        )
    if raw == "隔夜":
        return "最近一个完整外盘交易日", "“隔夜”按最近一个完整外盘交易日解释"
    if raw in {"本周", "这一周", "这周", "近一周", "过去一周", "一周内"}:
        return raw, f"“{raw}”按最新可用证据覆盖的交易周解释"
    match = _EXPLICIT_DATE_RE.fullmatch(raw)
    if match is not None:
        return f"{int(match.group(1)):04d}-{int(match.group(2)):02d}-{int(match.group(3)):02d}", None
    return raw, None


def _safe_subject(
    subject: object,
    raw_question: str,
    *,
    resolver_confirmed: bool = False,
) -> str | None:
    if not isinstance(subject, str):
        return None
    cleaned = subject.strip(" \t\r\n，,。！？!?：:")
    if (
        not cleaned
        or (cleaned == raw_question.strip() and not resolver_confirmed)
        or len(cleaned) > 32
        or (len(cleaned) > 12 and _QUESTION_LIKE_RE.search(cleaned))
    ):
        return None
    return cleaned


def _is_financial_task(question_type: str, question: str) -> bool:
    return question_type not in {
        "concept_definition",
        "methodology_discussion",
        "general_knowledge",
        "general_finance_qa",
    } or bool(
        re.search(
            r"(?:市场|行情|大盘|股票|个股|题材|板块|公司|指数|反弹|"
            r"产业|趋势|财务|估值|订单|客户|收入|利润)",
            question,
        )
    )


def task_frame_requires_retrieval(frame: TaskFrame) -> bool:
    """Return whether an execution route may safely omit evidence retrieval."""

    if frame.evidence_policy in {"stable_knowledge", "model_reasoning"}:
        return False
    if frame.evidence_policy == "general_finance_evidence":
        return _is_financial_task(frame.question_type, frame.raw_question)
    return True


def _user_goal(question_type: str, question: str, fallback: str) -> str:
    if question_type == "market_forecast" and _REBOUND_HORIZON_RE.search(question):
        return "判断最近一次市场反弹的可持续时间、继续条件与失效条件"
    return str(fallback or "形成与用户原问题一致的直接回答").strip()


def _default_required_outputs(question_type: str, question: str) -> tuple[str, ...]:
    if question_type == "market_forecast" and _REBOUND_HORIZON_RE.search(question):
        return (
            "current_baseline",
            "duration_assessment",
            "continuation_conditions",
            "invalidation_conditions",
            "evidence_boundary",
        )
    defaults: dict[str, tuple[str, ...]] = {
        "concept_definition": ("direct_definition", "evidence_boundary"),
        "methodology_discussion": ("direct_explanation", "tradeoffs"),
        "market_watch": ("direct_assessment", "supporting_evidence", "risk_signals"),
        "dated_market_review": ("market_summary", "mainline_structure", "risk_signals"),
        "market_forecast": (
            "direct_assessment",
            "scenario_paths",
            "continuation_conditions",
            "invalidation_conditions",
            "evidence_boundary",
        ),
        "market_cause": ("direct_assessment", "causal_chain", "counterpoint", "evidence_boundary"),
        "market_technical": ("technical_levels", "invalidation_conditions", "data_date"),
        "external_market": ("market_summary", "data_date", "evidence_boundary"),
        "comparison": ("comparison_dimensions", "key_differences", "evidence_boundary"),
        "event_forecast": ("scenario_paths", "transmission_chain", "invalidation_conditions"),
        "fact_check": ("direct_assessment", "supporting_evidence", "evidence_boundary"),
        "stock_deep_dive": ("direct_assessment", "supporting_evidence", "counterpoint"),
        "valuation_estimate": ("valuation_assessment", "scenario_range", "evidence_boundary"),
        "theme_analysis": ("direct_assessment", "chain_mapping", "counterpoint"),
        "news_impact": ("event_facts", "impact_transmission", "counterpoint"),
        "financial_analysis": ("financial_assessment", "metric_evidence", "counterpoint"),
        "quick_fact": ("fact_value", "as_of_date", "evidence_boundary"),
        "theme_track": (
            "change_summary",
            "supporting_evidence",
            "tracking_signals",
            "evidence_boundary",
        ),
        "kol_review": (
            "claim_summary",
            "evidence_assessment",
            "biases_and_gaps",
            "counterpoint",
        ),
        "comparison_analog": (
            "comparison_dimensions",
            "analog_similarities",
            "key_differences",
            "limits_of_analogy",
            "evidence_boundary",
        ),
        "trade_advice": (
            "conditional_thesis",
            "supporting_evidence",
            "risk_signals",
            "invalidation_conditions",
            "evidence_boundary",
        ),
        "general_knowledge": ("direct_answer", "evidence_boundary"),
        "general_finance_qa": ("direct_answer", "evidence_boundary"),
    }
    return defaults.get(question_type, ("direct_answer", "evidence_boundary"))


def _merge_strings(*groups: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(item for group in groups for item in group if item))
