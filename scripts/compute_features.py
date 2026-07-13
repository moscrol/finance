#!/usr/bin/env python3
"""增量计算 canonical DuckDB 的日频窗口特征。"""
from __future__ import annotations

import argparse
from collections.abc import Iterable

from market_feature_store.db import DB_PATH, connect, init_db

PERIODS = (5, 10, 20, 60)
FEATURES = ("market", "limit-advance", "stock", "sector", "technical", "period-rank")


def resolve_trade_date(con, requested: str | None) -> str:
    row = con.execute(
        """
        SELECT MAX(trade_date)
        FROM fact_market_daily
        WHERE trade_date <= COALESCE(CAST(? AS DATE), DATE '9999-12-31')
        """,
        [requested],
    ).fetchone()
    if not row or row[0] is None:
        raise RuntimeError(f"fact_market_daily 没有不晚于 {requested or 'latest'} 的交易日")
    resolved = str(row[0])
    if requested and resolved != requested:
        raise RuntimeError(f"{requested} 不是 fact_market_daily 中的交易日（最近为 {resolved}）")
    return resolved


def _empty_stage(con, stage: str, table: str) -> None:
    con.execute(f"DROP TABLE IF EXISTS {stage}")
    con.execute(f"CREATE TEMP TABLE {stage} AS SELECT * FROM {table} WHERE FALSE")


def _build_market(con, trade_date: str) -> tuple[str, str, str, bool]:
    stage = "_stage_feature_market_window"
    table = "feature_market_window"
    _empty_stage(con, stage, table)
    for period in PERIODS:
        con.execute(
            f"""
            INSERT INTO {stage}
            WITH base AS (
                SELECT trade_date, advancers, limit_up, limit_down, total_amount,
                       LAG(trade_date, {period}) OVER w AS start_date,
                       LAG(advancers, {period}) OVER w AS adv_start,
                       AVG(advancers) OVER
                           (ORDER BY trade_date ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) AS adv_ma5,
                       AVG(limit_up) OVER
                           (ORDER BY trade_date ROWS BETWEEN {period - 1} PRECEDING AND CURRENT ROW) AS lu_avg,
                       AVG(limit_down) OVER
                           (ORDER BY trade_date ROWS BETWEEN {period - 1} PRECEDING AND CURRENT ROW) AS ld_avg,
                       AVG(total_amount) OVER
                           (ORDER BY trade_date ROWS BETWEEN {period - 1} PRECEDING AND CURRENT ROW) AS amt_avg,
                       COUNT(*) OVER
                           (ORDER BY trade_date ROWS BETWEEN {period - 1} PRECEDING AND CURRENT ROW) AS wc
                FROM fact_market_daily
                WHERE trade_date <= ?
                WINDOW w AS (ORDER BY trade_date)
            )
            SELECT trade_date, start_date, trade_date,
                   adv_start, advancers, advancers - COALESCE(adv_start, 0),
                   ROUND(adv_ma5, 1), ROUND(lu_avg, 1), ROUND(ld_avg, 1), ROUND(amt_avg, 2),
                   CASE
                       WHEN advancers - COALESCE(adv_start, 0) > 200 THEN 'up'
                       WHEN advancers - COALESCE(adv_start, 0) < -200 THEN 'down'
                       ELSE 'flat'
                   END,
                   CURRENT_TIMESTAMP
            FROM base
            WHERE trade_date = ? AND start_date IS NOT NULL AND wc >= {period}
            """,
            [trade_date, trade_date],
        )
    return table, "as_of_date", stage, False


