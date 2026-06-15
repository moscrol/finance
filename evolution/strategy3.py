"""策略三 · 无前视确定性生成器（D0 口径）。

完全照搬 scripts/backfill_strategy3_touch_matrix.py 的 SQL 口径，只把输出从 HTML 改成
结构化 picks + 可回溯记录，并加入"代码兜底排序"保证完全可复现。

入场候选（计入名单、做前瞻收益打分）：
  - S3_FIRST_TOUCH（S3-L-A 首次Touch）：前一日偏离UP>+3，当日偏离UP∈[-3,+3]
  - S3_WINDOW（S3-L-B 动态窗口）：前 1~10 个交易日发生过Touch，当前偏离∈[-3,+5]，且未触发 SELL/RISK
离场信号（不计入名单）：SELL（touch后涨幅≥+5%兑现）、RISK（深破UP，偏离<-1.5%）。

口径全部使用"当日及以前"数据，无前视：
  - 核心池 = 严格前 15 个交易日内进过单日加权(pct*sqrt(amount)) Top20
  - UP = MA26 + 0.764×STDDEV_POP26（26 日，截至当日）
  - pdev = 前一日偏离（LAG，过去值）
"""
import duckdb


def _num(x):
    return float(x)


def clean(name):
    return (name or "").replace("\x00", "").strip()


