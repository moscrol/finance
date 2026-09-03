"""只读查询层: 板块/个股基础查询 + 数据体检。

所有函数只读 DuckDB, 返回结构化结果 (list[dict] / dict), 供 CLI 或其它模块调用。
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict

from .db import connect
from .signals import DOUBLE_RED_SQL


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
        # fact_stock_daily
        sk = con.execute(
            "SELECT COUNT(*), COUNT(DISTINCT trade_date), COUNT(DISTINCT stock_ts_code),"
            " MIN(trade_date), MAX(trade_date),"
            " SUM(CASE WHEN close IS NULL THEN 1 ELSE 0 END)"
            " FROM fact_stock_daily"
        ).fetchone()
        out["fact_stock_daily"] = {
            "rows": sk[0], "dates": sk[1], "stocks": sk[2],
            "date_min": str(sk[3]) if sk[3] else None,
            "date_max": str(sk[4]) if sk[4] else None, "null_close": sk[5] or 0,
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


def _sector_filter(con, sector: str, trade_date, table: str) -> tuple[str, list, dict]:
    """把用户给的板块名/码解析成事实表的**单个码**, 返回 (where 片段, 参数, 解析回执)。

    为什么不再 `sector_ts_code = ? OR sector_name = ?`: 供应商换码系后同名板块有两套码
    (2025-10 ~ 2026-07 并存), 按名字过滤会把两个供应商的成分股混成一张表; `国防军工`
    至今仍是两个 .FP 码同名。解析器 (sector_alias) 先定到码, 再按日期在候选里回退
    (退役码只在现行码当日无数据时才用)。维表里查不到的名字保留旧行为, 不静默吞掉。
    """
    from .sector_alias import pick_code_with_rows, resolve_sector_codes

    res = resolve_sector_codes(con, sector)
    receipt = res.to_dict()
    if res.codes:
        code = pick_code_with_rows(con, table, trade_date, res.codes) or res.codes[0]
        receipt["resolved_sector_ts_code"] = code
        return "sector_ts_code = ?", [code], receipt
    receipt["resolved_sector_ts_code"] = None
    return "(sector_ts_code = ? OR sector_name = ?)", [sector, sector], receipt


def sector_stocks(sector: str, trade_date: str | None = None, top: int = 20,
                  order_by: str = "amount") -> dict:
    """板块 → 个股: 某板块某日成分股, 按字段排序。

    返回里的 `resolution` 是解析回执: 用了哪个码、按什么命中、是否同名歧义——
    歧义时调用方必须把它说出来, 不能当成唯一答案。
    """
    allowed = {"amount", "pct_chg", "pct_chg_5d", "pct_chg_10d", "pct_chg_20d",
               "fund_flow_1d", "fund_flow_5d", "price"}
    if order_by not in allowed:
        order_by = "amount"
    con = connect(read_only=True)
    try:
        td = trade_date or _latest_date(con, "fact_sector_stock_daily")
        where, params, resolution = _sector_filter(con, sector, td, "fact_sector_stock_daily")
        rows = con.execute(
            f"""
            SELECT stock_name, stock_ts_code, price, pct_chg, amount,
                   pct_chg_5d, pct_chg_20d, sw_industry, leader_plate,
                   fund_flow_1d, fund_flow_5d, sector_name
            FROM fact_sector_stock_daily
            WHERE trade_date = ? AND {where}
            ORDER BY {order_by} DESC NULLS LAST
            LIMIT ?
            """,
            [td, *params, top],
        ).fetchall()
        cols = ["stock_name", "stock_ts_code", "price", "pct_chg", "amount",
                "pct_chg_5d", "pct_chg_20d", "sw_industry", "leader_plate",
                "fund_flow_1d", "fund_flow_5d", "sector_name"]
        return {"trade_date": str(td), "sector": sector,
                "resolution": resolution,
                "stocks": [dict(zip(cols, r)) for r in rows]}
    finally:
        con.close()


def _merge_alias_rows(con, rows: list[dict]) -> tuple[list[dict], int]:
    """个股 → 板块结果里, 同一条线的退役码与现行码只留现行那一行。

    并存日一只股会同时挂 `云计算.TI` 与 `云计算.FP`, 那是同一个板块的两个供应商
    版本, 不是两个板块。按 canonical 分组, 组内留 canonical 本身 (没有就留第一行)。
    真歧义 (国防军工 两个 .FP) canonical 不同, 两行都保留。视图不存在时原样返回。
    """
    from .sector_alias import load_canonical_map

    dim = load_canonical_map(con)
    if dim is None:
        return rows, 0
    kept: dict[str, dict] = {}
    order: list[str] = []
    for row in rows:
        code = row["sector_ts_code"]
        canonical = dim[code].canonical_sector_ts_code if code in dim else code
        if canonical not in kept:
            kept[canonical] = row
            order.append(canonical)
        elif code == canonical:
            kept[canonical] = row
    merged = [kept[c] for c in order]
    return merged, len(rows) - len(merged)


def stock_sectors(stock: str, trade_date: str | None = None) -> dict:
    """个股 → 板块: 某个股某日归属的所有复盘会板块 (同一板块的两套供应商码合并为一行)。"""
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
        sectors, merged = _merge_alias_rows(con, [dict(zip(cols, r)) for r in rows])
        return {"trade_date": str(td), "stock": stock,
                "alias_rows_merged": merged,
                "sectors": sectors}
    finally:
        con.close()


def _json_loads_list(raw: str | None) -> list:
    if not raw:
        return []
    try:
        val = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return val if isinstance(val, list) else []


def stock_highs(trade_date: str | None = None, period: str | None = None,
                top: int = 20, sector_top: int = 5) -> dict:
    con = connect(read_only=True)
    try:
        td = trade_date or _latest_date(con, "fact_stock_high_daily")
        market = con.execute(
            """
            SELECT stock_high_count_history, stock_high_count_3y, stock_high_count_2y,
                   stock_high_count_1y, stock_high_count_120d, stock_high_count_60d,
                   stock_high_count_20d
            FROM fact_market_daily WHERE trade_date = ?
            """,
            [td],
        ).fetchone()
        high_rows = con.execute(
            """
            SELECT stock_ts_code, stock_name, primary_high_period, primary_high_label,
                   high_periods_json, is_new, price, pct_chg, pct_chg_10d, amount,
                   market_cap, fund_today, limit_status, limit_times, sw_l1, sw_l2, plate
            FROM fact_stock_high_daily
            WHERE trade_date = ?
            ORDER BY amount DESC NULLS LAST, market_cap DESC NULLS LAST
            """,
            [td],
        ).fetchall()
        sector_rows = con.execute(
            """
            SELECT ss.stock_ts_code, ss.sector_name, ss.sector_ts_code, ss.sw_l1,
                   ss.pct_chg, ss.amount
            FROM fact_sector_stock_daily ss
            JOIN fact_stock_high_daily h
              ON ss.trade_date = h.trade_date AND ss.stock_ts_code = h.stock_ts_code
            WHERE h.trade_date = ?
            ORDER BY ss.stock_ts_code, ss.amount DESC NULLS LAST
            """,
            [td],
        ).fetchall()
    finally:
        con.close()

    sectors_by_stock = defaultdict(list)
    for code, sector_name, sector_ts_code, sw_l1, pct_chg, amount in sector_rows:
        sectors_by_stock[code].append({
            "sector_name": sector_name,
            "sector_ts_code": sector_ts_code,
            "sw_l1": sw_l1,
            "pct_chg": pct_chg,
            "amount": amount,
        })

    stocks = []
    for row in high_rows:
        (code, name, primary_period, primary_label, periods_raw, is_new, price,
         pct_chg, pct_chg_10d, amount, market_cap, fund_today, limit_status,
         limit_times, sw_l1, sw_l2, plate) = row
        periods = _json_loads_list(periods_raw)
        period_names = [str(p.get("period")) for p in periods if isinstance(p, dict)]
        if period and period not in period_names and period != primary_period:
            continue
        sectors = sectors_by_stock.get(code, [])[:max(sector_top, 0)]
        mapped_sw_l1 = sw_l1 or next((s["sw_l1"] for s in sectors if s.get("sw_l1")), None) or "未映射"
        stocks.append({
            "stock_ts_code": code,
            "stock_name": name,
            "sw_l1": mapped_sw_l1,
            "api_sw_l1": sw_l1,
            "sw_l2": sw_l2,
            "plate": plate,
            "primary_high_period": primary_period,
            "primary_high_label": primary_label,
            "high_periods": periods,
            "is_new": is_new,
            "price": price,
            "pct_chg": pct_chg,
            "pct_chg_10d": pct_chg_10d,
            "amount": amount,
            "market_cap": market_cap,
            "fund_today": fund_today,
            "limit_status": limit_status,
            "limit_times": limit_times,
            "sectors": sectors,
        })

    groups = []
    grouped = defaultdict(list)
    for stock in stocks:
        grouped[stock["sw_l1"]].append(stock)
    for sw_l1, items in grouped.items():
        sector_counter = Counter()
        history_count = 0
        for stock in items:
            if any(p.get("period") == "history" for p in stock["high_periods"] if isinstance(p, dict)):
                history_count += 1
            for sector in stock["sectors"]:
                if sector.get("sector_name"):
                    sector_counter[sector["sector_name"]] += 1
        ranked = sorted(items, key=lambda x: (x["amount"] is not None, x["amount"] or 0), reverse=True)
        groups.append({
            "sw_l1": sw_l1,
            "count": len(items),
            "history_count": history_count,
            "top_sectors": [name for name, _cnt in sector_counter.most_common(8)],
            "stocks": ranked[:top],
        })
    groups.sort(key=lambda x: (x["count"], x["history_count"]), reverse=True)

    counts = None
    if market:
        counts = {
            "history": market[0],
            "3y": market[1],
            "2y": market[2],
            "1y": market[3],
            "120d": market[4],
            "60d": market[5],
            "20d": market[6],
        }
    return {
        "trade_date": str(td) if td else None,
        "period": period,
        "market_counts": counts,
        "stock_count": len(stocks),
        "group_count": len(groups),
        "groups": groups,
        "stocks": stocks[:top],
    }


def _high_period_hit(periods_raw: str | None, period: str) -> bool:
    periods = _json_loads_list(periods_raw)
    return any(isinstance(p, dict) and p.get("period") == period for p in periods)


def _safe_ratio(current: int, avg: float):
    if avg > 0:
        return current / avg
    if current > 0:
        return float("inf")
    return None


def _peak_row(signal: str, sw_l1: str, current: int, history: list[int],
              ratio_threshold: float, min_count: int) -> dict:
    avg = sum(history) / len(history) if history else 0.0
    ratio = _safe_ratio(current, avg)
    is_peak = current >= min_count and (ratio is not None and ratio >= ratio_threshold)
    return {
        "signal": signal,
        "sw_l1": sw_l1,
        "current_count": current,
        "avg_20d": avg,
        "ratio": ratio,
        "min_count": min_count,
        "is_peak": is_peak,
        "history_counts": history,
    }


def _table_window_dates(con, table: str, target_date, window: int) -> list:
    rows = con.execute(
        f"""
        SELECT DISTINCT trade_date
        FROM {table}
        WHERE trade_date <= ?
        ORDER BY trade_date DESC
        LIMIT ?
        """,
        [target_date, int(window) + 1],
    ).fetchall()
    return [r[0] for r in reversed(rows)]


def sw_l1_signal_peaks(trade_date: str | None = None, high_period: str = "20d",
                       window: int = 20, ratio_threshold: float = 1.2,
                       min_limit_count: int = 3, min_high_count: int = 5,
                       top: int = 20) -> dict:
    con = connect(read_only=True)
    try:
        td = trade_date or _latest_date(con, "fact_market_daily")
        date_rows = con.execute(
            """
            SELECT trade_date
            FROM fact_market_daily
            WHERE trade_date <= ?
            ORDER BY trade_date DESC
            LIMIT ?
            """,
            [td, int(window) + 1],
        ).fetchall()
        dates = [r[0] for r in reversed(date_rows)]
        if not dates:
            return {
                "trade_date": str(td) if td else None,
                "high_period": high_period,
                "window": window,
                "ratio_threshold": ratio_threshold,
                "rows": [],
                "limit_rows": [],
                "high_rows": [],
                "date_count": 0,
                "history_dates": [],
            }
        target_date = dates[-1]
        limit_dates = _table_window_dates(con, "fact_theme_limit_stock_daily", target_date, window)
        high_dates = _table_window_dates(con, "fact_stock_high_daily", target_date, window)
        limit_history_dates = [d for d in limit_dates if d < target_date]
        high_history_dates = [d for d in high_dates if d < target_date]
        limit_rows = []
        if limit_dates:
            placeholders = ",".join("?" for _ in limit_dates)
            limit_rows = con.execute(
                f"""
                SELECT trade_date, COALESCE(sw_l1, '未映射') AS sw_l1, stock_ts_code
                FROM fact_theme_limit_stock_daily
                WHERE trade_date IN ({placeholders})
                  AND stock_ts_code IS NOT NULL
                """,
                limit_dates,
            ).fetchall()
        high_rows_raw = []
        if high_dates:
            placeholders = ",".join("?" for _ in high_dates)
            high_rows_raw = con.execute(
                f"""
                SELECT trade_date, COALESCE(sw_l1, '未映射') AS sw_l1, stock_ts_code, high_periods_json
                FROM fact_stock_high_daily
                WHERE trade_date IN ({placeholders})
                  AND stock_ts_code IS NOT NULL
                """,
                high_dates,
            ).fetchall()
    finally:
        con.close()

    limit_sets = defaultdict(set)
    high_sets = defaultdict(set)
    for d, sw_l1, code in limit_rows:
        limit_sets[(d, sw_l1)].add(code)
    for d, sw_l1, code, periods_raw in high_rows_raw:
        if _high_period_hit(periods_raw, high_period):
            high_sets[(d, sw_l1)].add(code)

    sw_limit = {sw for d, sw in limit_sets if d == target_date}
    sw_high = {sw for d, sw in high_sets if d == target_date}
    limit_out = []
    for sw_l1 in sw_limit:
        current = len(limit_sets.get((target_date, sw_l1), set()))
        history = [len(limit_sets.get((d, sw_l1), set())) for d in limit_history_dates]
        limit_out.append(_peak_row("limit_up", sw_l1, current, history, ratio_threshold, min_limit_count))
    high_out = []
    for sw_l1 in sw_high:
        current = len(high_sets.get((target_date, sw_l1), set()))
        history = [len(high_sets.get((d, sw_l1), set())) for d in high_history_dates]
        high_out.append(_peak_row("stock_high", sw_l1, current, history, ratio_threshold, min_high_count))

    rows = limit_out + high_out
    rows.sort(key=lambda x: (x["is_peak"], x["ratio"] == float("inf"), x["ratio"] or 0, x["current_count"]), reverse=True)
    limit_out.sort(key=lambda x: (x["is_peak"], x["ratio"] == float("inf"), x["ratio"] or 0, x["current_count"]), reverse=True)
    high_out.sort(key=lambda x: (x["is_peak"], x["ratio"] == float("inf"), x["ratio"] or 0, x["current_count"]), reverse=True)
    return {
        "trade_date": str(target_date),
        "high_period": high_period,
        "window": window,
        "ratio_threshold": ratio_threshold,
        "date_count": len(dates),
        "history_dates": [str(d) for d in dates[:-1]],
        "limit_history_dates": [str(d) for d in limit_history_dates],
        "high_history_dates": [str(d) for d in high_history_dates],
        "rows": rows[:top],
        "limit_rows": limit_out[:top],
        "high_rows": high_out[:top],
    }


def _date_range(con, start_date: str | None, end_date: str | None, days: int | None) -> list:
    end = end_date or _latest_date(con, "fact_market_daily")
    if days and not start_date:
        rows = con.execute(
            """
            SELECT trade_date
            FROM fact_market_daily
            WHERE trade_date <= ?
            ORDER BY trade_date DESC
            LIMIT ?
            """,
            [end, int(days)],
        ).fetchall()
        return [r[0] for r in reversed(rows)]
    rows = con.execute(
        """
        SELECT trade_date
        FROM fact_market_daily
        WHERE trade_date >= ? AND trade_date <= ?
        ORDER BY trade_date
        """,
        [start_date, end],
    ).fetchall()
    return [r[0] for r in rows]


def strong_subtheme_trace(start_date: str | None = None, end_date: str | None = None,
                          days: int | None = 60, high_period: str = "20d",
                          window: int = 20, ratio_threshold: float = 1.2,
                          min_limit_count: int = 3, min_high_count: int = 5,
                          top: int = 50) -> dict:
    con = connect(read_only=True)
    try:
        dates = _date_range(con, start_date, end_date, days)
        if not dates:
            return {
                "start_date": start_date,
                "end_date": end_date,
                "dates": [],
                "double_red_first": [],
                "resonance_first": [],
                "peak_first": [],
                "events": [],
            }
        start = dates[0]
        end = dates[-1]
        double_rows = con.execute(
            f"""
            WITH filtered AS (
                SELECT trade_date, sector_ts_code, sector_name, sw_l1, pct_chg, diff_ratio, amount,
                       ROW_NUMBER() OVER (PARTITION BY sector_ts_code ORDER BY trade_date) AS rn
                FROM fact_sector_daily
                WHERE trade_date >= ? AND trade_date <= ?
                  AND {DOUBLE_RED_SQL}
            )
            SELECT trade_date, sector_ts_code, sector_name, sw_l1, pct_chg, diff_ratio, amount
            FROM filtered
            WHERE rn = 1
            ORDER BY trade_date, diff_ratio DESC NULLS LAST, amount DESC NULLS LAST
            LIMIT ?
            """,
            [start, end, top],
        ).fetchall()
        resonance_rows = con.execute(
            """
            WITH filtered AS (
                SELECT trade_date, sector_ts_code, sector_name, sw_l1, pct_chg, diff_ratio, amount,
                       ROW_NUMBER() OVER (PARTITION BY sector_ts_code ORDER BY trade_date) AS rn
                FROM fact_sector_daily
                WHERE trade_date >= ? AND trade_date <= ?
                  AND multi_period_resonance = true
            )
            SELECT trade_date, sector_ts_code, sector_name, sw_l1, pct_chg, diff_ratio, amount
            FROM filtered
            WHERE rn = 1
            ORDER BY trade_date, diff_ratio DESC NULLS LAST, amount DESC NULLS LAST
            LIMIT ?
            """,
            [start, end, top],
        ).fetchall()
    finally:
        con.close()

    sector_cols = ["trade_date", "sector_ts_code", "sector_name", "sw_l1", "pct_chg", "diff_ratio", "amount"]
    double_first = [dict(zip(sector_cols, r)) for r in double_rows]
    resonance_first = [dict(zip(sector_cols, r)) for r in resonance_rows]
    for rows in (double_first, resonance_first):
        for row in rows:
            row["trade_date"] = str(row["trade_date"])

    peak_by_key = {}
    for d in dates:
        res = sw_l1_signal_peaks(
            trade_date=str(d),
            high_period=high_period,
            window=window,
            ratio_threshold=ratio_threshold,
            min_limit_count=min_limit_count,
            min_high_count=min_high_count,
            top=200,
        )
        for row in res["limit_rows"]:
            if not row["is_peak"] or len(res["limit_history_dates"]) < window:
                continue
            key = ("limit_up_peak", row["sw_l1"])
            peak_by_key.setdefault(key, {
                "trade_date": res["trade_date"],
                "signal": "limit_up_peak",
                **row,
            })
        for row in res["high_rows"]:
            if not row["is_peak"] or len(res["high_history_dates"]) < window:
                continue
            key = ("stock_high_peak", row["sw_l1"])
            peak_by_key.setdefault(key, {
                "trade_date": res["trade_date"],
                "signal": "stock_high_peak",
                **row,
            })

    peak_first = sorted(peak_by_key.values(), key=lambda x: (x["trade_date"], x["signal"], x["sw_l1"]))[:top]
    events = []
    for row in double_first:
        events.append({
            "trade_date": row["trade_date"],
            "signal": "double_red_first",
            "name": row["sector_name"],
            "sw_l1": row["sw_l1"],
            "detail": row,
        })
    for row in resonance_first:
        events.append({
            "trade_date": row["trade_date"],
            "signal": "multi_period_first",
            "name": row["sector_name"],
            "sw_l1": row["sw_l1"],
            "detail": row,
        })
    for row in peak_first:
        events.append({
            "trade_date": row["trade_date"],
            "signal": row["signal"],
            "name": row["sw_l1"],
            "sw_l1": row["sw_l1"],
            "detail": row,
        })
    events.sort(key=lambda x: (x["trade_date"], x["signal"], x["name"] or ""))
    return {
        "start_date": str(dates[0]),
        "end_date": str(dates[-1]),
        "dates": [str(d) for d in dates],
        "high_period": high_period,
        "window": window,
        "ratio_threshold": ratio_threshold,
        "double_red_first": double_first,
        "resonance_first": resonance_first,
        "peak_first": peak_first,
        "events": events[:top],
    }


def limit_heat(trade_date: str | None = None, theme: str | None = None,
               top: int = 20, with_stocks: bool = False, stock_top: int = 20) -> dict:
    con = connect(read_only=True)
    try:
        td = trade_date or _latest_date(con, "fact_theme_limit_heat_daily")
        params = [td]
        where = "WHERE trade_date = ?"
        if theme:
            where += " AND (sector_ts_code = ? OR sector_name = ?)"
            params.extend([theme, theme])
        heat_rows = con.execute(
            f"""
            SELECT sector_ts_code, sector_name, dimension, scope, data_stage,
                   is_realtime, source_update_time, market_limit_up_count,
                   limit_up_count, total_count, limit_up_ratio, market_share,
                   fd_amount, rank, top_stocks_json
            FROM fact_theme_limit_heat_daily
            {where}
            ORDER BY rank ASC NULLS LAST, limit_up_count DESC NULLS LAST
            LIMIT ?
            """,
            params + [top],
        ).fetchall()
        cols = [
            "sector_ts_code", "sector_name", "dimension", "scope", "data_stage",
            "is_realtime", "source_update_time", "market_limit_up_count",
            "limit_up_count", "total_count", "limit_up_ratio", "market_share",
            "fd_amount", "rank", "top_stocks_json",
        ]
        heats = []
        for row in heat_rows:
            item = dict(zip(cols, row))
            item["top_stocks"] = _json_loads_list(item.pop("top_stocks_json"))
            item["stocks"] = []
            heats.append(item)
        if with_stocks and heats:
            codes = [h["sector_ts_code"] for h in heats if h.get("sector_ts_code")]
            placeholders = ",".join("?" for _ in codes)
            stock_rows = con.execute(
                f"""
                SELECT sector_ts_code, stock_ts_code, stock_name, price, pct_chg,
                       pct_chg_3d, pct_chg_5d, pct_chg_10d, pct_chg_20d,
                       amount, circ_mv, total_mv, sw_l1, sw_l2, ths_concept_top,
                       fund_flow_1d, fund_flow_5d, limit_times, limit_status,
                       first_limit_time, last_limit_time, open_times,
                       leader_plate, leader_sub_plate, theme_names_json,
                       up_stat, high_status_label, fd_amount
                FROM fact_theme_limit_stock_daily
                WHERE trade_date = ? AND sector_ts_code IN ({placeholders})
                ORDER BY sector_ts_code, limit_times DESC NULLS LAST,
                         fd_amount DESC NULLS LAST, amount DESC NULLS LAST
                """,
                [td] + codes,
            ).fetchall()
            stock_cols = [
                "sector_ts_code", "stock_ts_code", "stock_name", "price", "pct_chg",
                "pct_chg_3d", "pct_chg_5d", "pct_chg_10d", "pct_chg_20d",
                "amount", "circ_mv", "total_mv", "sw_l1", "sw_l2", "ths_concept_top",
                "fund_flow_1d", "fund_flow_5d", "limit_times", "limit_status",
                "first_limit_time", "last_limit_time", "open_times",
                "leader_plate", "leader_sub_plate", "theme_names_json",
                "up_stat", "high_status_label", "fd_amount",
            ]
            by_sector = defaultdict(list)
            for row in stock_rows:
                stock = dict(zip(stock_cols, row))
                stock["theme_names"] = _json_loads_list(stock.pop("theme_names_json"))
                by_sector[stock["sector_ts_code"]].append(stock)
            for item in heats:
                item["stocks"] = by_sector.get(item["sector_ts_code"], [])[:stock_top]
        return {
            "trade_date": str(td) if td else None,
            "theme": theme,
            "count": len(heats),
            "heats": heats,
        }
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
                pivots.append((mx, "峰"))
                trend = -1
                mn = i
            elif v >= values[mn] + delta:
                pivots.append((mn, "谷"))
                trend = 1
                mx = i
        elif trend == 1:
            if v >= values[mx]:
                mx = i
            elif v <= values[mx] - delta:
                pivots.append((mx, "峰"))
                trend = -1
                mn = i
        else:
            if v <= values[mn]:
                mn = i
            elif v >= values[mn] + delta:
                pivots.append((mn, "谷"))
                trend = 1
                mx = i
    pivots.append((mx, "峰") if trend == 1 else (mn, "谷"))
    return pivots


def _rolling_mean(values: list[float], window: int, mode: str = "trailing") -> list[float]:
    """滚动均值, 边界用可用窗口 (min_periods=1)。

    mode='trailing': MA[i]=mean(values[i-window+1 .. i]), 与飞书 chart 表 MA5 口径一致。
    mode='center':   居中均值, 峰谷无滞后, 适合纯历史分析。
    """
    if window <= 1:
        return list(values)
    n = len(values)
    out = []
    if mode == "center":
        half = window // 2
        for i in range(n):
            seg = values[max(0, i - half):min(n, i + half + 1)]
            out.append(sum(seg) / len(seg))
    else:  # trailing
        for i in range(n):
            seg = values[max(0, i - window + 1):i + 1]
            out.append(sum(seg) / len(seg))
    return out


def advancers_extrema(delta: float = 1500, smooth: int = 1,
                      smooth_mode: str = "trailing") -> dict:
    """涨家数序列的波峰/波谷识别 (ZigZag 摆动检测)。

    delta: 确认反转所需的最小摆幅 (家数), 越大越只保留大波段。
    smooth: 滚动均值窗口, >1 时先平滑再检测; 默认1=裸涨家数。
    smooth_mode: 'trailing'(默认, 同飞书MA5) 或 'center'。
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
    series = _rolling_mean(raw, smooth, smooth_mode) if smooth > 1 else raw
    pivots = _zigzag(series, delta)
    out = []
    prev_val = None
    for idx, kind in pivots:
        val = series[idx]  # 摆幅按检测所用序列(裸或MA)度量
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
        # 一天只有几百个板块, 全取后再按 canonical 合并同名双码 (并存日 云计算.TI/.FP
        # 会各占一行), 最后截 top——先 LIMIT 再合并会少给。
        rows = con.execute(
            f"""
            SELECT sector_name, sector_ts_code, sw_l1, pct_chg, diff_ratio, amount
            FROM fact_sector_daily
            WHERE trade_date = ?
            ORDER BY {order_by} DESC NULLS LAST
            """,
            [td],
        ).fetchall()
        cols = ["sector_name", "sector_ts_code", "sw_l1", "pct_chg", "diff_ratio", "amount"]
        sectors, merged = _merge_alias_rows(con, [dict(zip(cols, r)) for r in rows])
        # 合并可能用 canonical 行替换了排在前面的退役码行, 重排一次保证名次按值。
        sectors.sort(key=lambda r: (r[order_by] is None, -(r[order_by] or 0.0)))
        return {"trade_date": str(td), "order_by": order_by,
                "alias_rows_merged": merged,
                "sectors": sectors[:top]}
    finally:
        con.close()


