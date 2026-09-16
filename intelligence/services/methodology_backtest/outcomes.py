"""前瞻结果表 ``history_outcomes``：每个 (实体, 交易日) 之后 h 个交易日的路径读数。

口径照抄 CLAUDE.md「市场假设验证」与 ``evolution/validate.py``：基准 = D0 收盘，T+h = 之后第 h 个
交易日收盘，收益按 ``pct_chg`` 复利累计；**窗口不含 D0 当日**——含了就是前视，selftest 的前视对照
与 pytest 的变异测试都打这一条。

每行字段（单位 %）：
- ``fwd_return``          T+h 相对 D0 的累计收益
- ``max_return``          路径上 T+1..T+h 各步累计收益的最大值
- ``days_to_peak``        取得 max_return 的最早步数（1..h）
- ``drawdown_after_peak`` 峰值到 T+h 的回撤 ``(1+fwd)/(1+max) - 1``（<=0）
- ``status``              ok / pending（日历还没走到 T+h）/ missing（日历有日、实体缺行）

交易日历取 ``history_calendar``（源自 ``fact_market_daily.trade_date``）。价格序列按 ``SERIES_BY_ENTITY_TYPE``
选：sector 与 theme 共用 ``fact_sector_daily.pct_chg``（题材实体 = 同一 ``sector_ts_code``，见 labels.py
说明），stock 用 ``fact_stock_daily.pct_chg``；序列键 ``(series, entity_id)`` 显式区分，不靠代码后缀
（.TI/.FP vs .SZ/.SH/.BJ）不撞车这种巧合。universe 分别取各自在 ``history_labels`` 里的 (实体, 日) 集合，
所以基准率也分别计算。个股停牌 / 缺行落在窗口内即 ``missing``——路径未定义就不猜。
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import duckdb

from .labels import LABEL_VERSION
from .store import (
    OUTCOMES_TABLES,
    SOURCE_ALIAS,
    BuildReport,
    attach_source,
    detach_source,
    naive_utc,
    open_labels_db,
    read_meta,
    reset_tables,
    utc_now,
    write_meta,
)

DEFAULT_HORIZONS: tuple[int, ...] = (3, 5, 7, 10)
# 实体类型 → 价格序列。键与值都是代码常量，拼进 SQL 文本前不经过任何用户输入。
SERIES_BY_ENTITY_TYPE: dict[str, str] = {"sector": "sector", "theme": "sector", "stock": "stock"}
OUTCOME_ENTITY_TYPES = tuple(SERIES_BY_ENTITY_TYPE)
# 路径累计从 D0 之后第 1 个交易日起算。改成 0 就是前视 bug（变异测试靶点）。
WINDOW_START_OFFSET = 1


def build_outcomes(
    source_db: str | Path,
    labels_db: str | Path,
    *,
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
    now: datetime | None = None,
) -> BuildReport:
    """按 ``history_labels`` 里的 sector / theme / stock universe 计算多窗口前瞻结果。需先 build-labels。"""
    horizons = tuple(sorted({int(h) for h in horizons}))
    if not horizons or any(h <= 0 for h in horizons):
        raise ValueError(f"horizons 必须是正整数集合，得到 {horizons}")
    computed_at = naive_utc(now or utc_now())

    con = open_labels_db(labels_db, read_only=False)
    try:
        meta = read_meta(con)
        if "labels" not in meta:
            raise RuntimeError("旁路库没有 labels 构建记录，先跑 build-labels")
        source_path = attach_source(con, source_db)
        try:
            source_max = con.execute(
                f"SELECT MAX(trade_date) FROM {SOURCE_ALIAS}.fact_market_daily"
            ).fetchone()[0]
            if str(source_max) != str(meta["labels"]["source_max_trade_date"]):
                raise RuntimeError(
                    "主库 max(trade_date) 与 labels 构建时不一致："
                    f"{source_max} vs {meta['labels']['source_max_trade_date']}，先重跑 build-labels"
                )
            reset_tables(con, OUTCOMES_TABLES)
            _build_return_series(con)
            _build_base_universe(con)
            for h in horizons:
                _insert_horizon(con, h, computed_at)
            con.execute("DROP TABLE IF EXISTS _ret")
            con.execute("DROP TABLE IF EXISTS _base")

            total = con.execute("SELECT COUNT(*) FROM history_outcomes").fetchone()[0]
            by_status = dict(
                con.execute(
                    "SELECT status, COUNT(*) FROM history_outcomes GROUP BY status ORDER BY status"
                ).fetchall()
            )
            by_type = dict(
                con.execute(
                    "SELECT entity_type, COUNT(*) FROM history_outcomes GROUP BY 1 ORDER BY 1"
                ).fetchall()
            )
            write_meta(
                con,
                build_kind="outcomes",
                label_version=LABEL_VERSION,
                source_db=source_path,
                source_max_trade_date=source_max,
                source_row_counts={
                    "by_status": {str(k): int(v) for k, v in by_status.items()},
                    "by_entity_type": {str(k): int(v) for k, v in by_type.items()},
                    "window_start_offset": WINDOW_START_OFFSET,
                },
                row_count=total,
                horizons=horizons,
                computed_at=computed_at,
            )
            cal = con.execute(
                "SELECT MIN(trade_date), MAX(trade_date), COUNT(*) FROM history_calendar"
            ).fetchone()
        finally:
            detach_source(con)
    finally:
        con.close()

    return BuildReport(
        build_kind="outcomes",
        labels_db=str(Path(labels_db).expanduser()),
        source_db=str(source_path),
        label_version=LABEL_VERSION,
        source_max_trade_date=str(source_max) if source_max is not None else None,
        calendar_start=str(cal[0]) if cal and cal[0] is not None else None,
        calendar_end=str(cal[1]) if cal and cal[1] is not None else None,
        calendar_days=int(cal[2]) if cal else 0,
        row_count=int(total),
        computed_at=computed_at.isoformat(timespec="seconds") + "Z",
        rows_by_label={f"horizon_{h}": int(total) // len(horizons) for h in horizons},
        extras={
            "horizons": list(horizons),
            "by_status": {str(k): int(v) for k, v in by_status.items()},
            "by_entity_type": {str(k): int(v) for k, v in by_type.items()},
        },
    )


def _build_return_series(con: duckdb.DuckDBPyConnection) -> None:
    """价格序列：published 板块 + 个股日涨跌幅，按日历 idx 编号，带 series 键。<= -100% 的脏值剔除（LN 定义域）。"""
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE _ret AS
        SELECT 'sector' AS series, c.idx, f.sector_ts_code AS entity_id, f.pct_chg
        FROM {SOURCE_ALIAS}.fact_sector_daily f
        JOIN history_calendar c ON c.trade_date = f.trade_date
        WHERE f.pct_chg IS NOT NULL AND f.pct_chg > -100
        QUALIFY ROW_NUMBER() OVER (
            PARTITION BY f.trade_date, f.sector_ts_code ORDER BY f.updated_at DESC NULLS LAST
        ) = 1
        UNION ALL
        SELECT 'stock' AS series, c.idx, s.stock_ts_code AS entity_id, s.pct_chg
        FROM {SOURCE_ALIAS}.fact_stock_daily s
        JOIN history_calendar c ON c.trade_date = s.trade_date
        WHERE s.stock_ts_code IS NOT NULL AND s.pct_chg IS NOT NULL AND s.pct_chg > -100
        QUALIFY ROW_NUMBER() OVER (
            PARTITION BY s.trade_date, s.stock_ts_code ORDER BY s.updated_at DESC NULLS LAST
        ) = 1
        """
    )


