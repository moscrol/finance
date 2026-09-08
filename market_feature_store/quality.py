"""每日数据质检（#5 数据运营）：缺日扫描 + 行数异常 + 关键值域检查。

与 scripts/check_daily_review_data.py 的分工：
- check_daily_review_data.py = 当日完整性闸门（当日行数/关键字段空值/涨停明细/日报占位），
  已接在同步段末尾，rc 非零会让 nightly 告警。
- 本模块 = 跨日健康检查：历史断档（以 fact_market_daily 为交易日历基准）、
  当日行数相对历史水位的异常收缩、关键指标值域越界。全部只读 SQL，可注入连接单测。
"""
from __future__ import annotations

from typing import Any

DEFAULT_WINDOW = 20
ROW_SHRINK_RATIO = 0.5

GAP_TABLES = [
    "fact_sector_daily",
    "fact_sw_l1_daily",
    "fact_sector_stock_daily",
    "fact_stock_high_daily",
    "fact_theme_limit_heat_daily",
    "fact_limit_advance_daily",
    "fact_stock_daily",
    "fact_mainline_theme_daily",
    "fact_mainline_stock_daily",
    "fact_mainline_sector_daily",
    # 复盘会公开资产（2026-08-13 起）：390 日回补齐后才进门禁——之前历史为空，
    # 进了会天天误报（棘轮：先补齐存量，再拦新增断档）。
    # 天然稀疏的不进：auction（2026-01-16 起才有数）、fact_event_daily /
    # fact_historical_mapping（部分日接口即空）、fact_regulation_*（事件非每日，
    # 且 pool 用 effective_date 列，本检查按 trade_date 扫）。
    "fact_core_stock_daily",
    "fact_dragon_tiger_daily",
    "fact_leader_height_daily",
    "fact_global_index_daily",
    "fact_global_stock_daily",
    # 2026-08-13 补齐 2025-01-16 后 390/390，棘轮闭合进门禁。
    "fact_dragon_summary_daily",
    # 2026-08-13 近 60 日窗口回补完成（60/60 连续、抽查对源头一致）后进门禁。
    # gap 检查只看近 DEFAULT_WINDOW 日且从表首日（2026-05-20）起算，历史更早为空不误报。
    "fact_dragon_seat_daily",
]

# 行数异常收缩只查"宇宙规模近似恒定"的结构表；新高/涨停/晋级类表行数随行情天然大幅波动，
# 用中位数收缩比会天天误报（Mac 真实库验证：新高家数 139 vs 中位 367 属正常市况）。
#
# 2026-07-30：按同一判据把三张 fact_mainline_* 移出本列表。它们统计的是"当日有几条
# 主线、主线里有几只股"，本身就是随行情变化的量，不是恒定宇宙。近 29 个交易日实测：
#   fact_mainline_theme_daily    2 ~ 7    最大/最小 3.5x
#   fact_mainline_stock_daily   30 ~ 163  最大/最小 5.4x
#   fact_mainline_sector_daily   5 ~ 15   最大/最小 3.0x
# 对照恒定表：fact_sw_l1_daily 与 fact_sector_period_rank_daily 均为 1.0x。
#
# 后果不是"少报一个告警"：跨日门禁 FAIL 会让夜间管线其后 16 步全部 SKIP，
# 包括 theme-candidates / agent-daily / 策略矩阵 / cockpit。2026-07-29 那天主线
# 只有 3 条题材 53 只股，重跑同步仍是 53 且报 complete——数据是完整的，行情就是那么窄。
# 也就是说行情越窄，工作台的题材层被掐得越死，而那正是最需要它的时候。
#
# 断档检查（GAP_TABLES）对这三张表保留：某日整天没有行仍然 FAIL，
# 那才是对"随行情波动的表"有效的失败信号。
ROW_ANOMALY_TABLES = [
    "fact_sector_daily",
    "fact_sw_l1_daily",
    "fact_sector_stock_daily",
    "fact_stock_daily",
    "fact_sector_period_rank_daily",
    # 复盘会公开资产里的恒定宇宙表（390 日实测每日行数恒定：50 / 5 / 194）。
    # dragon 随行情波动（实测 46~104），不进本列表，断档检查已覆盖。
    "fact_core_stock_daily",
    "fact_global_index_daily",
    "fact_global_stock_daily",
]

