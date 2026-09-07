from intelligence.services.teaching_framework.flags import compute_flags, normalize_hhmm


def test_previous_predicates_require_adjacent_calendar_days():
    rows = [
        {
            "trade_date": "2026-01-01",
            "sh_index_close": 99,
            "sh_week_ma": 100,
            "sh_deviation_pct": -1,
        },
        {
            "trade_date": "2026-01-03",
            "sh_index_close": 101,
            "sh_week_ma": 100,
            "sh_deviation_pct": 1,
        },
    ]
    out = compute_flags(rows, calendar=["2026-01-01", "2026-01-02", "2026-01-03"])
    assert out[1]["cross_above_week_ma"] is None


def test_duplicate_stock_rows_are_collapsed_for_max_boards():
    market = [
        {
            "trade_date": "2026-01-01",
            "sh_index_close": 1,
            "sh_week_ma": 1,
            "sh_deviation_pct": 0,
        }
    ]
    stocks = [
        {"trade_date": "2026-01-01", "stock_ts_code": "A", "limit_times": 3},
        {"trade_date": "2026-01-01", "stock_ts_code": "A", "limit_times": 3},
    ]
    assert compute_flags(market, stock_rows=stocks)[0]["max_boards"] == 3


def test_compact_time_normalization():
    assert normalize_hhmm("093500").hour == 9
    assert normalize_hhmm("09:35").minute == 35
    assert normalize_hhmm("bad") is None


def _market(day: str, amount):
    return {"trade_date": day, "sh_index_close": 1, "sh_week_ma": 1, "sh_deviation_pct": 0, "total_amount": amount, "amount_ma20": 100.0}


def test_volume_band_follows_founder_100_120_moderate_window():
    """量能比（当日 / 20 日均量 × 100）：<100 shrink · 100–120 moderate（「100–120 属于温和放量」）· >120 surge；NULL stays NULL."""
    params = {"volume_level": {"basis": "amount_vs_ma20_pct", "moderate_from_pct": 100, "surge_from_pct": 120}}
    days = ["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08", "2026-01-09", "2026-01-12"]
    rows = [_market(d, v) for d, v in zip(days, (95.0, 100.0, 112.5, 120.0, 120.1, None))]
    out = compute_flags(rows, calendar=days, params=params)
    assert [r["amount_vs_ma20_pct"] for r in out] == [95.0, 100.0, 112.5, 120.0, 120.1, None]
    assert [r["volume_band"] for r in out] == ["shrink", "moderate", "moderate", "moderate", "surge", None]
    assert [r["volume_surge"] for r in out] == [False, False, False, False, True, None]
    assert [r["volume_expanding"] for r in out] == [False, True, True, True, True, None]
    assert [r["shrink_day"] for r in out] == [True, False, False, False, False, None]  # shrink_day is the same ruler below 100


def _ohlc(day: str, close: float, high: float, low: float, dev: float):
    return {"trade_date": day, "sh_index_close": close, "sh_index_high": high, "sh_index_low": low,
            "sh_week_ma": 100.0, "sh_deviation_pct": dev}


def test_index_range_scalars_use_base_close_and_require_contiguous_window():
    """区间涨幅 / 振幅都以窗口前一日收盘为基；偏离度变化是两端之差；窗口不满或跨缺日 → NULL + 缺口。"""
    days = ["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08", "2026-01-09", "2026-01-12"]
    rows = [
        _ohlc(days[0], 100.0, 101.0, 99.0, 0.0),
        _ohlc(days[1], 102.0, 104.0, 101.0, 0.5),
        _ohlc(days[2], 103.0, 106.0, 100.0, 1.2),
        _ohlc(days[4], 99.0, 103.0, 97.0, -0.8),   # 01-08 missing from the source
        _ohlc(days[5], 101.0, 102.0, 98.0, -0.1),
    ]
    out = compute_flags(rows, calendar=days, params={"index_range_windows": [2]})
    first, second, third, fifth, sixth = out
    for rec in (first, second):
        assert rec["sh_index_pct_chg_2d"] is None and rec["scalar_gaps"]["sh_index_pct_chg_2d"] == "window_incomplete"
    # 01-07 over base 01-05: gain 3%, amplitude (106 − 100) / 100, deviation 1.2 − 0.0
    assert (third["sh_index_pct_chg_2d"], third["sh_index_amplitude_2d"], third["sh_deviation_change_2d"]) == (3.0, 6.0, 1.2)
    assert "sh_index_pct_chg_2d" not in third["scalar_gaps"]
    # the window ending 01-09 needs 01-07..01-09 to be adjacent calendar days; 01-08 is absent
    assert fifth["sh_index_amplitude_2d"] is None and fifth["scalar_gaps"]["sh_index_amplitude_2d"] == "window_incomplete"
    assert sixth["sh_index_pct_chg_2d"] is None and sixth["scalar_gaps"]["sh_deviation_change_2d"] == "window_incomplete"


