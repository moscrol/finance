from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import duckdb
import pytest

from intelligence.services.teaching_framework.params import load_params
from scripts.teaching_framework import main, parser

DAYS = ["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08", "2026-01-09",
        "2026-01-12", "2026-01-13", "2026-01-14", "2026-01-15", "2026-01-16"]

# (day, stock, boards).  A leads then breaks on day 3 into a low-board handoff
# (B 1-2-3, gap 1); B breaks on day 6 into a tie; D breaks on day 8 into a
# high-board successor (F already at 3); F breaks on day 9 into a low-board
# successor (G 2-3, gap 0); G breaks on day 10 with no successor (open).
LIMIT_ROWS = [
    (DAYS[0], "A", 3),
    (DAYS[1], "A", 4), (DAYS[1], "B", 1),
    (DAYS[2], "B", 2), (DAYS[2], "C", 1),
    (DAYS[3], "B", 3),
    (DAYS[4], "B", 4), (DAYS[4], "D", 2), (DAYS[4], "E", 2),
    (DAYS[5], "D", 3), (DAYS[5], "E", 3), (DAYS[5], "F", 2),
    (DAYS[6], "D", 4), (DAYS[6], "F", 3),
    (DAYS[7], "F", 4), (DAYS[7], "G", 2),
    (DAYS[8], "G", 3),
    (DAYS[9], "H", 1),
]


def _market_row(i: int, day: str) -> tuple:
    close, open_, dev, surge = 101.0, 100.5, 1.0, 3.0
    top3 = 0.3
    if i == 0 or i == 3 or i == 8:
        dev = 2.0  # overheated -> 高位震荡 by argmax
    if i == 2:
        top3 = None  # gap day
    if i == 5:
        close, open_, dev = 99.0, 98.0, -1.0  # gap-down break below the MA
    # total_amount against amount_ma20 = 90: 100 → 量能比 111% (温和放量) on ordinary days,
    # 125 → 139% (暴量) as the breakout volume on day 7 and the in-trend surge on day 10
    # (a two-sided factor, scores for no stage).
    amount = 125.0 if i in (6, 9) else 100.0
    if i == 6 or i == 9:
        surge = 25.0
    limit_up = sum(1 for d, _, _ in LIMIT_ROWS if d == day)
    stage = "主升阶段" if i % 2 == 0 else "震荡阶段"
    high, low = close + 1.0, open_ - 1.0
    return (day, close, open_, high, low, 100.0, dev, amount, 90.0, surge, top3, stage, "放量", None, "vendor", limit_up, 2500,
            "电子", "机械设备", "电力设备")


