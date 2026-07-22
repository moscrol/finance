"""Offline checks that constraints do not make an agent less capable.

The five-dimension three-arm records are independent release evidence: after
adding retrieval and verification, did the Workbench still answer the user's
actual task?  Keyword checks remain a separate protocol gate.  The older
deterministic answer-shape metrics at the bottom of this module remain advisory
and are retained for API compatibility.

This module is deterministic and side-effect free; it never calls an LLM or a
runtime itself.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any, Mapping, Sequence

from intelligence.eval.presentation_diversity import heading_sequence


_CITATION_RE = re.compile(r"\[([A-Z]\d+)\]")
_HEADING_RE = re.compile(r"^#{1,6}\s+")
_GAP_MARKS = ("证据缺口", "暂无证据", "无法确认", "尚不能确认", "保持未知", "缺少")
_CONTROL_PLANE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("absolute_path", re.compile(r"(?:/Users/|/home/|[A-Za-z]:\\\\)[^\s，。；]+")),
    ("run_id", re.compile(r"\brun[_-]\d{8,}", re.I)),
    ("fallback_reason", re.compile(r"\bfallback_reason\b", re.I)),
    ("provider_trace", re.compile(r"\bProviderTrace\b")),
    ("artifact_field", re.compile(r"\b(?:answer_spec|decision_brief|registry_tags)\b", re.I)),
    ("internal_candidate", re.compile(r"候选来源|generic[_ ]theme|graph_only", re.I)),
)

CAPABILITY_SCORE_RUBRIC: Mapping[int, str] = {
    0: "missing or wrong",
    1: "materially inadequate",
    2: "partial",
    3: "substantially complete",
    4: "fully satisfies the dimension",
}


def _integer_field(value: Mapping[str, Any], name: str) -> int:
    item = value[name]
    if isinstance(item, bool) or not isinstance(item, int):
        raise ValueError(f"{name} must be an integer")
    return item


def _boolean_field(value: Mapping[str, Any], name: str) -> bool:
    item = value[name]
    if not isinstance(item, bool):
        raise ValueError(f"{name} must be a boolean")
    return item


@dataclass(frozen=True)
class CapabilityScore:
    """Human-judged task capability on five 0..4 dimensions.

    ``normalized_total`` is the arithmetic sum divided by the maximum possible
    sum (``5 * 4``), so comparison thresholds use an unambiguous 0..1 scale.
    """

    directness: int
    coverage: int
    relevance: int
    truth_boundary: int
    usefulness: int

    def __post_init__(self) -> None:
        for name in (
            "directness",
            "coverage",
            "relevance",
            "truth_boundary",
            "usefulness",
        ):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not 0 <= value <= 4
            ):
                raise ValueError(f"{name} must be an integer from 0 to 4")

    @property
    def total_units(self) -> int:
        """Integer score units used by the regression gate (maximum 20)."""

        return (
            self.directness
            + self.coverage
            + self.relevance
            + self.truth_boundary
            + self.usefulness
        )

    @property
    def normalized_total(self) -> float:
        return round(self.total_units / 20, 4)

    def to_dict(self) -> dict[str, int | float]:
        return {
            "directness": self.directness,
            "coverage": self.coverage,
            "relevance": self.relevance,
            "truth_boundary": self.truth_boundary,
            "usefulness": self.usefulness,
            "normalized_total": self.normalized_total,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CapabilityScore":
        return cls(
            directness=_integer_field(value, "directness"),
            coverage=_integer_field(value, "coverage"),
            relevance=_integer_field(value, "relevance"),
            truth_boundary=_integer_field(value, "truth_boundary"),
            usefulness=_integer_field(value, "usefulness"),
        )


@dataclass(frozen=True)
class ConversationMessage:
    role: str
    content: str

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ConversationMessage":
        return cls(role=str(value["role"]), content=str(value["content"]))


@dataclass(frozen=True)
class CapabilityCase:
    """Frozen inputs shared by all three evaluation arms."""

    case_id: str
    question: str
    conversation_context: tuple[ConversationMessage, ...]
    model: str
    temperature: float
    timeout: float
    as_of: str

    def __post_init__(self) -> None:
        for name in ("case_id", "question", "model", "as_of"):
            if not isinstance(getattr(self, name), str) or not getattr(
                self, name
            ).strip():
                raise ValueError(f"{name} must be a non-empty string")
        if self.temperature < 0 or self.timeout <= 0:
            raise ValueError("temperature must be non-negative and timeout positive")

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "question": self.question,
            "conversation_context": [
                item.to_dict() for item in self.conversation_context
            ],
            "model": self.model,
            "temperature": self.temperature,
            "timeout": self.timeout,
            "as_of": self.as_of,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CapabilityCase":
        return cls(
            case_id=str(value["case_id"]),
            question=str(value["question"]),
            conversation_context=tuple(
                ConversationMessage.from_dict(item)
                for item in value.get("conversation_context") or ()
            ),
            model=str(value["model"]),
            temperature=float(value["temperature"]),
            timeout=float(value["timeout"]),
            as_of=str(value["as_of"]),
        )


@dataclass(frozen=True)
class CapabilityRunResult:
    """One arm's answer, judgment, and cost metadata; latency is in seconds."""

    case_id: str
    arm: str
    answer: str
    score: CapabilityScore
    latency: float
    llm_calls: int
    tool_calls: int
    fallback_reason: str | None
    protocol_passed: bool
    protocol_issues: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.arm not in {"bare", "current", "episode"}:
            raise ValueError("arm must be bare, current, or episode")
        if not isinstance(self.protocol_passed, bool):
            raise ValueError("protocol_passed must be a boolean")
        for name in ("llm_calls", "tool_calls"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{name} must be an integer")
        if self.latency < 0 or self.llm_calls < 0 or self.tool_calls < 0:
            raise ValueError("execution metrics cannot be negative")

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "arm": self.arm,
            "answer": self.answer,
            "score": self.score.to_dict(),
            "latency": self.latency,
            "llm_calls": self.llm_calls,
            "tool_calls": self.tool_calls,
            "fallback_reason": self.fallback_reason,
            "protocol_passed": self.protocol_passed,
            "protocol_issues": list(self.protocol_issues),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CapabilityRunResult":
        answer = value["answer"]
        fallback_reason = value["fallback_reason"]
        protocol_issues = value["protocol_issues"]
        if not isinstance(answer, str):
            raise ValueError("answer must be a string")
        if fallback_reason is not None and not isinstance(fallback_reason, str):
            raise ValueError("fallback_reason must be a string or null")
        if not isinstance(protocol_issues, list) or not all(
            isinstance(item, str) for item in protocol_issues
        ):
            raise ValueError("protocol_issues must be a list of strings")
        return cls(
            case_id=str(value["case_id"]),
            arm=str(value["arm"]),
            answer=answer,
            score=CapabilityScore.from_dict(value["score"]),
            latency=float(value["latency"]),
            llm_calls=_integer_field(value, "llm_calls"),
            tool_calls=_integer_field(value, "tool_calls"),
            fallback_reason=fallback_reason,
            protocol_passed=_boolean_field(value, "protocol_passed"),
            protocol_issues=tuple(protocol_issues),
        )


@dataclass(frozen=True)
class BareComparison:
    case_id: str
    harness_arm: str
    bare_score: float
    harness_score: float
    threshold: float
    passed: bool
    failure_reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "harness_arm": self.harness_arm,
            "bare_score": self.bare_score,
            "harness_score": self.harness_score,
            "threshold": self.threshold,
            "passed": self.passed,
            "failure_reasons": list(self.failure_reasons),
        }


