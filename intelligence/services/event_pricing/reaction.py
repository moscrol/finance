"""``EventReaction``：锚点 × 实体 → 事前 m 日 / 当日 / 事后 3-5-10 日、超额、形状标签、「已定价」代理、横截面。

口径与 ``methodology_backtest.outcomes`` 完全一致：基准 = D0 收盘，事后窗从 D0+1 起算、按 ``pct_chg`` 复利；
事前窗止于 D0−1。板块事后窗**直接读** ``history_outcomes``（不重算）；市场层无 outcomes 行，按同一公式算。
特征池 ``_feat`` 覆盖**全部** (实体, 交易日)，锚点行从池里取——非锚点日就是四态读数的基准。
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

import duckdb

from market_feature_store.db import DB_PATH as CANONICAL_DB_PATH

from intelligence.services.methodology_backtest.store import (
    SOURCE_ALIAS,
    BuildReport,
    attach_source,
    default_labels_db_path,
    detach_source,
    naive_utc,
    open_labels_db,
    read_meta,
    utc_now,
    write_meta,
)

from .params import EventParams, load_params
from .store import REACTION_TABLES, ensure_event_schema, reset_event_tables

SUPPORTED_HORIZONS = (3, 5, 10)
SHAPES = ("pre_up_post_down", "pre_down_post_up", "continuation_up", "continuation_down", "flat", "mixed")
SEMANTICS_EXPECTATION = "expectation"
SEMANTICS_STATE_ONLY = "state_only"
CONSENSUS_GAP = "not_wired"
GAP_KIND_REACTION = "reaction"
HEAT_TIER_SQL = "dimension = 'sector' AND scope = 'all' AND data_stage = 'final' AND COALESCE(is_realtime, false) = false"


def _same_entity(a: str, b: str) -> str:
    return f"{a}.entity_type = {b}.entity_type AND {a}.entity_id = {b}.entity_id"


def quantile(sorted_values: list[float], q: float) -> float:
    """线性插值分位数（与 DuckDB quantile_cont 同定义）。输入须已升序且非空。"""
    n = len(sorted_values)
    if n == 1:
        return sorted_values[0]
    pos = (n - 1) * q
    lo = int(pos)
    hi = min(lo + 1, n - 1)
    frac = pos - lo
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * frac


# --------------------------------------------------------------------------- #
# 特征池（TEMP 表，主库已 ATTACH 为 src）
# --------------------------------------------------------------------------- #
def build_feature_pool(con: duckdb.DuckDBPyConnection, params: EventParams) -> None:
    if tuple(params.post_horizons) != SUPPORTED_HORIZONS:
        raise ValueError(f"v0 表结构只支持 post_horizons={SUPPORTED_HORIZONS}，参数给的是 {params.post_horizons}")
    m = int(params.pre_days)
    L = int(params.amount_ratio_lookback_days)
    min_l = max(1, (L * 3 + 3) // 4)
    W = int(params.crowding_lookback_days)
    min_obs = int(params.crowding_min_obs)
    sh = int(params.shape_horizon)

    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE _series AS
        SELECT 'sector' AS entity_type, f.sector_ts_code AS entity_id, c.idx,
               f.pct_chg, f.amount, h.limit_up_count AS limit_up
        FROM (
            SELECT trade_date, sector_ts_code, pct_chg, amount
            FROM {SOURCE_ALIAS}.fact_sector_daily
            WHERE pct_chg IS NOT NULL AND pct_chg > -100 AND sector_ts_code IS NOT NULL
            QUALIFY ROW_NUMBER() OVER (PARTITION BY trade_date, sector_ts_code ORDER BY updated_at DESC NULLS LAST) = 1
        ) f
        JOIN history_calendar c ON c.trade_date = f.trade_date
        LEFT JOIN (
            SELECT trade_date, sector_ts_code, limit_up_count
            FROM {SOURCE_ALIAS}.fact_theme_limit_heat_daily
            WHERE {HEAT_TIER_SQL}
            QUALIFY ROW_NUMBER() OVER (PARTITION BY trade_date, sector_ts_code ORDER BY updated_at DESC NULLS LAST) = 1
        ) h ON h.trade_date = f.trade_date AND h.sector_ts_code = f.sector_ts_code
        UNION ALL
        SELECT 'market', 'market', c.idx, md.sh_index_pct_chg, md.total_amount, md.limit_up
        FROM {SOURCE_ALIAS}.fact_market_daily md
        JOIN history_calendar c ON c.trade_date = md.trade_date
        WHERE md.sh_index_pct_chg IS NOT NULL AND md.sh_index_pct_chg > -100
        """
    )
    # 事前窗：D0−m .. D0−1，必须恰好 m 行（缺行 = NULL，不补）
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE _pre AS
        SELECT b.entity_type, b.entity_id, b.idx,
               CASE WHEN COUNT(r.idx) = {m} THEN (EXP(SUM(LN(1 + r.pct_chg / 100.0))) - 1) * 100 END AS pre_return
        FROM _series b
        LEFT JOIN _series r ON {_same_entity("r", "b")} AND r.idx BETWEEN b.idx - {m} AND b.idx - 1
        GROUP BY 1, 2, 3
        """
    )
    # 事后窗：板块读 outcomes；市场按同一公式算
    con.execute("CREATE OR REPLACE TEMP TABLE _fwd (entity_type VARCHAR, entity_id VARCHAR, idx INTEGER, horizon INTEGER, fwd_return DOUBLE, max_return DOUBLE, days_to_peak INTEGER, drawdown_after_peak DOUBLE, status VARCHAR)")
    con.execute(
        """
        INSERT INTO _fwd
        SELECT o.entity_type, o.entity_id, c.idx, o.horizon, o.fwd_return, o.max_return, o.days_to_peak, o.drawdown_after_peak, o.status
        FROM history_outcomes o
        JOIN history_calendar c ON c.trade_date = o.trade_date
        WHERE o.entity_type = 'sector' AND o.horizon IN (3, 5, 10)
        """
    )
    for h in SUPPORTED_HORIZONS:
        con.execute(
            f"""
            INSERT INTO _fwd
            WITH base AS (SELECT idx FROM _series WHERE entity_type = 'market'),
            steps AS (
                SELECT b.idx, r.idx - b.idx AS step, r.pct_chg
                FROM base b
                JOIN _series r ON r.entity_type = 'market' AND r.idx BETWEEN b.idx + 1 AND b.idx + {h}
            ),
            path AS (
                SELECT *, EXP(SUM(LN(1 + pct_chg / 100.0)) OVER (PARTITION BY idx ORDER BY step ROWS UNBOUNDED PRECEDING)) - 1 AS cum
                FROM steps
            ),
            peak AS (SELECT *, MAX(cum) OVER (PARTITION BY idx) AS mx FROM path),
            agg AS (
                SELECT idx, COUNT(*) AS n_steps,
                       MAX(CASE WHEN step = {h} THEN cum END) AS fwd,
                       MAX(mx) AS mx,
                       MIN(CASE WHEN cum = mx THEN step END) AS peak_step
                FROM peak GROUP BY idx
            )
            SELECT 'market', 'market', b.idx, {h},
                   CASE WHEN a.n_steps = {h} THEN a.fwd * 100 END,
                   CASE WHEN a.n_steps = {h} THEN a.mx * 100 END,
                   CASE WHEN a.n_steps = {h} THEN a.peak_step END,
                   CASE WHEN a.n_steps = {h} THEN ((1 + a.fwd) / (1 + a.mx) - 1) * 100 END,
                   CASE WHEN a.n_steps = {h} THEN 'ok'
                        WHEN b.idx + {h} > (SELECT MAX(idx) FROM history_calendar) THEN 'pending'
                        ELSE 'missing' END
            FROM base b LEFT JOIN agg a ON a.idx = b.idx
            """
        )
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE _fwdp AS
        SELECT entity_type, entity_id, idx,
               MAX(CASE WHEN horizon = 3 THEN fwd_return END) AS fwd_3,
               MAX(CASE WHEN horizon = 5 THEN fwd_return END) AS fwd_5,
               MAX(CASE WHEN horizon = 10 THEN fwd_return END) AS fwd_10,
               MAX(CASE WHEN horizon = 10 THEN max_return END) AS max_10,
               MAX(CASE WHEN horizon = 10 THEN days_to_peak END) AS peak_10,
               MAX(CASE WHEN horizon = 10 THEN drawdown_after_peak END) AS dd_10,
               MAX(CASE WHEN horizon = {sh} THEN status END) AS status_shape
        FROM _fwd GROUP BY 1, 2, 3
        """
    )
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE _amt AS
        SELECT b.entity_type, b.entity_id, b.idx,
               CASE WHEN COUNT(r.amount) >= {min_l} THEN b.amount / NULLIF(AVG(r.amount), 0) END AS d0_amount_ratio
        FROM _series b
        LEFT JOIN _series r ON {_same_entity("r", "b")} AND r.idx BETWEEN b.idx - {L} AND b.idx - 1 AND r.amount IS NOT NULL
        GROUP BY 1, 2, 3, b.amount
        """
    )
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE _crowd AS
        SELECT b.entity_type, b.entity_id, b.idx,
               CASE WHEN l.amount IS NOT NULL AND COUNT(r.amount) >= {min_obs}
                    THEN 100.0 * SUM(CASE WHEN r.amount < l.amount THEN 1 ELSE 0 END) / COUNT(r.amount) END AS crowding_pct_dm1
        FROM _series b
        LEFT JOIN _series l ON {_same_entity("l", "b")} AND l.idx = b.idx - 1
        LEFT JOIN _series r ON {_same_entity("r", "b")} AND r.idx BETWEEN b.idx - {W} AND b.idx - 1 AND r.amount IS NOT NULL
        GROUP BY 1, 2, 3, l.amount
        """
    )
    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE _stage AS
        SELECT c.idx, l.value_text AS stage
        FROM history_labels l JOIN history_calendar c ON c.trade_date = l.trade_date
        WHERE l.entity_type = 'market' AND l.label = 'market_stage'
        """
    )
    thr_sector = float(params.shape_threshold_pct["sector"])
    thr_market = float(params.shape_threshold_pct["market"])
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE _feat AS
        WITH joined AS (
            SELECT s.entity_type, s.entity_id, s.idx, c.trade_date,
                   p.pre_return AS pre_return_m, s.pct_chg AS d0_return, a.d0_amount_ratio,
                   s.limit_up AS d0_limit_up, s.limit_up - l1.limit_up AS d0_limit_up_delta,
                   f.fwd_3, f.fwd_5, f.fwd_10, f.max_10, f.peak_10, f.dd_10, f.status_shape,
                   cr.crowding_pct_dm1, st.stage AS market_stage_dm1,
                   CASE WHEN s.entity_type = 'sector' THEN p.pre_return - mp.pre_return END AS excess_pre_m,
                   CASE WHEN s.entity_type = 'sector' THEN s.pct_chg - ms.pct_chg END AS excess_d0,
                   CASE WHEN s.entity_type = 'sector' THEN f.fwd_3 - mf.fwd_3 END AS excess_fwd_3,
                   CASE WHEN s.entity_type = 'sector' THEN f.fwd_5 - mf.fwd_5 END AS excess_fwd_5,
                   CASE WHEN s.entity_type = 'sector' THEN f.fwd_10 - mf.fwd_10 END AS excess_fwd_10,
                   CASE WHEN s.entity_type = 'sector' THEN ? ELSE ? END AS x
            FROM _series s
            JOIN history_calendar c ON c.idx = s.idx
            LEFT JOIN _pre p ON {_same_entity("p", "s")} AND p.idx = s.idx
            LEFT JOIN _amt a ON {_same_entity("a", "s")} AND a.idx = s.idx
            LEFT JOIN _series l1 ON {_same_entity("l1", "s")} AND l1.idx = s.idx - 1
            LEFT JOIN _fwdp f ON {_same_entity("f", "s")} AND f.idx = s.idx
            LEFT JOIN _crowd cr ON {_same_entity("cr", "s")} AND cr.idx = s.idx
            LEFT JOIN _stage st ON st.idx = s.idx - 1
            LEFT JOIN _pre mp ON mp.entity_type = 'market' AND mp.idx = s.idx
            LEFT JOIN _series ms ON ms.entity_type = 'market' AND ms.idx = s.idx
            LEFT JOIN _fwdp mf ON mf.entity_type = 'market' AND mf.idx = s.idx
        ),
        shaped AS (
            SELECT *,
                   CASE WHEN entity_type = 'sector' THEN excess_pre_m ELSE pre_return_m END AS sp,
                   CASE WHEN entity_type = 'sector' THEN excess_fwd_{sh} ELSE fwd_{sh} END AS sf
            FROM joined
        )
        SELECT *,
               CASE WHEN sp IS NULL OR sf IS NULL THEN NULL
                    WHEN sp > x AND sf < -x THEN 'pre_up_post_down'
                    WHEN sp < -x AND sf > x THEN 'pre_down_post_up'
                    WHEN sp > x AND sf > x THEN 'continuation_up'
                    WHEN sp < -x AND sf < -x THEN 'continuation_down'
                    WHEN ABS(sp) <= x AND ABS(sf) <= x THEN 'flat'
                    ELSE 'mixed' END AS shape_tag
        FROM shaped
        """,
        [thr_sector, thr_market],
    )


