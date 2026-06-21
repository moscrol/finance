from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from intelligence.paths import ProjectPaths, default_paths
from intelligence.services.logic_market_match import (
    LABEL_DATA_GAP,
    LABEL_NEW_CANDIDATE,
    LABEL_NOISE,
    LABEL_OLD_WAKEUP,
    available_candidate_dates,
    batch_match_logic_to_market,
)
from intelligence.summary import WorkflowStep, WorkflowSummary, now_iso
from scripts.build_daily_ops_ledger import build_ledger


@dataclass(frozen=True)
class DailyAgentOptions:
    date: str
    finance_root: str | Path | None = None
    kb_wiki: str | Path | None = None
    recent: int = 1
    top_per_date: int = 10
    top_companies: int = 8
    max_evidence: int = 5


def _paths_from_options(options: DailyAgentOptions) -> ProjectPaths:
    defaults = default_paths()
    return ProjectPaths(
        finance_root=Path(options.finance_root).expanduser() if options.finance_root else defaults.finance_root,
        knowledge_wiki=Path(options.kb_wiki).expanduser() if options.kb_wiki else defaults.knowledge_wiki,
        finance_site=defaults.finance_site,
    )


def _select_dates(date: str, recent: int, exports_dir: Path) -> list[str]:
    if recent <= 1:
        return [date]
    dates = [item for item in available_candidate_dates(exports_dir) if item <= date]
    selected = dates[-recent:]
    if date not in selected:
        selected.append(date)
    return selected


def _route_for_result(row: dict[str, Any]) -> str:
    classification = row.get("classification")
    gaps = row.get("data_gaps") or []
    if classification == LABEL_OLD_WAKEUP and not gaps:
        return "front-map / deep-dive"
    if classification == LABEL_OLD_WAKEUP and gaps:
        return "先保留，等统一回补 trace/evidence 后再 deep-dive"
    if classification == LABEL_NEW_CANDIDATE:
        return "brief / front-map，先建题材地图"
    if classification == LABEL_DATA_GAP:
        return "进入统一回补队列，先判断是不是污染词或别名"
    if classification == LABEL_NOISE:
        return "暂不处理，等待新盘面或证据"
    return "人工复核"


def _compact_result(row: dict[str, Any]) -> dict[str, Any]:
    stocks = []
    for stock in row.get("strong_stocks", [])[:5]:
        if isinstance(stock, dict):
            stocks.append(stock.get("stock_name") or stock.get("stock_ts_code") or "")
    return {
        "date": row.get("date"),
        "query": row.get("query"),
        "classification": row.get("classification"),
        "confidence": row.get("confidence"),
        "priority_score": row.get("priority_score"),
        "matched_theme": row.get("matched_theme"),
        "trigger_types": row.get("trigger_types") or [],
        "strong_stocks": [item for item in stocks if item],
        "data_gaps": row.get("data_gaps") or [],
        "route": _route_for_result(row),
        "next_actions": row.get("next_actions") or [],
    }


def _build_decision(batch: dict[str, Any]) -> dict[str, Any]:
    decision = {
        "old_logic_wakeup": [],
        "new_logic_candidate": [],
        "data_gap": [],
        "noise_or_unconfirmed": [],
    }
    for row in batch.get("results", []):
        compact = _compact_result(row)
        bucket = compact["classification"]
        if bucket in decision:
            decision[bucket].append(compact)
    for rows in decision.values():
        rows.sort(key=lambda item: float(item.get("priority_score") or 0), reverse=True)
    return decision


def _agent_next_actions(report: dict[str, Any]) -> list[str]:
    actions: list[str] = []
    decision = report["decision"]
    if decision["old_logic_wakeup"]:
        actions.append("优先打开 old_logic_wakeup：确认是否需要 front-map 或 deep-dive。")
    if decision["new_logic_candidate"]:
        actions.append("新逻辑先用 brief/front-map 定义题材边界，不急着 deep-dive。")
    if decision["data_gap"]:
        actions.append("数据缺口只登记到回补队列；本轮不自动 source/concept/IMA 回补。")
    ledger = report["ledger"]
    if ledger["sections"]["market_review"]["missing_count"]:
        actions.append("先补齐 daily workflow 产物，否则 agent 判断只作为预览。")
    if not actions:
        actions.append("今日产物和逻辑匹配清洁；可进入人工复盘或单题材深挖。")
    return actions


def build_daily_agent_report(options: DailyAgentOptions) -> dict[str, Any]:
    paths = _paths_from_options(options)
    ledger = build_ledger(options.date, paths)
    selected_dates = _select_dates(options.date, options.recent, paths.market_exports)
    batch = batch_match_logic_to_market(
        dates=selected_dates,
        top_per_date=options.top_per_date,
        exports_dir=paths.market_exports,
        kb_wiki=paths.knowledge_wiki,
        top_companies=options.top_companies,
        max_evidence=options.max_evidence,
    ).to_dict()
    report = {
        "date": options.date,
        "generated_at": now_iso(),
        "paths": {
            "finance_root": str(paths.finance_root),
            "knowledge_wiki": str(paths.knowledge_wiki),
            "market_exports": str(paths.market_exports),
        },
        "ledger": ledger,
        "logic_batch": batch,
        "decision": _build_decision(batch),
        "notes": [
            "agent-daily 是只读入口：读取 daily workflow、知识库和 logic-match 产物，不自动回补。",
            "回补类事项只进入 data_gap / gap_queue，等待用户统一处理。",
        ],
    }
    report["next_actions"] = _agent_next_actions(report)
    return report


