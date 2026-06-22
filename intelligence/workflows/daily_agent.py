from __future__ import annotations

import json
from html import escape
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
from intelligence.services import kb_rag
from intelligence.summary import WorkflowStep, WorkflowSummary, now_iso
from scripts.build_daily_ops_ledger import build_ledger


GAP_LABELS = {
    "missing_source_trace": "缺来源回溯",
    "missing_concept": "缺概念/待归一",
    "missing_entity_exposure": "缺公司暴露",
    "missing_evidence": "缺证据",
    "missing_market_signal": "缺盘面信号",
}

MODE_LABELS = {
    "hybrid": "混合检索",
    "dense": "向量检索",
    "bm25": "关键词检索",
}

CLASS_LABELS = {
    LABEL_OLD_WAKEUP: "旧逻辑唤醒",
    LABEL_NEW_CANDIDATE: "新逻辑候选",
    LABEL_DATA_GAP: "数据缺口",
    LABEL_NOISE: "暂不处理/待确认",
}


@dataclass(frozen=True)
class DailyAgentOptions:
    date: str
    finance_root: str | Path | None = None
    kb_wiki: str | Path | None = None
    recent: int = 1
    top_per_date: int = 10
    top_companies: int = 8
    max_evidence: int = 5
    semantic_rag_top_n: int = 3
    wiki_rag_k: int = 3
    wiki_rag_mode: str = "hybrid"
    wiki_rag_timeout: int = 120


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
        return "题材地图 / 深度研究"
    if classification == LABEL_OLD_WAKEUP and gaps:
        return "先保留，等统一补来源回溯/证据后再深度研究"
    if classification == LABEL_NEW_CANDIDATE:
        return "题材快报 / 题材地图，先建边界"
    if classification == LABEL_DATA_GAP:
        return "进入统一回补队列，先判断是不是污染词或别名"
    if classification == LABEL_NOISE:
        return "暂不处理，等待新盘面或证据"
    return "人工复核"


def _format_gaps(gaps: list[str]) -> str:
    if not gaps:
        return "-"
    return ", ".join(GAP_LABELS.get(gap, gap) for gap in gaps)