def anchor_feature_rows(con: duckdb.DuckDBPyConnection) -> list[tuple]:
    """锚点 × 特征池。锚点当日没有价格行的实体也保留（特征全 NULL → missing）。"""
    return con.execute(
        """
        SELECT a.entity_type, a.entity_id, a.trade_date, a.label, a.value_text, c.idx,
               f.pre_return_m, f.d0_return, f.d0_amount_ratio, f.d0_limit_up, f.d0_limit_up_delta,
               f.fwd_3, f.fwd_5, f.fwd_10, f.max_10, f.peak_10, f.dd_10, f.status_shape,
               f.excess_pre_m, f.excess_d0, f.excess_fwd_3, f.excess_fwd_5, f.excess_fwd_10,
               f.shape_tag, f.crowding_pct_dm1, f.market_stage_dm1
        FROM history_event_anchors a
        JOIN history_calendar c ON c.trade_date = a.trade_date
        LEFT JOIN _feat f ON f.entity_type = a.entity_type AND f.entity_id = a.entity_id AND f.idx = c.idx
        ORDER BY a.trade_date, a.label, a.entity_type, a.entity_id
        """
    ).fetchall()


def node_id(event_class: str, reaction_day: str, entity_type: str, entity_id: str) -> str:
    return hashlib.sha256(f"{event_class}|{reaction_day}|{entity_type}|{entity_id}".encode("utf-8")).hexdigest()[:16]


