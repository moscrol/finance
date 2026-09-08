"""结构化历史标签层（设计稿 §3.1 表前 12 行 + P1 个股三行）：把「图像」编译成表里的一行。

    (entity_type, entity_id, trade_date, label, value_num, value_text, label_version, computed_at)

三条硬约束：
1. **确认日语义**：任一 (实体, 交易日) 上的值只依赖该日及之前的事实。用到 ``t+1`` 的标签都是 bug。
2. **复用勿重定义**：严格双红 ``pct_chg>0 且 diff_ratio>10 且 amount>500`` 抄 strategy1-matrix；
   放量阈值与 MA5 峰谷确认日算法直接调 ``market_feature_store.analysis.turning_points``。
3. **确定性 + 版本化**：同一主库同一代码同输出；口径的每次改动升 ``LABEL_VERSION``。

标签目录（sector / theme 的 entity_id 统一用 ``sector_ts_code``，展示时再 join ``dim_sector``；
stock 用 ``stock_ts_code``）：

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
| theme | lifecycle_stage | text/NULL | 题材生命周期七段（酝酿/首发/发酵/主升/分歧/退潮/回流；``theme_lifecycle_timeline.derive_stages`` 状态机，阈值不复制）；首个盘面信号之前与段间空档为 NULL（gap，不是「酝酿」——酝酿要消息面证据，旁路库不读知识库） |
| market | market_stage | text | 投影 ``fact_market_daily.market_stage``，去掉末尾「阶段」别名；NULL 保留 |
| market | volume_surge | 1/0/NULL | ``amount_vs_yesterday_pct > VOLUME_SURGE_PCT``（与 detect_turning_points 同阈值，真库上两口径 74 日完全一致） |
| market | ma5_peak_confirmed | 1/0 | ``SignalDetector`` 的 MA5 顶确认日 |
| market | ma5_valley_confirmed | 1/0 | ``SignalDetector`` 的 MA5 谷确认日 |
| stock | limit_up | 1/0/NULL | 当日在 ``fact_theme_limit_stock_daily`` 且 ``limit_status='U'``；涨停表整日缺失则 NULL |
| stock | first_board | 1/0/NULL | 涨停且 ``limit_times = 1``（连板数 1）；不涨停为 0；涨停但连板数缺失或整日缺失为 NULL |
| stock | new_high_1y | 1/0/NULL | ``fact_stock_high_daily.primary_high_period`` ∈ ``NEW_HIGH_1Y_PERIODS``；新高表整日缺失则 NULL |

``data_gap``（当日 >90% published 板块 ``diff_ratio = 0``）单独落 ``history_data_gaps``，不占标签名额：
该日双红类标签置 NULL，既不进事件集也不进基准率，并进收据成立条件。

题材实体为什么也用 ``sector_ts_code``：2026-09-04 真库核数，``fact_theme_limit_heat_daily`` 623 个代码
全部出现在 ``fact_sector_daily``，99.3% 的热度行能拿到同日 ``pct_chg``；而 ``fact_mainline_theme_daily``
的 ``theme_code``（TH000xx.FP）与之不在同一 ID 空间、无法 join，故 ``mainline_flag`` 取
``fact_mainline_sector_daily``（同 ID 空间，覆盖 106 日 vs 53 日）。

个股 universe 为什么是「涨停表 ∪ 新高表」而不是全市场（``STOCK_UNIVERSE = limit_high_union``）：
全市场 5,568 只 × 405 日 ≈ 2.1M 个股日，标签 + 前瞻结果要 ~8M 行，旁路库膨胀十倍，而问题本身
是「强势股池子里，首板 / 新高这一层选择有没有超额」——基准率取同一池子才是设计稿 §3.2「同 universe」
的本意；择时效应由 ``same_universe_event_days`` 对照列剥离。并集内三个标签稠密打 1/0，只在源表
整日缺失时置 NULL（2026-09-04 真库：涨停表 405 日里缺 10 日，主库 ``fact_market_daily.limit_up``
显示那些天有 40–92 只涨停，是同步缺口不是零涨停日；新高表 405 日全覆盖）。

涨停 / 首板为什么不取设计稿写的 ``fact_limit_advance_daily``：该表由 ``sync_fupanhui_limit_advance``
写入时固定 ``min_boards=2``，**没有首板行**（真库 4,907 行 boards 全 >= 2），且 ``first_limit_date``
依赖接口返回的日期列表，真库有大量负 gap（-9 ～ -337 个交易日）；而 ``fact_theme_limit_stock_daily``
是全量涨停股（``limit_status`` 全 'U'，``limit_times`` 即连板数，首板 21,108 个股日占 79.5%），
逐日只数与 ``fact_market_daily.limit_up`` 在 336/395 日完全相等，与连板梯队重叠部分
``boards == limit_times`` 4,671/4,671。同一 (日, 股) 在多个板块下重复出现，``limit_times`` 零冲突，
按 (日, 股) 折叠。

``new_high_1y`` 为什么用 ``primary_high_period`` 而不解析 ``high_periods_json``：真库核数 primary
恒为 json 里最长周期且周期嵌套（长周期新高必含短周期），primary ∈ {1y,2y,3y,history} 与
json 含 "1y" 两种判法行数完全相等（61,635）。``is_new``（当日新进榜 / 周期升级）未做标签，留作候选。
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

from intelligence.services.market_stage import normalize_market_stage

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

# 口径版本。热度档位、阈值、算法、标签目录任何一处变动都要升版本，旧收据凭它判「不可比」。
# v1 → v2：新增 stock 三标签（limit_up / first_board / new_high_1y），sector / theme / market 口径未动。
# v2 → v3：market_stage 去掉上游值末尾的「阶段」别名，NULL 仍为 NULL。
# v3 → v4：新增 theme 标签 lifecycle_stage（工单 #21 剩余 / G-04：七段单一词表，theme_lifecycle_timeline 状态机）；其余口径未动。
HEAT_TIER = {"dimension": "sector", "scope": "all", "data_stage": "final", "is_realtime": False}
LABEL_VERSION = "v4-heat_sector_all_final_nonrt-stock_limit_high_union-market_stage_normalized-lifecycle_stage_tsm_v1"

DATA_GAP_ZERO_RATIO = 0.9
DUAL_RED_DIFF_RATIO_GT = 10.0
DUAL_RED_AMOUNT_GT = 500.0
HEAT_RANK_JUMP_GE = 5
AMOUNT_RANK_TOP = 10
# 个股：涨停状态码（复盘会 limit_status：U 涨停 / Z 炸板 / D 跌停）；一年新高 = primary 周期在此集合内。
LIMIT_UP_STATUS = "U"
FIRST_BOARD_LIMIT_TIMES = 1
NEW_HIGH_1Y_PERIODS = ("1y", "2y", "3y", "history")
STOCK_UNIVERSE = "limit_high_union"

SECTOR_LABELS = (
    "dual_red_strict",
    "dual_red_streak",
    "diff_ratio_turn_up",
    "multi_period_resonance",
    "amount_rank_top10",
)
THEME_LABELS = ("limit_heat_rank", "limit_heat_rank_jump", "mainline_flag", "lifecycle_stage")
MARKET_LABELS = ("market_stage", "volume_surge", "ma5_peak_confirmed", "ma5_valley_confirmed")
STOCK_LABELS = ("limit_up", "first_board", "new_high_1y")
ALL_LABELS = SECTOR_LABELS + THEME_LABELS + MARKET_LABELS + STOCK_LABELS
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
    "market_stage": "normalize_market_stage(fact_market_daily.market_stage): strip one trailing '阶段'; NULL stays NULL",
    "mainline_flag": "fact_mainline_sector_daily (trade_date, sector_ts_code) exists; NULL on days without coverage",
    "lifecycle_stage": "theme_lifecycle_timeline.derive_stages(fact_sector_daily rows + limit_heat limit_up_count; no message dates, no boards) → 酝酿/首发/发酵/主升/分歧/退潮/回流 per day; NULL before first market signal / between segments",
    "stock_universe": (
        f"{STOCK_UNIVERSE}: distinct (trade_date, stock_ts_code) in fact_theme_limit_stock_daily UNION "
        "fact_stock_high_daily; labels dense 1/0 inside, NULL only on days the source table has no rows"
    ),
    "limit_up": f"fact_theme_limit_stock_daily row with limit_status='{LIMIT_UP_STATUS}' (collapsed over sectors)",
    "first_board": f"limit_up AND limit_times = {FIRST_BOARD_LIMIT_TIMES}; not limit_up → 0; limit_times NULL → NULL",
    "new_high_1y": f"fact_stock_high_daily.primary_high_period IN {list(NEW_HIGH_1Y_PERIODS)}",
    "entity_id": "sector_ts_code for sector & theme; 'market' for market; stock_ts_code for stock",
}


def build_labels(
    source_db: str | Path,
    labels_db: str | Path,
    *,
    now: datetime | None = None,
) -> BuildReport:
    """从主库只读重建全部 16 个标签 + data_gap + 交易日历，写入旁路库。幂等：同输入同输出。"""
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
            _build_lifecycle_stage_labels(con, computed_at)
            ma5_counts = _build_market_labels(con, computed_at)
            stock_coverage = _build_stock_labels(con, computed_at)

            source_max = con.execute(
                f"SELECT MAX(trade_date) FROM {SOURCE_ALIAS}.fact_market_daily"
            ).fetchone()[0]
            counts = _source_counts(con)
            counts["ma5_signals"] = ma5_counts
            counts["stock_coverage"] = stock_coverage
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
# theme：生命周期七段（工单 #21 剩余 / G-04）
# --------------------------------------------------------------------------- #
def lifecycle_stage_rows_by_code(con: duckdb.DuckDBPyConnection) -> dict[str, list[dict[str, Any]]]:
    """每个 ``sector_ts_code`` 的升序逐日行，形状与 ``theme_lifecycle_timeline.load_theme_daily_rows`` 一致。

    涨停数按 ``sector_name`` 精确匹配热度表（同一代码历史上可能多名，全部认）；连板高度 / 首板数不接
    （``fact_limit_advance_daily.theme LIKE`` 是模糊匹配，进标签会把口径变成猜）——状态机对缺失有声明：
    「连板高度数据缺失：主升判定放宽为仅连续双红」。
    """
    base = con.execute(
        f"""
        SELECT sector_ts_code, sector_name, CAST(trade_date AS DATE) AS d, pct_chg, diff_ratio, amount
        FROM {SOURCE_ALIAS}.fact_sector_daily
        WHERE sector_ts_code IS NOT NULL
        ORDER BY sector_ts_code, d
        """
    ).fetchall()
    heat: dict[tuple[str, str], float | None] = {}
    try:
        for name, d, lu in con.execute(
            f"""
            SELECT sector_name, CAST(trade_date AS DATE), MAX(limit_up_count)
            FROM {SOURCE_ALIAS}.fact_theme_limit_heat_daily
            WHERE sector_name IS NOT NULL GROUP BY 1, 2
            """
        ).fetchall():
            heat[(str(name), str(d))] = lu
    except duckdb.Error:
        heat = {}
    by_code: dict[str, list[dict[str, Any]]] = {}
    for code, name, d, pct, diff, amt in base:
        by_code.setdefault(str(code), []).append(
            {
                "trade_date": str(d),
                "pct_chg": pct,
                "diff_ratio": diff,
                "amount": amt,
                "limit_up_count": heat.get((str(name), str(d))),
                "market_share": None,
                "max_boards": None,
                "first_board_count": None,
            }
        )
    return by_code


def _build_lifecycle_stage_labels(con: duckdb.DuckDBPyConnection, computed_at: datetime) -> int:
    """每个（板块, 交易日）一条 ``lifecycle_stage``：段内落七段词，段外不落行（NULL）。

    值是**站在当天**的读数（``derive_stages(..., daily=)``：循环里每天记下机器当时所在的段），不是事后
    段落表按天取值——退潮 / 回流的起点回溯与 ``merge_short_phases`` 会事后改写段边界，按它们取值就是前视。
    与 ``river.theme_lifecycle_stage_object`` 同一函数同一口径，随机抽 30 格两边逐字节相等（测试钉住）。
    """
    from intelligence.services import theme_lifecycle_timeline as _tl

    by_code = lifecycle_stage_rows_by_code(con)
    days = set(str(r[0]) for r in con.execute("SELECT trade_date FROM history_calendar").fetchall())
    if not days or not by_code:
        return 0
    rows: list[tuple] = []
    for code, series in sorted(by_code.items()):
        daily: dict[str, str] = {}
        _tl.derive_stages(series, daily=daily)
        for day, stage in daily.items():
            if day not in days:
                continue
            rows.append(("theme", code, day, "lifecycle_stage", None, stage, LABEL_VERSION, computed_at))
    if rows:
        con.executemany(
            """
            INSERT INTO history_labels
                (entity_type, entity_id, trade_date, label, value_num, value_text, label_version, computed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
    return len(rows)


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
    # Apply the canonical projection in Python so the source fact table stays
    # untouched and every writer shares exactly the same missing-value rules.
    stage_rows = con.execute(
        f"""
        SELECT m.trade_date, m.market_stage
        FROM {SOURCE_ALIAS}.fact_market_daily m
        JOIN history_calendar c ON c.trade_date = m.trade_date
        ORDER BY m.trade_date
        """
    ).fetchall()
    con.executemany(
        """
        INSERT INTO history_labels
            (entity_type, entity_id, trade_date, label, value_num, value_text, label_version, computed_at)
        VALUES (?, ?, ?, 'market_stage', NULL, ?, ?, ?)
        """,
        [
            ("market", MARKET_ENTITY_ID, trade_date, normalize_market_stage(stage), LABEL_VERSION, computed_at)
            for trade_date, stage in stage_rows
        ],
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


# --------------------------------------------------------------------------- #
# stock（universe = 涨停表 ∪ 新高表，并集内稠密 1/0）
# --------------------------------------------------------------------------- #
def _build_stock_labels(con: duckdb.DuckDBPyConnection, computed_at: datetime) -> dict[str, Any]:
    """三个个股标签。返回覆盖读数（两张源表各有多少日、并集多大、涨停表缺哪些日）供成立条件引用。"""
    # 涨停表同一 (日, 股) 在多个板块下重复，按 (日, 股) 折叠；limit_times 真库零冲突，MAX 只是折叠手段。
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE _stk_lim AS
        SELECT t.trade_date, t.stock_ts_code AS entity_id,
               MAX(CASE WHEN t.limit_status = ? THEN 1 ELSE 0 END) AS is_limit,
               MAX(CASE WHEN t.limit_status = ? THEN t.limit_times END) AS limit_times
        FROM {SOURCE_ALIAS}.fact_theme_limit_stock_daily t
        JOIN history_calendar c ON c.trade_date = t.trade_date
        WHERE t.stock_ts_code IS NOT NULL
        GROUP BY 1, 2
        """,
        [LIMIT_UP_STATUS, LIMIT_UP_STATUS],
    )
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE _stk_high AS
        SELECT h.trade_date, h.stock_ts_code AS entity_id, h.primary_high_period
        FROM {SOURCE_ALIAS}.fact_stock_high_daily h
        JOIN history_calendar c ON c.trade_date = h.trade_date
        WHERE h.stock_ts_code IS NOT NULL
        QUALIFY ROW_NUMBER() OVER (
            PARTITION BY h.trade_date, h.stock_ts_code ORDER BY h.updated_at DESC NULLS LAST
        ) = 1
        """
    )
    period_placeholders = ", ".join("?" for _ in NEW_HIGH_1Y_PERIODS)
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE _stk AS
        WITH u AS (
            SELECT trade_date, entity_id FROM _stk_lim
            UNION
            SELECT trade_date, entity_id FROM _stk_high
        ),
        lim_days AS (SELECT DISTINCT trade_date FROM _stk_lim),
        high_days AS (SELECT DISTINCT trade_date FROM _stk_high)
        SELECT u.trade_date, u.entity_id,
            CASE WHEN ld.trade_date IS NULL THEN NULL
                 WHEN l.is_limit = 1 THEN 1
                 ELSE 0 END AS limit_up,
            CASE WHEN ld.trade_date IS NULL THEN NULL
                 WHEN l.is_limit IS DISTINCT FROM 1 THEN 0
                 WHEN l.limit_times IS NULL THEN NULL
                 WHEN l.limit_times = ? THEN 1
                 ELSE 0 END AS first_board,
            CASE WHEN hd.trade_date IS NULL THEN NULL
                 WHEN h.entity_id IS NOT NULL AND h.primary_high_period IS NULL THEN NULL
                 WHEN h.primary_high_period IN ({period_placeholders}) THEN 1
                 ELSE 0 END AS new_high_1y
        FROM u
        LEFT JOIN lim_days ld ON ld.trade_date = u.trade_date
        LEFT JOIN high_days hd ON hd.trade_date = u.trade_date
        LEFT JOIN _stk_lim l ON l.trade_date = u.trade_date AND l.entity_id = u.entity_id
        LEFT JOIN _stk_high h ON h.trade_date = u.trade_date AND h.entity_id = u.entity_id
        """,
        [FIRST_BOARD_LIMIT_TIMES, *NEW_HIGH_1Y_PERIODS],
    )
    for label in STOCK_LABELS:
        con.execute(
            f"""
            INSERT INTO history_labels
                (entity_type, entity_id, trade_date, label, value_num, value_text, label_version, computed_at)
            SELECT 'stock', entity_id, trade_date, ?, ({label})::DOUBLE, NULL, ?, ?
            FROM _stk
            """,
            [label, LABEL_VERSION, computed_at],
        )

    universe_n, lim_days, high_days = con.execute(
        """
        SELECT COUNT(*),
               (SELECT COUNT(DISTINCT trade_date) FROM _stk_lim),
               (SELECT COUNT(DISTINCT trade_date) FROM _stk_high)
        FROM _stk
        """
    ).fetchone()
    # 涨停表在自身首末日之间缺的交易日：这些天 limit_up / first_board 为 NULL，读者据此判「缺口还是零涨停」。
    lim_missing = [
        str(r[0])
        for r in con.execute(
            """
            SELECT c.trade_date FROM history_calendar c
            WHERE c.trade_date BETWEEN (SELECT MIN(trade_date) FROM _stk_lim) AND (SELECT MAX(trade_date) FROM _stk_lim)
              AND NOT EXISTS (SELECT 1 FROM _stk_lim l WHERE l.trade_date = c.trade_date)
            ORDER BY 1
            """
        ).fetchall()
    ]
    for name in ("_stk", "_stk_high", "_stk_lim"):
        con.execute(f"DROP TABLE IF EXISTS {name}")
    return {
        "universe": STOCK_UNIVERSE,
        "universe_stock_days": int(universe_n),
        "limit_list_days": int(lim_days),
        "high_list_days": int(high_days),
        "limit_list_missing_days": lim_missing,
    }


def _source_counts(con: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    """成立条件用的源库读数；顺带记下 published 名单里的代码代际分布（.TI/.FP 并存是已知陷阱）。"""
    out: dict[str, Any] = {}
    for table in (
        "fact_market_daily",
        "fact_sector_daily",
        "fact_theme_limit_heat_daily",
        "fact_mainline_sector_daily",
        "fact_theme_limit_stock_daily",
        "fact_stock_high_daily",
        "fact_stock_daily",
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