def compare_with_bare(
    bare: CapabilityRunResult,
    harness: CapabilityRunResult,
    *,
    threshold: float = 0.2,
) -> BareComparison:
    """Compare one harness arm to bare on the normalized 0..1 scale."""

    if bare.arm != "bare":
        raise ValueError("the baseline result must use the bare arm")
    if bare.tool_calls != 0:
        raise ValueError("bare arm must not call tools or databases")
    if not bare.protocol_passed:
        raise ValueError("bare arm protocol must pass")
    if harness.arm not in {"current", "episode"}:
        raise ValueError("the harness result must use current or episode")
    if bare.case_id != harness.case_id:
        raise ValueError("bare and harness results must belong to the same case")
    if not 0 <= threshold <= 1:
        raise ValueError("threshold must use the normalized 0..1 scale")
    bare_score = bare.score.normalized_total
    harness_score = harness.score.normalized_total
    threshold_units = Decimal(str(threshold)) * Decimal(20)
    regression = (
        Decimal(harness.score.total_units) + threshold_units
        < Decimal(bare.score.total_units)
    )
    failures: list[str] = []
    if regression:
        failures.append("capability_regression")
    if not harness.protocol_passed:
        failures.append("protocol_failed")
    return BareComparison(
        case_id=harness.case_id,
        harness_arm=harness.arm,
        bare_score=bare_score,
        harness_score=harness_score,
        threshold=threshold,
        passed=not failures,
        failure_reasons=tuple(failures),
    )


