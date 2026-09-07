#!/usr/bin/env python3
"""Build and inspect the teaching-framework slice 1 sidecar objects."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from intelligence.services.methodology_backtest.labels import (  # noqa: E402
    DUAL_RED_AMOUNT_GT,
    DUAL_RED_DIFF_RATIO_GT,
    LABEL_VERSION,
)
from intelligence.services.methodology_backtest.store import (  # noqa: E402
    check_teaching_schema,
    default_labels_db_path,
    open_labels_db,
)
from intelligence.services.river_query import cohort_compare, normalize_stage  # noqa: E402
from intelligence.services.teaching_framework.index_stage import (  # noqa: E402
    build_index_stage,
    label_readouts,
    to_label_rows,
)
from intelligence.services.teaching_framework.leader_succession import (  # noqa: E402
    build_succession,
)
from intelligence.services.teaching_framework.params import (  # noqa: E402
    framework_version,
    load_params,
    parameter_hash,
)
from intelligence.services.teaching_framework.readouts import (  # noqa: E402
    baseline_by_stage,
    eligible_baseline,
    handoff_readout,
    receipt_summary,
    stage_handoff_readouts,
    succession_diagnostics,
)
from intelligence.services.teaching_framework.receipts import (  # noqa: E402
    canonical_rows_hash,
    make_receipt,
    write_receipt,
)
from intelligence.services.teaching_framework.sector_roles import (  # noqa: E402
    MONEY_EFFECT_DEFINITIONS,
    SECTOR_LABELS,
    build_sector_roles,
    money_effect_rule_rows,
)
from intelligence.services.methodology_backtest.stats import readout as stats_readout  # noqa: E402

SOURCE_TABLES = (
    "fact_market_daily", "fact_mainline_sector_daily", "fact_theme_limit_stock_daily", "fact_stock_daily",
    "fact_sector_daily", "fact_theme_limit_heat_daily", "fact_stock_high_daily",
)
BIRTH_COHORT_FEATURES = ("tf.stage_coarse", "tf.deviation_band", "volume_state")


def _now(value: str | None) -> datetime:
    if value:
        text = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc).replace(microsecond=0)


def _rows(con: duckdb.DuckDBPyConnection, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
    cur = con.execute(sql, params or [])
    names = [str(item[0]) for item in cur.description]
    return [dict(zip(names, row, strict=True)) for row in cur.fetchall()]


def _load_market(source: duckdb.DuckDBPyConnection) -> tuple[list[dict[str, Any]], list[str]]:
    market = _rows(source, "SELECT * FROM fact_market_daily ORDER BY trade_date")
    return market, [str(row["trade_date"])[:10] for row in market]


def _load_limit_rows(source: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    return _rows(
        source,
        """SELECT trade_date, stock_ts_code, stock_name, limit_times, open_times,
                  first_limit_time, up_stat, circ_mv, amount
           FROM fact_theme_limit_stock_daily
           WHERE limit_status = 'U'
           ORDER BY trade_date, stock_ts_code""",
    )


def _source_counts(source: duckdb.DuckDBPyConnection) -> dict[str, int]:
    return {table: int(source.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) for table in SOURCE_TABLES}


# 「整体的水位」（创始人 2026-09-07）：全市场个股的涨幅中位数、平均股价、个股相对自身
# MA5 / MA10 偏离度的中位数。均线只用截至当日的收盘；一只股票要在窗口内每个交易日都有
# 行（按 fact_market_daily 日历索引连续）才计入偏离度中位数，停牌股当日不算。
BREADTH_SQL = """
WITH cal AS (
    SELECT trade_date, ROW_NUMBER() OVER (ORDER BY trade_date) AS idx FROM fact_market_daily
),
s AS (
    SELECT d.trade_date, d.stock_ts_code, d.close, d.pct_chg, c.idx
    FROM fact_stock_daily d JOIN cal c USING (trade_date)
    WHERE d.close IS NOT NULL
),
w AS (
    SELECT *,
        AVG(close)   OVER (PARTITION BY stock_ts_code ORDER BY idx ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) AS ma5,
        COUNT(*)     OVER (PARTITION BY stock_ts_code ORDER BY idx ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) AS n5,
        LAG(idx, 4)  OVER (PARTITION BY stock_ts_code ORDER BY idx) AS idx_lag4,
        AVG(close)   OVER (PARTITION BY stock_ts_code ORDER BY idx ROWS BETWEEN 9 PRECEDING AND CURRENT ROW) AS ma10,
        COUNT(*)     OVER (PARTITION BY stock_ts_code ORDER BY idx ROWS BETWEEN 9 PRECEDING AND CURRENT ROW) AS n10,
        LAG(idx, 9)  OVER (PARTITION BY stock_ts_code ORDER BY idx) AS idx_lag9
    FROM s
)
SELECT trade_date,
       COUNT(*)                                                       AS stock_count,
       MEDIAN(pct_chg)                                                AS pct_chg_median,
       100.0 * COUNT(CASE WHEN pct_chg > 0 THEN 1 END) / COUNT(*)    AS up_ratio_pct,
       SUM(CAST(close AS DECIMAL(18, 4))) / COUNT(*)                  AS price_mean,  -- exact sum: order-independent
       MEDIAN(CASE WHEN n5 = 5 AND idx_lag4 = idx - 4 THEN (close / ma5 - 1) * 100 END)   AS ma5_deviation_median,
       COUNT(CASE WHEN n5 = 5 AND idx_lag4 = idx - 4 THEN 1 END)                            AS ma5_count,
       MEDIAN(CASE WHEN n10 = 10 AND idx_lag9 = idx - 9 THEN (close / ma10 - 1) * 100 END) AS ma10_deviation_median,
       COUNT(CASE WHEN n10 = 10 AND idx_lag9 = idx - 9 THEN 1 END)                          AS ma10_count
