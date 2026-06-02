"""只读查询层: 板块/个股基础查询 + 数据体检。

所有函数只读 DuckDB, 返回结构化结果 (list[dict] / dict), 供 CLI 或其它模块调用。
"""
from __future__ import annotations

from .db import connect


def _latest_date(con, table: str):
    row = con.execute(f"SELECT MAX(trade_date) FROM {table}").fetchone()
    return row[0] if row else None


def health() -> dict:
    """数据体检: 各表行数 / 覆盖交易日 / 空值 / 映射完整度。"""
    con = connect(read_only=True)
    try:
        out = {}
        # dim_sector
        out["dim_sector"] = {
            "total": con.execute("SELECT COUNT(*) FROM dim_sector").fetchone()[0],
            "mapped_sw_l1": con.execute(
                "SELECT COUNT(*) FROM dim_sector WHERE sw_l1 IS NOT NULL"
            ).fetchone()[0],
        }
        # fact_sector_daily
        d = con.execute(
            "SELECT COUNT(*), COUNT(DISTINCT trade_date), MIN(trade_date), MAX(trade_date),"
            " SUM(CASE WHEN diff_ratio IS NULL THEN 1 ELSE 0 END),"
            " SUM(CASE WHEN sw_l1 IS NULL THEN 1 ELSE 0 END)"
            " FROM fact_sector_daily"
        ).fetchone()
        out["fact_sector_daily"] = {
            "rows": d[0], "dates": d[1], "date_min": str(d[2]) if d[2] else None,
            "date_max": str(d[3]) if d[3] else None,
            "null_diff_ratio": d[4] or 0, "null_sw_l1": d[5] or 0,
        }
        # fact_sector_stock_daily
        s = con.execute(
            "SELECT COUNT(*), COUNT(DISTINCT trade_date), COUNT(DISTINCT sector_ts_code),"
            " COUNT(DISTINCT stock_ts_code), MAX(trade_date),"
            " SUM(CASE WHEN stock_ts_code IS NULL THEN 1 ELSE 0 END),"
            " SUM(CASE WHEN sw_l1 IS NULL THEN 1 ELSE 0 END)"
            " FROM fact_sector_stock_daily"
        ).fetchone()
        out["fact_sector_stock_daily"] = {
            "rows": s[0], "dates": s[1], "sectors": s[2], "stocks": s[3],
            "date_max": str(s[4]) if s[4] else None,
            "null_stock_code": s[5] or 0, "null_sw_l1": s[6] or 0,
        }
        # fact_market_daily
        m = con.execute(
            "SELECT COUNT(*), COUNT(DISTINCT trade_date), MIN(trade_date), MAX(trade_date),"
            " SUM(CASE WHEN total_amount IS NULL THEN 1 ELSE 0 END)"
            " FROM fact_market_daily"
        ).fetchone()
        out["fact_market_daily"] = {
            "rows": m[0], "dates": m[1], "date_min": str(m[2]) if m[2] else None,
            "date_max": str(m[3]) if m[3] else None, "null_total_amount": m[4] or 0,
        }
        # 完整度: 最新交易日 dim_sector 覆盖了多少板块有成分股
        latest = out["fact_sector_stock_daily"]["date_max"]
        if latest:
            covered = con.execute(
                "SELECT COUNT(DISTINCT sector_ts_code) FROM fact_sector_stock_daily WHERE trade_date = ?",
                [latest],
            ).fetchone()[0]
            out["coverage_latest"] = {
                "date": latest,
                "sectors_with_stocks": covered,
                "dim_sector_total": out["dim_sector"]["total"],
            }
        return out
    finally:
        con.close()


def sector_stocks(sector: str, trade_date: str | None = None, top: int = 20,
                  order_by: str = "amount") -> dict:
    """板块 → 个股: 某板块某日成分股, 按字段排序。"""
    allowed = {"amount", "pct_chg", "pct_chg_5d", "pct_chg_10d", "pct_chg_20d",
               "fund_flow_1d", "fund_flow_5d", "price"}
    if order_by not in allowed:
        order_by = "amount"
    con = connect(read_only=True)
    try:
        td = trade_date or _latest_date(con, "fact_sector_stock_daily")
        rows = con.execute(
            f"""
            SELECT stock_name, stock_ts_code, price, pct_chg, amount,
                   pct_chg_5d, pct_chg_20d, sw_industry, leader_plate,
                   fund_flow_1d, fund_flow_5d, sector_name
            FROM fact_sector_stock_daily
            WHERE trade_date = ? AND (sector_ts_code = ? OR sector_name = ?)
            ORDER BY {order_by} DESC NULLS LAST
            LIMIT ?
            """,
            [td, sector, sector, top],
        ).fetchall()
        cols = ["stock_name", "stock_ts_code", "price", "pct_chg", "amount",
                "pct_chg_5d", "pct_chg_20d", "sw_industry", "leader_plate",
                "fund_flow_1d", "fund_flow_5d", "sector_name"]
        return {"trade_date": str(td), "sector": sector,
                "stocks": [dict(zip(cols, r)) for r in rows]}
    finally:
        con.close()


