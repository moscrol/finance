from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from intelligence.services.logic_market_match import (
    LogicMarketMatchResult,
    LogicMatchBatchResult,
    batch_match_logic_to_market,
    match_logic_to_market,
    render_batch,
    render_match,
)
from intelligence.summary import WorkflowStep, WorkflowSummary, now_iso


@dataclass(frozen=True)
class LogicMatchOptions:
    query: str
    date: str | None = None
    exports_dir: str | Path | None = None
    kb_wiki: str | Path | None = None
    top_companies: int = 12
    max_evidence: int = 8


@dataclass(frozen=True)
class LogicMatchBatchOptions:
    dates: tuple[str, ...] = ()
    recent: int = 5
    top_per_date: int = 10
    exports_dir: str | Path | None = None
    kb_wiki: str | Path | None = None
    top_companies: int = 8
    max_evidence: int = 5


def run_logic_match(options: LogicMatchOptions) -> tuple[WorkflowSummary, LogicMarketMatchResult, str]:
    result = match_logic_to_market(
        query=options.query,
        date=options.date,
        exports_dir=options.exports_dir,
        kb_wiki=options.kb_wiki,
        top_companies=options.top_companies,
        max_evidence=options.max_evidence,
    )
    summary = WorkflowSummary(
        workflow="logic-match",
        status="PASS",
        started_at=now_iso(),
        inputs={"query": options.query, "date": options.date},
    )
    summary.steps.append(
        WorkflowStep(
            name="market-match",
            status="PASS" if result.market_found else "WARN",
            outputs=[
                f"matched_theme={result.matched_theme or '-'}",
                f"priority_score={result.priority_score if result.priority_score is not None else '-'}",
            ],
        )
    )
    summary.steps.append(
        WorkflowStep(
            name="knowledge-match",
            status="PASS" if result.concept_matches and result.entity_exposures else "WARN",
            outputs=[
                f"concepts={len(result.concept_matches)}",
                f"entity_exposures={len(result.entity_exposures)}",
                f"evidence={len(result.evidence_items)}",
            ],
        )
    )
    summary.steps.append(
        WorkflowStep(
            name="classification",
            status="PASS" if result.classification != "noise_or_unconfirmed" else "WARN",
            outputs=[f"classification={result.classification}", f"confidence={result.confidence:.2f}"],
            warnings=list(result.data_gaps),
        )
    )
    summary.outputs = [result.classification, *result.next_actions]
    summary.warnings = list(result.warnings)
    summary.next_actions = list(result.next_actions)
    summary.finish("PASS" if result.classification in {"old_logic_wakeup", "new_logic_candidate"} else "WARN")
    return summary, result, render_match(result)


def run_logic_match_batch(options: LogicMatchBatchOptions) -> tuple[WorkflowSummary, LogicMatchBatchResult, str]:
    result = batch_match_logic_to_market(
        dates=list(options.dates) or None,
        recent=options.recent,
        top_per_date=options.top_per_date,
        exports_dir=options.exports_dir,
        kb_wiki=options.kb_wiki,
        top_companies=options.top_companies,
        max_evidence=options.max_evidence,
    )
    summary = WorkflowSummary(
        workflow="logic-match-batch",
        status="PASS",
        started_at=now_iso(),
        inputs={
            "dates": list(options.dates),
            "recent": options.recent,
            "top_per_date": options.top_per_date,
        },
    )
    summary.steps.append(
        WorkflowStep(
            name="batch-scan",
            status="PASS" if result.scanned_count else "WARN",
            outputs=[
                f"dates={','.join(result.dates) or '-'}",
                f"scanned={result.scanned_count}",
                f"gap_queue={len(result.gap_queue)}",
            ],
            warnings=list(result.warnings),
        )
    )
    summary.outputs = [f"{item.date}:{item.query}:{item.classification}" for item in result.gap_queue[:50]]
    summary.warnings = list(result.warnings)
    summary.next_actions = [
        "Review the priority gap queue; backfill only gaps that affect recent market candidates.",
        "Run source/concept/IMA backfills for high-priority rows, then rerun logic-match-batch.",
    ]
    summary.finish("PASS" if result.scanned_count else "WARN")
    return summary, result, render_batch(result)