def _interval_stock_rank(start: str, end: str, top: int,
                         min_amount: float, order_by: str) -> dict:
    con = connect(read_only=True)
    try:
        rng = con.execute(
            "SELECT MIN(trade_date), MAX(trade_date) FROM fact_stock_daily"
            " WHERE trade_date >= ? AND trade_date <= ?",
            [start, end],
        ).fetchone()
        if not rng or rng[0] is None:
            return {
                "start": start, "end": end,
                "actual_start": None, "actual_end": None,
                "metadata_date": None,
                "min_amount": min_amount,
                "stocks": [],
            }
        actual_end = str(rng[1])
        meta = con.execute(
            "SELECT MAX(trade_date) FROM fact_sector_stock_daily"
            " WHERE trade_date >= ? AND trade_date <= ?",
            [start, actual_end],
        ).fetchone()
        metadata_date = str(meta[0]) if meta and meta[0] else actual_end
        order_col = "weighted_gain" if order_by == "weighted_gain" else "interval_gain"
        rows = con.execute(
            f"""
            WITH w AS (
                SELECT stock_ts_code, stock_name, trade_date, close, pre_close, amount,
                       ROW_NUMBER() OVER (PARTITION BY stock_ts_code ORDER BY trade_date) AS rn_asc,
                       ROW_NUMBER() OVER (PARTITION BY stock_ts_code ORDER BY trade_date DESC) AS rn_desc,
                       AVG(amount) OVER (PARTITION BY stock_ts_code) AS avg_amt,
                       COUNT(*) OVER (PARTITION BY stock_ts_code) AS ndays
                FROM fact_stock_daily
                WHERE trade_date >= ? AND trade_date <= ?
            ),
            agg AS (
                SELECT stock_ts_code, stock_name, avg_amt, ndays,
                       MAX(CASE WHEN rn_asc = 1 THEN pre_close END) AS base_close,
                       MAX(CASE WHEN rn_desc = 1 THEN close END) AS end_close
                FROM w GROUP BY stock_ts_code, stock_name, avg_amt, ndays
            ),
            perf AS (
            SELECT stock_ts_code, stock_name, ndays, avg_amt,
                   (end_close / base_close - 1) * 100 AS interval_gain,
                   avg_amt * ((end_close / base_close - 1) * 100) / 100 AS weighted_gain
            FROM agg
            WHERE base_close IS NOT NULL AND base_close > 0 AND avg_amt >= ?
            ),
            ranked AS (
                SELECT *
                FROM perf
                ORDER BY {order_col} DESC NULLS LAST
                LIMIT ?
            ),
            sector_ranked AS (
                SELECT stock_ts_code, sector_name, sw_industry, amount,
                       ROW_NUMBER() OVER (PARTITION BY stock_ts_code ORDER BY amount DESC NULLS LAST) AS rn
                FROM fact_sector_stock_daily
                WHERE trade_date = ?
            ),
            sector_meta AS (
                SELECT stock_ts_code,
                       string_agg(sector_name, '、' ORDER BY amount DESC NULLS LAST) FILTER (WHERE rn <= 5) AS sectors,
                       MAX(CASE WHEN rn = 1 THEN NULLIF(split_part(sw_industry, '-', 1), '') END) AS standard_sw_l1
                FROM sector_ranked
                GROUP BY stock_ts_code
            ),
            limit_meta AS (
                SELECT stock_ts_code, any_value(sw_l1) AS sw_l1
                FROM fact_theme_limit_stock_daily
                WHERE trade_date = ? AND sw_l1 IS NOT NULL
                GROUP BY stock_ts_code
            ),
            up_window AS (
                SELECT stock_ts_code, trade_date, close,
                       AVG(close) OVER (PARTITION BY stock_ts_code ORDER BY trade_date ROWS BETWEEN 25 PRECEDING AND CURRENT ROW) AS ma26,
                       STDDEV_POP(close) OVER (PARTITION BY stock_ts_code ORDER BY trade_date ROWS BETWEEN 25 PRECEDING AND CURRENT ROW) AS std26,
                       COUNT(close) OVER (PARTITION BY stock_ts_code ORDER BY trade_date ROWS BETWEEN 25 PRECEDING AND CURRENT ROW) AS n26,
                       ROW_NUMBER() OVER (PARTITION BY stock_ts_code ORDER BY trade_date DESC) AS rn
                FROM fact_stock_daily
                WHERE close IS NOT NULL
            ),
            up_meta AS (
                SELECT stock_ts_code, trade_date AS up_trade_date, close AS latest_close,
                       ma26, std26, ma26 + 0.764 * std26 AS up_value,
                       (close / (ma26 + 0.764 * std26) - 1) * 100 AS up_deviation_pct
                FROM up_window
                WHERE rn = 1 AND n26 = 26 AND ma26 + 0.764 * std26 > 0
            )
            SELECT r.stock_ts_code, r.stock_name, r.ndays, r.avg_amt,
                   r.interval_gain, r.weighted_gain,
                   COALESCE(sector_meta.sectors, '-') AS sectors,
                   COALESCE(sector_meta.standard_sw_l1, h.sw_l1, limit_meta.sw_l1, '未映射') AS sw_l1,
                   up_meta.latest_close, up_meta.up_value, up_meta.up_deviation_pct, up_meta.up_trade_date
            FROM ranked r
            LEFT JOIN sector_meta ON sector_meta.stock_ts_code = r.stock_ts_code
            LEFT JOIN fact_stock_high_daily h
              ON h.trade_date = ? AND h.stock_ts_code = r.stock_ts_code
            LEFT JOIN limit_meta ON limit_meta.stock_ts_code = r.stock_ts_code
            LEFT JOIN up_meta ON up_meta.stock_ts_code = r.stock_ts_code
            ORDER BY r.{order_col} DESC NULLS LAST
            LIMIT ?
            """,
            [start, end, min_amount, top, metadata_date, metadata_date, metadata_date, top],
        ).fetchall()
        cols = ["stock_ts_code", "stock_name", "ndays", "avg_amount",
                "interval_gain", "weighted_gain", "sectors", "sw_l1",
                "latest_close", "up_value", "up_deviation_pct", "up_trade_date"]
        stocks = [dict(zip(cols, r)) for r in rows]
        for s in stocks:
            if isinstance(s.get("stock_name"), str):
                s["stock_name"] = s["stock_name"].replace("\x00", "")
        return {
            "start": start, "end": end,
            "actual_start": str(rng[0]) if rng[0] else None,
            "actual_end": actual_end,
            "metadata_date": metadata_date,
            "min_amount": min_amount,
            "stocks": stocks,
        }
    finally:
        con.close()


def weighted_gainers(start: str, end: str, top: int = 20,
                     min_amount: float = 1.0) -> dict:
    return _interval_stock_rank(start, end, top, min_amount, "weighted_gain")


def interval_gainers(start: str, end: str, top: int = 20,
                     min_amount: float = 1.0) -> dict:
    return _interval_stock_rank(start, end, top, min_amount, "interval_gain")
