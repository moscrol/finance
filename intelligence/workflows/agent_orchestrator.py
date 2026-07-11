from __future__ import annotations

import json
import shlex
import string
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from intelligence.paths import default_paths
from intelligence.runner import run_command_step
from intelligence.services.question_router import RouteDecision, RoutePath, render_decision, route_question
from intelligence.summary import WorkflowStep, WorkflowSummary, now_iso


MIN_AUTO_EXECUTION_CONFIDENCE = 0.7


@dataclass(frozen=True)
class OrchestratorOptions:
    query: str
    date: str | None = None
    knowledge_wiki: str | Path | None = None
    finance_root: str | Path | None = None
    recent: int = 5
    top_per_date: int = 10
    execute: bool = False


@dataclass
class OrchestratedPath:
    id: str
    label: str
    command: str = ""
    argv: list[str] = field(default_factory=list)
    auto_execute: bool = False
    risk_level: str = "medium"
    status: str = "planned"
    skip_reason: str = ""
    outputs: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class OrchestratorResult:
    query: str
    execute: bool
    decision: RouteDecision
    paths: list[OrchestratedPath]

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "execute": self.execute,
            "decision": self.decision.to_dict(),
            "paths": [path.to_dict() for path in self.paths],
        }


def run_agent_orchestrator(options: OrchestratorOptions) -> tuple[WorkflowSummary, OrchestratorResult, str]:
    decision = route_question(options.query)
    summary = WorkflowSummary(
        workflow="agent-orchestrator",
        status="PASS",
        started_at=now_iso(),
        inputs={
            "query": options.query,
            "date": options.date,
            "execute": options.execute,
        },
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

    context = _context(options)
    planned = [_plan_path(path, context) for path in decision.selected_paths]
    for item in planned:
        step = _step_for_plan(item, options, decision.confidence)
        if options.execute and _is_executable(item, decision.confidence):
            step = run_command_step(f"execute:{item.id}", item.argv, context["finance_root"])
            item.status = "executed" if step.status == "PASS" else "failed"
            item.outputs = list(step.outputs)
            item.warnings = list(step.warnings)
        summary.steps.append(step)

    result = OrchestratorResult(query=options.query, execute=options.execute, decision=decision, paths=planned)
    summary.outputs = [path.command for path in planned if path.command]
    summary.warnings = list(decision.warnings) + [path.skip_reason for path in planned if path.skip_reason]
    summary.next_actions = _next_actions(result)
    if any(step.status == "FAIL" for step in summary.steps):
        summary.finish("FAIL")
    elif not decision.selected_paths or (options.execute and any(step.status == "SKIP" for step in summary.steps[1:])):
        summary.finish("WARN")
    else:
        summary.finish("PASS")
    return summary, result, render_orchestrator(result)


def _context(options: OrchestratorOptions) -> dict[str, Any]:
    paths = default_paths()
    finance_root = Path(options.finance_root).expanduser() if options.finance_root else paths.finance_root
    knowledge_wiki = Path(options.knowledge_wiki).expanduser() if options.knowledge_wiki else paths.knowledge_wiki
    return {
        "query": options.query,
        "date": options.date or "{date}",
        "knowledge_wiki": str(knowledge_wiki),
        "kb_wiki": str(knowledge_wiki),
        "finance_root": str(finance_root),
        "recent": options.recent,
        "top_per_date": options.top_per_date,
    }


def _plan_path(path: RoutePath, context: dict[str, Any]) -> OrchestratedPath:
    item = OrchestratedPath(
        id=path.id,
        label=path.label,
        auto_execute=path.auto_execute,
        risk_level=path.risk_level,
    )
    if not path.command_template:
        item.status = "skipped"
        item.skip_reason = "missing_command_template"
        return item
    missing = _missing_placeholders(path.command_template, context)
    if missing:
        item.status = "skipped"
        item.skip_reason = f"missing_inputs:{','.join(missing)}"
        return item
    item.argv = [_format_token(token, context) for token in shlex.split(path.command_template)]
    item.command = shlex.join(item.argv)
    return item


def _missing_placeholders(template: str, context: dict[str, Any]) -> list[str]:
    missing = []
    for _, field_name, _, _ in string.Formatter().parse(template):
        if not field_name:
            continue
        value = context.get(field_name)
        if value is None or value == f"{{{field_name}}}":
            missing.append(field_name)
    return sorted(set(missing))


def _format_token(token: str, context: dict[str, Any]) -> str:
    return token.format_map({key: str(value) for key, value in context.items()})


def _is_executable(item: OrchestratedPath, confidence: float) -> bool:
    return (
        bool(item.argv)
        and item.auto_execute
        and item.risk_level == "low"
        and confidence >= MIN_AUTO_EXECUTION_CONFIDENCE
        and not item.skip_reason
    )


def _step_for_plan(item: OrchestratedPath, options: OrchestratorOptions, confidence: float) -> WorkflowStep:
    if item.skip_reason:
        return WorkflowStep(
            name=f"plan:{item.id}",
            status="SKIP",
            outputs=[item.command] if item.command else [],
            warnings=[item.skip_reason],
        )
    if not options.execute:
        return WorkflowStep(
            name=f"plan:{item.id}",
            status="SKIP",
            outputs=[item.command],
            warnings=["preview_only"],
        )
    if not item.auto_execute:
        item.status = "skipped"
        item.skip_reason = "auto_execute_false"
    elif item.risk_level != "low":
        item.status = "skipped"
        item.skip_reason = "risk_not_low"
    elif confidence < MIN_AUTO_EXECUTION_CONFIDENCE:
        item.status = "skipped"
        item.skip_reason = "route_confidence_too_low"
    if item.skip_reason:
        return WorkflowStep(
            name=f"plan:{item.id}",
            status="SKIP",
            outputs=[item.command],
            warnings=[item.skip_reason],
        )
    return WorkflowStep(name=f"plan:{item.id}", status="PASS", outputs=[item.command])


def _next_actions(result: OrchestratorResult) -> list[str]:
    if not result.paths:
        return [result.decision.next_action]
    out = []
    for path in result.paths:
        if path.skip_reason:
            out.append(f"review:{path.id}:{path.skip_reason}")
        elif result.execute and path.status == "executed":
            out.append(f"executed:{path.id}")
        else:
            out.append(f"preview:{path.id}")
    return out


def render_orchestrator(result: OrchestratorResult) -> str:
    lines = [
        "# Agent Orchestrator",
        "",
        render_decision(result.decision).rstrip(),
        "",
        "## Execution Plan",
        "",
    ]
    if not result.paths:
        lines.extend(["未选中可执行路径。", ""])
        return "\n".join(lines)
    lines.extend([
        "| Path | Risk | Auto | Status | Command / Reason |",
        "|---|---|---|---|---|",
    ])
    for path in result.paths:
        command_or_reason = path.command or path.skip_reason or "-"
        lines.append(
            "| {id} | {risk} | {auto} | {status} | `{cmd}` |".format(
                id=path.id,
                risk=path.risk_level,
                auto=str(path.auto_execute).lower(),
                status=path.status,
                cmd=command_or_reason.replace("|", "/"),
            )
        )
    lines.append("")
    lines.append("## JSON")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    lines.append("```")
    lines.append("")
    return "\n".join(lines)
