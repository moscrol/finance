from intelligence.services.teaching_framework.coverage import build_coverage, normalize_hhmmss
from intelligence.services.teaching_framework.leader_succession import build_succession, top_by_day


def test_coverage_distinguishes_empty_and_missing_and_dedupes():
    calendar = ["2026-01-01", "2026-01-02", "2026-01-03"]
    rows = {"2026-01-01": [{"stock_ts_code": "A", "limit_times": 3}, {"stock_ts_code": "A", "limit_times": 3}], "2026-01-02": []}
    cov = build_coverage(calendar, rows)
    assert cov["2026-01-01"].status == "covered"
    assert len(cov["2026-01-01"].rows) == 1
    assert cov["2026-01-02"].status == "covered_empty"
    assert cov["2026-01-03"].status == "missing"


def test_top_tie_and_field_null_are_fail_closed():
    cov = build_coverage(["2026-01-01", "2026-01-02"], {"2026-01-01": [{"stock_ts_code": "A", "limit_times": 3}, {"stock_ts_code": "B", "limit_times": 3}], "2026-01-02": [{"stock_ts_code": "C", "limit_times": None}]})
    top = top_by_day(cov)
    assert top["2026-01-01"].status == "tie"
    assert top["2026-01-02"].status == "field_null"


def test_succession_true_false_gap_zero_and_overtaken():
    dates = [f"2026-01-0{i}" for i in range(1, 7)]
    rows = [
        {"trade_date": dates[0], "stock_ts_code": "A", "stock_name": "A", "limit_times": 3},
        {"trade_date": dates[1], "stock_ts_code": "B", "stock_name": "B", "limit_times": 3},  # zero-gap successor
        {"trade_date": dates[2], "stock_ts_code": "B", "stock_name": "B", "limit_times": 3},
        {"trade_date": dates[2], "stock_ts_code": "A", "stock_name": "A", "limit_times": 4},  # B overtaken in day 3
        {"trade_date": dates[3], "stock_ts_code": "C", "stock_name": "C", "limit_times": 1},
        {"trade_date": dates[4], "stock_ts_code": "C", "stock_name": "C", "limit_times": 3},
    ]
    out = build_succession(dates, rows, covered_dates=dates)
    assert out["nodes"][0].status == "ok"
    assert out["nodes"][0].gap_days == 0
    assert out["nodes"][0].handoff is False
    assert out["overtaken"][0]["event_day"] == dates[2]


def test_data_gap_and_open_tail():
    dates = ["2026-01-01", "2026-01-02", "2026-01-03"]
    rows = {dates[0]: [{"stock_ts_code": "A", "limit_times": 3}], dates[1]: []}
    out = build_succession(dates, rows)
    assert out["nodes"][0].status == "unverifiable"
    assert out["nodes"][0].status_reason == "data_gap"
    rows = {dates[0]: [{"stock_ts_code": "A", "limit_times": 3}]}
    out = build_succession(dates, rows, covered_dates=[dates[0]])
    assert out["nodes"] == []  # no covered break day; source gap is not a break


def test_time_normalization_and_unknown_shape():
    assert normalize_hhmmss(92500) == "09:25"
    assert normalize_hhmmss("09:35:00") == "09:35"
    dates = ["2026-01-01", "2026-01-02", "2026-01-03"]
    rows = [
        {"trade_date": dates[0], "stock_ts_code": "A", "limit_times": 3},
        {"trade_date": dates[1], "stock_ts_code": "B", "limit_times": 1, "open_times": None, "first_limit_time": None},
        {"trade_date": dates[2], "stock_ts_code": "B", "limit_times": 3, "open_times": None, "first_limit_time": None},
    ]
    n = build_succession(dates, rows, covered_dates=dates)["nodes"][0]
    assert n.shape_tags["reseal"] == "unknown"
    assert n.shape_tags["one_word_or_instant"] == "unknown"
