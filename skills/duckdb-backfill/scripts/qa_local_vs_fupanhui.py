#!/usr/bin/env python3
"""自算 vs fupanhui 双轨对账（只读、零网络）——剥离 fupanhui 的切换门。

用我们自己的底数据（fact_stock_daily 东财/mootdx、fact_sw_l1_daily 申万官方、fact_sector_daily/
fact_sector_stock_daily 只借名单）按公开规则重算 fupanhui 的加工字段，与库里已有的 fupanhui 值逐日比。
每个数据族给一个读数和一个判定；切换期每天跑，读数稳定在门内才把该族的源切到本地。

    python3 skills/duckdb-backfill/scripts/qa_local_vs_fupanhui.py                # 最近 15 个完整日
    python3 skills/duckdb-backfill/scripts/qa_local_vs_fupanhui.py --start 2026-08-13 --end 2026-09-02 --json /tmp/dt.json

退出码：0 = 已对上的族全部在门内；2 = 有族越门；3 = BLOCKED（写锁）。
「底数据坏日」（我们自己的全A成交额与 fupanhui 沪深总额差 >10%）自动剔出统计并单列，
那是回补问题不是口径问题（2026-08-13 东财快照写成半日量就是这样被发现的）。

规则口径（2026-09-07 实测定形）：
- 涨跌停板：北交所 30%、创业/科创 20%、其余 10%（ST 现行也是 10%，按 5% 会多报）。
  涨停价：沪深 = 四舍五入到分（tie 434/451 向上）；北交所 = 向下取整到分（40/40 实测，如 16.25×1.3=21.125→21.12）。
  新股（名字 N/C 开头）不计；停牌（amount=0）不计；**ST 不计**——fupanhui 的涨停家数/题材涨停/涨停明细都不含 ST
  （明细 0 只 ST；剔掉后板块一致率 91.7%→96.4%）。
- fupanhui 总成交额 = 沪深不含北交所；量能 MA20 含当日；量能比 = 当日/MA20×100。
- 前三行业 = 申万一级成交份额。
- 新高：有 high 列时按日内最高价，否则按收盘价（收盘价口径与 fupanhui 差 ±20%，只作参考）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

EXIT_FAIL = 2
EXIT_BLOCKED = 3
BAD_BASE_RATIO = 0.10  # 我们的沪深成交额与 fph 总额差 >10% → 底数据坏日

# 每族的门（对干净日统计）。数值来自 2026-08-14~09-02 十四个干净日的实测。
GATES = {
    "advancers": ("涨家数 |Δ|≤10 的日子占比（mootdx 裸前收日与东财差几只）", 0.90),
    "total_amount": ("沪深成交额比 fph/自算 在 0.998~1.002 的日子占比", 0.90),
    "limit_up": ("涨停家数 |Δ|≤6 的日子占比", 0.90),
    "limit_down": ("跌停家数 |Δ|≤6 的日子占比", 0.80),
    "volume_fields": ("量比昨日 |Δ|≤0.1、MA20 相对差 ≤0.05%、量能比 |Δ|≤0.1 的日子占比", 0.90),
    "top3_industry": ("前三行业名次一致的日子占比", 0.90),
    "sector_limit_up": ("逐板块涨停数一致率（不含 ST）", 0.95),
    "limit_stock_recall": ("fph 涨停明细被自算覆盖的比例（召回）", 0.97),
    "ladder_boards": ("连板 boards 与自算连板数一致率", 0.95),
    "leader_height": ("龙头高度一致的日子占比", 0.90),
}
# 已知还对不上、只出读数不设门的族
INFO_ONLY = {
    "stock_high": "新高家数：按日内最高价（high）；fupanhui 用前复权，20 日相对误差中位 ~12%",
    "strength_top5": "市场强度：fupanhui 的 top5 集合未逆向出；自家口径=涨幅前 5% 个股（compute-market-editorial-local），见上方编辑层读数",
}

LIMIT_RULE_SQL = """
    CASE WHEN stock_ts_code LIKE '%.BJ' THEN 0.30
         WHEN stock_ts_code LIKE '30%' OR stock_ts_code LIKE '68%' THEN 0.20
         ELSE 0.10 END
