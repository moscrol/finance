"""Semantic grounding gate for one continuous research episode.

``episode_verifier`` proves only the structural part of an episode: every
required output has a valid evidence binding.  This module is the deliberately
separate semantic gate.  It gives a private, numbered evidence registry to a
    strict JSON judge, permits bounded deletion-only repairs, and projects only
    a safe answer to the public boundary.

The module is provider-neutral.  Tests and canary callers can inject a small
``judge_fn``/primary model; production can use the independent provider chosen
by :func:`llm_refine.judge_provider`.  No NLI model or second retrieval path is
introduced here: a semantic judge may reject or narrow an answer, never add
evidence.  Mixed/blocked structural partials stay partial.  An honest runtime
partial whose contracted slots are already fulfilled (the 2026-08-19
deadline_exhausted shape) may be reported completed after a judge pass.
Optional numeric-claim
recheck (bookgap S2) may attach ``source_recheck`` when ``ASK_JUDGE_RECHECK``
is on; the default remains off.
"""

from __future__ import annotations

import inspect
import json
import os
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import date
from typing import Literal, Protocol, cast, runtime_checkable

from intelligence.services import answer_model, llm_refine
from intelligence.services.agent_research import (
    AgentEvidence,
    StructuredObservation,
    describe_lost_observation,
    grounded_values_in_text,
)
from intelligence.services.degraded_fallback import (
    gap_transparency,
    is_model_service_unavailable,
)
from intelligence.services.session_projection import (
    CAUSE_EVIDENCE_GAP,
    CAUSE_JUDGE_UNAVAILABLE_HELD,
    CAUSE_MODEL_UNAVAILABLE,
    CAUSE_TRANSIENT_VERIFIER_OUTAGE,
    CAUSE_VERIFICATION_INCOMPLETE,
    CAUSE_VERIFIED,
    TerminalFacts,
    view,
)
from intelligence.services.agent_runtime import (
    AgentModelClient,
    AgentOutcome,
    ModelTurn,
    OutputEvidenceBinding,
)
from intelligence.services.episode_answer_hygiene import (
    choose_repair_rollback,
    classify_asked_date_coverage,
    find_unattempted_claims,
    repair_collapsed_to_stub,
    rewrite_unattempted_claims,
    rewrite_unverified_kb_gap_claims,
)
from intelligence.services.episode_protocol import (
    cited_evidence_ordinals,
    evidence_ordinal_table,
)
from intelligence.services.episode_issues import (
    Issue,
    IssueCode,
    allows_partial_release,
)
from intelligence.services.episode_output_substance import (
    JUDGMENT_OUTPUT_IDS,
    contract_has_model_reasoning_judgment,
    label_unlabelled_analytical_inferences,
    lost_required_output_substance,
    remove_lost_output_scaffolding,
)
from intelligence.services.episode_verifier import (
    VerifiedEpisodeOutcome,
    verify_episode_outcome,
)
from intelligence.services.judge_degrade import (
    classify_degrade_counts,
    degrade_class_for_status,
)
from intelligence.services.judge_source_recheck import recheck_draft, recheck_enabled
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import (
    FORWARD_HYPOTHESIS_OUTPUT_IDS,
    ResearchDeadline,
    ResearchPolicy,
    apply_env_ceiling,
    derive_stage_caps,
    policy_for_env,
)
from intelligence.services.task_frame import TaskFrame, last_explicit_iso_date
from intelligence.services.task_fulfillment import answer_has_output_marker
from intelligence.services.tool_result_budget import MAX_EVIDENCE_TITLE_CHARS


SemanticStatus = Literal["completed", "partial", "failed"]
JudgeStatus = Literal["passed", "repaired", "rejected", "unavailable"]
# 30.0 → 50.0（2026-08-20，压 prompt 后仍罩不住 grok 尾巴）。
#
# 压缩后的液冷同形 payload + 适配器 argv（``--max-turns 1`` /
# ``--json-schema`` / ``effort=low``）串行 N=5：18.9 / 23.4 / 23.6 / 26.2 /
# 46.7s。中位数已回 25s 内，但尾巴 46.7 > ``min(30, 窗×0.5)=25``。
# ``#269`` 只改余量切法，首发公式仍是半窗，50s 共享窗永远发不出 47s。
# 把 cap 提到与窗齐平，一次完整尝试 = 整窗；快失败仍由余额账给重试。
#
# 未动 T / ``_REPAIR_SECONDS_CAP`` / 档位 total/reserve / 工具批（R-07：
# 有 08-20 延迟实测才抬这个 30）。窗地板仍 50（R-10 的窗侧不变）。
DEFAULT_JUDGE_TIMEOUT_SECONDS = 50.0
MAX_SEMANTIC_JUDGE_WINDOW_SECONDS = 60.0
# 剩余窗不足一次完整尝试时不再发起半截调用（W2）。不要靠再抬窗口罩尾部。
LEFTOVER_WINDOW_ISSUE = (
    "semantic judge leftover window below one complete attempt"
)


def semantic_judge_window_seconds(policy: ResearchPolicy | None = None) -> float:
    """Total window shared by all judge attempts.

    Bookgap S3: the source of truth is ``derive_stage_caps`` (a fraction of
    synthesis reserve).  ``ASK_SEMANTIC_JUDGE_WINDOW`` can only lower it.
    One complete attempt is ``min(per_attempt_cap, window)`` — the 0.5
    pre-split was retired after the 08-20 grok tail (46.7s) could not fit
    in half of the 50s floor.
    """

    caps = derive_stage_caps(policy or policy_for_env())
    return apply_env_ceiling(caps.judge_window_seconds, "ASK_SEMANTIC_JUDGE_WINDOW")
MAX_SEMANTIC_JUDGE_ATTEMPTS = 3
JudgeFn = Callable[..., object]


@runtime_checkable
class _FinalizerJudgeProvider(Protocol):
    """Minimal seam the verifier needs from a finalizer.

    The verifier never calls ``recover()`` — it only reads ``_model`` as a
    fallback judge client.  Defining this Protocol here (in the domain layer)
    lets ``runtime/episode_finalizer`` satisfy it structurally, instead of the
    domain layer importing a runtime module.  This is the dependency inversion
    that breaks the only seam in the layer gate.
    """

    _model: AgentModelClient

_SENTENCE_RE = re.compile(r"(?<=[。！？!?；;])|\n+")
_CONTROL_FIELD_RE = re.compile(
    r"(?:\b(?:content[_ ]?hash|evidence[_ ]?hash|internal[_ ]?locator|"
    r"system[_ ]?prompt|tool[_ ]?calls?)\b\s*[:=]?|"
    r"\bhash\b\s*[:=]|\bprovider(?:[_ ]?name)?\b\s*[:=]|"
    r"\b_?provider_(?:attempts?|trace)\b\s*[:=]?|"
    r"\bendpoint\b\s*[:=]|"
    r"证据哈希|内容哈希|内部定位|系统提示|工具调用)",
    re.IGNORECASE,
)
_STRICT_JSON_FENCE_RE = re.compile(
    r"\A```(?:json)?[ \t]*\r?\n(?P<body>\{.*\})\r?\n```[ \t]*\Z",
    re.DOTALL | re.IGNORECASE,
)
_HTTP_STATUS_ERROR_RE = re.compile(
    r"\b(?:http(?:\s+status)?|status(?:[_\s]+code)?|code)\s*[:=]?\s*(\d{3})\b",
    re.IGNORECASE,
)
_ISSUE_SENTENCE_INDEX_RE = re.compile(
    r"(?:第\s*(\d+)\s*句|句\s*(\d+)|sentence\s*#?\s*(\d+))",
    re.IGNORECASE,
)
_CONDITION_TRIGGER_RE = re.compile(
    r"(?:若|如果|失效|降级|跌破|站稳|至少|"
    r"阈值|支撑|才算成立|才成立)"
)
_LEADING_CONDITION_LABEL_RE = re.compile(
    r"^\s*(?:[-*]\s*)?"
    r"(?:条件|失效信号|降级信号|触发条件)\s*"
    r"(?:\d+|[一二三四五六七八九十]+)?"
    r"\s*(?:[:：、.)）-]\s*)?"
)
_LEADING_SECTION_RE = re.compile(r"^\s*【[^】]{1,80}】\s*")
_LEADING_LIST_LABEL_RE = re.compile(
    r"^\s*(?:[-*]\s*)?(?:\d+|[一二三四五六七八九十]+)\s*"
    r"(?:[:：、.)）-]\s*)"
)
_DATE_TOKEN_RE = re.compile(
    r"(?:20\d{2}年\d{1,2}月\d{1,2}日|"
    r"20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}|"
    r"\d{1,2}月\d{1,2}日|"
    r"(?<!\d)(?:0?[1-9]|1[0-2])/(?:0?[1-9]|[12]\d|3[01])(?!\d)|"
    r"(?<!\d)(?:0[1-9]|1[0-2])[-/.](?:0[1-9]|[12]\d|3[01])(?!\d))"
)
_ARABIC_QUANTITY_RE = re.compile(
    r"[+-]?\d[\d,]*(?:\.\d+)?"
    r"(?:\s*(?:至|到|~|～|—|→|-)\s*[+-]?\d[\d,]*(?:\.\d+)?)?"
    r"\s*(?:万亿元|万亿|亿元|亿|个百分点|%|点|家|只|个|天|日|周|月|年|倍|成)?"
)
_CHINESE_QUANTITY_RE = re.compile(
    r"(?!万亿元)[一二两三四五六七八九十百千万亿]+"
    r"(?:万亿元|亿元|个百分点|点|家|只|个|天|日|周|月|年|倍|成)"
)
_QUANTITY_PARSE_RE = re.compile(
    r"\A(?P<first>[+-]?\d+(?:\.\d+)?)"
    r"(?:(?:至|到|-)(?P<second>[+-]?\d+(?:\.\d+)?))?"
    r"(?P<unit>万亿元|万亿|亿元|亿|个百分点|%|点|家|只|个|天|日|周|月|年|倍|成)?\Z"
)
_NEGATIVE_CONTEXT_RE = re.compile(
    r"(?:下降|下滑|减少|缩(?:量|约|减)?|回落|下跌|跌幅|负增长)"
)
_ORDERED_LIST_ITEM_RE = re.compile(
    r"^(?P<indent>\s*)(?P<number>\d+)(?P<suffix>[）).、])(?P<body>.*)$"
)
_CIRCLED_LIST_NUMBERS = "①②③④⑤⑥⑦⑧⑨⑩"
_EXPLICIT_LIST_COUNT_RE = re.compile(
    r"(?P<label>依据|理由|原因|条件|要点|因素|信号|维度|方面)"
    r"\s*(?:(?:一共|共|有|包括)\s*)?"
    r"(?P<count>\d+|[一二两三四五六七八九十]+)"
    r"(?P<unit>点|条|项|个|方面|种)"
)
_PREFIXED_LIST_COUNT_RE = re.compile(
    r"(?P<count>\d+|[一二两三四五六七八九十]+)"
    r"(?P<unit>层)"
    r"(?P<descriptor>[^，,。；;\n]{0,12}?(?:框架|方法|验证|条件|要点))"
)
_PAREN_LIST_NUMBER_RE = re.compile(
    r"(?P<open>[(（])(?P<number>\d{1,2})(?P<close>[)）])"
)
_NUMERIC_CONDITION_ISSUE = Issue(
    IssueCode.NUMERIC_UNSUPPORTED,
    "numeric_condition",
    "unsupported numeric condition without bound evidence",
)
_CALENDAR_WEEKDAY_ISSUE = Issue(
    IssueCode.CALENDAR_WEEKDAY_MISMATCH,
    "weekday",
    "calendar weekday mismatch with bound evidence",
)
_PATH_TREND_ISSUE = Issue(
    IssueCode.PATH_TREND_MISMATCH,
    "path_trend",
    "path trend mismatch with bound evidence",
)
_UNRESOLVED_EVIDENCE_ISSUE = Issue(
    IssueCode.UNRESOLVED_EVIDENCE_ORDINAL,
    "unresolved_evidence_ordinal",
    "cited evidence ordinal is not in this episode's evidence table",
)
SEMANTIC_QUALITY_DOUBT_MARK = "【质检存疑】"
_FULL_ISO_DATE_RE = re.compile(
    r"(?<!\d)(?P<year>20\d{2})-(?P<month>\d{1,2})-(?P<day>\d{1,2})(?!\d)"
)
_FULL_CHINESE_DATE_RE = re.compile(
    r"(?<!\d)(?P<year>20\d{2})年(?P<month>\d{1,2})月"
    r"(?P<day>\d{1,2})日"
)
_DATE_WEEKDAY_RE = re.compile(
    r"(?:(?P<year>20\d{2})年)?(?P<month>\d{1,2})月"
    r"(?P<day>\d{1,2})日\s*[（(]?"
    r"(?P<label>(?:周|星期)[一二三四五六日天])[）)]?"
)
_TURNOVER_OBSERVATION_RE = re.compile(
    r"(?P<date>20\d{2}-\d{1,2}-\d{1,2})"
    r"[^。；;\n]{0,100}?成交(?:额)?\s*"
    r"(?P<value>\d+(?:\.\d+)?)\s*亿"
)
_DOWNWARD_PATH_RE = re.compile(
    r"(?:一路(?:下跌|下滑|滑落|下降|回落|萎缩|走低)|"
    r"(?:持续|连续)(?:下跌|下滑|下降|回落|萎缩|缩量|走低))"
)
_UPWARD_PATH_RE = re.compile(
    r"(?:一路(?:上升|上涨|攀升|走高|增长|放大)|"
    r"(?:持续|连续)(?:上升|上涨|攀升|走高|增长|放大|放量))"
)
_TURNOVER_AMOUNT_SUBJECT_RE = re.compile(
    r"(?:成交额|成交金额|量能|"
    r"成交(?=\s*(?:从|自|在|由|正|仍|一路|持续|连续)))"
)
_PATH_SCOPE_BLOCKER_RE = re.compile(
    r"(?:并未|尚未|未(?!来)|没有|并非|不是|不具备|不能说|"
    r"尚难确认|无法确认|是否|预计|预期|可能|似乎|或许|也许|大概|"
    r"或将|未来|后续|"
    r"接下来|若|如果|假如|倘若|只有|除非|一旦|当(?!日))"
    r"[^，,；;。！？!?\n]{0,20}$"
)
_PATH_POST_SCOPE_BLOCKER_RE = re.compile(
    r"^(?:(?:但|不过|然而|可是|却)\s*)?"
    r"(?:(?:的|这一|该)说法)?"
    r"(?:并不成立|不成立|不准确|有待验证|尚未确认|是否)|"
    r"^(?:尚|仍|目前)?(?:无法|不能|难以)(?:确认|核验|验证|成立)|"
    r"^(?:并非|不是)(?:事实|趋势|结论)|"
    r"^不应(?:解读|视为|认为)|"
    r"^(?:的)?可能性(?:较低|不高)|"
    r"^(?:时|才|则)"
)
_LOCAL_PATH_WINDOW_RE = re.compile(
    r"(?:近|最近|过去|此前|前|连续)?\s*"
    r"(?:\d+|[一二两三四五六七八九十百]+)\s*(?:个)?"
    r"(?:交易日|日|天)"
)
_LOCAL_PATH_SEGMENT_RE = re.compile(
    r"(?:先[^，,；;。！？!?\n]{0,12}(?:后|再)|"
    r"(?:自|从)[^，,；;。！？!?\n]{1,12}(?:起|开始)|"
    r"(?:随后|此后|之后|其后))"
)
_OTHER_PATH_METRIC_RE = re.compile(
    r"(?:上涨家数|下跌家数|涨停|跌停|指数|股价|板块)"
)
_WEEKDAY_INDEX = {
    "一": 0,
    "二": 1,
    "三": 2,
    "四": 3,
    "五": 4,
    "六": 5,
    "日": 6,
    "天": 6,
}
_JUDGE_REPORT_TOOL_NAME = "submit_grounding_report"
_JUDGE_REPORT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": _JUDGE_REPORT_TOOL_NAME,
            "description": "提交逐句语义证据审查结果，不执行任何外部动作。",
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "passed": {"type": "boolean"},
                    "rejected_sentence_indexes": {
                        "type": "array",
                        "items": {"type": "integer"},
                    },
                    "issues": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": [
                    "passed",
                    "rejected_sentence_indexes",
                    "issues",
                ],
            },
        },
    }
]

_JUDGE_SYSTEM_PROMPT = (
    "你是严格的语义证据审查器。只审查用户 JSON 中的原问题、required-output "
    "绑定、证据注册表和编号句子；不要引入外部知识，也不要重写句子。检查主体、"
    "当前时点、事实/假设边界、因果证据、数字支持和跨题污染。观察事实、事实数字、"
    "外部因果和历史概率必须有直接证据。分析问题允许从已绑定事实做透明推导：若"
    "句子明确标注为判断、情景或估计，且推理前提可在证据中核验，不要要求 evidence "
    "原文已经包含预测结论。“据此判断”“这说明”“这意味着”也属于显式分析标记，"
    "但仍须核验其观察前提，不能把外部原因偷渡成事实。用户明确要求持续时间、"
    "空间、估值或其他预测时，允许"
    "给出带不确定性和条件的主观区间；但发明外部原因、支持性统计或任意触发阈值仍"
    "应拒绝。tool_status_registry 只支持检索过程状态，例如本轮是否命中；它不能支持"
    "市场事实或因果结论。答案不得暴露 capability、工具、provider 或哈希等内部标识，"
    "只能用“本轮资讯检索未命中”等自然语言。"
    "verified_quantities 是**已由确定性核对确认**来自 evidence_registry 的数值清单"
    "（逐字节相等才入列）：其中出现的数**不得**判为“未注册数字”“无直接证据”"
    "或“注册表无对应条目”，也不得因此摘除 required output。你要审的是这些数被"
    "用来支撑的**语义**（因果是否成立、口径有没有混用、日期是否对得上），"
    "不是它们在不在证据里——那一半已经查过了。清单之外的数仍按原规则审查。"
    "evidence_registry 的 E 编号与正文引用"
    "同一空间，可不连续；output_bindings.evidence_ids 与其对应。required_outputs 中的 "
    "答案对自身证据边界或推理层级的披露句（如“原文未覆盖某时段，此段映射为"
    "推理层”“以下为视角层推断”）是降低断言强度的元陈述，不是外部事实，"
    "不要求证据也不得拒绝；但披露句若同时断言具体行情数字或外部事件，仍按"
    "事实句审查。"
    "grounding_mode 是硬边界：evidence 只能引用直接证据，user_premise 只能评估用户"
    "给出的条件，model_reasoning 可以在不伪造证据的前提下给出方法论推理。若 "
    "answer_grounding_mode 为 model_reasoning，不得仅因方法步骤、T+N 观察窗口或"
    "定性判断没有 evidence_ids 而拒绝；只有它把外部事实、历史胜率或当前行情冒充"
    "已核验事实时才拒绝。若为 user_premise，用户明确给出的条件视为假设前提，不要求"
    "先证明该前提为真。只输出一个严格 "
    "JSON 对象，字段必须是 "
    "passed(boolean)、rejected_sentence_indexes(integer list)、issues(string list)。"
    "passed=true 时 rejected_sentence_indexes 必须为空；发现违反上述边界的句子时"
    "passed=false 并列出句号。必须从第1句检查到最后一句，一次返回全部不合格句号；"
    "不得发现首批问题后提前停止。issues 只能描述不合格句；issues 中明确提到的"
    "句号集合必须与 rejected_sentence_indexes 一致。若提供 "
    "submit_grounding_report 函数，必须优先"
    "调用它提交上述三个字段；只有不支持函数调用时才直接输出 JSON。"
)

