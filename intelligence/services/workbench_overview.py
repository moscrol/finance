from __future__ import annotations

import json
import re
import statistics
from collections import defaultdict
from datetime import date
from pathlib import Path
import duckdb

from intelligence.services.market_moneyflow import load_moneyflow_snapshot
from intelligence.services.forecast_learning import learning_feedback_projection


_FRESHNESS_TABLES = (
    ("market", "市场总览", "fact_market_daily", "trade_date"),
    ("mainline_theme", "题材主线", "fact_mainline_theme_daily", "trade_date"),
    ("mainline_sector", "主线板块明细", "fact_mainline_sector_daily", "trade_date"),
    ("mainline_stock", "主线个股明细", "fact_mainline_stock_daily", "trade_date"),
    ("sector", "板块行情", "fact_sector_daily", "trade_date"),
    ("feature", "滚动特征", "feature_market_window", "as_of_date"),
)
_QUEUE_LABELS = {
    "today_do_ima": ("new", "新出现"),
    "today_find_official_evidence": ("strengthened", "被加强"),
    "today_downgrade_or_watch": ("weakened", "被削弱 / 纠正"),
    "today_wait_market_validation": ("pending", "等待验证"),
}
_KNOWLEDGE_STAGES = ("暗流", "观察", "萌芽", "第一轮", "催化共振", "一致认同")
_MARKET_STAGES = ("未确认", "首次响应", "扩散", "主升", "分歧 / 兑现")
_FORECAST_SAMPLE_GOAL = 25


def _date_text(value: object) -> str | None:
    if value is None:
        return None
    return value.isoformat() if isinstance(value, date) else str(value)


