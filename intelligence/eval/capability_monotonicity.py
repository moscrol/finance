"""Offline checks that constraints do not make an agent less capable.

The production verifier answers a binary question: may this factual claim be
shown?  This module answers a different, advisory question: after adding
retrieval and verification, did the Workbench still answer the user's actual
task and preserve a useful fallback?

All metrics are deterministic and side-effect free.  They are deliberately
kept out of production prompts and gates; otherwise the evaluator would become
another source of template pressure.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
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


@dataclass(frozen=True)
class CapabilityScore:
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
    minimal: CapabilityScore
    workbench: CapabilityScore
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


def evaluate_capability_case(case: Mapping[str, Any]) -> CapabilityScore:
    answer = str(case.get("answer") or "")
    coverage, missing = task_coverage_score(answer, case.get("requirements") or ())
    leak_score, leaks = control_plane_leak_score(answer)
    return CapabilityScore(
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