FROM w
GROUP BY trade_date
ORDER BY trade_date
"""


def _load_breadth(source: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    return _rows(source, BREADTH_SQL)


# 板块侧的市场级日聚合（第二刀，创始人第六段「一体两面」）：
#   new_high_1y_count      1 年及以上周期新高的个股数（fact_stock_high_daily.primary_high_period ∈ 1y/2y/3y/history）
#   dual_red_theme_count   严格双红题材数，口径与回测层 dual_red_strict 完全一致（pct>0 ∧ diff>10 ∧ amount>500）
#   limit_themes_ge3       当日涨停家数 ≥ 3 的题材数（fact_theme_limit_heat_daily final）
#   limit_top1_share_pct   第一题材占全市场涨停的份额
# 某张表当日没有行 → 该列 NULL（flags 侧记缺口），不用 0 冒充。
SECTOR_SQL = f"""
WITH cal AS (SELECT trade_date FROM fact_market_daily),
nh AS (
    SELECT trade_date, COUNT(*) AS new_high_1y_count
    FROM fact_stock_high_daily WHERE primary_high_period IN ('1y', '2y', '3y', 'history')
    GROUP BY trade_date
),
dr AS (
    SELECT trade_date,
           SUM(CASE WHEN pct_chg > 0 AND diff_ratio > {DUAL_RED_DIFF_RATIO_GT} AND amount > {DUAL_RED_AMOUNT_GT} THEN 1 ELSE 0 END) AS dual_red_theme_count,
           -- 双红题材散布在几个申万一级（题材层的「先量再建」：左底向上 6 / 共建主线 5 vs 左底向下 2 / 二次探底 2）；没有双红则 NULL。
           NULLIF(COUNT(DISTINCT CASE WHEN pct_chg > 0 AND diff_ratio > {DUAL_RED_DIFF_RATIO_GT} AND amount > {DUAL_RED_AMOUNT_GT} THEN sw_l1 END), 0) AS dual_red_l1_distinct
    FROM fact_sector_daily WHERE pct_chg IS NOT NULL AND diff_ratio IS NOT NULL AND amount IS NOT NULL
    GROUP BY trade_date
),
lh AS (
    SELECT trade_date,
           SUM(CASE WHEN limit_up_count >= 3 THEN 1 ELSE 0 END) AS limit_themes_ge3,
           MAX(market_share) AS limit_top1_share_pct
    FROM fact_theme_limit_heat_daily WHERE data_stage = 'final'
    GROUP BY trade_date
),
-- 赚钱效应（5 日涨幅前 10 的板块）里有多大比例落在当日成交占比前三的申万一级之外。
-- 创始人第五段「周均线下方……赚钱效应往往就不在成交占比前三的主流板块」；候选规则在此定义下 supported。
-- 5 日涨幅 = 连续 5 个日历交易日（按 fact_market_daily 日历索引）都有行的板块的复合涨幅，窗口不完整不排名。
idx AS (SELECT trade_date, ROW_NUMBER() OVER (ORDER BY trade_date) AS i FROM fact_market_daily),
sw AS (
    SELECT s.trade_date, s.sector_ts_code, s.sw_l1, c.i,
           SUM(LN(1 + s.pct_chg / 100.0)) OVER (PARTITION BY s.sector_ts_code ORDER BY c.i ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) AS lg5,
           COUNT(*) OVER (PARTITION BY s.sector_ts_code ORDER BY c.i ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) AS n5,
           LAG(c.i, 4) OVER (PARTITION BY s.sector_ts_code ORDER BY c.i) AS i_lag4
    FROM fact_sector_daily s JOIN idx c USING (trade_date)
    WHERE s.pct_chg IS NOT NULL AND s.pct_chg > -100
),
ranked AS (
    SELECT trade_date, sector_ts_code, sw_l1,
           ROW_NUMBER() OVER (PARTITION BY trade_date ORDER BY lg5 DESC, sector_ts_code) AS rn
    FROM sw WHERE n5 = 5 AND i_lag4 = i - 4
),
me AS (
    SELECT r.trade_date,
           COUNT(CASE WHEN r.sw_l1 IS NOT NULL THEN 1 END) AS known,
           COUNT(CASE WHEN r.sw_l1 IS NOT NULL AND r.sw_l1 NOT IN (m.industry_1, m.industry_2, m.industry_3) THEN 1 END) AS outside
    FROM ranked r JOIN fact_market_daily m USING (trade_date)
    WHERE r.rn <= 10 AND m.industry_1 IS NOT NULL AND m.industry_2 IS NOT NULL AND m.industry_3 IS NOT NULL
    GROUP BY r.trade_date
),
-- 涨停领涨集合（涨停家数前 10，家数同则封板金额大者先，再按代码）与 5 个交易日前同一集合的 Jaccard（%）。
-- 题材层的「先量再建」读数：主流主升 中位 50 / 2.0 43 vs 共建主线 33 / 承接盘反复 33 / 缩量右底 25——主升期领涨题材持续。
-- 任一侧无集合（当日或 5 日前热度表未覆盖、或无涨停）则 NULL，不当作全部更替。
lt AS (
    SELECT h.trade_date, h.sector_ts_code, c.i,
           ROW_NUMBER() OVER (PARTITION BY h.trade_date ORDER BY h.limit_up_count DESC, COALESCE(h.fd_amount, 0) DESC, h.sector_ts_code) AS rn
    FROM fact_theme_limit_heat_daily h JOIN idx c USING (trade_date)
    WHERE h.data_stage = 'final' AND h.limit_up_count > 0
),
lt10 AS (SELECT trade_date, i, sector_ts_code FROM lt WHERE rn <= 10),
la AS (SELECT i, trade_date, COUNT(*) AS n_a FROM lt10 GROUP BY i, trade_date),
lb AS (SELECT i + 5 AS i, COUNT(*) AS n_b FROM lt10 GROUP BY i),
li AS (SELECT a.i, COUNT(*) AS inter FROM lt10 a JOIN lt10 b ON b.i = a.i - 5 AND b.sector_ts_code = a.sector_ts_code GROUP BY a.i),
lj AS (
    SELECT la.trade_date, 100.0 * COALESCE(li.inter, 0) / (la.n_a + lb.n_b - COALESCE(li.inter, 0)) AS limit_top10_persist_5d_pct
    FROM la JOIN lb USING (i) LEFT JOIN li USING (i)
),
-- 承接：昨日涨停股（题材涨停股表 limit_status='U'，按股票去重）今日在个股日线上的平均涨幅（%）。
-- 平台「承接盘反复」的字面对象：主流主升 5 日内负溢价天数均值 0.07 / 2.0 0.23，承接盘反复 0.59，共建主线 0.70，
-- 左底向下 1.21 / 缩量右底 1.15；正负翻转次数 主升 0.18、承接盘反复 0.91、共建主线 1.36、二次探底 1.97。
-- 昨日无涨停股或今日个股日线缺则 NULL；5 日窗口要求连续 5 个日历交易日都有值。
lim AS (
    SELECT DISTINCT l.trade_date, c.i, l.stock_ts_code
    FROM fact_theme_limit_stock_daily l JOIN idx c USING (trade_date) WHERE l.limit_status = 'U'
),
prem AS (
    -- exact DECIMAL sum, not AVG(DOUBLE): the parallel hash aggregate sums in arbitrary order and a value sitting on a
    -- 6-decimal rounding boundary (0.6590625) flipped between two otherwise identical rebuilds.
    SELECT c.trade_date, c.i, SUM(CAST(s.pct_chg AS DECIMAL(18, 6))) / COUNT(*) AS limit_premium_pct
    FROM lim JOIN idx c ON c.i = lim.i + 1
    JOIN fact_stock_daily s ON s.trade_date = c.trade_date AND s.stock_ts_code = lim.stock_ts_code
    WHERE s.pct_chg IS NOT NULL
    GROUP BY c.trade_date, c.i
),
prem_lag AS (SELECT *, LAG(limit_premium_pct) OVER (ORDER BY i) AS prev_pct, LAG(i) OVER (ORDER BY i) AS prev_i FROM prem),
prem_w AS (
    SELECT trade_date, i, limit_premium_pct,
           AVG(limit_premium_pct) OVER w AS ma5, COUNT(*) OVER w AS n5, LAG(i, 4) OVER (ORDER BY i) AS i_lag4,
           SUM(CASE WHEN limit_premium_pct < 0 THEN 1 ELSE 0 END) OVER w AS neg5,
           SUM(CASE WHEN prev_i = i - 1 AND SIGN(limit_premium_pct) <> SIGN(prev_pct) THEN 1 ELSE 0 END) OVER w AS flips5
    FROM prem_lag WINDOW w AS (ORDER BY i ROWS BETWEEN 4 PRECEDING AND CURRENT ROW)
)
SELECT cal.trade_date, nh.new_high_1y_count, dr.dual_red_theme_count, dr.dual_red_l1_distinct, lh.limit_themes_ge3, lh.limit_top1_share_pct,
       CASE WHEN me.known > 0 THEN 100.0 * me.outside / me.known END AS rps5_outside_top3_pct,
       lj.limit_top10_persist_5d_pct,
       prem_w.limit_premium_pct,
       CASE WHEN prem_w.n5 = 5 AND prem_w.i_lag4 = prem_w.i - 4 THEN prem_w.ma5 END AS limit_premium_ma5_pct,
       CASE WHEN prem_w.n5 = 5 AND prem_w.i_lag4 = prem_w.i - 4 THEN prem_w.neg5 END AS limit_premium_neg_5d,
       CASE WHEN prem_w.n5 = 5 AND prem_w.i_lag4 = prem_w.i - 4 THEN prem_w.flips5 END AS limit_premium_flips_5d
