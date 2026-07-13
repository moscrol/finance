"""Structured, module-by-module Workbench reports.

The stream contract is deliberately presentation-neutral: producers emit bounded
JSON modules, SSE transports them, and React decides how to render them. Canonical
Markdown remains an input source, never the primary Workbench artifact.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from intelligence.api.daily_reports import project_daily_review_markdown
from intelligence.services.ask import AskResult, SUBHEAD
from intelligence.services.market_moneyflow import MoneyflowSnapshot

REPORT_SCHEMA_VERSION = 1

_DAILY_TITLE_REPLACEMENTS = {
    "题材量能": "哪些方向在放量上涨",
    "新高方向": "哪些行业在创新高",
    "涨停方向": "涨停较集中的方向",
    "加权强股": "成交活跃且涨幅靠前的股票",
    "市场环境判断": "市场判断",
    "数据覆盖提醒": "数据说明",
    "专业数据": "数据明细",
    "量能状态": "成交情况",
    "情绪状态": "赚钱效应",
    "成交集中": "资金集中度",
    "强度状态": "短线热度",
}


def _humanize_daily_title(value: object) -> object:
    if not isinstance(value, str):
        return value
    return _DAILY_TITLE_REPLACEMENTS.get(value, value)


def _signed_change(value: str, *, unit: str = "%") -> str:
    number = float(value)
    direction = "增加" if number >= 0 else "减少"
    return f"{direction}{abs(number):.2f}{unit}"


def _humanize_daily_text(value: object) -> object:
    if not isinstance(value, str):
        return value
    text = value.strip()
    index_match = re.fullmatch(
        r"上证\s+([\d.]+)，涨幅\s+([+-]?[\d.]+)%，偏离度\s+([+-]?[\d.]+)%",
        text,
    )
    if index_match:
        close, change, distance = index_match.groups()
        return (
            f"上证收于 {float(close):.2f} 点，涨跌幅 {float(change):.2f}%，"
            f"距离短期均线 {float(distance):.2f}%"
        )
    amount_match = re.fullmatch(
        r"成交额\s*([\d.]+)亿，较昨日\s*([+-]?[\d.]+)%，相对20日均量\s*([\d.]+)%",
        text,
    )
    if amount_match:
        amount, change, ratio = amount_match.groups()
        return (
            f"成交额 {float(amount):.2f} 亿元（约 {float(amount) / 10000:.2f} 万亿元），"
            f"较昨日{_signed_change(change)}，达到近20日平均的 {float(ratio):.2f}%"
        )
    mood_match = re.fullmatch(
        r"涨家数\s*([\d.]+)，MA5\s*([\d.]+)，涨停\s*([\d.]+)，跌停\s*([\d.]+)",
        text,
    )
    if mood_match:
        advancers, average, limit_up, limit_down = mood_match.groups()
        return (
            f"上涨 {int(float(advancers))} 只，近5日平均 {float(average):.0f} 只，"
            f"涨停 {int(float(limit_up))} 只，跌停 {int(float(limit_down))} 只"
        )
    concentration_match = re.fullmatch(
        r"前三行业\s*([\d.]+)%，较昨日\s*([+-]?[\d.]+)pct",
        text,
    )
    if concentration_match:
        ratio, change = concentration_match.groups()
        return (
            f"成交最集中的三个行业占 {float(ratio):.2f}%，"
            f"较昨日{_signed_change(change, unit='个百分点')}"
        )
    strength_match = re.fullmatch(
        r"沸点，强度加权涨幅\s*([\d.]+)%，强度成交占比\s*([\d.]+)%",
        text,
    )
    if strength_match:
        change, ratio = strength_match.groups()
        return (
            f"短线情绪偏热；强势股平均上涨 {float(change):.2f}%，"
            f"相关成交占全市场 {float(ratio):.2f}%"
        )
    environment_match = re.fullmatch(
        r"(\d{4}-\d{2}-\d{2})\s+市场性质为\s*(.+?)，市场阶段为\s*(.+?)。"
        r"成交额\s*([\d.]+)亿，较昨日\s*([+-]?[\d.]+)%；"
        r"前三行业占比\s*([\d.]+)%[。；]"
        r"主线集中在\s*(.+?)\s*相关方向，强度状态为\s*(.+?)。",
        text,
    )
    if environment_match:
        (
            date,
            market_type,
            stage,
            amount,
            amount_change,
            concentration,
            directions,
            heat,
        ) = environment_match.groups()
        heat_text = (
            "短线情绪偏热"
            if heat.strip() == "沸点"
            else f"短线热度为{heat.strip()}"
        )
        return (
            f"{date} 为{market_type.strip()}，市场处于{stage.strip()}。"
            f"成交额 {float(amount):.2f} 亿元，较昨日{_signed_change(amount_change)}；"
            f"成交最集中的三个行业占 {float(concentration):.2f}%。"
            f"资金主要集中在{directions.strip()}，{heat_text}"
        )
    coverage_match = re.search(
        r"fact_sw_l1_daily：OK（降级\s*(\d+)/(\d+)：复盘会聚合代理）",
        text,
    )
    if coverage_match:
        used, total = coverage_match.groups()
        return (
            f"一级行业行情当日有 {used}/{total} 行使用替代口径；"
            "可用于判断方向，精确值需谨慎"
        )
    text = re.sub(
        r"普通交易日\s*/\s*(.+阶段)\s*第(\d+)天",
        r"市场处于\1的第\2个交易日",
        text,
    )
    text = re.sub(
        r"双红\s+(\d+)\s*个，单红\s+(\d+)\s*个；双红主线：",
        r"\1 个方向同时上涨且放量，\2 个方向只满足上涨或放量其中一项；"
        r"主要放量上涨方向：",
        text,
    )
    text = text.replace("双红主线：", "上涨且成交同步放大的方向：")
    text = text.replace("120日新高", "近120日新高")
    text = text.replace("前三申万：", "主要行业：")
    text = text.replace("核心涨停题材：", "涨停较集中的方向：")
    text = text.replace("偏离度", "距离短期均线")
    text = text.replace("MA5", "近5日平均")
    text = re.sub(r"强度状态为\s*沸点", "短线情绪偏热", text)
    text = re.sub(r"短线热度为\s*沸点", "短线情绪偏热", text)
    text = text.replace("强度状态为", "短线热度为")
    text = text.replace("主线集中在", "资金主要集中在")
    text = text.replace("fact_sw_l1_daily", "一级行业行情数据")
    text = text.replace("fact_sector_daily", "板块行情数据")
    text = text.replace("fact_market_daily", "市场日行情数据")
    text = text.replace("fact_stock_daily", "个股日行情数据")
    text = text.replace("表：状态；", "")
    text = text.replace("：OK", "：数据完整")
    text = text.replace("canonical Daily Review", "本地正式日报")
    text = text.replace("deterministic_projection", "本地数据整理")
    if text.startswith("⚠️ 数据降级："):
        return (
            "行业官方口径当日缺数，现使用板块行情汇总作为替代；"
            "可用于判断方向，不应把精确涨跌幅和成交额视为官方行业指数"
        )
    return text


def _humanize_daily_item(item: dict[str, Any]) -> dict[str, Any]:
    humanized = dict(item)
    humanized["title"] = _humanize_daily_title(humanized.get("title"))
    humanized["summary"] = _humanize_daily_text(humanized.get("summary"))
    return humanized


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
        return None, [], ["未找到本地复盘报告；日报基础模块缺失。"]
    source_path = candidates[0]
    date_text = source_path.name.removesuffix("-daily-review.md")
    projection = project_daily_review_markdown(
        source_path.read_text(encoding="utf-8"),
        source_path=str(source_path.relative_to(repo_root)),
        date=date_text,
    )
    warnings = [
        str(_humanize_daily_text(warning))
        for warning in projection.get("provenance", {}).get("warnings", [])
    ]
    metrics = [
        {
            **metric,
            "label": _humanize_daily_title(metric.get("label")),
            "value": _humanize_daily_text(metric.get("value")),
        }
        for metric in projection.get("metrics", [])
    ]
    modules: list[dict[str, Any]] = [
        {
            "module_id": "daily_overview",
            "title": "今日核心",
            "kind": "summary",
            "status": "degraded" if warnings else "complete",
            "summary": "基于本地复盘报告数据。",
            "content": None,
            "metrics": metrics,
            "items": [
                {
                    "summary": _humanize_daily_text(line),
                    "badges": [],
                    "meta": [],
                }
                for line in projection.get("plain_summary", [])
            ],
            "table": {
                "columns": [
                    {"key": "dimension", "label": "维度"},
                    {"key": "conclusion", "label": "结论"},
                ],
                "rows": [
                    {
                        "dimension": metric.get("label"),
                        "conclusion": metric.get("value"),
                    }
                    for metric in metrics
                ],
            }
            if metrics
            else None,
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
                "title": str(
                    _humanize_daily_title(
                        section.get("title") or f"日报章节 {index}"
                    )
                ),
                "kind": "list",
                "status": "complete",
                "summary": None,
                "content": None,
                "metrics": [],
                "items": [
                    _humanize_daily_item(item)
                    for item in section.get("items", [])
                    if isinstance(item, dict)
                ],
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


def render_daily_review_answer(
    *,
    date_text: str | None,
    modules: list[dict[str, Any]],
    warnings: list[str],
) -> str:
    metrics: dict[str, str] = {}
    directions: list[tuple[str, str]] = []
    data_notes: list[str] = []
    stage = ""
    for module in modules:
        for metric in module.get("metrics", []):
            if not isinstance(metric, dict):
                continue
            label = metric.get("label")
            value = metric.get("value")
            if isinstance(label, str) and isinstance(value, str):
                metrics[label] = value
        title = module.get("title")
        for item in module.get("items", []):
            if not isinstance(item, dict):
                continue
            item_title = item.get("title")
            summary = item.get("summary")
            if not isinstance(summary, str) or not summary.strip():
                continue
            if title == "主要方向" and isinstance(item_title, str):
                directions.append((item_title, summary))
            if item_title == "数据说明":
                data_notes.append(summary)
            if not stage and "市场处于" in summary:
                stage = summary
            if not stage:
                stage_match = re.search(r"市场阶段为\s*(.+?阶段)", summary)
                if stage_match:
                    stage = f"市场仍处于{stage_match.group(1)}"

    index_text = metrics.get("指数表现", "")
    amount_text = metrics.get("成交情况", "")
    mood_text = metrics.get("赚钱效应", "")
    concentration_text = metrics.get("资金集中度", "")
    heat_text = metrics.get("短线热度", "")

    index_change = re.search(r"涨跌幅\s*([+-]?[\d.]+)%", index_text)
    advancers = re.search(r"上涨\s*(\d+)\s*只", mood_text)
    amount_change = re.search(r"较昨日(增加|减少)([\d.]+)%", amount_text)
    index_pct = float(index_change.group(1)) if index_change else None
    advancer_count = int(advancers.group(1)) if advancers else None
    volume_expanded = amount_change is not None and amount_change.group(1) == "增加"

    if index_pct is not None and index_pct < 0 and (advancer_count or 0) >= 3000:
        core = "指数下跌、但多数个股上涨"
    elif index_pct is not None and index_pct >= 0 and (advancer_count or 0) >= 3000:
        core = "指数和多数个股同步走强"
    elif index_pct is not None and index_pct < 0:
        core = "指数和个股整体承压"
    else:
        core = "指数与个股表现分化"
    if volume_expanded:
        core += "，成交明显放大"

    display_date = date_text or "最新交易日"
    date_match = re.fullmatch(r"\d{4}-(\d{2})-(\d{2})", display_date)
    if date_match:
        display_date = f"{int(date_match.group(1))}月{int(date_match.group(2))}日"

    lines = [
        f"## {display_date}复盘",
        "",
        f"**一句话结论：** 这是一个{core}的交易日。"
        + (f"{stage}。" if stage else "")
        + "短线机会不少，但持续性仍要看下一交易日的成交和扩散情况。",
        "",
        "### 市场发生了什么",
    ]
    for text in (index_text, mood_text, amount_text, concentration_text, heat_text):
        if text:
            lines.append(f"- {text}。")

    if directions:
        lines.extend(["", "### 资金主要去了哪里"])
        for title, summary in directions[:4]:
            prefix = f"{title}："
            if summary.startswith(prefix):
                summary = summary.removeprefix(prefix)
            lines.append(f"- **{title}：** {summary}。")

    lines.extend(["", "### 下一交易日重点看"])
    average = re.search(r"近5日平均\s*([\d.]+)\s*只", mood_text)
    ratio = re.search(r"近20日平均的\s*([\d.]+)%", amount_text)
    if average:
        lines.append(
            f"- 上涨家数能否继续高于近5日平均的 {float(average.group(1)):.0f} 只；"
            "若快速回落，说明普涨持续性不足。"
        )
    else:
        lines.append("- 上涨家数能否继续扩散，而不是只剩少数高位股票活跃。")
    if ratio:
        lines.append(
            f"- 成交额能否维持在近20日平均附近；本日为其 {float(ratio.group(1)):.2f}%。"
        )
    else:
        lines.append("- 成交额能否继续支撑当前的市场热度。")
    lines.append("- 热门方向能否从涨停扩散到成交和创新高，而不是只有前排股票表现。")

    notes = [*data_notes, *warnings]
    if stage or notes:
        lines.extend(["", "### 风险与数据说明"])
        if stage:
            lines.append("- 市场仍处于横盘阶段；短线热度较高后，次日容易出现分化。")
        lines.extend(
            f"- {note.rstrip('。.!')}。" for note in dict.fromkeys(notes)
        )

    return "\n".join(lines).rstrip() + "\n"


def daily_agent_projection_modules(
    projection: dict[str, Any],
) -> list[dict[str, Any]]:
    provenance = projection.get("provenance", {})
    warnings = list(provenance.get("warnings", []))
    date_text = projection.get("date")
    source = provenance.get("canonical_path")
    modules: list[dict[str, Any]] = [
        {
            "module_id": "daily_agent_overview",
            "title": str(projection.get("title") or "日常研究雷达"),
            "kind": "summary",
            "status": "degraded" if warnings else "complete",
            "summary": "基于 canonical Daily Agent JSON 的确定性投影。",
            "content": None,
            "metrics": list(projection.get("metrics", [])),
            "items": [
                {"summary": line, "badges": [], "meta": []}
                for line in projection.get("plain_summary", [])
            ],
            "table": None,
            "warnings": warnings,
            "provenance": {
                "source": source,
                "as_of": date_text,
                "generated_by": "deterministic_projection",
            },
        }
    ]
    section_kinds = {
        "今天要做什么": "actions",
        "证据边界": "evidence",
    }
    for index, section in enumerate(projection.get("sections", []), start=1):
        title = str(section.get("title") or f"研究章节 {index}")
        modules.append(
            {
                "module_id": f"daily_agent_section_{index}",
                "title": title,
                "kind": section_kinds.get(title, "list"),
                "status": "complete",
                "summary": None,
                "content": None,
                "metrics": [],
                "items": list(section.get("items", [])),
                "table": None,
                "warnings": [],
                "provenance": {
                    "source": source,
                    "as_of": date_text,
                    "generated_by": "deterministic_projection",
                },
            }
        )
    return modules


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
