"""双红时间轴证据写明金额阈值单位与窗口计数（2026-09-25 L6-T3 数字门误删）。"""

from intelligence.services.asof_prefetch import (
    format_dual_red_counts,
    format_sector_timeline,
    sector_timeline_observations,
)

WINDOW = {"sector_name": "低空经济", "start": "2026-09-14", "end": "2026-09-18"}
ROWS = [
    {"trade_date": "2026-09-11", "pct_chg": 2.0, "amount": 900.0, "diff_ratio": 30.0},  # 窗外
    {"trade_date": "2026-09-14", "pct_chg": 0.4, "amount": 620.5, "diff_ratio": 12.5},  # 双红
    {"trade_date": "2026-09-15", "pct_chg": -0.3, "amount": 480.2, "diff_ratio": 3.2},
    {"trade_date": "2026-09-16", "pct_chg": 1.2, "amount": 655.1, "diff_ratio": 15.4},  # 双红
    # 同日两行互相矛盾：口径分歧，该日不作为证据，也不计数。
    {"trade_date": "2026-09-17", "pct_chg": 0.8, "amount": 610.0, "diff_ratio": 11.2},
    {"trade_date": "2026-09-17", "pct_chg": 0.9, "amount": 612.0, "diff_ratio": 11.9},
    {"trade_date": "2026-09-18", "pct_chg": -1.1, "amount": 530.6, "diff_ratio": -4.4},
]


def test_timeline_header_states_amount_unit_and_counts_usable_days_only() -> None:
    header = format_sector_timeline(ROWS, **WINDOW).splitlines()[0]
    assert "amount>500，amount 单位为亿（即 500亿）" in header
    # 窗口内 5 个交易日，09-17 口径分歧不计 → 4 天；其中双红 2 天（09-14、09-16）。
    assert header.endswith("交易日数=4；双红天数=2")


def _counts(observations):
    return {obs.metric: obs for obs in observations if obs.metric in {"trading_days", "double_red_days"}}


def test_timeline_observations_carry_counts_on_last_usable_day() -> None:
    observations = sector_timeline_observations(ROWS, **WINDOW)
    counts = _counts(observations)
    assert counts["trading_days"].value == 4.0 and counts["double_red_days"].value == 2.0
    assert {obs.as_of for obs in counts.values()} == {"2026-09-18"}
    assert {obs.subject for obs in counts.values()} == {"低空经济"}
    # 逐格观察值不变：分歧日的格子仍不产出。
    assert not [obs for obs in observations if obs.as_of == "2026-09-17"]


def test_counts_never_dated_on_a_divergent_last_day() -> None:
    """窗口最后一天是口径分歧日时，计数记在前一个可用交易日上，分歧日仍零观察值。"""

    rows = [row for row in ROWS if row["trade_date"] != "2026-09-18"]
    observations = sector_timeline_observations(rows, **{**WINDOW, "end": "2026-09-17"})
    counts = _counts(observations)
    assert counts["trading_days"].value == 3.0 and counts["double_red_days"].value == 2.0
    assert {obs.as_of for obs in counts.values()} == {"2026-09-16"}
    assert not [obs for obs in observations if obs.as_of == "2026-09-17"]


def test_no_rows_means_no_count_observations_and_unchanged_empty_message() -> None:
    assert not [
        obs
        for obs in sector_timeline_observations([], **WINDOW)
        if obs.metric in {"trading_days", "double_red_days"}
    ]
    assert format_sector_timeline([], **WINDOW).startswith("未锚定板块逐日行：低空经济")


def test_dual_red_count_item_shares_the_unit_note() -> None:
    assert "amount 单位为亿（即 500亿）" in format_dual_red_counts({"2026-09-18": "3"})
