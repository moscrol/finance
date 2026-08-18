"""D0 盘面时序直查数据块：白名单指标的「过去 N 个交易日逐日」确定性直查。

设计（与 D1-D5 数据块同一纪律）：

- **参数化白名单查询，不开放任意 SQL**：每个指标是一条固定 SQL（或固定聚合口径），
  用户问题只能选择「指标 × 窗口」两个参数。这是把「LLM 自由取数」收敛为
  「确定性检索 + LLM 只做合成」的护城河做法——同类思路也用于 text-to-SQL 产品里
  的 semantic layer / metric store（先定义指标口径，再让模型选指标，而不是拼 SQL）。
- **意图路由用确定性正则**，不用 LLM 分类：时序取数意图（逐日/过去 N 日/时序）
  词面特征极强，正则可复核、零成本、无幻觉；LLM 分类留给词面模糊的问题类型。
- 结果表格化并带 ``[D0]`` 引用编号；缺数日显式标 ``—`` 并声明缺口，禁止外推补齐。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from intelligence.paths import default_market_db_path
from intelligence.services import retrieval_cache
from intelligence.services.metric_spec import METRICS, MetricSpec
from intelligence.services.trading_calendar import non_trading_day_note
from market_feature_store.signals import DOUBLE_RED_DESCRIPTION, DOUBLE_RED_SQL

REPO_ROOT = Path(__file__).resolve().parents[2]


DEFAULT_MARKET_DB_PATH = default_market_db_path()

DEFAULT_WINDOW = 10
MIN_WINDOW = 2
MAX_WINDOW = 60

_INTENT_TERMS = ("逐日", "每日变化", "每天变化", "逐天", "时序", "日度变化", "精确查数", "精确取数")
_WINDOW_RE = re.compile(r"(?:过去|近|最近)\s*(\d{1,3})\s*(?:个)?\s*(?:交易日|天|日)")


@dataclass(frozen=True)
class TimeseriesIntent:
    window: int
    metric_keys: tuple[str, ...]

    @property
    def metrics(self) -> list[MetricSpec]:
        return [METRICS[k] for k in self.metric_keys]


def parse_timeseries_intent(query: str) -> TimeseriesIntent | None:
    """确定性意图路由：识别「白名单指标 × 过去 N 日逐日」时序取数问题。

    触发条件（两者都要）：
    1. 时序意图词（逐日/时序/精确查数…）或显式窗口短语（过去/近 N 个交易日）；
    2. 至少命中一个白名单指标别名。
    """
    text = re.sub(r"\s+", "", str(query or ""))
    if not text:
        return None
    window_match = _WINDOW_RE.search(str(query or ""))
    has_intent = any(term in text for term in _INTENT_TERMS) or window_match is not None
    if not has_intent:
        return None
    hit_keys: list[str] = []
    claimed_spans: list[str] = []
    # 别名按长度倒序匹配，避免「涨停家数」同时把「涨停」当成第二个指标。
    alias_index = sorted(
        ((alias, spec.key) for spec in METRICS.values() for alias in spec.aliases),
        key=lambda item: len(item[0]),
        reverse=True,
    )
    remaining = text
    for alias, key in alias_index:
        if alias in remaining and key not in hit_keys:
            hit_keys.append(key)
            remaining = remaining.replace(alias, "□")
            claimed_spans.append(alias)
    if not hit_keys:
        return None
    window = DEFAULT_WINDOW
    if window_match:
        window = max(MIN_WINDOW, min(MAX_WINDOW, int(window_match.group(1))))
    ordered = [k for k in METRICS if k in hit_keys]
    return TimeseriesIntent(window=window, metric_keys=tuple(ordered))


# 「某日 X 是多少」的取值问法。和 _INTENT_TERMS（逐日/时序）分开：那是要一条曲线，
# 这是要一个数。
_POINT_VALUE_TERMS = ("多少", "几家", "几个", "几板", "是多少", "有多少")
# 要的是一份复盘而不是一个数：命中这些时不走单指标直查，仍交给 daily-review。
_REVIEW_INTENT_TERMS = (
    "复盘", "总览", "全景", "结构", "主线", "怎么样", "如何", "什么情况", "表现",
)


def parse_single_metric_intent(query: str) -> MetricSpec | None:
    """识别「指定日期 + 单一白名单指标 + 要一个数」的精确取值问题。

    这类问题此前被 is_dated_market_review 抢走送进 daily-review 工作流；当日
    日报导出不存在时，它不会退到 DuckDB 单指标查询，而是落进通用题材研究，
    甚至把问题文本当成题材名——而 fact_market_daily.limit_up 这个标准口径
    一直就在 METRICS 里。是路由层错，不是数据不存在。

    别名只从 METRICS 取，不另立词表：本仓已经因为「两条判定链各写一份词表」
    栽过一次（quick_fact 认不出「收盘价多少」）。

    命中多个指标时返回 None——那是一份小复盘，交给 daily-review 更合适。
    """
    text = re.sub(r"\s+", "", str(query or ""))
    if not text:
        return None
    if not any(term in text for term in _POINT_VALUE_TERMS):
        return None
    if any(term in text for term in _REVIEW_INTENT_TERMS):
        return None
    alias_index = sorted(
        ((alias, spec.key) for spec in METRICS.values() for alias in spec.aliases),
        key=lambda item: len(item[0]),
        reverse=True,
    )
    hit_keys: list[str] = []
    remaining = text
    for alias, key in alias_index:
        if alias in remaining and key not in hit_keys:
            hit_keys.append(key)
            remaining = remaining.replace(alias, "□")
    if len(hit_keys) != 1:
        return None
    return METRICS[hit_keys[0]]


def fetch_timeseries(
    intent: TimeseriesIntent,
    market_db_path: str | Path | None,
    *,
    on_date: str | None = None,
) -> dict[str, Any]:
    """执行白名单时序直查。

    返回 ``{"found", "dates", "values": {metric_key: {date: value}}, "warnings"}``；
    库不可用/无数据时 found=False 并带 warnings（缺口显式声明，不静默）。

    ``on_date`` 把结果锚定到某一个交易日（「2026-02-17 涨停家数多少」这类精确
    取值），而不是默认的「最近 window 个交易日」。下游全部以返回的 ``dates``
    为准，所以只需改 dates/start，SQL 无需分叉；该日无记录时照常走下面的缺口
    告警，明确说「无记录」，不静默也不改走题材检索。
    """
    db_path = Path(market_db_path).expanduser() if market_db_path else DEFAULT_MARKET_DB_PATH
    if not db_path.exists():
        return {"found": False, "dates": [], "values": {}, "warnings": [f"本地 DuckDB 不存在：{db_path}"]}
    db_result = retrieval_cache.try_connect_readonly(db_path)
    if db_result.status == "dependency_unavailable":
        return {"found": False, "dates": [], "values": {}, "warnings": ["duckdb 库不可用"]}
    if db_result.status == "open_failed":
        return {
            "found": False,
            "dates": [],
            "values": {},
            "warnings": [f"DuckDB 连接失败（{db_result.error_type or 'unknown'}）"],
        }
    con = db_result.connection
    try:
        warnings: list[str] = []
        if on_date:
            dates = [str(on_date)]
            try:
                closure = non_trading_day_note(date.fromisoformat(str(on_date)[:10]))
            except ValueError:
                closure = None
            if closure:
                warnings.append(closure.split("；")[0].strip())
        else:
            date_rows = con.execute(
                "SELECT DISTINCT trade_date FROM fact_market_daily ORDER BY trade_date DESC LIMIT ?",
                [intent.window],
            ).fetchall()
            dates = sorted(str(r[0]) for r in date_rows if r and r[0] is not None)
            if not dates:
                return {
                    "found": False,
                    "dates": [],
                    "values": {},
                    "warnings": ["fact_market_daily 无交易日数据"],
                }
        start = dates[0]
        values: dict[str, dict[str, Any]] = {}
        market_keys = [k for k in intent.metric_keys if k in {"limit_up", "limit_down", "advancers", "total_amount"}]
        if market_keys:
            cols = ", ".join(market_keys)
            rows = con.execute(
                f"SELECT trade_date, {cols} FROM fact_market_daily WHERE trade_date >= ? ORDER BY trade_date",
                [start],
            ).fetchall()
            for row in rows:
                d = str(row[0])
                for i, key in enumerate(market_keys, start=1):
                    values.setdefault(key, {})[d] = row[i]
        if "max_boards" in intent.metric_keys:
            rows = con.execute(
                "SELECT trade_date, MAX(boards) FROM fact_limit_advance_daily WHERE trade_date >= ? GROUP BY 1",
                [start],
            ).fetchall()
            values["max_boards"] = {str(r[0]): r[1] for r in rows}
        if "promotion_rate" in intent.metric_keys:
            rows = con.execute(
                """
                SELECT trade_date, MAX(promotion_rate)
                FROM fact_limit_advance_daily
                WHERE trade_date >= ? AND boards = 2 AND promotion_rate IS NOT NULL
                GROUP BY 1
                """,
                [start],
            ).fetchall()
            values["promotion_rate"] = {str(r[0]): r[1] for r in rows}
        if "double_red_count" in intent.metric_keys:
            rows = con.execute(
                f"""
                SELECT trade_date, COUNT(*)
                FROM fact_sector_daily
                WHERE trade_date >= ? AND {DOUBLE_RED_SQL}
                GROUP BY 1
                """,
                [start],
            ).fetchall()
            found_dates = {str(r[0]): r[1] for r in rows}
            # 双红数=0 与「该日板块数据缺失」必须区分：有板块行才敢写 0。
            covered_rows = con.execute(
                "SELECT trade_date, COUNT(*) FROM fact_sector_daily WHERE trade_date >= ? GROUP BY 1",
                [start],
            ).fetchall()
            covered = {str(r[0]) for r in covered_rows if r[1]}
            values["double_red_count"] = {
                d: found_dates.get(d, 0 if d in covered else None) for d in dates
            }
        for key in intent.metric_keys:
            spec = METRICS[key]
            missing = [d for d in dates if values.get(key, {}).get(d) is None]
            if missing:
                warnings.append(f"{spec.label}缺口：{('、'.join(missing))} 无记录（{spec.caliber}），已以 — 标注")
        return {"found": True, "dates": dates, "values": values, "warnings": warnings}
    except Exception as exc:
        return {"found": False, "dates": [], "values": {}, "warnings": [f"时序直查失败：{exc}"]}
    finally:
        try:
            con.close()
        except Exception:
            pass


def _fmt_cell(key: str, value: Any) -> str:
    if value is None:
        return "—"
    if key == "total_amount":
        try:
            return f"{float(value):.0f}"
        except (TypeError, ValueError):
            return str(value)
    return str(value)


def timeseries_block_for_llm(
    intent: TimeseriesIntent,
    market_db_path: str | Path | None,
    *,
    on_date: str | None = None,
) -> str:
    """把时序直查结果渲染成带 [D0] 引用编号的确定性数据块（空串=未取到）。"""
    fetched = fetch_timeseries(intent, market_db_path, on_date=on_date)
    if not fetched["found"]:
        return ""
    dates: list[str] = fetched["dates"]
    values: dict[str, dict[str, Any]] = fetched["values"]
    specs = intent.metrics
    lines = ["## 盘面时序直查数据块 [D0]"]
    lines.append(
        f"- 查询口径：过去 {len(dates)} 个交易日（{dates[0]} ~ {dates[-1]}），"
        "本地 DuckDB market_feature_store 白名单指标参数化直查，非 LLM 生成。"
    )
    for spec in specs:
        lines.append(f"- {spec.label}口径：{spec.caliber}" + (f"，单位 {spec.unit}" if spec.unit else ""))
    header = "| 交易日 | " + " | ".join(s.label for s in specs) + " |"
    sep = "|" + "---|" * (len(specs) + 1)
    lines.append("")
    lines.append(header)
    lines.append(sep)
    for d in dates:
        cells = [_fmt_cell(s.key, values.get(s.key, {}).get(d)) for s in specs]
        lines.append(f"| {d} | " + " | ".join(cells) + " |")
    lines.append("")
    for w in fetched["warnings"]:
        lines.append(f"- 数据缺口：{w}")
    lines.append(
        "- 使用要求：回答该类精确取数问题时必须原样引用上表数值并标注 [D0]；"
        "缺口日只能声明缺数，禁止外推、改写或用其他来源补齐。"
    )
    return "\n".join(lines)


def latest_double_red_snapshot_block_for_llm(
    market_db_path: str | Path | None,
    *,
    limit: int = 20,
) -> str:
    """Return the latest strict double-red sector list plus its metric definition.

    This is a point-in-time metric query, not a new answer route.  It reuses the
    same semantic-layer formula as the daily report so a mixed question such as
    “what is double red, and which sectors are double red now?” can bind both the
    definition and the current fact to one deterministic evidence product.
    """

    db_path = (
        Path(market_db_path).expanduser()
        if market_db_path
        else DEFAULT_MARKET_DB_PATH
    )
    if not db_path.exists():
        return ""
    try:
        con = retrieval_cache.connect_readonly(db_path)
    except Exception:
        return ""
    try:
        row = con.execute("select max(trade_date) from fact_sector_daily").fetchone()
        trade_date = str(row[0]) if row and row[0] is not None else ""
        if not trade_date:
            return ""
        rows = con.execute(
            f"""
            select sector_name, pct_chg, diff_ratio, amount
            from fact_sector_daily
            where trade_date = ? and {DOUBLE_RED_SQL}
            order by amount desc, sector_name
            limit ?
            """,
            [trade_date, max(1, min(int(limit), 50))],
        ).fetchall()
        lines = [
            "## 当前双红板块快照 [D4]",
            f"- 双红定义：{DOUBLE_RED_DESCRIPTION}",
            f"- 双红数据截至：{trade_date}；口径为 fact_sector_daily 严格条件，非模型判断。",
        ]
        if rows:
            lines.append(
                "- 当前双红板块："
                + "；".join(
                    f"{name}（涨幅 {float(pct):.2f}%，边际量 {float(diff):.2f}%，成交额 {float(amount):.2f} 亿元）"
                    for name, pct, diff, amount in rows
                )
                + "。"
            )
        else:
            lines.append("- 当前双红板块：按严格口径未检出；这表示结果为 0，不等同数据缺失。")
        return "\n".join(lines)
    except Exception:
        return ""
    finally:
        try:
            con.close()
        except Exception:
            pass
