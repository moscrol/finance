"""Live runner for the agent eval gate.

Drives a real :class:`~intelligence.runtime.agent.AgentSession` over a golden
case set, adapts each turn's :class:`AgentResult` into a serializable
:class:`~intelligence.eval.agent_eval.TurnInput`, and applies the gate. Needs an
LLM key + the KB, so it is *not* a PR-CI check — run it on demand (or on a
schedule) to measure "改了有没有更好".

Two extra affordances make it a real regression gate, not a one-shot demo:
- ``run_eval`` returns a ``run_record`` (every turn's TurnInput as plain dicts)
  alongside the live scorecard, so a baseline run can be saved to disk.
- ``score_run`` re-scores a saved ``run_record`` **without any LLM/KB**, so
  thresholds can be re-tuned and old runs re-graded offline, deterministically.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from intelligence.eval.agent_eval import (
    CaseSpec,
    Scorecard,
    TurnInput,
    build_scorecard,
    parse_wiki_step,
    score_case,
)
from intelligence.eval.presentation_diversity import audit_presentation_diversity


@dataclass
class EvalRunOptions:
    kb_wiki: str | Path | None = None
    exports_dir: str | Path | None = None
    top_companies: int = 12
    module_timeout: int = 180
    wiki_rag_k: int = 6
    wiki_rag_mode: str = "hybrid"
    wiki_rag_timeout: int = 90
    max_steps: int = 6
    llm_model: str | None = None
    llm_timeout: int = 90


def load_cases(path: str | Path) -> tuple[list[CaseSpec], float]:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    specs = [CaseSpec.from_dict(c) for c in doc.get("cases", [])]
    gate = float(doc.get("aggregate_gate", 1.0))
    return specs, gate


# --------------------------------------------------------------------------- #
# AgentResult -> TurnInput adapter
# --------------------------------------------------------------------------- #
def turn_input_from_result(
    question: str, result: Any, registry_tags: list[str], *, is_followup: bool
) -> TurnInput:
    """Adapt one :class:`AgentResult` + a snapshot of the cumulative citation
    tags into the scorer's :class:`TurnInput`. ``registry_tags`` must be
    snapshotted by the caller right after the turn (the live list keeps
    mutating across turns)."""
    tools_called: list[str] = []
    wiki_calls = wiki_hits = 0
    relevances: list[float] = []
    for step in result.steps:
        tools_called.append(step.tool)
        if step.tool == "search_wiki":
            wiki_calls += 1
            hit, rel = parse_wiki_step(step.result_preview or "")
            if hit:
                wiki_hits += 1
                if rel is not None:
                    relevances.append(rel)
    return TurnInput(
        question=question,
        answer=result.answer,
        tools_called=tools_called,
        registry_tags=list(registry_tags),
        wiki_calls=wiki_calls,
        wiki_hit_calls=wiki_hits,
        wiki_top_relevances=relevances,
        is_followup=is_followup,
    )


def run_case(spec: CaseSpec, opts: EvalRunOptions) -> list[TurnInput]:
    """Run one case (首轮 + 依次追问) on a fresh persistent agent session."""
    from intelligence.runtime.agent import AgentSession
    from intelligence.services.ask import AskOptions

    options = AskOptions(
        query=spec.query,
        date=spec.date,
        exports_dir=opts.exports_dir,
        kb_wiki=opts.kb_wiki,
        top_companies=opts.top_companies,
        module_timeout=opts.module_timeout,
        wiki_rag_k=opts.wiki_rag_k,
        wiki_rag_mode=opts.wiki_rag_mode,
        wiki_rag_timeout=opts.wiki_rag_timeout,
        compose=True,
    )
    session = AgentSession(
        options,
        model_override=opts.llm_model,
        timeout=opts.llm_timeout,
        max_steps=opts.max_steps,
    )

    turns: list[TurnInput] = []
    res = session.start(spec.query)
    turns.append(
        turn_input_from_result(
            spec.query, res, [c.tag for c in session.citations], is_followup=False
        )
    )
    # turn-1 degraded (no key / failure) → don't pretend follow-ups ran.
    if res.ok:
        for q in spec.followups:
            r = session.ask(q)
            turns.append(
                turn_input_from_result(
                    q, r, [c.tag for c in session.citations], is_followup=True
                )
            )
    return turns


def run_eval(
    specs: list[CaseSpec],
    aggregate_gate: float,
    opts: EvalRunOptions,
    *,
    case_runner: Callable[[CaseSpec, EvalRunOptions], list[TurnInput]] | None = None,
) -> tuple[Scorecard, dict[str, Any]]:
    """Run every case live and score it. Returns (scorecard, run_record). The
    ``run_record`` is a plain-dict transcript of inputs that :func:`score_run`
    can re-grade offline without an LLM."""
    runner = case_runner or run_case
    case_scores = []
    record_cases = []
    for spec in specs:
        turns = runner(spec, opts)
        case_scores.append(score_case(turns, spec))
        record_cases.append({"id": spec.id, "turns": [t.to_dict() for t in turns]})
    scorecard = build_scorecard(case_scores, aggregate_gate)
    diversity_answers = [
        (record["id"], str(record["turns"][0].get("answer") or ""))
        for record in record_cases
        if record["turns"]
    ]
    run_record = {
        "aggregate_gate": aggregate_gate,
        "cases": record_cases,
        # Advisory only: reliability remains governed by claim/evidence gates.
        "presentation_diversity": audit_presentation_diversity(
            diversity_answers
        ).to_dict(),
    }
    return scorecard, run_record


def score_run(
    run_record: dict[str, Any], specs: list[CaseSpec], aggregate_gate: float | None = None
) -> Scorecard:
    """Re-score a saved ``run_record`` offline (no LLM/KB). Deterministic."""
    by_id = {s.id: s for s in specs}
    gate = aggregate_gate if aggregate_gate is not None else float(run_record.get("aggregate_gate", 1.0))
    case_scores = []
    for rc in run_record.get("cases", []):
        spec = by_id.get(rc["id"])
        if spec is None:
            continue
        turns = [TurnInput.from_dict(t) for t in rc.get("turns", [])]
        case_scores.append(score_case(turns, spec))
    return build_scorecard(case_scores, gate)


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def _fmt_rel(v: float | None) -> str:
    return "—" if v is None else f"{v:.3f}"


def _fmt_rate(v: float | None) -> str:
    return "—" if v is None else f"{v:.0%}"


def format_scorecard(card: Scorecard) -> str:
    lines: list[str] = []
    verdict = "PASS ✅" if card.passed else "FAIL ❌"
    lines.append(f"# agent 评测闸记分卡 — {verdict}")
    lines.append(
        f"\n通过率 {card.pass_rate:.0%}（闸 {card.aggregate_gate:.0%}）"
        f"｜{sum(1 for c in card.cases if c.passed)}/{len(card.cases)} case 通过\n"
    )
    lines.append("| case | 通过 | 实体召回 | 源覆盖 | 引用可解析 | 错配实体 | 证据越级 | W顶相关度 | W未命中率 |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for c in card.cases:
        resolvable = min((t.citation_resolvable for t in c.turns), default=1.0)
        w_top = max(
            (t.wiki_top_relevance for t in c.turns if t.wiki_top_relevance is not None),
            default=None,
        )
        w_miss = next(
            (t.wiki_miss_rate for t in c.turns if t.wiki_miss_rate is not None), None
        )
        false_attr = "✅" if not c.false_attributions else "、".join(c.false_attributions)
        overclaims = "✅" if not c.overclaims else "、".join(c.overclaims)
        lines.append(
            f"| {c.case_id} | {'✅' if c.passed else '❌'} "
            f"| {c.entity_recall:.0%}（{len(c.matched_entities)}/{len(c.matched_entities)+len(c.missing_entities)}）"
            f"| {'✅' if c.source_coverage else '缺'+'、'.join(c.missing_sources)} "
            f"| {resolvable:.0%} | {false_attr} | {overclaims} | {_fmt_rel(w_top)} | {_fmt_rate(w_miss)} |"
        )
    fails = [(c.case_id, f) for c in card.cases for f in c.failures]
    if fails:
        lines.append("\n## 失败项")
        for cid, f in fails:
            lines.append(f"- **{cid}**：{f}")
    else:
        lines.append("\n所有 case 通过：无编造引用、免责声明齐全、期望实体/源均覆盖、工具预算正常、无错配实体或证据越级。")
    return "\n".join(lines) + "\n"
