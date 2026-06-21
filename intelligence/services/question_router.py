from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from intelligence.services.path_registry import PathSpec, load_registry


ROUTE_KNOWN = "known_workflow"
ROUTE_PLANNER = "planner_analysis"
ROUTE_DATA_GAP = "data_gap"
ROUTE_CLARIFICATION = "clarification_needed"

ANALYSIS_TRIGGERS = (
    "为什么", "怎么看", "怎么理解", "有没有机会", "有没有弹性", "是否", "能不能",
    "值不值", "逻辑", "盘面", "异动", "上涨", "下跌", "共振", "兑现", "风险",
    "预期差", "旧逻辑", "新逻辑", "唤醒", "噪音",
)
DATA_GAP_TRIGGERS = (
    "缺", "missing", "没有source", "没source", "没有 raw", "没 raw", "没有raw",
    "没进库", "未入库", "补库", "补齐", "查漏补缺", "trace", "可追溯",
)
CLARIFY_TRIGGERS = ("随便", "帮我看看", "分析一下", "看看")


@dataclass(frozen=True)
class RoutePath:
    id: str
    label: str
    kind: str
    reason: str
    command_template: str = ""
    auto_execute: bool = False
    risk_level: str = "medium"
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "kind": self.kind,
            "reason": self.reason,
            "command_template": self.command_template,
            "auto_execute": self.auto_execute,
            "risk_level": self.risk_level,
            "notes": self.notes,
        }


@dataclass
class RouteDecision:
    query: str
    route_type: str
    confidence: float
    selected_paths: list[RoutePath] = field(default_factory=list)
    plan_steps: list[str] = field(default_factory=list)
    missing_data_checks: list[str] = field(default_factory=list)
    next_action: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "route_type": self.route_type,
            "confidence": self.confidence,
            "selected_paths": [path.to_dict() for path in self.selected_paths],
            "plan_steps": self.plan_steps,
            "missing_data_checks": self.missing_data_checks,
            "next_action": self.next_action,
            "warnings": self.warnings,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", text.lower())


def trigger_hits(query: str, spec: PathSpec) -> list[str]:
    q = normalize(query)
    hits = []
    for trigger in spec.triggers:
        t = normalize(trigger)
        if t and t in q:
            hits.append(trigger)
    return hits


def _route_path(spec: PathSpec, reason: str) -> RoutePath:
    return RoutePath(
        id=spec.id,
        label=spec.label,
        kind=spec.kind,
        reason=reason,
        command_template=spec.command_template,
        auto_execute=spec.auto_execute,
        risk_level=spec.risk_level,
        notes=spec.notes,
    )


def _is_bare_theme(query: str) -> bool:
    text = query.strip()
    if not text:
        return False
    if len(text) <= 12 and not any(token in text for token in ANALYSIS_TRIGGERS + DATA_GAP_TRIGGERS):
        return True
    return False


