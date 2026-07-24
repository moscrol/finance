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
evidence or upgrade a structurally partial outcome.
"""

from __future__ import annotations

import inspect
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Literal, cast

from intelligence.services import answer_model, llm_refine
from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import (
    AgentModelClient,
    AgentOutcome,
    ModelTurn,
)
from intelligence.services.episode_finalizer import EpisodeFinalizer
from intelligence.services.episode_verifier import (
    VerifiedEpisodeOutcome,
    verify_episode_outcome,
)
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import (
    ResearchDeadline,
    ResearchTaskContract,
)
from intelligence.services.task_fulfillment import answer_has_output_marker
from intelligence.services.task_frame import TaskFrame


SemanticStatus = Literal["completed", "partial", "failed"]
JudgeStatus = Literal["passed", "repaired", "rejected", "unavailable"]
DEFAULT_JUDGE_TIMEOUT_SECONDS = 25.0
JudgeFn = Callable[..., object]

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
_NUMERIC_CONDITION_ISSUE = "unsupported numeric condition without bound evidence"
_CALENDAR_WEEKDAY_ISSUE = "calendar weekday mismatch with bound evidence"
_PATH_TREND_ISSUE = "path trend mismatch with bound evidence"
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
    r"一路(?:下跌|下滑|滑落|下降|回落|萎缩|走低)"
)
_UPWARD_PATH_RE = re.compile(
    r"一路(?:上升|上涨|攀升|走高|增长|放大)"
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
    "只能用“本轮资讯检索未命中”等自然语言。evidence_registry 使用本次裁判内的 "
    "E 编号，output_bindings.evidence_ids 与其对应。遵循 claim_policy。只输出一个严格 "
    "JSON 对象，字段必须是 "
    "passed(boolean)、rejected_sentence_indexes(integer list)、issues(string list)。"
    "passed=true 时 rejected_sentence_indexes 必须为空；发现违反上述边界的句子时"
    "passed=false 并列出句号。必须从第1句检查到最后一句，一次返回全部不合格句号；"
    "不得发现首批问题后提前停止。issues 只能描述不合格句；issues 中明确提到的"
    "句号集合必须与 rejected_sentence_indexes 一致。若提供 "
    "submit_grounding_report 函数，必须优先"
    "调用它提交上述三个字段；只有不支持函数调用时才直接输出 JSON。"
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


@dataclass(frozen=True)
class SemanticEpisodeOutcome:
    verified: VerifiedEpisodeOutcome
    status: SemanticStatus
    public_answer: str
    judge_status: JudgeStatus
    issues: tuple[str, ...] = ()
    correlated_judge: bool = False
    gap_output_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        """Return the private artifact shape (public text stays sanitized)."""

        return {
            "status": self.status,
            "public_answer": self.public_answer,
            "judge_status": self.judge_status,
            "issues": list(self.issues),
            "correlated_judge": self.correlated_judge,
            "gap_output_ids": list(self.gap_output_ids),
            "verified": self.verified.to_dict(),
        }


@dataclass(frozen=True)
class _JudgeCall:
    report: answer_model.GroundingJudgeReport | None
    unavailable: bool
    correlated: bool
    issue: str = ""
    root_deadline_exhausted: bool = False


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
        finalizer: EpisodeFinalizer | None = None,
        *,
        primary_judge: AgentModelClient | JudgeFn | None = None,
        judge_client: AgentModelClient | JudgeFn | None = None,
        judge_timeout: float = DEFAULT_JUDGE_TIMEOUT_SECONDS,
    ) -> None:
        self._judge_fn = judge_fn
        self._primary_judge = primary_judge or judge_client
        self._finalizer = finalizer
        self._judge_timeout = max(0.1, float(judge_timeout))

    def verify(
        self,
        *,
        frame: TaskFrame,
        structurally_verified: VerifiedEpisodeOutcome,
        deadline: ResearchDeadline,
    ) -> SemanticEpisodeOutcome:
        """Run structural-first verification with bounded deletion-only repair."""

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
            # A semantic pass cannot promote a structural partial.  Avoid even
            # calling the judge when no useful required output survived or the
            # partial was caused by anything other than an explicit evidence
            # gap.  A mixed fulfilled/gap result may still be judged and
            # released as partial, but can never be promoted to completed.
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
                        dict.fromkeys((*structural.issues, _NUMERIC_CONDITION_ISSUE))
                    ),
                    correlated_judge=False,
                )
            structural, _preflight_frame = preflight
            preflight_issues = tuple(
                issue
                for indexes, issue in (
                    (numeric_rejected, _NUMERIC_CONDITION_ISSUE),
                    (weekday_rejected, _CALENDAR_WEEKDAY_ISSUE),
                    (path_rejected, _PATH_TREND_ISSUE),
                )
                if indexes
            )
            marker_loss = _lost_required_output_markers(
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

        request = self._judge_request(frame, structural, sentences)
        first = self._run_judge(request, deadline)
        if deadline.expired:
            first = _JudgeCall(
                None,
                True,
                first.correlated,
                "semantic judge deadline exhausted",
            )
        if first.report is None:
            issue = first.issue or "semantic judge unavailable"
            return SemanticEpisodeOutcome(
                verified=structural,
                status="partial",
                public_answer=self._gap_answer(frame, structural),
                judge_status="unavailable",
                issues=tuple(
                    dict.fromkeys((*structural.issues, *preflight_issues, issue))
                ),
                correlated_judge=first.correlated,
            )

        first = _apply_numeric_condition_gate(first, sentences, structural)
        assert first.report is not None
        if first.report.passed:
            if marker_loss_outputs:
                return self._marker_loss_partial_public(
                    frame,
                    structural,
                    marker_loss_outputs,
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
            )

        repaired = self._repair(
            frame=frame,
            structural=structural,
            rejected_sentence_indexes=first.report.rejected_sentence_indexes,
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
            return SemanticEpisodeOutcome(
                verified=structural,
                status="partial",
                public_answer=self._gap_answer(frame, structural),
                judge_status="rejected",
                issues=issues,
                correlated_judge=first.correlated,
            )

        repaired_verified, _repaired_frame = repaired
        marker_loss = _lost_required_output_markers(
            contract,
            structural.outcome.draft,
            repaired_verified.outcome.draft,
        )
        marker_loss = tuple(
            dict.fromkeys((*marker_loss_outputs, *marker_loss))
        )
        if marker_loss:
            issues = tuple(
                dict.fromkeys(
                    (
                        *repaired_verified.issues,
                        *preflight_issues,
                        *first.report.issues,
                        *_marker_loss_issues(marker_loss),
                    )
                )
            )
            return self._marker_loss_partial_public(
                frame,
                repaired_verified,
                marker_loss,
                judge_issues=issues,
                correlated_judge=first.correlated,
            )
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
            return SemanticEpisodeOutcome(
                verified=repaired_verified,
                status="partial",
                public_answer=self._gap_answer(frame, repaired_verified),
                judge_status="rejected",
                issues=issues,
                correlated_judge=first.correlated,
            )

        # The re-judge sees the repaired draft but exactly the same evidence.
        repaired_sentences = _numbered_sentences(repaired_verified.outcome.draft)
        second = self._run_judge(
            self._judge_request(frame, repaired_verified, repaired_sentences),
            deadline,
        )
        second = _apply_optional_rejudge_deadline(second, deadline)
        second = _apply_numeric_condition_gate(
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
            )

        if second.report is None and second.root_deadline_exhausted:
            # The first completed report reviewed the entire original draft
            # and named the only spans it rejected. Removing those spans is a
            # monotonic operation: it cannot add a claim or evidence. A
            # best-effort rejudge may catch omissions, but its timeout must not
            # erase the already-reviewed remainder.
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
            )

        if (
            second.report is not None
            and second.report.rejected_sentence_indexes
        ):
            repaired_twice = self._repair(
                frame=frame,
                structural=repaired_verified,
                rejected_sentence_indexes=second.report.rejected_sentence_indexes,
            )
            if repaired_twice is not None:
                twice_verified, _twice_frame = repaired_twice
                second_marker_loss = _lost_required_output_markers(
                    contract,
                    repaired_verified.outcome.draft,
                    twice_verified.outcome.draft,
                )
                if second_marker_loss:
                    issues = tuple(
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
                    return self._marker_loss_partial_public(
                        frame,
                        twice_verified,
                        second_marker_loss,
                        judge_issues=issues,
                        correlated_judge=correlated,
                    )
                if (
                    twice_verified.verified_status == "completed"
                    or _can_semantically_release_partial(twice_verified)
                ):
                    twice_sentences = _numbered_sentences(
                        twice_verified.outcome.draft
                    )
                    third = self._run_judge(
                        self._judge_request(
                            frame,
                            twice_verified,
                            twice_sentences,
                        ),
                        deadline,
                    )
                    third = _apply_optional_rejudge_deadline(third, deadline)
                    third = _apply_numeric_condition_gate(
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
                        )
                    if third.report is None and third.root_deadline_exhausted:
                        # The second completed report reviewed the once-
                        # repaired draft. Its exact rejected spans have now
                        # been removed, so an optional final rejudge timeout
                        # cannot erase that twice-reviewed remainder.
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
                        terminal_repair = self._repair(
                            frame=frame,
                            structural=twice_verified,
                            rejected_sentence_indexes=(
                                third.report.rejected_sentence_indexes
                            ),
                        )
                        if terminal_repair is not None:
                            terminal_verified, _terminal_frame = terminal_repair
                            terminal_marker_loss = _lost_required_output_markers(
                                contract,
                                twice_verified.outcome.draft,
                                terminal_verified.outcome.draft,
                            )
                            if terminal_marker_loss and (
                                terminal_verified.verified_status == "completed"
                                or _can_semantically_release_partial(
                                    terminal_verified
                                )
                            ):
                                return self._marker_loss_partial_public(
                                    frame,
                                    terminal_verified,
                                    terminal_marker_loss,
                                    judge_issues=tuple(
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
                                    ),
                                    correlated_judge=correlated,
                                )
                            if not terminal_marker_loss and (
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
                    return SemanticEpisodeOutcome(
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
        return SemanticEpisodeOutcome(
            verified=repaired_verified,
            status="partial",
            public_answer=self._gap_answer(frame, repaired_verified),
            judge_status=("unavailable" if second.report is None else "rejected"),
            issues=issues,
            correlated_judge=correlated,
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
        return {
            "question": frame.raw_question,
            "task_frame": {
                "subject": frame.subject,
                "subject_kind": frame.subject_kind,
                "question_type": frame.question_type,
                "timeframe": frame.timeframe,
                "user_goal": frame.user_goal,
            },
            "required_outputs": required_outputs,
            "output_bindings": output_bindings,
            "evidence_registry": evidence_registry,
            "tool_status_registry": _semantic_tool_status_registry(
                verified.outcome.traces
            ),
            "claim_policy": dict(_CLAIM_POLICY),
            "sentences": sentences,
        }

    def _run_judge(
        self,
        request: dict[str, object],
        deadline: ResearchDeadline,
    ) -> _JudgeCall:
        timeout = deadline.synthesis_timeout(self._judge_timeout)
        if timeout <= 0.001:
            return _JudgeCall(
                None,
                True,
                False,
                "semantic judge deadline exhausted",
                root_deadline_exhausted=True,
            )

        provider = None
        try:
            provider = llm_refine.judge_provider()
        except Exception:
            provider = None
        if provider is not None:
            messages = [
                {"role": "system", "content": _JUDGE_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(request, ensure_ascii=False),
                },
            ]
            for attempt in range(2):
                attempt_timeout = deadline.synthesis_timeout(self._judge_timeout)
                if attempt_timeout <= 0.001:
                    return _JudgeCall(
                        None,
                        True,
                        False,
                        "semantic judge deadline exhausted",
                        root_deadline_exhausted=True,
                    )
                try:
                    with llm_refine.provider_override(provider):
                        content, _used, reason = llm_refine.complete(
                            messages,
                            timeout=attempt_timeout,
                            temperature=0.0,
                        )
                except Exception as exc:  # pragma: no cover - adapter boundary
                    issue, retryable = _stable_semantic_judge_error(
                        type(exc).__name__
                    )
                    if attempt == 0 and retryable and not deadline.expired:
                        continue
                    return _JudgeCall(None, True, False, issue)
                report = self._parse_report(content, len(request["sentences"]))
                if report is not None:
                    return _JudgeCall(report, False, False)
                issue, retryable = _stable_semantic_judge_error(
                    reason or "invalid semantic judge output"
                )
                if attempt == 0 and retryable and not deadline.expired:
                    continue
                return _JudgeCall(None, True, False, issue)
            return _JudgeCall(None, True, False, "semantic judge unavailable")

        # Explicit injection is the deterministic test/canary seam only when
        # no independent LLM_JUDGE provider is configured.  It is correlated
        # because it normally shares the primary composer model.
        if self._judge_fn is not None:
            return self._invoke_injected(self._judge_fn, request, timeout, True)

        primary = self._primary_judge
        if primary is None and self._finalizer is not None:
            primary = getattr(self._finalizer, "_model", None)
        if primary is None:
            return _JudgeCall(None, True, True, "semantic judge unavailable")
        if callable(primary) and not hasattr(primary, "complete"):
            return self._invoke_injected(cast(JudgeFn, primary), request, timeout, True)
        messages = [
            {"role": "system", "content": _JUDGE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(request, ensure_ascii=False),
            },
        ]
        for attempt in range(2):
            attempt_timeout = deadline.synthesis_timeout(self._judge_timeout)
            if attempt_timeout <= 0.001:
                return _JudgeCall(
                    None,
                    True,
                    True,
                    "semantic judge deadline exhausted",
                    root_deadline_exhausted=True,
                )
            try:
                turn = primary.complete(
                    messages=messages,
                    tools=_JUDGE_REPORT_TOOLS,
                    timeout=attempt_timeout,
                )
            except Exception as exc:
                issue, retryable = _stable_semantic_judge_error(type(exc).__name__)
                if attempt == 0 and retryable and not deadline.expired:
                    continue
                return _JudgeCall(None, True, True, issue)
            if not isinstance(turn, ModelTurn):
                return _JudgeCall(
                    None,
                    True,
                    True,
                    "semantic judge invalid provider response",
                )
            if turn.error:
                issue, retryable = _stable_semantic_judge_error(turn.error)
                if attempt == 0 and retryable and not deadline.expired:
                    continue
                return _JudgeCall(None, True, True, issue)
            if turn.tool_calls:
                report = self._parse_tool_report(
                    turn,
                    len(request["sentences"]),
                )
                if report is None:
                    return _JudgeCall(
                        None,
                        True,
                        True,
                        "semantic judge returned an invalid tool call",
                    )
                return _JudgeCall(report, False, True)
            report = self._parse_report(turn.content, len(request["sentences"]))
            if report is None:
                return _JudgeCall(None, True, True, "invalid semantic judge output")
            return _JudgeCall(report, False, True)
        return _JudgeCall(None, True, True, "semantic judge unavailable")

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
    ) -> _JudgeCall:
        try:
            value = _call_flexible(fn, request, timeout)
        except Exception as exc:
            return _JudgeCall(
                None,
                True,
                correlated,
                f"semantic judge unavailable: {type(exc).__name__}",
            )
        report = SemanticEpisodeVerifier._parse_report(
            value,
            len(cast(list[object], request["sentences"])),
        )
        if report is None:
            return _JudgeCall(None, True, correlated, "invalid semantic judge output")
        return _JudgeCall(report, False, correlated)

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
        repaired_outcome = AgentOutcome(
            task_frame_hash=original.task_frame_hash,
            status=original.status,
            draft=draft,
            evidence=original.evidence,
            traces=original.traces,
            gaps=original.gaps,
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
    ) -> SemanticEpisodeOutcome:
        public = _sanitize_public_answer(
            verified.outcome.draft,
            verified.outcome.evidence,
            verified.outcome.traces,
        )
        if not public:
            return SemanticEpisodeOutcome(
                verified=verified,
                status="partial",
                public_answer=self._gap_answer(frame, verified),
                judge_status=judge_status,
                issues=tuple(dict.fromkeys((*judge_issues, "public projection empty"))),
                correlated_judge=correlated_judge,
            )
        return SemanticEpisodeOutcome(
            verified=verified,
            status=(
                "completed"
                if verified.verified_status == "completed"
                else "partial"
            ),
            public_answer=public,
            judge_status=judge_status,
            issues=judge_issues,
            correlated_judge=correlated_judge,
        )

    def _marker_loss_partial_public(
        self,
        frame: TaskFrame,
        verified: VerifiedEpisodeOutcome,
        output_ids: tuple[str, ...],
        *,
        judge_issues: tuple[str, ...],
        correlated_judge: bool,
    ) -> SemanticEpisodeOutcome:
        """Keep reviewed remainder and expose only the deleted slot as a gap."""

        public = _sanitize_public_answer(
            verified.outcome.draft,
            verified.outcome.evidence,
            verified.outcome.traces,
        )
        if not public:
            return SemanticEpisodeOutcome(
                verified=verified,
                status="partial",
                public_answer=self._gap_answer(frame, verified),
                judge_status="repaired",
                issues=judge_issues,
                correlated_judge=correlated_judge,
                gap_output_ids=output_ids,
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
        gap = (
            "证据缺口："
            + "、".join(labels)
            + "中的未核验表述已删除，需补充直接证据后再判断。"
        )
        return SemanticEpisodeOutcome(
            verified=verified,
            status="partial",
            public_answer=f"{public}\n{gap}",
            judge_status="repaired",
            issues=judge_issues,
            correlated_judge=correlated_judge,
            gap_output_ids=output_ids,
        )

    @staticmethod
    def _gap_answer(
        frame: TaskFrame,
        verified: VerifiedEpisodeOutcome,
    ) -> str:
        question = frame.raw_question.strip() or "当前问题"
        contract = verified.contract
        if contract is not None:
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
                    (item.description.strip() or item.output_id)
                    for item in targets
                    if item.description.strip() or item.output_id
                )
            )
            if labels:
                return (
                    f"关于“{question}”，现有证据不足，暂不能可靠回答。"
                    + "仍需核验："
                    + "、".join(labels[:3])
                )
        return f"关于“{question}”，现有证据不足，暂不能可靠回答。"

    @staticmethod
    def _generic_gap_answer(frame: TaskFrame) -> str:
        question = frame.raw_question.strip() or "当前问题"
        return f"关于“{question}”，现有证据不足，暂不能可靠回答。"


def _can_semantically_release_partial(
    verified: VerifiedEpisodeOutcome,
) -> bool:
    """Allow a useful partial through the judge without weakening hard gates.

    Only an explicit required-output evidence gap is eligible.  Missing
    bindings, unknown hashes, frame mismatches, and every other structural
    issue still fail closed before the semantic judge sees the draft.
    """

    if verified.verified_status != "partial":
        return False
    if not verified.outcome.draft.strip():
        return False
    if not any(
        item.status == "fulfilled" for item in verified.completion.outputs
    ):
        return False
    if (
        verified.outcome.status == "partial"
        and not verified.issues
        and verified.completion.factual_grounding == "fulfilled"
        and verified.completion.task_coverage == "fulfilled"
    ):
        # The runtime declared an honest partial even though every structural
        # binding is present. Judge the prose, but preserve the partial status.
        return True
    if not verified.issues:
        return False
    return all(
        issue.startswith(
            (
                "required output reports gap:",
                "missing mandatory capability evidence:",
            )
        )
        for issue in verified.issues
    )


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
    issues = tuple(dict.fromkeys((*report.issues, _NUMERIC_CONDITION_ISSUE)))
    return _JudgeCall(
        answer_model.GroundingJudgeReport(
            passed=False,
            rejected_sentence_indexes=tuple(sorted(rejected)),
            issues=issues,
        ),
        call.unavailable,
        call.correlated,
        call.issue,
        call.root_deadline_exhausted,
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
        return _JudgeCall(
            None,
            True,
            call.correlated,
            "semantic judge deadline exhausted",
            root_deadline_exhausted=True,
        )
    return call


def _novel_numeric_condition_indexes(
    sentences: list[dict[str, object]],
    verified: VerifiedEpisodeOutcome,
) -> tuple[int, ...]:
    """Return conditional sentences containing quantities absent from evidence."""

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
    not monotonic.  The narrow ``一路`` gate only fires when at least three
    dated turnover observations are bound, so ordinary two-point comparisons
    and explicitly local statements such as ``连续两个交易日回落`` remain the
    semantic judge's responsibility.
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
        if not isinstance(index, int) or "成交额" not in text:
            continue
        if _DOWNWARD_PATH_RE.search(text) and not is_non_increasing:
            rejected.add(index)
        if _UPWARD_PATH_RE.search(text) and not is_non_decreasing:
            rejected.add(index)
    return tuple(sorted(rejected))


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
    return frozenset(
        _normalize_quantity(quantity)
        for quantity in (
            *_ARABIC_QUANTITY_RE.findall(corpus),
            *_CHINESE_QUANTITY_RE.findall(corpus),
        )
        if _normalize_quantity(quantity)
    )


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
    return _renumber_ordered_list_items(source.strip())


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
    return "".join(rendered)


def _lost_required_output_markers(
    contract: ResearchTaskContract,
    before: str,
    after: str,
) -> tuple[str, ...]:
    """Prevent sentence repair from silently deleting a visible answer slot."""

    return tuple(
        item.output_id
        for item in contract.required_outputs
        if item.required
        and answer_has_output_marker(item.output_id, before)
        and not answer_has_output_marker(item.output_id, after)
    )


def _marker_loss_issues(output_ids: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        f"semantic repair removed required output: {output_id}"
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


def _semantic_evidence_projection(
    outcome: AgentOutcome,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Alias and project only answer-bound evidence for semantic judging."""

    bound_hashes = {
        evidence_hash
        for binding in outcome.bindings
        for evidence_hash in binding.evidence_hashes
    }
    alias_by_hash: dict[str, str] = {}
    registry: list[dict[str, object]] = []
    for item in outcome.evidence:
        if not item.content_hash or item.content_hash not in bound_hashes:
            continue
        evidence_id = f"E{len(registry) + 1}"
        alias_by_hash[item.content_hash] = evidence_id
        projected: dict[str, object] = {
            "evidence_id": evidence_id,
            "tool": item.tool,
            "detail": item.detail or item.title,
            "source_date": item.source_date,
            "evidence_tier": item.evidence_tier,
        }
        if item.freshness and item.freshness != "unknown":
            projected["freshness"] = item.freshness
        if item.supports:
            projected["supports"] = list(item.supports)
        if item.contradicts:
            projected["contradicts"] = list(item.contradicts)
        if item.independent_key:
            projected["independent_key"] = item.independent_key
        registry.append(projected)
    bindings = [
        {
            "output_id": binding.output_id,
            "evidence_ids": [
                alias_by_hash[evidence_hash]
                for evidence_hash in binding.evidence_hashes
                if evidence_hash in alias_by_hash
            ],
            "gap": binding.gap,
        }
        for binding in outcome.bindings
    ]
    return bindings, registry


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
            output_bindings=request["output_bindings"],
            evidence_registry=request["evidence_registry"],
            tool_status_registry=request["tool_status_registry"],
            claim_policy=request["claim_policy"],
            sentences=request["sentences"],
            timeout=timeout,
        )
    named = {
        name: request[name]
        for name in (
            "question",
            "required_outputs",
            "output_bindings",
            "evidence_registry",
            "tool_status_registry",
            "claim_policy",
            "sentences",
        )
        if name in parameters
    }
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
            "output_bindings": request["output_bindings"],
            "bindings": request["output_bindings"],
            "evidence_registry": request["evidence_registry"],
            "evidence": request["evidence_registry"],
            "registry": request["evidence_registry"],
            "tool_status_registry": request["tool_status_registry"],
            "tool_statuses": request["tool_status_registry"],
            "claim_policy": request["claim_policy"],
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


def _stable_semantic_judge_error(value: object) -> tuple[str, bool]:
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
        return "semantic judge configuration error", False
    if "budget" in normalized or "预算" in normalized:
        return "semantic judge call budget exhausted", False
    if "cancel" in normalized or "取消" in normalized:
        return "semantic judge cancelled", False
    if any(
        marker in normalized
        for marker in (
            "timeout",
            "timed out",
            "remote",
            "urlerror",
            "connection",
            "empty_model_response",
            "rate limit",
            "temporar",
            "429",
            "500",
            "502",
            "503",
            "504",
            "限流",
            "网络",
            "断开",
        )
    ):
        return "semantic judge transient provider error", True
    if "invalid" in normalized or "malformed" in normalized:
        return "semantic judge invalid provider response", False
    return "semantic judge provider error", False


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
        if _contains_private_token(line, private_tokens):
            continue
        if line.startswith("{") and line.endswith("}"):
            continue
        kept.append(line)
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


__all__ = ["SemanticEpisodeOutcome", "SemanticEpisodeVerifier"]
