from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from intelligence.services.ask import AskOptions, AskResult, answer_query, render_answer
from intelligence.summary import WorkflowStep, WorkflowSummary, now_iso


@dataclass(frozen=True)
class AskWorkflowOptions:
    query: str
    date: str | None = None
    exports_dir: str | Path | None = None
    kb_wiki: str | Path | None = None
    top_companies: int = 12
    use_modules: bool = True
    modules: tuple[str, ...] | None = None
    module_timeout: int = 180


def run_ask(options: AskWorkflowOptions) -> tuple[WorkflowSummary, AskResult, str]:
    summary = WorkflowSummary(
        workflow="ask",
        status="PASS",
        started_at=now_iso(),
        inputs={"query": options.query, "date": options.date},
    )
    result = answer_query(
        AskOptions(
            query=options.query,
            date=options.date,
            exports_dir=options.exports_dir,
            kb_wiki=options.kb_wiki,
            top_companies=options.top_companies,
            use_modules=options.use_modules,
            modules=options.modules,
            module_timeout=options.module_timeout,
        )
    )
    answer = render_answer(result)

    summary.steps.append(
        WorkflowStep(
            name="market-source",
            status="PASS" if result.found_market else "WARN",
            outputs=[f"matched_theme={result.matched_theme}", f"trade_date={result.trade_date}"],
        )
    )
    summary.steps.append(
        WorkflowStep(
            name="graph-source",
            status="PASS" if result.found_graph else "WARN",
            outputs=[f"citations={len(result.citations)}"],
        )
    )
    summary.steps.append(
        WorkflowStep(
            name="theme-radar-modules",
            status="PASS" if result.routed_modules else "SKIP",
            outputs=[f"routed={'/'.join(result.routed_modules) or '-'}"],
        )
    )
    summary.outputs = [f"[{c.tag}] {c.source}" for c in result.citations]
    summary.warnings = list(result.warnings)
    summary.next_actions = [
        "Wire the remaining theme-radar 模式 (front-map/deep-dive/scan/migrate) as recall backends.",
        "Refine 结论/交易含义 with an LLM provider.",
        "Add a Temporal Facts layer so superseded/invalidated evidence is filtered automatically.",
    ]
    summary.finish(result.status)
    return summary, result, answer