def _build_limit_advance(con, trade_date: str) -> tuple[str, str, str, bool]:
    stage = "_stage_feature_limit_advance_window"
    table = "feature_limit_advance_window"
    _empty_stage(con, stage, table)
    for period in PERIODS:
        con.execute(
            f"""
            INSERT INTO {stage}
            WITH calendar AS (
                SELECT trade_date,
                       LAG(trade_date, {period - 1}) OVER (ORDER BY trade_date) AS start_date
                FROM fact_market_daily
                WHERE trade_date <= ?
            ),
            target AS (
                SELECT trade_date AS as_of_date, start_date
                FROM calendar
                WHERE trade_date = ?
            )
            SELECT t.as_of_date, t.start_date, t.as_of_date,
                   f.stock_ts_code, f.stock_name,
                   COUNT(DISTINCT f.trade_date), MAX(f.boards),
                   MIN(f.trade_date), MAX(f.trade_date),
                   STRING_AGG(DISTINCT f.theme, ',' ORDER BY f.theme),
                   CURRENT_TIMESTAMP
            FROM target t
            JOIN fact_limit_advance_daily f
              ON f.trade_date BETWEEN t.start_date AND t.as_of_date
            WHERE t.start_date IS NOT NULL
            GROUP BY t.as_of_date, t.start_date, f.stock_ts_code, f.stock_name
            """,
            [trade_date, trade_date],
        )
    return table, "as_of_date", stage, True


def _build_stock(con, trade_date: str) -> tuple[str, str, str, bool]:
    stage = "_stage_feature_stock_window"
    table = "feature_stock_window"
    _empty_stage(con, stage, table)
    for period in PERIODS:
        con.execute(
            f"""
            INSERT INTO {stage}
            WITH base AS (
                SELECT trade_date, stock_ts_code, stock_name, close, amount,
                       LAG(close, {period}) OVER w AS close_start,
                       LAG(trade_date, {period}) OVER w AS start_date,
                       AVG(amount) OVER (
                           PARTITION BY stock_ts_code ORDER BY trade_date
                           ROWS BETWEEN {period - 1} PRECEDING AND CURRENT ROW
                       ) AS avg_amt,
                       COUNT(*) OVER (
                           PARTITION BY stock_ts_code ORDER BY trade_date
                           ROWS BETWEEN {period - 1} PRECEDING AND CURRENT ROW
                       ) AS wc
                FROM fact_stock_daily
                WHERE trade_date <= ?
                WINDOW w AS (PARTITION BY stock_ts_code ORDER BY trade_date)
            ),
            gains AS (
                SELECT trade_date AS as_of_date, start_date, trade_date AS end_date,
                       stock_ts_code, stock_name,
                       ROUND((close / NULLIF(close_start, 0) - 1) * 100, 2) AS gain,
                       ROUND(avg_amt, 4) AS avg_amount
                FROM base
                WHERE trade_date = ? AND close_start > 0 AND wc >= {period}
            ),
            sectors AS (
                SELECT stock_ts_code,
                       COUNT(DISTINCT sector_name) AS cnt,
                       STRING_AGG(DISTINCT sector_name, ',' ORDER BY sector_name) AS names,
                       STRING_AGG(DISTINCT sw_l1, ',' ORDER BY sw_l1) AS sw1
                FROM fact_sector_stock_daily
                WHERE trade_date = ?
                GROUP BY stock_ts_code
            )
            SELECT g.as_of_date, g.start_date, g.end_date, g.stock_ts_code, g.stock_name,
                   g.gain, g.avg_amount, ROUND(g.avg_amount * g.gain / 100, 4),
                   COALESCE(s.cnt, 0), s.names, s.sw1, CURRENT_TIMESTAMP
            FROM gains g
            LEFT JOIN sectors s USING (stock_ts_code)
            """,
            [trade_date, trade_date, trade_date],
        )
    return table, "as_of_date", stage, False


