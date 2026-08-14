from __future__ import annotations

from dataclasses import dataclass

from intelligence.services.question_router import RouteDecision, render_decision, route_question
from intelligence.summary import WorkflowStep, WorkflowSummary, now_iso


@dataclass(frozen=True)
class RouteWorkflowOptions:
    query: str


def run_route(options: RouteWorkflowOptions) -> tuple[WorkflowSummary, RouteDecision, str]:
    decision = route_question(options.query)
    summary = WorkflowSummary(
        workflow="route",
        status="PASS",
        started_at=now_iso(),
        inputs={"query": options.query},
    )
    summary.steps.append(
        WorkflowStep(
            name="question-router",
            status="PASS",
            outputs=[
                f"route_type={decision.route_type}",
                f"confidence={decision.confidence:.2f}",
                f"paths={','.join(path.id for path in decision.selected_paths) or '-'}",
            ],
            warnings=list(decision.warnings),
        )
    )
    summary.outputs = [path.id for path in decision.selected_paths]
    summary.warnings = list(decision.warnings)
    summary.next_actions = [decision.next_action]
    summary.finish("PASS")
    return summary, decision, render_decision(decision)

