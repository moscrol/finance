"""Bounded, read-only temporal projection of the existing daily-review archive.

One day is read from its own JSON, never from a later report's overlapping matrix.
No HTML scraping, market writes, model calls or retrospective knowledge claims.
"""
from __future__ import annotations

import math
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from intelligence.services.river_daily_review import available_dates, daily_review_snapshot
from market_feature_store.trading_days import trading_day_verdict
from intelligence.services.river_review_contract import evidence_contract

METRICS = (
    ("total_amount", "市场成交额", "亿元"),
    ("advancers_ma5", "涨家数 MA5", "家"),
    ("strength_avg_pct", "强度加权涨幅", "%"),
    ("top3_industry_ratio", "前三行业成交占比", "%"),
    ("double_red_count", "当日双红", "个"),
    ("stock_high_120d_count", "120日新高", "只"),
)
ROW_LIMIT = 80
READ_BUDGET = 24 * 1024 * 1024


def _number(value: Any) -> float | int | None:
    try:
        return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None
    except OverflowError:
        return None


def _sessions(end: date, count: int) -> tuple[list[date], bool]:
    result = []
    cursor = end
    complete = True
    for _ in range(366):
        verdict = trading_day_verdict(cursor)
        if verdict.source == "env_override":
            raise ValueError("交易日历存在强制运行覆盖，连续复盘不使用强制值推断历史交易日")
        if verdict.is_unknown:
            complete = False
            break
        if verdict.is_trading:
            result.append(cursor)
            if len(result) == count:
                break
        if cursor == date.min:
            complete = False
            break
        cursor -= timedelta(days=1)
    return list(reversed(result)), complete and len(result) == count


def _matrix_day(report: dict, mode: str, industry: str, day: str) -> dict:
    matches = [m for m in report["matrices"][mode] if m["industry"] == industry]
    matrix = matches[0] if len(matches) == 1 else None
    if not matrix or day not in matrix["dates"]:
        return {"status": "not_reported", "rows": [], "truncated": False}
    column = matrix["dates"].index(day) + 1
    rows = [{"name": row[0], "value": row[column]} for row in matrix["rows"]]
    return {"status": "available" if rows else "not_reported", "rows": rows[:ROW_LIMIT],
            "truncated": len(rows) > ROW_LIMIT, "total_rows": len(rows)}


