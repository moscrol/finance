"""P4 历史有效性评估（logic effectiveness scorecard）。

当生命周期快照 / theme-candidates 历史积累后，为每条逻辑（题材）计算
历史成绩单：胜率、半衰期、最大回撤、强势股扩散率、相对强度变化、
叙事-事实偏离，以及 CAR(0,5)/CAR(0,20)。

诚实降级原则（对齐 agent.md「可降级、不静默失败」）：
- 热度类指标（胜率/半衰期/回撤/扩散/相对强度/偏离）可从 a77 已有的
  theme-candidates 历史推出，样本不足时明确标注「样本不足」而非编造。
- CAR(0,5)/CAR(0,20) 需要个股前向收益，依赖另一台 Mac 的
  market_snapshot 面板；未提供面板或前向交易日不足时返回 None 并标注
  「数据不足/未配置」，绝不从 0 编造。
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any

from intelligence.services.ask import load_theme_candidates


STATUS_OK = "已评估"
STATUS_INSUFFICIENT = "样本不足"

CAR_STATUS_OK = "已评估"
CAR_STATUS_NO_PANEL = "数据不足/未配置"

# 证据层强度排序（用于叙事-事实偏离）。
_EVIDENCE_RANK = {
    "已证伪": 0,
    "-": 1,
    "数据缺口": 1,
    "盘面触发待解释": 2,
    "新逻辑观察": 2,
    "旧逻辑待验证": 3,
    "能力栈候选": 3,
    "重点验证": 4,
    "已有事实验证": 5,
}


def build_effectiveness_scorecard(
    theme: str,
    history_rows: list[dict[str, Any]],
    *,
    return_panel: dict[str, Any] | None = None,
    forward_windows: tuple[int, ...] = (5, 20),
    min_samples: int = 3,
) -> dict[str, Any]:
    """为单题材产出历史成绩单。

    history_rows: 该题材的按日记录，每条至少含 date / priority_score /
    trigger_types / strong_stocks（名称列表），可选 evidence_status。
    return_panel: load_market_return_panel 的输出；None 表示无盘面收益面板。
    """
    rows = _clean_history(history_rows)
    sample_days = len(rows)
    base = {
        "逻辑": theme,
        "样本天数": sample_days,
        "观察窗口": [row["date"] for row in rows],
    }
    if sample_days < min_samples:
        base.update(
            {
                "状态": STATUS_INSUFFICIENT,
                "说明": f"仅 {sample_days} 个观察日（<{min_samples}），暂不给历史成绩单，避免假信号。",
                "CAR": _car_block(theme, rows, return_panel, forward_windows),
            }
        )
        return base

    priorities = [row["priority"] for row in rows]
    stock_counts = [row["stock_count"] for row in rows]

    base.update(
        {
            "状态": STATUS_OK,
            "胜率": _win_rate(priorities),
            "半衰期": _half_life(priorities),
            "最大回撤": _max_drawdown(priorities),
            "强势股扩散率": _diffusion_rate(stock_counts),
            "相对强度变化": _relative_strength_change(priorities),
            "叙事事实偏离": _narrative_fact_deviation(rows),
            "CAR": _car_block(theme, rows, return_panel, forward_windows),
        }
    )
    return base


def build_effectiveness_for_decision(
    decision: dict[str, list[dict[str, Any]]],
    history_by_theme: dict[str, list[dict[str, Any]]],
    *,
    return_panel: dict[str, Any] | None = None,
    forward_windows: tuple[int, ...] = (5, 20),
    min_samples: int = 3,
) -> None:
    """把历史成绩单挂到 decision 各 bucket 的逻辑行上。"""
    for bucket in ("old_logic_wakeup", "new_logic_candidate", "data_gap"):
        for row in decision.get(bucket, []):
            if "placeholder_market_theme" in set(row.get("data_gaps") or []):
                continue
            theme = _theme(row)
            if not theme:
                continue
            scorecard = build_effectiveness_scorecard(
                theme,
                history_by_theme.get(theme, []),
                return_panel=return_panel,
                forward_windows=forward_windows,
                min_samples=min_samples,
            )
            row["logic_effectiveness"] = scorecard
            row["历史有效性"] = scorecard


def summarize_effectiveness(decision: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """汇总当日逻辑历史成绩单概况（供 report-level summary）。"""
    evaluated = 0
    insufficient = 0
    car_available = 0
    win_rates: list[float] = []
    for bucket in ("old_logic_wakeup", "new_logic_candidate", "data_gap"):
        for row in decision.get(bucket, []):
            scorecard = row.get("logic_effectiveness")
            if not isinstance(scorecard, dict):
                continue
            if scorecard.get("状态") == STATUS_OK:
                evaluated += 1
                win = scorecard.get("胜率")
                if isinstance(win, (int, float)):
                    win_rates.append(float(win))
            else:
                insufficient += 1
            car = scorecard.get("CAR") or {}
            if isinstance(car, dict) and car.get("状态") == CAR_STATUS_OK:
                car_available += 1
    return {
        "已评估逻辑数": evaluated,
        "样本不足逻辑数": insufficient,
        "CAR可用逻辑数": car_available,
        "平均胜率": round(statistics.mean(win_rates), 3) if win_rates else None,
    }


def load_effectiveness_history(
    exports_dir: str | Path,
    dates: list[str],
    current_date: str,
    top_per_date: int | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """从 theme-candidates 导出读取各题材历史（含当日及之前）。"""
    history: dict[str, list[dict[str, Any]]] = {}
    for day in sorted(dates):
        if day > current_date:
            continue
        loaded = load_theme_candidates(exports_dir, day)
        doc = loaded.get("doc") or {}
        rows = _candidate_rows(doc)
        if top_per_date:
            rows = sorted(rows, key=lambda row: _num(row.get("priority_score")), reverse=True)[:top_per_date]
        for row in rows:
            theme = _theme(row)
            if not theme:
                continue
            history.setdefault(theme, []).append(
                {
                    "date": day,
                    "priority_score": row.get("priority_score"),
                    "trigger_types": list(row.get("trigger_types") or []),
                    "strong_stocks": _strong_stock_names(row),
                    "evidence_status": _evidence_status(row),
                }
            )
    return history


def load_market_return_panel(
    market_snapshot_dir: str | Path,
    dates: list[str],
) -> dict[str, Any]:
    """从 market_snapshot/YYYY-MM-DD.json 构建前向收益面板。

    返回 {
        "trade_dates": [...升序...],
        "returns": {date: {ts_code: pct_chg}},
        "benchmark": {date: 截面基准涨幅},
        "theme_stocks": {date: {concept: [ts_code,...]}},
    }
    缺目录 / 缺文件时返回空面板（trade_dates 为空），由 CAR 层降级。
    """
    base = Path(market_snapshot_dir).expanduser()
    returns: dict[str, dict[str, float]] = {}
    benchmark: dict[str, float] = {}
    theme_stocks: dict[str, dict[str, list[str]]] = {}
    trade_dates: list[str] = []
    for day in sorted(dates):
        doc = _read_json(base / f"{day}.json")
        if not isinstance(doc, dict):
            continue
        stocks = doc.get("strong_stocks")
        if not isinstance(stocks, list):
            continue
        day_returns: dict[str, float] = {}
        day_theme: dict[str, list[str]] = {}
        pct_values: list[float] = []
        for stock in stocks:
            if not isinstance(stock, dict):
                continue
            code = str(stock.get("stock_ts_code") or "").strip()
            if not code:
                continue
            pct = _num(stock.get("pct_chg"))
            day_returns[code] = pct
            pct_values.append(pct)
            for concept in stock.get("concepts") or []:
                name = str(concept).strip()
                if name:
                    day_theme.setdefault(name, []).append(code)
        if not day_returns:
            continue
        trade_dates.append(day)
        returns[day] = day_returns
        benchmark[day] = round(statistics.mean(pct_values), 4) if pct_values else 0.0
        theme_stocks[day] = day_theme
    return {
        "trade_dates": trade_dates,
        "returns": returns,
        "benchmark": benchmark,
        "theme_stocks": theme_stocks,
    }


def compute_car(
    panel: dict[str, Any],
    theme: str,
    anchor_date: str,
    window: int,
) -> float | None:
    """anchor_date 之后 window 个交易日内，题材成分股的累计超额收益均值。

    超额 = 个股当日 pct_chg - 当日截面基准。前向交易日不足 window 返回 None。
    """
    trade_dates = panel.get("trade_dates") or []
    if anchor_date not in trade_dates:
        return None
    idx = trade_dates.index(anchor_date)
    forward = trade_dates[idx + 1 : idx + 1 + window]
    if len(forward) < window:
        return None
    theme_stocks = panel.get("theme_stocks") or {}
    codes = theme_stocks.get(anchor_date, {}).get(theme) or []
    if not codes:
        return None
    returns = panel.get("returns") or {}
    benchmark = panel.get("benchmark") or {}
    per_stock: list[float] = []
    for code in codes:
        cumulative = 0.0
        seen = False
        for day in forward:
            day_ret = returns.get(day, {})
            if code in day_ret:
                cumulative += day_ret[code] - benchmark.get(day, 0.0)
                seen = True
        if seen:
            per_stock.append(cumulative)
    if not per_stock:
        return None
    return round(statistics.mean(per_stock), 4)


# --- 指标实现 ---------------------------------------------------------------


def _win_rate(priorities: list[float]) -> float:
    """逐日前向：次日 priority 不低于当日的占比（热度持续胜率，proxy）。"""
    pairs = list(zip(priorities, priorities[1:]))
    if not pairs:
        return 0.0
    wins = sum(1 for cur, nxt in pairs if nxt >= cur)
    return round(wins / len(pairs), 3)


def _half_life(priorities: list[float]) -> dict[str, Any]:
    """从峰值 priority 起，跌到峰值一半所需的交易日数。"""
    peak = max(priorities)
    peak_idx = priorities.index(peak)
    if peak <= 0:
        return {"交易日": None, "说明": "峰值非正，无法计算半衰期。"}
    target = peak / 2.0
    for offset, value in enumerate(priorities[peak_idx + 1 :], start=1):
        if value <= target:
            return {"交易日": offset, "说明": f"峰值 {round(peak, 2)} 后 {offset} 个交易日跌破半值。"}
    tail = len(priorities) - peak_idx - 1
    return {"交易日": None, "说明": f"观察期内（峰后 {tail} 日）未见半衰，热度尚未减半。"}


def _max_drawdown(priorities: list[float]) -> dict[str, Any]:
    """priority 序列的最大峰谷回撤（占峰值比例，热度回撤 proxy）。"""
    peak = priorities[0]
    max_dd = 0.0
    for value in priorities:
        if value > peak:
            peak = value
        if peak > 0:
            dd = (peak - value) / peak
            if dd > max_dd:
                max_dd = dd
    return {"比例": round(max_dd, 3), "口径": "priority 峰谷回撤"}


def _diffusion_rate(stock_counts: list[int]) -> dict[str, Any]:
    """强势股扩散：日均净增 + 扩散天数占比。"""
    deltas = [b - a for a, b in zip(stock_counts, stock_counts[1:])]
    expand_days = sum(1 for d in deltas if d > 0)
    return {
        "日均净增": round(statistics.mean(deltas), 3) if deltas else 0.0,
        "扩散天数占比": round(expand_days / len(deltas), 3) if deltas else 0.0,
        "区间强势股": [stock_counts[0], stock_counts[-1]],
    }


def _relative_strength_change(priorities: list[float]) -> dict[str, Any]:
    """相对强度变化：首末 priority 差 + 近段斜率方向。"""
    span = round(priorities[-1] - priorities[0], 3)
    recent = priorities[-3:]
    slope = round((recent[-1] - recent[0]) / (len(recent) - 1), 3) if len(recent) > 1 else 0.0
    direction = "走强" if span > 0 else "走弱" if span < 0 else "持平"
    return {"区间变化": span, "近段斜率": slope, "方向": direction}


def _narrative_fact_deviation(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """叙事-事实偏离：热度分位 - 证据层强度分位。正值=叙事跑在事实前面。"""
    latest = rows[-1]
    priorities = [row["priority"] for row in rows]
    peak = max(priorities) or 1.0
    heat_pct = round(latest["priority"] / peak, 3) if peak else 0.0
    status = latest.get("evidence_status") or "-"
    rank = _EVIDENCE_RANK.get(status, 1)
    evidence_pct = round(rank / max(_EVIDENCE_RANK.values()), 3)
    deviation = round(heat_pct - evidence_pct, 3)
    if deviation >= 0.4:
        flag = "叙事显著领先事实（警惕透支）"
    elif deviation <= -0.2:
        flag = "事实强于叙事（仍有预期差）"
    else:
        flag = "叙事与事实大致匹配"
    return {
        "偏离值": deviation,
        "热度分位": heat_pct,
        "证据层": status,
        "证据分位": evidence_pct,
        "判断": flag,
    }


def _car_block(
    theme: str,
    rows: list[dict[str, Any]],
    return_panel: dict[str, Any] | None,
    forward_windows: tuple[int, ...],
) -> dict[str, Any]:
    if not return_panel or not (return_panel.get("trade_dates")):
        return {
            "状态": CAR_STATUS_NO_PANEL,
            "说明": "未接入 market_snapshot 收益面板（MARKET_SNAPSHOT_DIR 未配置或无前向数据），CAR 不计算。",
        }
    anchors = [row["date"] for row in rows if row.get("triggers")]
    if not anchors:
        anchors = [row["date"] for row in rows]
    result: dict[str, Any] = {"状态": CAR_STATUS_OK, "锚点数": 0}
    any_value = False
    for window in forward_windows:
        per_anchor = [compute_car(return_panel, theme, anchor, window) for anchor in anchors]
        values = [v for v in per_anchor if v is not None]
        key = f"CAR(0,{window})"
        if values:
            any_value = True
            result[key] = round(statistics.median(values), 4)
        else:
            result[key] = None
        result["锚点数"] = max(result["锚点数"], len(values))
    if not any_value:
        return {
            "状态": CAR_STATUS_NO_PANEL,
            "说明": "面板存在但锚点前向交易日不足或题材无成分股映射，CAR 不计算。",
        }
    return result


# --- 解析辅助 ---------------------------------------------------------------


def _clean_history(history_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for row in sorted(history_rows, key=lambda item: str(item.get("date") or "")):
        date = str(row.get("date") or "").strip()
        if not date:
            continue
        cleaned.append(
            {
                "date": date,
                "priority": _num(row.get("priority_score")),
                "stock_count": len(row.get("strong_stocks") or []),
                "triggers": list(row.get("trigger_types") or []),
                "evidence_status": row.get("evidence_status"),
            }
        )
    return cleaned


def _candidate_rows(doc: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(doc.get("candidates"), list):
        return [row for row in doc["candidates"] if isinstance(row, dict)]
    rows: list[dict[str, Any]] = []
    for key in ("deep_candidates", "watch_candidates", "long_tail_candidates"):
        rows.extend(row for row in doc.get(key, []) or [] if isinstance(row, dict))
    return rows


def _strong_stock_names(row: dict[str, Any]) -> list[str]:
    evidence = row.get("market_evidence") if isinstance(row.get("market_evidence"), dict) else {}
    stocks = evidence.get("strong_stocks") if isinstance(evidence, dict) else []
    names: list[str] = []
    for stock in stocks or []:
        if isinstance(stock, dict):
            name = str(stock.get("stock_name") or stock.get("name") or "").strip()
            if name:
                names.append(name)
    return names


def _evidence_status(row: dict[str, Any]) -> str:
    judgment = row.get("research_judgment") if isinstance(row.get("research_judgment"), dict) else {}
    return str(judgment.get("证据状态") or "-")


def _theme(row: dict[str, Any]) -> str:
    return str(row.get("query") or row.get("concept") or row.get("逻辑") or "").strip()


def _num(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
