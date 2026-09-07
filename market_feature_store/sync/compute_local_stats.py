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


# ---------------------------------------------------------------------------
# 4. 编辑层自家替代版：强度 / 量能状态 / 冰点（周期阶段仍留空，见 docstring）
# ---------------------------------------------------------------------------
LOCAL_STRENGTH_SOURCE = "local:top5pct"
STRENGTH_TOP_FRACTION = 0.05  # 涨幅前 5% 个股（不含北交所）。与 fupanhui 的 strength_amount 中位误差 ~3%，尾部 25%
# fupanhui 405 个有标签日实测：强势 5.20~8.00、沸点 ≥8.01、正常 3.71~4.83、冰点 0.69 → 阈值 2 / 5 / 8，一致率 99.75%
STRENGTH_STATUS_BANDS = ((2.0, "冰点"), (5.0, "正常"), (8.0, "强势"), (float("inf"), "沸点"))
# fupanhui 当前口径四档，247 个有标签日一致率 100%
VOLUME_STATE_BANDS = ((85.0, "缩量观望"), (100.0, "正常量能"), (120.0, "主线抱团"), (float("inf"), "放量突破"))
# fupanhui ice_point JSON 里自述的分区：<78 极冰、[78,85) 接近冰点、[85,95) 偏冷、其余正常；资格判断依赖其周期阶段，本地不做
ICE_BANDS = ((78.0, "极冰"), (85.0, "接近冰点"), (95.0, "偏冷"), (float("inf"), "正常"))


def _band(value, bands):
    if value is None:
        return None
    for upper, label in bands:
        if value < upper:
            return label
    return bands[-1][1]