def _compact_result(row: dict[str, Any]) -> dict[str, Any]:
    stocks = []
    for stock in row.get("strong_stocks", [])[:5]:
        if isinstance(stock, dict):
            stocks.append(stock.get("stock_name") or stock.get("stock_ts_code") or "")
    concept_matches = row.get("concept_matches") or []
    entity_exposures = row.get("entity_exposures") or []
    evidence_items = row.get("evidence_items") or []
    source_traces = row.get("source_traces") or []
    return {
        "date": row.get("date"),
        "query": row.get("query"),
        "classification": row.get("classification"),
        "confidence": row.get("confidence"),
        "priority_score": row.get("priority_score"),
        "matched_theme": row.get("matched_theme"),
        "trigger_types": row.get("trigger_types") or [],
        "strong_stocks": [item for item in stocks if item],
        "structured_counts": {
            "concept": len(concept_matches),
            "company_exposure": len(entity_exposures),
            "evidence": len(evidence_items),
            "source_trace": len(source_traces),
            "missing_source_trace": sum(1 for item in source_traces if not item.get("source_exists")),
        },
        "source_traces": source_traces[:5],
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


def _semantic_query(row: dict[str, Any]) -> str:
    parts = [str(row.get("query") or ""), str(row.get("matched_theme") or "")]
    parts.extend(str(item) for item in (row.get("strong_stocks") or [])[:3])
    return " ".join(part for part in parts if part).strip()


def _semantic_hit_dict(hit: kb_rag.WikiHit) -> dict[str, Any]:
    return {
        "title": hit.title,
        "file_path": hit.file_path,
        "score": hit.score,
        "excerpt": hit.excerpt,
        "via_neighbor": hit.via_neighbor,
    }


def _material_type(file_path: str, title: str = "") -> str:
    text = f"{file_path} {title}".lower()
    if file_path.startswith("raw/") or "/raw/" in file_path:
        return "原始材料"
    if "briefing" in text or "briefings" in text or "晨汇" in title or "卖方" in title:
        return "晨汇/简报"
    if file_path.startswith("wiki/synthesis/"):
        return "综合研究页"
    if file_path.startswith("wiki/sources/"):
        if "逻辑" in title:
            return "公司逻辑卡"
        if "deepdive" in text or "deep_dive" in text or "deep-dive" in text:
            return "旧深度研究"
        return "证据源页"
    if file_path.startswith("wiki/concepts/"):
        return "概念页"
    if file_path.startswith("wiki/entities/"):
        return "公司页"
    return "其他材料"


def _evidence_role(material_type: str, title: str) -> str:
    text = title.lower()
    if material_type in {"旧深度研究", "综合研究页"}:
        return "旧逻辑主线"
    if material_type == "原始材料":
        return "原文依据"
    if material_type == "公司逻辑卡":
        return "相关公司证据"
    if material_type == "公司页":
        return "公司暴露证据"
    if material_type == "概念页":
        return "标准概念/别名证据"
    if material_type == "晨汇/简报":
        return "当时市场叙事记录"
    if "deepdive" in text or "研究" in title:
        return "旧逻辑主线"
    return "辅助证据"


def _trace_status(file_path: str, material_type: str, gaps: list[str]) -> str:
    if material_type == "原始材料":
        base = "已命中原始材料"
    elif material_type in {"证据源页", "旧深度研究", "公司逻辑卡"}:
        base = "已命中来源页，原始材料/来源清单待抽查"
    elif material_type in {"综合研究页", "晨汇/简报"}:
        base = "已命中整理页，需保留来源链"
    elif material_type in {"概念页", "公司页"}:
        base = "已命中知识页，不等于原始出处"
    else:
        base = "命中材料，回溯状态待确认"
    if "missing_source_trace" in gaps:
        return f"{base}；结构化层提示来源回溯有缺口"
    if "missing_evidence" in gaps:
        return f"{base}；结构化层提示证据有缺口"
    return base


def _structured_status(row: dict[str, Any]) -> dict[str, Any]:
    counts = row.get("structured_counts") or {}
    gaps = set(row.get("data_gaps") or [])
    return {
        "概念": "已命中" if counts.get("concept", 0) > 0 and "missing_concept" not in gaps else "缺概念/待归一",
        "公司暴露": "已命中" if counts.get("company_exposure", 0) > 0 and "missing_entity_exposure" not in gaps else "缺公司暴露",
        "证据": "已命中" if counts.get("evidence", 0) > 0 and "missing_evidence" not in gaps else "缺证据",
        "来源回溯": "有缺口" if "missing_source_trace" in gaps or counts.get("missing_source_trace", 0) else "未发现缺口",
    }


def _semantic_overall_status(row: dict[str, Any]) -> tuple[str, str]:
    hits = row.get("semantic_hits") or []
    gaps = set(row.get("data_gaps") or [])
    classification = row.get("classification")
    structured_ok = classification == LABEL_OLD_WAKEUP and not {"missing_concept", "missing_entity_exposure", "missing_evidence"} & gaps
    if hits and structured_ok and not gaps:
        return "结构化和向量互相支持", "图谱/证据有命中，向量也找到了旧材料，可作为旧逻辑唤醒优先项。"
    if hits and structured_ok and gaps:
        return "旧逻辑成立但回溯有缺口", "结构化层和向量层都支持旧逻辑，但仍有来源/证据等缺口要补。"
    if hits and "missing_concept" in gaps:
        return "向量搜到旧材料但概念未归一", "向量层提示可能有旧逻辑，结构化层还没把概念正式登记。"
    if hits:
        return "向量有材料，结构化待补", "先把命中材料用于归一、补证据或补公司暴露。"
    if row.get("semantic_rag_status") == "unavailable":
        return "向量层暂不可用", "只保留结构化判断，等 RAG 索引或依赖恢复后再复核。"
    return "未补语义证据", "本条未进入语义召回额度，或没有命中旧材料。"


def _evidence_card_next_action(row: dict[str, Any], status: str) -> str:
    gaps = set(row.get("data_gaps") or [])
    if "missing_source_trace" in gaps:
        return "先补来源页/原始材料回溯，再进入深度研究。"
    if "missing_concept" in gaps:
        return "先判断是不是别名/污染词，再做概念归一。"
    if "missing_entity_exposure" in gaps:
        return "先补公司暴露，确认哪些强势股是真相关。"
    if "missing_evidence" in gaps:
        return "先补公告/研报/订单等证据，不要只看盘面。"
    if status == "结构化和向量互相支持":
        return "可以进入题材地图/深度研究，并抽查最相关命中材料。"
    if row.get("classification") == LABEL_NEW_CANDIDATE:
        return "先建题材地图，确认边界后再深度研究。"
    return row.get("route") or "人工复核。"


def _build_evidence_card(row: dict[str, Any]) -> dict[str, Any]:
    hits = row.get("semantic_hits") or []
    evidence_items = []
    for hit in hits:
        material_type = _material_type(str(hit.get("file_path") or ""), str(hit.get("title") or ""))
        evidence_items.append(
            {
                "材料": str(hit.get("title") or ""),
                "类型": material_type,
                "作用": _evidence_role(material_type, str(hit.get("title") or "")),
                "路径": str(hit.get("file_path") or ""),
                "相关度": round(float(hit.get("score") or 0.0), 4),
                "摘录": str(hit.get("excerpt") or ""),
                "回溯状态": _trace_status(str(hit.get("file_path") or ""), material_type, row.get("data_gaps") or []),
            }
        )
    status, reason = _semantic_overall_status(row)
    return {
        "标题": f"旧逻辑证据卡：{row.get('query') or '-'}",
        "当前判断": CLASS_LABELS.get(row.get("classification"), row.get("classification") or "-"),
        "结构化检查": _structured_status(row),
        "向量旧材料": {
            "状态": "有命中" if hits else row.get("semantic_rag_status") or "未补",
            "检索词": row.get("semantic_rag_query") or "-",
            "命中数量": len(hits),
        },
        "命中材料": evidence_items,
        "综合判断": status,
        "判断理由": reason,
        "缺口": row.get("data_gaps") or [],
        "下一步": _evidence_card_next_action(row, status),
    }


def _enrich_decision_with_semantic_rag(
    decision: dict[str, list[dict[str, Any]]],
    options: DailyAgentOptions,
    kb_wiki: Path,
) -> list[str]:
    warnings: list[str] = []
    remaining = max(0, int(options.semantic_rag_top_n or 0))

    for bucket in ("old_logic_wakeup", "new_logic_candidate", "data_gap"):
        for row in decision.get(bucket, []):
            if remaining <= 0:
                continue
            query = _semantic_query(row)
            if not query:
                row["semantic_rag_status"] = "skipped"
                row["semantic_evidence_card"] = _build_evidence_card(row)
                continue
            wr = kb_rag.retrieve(
                query,
                kb_wiki,
                k=options.wiki_rag_k,
                mode=options.wiki_rag_mode,
                timeout=options.wiki_rag_timeout,
            )
            row["semantic_rag_query"] = query
            row["semantic_rag_mode"] = options.wiki_rag_mode
            if wr.ok:
                row["semantic_rag_status"] = "hit"
                row["semantic_hits"] = [_semantic_hit_dict(hit) for hit in wr.hits]
            else:
                row["semantic_rag_status"] = "unavailable"
                row["semantic_hits"] = []
                if wr.warning:
                    warnings.append(f"{query}: {wr.warning}")
            row["semantic_evidence_card"] = _build_evidence_card(row)
            remaining -= 1
    for rows in decision.values():
        for row in rows:
            row.setdefault("semantic_evidence_card", _build_evidence_card(row))
    return warnings


def _agent_next_actions(report: dict[str, Any]) -> list[str]:
    actions: list[str] = []
    decision = report["decision"]
    if decision["old_logic_wakeup"]:
        actions.append("优先打开旧逻辑唤醒：确认是否需要题材地图或深度研究。")
    semantic_hits = sum(1 for rows in decision.values() for row in rows if row.get("semantic_hits"))
    if semantic_hits:
        actions.append("语义召回已给出 W 命中；优先复核结构化命中和 W 命中同时存在的条目。")
    if decision["new_logic_candidate"]:
        actions.append("新逻辑先用题材快报/题材地图定义边界，不急着深度研究。")
    if decision["data_gap"]:
        actions.append("数据缺口只登记到回补队列；本轮不自动补来源/概念/IMA。")
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
    decision = _build_decision(batch)
    semantic_warnings = _enrich_decision_with_semantic_rag(decision, options, paths.knowledge_wiki)
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
        "decision": decision,
        "semantic_rag": {
            "enabled": options.semantic_rag_top_n > 0,
            "top_n": options.semantic_rag_top_n,
            "k": options.wiki_rag_k,
            "mode": options.wiki_rag_mode,
            "warnings": semantic_warnings,
        },
        "notes": [
            "agent-daily 是只读入口：读取 daily workflow、知识库和 logic-match 产物，不自动回补。",
            "回补类事项只进入数据缺口队列，等待用户统一处理，不自动补来源/概念/IMA。",
        ],
    }
    report["next_actions"] = _agent_next_actions(report)
    return report


