"""Structured, module-by-module Workbench reports.

The stream contract is deliberately presentation-neutral: producers emit bounded
JSON modules, SSE transports them, and React decides how to render them. Canonical
Markdown remains an input source, never the primary Workbench artifact.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from intelligence.api.daily_reports import project_daily_review_markdown
from intelligence.services.ask import AskResult, SUBHEAD
from intelligence.services.market_moneyflow import MoneyflowSnapshot

REPORT_SCHEMA_VERSION = 1


def new_structured_report(
    *,
    run_id: str,
    question: str,
    task_type: str,
) -> dict[str, Any]:
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "report_id": run_id,
        "title": question,
        "task_type": task_type,
        "status": "streaming",
        "as_of": None,
        "llm": {"used": False, "provider": None, "model": None},
        "modules": [],
        "warnings": [],
    }


def upsert_report_module(
    report: dict[str, Any],
    module: dict[str, Any],
) -> dict[str, Any]:
    modules = [
        existing
        for existing in report.get("modules", [])
        if existing.get("module_id") != module.get("module_id")
    ]
    modules.append(module)
    report["modules"] = modules
    return report


def daily_projection_modules(
    repo_root: Path,
) -> tuple[str | None, list[dict[str, Any]], list[str]]:
    exports = repo_root / "market_feature_store" / "exports"
    candidates = sorted(exports.glob("*-daily-review.md"), reverse=True)
    if not candidates:
        return None, [], ["未找到 canonical Daily Review Markdown；日报基础模块缺失。"]
    source_path = candidates[0]
    date_text = source_path.name.removesuffix("-daily-review.md")
    projection = project_daily_review_markdown(
        source_path.read_text(encoding="utf-8"),
        source_path=str(source_path.relative_to(repo_root)),
        date=date_text,
    )
    warnings = list(projection.get("provenance", {}).get("warnings", []))
    modules: list[dict[str, Any]] = [
        {
            "module_id": "daily_overview",
            "title": "今日核心",
            "kind": "summary",
            "status": "degraded" if warnings else "complete",
            "summary": "基于 canonical Daily Review 的确定性投影。",
            "content": None,
            "metrics": projection.get("metrics", []),
            "items": [
                {"summary": line, "badges": [], "meta": []}
                for line in projection.get("plain_summary", [])
            ],
            "table": None,
            "warnings": warnings,
            "provenance": {
                "source": projection.get("provenance", {}).get("canonical_path"),
                "as_of": date_text,
                "generated_by": "deterministic_projection",
            },
        }
    ]
    for index, section in enumerate(projection.get("sections", []), start=1):
        modules.append(
            {
                "module_id": f"daily_section_{index}",
                "title": str(section.get("title") or f"日报章节 {index}"),
                "kind": "list",
                "status": "complete",
                "summary": None,
                "content": None,
                "metrics": [],
                "items": list(section.get("items", [])),
                "table": None,
                "warnings": [],
                "provenance": {
                    "source": projection.get("provenance", {}).get("canonical_path"),
                    "as_of": date_text,
                    "generated_by": "deterministic_projection",
                },
            }
        )
    return date_text, modules, warnings


def moneyflow_module(snapshot: MoneyflowSnapshot) -> dict[str, Any]:
    coverage_total = sum(snapshot.coverage.values())
    leader = snapshot.leaders[0] if snapshot.leaders else None
    metrics = [
        {"label": "扫描日期", "value": snapshot.trade_date or "无数据"},
        {"label": "覆盖股票", "value": str(coverage_total), "context": "涨停股 + 成交额前100"},
        {
            "label": "净流入强度首位",
            "value": leader.stock_name if leader else "无数据",
            "context": f"{leader.score:.2f}%" if leader and leader.score is not None else None,
        },
        {"label": "量化单样本", "value": str(len(snapshot.quant_orders))},
    ]
    leader_rows = [
        {
            "stock": row.stock_name,
            "scan_type": row.scan_type,
            "main_buy_net_wan": row.main_buy_net_wan,
            "total_buy_net_wan": row.total_buy_net_wan,
            "score": row.score,
            "rank": row.rank,
            "pct_change": row.pct_change,
        }
        for row in snapshot.leaders
    ]
    quant_items = [
        {
            "title": row.stock_name,
            "summary": (
                f"量化单 {row.quant_amount_wan or 0:.1f} 万，"
                f"占大单买入 {row.quant_pct_of_big_buy or 0:.1f}%"
            ),
            "badges": [f"{row.cluster_count or 0} 个簇"],
            "meta": (
                [{"label": "最大簇", "value": row.biggest_cluster}]
                if row.biggest_cluster
                else []
            ),
        }
        for row in snapshot.quant_orders
    ]
    return {
        "module_id": "l2_moneyflow",
        "title": "L2 大单资金流",
        "kind": "table",
        "status": "complete" if snapshot.status == "ok" else "degraded",
        "summary": "自有逐笔成交口径；直接读取 DuckDB 特征表，非 LLM 生成。",
        "content": None,
        "metrics": metrics,
        "items": quant_items,
        "table": {
            "columns": [
                {"key": "stock", "label": "股票"},
                {"key": "scan_type", "label": "扫描口径"},
                {"key": "main_buy_net_wan", "label": "主买净额(万)"},
                {"key": "total_buy_net_wan", "label": "总买净额(万)"},
                {"key": "score", "label": "净流入强度(%)"},
                {"key": "pct_change", "label": "涨幅(%)"},
            ],
            "rows": leader_rows,
        },
        "warnings": list(snapshot.warnings),
        "provenance": {
            "source": snapshot.source,
            "as_of": snapshot.trade_date,
            "generated_by": "deterministic_duckdb_query",
        },
    }


def ask_result_modules(result: AskResult) -> list[dict[str, Any]]:
    modules: list[dict[str, Any]] = []
    review_degraded = result.review_gate is not None and result.review_gate.warn_count > 0
    rag_degraded = (
        result.wiki_rag_telemetry is not None
        and (
            result.wiki_rag_telemetry.degraded
            or result.wiki_rag_telemetry.status not in {"ok", "pending"}
        )
    )
    answer_degraded = bool(result.warnings) or review_degraded or rag_degraded
    if result.synthesis:
        modules.append(
            {
                "module_id": "llm_synthesis",
                "title": "LLM 综合判断",
                "kind": "narrative",
                "status": "degraded" if answer_degraded else "complete",
                "summary": "LLM 只在已检索证据边界内组织表达；请按引用核对。",
                "content": result.synthesis,
                "metrics": [],
                "items": [],
                "table": None,
                "warnings": list(dict.fromkeys(result.warnings)) if answer_degraded else [],
                "provenance": {
                    "source": "retrieved_evidence",
                    "as_of": result.trade_date,
                    "generated_by": f"llm:{result.llm_provider or 'unknown'}",
                },
            }
        )
    section_kinds = {
        "结论": "summary",
        "证据链": "evidence",
        "分歧反证": "risks",
        "后续验证点": "actions",
        "检索可观测": "telemetry",
        "输出质检": "review",
        "交易含义": "implications",
        "引用来源": "sources",
    }
    for index, (title, lines) in enumerate(result.sections.items(), start=1):
        section_degraded = (
            (title == "输出质检" and review_degraded)
            or (title in {"证据链", "检索可观测", "引用来源"} and rag_degraded)
            or (title in {"结论", "交易含义"} and answer_degraded)
        )
        items = []
        for line in lines:
            text = str(line)
            if text.startswith(SUBHEAD):
                items.append(
                    {
                        "title": text[len(SUBHEAD) :],
                        "summary": "",
                        "badges": ["分组"],
                        "meta": [],
                    }
                )
            else:
                items.append({"summary": text, "badges": [], "meta": []})
        modules.append(
            {
                "module_id": f"research_{index}_{section_kinds.get(title, 'section')}",
                "title": title,
                "kind": section_kinds.get(title, "list"),
                "status": "degraded" if section_degraded else "complete",
                "summary": None,
                "content": None,
                "metrics": [],
                "items": items,
                "table": None,
                "warnings": list(dict.fromkeys(result.warnings)) if section_degraded else [],
                "provenance": {
                    "source": "ask_retrieval_pipeline",
                    "as_of": result.trade_date,
                    "generated_by": "deterministic_projection",
                },
            }
        )
    return modules


def complete_report(
    report: dict[str, Any],
    *,
    as_of: str | None,
    warnings: list[str],
    llm_provider: str | None,
    llm_model: str | None,
) -> dict[str, Any]:
    report["status"] = "completed"
    report["as_of"] = as_of
    report["warnings"] = list(dict.fromkeys(warnings))
    report["llm"] = {
        "used": llm_provider is not None,
        "provider": llm_provider,
        "model": llm_model,
    }
    report["completed_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return report
