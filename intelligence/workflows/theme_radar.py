from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from intelligence.services import ThemeRadarService
from intelligence.summary import WorkflowStep, WorkflowSummary, now_iso


@dataclass(frozen=True)
class ThemeRadarOptions:
    date: str
    market_triggered: bool = False
    top: int = 50
    out_json: str | None = None
    out_md: str | None = None


def run_theme_radar(options: ThemeRadarOptions) -> WorkflowSummary:
    summary = WorkflowSummary(
        workflow="theme",
        status="PASS",
        started_at=now_iso(),
        inputs={
            "date": options.date,
            "market_triggered": options.market_triggered,
            "top": options.top,
            "out_json": options.out_json,
            "out_md": options.out_md,
        },
    )
    if not options.market_triggered:
        summary.steps.append(
            WorkflowStep(
                name="theme-mode",
                status="FAIL",
                errors=["only --market-triggered mode is supported in the minimal theme CLI"],
            )
        )
        summary.errors = ["theme-mode: only --market-triggered mode is supported in the minimal theme CLI"]
        summary.finish("FAIL")
        return summary

    result = ThemeRadarService().build_market_triggered_candidates(options.date, top=options.top)
    summary.steps.append(_step_from_candidates(result))
    summary.outputs = [
        f"trade_date={result.get('trade_date')}",
        f"candidate_count={result.get('candidate_count', 0)}",
        f"deep_count={result.get('tier_summary', {}).get('deep_count', 0)}",
        f"watch_count={result.get('tier_summary', {}).get('watch_count', 0)}",
        f"long_tail_count={result.get('tier_summary', {}).get('long_tail_count', 0)}",
        *[
            (
                f"candidate={item.get('market_theme')} score={item.get('priority_score')} "
                f"triggers={','.join(item.get('trigger_types', []))} "
                f"concept_count={item.get('knowledge_status', {}).get('concept_count', 0)} "
                f"exposure_count={item.get('knowledge_status', {}).get('exposure_count', 0)} "
                f"evidence_count={item.get('knowledge_status', {}).get('evidence_count', 0)}"
            )
            for item in result.get("candidates", [])[:5]
        ],
    ]
    if options.out_json:
        out_path = _write_payload(options.out_json, result)
        summary.outputs.append(f"out_json={out_path}")
    if options.out_md:
        out_path = _write_text(options.out_md, render_market_triggered_markdown(result, top=options.top))
        summary.outputs.append(f"out_md={out_path}")
    summary.warnings = [f"market-triggered-candidates: {msg}" for msg in result.get("warnings", [])]
    summary.errors = [f"market-triggered-candidates: {msg}" for msg in result.get("errors", [])]
    summary.next_actions = ["Review market-triggered candidates before enabling deep radar report generation."]
    summary.finish("PASS" if result.get("found") and not summary.errors else "WARN" if not summary.errors else "FAIL")
    return summary


def _step_from_candidates(result: dict[str, Any]) -> WorkflowStep:
    status = "PASS" if result.get("found") else "WARN"
    if result.get("errors"):
        status = "FAIL"
    return WorkflowStep(
        name="market-triggered-candidates",
        status=status,
        outputs=[
            f"trade_date={result.get('trade_date')}",
            f"candidate_count={result.get('candidate_count', 0)}",
        ],
        warnings=result.get("warnings", []),
        errors=result.get("errors", []),
    )


def _write_payload(path: str, payload: dict[str, Any]) -> Path:
    out = Path(path).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out


def _write_text(path: str, text: str) -> Path:
    out = Path(path).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    return out


def render_market_triggered_markdown(result: dict[str, Any], top: int = 50) -> str:
    trade_date = result.get("trade_date") or ""
    context = result.get("market_context", {})
    deep_candidates = result.get("deep_candidates", [])[: min(10, top)]
    remaining_top = max(top - len(deep_candidates), 0)
    watch_candidates = result.get("watch_candidates", [])[: min(20, remaining_top)]
    remaining_top = max(remaining_top - len(watch_candidates), 0)
    long_tail_candidates = result.get("long_tail_candidates", [])[:remaining_top]
    lines = [
        f"# {trade_date} 市场触发候选简报",
        "",
        "> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。",
        "",
        "## 一、市场上下文",
        "",
        f"- **市场阶段**：{_value(context.get('market_stage'))}",
        f"- **成交额**：{_value(context.get('total_amount'))}",
        f"- **上涨家数**：{_value(context.get('advancers'))}",
        f"- **涨停 / 跌停**：{_value(context.get('limit_up'))} / {_value(context.get('limit_down'))}",
        f"- **容量前三行业**：{_capacity_text(context.get('capacity_sectors', []))}",
        "",
        "## 二、核心候选 Deep（Top 10）",
        "",
        _candidate_overview_table(deep_candidates),
        "",
        "## 三、观察候选 Watch（Top 11-30）",
        "",
        _candidate_overview_table(watch_candidates),
        "",
        "## 四、长尾候选 Long Tail（Top 31-50）",
        "",
        _candidate_overview_table(long_tail_candidates),
        "",
        "## 五、核心候选明细",
        "",
    ]
    for item in deep_candidates:
        lines.extend(_candidate_section(int(item.get("rank") or 0), item))
    if result.get("warnings"):
        lines.extend(["## 六、Warnings", "", *[f"- {warning}" for warning in result.get("warnings", [])], ""])
    return "\n".join(lines)