def _build_sector(con, trade_date: str) -> tuple[str, str, str, bool]:
    stage = "_stage_feature_sector_window"
    table = "feature_sector_window"
    _empty_stage(con, stage, table)
    for period in PERIODS:
        con.execute(
            f"""
            INSERT INTO {stage}
            WITH base AS (
                SELECT trade_date, sector_ts_code, sector_name, sw_l1, amount, diff_ratio,
                       LAG(trade_date, {period}) OVER w AS start_date,
                       LAG(amount, {period}) OVER w AS amount_start,
                       LAG(diff_ratio, {period}) OVER w AS diff_start_val,
                       SUM(pct_chg) OVER (
                           PARTITION BY sector_ts_code ORDER BY trade_date
                           ROWS BETWEEN {period - 1} PRECEDING AND CURRENT ROW
                       ) AS sum_pct,
                       AVG(amount) OVER (
                           PARTITION BY sector_ts_code ORDER BY trade_date
                           ROWS BETWEEN {period - 1} PRECEDING AND CURRENT ROW
                       ) AS avg_amt,
                       MAX(diff_ratio) OVER (
                           PARTITION BY sector_ts_code ORDER BY trade_date
                           ROWS BETWEEN {period - 1} PRECEDING AND CURRENT ROW
                       ) AS diff_mx,
                       MIN(diff_ratio) OVER (
                           PARTITION BY sector_ts_code ORDER BY trade_date
                           ROWS BETWEEN {period - 1} PRECEDING AND CURRENT ROW
                       ) AS diff_mn,
                       COUNT(*) OVER (
                           PARTITION BY sector_ts_code ORDER BY trade_date
                           ROWS BETWEEN {period - 1} PRECEDING AND CURRENT ROW
                       ) AS wc
                FROM fact_sector_daily
                WHERE trade_date <= ?
                WINDOW w AS (PARTITION BY sector_ts_code ORDER BY trade_date)
            )
            SELECT trade_date, start_date, trade_date, sector_ts_code, sector_name, sw_l1,
                   ROUND(sum_pct, 2), ROUND(avg_amt, 2),
                   ROUND((amount / NULLIF(amount_start, 0) - 1) * 100, 2),
                   diff_start_val, diff_ratio, diff_mx, diff_mn,
                   ROUND(diff_ratio - COALESCE(diff_start_val, 0), 2),
                   CASE
                       WHEN diff_ratio - COALESCE(diff_start_val, 0) > 1 THEN 'up'
                       WHEN diff_ratio - COALESCE(diff_start_val, 0) < -1 THEN 'down'
                       ELSE 'flat'
                   END,
                   CURRENT_TIMESTAMP
            FROM base
            WHERE trade_date = ? AND start_date IS NOT NULL AND wc >= {period}
            """,
            [trade_date, trade_date],
        )
    return table, "as_of_date", stage, False


def _build_technical(con, trade_date: str) -> tuple[str, str, str, bool]:
    stage = "_stage_feature_stock_technical_daily"
    table = "feature_stock_technical_daily"
    _empty_stage(con, stage, table)
    con.execute(
        f"""
        INSERT INTO {stage}
        WITH tech AS (
            SELECT trade_date, stock_ts_code, stock_name, close,
                   AVG(close) OVER w AS ma26,
                   STDDEV_POP(close) OVER w AS std26,
                   COUNT(*) OVER w AS wc
            FROM fact_stock_daily
            WHERE trade_date <= ?
            WINDOW w AS (
                PARTITION BY stock_ts_code ORDER BY trade_date
                ROWS BETWEEN 25 PRECEDING AND CURRENT ROW
            )
        )
        SELECT trade_date, stock_ts_code, stock_name, close,
               ROUND(ma26, 4), ROUND(std26, 4),
               ROUND(ma26 + 0.764 * std26, 4),
               ROUND((close / NULLIF(ma26 + 0.764 * std26, 0) - 1) * 100, 2),
               CURRENT_TIMESTAMP
        FROM tech
        WHERE trade_date = ? AND wc = 26
        """,
        [trade_date, trade_date],
    )
    return table, "trade_date", stage, False