FROM cal LEFT JOIN nh USING (trade_date) LEFT JOIN dr USING (trade_date) LEFT JOIN lh USING (trade_date) LEFT JOIN me USING (trade_date)
     LEFT JOIN lj USING (trade_date) LEFT JOIN prem_w USING (trade_date)
ORDER BY cal.trade_date
"""


def _load_sector_breadth(source: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    return _rows(source, SECTOR_SQL)


def _open_sidecar_for_write(path: Path) -> duckdb.DuckDBPyConnection:
    side = open_labels_db(path, read_only=False)
    problems = check_teaching_schema(side)
    if problems:
        side.close()
        raise RuntimeError("旁路库 schema 过期：\n  " + "\n  ".join(problems))
    return side


def _read_context(labels_path: Path) -> dict[str, dict[str, Any]]:
    """Teaching labels keyed by day; ``tf.`` is the native namespace, ``src.`` stays prefixed."""
    if not labels_path.is_file():
        return {}
    context: dict[str, dict[str, Any]] = {}
    side = open_labels_db(labels_path, read_only=True)
    try:
        try:
            rows = side.execute(
                """SELECT trade_date, label, value_num, value_text
                   FROM history_teaching_labels
                   WHERE entity_type='market' AND entity_id='market' AND status='ok'"""
            ).fetchall()
        except duckdb.CatalogException:
            return {}
    finally:
        side.close()
    for day, label, value_num, value_text in rows:
        value = value_text if value_text is not None else value_num
        context.setdefault(str(day)[:10], {})[str(label).removeprefix("tf.")] = value
    return context


REFERENCE_SOURCE = "fupanhui.reviews_overview"


def _read_reference(labels_path: Path) -> dict[str, dict[str, Any]]:
    """Platform reference stages keyed by day, if the sidecar has them (创始人：「当参照」)."""
    if not labels_path.is_file():
        return {}
    side = open_labels_db(labels_path, read_only=True)
    try:
        try:
            rows = _rows(side, "SELECT * FROM history_reference_stages WHERE source = ?", [REFERENCE_SOURCE])
        except duckdb.CatalogException:
            return {}
    finally:
        side.close()
    return {str(row["trade_date"])[:10]: row for row in rows}


def _num(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def cmd_load_reference(args: argparse.Namespace) -> int:
    """Load a pulled reviews/overview JSON (see scripts/fupanhui_review_overview_pull.py) into the sidecar."""
    payload = json.loads(Path(args.json).expanduser().read_text(encoding="utf-8"))
    items = payload.get("items") or []
    if not items:
        raise ValueError("参考标注 JSON 里没有 items")
    pulled_at = payload.get("pulled_at")
    loaded_at = _now(args.computed_at).replace(tzinfo=None)
    side = _open_sidecar_for_write(Path(args.labels_db).expanduser())
    try:
        side.execute("DELETE FROM history_reference_stages WHERE source = ?", [REFERENCE_SOURCE])
        rows = []
        for it in items:
            liq, br, a5, sw, p5 = (it.get(k) or {} for k in ("liquidity", "breadth", "amount_top5", "sw_industry", "price_top5"))
            vendor_updated = it.get("updated_at")
            rows.append((
                REFERENCE_SOURCE, it["trade_date"], it.get("cycle_stage"), it.get("external_cycle"), it.get("internal_cycle"),
                it.get("is_ice_point"), it.get("ice_point_level"),
                _num(liq.get("market_amount_yi")), _num(liq.get("market_amount_change_pct")), _num(liq.get("market_amount_ma20_yi")), _num(liq.get("market_amount_vs_ma20_pct")),
                _num(br.get("up_rate_ma5_pct")), br.get("up_count"), br.get("limit_up_count_non_st"),
                _num(sw.get("top3_market_share_pct")), _num(a5.get("market_share_pct")), _num(a5.get("rising_amount_share_pct")), _num(a5.get("rising_avg_change_pct")),
                _num(p5.get("avg_change_pct")), _num(p5.get("market_share_pct")), _num(p5.get("amount_change_pct")),
                it.get("formula_version"), it.get("data_version"),
                datetime.fromisoformat(vendor_updated).astimezone(timezone.utc).replace(tzinfo=None) if vendor_updated else None,
                json.dumps(it, ensure_ascii=False, sort_keys=True),
                datetime.fromisoformat(pulled_at.replace("Z", "+00:00")).astimezone(timezone.utc).replace(tzinfo=None) if pulled_at else None,
                loaded_at,
            ))
        side.executemany(
            """INSERT INTO history_reference_stages VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        summary = _rows(
            side,
            """SELECT cycle_stage, COUNT(*) AS days, MIN(trade_date) AS first_day, MAX(trade_date) AS last_day
               FROM history_reference_stages WHERE source = ? GROUP BY cycle_stage ORDER BY days DESC""",
            [REFERENCE_SOURCE],
        )
        span = side.execute("SELECT MIN(trade_date), MAX(trade_date), COUNT(*) FROM history_reference_stages WHERE source = ?", [REFERENCE_SOURCE]).fetchone()
    finally:
        side.close()
    print(json.dumps({
        "source": REFERENCE_SOURCE, "rows": len(rows), "first_day": span[0], "last_day": span[1],
        "by_cycle_stage": summary, "pulled_at": pulled_at, "note": "reference stages are vendor labels written after the fact (updated_at); comparison only, never a label input",
    }, ensure_ascii=False, indent=2, default=str))
    return 0