def _semantics(payload: dict[str, Any], window_start: date | None) -> str:
    pub = payload.get("schedule_published_at")
    if not payload.get("scheduled") or not pub or window_start is None:
        return SEMANTICS_STATE_ONLY
    return SEMANTICS_EXPECTATION if date.fromisoformat(pub) <= window_start else SEMANTICS_STATE_ONLY


def _status(pre: float | None, d0: float | None, fwd_shape: float | None, status_shape: str | None, idx: int, max_idx: int, sh: int) -> str:
    if fwd_shape is None:
        if status_shape == "pending" or idx + sh > max_idx:
            return "pending"
        return "missing"
    if pre is None or d0 is None:
        return "missing"
    return "ok"


def _cross_section(con: duckdb.DuckDBPyConnection, params: EventParams, market_anchors: list[tuple[str, int, str]], computed_at: datetime) -> tuple[int, dict[int, float | None]]:
    """market 类锚点日的板块横截面（前 / 后 K）与申万一级全表；返回 (写入行数, {idx: dispersion_iqr})。"""
    k = int(params.cross_section_top_k)
    sh = int(params.shape_horizon)
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE _names AS
        SELECT sector_ts_code AS entity_id, ANY_VALUE(sector_name) AS entity_name
        FROM (SELECT sector_ts_code, sector_name FROM {SOURCE_ALIAS}.fact_sector_daily
              QUALIFY ROW_NUMBER() OVER (PARTITION BY sector_ts_code ORDER BY trade_date DESC) = 1)
        GROUP BY 1
        """
    )
    # 申万一级序列 + 当日 / 事后 sh 日（同一公式）
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE _sw AS
        SELECT c.idx, s.sw_l1 AS entity_id, s.pct_chg
        FROM (
            SELECT trade_date, sw_l1, pct_chg FROM {SOURCE_ALIAS}.fact_sw_l1_daily
            WHERE pct_chg IS NOT NULL AND pct_chg > -100 AND sw_l1 IS NOT NULL
            QUALIFY ROW_NUMBER() OVER (PARTITION BY trade_date, sw_l1 ORDER BY updated_at DESC NULLS LAST) = 1
        ) s JOIN history_calendar c ON c.trade_date = s.trade_date
        """
    )
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE _sw_feat AS
        SELECT b.idx, b.entity_id, b.pct_chg AS d0,
               CASE WHEN COUNT(r.idx) = {sh} THEN (EXP(SUM(LN(1 + r.pct_chg / 100.0))) - 1) * 100 END AS fwd
        FROM _sw b LEFT JOIN _sw r ON r.entity_id = b.entity_id AND r.idx BETWEEN b.idx + 1 AND b.idx + {sh}
        GROUP BY 1, 2, 3
        """
    )
    rows: list[list[Any]] = []
    dispersion: dict[int, float | None] = {}
    for cls, idx, rd in market_anchors:
        sect = con.execute(
            f"""
            SELECT f.entity_id, n.entity_name, f.excess_d0, f.excess_fwd_{sh}, f.d0_return
            FROM _feat f LEFT JOIN _names n ON n.entity_id = f.entity_id
            WHERE f.entity_type = 'sector' AND f.idx = ?
            """,
            [idx],
        ).fetchall()
        d0s = sorted(float(r[4]) for r in sect if r[4] is not None)
        dispersion[idx] = (quantile(d0s, 0.75) - quantile(d0s, 0.25)) if len(d0s) >= 8 else None
        for metric, col, reverse in (
            ("excess_d0_top", 2, True),
            ("excess_d0_bottom", 2, False),
            (f"excess_fwd{sh}_top", 3, True),
            (f"excess_fwd{sh}_bottom", 3, False),
        ):
            # 并列按实体代码定序，否则重建时前 K 名的边界行会漂
            sign = -1.0 if reverse else 1.0
            ranked = sorted((r for r in sect if r[col] is not None), key=lambda r: (sign * float(r[col]), str(r[0])))[:k]
            for i, r in enumerate(ranked, start=1):
                rows.append([cls, rd, "sector", metric, i, r[0], r[1], float(r[col]), params.ev_version, naive_utc(computed_at)])
        mkt = con.execute("SELECT d0_return, fwd_%d FROM _feat WHERE entity_type = 'market' AND idx = ?" % sh, [idx]).fetchone()
        sw = con.execute("SELECT entity_id, d0, fwd FROM _sw_feat WHERE idx = ?", [idx]).fetchall()
        if mkt is not None and sw:
            m_d0, m_fwd = mkt
            for metric, pick in (("sw_l1_excess_d0", 1), (f"sw_l1_excess_fwd{sh}", 2)):
                base = m_d0 if pick == 1 else m_fwd
                if base is None:
                    continue
                vals = [(str(r[0]), float(r[pick]) - float(base)) for r in sw if r[pick] is not None]
                vals.sort(key=lambda t: (-t[1], t[0]))
                for i, (name, v) in enumerate(vals, start=1):
                    rows.append([cls, rd, "sw_l1", metric, i, name, name, float(v), params.ev_version, naive_utc(computed_at)])
    if rows:
        con.executemany(
            """
            INSERT OR REPLACE INTO history_event_cross_section
                (event_class, reaction_day, entity_kind, metric, rank, entity_id, entity_name, value, ev_version, computed_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            rows,
        )
    return len(rows), dispersion


