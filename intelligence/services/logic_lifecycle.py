from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any

from intelligence.services import checkpoints as checkpoints_svc
from intelligence.services.ask import load_theme_candidates


STAGE_NEW = "新出现"
STAGE_WAKEUP = "旧逻辑唤醒"
STAGE_WARMING = "升温验证"
STAGE_ACCELERATING = "加速定价"
STAGE_DIVERGING = "高位分歧"
STAGE_DECLINING = "衰退观察"
STAGE_EXIT = "证伪退出"


def build_lifecycle_snapshot(current: dict[str, Any], history_rows: list[dict[str, Any]]) -> dict[str, Any]:
    history = sorted(history_rows, key=lambda row: str(row.get("date") or ""))
    target = _theme(current)
    previous = history[-1] if history else None
    continuous_days = _continuous_days(current, history)
    priority_delta = _round_delta(_priority(current), _priority(previous)) if previous else 0.0
    stock_delta = _stock_count(current) - _stock_count(previous) if previous else 0
    trigger_delta = (
        len(set(current.get("trigger_types") or [])) - len(set((previous or {}).get("trigger_types") or []))
        if previous
        else 0
    )
    old_material_hit = _old_material_hit(current) or any(_old_material_hit(row) for row in history)
    judgment_status = str((current.get("research_judgment") or {}).get("证据状态") or "-")

    stage, stage_change = _stage(current, history, priority_delta, stock_delta, trigger_delta, old_material_hit, judgment_status, continuous_days)
    reason = _reason(stage, continuous_days, priority_delta, stock_delta, trigger_delta, old_material_hit, judgment_status)
    next_action = _next_action(stage, judgment_status)

    return {
        "逻辑": target,
        "生命周期阶段": stage,
        "阶段变化": stage_change,
        "变化原因": reason,
        "观察窗口": [row.get("date") for row in history] + [current.get("date")],
        "连续出现天数": continuous_days,
        "priority变化": priority_delta,
        "强势股变化": stock_delta,
        "触发信号变化": trigger_delta,
        "旧材料命中": bool(old_material_hit),
        "证据状态": judgment_status,
        "当前priority": _priority(current),
        "当前强势股数": _stock_count(current),
        "当前触发信号": list(current.get("trigger_types") or []),
        "下一步": next_action,
    }


CHECKPOINT_CATEGORY = "生命周期推演"
CHECKPOINT_SOURCE = "logic_lifecycle"

# 带前瞻判断的阶段 → (可证伪陈述, 回检窗口天数)。
# 只有对未来有明确预期的阶段才登记；「新出现/衰退观察/证伪退出」无前瞻判断不登记。
_CHECKPOINT_SPECS: dict[str, tuple[str, int]] = {
    STAGE_WAKEUP: ("旧逻辑唤醒将获得新证据支撑（L2/L3 缺口被补上）", 5),
    STAGE_WARMING: ("升温将获得事实支撑（登记后出现新证据）", 5),
    STAGE_ACCELERATING: ("加速定价将有 L3 持续性验证跟上", 3),
    STAGE_DIVERGING: ("高位分歧期证据仍在新增（否则转入衰退观察）", 3),
}


def register_lifecycle_checkpoints(
    decision: dict[str, list[dict[str, Any]]],
    *,
    date: str,
    checkpoints_path: str | Path,
    session_id: str | None = None,
) -> list[dict[str, Any]]:
    """把带前瞻判断的生命周期阶段登记成可证伪点（幂等：同 claim+due 跳过）。

    与 framework_interpretation.register_judgments 同一套台账口径；
    metric 用 kb_evidence（登记后该题材是否出现新证据），缺数时 resolver 优雅降级。
    """
    existing, _ = checkpoints_svc.load_checkpoints(checkpoints_path)
    seen = {(str(r.get("claim") or ""), str(r.get("due") or "")) for r in existing}
    added: list[dict[str, Any]] = []
    for bucket in ("old_logic_wakeup", "new_logic_candidate", "data_gap"):
        for row in decision.get(bucket, []) or []:
            lifecycle = row.get("logic_lifecycle") or {}
            stage = str(lifecycle.get("生命周期阶段") or "")
            spec = _CHECKPOINT_SPECS.get(stage)
            theme = _theme(row)
            if not spec or not theme:
                continue
            statement, window = spec
            due = _due_date(date, window)
            if not due:
                continue
            claim = f"[{date}][{stage}] {theme}：{statement}"
            if (claim, due) in seen:
                continue
            _, record = checkpoints_svc.register_checkpoint(
                checkpoints_path,
                claim=claim,
                due=due,
                category=CHECKPOINT_CATEGORY,
                source=CHECKPOINT_SOURCE,
                themes=[theme],
                metric={"type": "kb_evidence", "op": ">=", "target": 1, "target_name": theme},
                session_id=session_id,
            )
            seen.add((claim, due))
            added.append(record)
    return added


