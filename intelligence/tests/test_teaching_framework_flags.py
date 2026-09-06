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