def _section_rows(rows: list[dict[str, Any]], limit: int = 10) -> list[str]:
    if not rows:
        return ["- 无"]
    lines = []
    for item in rows[:limit]:
        gaps = _format_gaps(item["data_gaps"])
        stocks = ", ".join(item["strong_stocks"]) or "-"
        semantic_hits = item.get("semantic_hits") or []
        if semantic_hits:
            semantic = "；".join(hit.get("title", "") for hit in semantic_hits[:2] if hit.get("title")) or "hit"
        elif item.get("semantic_rag_status") == "unavailable":
            semantic = "不可用"
        else:
            semantic = "-"
        lines.append(
            f"- {item['query']}｜priority={item['priority_score'] if item['priority_score'] is not None else '-'}"
            f"｜confidence={item['confidence']}｜强势股={stocks}｜缺口={gaps}｜语义={semantic}｜路径={item['route']}"
        )
    return lines


def _evidence_card_rows(decision: dict[str, list[dict[str, Any]]], limit: int = 8) -> list[str]:
    cards: list[dict[str, Any]] = []
    for bucket in ("old_logic_wakeup", "new_logic_candidate", "data_gap"):
        cards.extend(row.get("semantic_evidence_card") for row in decision.get(bucket, []) if row.get("semantic_evidence_card"))
    if not cards:
        return ["- 无"]

    lines: list[str] = []
    for card in cards[:limit]:
        structured = card.get("结构化检查") or {}
        semantic = card.get("向量旧材料") or {}
        lines.append(f"### {card.get('标题')}")
        lines.append("")
        lines.append(f"- 判断：{card.get('综合判断')}。{card.get('判断理由')}")
        lines.append(
            "- 结构化："
            f"概念={structured.get('概念', '-')}；"
            f"公司暴露={structured.get('公司暴露', '-')}；"
            f"证据={structured.get('证据', '-')}；"
            f"来源回溯={structured.get('来源回溯', '-')}"
        )
        lines.append(
            f"- 向量旧材料：{semantic.get('状态', '-')}｜命中 {semantic.get('命中数量', 0)}｜检索词：{semantic.get('检索词', '-')}"
        )
        materials = card.get("命中材料") or []
        if materials:
            for item in materials[:3]:
                lines.append(
                    f"- 命中：{item.get('类型')}｜{item.get('作用')}｜{item.get('材料')}｜"
                    f"回溯：{item.get('回溯状态')}"
                )
        else:
            lines.append("- 命中：无")
        gaps = _format_gaps(card.get("缺口") or [])
        lines.append(f"- 缺口：{gaps}")
        lines.append(f"- 下一步：{card.get('下一步')}")
        lines.append("")
    return lines