@pytest.fixture
def source_db(tmp_path: Path) -> Path:
    path = tmp_path / "source.duckdb"
    con = duckdb.connect(str(path))
    con.execute(
        """CREATE TABLE fact_market_daily (
            trade_date DATE, sh_index_close DOUBLE, sh_index_open DOUBLE, sh_index_high DOUBLE, sh_index_low DOUBLE,
            sh_week_ma DOUBLE, sh_deviation_pct DOUBLE, total_amount DOUBLE, amount_ma20 DOUBLE, amount_vs_yesterday_pct DOUBLE,
            top3_industry_ratio DOUBLE, market_stage VARCHAR, volume_state VARCHAR, ice_point VARCHAR,
            sh_week_ma_source VARCHAR, limit_up INTEGER, advancers INTEGER,
            industry_1 VARCHAR, industry_2 VARCHAR, industry_3 VARCHAR)"""
    )
    con.executemany("INSERT INTO fact_market_daily VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", [_market_row(i, d) for i, d in enumerate(DAYS)])
    con.execute("CREATE TABLE fact_mainline_sector_daily (trade_date DATE, sector_ts_code VARCHAR, amount DOUBLE)")
    con.executemany("INSERT INTO fact_mainline_sector_daily VALUES (?, ?, ?)", [(d, "S1", 10.0) for d in DAYS])
    con.execute(
        """CREATE TABLE fact_theme_limit_stock_daily (
            trade_date DATE, stock_ts_code VARCHAR, stock_name VARCHAR, limit_times INTEGER, open_times INTEGER,
            first_limit_time VARCHAR, up_stat VARCHAR, circ_mv DOUBLE, amount DOUBLE, limit_status VARCHAR)"""
    )
    con.executemany(
        "INSERT INTO fact_theme_limit_stock_daily VALUES (?, ?, ?, ?, NULL, '093000', NULL, 1000.0, 50.0, 'U')",
        [(d, s, s, b) for d, s, b in LIMIT_ROWS],
    )
    con.execute("CREATE TABLE fact_stock_daily (trade_date DATE, stock_ts_code VARCHAR, close DOUBLE, pct_chg DOUBLE, amount DOUBLE)")
    con.executemany(
        "INSERT INTO fact_stock_daily VALUES (?, ?, ?, ?, ?)",
        [(d, s, 10.0 * (k + 1) + i, 1.0 * (k - 1), a) for i, d in enumerate(DAYS) for k, (s, a) in enumerate((("X", 30.0), ("Y", 20.0), ("Z", 10.0)))],
    )
    # Sector side (第二刀): two sectors a day, one strict 双红 on even days; 3 limit-ups in S1; new highs = day index + 1
    # stocks at 1y-or-longer periods, except day 4 which has no high rows at all.
    con.execute("CREATE TABLE fact_sector_daily (trade_date DATE, sector_ts_code VARCHAR, sector_name VARCHAR, sw_l1 VARCHAR, pct_chg DOUBLE, diff_ratio DOUBLE, amount DOUBLE)")
    con.executemany(
        "INSERT INTO fact_sector_daily VALUES (?, ?, ?, ?, ?, ?, ?)",
        [row for i, d in enumerate(DAYS) for row in ((d, "S1", "甲", "电子", 1.0 if i % 2 == 0 else -0.5, 12.0, 600.0), (d, "S2", "乙", "通信", 0.5, 5.0, 300.0))],
    )
    con.execute("CREATE TABLE fact_theme_limit_heat_daily (trade_date DATE, sector_ts_code VARCHAR, data_stage VARCHAR, limit_up_count INTEGER, market_share DOUBLE, fd_amount DOUBLE)")
    con.executemany(
        "INSERT INTO fact_theme_limit_heat_daily VALUES (?, ?, 'final', ?, ?, ?)",
        [row for d in DAYS for row in ((d, "S1", 3, 60.0, 9000.0), (d, "S2", 1, 20.0, 1000.0))],
    )
    con.execute("CREATE TABLE fact_stock_high_daily (trade_date DATE, stock_ts_code VARCHAR, primary_high_period VARCHAR)")
    con.executemany(
        "INSERT INTO fact_stock_high_daily VALUES (?, ?, ?)",
        [(d, f"H{n}", "1y" if n % 2 else "20d") for i, d in enumerate(DAYS) if i != 3 for n in range(2 * (i + 1))],
    )
    con.close()
    return path


# Synthetic common ranges on 量能比 (ordinary days 111%, 暴量 days 139%) and 周均线偏离度, so stages are hand-derivable.
CLI_BANDS = {
    "stage_bands": {
        "左底向下": {"amount_vs_ma20_pct": [105, 115], "src.sh_deviation_pct": [-2.0, -0.5]},
        "共建主线": {"amount_vs_ma20_pct": [105, 115], "src.sh_deviation_pct": [0.5, 1.4]},
        "主流主升": {"amount_vs_ma20_pct": [130, 145]},
        "高位震荡": {"amount_vs_ma20_pct": [105, 115], "src.sh_deviation_pct": [0.5, 3.0]},
    },
    "transition_graph": {
        "左底向下": ["左底向上", "二次探底"], "左底向上": ["二次探底"], "二次探底": ["缩量右底", "共建主线"], "缩量右底": ["共建主线"],
        "共建主线": ["主流主升", "左底向下"], "主流主升": ["高位震荡"], "主流主升2.0": ["高位震荡", "左底向下"], "高位震荡": ["主流主升2.0", "左底向下"],
    },
    "stage_bands_derived_from": {"train_until": "2025-10-31", "source": "test fixture"},
}