def route_question(query: str, registry: list[PathSpec] | None = None) -> RouteDecision:
    specs = registry or load_registry()
    raw_query = str(query or "").strip()
    if not raw_query:
        return RouteDecision(
            query=raw_query,
            route_type=ROUTE_CLARIFICATION,
            confidence=0.1,
            next_action="ask_user_to_clarify",
            warnings=["empty query"],
            plan_steps=["请补充你要分析的题材、个股、日期或材料类型。"],
        )

    matched: list[RoutePath] = []
    for spec in specs:
        hits = trigger_hits(raw_query, spec)
        if hits:
            matched.append(_route_path(spec, f"matched triggers: {', '.join(hits[:5])}"))

    q_norm = normalize(raw_query)
    has_analysis = any(normalize(token) in q_norm for token in ANALYSIS_TRIGGERS)
    has_data_gap = any(normalize(token) in q_norm for token in DATA_GAP_TRIGGERS)

    if has_data_gap:
        gap_paths = [path for path in matched if path.id in {"daily_ops_ledger", "logic_match_batch", "concept_backfill", "source_backfill", "ima_stock_ingest"}]
        by_id = {spec.id: spec for spec in specs}
        existing_ids = {path.id for path in gap_paths}
        ordered_gap_paths: list[RoutePath] = []
        for path_id in ("daily_ops_ledger", "logic_match_batch", "source_backfill", "concept_backfill", "ima_stock_ingest"):
            if path_id in existing_ids:
                ordered_gap_paths.extend(path for path in gap_paths if path.id == path_id)
                continue
            if path_id in {"daily_ops_ledger", "logic_match_batch"}:
                spec = by_id.get(path_id)
                if spec:
                    reason = "data-gap status baseline" if path_id == "daily_ops_ledger" else "data-gap priority queue"
                    ordered_gap_paths.append(_route_path(spec, reason))
        gap_paths = ordered_gap_paths
        return RouteDecision(
            query=raw_query,
            route_type=ROUTE_DATA_GAP,
            confidence=0.78 if gap_paths else 0.55,
            selected_paths=gap_paths,
            missing_data_checks=[
                "检查 daily-ops-ledger 的 missing source / missing concept / 未入库 / 待人工确认。",
                "检查 raw/source/evidence 是否能互相追溯。",
                "若缺口是真实业务概念，再进入 concept_backfill；若只是别名或污染词，先归一或清理。",
            ],
            plan_steps=[
                "先跑只读台账，不直接修库。",
                "按缺口类型分流到 source_backfill、concept_backfill 或 IMA stock ingest。",
                "高风险写入步骤需要人工确认或 dry-run 报告。",
            ],
            next_action="run_daily_ops_ledger_then_backfill_queue",
        )

    if matched and not has_analysis:
        return RouteDecision(
            query=raw_query,
            route_type=ROUTE_KNOWN,
            confidence=min(0.95, 0.62 + len(matched) * 0.08),
            selected_paths=matched,
            plan_steps=[
                "确认路径所需输入是否齐全。",
                "优先 dry-run 或只读预览。",
                "若路径 auto_execute=false，生成执行清单而不是自动写库。",
            ],
            next_action=f"run_or_preview:{matched[0].id}",
        )

    if has_analysis or _is_bare_theme(raw_query):
        by_id = {spec.id: spec for spec in specs}
        planner_paths: list[RoutePath] = []
        for path in matched:
            if path.id not in {p.id for p in planner_paths}:
                planner_paths.append(path)
        for path_id in ("logic_market_match", "front_map", "deep_dive"):
            spec = by_id.get(path_id)
            if spec and spec.id not in {p.id for p in planner_paths}:
                reason = "planner default path" if path_id == "logic_market_match" else "optional drill-down path"
                planner_paths.append(_route_path(spec, reason))
        return RouteDecision(
            query=raw_query,
            route_type=ROUTE_PLANNER,
            confidence=0.72 if has_analysis else 0.58,
            selected_paths=planner_paths,
            missing_data_checks=[
                "是否有对应日期 theme-candidates。",
                "知识库是否存在 concept_graph/entity_exposures/evidence_index 命中。",
                "证据是否有 source/raw trace。",
                "个股问题是否已有 IMA stock card。",
            ],
            plan_steps=[
                "先做 logic_market_match：盘面信号对齐知识库逻辑与证据。",
                "若是已知题材，再按需要进入 front-map 或 deep-dive。",
                "若证据不足，输出补 source/concept/IMA 的任务，而不是硬答。",
            ],
            next_action="run_logic_match",
        )

    if matched:
        return RouteDecision(
            query=raw_query,
            route_type=ROUTE_KNOWN,
            confidence=0.55,
            selected_paths=matched,
            plan_steps=["命中已知路径，但意图不够强；建议先输出 dry-run 计划。"],
            next_action=f"preview:{matched[0].id}",
            warnings=["weak intent; route with caution"],
        )

    if any(token == raw_query for token in CLARIFY_TRIGGERS):
        return RouteDecision(
            query=raw_query,
            route_type=ROUTE_CLARIFICATION,
            confidence=0.5,
            plan_steps=["请用户补充题材/个股/日期/材料类型。"],
            next_action="ask_user_to_clarify",
        )

    return RouteDecision(
        query=raw_query,
        route_type=ROUTE_PLANNER,
        confidence=0.42,
        selected_paths=[],
        missing_data_checks=["未命中已知路径；需要先抽取问题里的题材、个股、日期和目标。"],
        plan_steps=[
            "让 Planner 抽取实体与目标。",
            "若抽取到题材/个股，转 logic_market_match。",
            "若抽取失败，向用户追问。",
        ],
        next_action="planner_extract_intent",
        warnings=["no registered path matched"],
    )


def render_decision(decision: RouteDecision) -> str:
    lines = [
        f"# Route Decision",
        "",
        f"- Query: {decision.query}",
        f"- Route type: {decision.route_type}",
        f"- Confidence: {decision.confidence:.2f}",
        f"- Next action: {decision.next_action}",
        "",
        "## Selected Paths",
        "",
    ]
    if decision.selected_paths:
        for path in decision.selected_paths:
            lines.append(f"- `{path.id}`｜{path.label}｜{path.reason}")
            if path.command_template:
                lines.append(f"  command: `{path.command_template}`")
    else:
        lines.append("- none")
    lines.extend(["", "## Plan Steps", ""])
    for step in decision.plan_steps:
        lines.append(f"- {step}")
    if decision.missing_data_checks:
        lines.extend(["", "## Missing Data Checks", ""])
        for item in decision.missing_data_checks:
            lines.append(f"- {item}")
    if decision.warnings:
        lines.extend(["", "## Warnings", ""])
        for warning in decision.warnings:
            lines.append(f"- {warning}")
    lines.append("")
    return "\n".join(lines)