@dataclass(frozen=True)
class ThreeArmRecord:
    case: CapabilityCase
    bare: CapabilityRunResult
    current: CapabilityRunResult
    episode: CapabilityRunResult

    def __post_init__(self) -> None:
        results = (self.bare, self.current, self.episode)
        if tuple(item.arm for item in results) != ("bare", "current", "episode"):
            raise ValueError(
                "three-arm records require bare, current, and episode results"
            )
        if any(item.case_id != self.case.case_id for item in results):
            raise ValueError("all results must match the case id")

    def to_dict(self) -> dict[str, Any]:
        return {
            "case": self.case.to_dict(),
            "bare": self.bare.to_dict(),
            "current": self.current.to_dict(),
            "episode": self.episode.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ThreeArmRecord":
        return cls(
            case=CapabilityCase.from_dict(value["case"]),
            bare=CapabilityRunResult.from_dict(value["bare"]),
            current=CapabilityRunResult.from_dict(value["current"]),
            episode=CapabilityRunResult.from_dict(value["episode"]),
        )


@dataclass(frozen=True)
class ThreeArmEvaluation:
    case_id: str
    current: BareComparison
    episode: BareComparison
    record: ThreeArmRecord

    @property
    def passed(self) -> bool:
        return self.current.passed and self.episode.passed

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "passed": self.passed,
            "current": self.current.to_dict(),
            "episode": self.episode.to_dict(),
            "record": self.record.to_dict(),
        }


def evaluate_three_arm_record(
    record: ThreeArmRecord,
    *,
    threshold: float = 0.2,
) -> ThreeArmEvaluation:
    return ThreeArmEvaluation(
        case_id=record.case.case_id,
        current=compare_with_bare(record.bare, record.current, threshold=threshold),
        episode=compare_with_bare(record.bare, record.episode, threshold=threshold),
        record=record,
    )


def summarize_three_arm_records(
    records: Sequence[ThreeArmRecord],
    *,
    threshold: float = 0.2,
) -> dict[str, Any]:
    """Build the independent evidence document consumed by acceptance gates."""

    evaluations = [
        evaluate_three_arm_record(record, threshold=threshold) for record in records
    ]
    comparisons = [
        comparison
        for evaluation in evaluations
        for comparison in (evaluation.current, evaluation.episode)
    ]
    return {
        "schema_version": 1,
        "gate": "capability_monotonicity",
        "score_scale": {
            "dimension_min": 0,
            "dimension_max": 4,
            "dimension_count": 5,
            "normalization": "sum(dimensions) / 20",
            "normalized_range": [0.0, 1.0],
            "rubric": dict(CAPABILITY_SCORE_RUBRIC),
        },
        "threshold": threshold,
        "evidence_present": bool(evaluations),
        "passed": bool(evaluations) and all(item.passed for item in evaluations),
        "case_count": len(evaluations),
        "arm_comparison_count": len(comparisons),
        "regression_count": sum(
            "capability_regression" in item.failure_reasons for item in comparisons
        ),
        "failed_comparison_count": sum(not item.passed for item in comparisons),
        "evaluations": [item.to_dict() for item in evaluations],
    }


DEFAULT_CAPABILITY_CASES: tuple[CapabilityCase, ...] = (
    CapabilityCase(
        case_id="rebound-duration",
        question="昨天的反弹能持续多久",
        conversation_context=(
            ConversationMessage(
                role="user",
                content="只讨论 A 股整体市场，不讨论个股。",
            ),
        ),
        model="glm-5.2",
        temperature=0.0,
        timeout=180.0,
        as_of="2026-07-22",
    ),
    CapabilityCase(
        case_id="current-mainline",
        question="目前市场的主线是什么",
        conversation_context=(),
        model="glm-5.2",
        temperature=0.0,
        timeout=180.0,
        as_of="2026-07-22",
    ),
    CapabilityCase(
        case_id="unfamiliar-theme-without-skill",
        question="一个没有现成 skill 的陌生题材怎么判断",
        conversation_context=(
            ConversationMessage(
                role="user",
                content="请先给判断方法，再说明实时证据缺口。",
            ),
        ),
        model="glm-5.2",
        temperature=0.0,
        timeout=180.0,
        as_of="2026-07-22",
    ),
)