# (字段, 下限, 上限)；None = 不设界。基于 A 股常识口径，宁松勿严，只拦明显脏数。
MARKET_VALUE_RANGES: list[tuple[str, float | None, float | None]] = [
    ("total_amount", 1.0, None),
    ("advancers", 0.0, 7000.0),
    ("limit_up", 0.0, 500.0),
    ("limit_down", 0.0, 500.0),
    ("volume_ratio", 0.01, None),
    ("sh_index_close", 1.0, None),
    ("sh_index_pct_chg", -12.0, 12.0),
]


def _connect_ro():
    from .db import connect

    return connect(read_only=True)


def latest_trade_date(con=None) -> str | None:
    owned = con is None
    con = con or _connect_ro()
    try:
        row = con.execute("SELECT MAX(trade_date) FROM fact_market_daily").fetchone()
        return str(row[0]) if row and row[0] else None
    finally:
        if owned:
            con.close()


def calendar_gaps(con=None, window: int = DEFAULT_WINDOW, tables: list[str] | None = None) -> list[dict[str, Any]]:
    """近 window 个交易日内（fact_market_daily 为日历基准），各表的断档日。

    只在表自身覆盖区间内查（表首日之前不算缺），避免历史短表误报。"""
    owned = con is None
    con = con or _connect_ro()
    try:
        cal = [
            str(r[0])
            for r in con.execute(
                "SELECT trade_date FROM fact_market_daily ORDER BY trade_date DESC LIMIT ?",
                [window],
            ).fetchall()
        ]
        if not cal:
            return []
        gaps: list[dict[str, Any]] = []
        for table in tables or GAP_TABLES:
            row = con.execute(f"SELECT MIN(trade_date) FROM {table}").fetchone()
            first = str(row[0]) if row and row[0] else None
            if first is None:
                gaps.append({"table": table, "missing_dates": list(reversed(cal)), "note": "空表"})
                continue
            have = {
                str(r[0])
                for r in con.execute(
                    f"SELECT DISTINCT trade_date FROM {table} WHERE trade_date >= ?",
                    [min(cal)],
                ).fetchall()
            }
            missing = sorted(d for d in cal if d >= first and d not in have)
            if missing:
                gaps.append({"table": table, "missing_dates": missing})
        return gaps
    finally:
        if owned:
            con.close()