def build_reaction(
    source_db: str | Path | None,
    labels_db: str | Path | None,
    *,
    params: EventParams | None = None,
    now: datetime | None = None,
) -> BuildReport:
    params = params or load_params()
    source = Path(source_db).expanduser() if source_db else CANONICAL_DB_PATH
    labels_path = Path(labels_db).expanduser() if labels_db else default_labels_db_path(source)
    computed_at = naive_utc(now or utc_now())
    sh = int(params.shape_horizon)
    m = int(params.pre_days)

    con = open_labels_db(labels_path, read_only=False)
    try:
        ensure_event_schema(con)
        meta = read_meta(con)
        for kind in ("labels", "outcomes", "event_calendar", "event_anchors"):
            if kind not in meta:
                raise RuntimeError(f"旁路库没有 {kind} 构建记录，先跑对应 build")
        for kind in ("event_calendar", "event_anchors"):
            if meta[kind]["label_version"] != params.ev_version:
                raise RuntimeError(f"{kind} 版本 {meta[kind]['label_version']} ≠ 当前参数 {params.ev_version}，先重跑")
        if 5 not in (meta["outcomes"].get("horizons") or []) or 10 not in (meta["outcomes"].get("horizons") or []):
            raise RuntimeError(f"history_outcomes 的 horizons {meta['outcomes'].get('horizons')} 缺 5 / 10，先重跑 outcomes")
        source_path = attach_source(con, source)
        try:
            build_feature_pool(con, params)
            cal_rows = con.execute("SELECT idx, trade_date FROM history_calendar ORDER BY idx").fetchall()
            idx_to_date = {int(i): d for i, d in cal_rows}
            max_idx = max(idx_to_date) if idx_to_date else -1
            feats = anchor_feature_rows(con)
            reset_event_tables(con, REACTION_TABLES)
            records: list[list[Any]] = []
            market_anchors: list[tuple[str, int, str]] = []
            n_by_status: dict[str, int] = {}
            for row in feats:
                (etype, eid, rd, label, value_text, idx, pre, d0, amt_ratio, lu, lu_delta,
                 f3, f5, f10, mx10, pk10, dd10, status_shape,
                 ex_pre, ex_d0, ex3, ex5, ex10, shape, crowd, stage) = row
                cls = label[3:] if label.startswith("ev.") else label
                payload = json.loads(value_text) if value_text else {}
                fwd_shape = {3: f3, 5: f5, 10: f10}[sh]
                status = _status(pre, d0, fwd_shape, status_shape, int(idx), max_idx, sh)
                window_start = idx_to_date.get(int(idx) - m)
                semantics = _semantics(payload, window_start)
                rd_s = rd.isoformat()
                if etype == "market":
                    market_anchors.append((cls, int(idx), rd_s))
                records.append(
                    [
                        node_id(cls, rd_s, etype, eid), cls, rd, date.fromisoformat(payload.get("event_date") or rd_s),
                        bool(payload.get("scheduled", False)), str(payload.get("source_grade") or "editorial"),
                        etype, eid, semantics,
                        pre, d0, amt_ratio, lu, lu_delta, f3, f5, f10, mx10, pk10, dd10,
                        ex_pre, ex_d0, ex3, ex5, ex10, shape, crowd, None, CONSENSUS_GAP, None, stage,
                        status, params.ev_version, naive_utc(computed_at),
                    ]
                )
                n_by_status[status] = n_by_status.get(status, 0) + 1
            n_cross, dispersion = _cross_section(con, params, market_anchors, computed_at)
            for rec in records:
                if rec[6] == "market":
                    idx = next((i for c, i, r in market_anchors if r == rec[2].isoformat() and c == rec[1]), None)
                    rec[29] = dispersion.get(idx) if idx is not None else None
            # 反应日当天连价格行都没有的实体：状态 missing 之外再记一条缺口，理由要说清（板块序列换宇宙时这是主因）
            con.execute("DELETE FROM history_event_gaps WHERE gap_kind = ?", [GAP_KIND_REACTION])
            gap_rows = [
                [GAP_KIND_REACTION, f"{rec[1]}:{rec[2].isoformat()}:{rec[7]}", "no_price_row_on_reaction_day", rec[6], params.ev_version, naive_utc(computed_at)]
                for rec in records
                if rec[31] == "missing" and rec[10] is None
            ]
            if gap_rows:
                con.executemany(
                    "INSERT OR IGNORE INTO history_event_gaps (gap_kind, gap_key, reason, detail, ev_version, computed_at) VALUES (?,?,?,?,?,?)",
                    gap_rows,
                )
            if records:
                con.executemany(
                    """
                    INSERT INTO history_event_reaction (
                        node_id, event_class, reaction_day, event_date, scheduled, source_grade, entity_type, entity_id,
                        pre_window_semantics, pre_return_m, d0_return, d0_amount_ratio, d0_limit_up, d0_limit_up_delta,
                        fwd_return_3, fwd_return_5, fwd_return_10, max_return_10, days_to_peak_10, drawdown_after_peak_10,
                        excess_pre_m, excess_d0, excess_fwd_3, excess_fwd_5, excess_fwd_10, shape_tag, crowding_pct_dm1,
                        consensus_stage_dm1, consensus_stage_gap, dispersion_d0_iqr, market_stage_dm1, status, ev_version, computed_at
                    ) VALUES ({})
                    """.format(",".join("?" * 34)),
                    records,
                )
            by_class = dict(con.execute("SELECT event_class, COUNT(*) FROM history_event_reaction GROUP BY 1 ORDER BY 1").fetchall())
            by_sem = dict(con.execute("SELECT pre_window_semantics, COUNT(*) FROM history_event_reaction GROUP BY 1 ORDER BY 1").fetchall())
            source_max = con.execute(f"SELECT MAX(trade_date) FROM {SOURCE_ALIAS}.fact_market_daily").fetchone()[0]
            write_meta(
                con,
                build_kind="event_reaction",
                label_version=params.ev_version,
                source_db=source_path,
                source_max_trade_date=source_max,
                source_row_counts={
                    "anchors": len(feats),
                    "by_status": n_by_status,
                    "by_class": {str(k): int(v) for k, v in by_class.items()},
                    "by_semantics": {str(k): int(v) for k, v in by_sem.items()},
                    "cross_section_rows": n_cross,
                    "no_price_row_on_reaction_day": len(gap_rows),
                    "params": params.to_dict(),
                },
                row_count=len(records),
                horizons=SUPPORTED_HORIZONS,
                computed_at=computed_at,
            )
        finally:
            detach_source(con)
    finally:
        con.close()
    return BuildReport(
        build_kind="event_reaction",
        labels_db=str(labels_path),
        source_db=str(source_path),
        label_version=params.ev_version,
        source_max_trade_date=str(source_max) if source_max is not None else None,
        calendar_start=idx_to_date[min(idx_to_date)].isoformat() if idx_to_date else None,
        calendar_end=idx_to_date[max_idx].isoformat() if idx_to_date else None,
        calendar_days=len(idx_to_date),
        row_count=len(records),
        computed_at=computed_at.isoformat(timespec="seconds") + "Z",
        rows_by_label={str(k): int(v) for k, v in by_class.items()},
        extras={
            "by_status": n_by_status,
            "by_semantics": {str(k): int(v) for k, v in by_sem.items()},
            "cross_section_rows": n_cross,
            "no_price_row_on_reaction_day": len(gap_rows),
        },
    )