def render_daily_agent(report: dict[str, Any]) -> str:
    decision = report["decision"]
    ledger = report["ledger"]
    batch = report["logic_batch"]
    lines = [
        f"# 每日 Agent 简报 - {report['date']}",
        "",
        "## 今日判断",
        "",
        f"- 日常产物状态：`{ledger['status']}`",
        f"- 扫描逻辑数：{batch['scanned_count']}",
        f"- 旧逻辑唤醒：{len(decision['old_logic_wakeup'])}",
        f"- 新逻辑候选：{len(decision['new_logic_candidate'])}",
        f"- 数据缺口：{len(decision['data_gap'])}",
        f"- 暂不处理/待确认：{len(decision['noise_or_unconfirmed'])}",
        f"- 向量旧材料：{MODE_LABELS.get(report['semantic_rag']['mode'], report['semantic_rag']['mode'])}，补前 {report['semantic_rag']['top_n']} 条",
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
        "## 回补队列",
        "",
    ]
    gap_queue = batch.get("gap_queue") or []
    if gap_queue:
        for item in gap_queue[:20]:
            lines.append(
                f"- {item['query']}｜{CLASS_LABELS.get(item['classification'], item['classification'])}｜priority={item['priority']}｜缺口={_format_gaps(item['data_gaps'])}"
            )
    else:
        lines.append("- 无")
    lines.extend(["", "## 旧逻辑证据卡", "", *_evidence_card_rows(decision)])
    if report["semantic_rag"]["warnings"]:
        lines.extend(["", "## 向量旧材料告警", ""])
        for warning in report["semantic_rag"]["warnings"][:10]:
            lines.append(f"- {warning}")
    lines.extend(["", "## 下一步", ""])
    for action in report["next_actions"]:
        lines.append(f"- {action}")
    lines.extend(["", "## 说明", ""])
    for note in report["notes"]:
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