_NON_EVIDENCE_JUDGE_SYSTEM_PROMPT = (
    "你是方法论与反事实边界审查器。只审查用户 JSON，不引入外部知识，不重写句子。"
    "answer_grounding_mode 只会是 model_reasoning 或 user_premise。"
    "model_reasoning 允许模型给出分析框架、定性因果链、T+N 观察窗口、验证清单和"
    "启发式阈值；这些内容不要求 evidence_ids，不能仅因缺少证据而拒绝。"
    "user_premise 题中，用户明确给出的前提视为真的假设，不能要求先证明前提，也不能"
    "把该前提改写成当前市场事实。只拒绝以下句子：冒充已核验的当前/历史外部事实，"
    "编造历史胜率或支持性统计，把假设偷换成事实，偏离原问题，或暴露工具、provider、"
    "哈希等控制字段。不要评价方法是否最优，也不要因它是经验规则、步骤或主观推理而"
    "拒绝。必须检查全部编号句子。只输出严格 JSON：passed(boolean)、"
    "rejected_sentence_indexes(integer list)、issues(string list)。passed=true 时"
    "索引列表必须为空；passed=false 时 issues 只能说明被拒绝句并与索引一致。若提供 "
    "submit_grounding_report 函数，必须优先调用它。"
)

_CLAIM_POLICY = {
    "observed_facts_require_direct_evidence": True,
    "labelled_analytical_inference_allowed": True,
    "requested_conditional_estimate_allowed": True,
    "unsupported_external_cause_rejected": True,
    "unsupported_historical_probability_rejected": True,
    "unsupported_supporting_statistics_rejected": True,
    "unsupported_numeric_trigger_rejected": True,
}
# Episode harness traces, not retrieval process status. The judge prompt
# already says tool_status_registry cannot support market facts; sending
# agent_loop success rows only pads the JSON.
_JUDGE_HIDDEN_STATUS_CAPABILITIES = frozenset({"agent_loop"})
_JUDGE_JSON_SEPARATORS = (",", ":")


def compact_judge_payload(value: object) -> object:
    """Drop blanks and duplicated defaults from the judge JSON.

    Kept: ``0`` / ``False`` / empty lists (``evidence_ids: []`` is a
    finding). Dropped: ``None``, ``""``, ``required: true`` (the default),
    and ``claim_policy`` (already written in the system prompt).
    """

    if isinstance(value, dict):
        compacted: dict[str, object] = {}
        for key, item in value.items():
            if key == "required" and item is True:
                continue
            if key == "claim_policy":
                continue
            nested = compact_judge_payload(item)
            if key == "tool_status_registry" and isinstance(nested, list):
                nested = [
                    row
                    for row in nested
                    if not (
                        isinstance(row, dict)
                        and str(row.get("capability") or "")
                        in _JUDGE_HIDDEN_STATUS_CAPABILITIES
                    )
                ]
            if nested is None or nested == "":
                continue
            if key == "tool_status_registry" and nested == []:
                continue
            compacted[key] = nested
        return compacted
    if isinstance(value, list):
        return [compact_judge_payload(item) for item in value]
    return value


def dumps_judge_request(request: Mapping[str, object]) -> str:
    """Wire JSON for the judge: compact separators, no default padding."""

    payload = compact_judge_payload(dict(request))
    return json.dumps(payload, ensure_ascii=False, separators=_JUDGE_JSON_SEPARATORS)


@dataclass(frozen=True)
class SemanticEpisodeOutcome:
    verified: VerifiedEpisodeOutcome
    status: SemanticStatus
    public_answer: str
    judge_status: JudgeStatus
    issues: tuple[str, ...] = ()
    correlated_judge: bool = False
    gap_output_ids: tuple[str, ...] = ()
    rejected_claim_indexes: tuple[int, ...] = ()
    repair_output_ids: tuple[str, ...] = ()
    timeout_asked: float | None = None
    timeout_configured: float | None = None
    remaining_seconds_at_entry: float | None = None
    exc_class: str | None = None
    http_status: int | None = None
    judge_attempt_index: int | None = None
    judge_request: dict[str, object] | None = None
    repair_withheld: bool = False
    unattempted_claim_count: int = 0
    asked_date_coverage: str = "not_applicable"
    repair_collapsed_to_stub: bool = False
    repair_rollback_mode: str | None = None

    def __post_init__(self) -> None:
        if not self.repair_output_ids:
            object.__setattr__(
                self,
                "repair_output_ids",
                tuple(
                    dict.fromkeys(
                        (*self.gap_output_ids, *self.verified.missing_outputs)
                    )
                ),
            )
        object.__setattr__(
            self,
            "gap_output_ids",
            tuple(dict.fromkeys(self.gap_output_ids)),
        )
        object.__setattr__(
            self,
            "rejected_claim_indexes",
            tuple(
                sorted(
                    {
                        index
                        for index in self.rejected_claim_indexes
                        if isinstance(index, int) and index >= 0
                    }
                )
            ),
        )

    def to_dict(self) -> dict[str, object]:
        """Return the private artifact shape (public text stays sanitized)."""

        degrade_class = degrade_class_for_status(self.judge_status)
        judge_count, content_count = classify_degrade_counts(
            judge_status=self.judge_status,
            extra_degrade_count=0,
            exc_class=self.exc_class,
            timeout_asked=self.timeout_asked,
        )
        _bindings, _registry, telemetry = _project_semantic_evidence(
            self.verified.outcome
        )
        payload: dict[str, object] = {
            "status": self.status,
            "public_answer": self.public_answer,
            "judge_status": self.judge_status,
            "issues": list(self.issues),
            "correlated_judge": self.correlated_judge,
            "gap_output_ids": list(self.gap_output_ids),
            "rejected_claim_indexes": list(self.rejected_claim_indexes),
            "repair_output_ids": list(self.repair_output_ids),
            "timeout_asked": self.timeout_asked,
            "timeout_configured": self.timeout_configured,
            "remaining_seconds_at_entry": self.remaining_seconds_at_entry,
            "exc_class": self.exc_class,
            "http_status": self.http_status,
            "judge_attempt_index": self.judge_attempt_index,
            "repair_withheld": self.repair_withheld,
            "unattempted_claim_count": self.unattempted_claim_count,
            "asked_date_coverage": self.asked_date_coverage,
            "repair_collapsed_to_stub": self.repair_collapsed_to_stub,
            "repair_rollback_mode": self.repair_rollback_mode,
            "projection_dropped_field_chars": telemetry.dropped_field_chars,
            "projection_truncated_field_chars": telemetry.truncated_field_chars,
            "projection_ordinal_mismatch_count": telemetry.ordinal_mismatch_count,
            "evidence_alias_offset": telemetry.alias_offset,
            "projection_cited_unbound_count": telemetry.cited_unbound_count,
            "degrade_class": degrade_class,
            "judge_unavailable_count": judge_count,
            "content_degraded_count": content_count,
            "pending_rejudge": self.judge_status == "unavailable",
            "verified": self.verified.to_dict(),
        }
        if self.judge_request is not None:
            payload["judge_request"] = self.judge_request
        return payload


@dataclass(frozen=True)
class _HygieneSnapshot:
    unattempted_claim_count: int = 0
    asked_date_coverage: str = "not_applicable"
    issues: tuple[str, ...] = ()


@dataclass(frozen=True)
class _JudgeCall:
    report: answer_model.GroundingJudgeReport | None
    unavailable: bool
    correlated: bool
    issue: str = ""
    root_deadline_exhausted: bool = False
    transient_provider_failure: bool = False
    # Fail closed: only explicitly classified deadline/transient failures may
    # opt into deletion-only candidate release. Malformed provider output must
    # never inherit release eligibility from a dataclass default.
    monotonic_release_safe: bool = False
    timeout_asked: float | None = None
    timeout_configured: float | None = None
    remaining_seconds_at_entry: float | None = None
    exc_class: str | None = None
    http_status: int | None = None
    judge_attempt_index: int | None = None
    request: dict[str, object] | None = None


def _judge_failure_identity(value: object) -> tuple[str | None, int | None]:
    """Capture the raw failure class before llm_refine flattens it.

    ``_failure_reason`` maps TimeoutError → ``timeout``; this helper keeps
    TimeoutError / HTTPError / ConnectionError distinguishable for H8/H9.
    Exception messages are discarded so public artifacts stay sanitized.
    """

    if isinstance(value, BaseException):
        status = getattr(value, "code", None)
        if isinstance(status, int) and 100 <= status <= 599:
            return type(value).__name__, status
        return type(value).__name__, None
    text = str(value or "").strip()
    if not text:
        return None, None
    http = re.search(r"HTTP\s+(\d{3})", text, re.IGNORECASE)
    if http is not None:
        return "HTTPError", int(http.group(1))
    boxed = re.search(r"（([^）]+)）", text)
    if boxed is not None:
        name = boxed.group(1).strip()
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]+", name):
            return name, None
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]+", text):
        return text, None
    return None, None


def _deadline_remaining_seconds(deadline: object) -> float | None:
    """Duck-typed remaining(); test stubs may only implement synthesis_timeout."""

    remaining = getattr(deadline, "remaining", None)
    if not callable(remaining):
        return None
    try:
        return float(remaining())
    except Exception:
        return None


def _attach_judge_clock(
    outcome: SemanticEpisodeOutcome,
    call: _JudgeCall,
) -> SemanticEpisodeOutcome:
    pending_request = (
        dict(call.request)
        if outcome.judge_status == "unavailable" and call.request is not None
        else None
    )
    return replace(
        outcome,
        timeout_asked=call.timeout_asked,
        timeout_configured=call.timeout_configured,
        remaining_seconds_at_entry=call.remaining_seconds_at_entry,
        exc_class=call.exc_class,
        http_status=call.http_status,
        judge_attempt_index=call.judge_attempt_index,
        judge_request=pending_request,
    )