def _due_date(value: str, days: int) -> str | None:
    day = _parse_date(value)
    return (day + timedelta(days=days)).isoformat() if day else None


def build_lifecycle_for_decision(
    decision: dict[str, list[dict[str, Any]]],
    history_by_theme: dict[str, list[dict[str, Any]]],
) -> None:
    for bucket in ("old_logic_wakeup", "new_logic_candidate", "data_gap"):
        for row in decision.get(bucket, []):
            if "placeholder_market_theme" in set(row.get("data_gaps") or []):
                continue
            row["logic_lifecycle"] = build_lifecycle_snapshot(row, history_by_theme.get(_theme(row), []))


def load_theme_history(
    exports_dir: str | Path,
    dates: list[str],
    current_date: str,
    top_per_date: int | None = None,
) -> dict[str, list[dict[str, Any]]]:
    history: dict[str, list[dict[str, Any]]] = {}
    for day in dates:
        if day >= current_date:
            continue
        loaded = load_theme_candidates(exports_dir, day)
        doc = loaded.get("doc") or {}
        rows = _candidate_rows(doc)
        if top_per_date:
            rows = sorted(rows, key=lambda row: float(row.get("priority_score") or 0), reverse=True)[:top_per_date]
        for row in rows:
            theme = _theme(row)
            if not theme:
                continue
            history.setdefault(theme, []).append(_candidate_to_history_row(row, day))
    return history


