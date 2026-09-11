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
from intelligence.services import reading_baseline, retrieval_cache
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
    lines.extend(reading_baseline.block_rule_lines("D0"))
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


# --------------------------------------------------------------------------- #
# D18 涨停封板时间数据块（W5 / G1a 接线）
#
# 为什么单开一块：`fact_theme_limit_stock_daily.first_limit_time /
# last_limit_time` 累计 14.9 万行非空，但此前 **ask 应答链**（ask / ask_synthesis /
# evidence_*）无一处引用——消费方是 skills、报表，以及 `river.py` 与
# `teaching_framework/{coverage,leader_succession}.py`（后两者在主干就有，别据此
# 断言「services 无一处引用」）。数据在库里，agent 面前没有。
# 这就是 reading-rules-inventory §5 的 G1a：「有封板时间但无块输出」。
#
# ⚠ 为什么有第二个源（2026-09-11 查清，此前一版注释把原因写错了，勿沿用）
#
# 现象：`first_limit_time` 到 2026-09-02 逐日 100% 非空，09-03 起连续 5 个交易日
# 全 NULL 而行照常进——「行在、值全 NULL」的空壳，只数行数抓不到。
#
# 但**这不是上游断供，是换了写入方**。`source` 列直接点名：09-02 及以前是
# `fupanhui:watchlist/limit-distribution/stocks`，09-03 起是 `local:limit-rule`。
# 后者是 `compute_local_stats.py` 的本地自算链路（fupanhui 账号风控后的生产链路，
# 见 consumption_registry 的 `local` 计划），按设计只写 12 列——封板时点属
# **盘中事实**，从日线 OHLCV 推不出来，它结构上就产不出。同批归零的有 22 列。
# 所以：不需要外呼比对 payload 字段名，答案在仓里。风控期间 fupanhui 那半会一直空。
#
# 替代源：`fact_limit_pool_hithink`（同花顺官方涨停池，工单 #41）。按 pool 分区，
# `limit_up` 池的 `limit_up_time` 100% 非空，历史回到 2020-07。2026-09-02（两源都
# 有的日子）交叉验证：49 只交集**逐只到分钟全部一致**，hithink 是 fupanhui 的完整
# 子集（fupanhui 多 3 只）。故本块 fupanhui 无读数时回落到它，并在块里自报换了源。
# 注意分区语义：`limit_up` 与 `limit_break` 两池**互斥**，`open_times` 只描述
# 「炸了没回封」的票，不等于「涨停票盘中开过几次板」。
#
# G1b 仍未解决，SPT-A06 仍留 _PENDING_RULES。SPT-A06（秒板未换手则后排无价值）
# 要的是涨停票的换手充分与否：fupanhui 的 `open_times` 15.2 万行恒 NULL；hithink
# 有 `turnover_ratio_pct` 列但**实测 0% 填充**（又一根空壳柱子，别再以为它能用）。
# 故这里不调 `reading_baseline.block_rule_lines("D18")`——没有规则可挂，挂了就是把
# 模型拿不到输入的判读注入进去。
# --------------------------------------------------------------------------- #

_SEAL_TERMS = ("封板", "秒板", "打板", "一字板", "首封", "炸板", "回封")
_SEAL_PAIR_RE = re.compile(
    r"涨停.{0,6}(?:时间|节奏|梯队|结构|先后|顺序|后排|换手)"
    r"|(?:时间|节奏|梯队|先后|顺序).{0,6}涨停"
)


def parse_limit_seal_intent(query: str) -> bool:
    """封板时序意图：词面特征强，确定性正则即可，不用 LLM 分类（同 D0 纪律）。"""
    q = str(query or "")
    if not q.strip():
        return False
    if any(term in q for term in _SEAL_TERMS):
        return True
    return bool(_SEAL_PAIR_RE.search(q))


def _fmt_seal_time(raw: Any) -> str:
    """原始 HHMMSS（如 ``100031`` / ``93000``）→ ``10:00:31``；非法值原样透出。"""
    text = str(raw or "").strip()
    if not text:
        return "—"
    if not text.isdigit() or len(text) > 6:
        return text
    padded = text.zfill(6)
    return f"{padded[0:2]}:{padded[2:4]}:{padded[4:6]}"


