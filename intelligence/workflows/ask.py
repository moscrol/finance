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
    use_wiki_rag: bool = True
    wiki_rag_k: int = 6
    wiki_rag_mode: str = "hybrid"
    wiki_rag_timeout: int = 90
    wiki_rag_index_dir: str | Path | None = None
    use_llm: bool = False
    compose: bool = False
    llm_model: str | None = None
    llm_timeout: int = 60
    detail: bool = False
    user: str | None = None
    experience_cards_window: int = 12
    use_l3_lookup: bool = False
    l3_lookup_timeout: int = 480
    l3_lookup_limit: int = 5


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
            use_wiki_rag=options.use_wiki_rag,
            wiki_rag_k=options.wiki_rag_k,
            wiki_rag_mode=options.wiki_rag_mode,
            wiki_rag_timeout=options.wiki_rag_timeout,
            wiki_rag_index_dir=options.wiki_rag_index_dir,
            use_llm=options.use_llm,
            compose=options.compose,
            llm_model=options.llm_model,
            llm_timeout=options.llm_timeout,
            detail=options.detail,
            user=options.user,
            experience_cards_window=options.experience_cards_window,
            use_l3_lookup=options.use_l3_lookup,
            l3_lookup_timeout=options.l3_lookup_timeout,
            l3_lookup_limit=options.l3_lookup_limit,
        )
    )
    answer = render_answer(result)
    plan = result.question_plan

    summary.steps.append(
        WorkflowStep(
            name="answer-orchestrator",
            status="PASS" if plan and plan.confidence >= 0.5 else "WARN",
            outputs=[
                f"type={(plan.question_type if plan else '-')}",
                f"depth={(plan.depth if plan else '-')}",
                f"confidence={(f'{plan.confidence:.2f}' if plan else '-')}",
                f"lenses={len(plan.required_lenses) if plan else 0}",
                f"sources={len(plan.retrieval_plan) if plan else 0}",
            ],
            warnings=list(plan.warnings) if plan else ["question plan missing"],
        )
    )
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
            name="wiki-rag-source",
            status="PASS" if result.found_wiki else ("SKIP" if not options.use_wiki_rag else "WARN"),
            outputs=[f"found_wiki={result.found_wiki}"],
        )
    )
    summary.steps.append(
        WorkflowStep(
            name="l3-evidence-tools",
            status=(
                "PASS"
                if result.l3_evidence.items
                else ("WARN" if options.use_l3_lookup and result.l3_evidence.gaps else "SKIP")
            ),
            outputs=[
                f"enabled={options.use_l3_lookup}",
                f"gaps={len(result.l3_evidence.gaps)}",
                f"items={len(result.l3_evidence.items)}",
                f"commands={len(result.l3_evidence.commands)}",
            ],
            warnings=list(result.l3_evidence.warnings),
        )
    )
    audit = result.evidence_audit
    telemetry = result.retrieval_telemetry
    summary.steps.append(
        WorkflowStep(
            name="research-brief-skills",
            status="PASS" if audit is not None else "SKIP",
            outputs=[
                f"verdict={(audit.verdict if audit else '-')}",
                f"layers={('/'.join(f'{k}x{v}' for k, v in sorted(audit.layer_counts.items())) if audit else '-')}",
                f"covers_l3={telemetry.covers_l3 if telemetry else '-'}",
                f"stock_brief={result.stock_brief is not None}",
                f"market_phase={(result.market_state.phase if result.market_state else '-')}",
                f"theme_stage={(result.theme_lifecycle.stage if result.theme_lifecycle else '-')}",
                f"review_gate={(result.review_gate.status if result.review_gate else '-')}",
            ],
            warnings=list(audit.warnings) if audit else [],
        )
    )
    summary.steps.append(
        WorkflowStep(
            name="theme-radar-modules",
            status="PASS" if result.routed_modules else "SKIP",
            outputs=[f"routed={'/'.join(result.routed_modules) or '-'}"],
        )
    )
    summary.steps.append(
        WorkflowStep(
            name="llm-refine",
            status="PASS" if result.llm_refined else ("WARN" if options.use_llm else "SKIP"),
            outputs=[f"provider={result.llm_provider or '-'}", f"refined={result.llm_refined}"],
        )
    )
    summary.steps.append(
        WorkflowStep(
            name="llm-compose",
            status="PASS" if result.synthesis else ("WARN" if options.compose else "SKIP"),
            outputs=[f"provider={result.llm_provider or '-'}", f"composed={bool(result.synthesis)}"],
        )
    )
    summary.outputs = [f"[{c.tag}] {c.source}" for c in result.citations]
    summary.warnings = list(result.warnings)
    summary.next_actions = [
        "Add a Temporal Facts layer so superseded/invalidated evidence is filtered automatically.",
        "Wire daily-loop (盘前预测→盘后多周期验证→写回记忆).",
    ]
    summary.finish(result.status)
    return summary, result, answer
