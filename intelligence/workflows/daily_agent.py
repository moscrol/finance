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
from intelligence.services import logic_lifecycle
from intelligence.services import logic_effectiveness
from intelligence.services import market_validation
from intelligence.services import research_queue
from intelligence.services import research_judge
from intelligence.summary import WorkflowStep, WorkflowSummary, now_iso
from scripts.build_daily_ops_ledger import build_ledger


GAP_LABELS = {
    "placeholder_market_theme": "盘面占位/题材未映射",
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
    effectiveness_window: int = 20


def _paths_from_options(options: DailyAgentOptions) -> ProjectPaths:
    defaults = default_paths()
    return ProjectPaths(
        finance_root=Path(options.finance_root).expanduser() if options.finance_root else defaults.finance_root,
        knowledge_wiki=Path(options.kb_wiki).expanduser() if options.kb_wiki else defaults.knowledge_wiki,
        finance_site=defaults.finance_site,
        market_snapshot_dir=defaults.market_snapshot_dir,
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
        if "placeholder_market_theme" in gaps:
            return "先看连板股名单和主导行业，等题材名明确后再映射"
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
    if "placeholder_market_theme" in gaps:
        return "这是盘面占位信号，不做 concept deep-dive；先人工看连板股名单和行业归因。"
    if "missing_source_trace" in gaps:
        return "先补来源页/原始材料回溯，再进入深度研究。"
    if "missing_concept" in gaps:
        return "先判断是不是别名/污染词，再做概念归一。"
    if "missing_entity_exposure" in gaps:
        return "先补公司暴露，确认哪些强势股是真相关。"
    if "missing_evidence" in gaps:
        return "先补公告/研报/订单等证据，不要只看盘面。"
    judgment = row.get("research_judgment") or {}
    if judgment.get("建议动作"):
        return str(judgment["建议动作"])
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
    if row.get("classification") == LABEL_OLD_WAKEUP:
        title_prefix = "旧逻辑证据卡"
    elif row.get("classification") == LABEL_NEW_CANDIDATE:
        title_prefix = "新逻辑候选证据卡"
    elif "placeholder_market_theme" in set(row.get("data_gaps") or []):
        title_prefix = "盘面占位信号"
    else:
        title_prefix = "数据缺口证据卡"
    return {
        "标题": f"{title_prefix}：{row.get('query') or '-'}",
        "当前判断": CLASS_LABELS.get(row.get("classification"), row.get("classification") or "-"),
        "结构化检查": _structured_status(row),
        "向量旧材料": {
            "状态": "有命中" if hits else row.get("semantic_rag_status") or "未补",
            "检索词": row.get("semantic_rag_query") or "-",
            "命中数量": len(hits),
        },
        "命中材料": evidence_items,
        "证据裁判": row.get("research_judgment") or {},
        "生命周期": row.get("logic_lifecycle") or {},
        "盘面验证": row.get("market_validation") or {},
        "历史有效性": row.get("logic_effectiveness") or {},
        "综合判断": status,
        "判断理由": reason,
        "缺口": row.get("data_gaps") or [],
        "下一步": _evidence_card_next_action(row, status),
    }


def _enrich_decision_with_research_judgment(
    decision: dict[str, list[dict[str, Any]]],
    kb_wiki: Path,
    max_evidence: int,
) -> list[str]:
    warnings: list[str] = []
    for bucket in ("old_logic_wakeup", "new_logic_candidate", "data_gap"):
        for row in decision.get(bucket, []):
            if "placeholder_market_theme" in set(row.get("data_gaps") or []):
                continue
            try:
                row["research_judgment"] = research_judge.judge_row(row, kb_wiki=kb_wiki, max_evidence=max_evidence)
            except Exception as exc:
                row["research_judgment"] = {
                    "目标": row.get("query") or "-",
                    "证据状态": "裁判不可用",
                    "已有证据层": [],
                    "缺失证据层": [],
                    "已有证据": [],
                    "建议动作": row.get("route") or "人工复核。",
                    "不可升级原因": [str(exc)],
                }
                warnings.append(f"{row.get('query') or '-'}: {exc}")
    return warnings


def _enrich_decision_with_lifecycle(
    decision: dict[str, list[dict[str, Any]]],
    history_by_theme: dict[str, list[dict[str, Any]]],
) -> None:
    logic_lifecycle.build_lifecycle_for_decision(decision, history_by_theme)
    for rows in decision.values():
        for row in rows:
            if row.get("logic_lifecycle"):
                row["生命周期"] = row["logic_lifecycle"]


def _enrich_decision_with_market_validation(
    decision: dict[str, list[dict[str, Any]]],
    current_by_theme: dict[str, dict[str, Any]],
    history_by_theme: dict[str, list[dict[str, Any]]],
) -> None:
    market_validation.build_market_validation_for_decision(decision, current_by_theme, history_by_theme)


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
            if "placeholder_market_theme" not in set(row.get("data_gaps") or []):
                row.setdefault("semantic_evidence_card", _build_evidence_card(row))
    return warnings


def _agent_next_actions(report: dict[str, Any]) -> list[str]:
    actions: list[str] = []
    decision = report["decision"]
    task_summary = (report.get("research_queue") or {}).get("summary") or {}
    if task_summary.get("total"):
        parts = []
        if task_summary.get("today_do_ima"):
            parts.append(f"做 IMA {task_summary['today_do_ima']} 条")
        if task_summary.get("today_find_official_evidence"):
            parts.append(f"找公告/调研/订单 {task_summary['today_find_official_evidence']} 条")
        if task_summary.get("today_wait_market_validation"):
            parts.append(f"等盘面验证 {task_summary['today_wait_market_validation']} 条")
        if task_summary.get("today_downgrade_or_watch"):
            parts.append(f"降级观察 {task_summary['today_downgrade_or_watch']} 条")
        actions.append("今日研究任务队列：" + "；".join(parts) + "。")
    judgments = [
        row.get("research_judgment") or {}
        for rows in decision.values()
        for row in rows
        if row.get("research_judgment")
    ]
    priority_targets = [item.get("目标") for item in judgments if item.get("证据状态") == "重点验证"]
    baseline_targets = [item.get("目标") for item in judgments if item.get("证据状态") == "能力栈候选"]
    if priority_targets:
        actions.append(f"证据裁判提示重点验证：{', '.join(str(item) for item in priority_targets[:5])}；优先找公告/调研/订单/客户验证。")
    if baseline_targets:
        actions.append(f"年报/F10 只证明能力栈：{', '.join(str(item) for item in baseline_targets[:5])}；下一步补 L3 官方验证或等盘面验证。")
    if decision["old_logic_wakeup"]:
        actions.append("优先打开旧逻辑唤醒：确认是否需要题材地图或深度研究。")
    semantic_hits = sum(1 for rows in decision.values() for row in rows if row.get("semantic_hits"))
    if semantic_hits:
        actions.append("语义召回已给出 W 命中；优先复核结构化命中和 W 命中同时存在的条目。")
    if decision["new_logic_candidate"]:
        actions.append("新逻辑先用题材快报/题材地图定义边界，不急着深度研究。")
    if decision["data_gap"]:
        actions.append("数据缺口只登记到回补队列；本轮不自动补来源/概念/IMA。")
    if decision["noise_or_unconfirmed"]:
        actions.append("待确认项先看是不是盘面占位或噪音；不要直接当成 concept deep-dive。")
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
    judgment_warnings = _enrich_decision_with_research_judgment(decision, paths.knowledge_wiki, options.max_evidence)
    lifecycle_dates = [item for item in available_candidate_dates(paths.market_exports) if item <= options.date][-6:]
    history_by_theme = logic_lifecycle.load_theme_history(
        paths.market_exports,
        lifecycle_dates,
        options.date,
        top_per_date=options.top_per_date,
    )
    _enrich_decision_with_lifecycle(decision, history_by_theme)
    current_market_by_theme, market_history_by_theme = market_validation.load_market_validation_context(
        paths.market_exports,
        lifecycle_dates,
        options.date,
        top_per_date=options.top_per_date,
    )
    _enrich_decision_with_market_validation(decision, current_market_by_theme, market_history_by_theme)
    effectiveness_dates = [item for item in available_candidate_dates(paths.market_exports) if item <= options.date][-options.effectiveness_window:]
    effectiveness_history = logic_effectiveness.load_effectiveness_history(
        paths.market_exports,
        effectiveness_dates,
        options.date,
        top_per_date=options.top_per_date,
    )
    return_panel = logic_effectiveness.load_market_return_panel(
        paths.market_snapshot_dir,
        effectiveness_dates,
    )
    logic_effectiveness.build_effectiveness_for_decision(
        decision,
        effectiveness_history,
        return_panel=return_panel,
    )
    effectiveness_summary = logic_effectiveness.summarize_effectiveness(decision)
    semantic_warnings = _enrich_decision_with_semantic_rag(decision, options, paths.knowledge_wiki)
    task_queue = research_queue.build_research_queue(decision)
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
        "research_judge": {
            "enabled": True,
            "warnings": judgment_warnings,
        },
        "research_queue": task_queue,
        "logic_effectiveness": {
            "enabled": True,
            "window": options.effectiveness_window,
            "car_panel_dates": len(return_panel.get("trade_dates") or []),
            "summary": effectiveness_summary,
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
        judgment = item.get("research_judgment") or {}
        judgment_text = judgment.get("证据状态") or "-"
        lifecycle = item.get("logic_lifecycle") or {}
        lifecycle_text = lifecycle.get("生命周期阶段") or "-"
        market = item.get("market_validation") or {}
        market_text = market.get("盘面验证强度") or "-"
        effectiveness_text = _effectiveness_brief(item.get("logic_effectiveness") or {})
        lines.append(
            f"- {item['query']}｜priority={item['priority_score'] if item['priority_score'] is not None else '-'}"
            f"｜confidence={item['confidence']}｜强势股={stocks}｜缺口={gaps}｜语义={semantic}｜生命周期={lifecycle_text}｜盘面验证={market_text}｜历史有效性={effectiveness_text}｜裁判={judgment_text}｜路径={item['route']}"
        )
    return lines


def _effectiveness_brief(scorecard: dict[str, Any]) -> str:
    if not scorecard:
        return "-"
    if scorecard.get("状态") != "已评估":
        return scorecard.get("状态") or "-"
    parts = []
    win = scorecard.get("胜率")
    if isinstance(win, (int, float)):
        parts.append(f"胜率{win}")
    half = (scorecard.get("半衰期") or {}).get("交易日")
    parts.append(f"半衰期{half if half is not None else '未减半'}")
    dd = (scorecard.get("最大回撤") or {}).get("比例")
    if isinstance(dd, (int, float)):
        parts.append(f"回撤{dd}")
    car = scorecard.get("CAR") or {}
    if car.get("状态") == "已评估":
        car5 = car.get("CAR(0,5)")
        car20 = car.get("CAR(0,20)")
        parts.append(f"CAR5={car5 if car5 is not None else '-'}/CAR20={car20 if car20 is not None else '-'}")
    else:
        parts.append("CAR未配置")
    return "｜".join(parts)


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
        judgment = card.get("证据裁判") or {}
        if judgment:
            lines.append(
                "- 证据裁判："
                f"{judgment.get('证据状态', '-')}｜"
                f"已有：{'、'.join(judgment.get('已有证据层') or []) or '-'}｜"
                f"缺：{'、'.join(judgment.get('缺失证据层') or []) or '-'}"
            )
        lifecycle = card.get("生命周期") or {}
        if lifecycle:
            lines.append(
                "- 生命周期："
                f"{lifecycle.get('生命周期阶段', '-')}｜"
                f"{lifecycle.get('阶段变化', '-')}｜"
                f"{lifecycle.get('变化原因', '-')}"
            )
        market = card.get("盘面验证") or {}
        if market:
            lines.append(
                "- 盘面验证："
                f"{market.get('盘面验证强度', '-')}｜"
                f"{market.get('验证结论', '-')}"
            )
        effectiveness = card.get("历史有效性") or {}
        if effectiveness:
            lines.append(f"- 历史有效性：{_effectiveness_brief(effectiveness)}")
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


def _research_queue_rows(queue: dict[str, Any], limit: int = 8) -> list[str]:
    sections = [
        ("today_do_ima", "今日该做 IMA"),
        ("today_find_official_evidence", "今日该找公告/调研/订单"),
        ("today_wait_market_validation", "今日等盘面验证"),
        ("today_downgrade_or_watch", "今日降级/观察"),
    ]
    lines: list[str] = []
    for key, title in sections:
        items = list(queue.get(key) or [])
        lines.append(f"### {title}")
        lines.append("")
        if not items:
            lines.append("- 无")
            lines.append("")
            continue
        for item in items[:limit]:
            stocks = "、".join(item.get("强势股") or []) or "-"
            missing = "、".join(item.get("缺失证据层") or []) or "-"
            lines.append(
                f"- {item.get('目标', '-')}｜priority={item.get('优先级', '-')}｜"
                f"生命周期={item.get('生命周期阶段', '-')}｜裁判={item.get('证据状态', '-')}｜"
                f"缺={missing}｜强势股={stocks}｜理由={item.get('理由', '-')}"
            )
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
        "## 待确认：占位信号 / 噪音",
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
    lines.extend(["", "## 今日研究任务队列", "", *_research_queue_rows(report.get("research_queue") or {})])
    lines.extend(["", "## 逻辑证据卡", "", *_evidence_card_rows(decision)])
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


def _semantic_summary(row: dict[str, Any]) -> str:
    hits = row.get("semantic_hits") or []
    if hits:
        return "；".join(str(hit.get("title") or "") for hit in hits[:2] if hit.get("title")) or "有命中"
    status = row.get("semantic_rag_status")
    if status == "unavailable":
        return "向量暂不可用"
    if status == "skipped":
        return "未生成检索词"
    return "未补"


def _html_badge(text: Any, kind: str = "muted") -> str:
    return f'<span class="badge {escape(kind)}">{escape(str(text))}</span>'


def _html_metric(label: str, value: Any, note: str = "") -> str:
    note_html = f"<small>{escape(note)}</small>" if note else ""
    return f'<div class="metric"><span>{escape(label)}</span><strong>{escape(str(value))}</strong>{note_html}</div>'


def _row_status_kind(row: dict[str, Any]) -> str:
    gaps = set(row.get("data_gaps") or [])
    judgment = row.get("research_judgment") or {}
    if judgment.get("证据状态") in {"已有事实验证", "重点验证"}:
        return "good"
    if judgment.get("证据状态") in {"能力栈候选", "盘面触发待解释"}:
        return "watch"
    if row.get("semantic_hits") and not gaps:
        return "good"
    if row.get("semantic_hits") or row.get("classification") == LABEL_OLD_WAKEUP:
        return "watch"
    if gaps:
        return "gap"
    return "muted"


def _html_table(rows: list[dict[str, Any]], empty: str) -> str:
    if not rows:
        return f'<p class="empty">{escape(empty)}</p>'
    body = []
    for row in rows:
        stocks = "、".join(row.get("strong_stocks") or []) or "-"
        gaps = _format_gaps(row.get("data_gaps") or [])
        semantic = _semantic_summary(row)
        judgment = row.get("research_judgment") or {}
        judgment_status = judgment.get("证据状态") or "-"
        lifecycle = row.get("logic_lifecycle") or {}
        lifecycle_status = lifecycle.get("生命周期阶段") or "-"
        market = row.get("market_validation") or {}
        market_status = market.get("盘面验证强度") or "-"
        action = row.get("route") or "-"
        body.append(
            "<tr>"
            f"<td><strong>{escape(str(row.get('query') or '-'))}</strong></td>"
            f"<td>{escape(str(row.get('priority_score') if row.get('priority_score') is not None else '-'))}</td>"
            f"<td>{_html_badge(row.get('confidence') if row.get('confidence') is not None else '-', _row_status_kind(row))}</td>"
            f"<td>{escape(stocks)}</td>"
            f"<td>{escape(gaps)}</td>"
            f"<td>{escape(semantic)}</td>"
            f"<td>{_html_badge(lifecycle_status, _row_status_kind(row))}</td>"
            f"<td>{_html_badge(market_status, _row_status_kind(row))}</td>"
            f"<td>{_html_badge(judgment_status, _row_status_kind(row))}</td>"
            f"<td>{escape(action)}</td>"
            "</tr>"
        )
    return (
        '<div class="table-wrap"><table><thead><tr>'
        "<th>题材</th><th>优先级</th><th>可信度</th><th>强势股</th><th>缺口</th><th>旧材料</th><th>生命周期</th><th>盘面验证</th><th>证据裁判</th><th>建议动作</th>"
        "</tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table></div>"
    )


def _html_gap_queue(report: dict[str, Any]) -> str:
    gap_queue = report["logic_batch"].get("gap_queue") or []
    if not gap_queue:
        return '<p class="empty">暂无需要统一回补的项目。</p>'
    items = []
    for item in gap_queue[:12]:
        label = CLASS_LABELS.get(item.get("classification"), item.get("classification") or "-")
        items.append(
            '<li>'
            f'<span class="topic">{escape(str(item.get("query") or "-"))}</span>'
            f'{_html_badge(label, "gap" if item.get("classification") == LABEL_DATA_GAP else "watch")}'
            f'<span class="score">优先级 {escape(str(item.get("priority") or "-"))}</span>'
            f'<span class="muted-text">{escape(_format_gaps(item.get("data_gaps") or []))}</span>'
            '</li>'
        )
    return '<ul class="queue">' + "".join(items) + "</ul>"


def _html_evidence_cards(decision: dict[str, list[dict[str, Any]]]) -> str:
    rows: list[dict[str, Any]] = []
    for bucket in ("old_logic_wakeup", "new_logic_candidate", "data_gap"):
        rows.extend(row for row in decision.get(bucket, []) if row.get("semantic_evidence_card"))
    if not rows:
        return '<p class="empty">暂无证据卡。</p>'

    cards = []
    for row in rows[:8]:
        card = row["semantic_evidence_card"]
        structured = card.get("结构化检查") or {}
        semantic = card.get("向量旧材料") or {}
        judgment = card.get("证据裁判") or {}
        lifecycle = card.get("生命周期") or {}
        market = card.get("盘面验证") or {}
        gaps = _format_gaps(card.get("缺口") or [])
        materials = card.get("命中材料") or []
        mat_html = []
        for item in materials[:3]:
            excerpt = str(item.get("摘录") or "").strip()
            excerpt_html = f'<p class="excerpt">{escape(excerpt[:180])}</p>' if excerpt else ""
            mat_html.append(
                '<div class="material">'
                f'<div>{_html_badge(item.get("类型") or "-", "info")} <strong>{escape(str(item.get("材料") or "-"))}</strong></div>'
                f'<p>{escape(str(item.get("作用") or "-"))}｜{escape(str(item.get("回溯状态") or "-"))}</p>'
                f'{excerpt_html}'
                '</div>'
            )
        if not mat_html:
            mat_html.append('<p class="empty small">未补向量旧材料。本条可先看结构化结论。</p>')
        card_html = (
            '<article class="evidence-card">'
            f'<header><h3>{escape(str(card.get("标题") or "-"))}</h3>{_html_badge(card.get("综合判断") or "-", _row_status_kind(row))}</header>'
            f'<p class="reason">{escape(str(card.get("判断理由") or "-"))}</p>'
            '<div class="checks">'
            f'{_html_badge("概念：" + str(structured.get("概念", "-")), "good" if structured.get("概念") == "已命中" else "gap")}'
            f'{_html_badge("公司：" + str(structured.get("公司暴露", "-")), "good" if structured.get("公司暴露") == "已命中" else "gap")}'
            f'{_html_badge("证据：" + str(structured.get("证据", "-")), "good" if structured.get("证据") == "已命中" else "gap")}'
            f'{_html_badge("回溯：" + str(structured.get("来源回溯", "-")), "gap" if structured.get("来源回溯") == "有缺口" else "good")}'
            '</div>'
            f'<div class="semantic-line">向量旧材料：<strong>{escape(str(semantic.get("状态", "-")))}</strong>，命中 {escape(str(semantic.get("命中数量", 0)))} 条</div>'
            f'<div class="semantic-line">生命周期：<strong>{escape(str(lifecycle.get("生命周期阶段", "-")))}</strong>｜{escape(str(lifecycle.get("阶段变化", "-")))}｜{escape(str(lifecycle.get("变化原因", "-")))}</div>'
            f'<div class="semantic-line">盘面验证：<strong>{escape(str(market.get("盘面验证强度", "-")))}</strong>｜{escape(str(market.get("验证结论", "-")))}</div>'
            f'<div class="semantic-line">证据裁判：<strong>{escape(str(judgment.get("证据状态", "-")))}</strong>｜已有：{escape("、".join(judgment.get("已有证据层") or []) or "-")}｜缺：{escape("、".join(judgment.get("缺失证据层") or []) or "-")}</div>'
            + "".join(mat_html)
            + f'<div class="next"><span>缺口：{escape(gaps)}</span><strong>{escape(str(card.get("下一步") or "-"))}</strong></div>'
            '</article>'
        )
        cards.append(card_html)
    return '<div class="evidence-grid">' + "".join(cards) + "</div>"


def _html_research_queue(queue: dict[str, Any]) -> str:
    sections = [
        ("today_do_ima", "今日该做 IMA", "info"),
        ("today_find_official_evidence", "今日该找公告/调研/订单", "watch"),
        ("today_wait_market_validation", "今日等盘面验证", "good"),
        ("today_downgrade_or_watch", "今日降级/观察", "gap"),
    ]
    columns = []
    for key, title, kind in sections:
        items = list(queue.get(key) or [])
        body = []
        if not items:
            body.append('<p class="empty small">暂无</p>')
        for item in items[:6]:
            stocks = "、".join(item.get("强势股") or []) or "-"
            missing = "、".join(item.get("缺失证据层") or []) or "-"
            body.append(
                '<li>'
                f'<strong>{escape(str(item.get("目标") or "-"))}</strong>'
                f'<span>{escape(str(item.get("理由") or "-"))}</span>'
                f'<small>priority={escape(str(item.get("优先级") or "-"))}｜生命周期={escape(str(item.get("生命周期阶段") or "-"))}｜裁判={escape(str(item.get("证据状态") or "-"))}</small>'
                f'<small>缺：{escape(missing)}｜强势股：{escape(stocks)}</small>'
                '</li>'
            )
        columns.append(
            '<div class="task-col">'
            f'<h3>{_html_badge(title, kind)}</h3>'
            '<ul>'
            + "".join(body)
            + '</ul></div>'
        )
    return '<div class="task-grid">' + "".join(columns) + "</div>"


def render_daily_agent_html(report: dict[str, Any], markdown: str) -> str:
    title = f"每日 Agent 简报 - {report['date']}"
    decision = report["decision"]
    ledger = report["ledger"]
    batch = report["logic_batch"]
    status_kind = "good" if ledger["status"] == "PASS" else "watch"
    next_actions = "".join(f"<li>{escape(str(action))}</li>" for action in report.get("next_actions", []))
    notes = "".join(f"<li>{escape(str(note))}</li>" for note in report.get("notes", []))
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title>
<style>
:root{{--paper:#fffaf1;--ink:#17140f;--muted:#746b5d;--line:#d8cbbb;--accent:#0057ff;--card:#fffdf8;--good:#0f7b43;--watch:#a35b00;--gap:#b3261e;--soft:#f3eadb}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--paper);color:var(--ink);font-family:'Avenir Next','PingFang SC','Hiragino Sans GB',sans-serif;line-height:1.65}}
main{{max-width:1280px;margin:0 auto;padding:24px}}
.hero{{border:1px solid var(--ink);background:var(--card);padding:22px 24px;margin-bottom:18px;display:flex;justify-content:space-between;gap:18px;align-items:flex-end}}
.kicker{{font-size:12px;letter-spacing:.18em;color:var(--accent);font-weight:900}}
h1{{margin:4px 0 0;font-size:32px;line-height:1.15}}
h2{{font-size:20px;margin:0 0 12px}}
h3{{font-size:16px;margin:0}}
.hero p{{margin:8px 0 0;color:var(--muted)}}
.section{{border:1px solid var(--line);background:var(--card);padding:18px;margin:14px 0}}
.metrics{{display:grid;grid-template-columns:repeat(6,minmax(120px,1fr));gap:10px;margin:14px 0}}
.metric{{border:1px solid var(--line);background:#fff;padding:12px}}
.metric span{{display:block;color:var(--muted);font-size:12px}}
.metric strong{{display:block;font-size:26px;line-height:1.1;margin-top:4px}}
.metric small{{display:block;color:var(--muted);margin-top:4px}}
.badge{{display:inline-flex;align-items:center;border:1px solid var(--line);border-radius:999px;padding:2px 9px;font-size:12px;font-weight:800;background:#fff;margin:2px 4px 2px 0;white-space:nowrap}}
.badge.good{{color:var(--good);border-color:#91c7aa;background:#eef8f2}}
.badge.watch{{color:var(--watch);border-color:#e2b36f;background:#fff7e8}}
.badge.gap{{color:var(--gap);border-color:#e7aaa5;background:#fff0ee}}
.badge.info{{color:var(--accent);border-color:#9bbcff;background:#eef4ff}}
.table-wrap{{overflow:auto;border:1px solid var(--line)}}
table{{width:100%;border-collapse:collapse;background:#fff;min-width:900px}}
th,td{{border-bottom:1px solid var(--line);padding:10px 12px;text-align:left;vertical-align:top;font-size:14px}}
th{{background:var(--soft);font-size:12px;color:var(--muted);white-space:nowrap}}
tr:last-child td{{border-bottom:0}}
.two-col{{display:grid;grid-template-columns:1.15fr .85fr;gap:14px}}
.queue{{list-style:none;padding:0;margin:0;display:grid;gap:8px}}
.queue li{{border:1px solid var(--line);background:#fff;padding:10px 12px;display:flex;gap:10px;align-items:center;flex-wrap:wrap}}
.topic{{font-weight:900}}
.score{{font-size:12px;color:var(--muted)}}
.muted-text{{color:var(--muted);font-size:13px}}
.evidence-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}}
.evidence-card{{border:1px solid var(--line);background:#fff;padding:14px}}
.evidence-card header{{display:flex;gap:10px;align-items:flex-start;justify-content:space-between;margin-bottom:8px}}
.reason{{margin:8px 0;color:#362f25}}
.checks{{margin:10px 0}}
.semantic-line{{border-top:1px solid var(--line);padding-top:10px;margin-top:8px;color:var(--muted)}}
.material{{border:1px solid #eadccc;background:#fffdf8;padding:10px;margin-top:10px}}
.material p{{margin:6px 0 0;color:var(--muted);font-size:13px}}
.excerpt{{color:#453b30!important}}
.next{{margin-top:12px;border-top:1px solid var(--line);padding-top:10px;display:grid;gap:6px}}
.next span{{color:var(--muted);font-size:13px}}
.empty{{color:var(--muted);margin:0}}
.empty.small{{font-size:13px}}
.actions{{margin:0;padding-left:20px}}
.task-grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}}
.task-col{{border:1px solid var(--line);background:#fff;padding:12px}}
.task-col h3{{margin-bottom:8px}}
.task-col ul{{list-style:none;margin:0;padding:0;display:grid;gap:10px}}
.task-col li{{border-top:1px solid var(--line);padding-top:8px;display:grid;gap:4px}}
.task-col li:first-child{{border-top:0;padding-top:0}}
.task-col span,.task-col small{{color:var(--muted);font-size:12px}}
@media (max-width:900px){{main{{padding:14px}}.hero{{display:block}}.metrics{{grid-template-columns:repeat(2,1fr)}}.two-col,.evidence-grid{{grid-template-columns:1fr}}}}
@media (max-width:1100px){{.task-grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}
@media (max-width:680px){{.task-grid{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<main>
  <section class="hero">
    <div><div class="kicker">DAILY AGENT</div><h1>{escape(title)}</h1><p>先看结论，再看回补，最后看证据卡。页面展示偏人工阅读，JSON 仍保留完整机器字段。</p></div>
    <div>{_html_badge("日常产物 " + str(ledger["status"]), status_kind)}{_html_badge("向量旧材料 " + MODE_LABELS.get(report["semantic_rag"]["mode"], report["semantic_rag"]["mode"]), "info")}</div>
  </section>
  <section class="metrics">
    {_html_metric("扫描逻辑", batch["scanned_count"])}
    {_html_metric("旧逻辑唤醒", len(decision["old_logic_wakeup"]), "优先判断是否需要深挖")}
    {_html_metric("新逻辑候选", len(decision["new_logic_candidate"]))}
    {_html_metric("数据缺口", len(decision["data_gap"]), "进入回补队列")}
    {_html_metric("待确认", len(decision["noise_or_unconfirmed"]))}
    {_html_metric("向量补证", report["semantic_rag"]["top_n"], "默认只补最靠前")}
  </section>
  <section class="section">
    <h2>马上看：旧逻辑唤醒</h2>
    {_html_table(decision["old_logic_wakeup"], "今天没有旧逻辑唤醒。")}
  </section>
  <section class="two-col">
    <section class="section">
      <h2>需要回补：概念 / 公司 / 证据 / 来源</h2>
      {_html_table(decision["data_gap"], "暂无数据缺口。")}
    </section>
    <section class="section">
      <h2>回补队列</h2>
      {_html_gap_queue(report)}
    </section>
  </section>
  <section class="section">
    <h2>待确认：占位信号 / 噪音</h2>
    {_html_table(decision["noise_or_unconfirmed"], "暂无待确认项。")}
  </section>
  <section class="section">
    <h2>今日研究任务队列</h2>
    {_html_research_queue(report.get("research_queue") or {})}
  </section>
  <section class="section">
    <h2>逻辑证据卡</h2>
    {_html_evidence_cards(decision)}
  </section>
  <section class="section">
    <h2>下一步</h2>
    <ul class="actions">{next_actions}</ul>
  </section>
  <section class="section">
    <h2>说明</h2>
    <ul class="actions">{notes}</ul>
  </section>
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
        f"research_judge={sum(1 for rows in report['decision'].values() for row in rows if row.get('research_judgment'))}",
        f"semantic_rag_hits={sum(1 for rows in report['decision'].values() for row in rows if row.get('semantic_hits'))}",
    ]
    summary.warnings = (
        list(batch.get("warnings") or [])
        + list(report["research_judge"]["warnings"])
        + list(report["semantic_rag"]["warnings"])
    )
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