def _section_rows(rows: list[dict[str, Any]], limit: int = 10) -> list[str]:
    if not rows:
        return ["- 无"]
    lines = []
    for item in rows[:limit]:
        gaps = ", ".join(item["data_gaps"]) or "-"
        stocks = ", ".join(item["strong_stocks"]) or "-"
        lines.append(
            f"- {item['query']}｜priority={item['priority_score'] if item['priority_score'] is not None else '-'}"
            f"｜confidence={item['confidence']}｜强势股={stocks}｜缺口={gaps}｜路径={item['route']}"
        )
    return lines


def render_daily_agent(report: dict[str, Any]) -> str:
    decision = report["decision"]
    ledger = report["ledger"]
    batch = report["logic_batch"]
    lines = [
        f"# Daily Agent Report - {report['date']}",
        "",
        "## 今日判断",
        "",
        f"- Daily ops status: `{ledger['status']}`",
        f"- Logic scanned: {batch['scanned_count']}",
        f"- Old logic wakeup: {len(decision['old_logic_wakeup'])}",
        f"- New logic candidate: {len(decision['new_logic_candidate'])}",
        f"- Data gap: {len(decision['data_gap'])}",
        f"- Noise/unconfirmed: {len(decision['noise_or_unconfirmed'])}",
        "",
        "## 旧逻辑唤醒",
        "",
        *_section_rows(decision["old_logic_wakeup"]),
        "",
        "## 新逻辑候选",
        "",
        *_section_rows(decision["new_logic_candidate"]),
        "",
        "## 数据缺口 / 以后统一回补",
        "",
        *_section_rows(decision["data_gap"]),
        "",
        "## 暂不处理",
        "",
        *_section_rows(decision["noise_or_unconfirmed"]),
        "",
        "## Gap Queue",
        "",
    ]
    gap_queue = batch.get("gap_queue") or []
    if gap_queue:
        for item in gap_queue[:20]:
            lines.append(
                f"- {item['query']}｜{item['classification']}｜priority={item['priority']}｜gaps={', '.join(item['data_gaps']) or '-'}"
            )
    else:
        lines.append("- 无")
    lines.extend(["", "## Next Actions", ""])
    for action in report["next_actions"]:
        lines.append(f"- {action}")
    lines.extend(["", "## Notes", ""])
    for note in report["notes"]:
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


def run_daily_agent(options: DailyAgentOptions) -> tuple[WorkflowSummary, dict[str, Any], str]:
    report = build_daily_agent_report(options)
    ledger_status = report["ledger"]["status"]
    batch = report["logic_batch"]
    summary = WorkflowSummary(
        workflow="agent-daily",
        status="PASS",
        started_at=now_iso(),
        inputs={
            "date": options.date,
            "recent": options.recent,
            "top_per_date": options.top_per_date,
        },
    )
    summary.steps.append(
        WorkflowStep(
            name="daily-ledger",
            status=ledger_status if ledger_status in {"PASS", "WARN"} else "FAIL",
            outputs=[
                f"market_missing={report['ledger']['sections']['market_review']['missing_count']}",
                f"briefings={report['ledger']['sections']['morning_briefing']['count']}",
            ],
        )
    )
    summary.steps.append(
        WorkflowStep(
            name="logic-market-batch",
            status="PASS" if batch["scanned_count"] else "WARN",
            outputs=[
                f"dates={','.join(batch['dates']) or '-'}",
                f"scanned={batch['scanned_count']}",
                f"gap_queue={len(batch['gap_queue'])}",
            ],
            warnings=list(batch.get("warnings") or []),
        )
    )
    summary.outputs = [
        f"old_logic_wakeup={len(report['decision']['old_logic_wakeup'])}",
        f"new_logic_candidate={len(report['decision']['new_logic_candidate'])}",
        f"data_gap={len(report['decision']['data_gap'])}",
    ]
    summary.warnings = list(batch.get("warnings") or [])
    summary.next_actions = list(report["next_actions"])
    if any(step.status == "FAIL" for step in summary.steps):
        summary.finish("FAIL")
    elif any(step.status == "WARN" for step in summary.steps):
        summary.finish("WARN")
    else:
        summary.finish("PASS")
    return summary, report, render_daily_agent(report)


def write_daily_agent_outputs(report: dict[str, Any], markdown: str, out_json: str | Path, out_md: str | Path) -> None:
    json_path = Path(out_json).expanduser()
    md_path = Path(out_md).expanduser()
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")
