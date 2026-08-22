"""策略四 · 无前视确定性生成器（D0 口径）。

完全照搬 scripts/render_strategy4_dual_engine_matrix.py 的 SQL 口径，只把输出从 HTML 改成
结构化 picks + 可回溯记录，并加入"代码兜底排序"保证完全可复现。

picks（计入名单、做前瞻收益打分）：
  - ENGINE_A（引擎A 加权动量）：单日加权(pct*sqrt(amount)) Top20 ∩ 容量前三行业 ∩ (当日涨停近似≥9.8% 或 近7交易日重复进Top20)
  - ENGINE_B（引擎B 长高趋势）：当日≥1年新高 ∩ 近8日内新高≥3天 ∩ 容量前三行业
  - OVERLAP（双引擎重叠）：同时入选 A(合格) 与 B 的票
开关(gate)只作为状态记录（golden/soft/observe），不过滤名单——与原矩阵一致（名单照出）。

口径全部使用"当日及以前"数据，无前视：prior7/hi5 都是 p.trade_date<当日 或 ≤当日的回看窗口。
"""
import duckdb
from market_feature_store.signals import DOUBLE_RED_SQL


def _num(x):
    return float(x)


def clean(name):
    return (name or "").replace("\x00", "").strip()


def generate_range(db_path, dates, params):
    """对给定交易日列表生成策略四双引擎候选。返回 {date_iso: payload}。"""
    if not dates:
        return {}
    p4 = params.get("strategy4", {})
    w20N = int(p4.get("w20_topN", 20))
    prior_days = int(p4.get("prior_interval_days", 11))
    limit_pct = _num(p4.get("limit_pct", 9.8))
    hi5_days = int(p4.get("hi5_interval_days", 8))
    hi5_min = int(p4.get("hi5_min", 3))
    cap = int(p4.get("engine_cap", 6))
    gate_lo = _num(p4.get("gate_top3r_lo", 40))
    gate_hi = _num(p4.get("gate_top3r_hi", 45))
    soft_hi = _num(p4.get("soft_top3r_hi", 45))
    high_periods = tuple(p4.get("high_periods", ["1y", "2y", "3y", "history"]))
    start = min(dates)
    end = max(dates)

    con = duckdb.connect()
    con.execute(f"ATTACH '{db_path}' AS db (READ_ONLY)")
    con.execute(f"""
    CREATE TEMP TABLE drd AS
    SELECT trade_date, count(*) dr_count,
      string_agg(sector_name, '、' ORDER BY amount DESC) dr_names
    FROM db.fact_sector_daily
    WHERE {DOUBLE_RED_SQL} GROUP BY 1""")
    con.execute("""
    CREATE TEMP TABLE mkt AS
    SELECT m.trade_date, m.market_stage, m.advancers, m.sh_index_pct_chg,
      m.industry_1, m.industry_2, m.industry_3, m.top3_industry_ratio top3r,
      COALESCE(d.dr_count,0) dr_count, d.dr_names,
      AVG(COALESCE(d.dr_count,0)) OVER w5 dr_ma5,
      AVG(COALESCE(d.dr_count,0)) OVER w20 dr_ma20
    FROM db.fact_market_daily m LEFT JOIN drd d USING (trade_date)
    WINDOW w5 AS (ORDER BY m.trade_date ROWS BETWEEN 4 PRECEDING AND CURRENT ROW),
           w20 AS (ORDER BY m.trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW)""")
    con.execute("""
    CREATE TEMP TABLE swmap AS
    SELECT stock_ts_code, mode(sw_l1) sw_l1 FROM db.fact_sector_stock_daily GROUP BY 1""")
    con.execute(f"""
    CREATE TEMP TABLE w20 AS
    SELECT trade_date, stock_ts_code, stock_name, pct_chg, amount, w_rank FROM (
      SELECT trade_date, stock_ts_code, stock_name, pct_chg, amount,
        ROW_NUMBER() OVER (PARTITION BY trade_date ORDER BY pct_chg*sqrt(GREATEST(amount,0)) DESC) w_rank
      FROM db.fact_stock_daily WHERE pct_chg>0)
    WHERE w_rank<={w20N}""")

    eng_a = con.execute(f"""
    SELECT w.trade_date, w.stock_ts_code, w.stock_name, sm.sw_l1, w.pct_chg, w.amount, w.w_rank,
      (SELECT count(*) FROM w20 p WHERE p.stock_ts_code=w.stock_ts_code
        AND p.trade_date<w.trade_date AND p.trade_date>=w.trade_date-INTERVAL {prior_days} DAY) prior7,
      (w.pct_chg>={limit_pct})::int is_limit
    FROM w20 w
    JOIN swmap sm USING (stock_ts_code)
    JOIN mkt m ON w.trade_date=m.trade_date
    WHERE sm.sw_l1 IN (m.industry_1, m.industry_2, m.industry_3)
      AND w.trade_date BETWEEN DATE '{start}' AND DATE '{end}'
    ORDER BY w.trade_date, w.w_rank, w.stock_ts_code""").fetchall()

    eng_b = con.execute(f"""
    WITH hd AS (
      SELECT trade_date, stock_ts_code, stock_name, primary_high_period, primary_high_label,
        pct_chg, amount, sw_l1,
        (SELECT count(DISTINCT p.trade_date) FROM db.fact_stock_high_daily p
          WHERE p.stock_ts_code=fact_stock_high_daily.stock_ts_code
            AND p.trade_date<=fact_stock_high_daily.trade_date
            AND p.trade_date>fact_stock_high_daily.trade_date-INTERVAL {hi5_days} DAY) hi5
      FROM db.fact_stock_high_daily
      WHERE trade_date BETWEEN DATE '{start}' AND DATE '{end}')
    SELECT hd.trade_date, hd.stock_ts_code, hd.stock_name, hd.sw_l1, hd.pct_chg, hd.amount,
      hd.primary_high_label, hd.hi5
    FROM hd JOIN mkt m ON hd.trade_date=m.trade_date
    WHERE hd.primary_high_period IN {high_periods}
      AND hd.hi5>={hi5_min}
      AND hd.sw_l1 IN (m.industry_1, m.industry_2, m.industry_3)
    ORDER BY hd.trade_date, hd.amount DESC, hd.stock_ts_code""").fetchall()

    days = con.execute(f"""
    SELECT trade_date, market_stage, advancers, sh_index_pct_chg,
      industry_1, industry_2, industry_3, top3r, dr_count, dr_names,
      round(dr_ma5,1), round(dr_ma20,1)
    FROM mkt WHERE trade_date BETWEEN DATE '{start}' AND DATE '{end}'
    ORDER BY trade_date""").fetchall()
    con.close()

    a_by_day, b_by_day = {}, {}
    for r in eng_a:
        a_by_day.setdefault(r[0].isoformat(), []).append(r)
    for r in eng_b:
        b_by_day.setdefault(r[0].isoformat(), []).append(r)

    day_meta = {td.isoformat(): row for row in days for td in [row[0]]}

    out = {}
    for d in dates:
        meta = day_meta.get(d)
        if meta is None:
            continue
        (_, stage, adv, shp, i1, i2, i3, top3r, drc, drn, dma5, dma20) = meta
        gate_ok = (dma5 is not None and dma20 is not None and dma5 > dma20
                   and top3r is not None and gate_lo <= top3r <= gate_hi)
        soft = top3r is not None and top3r < soft_hi
        gate = "golden" if gate_ok else ("soft" if soft else "observe")

        a_all = a_by_day.get(d, [])
        b_all = b_by_day.get(d, [])
        a_qual = [r for r in a_all if r[7] >= 1 or r[8] == 1]
        b_codes = {r[1] for r in b_all}
        a_codes = {r[1] for r in a_qual}
        overlap = a_codes & b_codes

        picks = []
        for r in a_qual[:cap]:
            _, code, name, sw, pct, amt, rk, prior7, is_limit = r
            picks.append({
                "code": code, "name": clean(name), "sw_l1": clean(sw),
                "pct_chg": round(pct, 2) if pct is not None else None,
                "amount": round(amt, 2) if amt is not None else None,
                "w_rank": rk, "prior7": prior7, "is_limit": bool(is_limit),
                "dual": code in b_codes,
                "conditions": {
                    "weighted_top20": True,
                    "in_top3_industry": True,
                    "limit_or_repeat7": (bool(is_limit) or prior7 >= 1),
                },
                "scope": "ENGINE_A",
            })
        for r in b_all[:cap]:
            _, code, name, sw, pct, amt, hilabel, hi5 = r
            picks.append({
                "code": code, "name": clean(name), "sw_l1": clean(sw),
                "pct_chg": round(pct, 2) if pct is not None else None,
                "amount": round(amt, 2) if amt is not None else None,
                "high_label": clean(hilabel), "hi5": hi5,
                "dual": code in a_codes,
                "conditions": {
                    "long_period_high": True,
                    "hi5_ge_min": hi5 >= hi5_min,
                    "in_top3_industry": True,
                },
                "scope": "ENGINE_B",
            })

        out[d] = {
            "gate": gate,
            "coverage": {
                "engine_a_all": len(a_all), "engine_a_qualified": len(a_qual),
                "engine_b": len(b_all), "overlap": len(overlap),
                "top3r": round(top3r, 1) if top3r is not None else None,
                "dr_ma5": dma5, "dr_ma20": dma20,
            },
            "counts": {
                "ENGINE_A": len(a_qual[:cap]),
                "ENGINE_B": len(b_all[:cap]),
                "OVERLAP": len(overlap),
                "S4_ALL": len({p["code"] for p in picks}),
            },
            "picks": picks,
        }
    return out


def picks_in_scope(payload, scope):
    picks = payload.get("picks", [])
    if scope == "ENGINE_A":
        sel = [p for p in picks if p["scope"] == "ENGINE_A"]
    elif scope == "ENGINE_B":
        sel = [p for p in picks if p["scope"] == "ENGINE_B"]
    elif scope == "OVERLAP":
        sel = [p for p in picks if p.get("dual")]
    else:  # S4_ALL
        sel = picks
    seen, dedup = set(), []
    for p in sel:
        if p["code"] in seen:
            continue
        seen.add(p["code"])
        dedup.append(p)
    return dedup