def render_daily_agent_html(report: dict[str, Any], markdown: str) -> str:
    title = f"每日 Agent 简报 - {report['date']}"
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title>
<style>
:root{{--paper:#fffaf1;--ink:#17140f;--muted:#746b5d;--line:#d8cbbb;--accent:#0057ff;--card:#fffdf8}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--paper);color:var(--ink);font-family:'Avenir Next','PingFang SC','Hiragino Sans GB',sans-serif;line-height:1.65}}
main{{max-width:1180px;margin:0 auto;padding:24px}}
.hero{{border:1px solid var(--ink);background:var(--card);padding:20px 24px;margin-bottom:18px}}
.kicker{{font-size:12px;letter-spacing:.22em;color:var(--accent);font-weight:900;text-transform:uppercase}}
h1{{margin:6px 0 0;font-size:34px;line-height:1.1}}
pre{{white-space:pre-wrap;word-break:break-word;border:1px solid var(--line);background:#fffdf8;padding:18px 20px;margin:0;font:14px/1.7 'SFMono-Regular','Menlo','PingFang SC',monospace}}
</style>
</head>
<body>
<main>
  <section class="hero"><div class="kicker">Agent Daily Brief</div><h1>{escape(title)}</h1></section>
  <pre>{escape(markdown)}</pre>
</main>
</body>
</html>
"""


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
            "semantic_rag_top_n": options.semantic_rag_top_n,
            "wiki_rag_mode": options.wiki_rag_mode,
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
        f"semantic_rag_hits={sum(1 for rows in report['decision'].values() for row in rows if row.get('semantic_hits'))}",
    ]
    summary.warnings = list(batch.get("warnings") or []) + list(report["semantic_rag"]["warnings"])
    summary.next_actions = list(report["next_actions"])
    if any(step.status == "FAIL" for step in summary.steps):
        summary.finish("FAIL")
    elif any(step.status == "WARN" for step in summary.steps):
        summary.finish("WARN")
    else:
        summary.finish("PASS")
    return summary, report, render_daily_agent(report)


def write_daily_agent_outputs(
    report: dict[str, Any],
    markdown: str,
    out_json: str | Path,
    out_md: str | Path,
    out_html: str | Path | None = None,
) -> None:
    json_path = Path(out_json).expanduser()
    md_path = Path(out_md).expanduser()
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")
    if out_html:
        html_path = Path(out_html).expanduser()
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(render_daily_agent_html(report, markdown), encoding="utf-8")
