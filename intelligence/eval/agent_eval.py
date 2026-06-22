"""Deterministic scorer for agent answers (the P1+ 评测闸 core).

Design:
- **Pure & dependency-free.** Operates over :class:`TurnInput` (a small
  serializable view of one agent turn) + :class:`CaseSpec` (题 + 期望). No LLM,
  no KB, no I/O. This is what makes the gate *repeatable*: the same run scores
  identically, so "改了有没有更好" is a number, not a vibe.
- **Per-turn hard gates** catch the things that must never regress: hallucinated
  citations (a ``[R7]`` the registry never minted), missing 免责声明, and tool
  budgets blowing up / collapsing. **Case-level gates** check that the expected
  companies surfaced (entity recall) and the expected sources were actually
  *cited* (not merely touched).
- **W (wiki dense) metrics are reported, not gated.** P0 showed W relevance
  legitimately varies by theme (光刻胶 ~0.53 vs 商业航天 ~0.20); gating on it
  would punish the agent for a retrieval-coverage gap it correctly compensates
  for. They are surfaced so a future tuning pass has a number to move.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

DISCLAIMER_MARK = "非投资建议"
GRAPH_ONLY_MARK = "graph_only"
STALE_MARKS = ("⚠️过期", "⚠️ 过期", "⚠ 过期", "过期")

_CITE_RE = re.compile(r"\[([SGRW])(\d+)\]")
_RELEVANCE_RE = re.compile(r"相关度\s*([0-9]*\.?[0-9]+)")
_WIKI_MISS_MARKS = ("无命中", "不可用")


# --------------------------------------------------------------------------- #
# Inputs
# --------------------------------------------------------------------------- #
@dataclass
class CaseSpec:
    """One golden eval case: a theme + follow-ups + what a good answer must hit."""

    id: str
    query: str
    date: str | None = None
    followups: list[str] = field(default_factory=list)
    expect_entities: list[str] = field(default_factory=list)
    expect_concepts: list[str] = field(default_factory=list)
    expect_sources: list[str] = field(default_factory=list)  # e.g. ["S","G","R","W"]
    min_tool_calls: int = 3          # applies to the first turn only
    max_tool_calls: int = 40         # applies to every turn
    entity_recall_gate: float = 0.5
    require_disclaimer: bool = True

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CaseSpec":
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in d.items() if k in known})


@dataclass
class TurnInput:
    """A serializable view of one agent turn — the only thing the scorer reads.

    The live runner builds these from an :class:`AgentResult`; tests build them
    by hand. ``registry_tags`` is the *cumulative* set of citation tags the
    session had minted by the end of this turn (cross-turn reuse is allowed), so
    any cited tag outside it is a hallucination.
    """

    question: str
    answer: str | None
    tools_called: list[str] = field(default_factory=list)
    registry_tags: list[str] = field(default_factory=list)
    wiki_calls: int = 0
    wiki_hit_calls: int = 0
    wiki_top_relevances: list[float] = field(default_factory=list)
    is_followup: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "answer": self.answer,
            "tools_called": list(self.tools_called),
            "registry_tags": list(self.registry_tags),
            "wiki_calls": self.wiki_calls,
            "wiki_hit_calls": self.wiki_hit_calls,
            "wiki_top_relevances": list(self.wiki_top_relevances),
            "is_followup": self.is_followup,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "TurnInput":
        return cls(
            question=d.get("question", ""),
            answer=d.get("answer"),
            tools_called=list(d.get("tools_called") or []),
            registry_tags=list(d.get("registry_tags") or []),
            wiki_calls=int(d.get("wiki_calls") or 0),
            wiki_hit_calls=int(d.get("wiki_hit_calls") or 0),
            wiki_top_relevances=[float(x) for x in (d.get("wiki_top_relevances") or [])],
            is_followup=bool(d.get("is_followup")),
        )


# --------------------------------------------------------------------------- #
# Scores
# --------------------------------------------------------------------------- #
@dataclass
class TurnScore:
    question: str
    answered: bool
    cited_tags: list[str]
    dangling_citations: list[str]
    citation_resolvable: float
    disclaimer_present: bool
    cited_sources: list[str]
    tool_calls: int
    tool_calls_in_range: bool
    graph_only_flagged: bool
    stale_flagged: bool
    wiki_calls: int
    wiki_top_relevance: float | None
    wiki_miss_rate: float | None
    passed: bool
    failures: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class CaseScore:
    case_id: str
    turns: list[TurnScore]
    entity_recall: float
    matched_entities: list[str]
    missing_entities: list[str]
    concept_recall: float
    cited_sources: list[str]
    missing_sources: list[str]
    source_coverage: bool
    passed: bool
    failures: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = {k: v for k, v in self.__dict__.items() if k != "turns"}
        d["turns"] = [t.to_dict() for t in self.turns]
        return d


@dataclass
class Scorecard:
    cases: list[CaseScore]
    pass_rate: float
    aggregate_gate: float
    passed: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "pass_rate": self.pass_rate,
            "aggregate_gate": self.aggregate_gate,
            "passed": self.passed,
            "cases": [c.to_dict() for c in self.cases],
        }


# --------------------------------------------------------------------------- #
# Pure helpers
# --------------------------------------------------------------------------- #
def extract_cited_tags(text: str | None) -> list[str]:
    """All ``[S#]/[G#]/[R#]/[W#]`` tags in order of appearance (dups kept)."""
    return [f"{m.group(1)}{m.group(2)}" for m in _CITE_RE.finditer(text or "")]


def parse_wiki_step(preview: str) -> tuple[bool, float | None]:
    """From a ``search_wiki`` tool-result preview, return (hit?, top_relevance).

    Robust to the 300-char preview truncation: the first hit's ``相关度`` sits at
    the start of the block, so a present score implies a hit. Explicit
    无命中/不可用 strings imply a miss.
    """
    if any(m in preview for m in _WIKI_MISS_MARKS):
        return False, None
    scores = [float(x) for x in _RELEVANCE_RE.findall(preview)]
    if scores:
        return True, max(scores)
    return False, None


def _contains_any(text: str, marks: tuple[str, ...]) -> bool:
    return any(m in text for m in marks)


# --------------------------------------------------------------------------- #
# Scoring
# --------------------------------------------------------------------------- #
def score_turn(ti: TurnInput, spec: CaseSpec) -> TurnScore:
    answer = ti.answer or ""
    answered = bool(answer.strip())
    cited = extract_cited_tags(answer)
    registry = set(ti.registry_tags)
    dangling = [t for t in cited if t not in registry]
    resolvable = 1.0 if not cited else (len(cited) - len(dangling)) / len(cited)
    cited_sources = sorted({t[0] for t in cited})
    disclaimer = DISCLAIMER_MARK in answer

    tool_calls = len(ti.tools_called)
    # First turn must do real retrieval; follow-ups may answer purely from memory
    # (0 tool calls is legitimate), but neither may blow the per-turn ceiling.
    floor = 0 if ti.is_followup else spec.min_tool_calls
    in_range = floor <= tool_calls <= spec.max_tool_calls

    top_rel = max(ti.wiki_top_relevances) if ti.wiki_top_relevances else None
    miss_rate = (
        (ti.wiki_calls - ti.wiki_hit_calls) / ti.wiki_calls if ti.wiki_calls else None
    )

    failures: list[str] = []
    if not answered:
        failures.append("未作答（answer 为空）")
    if dangling:
        failures.append("编造引用（注册表无此编号）：" + "、".join(dangling))
    if spec.require_disclaimer and answered and not disclaimer:
        failures.append("缺免责声明「（非投资建议）」")
    if not in_range:
        failures.append(f"工具调用数 {tool_calls} 不在 [{floor},{spec.max_tool_calls}]")

    return TurnScore(
        question=ti.question,
        answered=answered,
        cited_tags=cited,
        dangling_citations=dangling,
        citation_resolvable=resolvable,
        disclaimer_present=disclaimer,
        cited_sources=cited_sources,
        tool_calls=tool_calls,
        tool_calls_in_range=in_range,
        graph_only_flagged=GRAPH_ONLY_MARK in answer,
        stale_flagged=_contains_any(answer, STALE_MARKS),
        wiki_calls=ti.wiki_calls,
        wiki_top_relevance=top_rel,
        wiki_miss_rate=miss_rate,
        passed=not failures,
        failures=failures,
    )


def score_case(turns: list[TurnInput], spec: CaseSpec) -> CaseScore:
    turn_scores = [score_turn(t, spec) for t in turns]
    all_text = "\n".join(t.answer or "" for t in turns)

    matched = [e for e in spec.expect_entities if e in all_text]
    missing = [e for e in spec.expect_entities if e not in all_text]
    entity_recall = len(matched) / len(spec.expect_entities) if spec.expect_entities else 1.0

    concepts_hit = [c for c in spec.expect_concepts if c in all_text]
    concept_recall = (
        len(concepts_hit) / len(spec.expect_concepts) if spec.expect_concepts else 1.0
    )

    cited_sources = sorted({s for t in turn_scores for s in t.cited_sources})
    missing_sources = [s for s in spec.expect_sources if s not in cited_sources]
    source_coverage = not missing_sources

    failures: list[str] = []
    for i, ts in enumerate(turn_scores):
        if not ts.passed:
            label = "首轮" if i == 0 else f"追问{i}"
            failures.extend(f"[{label}] {f}" for f in ts.failures)
    if spec.expect_entities and entity_recall < spec.entity_recall_gate:
        failures.append(
            f"实体召回 {entity_recall:.2f} < 闸 {spec.entity_recall_gate:.2f}"
            f"（缺：{'、'.join(missing)}）"
        )
    if not source_coverage:
        failures.append("未覆盖期望源：" + "、".join(missing_sources))

    return CaseScore(
        case_id=spec.id,
        turns=turn_scores,
        entity_recall=entity_recall,
        matched_entities=matched,
        missing_entities=missing,
        concept_recall=concept_recall,
        cited_sources=cited_sources,
        missing_sources=missing_sources,
        source_coverage=source_coverage,
        passed=not failures,
        failures=failures,
    )


def build_scorecard(case_scores: list[CaseScore], aggregate_gate: float) -> Scorecard:
    total = len(case_scores)
    passed = sum(1 for c in case_scores if c.passed)
    pass_rate = passed / total if total else 0.0
    return Scorecard(
        cases=case_scores,
        pass_rate=pass_rate,
        aggregate_gate=aggregate_gate,
        passed=pass_rate >= aggregate_gate,
    )
