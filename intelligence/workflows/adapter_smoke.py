from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from intelligence.adapters import KnowledgeAdapter, MarketAdapter
from intelligence.summary import WorkflowStep, WorkflowSummary, now_iso


@dataclass(frozen=True)
class AdapterSmokeOptions:
    date: str | None = None
    entity: str = "ASML"
    concept: str | None = None


def run_adapter_smoke(options: AdapterSmokeOptions) -> WorkflowSummary:
    summary = WorkflowSummary(
        workflow="adapter-smoke",
        status="PASS",
        started_at=now_iso(),
        inputs={"date": options.date, "entity": options.entity, "concept": options.concept},
    )
    market = MarketAdapter()
    knowledge = KnowledgeAdapter()

    market_health = market.health()
    summary.steps.append(_step_from_result("market-health", market_health.get("ok", False), market_health))

    capacity = market.get_capacity_sectors(options.date)
    summary.steps.append(_step_from_result("capacity-sectors", capacity.get("found", False), capacity))

    double_red = market.get_double_red_themes(options.date)
    summary.steps.append(_step_from_result("double-red-themes", double_red.get("found", False), double_red))

    entity_exposures = knowledge.get_entity_exposures(options.entity)
    summary.steps.append(_step_from_result("entity-exposures", entity_exposures.get("found", False), entity_exposures))

    evidence = knowledge.get_evidence(options.entity, concept=options.concept)
    summary.steps.append(_step_from_result("evidence", evidence.get("found", False), evidence))

    summary.outputs = [
        f"market_health_ok={market_health.get('ok', False)}",
        f"capacity_sector_count={len(capacity.get('capacity_sectors', []))}",
        f"double_red_count={double_red.get('count', 0)}",
        f"entity_found={entity_exposures.get('found', False)}",
        f"concept_count={len(entity_exposures.get('concepts', {}))}",
        f"evidence_count={len(evidence.get('items', []))}",
    ]
    summary.warnings = _collect_messages(summary.steps, "warnings")
    summary.errors = _collect_messages(summary.steps, "errors")
    summary.next_actions = ["Use adapter-smoke before integrating adapters into service/workflow layers."]
    summary.finish(_summary_status(summary.steps))
    return summary


def _step_from_result(name: str, passed: bool, result: dict[str, Any]) -> WorkflowStep:
    warnings = result.get("warnings", []) if isinstance(result.get("warnings", []), list) else [str(result.get("warnings"))]
    errors = result.get("errors", []) if isinstance(result.get("errors", []), list) else [str(result.get("errors"))]
    return WorkflowStep(
        name=name,
        status="PASS" if passed else "WARN",
        outputs=_result_outputs(name, result),
        warnings=warnings,
        errors=errors,
    )


def _result_outputs(name: str, result: dict[str, Any]) -> list[str]:
    if name == "market-health":
        return [f"ok={result.get('ok', False)}"]
    if name == "capacity-sectors":
        return [f"count={len(result.get('capacity_sectors', []))}", f"trade_date={result.get('trade_date')}"]
    if name == "double-red-themes":
        return [f"count={result.get('count', 0)}", f"trade_date={result.get('trade_date')}"]
    if name == "entity-exposures":
        return [f"found={result.get('found', False)}", f"concept_count={len(result.get('concepts', {}))}"]
    if name == "evidence":
        return [f"found={result.get('found', False)}", f"evidence_count={len(result.get('items', []))}"]
    return []


def _collect_messages(steps: list[WorkflowStep], field: str) -> list[str]:
    messages: list[str] = []
    for step in steps:
        values = getattr(step, field)
        for value in values:
            messages.append(f"{step.name}: {value}")
    return messages


def _summary_status(steps: list[WorkflowStep]) -> str:
    if any(step.status == "FAIL" for step in steps):
        return "FAIL"
    if any(step.status == "WARN" for step in steps):
        return "WARN"
    return "PASS"