def test_index_range_scalars_fail_closed_per_field():
    days = ["2026-01-05", "2026-01-06", "2026-01-07"]
    rows = [_ohlc(days[0], 100.0, 101.0, 99.0, 0.0), _ohlc(days[1], 102.0, None, 101.0, None), _ohlc(days[2], 103.0, 105.0, 101.0, 1.0)]
    out = compute_flags(rows, calendar=days, params={"index_range_windows": [2]})
    last = out[2]
    assert last["sh_index_pct_chg_2d"] == 3.0
    assert last["sh_index_amplitude_2d"] is None and last["scalar_gaps"]["sh_index_amplitude_2d"] == "high_low_null"
    assert last["sh_deviation_change_2d"] == 1.0
    rows[0]["sh_deviation_pct"] = None
    last = compute_flags(rows, calendar=days, params={"index_range_windows": [2]})[2]
    assert last["sh_deviation_change_2d"] is None and last["scalar_gaps"]["sh_deviation_change_2d"] == "deviation_null"


def _dev_row(day: str, close: float, dev: float, open_: float = 100.0):
    return {"trade_date": day, "sh_index_close": close, "sh_index_open": open_, "sh_week_ma": 100.0, "sh_deviation_pct": dev}


def test_deviation_streaks_follow_the_founders_three_words():
    """持续走高 / 逐渐走低 / 回归周均 are runs of daily deviation moves; NULL or a calendar break resets to unknown."""
    days = ["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08", "2026-01-09", "2026-01-12", "2026-01-13"]
    devs = [-3.0, -2.0, -1.0, -1.5, -0.5, None, 0.5]
    rows = [_dev_row(d, 100 + v if v is not None else None, v) for d, v in zip(days, devs)]
    out = compute_flags(rows, calendar=days)
    rising = [r["deviation_rising_streak"] for r in out]
    falling = [r["deviation_falling_streak"] for r in out]
    toward = [r["deviation_toward_ma_streak"] for r in out]
    assert rising == [None, 1, 2, 0, 1, None, None]      # day 1 has no previous day; NULL day and its successor are unknown
    assert falling == [None, 0, 0, 1, 0, None, None]
    assert toward == [None, 1, 2, 0, 1, None, None]       # below the MA, rising is moving toward it


def test_up_candle_and_ma_side_episode_structure():
    """A run on one side of the MA is anchored at the observed cross; its extreme, retrace and retrace peak follow the path."""
    days = ["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08", "2026-01-09", "2026-01-12", "2026-01-13", "2026-01-14"]
    #        above    cross↓  探底     反弹      反弹      回踩      回踩      cross↑
    closes = [101.0,   99.0,   97.0,   98.5,    99.6,    98.8,    98.2,    100.8]
    devs = [c - 100 for c in closes]
    rows = [_dev_row(d, c, v, open_=c - 0.5 if i % 2 == 0 else c + 0.5) for i, (d, c, v) in enumerate(zip(days, closes, devs))]
    out = compute_flags(rows, calendar=days)
    assert [r["up_candle"] for r in out] == [True, False, True, False, True, False, True, False]
    # Day 1 is above the MA but no cross was observed: the run is unanchored → unknown.
    assert out[0]["ma_episode_day"] is None
    below = out[1:7]
    assert [r["ma_episode_day"] for r in below] == [1, 2, 3, 4, 5, 6]
    assert [r["ma_episode_extreme_dev"] for r in below] == [-1.0, -3.0, -3.0, -3.0, -3.0, -3.0]
    assert [r["ma_episode_retrace_pts"] for r in below] == [0.0, 0.0, 1.5, 2.6, 1.8, 1.2]
    assert [r["ma_episode_retrace_peak_pts"] for r in below] == [0.0, 0.0, 1.5, 2.6, 2.6, 2.6]
    # The cross back above starts a new anchored run on the other side.
    assert (out[7]["ma_episode_day"], out[7]["ma_episode_extreme_dev"], out[7]["ma_episode_retrace_pts"]) == (1, 0.8, 0.0)


def _leg_row(day: str, close: float, high: float, low: float, amount: float = 95.0, open_: float | None = None):
    """amount is the day's turnover against a 20-day mean of 100: 95 = 缩量, 125 = 暴量 (量能比 125%)."""
    return {"trade_date": day, "sh_index_close": close, "sh_index_open": open_ if open_ is not None else close,
            "sh_index_high": high, "sh_index_low": low, "sh_week_ma": 100.0, "sh_deviation_pct": close - 100,
            "total_amount": amount, "amount_ma20": 100.0}