def limit_seal_time_block_for_llm(
    market_db_path: str | Path | None,
    *,
    theme: str | None = None,
    entity: str | None = None,
    on_date: str | None = None,
    limit: int = 12,
) -> str:
    """涨停封板时间块 [D18]；无封板时间读数时返回空串（不注入、不出空块）。

    两个源，按「谁有当日读数」**择一，不混用**（混用会出现同一块里两套口径）：

    1. ``fact_theme_limit_stock_daily``（fupanhui 链路）——带题材维度，优先；
    2. ``fact_limit_pool_hithink`` 的 ``limit_up`` 池（同花顺官方）——fupanhui 风控
       期间唯一还有封板时点的源，回落时块内自报换了源。

    两源都有读数的历史日走 1，输出与加回落之前**逐字节相同**；回落只在 1 交不出
    东西时发生，所以这是纯增量，不动既有行为。
    """
    db_path = (
        Path(market_db_path).expanduser() if market_db_path else DEFAULT_MARKET_DB_PATH
    )
    if not db_path.exists():
        return ""
    try:
        con = retrieval_cache.connect_readonly(db_path)
    except Exception:
        return ""
    try:
        block = _seal_block_fupanhui(
            con, theme=theme, entity=entity, on_date=on_date, limit=limit
        )
        if block:
            return block
        return _seal_block_hithink(
            con, theme=theme, entity=entity, on_date=on_date, limit=limit
        )
    finally:
        try:
            con.close()
        except Exception:
            pass


def _seal_block_fupanhui(
    con: Any,
    *,
    theme: str | None,
    entity: str | None,
    on_date: str | None,
    limit: int,
) -> str:
    """源 1（优先）：fupanhui 链路，带题材维度。风控期间对近日恒交白卷。"""
    try:
        exists = con.execute(
            "select count(*) from information_schema.tables "
            "where table_name='fact_theme_limit_stock_daily'"
        ).fetchone()[0]
        if not exists:
            return ""
        row = con.execute(
            "select max(trade_date) from fact_theme_limit_stock_daily "
            "where (? is null or trade_date <= cast(? as date))",
            [on_date, on_date],
        ).fetchone()
        trade_date = str(row[0]) if row and row[0] is not None else ""
        if not trade_date:
            return ""
        counts = con.execute(
            """
            select
              count(distinct stock_ts_code) as total,
              count(distinct case
                when first_limit_time is not null and first_limit_time <> ''
                then stock_ts_code end) as with_seal
            from fact_theme_limit_stock_daily
            where trade_date = cast(? as date)
            """,
            [trade_date],
        ).fetchone()
        total = int(counts[0] or 0)
        with_seal = int(counts[1] or 0)
        # 反向验收：当日没有封板时间读数就不注入。有涨停行但该列全空时同样不出块——
        # 出一个空壳块等于让模型以为「查过了、没有」，那是静默降级的另一种形状。
        # 上游自 2026-09-03 起断供（见文件头），最近交易日走的就是这一条。
        #
        # 与下面的 `if not rows` 的关系（2026-09-11 实测更正，勿再写成「分工」）：
        # **本道过后 `if not rows` 不可达**。with_seal ≥ 1 时，带 keyword 命中则收口
        # 集非空，不命中则回落全市场，两路都必有行——实测把 `if not rows` 改成抛异常
        # 跑全套 D18 测试与直接探针，一次都没走到。它是纯防御性兜底（防日后有人移除
        # 回落逻辑或给 limit 传 0），不是第二种语义。保留，但别指望它变红。
        if with_seal == 0:
            return ""

        scope_note = ""
        params: list[Any] = [trade_date]
        keyword = (theme or entity or "").strip()
        scope_filter = ""
        if keyword:
            like = f"%{keyword}%"
            hit = con.execute(
                """
                select count(*)
                from fact_theme_limit_stock_daily
                where trade_date = cast(? as date)
                  and first_limit_time is not null and first_limit_time <> ''
                  and (sector_name ilike ? or stock_name ilike ?
                       or coalesce(ths_concept_top, '') ilike ?)
                """,
                [trade_date, like, like, like],
            ).fetchone()[0]
            if hit:
                scope_filter = (
                    "and (sector_name ilike ? or stock_name ilike ? "
                    "or coalesce(ths_concept_top, '') ilike ?)"
                )
                params += [like, like, like]
                scope_note = f"；已按「{keyword}」收口"
            else:
                scope_note = f"；「{keyword}」当日无封板时间读数，以下为全市场"
        params.append(max(1, min(int(limit), 50)))
        rows = con.execute(
            f"""
            select
              stock_ts_code,
              min(stock_name) as stock_name,
              min(first_limit_time) as first_seal,
              max(last_limit_time) as last_seal,
              max(limit_times) as limit_times,
              -- 不带 ORDER BY 的 string_agg 顺序不稳定：同一天同一只票两次跑会得到
              -- 「温控/液冷」和「液冷/温控」两种 prompt（2026-09-11 实测）。模型输入
              -- 不该有这种抖动，也让逐字节回归断言变得不可能。
              string_agg(distinct sector_name, '/' order by sector_name) as sectors
            from fact_theme_limit_stock_daily
            where trade_date = cast(? as date)
              and first_limit_time is not null and first_limit_time <> ''
              {scope_filter}
            group by stock_ts_code
            order by first_seal, limit_times desc, stock_ts_code
            limit ?
            """,
            params,
        ).fetchall()
        if not rows:
            return ""
        lines = [
            "## 涨停封板时间数据块 [D18]",
            f"- 数据截至：{trade_date}；口径为 fact_theme_limit_stock_daily 的 "
            "first_limit_time / last_limit_time（上游原始格式 HHMMSS），确定性直查、非模型推断。",
            f"- 覆盖：当日涨停 {total} 只（按 stock_ts_code 去重），"
            f"其中 {with_seal} 只有封板时间读数{scope_note}。",
            "- 逐只封板时间（按首封升序）：",
        ]
        for code, name, first_seal, last_seal, limit_times, sectors in rows:
            first_text = _fmt_seal_time(first_seal)
            last_text = _fmt_seal_time(last_seal)
            reseal = "，盘中开板后回封" if last_text != first_text and last_text != "—" else ""
            lines.append(
                f"  - {name}({code})：首封 {first_text}，末封 {last_text}，"
                f"连板 {limit_times if limit_times is not None else '—'}，"
                f"题材 {sectors or '—'}{reseal}"
            )
        lines.append(
            "- 使用要求：本块只支持「开盘即封 / 盘中封板」这类**时点**识别；"
            "**同表 open_times（炸板次数）上游恒 NULL**，本块无法判定换手是否充分，"
            "不得据此推断换手质量。末封晚于首封说明盘中开过板，但开板次数不可知；"
            "首封接近 09:25 通常是竞价一字板，仍不等于换手充分或不充分。"
        )
        return "\n".join(lines)
    except Exception:
        return ""