def _build_base_universe(con: duckdb.DuckDBPyConnection) -> None:
    series_case = " ".join(f"WHEN '{et}' THEN '{series}'" for et, series in SERIES_BY_ENTITY_TYPE.items())
    type_list = ", ".join(f"'{et}'" for et in OUTCOME_ENTITY_TYPES)
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE _base AS
        SELECT l.entity_type, l.entity_id, l.trade_date, c.idx,
               CASE l.entity_type {series_case} END AS series
        FROM (
            SELECT DISTINCT entity_type, entity_id, trade_date
            FROM history_labels
            WHERE entity_type IN ({type_list})
        ) l
        JOIN history_calendar c ON c.trade_date = l.trade_date
        """
    )


def _insert_horizon(con: duckdb.DuckDBPyConnection, h: int, computed_at: datetime) -> None:
    lo = WINDOW_START_OFFSET
    hi = WINDOW_START_OFFSET + h - 1
    con.execute(
        f"""
        INSERT INTO history_outcomes
            (entity_type, entity_id, trade_date, horizon, fwd_return, max_return,
             days_to_peak, drawdown_after_peak, status, computed_at)
        WITH steps AS (
            SELECT b.entity_type, b.entity_id, b.trade_date, b.idx,
                   r.idx - b.idx - {lo} + 1 AS step, r.pct_chg
            FROM _base b
            JOIN _ret r ON r.series = b.series AND r.entity_id = b.entity_id
                       AND r.idx BETWEEN b.idx + {lo} AND b.idx + {hi}
        ),
        path AS (
            SELECT *,
                   EXP(SUM(LN(1 + pct_chg / 100.0)) OVER (
                       PARTITION BY entity_type, entity_id, idx
                       ORDER BY step ROWS UNBOUNDED PRECEDING)) - 1 AS cum
            FROM steps
        ),
        peak AS (
            SELECT *, MAX(cum) OVER (PARTITION BY entity_type, entity_id, idx) AS mx
            FROM path
        ),
        agg AS (
            SELECT entity_type, entity_id, trade_date, idx,
                   COUNT(*) AS n_steps,
                   MAX(CASE WHEN step = ? THEN cum END) AS fwd,
                   MAX(mx) AS mx,
                   MIN(CASE WHEN cum = mx THEN step END) AS peak_step
            FROM peak
            GROUP BY 1, 2, 3, 4
        )
        SELECT b.entity_type, b.entity_id, b.trade_date, ?,
               CASE WHEN a.n_steps = ? THEN a.fwd * 100 END,
               CASE WHEN a.n_steps = ? THEN a.mx * 100 END,
               CASE WHEN a.n_steps = ? THEN a.peak_step END,
               CASE WHEN a.n_steps = ? THEN ((1 + a.fwd) / (1 + a.mx) - 1) * 100 END,
               CASE WHEN a.n_steps = ? THEN 'ok'
                    WHEN b.idx + {hi} > (SELECT MAX(idx) FROM history_calendar) THEN 'pending'
                    ELSE 'missing' END,
               ?
        FROM _base b
        LEFT JOIN agg a
          ON a.entity_type = b.entity_type AND a.entity_id = b.entity_id AND a.idx = b.idx
        """,
        [h, h, h, h, h, h, h, computed_at],
    )