def test_episode_leg_gain_amplitude_days_since_high_and_days_since_cross_above():
    """「那一个区间就是」: gain and amplitude are measured over the leg against the close before the cross."""
    days = ["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08", "2026-01-09"]
    rows = [
        _leg_row(days[0], 99.0, 99.5, 98.0),             # below
        _leg_row(days[1], 101.0, 101.5, 100.2),          # cross above: base close = 99
        _leg_row(days[2], 102.0, 103.0, 101.0),          # new leg high
        _leg_row(days[3], 101.5, 102.5, 101.0),          # high not exceeded: 1 day since high
        _leg_row(days[4], 101.8, 102.8, 101.2),          # 2 days since high
    ]
    out = compute_flags(rows, calendar=days, params={"breakout_confirm_days": 3})
    assert [r["days_since_cross_above"] for r in out] == [None, 0, 1, 2, 3]
    assert out[4]["ma_episode_pct_chg"] == round((101.8 / 99 - 1) * 100, 6)
    assert out[4]["ma_episode_amplitude"] == round((103.0 - 100.2) / 99 * 100, 6)
    assert [r["ma_episode_days_since_high"] for r in out[1:]] == [0, 0, 1, 2]
    rows[3]["sh_index_high"] = None  # a missing high inside the leg makes amplitude and days-since-high unknown
    out = compute_flags(rows, calendar=days, params={"breakout_confirm_days": 3})
    assert out[3]["ma_episode_amplitude"] is None and out[4]["ma_episode_days_since_high"] is None
    assert out[4]["ma_episode_pct_chg"] is not None  # gain only needs closes


def test_below_ma_cycle_first_cross_residual_touch_and_retest():
    """创始人流程: 第一次下穿 → 探底 → 反弹触碰周均（不放量的短暂上穿 = 残差）→ 回踩探底 → 放量上穿结束周期."""
    days = [f"2026-01-{d:02d}" for d in (5, 6, 7, 8, 9, 12, 13, 14, 15, 16)]
    rows = [
        _leg_row(days[0], 101.0, 101.5, 100.5),                 # above (unanchored start)
        _leg_row(days[1], 99.0, 100.5, 98.5),                   # first cross below -> cycle day 1
        _leg_row(days[2], 97.0, 98.0, 96.5),                    # 探底
        _leg_row(days[3], 100.3, 100.8, 99.0),                  # touches the MA: cross above without surge (residual so far)
        _leg_row(days[4], 100.1, 100.6, 99.6),                  # still above, no surge, day 2 of the excursion
        _leg_row(days[5], 98.8, 100.2, 98.5),                   # falls back within 3 days: retest, cycle continues
        _leg_row(days[6], 98.0, 98.9, 97.5),
        _leg_row(days[7], 100.9, 101.2, 99.8, amount=125.0),    # cross above with volume (量能比 125%): the turn; cycle ends
        _leg_row(days[8], 101.5, 102.0, 100.8),
        _leg_row(days[9], 102.0, 102.4, 101.3),
    ]
    out = compute_flags(rows, calendar=days, params={"breakout_confirm_days": 3})
    assert [r["cross_below_kind"] for r in out] == [None, "first", None, None, None, "retest", None, None, None, None]
    assert [r["below_ma_cycle_day"] for r in out] == [None, 1, 2, 3, 4, 5, 6, None, None, None]
    assert [r["days_since_cross_above"] for r in out] == [None, None, None, 0, 1, None, None, 0, 1, 2]
    # The retest is remembered for the rest of the cycle and forgotten once the volume breakout ends it.
    assert [r["below_ma_cycle_retest_seen"] for r in out] == [None, False, False, False, False, True, True, None, None, None]


def test_below_ma_cycle_ends_when_an_unconfirmed_excursion_outlives_the_tolerance():
    days = [f"2026-01-{d:02d}" for d in (5, 6, 7, 8, 9, 12, 13, 14)]
    rows = [
        _leg_row(days[0], 101.0, 101.5, 100.5),
        _leg_row(days[1], 99.0, 100.5, 98.5),    # first cross below
        _leg_row(days[2], 100.3, 100.8, 99.0),   # cross above, no surge
        _leg_row(days[3], 100.4, 100.9, 99.9),
        _leg_row(days[4], 100.5, 101.0, 100.0),  # day 3 of the excursion: tolerance not yet exceeded
        _leg_row(days[5], 100.6, 101.1, 100.1),  # day 4 above without surge: a real leg, the below cycle is over
        _leg_row(days[6], 99.5, 100.7, 99.0),    # next cross below starts a new cycle
        _leg_row(days[7], 99.0, 99.8, 98.5),
    ]
    out = compute_flags(rows, calendar=days, params={"breakout_confirm_days": 3})
    assert [r["below_ma_cycle_day"] for r in out] == [None, 1, 2, 3, 4, None, 1, 2]
    assert out[6]["cross_below_kind"] == "first"