def _seal_block_hithink(
    con: Any,
    *,
    theme: str | None,
    entity: str | None,
    on_date: str | None,
    limit: int,
) -> str:
    """源 2（回落）：同花顺官方涨停池 ``fact_limit_pool_hithink``。

    只取 ``limit_up`` 池：它与 ``limit_break`` 池互斥，``limit_up_time`` 100% 非空。
    题材维度该表没有，用 ``fact_sector_stock_daily``（本地自算链路仍在维护）补板块
    归属，并把同花顺自己的 ``limit_up_reason``（涨停原因）原样透出——它比板块名更
    贴近当日叙事，且是上游给的、非本地推断。
    """
    try:
        exists = con.execute(
            "select count(*) from information_schema.tables "
            "where table_name='fact_limit_pool_hithink'"
        ).fetchone()[0]
        if not exists:
            return ""
        row = con.execute(
            "select max(trade_date) from fact_limit_pool_hithink "
            "where pool='limit_up' and limit_up_time is not null and limit_up_time <> '' "
            "and (? is null or trade_date <= cast(? as date))",
            [on_date, on_date],
        ).fetchone()
        trade_date = str(row[0]) if row and row[0] is not None else ""
        if not trade_date:
            return ""
        total, with_seal = con.execute(
            """
            select count(distinct stock_ts_code),
                   count(distinct case when limit_up_time is not null and limit_up_time <> ''
                         then stock_ts_code end)
            from fact_limit_pool_hithink
            where trade_date = cast(? as date) and pool = 'limit_up'
            """,
            [trade_date],
        ).fetchone()
        if not with_seal:
            return ""

        scope_note = ""
        scope_filter = ""
        params: list[Any] = [trade_date]
        keyword = (theme or entity or "").strip()
        if keyword:
            like = f"%{keyword}%"
            probe = con.execute(
                """
                select count(*)
                from fact_limit_pool_hithink h
                left join fact_sector_stock_daily s
                  on s.trade_date = h.trade_date and s.stock_ts_code = h.stock_ts_code
                where h.trade_date = cast(? as date) and h.pool = 'limit_up'
                  and h.limit_up_time is not null and h.limit_up_time <> ''
                  and (coalesce(s.sector_name, '') ilike ?
                       or coalesce(h.limit_up_reason, '') ilike ?
                       or coalesce(s.stock_name, '') ilike ?)
                """,
                [trade_date, like, like, like],
            ).fetchone()[0]
            if probe:
                scope_filter = (
                    "and (coalesce(s.sector_name, '') ilike ? "
                    "or coalesce(h.limit_up_reason, '') ilike ? "
                    "or coalesce(s.stock_name, '') ilike ?)"
                )
                params += [like, like, like]
                scope_note = f"；已按「{keyword}」收口"
            else:
                scope_note = f"；「{keyword}」当日无封板时点读数，以下为全市场"
        params.append(max(1, min(int(limit), 50)))
        rows = con.execute(
            f"""
            select h.stock_ts_code,
                   min(s.stock_name) as stock_name,
                   min(h.limit_up_time) as seal_time,
                   max(h.continue_day_cnt) as limit_times,
                   max(h.seal_money) as seal_money,
                   min(h.limit_up_reason) as reason
            from fact_limit_pool_hithink h
            left join fact_sector_stock_daily s
              on s.trade_date = h.trade_date and s.stock_ts_code = h.stock_ts_code
            where h.trade_date = cast(? as date) and h.pool = 'limit_up'
              and h.limit_up_time is not null and h.limit_up_time <> ''
              {scope_filter}
            group by h.stock_ts_code
            order by seal_time, limit_times desc, h.stock_ts_code
            limit ?
            """,
            params,
        ).fetchall()
        if not rows:
            return ""
        # 名字补齐：`fact_limit_pool_hithink` 只有 ticker，板块成分表当日可能整天缺
        # （2026-09-08 实测：同花顺有该交易日，fupanhui/本地链路整天没有），退化成
        # 一串数字代码会让模型认不出标的。名字不随日期变，故取近 30 日内最后一次
        # 已知名（arg_max），不强求同日。
        missing = [r[0] for r in rows if not r[1]]
        name_map: dict[str, str] = {}
        if missing:
            placeholders = ",".join("?" for _ in missing)
            name_map = dict(
                con.execute(
                    f"""
                    select stock_ts_code, arg_max(stock_name, trade_date)
                    from fact_stock_daily
                    where stock_name is not null and stock_name <> ''
                      and trade_date between cast(? as date) - 30 and cast(? as date)
                      and stock_ts_code in ({placeholders})
                    group by stock_ts_code
                    """,
                    [trade_date, trade_date, *missing],
                ).fetchall()
            )
        lines = [
            "## 涨停封板时间数据块 [D18]",
            f"- 数据截至：{trade_date}；口径为**同花顺官方涨停池** "
            "fact_limit_pool_hithink（limit_up 池）的 limit_up_time，确定性直查、非模型推断。",
            "- ⚠ 换源说明：fupanhui 链路当日无封板时点读数（账号风控期间生产链路切成"
            "本地自算，封板时点属盘中事实，本地从日线推不出），故本块回落到同花顺官方源。"
            "两源在 2026-09-02 交叉验证 49 只交集逐只到分钟一致；此处只用其一，不混口径。",
            f"- 覆盖：当日涨停 {int(total or 0)} 只，"
            f"其中 {int(with_seal)} 只有封板时点读数{scope_note}。",
            "- 逐只封板时点（按首封升序）：",
        ]
        for code, name, seal_time, limit_times, seal_money, reason in rows:
            label = name or name_map.get(code) or str(code).split(".")[0]
            money = (
                f"，封单 {seal_money / 1e8:.2f} 亿"
                if isinstance(seal_money, (int, float)) and seal_money
                else ""
            )
            lines.append(
                f"  - {label}({code})：首封 {seal_time}，"
                f"连板 {limit_times if limit_times is not None else '—'}{money}，"
                f"涨停原因 {reason or '—'}"
            )
        lines.append(
            "- 使用要求：本块只支持「开盘即封 / 盘中封板」这类**时点**识别。"
            "本源**没有末封时点**（limit_up 池与 limit_break 炸板池互斥，"
            "该池内的票是收盘仍封住的），因此**不能判断盘中是否开过板**；"
            "换手是否充分同样判不了（turnover_ratio_pct 实测 0% 填充）。"
            "首封接近 09:25 通常是竞价一字板，仍不等于换手充分或不充分。"
        )
        return "\n".join(lines)
    except Exception:
        return ""