def _nearest_rank(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, int(round(q * (len(ordered) - 1)))))]


def cmd_calibrate_stages(args: argparse.Namespace) -> int:
    """Read each stage's common ranges and the observed transitions off the platform labels, into a new parameter file.

    用户 2026-09-07 第八 / 十段：门槛不由创始人给，「回溯历史来找出共性区间」；平台标注「当参照」。
    Only days up to ``--train-until`` are read; everything after is left for the receipt's
    ``agreement_validate``.  Quantiles are nearest-rank on the sidecar's view labels, so the
    output is reproducible from the same sidecar.
    """
    from intelligence.services.teaching_framework.stage_rules import BAND_VIEWS, REFERENCE_STAGE_ALIASES, STAGES

    params = load_params(args.params)
    labels_path = Path(args.labels_db).expanduser()
    lo_q, hi_q = float(args.quantiles[0]), float(args.quantiles[1])
    if not 0 <= lo_q < hi_q <= 1:
        raise ValueError("--quantiles 必须是 0 ≤ lo < hi ≤ 1")
    reference = _read_reference(labels_path)
    if not reference:
        raise ValueError("旁路库里没有参照标注；先 load-reference")
    side = open_labels_db(labels_path, read_only=True)
    try:
        label_rows = _rows(
            side,
            """SELECT trade_date, label, value_num FROM history_teaching_labels
               WHERE entity_type='market' AND entity_id='market' AND status='ok' AND value_num IS NOT NULL
                 AND trade_date <= ?""",
            [args.train_until],
        )
        labels_version = side.execute(
            "SELECT DISTINCT framework_version FROM history_teaching_labels WHERE framework_version IS NOT NULL"
        ).fetchall()
        # Pin the exact label build the bands were read from: the source data moves (backfills), and so do the quantiles.
        labels_receipt = side.execute(
            """SELECT canonical_hash, source_fingerprint, source_max_trade_date FROM history_teaching_receipts
               WHERE build_kind = 'teaching_labels' ORDER BY computed_at DESC LIMIT 1"""
        ).fetchone()
    finally:
        side.close()
    by_day: dict[str, dict[str, float]] = {}
    for row in label_rows:
        by_day.setdefault(str(row["trade_date"])[:10], {})[str(row["label"])] = float(row["value_num"])
    view_keys = {view: (view if view.startswith("src.") else f"tf.{view}") for view, _ in BAND_VIEWS}
    samples: dict[str, dict[str, list[float]]] = {stage: {view: [] for view in view_keys} for stage in STAGES}
    days_per_stage: Counter[str] = Counter()
    sequence: list[tuple[str, str]] = []
    for day in sorted(reference):
        if day > args.train_until:
            continue
        stage = REFERENCE_STAGE_ALIASES.get(str(reference[day].get("cycle_stage")))
        if stage is None:
            continue
        sequence.append((day, stage))
        if day not in by_day:
            continue
        days_per_stage[stage] += 1
        for view, key in view_keys.items():
            value = by_day[day].get(key)
            if value is not None:
                samples[stage][view].append(value)
    bands = {
        stage: {
            view: [round(_nearest_rank(vals, lo_q), 4), round(_nearest_rank(vals, hi_q), 4)]
            for view, vals in views.items() if len(vals) >= int(args.min_days)
        }
        for stage, views in samples.items()
    }
    transitions: dict[str, Counter[str]] = {stage: Counter() for stage in STAGES}
    for (_, a), (_, b) in zip(sequence, sequence[1:]):
        if a != b:
            transitions[a][b] += 1
    graph = {stage: sorted(targets, key=lambda t: (-targets[t], t)) for stage, targets in transitions.items()}
    out = dict(params)
    out["framework_version_base"] = args.version_base
    out["stage_bands"] = bands
    out["transition_graph"] = graph
    out["stage_bands_derived_from"] = {
        "source": REFERENCE_SOURCE,
        "train_until": args.train_until,
        "reference_days_used": sum(days_per_stage.values()),
        "days_per_stage": dict(sorted(days_per_stage.items())),
        "quantiles": [lo_q, hi_q],
        "min_days": int(args.min_days),
        "views": [view for view, _ in BAND_VIEWS],
        "labels_framework_version": sorted(str(v[0]) for v in labels_version),
        "labels_canonical_hash": labels_receipt[0] if labels_receipt else None,
        "labels_source_fingerprint": labels_receipt[1] if labels_receipt else None,
        "labels_source_max_trade_date": str(labels_receipt[2]) if labels_receipt and labels_receipt[2] is not None else None,
        "transition_counts": {stage: dict(sorted(c.items())) for stage, c in transitions.items() if c},
        "method": "nearest-rank quantiles of each view on the platform's stage days up to train_until; edges = stage moves observed in the same period",
    }
    target = Path(args.params_out).expanduser()
    target.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    validated = load_params(target)
    print(json.dumps({
        "params_out": str(target), "framework_version": framework_version(validated),
        "train_until": args.train_until, "days_per_stage": dict(sorted(days_per_stage.items())),
        "bands": bands, "transition_graph": graph,
    }, ensure_ascii=False, indent=2, default=str))
    return 0