def stock_sectors(stock: str, trade_date: str | None = None) -> dict:
    """个股 → 板块: 某个股某日归属的所有复盘会板块。"""
    con = connect(read_only=True)
    try:
        td = trade_date or _latest_date(con, "fact_sector_stock_daily")
        rows = con.execute(
            """
            SELECT sector_name, sector_ts_code, sw_l1, pct_chg, amount
            FROM fact_sector_stock_daily
            WHERE trade_date = ? AND (stock_ts_code = ? OR stock_name = ?)
            ORDER BY amount DESC NULLS LAST
            """,
            [td, stock, stock],
        ).fetchall()
        cols = ["sector_name", "sector_ts_code", "sw_l1", "pct_chg", "amount"]
        return {"trade_date": str(td), "stock": stock,
                "sectors": [dict(zip(cols, r)) for r in rows]}
    finally:
        con.close()


def _zigzag(values: list[float], delta: float) -> list[tuple[int, str]]:
    """ZigZag 摆动检测: 返回交替的 (index, '峰'|'谷')。

    delta 为确认反转所需的最小摆幅 (绝对值)。分别跟踪 running max/min,
    当价格自极值反向回撤 >= delta 时确认前一个极值为枢轴。
    """
    n = len(values)
    if n == 0:
        return []
    pivots: list[tuple[int, str]] = []
    trend = 0  # 0 未定, 1 上行(找峰), -1 下行(找谷)
    mx = mn = 0
    for i in range(1, n):
        v = values[i]
        if trend == 0:
            if v > values[mx]:
                mx = i
            if v < values[mn]:
                mn = i
            if v <= values[mx] - delta:
                pivots.append((mx, "峰")); trend = -1; mn = i
            elif v >= values[mn] + delta:
                pivots.append((mn, "谷")); trend = 1; mx = i
        elif trend == 1:
            if v >= values[mx]:
                mx = i
            elif v <= values[mx] - delta:
                pivots.append((mx, "峰")); trend = -1; mn = i
        else:
            if v <= values[mn]:
                mn = i
            elif v >= values[mn] + delta:
                pivots.append((mn, "谷")); trend = 1; mx = i
    pivots.append((mx, "峰") if trend == 1 else (mn, "谷"))
    return pivots


def _rolling_mean(values: list[float], window: int) -> list[float]:
    """居中滚动均值, 边界用可用窗口 (min_periods=1)。"""
    if window <= 1:
        return list(values)
    n = len(values)
    half = window // 2
    out = []
    for i in range(n):
        lo = max(0, i - half)
        hi = min(n, i + half + 1)
        seg = values[lo:hi]
        out.append(sum(seg) / len(seg))
    return out


def advancers_extrema(delta: float = 1500, smooth: int = 1) -> dict:
    """涨家数序列的波峰/波谷识别 (ZigZag 摆动检测)。

    delta: 确认反转所需的最小摆幅 (家数), 越大越只保留大波段。
    smooth: 居中滚动均值窗口, >1 时先平滑再检测 (减少日间毛刺), 默认1=不平滑。
    返回交替的枢轴列表, 每个含原始涨家数与(如平滑)平滑值。
    """
    con = connect(read_only=True)
    try:
        rows = con.execute(
            "SELECT trade_date, advancers FROM fact_market_daily"
            " WHERE advancers IS NOT NULL ORDER BY trade_date"
        ).fetchall()
    finally:
        con.close()
    dates = [r[0] for r in rows]
    raw = [float(r[1]) for r in rows]
    series = _rolling_mean(raw, smooth) if smooth > 1 else raw
    pivots = _zigzag(series, delta)
    out = []
    prev_val = None
    for idx, kind in pivots:
        val = raw[idx]
        swing = None if prev_val is None else round(val - prev_val)
        out.append({
            "date": str(dates[idx]),
            "type": kind,
            "advancers": int(raw[idx]),
            "smoothed": round(series[idx]) if smooth > 1 else None,
            "swing_from_prev": swing,
        })
        prev_val = val
    peaks = sum(1 for p in out if p["type"] == "峰")
    troughs = sum(1 for p in out if p["type"] == "谷")
    return {"delta": delta, "smooth": smooth, "n_days": len(raw),
            "peaks": peaks, "troughs": troughs, "pivots": out}


def top_sectors(trade_date: str | None = None, top: int = 20,
                order_by: str = "diff_ratio") -> dict:
    """板块排行: 某日按边际量/涨幅/成交额排序。"""
    allowed = {"diff_ratio", "pct_chg", "amount"}
    if order_by not in allowed:
        order_by = "diff_ratio"
    con = connect(read_only=True)
    try:
        td = trade_date or _latest_date(con, "fact_sector_daily")
        rows = con.execute(
            f"""
            SELECT sector_name, sw_l1, pct_chg, diff_ratio, amount
            FROM fact_sector_daily
            WHERE trade_date = ?
            ORDER BY {order_by} DESC NULLS LAST
            LIMIT ?
            """,
            [td, top],
        ).fetchall()
        cols = ["sector_name", "sw_l1", "pct_chg", "diff_ratio", "amount"]
        return {"trade_date": str(td), "order_by": order_by,
                "sectors": [dict(zip(cols, r)) for r in rows]}
    finally:
        con.close()
