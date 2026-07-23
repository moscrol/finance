"""Semantic grounding gate for one continuous research episode.

``episode_verifier`` proves only the structural part of an episode: every
required output has a valid evidence binding.  This module is the deliberately
separate semantic gate.  It gives a private, numbered evidence registry to a
strict JSON judge, permits one targeted repair, and projects only a safe answer
to the public boundary.

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
from typing import Literal, cast

from intelligence.services import answer_model, llm_refine
from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import (
    AgentModelClient,
    AgentOutcome,
    ModelTurn,
    public_agent_evidence,
)
from intelligence.services.episode_finalizer import EpisodeFinalizer
from intelligence.services.episode_verifier import (
    VerifiedEpisodeOutcome,
    verify_episode_outcome,
)
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import ResearchDeadline
from intelligence.services.task_frame import TaskFrame


SemanticStatus = Literal["completed", "partial", "failed"]
JudgeStatus = Literal["passed", "repaired", "rejected", "unavailable"]
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
_CONDITION_TRIGGER_RE = re.compile(
    r"(?:若|如果|条件|失效|降级|跌破|站稳|维持|至少|以上|以下|"
    r"阈值|支撑|保持|骤降|才算成立|才成立)"
)
_LEADING_CONDITION_LABEL_RE = re.compile(
    r"^\s*(?:[-*]\s*)?"
    r"(?:条件|失效信号|降级信号|触发条件)\s*"
    r"(?:\d+|[一二三四五六七八九十]+)?"
    r"\s*(?:[:：、.)）-]\s*)?"
)
_DATE_TOKEN_RE = re.compile(
    r"(?:20\d{2}年\d{1,2}月\d{1,2}日|"
    r"20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}|"
    r"\d{1,2}月\d{1,2}日)"
)
_ARABIC_QUANTITY_RE = re.compile(
    r"[+-]?\d[\d,]*(?:\.\d+)?"
    r"(?:\s*(?:至|到|~|～|—|-)\s*[+-]?\d[\d,]*(?:\.\d+)?)?"
    r"\s*(?:万亿元|亿元|个百分点|%|点|家|只|个|天|日|周|月|年|倍|成)?"
)
_CHINESE_QUANTITY_RE = re.compile(
    r"[一二两三四五六七八九十百千万亿]+"
    r"(?:万亿元|亿元|个百分点|点|家|只|个|天|日|周|月|年|倍|成)"
)
_NUMERIC_CONDITION_ISSUE = (
    "unsupported numeric condition without bound evidence"
)

_JUDGE_SYSTEM_PROMPT = (
    "你是严格的语义证据审查器。只审查用户 JSON 中的原问题、required-output "
    "绑定、证据注册表和编号句子；不要引入外部知识，也不要重写句子。检查主体、"
    "当前时点、事实/假设边界、因果证据、数字支持和跨题污染。观察事实、事实数字、"
    "外部因果和历史概率必须有直接证据。分析问题允许从已绑定事实做透明推导：若"
    "句子明确标注为判断、情景或估计，且推理前提可在证据中核验，不要要求 evidence "
    "原文已经包含预测结论。用户明确要求持续时间、空间、估值或其他预测时，允许"
    "给出带不确定性和条件的主观区间；但发明外部原因、支持性统计或任意触发阈值仍"
    "应拒绝。tool_status_registry 只支持检索过程状态，例如本轮是否命中；它不能支持"
    "市场事实或因果结论。答案不得暴露 capability、工具、provider 或哈希等内部标识，"
    "只能用“本轮资讯检索未命中”等自然语言。遵循 claim_policy。只输出一个严格 "
    "JSON 对象，字段必须是 "
    "passed(boolean)、rejected_sentence_indexes(integer list)、issues(string list)。"
    "passed=true 时 rejected_sentence_indexes 必须为空；发现违反上述边界的句子时"
    "passed=false 并列出句号。必须从第1句检查到最后一句，一次返回全部不合格句号；"
    "不得发现首批问题后提前停止。"
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

    def to_dict(self) -> dict[str, object]:
        """Return the private artifact shape (public text stays sanitized)."""

        return {
            "status": self.status,
            "public_answer": self.public_answer,
            "judge_status": self.judge_status,
            "issues": list(self.issues),
            "correlated_judge": self.correlated_judge,
            "verified": self.verified.to_dict(),
        }


@dataclass(frozen=True)
class _JudgeCall:
    report: answer_model.GroundingJudgeReport | None
    unavailable: bool
    correlated: bool
    issue: str = ""


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
        judge_timeout: float = 10.0,
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
        """Run structural-first semantic verification and at most one repair."""

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
        if structural.verified_status != "completed":
            # A semantic pass cannot promote a structural partial.  Avoid even
            # calling the judge here: no amount of semantic confidence repairs
            # a missing output binding.
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
                issues=tuple(dict.fromkeys((*structural.issues, issue))),
                correlated_judge=first.correlated,
            )

        first = _apply_numeric_condition_gate(first, sentences, structural)
        assert first.report is not None
        if first.report.passed:
            return self._completed_public(
                frame,
                structural,
                judge_status="passed",
                judge_issues=first.report.issues,
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
        if repaired_verified.verified_status != "completed":
            issues = tuple(
                dict.fromkeys(
                    (
                        *repaired_verified.issues,
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
        if deadline.expired:
            second = _JudgeCall(
                None,
                True,
                second.correlated,
                "semantic judge deadline exhausted",
            )
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
                    dict.fromkeys((*first.report.issues, *second.report.issues))
                ),
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
                    "evidence_types": list(item.evidence_types),
                    "required": item.required,
                }
                for item in contract.required_outputs
            ]
        else:
            required_outputs = [
                {"output_id": output_id, "required": True}
                for output_id in frame.required_outputs
            ]
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
            "output_bindings": [
                binding.to_dict() for binding in verified.outcome.bindings
            ],
            "evidence_registry": [
                public_agent_evidence(item) for item in verified.outcome.evidence
            ],
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
            return _JudgeCall(None, True, False, "semantic judge deadline exhausted")

        provider = None
        try:
            provider = llm_refine.judge_provider()
        except Exception:
            provider = None
        if provider is not None:
            try:
                with llm_refine.provider_override(provider):
                    content, _used, reason = llm_refine.complete(
                        [
                            {"role": "system", "content": _JUDGE_SYSTEM_PROMPT},
                            {
                                "role": "user",
                                "content": json.dumps(request, ensure_ascii=False),
                            },
                        ],
                        timeout=timeout,
                        temperature=0.0,
                    )
            except Exception as exc:  # pragma: no cover - adapter boundary
                return _JudgeCall(
                    None,
                    True,
                    False,
                    f"semantic judge unavailable: {type(exc).__name__}",
                )
            report = self._parse_report(content, len(request["sentences"]))
            if report is None:
                return _JudgeCall(
                    None, True, False, reason or "invalid semantic judge output"
                )
            return _JudgeCall(report, False, False)

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
                )
            try:
                turn = primary.complete(
                    messages=messages,
                    tools=[],
                    timeout=attempt_timeout,
                )
            except Exception as exc:
                issue, retryable = _stable_semantic_judge_error(
                    type(exc).__name__
                )
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
            if turn.tool_calls:
                return _JudgeCall(
                    None,
                    True,
                    True,
                    "semantic judge returned an invalid tool call",
                )
            if turn.error:
                issue, retryable = _stable_semantic_judge_error(turn.error)
                if attempt == 0 and retryable and not deadline.expired:
                    continue
                return _JudgeCall(None, True, True, issue)
            report = self._parse_report(turn.content, len(request["sentences"]))
            if report is None:
                return _JudgeCall(None, True, True, "invalid semantic judge output")
            return _JudgeCall(report, False, True)
        return _JudgeCall(None, True, True, "semantic judge unavailable")

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
                return value
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
            return answer_model.parse_grounding_judge_report(
                canonical,
                sentence_count=sentence_count,
            )
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
            status="completed",
            public_answer=public,
            judge_status=judge_status,
            issues=judge_issues,
            correlated_judge=correlated_judge,
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


def _numbered_sentences(draft: str) -> list[dict[str, object]]:
    sentences: list[dict[str, object]] = []
    for raw in _SENTENCE_RE.split(str(draft or "")):
        text = raw.strip()
        if not text:
            continue
        sentences.append({"index": len(sentences) + 1, "text": text})
    return sentences


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
    evidence_quantities = _bound_evidence_quantities(verified.outcome)
    for item in sentences:
        index = item.get("index")
        text = str(item.get("text") or "")
        if not isinstance(index, int) or not _CONDITION_TRIGGER_RE.search(text):
            continue
        candidate = _DATE_TOKEN_RE.sub("", text)
        candidate = _LEADING_CONDITION_LABEL_RE.sub("", candidate)
        quantities = (
            *_ARABIC_QUANTITY_RE.findall(candidate),
            *_CHINESE_QUANTITY_RE.findall(candidate),
        )
        if any(
            _normalize_quantity(quantity) not in evidence_quantities
            for quantity in quantities
            if _normalize_quantity(quantity)
        ):
            rejected.add(index)
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
    )


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
    )


def _drop_rejected_sentences(
    draft: str,
    rejected_sentence_indexes: tuple[int, ...],
) -> str:
    """Remove rejected spans while preserving accepted Markdown verbatim."""

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
    return source.strip()


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
