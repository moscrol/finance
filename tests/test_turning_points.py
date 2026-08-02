"""共享无前视转折信号引擎的回归测试。"""

from market_feature_store.analysis.turning_points import SignalDetector


def _series(values):
    dates = [f"2026-01-{day:02d}" for day in range(1, len(values) + 1)]
    return dates, [
        {"date": date, "count": 1000, "ma5": value}
        for date, value in zip(dates, values)
    ]


def test_peak_is_emitted_on_confirmation_day():
    dates, advancers = _series([2000, 2100, 2200, 2000, 1700, 1650, 1600])
    detector = SignalDetector(ma5_min_swing=500)

    signals = detector.detect(
        [{"date": date, "volume": None} for date in dates],
        advancers,
    )

    assert [(item.date, item.type) for item in signals if "peak" in item.type] == [
        ("2026-01-05", "peak_confirmed")
    ]


def test_future_suffix_does_not_change_historical_prefix():
    values = [
        1000, 1600, 2200, 2000, 1700, 1200, 1900, 2600, 2100, 1900,
        1400, 2000, 2700, 3300, 2600, 2000, 2600, 3200, 2500, 1800,
    ]
    dates, advancers = _series(values)
    market = [{"date": date, "volume": None} for date in dates]
    detector = SignalDetector(ma5_min_swing=500)
    full = detector.detect(market, advancers)

    for length in range(1, len(dates) + 1):
        prefix = detector.detect(market[:length], advancers[:length])
        expected = [
            (item.date, item.type, item.detail)
            for item in full
            if item.date <= dates[length - 1]
        ]
        actual = [(item.date, item.type, item.detail) for item in prefix]
        assert actual == expected


def test_volume_surge_uses_previous_observed_volume():
    dates, advancers = _series([1000, 1000, 1000])
    signals = SignalDetector().detect(
        [
            {"date": dates[0], "volume": 100.0},
            {"date": dates[1], "volume": 112.0},
            {"date": dates[2], "volume": 120.0},
        ],
        advancers,
    )
    assert [(item.date, item.type) for item in signals] == [
        (dates[1], "volume_surge")
    ]