def compute_market_editorial_local(trade_date, *, con=None, force: bool = False) -> dict:
    """fact_market_daily 编辑层字段的自家替代版。

    - strength_*：涨幅前 5% 个股（不含北交所、剔停牌）的平均涨幅 / 成交额合计 / 占沪深总额比 / 与昨日强度额的边际变化；
      status 按 2/5/8 阈值。fupanhui 的 "top5" 集合定义未逆向出来，这是**自家口径**，双轨对照中位误差 ~3%。
    - volume_state：量能比四档。ice_point：量能比分区 JSON（不做周期资格判断）。
    - market_stage / stage_day / summary_keywords：**留空**。周期阶段是 fupanhui 的周期模型，价格趋势规则粗粒度一致率只有 58%，
      不值得放进日报标题；405 个有标签日可作训练集另立单。
    """
    td = _as_date(trade_date)
    own = con is None
    if own:
        init_db()
        con = connect()
    try:
        row = con.execute(
            "SELECT strength_source, strength_avg_pct, total_amount, volume_ratio FROM fact_market_daily WHERE trade_date = ?", [td]
        ).fetchone()
        if row is None or row[2] is None:
            raise RuntimeError(f"{td} fact_market_daily 无当日行或 total_amount 为空，先跑 compute-market-overview-local")
        if row[0] and not str(row[0]).startswith("local:") and row[1] is not None and not force:
            return {"trade_date": td.isoformat(), "action": "skipped-has-foreign-values", "strength_source": row[0]}
        total_amount, volume_ratio = float(row[2]), row[3]

        top = con.execute(
            """
            WITH u AS (
              SELECT pct_chg, amount FROM fact_stock_daily
              WHERE trade_date = ? AND stock_ts_code NOT LIKE '%.BJ' AND pct_chg IS NOT NULL AND amount > 0
            ), n AS (SELECT CAST(ROUND(COUNT(*) * ?) AS INT) AS k FROM u),
            t AS (SELECT * FROM u ORDER BY pct_chg DESC LIMIT (SELECT k FROM n))
            SELECT (SELECT k FROM n), AVG(pct_chg), SUM(amount) FROM t
            """,
            [td, STRENGTH_TOP_FRACTION],
        ).fetchone()
        k, avg_pct, amt = top
        if not k:
            raise RuntimeError(f"{td} fact_stock_daily 无行，先同步个股日线")
        avg_pct = round(float(avg_pct), 2)
        amt = round(float(amt), 2)
        amount_pct = round(100.0 * amt / total_amount, 2) if total_amount else None
        hist = con.execute(
            """
            SELECT strength_avg_pct, strength_amount FROM fact_market_daily
            WHERE trade_date < ? AND strength_avg_pct IS NOT NULL ORDER BY trade_date DESC LIMIT 20
            """,
            [td],
        ).fetchall()
        y_avg = float(hist[0][0]) if hist else None
        y_amt = float(hist[0][1]) if hist and hist[0][1] is not None else None
        marginal = round((amt / y_amt - 1) * 100, 2) if y_amt else None
        ma5 = round((sum(float(h[0]) for h in hist[:4]) + avg_pct) / (min(len(hist), 4) + 1), 2) if hist else avg_pct
        ma20 = round((sum(float(h[0]) for h in hist[:19]) + avg_pct) / (min(len(hist), 19) + 1), 2) if hist else avg_pct
        status = _band(avg_pct, STRENGTH_STATUS_BANDS)
        volume_state = _band(volume_ratio, VOLUME_STATE_BANDS)

        prev_ice = con.execute(
            "SELECT ice_point FROM fact_market_daily WHERE trade_date < ? AND ice_point IS NOT NULL ORDER BY trade_date DESC LIMIT 1", [td]
        ).fetchone()
        prev_day = 0
        if prev_ice and prev_ice[0]:
            try:
                prev_day = int(json.loads(str(prev_ice[0]).replace("'", '"')).get("ice_point_day") or 0)
            except Exception:  # noqa: BLE001
                prev_day = 0
        level = _band(volume_ratio, ICE_BANDS)
        is_ice = level in ("极冰", "接近冰点")
        ice = {
            "is_eligible": None,
            "is_ice_point": is_ice,
            "level": level,
            "confidence": "rule",
            "ice_point_day": (prev_day + 1) if is_ice else 0,
            "vol_ratio_ma20": volume_ratio,
            "reason": (f"vol_ratio_ma20={volume_ratio}%：<78 极冰 / [78,85) 接近冰点 / [85,95) 偏冷 / 其余正常；"
                       "本地规则只判量能分区，不做周期阶段资格判断（周期阶段未建模）"),
            "source": "local:ice-rule",
        }
        now = datetime.now()
        con.execute("BEGIN TRANSACTION")
        con.execute(
            """
            UPDATE fact_market_daily SET
                strength_avg_pct = ?, strength_amount_pct = ?, strength_amount = ?, strength_marginal_pct = ?,
                strength_yesterday_avg_pct = ?, strength_ma5_avg_pct = ?, strength_ma20_avg_pct = ?, strength_status = ?,
                strength_source = ?, strength_updated_at = ?,
                volume_state = ?, ice_point = ?, updated_at = ?
            WHERE trade_date = ?
            """,
            [avg_pct, amount_pct, amt, marginal, y_avg, ma5, ma20, status, LOCAL_STRENGTH_SOURCE, now,
             volume_state, json.dumps(ice, ensure_ascii=False), now, td],
        )
        con.execute("COMMIT")
        return {"trade_date": td.isoformat(), "action": "written", "top_k": int(k), "strength_avg_pct": avg_pct,
                "strength_amount": amt, "strength_amount_pct": amount_pct, "strength_marginal_pct": marginal,
                "strength_status": status, "volume_state": volume_state, "ice_level": level}
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
# 5. 新高名单（fact_stock_high_daily），按日内最高价
# ---------------------------------------------------------------------------
LOCAL_HIGH_SOURCE = "local:high-ohlc"
# 库里历史从 2023-09 起（≈730 根）：history 要 ≥720 根可比历史，3y 放宽到 700，避免「历史新高命中而 3 年新高缺席」
HIGH_PERIODS = (("history", "历史新高", 720), ("3y", "3年新高", 700), ("2y", "2年新高", 488),
                ("1y", "1年新高", 244), ("120d", "120日新高", 120), ("60d", "60日新高", 60), ("20d", "20日新高", 20))


