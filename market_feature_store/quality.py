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
]

# 行数异常收缩只查"宇宙规模近似恒定"的结构表；新高/涨停/晋级类表行数随行情天然大幅波动，
# 用中位数收缩比会天天误报（Mac 真实库验证：新高家数 139 vs 中位 367 属正常市况）。
ROW_ANOMALY_TABLES = [
    "fact_sector_daily",
    "fact_sw_l1_daily",
    "fact_sector_stock_daily",
    "fact_stock_daily",
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


def check_daily(
    trade_date: str | None = None,
    con=None,
    window: int = DEFAULT_WINDOW,
    tables: list[str] | None = None,
) -> dict[str, Any]:
    """跨日质检总入口；返回 {trade_date, gaps, row_anomalies, range_violations, ok, brief}。"""
    owned = con is None
    con = con or _connect_ro()
    try:
        td = trade_date or latest_trade_date(con)
        if td is None:
            return {"trade_date": None, "gaps": [], "row_anomalies": [], "range_violations": [],
                    "ok": False, "brief": "fact_market_daily 为空，库未初始化或从未同步"}
        gaps = calendar_gaps(con, window=window, tables=tables)
        anomalies = row_count_anomalies(td, con, window=window, tables=tables)
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
        return {"trade_date": str(td), "window": window, "gaps": gaps, "row_anomalies": anomalies,
                "range_violations": violations, "ok": ok, "brief": brief}
    finally:
        if owned:
            con.close()
