"""一个小而全的授课框架旁路库夹具，供河对象 / 带读读数 / 卡片三组测试共用。

日历：2026-01-09 是波 0 的见顶日，01-12 起覆灭（→ 01-20），波 1 从 01-21 起、02-05 见顶、02-06 起覆灭（open）。
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

from intelligence.services.methodology_backtest.store import open_labels_db

BUILT_AT = datetime(2026, 9, 7, 15, 0, 0)
FW = "tf-v0.2+test"
STOCK_NAMES = ("甲甲股份", "乙乙科技", "丙丙电子", "己己新材", "庚庚生物", "子子精密", "丑丑通信", "寅寅汽车")


def _label(day: str, label: str, num=None, text=None):
    return ("market", "market", date.fromisoformat(day), label, num, text, "v-test", FW, "ok", None, BUILT_AT)


def build_sidecar(path: Path) -> Path:
    con = open_labels_db(path, read_only=False)
    evidence = {"scores": {"左底向下": 3}, "hits": [{"stage": "左底向下", "predicate": "E:first_cross_below"}],
                "confidence": {"stage": "左底向下", "hits": 3, "possible": 6, "missing": ["H:in_band:x"], "margin": 1},
                "from": "高位震荡", "entered": ["左底向下"], "eligible": ["左底向下", "高位震荡"], "resolution": "entry", "tied": []}
    rows = [
        _label("2026-01-12", "tf.stage_coarse", text="左底向下"), _label("2026-01-12", "tf.stage_fine", text="左底向下"),
        _label("2026-01-12", "tf.stage_evidence", text=json.dumps(evidence, ensure_ascii=False)),
        _label("2026-01-12", "tf.volume_band", text="shrink"), _label("2026-01-12", "tf.deviation_band", text="below"),
        _label("2026-01-12", "tf.above_week_ma", num=0), _label("2026-01-12", "tf.cross_below_kind", text="first"),
        _label("2026-01-12", "tf.below_ma_cycle_day", num=1), _label("2026-01-12", "tf.money_losing_day", num=1),
        _label("2026-01-12", "tf.money_losing_streak", num=2), _label("2026-01-12", "tf.limit_premium_ma5_pct", num=0.8),
        _label("2026-01-12", "tf.amount_vs_ma20_pct", num=84.0), _label("2026-01-12", "tf.turn_down", num=1),
        _label("2026-01-12", "tf.stock_price_mean", num=21.0),  # 切片不读的标签，不该漏进 payload
        # 资金面（第十五段）：龙虎榜 / 封单 / 竞价 / 成交占比 的市场级读数。
        _label("2026-01-12", "tf.dragon_net_amount", num=12.3), _label("2026-01-12", "tf.dragon_net_amount_ratio_pm", num=0.71),
        _label("2026-01-12", "tf.dragon_net_amount_ratio_pm_ma5", num=0.55), _label("2026-01-12", "tf.dragon_buy_sell_ratio", num=1.9),
        _label("2026-01-12", "tf.dragon_buy_sell_ratio_ma5", num=1.7), _label("2026-01-12", "tf.limit_seal_mv_ratio_median", num=96.4),
        _label("2026-01-12", "tf.limit_thick_seal_share_pct", num=48.0), _label("2026-01-12", "tf.auction_zt_pct_median", num=3.25),
        _label("2026-01-12", "tf.auction_zt_positive_share_pct", num=80.0), _label("2026-01-12", "tf.top100_amount_share", num=0.187),
        # 消息面（第十六段）：隔夜卖方事件的市场级读数。
        _label("2026-01-12", "tf.narrative_events", num=61.0), _label("2026-01-12", "tf.narrative_events_ratio_ma20_pct", num=118.0),
        _label("2026-01-12", "tf.narrative_concepts", num=34.0), _label("2026-01-12", "tf.narrative_new_concepts", num=3.0),
        _label("2026-01-12", "tf.narrative_hard_share_pct", num=14.0), _label("2026-01-12", "tf.narrative_top3_share_pct", num=27.0),
        _label("2026-01-12", "tf.narrative_cover_rps5_pct", num=40.0),
        _label("2026-01-13", "tf.money_losing_day", num=0), _label("2026-01-14", "tf.money_losing_day", num=1),
        _label("2026-02-06", "tf.money_losing_day", num=1),
    ]
    # 指数序列（给卡片）：01-05 → 01-14，收盘 3400 → 3300 缓跌，偏离度由 +1 到 −2，阶段前半高位震荡后半左底向下。
    for i, day in enumerate(("2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08", "2026-01-09", "2026-01-12", "2026-01-13", "2026-01-14")):
        rows += [_label(day, "src.sh_index_close", num=3400.0 - 12.5 * i), _label(day, "src.sh_deviation_pct", num=1.0 - 0.4 * i)]
        if day != "2026-01-12":  # 01-12 的这两条已经在上面
            rows += [_label(day, "tf.above_week_ma", num=1 if i < 5 else 0), _label(day, "tf.stage_coarse", text="高位震荡" if i < 5 else "左底向下")]
    con.executemany("INSERT INTO history_teaching_labels VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
    # 02-06 没有叙事读数：源断更的缺口行（河对象把原因挂到阶段对象上，带读要说清）。
    con.execute("INSERT INTO history_teaching_gaps (trade_date, gap_kind, missing_cols, framework_version, status, status_reason, computed_at) VALUES (?, 'tf.narrative_events', NULL, ?, 'gap', 'narrative_stale', ?)",
                [date(2026, 2, 6), FW, BUILT_AT])
    con.executemany("INSERT INTO history_teaching_labels VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", [_label("2026-02-06", "tf.stage_coarse", text="左底向下")])
    con.executemany(
        """INSERT INTO history_dynasties (wave_idx, rank, wave_start, peak_end, collapse_start, collapse_end, wave_status, stock_ts_code,
           stock_name, wave_gain_pct, sw_l1, max_boards, form, collapse_ret_pct, collapse_max_dd_pct, framework_version, computed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (0, 1, date(2025, 12, 12), date(2026, 1, 9), date(2026, 1, 12), date(2026, 1, 20), "ok", "600001.SH", "甲甲股份", 180.0, "电子", 5, "连板", -40.0, -45.0, FW, BUILT_AT),
            (0, 2, date(2025, 12, 12), date(2026, 1, 9), date(2026, 1, 12), date(2026, 1, 20), "ok", "600002.SH", "乙乙科技", 120.0, "通信", None, "趋势", -35.0, -40.0, FW, BUILT_AT),
            (0, 3, date(2025, 12, 12), date(2026, 1, 9), date(2026, 1, 12), date(2026, 1, 20), "ok", "600003.SH", "丙丙电子", 90.0, "电子", None, "趋势", -20.0, -30.0, FW, BUILT_AT),
            (1, 1, date(2026, 1, 21), date(2026, 2, 5), date(2026, 2, 6), None, "open", "300006.SZ", "己己新材", 150.0, "电子", None, "趋势", None, None, FW, BUILT_AT),
            (1, 2, date(2026, 1, 21), date(2026, 2, 5), date(2026, 2, 6), None, "open", "300007.SZ", "庚庚生物", 140.0, "医药生物", 4, "连板", None, None, FW, BUILT_AT),
        ],
    )
    con.executemany(
        """INSERT INTO history_dynasty_handoffs (old_wave_idx, new_wave_idx, new_rank, stock_ts_code, stock_name, new_wave_gain_pct, sw_l1, form,
           old_wave_rank, in_old_cohort, l1_in_old_top, collapse_ret_pct, collapse_ret_percentile, collapse_max_dd_pct, first_leg_ret_pct,
           new_high_in_collapse, separation_relative, separation_new_high, losing_days_ret_pct, losing_days_ret_percentile, separation_on_losing_days,
           other_days_ret_pct, other_days_ret_percentile, separation_on_other_days, framework_version, computed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (0, 1, 1, "300006.SZ", "己己新材", 150.0, "电子", "趋势", 6, False, True, 12.0, 90.0, -3.0, 1.0, True, True, True, -4.0, 50.0, False, 16.7, 95.0, True, FW, BUILT_AT),
            (0, 1, 2, "300007.SZ", "庚庚生物", 140.0, "医药生物", "连板", 7, False, False, 6.0, 80.0, -6.0, -2.0, True, False, True, 1.0, 90.0, True, 5.0, 60.0, False, FW, BUILT_AT),
        ],
    )
    con.executemany(
        """INSERT INTO history_range_leaders (window_days, trade_date, rank, stock_ts_code, stock_name, gain_pct, sw_l1, limit_times, tenure_day,
           prev_rank, framework_version, computed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [(20, date(2026, 1, 12), 1, "000011.SZ", "子子精密", 45.0, "电子", 3, 2, 1, FW, BUILT_AT), (20, date(2026, 1, 12), 2, "000012.SZ", "丑丑通信", 40.0, "通信", None, 1, 12, FW, BUILT_AT),
         (60, date(2026, 1, 12), 1, "000013.SZ", "寅寅汽车", 120.0, "汽车", None, 9, 1, FW, BUILT_AT)],
    )
    con.close()
    return path