class SemanticEpisodeVerifier:
    """Gate a structurally verified episode before public presentation.

    ``judge_fn`` is intentionally the smallest test seam.  It may accept one
    request mapping, keyword arguments, or return the strict JSON string,
    mapping, or :class:`GroundingJudgeReport`.  A production model can instead
    be injected as ``primary_judge``; when no explicit seam is supplied the
    independent ``LLM_JUDGE_*`` provider is preferred.
    """

    def __init__(
        self,
        judge_fn: JudgeFn | None = None,
        finalizer: _FinalizerJudgeProvider | None = None,
        *,
        primary_judge: AgentModelClient | JudgeFn | None = None,
        judge_client: AgentModelClient | JudgeFn | None = None,
        judge_timeout: float = DEFAULT_JUDGE_TIMEOUT_SECONDS,
    ) -> None:
        self._judge_fn = judge_fn
        self._primary_judge = primary_judge or judge_client
        self._finalizer = finalizer
        self._judge_timeout = max(0.1, float(judge_timeout))
        self._active_hygiene: _HygieneSnapshot | None = None
        self._semantic_reject_texts: tuple[str, ...] = ()
        self._semantic_reject_issues: tuple[str, ...] = ()

    def _finalize_outcome(
        self,
        outcome: SemanticEpisodeOutcome,
        call: _JudgeCall | None = None,
        *,
        repair_collapsed_to_stub: bool | None = None,
        repair_rollback_mode: str | None = None,
    ) -> SemanticEpisodeOutcome:
        hygiene = self._active_hygiene
        extras: dict[str, object] = {}
        if hygiene is not None:
            extras["unattempted_claim_count"] = hygiene.unattempted_claim_count
            extras["asked_date_coverage"] = hygiene.asked_date_coverage
            extras["issues"] = tuple(
                dict.fromkeys((*outcome.issues, *hygiene.issues))
            )
        if repair_collapsed_to_stub is not None:
            extras["repair_collapsed_to_stub"] = repair_collapsed_to_stub
        if repair_rollback_mode is not None:
            extras["repair_rollback_mode"] = repair_rollback_mode
        if extras:
            outcome = replace(outcome, **extras)
        outcome = self._project_semantic_quality_marks(outcome)
        if call is not None:
            outcome = _attach_judge_clock(outcome, call)
        return outcome

    def _note_semantic_reject(
        self,
        text: str,
        issues: tuple[str, ...],
    ) -> None:
        texts = list(self._semantic_reject_texts)
        snippet = str(text or "").strip()
        if snippet and snippet not in texts:
            texts.append(snippet)
        self._semantic_reject_texts = tuple(texts)
        merged = list(self._semantic_reject_issues)
        for issue in issues:
            if issue and issue not in merged:
                merged.append(issue)
        self._semantic_reject_issues = tuple(merged)

    def _plan_repair_indexes(
        self,
        rejected: tuple[int, ...],
        sentences: list[dict[str, object]],
        verified: VerifiedEpisodeOutcome,
        issues: tuple[str, ...] = (),
    ) -> tuple[int, ...]:
        mechanical, semantic = _partition_rejected_indexes(
            rejected,
            sentences=sentences,
            verified=verified,
        )
        contract = verified.contract
        text_by_index = {
            int(item["index"]): str(item["text"]) for item in sentences
        }
        repair = list(mechanical)
        for index in semantic:
            text = text_by_index.get(int(index), "")
            if _sentence_in_required_grounded_block(text, contract):
                self._note_semantic_reject(text, issues)
            else:
                repair.append(int(index))
        return tuple(sorted(set(repair)))

    def _project_semantic_quality_marks(
        self,
        outcome: SemanticEpisodeOutcome,
    ) -> SemanticEpisodeOutcome:
        texts = self._semantic_reject_texts
        if not texts:
            return outcome
        # 拒句与降级进 issues / judge_status，不进公开稿。质检条不上桌。
        issues = tuple(
            dict.fromkeys((*outcome.issues, *self._semantic_reject_issues))
        )
        judge_status = outcome.judge_status
        if judge_status == "passed":
            judge_status = "repaired"
        return replace(
            outcome,
            public_answer=view(
                TerminalFacts(
                    cause=CAUSE_VERIFIED,
                    public=outcome.public_answer,
                )
            ),
            issues=issues,
            judge_status=judge_status,
        )

    def verify(
        self,
        *,
        frame: TaskFrame,
        structurally_verified: VerifiedEpisodeOutcome,
        deadline: ResearchDeadline,
    ) -> SemanticEpisodeOutcome:
        """Run structural-first verification with bounded deletion-only repair."""

        self._semantic_reject_texts = ()
        self._semantic_reject_issues = ()
        structural = structurally_verified
        contract = structural.contract
        guard_status: SemanticStatus = (
            "failed" if structural.verified_status == "failed" else "partial"
        )
        if contract is None:
            return SemanticEpisodeOutcome(
                verified=structural,
                status=guard_status,
                public_answer=self._generic_gap_answer(frame),
                judge_status="unavailable",
                issues=tuple(
                    dict.fromkeys((*structural.issues, "semantic contract missing"))
                ),
                correlated_judge=False,
            )
        frame_hash = frame.task_frame_hash
        if (
            not contract.task_frame_hash
            or frame_hash != structural.outcome.task_frame_hash
            or frame_hash != contract.task_frame_hash
        ):
            return SemanticEpisodeOutcome(
                verified=structural,
                status=guard_status,
                public_answer=self._generic_gap_answer(frame),
                judge_status="unavailable",
                issues=tuple(
                    dict.fromkeys(
                        (*structural.issues, "semantic frame/contract hash mismatch")
                    )
                ),
                correlated_judge=False,
            )
        if (
            structural.verified_status != "completed"
            and not _can_semantically_release_partial(structural)
        ):
            # Mixed/blocked structural partials are not promoted.  Avoid even
            # calling the judge when no useful required output survived or the
            # partial was caused by anything outside the release allowlist
            # (explicit evidence gap / missing mandatory capability / evidence
            # type whitelist).  A mixed fulfilled/gap result may still be
            # judged and released as partial.  Honest runtime-partial with
            # every slot fulfilled is the exception: see
            # ``_contract_slots_all_fulfilled``.
            status: SemanticStatus = (
                "failed" if structural.verified_status == "failed" else "partial"
            )
            return SemanticEpisodeOutcome(
                verified=structural,
                status=status,
                public_answer=self._gap_answer(frame, structural),
                judge_status="unavailable",
                issues=structural.issues,
                correlated_judge=False,
            )

        draft = structural.outcome.draft
        if contract_has_model_reasoning_judgment(contract):
            labeled = label_unlabelled_analytical_inferences(draft)
            if labeled != draft:
                structural = replace(
                    structural,
                    outcome=replace(structural.outcome, draft=labeled),
                )
                draft = labeled
        sentences = _numbered_sentences(draft)
        if not sentences:
            return SemanticEpisodeOutcome(
                verified=structural,
                status="partial",
                public_answer=self._gap_answer(frame, structural),
                judge_status="unavailable",
                issues=("empty public draft",),
                correlated_judge=False,
            )

        preflight_issues: tuple[str, ...] = ()
        marker_loss_outputs: tuple[str, ...] = ()
        preflight_source = structural
        numeric_rejected = _novel_numeric_condition_indexes(
            sentences,
            structural,
        )
        weekday_rejected = _mismatched_weekday_indexes(
            sentences,
            structural,
        )
        path_rejected = _mismatched_path_trend_indexes(
            sentences,
            structural,
        )
        preflight_rejected = tuple(
            sorted(
                set(
                    (
                        *numeric_rejected,
                        *weekday_rejected,
                        *path_rejected,
                    )
                )
            )
        )
        if preflight_rejected:
            before_repair = structural.outcome.draft
            preflight_source = structural
            preflight = self._repair(
                frame=frame,
                structural=structural,
                rejected_sentence_indexes=preflight_rejected,
            )
            if preflight is None:
                return SemanticEpisodeOutcome(
                    verified=structural,
                    status="partial",
                    public_answer=self._gap_answer(frame, structural),
                    judge_status="rejected",
                    issues=tuple(
                        dict.fromkeys(
                            (*structural.issues, _NUMERIC_CONDITION_ISSUE.serialize())
                        )
                    ),
                    correlated_judge=False,
                )
            structural, _preflight_frame = preflight
            preflight_issues = tuple(
                issue.serialize()
                for indexes, issue in (
                    (numeric_rejected, _NUMERIC_CONDITION_ISSUE),
                    (weekday_rejected, _CALENDAR_WEEKDAY_ISSUE),
                    (path_rejected, _PATH_TREND_ISSUE),
                )
                if indexes
            )
            marker_loss = _lost_grounded_output_substance(
                contract,
                before_repair,
                structural.outcome.draft,
            )
            if marker_loss:
                marker_loss_outputs = marker_loss
            if (
                structural.verified_status != "completed"
                and not _can_semantically_release_partial(structural)
            ):
                return SemanticEpisodeOutcome(
                    verified=structural,
                    status="partial",
                    public_answer=self._gap_answer(frame, structural),
                    judge_status="rejected",
                    issues=tuple(
                        dict.fromkeys((*structural.issues, *preflight_issues))
                    ),
                    correlated_judge=False,
                )
            sentences = _numbered_sentences(structural.outcome.draft)

        structural, claim_issues, claim_count = self._apply_unattempted_claim_rewrite(
            frame, structural
        )
        structural = self._apply_kb_gap_proof_rewrite(structural)
        self._active_hygiene = _HygieneSnapshot(
            unattempted_claim_count=claim_count,
            asked_date_coverage=classify_asked_date_coverage(
                frame.raw_question,
                frame.question_type,
                structural.outcome.traces,
            ),
            issues=claim_issues,
        )
        sentences = _numbered_sentences(structural.outcome.draft)
        request = self._judge_request(frame, structural, sentences)
        first = replace(self._run_judge(request, deadline), request=request)
        if deadline.expired:
            deadline_release_safe = (
                first.report is None
                and (
                    first.monotonic_release_safe
                    or "deadline" in first.issue.casefold()
                )
            )
            first = replace(
                first,
                report=None,
                unavailable=True,
                issue="semantic judge deadline exhausted",
                root_deadline_exhausted=True,
                monotonic_release_safe=deadline_release_safe,
            )
        if first.report is None:
            issue = first.issue or "semantic judge unavailable"
            if first.monotonic_release_safe and issue in {
                "semantic judge deadline exhausted",
                "semantic judge transient provider error",
                LEFTOVER_WINDOW_ISSUE,
            }:
                candidate = self._transient_failure_candidate(
                    frame,
                    structural,
                    issues=tuple(
                        dict.fromkeys(
                            (*structural.issues, *preflight_issues, issue)
                        )
                    ),
                    correlated_judge=first.correlated,
                )
                if candidate is not None:
                    return self._finalize_outcome(candidate, first)
            return self._finalize_outcome(
                SemanticEpisodeOutcome(
                    verified=structural,
                    status="partial",
                    public_answer=self._gap_answer(
                        frame,
                        structural,
                        judge_unavailable=True,
                    ),
                    judge_status="unavailable",
                    issues=tuple(
                        dict.fromkeys((*structural.issues, *preflight_issues, issue))
                    ),
                    correlated_judge=first.correlated,
                ),
                first,
            )

        first = _apply_numeric_condition_gate(first, sentences, structural)
        first = _apply_meta_disclosure_exemption(first, sentences)
        first = _apply_unresolved_evidence_ordinal_gate(first, sentences, structural)
        assert first.report is not None
        if first.report.passed:
            if marker_loss_outputs:
                return self._marker_loss_or_withhold(
                    frame,
                    source=preflight_source,
                    wiped=structural,
                    marker_loss=marker_loss_outputs,
                    judge_issues=tuple(
                        dict.fromkeys(
                            (
                                *structural.issues,
                                *preflight_issues,
                                *first.report.issues,
                                *_marker_loss_issues(marker_loss_outputs),
                            )
                        )
                    ),
                    correlated_judge=first.correlated,
                    call=first,
                    issue_code="preflight_wiped_all_outputs",
                    issue_message="preflight repair removed every required output",
                    rejected_sentence_indexes=preflight_rejected,
                )
            return self._completed_public(
                frame,
                structural,
                judge_status=("repaired" if preflight_issues else "passed"),
                judge_issues=tuple(
                    dict.fromkeys(
                        (
                            *structural.issues,
                            *preflight_issues,
                                *first.report.issues,
                        )
                    )
                ),
                correlated_judge=first.correlated,
                call=first,
            )

        first_repair_indexes = self._plan_repair_indexes(
            first.report.rejected_sentence_indexes,
            sentences,
            structural,
            first.report.issues,
        )
        if not first_repair_indexes:
            return self._completed_public(
                frame,
                structural,
                judge_status="repaired",
                judge_issues=tuple(
                    dict.fromkeys(
                        (
                            *structural.issues,
                            *preflight_issues,
                            *first.report.issues,
                        )
                    )
                ),
                correlated_judge=first.correlated,
                call=first,
            )

        repaired = self._repair(
            frame=frame,
            structural=structural,
            rejected_sentence_indexes=first_repair_indexes,
        )
        if repaired is None:
            issues = tuple(
                dict.fromkeys(
                    (
                        *structural.issues,
                        *preflight_issues,
                        *first.report.issues,
                        "semantic repair unavailable",
                    )
                )
            )
            return self._finalize_outcome(
                SemanticEpisodeOutcome(
                    verified=structural,
                    status="partial",
                    public_answer=self._gap_answer(frame, structural),
                    judge_status="rejected",
                    issues=issues,
                    correlated_judge=first.correlated,
                ),
                first,
            )

        repaired_verified, _repaired_frame = repaired
        marker_loss = _lost_grounded_output_substance(
            contract,
            structural.outcome.draft,
            repaired_verified.outcome.draft,
        )
        marker_loss = tuple(
            dict.fromkeys((*marker_loss_outputs, *marker_loss))
        )
        first_issues = tuple(
            dict.fromkeys(
                (
                    *repaired_verified.issues,
                    *preflight_issues,
                    *first.report.issues,
                    *_marker_loss_issues(marker_loss),
                )
            )
        )
        withheld = self._maybe_withhold_after_repair(
            frame,
            source=structural,
            wiped=repaired_verified,
            rejected_sentence_indexes=first_repair_indexes,
            marker_loss=marker_loss,
            judge_issues=first_issues,
            correlated_judge=first.correlated,
            call=first,
            issue_code="repair_wiped_all_outputs",
            issue_message=(
                "semantic repair removed every required output; "
                "judge verdict treated as suspect"
            ),
        )
        if withheld is not None:
            return withheld
        if (
            repaired_verified.verified_status != "completed"
            and not _can_semantically_release_partial(repaired_verified)
        ):
            issues = tuple(
                dict.fromkeys(
                    (
                        *repaired_verified.issues,
                        *preflight_issues,
                        *first.report.issues,
                        "semantic repair remained structurally partial",
                    )
                )
            )
            return self._finalize_outcome(
                SemanticEpisodeOutcome(
                    verified=repaired_verified,
                    status="partial",
                    public_answer=self._gap_answer(frame, repaired_verified),
                    judge_status="rejected",
                    issues=issues,
                    correlated_judge=first.correlated,
                ),
                first,
            )

        # The re-judge sees the repaired draft but exactly the same evidence.
        repaired_sentences = _numbered_sentences(repaired_verified.outcome.draft)
        second_request = self._judge_request(
            frame, repaired_verified, repaired_sentences
        )
        second = replace(
            self._run_judge(second_request, deadline),
            request=second_request,
        )
        second = _apply_optional_rejudge_deadline(second, deadline)
        second = _apply_numeric_condition_gate(
            second,
            repaired_sentences,
            repaired_verified,
        )
        second = _apply_meta_disclosure_exemption(second, repaired_sentences)
        second = _apply_unresolved_evidence_ordinal_gate(
            second,
            repaired_sentences,
            repaired_verified,
        )
        correlated = first.correlated or second.correlated
        if second.report is not None and second.report.passed:
            return self._completed_public(
                frame,
                repaired_verified,
                judge_status="repaired",
                judge_issues=tuple(
                    dict.fromkeys(
                        (
                            *repaired_verified.issues,
                            *preflight_issues,
                            *first.report.issues,
                            *second.report.issues,
                        )
                    )
                ),
                correlated_judge=correlated,
                call=second,
            )

        if _optional_rejudge_allows_monotonic_release(second):
            # The first completed report reviewed the entire original draft
            # and named the only spans it rejected. Removing those spans is a
            # monotonic operation: it cannot add a claim or evidence. A
            # best-effort rejudge may catch omissions, but root-budget expiry
            # or an explicitly transient provider outage must not erase the
            # already-reviewed remainder. Invalid/malformed responses are not
            # transient and remain fail closed.
            second_issue = second.issue or "semantic rejudge unavailable"
            return self._completed_public(
                frame,
                repaired_verified,
                judge_status="repaired",
                judge_issues=tuple(
                    dict.fromkeys(
                        (
                            *repaired_verified.issues,
                            *preflight_issues,
                            *first.report.issues,
                            second_issue,
                        )
                    )
                ),
                correlated_judge=correlated,
                call=second,
            )

        if (
            second.report is not None
            and second.report.rejected_sentence_indexes
        ):
            second_repair_indexes = self._plan_repair_indexes(
                second.report.rejected_sentence_indexes,
                repaired_sentences,
                repaired_verified,
                second.report.issues,
            )
            if not second_repair_indexes:
                return self._completed_public(
                    frame,
                    repaired_verified,
                    judge_status="repaired",
                    judge_issues=tuple(
                        dict.fromkeys(
                            (
                                *repaired_verified.issues,
                                *preflight_issues,
                                *first.report.issues,
                                *second.report.issues,
                            )
                        )
                    ),
                    correlated_judge=correlated,
                    call=second,
                )
            repaired_twice = self._repair(
                frame=frame,
                structural=repaired_verified,
                rejected_sentence_indexes=second_repair_indexes,
            )
            if repaired_twice is not None:
                twice_verified, _twice_frame = repaired_twice
                second_marker_loss = _lost_grounded_output_substance(
                    contract,
                    repaired_verified.outcome.draft,
                    twice_verified.outcome.draft,
                )
                second_issues = tuple(
                    dict.fromkeys(
                        (
                            *twice_verified.issues,
                            *preflight_issues,
                            *first.report.issues,
                            *second.report.issues,
                            *_marker_loss_issues(second_marker_loss),
                        )
                    )
                )
                withheld = self._maybe_withhold_after_repair(
                    frame,
                    source=repaired_verified,
                    wiped=twice_verified,
                    rejected_sentence_indexes=second_repair_indexes,
                    marker_loss=second_marker_loss,
                    judge_issues=second_issues,
                    correlated_judge=correlated,
                    call=second,
                    issue_code="repair_wiped_all_outputs",
                    issue_message=(
                        "semantic repair removed every required output; "
                        "judge verdict treated as suspect"
                    ),
                )
                if withheld is not None:
                    return withheld
                if (
                    twice_verified.verified_status == "completed"
                    or _can_semantically_release_partial(twice_verified)
                ):
                    twice_sentences = _numbered_sentences(
                        twice_verified.outcome.draft
                    )
                    third_request = self._judge_request(
                        frame,
                        twice_verified,
                        twice_sentences,
                    )
                    third = replace(
                        self._run_judge(third_request, deadline),
                        request=third_request,
                    )
                    third = _apply_optional_rejudge_deadline(third, deadline)
                    third = _apply_numeric_condition_gate(
                        third,
                        twice_sentences,
                        twice_verified,
                    )
                    third = _apply_unresolved_evidence_ordinal_gate(
                        third,
                        twice_sentences,
                        twice_verified,
                    )
                    correlated = correlated or third.correlated
                    if third.report is not None and third.report.passed:
                        return self._completed_public(
                            frame,
                            twice_verified,
                            judge_status="repaired",
                            judge_issues=tuple(
                                dict.fromkeys(
                                    (
                                        *twice_verified.issues,
                                        *preflight_issues,
                                        *first.report.issues,
                                        *second.report.issues,
                                        *third.report.issues,
                                    )
                                )
                            ),
                            correlated_judge=correlated,
                            call=third,
                        )
                    if _optional_rejudge_allows_monotonic_release(third):
                        # The second completed report reviewed the once-
                        # repaired draft. Its exact rejected spans have now
                        # been removed, so an optional final rejudge timeout
                        # or transient provider outage cannot erase that
                        # twice-reviewed remainder.
                        third_issue = (
                            third.issue or "semantic final rejudge unavailable"
                        )
                        return self._completed_public(
                            frame,
                            twice_verified,
                            judge_status="repaired",
                            judge_issues=tuple(
                                dict.fromkeys(
                                    (
                                        *twice_verified.issues,
                                        *preflight_issues,
                                        *first.report.issues,
                                        *second.report.issues,
                                        third_issue,
                                    )
                                )
                            ),
                            correlated_judge=correlated,
                            call=third,
                        )
                    if (
                        third.report is not None
                        and third.report.rejected_sentence_indexes
                    ):
                        # The last report has already reviewed every remaining
                        # sentence.  Removing exactly its rejected indexes is a
                        # monotonic safety operation, so no fourth model call is
                        # needed; structural coverage and marker preservation
                        # still have to pass below.
                        third_repair_indexes = self._plan_repair_indexes(
                            third.report.rejected_sentence_indexes,
                            twice_sentences,
                            twice_verified,
                            third.report.issues,
                        )
                        if not third_repair_indexes:
                            return self._completed_public(
                                frame,
                                twice_verified,
                                judge_status="repaired",
                                judge_issues=tuple(
                                    dict.fromkeys(
                                        (
                                            *twice_verified.issues,
                                            *preflight_issues,
                                            *first.report.issues,
                                            *second.report.issues,
                                            *third.report.issues,
                                        )
                                    )
                                ),
                                correlated_judge=correlated,
                                call=third,
                            )
                        terminal_repair = self._repair(
                            frame=frame,
                            structural=twice_verified,
                            rejected_sentence_indexes=third_repair_indexes,
                        )
                        if terminal_repair is not None:
                            terminal_verified, _terminal_frame = terminal_repair
                            terminal_marker_loss = _lost_grounded_output_substance(
                                contract,
                                twice_verified.outcome.draft,
                                terminal_verified.outcome.draft,
                            )
                            terminal_issues = tuple(
                                dict.fromkeys(
                                    (
                                        *terminal_verified.issues,
                                        *preflight_issues,
                                        *first.report.issues,
                                        *second.report.issues,
                                        *third.report.issues,
                                        *_marker_loss_issues(
                                            terminal_marker_loss
                                        ),
                                    )
                                )
                            )
                            withheld = self._maybe_withhold_after_repair(
                                frame,
                                source=twice_verified,
                                wiped=terminal_verified,
                                rejected_sentence_indexes=third_repair_indexes,
                                marker_loss=terminal_marker_loss,
                                judge_issues=terminal_issues,
                                correlated_judge=correlated,
                                call=third,
                                issue_code="repair_wiped_all_outputs",
                                issue_message=(
                                    "semantic repair removed every required output; "
                                    "judge verdict treated as suspect"
                                ),
                            )
                            if withheld is not None:
                                return withheld
                            if (
                                terminal_verified.verified_status == "completed"
                                or _can_semantically_release_partial(
                                    terminal_verified
                                )
                            ):
                                return self._completed_public(
                                    frame,
                                    terminal_verified,
                                    judge_status="repaired",
                                    judge_issues=tuple(
                                        dict.fromkeys(
                                            (
                                                *terminal_verified.issues,
                                                *preflight_issues,
                                                *first.report.issues,
                                                *second.report.issues,
                                                *third.report.issues,
                                            )
                                        )
                                    ),
                                    correlated_judge=correlated,
                                    call=third,
                                )
                    third_issue = (
                        third.issue
                        if third.report is None
                        else "; ".join(third.report.issues)
                        or "semantic judge rejected twice-repaired draft"
                    )
                    issues = tuple(
                        dict.fromkeys(
                            (
                                *twice_verified.issues,
                                *preflight_issues,
                                *first.report.issues,
                                *second.report.issues,
                                third_issue,
                            )
                        )
                    )
                    return self._finalize_outcome(
                        SemanticEpisodeOutcome(
                            verified=twice_verified,
                            status="partial",
                            public_answer=self._gap_answer(frame, twice_verified),
                            judge_status=(
                                "unavailable"
                                if third.report is None
                                else "rejected"
                            ),
                            issues=issues,
                            correlated_judge=correlated,
                        ),
                        third,
                    )

        final_issue = (
            second.issue
            if second.report is None
            else "; ".join(second.report.issues)
            or "semantic judge rejected repaired draft"
        )
        issues = tuple(
            dict.fromkeys(
                (
                    *repaired_verified.issues,
                    *preflight_issues,
                    *first.report.issues,
                    final_issue,
                )
            )
        )
        return self._finalize_outcome(
            SemanticEpisodeOutcome(
                verified=repaired_verified,
                status="partial",
                public_answer=self._gap_answer(frame, repaired_verified),
                judge_status=("unavailable" if second.report is None else "rejected"),
                issues=issues,
                correlated_judge=correlated,
            ),
            second,
        )

    def _transient_failure_candidate(
        self,
        frame: TaskFrame,
        structural: VerifiedEpisodeOutcome,
        *,
        issues: tuple[str, ...],
        correlated_judge: bool,
    ) -> SemanticEpisodeOutcome | None:
        """Keep a safe candidate visible when a transient judge outage occurs.

        This is deliberately not a semantic pass: the result remains
        ``partial``/``unavailable`` and the public text carries the warning.
        Only a structurally complete (or explicitly evidence-gap partial)
        episode may reach this projection, and the caller must have classified
        the provider failure as transient/release-safe. Configuration,
        malformed-output, and contract failures continue to use the generic
        fail-closed gap.
        """

        if structural.verified_status != "completed" and not (
            _can_semantically_release_partial(structural)
        ):
            return None
        public = _sanitize_public_answer(
            structural.outcome.draft,
            structural.outcome.evidence,
            structural.outcome.traces,
        )
        if not public:
            return None
        return SemanticEpisodeOutcome(
            verified=structural,
            status="partial",
            public_answer=view(
                TerminalFacts(
                    cause=CAUSE_TRANSIENT_VERIFIER_OUTAGE,
                    question=frame.raw_question,
                    public=public,
                )
            ),
            judge_status="unavailable",
            issues=issues,
            correlated_judge=correlated_judge,
        )

    def _judge_request(
        self,
        frame: TaskFrame,
        verified: VerifiedEpisodeOutcome,
        sentences: list[dict[str, object]],
    ) -> dict[str, object]:
        contract = verified.contract
        if contract is not None:
            required_outputs: list[dict[str, object]] = [
                {
                    "output_id": item.output_id,
                    "description": item.description,
                    "required": item.required,
                    "grounding_mode": item.grounding_mode,
                }
                for item in contract.required_outputs
            ]
        else:
            required_outputs = [
                {"output_id": output_id, "required": True}
                for output_id in frame.required_outputs
            ]
        output_bindings, evidence_registry = _semantic_evidence_projection(
            verified.outcome
        )
        answer_grounding_mode = _answer_grounding_mode(contract)
        payload: dict[str, object] = {
            "question": frame.raw_question,
            "task_frame": {
                "subject": frame.subject,
                "subject_kind": frame.subject_kind,
                "question_type": frame.question_type,
                "timeframe": frame.timeframe,
                "user_goal": frame.user_goal,
            },
            "required_outputs": required_outputs,
            "answer_grounding_mode": answer_grounding_mode,
            "output_bindings": output_bindings,
            "evidence_registry": evidence_registry,
            "verified_quantities": _verified_quantities_for_judge(verified.outcome),
            "tool_status_registry": [
                row
                for row in _semantic_tool_status_registry(verified.outcome.traces)
                if str(row.get("capability") or "")
                not in _JUDGE_HIDDEN_STATUS_CAPABILITIES
            ],
            "sentences": sentences,
        }
        if recheck_enabled():
            draft = " ".join(str(item.get("text") or "") for item in sentences)
            payload["source_recheck"] = recheck_draft(draft)
        return cast(dict[str, object], compact_judge_payload(payload))

    def _clocked_judge_call(
        self,
        *,
        asked: float | None,
        remaining: float | None,
        correlated: bool,
        unavailable: bool,
        issue: str = "",
        report: answer_model.GroundingJudgeReport | None = None,
        failure: object | None = None,
        root_deadline_exhausted: bool = False,
        transient_provider_failure: bool = False,
        monotonic_release_safe: bool = False,
        judge_attempt_index: int | None = None,
    ) -> _JudgeCall:
        exc_class, http_status = (
            _judge_failure_identity(failure) if failure is not None else (None, None)
        )
        return _JudgeCall(
            report,
            unavailable,
            correlated,
            issue,
            root_deadline_exhausted=root_deadline_exhausted,
            transient_provider_failure=transient_provider_failure,
            monotonic_release_safe=monotonic_release_safe,
            timeout_asked=asked,
            timeout_configured=self._judge_timeout,
            remaining_seconds_at_entry=remaining,
            exc_class=exc_class,
            http_status=http_status,
            judge_attempt_index=judge_attempt_index,
        )

    def _run_judge(
        self,
        request: dict[str, object],
        deadline: ResearchDeadline,
    ) -> _JudgeCall:
        total_window = semantic_total_judge_window(
            deadline, configured_attempt_timeout=self._judge_timeout
        )
        attempt_timeouts = semantic_attempts_for_window(
            total_window,
            configured_attempt_timeout=self._judge_timeout,
        )
        if not attempt_timeouts:
            return self._clocked_judge_call(
                asked=0.0,
                remaining=_deadline_remaining_seconds(deadline),
                correlated=False,
                unavailable=True,
                issue="semantic judge deadline exhausted",
                root_deadline_exhausted=True,
                monotonic_release_safe=True,
            )

        # R-20260829-03 判官备链：主判官 + 显式配置的备胎（永不自动追加合成
        # 主链——「不静默退回相关自审」红线不变）。链退化为单主时行为与改动
        # 前逐字节一致。
        providers: tuple[object, ...] = ()
        try:
            providers = llm_refine.judge_provider_chain()
        except Exception:
            providers = ()
        provider = providers[0] if providers else None
        if provider is not None:
            leftover = _deadline_remaining_seconds(deadline)
            if leftover_window_blocks_complete_attempt(
                leftover, self._judge_timeout
            ):
                return self._clocked_judge_call(
                    asked=0.0,
                    remaining=leftover,
                    correlated=False,
                    unavailable=True,
                    issue=LEFTOVER_WINDOW_ISSUE,
                    root_deadline_exhausted=True,
                    monotonic_release_safe=True,
                )
            messages = [
                {"role": "system", "content": _judge_system_prompt(request)},
                {
                    "role": "user",
                    "content": dumps_judge_request(request),
                },
            ]
            prior_failures_release_safe = True
            # 窗口余额账：报价是「一次完整尝试」，真正的封顶是这里。
            # 用 deadline 读数扣账而不是另起时钟——冻结时间的测试才不会两套钟打架。
            window_left = total_window
            previous_remaining: float | None = None
            for attempt, timeout_limit in enumerate(attempt_timeouts):
                remaining_at_entry = _deadline_remaining_seconds(deadline)
                if previous_remaining is not None and remaining_at_entry is not None:
                    window_left -= max(0.0, previous_remaining - remaining_at_entry)
                previous_remaining = remaining_at_entry
                timeout_limit = min(timeout_limit, max(0.0, window_left))
                if leftover_window_blocks_complete_attempt(
                    remaining_at_entry, self._judge_timeout
                ):
                    return self._clocked_judge_call(
                        asked=0.0,
                        judge_attempt_index=attempt,
                        remaining=remaining_at_entry,
                        correlated=False,
                        unavailable=True,
                        issue=LEFTOVER_WINDOW_ISSUE,
                        root_deadline_exhausted=True,
                        monotonic_release_safe=True,
                    )
                attempt_timeout = deadline.synthesis_timeout(timeout_limit)
                if attempt_timeout <= 0.001:
                    failure_chain_release_safe = (
                        attempt == 0 or prior_failures_release_safe
                    )
                    return self._clocked_judge_call(
                        asked=attempt_timeout,
                        judge_attempt_index=attempt,
                        remaining=remaining_at_entry,
                        correlated=False,
                        unavailable=True,
                        issue="semantic judge deadline exhausted",
                        root_deadline_exhausted=True,
                        monotonic_release_safe=failure_chain_release_safe,
                    )
                # 槽位轮转：attempt 0 走主判官，之后的槽走链上下一位（链短于
                # 槽数时停在最后一位）。哪位判官真正服务了本轮，由 LLM 调用
                # 台账逐 attempt 记 provider 名，不另加 schema。
                active_provider = providers[min(attempt, len(providers) - 1)]
                try:
                    with llm_refine.provider_override(active_provider):
                        content, _used, reason = llm_refine.complete(
                            messages,
                            timeout=attempt_timeout,
                            temperature=0.0,
                        )
                except Exception as exc:  # pragma: no cover - adapter boundary
                    issue, retryable, release_safe = _stable_semantic_judge_error(
                        type(exc).__name__
                    )
                    should_retry = _should_retry_semantic_judge(
                        attempt,
                        retryable=retryable,
                        release_safe=release_safe,
                        prior_failures_release_safe=(
                            prior_failures_release_safe
                        ),
                        deadline=deadline,
                    )
                    prior_failures_release_safe &= release_safe
                    if not should_retry and _next_slot_switches_judge(
                        attempt, len(providers), len(attempt_timeouts), deadline
                    ):
                        # 主判官放弃但链上还有没上场的备胎：下一槽换人再试。
                        # 释放安全账照常累计，不因换人清零（R-20260829-03）。
                        should_retry = True
                    if should_retry:
                        continue
                    return self._clocked_judge_call(
                        asked=attempt_timeout,
                        judge_attempt_index=attempt,
                        remaining=remaining_at_entry,
                        correlated=False,
                        unavailable=True,
                        issue=issue,
                        failure=exc,
                        transient_provider_failure=(
                            prior_failures_release_safe
                        ),
                        monotonic_release_safe=prior_failures_release_safe,
                    )
                report = self._parse_report(content, len(request["sentences"]))
                if report is not None:
                    return self._clocked_judge_call(
                        asked=attempt_timeout,
                        judge_attempt_index=attempt,
                        remaining=remaining_at_entry,
                        correlated=False,
                        unavailable=False,
                        report=report,
                        monotonic_release_safe=prior_failures_release_safe,
                    )
                issue, retryable, release_safe = _stable_semantic_judge_error(
                    reason or "invalid semantic judge output"
                )
                should_retry = _should_retry_semantic_judge(
                    attempt,
                    retryable=retryable,
                    release_safe=release_safe,
                    prior_failures_release_safe=prior_failures_release_safe,
                    deadline=deadline,
                )
                prior_failures_release_safe &= release_safe
                if not should_retry and _next_slot_switches_judge(
                    attempt, len(providers), len(attempt_timeouts), deadline
                ):
                    # 同上：链上还有备胎时不在主判官身上判死刑。
                    should_retry = True
                if should_retry:
                    continue
                return self._clocked_judge_call(
                    asked=attempt_timeout,
                        judge_attempt_index=attempt,
                    remaining=remaining_at_entry,
                    correlated=False,
                    unavailable=True,
                    issue=issue,
                    failure=reason or "invalid semantic judge output",
                    transient_provider_failure=prior_failures_release_safe,
                    monotonic_release_safe=prior_failures_release_safe,
                )
            return self._clocked_judge_call(
                asked=None,
                remaining=_deadline_remaining_seconds(deadline),
                correlated=False,
                unavailable=True,
                issue="semantic judge unavailable",
            )

        # Explicit injection is the deterministic test/canary seam only when
        # no independent LLM_JUDGE provider is configured.  It is correlated
        # because it normally shares the primary composer model.
        if self._judge_fn is not None:
            remaining_at_entry = _deadline_remaining_seconds(deadline)
            asked = deadline.synthesis_timeout(attempt_timeouts[0])
            return self._invoke_injected(
                self._judge_fn,
                request,
                asked,
                True,
                timeout_configured=self._judge_timeout,
                remaining_seconds_at_entry=remaining_at_entry,
            )

        primary = self._primary_judge
        if primary is None and self._finalizer is not None:
            primary = getattr(self._finalizer, "_model", None)
        if primary is None:
            return self._clocked_judge_call(
                asked=None,
                remaining=_deadline_remaining_seconds(deadline),
                correlated=True,
                unavailable=True,
                issue="semantic judge unavailable",
            )
        if callable(primary) and not hasattr(primary, "complete"):
            remaining_at_entry = _deadline_remaining_seconds(deadline)
            asked = deadline.synthesis_timeout(attempt_timeouts[0])
            return self._invoke_injected(
                cast(JudgeFn, primary),
                request,
                asked,
                True,
                timeout_configured=self._judge_timeout,
                remaining_seconds_at_entry=remaining_at_entry,
            )
        messages = [
            {"role": "system", "content": _judge_system_prompt(request)},
            {
                "role": "user",
                "content": dumps_judge_request(request),
            },
        ]
        prior_failures_release_safe = True
        # 与 provider 分支同一本窗口余额账，见 _semantic_attempt_timeouts。
        window_left = total_window
        previous_remaining: float | None = None
        for attempt, timeout_limit in enumerate(attempt_timeouts):
            remaining_at_entry = _deadline_remaining_seconds(deadline)
            if previous_remaining is not None and remaining_at_entry is not None:
                window_left -= max(0.0, previous_remaining - remaining_at_entry)
            previous_remaining = remaining_at_entry
            attempt_timeout = deadline.synthesis_timeout(
                min(timeout_limit, max(0.0, window_left))
            )
            if attempt_timeout <= 0.001:
                failure_chain_release_safe = (
                    attempt == 0 or prior_failures_release_safe
                )
                return self._clocked_judge_call(
                    asked=attempt_timeout,
                        judge_attempt_index=attempt,
                    remaining=remaining_at_entry,
                    correlated=True,
                    unavailable=True,
                    issue="semantic judge deadline exhausted",
                    root_deadline_exhausted=True,
                    monotonic_release_safe=failure_chain_release_safe,
                )
            try:
                turn = primary.complete(
                    messages=messages,
                    tools=_JUDGE_REPORT_TOOLS,
                    timeout=attempt_timeout,
                )
            except Exception as exc:
                issue, retryable, release_safe = _stable_semantic_judge_error(
                    type(exc).__name__
                )
                should_retry = _should_retry_semantic_judge(
                    attempt,
                    retryable=retryable,
                    release_safe=release_safe,
                    prior_failures_release_safe=prior_failures_release_safe,
                    deadline=deadline,
                )
                prior_failures_release_safe &= release_safe
                if should_retry:
                    continue
                return self._clocked_judge_call(
                    asked=attempt_timeout,
                        judge_attempt_index=attempt,
                    remaining=remaining_at_entry,
                    correlated=True,
                    unavailable=True,
                    issue=issue,
                    failure=exc,
                    transient_provider_failure=prior_failures_release_safe,
                    monotonic_release_safe=prior_failures_release_safe,
                )
            if not isinstance(turn, ModelTurn):
                return self._clocked_judge_call(
                    asked=attempt_timeout,
                        judge_attempt_index=attempt,
                    remaining=remaining_at_entry,
                    correlated=True,
                    unavailable=True,
                    issue="semantic judge invalid provider response",
                )
            if turn.error:
                issue, retryable, release_safe = _stable_semantic_judge_error(
                    turn.error
                )
                should_retry = _should_retry_semantic_judge(
                    attempt,
                    retryable=retryable,
                    release_safe=release_safe,
                    prior_failures_release_safe=prior_failures_release_safe,
                    deadline=deadline,
                )
                prior_failures_release_safe &= release_safe
                if should_retry:
                    continue
                return self._clocked_judge_call(
                    asked=attempt_timeout,
                        judge_attempt_index=attempt,
                    remaining=remaining_at_entry,
                    correlated=True,
                    unavailable=True,
                    issue=issue,
                    failure=turn.error,
                    transient_provider_failure=prior_failures_release_safe,
                    monotonic_release_safe=prior_failures_release_safe,
                )
            if turn.tool_calls:
                report = self._parse_tool_report(
                    turn,
                    len(request["sentences"]),
                )
                if report is None:
                    return self._clocked_judge_call(
                        asked=attempt_timeout,
                        judge_attempt_index=attempt,
                        remaining=remaining_at_entry,
                        correlated=True,
                        unavailable=True,
                        issue="semantic judge returned an invalid tool call",
                    )
                return self._clocked_judge_call(
                    asked=attempt_timeout,
                        judge_attempt_index=attempt,
                    remaining=remaining_at_entry,
                    correlated=True,
                    unavailable=False,
                    report=report,
                    monotonic_release_safe=prior_failures_release_safe,
                )
            report = self._parse_report(turn.content, len(request["sentences"]))
            if report is None:
                return self._clocked_judge_call(
                    asked=attempt_timeout,
                        judge_attempt_index=attempt,
                    remaining=remaining_at_entry,
                    correlated=True,
                    unavailable=True,
                    issue="invalid semantic judge output",
                )
            return self._clocked_judge_call(
                asked=attempt_timeout,
                        judge_attempt_index=attempt,
                remaining=remaining_at_entry,
                correlated=True,
                unavailable=False,
                report=report,
                monotonic_release_safe=prior_failures_release_safe,
            )
        return self._clocked_judge_call(
            asked=None,
            remaining=_deadline_remaining_seconds(deadline),
            correlated=True,
            unavailable=True,
            issue="semantic judge unavailable",
        )

    @staticmethod
    def _parse_tool_report(
        turn: ModelTurn,
        sentence_count: int,
    ) -> answer_model.GroundingJudgeReport | None:
        if len(turn.tool_calls) != 1:
            return None
        call = turn.tool_calls[0]
        if call.name != _JUDGE_REPORT_TOOL_NAME:
            return None
        return SemanticEpisodeVerifier._parse_report(
            call.to_dict()["arguments"],
            sentence_count,
        )

    @staticmethod
    def _invoke_injected(
        fn: JudgeFn,
        request: dict[str, object],
        timeout: float,
        correlated: bool,
        *,
        timeout_configured: float | None = None,
        remaining_seconds_at_entry: float | None = None,
    ) -> _JudgeCall:
        configured = (
            float(timeout_configured) if timeout_configured is not None else float(timeout)
        )
        try:
            value = _call_flexible(fn, request, timeout)
        except Exception as exc:
            exc_class, http_status = _judge_failure_identity(exc)
            return _JudgeCall(
                None,
                True,
                correlated,
                f"semantic judge unavailable: {type(exc).__name__}",
                timeout_asked=timeout,
                timeout_configured=configured,
                remaining_seconds_at_entry=remaining_seconds_at_entry,
                exc_class=exc_class,
                http_status=http_status,
                judge_attempt_index=0,
            )
        report = SemanticEpisodeVerifier._parse_report(
            value,
            len(cast(list[object], request["sentences"])),
        )
        if report is None:
            return _JudgeCall(
                None,
                True,
                correlated,
                "invalid semantic judge output",
                timeout_asked=timeout,
                timeout_configured=configured,
                remaining_seconds_at_entry=remaining_seconds_at_entry,
                judge_attempt_index=0,
            )
        return _JudgeCall(
            report,
            False,
            correlated,
            monotonic_release_safe=True,
            timeout_asked=timeout,
            timeout_configured=configured,
            remaining_seconds_at_entry=remaining_seconds_at_entry,
            judge_attempt_index=0,
        )

    @staticmethod
    def _parse_report(
        value: object,
        sentence_count: int,
    ) -> answer_model.GroundingJudgeReport | None:
        try:
            if isinstance(value, answer_model.GroundingJudgeReport):
                if not isinstance(value.passed, bool):
                    return None
                rejected = value.rejected_sentence_indexes
                issues = value.issues
                if not isinstance(rejected, tuple) or any(
                    isinstance(index, bool) or not isinstance(index, int)
                    for index in rejected
                ):
                    return None
                if not isinstance(issues, tuple) or any(
                    not isinstance(issue, str) for issue in issues
                ):
                    return None
                if value.passed == bool(rejected):
                    return None
                if any(index < 1 or index > sentence_count for index in rejected):
                    return None
                return _reconcile_issue_sentence_indexes(value, sentence_count)
            if isinstance(value, ModelTurn):
                if value.error or value.tool_calls:
                    return None
                value = value.content
            elif isinstance(value, tuple) and value:
                # Provider seams may return ``(content, provider, reason)``.
                value = value[0]
            if isinstance(value, Mapping):
                payload = dict(value)
            elif isinstance(value, str):
                # Accept either one bare JSON object or exactly one JSON code
                # fence.  Some OpenAI-compatible models wrap schema-perfect
                # JSON even when instructed not to.  Surrounding prose and
                # trailing text remain invalid.
                serialized = value.strip()
                fenced = _STRICT_JSON_FENCE_RE.fullmatch(serialized)
                if fenced is not None:
                    serialized = fenced.group("body")
                payload = json.loads(serialized)
            else:
                return None
            if not isinstance(payload, dict) or set(payload) != {
                "passed",
                "rejected_sentence_indexes",
                "issues",
            }:
                return None
            passed = payload["passed"]
            rejected_raw = payload["rejected_sentence_indexes"]
            issues_raw = payload["issues"]
            if not isinstance(passed, bool):
                return None
            if not isinstance(rejected_raw, list) or any(
                isinstance(index, bool) or not isinstance(index, int)
                for index in rejected_raw
            ):
                return None
            if not isinstance(issues_raw, list) or any(
                not isinstance(issue, str) for issue in issues_raw
            ):
                return None
            canonical = json.dumps(payload, ensure_ascii=False)
            report = answer_model.parse_grounding_judge_report(
                canonical,
                sentence_count=sentence_count,
            )
            if report is None:
                return None
            return _reconcile_issue_sentence_indexes(report, sentence_count)
        except Exception:
            return None

    def _apply_unattempted_claim_rewrite(
        self,
        frame: TaskFrame,
        structural: VerifiedEpisodeOutcome,
    ) -> tuple[VerifiedEpisodeOutcome, tuple[str, ...], int]:
        asked_date = last_explicit_iso_date(frame.raw_question)
        claims = find_unattempted_claims(
            structural.outcome.draft,
            structural.outcome.traces,
            asked_date=asked_date,
        )
        if not claims:
            return structural, (), 0
        rewritten = rewrite_unattempted_claims(structural.outcome.draft, claims)
        if rewritten != structural.outcome.draft:
            structural = replace(
                structural,
                outcome=replace(structural.outcome, draft=rewritten),
            )
        issues = tuple(
            f"code=unattempted_claim :: 本次未查询 {claim.capability}"
            + (f" {claim.asked_date}" if claim.asked_date else "")
            for claim in claims
        )
        return structural, issues, len(claims)

    def _apply_kb_gap_proof_rewrite(
        self,
        structural: VerifiedEpisodeOutcome,
    ) -> VerifiedEpisodeOutcome:
        rewritten = rewrite_unverified_kb_gap_claims(
            structural.outcome.draft,
            structural.outcome.traces,
        )
        if rewritten == structural.outcome.draft:
            return structural
        return replace(
            structural,
            outcome=replace(structural.outcome, draft=rewritten),
        )

    def _withhold_public_source(
        self,
        before: str,
        rejected_sentence_indexes: tuple[int, ...],
    ) -> tuple[str, str, tuple[str, ...]]:
        minus = (
            _drop_rejected_sentences(before, rejected_sentence_indexes)
            if rejected_sentence_indexes
            else ""
        )
        public_source, mode = choose_repair_rollback(before, minus)
        extra: tuple[str, ...] = ()
        if mode == "whole_pre_repair" and rejected_sentence_indexes:
            extra = (
                "code=repair_collapsed_to_stub :: "
                "已回退至未经语义修复的稿，其中含 "
                f"{len(rejected_sentence_indexes)} 条未通过判官的表述",
            )
        return public_source, mode, extra

    def _maybe_withhold_stub(
        self,
        frame: TaskFrame,
        *,
        source: VerifiedEpisodeOutcome,
        wiped: VerifiedEpisodeOutcome,
        rejected_sentence_indexes: tuple[int, ...],
        judge_issues: tuple[str, ...],
        correlated_judge: bool,
        call: _JudgeCall | None,
    ) -> SemanticEpisodeOutcome | None:
        if not repair_collapsed_to_stub(
            source.outcome.draft,
            wiped.outcome.draft,
            frame.question_type,
        ):
            return None
        return self._emit_withheld_repair(
            frame,
            source=source,
            rejected_sentence_indexes=rejected_sentence_indexes,
            judge_issues=judge_issues,
            correlated_judge=correlated_judge,
            call=call,
            collapsed=True,
        )

    def _maybe_withhold_after_repair(
        self,
        frame: TaskFrame,
        *,
        source: VerifiedEpisodeOutcome,
        wiped: VerifiedEpisodeOutcome,
        rejected_sentence_indexes: tuple[int, ...],
        marker_loss: tuple[str, ...],
        judge_issues: tuple[str, ...],
        correlated_judge: bool,
        call: _JudgeCall | None,
        issue_code: str,
        issue_message: str,
    ) -> SemanticEpisodeOutcome | None:
        if marker_loss:
            return self._marker_loss_or_withhold(
                frame,
                source=source,
                wiped=wiped,
                marker_loss=marker_loss,
                judge_issues=judge_issues,
                correlated_judge=correlated_judge,
                call=call,
                issue_code=issue_code,
                issue_message=issue_message,
                rejected_sentence_indexes=rejected_sentence_indexes,
            )
        return self._maybe_withhold_stub(
            frame,
            source=source,
            wiped=wiped,
            rejected_sentence_indexes=rejected_sentence_indexes,
            judge_issues=judge_issues,
            correlated_judge=correlated_judge,
            call=call,
        )

    def _emit_withheld_repair(
        self,
        frame: TaskFrame,
        *,
        source: VerifiedEpisodeOutcome,
        rejected_sentence_indexes: tuple[int, ...],
        judge_issues: tuple[str, ...],
        correlated_judge: bool,
        call: _JudgeCall | None,
        collapsed: bool,
    ) -> SemanticEpisodeOutcome:
        public_source, mode, extra_issues = self._withhold_public_source(
            source.outcome.draft,
            rejected_sentence_indexes,
        )
        public = _sanitize_public_answer(
            public_source,
            source.outcome.evidence,
            source.outcome.traces,
        )
        issues = tuple(dict.fromkeys((*judge_issues, *extra_issues)))
        if not public:
            outcome = SemanticEpisodeOutcome(
                verified=source,
                status="partial",
                public_answer=self._gap_answer(frame, source),
                judge_status="repaired",
                issues=issues,
                correlated_judge=correlated_judge,
                gap_output_ids=(),
                repair_withheld=True,
                repair_collapsed_to_stub=collapsed,
                repair_rollback_mode=mode,
            )
        else:
            outcome = SemanticEpisodeOutcome(
                verified=source,
                status="partial",
                public_answer=view(
                    TerminalFacts(cause=CAUSE_VERIFIED, public=public)
                ),
                judge_status="repaired",
                issues=issues,
                correlated_judge=correlated_judge,
                gap_output_ids=(),
                repair_withheld=True,
                repair_collapsed_to_stub=collapsed,
                repair_rollback_mode=mode,
            )
        return self._finalize_outcome(
            outcome,
            call,
            repair_collapsed_to_stub=collapsed,
            repair_rollback_mode=mode,
        )

    def _repair(
        self,
        *,
        frame: TaskFrame,
        structural: VerifiedEpisodeOutcome,
        rejected_sentence_indexes: tuple[int, ...],
    ) -> tuple[VerifiedEpisodeOutcome, TaskFrame] | None:
        contract = structural.contract
        if contract is None:
            return None
        original = structural.outcome
        draft = _drop_rejected_sentences(
            original.draft,
            rejected_sentence_indexes,
        )
        if not draft:
            return None
        # 先按槽补回被连坐的真值，再算缺口。补回成功时缺口自然为空
        # （真值已在稿里）；缺口这条留作兜底——补不回来时它仍会记账，
        # 不让真值静默消失。
        draft, _restored = _restore_lost_observations(
            draft=draft,
            before=original.draft,
            evidence=original.evidence,
        )
        gaps = _gaps_with_lost_observations(
            gaps=original.gaps,
            before=original.draft,
            after=draft,
            evidence=original.evidence,
        )
        repaired_outcome = AgentOutcome(
            task_frame_hash=original.task_frame_hash,
            status=original.status,
            draft=draft,
            evidence=original.evidence,
            traces=original.traces,
            gaps=gaps,
            stop_reason="semantic_repair",
            events=original.events,
            bindings=original.bindings,
            usage=original.usage,
        )
        if repaired_outcome.task_frame_hash != frame.task_frame_hash:
            return None
        try:
            verified = verify_episode_outcome(contract, repaired_outcome)
        except Exception:
            return None
        return verified, frame

    def _completed_public(
        self,
        frame: TaskFrame,
        verified: VerifiedEpisodeOutcome,
        *,
        judge_status: Literal["passed", "repaired"],
        judge_issues: tuple[str, ...] = (),
        correlated_judge: bool = False,
        call: _JudgeCall | None = None,
    ) -> SemanticEpisodeOutcome:
        public = _sanitize_public_answer(
            verified.outcome.draft,
            verified.outcome.evidence,
            verified.outcome.traces,
        )
        if not public:
            outcome = SemanticEpisodeOutcome(
                verified=verified,
                status="partial",
                public_answer=self._gap_answer(frame, verified),
                judge_status=judge_status,
                issues=tuple(dict.fromkeys((*judge_issues, "public projection empty"))),
                correlated_judge=correlated_judge,
            )
        else:
            outcome = SemanticEpisodeOutcome(
                verified=verified,
                status=(
                    "completed"
                    if (
                        verified.verified_status == "completed"
                        or _contract_slots_all_fulfilled(verified)
                    )
                    else "partial"
                ),
                public_answer=view(
                    TerminalFacts(cause=CAUSE_VERIFIED, public=public)
                ),
                judge_status=judge_status,
                issues=judge_issues,
                correlated_judge=correlated_judge,
            )
        return self._finalize_outcome(outcome, call)

    def _marker_loss_or_withhold(
        self,
        frame: TaskFrame,
        *,
        source: VerifiedEpisodeOutcome,
        wiped: VerifiedEpisodeOutcome,
        marker_loss: tuple[str, ...],
        judge_issues: tuple[str, ...],
        correlated_judge: bool,
        call: _JudgeCall | None,
        issue_code: str,
        issue_message: str,
        rejected_sentence_indexes: tuple[int, ...] = (),
    ) -> SemanticEpisodeOutcome:
        """Keep the pre-repair draft when deletion would empty every required slot.

        Flagged-sentence rollback belongs to the stub path, not this one: C3
        withholds because the remainder lost required-slot substance, so
        publishing that remainder would recreate the wipe.
        """

        if _repair_wiped_all_required(source.contract, marker_loss):
            collapsed = repair_collapsed_to_stub(
                source.outcome.draft,
                wiped.outcome.draft,
                frame.question_type,
            )
            return self._emit_withheld_repair(
                frame,
                source=source,
                rejected_sentence_indexes=(),
                judge_issues=tuple(
                    dict.fromkeys(
                        (
                            *judge_issues,
                            f"code={issue_code} :: {issue_message}",
                        )
                    )
                ),
                correlated_judge=correlated_judge,
                call=call,
                collapsed=collapsed,
            )
        return self._marker_loss_partial_public(
            frame,
            wiped,
            marker_loss,
            judge_issues=judge_issues,
            correlated_judge=correlated_judge,
            call=call,
        )

    def _marker_loss_partial_public(
        self,
        frame: TaskFrame,
        verified: VerifiedEpisodeOutcome,
        output_ids: tuple[str, ...],
        *,
        judge_issues: tuple[str, ...],
        correlated_judge: bool,
        call: _JudgeCall | None = None,
    ) -> SemanticEpisodeOutcome:
        """Keep reviewed remainder; required slots degrade instead of vanishing."""

        verified = _shrink_verified_for_marker_loss(verified, output_ids)
        public = _sanitize_public_answer(
            remove_lost_output_scaffolding(
                verified.outcome.draft,
                output_ids,
            ),
            verified.outcome.evidence,
            verified.outcome.traces,
        )
        descriptions = {
            item.output_id: item.description.strip() or item.output_id
            for item in (
                verified.contract.required_outputs if verified.contract else ()
            )
        }
        labels = tuple(
            dict.fromkeys(
                descriptions.get(output_id, output_id)
                for output_id in output_ids
            )
        )
        if not public:
            outcome = SemanticEpisodeOutcome(
                verified=verified,
                status="partial",
                public_answer=view(TerminalFacts(cause=CAUSE_VERIFIED, public="")),
                judge_status="repaired",
                issues=judge_issues,
                correlated_judge=correlated_judge,
                gap_output_ids=output_ids,
            )
            return self._finalize_outcome(outcome, call)
        annotated = _with_required_output_degrade_mark(public, labels)
        outcome = SemanticEpisodeOutcome(
            verified=verified,
            status="partial",
            public_answer=view(
                TerminalFacts(cause=CAUSE_VERIFIED, public=annotated)
            ),
            judge_status="repaired",
            issues=judge_issues,
            correlated_judge=correlated_judge,
            gap_output_ids=output_ids,
        )
        return self._finalize_outcome(outcome, call)

    @staticmethod
    def _gap_answer(
        frame: TaskFrame,
        verified: VerifiedEpisodeOutcome,
        *,
        judge_unavailable: bool = False,
    ) -> str:
        """缺数三档的中间档：缺 X → 仍可判 Y → 验证窗口 Z。

        原版只说「证据不足 + 仍需核验 X」——把「一格没核验」和「全军覆没」
        呈现成同一句话，用户无从知道本轮其实已经核验了什么（knevo 对照里
        「从不输出裸的不知道」那条；08-01 验收 C 组的诚实度失分同源）。

        「仍可判 Y」的取材红线：**只用结构性事实**——契约里的槽位描述、
        binding 里去重后的证据哈希数、证据的来源日期。普通 ``evidence_gap``
        一个字都不从 draft 捞。``invalid_repair_finish`` 且证据非空改走
        ``verification_incomplete``：已兑现槽在拒稿前写入 ``public=``，未兑现
        槽交给 ``unknown_slots``，由 ``view()`` 渲成用户语言。
        """

        question = frame.raw_question.strip() or "当前问题"
        if judge_unavailable:
            # 禁语在下面的 evidence 分支，不看 cause。判官挂了必须改这条
            # body，不能只改开口。
            parts: list[str] = []
            evidence = verified.outcome.evidence
            if evidence:
                parts.append(
                    f"本轮已取得 {len(evidence)} 条证据，暂不对外引用；可直接重试。"
                )
            window = _latest_evidence_date(evidence)
            if window:
                parts.append(f"证据数据截至 {window}。")
            return view(
                TerminalFacts(
                    cause=CAUSE_JUDGE_UNAVAILABLE_HELD,
                    question=question,
                    gap_body="".join(parts),
                )
            )
        # 首句成因不跟 ASK_DEGRADED_FALLBACK：模型没服务成时不能写成「证据不足」。
        # invalid_repair_finish + 证据非空不是「没查到」，不得贴 evidence_gap。
        incomplete_repair = (
            str(verified.outcome.stop_reason or "") == "invalid_repair_finish"
            and bool(verified.outcome.evidence)
        )
        if is_model_service_unavailable(verified):
            cause = CAUSE_MODEL_UNAVAILABLE
        elif incomplete_repair:
            cause = CAUSE_VERIFICATION_INCOMPLETE
        else:
            cause = CAUSE_EVIDENCE_GAP
        contract = verified.contract
        if contract is None:
            return view(TerminalFacts(cause=cause, question=question))
        status_by_id = {
            item.output_id: item.status for item in verified.completion.outputs
        }
        required = tuple(
            item for item in contract.required_outputs if item.required
        )
        missing = tuple(
            item
            for item in required
            if status_by_id.get(item.output_id) != "fulfilled"
        )
        targets = missing or required
        labels = tuple(
            dict.fromkeys(
                _gap_label(item) for item in targets if _gap_label(item)
            )
        )
        bound_counts = {
            binding.output_id: len(dict.fromkeys(binding.evidence_hashes))
            for binding in verified.outcome.bindings
            if binding.evidence_hashes
        }
        kept = tuple(
            (_gap_label(item), bound_counts[item.output_id])
            for item in required
            if status_by_id.get(item.output_id) == "fulfilled"
            and bound_counts.get(item.output_id)
        )
        parts: list[str] = []
        if cause != CAUSE_VERIFICATION_INCOMPLETE and labels:
            parts.append("仍需核验：" + "、".join(labels[:3]) + "。")
        if kept:
            parts.append(
                "本轮已核验（供参考，不构成完整结论）："
                + "、".join(
                    f"{label}（{count} 条证据）" for label, count in kept[:3]
                )
                + "。"
            )
        elif verified.outcome.evidence:
            # LLM 超时 / deadline 打断时常见的形状：检索已完成、证据在手，
            # 但没走到 FINAL_JSON，一条都没绑定（08-12 A5 实测：25 条证据、
            # repair_model_unavailable、草稿空）。条数是结构性事实，说出来
            # 让用户区分「没查到」和「查到了没来得及核验」——两者的下一步
            # 完全不同（换问法 vs 直接重试）。
            parts.append(
                f"本轮已取得 {len(verified.outcome.evidence)} 条证据，"
                "但未完成核验绑定，暂不能引用；可直接重试。"
            )
        window = _latest_evidence_date(verified.outcome.evidence)
        if window:
            parts.append(f"证据数据截至 {window}；缺口补齐后可复验。")
        # ASK_DEGRADED_FALLBACK（默认 off）：knevo q13 七项里的「尝试过什么 /
        # 来源标注不降级」两段，确定性渲染，off 时空串、本函数输出逐字节不变。
        transparency = gap_transparency(verified)
        if transparency:
            parts.append(transparency)
        public = ""
        unknown_slots: tuple[str, ...] = ()
        if cause == CAUSE_VERIFICATION_INCOMPLETE:
            unknown_slots = labels
            if kept:
                public = str(verified.outcome.draft or "").strip()
        return view(
            TerminalFacts(
                cause=cause,
                question=question,
                public=public,
                gap_body="".join(parts),
                unknown_slots=unknown_slots,
            )
        )

    @staticmethod
    def _generic_gap_answer(frame: TaskFrame) -> str:
        question = frame.raw_question.strip() or "当前问题"
        return view(
            TerminalFacts(cause=CAUSE_EVIDENCE_GAP, question=question)
        )