def _bulk_insert_labels(side: duckdb.DuckDBPyConnection, rows: list[tuple[Any, ...]]) -> None:
    """Insert label rows through a temporary CSV + COPY: ~2M sector rows a day-by-day INSERT would take minutes."""
    import csv
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        for row in rows:
            writer.writerow(["" if v is None else v for v in row])
        tmp_path = handle.name
    try:
        side.execute(
            """INSERT INTO history_teaching_labels
               (entity_type, entity_id, trade_date, label, value_num, value_text, label_version, framework_version, status, status_reason, computed_at)
               SELECT * FROM read_csv(?, header=false, nullstr='', columns={
                 'entity_type':'VARCHAR','entity_id':'VARCHAR','trade_date':'DATE','label':'VARCHAR','value_num':'DOUBLE',
                 'value_text':'VARCHAR','label_version':'VARCHAR','framework_version':'VARCHAR','status':'VARCHAR',
                 'status_reason':'VARCHAR','computed_at':'TIMESTAMP'})""",
            [tmp_path],
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def cmd_build_sector_roles(args: argparse.Namespace) -> int:
    """C 类：板块角色逐日标签 + 板块级赚钱效应集合 + 候选规则 money_effect_outside_volume_top3_below_ma 的四态."""
    params = load_params(args.params)
    fw = framework_version(params)
    build_time = _now(args.computed_at)
    source_path = Path(args.db_path).expanduser()
    labels_path = Path(args.labels_db).expanduser()
    source = duckdb.connect(str(source_path), read_only=True)
    try:
        market, dates = _load_market(source)
        sectors = _rows(source, "SELECT trade_date, sector_ts_code, sector_name, sw_l1, pct_chg, amount, diff_ratio FROM fact_sector_daily ORDER BY trade_date, sector_ts_code")
        heat = _rows(source, "SELECT trade_date, sector_ts_code, limit_up_count, fd_amount FROM fact_theme_limit_heat_daily WHERE data_stage = 'final' ORDER BY trade_date, sector_ts_code")
        highs = _rows(source, "SELECT trade_date, sw_l1 FROM fact_stock_high_daily WHERE primary_high_period IN ('1y', '2y', '3y', 'history') ORDER BY trade_date")
        vendor = _rows(source, "SELECT trade_date, sector_ts_code FROM fact_mainline_sector_daily ORDER BY trade_date, sector_ts_code")
        source_counts = _source_counts(source)
    finally:
        source.close()
    result = build_sector_roles(sectors, heat, market, calendar=dates, high_rows=highs, vendor_rows=vendor)
    context = _read_context(labels_path)  # market teaching labels (above_week_ma / stage_coarse) from build-labels
    reference = _read_reference(labels_path)
    rows: list[tuple[Any, ...]] = []
    stamp = build_time.replace(tzinfo=None)
    for rec in result["sectors"]:
        for label in SECTOR_LABELS:
            value = rec.get(label)
            if isinstance(value, bool):
                num, text = int(value), None
            elif isinstance(value, (int, float)):
                num, text = float(value), None
            elif value is None:
                num, text = None, None
            else:
                num, text = None, str(value)
            rows.append(("sector", rec["sector_ts_code"], rec["trade_date"], f"tf.{label}", num, text, LABEL_VERSION, fw, "ok", None, stamp))
    # 候选规则四态：条件 = 周均线下方，基准 = 上方，每个赚钱效应定义各出一份。
    min_n = int(params["min_n"])
    rule_readouts = {}
    for definition in MONEY_EFFECT_DEFINITIONS:
        parts = money_effect_rule_rows(result["days"], context, definition=definition)
        ro = stats_readout(parts["below_ma"], baseline_n=len(parts["above_ma"]), baseline_k=sum(parts["above_ma"]), min_n=min_n)
        rule_readouts[definition] = {"readout": ro.to_dict(), "below_ma_days": len(parts["below_ma"]), "above_ma_days": len(parts["above_ma"]), "excluded": parts["excluded"]}
    # 先量再建：各定义的集合大小与「在前三申万之外」比例，按平台参照阶段分布。
    by_ref_stage: dict[str, dict[str, list[float]]] = {}
    for s in result["days"]:
        if s.get("status") != "ok":
            continue
        ref_stage = str((reference.get(str(s["trade_date"])[:10]) or {}).get("cycle_stage") or "unlabeled")
        bucket = by_ref_stage.setdefault(ref_stage, {})
        for key, v in s.items():
            # every numeric day-level aggregate (set sizes, outside-top3 shares, L1 concentration, 5-day Jaccard, 价板块 count)
            if key in ("trade_date", "sectors") or isinstance(v, bool) or not isinstance(v, (int, float)):
                continue
            bucket.setdefault(key, []).append(float(v))
    def _q(vals: list[float]) -> dict[str, Any]:
        vals = sorted(vals)
        n = len(vals)
        pick = lambda q: vals[min(n - 1, max(0, int(round(q * (n - 1)))))]  # noqa: E731
        return {"n": n, "p25": round(pick(0.25), 4), "median": round(pick(0.5), 4), "p75": round(pick(0.75), 4)}
    views_by_reference_stage = {stage: {k: _q(v) for k, v in sorted(m.items())} for stage, m in sorted(by_ref_stage.items())}
    day_status = Counter(str(s.get("status")) for s in result["days"])
    side = _open_sidecar_for_write(labels_path)
    try:
        side.execute("DELETE FROM history_teaching_labels WHERE entity_type = 'sector'")
        _bulk_insert_labels(side, rows)
        canonical = canonical_rows_hash(
            side, table="history_teaching_labels", primary_key=("entity_type", "entity_id", "trade_date", "label"),
            where="entity_type = 'sector'",
        )
        readouts = {
            "days": dict(sorted(day_status.items())),
            "sector_rows": len(result["sectors"]),
            "labels": list(SECTOR_LABELS),
            "money_effect_definitions": list(MONEY_EFFECT_DEFINITIONS),
            "money_effect_rule": {
                "name": "money_effect_outside_volume_top3_below_ma",
                "provenance": "teaching（用户 2026-09-07 第五段）",
                "condition": "tf.above_week_ma = 0（周均线下方）",
                "outcome": "赚钱效应集合里 sw_l1 已知的板块中，> 50% 不属于当日 industry_1..3",
                "baseline": "tf.above_week_ma = 1 的日子，同一 outcome",
                "by_definition": rule_readouts,
            },
            "views_by_reference_stage": views_by_reference_stage,
        }
        receipt = make_receipt(
            build_kind="sector_roles", framework_version=fw, label_version=LABEL_VERSION,
            source_db=str(source_path), source_max_trade_date=max(dates) if dates else None,
            source_row_counts=source_counts, parameter_hash=parameter_hash(params), canonical_hash=canonical,
            coverage_summary={"calendar_days": len(dates), "sector_days_ok": day_status.get("ok", 0), "sector_label_rows": len(rows)},
            gap_summary={"sector_rows_absent_days": day_status.get("sector_rows_absent", 0)},
            readouts=readouts, computed_at=build_time,
        )
        write_receipt(side, receipt)
    finally:
        side.close()
    print(json.dumps({"build_kind": "sector_roles", "framework_version": fw, "rows": len(rows), "canonical_hash": canonical, "readouts": readouts}, ensure_ascii=False, indent=2, default=str))
    return 0


def cmd_build_labels(args: argparse.Namespace) -> int:
    params = load_params(args.params)
    fw = framework_version(params)
    build_time = _now(args.computed_at)
    source_path = Path(args.db_path).expanduser()
    labels_path = Path(args.labels_db).expanduser()
    source = duckdb.connect(str(source_path), read_only=True)
    try:
        market, dates = _load_market(source)
        vendor = _rows(source, "SELECT trade_date, sector_ts_code, amount FROM fact_mainline_sector_daily ORDER BY trade_date, sector_ts_code")
        stocks = _load_limit_rows(source)
        amounts = _rows(source, "SELECT trade_date, stock_ts_code, amount FROM fact_stock_daily ORDER BY trade_date, stock_ts_code")
        breadth = _load_breadth(source)
        sector_breadth = _load_sector_breadth(source)
        source_counts = _source_counts(source)
    finally:
        source.close()
    records = build_index_stage(
        market, calendar=dates, vendor_rows=vendor, stock_rows=stocks,
        amount_rows=amounts, breadth_rows=breadth, sector_rows=sector_breadth, params=params, supplier_normalizer=normalize_stage,
    )
    label_rows = to_label_rows(records, framework_version=fw, computed_at=build_time)
    gap_rows: list[tuple[Any, ...]] = []
    for record in records:
        day = record["trade_date"]
        if record["gap"]:
            gap_rows.append((day, "market_input", json.dumps(record["gap"]), fw, "gap", "required_market_field_null"))
            continue
        for label, reason in sorted(record.get("scalar_gaps", {}).items()):
            gap_rows.append((day, f"tf.{label}", None, fw, "gap", reason))
    readouts = label_readouts(records, params, reference=_read_reference(labels_path) or None)
    side = _open_sidecar_for_write(labels_path)
    try:
        side.execute("DELETE FROM history_teaching_labels WHERE entity_type = 'market'")
        side.execute("DELETE FROM history_teaching_gaps")
        side.executemany(
            """INSERT INTO history_teaching_labels
               (entity_type, entity_id, trade_date, label, value_num, value_text,
                label_version, framework_version, status, status_reason, computed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    row["entity_type"], row["entity_id"], row["trade_date"], row["label"],
                    row["value_num"], row["value_text"], LABEL_VERSION, row["label_version"],
                    "ok", None, build_time.replace(tzinfo=None),
                )
                for row in label_rows
            ],
        )
        if gap_rows:
            side.executemany(
                """INSERT INTO history_teaching_gaps
                   (trade_date, gap_kind, missing_cols, framework_version, status, status_reason, computed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [(*gap, build_time.replace(tzinfo=None)) for gap in gap_rows],
            )
        canonical = canonical_rows_hash(
            side, table="history_teaching_labels", primary_key=("entity_type", "entity_id", "trade_date", "label"),
            where="entity_type = 'market'",
        )
        receipt = make_receipt(
            build_kind="teaching_labels", framework_version=fw, label_version=LABEL_VERSION,
            source_db=str(source_path), source_max_trade_date=max(dates) if dates else None,
            source_row_counts=source_counts, parameter_hash=parameter_hash(params),
            canonical_hash=canonical,
            coverage_summary={"market_days": readouts["days_total"], "usable_days": readouts["days_usable"], "gap_days": readouts["days_gap"]},
            gap_summary={"market_input": readouts["days_gap"], "scalar": readouts["scalar_gap_counts"]},
            readouts=readouts, computed_at=build_time,
        )
        write_receipt(side, receipt)
    finally:
        side.close()
    print(json.dumps({
        "build_kind": "teaching_labels", "framework_version": fw,
        "rows": len(label_rows), "gap_rows": len(gap_rows), "canonical_hash": canonical,
        "readouts": readouts,
    }, ensure_ascii=False, indent=2, default=str))
    return 0


def _birth_cohorts(nodes: list[Any], *, source_path: Path, labels_path: Path, fw: str) -> dict[str, Any]:
    """Birth-environment comparison per spec §4.6; tables only, nothing is registered."""
    births = [str(n.birth_day) for n in nodes if n.status == "ok" and n.birth_day]
    unique = sorted(set(births))
    out: dict[str, Any] = {
        "birth_days_total": len(births),
        "birth_days_unique": len(unique),
        "birth_days_duplicates_dropped": len(births) - len(unique),
        "bucket_policy": "teaching values bucket as-is (ambiguous / no_evidence are buckets); days without the label are dropped and counted in notes",
        "features": {},
    }
    for feature in BIRTH_COHORT_FEATURES:
        try:
            report = cohort_compare(
                unique, feature=feature, db_path=source_path,
                labels_db_path=labels_path if feature.startswith("tf.") else None,
                framework_version=fw if feature.startswith("tf.") else None,
            )
            out["features"][feature] = report.to_dict()
        except (FileNotFoundError, ValueError) as exc:
            out["features"][feature] = {"skipped": str(exc)}
    return out


def cmd_build_succession(args: argparse.Namespace) -> int:
    params = load_params(args.params)
    fw = framework_version(params)
    build_time = _now(args.computed_at)
    source_path = Path(args.db_path).expanduser()
    labels_path = Path(args.labels_db).expanduser()
    source = duckdb.connect(str(source_path), read_only=True)
    try:
        market, dates = _load_market(source)
        stocks = _load_limit_rows(source)
        source_counts = _source_counts(source)
    finally:
        source.close()
    limit_days = {str(row["trade_date"])[:10] for row in stocks}
    # A calendar day with no limit rows is only "covered empty" when the market
    # table independently says there were zero limit-ups; otherwise it is a gap.
    covered_dates = limit_days | {str(row["trade_date"])[:10] for row in market if row.get("limit_up") == 0}
    context = _read_context(labels_path)
    result = build_succession(
        dates, stocks, covered_dates=covered_dates, params=params,
        knowledge_cutoff=max(dates) if dates else None, context_by_date=context,
        framework_version=fw,
    )
    nodes = result["nodes"]
    min_n = int(params["min_n"])
    baseline_rows = eligible_baseline(result, dates, context_by_date=context)
    readout = handoff_readout(nodes, baseline=[row["handoff"] for row in baseline_rows], min_n=min_n)
    buckets = stage_handoff_readouts(nodes, baseline_by_stage(baseline_rows), min_n=min_n)
    readouts = {
        "handoff_rule": "leader_handoff_from_low_boards (provenance.kind=teaching; not registered in methodology/rules)",
        # Definitions are spelled out next to the verdict so the two rates are
        # read together with how their windows sit relative to the successor.
        "handoff_definition": {
            "event": "break day T: no member of the top group of T-1 (ties allowed, 创始人 09-07) is sealed on T; candidates = limit_times<=2 on T-1..T+1 excluding that group; outcome = the next top group disjoint from it (born on d>=T) has a member in candidates",
            "baseline": "non-break day D with at least one member of top(D-1) still sealed and not overtaken: candidates = limit_times<=2 on D-1..D+1 excluding top(D-1); outcome = next top group disjoint from top(D-1) (born on d>=D+1) has a member in candidates",
            "partial_breaks": "days where only part of a tied top group broke are not breaks (the market's highest is still one of yesterday's leaders); their count is in diagnostics.partial_break_days",
            "note": "the event window ends one day after the earliest possible birth; the baseline window ends at or before it — see diagnostics.baseline_handoff_by_distance_to_next_break and event_handoff_by_birth_boards before comparing the two rates",
        },
        "handoff_readout": readout.to_dict(),
        "handoff_by_break_stage": [bucket.to_dict() for bucket in buckets],
        "sample": receipt_summary(nodes, baseline_rows),
        "diagnostics": succession_diagnostics(result, baseline_rows),
        "birth_environment": _birth_cohorts(nodes, source_path=source_path, labels_path=labels_path, fw=fw),
    }
    side = _open_sidecar_for_write(labels_path)
    try:
        side.execute("DELETE FROM history_leader_succession")
        side.execute("DELETE FROM history_overtaken")
        for node in nodes:
            side.execute(
                """INSERT INTO history_leader_succession
                   (node_id, break_day, leader_i, leader_i_name, leader_i_peak_boards, leader_i_group_json,
                    birth_day, leader_next, leader_next_name, leader_next_group_json, birth_boards, candidates_json,
                    gap_days, path_json, shape_tags_json, handoff, context_break, context_birth, forward,
                    framework_version, status, status_reason, computed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    node.node_id, node.break_day, node.leader_i, node.leader_i_name,
                    node.leader_i_peak_boards, json.dumps(node.leader_i_group, ensure_ascii=False),
                    node.birth_day, node.leader_next, node.leader_next_name,
                    json.dumps(node.leader_next_group, ensure_ascii=False), node.birth_boards,
                    json.dumps(node.candidates, ensure_ascii=False),
                    node.gap_days, json.dumps(node.path, ensure_ascii=False), json.dumps(node.shape_tags, ensure_ascii=False),
                    node.handoff, json.dumps(node.context_break, ensure_ascii=False), json.dumps(node.context_birth, ensure_ascii=False),
                    json.dumps(node.forward, ensure_ascii=False),
                    fw, node.status, node.status_reason, build_time.replace(tzinfo=None),
                ],
            )
        for event in result["overtaken"]:
            side.execute(
                """INSERT INTO history_overtaken
                   (event_day, leader_i, leader_next, granularity, status, status_reason, computed_at)
                   VALUES (?, ?, ?, ?, 'ok', NULL, ?)""",
                [event["event_day"], event["previous_top"], event["overtaken_by"], event["event_granularity"], build_time.replace(tzinfo=None)],
            )
        canonical = canonical_rows_hash(side, table="history_leader_succession", primary_key=("break_day", "node_id"))
        receipt = make_receipt(
            build_kind="leader_succession", framework_version=fw, label_version=LABEL_VERSION,
            source_db=str(source_path), source_max_trade_date=max(dates) if dates else None,
            source_row_counts=source_counts, parameter_hash=parameter_hash(params), canonical_hash=canonical,
            coverage_summary={"calendar_days": len(dates), "limit_days": len(limit_days), "covered_days": len(covered_dates), "overtaken_events": len(result["overtaken"])},
            gap_summary=readouts["sample"]["nodes_unverifiable_by_reason"] | {"open": readouts["sample"]["nodes_open"]},
            readouts=readouts, computed_at=build_time,
        )
        write_receipt(side, receipt)
    finally:
        side.close()
    print(json.dumps({
        "build_kind": "leader_succession", "framework_version": fw,
        "nodes": len(nodes), "overtaken": len(result["overtaken"]),
        "canonical_hash": canonical, "readouts": readouts,
    }, ensure_ascii=False, indent=2, default=str))
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    side = open_labels_db(Path(args.labels_db).expanduser(), read_only=True)
    try:
        counts = {
            "teaching_labels": side.execute("SELECT COUNT(*) FROM history_teaching_labels").fetchone()[0],
            "teaching_gaps": dict(side.execute("SELECT gap_kind, COUNT(*) FROM history_teaching_gaps GROUP BY gap_kind ORDER BY gap_kind").fetchall()),
            "succession_nodes": side.execute("SELECT COUNT(*) FROM history_leader_succession").fetchone()[0],
            "succession_status": dict(side.execute("SELECT status, COUNT(*) FROM history_leader_succession GROUP BY status").fetchall()),
            "overtaken": side.execute("SELECT COUNT(*) FROM history_overtaken").fetchone()[0],
            "sector_label_rows": side.execute("SELECT COUNT(*) FROM history_teaching_labels WHERE entity_type = 'sector'").fetchone()[0],
            "reference_stages": side.execute("SELECT COUNT(*) FROM history_reference_stages").fetchone()[0],
        }
        receipt_rows = side.execute(
            """SELECT build_id, build_kind, framework_version, label_version, parameter_hash,
                      canonical_hash, coverage_summary, gap_summary, readouts, status, status_reason, computed_at
               FROM history_teaching_receipts ORDER BY computed_at, build_id"""
        ).fetchall()
    finally:
        side.close()
    receipts = []
    for row in receipt_rows:
        item = dict(zip(
            ("build_id", "build_kind", "framework_version", "label_version", "parameter_hash",
             "canonical_hash", "coverage_summary", "gap_summary", "readouts", "status", "status_reason", "computed_at"),
            row, strict=True,
        ))
        for key in ("coverage_summary", "gap_summary", "readouts"):
            item[key] = json.loads(item[key]) if item[key] else {}
        receipts.append(item)
    latest_ok = {}
    for item in receipts:
        if item["status"] == "ok":
            latest_ok[item["build_kind"]] = item
    result = {
        "counts": counts,
        "receipts": [{k: v for k, v in item.items() if k != "readouts"} for item in receipts],
        "latest_ok_readouts": {kind: item["readouts"] for kind, item in latest_ok.items()},
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Teaching framework slice 1")
    sub = ap.add_subparsers(dest="command", required=True)
    for name, func in (("build-labels", cmd_build_labels), ("build-succession", cmd_build_succession), ("build-sector-roles", cmd_build_sector_roles)):
        p = sub.add_parser(name)
        p.add_argument("--db-path", default="db/market_feature_store.duckdb")
        p.add_argument("--labels-db", default=None)
        p.add_argument("--params", default=None)
        p.add_argument("--computed-at", default=None)
        p.set_defaults(func=func)
    p = sub.add_parser("report")
    p.add_argument("--labels-db", default=None)
    p.set_defaults(func=cmd_report)
    p = sub.add_parser("load-reference", help="载入复盘会 reviews/overview 快照（scripts/fupanhui_review_overview_pull.py 的输出）作参照标注")
    p.add_argument("--json", required=True)
    p.add_argument("--labels-db", default=None)
    p.add_argument("--db-path", default="db/market_feature_store.duckdb")
    p.add_argument("--computed-at", default=None)
    p.set_defaults(func=cmd_load_reference)
    p = sub.add_parser("calibrate-stages", help="从旁路库的参照标注与视角标签算出各段共性区间与转移图，写成新参数文件")
    p.add_argument("--labels-db", default=None)
    p.add_argument("--db-path", default="db/market_feature_store.duckdb")
    p.add_argument("--params", default=None, help="输入参数文件（沿用其余键）")
    p.add_argument("--params-out", required=True)
    p.add_argument("--train-until", required=True, help="只用 ≤ 此日期的参照日（YYYY-MM-DD）；之后的日子留给验证")
    p.add_argument("--quantiles", nargs=2, default=("0.25", "0.75"))
    p.add_argument("--min-days", default=8, help="某段某视角样本少于此数不出区间")
    p.add_argument("--version-base", default="tf-v0.2")
    p.set_defaults(func=cmd_calibrate_stages)
    return ap


def main(argv: list[str] | None = None) -> int:
    ap = parser()
    args = ap.parse_args(argv)
    if getattr(args, "labels_db", None) is None:
        args.labels_db = str(default_labels_db_path(getattr(args, "db_path", None)))
    try:
        return int(args.func(args) or 0)
    except (duckdb.Error, FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
