"""Provider-contract scenarios are current-day synthetic observations.

Freeze the shared calendar clock alongside the explicit capture timestamp;
otherwise positive spot fixtures become historical as wall time advances.
"""

from datetime import date

import pytest

from market_feature_store import trading_days


@pytest.fixture(autouse=True)
def snapshot_calendar_clock(monkeypatch):
    class CalendarDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 7, 16)

    monkeypatch.setattr(trading_days, "date", CalendarDate)
    monkeypatch.delenv("L2_FORCE_TRADE_DAY", raising=False)
    monkeypatch.delenv("L2_FORCE_NON_TRADE_DAY", raising=False)