def _gap_label(item) -> str:
    """gap 答案里的槽位标签：描述只取首个分句。

    契约描述现在是给模型看的完整要求（#293 起带「写出具体数值……不得只作
    定性概括」的长指令），整段引用会把面向模型的指令文本原样打到用户可见的
    gap 答案里（08-12 A 组第二轮实测：A1 的 gap 答案变成一屏指令）。
    首个分句（「；」「，」之前）是描述的名词性主干，够定位、不带指令。
    """

    text = str(item.description or "").strip()
    if text:
        return re.split(r"[；，;,]", text, maxsplit=1)[0].strip()
    return str(item.output_id or "").strip()


def _latest_evidence_date(evidence: tuple) -> str:
    """本轮证据的最新来源日期（YYYY-MM-DD），没有合法日期返回空串。

    只认 ISO 形状的前 10 位：source_date 是自由文本字段，旧 runner 会填
    「日期+媒体」之类的混合串，直接 max() 会把非日期串比进来。
    """

    dates = sorted(
        value[:10]
        for item in evidence
        if (value := str(getattr(item, "source_date", "") or ""))
        and _ISO_DATE_RE.match(value[:10])
    )
    return dates[-1] if dates else ""


_ISO_DATE_RE = re.compile(r"^20\d{2}-\d{2}-\d{2}$")
_MARKER_LOSS_GAP = "semantic repair removed required output"
REQUIRED_OUTPUT_DEGRADED_MARK = "【质检降级】"