def generate_range(db_path, dates, params):
    """对给定交易日列表生成策略三入场候选。返回 {date_iso: payload}。"""
    if not dates:
        return {}
    p3 = params.get("strategy3", {})
    topN = int(p3.get("pool_topN", 20))
    lookbk = int(p3.get("pool_lookback_days", 15))
    maw = int(p3.get("ma_window", 26))
    upk = _num(p3.get("up_k", 0.764))
    t_lo = _num(p3.get("touch_dev_lo", -3))
    t_hi = _num(p3.get("touch_dev_hi", 3))
    prevgt = _num(p3.get("touch_prev_gt", 3))
    e_hi = _num(p3.get("early_dev_hi", 5))
    e_prev = _num(p3.get("early_prev_gt", 5))
    winlb = int(p3.get("window_lookback", 10))
    w_lo = _num(p3.get("window_dev_lo", -3))
    w_hi = _num(p3.get("window_dev_hi", 5))
    sell_g = _num(p3.get("sell_gain", 5))
    risk_d = _num(p3.get("risk_dev", -1.5))
    cap_a = int(p3.get("first_touch_cap", 5))
    cap_b = int(p3.get("window_cap", 5))
    w20_start = str(p3.get("w20_start", "2026-02-15"))
    dev_start = str(p3.get("dev_start", "2026-03-01"))
    rows_start = min(dates)
    maw1 = maw - 1

    con = duckdb.connect()
    con.execute(f"ATTACH '{db_path}' AS db (READ_ONLY)")
    con.execute(f"""
    CREATE TEMP TABLE w20 AS
    SELECT trade_date, stock_ts_code, stock_name, w_rank FROM (
      SELECT trade_date, stock_ts_code, stock_name,
        ROW_NUMBER() OVER (PARTITION BY trade_date ORDER BY pct_chg*sqrt(GREATEST(amount,0)) DESC) w_rank
      FROM db.fact_stock_daily WHERE pct_chg>0)
    WHERE w_rank<={topN} AND trade_date >= DATE '{w20_start}'""")
    con.execute("""
    CREATE TEMP TABLE tdates AS
    SELECT trade_date, ROW_NUMBER() OVER (ORDER BY trade_date) rn
    FROM (SELECT DISTINCT trade_date FROM db.fact_market_daily)""")
    con.execute(f"""
    CREATE TEMP TABLE dev AS
    SELECT trade_date, stock_ts_code, stock_name, close, pct_chg,
      100.0*(close/(ma+{upk}*sd)-1) dev,
      LAG(100.0*(close/(ma+{upk}*sd)-1)) OVER (PARTITION BY stock_ts_code ORDER BY trade_date) pdev
    FROM (
      SELECT trade_date, stock_ts_code, stock_name, close, pct_chg,
        AVG(close) OVER w ma, STDDEV_POP(close) OVER w sd
      FROM db.fact_stock_daily
      WHERE stock_ts_code IN (SELECT DISTINCT stock_ts_code FROM w20)
      WINDOW w AS (PARTITION BY stock_ts_code ORDER BY trade_date ROWS BETWEEN {maw1} PRECEDING AND CURRENT ROW))
    WHERE trade_date >= DATE '{dev_start}'""")
    con.execute(f"""
    CREATE TEMP TABLE pool AS
    SELECT d.trade_date, d.stock_ts_code,
      min(w.w_rank) best_rank, max(w.trade_date) last_w20
    FROM dev d
    JOIN tdates td ON td.trade_date=d.trade_date
    JOIN tdates tw ON tw.rn BETWEEN td.rn-{lookbk} AND td.rn-1
    JOIN w20 w ON w.stock_ts_code=d.stock_ts_code AND w.trade_date=tw.trade_date
    GROUP BY 1,2""")
    con.execute(f"""
    CREATE TEMP TABLE touch AS
    SELECT d.trade_date, d.stock_ts_code, d.close touch_close
    FROM dev d JOIN pool p USING (trade_date, stock_ts_code)
    WHERE d.dev BETWEEN {t_lo} AND {t_hi} AND d.pdev > {prevgt}""")
    rows = con.execute(f"""
    SELECT d.trade_date, d.stock_ts_code, d.stock_name, d.close, d.pct_chg,
      round(d.dev,2), round(d.pdev,2), p.best_rank, p.last_w20,
      t.trade_date AS touch_date, t.touch_close
    FROM dev d
    JOIN pool p USING (trade_date, stock_ts_code)
    LEFT JOIN (
      SELECT td.trade_date cur_date, t.stock_ts_code, max_by(t.trade_date, t.trade_date) trade_date,
        max_by(t.touch_close, t.trade_date) touch_close
      FROM tdates td
      JOIN tdates tw ON tw.rn BETWEEN td.rn-{winlb} AND td.rn-1
      JOIN touch t ON t.trade_date=tw.trade_date
      GROUP BY 1,2) t ON t.cur_date=d.trade_date AND t.stock_ts_code=d.stock_ts_code
    WHERE d.trade_date >= DATE '{rows_start}'
    ORDER BY d.trade_date, abs(d.dev), d.stock_ts_code""").fetchall()
    con.close()

    wanted = set(dates)
    by_day = {}
    for r in rows:
        d = r[0].isoformat()
        if d in wanted:
            by_day.setdefault(d, []).append(r)

    out = {}
    for d in dates:
        day = by_day.get(d, [])
        first_touch, early, window, sell, risk = [], [], [], [], []
        for r in day:
            _, code, name, close, pct, dv, pdv, brank, lastw, tdate, tclose = r
            if dv is None:
                continue
            if pdv is not None and pdv > prevgt and t_lo <= dv <= t_hi:
                first_touch.append(r)
            elif t_hi < dv <= e_hi and (pdv or 0) > e_prev:
                early.append(r)
            elif tdate is not None:
                gain = 100.0 * (close / tclose - 1) if tclose else 0.0
                if gain >= sell_g:
                    sell.append(r)
                elif dv < risk_d:
                    risk.append(r)
                elif w_lo <= dv <= w_hi:
                    window.append(r)
        first_touch.sort(key=lambda r: (abs(r[5]), r[1]))
        window.sort(key=lambda r: (abs(r[5]), r[1]))

        picks = []
        for r in first_touch[:cap_a]:
            _, code, name, close, pct, dv, pdv, brank, lastw, tdate, tclose = r
            picks.append({
                "code": code, "name": clean(name),
                "pct_chg": round(pct, 2) if pct is not None else None,
                "dev": dv, "pdev": pdv, "best_rank": brank,
                "conditions": {
                    "prev_dev_gt_thr": (pdv is not None and pdv > prevgt),
                    "dev_in_touch_band": (t_lo <= dv <= t_hi),
                    "in_pool_15d": True,
                },
                "scope": "S3_FIRST_TOUCH",
            })
        for r in window[:cap_b]:
            _, code, name, close, pct, dv, pdv, brank, lastw, tdate, tclose = r
            picks.append({
                "code": code, "name": clean(name),
                "pct_chg": round(pct, 2) if pct is not None else None,
                "dev": dv,
                "touch_date": tdate.isoformat() if tdate else None,
                "conditions": {
                    "touch_in_prior_window": True,
                    "dev_in_window_band": (w_lo <= dv <= w_hi),
                    "not_sell": True,
                    "not_deep_break": (dv >= risk_d),
                },
                "scope": "S3_WINDOW",
            })

        out[d] = {
            "coverage": {
                "first_touch": len(first_touch), "early": len(early),
                "window": len(window), "sell": len(sell), "risk": len(risk),
            },
            "counts": {
                "S3_FIRST_TOUCH": len(first_touch[:cap_a]),
                "S3_WINDOW": len(window[:cap_b]),
                "S3_ALL": len(picks),
            },
            "picks": picks,
        }
    return out


def picks_in_scope(payload, scope):
    picks = payload.get("picks", [])
    if scope == "S3_ALL":
        return picks
    return [p for p in picks if p["scope"] == scope]
