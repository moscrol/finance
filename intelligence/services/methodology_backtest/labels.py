"""结构化历史标签层 v1（设计稿 §3.1 表前 12 行）：把「图像」编译成表里的一行。

    (entity_type, entity_id, trade_date, label, value_num, value_text, label_version, computed_at)

三条硬约束：
1. **确认日语义**：任一 (实体, 交易日) 上的值只依赖该日及之前的事实。用到 ``t+1`` 的标签都是 bug。
2. **复用勿重定义**：严格双红 ``pct_chg>0 且 diff_ratio>10 且 amount>500`` 抄 strategy1-matrix；
   放量阈值与 MA5 峰谷确认日算法直接调 ``market_feature_store.analysis.turning_points``。
3. **确定性 + 版本化**：同一主库同一代码同输出；口径的每次改动升 ``LABEL_VERSION``。

标签目录 v1（entity_id 统一用 ``sector_ts_code``，展示时再 join ``dim_sector``）：

| 实体 | 标签 | 值 | 定义 |
|---|---|---|---|
| sector | dual_red_strict | 1/0/NULL | 严格双红；输入缺失或 data_gap 日为 NULL |
| sector | dual_red_streak | n/NULL | 截至当日连续双红天数（当日不双红为 0；日历断档或 data_gap 后重新计数） |
| sector | diff_ratio_turn_up | 1/0/NULL | 前一交易日 diff_ratio<=0 且当日 >0；前一日缺行/缺值/为 gap 日则 NULL |
| sector | multi_period_resonance | 1/0/NULL | 直接投影布尔列 |
| sector | amount_rank_top10 | 1/0/NULL | 当日成交额在 published 名单内排名 <=10（RANK，并列同名次） |
| theme | limit_heat_rank | rank | 涨停热度排名，档位写死见 ``HEAT_TIER`` |
| theme | limit_heat_rank_jump | 1/0/NULL | 排名较前一交易日提升 >=5；前一日无名次则 NULL |
| theme | mainline_flag | 1/0/NULL | 当日出现在 ``fact_mainline_sector_daily``；主线表无覆盖的日子为 NULL |
| market | market_stage | text | 直接投影 ``fact_market_daily.market_stage`` |
| market | volume_surge | 1/0/NULL | ``amount_vs_yesterday_pct > VOLUME_SURGE_PCT``（与 detect_turning_points 同阈值，真库上两口径 74 日完全一致） |
| market | ma5_peak_confirmed | 1/0 | ``SignalDetector`` 的 MA5 顶确认日 |
| market | ma5_valley_confirmed | 1/0 | ``SignalDetector`` 的 MA5 谷确认日 |

``data_gap``（当日 >90% published 板块 ``diff_ratio = 0``）单独落 ``history_data_gaps``，不占标签名额：
该日双红类标签置 NULL，既不进事件集也不进基准率，并进收据成立条件。

题材实体为什么也用 ``sector_ts_code``：2026-09-04 真库核数，``fact_theme_limit_heat_daily`` 623 个代码
全部出现在 ``fact_sector_daily``，99.3% 的热度行能拿到同日 ``pct_chg``；而 ``fact_mainline_theme_daily``
的 ``theme_code``（TH000xx.FP）与之不在同一 ID 空间、无法 join，故 ``mainline_flag`` 取
``fact_mainline_sector_daily``（同 ID 空间，覆盖 106 日 vs 53 日）。
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb

from market_feature_store.analysis.turning_points import (
    MA5_MIN_SWING,
    VOLUME_SURGE_PCT,
    SignalDetector,
)

from .store import (
    LABELS_TABLES,
    SOURCE_ALIAS,
    BuildReport,
    attach_source,
    detach_source,
    naive_utc,
    open_labels_db,
    reset_tables,
    utc_now,
    write_meta,
)

# 口径版本。热度档位、阈值、算法任何一处变动都要升版本，旧收据凭它判「不可比」。
HEAT_TIER = {"dimension": "sector", "scope": "all", "data_stage": "final", "is_realtime": False}
LABEL_VERSION = "v1-heat_sector_all_final_nonrt"

DATA_GAP_ZERO_RATIO = 0.9
DUAL_RED_DIFF_RATIO_GT = 10.0
DUAL_RED_AMOUNT_GT = 500.0
HEAT_RANK_JUMP_GE = 5
AMOUNT_RANK_TOP = 10

SECTOR_LABELS = (
    "dual_red_strict",
    "dual_red_streak",
    "diff_ratio_turn_up",
    "multi_period_resonance",
    "amount_rank_top10",
)
THEME_LABELS = ("limit_heat_rank", "limit_heat_rank_jump", "mainline_flag")
MARKET_LABELS = ("market_stage", "volume_surge", "ma5_peak_confirmed", "ma5_valley_confirmed")
ALL_LABELS = SECTOR_LABELS + THEME_LABELS + MARKET_LABELS
MARKET_ENTITY_ID = "market"

# 供收据引用的口径说明；与 LABEL_VERSION 一起落 history_build_meta.source_row_counts。
LABEL_SPEC: dict[str, Any] = {
    "label_version": LABEL_VERSION,
    "dual_red_strict": f"pct_chg>0 AND diff_ratio>{DUAL_RED_DIFF_RATIO_GT:g} AND amount>{DUAL_RED_AMOUNT_GT:g}",
    "data_gap": f">{DATA_GAP_ZERO_RATIO:.0%} published sector rows with diff_ratio=0",
    "heat_tier": HEAT_TIER,
    "limit_heat_rank_jump": f"prev_rank - rank >= {HEAT_RANK_JUMP_GE}",
    "amount_rank_top10": f"RANK() by amount DESC within trade_date <= {AMOUNT_RANK_TOP}",
    "volume_surge": f"amount_vs_yesterday_pct > {VOLUME_SURGE_PCT:g}",
    "ma5": f"turning_points.SignalDetector(MA5_MIN_SWING={MA5_MIN_SWING}) confirm-day, full fact_market_daily range",
    "mainline_flag": "fact_mainline_sector_daily (trade_date, sector_ts_code) exists; NULL on days without coverage",
    "entity_id": "sector_ts_code for sector & theme; 'market' for market",
}


def build_labels(
    source_db: str | Path,
    labels_db: str | Path,
    *,
    now: datetime | None = None,
) -> BuildReport:
    """从主库只读重建全部 12 个标签 + data_gap + 交易日历，写入旁路库。幂等：同输入同输出。"""
    computed_at = naive_utc(now or utc_now())
    con = open_labels_db(labels_db, read_only=False)
    try:
        source_path = attach_source(con, source_db)
        try:
            reset_tables(con, LABELS_TABLES)
            _build_calendar(con)
            gap_days = _build_data_gaps(con, computed_at)
            _build_sector_labels(con, computed_at)
            _build_theme_labels(con, computed_at)
            ma5_counts = _build_market_labels(con, computed_at)

            source_max = con.execute(
                f"SELECT MAX(trade_date) FROM {SOURCE_ALIAS}.fact_market_daily"
            ).fetchone()[0]
            counts = _source_counts(con)
            counts["ma5_signals"] = ma5_counts
            counts["label_spec"] = LABEL_SPEC
            total = con.execute("SELECT COUNT(*) FROM history_labels").fetchone()[0]
            write_meta(
                con,
                build_kind="labels",
                label_version=LABEL_VERSION,
                source_db=source_path,
                source_max_trade_date=source_max,
                source_row_counts=counts,
                row_count=total,
                horizons=None,
                computed_at=computed_at,
            )
            cal = con.execute(
                "SELECT MIN(trade_date), MAX(trade_date), COUNT(*) FROM history_calendar"
            ).fetchone()
            by_label = dict(
                con.execute(
                    "SELECT label, COUNT(*) FROM history_labels GROUP BY label ORDER BY label"
                ).fetchall()
            )
        finally:
            detach_source(con)
    finally:
        con.close()

    return BuildReport(
        build_kind="labels",
        labels_db=str(Path(labels_db).expanduser()),
        source_db=str(source_path),
        label_version=LABEL_VERSION,
        source_max_trade_date=str(source_max) if source_max is not None else None,
        calendar_start=str(cal[0]) if cal and cal[0] is not None else None,
        calendar_end=str(cal[1]) if cal and cal[1] is not None else None,
        calendar_days=int(cal[2]) if cal else 0,
        row_count=int(total),
        computed_at=computed_at.isoformat(timespec="seconds") + "Z",
        rows_by_label={str(k): int(v) for k, v in by_label.items()},
        data_gap_days=gap_days,
        extras={"source_row_counts": {k: v for k, v in counts.items() if k != "label_spec"}},
    )


# --------------------------------------------------------------------------- #
# 交易日历 + data_gap
# --------------------------------------------------------------------------- #
def _build_calendar(con: duckdb.DuckDBPyConnection) -> None:
    """交易日历取 ``fact_market_daily.trade_date``（工单目标 2），idx 从 0 起连续编号。"""
    con.execute(
        f"""
        INSERT INTO history_calendar (idx, trade_date)
        SELECT (ROW_NUMBER() OVER (ORDER BY trade_date) - 1)::INTEGER, trade_date
        FROM {SOURCE_ALIAS}.fact_market_daily
        ORDER BY trade_date
        """
    )


def _build_data_gaps(con: duckdb.DuckDBPyConnection, computed_at: datetime) -> list[str]:
    con.execute(
        f"""
        INSERT INTO history_data_gaps (trade_date, reason, zero_ratio, sector_rows, label_version, computed_at)
        SELECT trade_date, 'diff_ratio_all_zero', zero_n * 1.0 / n, n, ?, ?
        FROM (
            SELECT f.trade_date, COUNT(*) AS n,
                   SUM(CASE WHEN f.diff_ratio = 0 THEN 1 ELSE 0 END) AS zero_n
            FROM {SOURCE_ALIAS}.fact_sector_daily f
            JOIN history_calendar c ON c.trade_date = f.trade_date
            GROUP BY f.trade_date
        )
        WHERE n > 0 AND zero_n > ? * n
        ORDER BY trade_date
        """,
        [LABEL_VERSION, computed_at, DATA_GAP_ZERO_RATIO],
    )
    rows = con.execute("SELECT trade_date FROM history_data_gaps ORDER BY trade_date").fetchall()
    return [str(r[0]) for r in rows]


# --------------------------------------------------------------------------- #
# sector
# --------------------------------------------------------------------------- #
def _build_sector_labels(con: duckdb.DuckDBPyConnection, computed_at: datetime) -> None:
    # published 名单 = VIEW 暴露的那份；同日同码若出现多行（理论上不该），按 updated_at 取最新一行并计数。
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE _sec AS
        SELECT c.idx, f.trade_date, f.sector_ts_code AS entity_id,
               f.pct_chg, f.amount, f.diff_ratio, f.multi_period_resonance,
               (g.trade_date IS NOT NULL) AS is_gap
        FROM {SOURCE_ALIAS}.fact_sector_daily f
        JOIN history_calendar c ON c.trade_date = f.trade_date
        LEFT JOIN history_data_gaps g ON g.trade_date = f.trade_date
        QUALIFY ROW_NUMBER() OVER (
            PARTITION BY f.trade_date, f.sector_ts_code ORDER BY f.updated_at DESC NULLS LAST
        ) = 1
        """
    )
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE _sec_feat AS
        WITH base AS (
            SELECT *,
                CASE
                    WHEN is_gap OR pct_chg IS NULL OR diff_ratio IS NULL OR amount IS NULL THEN NULL
                    WHEN pct_chg > 0 AND diff_ratio > {DUAL_RED_DIFF_RATIO_GT} AND amount > {DUAL_RED_AMOUNT_GT} THEN 1
                    ELSE 0
                END AS dual_red,
                LAG(idx) OVER w AS prev_idx,
                LAG(diff_ratio) OVER w AS prev_diff,
                LAG(is_gap) OVER w AS prev_is_gap,
                CASE WHEN amount IS NULL THEN NULL
                     WHEN RANK() OVER (PARTITION BY trade_date ORDER BY amount DESC NULLS LAST) <= {AMOUNT_RANK_TOP} THEN 1
                     ELSE 0 END AS top10
            FROM _sec
            WINDOW w AS (PARTITION BY entity_id ORDER BY idx)
        ),
        brk AS (
            -- 连续段起点：非双红 / 未知 / 日历断档（缺行的那天视为断档，不跨越猜测）
            SELECT *,
                CASE WHEN dual_red IS NULL OR dual_red = 0 THEN 1
                     WHEN prev_idx IS NULL OR idx - prev_idx <> 1 THEN 1
                     ELSE 0 END AS is_break
            FROM base
        ),
        grp AS (
            SELECT *, SUM(is_break) OVER (PARTITION BY entity_id ORDER BY idx ROWS UNBOUNDED PRECEDING) AS seg
            FROM brk
        )
        SELECT idx, trade_date, entity_id, dual_red, multi_period_resonance, top10,
            CASE WHEN dual_red IS NULL THEN NULL
                 WHEN dual_red = 0 THEN 0
                 ELSE COUNT(*) FILTER (WHERE dual_red = 1) OVER (
                        PARTITION BY entity_id, seg ORDER BY idx ROWS UNBOUNDED PRECEDING)
            END AS streak,
            CASE WHEN is_gap OR diff_ratio IS NULL THEN NULL
                 WHEN prev_idx IS NULL OR idx - prev_idx <> 1 OR prev_diff IS NULL OR prev_is_gap THEN NULL
                 WHEN prev_diff <= 0 AND diff_ratio > 0 THEN 1
                 ELSE 0 END AS turn_up
        FROM grp
        """
    )
    inserts = {
        "dual_red_strict": "dual_red",
        "dual_red_streak": "streak",
        "diff_ratio_turn_up": "turn_up",
        "multi_period_resonance": (
            "CASE WHEN multi_period_resonance IS NULL THEN NULL WHEN multi_period_resonance THEN 1 ELSE 0 END"
        ),
        "amount_rank_top10": "top10",
    }
    for label, expr in inserts.items():
        con.execute(
            f"""
            INSERT INTO history_labels
                (entity_type, entity_id, trade_date, label, value_num, value_text, label_version, computed_at)
            SELECT 'sector', entity_id, trade_date, ?, ({expr})::DOUBLE, NULL, ?, ?
            FROM _sec_feat
            """,
            [label, LABEL_VERSION, computed_at],
        )
    con.execute("DROP TABLE IF EXISTS _sec_feat")


# --------------------------------------------------------------------------- #
# theme（热度表固定一档）
# --------------------------------------------------------------------------- #
def _build_theme_labels(con: duckdb.DuckDBPyConnection, computed_at: datetime) -> None:
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE _heat AS
        SELECT c.idx, h.trade_date, h.sector_ts_code AS entity_id, h.rank
        FROM {SOURCE_ALIAS}.fact_theme_limit_heat_daily h
        JOIN history_calendar c ON c.trade_date = h.trade_date
        WHERE h.dimension = ? AND h.scope = ? AND h.data_stage = ? AND h.is_realtime = ?
          AND h.rank IS NOT NULL
        """,
        [HEAT_TIER["dimension"], HEAT_TIER["scope"], HEAT_TIER["data_stage"], HEAT_TIER["is_realtime"]],
    )
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE _heat_feat AS
        WITH base AS (
            SELECT *,
                LAG(idx) OVER w AS prev_idx,
                LAG(rank) OVER w AS prev_rank
            FROM _heat
            WINDOW w AS (PARTITION BY entity_id ORDER BY idx)
        ),
        ml_days AS (SELECT DISTINCT trade_date FROM {SOURCE_ALIAS}.fact_mainline_sector_daily),
        ml AS (SELECT DISTINCT trade_date, sector_ts_code FROM {SOURCE_ALIAS}.fact_mainline_sector_daily)
        SELECT b.idx, b.trade_date, b.entity_id, b.rank,
            CASE WHEN b.prev_idx IS NULL OR b.idx - b.prev_idx <> 1 THEN NULL
                 WHEN b.prev_rank - b.rank >= {HEAT_RANK_JUMP_GE} THEN 1
                 ELSE 0 END AS rank_jump,
            CASE WHEN d.trade_date IS NULL THEN NULL
                 WHEN m.sector_ts_code IS NOT NULL THEN 1
                 ELSE 0 END AS mainline
        FROM base b
        LEFT JOIN ml_days d ON d.trade_date = b.trade_date
        LEFT JOIN ml m ON m.trade_date = b.trade_date AND m.sector_ts_code = b.entity_id
        """
    )
    inserts = {
        "limit_heat_rank": "rank",
        "limit_heat_rank_jump": "rank_jump",
        "mainline_flag": "mainline",
    }
    for label, expr in inserts.items():
        con.execute(
            f"""
            INSERT INTO history_labels
                (entity_type, entity_id, trade_date, label, value_num, value_text, label_version, computed_at)
            SELECT 'theme', entity_id, trade_date, ?, ({expr})::DOUBLE, NULL, ?, ?
            FROM _heat_feat
            """,
            [label, LABEL_VERSION, computed_at],
        )
    con.execute("DROP TABLE IF EXISTS _heat_feat")
    con.execute("DROP TABLE IF EXISTS _heat")


# --------------------------------------------------------------------------- #
# market
# --------------------------------------------------------------------------- #
def _market_series(con: duckdb.DuckDBPyConnection) -> tuple[list[dict], list[dict]]:
    """与 ``SectorDataProvider.get_market_data / get_advancers`` 同形的两段序列（全日历范围）。"""
    market_rows = con.execute(
        f"""
        SELECT trade_date, total_amount, amount_vs_yesterday_pct, limit_up, limit_down,
               sh_week_ma, sh_deviation_pct
        FROM {SOURCE_ALIAS}.fact_market_daily
        ORDER BY trade_date
        """
    ).fetchall()
    market_data = [
        {
            "date": str(r[0]),
            "volume": r[1],
            "volume_change": r[2],
            "limit_up": r[3],
            "limit_down": r[4],
            "week_ma": r[5],
            "deviation": r[6],
        }
        for r in market_rows
    ]
    adv_rows = con.execute(
        f"""
        SELECT trade_date, advancers,
               AVG(advancers) OVER (ORDER BY trade_date ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) AS ma5
        FROM {SOURCE_ALIAS}.fact_market_daily
        ORDER BY trade_date
        """
    ).fetchall()
    advancers = [
        {"date": str(d), "count": c, "ma5": float(m) if m is not None else None}
        for d, c, m in adv_rows
    ]
    return market_data, advancers


def _build_market_labels(con: duckdb.DuckDBPyConnection, computed_at: datetime) -> dict[str, int]:
    con.execute(
        f"""
        INSERT INTO history_labels
            (entity_type, entity_id, trade_date, label, value_num, value_text, label_version, computed_at)
        SELECT 'market', '{MARKET_ENTITY_ID}', m.trade_date, 'market_stage', NULL, m.market_stage, ?, ?
        FROM {SOURCE_ALIAS}.fact_market_daily m
        JOIN history_calendar c ON c.trade_date = m.trade_date
        """,
        [LABEL_VERSION, computed_at],
    )
    con.execute(
        f"""
        INSERT INTO history_labels
            (entity_type, entity_id, trade_date, label, value_num, value_text, label_version, computed_at)
        SELECT 'market', '{MARKET_ENTITY_ID}', m.trade_date, 'volume_surge',
               CASE WHEN m.amount_vs_yesterday_pct IS NULL THEN NULL
                    WHEN m.amount_vs_yesterday_pct > ? THEN 1 ELSE 0 END,
               NULL, ?, ?
        FROM {SOURCE_ALIAS}.fact_market_daily m
        JOIN history_calendar c ON c.trade_date = m.trade_date
        """,
        [VOLUME_SURGE_PCT, LABEL_VERSION, computed_at],
    )

    # MA5 峰谷：复用 SignalDetector（确认日语义在它内部保证），这里只把信号日铺成稠密 1/0。
    market_data, advancers = _market_series(con)
    signals = SignalDetector().detect(market_data, advancers)
    peaks: set[str] = set()
    valleys: set[str] = set()
    for sig in signals:
        kinds = set(sig.type.split("+"))
        if "peak_confirmed" in kinds:
            peaks.add(sig.date)
        if "valley_confirmed" in kinds:
            valleys.add(sig.date)
    con.execute("CREATE OR REPLACE TEMP TABLE _ma5 (trade_date DATE, kind VARCHAR)")
    rows = [(d, "peak") for d in sorted(peaks)] + [(d, "valley") for d in sorted(valleys)]
    if rows:
        con.executemany("INSERT INTO _ma5 VALUES (?, ?)", rows)
    for label, kind in (("ma5_peak_confirmed", "peak"), ("ma5_valley_confirmed", "valley")):
        con.execute(
            f"""
            INSERT INTO history_labels
                (entity_type, entity_id, trade_date, label, value_num, value_text, label_version, computed_at)
            SELECT 'market', '{MARKET_ENTITY_ID}', c.trade_date, ?,
                   CASE WHEN s.trade_date IS NOT NULL THEN 1 ELSE 0 END, NULL, ?, ?
            FROM history_calendar c
            LEFT JOIN _ma5 s ON s.trade_date = c.trade_date AND s.kind = ?
            """,
            [label, LABEL_VERSION, computed_at, kind],
        )
    con.execute("DROP TABLE IF EXISTS _ma5")
    return {"peak_confirmed": len(peaks), "valley_confirmed": len(valleys)}


def _source_counts(con: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    """成立条件用的源库读数；顺带记下 published 名单里的代码代际分布（.TI/.FP 并存是已知陷阱）。"""
    out: dict[str, Any] = {}
    for table in (
        "fact_market_daily",
        "fact_sector_daily",
        "fact_theme_limit_heat_daily",
        "fact_mainline_sector_daily",
    ):
        out[table] = con.execute(f"SELECT COUNT(*) FROM {SOURCE_ALIAS}.{table}").fetchone()[0]
    suffixes = con.execute(
        """
        SELECT regexp_extract(entity_id, '\\.([A-Z]+)$', 1) AS suffix, COUNT(DISTINCT entity_id)
        FROM history_labels WHERE entity_type = 'sector' GROUP BY 1 ORDER BY 1
        """
    ).fetchall()
    out["sector_code_suffixes"] = {str(s or "?"): int(n) for s, n in suffixes}
    dupes = con.execute(
        f"""
        SELECT COUNT(*) FROM (
            SELECT trade_date, sector_ts_code FROM {SOURCE_ALIAS}.fact_sector_daily
            GROUP BY 1, 2 HAVING COUNT(*) > 1)
        """
    ).fetchone()[0]
    out["sector_dupes_collapsed"] = int(dupes)
    return out