def row_count_anomalies(
    trade_date: str,
    con=None,
    window: int = DEFAULT_WINDOW,
    shrink_ratio: float = ROW_SHRINK_RATIO,
    tables: list[str] | None = None,
) -> list[dict[str, Any]]:
    """当日行数 < 此前 window 个交易日中位数 × shrink_ratio → 异常收缩（半截同步/上游截断）。"""
    owned = con is None
    con = con or _connect_ro()
    try:
        anomalies: list[dict[str, Any]] = []
        for table in tables or ROW_ANOMALY_TABLES:
            today = con.execute(
                f"SELECT COUNT(*) FROM {table} WHERE trade_date = ?", [trade_date]
            ).fetchone()[0]
            hist = [
                r[0]
                for r in con.execute(
                    f"""
                    SELECT COUNT(*) AS n FROM {table}
                    WHERE trade_date < ? GROUP BY trade_date
                    ORDER BY trade_date DESC LIMIT ?
                    """,
                    [trade_date, window],
                ).fetchall()
            ]
            if not hist:
                continue
            hist_sorted = sorted(hist)
            median = hist_sorted[len(hist_sorted) // 2]
            if median > 0 and today < median * shrink_ratio:
                anomalies.append(
                    {"table": table, "rows": today, "median": median,
                     "note": f"当日 {today} 行 < 近{len(hist)}日中位数 {median} × {shrink_ratio}"}
                )
        return anomalies
    finally:
        if owned:
            con.close()


def value_range_violations(trade_date: str, con=None) -> list[dict[str, Any]]:
    """fact_market_daily 当日关键指标值域检查（空值由完整性闸门负责，这里只查越界）。"""
    owned = con is None
    con = con or _connect_ro()
    try:
        fields = [f for f, _, _ in MARKET_VALUE_RANGES]
        row = con.execute(
            f"SELECT {', '.join(fields)} FROM fact_market_daily WHERE trade_date = ?",
            [trade_date],
        ).fetchone()
        if row is None:
            return [{"field": "fact_market_daily", "value": None, "note": f"{trade_date} 缺整行"}]
        violations: list[dict[str, Any]] = []
        for (field, lo, hi), value in zip(MARKET_VALUE_RANGES, row):
            if value is None:
                continue
            v = float(value)
            if (lo is not None and v < lo) or (hi is not None and v > hi):
                violations.append(
                    {"field": field, "value": v,
                     "note": f"越界（允许 {lo if lo is not None else '-inf'} ~ {hi if hi is not None else '+inf'}）"}
                )
        return violations
    finally:
        if owned:
            con.close()


def tables_in_plan(plan: str | None, base: list[str]) -> list[str]:
    """按计划裁剪门禁表：local（自算链路）不产 fupanhui 独有的表，它们缺行是设计不是断档。"""
    if not plan or plan in ("full", "cheap", "auto"):
        return list(base)
    from .consumption_registry import load_registry, tables_for_plan

    expected = tables_for_plan(load_registry(), plan)
    return [t for t in base if t in expected]


def check_daily(
    trade_date: str | None = None,
    con=None,
    window: int = DEFAULT_WINDOW,
    tables: list[str] | None = None,
    plan: str | None = None,
) -> dict[str, Any]:
    """跨日质检总入口；返回 {trade_date, gaps, row_anomalies, range_violations, ok, brief}。

    plan=local 时期望表按 consumption_registry.tables_for_plan 裁剪（gaps 与行数收缩都按裁剪后的表）。"""
    owned = con is None
    con = con or _connect_ro()
    # tables 显式给了就两处都用它（旧行为）；否则按计划分别裁剪断档表与恒定宇宙表
    gap_tables = tables if tables is not None else tables_in_plan(plan, GAP_TABLES)
    anomaly_tables = tables if tables is not None else tables_in_plan(plan, ROW_ANOMALY_TABLES)
    try:
        td = trade_date or latest_trade_date(con)
        if td is None:
            return {"trade_date": None, "gaps": [], "row_anomalies": [], "range_violations": [],
                    "ok": False, "brief": "fact_market_daily 为空，库未初始化或从未同步"}
        gaps = calendar_gaps(con, window=window, tables=gap_tables)
        anomalies = row_count_anomalies(td, con, window=window, tables=anomaly_tables)
        violations = value_range_violations(td, con)
        problems: list[str] = []
        for g in gaps:
            problems.append(f"{g['table']} 断档 {len(g['missing_dates'])} 日（最近 {g['missing_dates'][-1]}）")
        for a in anomalies:
            problems.append(f"{a['table']} 行数异常收缩（{a['rows']}/{a['median']}）")
        for v in violations:
            problems.append(f"{v['field']}={v['value']} {v['note']}")
        ok = not problems
        brief = "；".join(problems[:3]) + (f"（等{len(problems)}项）" if len(problems) > 3 else "") if problems else "通过"
        return {"trade_date": str(td), "window": window, "plan": plan, "gaps": gaps, "row_anomalies": anomalies,
                "range_violations": violations, "ok": ok, "brief": brief}
    finally:
        if owned:
            con.close()
