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
            first_limit_time VARCHAR, up_stat VARCHAR, circ_mv DOUBLE, amount DOUBLE, limit_status VARCHAR, fd_amount DOUBLE)"""
    )
    # 封单金额 = 板数 × 3000 万，流通市值 1000 亿：封单占流通市值 = 30 × 板数，只有 ≥ 4 板的算「厚封单」（≥ 100）。
    con.executemany(
        "INSERT INTO fact_theme_limit_stock_daily VALUES (?, ?, ?, ?, NULL, '093000', NULL, 1000.0, 50.0, 'U', ?)",
        [(d, s, s, b, 3000.0 * b) for d, s, b in LIMIT_ROWS],
    )
    con.execute("CREATE TABLE fact_stock_daily (trade_date DATE, stock_ts_code VARCHAR, stock_name VARCHAR, close DOUBLE, pct_chg DOUBLE, amount DOUBLE, high DOUBLE)")
    con.executemany(
        "INSERT INTO fact_stock_daily VALUES (?, ?, ?, ?, ?, ?, ?)",
        [(d, s, s.lower(), 10.0 * (k + 1) + i, 1.0 * (k - 1), a, 10.0 * (k + 1) + i + 0.5) for i, d in enumerate(DAYS) for k, (s, a) in enumerate((("X", 30.0), ("Y", 20.0), ("Z", 10.0)))],
    )
    # 承接 rows for the limit-up stocks: +2 on a day they limit again, −3 otherwise; NULL close keeps them out of breadth.
    limit_days = {(d, s) for d, s, _ in LIMIT_ROWS}
    con.executemany(
        "INSERT INTO fact_stock_daily VALUES (?, ?, ?, NULL, ?, NULL, NULL)",
        [(d, s, s.lower(), 2.0 if (d, s) in limit_days else -3.0) for d in DAYS for s in "ABCDEFGH"],
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
    # Stock → own 申万 industry ("一级-二级"), one theme row per stock a day is enough for the range-leader chain.
    con.execute("CREATE TABLE fact_sector_stock_daily (trade_date DATE, sector_ts_code VARCHAR, stock_ts_code VARCHAR, sw_industry VARCHAR)")
    con.executemany(
        "INSERT INTO fact_sector_stock_daily VALUES (?, 'S1', ?, ?)",
        [(d, s, ind) for d in DAYS for s, ind in (("X", "电子-半导体"), ("Y", "通信-通信设备"), ("Z", None))],
    )
    # 资金面（第十五段）：龙虎榜两只、竞价面板一只；01-13 起才有龙虎榜，所以 5 日均在窗口凑不齐前是 NULL。
    con.execute("CREATE TABLE fact_dragon_tiger_daily (trade_date DATE, stock_ts_code VARCHAR, stock_name VARCHAR, net_amount DOUBLE, l_amount DOUBLE)")
    con.executemany(
        "INSERT INTO fact_dragon_tiger_daily VALUES (?, ?, ?, ?, ?)",
        [row for d in DAYS[6:] for row in ((d, "X", "x", 2.0, 5.0), (d, "Y", "y", -0.5, 3.0))],
    )
    con.execute("CREATE TABLE fact_auction_stock_daily (trade_date DATE, panel_key VARCHAR, stock_ts_code VARCHAR, auction_pct DOUBLE, auction_amount DOUBLE)")
    con.executemany("INSERT INTO fact_auction_stock_daily VALUES (?, 'zt', 'X', ?, 0.5)", [(d, 3.0 if i % 2 else -1.0) for i, d in enumerate(DAYS)])
    con.execute("CREATE TABLE fact_stock_high_daily (trade_date DATE, stock_ts_code VARCHAR, primary_high_period VARCHAR, sw_l1 VARCHAR)")
    con.executemany(
        "INSERT INTO fact_stock_high_daily VALUES (?, ?, ?, ?)",
        [(d, f"H{n}", "1y" if n % 2 else "20d", "通信" if n % 4 == 1 else "电子") for i, d in enumerate(DAYS) if i != 3 for n in range(2 * (i + 1))],
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
        # 题材层第二轮: 双红 (S1 on even days, 电子 only) spans one L1 or none; the limit-up top-10 is {S1, S2} every day → Jaccard 100.
        l1d = dict(side.execute("SELECT trade_date, value_num FROM history_teaching_labels WHERE label='tf.dual_red_l1_distinct'").fetchall())
        assert l1d[date(2026, 1, 5)] == 1 and l1d[date(2026, 1, 6)] is None
        persist = dict(side.execute("SELECT trade_date, value_num FROM history_teaching_labels WHERE label='tf.limit_top10_persist_5d_pct'").fetchall())
        assert persist[date(2026, 1, 12)] == 100.0 and persist[date(2026, 1, 9)] is None
        # 承接: yesterday's limit-up stocks gain +2 when they limit again and −3 otherwise (fixture rows with NULL close, so
        # breadth is untouched). 01-16: G alone broke → −3; the five-day window 01-12..16 = (1/3, 1/3, −1/2, −1/2, −3).
        prem = dict(side.execute("SELECT trade_date, value_num FROM history_teaching_labels WHERE label='tf.limit_premium_pct'").fetchall())
        assert prem[date(2026, 1, 5)] is None and prem[date(2026, 1, 6)] == 2.0 and prem[date(2026, 1, 16)] == -3.0
        ma5 = dict(side.execute("SELECT trade_date, value_num FROM history_teaching_labels WHERE label='tf.limit_premium_ma5_pct'").fetchall())
        assert ma5[date(2026, 1, 9)] is None and ma5[date(2026, 1, 16)] == round((1 / 3 + 1 / 3 - 0.5 - 0.5 - 3.0) / 5, 6)
        neg = dict(side.execute("SELECT trade_date, value_num FROM history_teaching_labels WHERE label='tf.limit_premium_neg_5d'").fetchall())
        flips = dict(side.execute("SELECT trade_date, value_num FROM history_teaching_labels WHERE label='tf.limit_premium_flips_5d'").fetchall())
        assert neg[date(2026, 1, 16)] == 3 and flips[date(2026, 1, 16)] == 1 and flips[date(2026, 1, 12)] == 2
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


def test_load_reference_from_market_daily_accumulates_and_merges_by_platform_updated_at(capsys, tmp_path, source_db, params_file) -> None:
    """09-08：参照不再靠复盘总览翻页，每日同步把内层八段落进主库 fact_market_daily.cycle_stage（PR #665），load-reference 从那里累积；
    与 JSON 快照同源同表，同一天以平台 updated_at 较新者为准，两边都不会互相擦掉。"""
    sidecar = tmp_path / "labels.duckdb"
    # 主库没有这列 → 明说，不是空表；--json 与 --from-market-daily 二选一。
    assert main(["load-reference", "--from-market-daily", "--labels-db", str(sidecar), "--db-path", str(source_db)]) == 2
    assert "没有 cycle_stage 列" in capsys.readouterr().err
    assert main(["load-reference", "--labels-db", str(sidecar), "--db-path", str(source_db)]) == 2
    assert "二选一" in capsys.readouterr().err
    con = duckdb.connect(str(source_db))
    try:
        for col, typ in (("cycle_stage", "VARCHAR"), ("cycle_stage_source", "VARCHAR"), ("cycle_stage_updated_at", "TIMESTAMP"), ("updated_at", "TIMESTAMP")):
            con.execute(f"ALTER TABLE fact_market_daily ADD COLUMN {col} {typ}")
        # 每日同步落了三天（cycle_stage_updated_at 是平台 updated_at 转成的 UTC 无时区，与旁路库 vendor_updated_at 同一口径）：
        # 01-05 / 01-06 是「当时怎么说」，01-07 那天平台第二天改写过（updated_at 晚一天）。
        con.execute("UPDATE fact_market_daily SET cycle_stage = '承接盘反复', cycle_stage_source = 'fupanhui:reviews/summary.internal_cycle', cycle_stage_updated_at = TIMESTAMP '2026-01-05 10:55:00', updated_at = TIMESTAMP '2026-01-05 11:00:00' WHERE trade_date = DATE '2026-01-05'")
        con.execute("UPDATE fact_market_daily SET cycle_stage = '承接盘反复', cycle_stage_source = 'fupanhui:reviews/overview.cycle_stage', cycle_stage_updated_at = TIMESTAMP '2026-01-06 10:55:00', updated_at = TIMESTAMP '2026-01-06 11:00:00' WHERE trade_date = DATE '2026-01-06'")
        con.execute("UPDATE fact_market_daily SET cycle_stage = '左底向下', cycle_stage_source = 'fupanhui:reviews/summary.internal_cycle', cycle_stage_updated_at = TIMESTAMP '2026-01-08 10:55:00', updated_at = TIMESTAMP '2026-01-08 11:00:00' WHERE trade_date = DATE '2026-01-07'")
    finally:
        con.close()
    loaded = _run(capsys, "load-reference", "--from-market-daily", "--labels-db", str(sidecar), "--db-path", str(source_db), "--computed-at", "2026-01-08T12:00:00Z")
    assert (loaded["rows"], loaded["inserted"], loaded["updated"], loaded["kept"], loaded["table_rows"]) == (3, 3, 0, 0, 3)
    assert loaded["from"] == "fact_market_daily.cycle_stage" and {r["cycle_stage"]: r["days"] for r in loaded["by_cycle_stage"]} == {"承接盘反复": 2, "左底向下": 1}
    side = duckdb.connect(str(sidecar), read_only=True)
    try:
        row = side.execute("SELECT external_cycle, ice_point_level, amount_vs_ma20_pct, up_count, top3_market_share_pct, formula_version, data_version, vendor_updated_at, amount_yi FROM history_reference_stages WHERE trade_date = DATE '2026-01-05'").fetchone()
    finally:
        side.close()
    # 只搬平台自己给的字段；成交额单位未核 → NULL，不猜。
    assert row[0] is not None and row[5] == "fact_market_daily.cycle_stage" and row[6] == "fupanhui:reviews/summary.internal_cycle"
    assert str(row[7]) == "2026-01-05 10:55:00" and row[8] is None

    # 一份更晚拉的 JSON 快照覆盖 01-05 / 01-06（平台后来把 01-06 改成了「主流主升」），没有 01-07 → 01-07 保留，不被擦掉。
    payload = {"pulled_at": "2026-01-20T04:00:00Z", "items": [
        _reference_item("2026-01-05", "承接盘反复", "顶部横盘阶段", 100.0), _reference_item("2026-01-06", "主流主升", "主升阶段", 120.0),
    ]}
    payload["items"][0]["updated_at"] = "2026-01-05T18:00:00+08:00"   # = 10:00 UTC，比每日同步那条（10:55 UTC）早 → 保留每日那条（kept）
    payload["items"][1]["updated_at"] = "2026-01-19T18:55:13+08:00"   # 更晚 → 覆盖（updated）
    ref_json = tmp_path / "reference.json"
    ref_json.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    merged = _run(capsys, "load-reference", "--json", str(ref_json), "--labels-db", str(sidecar), "--db-path", str(source_db), "--computed-at", "2026-01-20T05:00:00Z")
    assert (merged["rows"], merged["inserted"], merged["updated"], merged["kept"], merged["table_rows"]) == (2, 0, 1, 1, 3)
    side = duckdb.connect(str(sidecar), read_only=True)
    try:
        stages = dict(side.execute("SELECT CAST(trade_date AS VARCHAR), cycle_stage FROM history_reference_stages ORDER BY trade_date").fetchall())
        versions = dict(side.execute("SELECT CAST(trade_date AS VARCHAR), formula_version FROM history_reference_stages ORDER BY trade_date").fetchall())
    finally:
        side.close()
    assert stages == {"2026-01-05": "承接盘反复", "2026-01-06": "主流主升", "2026-01-07": "左底向下"}
    assert versions == {"2026-01-05": "fact_market_daily.cycle_stage", "2026-01-06": "review_overview_v1", "2026-01-07": "fact_market_daily.cycle_stage"}
    # 再跑一次每日载入：三天都不比库里新 → 全部 kept，幂等。
    again = _run(capsys, "load-reference", "--from-market-daily", "--labels-db", str(sidecar), "--db-path", str(source_db), "--computed-at", "2026-01-21T12:00:00Z")
    assert (again["inserted"], again["updated"], again["kept"]) == (0, 0, 3)


def test_build_sector_roles_writes_sector_labels_and_rule_readout(capsys, tmp_path, source_db, params_file) -> None:
    """第二刀 C 类: sector labels ride in the same table under entity_type='sector'; market rows and their hash are untouched."""
    sidecar = tmp_path / "labels.duckdb"
    common = ["--db-path", str(source_db), "--labels-db", str(sidecar), "--params", str(params_file), "--computed-at", "2026-09-07T00:00:00Z"]
    labels = _run(capsys, "build-labels", *common)
    roles = _run(capsys, "build-sector-roles", *common)
    # Two sectors × 10 days × 18 labels.
    assert roles["rows"] == 2 * 10 * 18 and roles["readouts"]["days"] == {"ok": 10}
    side = duckdb.connect(str(sidecar), read_only=True)
    try:
        # 电子 is industry_1 on every fixture day (the 3-day rank needs three contiguous days: NULL on days 1-2).
        s1 = {r[0]: r[1] for r in side.execute("SELECT label, value_num FROM history_teaching_labels WHERE entity_type='sector' AND entity_id='S1' AND trade_date=DATE '2026-01-09'").fetchall()}
        assert s1["tf.role_volume_top3"] == 1 and s1["tf.limit_up_count"] == 3 and s1["tf.sharpness_limit_rank"] == 1
        assert s1["tf.rps_3d_rank"] in (1, 2) and s1["tf.money_effect.limit_top10"] == 1
        assert s1["tf.dual_red_strict"] == 1  # day index 4 is even: pct 1.0, diff 12, amount 600
        s2 = {r[0]: r[1] for r in side.execute("SELECT label, value_num FROM history_teaching_labels WHERE entity_type='sector' AND entity_id='S2' AND trade_date=DATE '2026-01-09'").fetchall()}
        assert s2["tf.role_volume_top3"] == 0 and s2["tf.role_price_top10"] == 1 and s2["tf.dual_red_strict"] == 0
        # 宽度: on 01-09 the 1y+ highs are 通信 ×3 (n = 1, 5, 9) vs 电子 ×2 → S2 carries the breadth role.
        assert s2["tf.role_breadth_top_l1"] == 1 and s1["tf.role_breadth_top_l1"] == 0
        # 主流两口径: the fixture's vendor mainline table lists S1 every day; the volume top-3 口径 is 电子 = S1.
        assert s1["tf.mainline_vendor"] == 1 and s2["tf.mainline_vendor"] == 0 and s1["tf.mainline_volume_top3"] == 1
        # 锐度合成: S1 (limit rank 1, rps5 rank 2) and S2 (2, 1) tie at 1.5 — both inside the top 10.
        assert s1["tf.sharpness_rank_mean"] == 1.5 and s2["tf.sharpness_rank_mean"] == 1.5 and s1["tf.role_sharpness_top10"] == 1
        # k-means needs at least k = 3 rows: the two-sector fixture leaves it NULL.
        assert s1["tf.money_effect.kmeans_hot"] is None
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
    assert set(rule) == {"limit_top10", "dual_red", "rps5_top10", "rank_mean_top10", "kmeans_hot"}
    assert roles["readouts"]["labels"][-1] == "money_effect.kmeans_hot"
    # Every fixture day has S1 (电子, the top-1 industry) in the limit_top10 set, so the outcome is never met; verdict stays insufficient_n at n < 10.
    assert rule["limit_top10"]["readout"]["verdict"] == "insufficient_n"
    assert rule["limit_top10"]["below_ma_days"] + rule["limit_top10"]["above_ma_days"] + sum(rule["limit_top10"]["excluded"].values()) == 10
    report = _run(capsys, "report", "--labels-db", str(sidecar))
    assert report["counts"]["sector_label_rows"] == 360


def test_build_range_leaders_writes_group_rows_handoffs_and_receipt(capsys, tmp_path, source_db, params_file) -> None:
    """区间涨幅高标链 (创始人 09-07 第九、十段): top-N by N-day gain per window, same-day exits/births paired as 衔接."""
    params = json.loads(params_file.read_text(encoding="utf-8"))
    params.update({"range_leader_windows": [2], "range_leader_top": 2, "range_leader_context": 3})
    params_file.write_text(json.dumps(params, ensure_ascii=False, indent=2), encoding="utf-8")
    sidecar = tmp_path / "labels.duckdb"
    common = ["--db-path", str(source_db), "--labels-db", str(sidecar), "--params", str(params_file), "--computed-at", "2026-09-07T00:00:00Z"]
    _run(capsys, "build-labels", *common)
    _run(capsys, "build-succession", *common)
    out = _run(capsys, "build-range-leaders", *common)
    # Closes are 10·(k+1) + i: X gains fastest, then Y, then Z — the top-2 group is {X, Y} on every day with a 2-day window (8 of 10).
    assert out["leader_rows"] == 16 and out["handoffs"] == 0
    side = duckdb.connect(str(sidecar), read_only=True)
    try:
        rows = side.execute("SELECT trade_date, rank, stock_ts_code, sw_l1, tenure_day, prev_rank FROM history_range_leaders ORDER BY trade_date, rank").fetchall()
        assert rows[0] == (date(2026, 1, 7), 1, "X", "电子", 1, None) and rows[1] == (date(2026, 1, 7), 2, "Y", "通信", 1, None)
        assert rows[-1] == (date(2026, 1, 16), 2, "Y", "通信", 8, 2)
        # 01-07 over 01-05: X 12/10 − 1 = 20 %, rounded like every other view scalar.
        assert side.execute("SELECT gain_pct FROM history_range_leaders WHERE trade_date = DATE '2026-01-07' AND rank = 1").fetchone() == (20.0,)
        assert side.execute("SELECT COUNT(*) FROM history_range_leader_handoffs").fetchone() == (0,)
        kinds = [r[0] for r in side.execute("SELECT build_kind FROM history_teaching_receipts ORDER BY build_kind").fetchall()]
        assert kinds == ["leader_succession", "range_leaders", "teaching_labels"]
    finally:
        side.close()
    readout = out["readouts"]["handoffs"]["2"]
    assert readout["days_ok"] == 8 and readout["days_gap"] == 2 and readout["handoffs"] == 0 and readout["births_per_day_mean"] == 0.0
    assert readout["entry_gain_pct_quartiles"]["n"] == 8 and readout["l1_distinct_median"] == 2
    assert out["readouts"]["cross_chain"]["succession_nodes"] == 4  # the four ok nodes of the 连板 chain; none of A..H has a close, so no overlap
    assert out["readouts"]["cross_chain"]["leader_i_in_range_top_on_break_day"] == {}
    again = _run(capsys, "build-range-leaders", *[*common[:-2], "--computed-at", "2026-09-08T00:00:00Z"])
    assert again["canonical_hash"] == out["canonical_hash"]
    report = _run(capsys, "report", "--labels-db", str(sidecar))
    assert report["counts"]["range_leader_rows"] == 16 and report["counts"]["range_leader_handoffs"] == 0


def test_build_dynasties_cuts_waves_from_the_reference_and_flags_separation(capsys, tmp_path, source_db, params_file) -> None:
    """王朝链 (创始人 09-07 第十三段): waves come from the platform stages; the new dynasty's members are read in the old one's collapse window."""
    params = json.loads(params_file.read_text(encoding="utf-8"))
    params.update({"dynasty_top": 2, "dynasty_cohort": 3})
    params_file.write_text(json.dumps(params, ensure_ascii=False, indent=2), encoding="utf-8")
    sidecar = tmp_path / "labels.duckdb"
    common = ["--db-path", str(source_db), "--labels-db", str(sidecar), "--params", str(params_file), "--computed-at", "2026-09-07T00:00:00Z"]
    # Without a reference the command fails closed: waves are cut on the platform's stages, nothing else.
    assert main(["build-dynasties", *common]) == 2 and "参照" in capsys.readouterr().err
    # 承接 ×5 | 左底向下 | 共建 共建 承接 2.0 → wave 0 (truncated, peaks day 5), one-day collapse (day 6), wave 1 (open) from day 7.
    stages = ["承接盘反复", "承接盘反复", "承接盘反复", "承接盘反复", "承接盘反复", "左底向下", "共建主线", "共建主线", "承接盘反复", "主流主升2.0"]
    payload = {"source": "fupanhui.com /api/v1/client/reviews/overview", "pulled_at": "2026-09-07T04:00:00Z", "available_since": "2021-09-13",
               "items": [_reference_item(d, s, "顶部横盘阶段", 100.0) for d, s in zip(DAYS, stages)]}
    ref_json = tmp_path / "reference.json"
    ref_json.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    _run(capsys, "load-reference", "--json", str(ref_json), "--labels-db", str(sidecar), "--db-path", str(source_db), "--computed-at", "2026-09-07T05:00:00Z")
    # 第十四段: 亏钱效应 must be measurable — without the market labels (tf.money_losing_day) the chain refuses to build.
    assert main(["build-dynasties", *common]) == 2 and "money_losing_day" in capsys.readouterr().err
    _run(capsys, "build-labels", *common)
    out = _run(capsys, "build-dynasties", *common)
    assert out["waves"] == 2 and out["handoff_rows"] == 3
    # 亏钱效应 counts are read back from the labels the same build wrote: the one-day collapse window (01-12) is flagged iff
    # tf.money_losing_day says so that day; the peak block of wave 0 covers its five labelled days.
    side = duckdb.connect(str(sidecar), read_only=True)
    try:
        losing = {r[0]: r[1] for r in side.execute("SELECT trade_date, value_num FROM history_teaching_labels WHERE label = 'tf.money_losing_day'").fetchall()}
    finally:
        side.close()
    assert set(losing) and all(v in (None, 0.0, 1.0) for v in losing.values())

    def expected(day_from: date, day_to: date) -> dict:
        labelled = {d: v for d, v in losing.items() if day_from <= d <= day_to and v is not None}
        return {"days": len(labelled), "flagged": sum(1 for v in labelled.values() if v == 1.0)}

    ml = out["readouts"]["waves"][0]["money_losing"]
    assert {k: ml["peak_block"][k] for k in ("days", "flagged")} == expected(date(2026, 1, 5), date(2026, 1, 9))
    assert {k: ml["collapse"][k] for k in ("days", "flagged")} == expected(date(2026, 1, 12), date(2026, 1, 12))
    assert ml["collapse_flagged_days"] == ([DAYS[5]] if losing.get(date(2026, 1, 12)) == 1.0 else [])
    assert out["readouts"]["waves"][1]["money_losing"]["collapse"] is None  # open wave: no collapse window to count
    waves = out["readouts"]["waves"]
    assert [w["status"] for w in waves] == ["truncated", "open"]
    assert waves[0]["collapse"] == [DAYS[5], DAYS[5]] and waves[0]["first_down_end"] == DAYS[5] and waves[0]["ranked_stocks"] == 0
    # New wave (01-13 → 01-16, base 01-12): X 19/15, Y 29/25, Z 39/35 → X, Y, Z; the 连板 stocks A..H have no close and never rank.
    assert waves[1]["start"] == DAYS[6] and waves[1]["peak_end"] == DAYS[9] and waves[1]["ranked_stocks"] == 3
    assert waves[1]["entry_gain_pct"]["top2"] == pytest.approx((29 / 25 - 1) * 100) and waves[1]["forms"]["cohort3"] == {"趋势": 3}
    side = duckdb.connect(str(sidecar), read_only=True)
    try:
        members = side.execute("SELECT wave_idx, rank, stock_ts_code, wave_status, form, collapse_ret_pct FROM history_dynasties ORDER BY wave_idx, rank").fetchall()
        assert members == [(1, 1, "X", "open", "趋势", None), (1, 2, "Y", "open", "趋势", None), (1, 3, "Z", "open", "趋势", None)]
        rows = side.execute(
            """SELECT new_rank, stock_ts_code, old_wave_rank, collapse_ret_pct, collapse_ret_percentile, new_high_in_collapse, separation_relative, first_leg_ret_pct
               FROM history_dynasty_handoffs ORDER BY new_rank"""
        ).fetchall()
        # Collapse day 01-12 over 01-09: X 15/14, Y 25/24, Z 35/34 → percentiles 66.67 / 33.33 / 0 (none reaches 0.9); every stock's
        # high (close + 0.5) is above the window before it → 新高分离 for all; the old wave has no visible start, so no old rank.
        assert [(r[0], r[1], r[2], r[5], r[6]) for r in rows] == [(1, "X", None, True, False), (2, "Y", None, True, False), (3, "Z", None, True, False)]
        assert rows[0][3] == pytest.approx((15 / 14 - 1) * 100, abs=1e-6) and rows[0][4] == 66.67 and rows[0][7] == rows[0][3]
        kinds = [r[0] for r in side.execute("SELECT build_kind FROM history_teaching_receipts ORDER BY build_kind").fetchall()]
        assert kinds == ["dynasties", "teaching_labels"]
    finally:
        side.close()
    (handoff,) = out["readouts"]["handoffs"]
    assert handoff["handoff"] == "W0→W1" and handoff["old_wave_status"] == "truncated" and handoff["money_losing"]["stocks"] == 3
    assert handoff["money_losing"]["index_ret_pct"] == pytest.approx((99 / 101 - 1) * 100, abs=1e-3)  # the fixture's gap-down day against the day before
    assert handoff["top2"]["new_in_collapse"]["share_separation_new_high"] == 1.0 and handoff["top2"]["new_in_collapse"]["share_separation_relative"] == 0.0
    assert handoff["top2"]["old_in_collapse"]["ret_pct"] is None  # truncated old wave: nothing to fall
    gate = out["readouts"]["separation_gate"]
    assert gate["cycles"] == 1 and gate["top2"]["n"] == 0 and gate["top2"]["verdict"] == "insufficient_n" and gate["cohort3"]["baseline_k"] == 3
    again = _run(capsys, "build-dynasties", *[*common[:-2], "--computed-at", "2026-09-08T00:00:00Z"])
    assert again["canonical_hash"] == out["canonical_hash"]
    report = _run(capsys, "report", "--labels-db", str(sidecar))
    assert report["counts"]["dynasty_rows"] == 3 and report["counts"]["dynasty_handoffs"] == 3


def test_stale_sidecar_schema_fails_closed(capsys, tmp_path, source_db, params_file) -> None:
    sidecar = tmp_path / "labels.duckdb"
    _build(capsys, source_db, sidecar, params_file, "2026-09-07T00:00:00Z")
    con = duckdb.connect(str(sidecar))
    con.execute("ALTER TABLE history_leader_succession DROP COLUMN forward")
    con.close()
    code = main(["build-succession", "--db-path", str(source_db), "--labels-db", str(sidecar), "--params", str(params_file)])
    assert code == 2
    assert "schema 过期" in capsys.readouterr().err
