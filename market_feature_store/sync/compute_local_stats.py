"""不靠 fupanhui 的本地加工层（2026-09-07 起，剥离路线第一批）。

三件事，全部只读自己的底数据（fact_stock_daily 东财/mootdx、fact_sw_l1_daily 申万官方、
fact_sector_stock_daily 名单）写本地加工表，source 一律 ``local:*``：

1. ``carry_forward_universe``：名单冻结——把最近一份 published 宇宙快照按当日重新发布，
   provider_source='local:carry'。fupanhui 停了以后 stitch/sector-daily-local 才有当日宇宙可用。
2. ``compute_limit_stats_local``：涨跌停统计（题材涨停热度 + 涨停明细 + 连板梯队 + 龙头高度）。
3. ``compute_market_overview_local``：fact_market_daily 的数字层（沪深总额/涨家数/涨跌停/量能/前三行业/新高家数）。

口径全部来自 skills/duckdb-backfill/scripts/qa_local_vs_fupanhui.py 对 08-14~09-02 的双轨实测：
- 涨停价：沪深四舍五入到分；北交所向下取整到分。板幅 北交所 30% / 创业科创 20% / 其余 10%（ST 也 10%）。
- 涨停统计不计 ST、不计新股（名字 N/C 开头）、不计停牌（amount=0）——fupanhui 口径如此，双轨才对得上。
- fupanhui 总成交额 = 沪深不含北交所；MA20 含当日；量能比 = 当日/MA20×100；前三行业 = 申万一级份额。
- 新高按日内最高价（high 列），没有 high 的日子不写（不用收盘价凑，差 ±20%）。

写入策略：只在该表当日**没有非 local 来源的行**时写（fupanhui 的历史值是参照，不覆盖）；``force=True`` 才覆盖。
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from ..db import connect, init_db
from ..sector_universe import SectorDescriptor, SectorUniverseStore

LOCAL_LIMIT_SOURCE = "local:limit-rule"
LOCAL_OVERVIEW_SOURCE = "local:overview"
CARRY_PROVIDER = "local:carry"

LIMIT_RULE_SQL = """
    CASE WHEN stock_ts_code LIKE '%.BJ' THEN 0.30
         WHEN stock_ts_code LIKE '30%' OR stock_ts_code LIKE '68%' THEN 0.20
         ELSE 0.10 END
