from __future__ import annotations

from intelligence.services.ask import AskOptions, AskResult, answer_query, render_answer
from intelligence.summary import WorkflowStep, WorkflowSummary, now_iso


def run_ask(options: AskOptions) -> tuple[WorkflowSummary, AskResult, str]:
    summary = WorkflowSummary(
        workflow="ask",
        status="PASS",
        started_at=now_iso(),
        inputs={"query": options.query, "date": options.date},
    )
    result = answer_query(options)
    answer = render_answer(result)
    if result.clarify is not None:
        # 澄清追问短路：本次未检索，只登记门控步骤；其余检索步骤不适用。
        summary.steps.append(
            WorkflowStep(
                name="clarify-gate",
                status="WARN",
                outputs=[f"reason={result.clarify.reason}", f"questions={len(result.clarify.questions)}"],
            )
        )
        summary.warnings = list(result.warnings)
        summary.finish("WARN")
        return summary, result, answer
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
