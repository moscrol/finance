from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from intelligence.services.research_queue import QUEUE_FIND_OFFICIAL, build_research_queue

EXPORT_DIR = ROOT / "market_feature_store" / "exports"
DEFAULT_FINHOT_DB = ROOT / "khazix-skills" / "finhot" / "data" / "finhot.db"

FACT_TERMS_BY_TYPE: dict[str, tuple[str, ...]] = {
    "announcement": ("公告", "互动易", "巨潮", "上交所", "深交所", "北交所", "交易所", "官网"),
    "order": ("订单", "中标", "合同", "定点", "框架协议", "签订", "采购"),
    "customer_validation": ("客户", "认证", "验证", "送样", "供应", "供应商", "导入", "通过测试"),
    "capacity": ("产能", "扩产", "投产", "产线", "项目", "基地", "达产"),
    "mass_production": ("量产", "批量", "出货", "交付", "规模化"),
    "revenue": ("收入", "营收", "业绩", "毛利", "贡献"),
    "price": ("涨价", "提价", "价格上调"),
}
FACT_TERMS = tuple(dict.fromkeys(term for terms in FACT_TERMS_BY_TYPE.values() for term in terms))
BASELINE_TERMS = ("产品", "主营", "业务", "解决方案", "应用", "用于", "布局", "能力")
DEFAULT_TARGET_EVIDENCE_TYPES = ["announcement", "order", "customer_validation", "capacity", "mass_production", "certification"]
OFFICIAL_SOURCE_TOKENS = ("巨潮", "公告", "互动易", "上交所", "深交所", "北交所", "交易所", "公司官网", "官网", "年报", "半年报", "招股书", "定期报告")
OFFICIAL_URL_TOKENS = ("cninfo.com.cn", "sse.com.cn", "szse.cn", "bse.cn", "static.cninfo", "pdf.dfcfw.com")
ANNUAL_REPORT_TOKENS = ("年报", "年度报告", "半年报", "半年度报告", "招股书", "定期报告")
ALERT_SOURCE_TOKENS = ("财联社", "同花顺", "东方财富", "新浪财经", "华尔街见闻", "格隆汇", "电报", "快讯")
SOCIAL_SOURCE_TOKENS = ("微博", "雪球", "X", "Twitter", "Nitter", "博主", "公众号")
REQUIRED_ITEM_COLUMNS = {"id", "source", "title", "content"}
EXPECTED_ITEM_COLUMNS = ["id", "source", "title", "content", "url", "ts", "day", "effective_ts", "score", "admitted", "dup_group", "event_id"]


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"missing input file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def text_value(value: Any) -> str:
    return str(value or "").strip()