def _candidate_rows(doc: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(doc.get("candidates"), list):
        return [row for row in doc["candidates"] if isinstance(row, dict)]
    rows: list[dict[str, Any]] = []
    for key in ("deep_candidates", "watch_candidates", "long_tail_candidates"):
        rows.extend(row for row in doc.get(key, []) or [] if isinstance(row, dict))
    return rows


def _candidate_to_history_row(row: dict[str, Any], day: str) -> dict[str, Any]:
    return {
        "query": _theme(row),
        "date": day,
        "priority_score": row.get("priority_score"),
        "trigger_types": list(row.get("trigger_types") or []),
        "strong_stocks": _candidate_strong_stock_names(row),
    }


def _candidate_strong_stock_names(row: dict[str, Any]) -> list[str]:
    market_evidence = row.get("market_evidence") if isinstance(row.get("market_evidence"), dict) else {}
    stocks = market_evidence.get("strong_stocks") if isinstance(market_evidence, dict) else []
    names: list[str] = []
    for stock in (stocks or [])[:5]:
        if isinstance(stock, dict):
            name = str(stock.get("stock_name") or stock.get("name") or "").strip()
            if name:
                names.append(name)
    return names


def _stage(
    current: dict[str, Any],
    history: list[dict[str, Any]],
    priority_delta: float,
    stock_delta: int,
    trigger_delta: int,
    old_material_hit: bool,
    judgment_status: str,
    continuous_days: int,
) -> tuple[str, str]:
    if not history:
        if old_material_hit or judgment_status in {"旧逻辑待验证", "能力栈候选", "重点验证", "已有事实验证"}:
            return STAGE_WAKEUP, "旧材料唤醒"
        return STAGE_NEW, "首次进入观察"
    if _has_exit_signal(current, judgment_status):
        return STAGE_EXIT, "证伪退出"
    if priority_delta <= -20 and stock_delta < 0:
        return STAGE_DECLINING, "热度衰退"
    if continuous_days >= 3 and priority_delta > 0 and stock_delta >= 0 and trigger_delta >= 0:
        if judgment_status in {"重点验证", "已有事实验证"} and priority_delta >= 20:
            return STAGE_ACCELERATING, "加速定价"
        return STAGE_WARMING, "连续升温"
    if continuous_days >= 2 and priority_delta > 0 and (stock_delta < 0 or trigger_delta < 0):
        return STAGE_DIVERGING, "高位分歧"
    if old_material_hit:
        return STAGE_WAKEUP, "沉睡后唤醒"
    if priority_delta < 0 and stock_delta <= 0:
        return STAGE_DIVERGING, "高位分歧"
    return STAGE_WAKEUP if old_material_hit else STAGE_WARMING, "持续观察"


def _reason(
    stage: str,
    continuous_days: int,
    priority_delta: float,
    stock_delta: int,
    trigger_delta: int,
    old_material_hit: bool,
    judgment_status: str,
) -> str:
    parts: list[str] = []
    if continuous_days <= 1 and stage == STAGE_NEW:
        parts.append("过去窗口未出现，今天首次进入候选。")
    elif continuous_days <= 1 and stage == STAGE_WAKEUP:
        parts.append("过去窗口未出现，但旧材料或证据已命中，属于旧逻辑重新触发。")
    else:
        parts.append(f"连续 {continuous_days} 日出现。")
    if priority_delta > 0:
        parts.append(f"priority 上升 {priority_delta:g}。")
    elif priority_delta < 0:
        parts.append(f"priority 下降 {abs(priority_delta):g}。")
    if stock_delta > 0:
        parts.append(f"强势股增加 {stock_delta} 只。")
    elif stock_delta < 0:
        parts.append(f"强势股减少 {abs(stock_delta)} 只。")
    if trigger_delta > 0:
        parts.append(f"触发信号增加 {trigger_delta} 类。")
    elif trigger_delta < 0:
        parts.append(f"触发信号减少 {abs(trigger_delta)} 类。")
    if old_material_hit:
        parts.append("旧材料命中，说明不是纯新故事。")
    if judgment_status and judgment_status != "-":
        parts.append(f"证据裁判为{judgment_status}。")
    return "".join(parts)


def _next_action(stage: str, judgment_status: str) -> str:
    if stage == STAGE_NEW:
        return "先确认题材边界和公司暴露，必要时做 IMA 或 front-map。"
    if stage == STAGE_WAKEUP:
        return "优先检查旧逻辑是否有 L2/L3 缺口，再判断是不是有效唤醒。"
    if stage == STAGE_WARMING:
        if judgment_status in {"能力栈候选", "重点验证", "旧逻辑待验证"}:
            return "优先找公告/调研/订单/客户验证，确认升温是否有事实支撑。"
        return "观察强势股扩散和成交边际，确认升温是否持续。"
    if stage == STAGE_ACCELERATING:
        return "进入重点跟踪，检查是否已有充分 L3，并等待 L4 持续性验证。"
    if stage == STAGE_DIVERGING:
        return "进入分歧观察，关注回撤、扩散减弱和证据是否继续新增。"
    if stage == STAGE_DECLINING:
        return "热度下降，降级观察；除非出现新 L3 事实或盘面重新扩散，否则不追加研究投入。"
    if stage == STAGE_EXIT:
        return "移出队列或标记证伪，后续只保留复盘记录。"
    return "人工复核生命周期状态。"


def _continuous_days(current: dict[str, Any], history: list[dict[str, Any]]) -> int:
    current_day = _parse_date(current.get("date"))
    if not current_day:
        return 1 if current else 0
    dates = {_parse_date(row.get("date")) for row in history}
    count = 1
    probe = current_day - timedelta(days=1)
    while probe in dates:
        count += 1
        probe -= timedelta(days=1)
    return count


def _theme(row: dict[str, Any]) -> str:
    return str(row.get("query") or row.get("canonical_concept") or row.get("market_theme") or row.get("matched_theme") or "").strip()


def _priority(row: dict[str, Any] | None) -> float:
    if not row:
        return 0.0
    try:
        return round(float(row.get("priority_score") or 0.0), 2)
    except (TypeError, ValueError):
        return 0.0


def _round_delta(current: float, previous: float) -> float:
    return round(current - previous, 2)


def _stock_count(row: dict[str, Any] | None) -> int:
    if not row:
        return 0
    stocks = row.get("strong_stocks") or []
    return len(stocks) if isinstance(stocks, list) else 0


def _old_material_hit(row: dict[str, Any]) -> bool:
    return bool(row.get("semantic_hits") or row.get("semantic_old_material_hit"))


def _has_exit_signal(current: dict[str, Any], judgment_status: str) -> bool:
    text = " ".join(str(value) for value in [judgment_status, current.get("route"), current.get("next_actions")] if value)
    return "证伪" in text or "移出" in text


def _parse_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
