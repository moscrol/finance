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
from pathlib import Path
from typing import Any

from intelligence.services import retrieval_cache

from market_feature_store.signals import DOUBLE_RED_SQL

REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_WINDOW = 10
MIN_WINDOW = 2
MAX_WINDOW = 60


@dataclass(frozen=True)
class MetricSpec:
    key: str
    label: str
    unit: str
    aliases: tuple[str, ...]
    caliber: str  # 口径说明（进入数据块，供合成与人工核对）


# 白名单指标注册表。新增指标只允许在这里登记（key → 固定查询口径），
# 不允许把用户问题文本拼进 SQL。
METRICS: dict[str, MetricSpec] = {
    "limit_up": MetricSpec(
        "limit_up", "涨停家数", "家", ("涨停家数", "涨停数", "涨停"),
        "fact_market_daily.limit_up",
    ),
    "limit_down": MetricSpec(
        "limit_down", "跌停家数", "家", ("跌停家数", "跌停数", "跌停"),
        "fact_market_daily.limit_down",
    ),
    "advancers": MetricSpec(
        "advancers", "涨家数", "家", ("涨家数", "上涨家数", "涨跌家数"),
        "fact_market_daily.advancers",
    ),
    "total_amount": MetricSpec(
        "total_amount", "全市成交额", "亿元", ("全市成交额", "成交额", "总成交", "成交量"),
        "fact_market_daily.total_amount（亿元）",
    ),
    "max_boards": MetricSpec(
        "max_boards", "连板最高高度", "板", ("连板高度", "连板最高", "最高板", "最高连板", "连板"),
        "fact_limit_advance_daily 当日 max(boards)",
    ),
    "promotion_rate": MetricSpec(
        "promotion_rate", "首板晋级率", "", ("晋级率", "晋级"),
        "fact_limit_advance_daily 当日 boards=2 行携带的首板→2板晋级率原文",
    ),
    "double_red_count": MetricSpec(
        "double_red_count", "双红板块数", "个", ("双红板块", "双红题材", "双红"),
        f"fact_sector_daily 当日满足 {DOUBLE_RED_SQL} 的板块数（严格双红定义）",
    ),
}

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


def fetch_timeseries(
    intent: TimeseriesIntent,
    market_db_path: str | Path | None,
) -> dict[str, Any]:
    """执行白名单时序直查。

    返回 ``{"found", "dates", "values": {metric_key: {date: value}}, "warnings"}``；
    库不可用/无数据时 found=False 并带 warnings（缺口显式声明，不静默）。
    """
    db_path = Path(market_db_path).expanduser() if market_db_path else REPO_ROOT / "db" / "market_feature_store.duckdb"
    if not db_path.exists():
        return {"found": False, "dates": [], "values": {}, "warnings": [f"本地 DuckDB 不存在：{db_path}"]}
    try:
        import duckdb  # type: ignore
    except Exception:
        return {"found": False, "dates": [], "values": {}, "warnings": ["duckdb 库不可用"]}
    try:
        con = retrieval_cache.connect_readonly(db_path)
    except Exception as exc:
        return {"found": False, "dates": [], "values": {}, "warnings": [f"DuckDB 连接失败：{exc}"]}
    try:
        date_rows = con.execute(
            "SELECT DISTINCT trade_date FROM fact_market_daily ORDER BY trade_date DESC LIMIT ?",
            [intent.window],
        ).fetchall()
        dates = sorted(str(r[0]) for r in date_rows if r and r[0] is not None)
        if not dates:
            return {"found": False, "dates": [], "values": {}, "warnings": ["fact_market_daily 无交易日数据"]}
        start = dates[0]
        values: dict[str, dict[str, Any]] = {}
        warnings: list[str] = []
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
) -> str:
    """把时序直查结果渲染成带 [D0] 引用编号的确定性数据块（空串=未取到）。"""
    fetched = fetch_timeseries(intent, market_db_path)
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