def _required_output_degraded_note(labels: tuple[str, ...]) -> str:
    # 控制面用。公开稿不得拼接这一行。
    if not labels:
        return ""
    return (
        f"{REQUIRED_OUTPUT_DEGRADED_MARK}"
        "部分必答格核验后不完整，残块保留，判断强度已降级。"
    )


def _with_required_output_degrade_mark(
    public: str,
    labels: tuple[str, ...],
) -> str:
    del labels
    return str(public or "")


def _shrink_verified_for_marker_loss(
    verified: VerifiedEpisodeOutcome,
    output_ids: tuple[str, ...],
) -> VerifiedEpisodeOutcome:
    """Contract lost public cells so they are no longer structurally fulfilled."""

    lost = tuple(
        dict.fromkeys(
            output_id.strip() for output_id in output_ids if output_id.strip()
        )
    )
    if not lost:
        return verified

    known_outputs = {item.output_id for item in verified.completion.outputs}
    known_bindings = {item.output_id for item in verified.outcome.bindings}
    actionable = tuple(
        output_id
        for output_id in lost
        if output_id in known_outputs or output_id in known_bindings
    )
    if not actionable:
        return verified

    actionable_set = frozenset(actionable)
    new_outputs = tuple(
        replace(
            item,
            status="missing",
            evidence_ids=(),
            gap=item.gap or _MARKER_LOSS_GAP,
        )
        if item.output_id in actionable_set
        else item
        for item in verified.completion.outputs
    )
    new_bindings: list[OutputEvidenceBinding] = []
    seen: set[str] = set()
    for binding in verified.outcome.bindings:
        seen.add(binding.output_id)
        if binding.output_id in actionable_set:
            new_bindings.append(
                replace(
                    binding,
                    evidence_hashes=(),
                    gap=binding.gap or _MARKER_LOSS_GAP,
                )
            )
        else:
            new_bindings.append(binding)
    for output_id in actionable:
        if output_id not in seen:
            new_bindings.append(
                OutputEvidenceBinding(output_id, (), _MARKER_LOSS_GAP)
            )

    extra_issues = tuple(
        Issue(
            IssueCode.MARKER_LOSS,
            output_id,
            f"{_MARKER_LOSS_GAP}: {output_id}",
        )
        for output_id in actionable
    )
    return replace(
        verified,
        outcome=replace(verified.outcome, bindings=tuple(new_bindings)),
        completion=replace(
            verified.completion,
            status="partial",
            outputs=new_outputs,
            factual_grounding="partial",
            task_coverage="partial",
            business_status="partial",
        ),
        verified_status="partial",
        missing_outputs=tuple(dict.fromkeys((*verified.missing_outputs, *actionable))),
        issue_items=tuple(dict.fromkeys((*verified.issue_items, *extra_issues))),
    )


def _gap_task_context(frame: TaskFrame) -> str:
    return {
        "valuation_estimate": "估值",
        "market_forecast": "市场预测",
        "market_cause": "原因归因",
        "market_mainline": "市场主线",
    }.get(frame.question_type, "")


def _contract_slots_all_fulfilled(verified: VerifiedEpisodeOutcome) -> bool:
    """True when every contracted slot is fulfilled and the structure has no issue.

    This is the 2026-08-19 production shape: runtime declared partial
    (``deadline_exhausted``) while bindings, coverage and draft were already
    complete. Structural verification never upgrades runtime status; after a
    judge pass the semantic gate may report completed — the deadline is an
    operational fact, not a missing required output.
    """

    if not verified.outcome.draft.strip():
        return False
    if verified.issue_items:
        return False
    if verified.completion.factual_grounding != "fulfilled":
        return False
    if verified.completion.task_coverage != "fulfilled":
        return False
    required_ids = {
        item.output_id
        for item in (verified.contract.required_outputs if verified.contract else ())
        if item.required
    }
    outputs = verified.completion.outputs
    if required_ids:
        return all(
            item.status == "fulfilled"
            for item in outputs
            if item.output_id in required_ids
        )
    return any(item.status == "fulfilled" for item in outputs)


def _can_semantically_release_partial(
    verified: VerifiedEpisodeOutcome,
) -> bool:
    """Allow a useful partial through the judge without weakening hard gates.

    Eligible issues are the ones where至少一个槽位已凭真实证据履行、缺口本身
    可以诚实呈现：模型自报 gap、强制能力未绑上、以及证据**类型白名单**问题
    （混绑已在结构层剔除非法哈希，整格非法则该槽已判 missing——两种情况下
    正文引用的仍是证据池里真实采集的内容）。Unknown hashes、伪造、frame
    mismatch、财务锚地板（FINANCIAL_ANCHOR_MISSING）等其余结构问题仍在语义
    裁判看到草稿之前 fail closed。放行只查 ``Issue.code`` / ``RELEASE_POLICY``，
    不匹配文案。
    """

    if verified.verified_status != "partial":
        return False
    if not verified.outcome.draft.strip():
        return False
    if not any(
        item.status == "fulfilled" for item in verified.completion.outputs
    ):
        return False
    if verified.outcome.status == "partial" and _contract_slots_all_fulfilled(
        verified
    ):
        return True
    return allows_partial_release(verified.issue_items)


def _numbered_sentences(draft: str) -> list[dict[str, object]]:
    sentences: list[dict[str, object]] = []
    for raw in _SENTENCE_RE.split(str(draft or "")):
        text = raw.strip()
        if not text:
            continue
        sentences.append({"index": len(sentences) + 1, "text": text})
    return sentences


def _reconcile_issue_sentence_indexes(
    report: answer_model.GroundingJudgeReport,
    sentence_count: int,
) -> answer_model.GroundingJudgeReport:
    """Keep the judge's parallel index/issue fields internally consistent.

    Some OpenAI-compatible models correctly describe every rejected sentence
    in ``issues`` but omit one of those indexes from the sibling integer list.
    The judge contract says issues describe only rejected sentences, so an
    explicit ``句N``/``Sentence N`` reference is itself a rejection signal.
    Adding that existing index can only narrow the draft; it never adds facts
    or upgrades a result.
    """

    if report.passed:
        return report
    rejected = set(report.rejected_sentence_indexes)
    for issue in report.issues:
        for match in _ISSUE_SENTENCE_INDEX_RE.finditer(issue):
            raw = next((group for group in match.groups() if group), "")
            if not raw:
                continue
            index = int(raw)
            if 1 <= index <= sentence_count:
                rejected.add(index)
    canonical = tuple(sorted(rejected))
    if canonical == report.rejected_sentence_indexes:
        return report
    return answer_model.GroundingJudgeReport(
        passed=False,
        rejected_sentence_indexes=canonical,
        issues=report.issues,
    )