@pytest.fixture
def params_file(tmp_path: Path) -> Path:
    params = load_params()
    params["top100_n"] = 2
    params["breadth_min_stocks"] = 3
    params["breakout_confirm_days"] = 1  # the fixture's day-10 surge is three days after the cross: keep it in-trend
    params.update(CLI_BANDS)
    path = tmp_path / "params.json"
    path.write_text(json.dumps(params, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _run(capsys, *argv: str) -> dict:
    assert main(list(argv)) == 0, capsys.readouterr().err
    return json.loads(capsys.readouterr().out)


def _build(capsys, source_db: Path, sidecar: Path, params_file: Path, computed_at: str) -> tuple[dict, dict]:
    common = ["--db-path", str(source_db), "--labels-db", str(sidecar), "--params", str(params_file), "--computed-at", computed_at]
    labels = _run(capsys, "build-labels", *common)
    succession = _run(capsys, "build-succession", *common)
    return labels, succession


def test_cli_exposes_slice_one_commands() -> None:
    for command in ("build-labels", "build-succession", "report"):
        args = parser().parse_args([command])
        assert args.command == command
        assert callable(args.func)


def test_end_to_end_build_is_deterministic_and_receipts_carry_readouts(capsys, tmp_path, source_db, params_file) -> None:
    sidecar = tmp_path / "labels.duckdb"
    labels, succession = _build(capsys, source_db, sidecar, params_file, "2026-09-07T00:00:00Z")

    assert labels["gap_rows"] >= 1
    readouts = labels["readouts"]
    assert readouts["days_total"] == 10 and readouts["days_gap"] == 1
    # Hand-derived under CLI_BANDS with the transition constraint: 高位震荡 on the overheated days 1, 4, 9 and,
    # by persistence (共建主线 is not reachable from 高位震荡 without a breakout), on days 2, 5 and 10; 左底向下 on the
    # gap-down day 6 (first cross below); 共建主线 on day 7 (breakout entry, resolution ``entry``) and day 8.
    assert readouts["stage_coarse_distribution"] == {"共建主线": 2, "左底向下": 1, "高位震荡": 6}
    assert readouts["resolution_distribution"] == {"argmax": 7, "entry": 2}  # day 7 breakout, day 9 overheated
    assert readouts["turn_counts"] == {"tf.turn_up": 1, "tf.turn_top": 1, "tf.turn_down": 1}
    assert readouts["supplier_contingency"] and readouts["supplier_disagree_days"] == 9
    assert readouts["founder_unconfirmed_predicate_days"] == {}
    assert readouts["stage_predicate_catalog"]["高位震荡"] == ["E:overheated", "H:in_band:amount_vs_ma20_pct", "H:in_band:src.sh_deviation_pct"]

    side = duckdb.connect(str(sidecar), read_only=True)
    try:
        labels_present = {r[0] for r in side.execute("SELECT DISTINCT label FROM history_teaching_labels").fetchall()}
        assert "src.market_stage" in labels_present and "tf.stage_coarse" in labels_present
        assert not {name for name in labels_present if name.startswith("tf.") and name.removeprefix("tf.") in {"market_stage", "volume_state", "limit_up", "advancers", "total_amount", "ice_point", "sh_week_ma_source"}}
        assert side.execute("SELECT COUNT(*) FROM history_teaching_labels WHERE trade_date = DATE '2026-01-07'").fetchone()[0] == 0
        gaps = dict(side.execute("SELECT gap_kind, COUNT(*) FROM history_teaching_gaps GROUP BY gap_kind").fetchall())
        assert gaps["market_input"] == 1
        share = side.execute("SELECT MIN(value_num), MAX(value_num) FROM history_teaching_labels WHERE label='tf.top100_amount_share'").fetchone()
        assert share == (0.4, 0.5)  # top-2 amount 50 over market turnover 100 (ordinary days) or 125 (the two 暴量 days)
        # 水位 scalars: median pct_chg of (-1, 0, 1) is 0; price mean is 20 + day index; MA5 deviation needs 5 consecutive days.
        assert side.execute("SELECT DISTINCT value_num FROM history_teaching_labels WHERE label='tf.stock_pct_chg_median'").fetchall() == [(0.0,)]
        assert side.execute("SELECT value_num FROM history_teaching_labels WHERE label='tf.stock_price_mean' AND trade_date=DATE '2026-01-06'").fetchone() == (21.0,)
        ma5 = dict(side.execute("SELECT trade_date, value_num FROM history_teaching_labels WHERE label='tf.stock_ma5_deviation_median' ORDER BY trade_date").fetchall())
        assert ma5[date(2026, 1, 6)] is None and ma5[date(2026, 1, 9)] is not None
        assert gaps["tf.stock_ma5_deviation_median"] == 3  # days 1, 2, 4 (day 3 is a market gap) lack a 5-day window
        assert "tf.volume_band" in labels_present and "src.amount_vs_yesterday_pct" in labels_present
        assert readouts["volume_band_by_stage"]
        # 高位震荡 views (创始人 09-07 第四段): 5-day gain / amplitude / deviation change on 01-12
        # are measured against the 01-05 close (101); the 10-day window never completes in 10 rows.
        gain, amplitude, dev_change = side.execute(
            """SELECT MAX(CASE WHEN label='tf.sh_index_pct_chg_5d' THEN value_num END),
                      MAX(CASE WHEN label='tf.sh_index_amplitude_5d' THEN value_num END),
                      MAX(CASE WHEN label='tf.sh_deviation_change_5d' THEN value_num END)
               FROM history_teaching_labels WHERE trade_date = DATE '2026-01-12'"""
        ).fetchone()
        assert (gain, amplitude, dev_change) == (round((99 / 101 - 1) * 100, 6), round((102 - 97) / 101 * 100, 6), -3.0)
        assert gaps["tf.sh_index_pct_chg_5d"] == 4 and gaps["tf.sh_index_amplitude_10d"] == 9
        assert readouts["view_scalars_by_stage"]["tf.sh_index_pct_chg_5d"]["高位震荡"]["n"] >= 1
        assert set(readouts["view_scalars_by_stage"]) >= {"tf.stock_pct_chg_median", "tf.sh_index_amplitude_5d", "tf.sh_deviation_change_5d"}
        assert "tf.sh_deviation_change_10d" not in readouts["view_scalars_by_stage"]  # no completed window, no distribution
        # 周均线上下方 × 量能: 9 usable days, one of them (01-12) below the MA; every day is a moderate 环比 except two surges.
        by_side = readouts["volume_by_ma_side"]
        assert by_side["above"]["days"] == 8 and by_side["below"]["days"] == 1
        assert by_side["above"]["band_moderate"] == 6 and by_side["above"]["band_surge"] == 2 and by_side["below"]["band_moderate"] == 1
        assert "amount_below_ma20" not in by_side["above"]  # total_amount 100 vs amount_ma20 90: never a shrink day
        # Day 10's surge is three days after the cross (window 1): a trend surge, written as a view, scored for nobody.
        trend = dict(side.execute("SELECT trade_date, value_num FROM history_teaching_labels WHERE label='tf.surge_in_trend'").fetchall())
        assert trend[date(2026, 1, 16)] == 1 and trend[date(2026, 1, 14)] == 0
        assert readouts["views_by_event"]["surge_in_trend"]["days"] == 1
        # Day 7 (cross with volume, coming from 左底向下) is the breakout entry; on day 8 the origin is already 共建主线,
        # so the still-open window no longer counts as an entry.
        assert readouts["views_by_event"]["breakout_confirmed"]["days"] == 1
        assert "src.sh_index_close" in labels_present
        assert readouts["reference_comparison"] is None  # no platform reference loaded in this fixture
        # Sector side (第二刀): day-indexed 1y+ new highs (day 4 has no high rows → NULL + gap), 双红 only on even days,
        # one theme with ≥ 3 limit-ups every day.
        nh = dict(side.execute("SELECT trade_date, value_num FROM history_teaching_labels WHERE label='tf.new_high_1y_count'").fetchall())
        assert nh[date(2026, 1, 6)] == 2 and nh[date(2026, 1, 8)] is None and nh[date(2026, 1, 16)] == 10
        assert gaps["tf.new_high_1y_count"] == 1
        dual = dict(side.execute("SELECT trade_date, value_num FROM history_teaching_labels WHERE label='tf.dual_red_theme_count'").fetchall())
        assert dual[date(2026, 1, 5)] == 1 and dual[date(2026, 1, 6)] == 0
        assert side.execute("SELECT DISTINCT value_num FROM history_teaching_labels WHERE label='tf.limit_themes_ge3'").fetchall() == [(1.0,)]
        assert "tf.new_high_1y_count" in readouts["view_scalars_by_stage"]
        # 5-day gainers S1 (电子, in the top three) and S2 (通信, outside): half of the set sits outside the top-three
        # industries once five contiguous days exist (from 01-09 on); days 1, 2 and 4 lack a window (day 3 is a market gap).
        outside = dict(side.execute("SELECT trade_date, value_num FROM history_teaching_labels WHERE label='tf.rps5_outside_top3_pct'").fetchall())
        assert outside[date(2026, 1, 9)] == 50.0 and outside[date(2026, 1, 12)] == 50.0 and outside[date(2026, 1, 6)] is None
        assert gaps["tf.rps5_outside_top3_pct"] == 3
        # Ties are leader groups (创始人 09-07): B's break on day 6 hands off to the tied group {D, E}
        # (both came out of the 2-board candidates), and E's lone break on day 7 is a partial break, not a node.
        statuses = dict(side.execute("SELECT status, COUNT(*) FROM history_leader_succession GROUP BY status").fetchall())
        assert statuses == {"ok": 4, "open": 1}
        handoffs = dict(side.execute("SELECT break_day, handoff FROM history_leader_succession WHERE status='ok'").fetchall())
        assert {str(k): v for k, v in handoffs.items()} == {DAYS[2]: True, DAYS[5]: True, DAYS[7]: False, DAYS[8]: True}
        tied = side.execute(
            "SELECT leader_next, leader_next_group_json, forward FROM history_leader_succession WHERE break_day = DATE '2026-01-12'"
        ).fetchone()
        assert tied[0] == "D|E" and json.loads(tied[1]) == ["D", "E"] and json.loads(tied[2])["handoff_members"] == ["D", "E"]
        receipts = side.execute("SELECT build_kind, readouts, status FROM history_teaching_receipts ORDER BY build_kind").fetchall()
        assert [r[0] for r in receipts] == ["leader_succession", "teaching_labels"] and all(r[2] == "ok" for r in receipts)
        persisted = json.loads(receipts[0][1])
        assert persisted["handoff_readout"]["n"] == 4 and persisted["handoff_readout"]["k"] == 3
        assert persisted["handoff_readout"]["verdict"] == "insufficient_n"
        # Baseline days 2, 5 and 7: prior leader still sealed, successor realized; day 7's prior is the tied group.
        assert persisted["sample"]["baseline_n"] == 3 and persisted["sample"]["baseline_k"] == 3
        assert persisted["diagnostics"]["event_handoff_by_birth_boards"] == {"3": {"n": 3, "k": 3}, "4": {"n": 1, "k": 0}}
        assert persisted["diagnostics"]["event_handoff_by_leader_next_size"] == {"1": {"n": 3, "k": 2}, "2": {"n": 1, "k": 1}}
        assert persisted["diagnostics"]["top_tie_size_days"] == {"1": 7, "2": 1}
        assert persisted["diagnostics"]["partial_break_days"] == 1 and persisted["diagnostics"]["partial_breaks"][0]["still_sealed"] == ["D"]
        assert persisted["birth_environment"]["birth_days_unique"] == 4
        assert persisted["birth_environment"]["features"]["tf.stage_coarse"]["cohort_size"] == 4
        assert {b["stage"] for b in persisted["handoff_by_break_stage"]} >= {"gap"}  # break on the gap day has no stage
    finally:
        side.close()

    # Spec §8.1: a fresh rebuild with a different build time hashes identically.
    other = tmp_path / "labels-again.duckdb"
    labels2, succession2 = _build(capsys, source_db, other, params_file, "2027-03-03T12:34:56Z")
    assert labels2["canonical_hash"] == labels["canonical_hash"]
    assert succession2["canonical_hash"] == succession["canonical_hash"]

    report = _run(capsys, "report", "--labels-db", str(sidecar))
    assert set(report["latest_ok_readouts"]) == {"teaching_labels", "leader_succession"}
    assert report["counts"]["succession_status"] == {"ok": 4, "open": 1}


def test_parameter_change_marks_old_receipts_incomparable(capsys, tmp_path, source_db, params_file) -> None:
    sidecar = tmp_path / "labels.duckdb"
    first, _ = _build(capsys, source_db, sidecar, params_file, "2026-09-07T00:00:00Z")
    params = json.loads(params_file.read_text(encoding="utf-8"))
    params["volume_level"]["surge_from_pct"] = 110
    changed = tmp_path / "params-changed.json"
    changed.write_text(json.dumps(params), encoding="utf-8")
    second = _run(capsys, "build-labels", "--db-path", str(source_db), "--labels-db", str(sidecar), "--params", str(changed), "--computed-at", "2026-09-08T00:00:00Z")
    assert second["framework_version"] != first["framework_version"]
    side = duckdb.connect(str(sidecar), read_only=True)
    try:
        rows = side.execute("SELECT framework_version, status FROM history_teaching_receipts WHERE build_kind='teaching_labels' ORDER BY computed_at").fetchall()
    finally:
        side.close()
    assert rows[0] == (first["framework_version"], "incomparable")
    assert rows[1] == (second["framework_version"], "ok")


def _reference_item(day: str, stage: str, external: str, vs_ma20: float) -> dict:
    return {
        "trade_date": day, "weekday": "周一", "data_version": "tushare_final", "formula_version": "review_overview_v1",
        "updated_at": f"{day}T18:55:13+08:00", "cycle_stage": stage, "external_cycle": external, "internal_cycle": f"{stage}阶段",
        "is_ice_point": False, "ice_point_level": "正常",
        "breadth": {"up_rate_ma5_pct": 50.0, "up_count": 2500, "limit_up_count_non_st": 60},
        "liquidity": {"market_amount_yi": 20000.0, "market_amount_change_pct": 1.0, "market_amount_ma20_yi": 20000.0, "market_amount_vs_ma20_pct": vs_ma20},
        "amount_top5": {"amount_yi": 8000.0, "market_share_pct": 40.0, "rising_amount_yi": 4000.0, "rising_amount_share_pct": 50.0, "rising_avg_change_pct": 3.0},
        "sw_industry": {"top3": [], "top3_market_share_pct": 38.0},
        "price_top5": {"amount_change_pct": 2.0, "avg_change_pct": 6.0, "market_share_pct": 9.0},
    }


def test_load_reference_and_compare_against_platform_stages(capsys, tmp_path, source_db, params_file) -> None:
    """创始人 09-07 第十段：平台标注「当参照」——载入后 build-labels 的收据带列联表、别名折算的一致率与按参照阶段的共性区间."""
    sidecar = tmp_path / "labels.duckdb"
    # Platform vocabulary on the fixture's ten days: 承接盘反复 (= 高位震荡) on the overheated days, 共建主线 after the cross.
    stages = ["承接盘反复", "承接盘反复", "承接盘反复", "承接盘反复", "承接盘反复", "左底向下", "共建主线", "共建主线", "承接盘反复", "主流主升2.0"]
    payload = {"source": "fupanhui.com /api/v1/client/reviews/overview", "pulled_at": "2026-09-07T04:00:00Z", "available_since": "2021-09-13",
               "items": [_reference_item(d, s, "顶部横盘阶段" if s == "承接盘反复" else "底部横盘阶段", 100.0 + i) for i, (d, s) in enumerate(zip(DAYS, stages))]}
    ref_json = tmp_path / "reference.json"
    ref_json.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    loaded = _run(capsys, "load-reference", "--json", str(ref_json), "--labels-db", str(sidecar), "--db-path", str(source_db), "--computed-at", "2026-09-07T05:00:00Z")
    assert loaded["rows"] == 10 and loaded["first_day"] == DAYS[0] and loaded["last_day"] == DAYS[9]
    assert {row["cycle_stage"]: row["days"] for row in loaded["by_cycle_stage"]} == {"承接盘反复": 6, "共建主线": 2, "左底向下": 1, "主流主升2.0": 1}

    labels, _ = _build(capsys, source_db, sidecar, params_file, "2026-09-07T00:00:00Z")
    cmp = labels["readouts"]["reference_comparison"]
    assert cmp["overlap_days"] == 9  # the gap day 01-07 has no computed stage row
    assert cmp["reference_stage_days"] == {"承接盘反复": 5, "共建主线": 2, "左底向下": 1, "主流主升2.0": 1}
    # Ours: days 1, 2, 4, 5, 9 高位震荡 (agree with 承接盘反复), day 6 左底向下 (agree), days 7-8 共建主线 (agree),
    # day 10 高位震荡 by persistence where the platform says 主流主升2.0 (disagree) → 8 of 9 resolved days agree.
    assert cmp["agreement"] == {"days": 9, "resolved_days": 9, "agree_days": 8, "rate": round(8 / 9, 4), "unresolved_days": 0}
    assert cmp["train_until"] == "2025-10-31" and cmp["agreement_train"]["days"] == 0 and cmp["agreement_validate"]["days"] == 9
    assert cmp["contingency"]["承接盘反复 × 高位震荡"] == 5 and cmp["contingency"]["主流主升2.0 × 高位震荡"] == 1
    by_ref = cmp["views_by_reference_stage"]
    assert by_ref["承接盘反复"]["days"] == 5 and by_ref["承接盘反复"]["ma_side"] == {"above": 5}
    assert by_ref["左底向下"]["ma_side"] == {"below": 1} and by_ref["左底向下"]["volume_band"] == {"moderate": 1}
    assert by_ref["共建主线"]["views"]["tf.amount_vs_ma20_pct"]["n"] == 2
    # Reference rows are never a label input: the label hash is identical with and without them.
    other = tmp_path / "labels-no-ref.duckdb"
    labels_no_ref, _ = _build(capsys, source_db, other, params_file, "2026-09-07T00:00:00Z")
    assert labels_no_ref["canonical_hash"] == labels["canonical_hash"]
    report = _run(capsys, "report", "--labels-db", str(sidecar))
    assert report["counts"]["reference_stages"] == 10


def test_build_sector_roles_writes_sector_labels_and_rule_readout(capsys, tmp_path, source_db, params_file) -> None:
    """第二刀 C 类: sector labels ride in the same table under entity_type='sector'; market rows and their hash are untouched."""
    sidecar = tmp_path / "labels.duckdb"
    common = ["--db-path", str(source_db), "--labels-db", str(sidecar), "--params", str(params_file), "--computed-at", "2026-09-07T00:00:00Z"]
    labels = _run(capsys, "build-labels", *common)
    roles = _run(capsys, "build-sector-roles", *common)
    # Two sectors × 10 days × 12 labels.
    assert roles["rows"] == 2 * 10 * 12 and roles["readouts"]["days"] == {"ok": 10}
    side = duckdb.connect(str(sidecar), read_only=True)
    try:
        # 电子 is industry_1 on every fixture day (the 3-day rank needs three contiguous days: NULL on days 1-2).
        s1 = {r[0]: r[1] for r in side.execute("SELECT label, value_num FROM history_teaching_labels WHERE entity_type='sector' AND entity_id='S1' AND trade_date=DATE '2026-01-09'").fetchall()}
        assert s1["tf.role_volume_top3"] == 1 and s1["tf.limit_up_count"] == 3 and s1["tf.sharpness_limit_rank"] == 1
        assert s1["tf.rps_3d_rank"] in (1, 2) and s1["tf.money_effect.limit_top10"] == 1
        assert s1["tf.dual_red_strict"] == 1  # day index 4 is even: pct 1.0, diff 12, amount 600
        s2 = {r[0]: r[1] for r in side.execute("SELECT label, value_num FROM history_teaching_labels WHERE entity_type='sector' AND entity_id='S2' AND trade_date=DATE '2026-01-09'").fetchall()}
        assert s2["tf.role_volume_top3"] == 0 and s2["tf.role_price_top10"] == 1 and s2["tf.dual_red_strict"] == 0
        assert side.execute("SELECT value_num FROM history_teaching_labels WHERE entity_type='sector' AND entity_id='S1' AND trade_date=DATE '2026-01-05' AND label='tf.rps_3d_rank'").fetchone() == (None,)
        # Market rows survive the sector build and hash identically.
        assert side.execute("SELECT COUNT(*) FROM history_teaching_labels WHERE entity_type='market'").fetchone()[0] > 0
        kinds = [r[0] for r in side.execute("SELECT build_kind FROM history_teaching_receipts ORDER BY build_kind").fetchall()]
        assert kinds == ["sector_roles", "teaching_labels"]
    finally:
        side.close()
    labels_again = _run(capsys, "build-labels", *common)
    assert labels_again["canonical_hash"] == labels["canonical_hash"]
    rule = roles["readouts"]["money_effect_rule"]["by_definition"]
    assert set(rule) == {"limit_top10", "dual_red", "rps5_top10", "rank_mean_top10"}
    # Every fixture day has S1 (电子, the top-1 industry) in the limit_top10 set, so the outcome is never met; verdict stays insufficient_n at n < 10.
    assert rule["limit_top10"]["readout"]["verdict"] == "insufficient_n"
    assert rule["limit_top10"]["below_ma_days"] + rule["limit_top10"]["above_ma_days"] + sum(rule["limit_top10"]["excluded"].values()) == 10
    report = _run(capsys, "report", "--labels-db", str(sidecar))
    assert report["counts"]["sector_label_rows"] == 240


def test_stale_sidecar_schema_fails_closed(capsys, tmp_path, source_db, params_file) -> None:
    sidecar = tmp_path / "labels.duckdb"
    _build(capsys, source_db, sidecar, params_file, "2026-09-07T00:00:00Z")
    con = duckdb.connect(str(sidecar))
    con.execute("ALTER TABLE history_leader_succession DROP COLUMN forward")
    con.close()
    code = main(["build-succession", "--db-path", str(source_db), "--labels-db", str(sidecar), "--params", str(params_file)])
    assert code == 2
    assert "schema 过期" in capsys.readouterr().err