"""


def up_px_sql(pre: str, lim: str, code: str) -> str:
    """涨停价：北交所向下取整到分，沪深四舍五入到分（2026-06~09 fupanhui 涨停明细实测）。"""
    return (f"CASE WHEN {code} LIKE '%.BJ' THEN FLOOR({pre}*(1+{lim})*100 + 1e-6)/100 "
            f"ELSE ROUND({pre}*(1+{lim}) + 1e-9, 2) END")


def dn_px_sql(pre: str, lim: str, code: str) -> str:
    """跌停价：北交所按对称假设向上取整（朝前收方向），沪深四舍五入。"""
    return (f"CASE WHEN {code} LIKE '%.BJ' THEN CEIL({pre}*(1-{lim})*100 - 1e-6)/100 "
            f"ELSE ROUND({pre}*(1-{lim}) + 1e-9, 2) END")


def q(con, sql, params=None):
    return con.execute(sql, params or []).fetchall()


def pick_dates(con, start, end, n):
    where = ["m.total_amount IS NOT NULL", "m.limit_up IS NOT NULL",
             "EXISTS (SELECT 1 FROM fact_sector_stock_daily s WHERE s.trade_date = m.trade_date)",
             "EXISTS (SELECT 1 FROM fact_stock_daily d WHERE d.trade_date = m.trade_date)"]
    params = []
    if start:
        where.append("m.trade_date >= ?")
        params.append(start)
    if end:
        where.append("m.trade_date <= ?")
        params.append(end)
    sql = f"SELECT CAST(m.trade_date AS VARCHAR) FROM fact_market_daily m WHERE {' AND '.join(where)} ORDER BY m.trade_date DESC"
    if not (start and end):
        sql += f" LIMIT {int(n)}"
    return sorted(r[0] for r in q(con, sql, params))


def build_lim(con, dates):
    ph = ",".join("?" for _ in dates)
    con.execute(
        f"""
        CREATE TEMP TABLE lim AS
        WITH s AS (
          SELECT trade_date, stock_ts_code, stock_name, close, pre_close, pct_chg, amount,
                 {LIMIT_RULE_SQL} AS lim,
                 (stock_name LIKE 'N%' OR stock_name LIKE 'C%') AS is_new,
                 (stock_name LIKE '%ST%') AS is_st
          FROM fact_stock_daily WHERE trade_date IN ({ph})
        )
        SELECT *,
               (NOT is_new AND pre_close > 0 AND amount > 0 AND close >= {up_px_sql('pre_close', 'lim', 'stock_ts_code')} - 1e-6) AS is_up,
               (NOT is_new AND pre_close > 0 AND amount > 0 AND close <= {dn_px_sql('pre_close', 'lim', 'stock_ts_code')} + 1e-6) AS is_dn
        FROM s
        """,
        dates,
    )


def run(start, end, n, json_path):
    from market_feature_store.db import DatabaseLockedError, connect, connect_read_only_with_retry

    try:
        con = connect_read_only_with_retry(
            attempts=int(os.environ.get("REVIEW_GATE_LOCK_ATTEMPTS", "13")),
            delay_seconds=float(os.environ.get("REVIEW_GATE_LOCK_DELAY_SECONDS", "10")),
            opener=lambda: connect(read_only=True),
        )
    except DatabaseLockedError as exc:
        print("RESULT: BLOCKED")
        print(f"- {exc}")
        return EXIT_BLOCKED

    out = {"generated_at": datetime.now().isoformat(timespec="seconds"), "families": {}, "bad_base_days": [], "days": {}}
    try:
        dates = pick_dates(con, start, end, n)
        if not dates:
            print("没有可对账的完整日")
            return EXIT_FAIL
        print(f"对账日 {len(dates)} 个: {dates[0]} ~ {dates[-1]}")
        ph = ",".join("?" for _ in dates)
        build_lim(con, dates)

        # ---- A. 市场总览
        rows = q(con, f"""
            WITH mine AS (
              SELECT trade_date, COUNT(*) FILTER (WHERE pct_chg > 0) adv,
                     SUM(amount) FILTER (WHERE stock_ts_code NOT LIKE '%.BJ') amt_ex_bj,
                     COUNT(*) FILTER (WHERE is_up AND NOT is_st) lu, COUNT(*) FILTER (WHERE is_dn AND NOT is_st) ld
              FROM lim GROUP BY 1)
            SELECT CAST(f.trade_date AS VARCHAR), f.advancers, m.adv, f.total_amount, m.amt_ex_bj, f.limit_up, m.lu, f.limit_down, m.ld
            FROM fact_market_daily f JOIN mine m USING (trade_date) WHERE f.trade_date IN ({ph}) ORDER BY 1""", dates)
        bad_days = set()
        per_day = {}
        for d, fa, ma, ft, mx, flu, mlu, fld, mld in rows:
            ratio = ft / mx if (ft and mx) else None
            if ratio is None or abs(ratio - 1) > BAD_BASE_RATIO:
                bad_days.add(d)
            per_day[d] = {"advancers": (fa, ma), "amount_ratio": ratio, "limit_up": (flu, mlu), "limit_down": (fld, mld)}
        clean = [d for d in dates if d not in bad_days]
        out["bad_base_days"] = sorted(bad_days)
        if bad_days:
            print(f"!! 底数据坏日（我们的沪深成交额与 fph 差 >{BAD_BASE_RATIO:.0%}，剔出统计，需用 mootdx 重抓）: {sorted(bad_days)}")
        print("\n== A. 市场总览（fph | 自算）==")
        print(f"{'date':<11}{'涨家数':>14}{'额比fph/自算':>12}{'涨停':>12}{'跌停':>12}")
        for d in dates:
            p = per_day[d]
            flag = "  <- 坏日" if d in bad_days else ""
            print(f"{d:<11}{f'{p['advancers'][0]}|{p['advancers'][1]}':>14}{(f'{p['amount_ratio']:.4f}' if p['amount_ratio'] else '-'):>12}"
                  f"{f'{p['limit_up'][0]}|{p['limit_up'][1]}':>12}{f'{p['limit_down'][0]}|{p['limit_down'][1]}':>12}{flag}")

        def share(pred):
            vals = [pred(per_day[d]) for d in clean]
            return sum(vals) / len(vals) if vals else 0.0

        fam = out["families"]
        fam["advancers"] = share(lambda p: abs(p["advancers"][0] - p["advancers"][1]) <= 10)
        fam["total_amount"] = share(lambda p: p["amount_ratio"] is not None and 0.998 <= p["amount_ratio"] <= 1.002)
        fam["limit_up"] = share(lambda p: abs(p["limit_up"][0] - p["limit_up"][1]) <= 6)
        fam["limit_down"] = share(lambda p: abs(p["limit_down"][0] - p["limit_down"][1]) <= 6)

        # 量能派生
        rows = q(con, f"""
            WITH t AS (
              SELECT trade_date, total_amount, LAG(total_amount) OVER (ORDER BY trade_date) prev,
                     AVG(total_amount) OVER (ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) ma20,
                     amount_vs_yesterday_pct, amount_ma20, volume_ratio
              FROM fact_market_daily WHERE total_amount IS NOT NULL)
            SELECT CAST(trade_date AS VARCHAR), amount_vs_yesterday_pct, (total_amount/prev-1)*100, amount_ma20, ma20, volume_ratio, total_amount/ma20*100
            FROM t WHERE trade_date IN ({ph})""", dates)
        ok = [d for d, a, a2, m, m2, v, v2 in rows if d in clean and None not in (a, a2, m, m2, v, v2)
              and abs(a - a2) <= 0.1 and abs(m - m2) <= 0.0005 * m and abs(v - v2) <= 0.1]
        fam["volume_fields"] = len(ok) / max(len(clean), 1)

        # 前三行业
        rows = q(con, f"""
            WITH sw AS (
              SELECT trade_date, sw_l1, 100.0*amount/SUM(amount) OVER (PARTITION BY trade_date) AS sw_share,
                     ROW_NUMBER() OVER (PARTITION BY trade_date ORDER BY amount DESC) rk
              FROM fact_sw_l1_daily WHERE trade_date IN ({ph}))
            SELECT CAST(f.trade_date AS VARCHAR), f.industry_1, f.industry_2, f.industry_3, f.top3_industry_ratio,
                   MAX(CASE WHEN rk=1 THEN sw_l1 END), MAX(CASE WHEN rk=2 THEN sw_l1 END), MAX(CASE WHEN rk=3 THEN sw_l1 END),
                   SUM(CASE WHEN rk<=3 THEN sw_share END)
            FROM fact_market_daily f JOIN sw USING (trade_date) WHERE f.trade_date IN ({ph}) GROUP BY 1,2,3,4,5""", dates + dates)
        hit = [d for d, a, b, c, t, x, y, z, t2 in rows if d in clean and (a, b, c) == (x, y, z)]
        fam["top3_industry"] = len(hit) / max(len(clean), 1)
        top3_dev = [abs(t - t2) for d, a, b, c, t, x, y, z, t2 in rows if d in clean and t and t2]
        print(f"\n量能三项一致 {len(ok)}/{len(clean)}；前三行业名次一致 {len(hit)}/{len(clean)}，占比 |Δ| 最大 {max(top3_dev) if top3_dev else 0:.2f}pp")

        # ---- B. 涨停题材热度 / 涨停明细召回
        rows = q(con, f"""
            WITH mine AS (
              SELECT m.trade_date, m.sector_ts_code, COUNT(*) FILTER (WHERE l.is_up AND NOT l.is_st) lu
              FROM fact_sector_stock_daily m JOIN lim l ON l.trade_date = m.trade_date AND l.stock_ts_code = m.stock_ts_code
              WHERE m.trade_date IN ({ph}) GROUP BY 1,2)
            SELECT CAST(h.trade_date AS VARCHAR), COUNT(*), COUNT(*) FILTER (WHERE h.limit_up_count = COALESCE(mine.lu,0))
            FROM fact_theme_limit_heat_daily h LEFT JOIN mine ON mine.trade_date = h.trade_date AND mine.sector_ts_code = h.sector_ts_code
            WHERE h.trade_date IN ({ph}) AND h.dimension='sector' AND h.scope='all' GROUP BY 1""", dates + dates)
        tot = sum(n for d, n, k in rows if d in clean)
        ex = sum(k for d, n, k in rows if d in clean)
        fam["sector_limit_up"] = ex / max(tot, 1)
        rows = q(con, f"""
            WITH f AS (SELECT DISTINCT trade_date, stock_ts_code FROM fact_theme_limit_stock_daily WHERE trade_date IN ({ph})),
                 m AS (SELECT trade_date, stock_ts_code FROM lim WHERE is_up AND NOT is_st)
            SELECT CAST(f.trade_date AS VARCHAR), COUNT(*), COUNT(m.stock_ts_code)
            FROM f LEFT JOIN m USING (trade_date, stock_ts_code) GROUP BY 1""", dates)
        tot = sum(n for d, n, k in rows if d in clean)
        ex = sum(k for d, n, k in rows if d in clean)
        fam["limit_stock_recall"] = ex / max(tot, 1)
        print(f"逐板块涨停数一致率 {fam['sector_limit_up']:.1%}；fph 涨停明细召回 {fam['limit_stock_recall']:.1%}")

        # ---- C. 连板 boards / 龙头高度
        ladder = q(con, f"SELECT CAST(trade_date AS VARCHAR), stock_ts_code, boards, CAST(first_limit_date AS VARCHAR) FROM fact_limit_advance_daily WHERE trade_date IN ({ph})", dates)
        hist = q(con, f"""
            WITH s AS (SELECT trade_date, stock_ts_code, close, pre_close, amount, {LIMIT_RULE_SQL} lim
                       FROM fact_stock_daily WHERE trade_date >= CAST(? AS DATE) - INTERVAL 45 DAY AND trade_date <= ?)
            SELECT stock_ts_code, CAST(trade_date AS VARCHAR),
                   (pre_close > 0 AND amount > 0 AND close >= {up_px_sql('pre_close', 'lim', 'stock_ts_code')} - 1e-6)
            FROM s ORDER BY 1, 2""", [dates[0], dates[-1]])
        series = defaultdict(list)
        for code, d, up in hist:
            series[code].append((d, bool(up)))

        def streak(code, d):
            """到 d 为止的连续涨停天数；返回 (天数, 是否踩到坏底数据日)。"""
            k, tainted = 0, False
            for dd, up in reversed(series.get(code, [])):
                if dd > d:
                    continue
                if dd in bad_days:
                    tainted = True
                if not up:
                    break
                k += 1
            return k, tainted

        # streak 数到坏底数据日（含被它中断）就不可信，剔出统计——08-13 半日量把 8 条梯队多算了一板
        lad = [(d, c, b) for d, c, b, _f0 in ladder if d in clean and not streak(c, d)[1]]
        fam["ladder_boards"] = sum(1 for d, c, b in lad if streak(c, d)[0] == b) / max(len(lad), 1)
        mx_by_day = defaultdict(int)
        for d, c, b in lad:
            mx_by_day[d] = max(mx_by_day[d], streak(c, d)[0])
        tainted_days = {d for d, c, b, _f0 in ladder if d in clean and streak(c, d)[1]}
        lh = q(con, f"SELECT CAST(trade_date AS VARCHAR), height FROM fact_leader_height_daily WHERE trade_date IN ({ph})", dates)
        lh = [(d, h) for d, h in lh if d in clean and d not in tainted_days]
        fam["leader_height"] = sum(1 for d, h in lh if mx_by_day.get(d) == h) / max(len(lh), 1)
        print(f"连板 boards 一致率 {fam['ladder_boards']:.1%}（{len(lad)} 条，剔除踩坏日的 {len(ladder) - len(lad)} 条）；龙头高度一致 {fam['leader_height']:.1%}（{len(lh)} 日）")

        # ---- D. 新高（只出读数）
        cols = {r[0] for r in q(con, "DESCRIBE fact_stock_daily")}
        use_high = False
        if "high" in cols:  # 老库在第一次写入器跑过前没有这列
            has_high = q(con, f"SELECT COUNT(*) FILTER (WHERE high IS NOT NULL), COUNT(*) FROM fact_stock_daily WHERE trade_date IN ({ph})", dates)[0]
            use_high = bool(has_high[1]) and has_high[0] / has_high[1] > 0.9
        px = "high" if use_high else "close"
        rows = q(con, f"""
            WITH h AS (
              SELECT trade_date, stock_ts_code, {px} AS px,
                     MAX({px}) OVER (PARTITION BY stock_ts_code ORDER BY trade_date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) m20,
                     MAX({px}) OVER (PARTITION BY stock_ts_code ORDER BY trade_date ROWS BETWEEN 60 PRECEDING AND 1 PRECEDING) m60,
                     MAX({px}) OVER (PARTITION BY stock_ts_code ORDER BY trade_date ROWS BETWEEN 120 PRECEDING AND 1 PRECEDING) m120,
                     COUNT(*) OVER (PARTITION BY stock_ts_code ORDER BY trade_date ROWS BETWEEN 120 PRECEDING AND 1 PRECEDING) n_prev
              FROM fact_stock_daily WHERE trade_date >= CAST(? AS DATE) - INTERVAL 200 DAY AND trade_date <= ?),
            agg AS (SELECT trade_date, COUNT(*) FILTER (WHERE n_prev>=20 AND px>m20) c20, COUNT(*) FILTER (WHERE n_prev>=60 AND px>m60) c60,
                           COUNT(*) FILTER (WHERE n_prev>=120 AND px>m120) c120 FROM h WHERE trade_date IN ({ph}) GROUP BY 1)
            SELECT CAST(a.trade_date AS VARCHAR), f.stock_high_count_20d, a.c20, f.stock_high_count_60d, a.c60, f.stock_high_count_120d, a.c120
            FROM agg a JOIN fact_market_daily f USING (trade_date) ORDER BY 1""", [dates[0], dates[-1]] + dates)
        rel = [abs(a - b) / a for d, a, b, *_ in rows if d in clean and a]
        out["families"]["stock_high"] = {"price_basis": px, "rel_err_20d_median": median(rel) if rel else None,
                                         "sample": [(d, f"{a}|{b}", f"{c}|{e}", f"{g}|{h}") for d, a, b, c, e, g, h in rows[-3:]]}
        print(f"新高家数（{px} 口径）20 日相对误差中位 {median(rel) if rel else float('nan'):.1%}；最近三日 fph|自算: {out['families']['stock_high']['sample']}")

        # ---- E. 编辑层替代版 vs fupanhui（有 fupanhui 值的日子才有对照；只出读数）
        ed = q(con, f"""
            WITH u AS (
              SELECT trade_date, pct_chg, amount,
                     ROW_NUMBER() OVER (PARTITION BY trade_date ORDER BY pct_chg DESC) rn,
                     COUNT(*) OVER (PARTITION BY trade_date) n
              FROM fact_stock_daily WHERE trade_date IN ({ph}) AND stock_ts_code NOT LIKE '%.BJ' AND pct_chg IS NOT NULL AND amount > 0),
            t AS (SELECT trade_date, AVG(pct_chg) avg5, SUM(amount) amt5 FROM u WHERE rn <= ROUND(n * 0.05) GROUP BY 1)
            SELECT CAST(f.trade_date AS VARCHAR), f.strength_avg_pct, t.avg5, f.strength_amount, t.amt5, f.strength_status, f.volume_state, f.volume_ratio
            FROM fact_market_daily f JOIN t USING (trade_date) WHERE f.trade_date IN ({ph}) AND f.strength_avg_pct IS NOT NULL
              AND f.strength_source NOT LIKE 'local:%'""", dates + dates)
        if ed:
            def _status(a):
                return "冰点" if a < 2 else "正常" if a < 5 else "强势" if a < 8 else "沸点"

            def _vol(v):
                return None if v is None else ("缩量观望" if v < 85 else "正常量能" if v < 100 else "主线抱团" if v < 120 else "放量突破")

            rel = [abs(a5 - a) / a for d, a, a5, *_ in ed if d in clean and a]
            st_hit = sum(1 for d, a, a5, *_r in ed if d in clean and _status(a5) == _r[2])
            vs_pairs = [(vs_, _vol(vr)) for d, a, a5, amt, amt5, st, vs_, vr in ed if d in clean and vs_ in ("缩量观望", "正常量能", "主线抱团", "放量突破")]
            vs_hit = sum(1 for a_, b_ in vs_pairs if a_ == b_)
            n_ed = sum(1 for d, *_ in ed if d in clean)
            out["families"]["editorial"] = {
                "strength_avg_pct_rel_err_median": median(rel) if rel else None,
                "strength_status_agree": st_hit / max(n_ed, 1),
                "volume_state_agree": vs_hit / max(len(vs_pairs), 1) if vs_pairs else None,
                "days": n_ed,
            }
            print(f"编辑层替代版 vs fph（{n_ed} 日）：强度均涨幅(前5%口径) 相对误差中位 {median(rel) if rel else float('nan'):.1%}；"
                  f"强度状态一致 {st_hit}/{n_ed}；量能状态一致 {vs_hit}/{len(vs_pairs)}")

        # ---- F. 主线 / 周期阶段：local 与 fupanhui 同日都有时才有对照（fupanhui 恢复后自动出读数）
        ml = q(con, f"""
            WITH f AS (SELECT trade_date, theme_name FROM fact_mainline_theme_daily WHERE source NOT LIKE 'local:%' AND trade_date IN ({ph})),
                 l AS (SELECT trade_date, theme_name FROM fact_mainline_theme_daily WHERE source LIKE 'local:%' AND trade_date IN ({ph}))
            SELECT CAST(d.trade_date AS VARCHAR),
                   (SELECT COUNT(*) FROM f WHERE f.trade_date = d.trade_date AND theme_name IN (SELECT theme_name FROM l WHERE l.trade_date = d.trade_date)),
                   (SELECT COUNT(DISTINCT theme_name) FROM (SELECT theme_name FROM f WHERE f.trade_date = d.trade_date UNION SELECT theme_name FROM l WHERE l.trade_date = d.trade_date))
            FROM (SELECT DISTINCT trade_date FROM f INTERSECT SELECT DISTINCT trade_date FROM l) d""", dates + dates)
        if ml:
            jac = [inter / uni for _d, inter, uni in ml if uni]
            out["families"]["mainline_jaccard"] = {"days": len(jac), "median": median(jac) if jac else None}
            print(f"主线题材 local vs fph 同日对照 {len(jac)} 日：Jaccard 中位 {median(jac) if jac else float('nan'):.2f}")
        st = q(con, f"""
            SELECT COUNT(*), COUNT(*) FILTER (WHERE l.market_stage = f.market_stage)
            FROM fact_market_daily f JOIN fact_market_daily l ON l.trade_date = f.trade_date
            WHERE f.trade_date IN ({ph}) AND f.market_stage IS NOT NULL AND f.market_stage_source IS NULL AND l.market_stage_source LIKE 'local:%'""", dates) if "market_stage_source" in {r[0] for r in q(con, "DESCRIBE fact_market_daily")} else []
        # 同一行不可能同时存两份标签；恢复访问后 fupanhui 标签走 ops 对照表再比。这里只在两份都在时输出。
        if st and st[0][0]:
            out["families"]["stage_agree"] = st[0][1] / st[0][0]
            print(f"周期阶段 local vs fph 一致 {st[0][1]}/{st[0][0]}")

        # 核心个股：口径已反推为「当日成交额前 50」，所以这里对的是**全历史**，不只抽样日。
        # 不命中的行按「我们当天有没有这只股的行」拆开——不拆的话数据缺口会伪装成口径差。
        cs = q(con, """
            WITH t AS (SELECT trade_date, stock_ts_code,
                              ROW_NUMBER() OVER (PARTITION BY trade_date ORDER BY amount DESC) rn
                       FROM fact_stock_daily),
                 top50 AS (SELECT trade_date, stock_ts_code FROM t WHERE rn <= 50)
            SELECT COUNT(*),
                   COUNT(*) FILTER (WHERE top50.stock_ts_code IS NOT NULL),
                   COUNT(*) FILTER (WHERE top50.stock_ts_code IS NULL AND s.stock_ts_code IS NULL),
                   COUNT(*) FILTER (WHERE top50.stock_ts_code IS NULL AND s.stock_ts_code IS NOT NULL
                                      AND s.amount IS NULL),
                   COUNT(*) FILTER (WHERE top50.stock_ts_code IS NULL AND s.amount IS NOT NULL),
                   COUNT(DISTINCT c.trade_date)
            FROM fact_core_stock_daily c
            LEFT JOIN top50 ON top50.trade_date = c.trade_date AND top50.stock_ts_code = c.stock_ts_code
            LEFT JOIN fact_stock_daily s ON s.trade_date = c.trade_date AND s.stock_ts_code = c.stock_ts_code
            WHERE c.source NOT LIKE 'local:%'""")
        if cs and cs[0][0]:
            n, hit, no_row, null_amt, value_gap, days = cs[0]
            out["families"]["core_stock_replay"] = {
                "days": days, "rows": n, "hit": hit,
                "miss": {"no_row": no_row, "null_amount": null_amt, "value_gap": value_gap}}
            print(f"核心个股复刻 {days} 日 {n} 行：命中成交额前 50 {hit}/{n} = {hit / n:.2%}")
            # 未命中必须拆到底数据层面。三个桶都在**我们这一侧**，没有一个是口径差；
            # 只报一个总数会让人以为「复刻不准」，而真相是那几天我们的 amount 本身就是坏的。
            print(f"  未命中 {n - hit} 行归因：没有这只股的行 {no_row} | 有行但 amount 为空 {null_amt}"
                  f" | 有值但我们的偏小 {value_gap}")

        # ---- 判定
        print("\n== 判定（干净日 %d 个）==" % len(clean))
        failed = []
        for key, (desc, gate) in GATES.items():
            val = fam[key]
            status = "PASS" if val >= gate else "FAIL"
            if status == "FAIL":
                failed.append(key)
            print(f"[{status}] {key:<18} {val:6.1%}  门 {gate:.0%}  {desc}")
        for key, desc in INFO_ONLY.items():
            print(f"[INFO] {key:<18} {desc}")
        out["clean_days"] = clean
        out["failed"] = failed
        out["ok"] = not failed
        print(f"\nRESULT: {'FAIL' if failed else 'PASS'} | 越门族 {failed or '无'} | 坏底数据日 {sorted(bad_days) or '无'}")
    finally:
        con.close()
    if json_path:
        Path(json_path).write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print(f"json -> {json_path}")
    return EXIT_FAIL if out.get("failed") else 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None)
    p.add_argument("--days", type=int, default=15, help="未给 --start/--end 时取最近 N 个完整日，默认 15")
    p.add_argument("--json", default=None)
    p.add_argument("--db", default=None, help="指向别的库（如 staging）")
    a = p.parse_args(argv)
    if a.db:
        os.environ["MARKET_FEATURE_STORE_DB"] = a.db
    return run(a.start, a.end, a.days, a.json)


if __name__ == "__main__":
    raise SystemExit(main())