def _apply_numeric_condition_gate(
    call: _JudgeCall,
    sentences: list[dict[str, object]],
    verified: VerifiedEpisodeOutcome,
) -> _JudgeCall:
    """Augment a model report with deterministic novel-threshold rejection.

    The model remains responsible for semantic entailment.  This narrow gate
    catches one correlated-judge failure observed in the real canary: a
    conditional sentence introduced a numeric threshold that did not occur in
    any evidence bound to the answer.  Dates, list labels, requested baseline
    estimates, and numeric anchors present in bound evidence are unaffected.
    """

    report = call.report
    if report is None:
        return call
    rejected = set(report.rejected_sentence_indexes)
    rejected.update(_novel_numeric_condition_indexes(sentences, verified))
    if rejected == set(report.rejected_sentence_indexes):
        return call
    issues = tuple(dict.fromkeys((*report.issues, _NUMERIC_CONDITION_ISSUE.message)))
    return replace(
        call,
        report=answer_model.GroundingJudgeReport(
            passed=False,
            rejected_sentence_indexes=tuple(sorted(rejected)),
            issues=issues,
        ),
    )


def v8_semantic_degrade_enabled() -> bool:
    """Rollback gate. Default on. Off folds every index into mechanical."""

    raw = str(os.environ.get("FINANCE_V8_SEMANTIC_DEGRADE", "1")).strip().lower()
    return raw not in {"0", "false", "off", "no"}


def _unresolved_evidence_ordinal_indexes(
    sentences: list[dict[str, object]],
    verified: VerifiedEpisodeOutcome,
) -> tuple[int, ...]:
    """Code-produced table-out-of-range E citations. Never parse LLM copy."""

    known = frozenset(evidence_ordinal_table(verified.outcome.evidence).values())
    rejected: list[int] = []
    for item in sentences:
        index = item.get("index")
        text = str(item.get("text") or "")
        if not isinstance(index, int):
            continue
        cited = cited_evidence_ordinals(text)
        if cited and any(token not in known for token in cited):
            rejected.append(index)
    return tuple(rejected)


def _mechanical_sentence_indexes(
    sentences: list[dict[str, object]],
    verified: VerifiedEpisodeOutcome,
) -> frozenset[int]:
    return frozenset(
        (
            *_novel_numeric_condition_indexes(sentences, verified),
            *_mismatched_weekday_indexes(sentences, verified),
            *_mismatched_path_trend_indexes(sentences, verified),
            *_unresolved_evidence_ordinal_indexes(sentences, verified),
        )
    )