def compute_stock_high_local(trade_date, *, con=None, force: bool = False) -> dict:
    """当日创 N 日新高的个股名单：high(D) > max(high 前 N 个交易日)。

    与 fupanhui 的差异（双轨 20 日相对误差中位 ~12%）：fupanhui 用前复权价，我们用裸价；库里历史从 2023-09 起，
    「历史新高」= 至少 700 根（≈3 年）可比历史内的新高。primary 取满足的最长周期。
    """
    td = _as_date(trade_date)
    own = con is None
    if own:
        init_db()
        con = connect()
    try:
        n = _has_foreign_rows(con, "fact_stock_high_daily", td)
        if n and not force:
            return {"trade_date": td.isoformat(), "action": "skipped-has-foreign-rows", "skipped": n}
        has_high = con.execute("SELECT COUNT(high), COUNT(*) FROM fact_stock_daily WHERE trade_date = ?", [td]).fetchone()
        if not has_high[1] or has_high[0] / has_high[1] < 0.9:
            raise RuntimeError(f"{td} fact_stock_daily 的 high 覆盖不足（{has_high[0]}/{has_high[1]}），先补 OHLC")
        wins = ", ".join(
            f"MAX(high) OVER (PARTITION BY stock_ts_code ORDER BY trade_date ROWS BETWEEN {n} PRECEDING AND 1 PRECEDING) AS m_{key}"
            for key, _label, n in HIGH_PERIODS
        )
        flags = ", ".join(f"(n_prev >= {n} AND high > m_{key}) AS f_{key}" for key, _label, n in HIGH_PERIODS)
        rows = con.execute(
            f"""
            WITH h AS (
              SELECT trade_date, stock_ts_code, stock_name, close, pct_chg, amount, high, {wins},
                     COUNT(high) OVER (PARTITION BY stock_ts_code ORDER BY trade_date ROWS BETWEEN 732 PRECEDING AND 1 PRECEDING) AS n_prev,
                     LAG(close, 10) OVER (PARTITION BY stock_ts_code ORDER BY trade_date) AS c10
              FROM fact_stock_daily
              WHERE trade_date <= ? AND trade_date >= CAST(? AS DATE) - INTERVAL 1200 DAY AND high IS NOT NULL
            )
            SELECT stock_ts_code, stock_name, close, pct_chg, amount, c10, {flags}
            FROM h WHERE trade_date = ? AND n_prev >= 20
            """,
            [td, td, td],
        ).fetchall()
        streaks = {}
        try:
            today, series = _limit_flags(con, td)
            streaks = {r[1]: _streak(series[r[1]], td)[0] for r in today if r[9]}
        except Exception:  # noqa: BLE001
            streaks = {}
        sw = dict(con.execute(
            "SELECT stock_ts_code, ANY_VALUE(sw_industry) FROM fact_sector_stock_daily WHERE trade_date = ? AND sw_industry IS NOT NULL GROUP BY 1", [td]
        ).fetchall())
        now = datetime.now()
        out = []
        for r in rows:
            code, name, close, pct, amt, c10 = r[:6]
            hit = [(key, label) for (key, label, _n), f in zip(HIGH_PERIODS, r[6:]) if f]
            if not hit:
                continue
            primary = hit[0]  # HIGH_PERIODS 从长到短，第一个命中即最长周期
            out.append((
                td, code, name, primary[0], primary[1],
                json.dumps([{"period": k, "label": lb} for k, lb in hit], ensure_ascii=False),
                None, close, pct, round((close / c10 - 1) * 100, 2) if (c10 and close) else None, amt,
                None, None, "涨停" if streaks.get(code) else None, streaks.get(code), sw.get(code), None, None, None,
                LOCAL_HIGH_SOURCE, now,
            ))
        con.execute("BEGIN TRANSACTION")
        con.execute("DELETE FROM fact_stock_high_daily WHERE trade_date = ?", [td])
        if out:
            con.executemany(
                """
                INSERT INTO fact_stock_high_daily
                  (trade_date, stock_ts_code, stock_name, primary_high_period, primary_high_label, high_periods_json,
                   is_new, price, pct_chg, pct_chg_10d, amount, market_cap, fund_today, limit_status, limit_times,
                   sw_l1, sw_l2, plate, whitelist_sectors_json, source, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                out,
            )
        con.execute("COMMIT")
        dist = {}
        for r in out:
            dist[r[4]] = dist.get(r[4], 0) + 1
        return {"trade_date": td.isoformat(), "action": "written", "rows": len(out), "by_label": dist}
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
# 6. 主线题材自家替代版（人气值：20 日涨幅 ×2 + 5 日涨停数 ×1 + 5 日均额 ×0.5 + 5 日双红 ×0.5）
# ---------------------------------------------------------------------------
LOCAL_MAINLINE_SOURCE = "local:mainline-v1"
MAINLINE_WEIGHTS = {"ret20": 2.0, "lu5": 1.0, "amt5": 0.5, "red5": 0.5}
MAINLINE_TOPK = 4
MAINLINE_STOCKS_PER_THEME = 20


def _z(values):
    import numpy as np

    v = np.array(values, dtype=float)
    s = v.std() or 1.0
    return (v - v.mean()) / s


def sector_theme_map(con) -> dict[str, str]:
    """板块→题材：先用 fupanhui 主线历史的归组（73 板块/14 题材，稳定），其余板块退到申万一级。"""
    hist = con.execute(
        "SELECT sector_ts_code, theme_name, COUNT(*) FROM fact_mainline_sector_daily WHERE source NOT LIKE 'local:%' GROUP BY 1, 2"
    ).fetchall()
    best: dict[str, tuple[str, int]] = {}
    for code, theme, n in hist:
        if code not in best or n > best[code][1]:
            best[code] = (theme, n)
    out = {c: t for c, (t, _n) in best.items()}
    for code, sw in con.execute("SELECT sector_ts_code, sw_l1 FROM dim_sector WHERE sw_l1 IS NOT NULL").fetchall():
        out.setdefault(code, sw)
    return out


def compute_mainline_local(trade_date, *, con=None, force: bool = False, topk: int = MAINLINE_TOPK) -> dict:
    """主线题材 = 人气值最高的 topk 个题材（题材分 = 成员板块分 top-3 均值）。

    与 fupanhui 主线历史（53 日）对照：题材集合 Jaccard 0.28（随机 0.09；只在其 14 个题材里选时 0.47）。
    fupanhui 的主线是编辑判断且题材是动态归组的，这里是**自家口径**，标 local:mainline-v1。
    主线个股：主线题材成员板块里的涨停股（不计 ST）优先，再按 涨幅×log(成交额) 补足，每题材最多 20 只。
    """
    import numpy as np

    td = _as_date(trade_date)
    own = con is None
    if own:
        init_db()
        con = connect()
    try:
        tables = ("fact_mainline_theme_daily", "fact_mainline_sector_daily", "fact_mainline_stock_daily")
        skipped = {t: _has_foreign_rows(con, t, td) for t in tables}
        skipped = {t: n for t, n in skipped.items() if n}
        if skipped and not force:
            return {"trade_date": td.isoformat(), "action": "skipped-has-foreign-rows", "skipped": skipped}
        from ..signals import DOUBLE_RED_SQL  # 双红阈值单一真本源（R-20260830-03）

        rows = con.execute(
            f"""
            WITH sd AS (
              SELECT trade_date, sector_ts_code, sector_name, pct_chg, amount,
                     SUM(pct_chg) OVER (PARTITION BY sector_ts_code ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) ret20,
                     AVG(amount) OVER (PARTITION BY sector_ts_code ORDER BY trade_date ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) amt5,
                     SUM(CASE WHEN {DOUBLE_RED_SQL} THEN 1 ELSE 0 END)
                       OVER (PARTITION BY sector_ts_code ORDER BY trade_date ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) red5
              FROM fact_sector_daily WHERE trade_date <= ? AND trade_date >= CAST(? AS DATE) - INTERVAL 45 DAY),
            lh AS (
              SELECT trade_date, sector_ts_code,
                     SUM(limit_up_count) OVER (PARTITION BY sector_ts_code ORDER BY trade_date ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) lu5
              FROM fact_theme_limit_heat_daily WHERE dimension = 'sector' AND scope = 'all' AND trade_date <= ?)
            SELECT sd.sector_ts_code, sd.sector_name, COALESCE(sd.ret20, 0), COALESCE(sd.amt5, 0), COALESCE(sd.red5, 0), COALESCE(lh.lu5, 0)
            FROM sd LEFT JOIN lh USING (trade_date, sector_ts_code) WHERE sd.trade_date = ?
            """,
            [td, td, td, td],
        ).fetchall()
        if not rows:
            raise RuntimeError(f"{td} fact_sector_daily 无行，先跑 sector-daily-local")
        codes = [r[0] for r in rows]
        names = {r[0]: r[1] for r in rows}
        score = (MAINLINE_WEIGHTS["ret20"] * _z([r[2] for r in rows]) + MAINLINE_WEIGHTS["amt5"] * _z(np.log1p([r[3] for r in rows]))
                 + MAINLINE_WEIGHTS["red5"] * _z([r[4] for r in rows]) + MAINLINE_WEIGHTS["lu5"] * _z(np.log1p([r[5] for r in rows])))
        mapping = sector_theme_map(con)
        theme_sectors: dict[str, list[tuple[str, float]]] = {}
        for c, s in zip(codes, score):
            t = mapping.get(c)
            if t:
                theme_sectors.setdefault(t, []).append((c, float(s)))
        theme_score = {t: float(np.mean(sorted((s for _c, s in v), reverse=True)[:3])) for t, v in theme_sectors.items()}
        chosen = sorted(theme_score, key=theme_score.get, reverse=True)[:topk]

        today, _series = _limit_flags(con, td, lookback_days=1)
        stock_row = {r[1]: r for r in today}
        now = datetime.now()
        theme_rows, sector_rows, stock_rows = [], [], []
        for rank, t in enumerate(chosen, start=1):
            code = f"LM{rank:03d}.LOCAL"
            secs = sorted(theme_sectors[t], key=lambda x: -x[1])
            theme_rows.append((td, code, t, len(secs), rank, LOCAL_MAINLINE_SOURCE, now))
            for c, _s in secs:
                sector_rows.append((td, code, t, c, names[c], LOCAL_MAINLINE_SOURCE, now))
            members = con.execute(
                f"SELECT DISTINCT stock_ts_code FROM fact_sector_stock_daily WHERE trade_date = ? AND sector_ts_code IN ({','.join('?' for _ in secs)})",
                [td, *[c for c, _s in secs]],
            ).fetchall()
            cands = []
            for (stk,) in members:
                r = stock_row.get(stk)
                if not r or r[8] or r[5] is None or not r[6]:  # 无行 / ST / 无涨幅 / 无成交
                    continue
                cands.append((1 if r[9] else 0, float(r[5]) * float(np.log1p(r[6])), stk, r))
            cands.sort(key=lambda x: (-x[0], -x[1]))
            for _up, _k, stk, r in cands[:MAINLINE_STOCKS_PER_THEME]:
                stock_rows.append((td, code, t, "mainline", stk, r[2], r[3], r[5], r[6], LOCAL_MAINLINE_SOURCE, now))
        con.execute("BEGIN TRANSACTION")
        for t in tables:
            con.execute(f"DELETE FROM {t} WHERE trade_date = ?", [td])
        con.executemany("INSERT INTO fact_mainline_theme_daily (trade_date, theme_code, theme_name, sector_count, min_sort, source, updated_at) VALUES (?,?,?,?,?,?,?)", theme_rows)
        con.executemany("INSERT INTO fact_mainline_sector_daily (trade_date, theme_code, theme_name, sector_ts_code, sector_name, source, updated_at) VALUES (?,?,?,?,?,?,?)", sector_rows)
        con.executemany(
            "INSERT INTO fact_mainline_stock_daily (trade_date, theme_code, theme_name, group_type, stock_ts_code, stock_name, price, pct_chg, amount, source, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            stock_rows,
        )
        con.execute("COMMIT")
        return {"trade_date": td.isoformat(), "action": "written", "themes": chosen, "theme_scores": {t: round(theme_score[t], 2) for t in chosen},
                "sector_rows": len(sector_rows), "stock_rows": len(stock_rows)}
    except Exception:
        try:
            con.execute("ROLLBACK")
        except Exception:  # noqa: BLE001
            pass
        raise
    finally:
        if own:
            con.close()