def _number(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_market_stage(value: object) -> str:
    text = str(value or "")
    for stage in ("修复", "主升", "轮动", "分歧", "退潮"):
        if stage in text:
            return stage
    if any(term in text for term in ("底部", "横盘", "冰点", "企稳")):
        return "修复"
    return text or "未知"


def _table_exists(con: duckdb.DuckDBPyConnection, table: str) -> bool:
    return bool(
        con.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = 'main' AND table_name = ?
            """,
            [table],
        ).fetchone()[0]
    )


def _latest_table_status(
    con: duckdb.DuckDBPyConnection,
    *,
    key: str,
    label: str,
    table: str,
    date_column: str,
    target_date: str | None,
) -> dict[str, object]:
    if not _table_exists(con, table):
        return {
            "key": key,
            "label": label,
            "date": None,
            "status": "missing",
            "row_count": 0,
            "message": "数据表尚未初始化",
        }
    latest, row_count = con.execute(
        f"""
        SELECT MAX({date_column}),
               COUNT(*) FILTER (WHERE {date_column} = (
                   SELECT MAX({date_column}) FROM {table}
               ))
        FROM {table}
        """
    ).fetchone()
    latest_text = _date_text(latest)
    status = "complete"
    message = "已更新"
    if latest_text is None:
        status, message = "missing", "暂无数据"
    elif target_date and latest_text < target_date:
        status, message = "stale", f"落后于市场总览 {target_date}"
    return {
        "key": key,
        "label": label,
        "date": latest_text,
        "status": status,
        "row_count": int(row_count or 0),
        "message": message,
    }


def _add_theme_coverage(
    con: duckdb.DuckDBPyConnection,
    target_date: str | None,
    statuses: list[dict[str, object]],
) -> None:
    if not target_date or not _table_exists(con, "fact_mainline_theme_daily"):
        return
    themes = int(
        con.execute(
            """
            SELECT COUNT(DISTINCT theme_code)
            FROM fact_mainline_theme_daily
            WHERE trade_date = ?
            """,
            [target_date],
        ).fetchone()[0]
        or 0
    )
    if themes == 0:
        return
    for key, table in (
        ("mainline_sector", "fact_mainline_sector_daily"),
        ("mainline_stock", "fact_mainline_stock_daily"),
    ):
        if not _table_exists(con, table):
            continue
        covered = int(
            con.execute(
                f"""
                SELECT COUNT(DISTINCT theme_code)
                FROM {table}
                WHERE trade_date = ?
                """,
                [target_date],
            ).fetchone()[0]
            or 0
        )
        for item in statuses:
            if item["key"] != key:
                continue
            item["coverage"] = {
                "covered": covered,
                "total": themes,
                "missing": themes - covered,
            }
            if covered < themes and item["status"] == "complete":
                item["status"] = "partial"
            if covered < themes:
                item["message"] = (
                    f"当前题材覆盖 {covered}/{themes}；未覆盖部分保持未知"
                )


def _latest_daily_agent(
    repo_root: Path, as_of_date: str | None
) -> tuple[Path | None, dict[str, object]]:
    exports = repo_root / "market_feature_store" / "exports"
    for path in sorted(exports.glob("*-daily-agent.json"), reverse=True):
        report_date = path.name.removesuffix("-daily-agent.json")
        if as_of_date and report_date > as_of_date:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            return path, payload
    return None, {}


def _knowledge_stage(item: dict[str, object]) -> str:
    lifecycle = item.get("logic_lifecycle") or item.get("生命周期") or {}
    raw = str(
        lifecycle.get("生命周期阶段")
        or item.get("生命周期阶段")
        or item.get("classification")
        or ""
    )
    if any(token in raw for token in ("一致", "拥挤", "兑现")):
        return "一致认同"
    if any(token in raw for token in ("共振", "升温", "强化")):
        return "催化共振"
    if any(token in raw for token in ("第一轮", "旧逻辑唤醒", "主线")):
        return "第一轮"
    if any(token in raw for token in ("萌芽", "新逻辑", "新出现")):
        return "萌芽"
    if any(token in raw for token in ("观察", "验证")):
        return "观察"
    return "暗流"


def _market_stage(cycle_statuses: list[str], current: bool) -> str:
    if not current:
        return "未确认"
    text = " ".join(cycle_statuses)
    if any(token in text for token in ("分歧", "兑现", "退潮", "衰退")):
        return "分歧 / 兑现"
    if any(token in text for token in ("主升", "加速")):
        return "主升"
    if any(token in text for token in ("扩散", "发酵", "轮动")):
        return "扩散"
    if any(token in text for token in ("启动", "首次", "萌芽")):
        return "首次响应"
    return "未确认"


def _daily_agent_candidates(
    payload: dict[str, object],
) -> dict[str, dict[str, object]]:
    candidates: dict[str, dict[str, object]] = {}
    decision = payload.get("decision")
    if not isinstance(decision, dict):
        return candidates
    for rows in decision.values():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = str(row.get("matched_theme") or row.get("query") or "").strip()
            if name and name not in candidates:
                candidates[name] = row
    return candidates


def _load_themes(
    con: duckdb.DuckDBPyConnection,
    target_date: str | None,
    agent_payload: dict[str, object],
    agent_date: str | None,
) -> list[dict[str, object]]:
    if not target_date or not _table_exists(con, "fact_mainline_theme_daily"):
        return []
    sector_current = (
        _table_exists(con, "fact_mainline_sector_daily")
        and _date_text(
            con.execute("SELECT MAX(trade_date) FROM fact_mainline_sector_daily").fetchone()[0]
        )
        == target_date
    )
    stock_current = (
        _table_exists(con, "fact_mainline_stock_daily")
        and _date_text(
            con.execute("SELECT MAX(trade_date) FROM fact_mainline_stock_daily").fetchone()[0]
        )
        == target_date
    )
    rows = con.execute(
        """
        SELECT theme_code, theme_name, sector_count, min_sort
        FROM fact_mainline_theme_daily
        WHERE trade_date = ?
        ORDER BY min_sort NULLS LAST, theme_name
        """,
        [target_date],
    ).fetchall()
    candidates = _daily_agent_candidates(agent_payload)
    result = []
    for theme_code, theme_name, sector_count, _min_sort in rows:
        sector_rows: list[tuple[object, ...]] = []
        if sector_current:
            sector_rows = con.execute(
                """
                SELECT sector_name, cycle_status
                FROM fact_mainline_sector_daily
                WHERE trade_date = ? AND theme_code = ?
                ORDER BY sort_no NULLS LAST
                """,
                [target_date, theme_code],
            ).fetchall()
        stock_count = 0
        if stock_current:
            stock_count = int(
                con.execute(
                    """
                    SELECT COUNT(DISTINCT stock_ts_code)
                    FROM fact_mainline_stock_daily
                    WHERE trade_date = ? AND theme_code = ?
                    """,
                    [target_date, theme_code],
                ).fetchone()[0]
            )
        candidate = candidates.get(str(theme_name), {})
        knowledge_stage = _knowledge_stage(candidate) if candidate else "暗流"
        cycle_statuses = [str(row[1] or "") for row in sector_rows]
        detail_current = bool(sector_rows) and stock_count > 0
        market_stage = _market_stage(cycle_statuses, bool(sector_rows))
        result.append(
            {
                "theme_code": str(theme_code or ""),
                "name": str(theme_name or theme_code or ""),
                "knowledge_stage": knowledge_stage,
                "knowledge_stage_index": _KNOWLEDGE_STAGES.index(knowledge_stage),
                "knowledge_date": agent_date,
                "market_stage": market_stage,
                "market_stage_index": _MARKET_STAGES.index(market_stage),
                "market_date": target_date,
                "source_count": int(
                    candidate.get("structured_counts", {}).get("source_trace", 0)
                    if isinstance(candidate.get("structured_counts"), dict)
                    else 0
                ),
                "sector_count": int(sector_count or len(sector_rows) or 0),
                "stock_count": stock_count,
                "sectors": [str(row[0]) for row in sector_rows[:4] if row[0]],
                "direction": str(
                    (candidate.get("logic_lifecycle") or candidate.get("生命周期") or {}).get(
                        "阶段变化", "待对齐"
                    )
                ),
                "evidence_type": str(
                    candidate.get("research_judgment", {}).get("证据状态")
                    if isinstance(candidate.get("research_judgment"), dict)
                    else candidate.get("classification", "盘面主线")
                ),
                "detail_status": "current" if detail_current else "stale",
            }
        )
    return result


def _user_facing_signal_text(value: object) -> str:
    text = str(value or "")
    for internal, user_facing in (
        ("L1/L2 叙事或基线材料", "研究叙事或公司基础资料"),
        ("L2 基线或 L3 官方验证", "公司基础资料或官方披露验证"),
        ("L1/L2 材料", "研究叙事与基础资料"),
        ("补 L2 基线", "补公司基础资料"),
        ("做 L3 验证", "做官方披露验证"),
        ("新增 L3 事实", "新增官方披露事实"),
        ("不重复 IMA", "不重复研究队列"),
        ("L1 叙事线索", "研究线索"),
        ("L2 基线", "公司基础资料"),
        ("L3 官方验证", "官方披露验证"),
        ("L3 事实", "官方披露事实"),
        ("L2/L3 缺口", "基础资料 / 官方披露缺口"),
        ("L1/L2", "研究叙事 / 基础资料"),
        ("L2/L3", "基础资料 / 官方披露"),
        ("L1", "研究资料"),
        ("L2", "公司基础资料"),
        ("L3", "官方披露"),
        ("IMA", "研究队列"),
    ):
        text = text.replace(internal, user_facing)
    return re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)


def _signal_card(
    item: dict[str, object],
    bucket: str,
    label: str,
    source_date: str | None,
) -> dict[str, object]:
    target = str(item.get("目标") or item.get("matched_theme") or item.get("query") or "未命名事件")
    market = item.get("market_validation") or item.get("盘面验证")
    market_summary = ""
    if isinstance(market, dict):
        market_summary = str(market.get("验证结论") or market.get("盘面验证强度") or "")
    return {
        "bucket": bucket,
        "bucket_label": label,
        "title": target,
        "change": str(item.get("阶段变化") or item.get("动作") or label),
        "summary": _user_facing_signal_text(
            item.get("理由") or item.get("变化原因") or item.get("建议动作")
        ),
        "source_type": "晨汇 / 研究队列",
        "source_date": source_date,
        "impact": target,
        "market_confirmation": _user_facing_signal_text(
            market_summary or "等待同日盘面核对"
        ),
        "next_validation": _user_facing_signal_text(
            item.get("建议动作") or item.get("下一步") or "等待下一交易日验证"
        ),
    }


def _load_signals(
    payload: dict[str, object],
    source_date: str | None,
) -> dict[str, list[dict[str, object]]]:
    queue = payload.get("research_queue")
    result = {bucket: [] for bucket, _label in _QUEUE_LABELS.values()}
    if not isinstance(queue, dict):
        return result
    for key, (bucket, label) in _QUEUE_LABELS.items():
        rows = queue.get(key)
        if not isinstance(rows, list):
            continue
        result[bucket] = [
            _signal_card(row, bucket, label, source_date)
            for row in rows[:8]
            if isinstance(row, dict)
        ]
    return result


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.is_file():
        return []
    rows: list[dict[str, object]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return []
    return rows


def _source_names(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return {
        str(item.get("source_id")): str(item.get("canonical") or item.get("source_id"))
        for item in payload.get("sources", [])
        if isinstance(item, dict) and item.get("source_id")
    }


def _aggregate_winrate(
    rows: list[dict[str, object]],
    names: dict[str, str],
    window: int,
    min_calls: int = 5,
) -> dict[str, dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        source_id = str(row.get("source_id") or "")
        if source_id and row.get(f"ret_{window}d_complete"):
            grouped[source_id].append(row)
    result: dict[str, dict[str, object]] = {}
    for source_id, events in grouped.items():
        excess = [
            float(event[f"excess_{window}d"])
            for event in events
            if event.get(f"excess_{window}d") is not None
        ]
        if len(excess) < min_calls:
            continue
        drawdowns = [
            float(event["post_peak_dd"])
            for event in events
            if event.get("post_peak_dd") is not None
        ]
        result[source_id] = {
            "source_id": source_id,
            "name": names.get(source_id, source_id),
            "sample_count": len(excess),
            "win_rate": sum(value > 0 for value in excess) / len(excess),
            "average_excess": statistics.mean(excess),
            "median_excess": statistics.median(excess),
            "average_drawdown": statistics.mean(drawdowns) if drawdowns else None,
        }
    return result


def _load_sellside(
    knowledge_wiki: Path,
) -> tuple[
    list[dict[str, object]],
    dict[str, list[dict[str, object]]],
    str | None,
]:
    store = knowledge_wiki / "raw" / "theme-radar" / "opinion-store"
    outcomes = _read_jsonl(store / "outcomes.jsonl")
    names = _source_names(store / "sources.json")
    win5 = _aggregate_winrate(outcomes, names, 5)
    win10 = _aggregate_winrate(outcomes, names, 10)
    rows = []
    for source_id in set(win5) | set(win10):
        five = win5.get(source_id)
        ten = win10.get(source_id)
        base = five or ten
        if base is None:
            continue
        best = max(
            ((5, five), (10, ten)),
            key=lambda pair: (
                pair[1]["win_rate"] if pair[1] else -1,
                pair[1]["sample_count"] if pair[1] else -1,
            ),
        )[0]
        rows.append(
            {
                "source_id": source_id,
                "name": base["name"],
                "sample_count": max(
                    five["sample_count"] if five else 0,
                    ten["sample_count"] if ten else 0,
                ),
                "t5_win_rate": five["win_rate"] if five else None,
                "t10_win_rate": ten["win_rate"] if ten else None,
                "average_excess": base["average_excess"],
                "median_excess": base["median_excess"],
                "average_drawdown": base["average_drawdown"],
                "best_window": f"T+{best}",
            }
        )
    rows.sort(
        key=lambda item: (
            item["t5_win_rate"] if item["t5_win_rate"] is not None else -1,
            item["average_excess"],
        ),
        reverse=True,
    )

    events = _read_jsonl(store / "opinion-events.jsonl")
    latest_date = max((str(row.get("report_date") or "") for row in events), default="") or None
    flow = {"priority": [], "confirmation": [], "caution": []}
    seen: set[tuple[str, str]] = set()
    for event in reversed(events):
        if latest_date and str(event.get("report_date") or "") != latest_date:
            continue
        name = str(event.get("concept") or event.get("term") or event.get("target") or "未命名观点")
        source = names.get(str(event.get("source_id") or ""), str(event.get("source") or "未署名"))
        dedupe = (name, source)
        if dedupe in seen:
            continue
        seen.add(dedupe)
        mentions = int(event.get("mention_count") or 0)
        has_hard = bool(event.get("hard_evidence"))
        if mentions >= 20:
            bucket = "caution"
            reason = "覆盖较拥挤，先观察兑现与掉队"
        elif has_hard and mentions <= 5:
            bucket = "priority"
            reason = "覆盖较低且出现较硬证据"
        else:
            bucket = "confirmation"
            reason = "逻辑可作确认，仍需盘面同日验证"
        if len(flow[bucket]) < 6:
            flow[bucket].append(
                {
                    "theme": name,
                    "source": source,
                    "report_date": latest_date,
                    "mention_count": mentions,
                    "reason": reason,
                }
            )
    return rows[:12], flow, latest_date


def _load_forecast_performance(repo_root: Path) -> dict[str, object]:
    """把双盲 verdict 聚合投影成 Workbench 可展示的方向命中率。

    verdict/answer 文件仍是唯一事实源；这里不落新台账。聚合逻辑复用 CLI，避免
    Workbench 与 `dual_blind_forecast.py aggregate` 出现两套命中口径。
    """
    ledger = repo_root / "docs" / "learning" / "forecast-review-ledger"
    empty = {
        "sample_goal": _FORECAST_SAMPLE_GOAL,
        "total_judged": 0,
        "decision_eligible": False,
        "rows": [],
    }
    if not ledger.is_dir():
        return empty
    try:
        from scripts.dual_blind_forecast import aggregate

        report = aggregate(ledger)
    except Exception:
        return empty
    rows: list[dict[str, object]] = []
    for key, stat in sorted((report.get("agents") or {}).items()):
        if not isinstance(stat, dict):
            continue
        bucket = (stat.get("verdicts_by_category") or {}).get("direction") or {}
        hits = int(bucket.get("hit") or 0)
        misses = int(bucket.get("miss") or 0)
        partial = int(bucket.get("partial") or 0)
        unverifiable = int(bucket.get("unverifiable") or 0)
        judged = hits + misses + partial
        if not judged and not unverifiable:
            continue
        rows.append(
            {
                "key": key,
                "agent": str(stat.get("agent") or key.split("/", 1)[0]),
                "source": str(stat.get("source") or "unknown"),
                "sample_count": judged,
                "hits": hits,
                "misses": misses,
                "partial": partial,
                "unverifiable": unverifiable,
                "hit_rate": round(hits / judged, 4) if judged else None,
                "weighted_rate": (
                    round((hits + partial * 0.5) / judged, 4) if judged else None
                ),
                "sample_goal": _FORECAST_SAMPLE_GOAL,
                "decision_eligible": judged >= _FORECAST_SAMPLE_GOAL,
            }
        )
    total = sum(int(row["sample_count"]) for row in rows)
    return {
        "sample_goal": _FORECAST_SAMPLE_GOAL,
        "total_judged": total,
        "decision_eligible": bool(rows)
        and all(bool(row["decision_eligible"]) for row in rows),
        "rows": rows,
    }


def _load_market(
    con: duckdb.DuckDBPyConnection,
    target_date: str | None,
    statuses: list[dict[str, object]],
) -> dict[str, object]:
    if not target_date or not _table_exists(con, "fact_market_daily"):
        return {
            "trade_date": target_date,
            "stage": "数据缺失",
            "mainlines": [],
            "risks": ["市场总览尚未生成"],
            "validation_points": ["先补齐市场总览数据"],
        }
    cursor = con.execute(
        """
        SELECT market_stage, advancers, limit_up, limit_down, total_amount,
               amount_vs_yesterday_pct, amount_ma20, top3_industry_ratio,
               concentration_state, strength_marginal_pct, strength_status
        FROM fact_market_daily
        WHERE trade_date = ?
        """,
        [target_date],
    )
    row = cursor.fetchone()
    if row is None:
        return {"trade_date": target_date, "stage": "数据缺失", "mainlines": []}
    (
        stage,
        advancers,
        limit_up,
        limit_down,
        total_amount,
        amount_change,
        amount_ma20,
        concentration,
        concentration_state,
        strength_marginal,
        strength_status,
    ) = row
    breadth_ma5 = None
    breadth_trend = None
    if _table_exists(con, "feature_market_window"):
        feature = con.execute(
            """
            SELECT advancers_ma5, breadth_trend
            FROM feature_market_window
            WHERE as_of_date = ?
            ORDER BY start_date DESC
            LIMIT 1
            """,
            [target_date],
        ).fetchone()
        if feature:
            breadth_ma5, breadth_trend = feature
    mainlines = []
    theme_status = next((item for item in statuses if item["key"] == "mainline_theme"), None)
    if theme_status and theme_status["status"] == "complete":
        mainlines = [
            str(item[0])
            for item in con.execute(
                """
                SELECT theme_name
                FROM fact_mainline_theme_daily
                WHERE trade_date = ?
                ORDER BY min_sort NULLS LAST
                LIMIT 6
                """,
                [target_date],
            ).fetchall()
            if item[0]
        ]
    risks = []
    if limit_down and int(limit_down) > 10:
        risks.append(f"跌停 {int(limit_down)} 家，尾部风险仍高")
    if concentration and float(concentration) >= 40:
        risks.append("赚钱效应集中度偏高，主线拥挤风险上升")
    stale_details = [
        item["label"]
        for item in statuses
        if item["key"] in {"mainline_sector", "mainline_stock"} and item["status"] != "complete"
    ]
    if stale_details:
        risks.append(f"{'、'.join(stale_details)}未更新，不展示旧板块或旧标的")
    if not risks:
        risks.append("未见结构性高风险，但仍需下一交易日确认")
    amount_vs_ma20 = None
    if _number(total_amount) is not None and _number(amount_ma20):
        amount_vs_ma20 = (_number(total_amount) / _number(amount_ma20) - 1) * 100
    validation_points = [
        "涨家数能否继续高于 MA5，确认赚钱效应是否扩散",
        "成交额能否维持或回到 20 日均值上方",
    ]
    if mainlines:
        validation_points.append(f"{'、'.join(mainlines[:2])}能否保持板块与个股同步确认")
    else:
        validation_points.append("等待同日题材数据后再确认当前主线")
    return {
        "trade_date": target_date,
        "stage": _normalize_market_stage(stage),
        "stage_source": str(stage or "未知"),
        "advancers": int(advancers) if advancers is not None else None,
        "advancers_ma5": _number(breadth_ma5),
        "breadth_trend": str(breadth_trend or "未知"),
        "limit_up": int(limit_up) if limit_up is not None else None,
        "limit_down": int(limit_down) if limit_down is not None else None,
        "total_amount": _number(total_amount),
        "amount_vs_yesterday_pct": _number(amount_change),
        "amount_vs_ma20_pct": amount_vs_ma20,
        "mainlines": mainlines,
        "risks": risks,
        "concentration_pct": _number(concentration),
        "concentration_state": str(concentration_state or "未知"),
        "strength_marginal_pct": _number(strength_marginal),
        "strength_status": str(strength_status or "未知"),
        "validation_points": validation_points,
    }


def _load_moneyflow_trends(
    con: duckdb.DuckDBPyConnection,
    target_date: str | None,
) -> list[dict[str, object]]:
    if not target_date or not _table_exists(con, "feature_l2_capital_flow_daily"):
        return []
    dates = [
        _date_text(row[0])
        for row in con.execute(
            """
            SELECT DISTINCT trade_date
            FROM feature_l2_capital_flow_daily
            WHERE trade_date <= ?
            ORDER BY trade_date DESC
            LIMIT 5
            """,
            [target_date],
        ).fetchall()
    ]
    dates = [item for item in dates if item]
    if not dates:
        return []
    rows = con.execute(
        """
        SELECT trade_date, stock_code, stock_name, main_buy_net_wan,
               rank, pct_change
        FROM feature_l2_capital_flow_daily
        WHERE trade_date IN (SELECT UNNEST(?::DATE[]))
        ORDER BY trade_date DESC, rank ASC NULLS LAST
        """,
        [dates],
    ).fetchall()
    grouped: dict[str, list[tuple[object, ...]]] = defaultdict(list)
    for row in rows:
        grouped[str(row[1] or "")].append(row)
    result = []
    for stock_code, history in grouped.items():
        latest = history[0]
        if _date_text(latest[0]) != dates[0]:
            continue
        consecutive = 0
        for event in history:
            if _number(event[3]) is not None and _number(event[3]) > 0:
                consecutive += 1
            else:
                break
        previous_rank = int(history[1][4]) if len(history) > 1 and history[1][4] else None
        latest_rank = int(latest[4]) if latest[4] else None
        rank_change = (
            previous_rank - latest_rank
            if previous_rank is not None and latest_rank is not None
            else None
        )
        pct_change = _number(latest[5])
        net = _number(latest[3])
        result.append(
            {
                "stock_code": stock_code,
                "stock_name": str(latest[2] or stock_code),
                "trade_date": dates[0],
                "history_days": len(history),
                "consecutive_inflow_days": consecutive,
                "rank_change": rank_change,
                "is_new": len(history) == 1,
                "divergence": (
                    "价格跌 / 资金流入"
                    if pct_change is not None
                    and net is not None
                    and pct_change < 0 < net
                    else "价格涨 / 资金流出"
                    if pct_change is not None
                    and net is not None
                    and pct_change > 0 > net
                    else None
                ),
            }
        )
    result.sort(
        key=lambda item: (
            int(item["consecutive_inflow_days"]),
            int(item["rank_change"] or 0),
        ),
        reverse=True,
    )
    return result[:20]


def build_workbench_overview(
    repo_root: str | Path,
    knowledge_wiki: str | Path,
) -> dict[str, object]:
    root = Path(repo_root)
    wiki = Path(knowledge_wiki)
    db_path = root / "db" / "market_feature_store.duckdb"
    agent_path, agent_payload = _latest_daily_agent(root, None)
    agent_date = str(agent_payload.get("date") or "") or None
    winrate, sellside_flow, sellside_date = _load_sellside(wiki)
    forecast_performance = _load_forecast_performance(root)
    learning_feedback = learning_feedback_projection(
        root / "docs" / "learning" / "forecast-lessons"
    )
    moneyflow = load_moneyflow_snapshot(db_path)
    missing_response = {
        "as_of_date": None,
        "market": {
            "trade_date": None,
            "stage": "数据缺失",
            "mainlines": [],
            "risks": ["本地市场数据暂不可用"],
            "validation_points": ["先完成数据同步与质量检查"],
        },
        "themes": [],
        "theme_axes": {
            "knowledge": list(_KNOWLEDGE_STAGES),
            "market": list(_MARKET_STAGES),
        },
        "signals": _load_signals(agent_payload, agent_date),
        "signal_date": agent_date,
        "winrate": winrate,
        "forecast_performance": forecast_performance,
        "learning_feedback": learning_feedback,
        "sellside_flow": sellside_flow,
        "sellside_date": sellside_date,
        "moneyflow": moneyflow.to_dict(),
        "moneyflow_trends": [],
        "validation": {
            "logic_effectiveness": agent_payload.get("logic_effectiveness", {}),
            "hypothesis_status": "等待市场数据",
        },
        "data_status": [
            {
                "key": "database",
                "label": "市场数据库",
                "date": None,
                "status": "missing",
                "row_count": 0,
                "message": "数据库文件不存在",
            }
        ],
        "agent_artifact": str(agent_path) if agent_path else None,
    }
    if not db_path.is_file():
        return missing_response
    try:
        con = duckdb.connect(str(db_path), read_only=True)
    except Exception:
        missing_response["data_status"][0]["message"] = "数据库暂时不可读"
        return missing_response
    try:
        target_date = None
        if _table_exists(con, "fact_market_daily"):
            target_date = _date_text(
                con.execute("SELECT MAX(trade_date) FROM fact_market_daily").fetchone()[0]
            )
        agent_path, agent_payload = _latest_daily_agent(root, target_date)
        agent_date = str(agent_payload.get("date") or "") or None
        statuses = [
            _latest_table_status(
                con,
                key=key,
                label=label,
                table=table,
                date_column=date_column,
                target_date=target_date,
            )
            for key, label, table, date_column in _FRESHNESS_TABLES
        ]
        _add_theme_coverage(con, target_date, statuses)
        moneyflow = load_moneyflow_snapshot(db_path, as_of_date=target_date)
        l2_status = {
            "key": "l2",
            "label": "Level2 资金流",
            "date": moneyflow.trade_date,
            "status": "complete" if moneyflow.status == "ok" else moneyflow.status,
            "row_count": sum(moneyflow.coverage.values()),
            "message": "；".join(moneyflow.warnings[:1]) or "已更新",
        }
        if _table_exists(con, "ops_pipeline_run_daily") and target_date:
            markers = con.execute(
                """
                SELECT step, status, row_count
                FROM ops_pipeline_run_daily
                WHERE trade_date = ? AND pipeline = 'l2-moneyflow'
                """,
                [target_date],
            ).fetchall()
            marker_statuses = {str(row[0]): str(row[1]) for row in markers}
            if markers:
                expected = {"limitup", "top100", "quant"}
                if expected <= set(marker_statuses) and all(
                    marker_statuses[step] == "complete" for step in expected
                ):
                    l2_status["status"] = "complete"
                    l2_status["message"] = "三个扫描步骤均完成"
                elif any(status == "failed" for status in marker_statuses.values()):
                    l2_status["status"] = "failed"
                    l2_status["message"] = "至少一个扫描步骤失败"
                elif any(status == "running" for status in marker_statuses.values()):
                    l2_status["status"] = "running"
                    l2_status["message"] = "扫描仍在运行，不能视为完成"
                else:
                    l2_status["status"] = "partial"
                    l2_status["message"] = "扫描步骤不完整"
                l2_status["row_count"] = sum(int(row[2] or 0) for row in markers)
        statuses.append(l2_status)
        statuses.append(
            {
                "key": "knowledge",
                "label": "晨汇 / 知识事件",
                "date": agent_date,
                "status": (
                    "missing"
                    if not agent_date
                    else "complete"
                    if not target_date or agent_date == target_date
                    else "stale"
                ),
                "row_count": sum(
                    len(rows)
                    for rows in _load_signals(agent_payload, agent_date).values()
                ),
                "message": (
                    "暂无可用事件快照"
                    if not agent_date
                    else "已与市场同日对齐"
                    if agent_date == target_date
                    else f"知识事件日期为 {agent_date}，独立于市场日期展示"
                ),
            }
        )
        return {
            "as_of_date": target_date,
            "market": _load_market(con, target_date, statuses),
            "themes": _load_themes(
                con, target_date, agent_payload, agent_date
            ),
            "theme_axes": {
                "knowledge": list(_KNOWLEDGE_STAGES),
                "market": list(_MARKET_STAGES),
            },
            "signals": _load_signals(agent_payload, agent_date),
            "signal_date": agent_date,
            "winrate": winrate,
            "forecast_performance": forecast_performance,
            "learning_feedback": learning_feedback,
            "sellside_flow": sellside_flow,
            "sellside_date": sellside_date,
            "moneyflow": moneyflow.to_dict(),
            "moneyflow_trends": _load_moneyflow_trends(con, target_date),
            "validation": {
                "logic_effectiveness": agent_payload.get("logic_effectiveness", {}),
                "hypothesis_status": (
                    "同日可回检" if agent_date == target_date else "等待同日知识事件"
                ),
            },
            "data_status": statuses,
            "agent_artifact": (
                str(agent_path.relative_to(root)) if agent_path else None
            ),
        }
    except Exception:
        missing_response["data_status"][0]["message"] = "读取失败，保持未知状态"
        return missing_response
    finally:
        con.close()