def unique(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = text_value(value)
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def escape_md(value: Any) -> str:
    return text_value(value).replace("|", "/").replace("\n", " ") or "-"


def stock_name(value: Any) -> str:
    if isinstance(value, dict):
        return text_value(value.get("stock_name") or value.get("name") or value.get("company"))
    return text_value(value)


def extract_stock_names(value: Any) -> list[str]:
    return unique([stock_name(item) for item in as_list(value)])


def priority_label(value: Any) -> str:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return "P1"
    if score >= 120:
        return "P0"
    if score >= 80:
        return "P1"
    return "P2"


def query_terms_for(theme: str, entities: list[str]) -> list[str]:
    return unique([theme, *entities, *FACT_TERMS])


def task_from_queue_item(item: dict[str, Any], trade_date: str, index: int, lookback_days: int) -> dict[str, Any]:
    theme = text_value(item.get("目标") or item.get("theme") or item.get("query"))
    entities = extract_stock_names(item.get("强势股") or item.get("strong_stocks"))
    reason = text_value(item.get("理由") or item.get("reason"))
    claim = reason or "缺 L3 官方验证，需找公告、调研、订单、客户验证或产能证据。"
    return {
        "task_id": f"{trade_date or 'unknown'}-daily-find-official-{index:03d}",
        "source": "daily_research_queue",
        "trade_date": trade_date,
        "theme": theme,
        "concept": theme,
        "claim": claim,
        "entities": entities,
        "strong_stocks": entities,
        "target_layer": "L3_current_official_catalyst",
        "target_evidence_types": list(DEFAULT_TARGET_EVIDENCE_TYPES),
        "query_terms": query_terms_for(theme, entities),
        "priority": priority_label(item.get("优先级") or item.get("priority_score")),
        "lookback_days": lookback_days,
        "metadata": {
            "research_queue_reason": reason,
            "research_queue_action": text_value(item.get("动作") or item.get("action")),
            "evidence_status": text_value(item.get("证据状态")),
            "existing_layers": as_list(item.get("已有证据层")),
            "missing_layers": as_list(item.get("缺失证据层")),
            "suggested_action": text_value(item.get("建议动作")),
        },
    }


def queue_rows_from_daily_report(report: dict[str, Any]) -> list[dict[str, Any]]:
    research_queue = report.get("research_queue") if isinstance(report.get("research_queue"), dict) else None
    if research_queue:
        return [row for row in as_list(research_queue.get(QUEUE_FIND_OFFICIAL)) if isinstance(row, dict)]
    if isinstance(report.get(QUEUE_FIND_OFFICIAL), list):
        return [row for row in as_list(report.get(QUEUE_FIND_OFFICIAL)) if isinstance(row, dict)]
    decision = report.get("decision") if isinstance(report.get("decision"), dict) else {}
    if decision:
        queue = build_research_queue(decision)
        return [row for row in as_list(queue.get(QUEUE_FIND_OFFICIAL)) if isinstance(row, dict)]
    return []


def tasks_from_daily_report(report: dict[str, Any], lookback_days: int) -> list[dict[str, Any]]:
    trade_date = text_value(report.get("trade_date") or report.get("date"))
    rows = queue_rows_from_daily_report(report)
    return [task_from_queue_item(item, trade_date, idx + 1, lookback_days) for idx, item in enumerate(rows)]


def normalize_tasks(payload: Any, lookback_days: int) -> list[dict[str, Any]]:
    rows = payload.get("tasks") if isinstance(payload, dict) else payload
    tasks = [row for row in as_list(rows) if isinstance(row, dict)]
    normalized = []
    for idx, row in enumerate(tasks, start=1):
        task = dict(row)
        task.setdefault("task_id", f"task-{idx:03d}")
        task.setdefault("source", "manual_tasks")
        task.setdefault("claim", text_value(task.get("theme") or task.get("concept")))
        task.setdefault("target_layer", "L3_current_official_catalyst")
        task.setdefault("target_evidence_types", list(DEFAULT_TARGET_EVIDENCE_TYPES))
        task.setdefault("lookback_days", lookback_days)
        task["entities"] = unique([text_value(x) for x in as_list(task.get("entities"))])
        theme = text_value(task.get("theme") or task.get("concept") or task.get("claim"))
        task["theme"] = theme
        task.setdefault("concept", theme)
        existing_terms = [text_value(x) for x in as_list(task.get("query_terms"))]
        task["query_terms"] = unique(existing_terms or query_terms_for(theme, task["entities"]))
        normalized.append(task)
    return normalized


def parse_iso_day(value: Any) -> date | None:
    text = text_value(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def item_columns(conn: sqlite3.Connection) -> set[str]:
    return {str(row[1]) for row in conn.execute("PRAGMA table_info(items)").fetchall()}


def schema_diagnostic(conn: sqlite3.Connection) -> dict[str, Any]:
    tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
    columns = {table: [row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()] for table in tables}
    return {"tables": tables, "columns": columns}


def open_finhot_readonly(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    columns = item_columns(conn)
    missing = sorted(REQUIRED_ITEM_COLUMNS - columns)
    if missing:
        diag = schema_diagnostic(conn)
        conn.close()
        raise ValueError(f"finhot items schema missing columns {missing}; diagnostic={json.dumps(diag, ensure_ascii=False)}")
    return conn


def terms_for_search(task: dict[str, Any]) -> list[str]:
    entity_terms = [text_value(x) for x in as_list(task.get("entities"))]
    query_terms = [text_value(x) for x in as_list(task.get("query_terms")) if text_value(x) not in FACT_TERMS]
    return unique([
        text_value(task.get("theme")),
        text_value(task.get("concept")),
        *entity_terms,
        *query_terms,
    ])[:40]


def select_items_for_task(conn: sqlite3.Connection, task: dict[str, Any], fallback_trade_date: str) -> list[dict[str, Any]]:
    columns = item_columns(conn)
    selected = ", ".join(col if col in columns else f"NULL AS {col}" for col in EXPECTED_ITEM_COLUMNS)
    where: list[str] = []
    params: list[Any] = []
    trade_day = parse_iso_day(task.get("trade_date") or fallback_trade_date)
    lookback_days = int(task.get("lookback_days") or 14)
    if trade_day and "day" in columns:
        start = trade_day - timedelta(days=max(lookback_days - 1, 0))
        where.append("day BETWEEN ? AND ?")
        params.extend([start.isoformat(), trade_day.isoformat()])
    terms = terms_for_search(task)
    if terms:
        ors = []
        for term in terms:
            pattern = f"%{term}%"
            ors.append("(title LIKE ? OR content LIKE ?)")
            params.extend([pattern, pattern])
        where.append("(" + " OR ".join(ors) + ")")
    if not where:
        return []
    order_col = "effective_ts" if "effective_ts" in columns else "ts" if "ts" in columns else "id"
    sql = f"SELECT {selected} FROM items WHERE {' AND '.join(where)} ORDER BY {order_col} DESC LIMIT 500"
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def match_terms(text: str, terms: list[str]) -> list[str]:
    return unique([term for term in terms if term and term in text])


def matched_fact_terms(text: str) -> list[str]:
    return [term for term in FACT_TERMS if term in text]


def matched_baseline_terms(text: str) -> list[str]:
    return [term for term in BASELINE_TERMS if term in text]


def evidence_type_for(facts: list[str], baseline_terms: list[str]) -> str:
    for evidence_type, terms in FACT_TERMS_BY_TYPE.items():
        if any(term in facts for term in terms):
            return evidence_type
    return "baseline" if baseline_terms else "unknown"


def source_kind(source: str, title: str, url: str) -> str:
    source_url = f"{source} {url}"
    if any(token in source_url for token in OFFICIAL_SOURCE_TOKENS + OFFICIAL_URL_TOKENS):
        return "official"
    if any(token in source for token in SOCIAL_SOURCE_TOKENS):
        return "social"
    if any(token in source for token in ALERT_SOURCE_TOKENS):
        return "alert"
    if any(token in title for token in ANNUAL_REPORT_TOKENS) and any(token in source_url for token in OFFICIAL_URL_TOKENS):
        return "official"
    return "media"


def source_tier(kind: str) -> str:
    return {
        "official": "official",
        "alert": "T1_alert",
        "media": "T1.5_media",
        "social": "T2_social",
    }.get(kind, "unknown")


def is_annual_report(source: str, title: str, content: str, url: str) -> bool:
    blob = f"{source} {title} {content[:500]} {url}"
    return any(token in blob for token in ANNUAL_REPORT_TOKENS)


def classify_layer(kind: str, annual_report: bool, facts: list[str], baseline_terms: list[str]) -> str:
    if kind == "official":
        if annual_report:
            return "L3_historical_official_fact" if facts else "L2_official_baseline"
        return "L3_current_official_catalyst" if facts else "L2_official_baseline"
    if kind == "social":
        return "L1_signal"
    return "L3_candidate" if facts else "L1_signal"


def recency_bonus(item_day: Any, trade_date: str, lookback_days: int) -> float:
    item_date = parse_iso_day(item_day)
    trade_day = parse_iso_day(trade_date)
    if not item_date or not trade_day or lookback_days <= 0:
        return 0.0
    delta = (trade_day - item_date).days
    if delta < 0 or delta >= lookback_days:
        return 0.0
    return round(0.1 * (1 - delta / lookback_days), 4)


def confidence_for(task: dict[str, Any], row: dict[str, Any], kind: str, entities: list[str], themes: list[str], facts: list[str]) -> float:
    score = 0.0
    task_entities = as_list(task.get("entities"))
    score += 0.25 if entities else 0.1 if not task_entities else 0.0
    score += 0.25 if themes else 0.0
    score += 0.25 if facts else 0.0
    score += {"official": 0.2, "alert": 0.12, "media": 0.08, "social": 0.03}.get(kind, 0.0)
    try:
        finhot_score = float(row.get("score") or 0.0)
    except (TypeError, ValueError):
        finhot_score = 0.0
    score += min(max(finhot_score, 0.0), 1.0) * 0.05
    if int(row.get("admitted") if row.get("admitted") is not None else 1):
        score += 0.03
    score += recency_bonus(row.get("day"), text_value(task.get("trade_date")), int(task.get("lookback_days") or 14))
    return round(min(score, 1.0), 4)


def base_item(task: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": task.get("task_id"),
        "item_id": f"finhot:{row.get('id')}",
        "source": row.get("source") or "",
        "published_at": row.get("day") or "",
        "title": row.get("title") or "",
        "text": row.get("content") or "",
        "url": row.get("url") or "",
        "finhot_score": row.get("score"),
        "admitted": bool(row.get("admitted") if row.get("admitted") is not None else True),
        "dup_group": row.get("dup_group") or "",
    }


def classify_row_for_task(task: dict[str, Any], row: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    source = text_value(row.get("source"))
    title = text_value(row.get("title"))
    content = text_value(row.get("content"))
    url = text_value(row.get("url"))
    text = f"{source} {title} {content} {url}"
    evidence_text = f"{title} {content} {url}"
    entity_terms = [text_value(x) for x in as_list(task.get("entities"))]
    theme_terms = unique([text_value(task.get("theme")), text_value(task.get("concept")), *[text_value(x) for x in as_list(task.get("query_terms")) if x not in FACT_TERMS and x not in entity_terms]])
    entities = match_terms(text, entity_terms)
    themes = match_terms(text, theme_terms)
    facts = matched_fact_terms(evidence_text)
    baseline_terms = matched_baseline_terms(evidence_text)
    if not (entities or themes or facts or baseline_terms):
        return None, None
    item = base_item(task, row)
    item.update({
        "matched_entities": entities,
        "matched_theme_terms": themes,
        "matched_fact_terms": facts,
        "matched_baseline_terms": baseline_terms,
    })
    if row.get("dup_group"):
        item["reject_reason"] = "stale_duplicate"
        return None, item
    if not themes:
        item["reject_reason"] = "theme_mismatch"
        return None, item
    kind = source_kind(source, title, url)
    if not facts and not (kind == "official" and baseline_terms):
        item["reject_reason"] = "no_fact_term"
        return None, item
    if entity_terms and not entities:
        item["reject_reason"] = "entity_mismatch"
        return None, item
    annual = is_annual_report(source, title, content, url)
    layer = classify_layer(kind, annual, facts, baseline_terms)
    confidence = confidence_for(task, row, kind, entities, themes, facts)
    candidate = item | {
        "source_tier": source_tier(kind),
        "evidence_type": evidence_type_for(facts, baseline_terms),
        "evidence_layer": layer,
        "confidence": confidence,
        "reason": reason_for_candidate(kind, layer, entities, themes, facts),
    }
    return candidate, None


def reason_for_candidate(kind: str, layer: str, entities: list[str], themes: list[str], facts: list[str]) -> str:
    entity_part = f"命中实体：{'、'.join(entities)}；" if entities else "无实体约束或未要求实体；"
    theme_part = f"命中题材：{'、'.join(themes[:5])}；"
    fact_part = f"命中事实词：{'、'.join(facts[:8])}；"
    if layer == "L3_current_official_catalyst":
        return entity_part + theme_part + fact_part + "来源可识别为官方/交易所/公司源，作为当前催化候选。"
    if layer == "L3_historical_official_fact":
        return entity_part + theme_part + fact_part + "年报/定期报告含硬事实，作为历史官方事实候选。"
    if layer == "L3_candidate":
        return entity_part + theme_part + fact_part + "来源为快讯/媒体转述，需继续追官方原文。"
    if kind == "social":
        return entity_part + theme_part + fact_part + "来源为社交/博主，仅作发现线索。"
    return entity_part + theme_part + fact_part + "作为弱线索保留。"


def search_tasks_in_finhot(tasks: list[dict[str, Any]], db_path: Path, trade_date: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    if not db_path.exists():
        return [], [], [f"missing finhot db: {db_path}"]
    conn = open_finhot_readonly(db_path)
    candidates: list[dict[str, Any]] = []
    rejects: list[dict[str, Any]] = []
    try:
        for task in tasks:
            for row in select_items_for_task(conn, task, trade_date):
                candidate, reject = classify_row_for_task(task, row)
                if candidate:
                    candidates.append(candidate)
                if reject:
                    rejects.append(reject)
    finally:
        conn.close()
    candidates.sort(key=lambda item: (-float(item.get("confidence") or 0), str(item.get("task_id") or ""), str(item.get("item_id") or "")))
    rejects.sort(key=lambda item: (str(item.get("task_id") or ""), str(item.get("reject_reason") or ""), str(item.get("item_id") or "")))
    return candidates, rejects, warnings


def status_for_task(task: dict[str, Any], candidates: list[dict[str, Any]], rejects: list[dict[str, Any]], missing_db: bool) -> str:
    if missing_db:
        return "input_gap"
    if not text_value(task.get("theme")) and not as_list(task.get("query_terms")):
        return "input_gap"
    if any(item.get("evidence_layer") == "L3_current_official_catalyst" for item in candidates):
        return "official_candidate_found"
    if candidates:
        if all(item.get("evidence_layer") == "L1_signal" for item in candidates):
            return "only_weak_signal"
        return "candidate_found"
    if any(item.get("reject_reason") == "entity_mismatch" for item in rejects):
        return "needs_alias_mapping"
    return "not_found"


def build_report(tasks: list[dict[str, Any]], finhot_db: Path, trade_date: str = "") -> dict[str, Any]:
    if not trade_date:
        trade_date = next((text_value(task.get("trade_date")) for task in tasks if text_value(task.get("trade_date"))), "")
    candidates, rejects, warnings = search_tasks_in_finhot(tasks, finhot_db, trade_date)
    missing_db = any(w.startswith("missing finhot db") for w in warnings)
    candidates_by_task: dict[str, list[dict[str, Any]]] = {}
    rejects_by_task: dict[str, list[dict[str, Any]]] = {}
    for item in candidates:
        candidates_by_task.setdefault(text_value(item.get("task_id")), []).append(item)
    for item in rejects:
        rejects_by_task.setdefault(text_value(item.get("task_id")), []).append(item)
    task_rows: list[dict[str, Any]] = []
    for task in tasks:
        task_id = text_value(task.get("task_id"))
        task_candidates = candidates_by_task.get(task_id, [])
        task_rejects = rejects_by_task.get(task_id, [])
        best = task_candidates[0] if task_candidates else {}
        task_rows.append(dict(task) | {
            "status": status_for_task(task, task_candidates, task_rejects, missing_db),
            "best_evidence_layer": best.get("evidence_layer") or "",
            "best_confidence": best.get("confidence") if best else None,
            "matched_count": len(task_candidates),
            "rejected_count": len(task_rejects),
            "next_action": next_action_for_task(best, task_candidates),
        })
    status_counts = Counter(text_value(task.get("status")) for task in task_rows)
    layer_counts = Counter(text_value(item.get("evidence_layer")) for item in candidates)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "trade_date": trade_date,
        "source": "finhot-evidence-hunter",
        "read_only": True,
        "inputs": {"finhot_db": str(finhot_db)},
        "summary": {
            "task_count": len(task_rows),
            "matched_count": len(candidates),
            "rejected_count": len(rejects),
            "status_counts": dict(sorted(status_counts.items())),
            "evidence_layer_counts": dict(sorted(layer_counts.items())),
        },
        "tasks": task_rows,
        "matched_items": candidates,
        "rejected_items": rejects,
        "warnings": warnings,
    }


def next_action_for_task(best: dict[str, Any], candidates: list[dict[str, Any]]) -> str:
    if not candidates:
        return "未找到有效候选；扩大别名、延长窗口或接入公告/互动易官方源。"
    layer = text_value(best.get("evidence_layer"))
    if layer == "L3_current_official_catalyst":
        return "人工确认官方原文后，进入 approved evidence manifest。"
    if layer == "L3_candidate":
        return "先追公告/互动易/官网原文，确认后再升级为 L3 官方验证。"
    if layer == "L3_historical_official_fact":
        return "可作为历史硬事实候选；若验证当前催化，仍需找近期官方材料。"
    if layer == "L2_official_baseline":
        return "可补官方基线；当前催化仍需订单/客户/量产等新事实。"
    return "仅作线索观察，不写库。"


def render_markdown(report: dict[str, Any]) -> str:
    summary = report.get("summary") or {}
    lines = [
        f"# {report.get('trade_date') or '-'} FinHot Evidence Hunter（read-only）",
        "",
        "> 本报告只读：不写知识库、不升级 evidence_index/entity_exposures、不刷新 RAG。",
        "",
        "## 摘要",
        "",
        f"- **task_count**: {summary.get('task_count', 0)}",
        f"- **matched_count**: {summary.get('matched_count', 0)}",
        f"- **rejected_count**: {summary.get('rejected_count', 0)}",
        f"- **status_counts**: `{json.dumps(summary.get('status_counts', {}), ensure_ascii=False)}`",
        f"- **evidence_layer_counts**: `{json.dumps(summary.get('evidence_layer_counts', {}), ensure_ascii=False)}`",
        "",
    ]
    warnings = as_list(report.get("warnings"))
    if warnings:
        lines.extend(["## Warnings", ""])
        lines.extend(f"- **warning**: {escape_md(w)}" for w in warnings)
        lines.append("")
    lines.extend(["## 任务", "", "| Status | Priority | Theme | Entities | Best layer | Confidence | Next action |", "|---|---|---|---|---|---:|---|"])
    for task in as_list(report.get("tasks")):
        if not isinstance(task, dict):
            continue
        confidence = task.get("best_confidence")
        confidence_text = "-" if confidence is None else f"{float(confidence):.2f}"
        lines.append(
            "| {status} | {priority} | {theme} | {entities} | {layer} | {confidence} | {action} |".format(
                status=escape_md(task.get("status")),
                priority=escape_md(task.get("priority")),
                theme=escape_md(task.get("theme")),
                entities=escape_md("、".join(as_list(task.get("entities")))),
                layer=escape_md(task.get("best_evidence_layer")),
                confidence=confidence_text,
                action=escape_md(task.get("next_action")),
            )
        )
    lines.extend(["", "## 候选证据", "", "| Task | Layer | Conf | Source | Entity | Fact terms | Title | Reason | URL |", "|---|---|---:|---|---|---|---|---|---|"])
    for item in as_list(report.get("matched_items"))[:120]:
        if not isinstance(item, dict):
            continue
        lines.append(
            "| {task} | {layer} | {conf:.2f} | {source} | {entities} | {facts} | {title} | {reason} | {url} |".format(
                task=escape_md(item.get("task_id")),
                layer=escape_md(item.get("evidence_layer")),
                conf=float(item.get("confidence") or 0),
                source=escape_md(item.get("source")),
                entities=escape_md("、".join(as_list(item.get("matched_entities")))),
                facts=escape_md("、".join(as_list(item.get("matched_fact_terms"))[:8])),
                title=escape_md(item.get("title")),
                reason=escape_md(item.get("reason")),
                url=escape_md(item.get("url")),
            )
        )
    lines.extend(["", "## 拒绝/降级项", "", "| Task | Reject reason | Source | Title | Matched theme | Matched entity | Matched facts |", "|---|---|---|---|---|---|---|"])
    for item in as_list(report.get("rejected_items"))[:120]:
        if not isinstance(item, dict):
            continue
        lines.append(
            "| {task} | {reason} | {source} | {title} | {themes} | {entities} | {facts} |".format(
                task=escape_md(item.get("task_id")),
                reason=escape_md(item.get("reject_reason")),
                source=escape_md(item.get("source")),
                title=escape_md(item.get("title")),
                themes=escape_md("、".join(as_list(item.get("matched_theme_terms")))),
                entities=escape_md("、".join(as_list(item.get("matched_entities")))),
                facts=escape_md("、".join(as_list(item.get("matched_fact_terms"))[:8])),
            )
        )
    lines.append("")
    return "\n".join(lines)


def output_paths_for(trade_date: str) -> tuple[Path, Path, Path]:
    stem_date = trade_date or datetime.now().date().isoformat()
    return (
        EXPORT_DIR / f"{stem_date}-verification-tasks.json",
        EXPORT_DIR / f"{stem_date}-evidence-hunter.json",
        EXPORT_DIR / f"{stem_date}-evidence-hunter.md",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build read-only FinHot evidence hunter report")
    parser.add_argument("--daily-agent-json")
    parser.add_argument("--tasks")
    parser.add_argument("--finhot-db", default=str(DEFAULT_FINHOT_DB))
    parser.add_argument("--trade-date", default="")
    parser.add_argument("--lookback-days", type=int, default=14)
    parser.add_argument("--out-tasks")
    parser.add_argument("--out-json")
    parser.add_argument("--out-md")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.tasks and not args.daily_agent_json:
        raise SystemExit("provide --tasks or --daily-agent-json")
    if args.tasks:
        raw_tasks = load_json(Path(args.tasks).expanduser())
        tasks = normalize_tasks(raw_tasks, args.lookback_days)
        trade_date = args.trade_date or next((text_value(task.get("trade_date")) for task in tasks if text_value(task.get("trade_date"))), "")
    else:
        daily_path = Path(args.daily_agent_json).expanduser()
        report = load_json(daily_path)
        if not isinstance(report, dict):
            raise ValueError(f"daily agent json root is not an object: {daily_path}")
        tasks = tasks_from_daily_report(report, args.lookback_days)
        trade_date = args.trade_date or text_value(report.get("trade_date") or report.get("date"))
    default_tasks, default_json, default_md = output_paths_for(trade_date)
    out_tasks = Path(args.out_tasks).expanduser() if args.out_tasks else default_tasks
    out_json = Path(args.out_json).expanduser() if args.out_json else default_json
    out_md = Path(args.out_md).expanduser() if args.out_md else default_md
    finhot_db = Path(args.finhot_db).expanduser()
    write_json(out_tasks, {"trade_date": trade_date, "source": "verification_tasks", "tasks": tasks})
    report = build_report(tasks, finhot_db, trade_date)
    report["inputs"].update({
        "tasks": str(out_tasks),
        "daily_agent_json": text_value(args.daily_agent_json),
    })
    write_json(out_json, report)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_markdown(report), encoding="utf-8")
    print(f"wrote {out_tasks}")
    print(f"wrote {out_json}")
    print(f"wrote {out_md}")
    print(f"summary={json.dumps(report['summary'], ensure_ascii=False, sort_keys=True)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
