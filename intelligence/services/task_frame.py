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

from intelligence.services.trading_calendar import question_non_trading_note
from intelligence.services.user_task import UserTask
from intelligence.services.historical_research.intent import (
    HistoryIntent,
    infer_history_intent,
    named_wave_subject,
)

if TYPE_CHECKING:
    from intelligence.services.query_understanding import QueryEnvelope


LLMComplete = Callable[
    [list[dict[str, str]]], tuple[str | None, object | None, str]
]

_POLICY_BY_QUESTION_TYPE: dict[str, str] = {
    "concept_definition": "stable_knowledge",
    "methodology_discussion": "model_reasoning",
    "market_watch": "current_a_share_market",
    # 政策名必须与 market_watch 不同：_QUESTION_TYPE_BY_POLICY 是反查表，
    # 同名政策会让后注册的题型静默顶掉先注册的。
    "watchlist_digest": "user_watchlist_digest",
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
    "disclosure_scan": "official_disclosure_scan",
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
_COMPARATIVE_DECISION_RE = re.compile(
    r"(?:和|与).{0,32}(?:哪个|哪一个|谁).{0,20}(?:更|优先|胜出|主线)"
)
_COUNTERFACTUAL_ASSESSMENT_RE = re.compile(
    r"^(?:如果|若|假设).{0,80}(?:还能|是否|能否).{0,16}(?:算|成立|确认|持续)"
)
_DECISION_METHOD_RE = re.compile(
    r"(?:应该|应当|该|如何|怎么).{0,20}(?:判断|区分|识别).{0,32}"
    r"(?:候选|噪音|有效|真假|主线)"
)
_INVALIDATION_FOLLOWUP_RE = re.compile(
    r"(?:什么时候|何时|哪些条件|什么条件).{0,16}(?:失效|证伪|不成立|作废)"
)


@dataclass(frozen=True)
class TaskFrame:
    raw_question: str
    user_goal: str
    question_type: str
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
    history_intent: HistoryIntent | None = None

    @property
    def task_frame_hash(self) -> str:
        payload = asdict(self)
        if self.history_intent is None:
            payload.pop("history_intent")  # Keep legacy frame identities stable.
        encoded = json.dumps(
            payload,
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

    def to_user_task(
        self,
        context: dict[str, object] | str | None = None,
    ) -> UserTask:
        """Expose the migration projection without making TaskFrame a route owner."""
        return UserTask.from_task_frame(self, context)

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
            evidence_policy = str(value["evidence_policy"])
            raw_question_type = value.get("question_type")
            question_type = (
                raw_question_type.strip()
                if isinstance(raw_question_type, str) and raw_question_type.strip()
                else _legacy_question_type(
                    evidence_policy,
                    tuple(required_outputs),
                )
            )
            if any(
                item is not None and not isinstance(item, str)
                for item in (subject, timeframe, clarification)
            ):
                return None
            return cls(
                raw_question=str(value["raw_question"]),
                user_goal=str(value["user_goal"]),
                question_type=question_type,
                subject=subject,
                subject_kind=str(value["subject_kind"]),
                market_scope=str(value["market_scope"]),
                timeframe=timeframe,
                required_outputs=tuple(required_outputs),
                assumptions=tuple(assumptions),
                ambiguities=tuple(ambiguities),
                clarification_question=clarification,
                evidence_policy=evidence_policy,
                confidence=max(0.0, min(1.0, float(value["confidence"]))),
                history_intent=HistoryIntent.from_dict(value.get("history_intent")),
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
    history_intent = infer_history_intent(question)
    if history_intent is not None and history_intent.purpose == "historical_comparison":
        question_type = "comparison_analog"
    elif history_intent is not None and question_type not in {
        "theme_analysis",
        "comparison_analog",
        "stock_deep_dive",
    }:
        question_type = "theme_analysis"
    market_scope, market_is_default = _market_scope(question)
    timeframe, timeframe_assumption = _timeframe(envelope.timeframe)
    subject = _safe_subject(
        envelope.subject,
        question,
        resolver_confirmed=envelope.matched_by
        in {"ticker", "entity", "candidate", "alias"},
    )
    subject_kind = str(envelope.subject_kind or "unknown")
    if history_intent is not None and subject is None:
        subject = named_wave_subject(question)
        if subject is not None:
            subject_kind = "theme"
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
    # 确定性日历事实（R15-C1/C2）：问题里的日期是周末/公告休市日时，把
    # 「该日休市、无行情数据」注入假设——它随 episode input 到达模型，
    # 模型据此直接回答，而不是烧完检索窗后答「证据不足」。
    if _is_financial_task(question_type, question):
        calendar_note = question_non_trading_note(question)
        if calendar_note is not None:
            assumptions.append(calendar_note)
    if subject is None and inherited_subject:
        subject = _safe_subject(inherited_subject, question)
    if (
        subject is None
        and not unbound_rebound_reference
        and question_type
        in {
            "market_forecast",
            "market_cause",
            "market_technical",
        }
    ):
        subject = "A股市场" if market_scope == "A股" else f"{market_scope}市场"
        subject_kind = "market_pattern"

    outputs = derive_required_outputs(
        question_type,
        question,
        extra=tuple(str(item) for item in envelope.required_outputs),
    )
    if history_intent is not None:
        outputs = ("direct_assessment", "counterpoint", "evidence_boundary")
    ambiguities = (
        ("“这个反弹”缺少可唯一绑定的主体，可能改变工具和结论",)
        if unbound_rebound_reference
        else ()
    )
    if history_intent is not None and history_intent.window_error:
        ambiguities = (*ambiguities, history_intent.window_error)
    frame = TaskFrame(
        raw_question=question,
        user_goal=_user_goal(question_type, question, envelope.decision_goal),
        question_type=question_type,
        subject=subject,
        subject_kind=subject_kind,
        market_scope=market_scope,
        timeframe=timeframe,
        required_outputs=outputs,
        assumptions=tuple(assumptions),
        ambiguities=ambiguities,
        clarification_question=(history_intent.window_error if history_intent and history_intent.window_error else _clarification_for(ambiguities)),
        evidence_policy=_POLICY_BY_QUESTION_TYPE.get(
            question_type,
            _POLICY_BY_QUESTION_TYPE["general_finance_qa"],
        ),
        confidence=max(0.0, min(1.0, float(envelope.confidence))),
        history_intent=history_intent,
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

    if frame.history_intent is not None:
        question_type = (
            frame.question_type
            if frame.question_type
            in {"theme_analysis", "comparison_analog", "stock_deep_dive"}
            else "theme_analysis"
        )
        required_outputs = frame.required_outputs

    explicit_outputs = _explicit_required_outputs(frame.raw_question)
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
    # Same filter as ``derive_required_outputs``: this is the second producer of
    # ``frame.required_outputs``, and a blank id surviving only on the
    # inheritance path would score one answer against two different coverage
    # denominators depending on which path built the frame.
    merged_outputs = (
        explicit_outputs
        if explicit_outputs
        else _clean_outputs(
            inherited_outputs,
            canonical_outputs,
            required_outputs,
        )
    )
    return replace(
        frame,
        question_type=question_type,
        subject=_safe_subject(subject, frame.raw_question),
        subject_kind=subject_kind or frame.subject_kind,
        timeframe=timeframe if timeframe is not None else frame.timeframe,
        required_outputs=merged_outputs,
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
    if frame.history_intent is not None and frame.history_intent.window_error:
        resolved = infer_history_intent("历史行情复盘，只研究" + cleaned)
        if resolved and resolved.requested_start and resolved.requested_end and not resolved.window_error:
            resolved = replace(resolved, purpose=frame.history_intent.purpose,
                               strict_window=frame.history_intent.strict_window)
            return replace(frame, history_intent=resolved, ambiguities=(), clarification_question=None,
                           assumptions=_merge_strings(frame.assumptions, ("用户澄清历史窗口为" + resolved.requested_start + "至" + resolved.requested_end,)))
        return frame  # Unresolved explicit bounds must never turn into unbounded permission.
    if is_missing_material_clarification(frame):
        # 追问的是「材料在哪」，回答是贴进来的材料本身：它不是主体名，不能走下面的
        # 主体/市场归一（一段研报正文会被 _safe_subject 判掉、再默认成「A股市场 /
        # market_pattern」，把提纯题改写成盘面题）。主体、类型一律保留，材料由对话
        # 上下文带进研究轮。
        assumption = (
            f"用户在唯一一次澄清中补充了材料原文（约 {len(cleaned)} 字）"
            if cleaned
            else "澄清预算已用尽，用户未提供材料，按无材料继续"
        )
        return replace(
            frame,
            assumptions=_merge_strings(frame.assumptions, (assumption,)),
            ambiguities=(),
            clarification_question=None,
        )
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


# 「要处理的材料不在对话里」这一类歧义。2026-09-04 B6（「把这份卖方材料提纯一下」，
# 题面没附材料）：对齐模型写出了 "'这份卖方材料'所指文档完全缺失，需用户提供原文或
# 粘贴内容"，但下面那两条只认「主体/市场…不明/冲突/改变」的正则认不出它，
# clarification_question 落成 None，题进了研究车道；模型稿老老实实写了「材料缺失、
# 请提供原文」，结构校验却因两个 required_outputs 都 gap 而不放行，发布层换成
# 「证据不足，暂不能可靠回答」模板——用户根本不知道自己忘了贴附件。认不出来就放行
# 是 fail open；这里把「材料缺失」补成会拦下的形状。
_MISSING_MATERIAL_NOUN_RE = re.compile(
    r"(?:材料|文档|原文|附件|文件|研报|纪要|公告|链接|正文|截图|表格|数据文件)"
)
_MISSING_MATERIAL_STATE_RE = re.compile(
    r"(?:缺失|未附|未提供|未给出|未上传|没有提供|没有附|不存在|"
    r"需(?:要)?(?:用户)?(?:提供|粘贴|上传|补充)|请(?:用户)?(?:提供|粘贴|上传|补充))"
)
# 模型自己已经给了默认处置的歧义（「…未提供，先按 X 处理」）不拦：那是 assumption
# 写错了栏，不是阻塞。只有「缺 + 没有默认处置」才追问。
_SELF_RESOLVED_RE = re.compile(r"(?:先按|暂按|默认按|默认|假定|假设|按.{0,12}(?:处理|执行|继续))")

MISSING_MATERIAL_CLARIFICATION = (
    "这题要处理的材料（原文 / 文件 / 链接）我这边没有拿到——"
    "请把内容贴进来或给出来源链接，我再继续。"
)


def _is_missing_material_ambiguity(item: str) -> bool:
    text = str(item or "")
    if not text or _SELF_RESOLVED_RE.search(text):
        return False
    return bool(
        _MISSING_MATERIAL_NOUN_RE.search(text) and _MISSING_MATERIAL_STATE_RE.search(text)
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
        if any(_is_missing_material_ambiguity(item) for item in ambiguities):
            return MISSING_MATERIAL_CLARIFICATION
        return None
    if "市场" in blocking:
        return "你希望我按 A 股、美股，还是其他市场来判断？"
    return "你希望我围绕哪个明确主体继续判断？"


def is_missing_material_clarification(frame: object) -> bool:
    return getattr(frame, "clarification_question", None) == MISSING_MATERIAL_CLARIFICATION


# 周历/周末大事：窗口词 × 日程词。单独「周末发酵了什么新闻」不算，
# 避免把主题发酵题或普通周末新闻收成跨市场日历。
_CALENDAR_WINDOW_MARKERS = ("下周", "本周", "周末", "这周")
_CALENDAR_EVENT_MARKERS = ("大事", "日历", "催化", "事件", "日程", "周历")
_EXPLICIT_A_SHARE_MARKERS = ("a股", "沪市", "深市", "北交所")
_A_SHARE_SEARCH_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9])A股(?![A-Za-z0-9])")


def is_weekly_calendar_question(question: str) -> bool:
    """「下周/周末 + 大事/日历」跨市场周历，不是默认 A 股复盘。"""

    folded = re.sub(r"\s+", "", str(question or ""))
    if not folded:
        return False
    has_window = any(marker in folded for marker in _CALENDAR_WINDOW_MARKERS)
    has_event = any(marker in folded for marker in _CALENDAR_EVENT_MARKERS)
    return has_window and has_event


def question_has_explicit_a_share(question: str) -> bool:
    folded = re.sub(r"\s+", "", str(question or "")).casefold()
    return any(marker in folded for marker in _EXPLICIT_A_SHARE_MARKERS)


def strip_default_a_share_search_token(query: str, question: str) -> tuple[str, str]:
    """周历题且问句未点名 A 股时，去掉检索串里被默认范围塞进的「A股」。

    返回 ``(query, note)``；未改动时 note 为空。显式「下周 A 股大事」不剥。
    """

    raw = str(query or "")
    if not raw or not is_weekly_calendar_question(question):
        return raw, ""
    if question_has_explicit_a_share(question):
        return raw, ""
    cleaned = _A_SHARE_SEARCH_TOKEN_RE.sub(" ", raw)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if cleaned == raw.strip():
        return raw, ""
    return cleaned, "已去掉默认市场词「A股」（问句未指定市场）"


def _market_scope(question: str) -> tuple[str, bool]:
    folded = re.sub(r"\s+", "", question).casefold()
    if any(term in folded for term in ("美股", "美国股市", "纳指", "道指", "标普", "soxx", "qqq")):
        return "美股", False
    if "港股" in folded or "恒生" in folded:
        return "港股", False
    if "全球市场" in folded:
        return "全球", False
    if question_has_explicit_a_share(question):
        return "A股", False
    if is_weekly_calendar_question(question):
        return "跨市场", False
    return "A股", True


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


# 每个 frame 都会有的兜底输出（``general_knowledge`` / ``general_finance_qa``
# 以及所有未映射类型都取这一对），因此它们**不构成**「需要检索」的信号。
_GENERIC_REQUIRED_OUTPUTS = frozenset({"direct_answer", "evidence_boundary"})


def _is_financial_task(question_type: str, question: str) -> bool:
    return question_type not in {
        "concept_definition",
        "methodology_discussion",
        "general_knowledge",
        "general_finance_qa",
    } or bool(
        re.search(
            # 「A股/a股」原先不在表里——而「大盘」在，于是「明天大盘怎么走」
            # 能命中、「你觉得a股明天会怎么走」命不中。这是产品最核心的说法
            # （CLAUDE.md 标题就是「A股量化复盘+研究工具集」）。
            # 港股/美股一并补上，它们同样是这里天天出现的主体。
            # 涨停/跌停/连板/涨家数/成交额（2026-08-13 R15-C2）：「2026-02-17
            # 涨停家数多少」一个财务词都不带地问了最典型的盘面指标——
            # 这些是复盘工作流的一等公民词，缺席让日历事实注入整条落空。
            r"(?:市场|行情|大盘|[Aa]\s*股|港股|美股|股票|个股|题材|板块|"
            r"公司|指数|反弹|产业|趋势|财务|估值|订单|客户|收入|利润|"
            r"涨停|跌停|连板|涨家数|成交额)",
            question,
        )
    )


def task_frame_requires_retrieval(frame: TaskFrame) -> bool:
    """Return whether an execution route may safely omit evidence retrieval."""

    if frame.evidence_policy in {"stable_knowledge", "model_reasoning"}:
        return False
    if frame.evidence_policy == "general_finance_evidence":
        # 先看 frame 自己点名的产出物，再退回关键词匹配。
        #
        # 实测 run_20260731_175959_316535：turn controller 的 LLM 调用失败，
        # question_type 停在默认的 general_finance_qa，于是这里落到关键词分支；
        # 而关键词表里**没有「A股」**（有「大盘」），「你觉得a股明天会怎么走」
        # 判 False → _enforce_task_frame_route 的地板不生效 → 兜底成 chat 车道，
        # 用户拿到「我没办法预测」，整条研究链一次都没跑。
        #
        # 判据其实一直在手边：同一个 frame 的 required_outputs 是
        # ("scenario_tree",)——一个要求产出情景树的问题不可能不需要证据。
        # 只补关键词是 ch28 点名的「打地鼠」：关键词表永远追不上用户的说法，
        # 而 required_outputs 是结构化的，不会因为换个措辞就漏。
        #
        # 注意判的是「**超出**通用默认」而不是「非空」：
        # ``("direct_answer", "evidence_boundary")`` 是 general_knowledge /
        # general_finance_qa 以及所有未映射类型的兜底值，每个 frame 都有——
        # 按非空判会把「给我讲个笑话」也拖进研究车道（既有测试
        # test_retrieval_floor_keeps_plain_chat_without_signals 抓到过）。
        if set(frame.required_outputs) - _GENERIC_REQUIRED_OUTPUTS:
            return True
        # 第三道结构性地板（2026-08-27 D6，run_20260827_184531_798332）：
        # 「2026-07-22 高标股的晋级情况如何，有没有出现空档」——required_outputs
        # 恰好是通用默认（上一格不触发），而「高标股/晋级/空档」全不在下面的
        # 关键词表里。8-13 补了涨停/连板，这次输在新黑话——上面 08-01 注释里
        # 「关键词表永远追不上用户的说法」一语成谶。这次补的不是词：带完整
        # 日历日期的金融题不可能靠模型记忆回答（has_explicit_date 的 docstring
        # 就说它是最强时效信号），timeframe 是 understand_query 抽好的结构化
        # 字段，raw_question 兜底抽取失败的场景。月份粒度（2026年7月）不算。
        if has_explicit_date(frame.timeframe or "") or has_explicit_date(
            frame.raw_question
        ):
            return True
        return _is_financial_task(frame.question_type, frame.raw_question)
    return True


def has_explicit_date(question: str) -> bool:
    """Whether the text carries a literal calendar date such as 2026-08-07.

    Exposed because a written-out date is the strongest freshness signal there
    is, and more than one module needs it.  ``evidence_capabilities`` first
    carried its own copy of this pattern; two regexes that must stay identical
    are a drift waiting to happen, so the pattern lives here alone.
    """

    return _EXPLICIT_DATE_RE.search(str(question or "")) is not None


def last_explicit_iso_date(question: str) -> str | None:
    """Last calendar date in the question, as ``YYYY-MM-DD``.

    ``has_explicit_date`` is a boolean. Coverage and Q1 both need the actual
    day, and they must keep using this same pattern so a written-out 7 月 23
    day cannot drift from a hyphenated ``2026-07-23``.
    """

    matches = tuple(_EXPLICIT_DATE_RE.finditer(str(question or "")))
    if not matches:
        return None
    year, month, day = matches[-1].groups()
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


def _user_goal(question_type: str, question: str, fallback: str) -> str:
    if question_type == "market_forecast" and _REBOUND_HORIZON_RE.search(question):
        return "判断最近一次市场反弹的可持续时间、继续条件与失效条件"
    if _COMPARATIVE_DECISION_RE.search(question):
        return "比较候选方向并给出主线胜出判断、依据、反证与失效条件"
    if _COUNTERFACTUAL_ASSESSMENT_RE.search(question):
        return "判断反事实条件下原结论是否仍成立，并解释因果链与验证条件"
    if _DECISION_METHOD_RE.search(question):
        return "给出可执行的判断方法、证据层级、失败模式与验证路径"
    if _INVALIDATION_FOLLOWUP_RE.search(question):
        return "说明上一判断的可核验失效条件及其证据依据"
    return str(fallback or "形成与用户原问题一致的直接回答").strip()


def derive_required_outputs(
    question_type: str,
    question: str,
    *,
    extra: tuple[str, ...] = (),
) -> tuple[str, ...]:
    """Derive a question's required outputs from type + wording alone.

    Extracted from ``build_task_frame`` so routes that never build a
    ``QueryEnvelope`` can still name the same slots.  ``POST /api/runs``
    (``api/app.py:_run_ask``) is one: it has the question and a resolved
    ``question_type`` but no envelope, so before this it had no way to say what
    the answer owed — and reported ``answer_status`` without checking anything.

    Pure and deterministic: an explicit wording match wins outright, otherwise
    the per-type defaults merge with ``extra``.  Kept as the single source for
    that table so a second caller cannot drift from ``build_task_frame``.

    Blank ``extra`` ids are dropped, which is a deliberate tightening over the
    pre-``03cb32fb`` behaviour (the old inline ``_merge_strings`` only filtered
    falsy values, so a whitespace-only id survived).  Rationale and the shared
    filter live in ``_clean_outputs``; ``rebase_task_frame`` uses the same one so
    the two producers of ``required_outputs`` cannot disagree.
    """

    explicit_outputs = _explicit_required_outputs(question)
    if explicit_outputs:
        return explicit_outputs
    return _clean_outputs(
        _default_required_outputs(question_type, question),
        extra,
    )


def _explicit_required_outputs(question: str) -> tuple[str, ...]:
    if _COMPARATIVE_DECISION_RE.search(question):
        return (
            "comparison_conclusion",
            "supporting_evidence",
            "counterpoint",
            "invalidation_conditions",
        )
    if _COUNTERFACTUAL_ASSESSMENT_RE.search(question):
        return (
            "direct_assessment",
            "causal_chain",
            "counterpoint",
            "verification_conditions",
        )
    if _DECISION_METHOD_RE.search(question):
        return (
            "method",
            "evidence_hierarchy",
            "failure_modes",
            "verification_path",
        )
    if _INVALIDATION_FOLLOWUP_RE.search(question):
        return ("invalidation_conditions", "supporting_evidence")
    return ()


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
        "watchlist_digest": (
            "direct_assessment",
            "supporting_evidence",
            "evidence_boundary",
        ),
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
        "disclosure_scan": ("direct_assessment", "supporting_evidence", "evidence_boundary"),
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


def _clean_outputs(*groups: tuple[str, ...]) -> tuple[str, ...]:
    """Merge output-id groups, dropping blank ids and preserving first-seen order.

    Both producers of ``frame.required_outputs`` route through here so they
    cannot drift apart: ``derive_required_outputs`` on the build path and
    ``rebase_task_frame`` on the multi-turn inheritance path.

    Blank ids are dropped on purpose.  A whitespace-only id cannot serve as a
    slot name when judging marker coverage, so keeping one only inflates the
    coverage denominator by an entry nothing can ever satisfy.  Worse, if only
    one producer dropped it, the same answer would be scored against two
    different denominators depending on which path built the frame — and
    ``03cb32fb`` just lifted that judging into ``services`` for both engines to
    share, so a split producer口径 would undo it.

    Deliberately not folded into ``_merge_strings``: that one also merges
    assumptions and ambiguities, where trimming is a separate contract.
    """

    return _merge_strings(
        tuple(
            str(item)
            for group in groups
            for item in group
            if str(item).strip()
        )
    )


def _legacy_question_type(
    evidence_policy: str,
    required_outputs: tuple[str, ...],
) -> str:
    """Infer old serialized frames that predate the explicit question type."""

    if (
        evidence_policy == "comparable_multi_source_evidence"
        and "limits_of_analogy" in required_outputs
    ):
        return "comparison_analog"
    return _QUESTION_TYPE_BY_POLICY.get(
        evidence_policy,
        "general_finance_qa",
    )
