from __future__ import annotations

from pathlib import Path
from typing import Any

from intelligence.services.ask import load_theme_candidates


VALIDATION_STRONG = "强验证"
VALIDATION_MEDIUM = "中等验证"
VALIDATION_WEAK = "弱验证"
VALIDATION_NONE = "无盘面验证"


def build_market_validation_snapshot(current: dict[str, Any] | None, history_rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not current:
        return {
            "盘面验证强度": VALIDATION_NONE,
            "验证结论": "未进入当日盘面候选，暂无 L4 盘面验证。",
            "当前盘面": {},
            "边际变化": {},
            "关键触发": [],
            "强势股": [],
            "下一步": "等待下一次盘面触发或补充市场快照。",
        }

    history = sorted(history_rows, key=lambda row: str(row.get("trade_date") or row.get("date") or ""))
    previous = history[-1] if history else None
    current_metrics = _metrics(current)
    previous_metrics = _metrics(previous) if previous else {}
    changes = _changes(current_metrics, previous_metrics) if previous else _empty_changes()
    strength = _strength(current_metrics)
    conclusion = _conclusion(strength, current_metrics, changes, has_previous=bool(previous))
    return {
        "盘面验证强度": strength,
        "验证结论": conclusion,
        "当前盘面": current_metrics,
        "边际变化": changes,
        "关键触发": list(current.get("trigger_types") or []),
        "强势股": _strong_stock_summaries(current),
        "下一步": _next_action(strength),
    }


def build_market_validation_for_decision(
    decision: dict[str, list[dict[str, Any]]],
    current_by_theme: dict[str, dict[str, Any]],
    history_by_theme: dict[str, list[dict[str, Any]]],
) -> None:
    for bucket in ("old_logic_wakeup", "new_logic_candidate", "data_gap"):
        for row in decision.get(bucket, []):
            if "placeholder_market_theme" in set(row.get("data_gaps") or []):
                continue
            theme = _theme(row)
            row["market_validation"] = build_market_validation_snapshot(
                current_by_theme.get(theme),
                history_by_theme.get(theme, []),
            )
            row["盘面验证"] = row["market_validation"]


def load_market_validation_context(
    exports_dir: str | Path,
    dates: list[str],
    current_date: str,
    top_per_date: int | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    current_by_theme: dict[str, dict[str, Any]] = {}
    history_by_theme: dict[str, list[dict[str, Any]]] = {}
    for day in dates:
        loaded = load_theme_candidates(exports_dir, day)
        doc = loaded.get("doc") or {}
        rows = _candidate_rows(doc)
        if top_per_date:
            rows = sorted(rows, key=lambda row: float(row.get("priority_score") or 0), reverse=True)[:top_per_date]
        for row in rows:
            theme = _theme(row)
            if not theme:
                continue
            enriched = dict(row)
            enriched.setdefault("trade_date", day)
            if day == current_date:
                current_by_theme[theme] = enriched
            elif day < current_date:
                history_by_theme.setdefault(theme, []).append(enriched)
    return current_by_theme, history_by_theme


def _candidate_rows(doc: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(doc.get("candidates"), list):
        return [row for row in doc["candidates"] if isinstance(row, dict)]
    rows: list[dict[str, Any]] = []
    for key in ("deep_candidates", "watch_candidates", "long_tail_candidates"):
        rows.extend(row for row in doc.get(key, []) or [] if isinstance(row, dict))
    return rows


def _metrics(row: dict[str, Any] | None) -> dict[str, Any]:
    if not row:
        return {}
    evidence = row.get("market_evidence") if isinstance(row.get("market_evidence"), dict) else {}
    sector = evidence.get("sector_metrics") if isinstance(evidence.get("sector_metrics"), dict) else {}
    limit_heat = evidence.get("limit_heat") if isinstance(evidence.get("limit_heat"), dict) else {}
    high = evidence.get("new_high_direction") if isinstance(evidence.get("new_high_direction"), dict) else {}
    strong_stocks = evidence.get("strong_stocks") if isinstance(evidence.get("strong_stocks"), list) else []
    triggers = list(row.get("trigger_types") or [])
    return {
        "priority": _num(row.get("priority_score")),
        "触发信号数": len(set(triggers)),
        "涨停数": int(_num(limit_heat.get("limit_up_count")) or 0),
        "新高数": int(_num(high.get("high_count")) or 0),
        "强势股数": len(strong_stocks),
        "板块涨幅": _num(sector.get("pct_chg")),
        "边际量": _num(sector.get("diff_ratio")),
        "成交额": _num(sector.get("amount")),
        "容量前三": bool(sector.get("in_capacity_top3") or high.get("in_capacity_top3")),
    }


def _changes(current: dict[str, Any], previous: dict[str, Any]) -> dict[str, Any]:
    return {
        "priority变化": _delta(current.get("priority"), previous.get("priority")),
        "触发信号变化": int(current.get("触发信号数") or 0) - int(previous.get("触发信号数") or 0),
        "涨停变化": int(current.get("涨停数") or 0) - int(previous.get("涨停数") or 0),
        "新高变化": int(current.get("新高数") or 0) - int(previous.get("新高数") or 0),
        "强势股变化": int(current.get("强势股数") or 0) - int(previous.get("强势股数") or 0),
    }


def _empty_changes() -> dict[str, Any]:
    return {
        "priority变化": 0.0,
        "触发信号变化": 0,
        "涨停变化": 0,
        "新高变化": 0,
        "强势股变化": 0,
    }


def _strength(metrics: dict[str, Any]) -> str:
    priority = float(metrics.get("priority") or 0)
    trigger_count = int(metrics.get("触发信号数") or 0)
    limit_up = int(metrics.get("涨停数") or 0)
    high_count = int(metrics.get("新高数") or 0)
    strong_count = int(metrics.get("强势股数") or 0)
    capacity = bool(metrics.get("容量前三"))
    if priority >= 150 or (limit_up >= 5 and high_count >= 5) or (capacity and trigger_count >= 4):
        return VALIDATION_STRONG
    if priority >= 80 or limit_up >= 2 or high_count >= 3 or strong_count >= 3 or trigger_count >= 2:
        return VALIDATION_MEDIUM
    if priority > 0 or trigger_count > 0 or strong_count > 0:
        return VALIDATION_WEAK
    return VALIDATION_NONE


def _momentum(changes: dict[str, Any], has_previous: bool) -> str:
    if not has_previous:
        return ""
    delta = float(changes.get("priority变化") or 0)
    limit_delta = int(changes.get("涨停变化") or 0)
    high_delta = int(changes.get("新高变化") or 0)
    if delta <= -30:
        detail = []
        if limit_delta < 0:
            detail.append(f"涨停减 {abs(limit_delta)} 只")
        if high_delta < 0:
            detail.append(f"新高减 {abs(high_delta)} 只")
        suffix = f"（{'、'.join(detail)}）" if detail else ""
        return f"但优先级较前一日回落 {abs(delta):g}{suffix}，边际动能在衰减"
    if delta >= 30:
        return f"且优先级较前一日抬升 {delta:g}，边际动能在增强"
    return "优先级较前一日大体持平"


def _conclusion(strength: str, metrics: dict[str, Any], changes: dict[str, Any], has_previous: bool) -> str:
    prefix = "" if has_previous else "当前首次进入观察窗口，"
    momentum = _momentum(changes, has_previous)
    momentum_text = f"；{momentum}" if momentum else ""
    if strength == VALIDATION_STRONG:
        return (
            f"{prefix}多信号共振，盘面给出较强 L4 验证（涨停 {metrics.get('涨停数', 0)} 只，"
            f"新高 {metrics.get('新高数', 0)} 只）{momentum_text}。"
        )
    if strength == VALIDATION_MEDIUM:
        return (
            f"{prefix}有盘面信号，但扩散强度或持续性还需要继续观察（触发"
            f" {metrics.get('触发信号数', 0)} 类，强势股 {metrics.get('强势股数', 0)} 只）"
            f"{momentum_text}。"
        )
    if strength == VALIDATION_WEAK:
        return f"{prefix}有零星盘面信号，但扩散不足，暂不能证明逻辑被系统性重定价。"
    return "没有有效盘面候选，暂不构成 L4 验证。"


def _strong_stock_summaries(row: dict[str, Any]) -> list[str]:
    evidence = row.get("market_evidence") if isinstance(row.get("market_evidence"), dict) else {}
    stocks = evidence.get("strong_stocks") if isinstance(evidence.get("strong_stocks"), list) else []
    out: list[str] = []
    for stock in stocks[:5]:
        if not isinstance(stock, dict):
            continue
        name = str(stock.get("stock_name") or stock.get("name") or "").strip()
        if not name:
            continue
        pct = stock.get("pct_chg")
        amount = stock.get("amount")
        high = stock.get("high_status_label") or "-"
        parts = [name]
        if pct is not None:
            parts.append(f"涨幅{_num(pct):g}%")
        if amount is not None:
            parts.append(f"成交{_num(amount):g}亿")
        if high != "-":
            parts.append(str(high))
        out.append("｜".join(parts))
    return out


def _next_action(strength: str) -> str:
    if strength == VALIDATION_STRONG:
        return "优先跟踪是否继续扩散，并要求证据层同步升级。"
    if strength == VALIDATION_MEDIUM:
        return "继续观察强势股扩散、成交边际和下一日是否延续。"
    if strength == VALIDATION_WEAK:
        return "暂不因单日脉冲升级，等待更多盘面或事实验证。"
    return "等待盘面重新触发。"


def _theme(row: dict[str, Any]) -> str:
    return str(row.get("query") or row.get("canonical_concept") or row.get("market_theme") or row.get("matched_theme") or "").strip()


def _num(value: Any) -> float:
    try:
        return round(float(value or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def _delta(current: Any, previous: Any) -> float:
    return round(float(current or 0) - float(previous or 0), 2)