def test_range_structure_flags_compare_adjacent_blocks():
    """高位震荡 形态 = 高点不抬高加收敛 (创始人 09-07 第七段): recent block vs the block before it."""
    days = [f"2026-01-{d:02d}" for d in (5, 6, 7, 8, 9, 12, 13)]
    highs = [105.0, 106.0, 104.0, 105.5, 104.5, 103.0, 108.0]
    lows = [100.0, 101.0, 100.5, 102.0, 102.5, 101.0, 101.0]
    rows = [_leg_row(d, 102.0, h, lo) for d, h, lo in zip(days, highs, lows)]
    out = compute_flags(rows, calendar=days, params={"index_range_windows": [3]})
    # First five days lack two full 3-day blocks.
    assert all(r["index_high_not_rising_3d"] is None for r in out[:5])
    # 01-12: recent block 01-08..01-12 has highs (105.5, 104.5, 103.0) → max 105.5, lows min 101.0;
    # earlier block 01-05..01-07 has highs (105, 106, 104) → max 106, lows min 100.
    # 105.5 <= 106 → high not rising; range 4.5 < 6 → converging.
    assert (out[5]["index_high_not_rising_3d"], out[5]["index_range_converging_3d"]) == (True, True)
    # 01-13: recent 01-09..01-13 highs (104.5, 103.0, 108.0) → max 108 > earlier (01-06..01-08) max 106 → rising;
    # recent range 108 - 101 = 7 vs earlier 106 - 100.5 = 5.5 → not converging.
    assert (out[6]["index_high_not_rising_3d"], out[6]["index_range_converging_3d"]) == (False, False)
    rows[2]["sh_index_low"] = None
    out = compute_flags(rows, calendar=days, params={"index_range_windows": [3]})
    assert out[5]["index_range_converging_3d"] is None  # a missing low inside either block: unknown


def test_ma_side_episode_is_unknown_across_a_calendar_break():
    days = ["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08", "2026-01-09"]
    rows = [_dev_row(days[0], 101.0, 1.0), _dev_row(days[1], 99.0, -1.0), _dev_row(days[3], 98.0, -2.0), _dev_row(days[4], 97.0, -3.0)]
    out = compute_flags(rows, calendar=days)
    assert out[1]["ma_episode_day"] == 1
    assert out[2]["ma_episode_day"] is None and out[3]["ma_episode_day"] is None  # 01-07 missing: the run lost its anchor


def test_breadth_scalars_fail_closed_on_absent_day_and_thin_coverage():
    days = ["2026-01-05", "2026-01-06", "2026-01-07"]
    breadth = [
        {"trade_date": days[0], "stock_count": 5000, "pct_chg_median": 0.4, "price_mean": 20.5,
         "ma5_deviation_median": None, "ma5_count": 0, "ma10_deviation_median": None, "ma10_count": 0},
        {"trade_date": days[1], "stock_count": 2100, "pct_chg_median": -3.0, "price_mean": 19.0,
         "ma5_deviation_median": -1.2, "ma5_count": 2090, "ma10_deviation_median": -2.0, "ma10_count": 2050},
    ]
    breadth[0]["price_mean"] = 20.500000000000004  # last-bit noise from a parallel SQL AVG
    out = compute_flags([_market(d, 1.0) for d in days], calendar=days, breadth_rows=breadth, params={"breadth_min_stocks": 4000})
    full, thin, absent = out
    assert (full["stock_pct_chg_median"], full["stock_price_mean"]) == (0.4, 20.5)
    assert full["stock_ma5_deviation_median"] is None and full["scalar_gaps"]["stock_ma5_deviation_median"] == "ma5_count_below_floor"
    assert thin["stock_pct_chg_median"] is None and thin["scalar_gaps"]["stock_pct_chg_median"] == "stock_count_below_floor"
    assert thin["stock_ma10_deviation_median"] is None and thin["scalar_gaps"]["stock_ma10_deviation_median"] == "ma10_count_below_floor"
    assert absent["stock_price_mean"] is None and absent["scalar_gaps"]["stock_price_mean"] == "stock_rows_absent"
