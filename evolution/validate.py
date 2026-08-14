"""前瞻收益验证：基准 = D0 收盘，T+h = 之后第 h 个交易日收盘，ret% = (close_h/close_0 - 1)*100。

交易日历取自 fact_stock_daily 的 distinct trade_date（升序）。无前视、可复现。
状态：ok（算出收益）/ pending（未来交易日尚未入库）/ missing（该日有交易日但缺该票收盘）。
"""


def trading_calendar(con):
    return [str(x[0]) for x in con.execute(
        "select distinct trade_date from fact_stock_daily order by trade_date").fetchall()]


def forward_returns(con, picks_by_date, horizons):
    """picks_by_date: {date: [code, ...]}；返回 (ret_map, calendar)。

    ret_map[(date, code)][h] = {"status","target","ret_pct"}。
    """
    cal = trading_calendar(con)
    idx = {d: i for i, d in enumerate(cal)}
    codes = sorted({c for cs in picks_by_date.values() for c in cs})
    dates = sorted(picks_by_date)
    if not codes:
        return {}, cal

    need_days = set()
    for d in dates:
        i = idx.get(d)
        if i is None:
            continue
        need_days.add(d)
        for h in horizons:
            if i + h < len(cal):
                need_days.add(cal[i + h])
    need_days = sorted(need_days)

    closes = {}
    if need_days:
        qd = ",".join(["?"] * len(need_days))
        qc = ",".join(["?"] * len(codes))
        for code, day, close in con.execute(
            f"select stock_ts_code, cast(trade_date as varchar), close from fact_stock_daily "
            f"where trade_date in ({qd}) and stock_ts_code in ({qc})",
            [*need_days, *codes],
        ).fetchall():
            closes[(code, day)] = close

    out = {}
    for d in dates:
        i = idx.get(d)
        for c in picks_by_date[d]:
            base = closes.get((c, d))
            rec = {}
            for h in horizons:
                if i is None:
                    rec[h] = {"status": "missing", "target": None, "ret_pct": None}
                    continue
                if i + h >= len(cal):
                    rec[h] = {"status": "pending", "target": None, "ret_pct": None}
                    continue
                tgt = cal[i + h]
                if base in (None, 0):
                    rec[h] = {"status": "missing", "target": tgt, "ret_pct": None}
                    continue
                fut = closes.get((c, tgt))
                if fut is None:
                    rec[h] = {"status": "missing", "target": tgt, "ret_pct": None}
                else:
                    rec[h] = {"status": "ok", "target": tgt, "ret_pct": round((fut / base - 1) * 100, 2)}
            out[(d, c)] = rec
    return out, cal


def aggregate(ret_map, picks_by_date, horizons, params):
    win_gt = params["validation"]["win_gt"]
    strong = params["validation"]["strong_ge"]
    fail = params["validation"]["fail_le"]
    agg = {}
    for h in horizons:
        vals = []
        pend = miss = 0
        for d, cs in picks_by_date.items():
            for c in cs:
                r = ret_map.get((d, c), {}).get(h)
                if not r:
                    continue
                if r["status"] == "ok":
                    vals.append(r["ret_pct"])
                elif r["status"] == "pending":
                    pend += 1
                else:
                    miss += 1
        n = len(vals)
        agg[h] = {
            "n": n, "pending": pend, "missing": miss,
            "win": round(100 * sum(v > win_gt for v in vals) / n, 1) if n else None,
            "mean": round(sum(vals) / n, 2) if n else None,
            "strong": round(100 * sum(v >= strong for v in vals) / n, 1) if n else None,
            "fail": round(100 * sum(v <= fail for v in vals) / n, 1) if n else None,
        }
    return agg