def build_fixture_document() -> dict[str, Any]:
    """Return the offline fixture plus the execution contract for each arm."""

    return {
        "schema_version": 1,
        "arm_contracts": {
            "bare": "send only question; no tools or databases",
            "current": "run the current Workbench",
            "episode": "run the continuous AgentEpisode candidate",
        },
        "score_scale": {
            "dimensions": [
                "directness",
                "coverage",
                "relevance",
                "truth_boundary",
                "usefulness",
            ],
            "rubric": dict(CAPABILITY_SCORE_RUBRIC),
            "normalization": "sum(dimensions) / 20",
        },
        "cases": [case.to_dict() for case in DEFAULT_CAPABILITY_CASES],
    }


@dataclass(frozen=True)
class AdvisoryCapabilityScore:
    case_id: str
    directness: float
    task_coverage: float
    grounding: float
    control_plane_leak_score: float
    template_signature: str
    fallback_fidelity: float
    missing_outputs: tuple[str, ...] = ()
    leak_kinds: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CapabilityComparison:
    case_id: str
    minimal: AdvisoryCapabilityScore
    workbench: AdvisoryCapabilityScore
    deltas: Mapping[str, float]
    monotonic: bool
    regressions: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["minimal"] = self.minimal.to_dict()
        value["workbench"] = self.workbench.to_dict()
        return value


def _normalized(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "", str(text or "")).lower()


def _first_paragraph(answer: str) -> str:
    for raw in str(answer or "").splitlines():
        line = raw.strip()
        if not line or _HEADING_RE.match(line):
            continue
        return line[:240]
    return ""


def _contains_any(text: str, values: Sequence[str]) -> bool:
    normalized = _normalized(text)
    return any(_normalized(value) in normalized for value in values if _normalized(value))


def directness_score(
    question: str,
    answer: str,
    *,
    direct_targets: Sequence[str] = (),
) -> float:
    """Score whether the first substantive paragraph answers the requested goal."""
    lead = _first_paragraph(answer)
    if not lead:
        return 0.0
    targets = tuple(direct_targets) or tuple(
        token
        for token in re.findall(r"[A-Za-z][A-Za-z0-9_-]{1,}|[\u4e00-\u9fff]{2,6}", question)
        if token not in {"什么", "怎么", "如何", "认为", "是否", "主要", "这一周"}
    )
    if targets and _contains_any(lead, targets):
        return 1.0
    if _contains_any(lead, _GAP_MARKS):
        return 0.8
    if targets and _contains_any(answer, targets):
        return 0.45
    return 0.25 if len(_normalized(lead)) >= 12 else 0.0


def task_coverage_score(
    answer: str,
    requirements: Sequence[Mapping[str, Any]],
) -> tuple[float, tuple[str, ...]]:
    """Treat an explicit evidence gap as coverage, not as a fabricated success."""
    if not requirements:
        return (1.0 if str(answer or "").strip() else 0.0), ()
    fulfilled = 0
    missing: list[str] = []
    for item in requirements:
        output_id = str(item.get("id") or "required_output")
        satisfy_any = tuple(str(value) for value in item.get("satisfy_any") or ())
        gap_any = tuple(str(value) for value in item.get("gap_any") or _GAP_MARKS)
        if _contains_any(answer, satisfy_any) or _contains_any(answer, gap_any):
            fulfilled += 1
        else:
            missing.append(output_id)
    return round(fulfilled / len(requirements), 4), tuple(missing)


def grounding_score(
    answer: str,
    claims: Sequence[Mapping[str, Any]] = (),
    evidence_ids: Sequence[str] = (),
) -> float:
    """Ratio of auditable claims linked to evidence known to the run."""
    if claims:
        registry = {str(item) for item in evidence_ids}
        factual = [item for item in claims if bool(item.get("factual", True))]
        if not factual:
            return 1.0
        grounded = 0
        for claim in factual:
            linked = {str(item) for item in claim.get("evidence_ids") or ()}
            if linked and (not registry or linked.issubset(registry)):
                grounded += 1
        return round(grounded / len(factual), 4)

    citations = _CITATION_RE.findall(str(answer or ""))
    if citations:
        registry = {str(item) for item in evidence_ids}
        if not registry:
            return 1.0
        return round(sum(tag in registry for tag in citations) / len(citations), 4)
    # A fail-closed gap contains no affirmative fact that needs grounding.
    if _contains_any(answer, _GAP_MARKS):
        return 1.0
    return 0.0