def _candidate_overview_table(candidates: list[dict[str, Any]]) -> str:
    return _markdown_table(
        ["排名", "题材", "标准概念", "申万一级", "评分", "触发", "概念", "公司暴露", "证据", "缺口"],
        [
            [
                item.get("rank"),
                item.get("market_theme"),
                item.get("canonical_concept"),
                item.get("sw_l1"),
                item.get("priority_score"),
                "、".join(item.get("trigger_types", [])),
                item.get("knowledge_status", {}).get("concept_count", 0),
                item.get("knowledge_status", {}).get("exposure_count", 0),
                item.get("knowledge_status", {}).get("evidence_count", 0),
                "、".join(item.get("knowledge_status", {}).get("backfill_gaps", [])) or "-",
            ]
            for item in candidates
        ],
    )


def _candidate_section(index: int, item: dict[str, Any]) -> list[str]:
    metrics = item.get("market_evidence", {}).get("sector_metrics", {})
    concepts = item.get("matched_concepts", [])
    companies = item.get("candidate_companies", [])
    details = item.get("score_detail", [])
    status = item.get("knowledge_status", {})
    return [
        f"## 候选 {index}：{_value(item.get('market_theme'))}",
        "",
        f"- **标准概念**：{_value(item.get('canonical_concept'))}",
        f"- **申万一级**：{_value(item.get('sw_l1'))}",
        f"- **评分**：{_value(item.get('priority_score'))}",
        f"- **触发类型**：{'、'.join(item.get('trigger_types', [])) or '-'}",
        f"- **盘面信号**：涨幅 {_value(metrics.get('pct_chg'))}%，边际量 {_value(metrics.get('diff_ratio'))}%，成交额 {_value(metrics.get('amount'))} 亿，容量前三={_yes_no(metrics.get('in_capacity_top3'))}",
        f"- **知识库状态**：concept={_yes_no(status.get('local_concept_found'))}（{status.get('concept_count', 0)}），exposure={_yes_no(status.get('local_exposures_found'))}（{status.get('exposure_count', 0)}），evidence={_yes_no(status.get('local_evidence_found'))}（{status.get('evidence_count', 0)}）",
        f"- **缺口标记**：{'、'.join(status.get('backfill_gaps', [])) or '-'}",
        "",
        "**评分明细**",
        "",
        _markdown_table(
            ["信号", "加分", "原因"],
            [[row.get("signal"), row.get("score"), row.get("reason")] for row in details[:8]],
        ),
        "",
        "**匹配概念**",
        "",
        _markdown_table(["概念", "分数"], [[row.get("concept"), row.get("score")] for row in concepts[:5]]),
        "",
        "**候选公司暴露**",
        "",
        _markdown_table(
            ["公司", "代码", "概念", "角色/摘要", "强度", "证据层", "分数"],
            [
                [
                    row.get("company"),
                    row.get("ticker"),
                    row.get("concept"),
                    _truncate(row.get("role"), 36),
                    row.get("strength"),
                    row.get("evidence_layer"),
                    row.get("score"),
                ]
                for row in companies[:8]
            ],
        ),
        "",
    ]


def _markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    if not rows:
        rows = [["-" for _ in headers]]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        values = [_escape_cell(_value(value)) for value in row]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def _capacity_text(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "-"
    return "、".join(f"{row.get('rank')}.{row.get('name')}({row.get('ratio')}%, {row.get('capacity_type')})" for row in rows)


def _yes_no(value: Any) -> str:
    if value is None:
        return "-"
    return "是" if value else "否"


def _value(value: Any) -> str:
    if value is None or value == "":
        return "-"
    return str(value)


def _truncate(value: Any, limit: int) -> str:
    text = _value(value)
    return text if len(text) <= limit else text[:limit] + "..."


def _escape_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