def review_history(exports: Path, *, end: date | None = None, days: int = 20, industry: str | None = None) -> dict:
    if not 5 <= days <= 60:
        raise ValueError("连续复盘窗口需在5到60个交易日之间")
    if industry is not None and (not industry.strip() or len(industry) > 160):
        raise ValueError("行业名称无效")
    today = date.today()
    archive_dates = [d for d in available_dates(exports) if d <= today.isoformat()]
    end = end or (date.fromisoformat(archive_dates[-1]) if archive_dates else today)
    if end > today:
        raise ValueError("连续复盘不能读取未来日期")
    sessions, calendar_complete = _sessions(end, days + 1)  # One extra day for adjacent comparisons.
    if not sessions:
        raise ValueError("该区间交易日历未知；请使用单日归档，不猜测交易日")
    visible = sessions[-days:]
    budget = READ_BUDGET
    snapshots: dict[str, dict] = {}
    failures: dict[str, str] = {}
    # Newest first: when the budget is exhausted disclose earlier gaps, never silently clip.
    for session in reversed(sessions):
        day = session.isoformat()
        path = exports / f"{day}-daily-review.json"
        try:
            if path.exists():
                if path.resolve().parent != exports.resolve():
                    raise ValueError("outside archive root")
                size = path.stat().st_size
                if size > budget:
                    failures[day] = "read_budget_exceeded"
                    continue
                budget -= size
            snapshots[day] = daily_review_snapshot(exports, as_of=session, include_available_dates=False)
        except (OSError, ValueError, TypeError, KeyError, IndexError):
            failures[day] = "invalid_archive"

    industries = list(dict.fromkeys(
        name for session in reversed(visible)
        for name in (snapshots.get(session.isoformat(), {}).get("report") or {}).get("industries", [])
    ))
    chosen = industry if industry is not None else next(iter(industries), "")
    points = []
    for session in visible:
        day = session.isoformat()
        snapshot = snapshots.get(day, {})
        report = snapshot.get("report")
        point: dict[str, Any] = {
            "date": day, "status": "unavailable" if day in failures else snapshot.get("status", "missing"),
            "reason": failures.get(day), "provenance": snapshot.get("provenance"),
            "metrics": {}, "deltas": {}, "top_industries": [], "industry_rank": None,
            "industry_status": "unknown", "engines": None, "matrices": {},
            "warnings": [], "comparison_date": None,
            "detail_url": f"/api/river/daily-review?as_of={day}",
        }
        if report:
            facts = report["facts"]
            point["metrics"] = {key: _number(facts.get(key)) for key, _, _ in METRICS}
            top = facts.get("top_amount_sw_l1", [])
            # Empty/malformed lists cannot establish either a rank or an exit.
            valid_top = 0 < len(top) <= 3 and all(top) and len(set(top)) == len(top)
            point["top_industries"] = top if valid_top else []
            point["industry_rank"] = top.index(chosen) + 1 if valid_top and chosen in top else None
            point["industry_status"] = (
                "ranked" if point["industry_rank"] is not None
                else "not_in_list" if valid_top else "unknown"
            )
            point["matrices"] = {mode: _matrix_day(report, mode, chosen, day)
                                  for mode in ("double_red", "stock_highs", "limit_up")}
            engines = [e for e in report["engines"] if e["industry"] == chosen]
            if len(engines) == 1:
                e = engines[0]
                point["engines"] = {"columns": e["columns"], "rows": e["rows"][:ROW_LIMIT],
                                    "truncated": len(e["rows"]) > ROW_LIMIT, "total_rows": len(e["rows"])}
            point["warnings"] = report["warnings"] + report["diagnostics"]
            idx = sessions.index(session)
            previous = sessions[idx - 1].isoformat() if idx > 0 else None
            prior_report = (snapshots.get(previous, {}) if previous else {}).get("report")
            if prior_report:
                point["comparison_date"] = previous
                point["deltas"] = {
                    key: (_number(value - prior) if value is not None and prior is not None else None)
                    for key, _, _ in METRICS
                    for value, prior in [(point["metrics"][key], _number(prior_report["facts"].get(key)))]
                }
        points.append(point)
    return {
        "schema_version": 1, "knowledge_mode": "archived_report_not_as_known",
        "evidence_contract": evidence_contract(),
        "requested_end": end.isoformat(), "start": visible[0].isoformat(), "end": visible[-1].isoformat(),
        "requested_days": days, "calendar_complete": calendar_complete,
        "industry": chosen, "industries": industries, "points": points,
        "metrics": [{"key": k, "label": label, "unit": unit, "source_field": f"facts.{k}"} for k, label, unit in METRICS],
        "coverage": {"available": sum(p["status"] == "available" for p in points), "total": len(points)},
        "limits": {"max_days": 60, "max_rows_per_day_section": ROW_LIMIT, "max_read_bytes": READ_BUDGET},
        "notes": [
            "每个日期只读取该日归档；不从后一天的滚动矩阵回填，也不将重叠矩阵重复计数。",
            "归档是当前保存的日报版本，可能事后生成或覆盖；不是严格当时可知回放。",
            "变化值仅为相邻计划交易日同字段的算术差，不是收益率、连续信号或因果解释；百分比指标之差为百分点。",
            "使用daily-review/v1字段口径；历史公式版本未完整记录，差值仅供核对，不证明规则跨期一致。",
            "未列入榜单不等于零；空名单、空矩阵和缺归档保持未知。行业与子板块原名不做隐式合并。",
            "矩阵保留当日原值；发动机保留原列顺序。行数超限明确标记，可到同日归档查完整表。",
            "窗口内归档缺失处不计算差值；未知年份不猜交易日。",
        ],
    }