def control_plane_leak_score(answer: str) -> tuple[float, tuple[str, ...]]:
    """Return 0 for a clean answer and approach 1 as leak classes accumulate."""
    kinds = tuple(name for name, pattern in _CONTROL_PLANE_PATTERNS if pattern.search(answer or ""))
    return round(min(1.0, len(kinds) / 3), 4), kinds


def template_signature(answer: str) -> str:
    """Compact heading/paragraph-function signature for batch comparison."""
    headings = heading_sequence(answer)
    roles: list[str] = []
    for raw in str(answer or "").splitlines():
        line = raw.strip()
        if not line or _HEADING_RE.match(line):
            continue
        if line.startswith(("-", "*")):
            role = "bullet"
        elif _contains_any(line, _GAP_MARKS):
            role = "gap"
        elif any(mark in line for mark in ("因此", "所以", "核心", "结论", "直接")):
            role = "answer"
        elif any(mark in line for mark in ("如果", "若", "风险", "证伪")):
            role = "boundary"
        else:
            role = "support"
        if not roles or roles[-1] != role:
            roles.append(role)
    heading_part = "/".join(headings) if headings else "no-heading"
    return f"{heading_part}|{'>'.join(roles) or 'empty'}"


def _phrase_coverage(phrase: str, answer: str) -> float:
    wanted = _normalized(phrase)
    actual = _normalized(answer)
    if not wanted:
        return 1.0
    if wanted in actual:
        return 1.0
    if len(wanted) < 2:
        return float(wanted in actual)
    grams = {wanted[index : index + 2] for index in range(len(wanted) - 1)}
    return round(sum(gram in actual for gram in grams) / len(grams), 4)


def fallback_fidelity_score(answer: str, decision_brief: Mapping[str, Any] | None) -> float:
    """Check that a degraded renderer retains the brief's two semantic anchors."""
    if not decision_brief:
        return 1.0
    anchors = (
        str(decision_brief.get("direct_answer") or ""),
        str(decision_brief.get("core_tension") or ""),
    )
    return round(sum(_phrase_coverage(anchor, answer) for anchor in anchors) / 2, 4)


def evaluate_capability_case(case: Mapping[str, Any]) -> AdvisoryCapabilityScore:
    answer = str(case.get("answer") or "")
    coverage, missing = task_coverage_score(answer, case.get("requirements") or ())
    leak_score, leaks = control_plane_leak_score(answer)
    return AdvisoryCapabilityScore(
        case_id=str(case.get("id") or "case"),
        directness=directness_score(
            str(case.get("question") or ""),
            answer,
            direct_targets=case.get("direct_targets") or (),
        ),
        task_coverage=coverage,
        grounding=grounding_score(
            answer,
            case.get("claims") or (),
            case.get("evidence_ids") or (),
        ),
        control_plane_leak_score=leak_score,
        template_signature=template_signature(answer),
        fallback_fidelity=fallback_fidelity_score(answer, case.get("decision_brief")),
        missing_outputs=missing,
        leak_kinds=leaks,
    )


def compare_capability(
    minimal_case: Mapping[str, Any],
    workbench_case: Mapping[str, Any],
    *,
    tolerance: float = 0.05,
) -> CapabilityComparison:
    """Pair a minimal-model answer with the Workbench answer for the same task."""
    minimal = evaluate_capability_case(minimal_case)
    workbench = evaluate_capability_case(workbench_case)
    names = ("directness", "task_coverage", "grounding", "fallback_fidelity")
    deltas = {
        name: round(float(getattr(workbench, name)) - float(getattr(minimal, name)), 4)
        for name in names
    }
    deltas["control_plane_leak_score"] = round(
        minimal.control_plane_leak_score - workbench.control_plane_leak_score,
        4,
    )
    regressions = tuple(name for name, delta in deltas.items() if delta < -tolerance)
    return CapabilityComparison(
        case_id=workbench.case_id,
        minimal=minimal,
        workbench=workbench,
        deltas=deltas,
        monotonic=not regressions,
        regressions=regressions,
    )