def _partition_rejected_indexes(
    rejected: tuple[int, ...],
    *,
    sentences: list[dict[str, object]],
    verified: VerifiedEpisodeOutcome,
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Split rejected indexes into (mechanical, semantic). Code-produced only."""

    canonical = tuple(
        sorted({int(index) for index in rejected if int(index) >= 1})
    )
    if not v8_semantic_degrade_enabled():
        return canonical, ()
    mechanical_set = _mechanical_sentence_indexes(sentences, verified)
    mechanical = tuple(index for index in canonical if index in mechanical_set)
    semantic = tuple(index for index in canonical if index not in mechanical_set)
    return mechanical, semantic


def _apply_unresolved_evidence_ordinal_gate(
    call: _JudgeCall,
    sentences: list[dict[str, object]],
    verified: VerifiedEpisodeOutcome,
) -> _JudgeCall:
    """Fail-closed when the judge passed a table-out-of-range E citation.

    When the judge already rejected some indexes, do not add extra E indexes:
    sequential mechanical rejudge (C cluster / W1 ④) keeps one-at-a-time
    deletion. Intersection with the partitioner still classifies the rejected
    E indexes as mechanical.
    """

    report = call.report
    if report is None:
        return call
    unresolved = set(_unresolved_evidence_ordinal_indexes(sentences, verified))
    if not unresolved:
        return call
    rejected = set(report.rejected_sentence_indexes)
    if report.passed:
        rejected.update(unresolved)
    if rejected == set(report.rejected_sentence_indexes):
        return call
    issues = tuple(
        dict.fromkeys((*report.issues, _UNRESOLVED_EVIDENCE_ISSUE.serialize()))
    )
    return replace(
        call,
        report=answer_model.GroundingJudgeReport(
            passed=False,
            rejected_sentence_indexes=tuple(sorted(rejected)),
            issues=issues,
        ),
    )


def _required_grounded_output_ids(contract: object) -> frozenset[str]:
    """Same membership `_lost_grounded_output_substance` cares about."""

    ids: set[str] = set()
    for item in getattr(contract, "required_outputs", ()):
        if not getattr(item, "required", True):
            continue
        output_id = str(getattr(item, "output_id", ""))
        mode = str(getattr(item, "grounding_mode", "evidence"))
        if mode == "evidence" or (
            output_id in JUDGMENT_OUTPUT_IDS and mode == "model_reasoning"
        ):
            ids.add(output_id)
    return frozenset(ids)


def _sentence_in_required_grounded_block(
    sentence_text: str,
    contract: object,
) -> bool:
    required = _required_grounded_output_ids(contract)
    if not required:
        return False
    other_ids = tuple(
        str(getattr(item, "output_id", ""))
        for item in getattr(contract, "required_outputs", ())
        if str(getattr(item, "output_id", ""))
        and str(getattr(item, "output_id", "")) not in required
    )
    if other_ids and any(
        answer_has_output_marker(output_id, sentence_text) for output_id in other_ids
    ):
        if not any(
            answer_has_output_marker(output_id, sentence_text) for output_id in required
        ):
            return False
    return True


def _annotate_semantic_rejects(
    public: str,
    semantic_texts: tuple[str, ...],
) -> str:
    """存疑句不再盖章。标记只允许出现在 issues / 控制面。"""

    del semantic_texts
    return str(public or "")


def _semantic_degrade_labels(verified: VerifiedEpisodeOutcome) -> tuple[str, ...]:
    contract = verified.contract
    required = _required_grounded_output_ids(contract)
    if not required:
        return ()
    descriptions = {
        item.output_id: item.description.strip() or item.output_id
        for item in (contract.required_outputs if contract is not None else ())
    }
    return tuple(
        dict.fromkeys(descriptions.get(output_id, output_id) for output_id in required)
    )


_META_DISCLOSURE_RE = re.compile(
    r"映射为推理层|视角层推断|视角层判断|属于?推理层|原文未覆盖|语料未覆盖"
)
# 带具体价值断言的句子不豁免：披露句只允许降低断言强度，不允许顺带夹带行情事实。
_META_DISCLOSURE_VALUE_RE = re.compile(
    r"[0-9]+(?:\.[0-9]+)?\s*(?:%|％|亿|万元|万手|元|倍|家|个点)|涨停|跌停|新高|新低"
)


def _is_meta_disclosure(sentence: str) -> bool:
    text = str(sentence or "")
    return bool(_META_DISCLOSURE_RE.search(text)) and not _META_DISCLOSURE_VALUE_RE.search(text)


def _apply_meta_disclosure_exemption(
    call: _JudgeCall,
    sentences: list[dict[str, object]],
) -> _JudgeCall:
    """豁免「答案对自身证据边界/推理层级的披露句」的判定拒绝。

    这类句子（如“KOL原文未覆盖8月盘面，映射为推理层”）是视角层按规则输出的
    诚实声明，作用是降低断言强度；证据注册表里结构性不存在“语料覆盖范围”
    这类证据，按外部事实句审查等于要求它必死，repair 随之把对用户最有价值的
    边界声明从公开答案里删掉（2026-08-19 生产 run 实锤）。带具体行情数字或
    涨跌停等价值断言的句子不豁免，防止借披露句夹带事实。
    """

    report = call.report
    if report is None or not report.rejected_sentence_indexes:
        return call
    text_by_index = {int(item["index"]): str(item["text"]) for item in sentences}
    exempted = {
        index
        for index in report.rejected_sentence_indexes
        if _is_meta_disclosure(text_by_index.get(int(index), ""))
    }
    if not exempted:
        return call
    kept = tuple(
        index for index in report.rejected_sentence_indexes if index not in exempted
    )
    kept_issues = tuple(
        issue
        for issue in report.issues
        if not any(f"第{index}句" in issue for index in exempted)
    )
    return replace(
        call,
        report=answer_model.GroundingJudgeReport(
            passed=not kept,
            rejected_sentence_indexes=kept,
            issues=kept_issues,
        ),
    )


def _apply_optional_rejudge_deadline(
    call: _JudgeCall,
    deadline: ResearchDeadline,
) -> _JudgeCall:
    """Classify only genuine root-deadline exhaustion as releasable.

    A valid late rejection remains useful and must narrow the draft. A valid
    late pass cannot authorize work after the hard boundary, but the earlier
    completed report still permits monotonic deletion-only release. Malformed,
    configuration-invalid, and bad-tool responses retain their original
    failure identity even when they happen to return after the clock expires.
    """

    if call.root_deadline_exhausted or not deadline.expired:
        return call
    if call.report is not None and not call.report.passed:
        return call
    if call.report is not None and call.report.passed:
        return replace(
            call,
            report=None,
            unavailable=True,
            issue="semantic judge deadline exhausted",
            root_deadline_exhausted=True,
        )
    return call


def _optional_rejudge_allows_monotonic_release(call: _JudgeCall) -> bool:
    """Allow only budget expiry or a classified transient after a full review."""

    return (
        call.report is None
        and call.monotonic_release_safe
        and (
            call.root_deadline_exhausted
            or call.transient_provider_failure
        )
    )


def _novel_numeric_condition_indexes(
    sentences: list[dict[str, object]],
    verified: VerifiedEpisodeOutcome,
) -> tuple[int, ...]:
    """Return conditional sentences containing quantities absent from evidence."""

    contract = verified.contract
    if contract is not None and contract.required_outputs:
        # 整体豁免问的是「这份契约是不是压根不靠证据」，所以**保留** required
        # 过滤：prior_recall / prime_* 这类可选 advisory 槽签的不是 evidence，
        # 但它们不该把一份必需槽全 evidence 的契约说成 evidence-free。下面那块
        # 条件槽豁免问的是另一个问题，故不带这个过滤——两块不对称是有意的，
        # 别为了「统一风格」把这里也放宽。
        if all(
            item.grounding_mode != "evidence"
            for item in contract.required_outputs
            if item.required
        ):
            return ()
        # 条件槽粒度豁免：契约把前瞻假设槽（情景/持续/证伪条件）签成
        # model_reasoning 时，条件句里的新阈值是模型受契约委托提出的判断，
        # 不再按「证据里没有的数量」连坐整句。此前门禁只认「全契约非
        # evidence」的整体豁免，混合契约（如 market_forecast 带 evidence 的
        # 边界槽）下证伪阈值必死。事实句仍由语义判官逐句审。
        #
        # 这里**不看 required**：required 回答「缺了算不算失败」，grounding_mode
        # 回答「谁授权这个阈值」，是两根正交的轴，豁免只该看后者。装配层给前瞻
        # 信号题挂的可选前瞻槽（required=False + model_reasoning）因此同享豁免
        # ——否则契约明示「你可以在这格提阈值」、运行时照删，等于授权没传到执行
        # 者手上（R-20260824-20）。混合签约仍由下面的 all() 一票否决向证据侧。
        condition_items = tuple(
            item
            for item in contract.required_outputs
            if item.output_id in FORWARD_HYPOTHESIS_OUTPUT_IDS
        )
        if condition_items and all(
            item.grounding_mode != "evidence" for item in condition_items
        ):
            return ()

    rejected: set[int] = set()
    evidence_quantities = _bound_evidence_quantities(verified.outcome)
    for item in sentences:
        index = item.get("index")
        text = str(item.get("text") or "")
        if not isinstance(index, int):
            continue
        candidate = _DATE_TOKEN_RE.sub("", text)
        candidate = _LEADING_SECTION_RE.sub("", candidate)
        candidate = _LEADING_LIST_LABEL_RE.sub("", candidate)
        candidate = _LEADING_CONDITION_LABEL_RE.sub("", candidate)
        trigger = _CONDITION_TRIGGER_RE.search(candidate)
        if trigger is None:
            continue
        if trigger.group(0) in {"若", "如果"}:
            candidate = candidate[trigger.start() :]
        quantities = (
            *_ARABIC_QUANTITY_RE.findall(candidate),
            *_CHINESE_QUANTITY_RE.findall(candidate),
        )
        if any(
            not _quantity_supported_by_evidence(
                quantity,
                evidence_quantities,
                sentence=text,
            )
            for quantity in quantities
            if _normalize_quantity(quantity)
        ):
            rejected.add(index)
    return tuple(sorted(rejected))


def draft_sentence_count(draft: str) -> int:
    """Public sentence count for W5 anti-regression (new sentences fail closed)."""

    return len(_numbered_sentences(draft))


def numeric_condition_unsupported(verified: VerifiedEpisodeOutcome) -> bool:
    """True when the draft has a novel numeric condition G11 would redact.

    Adapter runs this *before* the judge so a backfill turn can fetch the
    missing number via the subject-anchored capability instead of thinning
    the answer.
    """

    return bool(
        _novel_numeric_condition_indexes(
            _numbered_sentences(verified.outcome.draft),
            verified,
        )
    )


def _mismatched_weekday_indexes(
    sentences: list[dict[str, object]],
    verified: VerifiedEpisodeOutcome,
) -> tuple[int, ...]:
    """Reject date/weekday labels that contradict a bound calendar date."""

    evidence_dates = _bound_evidence_dates(verified.outcome)
    rejected: set[int] = set()
    for item in sentences:
        index = item.get("index")
        text = str(item.get("text") or "")
        if not isinstance(index, int):
            continue
        for match in _DATE_WEEKDAY_RE.finditer(text):
            month = int(match.group("month"))
            day = int(match.group("day"))
            raw_year = match.group("year")
            candidates = {
                value
                for value in evidence_dates
                if value.month == month
                and value.day == day
                and (raw_year is None or value.year == int(raw_year))
            }
            expected = {value.weekday() for value in candidates}
            stated = _WEEKDAY_INDEX.get(match.group("label")[-1])
            if len(expected) == 1 and stated not in expected:
                rejected.add(index)
                break
    return tuple(sorted(rejected))


def _mismatched_path_trend_indexes(
    sentences: list[dict[str, object]],
    verified: VerifiedEpisodeOutcome,
) -> tuple[int, ...]:
    """Reject all-window path language contradicted by bound turnover points.

    Endpoint movement can be correct while the path between those endpoints is
    not monotonic.  The narrow all-path gate covers ``一路`` plus unbounded
    ``持续/连续`` language only when at least three dated turnover observations
    are bound. Explicitly local statements such as ``连续两个交易日回落`` do not
    match these patterns and remain the semantic judge's responsibility.
    """

    series = _bound_turnover_series(verified.outcome)
    if len(series) < 3:
        return ()
    values = [value for _trade_date, value in series]
    is_non_increasing = all(
        current <= previous for previous, current in zip(values, values[1:])
    )
    is_non_decreasing = all(
        current >= previous for previous, current in zip(values, values[1:])
    )
    rejected: set[int] = set()
    for item in sentences:
        index = item.get("index")
        text = str(item.get("text") or "")
        if not isinstance(index, int):
            continue
        downward, upward = _turnover_path_directions(text)
        if downward and not is_non_increasing:
            rejected.add(index)
        if upward and not is_non_decreasing:
            rejected.add(index)
    return tuple(sorted(rejected))


def _turnover_path_directions(text: str) -> tuple[bool, bool]:
    """Bind amount-like turnover subjects to asserted path words locally."""

    downward = False
    upward = False
    for clause in re.split(r"[；;。！？!?\n]+", text):
        if not clause:
            continue
        for pattern, direction in (
            (_DOWNWARD_PATH_RE, "down"),
            (_UPWARD_PATH_RE, "up"),
        ):
            for path_match in pattern.finditer(clause):
                all_subjects = tuple(
                    _TURNOVER_AMOUNT_SUBJECT_RE.finditer(clause)
                )
                subjects_before = tuple(
                    subject
                    for subject in all_subjects
                    if subject.end() <= path_match.start()
                )
                subjects_after = tuple(
                    subject
                    for subject in all_subjects
                    if subject.start() >= path_match.end()
                )
                locally_bound = False
                bound_subject = None
                if subjects_before:
                    subject = subjects_before[-1]
                    bridge = clause[subject.end() : path_match.start()]
                    locally_bound = _turnover_bridge_is_locally_bound(bridge)
                    if locally_bound:
                        bound_subject = subject
                if not locally_bound and subjects_after:
                    subject = subjects_after[0]
                    bridge = clause[path_match.end() : subject.start()]
                    locally_bound = _inverted_turnover_bridge_is_locally_bound(
                        bridge
                    )
                    if locally_bound:
                        bound_subject = subject
                if not locally_bound:
                    continue
                assert bound_subject is not None
                scope = _path_assertion_scope(
                    clause,
                    subject_start=bound_subject.start(),
                    path_start=path_match.start(),
                )
                if _PATH_SCOPE_BLOCKER_RE.search(scope):
                    continue
                if (
                    not path_match.group(0).startswith("一路")
                    and _LOCAL_PATH_WINDOW_RE.search(scope)
                ):
                    continue
                if _LOCAL_PATH_SEGMENT_RE.search(scope):
                    continue
                suffix = clause[
                    path_match.end() : path_match.end() + 28
                ].lstrip("，, ")
                if _LOCAL_PATH_WINDOW_RE.match(suffix):
                    continue
                if _LOCAL_PATH_SEGMENT_RE.match(suffix):
                    continue
                if _PATH_POST_SCOPE_BLOCKER_RE.search(suffix):
                    continue
                if direction == "down":
                    downward = True
                else:
                    upward = True
    return downward, upward


def _path_assertion_scope(
    clause: str,
    *,
    subject_start: int,
    path_start: int,
) -> str:
    """Return only modifiers that can govern the nearest turnover subject."""

    local_start = min(subject_start, path_start)
    prefix = clause[:local_start]
    other_metrics = tuple(_OTHER_PATH_METRIC_RE.finditer(prefix))
    if other_metrics:
        prefix = prefix[other_metrics[-1].end() :]
    scope = prefix[-24:] + clause[local_start:path_start]
    return re.split(r"(?:但|而是|而|不过|然而|可是|却)", scope)[-1]


def _turnover_bridge_is_locally_bound(bridge: str) -> bool:
    if len(bridge) > 48:
        return False
    if _OTHER_PATH_METRIC_RE.search(bridge) is None:
        return True
    coordinated_metrics = re.fullmatch(
        r"\s*(?:(?:与|和|及|、)\s*"
        r"(?:上涨家数|下跌家数|涨停|跌停|指数|股价|板块))+"
        r"\s*(?:均|都|同步|共同)?\s*",
        bridge,
    )
    return coordinated_metrics is not None


def _inverted_turnover_bridge_is_locally_bound(bridge: str) -> bool:
    return re.fullmatch(r"\s*(?:的|之)?\s*", bridge) is not None


def _bound_turnover_series(outcome: AgentOutcome) -> tuple[tuple[date, float], ...]:
    bound_hashes = {
        content_hash
        for binding in outcome.bindings
        for content_hash in binding.evidence_hashes
    }
    observations: dict[date, float] = {}
    for item in outcome.evidence:
        if item.content_hash not in bound_hashes:
            continue
        corpus = " ".join((item.title, item.detail))
        for match in _TURNOVER_OBSERVATION_RE.finditer(corpus):
            try:
                trade_date = date.fromisoformat(match.group("date"))
                value = float(match.group("value"))
            except (TypeError, ValueError):
                continue
            observations[trade_date] = value
    return tuple(sorted(observations.items()))


def _bound_evidence_dates(outcome: AgentOutcome) -> frozenset[date]:
    bound_hashes = {
        content_hash
        for binding in outcome.bindings
        for content_hash in binding.evidence_hashes
    }
    parsed: set[date] = set()
    for item in outcome.evidence:
        if item.content_hash not in bound_hashes:
            continue
        corpus = " ".join(
            (
                item.title,
                item.detail,
                item.source,
                str(item.source_date or ""),
            )
        )
        for pattern in (_FULL_ISO_DATE_RE, _FULL_CHINESE_DATE_RE):
            for match in pattern.finditer(corpus):
                try:
                    parsed.add(
                        date(
                            int(match.group("year")),
                            int(match.group("month")),
                            int(match.group("day")),
                        )
                    )
                except ValueError:
                    continue
    return frozenset(parsed)


def _bound_evidence_quantities(outcome: AgentOutcome) -> frozenset[str]:
    bound_hashes = {
        content_hash
        for binding in outcome.bindings
        for content_hash in binding.evidence_hashes
    }
    fields: list[str] = []
    for item in outcome.evidence:
        if item.content_hash not in bound_hashes:
            continue
        fields.extend(
            (
                item.title,
                item.detail,
                item.source,
                str(item.source_date or ""),
            )
        )
    corpus = " ".join(fields)
    quantities = {
        _normalize_quantity(quantity)
        for quantity in (
            *_ARABIC_QUANTITY_RE.findall(corpus),
            *_CHINESE_QUANTITY_RE.findall(corpus),
        )
        if _normalize_quantity(quantity)
    }
    # 结构化观察值**不受 binding 约束**。上面那段只认被 binding 引用过的证据，
    # 是引用卫生；而 observations 是 harness 自己投递上桌的事实，它是不是真的
    # 与模型有没有记得绑引用无关。少了这一段，模型写对了数却忘了绑，真话会被
    # 判成「证据里没有的数量」连坐删句——那是拿引用卫生当真伪判据，模型越强
    # （写得越细、数字越多）被误删越多。
    #
    # 只放宽到结构化值，不放宽到未绑定证据的**文本**：前者是机器可核的投递物，
    # 后者仍需引用卫生把关。
    for item in outcome.evidence:
        for obs in item.observations:
            token = _normalize_quantity(f"{obs.value:g}")
            if token:
                quantities.add(token)
    return frozenset(quantities)


def _normalize_quantity(value: object) -> str:
    return (
        re.sub(r"[\s,，]", "", str(value or ""))
        .replace("～", "至")
        .replace("~", "至")
        .replace("—", "至")
        .replace("→", "至")
    )


def _quantity_supported_by_evidence(
    quantity: object,
    evidence_quantities: frozenset[str],
    *,
    sentence: str,
) -> bool:
    """Match exact quantities or deterministic same-unit rounding.

    The tolerance is the half-unit implied by the answer's shown precision.
    For example, ``17%`` may represent evidence ``-17.27%`` when the sentence
    explicitly says the value fell, while ``3800点`` cannot represent
    ``3876.777点``. Currency units are converted between 亿元 and 万亿元.
    """

    normalized = _normalize_quantity(quantity)
    if normalized in evidence_quantities:
        return True
    candidate = _parse_quantity(normalized)
    if candidate is None:
        return False
    for evidence in evidence_quantities:
        observed = _parse_quantity(evidence)
        if observed is None or not _same_quantity_dimension(candidate, observed):
            continue
        if _rounded_quantity_matches(candidate, observed, sentence=sentence):
            return True
    return False


def _parse_quantity(
    value: str,
) -> tuple[tuple[float, ...], str, int] | None:
    match = _QUANTITY_PARSE_RE.fullmatch(value)
    if match is None:
        return None
    raw_values = tuple(
        item
        for item in (match.group("first"), match.group("second"))
        if item is not None
    )
    if not raw_values:
        return None
    decimals = max(
        len(item.partition(".")[2]) if "." in item else 0 for item in raw_values
    )
    return tuple(float(item) for item in raw_values), match.group("unit") or "", decimals


def _quantity_dimension(unit: str) -> tuple[str, float]:
    if unit in {"万亿元", "万亿"}:
        return "currency_yi", 10000.0
    if unit in {"亿元", "亿"}:
        return "currency_yi", 1.0
    return unit, 1.0


def _same_quantity_dimension(
    left: tuple[tuple[float, ...], str, int],
    right: tuple[tuple[float, ...], str, int],
) -> bool:
    left_dimension, _left_scale = _quantity_dimension(left[1])
    right_dimension, _right_scale = _quantity_dimension(right[1])
    return bool(left_dimension and left_dimension == right_dimension)


def _rounded_quantity_matches(
    candidate: tuple[tuple[float, ...], str, int],
    observed: tuple[tuple[float, ...], str, int],
    *,
    sentence: str,
) -> bool:
    candidate_values, candidate_unit, candidate_decimals = candidate
    observed_values, observed_unit, _observed_decimals = observed
    if len(candidate_values) != len(observed_values) and not (
        len(candidate_values) == 1 and len(observed_values) > 1
    ):
        return False
    _candidate_dimension, candidate_scale = _quantity_dimension(candidate_unit)
    _observed_dimension, observed_scale = _quantity_dimension(observed_unit)
    observed_in_candidate_unit = tuple(
        value * observed_scale / candidate_scale for value in observed_values
    )
    tolerance = 0.5 * (10 ** (-candidate_decimals))
    negative_context = bool(_NEGATIVE_CONTEXT_RE.search(sentence))
    if len(candidate_values) == 1 and len(observed_in_candidate_unit) > 1:
        expected_values = candidate_values * len(observed_in_candidate_unit)
    else:
        expected_values = candidate_values
    matches: list[bool] = []
    for expected, actual in zip(expected_values, observed_in_candidate_unit):
        if expected * actual < 0:
            if not (negative_context and expected >= 0 and actual < 0):
                matches.append(False)
                continue
            actual = abs(actual)
        matches.append(abs(expected - actual) <= tolerance + 1e-12)
    if len(candidate_values) == 1 and len(observed_values) > 1:
        return any(matches)
    return all(matches)


_SLOT_METRIC_LABELS = {
    "pct_chg": "涨跌幅",
    "amount": "成交额亿",
    "diff_ratio": "边际量",
    "total_amount": "市场成交额亿",
    "advancers": "上涨家数",
    "limit_up": "涨停家数",
    "limit_down": "跌停家数",
}

_SLOT_HEADING = "【预取事实】"


def slot_line_for_observations(
    observations: tuple[StructuredObservation, ...],
) -> str:
    """把观察值渲染成一行系统填的事实，**模型一个字没写**。

    这是「槽」的最小形态：内容全部来自已投递的预取观察值，判官无据可删——
    它要驳的是模型的未核验表述，而这一行不是模型写的。

    与判官的分工由此变成结构性的，不再靠提示词自觉：
    数字住在槽里（系统填、必真），叙述住在格间（模型写、判官可删）。
    删叙述永远删不掉数字。
    """

    if not observations:
        return ""
    grouped: dict[tuple[str, str], list[StructuredObservation]] = {}
    for obs in observations:
        grouped.setdefault((obs.subject, obs.as_of), []).append(obs)
    parts: list[str] = []
    for (subject, as_of), items in grouped.items():
        fields = "；".join(
            f"{_SLOT_METRIC_LABELS.get(obs.metric, obs.metric)}={obs.value:.12g}"
            for obs in items
        )
        parts.append(f"{subject} {as_of}：{fields}")
    return _SLOT_HEADING + "｜".join(parts)


def _restore_lost_observations(
    *,
    draft: str,
    before: str,
    evidence: tuple[AgentEvidence, ...],
) -> tuple[str, tuple[StructuredObservation, ...]]:
    """判官删完之后，把被连坐掉的有据数值以槽的形态补回稿件。

    只补**数值本身**，不补任何被驳回的叙述——被删的因果/判断不会借尸还魂。
    Gate 1 现场活下来的是错口径的主线句，真值 4.74/3432.59 陪葬；
    补回之后真值一定在稿子里，与它原先绑的那句叙述死活无关。
    """

    lost = grounded_values_in_text(before, evidence)
    if not lost:
        return draft, ()
    survivors = {obs.value for obs in grounded_values_in_text(draft, evidence)}
    missing = tuple(obs for obs in lost if obs.value not in survivors)
    if not missing:
        return draft, ()
    return f"{draft.rstrip()}\n\n{slot_line_for_observations(missing)}", missing


def _gaps_with_lost_observations(
    *,
    gaps: tuple[str, ...],
    before: str,
    after: str,
    evidence: tuple[AgentEvidence, ...],
) -> tuple[str, ...]:
    """判官删句后，把被连坐掉的**有据数值**补记成缺口。

    Gate 1 实锤（`docs/verification/2026-08-21-gate1-pcb-exact-name.md`）：判官
    把「缩量洗盘后主升」整段判未核验删掉，真值 4.74/3432.59 绑在那段里一起没
    了，活下来的反而是错口径的句子。**真话和编造绑同一段，一刀切下去真话陪葬。**

    这里不改删除决定——给含真值的句子发免死金牌会让编造搭便车（那是「变错」，
    必须硬）。改的是：删掉的真值**不再静默消失**，而是落成缺口，下游可按槽
    重新呈现。拦的是信息丢失，不是模型的表达，所以是保下限不是封上限。
    """

    lost = grounded_values_in_text(before, evidence)
    if not lost:
        return gaps
    survivors = {obs.value for obs in grounded_values_in_text(after, evidence)}
    notes = tuple(
        describe_lost_observation(obs) for obs in lost if obs.value not in survivors
    )
    if not notes:
        return gaps
    return tuple(dict.fromkeys((*gaps, *notes)))


def _drop_rejected_sentences(
    draft: str,
    rejected_sentence_indexes: tuple[int, ...],
) -> str:
    """Remove rejected spans and repair presentational list numbering.

    Accepted claim prose stays byte-for-byte unchanged.  Numeric list labels
    are presentation metadata, so a removed middle item is deterministically
    renumbered instead of leaking a visibly broken ``1, 3, 4`` sequence.
    """

    source = str(draft or "")
    original_source = source
    rejected = frozenset(rejected_sentence_indexes)
    spans: list[tuple[int, int]] = []
    cursor = 0
    for item in _numbered_sentences(source):
        text = str(item["text"])
        start = source.find(text, cursor)
        if start < 0:
            return ""
        end = start + len(text)
        if item["index"] in rejected:
            delete_start = start
            line_start = source.rfind("\n", 0, start) + 1
            if source[line_start:start].strip() == "":
                delete_start = line_start
            delete_end = end
            if (
                delete_end < len(source)
                and source[delete_end] == "\n"
                and (delete_start == 0 or source[delete_start - 1] == "\n")
            ):
                delete_end += 1
            spans.append((delete_start, delete_end))
        cursor = end
    for start, end in reversed(spans):
        source = f"{source[:start]}{source[end:]}"
    repaired = _renumber_ordered_list_items(source.strip())
    return _reconcile_explicit_list_counts(original_source, repaired)


def _reconcile_explicit_list_counts(before: str, after: str) -> str:
    """Keep an explicit count aligned with a surviving ordered-list group.

    This is deliberately narrow: only a count phrase immediately followed by
    one ordered list whose original length equals that count is eligible.  A
    count that cannot be mapped safely is removed rather than guessed.
    """

    matches = tuple(
        sorted(
            (
                *_EXPLICIT_LIST_COUNT_RE.finditer(before),
                *_PREFIXED_LIST_COUNT_RE.finditer(before),
            ),
            key=lambda item: item.start(),
        )
    )
    if not matches:
        return after
    replacements: list[tuple[int, int, str]] = []
    after_cursor = 0
    for match in matches:
        original_count = _parse_small_count(match.group("count"))
        if original_count is None:
            continue
        before_group = _next_list_group_count(
            before,
            match.end(),
            contiguous=False,
        )
        if before_group != original_count:
            continue
        phrase = match.group(0)
        after_start = after.find(phrase, after_cursor)
        if after_start < 0:
            continue
        after_end = after_start + len(phrase)
        after_cursor = after_end
        after_group = _next_list_group_count(after, after_end)
        if after_group == original_count:
            continue
        if after_group is None or after_group < 1:
            label = match.groupdict().get("label") or ""
            descriptor = match.groupdict().get("descriptor") or ""
            replacements.append(
                (after_start, after_end, label or descriptor)
            )
            continue
        rendered_count = _render_small_count(
            after_group,
            chinese=not match.group("count").isdigit(),
        )
        label = match.groupdict().get("label")
        descriptor = match.groupdict().get("descriptor")
        replacement = (
            f"{label}有{rendered_count}{match.group('unit')}"
            if label
            else f"{rendered_count}{match.group('unit')}{descriptor}"
        )
        replacements.append((after_start, after_end, replacement))
    # Apply from right to left so each replacement keeps later offsets stable.
    for start, end, replacement in reversed(replacements):
        if end <= len(after):
            after = f"{after[:start]}{replacement}{after[end:]}"
    return after


def _next_ordered_group_count(
    text: str,
    start: int,
    *,
    contiguous: bool = True,
) -> int | None:
    """Return the first ordered-list line group after ``start``."""

    tail = text[start:].lstrip(" \t:：-")
    lines = tail.splitlines()
    group_count = 0
    expected = 1
    started = False
    consumed_chars = 0
    for line in lines:
        match = _ORDERED_LIST_ITEM_RE.fullmatch(line)
        if match is not None and (
            not contiguous or int(match.group("number")) == expected
        ):
            started = True
            group_count += 1
            expected += 1
        elif started:
            break
        consumed_chars += len(line) + 1
        if not started and consumed_chars > 400:
            break
    return group_count if started else None


def _next_list_group_count(
    text: str,
    start: int,
    *,
    contiguous: bool = True,
) -> int | None:
    ordered = _next_ordered_group_count(
        text,
        start,
        contiguous=contiguous,
    )
    parenthesized = _next_parenthesized_group_count(
        text,
        start,
        contiguous=contiguous,
    )
    if ordered is None:
        return parenthesized
    if parenthesized is None:
        return ordered
    return max(ordered, parenthesized)


def _next_parenthesized_group_count(
    text: str,
    start: int,
    *,
    contiguous: bool = True,
) -> int | None:
    tail = text[start : start + 1200]
    matches = tuple(_PAREN_LIST_NUMBER_RE.finditer(tail))
    if not matches or matches[0].start() > 400:
        return None
    count = 1
    expected = int(matches[0].group("number")) + 1
    previous = matches[0]
    for match in matches[1:]:
        bridge = tail[previous.end() : match.start()]
        if len(bridge) > 400 or re.search(r"[。！？!?\n]", bridge):
            break
        if contiguous and int(match.group("number")) != expected:
            break
        count += 1
        expected = int(match.group("number")) + 1
        previous = match
    return count if count >= 2 else None


def _parse_small_count(value: str) -> int | None:
    if value.isdigit():
        parsed = int(value)
        return parsed if 1 <= parsed <= 20 else None
    digits = {
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
        "十": 10,
    }
    if value == "十":
        return 10
    if len(value) == 1:
        return digits.get(value)
    if len(value) == 2 and value[0] == "十" and value[1] in digits:
        return 10 + digits[value[1]]
    if len(value) == 2 and value[1] == "十" and value[0] in digits:
        return digits[value[0]] * 10
    return None


def _render_small_count(value: int, *, chinese: bool) -> str:
    if not chinese:
        return str(value)
    if value <= 10:
        return ("一", "二", "三", "四", "五", "六", "七", "八", "九", "十")[
            value - 1
        ]
    if value < 20:
        return "十" + "一二三四五六七八九"[value - 11]
    return str(value)


def _renumber_ordered_list_items(source: str) -> str:
    """Renumber contiguous Chinese/Markdown ordered-list lines from one."""

    rendered: list[str] = []
    position = 0
    for line in source.splitlines(keepends=True):
        body = line.rstrip("\r\n")
        ending = line[len(body) :]
        match = _ORDERED_LIST_ITEM_RE.fullmatch(body)
        if match is not None:
            position += 1
            rendered.append(
                f"{match.group('indent')}{position}{match.group('suffix')}"
                f"{match.group('body')}{ending}"
            )
            continue
        if body.strip():
            position = 0
        rendered.append(line)
    return _renumber_circled_list_items("".join(rendered))


def _renumber_circled_list_items(source: str) -> str:
    """Repair inline circled-number sequences after a rejected item is removed."""

    rendered: list[str] = []
    position = 0
    for char in source:
        if char not in _CIRCLED_LIST_NUMBERS:
            rendered.append(char)
            continue
        if char == _CIRCLED_LIST_NUMBERS[0] or position == 0:
            position = 1
        else:
            position += 1
        rendered.append(
            _CIRCLED_LIST_NUMBERS[position - 1]
            if position <= len(_CIRCLED_LIST_NUMBERS)
            else char
        )
    return _renumber_parenthesized_list_items("".join(rendered))


def _renumber_parenthesized_list_items(source: str) -> str:
    """Renumber inline ``(2), (3)`` list groups after deletion."""

    matches = list(_PAREN_LIST_NUMBER_RE.finditer(source))
    groups: list[list[re.Match[str]]] = []
    current: list[re.Match[str]] = []
    for match in matches:
        if not current:
            current = [match]
            continue
        bridge = source[current[-1].end() : match.start()]
        increasing = int(match.group("number")) > int(
            current[-1].group("number")
        )
        if len(bridge) <= 400 and not re.search(r"[。！？!?\n]", bridge) and increasing:
            current.append(match)
            continue
        if len(current) >= 2:
            groups.append(current)
        current = [match]
    if len(current) >= 2:
        groups.append(current)

    replacements: list[tuple[int, int, str]] = []
    for group in groups:
        numbers = [int(match.group("number")) for match in group]
        if numbers == list(range(1, len(group) + 1)):
            continue
        for index, match in enumerate(group, start=1):
            replacements.append(
                (
                    match.start(),
                    match.end(),
                    f"{match.group('open')}{index}{match.group('close')}",
                )
            )
    for start, end, replacement in reversed(replacements):
        source = f"{source[:start]}{replacement}{source[end:]}"
    return source


def _marker_loss_gap_sentence(
    *,
    labels: tuple[str, ...],
    context_prefix: str,
    all_were_fulfilled: bool,
) -> str:
    """按**丢失原因**给缺口文案分流，别把 harness 的问题甩锅给数据。

    生产实测 `run_20260821_114642_385979`（诊断见
    `docs/verification/2026-08-21-judge-quantity-blindspot.md`）：
    `structural_verifier` 判四个必填格全部 `fulfilled`、零 gap，随后语义质检
    重写公开稿丢掉两格，用户看到的却是「**需补充直接证据**后再判断」——
    让人去补一份根本不缺的证据。归因错了，指引也就错了。

    两种缺口的处置相反，必须分开说：

    - 本来就没取到证据 → 补数据是对的
    - 代码侧已判达标、是质检把表述删了 → **不要补数据**，该重做那一格

    这不改判官的任何权力，只让它造成的后果被如实归因。
    """

    body = context_prefix + "、".join(labels)
    if all_were_fulfilled:
        return (
            "结构缺口："
            + body
            + "在结构核验中已判达标，但本轮质检重写时删除了其表述。"
            "这不是证据不足——不需要补充数据，应重做这些部分。"
        )
    return "证据缺口：" + body + "中的未核验表述已删除，需补充直接证据后再判断。"


def _marker_loss_issues(output_ids: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        Issue(
            IssueCode.MARKER_LOSS,
            output_id,
            f"{_MARKER_LOSS_GAP}: {output_id}",
        ).serialize()
        for output_id in output_ids
    )


def _semantic_tool_status_registry(
    traces: tuple[ProviderTrace, ...],
) -> list[dict[str, object]]:
    """Project process status without provider diagnostics or trace identity."""

    statuses: list[dict[str, object]] = []
    seen: set[tuple[str, str, int, str | None]] = set()
    for trace in traces:
        capability = str(trace.capability or "").strip()
        if not capability:
            continue
        key = (
            capability,
            trace.status,
            trace.result_count,
            trace.source_trade_date,
        )
        if key in seen:
            continue
        seen.add(key)
        statuses.append(
            {
                "capability": capability,
                "status": trace.status,
                "result_count": trace.result_count,
                "source_trade_date": trace.source_trade_date,
            }
        )
    return statuses


def _verified_quantities_for_judge(
    outcome: AgentOutcome,
) -> list[dict[str, object]]:
    """投递给判官：稿件里哪些数**已由确定性核对确认来自已投递观察值**。

    为什么要投递而不是让判官自己查（2026-08-21 生产实测，
    `docs/verification/2026-08-21-judge-quantity-blindspot.md`）：

    判官拿到了完整的 E1（2285 字符、43 行逐日行情，含 `成交额亿=775.76`），
    投影不截 `detail`、压缩也不动它——**它看得见**。但它仍写下「证据注册表无
    该题材量价时间轴」，把 `0.15 / 775.76 / 13.78 / 2.81` 全判成「未注册数字」，
    连带摘掉 `direct_assessment` 与 `counterpoint` 两个必填输出。

    同一份稿件 + 同一份证据，确定性逐字核对这四个数**全部判对**。
    「这个数在不在证据里」是可判定的机械问题，交给 LLM 等于把必然正确换成
    概率正确——按约束三筛（`harness-reference/PLAYBOOK.md`）：拦输出、
    答题模型越强写得越精确被误伤越多，是典型的封上限。

    因此把机械那半从判官手里拿走、直接投递结论，判官只留语义判断
    （因果是否成立、口径有没有混用）。这不放宽任何东西：只有与已投递观察值
    **逐字节相等**的数才会进这份清单，编造的数进不来。
    """

    values = grounded_values_in_text(outcome.draft, outcome.evidence)
    return [
        {
            "value": obs.value,
            "subject": obs.subject,
            "as_of": obs.as_of,
            "metric": obs.metric,
        }
        for obs in values
    ]


def _semantic_evidence_projection(
    outcome: AgentOutcome,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Alias and project only answer-bound evidence for semantic judging."""

    bindings, registry, _telemetry = _project_semantic_evidence(outcome)
    return bindings, registry


@dataclass(frozen=True)
class _ProjectionTelemetry:
    dropped_field_chars: int
    truncated_field_chars: int
    ordinal_mismatch_count: int
    alias_offset: int
    cited_unbound_count: int


def _project_semantic_evidence(
    outcome: AgentOutcome,
) -> tuple[list[dict[str, object]], list[dict[str, object]], _ProjectionTelemetry]:
    """Project answer-relied evidence using the episode ordinal table as the only id issuer.

    选集 = 绑定 ∪ 正文可反解引用（R-20260821-06）。正文显式引用是答案对依赖的
    声明，比 bindings 记账数组更直接；漏记账不该让判官对真实证据做存在性否证。
    未引用且未绑定的卡仍不送判官——绑定纪律只对「答案真的依赖」的证据放行。
    表外引用（E 号反解不到卡）不做模糊纠正，照旧走判官删除路径。
    """

    ordinals = evidence_ordinal_table(outcome.evidence)
    bound_hashes = {
        evidence_hash
        for binding in outcome.bindings
        for evidence_hash in binding.evidence_hashes
    }
    cited_ids = set(cited_evidence_ordinals(outcome.draft))
    alias_by_hash: dict[str, str] = {}
    registry: list[dict[str, object]] = []
    dropped_field_chars = 0
    truncated_field_chars = 0
    cited_unbound_count = 0
    bound_emitted_ids: set[str] = set()
    for item in outcome.evidence:
        if not item.content_hash:
            continue
        evidence_id = ordinals[item.content_hash]
        is_bound = item.content_hash in bound_hashes
        if not is_bound and evidence_id not in cited_ids:
            continue
        if is_bound:
            bound_emitted_ids.add(evidence_id)
        else:
            cited_unbound_count += 1
        alias_by_hash[item.content_hash] = evidence_id
        projected: dict[str, object] = {
            "evidence_id": evidence_id,
            "tool": item.tool,
            "source_date": item.source_date,
            "evidence_tier": item.evidence_tier,
        }
        title = str(item.title or "")
        if title:
            if len(title) > MAX_EVIDENCE_TITLE_CHARS:
                truncated_field_chars += len(title) - MAX_EVIDENCE_TITLE_CHARS
            projected["title"] = title[:MAX_EVIDENCE_TITLE_CHARS]
        detail = str(item.detail or "")
        if detail:
            projected["detail"] = detail
        if item.freshness and item.freshness != "unknown":
            projected["freshness"] = item.freshness
        if item.supports:
            projected["supports"] = list(item.supports)
        if item.contradicts:
            projected["contradicts"] = list(item.contradicts)
        if item.independent_key:
            projected["independent_key"] = item.independent_key
        if title and "title" not in projected:
            dropped_field_chars += len(title)
        if detail and "detail" not in projected:
            dropped_field_chars += len(detail)
        registry.append(projected)
    bindings: list[dict[str, object]] = []
    for binding in outcome.bindings:
        projected_binding: dict[str, object] = {
            "output_id": binding.output_id,
            "evidence_ids": [
                alias_by_hash[evidence_hash]
                for evidence_hash in binding.evidence_hashes
                if evidence_hash in alias_by_hash
            ],
            "gap": binding.gap,
        }
        # ``evidence`` is the historical default; omit it in the compact
        # projection for compatibility while making non-evidence semantics
        # explicit to the judge.
        if binding.basis != "evidence":
            projected_binding["basis"] = binding.basis
        bindings.append(projected_binding)
    bound_issued = {
        ordinals[digest]
        for digest in bound_hashes
        if digest in ordinals
    }
    telemetry = _ProjectionTelemetry(
        dropped_field_chars=dropped_field_chars,
        truncated_field_chars=truncated_field_chars,
        # D2 哨兵只对绑定集合有语义：引用补送的行不属于发放对账范围。
        ordinal_mismatch_count=len(
            bound_issued.symmetric_difference(bound_emitted_ids)
        ),
        alias_offset=len(outcome.evidence) - len(registry),
        cited_unbound_count=cited_unbound_count,
    )
    return bindings, registry, telemetry


def _repair_wiped_all_required(contract: object, marker_loss: tuple[str, ...]) -> bool:
    """Return whether repair emptied every evidence-grounded required output."""

    return bool(_required_evidence_outputs(contract)) and _required_evidence_outputs(
        contract
    ) <= set(marker_loss)


def _required_evidence_outputs(contract: object) -> set[str]:
    return {
        str(item.output_id)
        for item in getattr(contract, "required_outputs", ())
        if getattr(item, "required", True)
        and str(getattr(item, "grounding_mode", "evidence")) == "evidence"
    }


def _answer_grounding_mode(contract: object) -> str:
    required_outputs = getattr(contract, "required_outputs", ())
    modes = tuple(
        dict.fromkeys(
            str(getattr(item, "grounding_mode", "evidence"))
            for item in required_outputs
            if getattr(item, "required", True)
        )
    )
    if not modes:
        return "evidence"
    return modes[0] if len(modes) == 1 else "mixed"


def _lost_grounded_output_substance(
    contract: object,
    before: str,
    after: str,
) -> tuple[str, ...]:
    lost = lost_required_output_substance(contract, before, after)
    grounding_by_id = {
        str(getattr(item, "output_id", "")): str(
            getattr(item, "grounding_mode", "evidence")
        )
        for item in getattr(contract, "required_outputs", ())
    }
    return tuple(
        output_id
        for output_id in lost
        if grounding_by_id.get(output_id, "evidence") == "evidence"
        or (
            output_id in JUDGMENT_OUTPUT_IDS
            and grounding_by_id.get(output_id, "evidence") == "model_reasoning"
        )
    )


def _judge_system_prompt(request: Mapping[str, object]) -> str:
    if request.get("answer_grounding_mode") in {
        "model_reasoning",
        "user_premise",
    }:
        return _NON_EVIDENCE_JUDGE_SYSTEM_PROMPT
    return _JUDGE_SYSTEM_PROMPT


def _call_flexible(fn: JudgeFn, request: dict[str, object], timeout: float) -> object:
    """Call tiny injected judges without imposing one test-only signature."""

    try:
        signature = inspect.signature(fn)
    except (TypeError, ValueError):
        return fn(request)
    parameters = signature.parameters
    if any(
        param.kind == inspect.Parameter.VAR_KEYWORD for param in parameters.values()
    ):
        return fn(
            question=request["question"],
            required_outputs=request["required_outputs"],
            answer_grounding_mode=request["answer_grounding_mode"],
            output_bindings=request["output_bindings"],
            evidence_registry=request["evidence_registry"],
            tool_status_registry=request.get("tool_status_registry") or [],
            claim_policy=request.get("claim_policy") or dict(_CLAIM_POLICY),
            sentences=request["sentences"],
            timeout=timeout,
        )
    named = {
        name: request[name]
        for name in (
            "question",
            "required_outputs",
            "answer_grounding_mode",
            "output_bindings",
            "evidence_registry",
            "sentences",
        )
        if name in parameters
    }
    if "tool_status_registry" in parameters:
        named["tool_status_registry"] = request.get("tool_status_registry") or []
    if "claim_policy" in parameters:
        named["claim_policy"] = request.get("claim_policy") or dict(_CLAIM_POLICY)
    if "timeout" in parameters:
        named["timeout"] = timeout
    required_positional = [
        parameter
        for parameter in parameters.values()
        if parameter.kind
        in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        and parameter.default is inspect.Parameter.empty
    ]
    if named and all(parameter.name in named for parameter in required_positional):
        return fn(**named)
    if required_positional:
        aliases = {
            "request": request,
            "payload": request,
            "question": request["question"],
            "required_outputs": request["required_outputs"],
            "answer_grounding_mode": request["answer_grounding_mode"],
            "output_bindings": request["output_bindings"],
            "bindings": request["output_bindings"],
            "evidence_registry": request["evidence_registry"],
            "evidence": request["evidence_registry"],
            "registry": request["evidence_registry"],
            "tool_status_registry": request.get("tool_status_registry") or [],
            "tool_statuses": request.get("tool_status_registry") or [],
            "claim_policy": request.get("claim_policy") or dict(_CLAIM_POLICY),
            "sentences": request["sentences"],
            "answer_sentences": request["sentences"],
            "timeout": timeout,
        }
        positional: list[object] = []
        for parameter in required_positional:
            if parameter.name not in aliases:
                break
            positional.append(aliases[parameter.name])
        if len(positional) == len(required_positional):
            return fn(*positional)
    return fn(request)


def _stable_semantic_judge_error(value: object) -> tuple[str, bool, bool]:
    """Classify provider failure without projecting raw diagnostics."""

    normalized = str(value or "").strip().casefold()
    if any(
        marker in normalized
        for marker in (
            "401",
            "402",
            "403",
            "authentication",
            "authorization",
            "api key",
            "未配置",
            "鉴权",
            "认证",
        )
    ):
        return "semantic judge configuration error", False, False
    if "budget" in normalized or "预算" in normalized:
        return "semantic judge call budget exhausted", False, False
    if "cancel" in normalized or "取消" in normalized:
        return "semantic judge cancelled", False, False
    # CLI judge 的故障要在通用分支之前判：`GrokCliInvalidJson` 含 "invalid"，
    # 会被下面那条 invalid 分支抢走并判成 retryable=False。
    #
    # ⚠ 这里匹配的是**类名**（`grokcli…`），不是异常消息。上游
    # `llm_refine.complete()` 产出的串是 `LLM 调用失败（{type(exc).__name__}）`，
    # **消息正文根本不进这个串**。第一版按消息里的 `grok_cli_empty` 写匹配，
    # 结果是一段永不触发的死代码——读起来像修好了，实测 retryable 仍为 False。
    #
    # 空输出 / 非零退出 / 坏 JSON 对一个子进程 CLI 都是**瞬时**故障：实测同一个
    # 二进制在琐碎提示上耗时 8.4~48.5s，抽风一次不代表下一次也抽。重试机制
    # （MAX_SEMANTIC_JUDGE_ATTEMPTS=3）本来就在，这里只是别再把它短路掉。
    if "grokcli" in normalized:
        if "emptyprompt" in normalized:
            # 提示词是空的属于调用方 bug，重试也还是空。刻意不放进瞬时档。
            return "semantic judge invalid provider response", False, False
        return "semantic judge transient provider error", True, False
    if any(
        marker in normalized
        for marker in (
            "empty_model_response",
            "invalid",
            "malformed",
            "model not found",
            "endpoint",
        )
    ):
        retryable = "empty_model_response" in normalized
        return "semantic judge invalid provider response", retryable, False
    status_match = _HTTP_STATUS_ERROR_RE.search(normalized)
    if status_match is not None:
        status = int(status_match.group(1))
        if status == 429 or 500 <= status <= 599:
            return "semantic judge transient provider error", True, True
        return "semantic judge provider error", False, False
    if any(
        marker in normalized
        for marker in (
            "timeouterror",
            "readtimeout",
            "connecttimeout",
            "connectionerror",
            "connectionreseterror",
            "connectionrefusederror",
            "connectionabortederror",
            "urlerror",
            "remotedisconnected",
        )
    ):
        return "semantic judge transient provider error", True, True
    if any(
        marker in normalized
        for marker in (
            "timeout error",
            "timed out",
            "provider_timeout",
            "connection error",
            "connection reset",
            "connection refused",
            "connection aborted",
            "rate limit",
            "temporarily unavailable",
            "限流",
            "网络错误",
            "网络连接",
            "连接断开",
        )
    ):
        return "semantic judge transient provider error", True, False
    return "semantic judge provider error", False, False


def complete_judge_attempt_seconds(configured_attempt_timeout: float) -> float:
    """One complete first attempt under a full window, not a leftover sliver."""

    per_attempt_cap = max(0.1, float(configured_attempt_timeout))
    full_window = min(
        semantic_judge_window_seconds(),
        per_attempt_cap * MAX_SEMANTIC_JUDGE_ATTEMPTS,
    )
    return min(per_attempt_cap, full_window)


def leftover_window_blocks_complete_attempt(
    remaining_seconds: float | None,
    configured_attempt_timeout: float,
) -> bool:
    """True when the leftover window cannot fit one complete judge attempt."""

    if remaining_seconds is None:
        return False
    return float(remaining_seconds) + 1e-9 < complete_judge_attempt_seconds(
        configured_attempt_timeout
    )


def _semantic_attempt_timeouts(
    deadline: ResearchDeadline,
    *,
    configured_attempt_timeout: float,
) -> tuple[float, ...]:
    """Reserve one bounded semantic window; spend it without pre-splitting.

    ``#269`` 取消了 ``(25, 12.5, 12.5)`` 预切，每一发按一次完整尝试报价，
    由 ``_run_judge`` 窗口余额账封顶。``#272`` 压过 payload 后 grok 尾巴
    仍是 46.7s，半窗 25s 罩不住。本轮只动两处：cap 30→50，完整尝试 =
    ``min(cap, 窗)`` 不再 ``×0.5``。窗地板仍 50；T / ``_REPAIR_SECONDS_CAP``
    / 档位 / 工具批不动（R-07：有 08-20 N=5 延迟实测才抬这个 30）。

    快失败（502/连接重置）几乎不吃窗，余额账仍给下一发接近整窗；慢失败
    吃满 50s 后第三发拿 0，走既有 deadline-exhausted。episode 剩余 < 50s
    时守卫拒发——对 grok 来说那本就是半截。
    """

    per_attempt_cap = max(0.1, float(configured_attempt_timeout))
    return semantic_attempts_for_window(
        semantic_total_judge_window(
            deadline, configured_attempt_timeout=per_attempt_cap
        ),
        configured_attempt_timeout=per_attempt_cap,
    )


def semantic_attempts_for_window(
    total_window: float,
    *,
    configured_attempt_timeout: float,
) -> tuple[float, ...]:
    """Attempt quotes for an already-measured window.

    ``_run_judge`` 用这个变体，好让 ``synthesis_timeout`` 每轮只被调用一次——
    有测试用「数 synthesis_timeout 次数」的假 deadline 来关闭重试窗，多调一次
    就会把它的计数器错开。
    """

    per_attempt_cap = max(0.1, float(configured_attempt_timeout))
    if total_window <= 0.001:
        return ()
    complete = min(complete_judge_attempt_seconds(per_attempt_cap), total_window)
    if complete <= 0.001:
        return ()
    return tuple(complete for _ in range(MAX_SEMANTIC_JUDGE_ATTEMPTS))


def semantic_total_judge_window(
    deadline: ResearchDeadline,
    *,
    configured_attempt_timeout: float,
) -> float:
    """Total wall clock all judge attempts may share. Unchanged by the repartition."""

    per_attempt_cap = max(0.1, float(configured_attempt_timeout))
    return deadline.synthesis_timeout(
        min(
            semantic_judge_window_seconds(),
            per_attempt_cap * MAX_SEMANTIC_JUDGE_ATTEMPTS,
        )
    )


def _should_retry_semantic_judge(
    attempt: int,
    *,
    retryable: bool,
    release_safe: bool,
    prior_failures_release_safe: bool,
    deadline: ResearchDeadline,
) -> bool:
    """Spend a third attempt only on a typed release-grade transient."""

    if not retryable or deadline.expired:
        return False
    if attempt == 0:
        return True
    return attempt == 1 and prior_failures_release_safe and release_safe


def _next_slot_switches_judge(
    attempt: int,
    provider_count: int,
    attempt_count: int,
    deadline: ResearchDeadline,
) -> bool:
    """下一尝试槽是否会换上链上另一位判官（R-20260829-03 判官备链）。

    只在「本槽判官已放弃、但下一槽存在且映射到不同 provider、窗口未烧穿」
    时为真——它放行的是**换人**，不是给同一位判官加次数；单主链
    （provider_count<=1）恒 False，行为与改动前逐字节一致。
    """

    if provider_count <= 1 or deadline.expired:
        return False
    if attempt + 1 >= attempt_count:
        return False
    current = min(attempt, provider_count - 1)
    upcoming = min(attempt + 1, provider_count - 1)
    return upcoming != current


def _sanitize_public_answer(
    draft: str,
    evidence: tuple[AgentEvidence, ...],
    traces: tuple[ProviderTrace, ...],
) -> str:
    private_tokens = _private_tokens(evidence, traces)
    kept: list[str] = []
    for raw in str(draft or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("{") and line.endswith("}"):
            continue
        if not _contains_private_token(line, private_tokens):
            kept.append(line)
            continue
        for item in _numbered_sentences(line):
            sentence = str(item.get("text") or "").strip()
            if not sentence or _contains_private_token(sentence, private_tokens):
                continue
            if sentence.startswith("{") and sentence.endswith("}"):
                continue
            kept.append(sentence)
    return "\n".join(kept).strip()


def _private_tokens(
    evidence: tuple[AgentEvidence, ...],
    traces: tuple[ProviderTrace, ...] = (),
) -> frozenset[str]:
    return frozenset(
        token.casefold()
        for token in (
            *(item.tool for item in evidence),
            *(item.content_hash for item in evidence),
            *(trace.capability for trace in traces),
        )
        if token
    )


def _contains_private_token(value: object, private_tokens: frozenset[str]) -> bool:
    text = str(value or "")
    if not text:
        return False
    if _CONTROL_FIELD_RE.search(text):
        return True
    folded = text.casefold()
    return any(token in folded for token in private_tokens)


__all__ = [
    "REQUIRED_OUTPUT_DEGRADED_MARK",
    "SEMANTIC_QUALITY_DOUBT_MARK",
    "SemanticEpisodeOutcome",
    "SemanticEpisodeVerifier",
    "draft_sentence_count",
    "numeric_condition_unsupported",
    "v8_semantic_degrade_enabled",
]