def _build_period_rank(con, trade_date: str) -> tuple[str, str, str, bool]:
    stage = "_stage_fact_sector_period_rank_daily"
    table = "fact_sector_period_rank_daily"
    _empty_stage(con, stage, table)
    for period_type, period in (("daily", 1), ("day3", 3), ("day5", 5), ("day10", 10)):
        con.execute(
            f"""
            INSERT INTO {stage}
            WITH trade_days AS (
                SELECT trade_date,
                       ROW_NUMBER() OVER (ORDER BY trade_date DESC) AS day_no
                FROM (
                    SELECT DISTINCT trade_date
                    FROM fact_market_daily
                    WHERE trade_date <= ?
                )
            ),
            returns AS (
                SELECT s.sector_ts_code, ARG_MAX(s.sector_name, s.trade_date) AS sector_name,
                       ROUND(
                           (PRODUCT(1 + COALESCE(s.pct_chg, 0) / 100) - 1) * 100,
                           2
                       ) AS change_pct
                FROM fact_sector_daily s
                JOIN trade_days d USING (trade_date)
                WHERE d.day_no <= {period}
                GROUP BY s.sector_ts_code
                HAVING COUNT(DISTINCT s.trade_date) = {period}
            ),
            heat AS (
                SELECT sector_ts_code, SUM(limit_up_count)::INTEGER AS limit_up_count
                FROM fact_theme_limit_heat_daily
                WHERE trade_date = ?
                GROUP BY sector_ts_code
            ),
            ranked AS (
                SELECT r.*, h.limit_up_count,
                       ROW_NUMBER() OVER (
                           ORDER BY r.change_pct DESC, r.sector_ts_code
                       ) AS rank
                FROM returns r
                LEFT JOIN heat h USING (sector_ts_code)
            )
            SELECT CAST(? AS DATE), ?, rank, sector_ts_code, sector_name,
                   change_pct, limit_up_count, NULL,
                   'derived:fact_sector_daily', CURRENT_TIMESTAMP
            FROM ranked
            WHERE rank <= 10
            """,
            [trade_date, trade_date, trade_date, period_type],
        )
    return table, "trade_date", stage, False


BUILDERS = {
    "market": _build_market,
    "limit-advance": _build_limit_advance,
    "stock": _build_stock,
    "sector": _build_sector,
    "technical": _build_technical,
    "period-rank": _build_period_rank,
}


def compute_features(
    trade_date: str | None = None,
    selected: Iterable[str] = FEATURES,
    con=None,
) -> dict:
    owned = con is None
    if owned:
        init_db()
        con = connect()
    selected_names = tuple(selected)
    try:
        target = resolve_trade_date(con, trade_date)
        stages = [BUILDERS[name](con, target) for name in selected_names]
        counts = {}
        for table, _date_column, stage, allow_empty in stages:
            count = con.execute(f"SELECT COUNT(*) FROM {stage}").fetchone()[0]
            counts[table] = count
            if not allow_empty and count == 0:
                raise RuntimeError(f"{table} 在 {target} 的 staging 结果为空，正式表保持不变")

        con.execute("BEGIN TRANSACTION")
        for table, date_column, stage, _allow_empty in stages:
            con.execute(f"DELETE FROM {table} WHERE {date_column} = ?", [target])
            con.execute(f"INSERT INTO {table} SELECT * FROM {stage}")
        con.execute("COMMIT")
        return {"trade_date": target, "tables": counts, "status": "complete"}
    except Exception:
        try:
            con.execute("ROLLBACK")
        except Exception:
            pass
        raise
    finally:
        if owned:
            con.close()


def main(argv: list[str] | None = None, default_selected: Iterable[str] = FEATURES) -> int:
    parser = argparse.ArgumentParser(description="增量计算日频窗口特征")
    parser.add_argument("--trade-date", default=None, help="目标交易日，留空取 canonical DB 最新日")
    parser.add_argument("--only", choices=FEATURES, default=None, help="只计算一个特征族")
    args = parser.parse_args(argv)
    selected = (args.only,) if args.only else tuple(default_selected)
    print(f"DB: {DB_PATH}")
    stats = compute_features(args.trade_date, selected)
    print(f"交易日: {stats['trade_date']} | 状态: {stats['status']}")
    for table, count in stats["tables"].items():
        print(f"{table}: {count} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