"""


def up_px_sql(pre: str, lim: str, code: str) -> str:
    return (f"CASE WHEN {code} LIKE '%.BJ' THEN FLOOR({pre}*(1+{lim})*100 + 1e-6)/100 "
            f"ELSE ROUND({pre}*(1+{lim}) + 1e-9, 2) END")


def dn_px_sql(pre: str, lim: str, code: str) -> str:
    return (f"CASE WHEN {code} LIKE '%.BJ' THEN CEIL({pre}*(1-{lim})*100 - 1e-6)/100 "
            f"ELSE ROUND({pre}*(1-{lim}) + 1e-9, 2) END")


def _as_date(value) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _has_foreign_rows(con, table: str, td: date) -> int:
    return con.execute(
        f"SELECT COUNT(*) FROM {table} WHERE trade_date = ? AND (source IS NULL OR source NOT LIKE 'local:%')",
        [td],
    ).fetchone()[0]


# ---------------------------------------------------------------------------
# 1. 名单冻结
# ---------------------------------------------------------------------------
def carry_forward_universe(trade_date, *, con=None, provider: str = CARRY_PROVIDER,
                           supersede: bool = False, base_date=None) -> dict:
    """把最近一份 published 宇宙按当日重新发布。

    supersede: 当日已有 published 快照也照样承接并顶替（原快照留作 superseded）——
    用于把「identity 已变但成分名单没抓到」的那天（如 2026-09-03，22 个板块 expected 变了、成分 0 行）
    冻回最后一份完整名单对应的宇宙，否则 stitch 会把这些板块留给已不存在的 provider。
    base_date: 指定承接哪一天的快照，默认取 trade_date 之前最近一份。
    """
    td = _as_date(trade_date)
    own = con is None
    if own:
        init_db()
        con = connect()
    try:
        existing = con.execute(
            "SELECT snapshot_id, provider_source FROM ops_sector_universe_snapshot_daily WHERE trade_date = ? AND status = 'published'",
            [td],
        ).fetchall()
        if existing and not supersede:
            return {"trade_date": td.isoformat(), "action": "exists", "snapshot_id": existing[0][0],
                    "provider_source": existing[0][1], "sectors": None, "base_date": None}
        if base_date is not None:
            base = con.execute(
                """
                SELECT trade_date, snapshot_id, provider_source FROM ops_sector_universe_snapshot_daily
                WHERE status = 'published' AND trade_date = ? ORDER BY captured_at DESC LIMIT 1
                """,
                [_as_date(base_date)],
            ).fetchone()
        else:
            base = con.execute(
                """
                SELECT trade_date, snapshot_id, provider_source FROM ops_sector_universe_snapshot_daily
                WHERE status = 'published' AND trade_date < ?
                ORDER BY trade_date DESC, captured_at DESC LIMIT 1
                """,
                [td],
            ).fetchone()
        if base is None:
            raise RuntimeError(f"{td} 之前没有任何 published 宇宙，无法承接")
        base_date, base_snapshot, _base_provider = base
        rows = con.execute(
            """
            SELECT u.sector_ts_code, u.sector_name, u.expected_stock_count, d.sw_l1
            FROM fact_sector_universe_daily u LEFT JOIN dim_sector d ON d.sector_ts_code = u.sector_ts_code
            WHERE u.trade_date = ? AND u.snapshot_id = ? ORDER BY 1
            """,
            [base_date, base_snapshot],
        ).fetchall()
        sectors = [SectorDescriptor(code, name, int(n), sw) for code, name, n, sw in rows]
        published = SectorUniverseStore(con).publish_snapshot(
            trade_date=td, provider_source=provider, sectors=sectors, captured_at=datetime.now(timezone.utc),
        )
        if existing:
            # store 只在同 provider 内顶替；跨 provider 的旧 published 要显式标 superseded，
            # 否则 identity_delta / sector-daily-local 会看到两份 published 直接拒跑。
            con.execute(
                "UPDATE ops_sector_universe_snapshot_daily SET status = 'superseded' "
                "WHERE trade_date = ? AND status = 'published' AND snapshot_id <> ?",
                [td, published.snapshot_id],
            )
        return {"trade_date": td.isoformat(), "action": "carried-superseding" if existing else "carried", "snapshot_id": published.snapshot_id,
                "provider_source": provider, "sectors": len(sectors), "base_date": _as_date(base_date).isoformat()}
    finally:
        if own:
            con.close()


# ---------------------------------------------------------------------------
# 2. 涨跌停统计
# ---------------------------------------------------------------------------
def _limit_flags(con, td: date, lookback_days: int = 60) -> tuple[list[tuple], dict[str, list[tuple[date, bool]]]]:
    """返回 (当日全A带涨跌停判定的行, 每只股近 lookback 天的 (日期, 是否涨停) 序列)。"""
    since = td - timedelta(days=lookback_days)
    rows = con.execute(
        f"""
        WITH s AS (
          SELECT trade_date, stock_ts_code, stock_name, close, pre_close, pct_chg, amount,
                 {LIMIT_RULE_SQL} AS lim,
                 (stock_name LIKE 'N%' OR stock_name LIKE 'C%') AS is_new,
                 (stock_name LIKE '%ST%') AS is_st
          FROM fact_stock_daily WHERE trade_date >= ? AND trade_date <= ?
        )
        SELECT trade_date, stock_ts_code, stock_name, close, pre_close, pct_chg, amount, is_new, is_st,
               (NOT is_new AND pre_close > 0 AND amount > 0 AND close >= {up_px_sql('pre_close', 'lim', 'stock_ts_code')} - 1e-6) AS is_up,
               (NOT is_new AND pre_close > 0 AND amount > 0 AND close <= {dn_px_sql('pre_close', 'lim', 'stock_ts_code')} + 1e-6) AS is_dn
        FROM s ORDER BY stock_ts_code, trade_date
        """,
        [since, td],
    ).fetchall()
    series: dict[str, list[tuple[date, bool]]] = defaultdict(list)
    today: list[tuple] = []
    for r in rows:
        d = _as_date(r[0])
        series[r[1]].append((d, bool(r[9])))
        if d == td:
            today.append(r)
    return today, series


def _streak(seq: list[tuple[date, bool]], td: date) -> tuple[int, date | None]:
    k, first = 0, None
    for d, up in reversed(seq):
        if d > td:
            continue
        if not up:
            break
        k += 1
        first = d
    return k, first


def compute_limit_stats_local(trade_date, *, con=None, force: bool = False, min_boards: int = 2) -> dict:
    td = _as_date(trade_date)
    own = con is None
    if own:
        init_db()
        con = connect()
    try:
        skipped = {}
        for table in ("fact_theme_limit_heat_daily", "fact_theme_limit_stock_daily",
                      "fact_limit_advance_daily", "fact_leader_height_daily"):
            n = _has_foreign_rows(con, table, td)
            if n and not force:
                skipped[table] = n
        if skipped:
            return {"trade_date": td.isoformat(), "action": "skipped-has-foreign-rows", "skipped": skipped}

        today, series = _limit_flags(con, td)
        if not today:
            raise RuntimeError(f"{td} fact_stock_daily 无行，先同步个股日线")
        up_stocks = {r[1]: r for r in today if r[9] and not r[8]}  # 涨停且非 ST
        market_lu = len(up_stocks)
        market_ld = sum(1 for r in today if r[10] and not r[8])
        streaks = {code: _streak(series[code], td) for code in up_stocks}

        members = con.execute(
            "SELECT sector_ts_code, sector_name, stock_ts_code, sw_l1 FROM fact_sector_stock_daily WHERE trade_date = ?",
            [td],
        ).fetchall()
        by_sector: dict[str, dict] = {}
        for code, name, stock, sw in members:
            sec = by_sector.setdefault(code, {"name": name, "total": 0, "hits": []})
            sec["total"] += 1
            if stock in up_stocks:
                sec["hits"].append((stock, sw))

        now = datetime.now()
        con.execute("BEGIN TRANSACTION")
        for table in ("fact_theme_limit_heat_daily", "fact_theme_limit_stock_daily",
                      "fact_limit_advance_daily", "fact_leader_height_daily"):
            con.execute(f"DELETE FROM {table} WHERE trade_date = ?", [td])

        heat_rows, detail_rows = [], []
        ranked = sorted(((c, s) for c, s in by_sector.items() if s["hits"]), key=lambda x: (-len(x[1]["hits"]), x[0]))
        for rank, (code, sec) in enumerate(ranked, start=1):
            hits = sec["hits"]
            top = sorted(hits, key=lambda h: -streaks[h[0]][0])[:5]
            heat_rows.append((
                td, code, sec["name"], "sector", "all", "final", False, now,
                market_lu, len(hits), sec["total"],
                round(100.0 * len(hits) / sec["total"], 2) if sec["total"] else None,
                round(100.0 * len(hits) / market_lu, 2) if market_lu else None,
                None, rank,
                json.dumps([{"ts_code": s, "name": up_stocks[s][2], "limit_times": streaks[s][0]} for s, _ in top], ensure_ascii=False),
                LOCAL_LIMIT_SOURCE, now,
            ))
            for stock, sw in hits:
                r = up_stocks[stock]
                detail_rows.append((td, code, sec["name"], stock, r[2], r[3], r[5], r[6], streaks[stock][0], sw,
                                    LOCAL_LIMIT_SOURCE, now))
        if heat_rows:
            con.executemany(
                """
                INSERT INTO fact_theme_limit_heat_daily
                  (trade_date, sector_ts_code, sector_name, dimension, scope, data_stage, is_realtime, source_update_time,
                   market_limit_up_count, limit_up_count, total_count, limit_up_ratio, market_share, fd_amount, rank,
                   top_stocks_json, source, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                heat_rows,
            )
        if detail_rows:
            con.executemany(
                """
                INSERT INTO fact_theme_limit_stock_daily
                  (trade_date, sector_ts_code, sector_name, stock_ts_code, stock_name, price, pct_chg, amount,
                   limit_times, sw_l1, source, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                detail_rows,
            )

        ladder = []
        for stock, (boards, first) in streaks.items():
            if boards >= min_boards:
                r = up_stocks[stock]
                theme = next((sec["name"] for _c, sec in ranked if any(h[0] == stock for h in sec["hits"])), None)
                ladder.append((td, stock, r[2], boards, first, theme, r[5], None, LOCAL_LIMIT_SOURCE, now))
        if ladder:
            con.executemany(
                """
                INSERT INTO fact_limit_advance_daily
                  (trade_date, stock_ts_code, stock_name, boards, first_limit_date, theme, pct_chg, promotion_rate, source, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                ladder,
            )
        leader = max(streaks.items(), key=lambda kv: (kv[1][0], up_stocks[kv[0]][6] or 0), default=None) if streaks else None
        if leader is not None:
            stock, (height, _first) = leader
            con.execute(
                """
                INSERT INTO fact_leader_height_daily
                  (trade_date, height, leader_ts_code, leader_name, limit_times, fd_amount, first_limit_time, source, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                [td, height, stock, up_stocks[stock][2], height, None, None, LOCAL_LIMIT_SOURCE, now],
            )
        con.execute("COMMIT")
        return {
            "trade_date": td.isoformat(), "action": "written",
            "market_limit_up": market_lu, "market_limit_down": market_ld,
            "sectors_with_limit_up": len(heat_rows), "detail_rows": len(detail_rows),
            "ladder_rows": len(ladder), "leader_height": leader[1][0] if leader else 0,
            "members_seen": len(members),
        }
    except Exception:
        try:
            con.execute("ROLLBACK")
        except Exception:  # noqa: BLE001
            pass
        raise
    finally:
        if own:
            con.close()


# ---------------------------------------------------------------------------
# 3. 市场总览数字层
# ---------------------------------------------------------------------------
HIGH_WINDOWS = {"20d": 20, "60d": 60, "120d": 120, "1y": 244, "2y": 488, "3y": 732}


def _concentration_state(ratio):
    """与 fupanhui 同口径（sync_fupanhui_market_daily._concentration_state）：<35 分散，≤45 正常，>45 集中。"""
    from .sync_fupanhui_market_daily import _concentration_state as _fph

    return _fph(ratio)


def compute_market_overview_local(trade_date, *, con=None, force: bool = False) -> dict:
    td = _as_date(trade_date)
    own = con is None
    if own:
        init_db()
        con = connect()
    try:
        row = con.execute(
            "SELECT source, total_amount, advancers FROM fact_market_daily WHERE trade_date = ?", [td]
        ).fetchone()
        if row and row[0] and not str(row[0]).startswith("local:") and row[1] is not None and row[2] is not None and not force:
            return {"trade_date": td.isoformat(), "action": "skipped-has-foreign-values", "source": row[0]}

        today, _series = _limit_flags(con, td, lookback_days=1)
        if not today:
            raise RuntimeError(f"{td} fact_stock_daily 无行，先同步个股日线")
        total_amount = round(sum(float(r[6] or 0) for r in today if not r[1].endswith(".BJ")), 2)
        advancers = sum(1 for r in today if r[5] is not None and r[5] > 0)
        limit_up = sum(1 for r in today if r[9] and not r[8])
        limit_down = sum(1 for r in today if r[10] and not r[8])

        hist = con.execute(
            "SELECT trade_date, total_amount FROM fact_market_daily WHERE trade_date < ? AND total_amount IS NOT NULL ORDER BY trade_date DESC LIMIT 19",
            [td],
        ).fetchall()
        prev_total = float(hist[0][1]) if hist else None
        window = [total_amount] + [float(h[1]) for h in hist]
        ma20 = round(sum(window) / len(window), 2)
        vs_yesterday = round((total_amount / prev_total - 1) * 100, 2) if prev_total else None
        volume_ratio = round(total_amount / ma20 * 100, 2) if ma20 else None

        sw = con.execute(
            "SELECT sw_l1, amount FROM fact_sw_l1_daily WHERE trade_date = ? AND amount IS NOT NULL ORDER BY amount DESC", [td]
        ).fetchall()
        sw_total = sum(float(a) for _n, a in sw) or None
        top3 = [(n, round(100.0 * float(a) / sw_total, 1)) for n, a in sw[:3]] if sw_total else []
        while len(top3) < 3:
            top3.append((None, None))
        top3_ratio = round(sum(r for _n, r in top3 if r is not None), 1) if sw_total else None

        highs = {k: None for k in HIGH_WINDOWS}
        cols = {r[0] for r in con.execute("DESCRIBE fact_stock_daily").fetchall()}
        if "high" in cols:
            has_high = con.execute(
                "SELECT COUNT(high), COUNT(*) FROM fact_stock_daily WHERE trade_date = ?", [td]
            ).fetchone()
            if has_high[1] and has_high[0] / has_high[1] > 0.9:
                exprs = ", ".join(
                    f"COUNT(*) FILTER (WHERE n_prev >= {n} AND px > m{n})" for n in HIGH_WINDOWS.values()
                )
                wins = ", ".join(
                    f"MAX(high) OVER (PARTITION BY stock_ts_code ORDER BY trade_date ROWS BETWEEN {n} PRECEDING AND 1 PRECEDING) AS m{n}"
                    for n in HIGH_WINDOWS.values()
                )
                res = con.execute(
                    f"""
                    WITH h AS (
                      SELECT trade_date, stock_ts_code, high AS px, {wins},
                             COUNT(high) OVER (PARTITION BY stock_ts_code ORDER BY trade_date ROWS BETWEEN 732 PRECEDING AND 1 PRECEDING) AS n_prev
                      FROM fact_stock_daily WHERE trade_date <= ? AND trade_date >= CAST(? AS DATE) - INTERVAL 1200 DAY AND high IS NOT NULL
                    )
                    SELECT {exprs} FROM h WHERE trade_date = ?
                    """,
                    [td, td, td],
                ).fetchone()
                highs = dict(zip(HIGH_WINDOWS, res))

        # 周均线/偏离度：上证近 5 个交易日收盘均值（index-daily 已写 sh_index_close 时才算；已有值不覆盖）
        sh_rows = con.execute(
            "SELECT trade_date, sh_index_close FROM fact_market_daily WHERE trade_date <= ? AND sh_index_close IS NOT NULL ORDER BY trade_date DESC LIMIT 5",
            [td],
        ).fetchall()
        sh_close = float(sh_rows[0][1]) if sh_rows and _as_date(sh_rows[0][0]) == td else None
        sh_ma5 = round(sum(float(r[1]) for r in sh_rows) / 5, 2) if (sh_close is not None and len(sh_rows) == 5) else None
        sh_dev = round((sh_close / sh_ma5 - 1) * 100, 2) if (sh_close and sh_ma5) else None

        now = datetime.now()
        con.execute("BEGIN TRANSACTION")
        con.execute(
            """
            INSERT INTO fact_market_daily (trade_date, total_amount, amount_vs_yesterday_pct, amount_ma20, volume_ratio,
                advancers, limit_up, limit_down, top3_industry_ratio, concentration_state,
                industry_1, industry_1_ratio, industry_2, industry_2_ratio, industry_3, industry_3_ratio,
                stock_high_count_20d, stock_high_count_60d, stock_high_count_120d, stock_high_count_1y,
                stock_high_count_2y, stock_high_count_3y, stock_high_source, stock_high_updated_at,
                sh_week_ma, sh_deviation_pct, sh_week_ma_source, source, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT (trade_date) DO UPDATE SET
                total_amount = EXCLUDED.total_amount, amount_vs_yesterday_pct = EXCLUDED.amount_vs_yesterday_pct,
                amount_ma20 = EXCLUDED.amount_ma20, volume_ratio = EXCLUDED.volume_ratio,
                advancers = EXCLUDED.advancers, limit_up = EXCLUDED.limit_up, limit_down = EXCLUDED.limit_down,
                top3_industry_ratio = EXCLUDED.top3_industry_ratio, concentration_state = EXCLUDED.concentration_state,
                industry_1 = EXCLUDED.industry_1, industry_1_ratio = EXCLUDED.industry_1_ratio,
                industry_2 = EXCLUDED.industry_2, industry_2_ratio = EXCLUDED.industry_2_ratio,
                industry_3 = EXCLUDED.industry_3, industry_3_ratio = EXCLUDED.industry_3_ratio,
                stock_high_count_20d = COALESCE(EXCLUDED.stock_high_count_20d, fact_market_daily.stock_high_count_20d),
                stock_high_count_60d = COALESCE(EXCLUDED.stock_high_count_60d, fact_market_daily.stock_high_count_60d),
                stock_high_count_120d = COALESCE(EXCLUDED.stock_high_count_120d, fact_market_daily.stock_high_count_120d),
                stock_high_count_1y = COALESCE(EXCLUDED.stock_high_count_1y, fact_market_daily.stock_high_count_1y),
                stock_high_count_2y = COALESCE(EXCLUDED.stock_high_count_2y, fact_market_daily.stock_high_count_2y),
                stock_high_count_3y = COALESCE(EXCLUDED.stock_high_count_3y, fact_market_daily.stock_high_count_3y),
                stock_high_source = COALESCE(EXCLUDED.stock_high_source, fact_market_daily.stock_high_source),
                stock_high_updated_at = COALESCE(EXCLUDED.stock_high_updated_at, fact_market_daily.stock_high_updated_at),
                sh_week_ma = COALESCE(fact_market_daily.sh_week_ma, EXCLUDED.sh_week_ma),
                sh_deviation_pct = COALESCE(fact_market_daily.sh_deviation_pct, EXCLUDED.sh_deviation_pct),
                sh_week_ma_source = COALESCE(fact_market_daily.sh_week_ma_source, EXCLUDED.sh_week_ma_source),
                source = EXCLUDED.source, updated_at = EXCLUDED.updated_at
            """,
            [td, total_amount, vs_yesterday, ma20, volume_ratio, advancers, limit_up, limit_down, top3_ratio,
             _concentration_state(top3_ratio),
             top3[0][0], top3[0][1], top3[1][0], top3[1][1], top3[2][0], top3[2][1],
             highs["20d"], highs["60d"], highs["120d"], highs["1y"], highs["2y"], highs["3y"],
             "local:high-ohlc" if highs["20d"] is not None else None, now if highs["20d"] is not None else None,
             sh_ma5, sh_dev, "ma_recompute" if sh_ma5 is not None else None,
             LOCAL_OVERVIEW_SOURCE, now],
        )
        con.execute("COMMIT")
        return {
            "trade_date": td.isoformat(), "action": "written", "total_amount": total_amount, "advancers": advancers,
            "limit_up": limit_up, "limit_down": limit_down, "amount_ma20": ma20, "volume_ratio": volume_ratio,
            "top3": top3, "top3_ratio": top3_ratio, "stock_high_20d": highs["20d"], "sh_week_ma": sh_ma5,
        }
    except Exception:
        try:
            con.execute("ROLLBACK")
        except Exception:  # noqa: BLE001
            pass
        raise
    finally:
        if own:
            con.close()
