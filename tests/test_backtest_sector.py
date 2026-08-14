"""backtest_sector 的无前视（look-ahead）回归测试。

覆盖两个不变量：
1. 追加未来数据不会改变此前已发出的信号（前缀稳定性）。
2. 信号日只做确认，入场发生在次一交易日。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "backtest_sector", Path(__file__).resolve().parents[1] / "scripts" / "backtest_sector.py"
)
bs = importlib.util.module_from_spec(_SPEC)
sys.modules["backtest_sector"] = bs
_SPEC.loader.exec_module(bs)


DATES = [f"2026-01-{d:02d}" for d in range(1, 21)]


def _advancers(ma5_values):
    return [
        {"date": DATES[i], "count": 1000, "ma5": float(v)}
        for i, v in enumerate(ma5_values)
    ]


def _market(volumes):
    return [
        {"date": DATES[i], "volume": v, "volume_change": None,
         "limit_up": 0, "limit_down": 0, "week_ma": None, "deviation": None}
        for i, v in enumerate(volumes)
    ]


class TestPivotConfirmation:
    def test_peak_confirmed_on_confirmation_date_only(self):
        # MA5: 涨到 2200（第3日）后回落，第5日跌至 1700，回撤 500 ≥ 阈值 → 第5日确认峰
        ma5 = [2000, 2100, 2200, 2000, 1700, 1650, 1600]
        det = bs.SignalDetector(ma5_min_swing=500)
        signals = det.detect(_market([None] * 7), _advancers(ma5))
        pivot_signals = [s for s in signals if "peak" in s.type or "valley" in s.type]
        assert len(pivot_signals) == 1
        s = pivot_signals[0]
        assert s.type == "peak_confirmed"
        assert s.date == DATES[4]  # 确认日，而非峰值日或峰值次日
        assert DATES[2] in s.detail  # 峰值日记录在描述里

    def test_no_signal_before_confirmation(self):
        # 截止第4日回撤只有 200 < 500，不应有任何峰/谷信号
        ma5 = [2000, 2100, 2200, 2000]
        det = bs.SignalDetector(ma5_min_swing=500)
        signals = det.detect(_market([None] * 4), _advancers(ma5))
        assert [s for s in signals if "peak" in s.type or "valley" in s.type] == []

    def test_appending_future_data_never_changes_prior_signals(self):
        ma5 = [1000, 1600, 2200, 2000, 1700, 1200, 1900, 2600, 2100, 1900,
               1400, 2000, 2700, 3300, 2600, 2000, 2600, 3200, 2500, 1800]
        det = bs.SignalDetector(ma5_min_swing=500)
        market = _market([None] * len(ma5))

        full = det.detect(market, _advancers(ma5))
        for k in range(1, len(ma5) + 1):
            prefix_signals = det.detect(market[:k], _advancers(ma5[:k]))
            cutoff = DATES[k - 1]
            expected = [(s.date, s.type, s.detail) for s in full if s.date <= cutoff]
            got = [(s.date, s.type, s.detail) for s in prefix_signals]
            assert got == expected, f"prefix len={k}: {got} != {expected}"


class FakeProvider:
    """内存版 SectorDataProvider，构造确定性的回测场景。"""

    def __init__(self, dates, sector_rows, market, advancers):
        self._dates = dates
        self._sector_rows = sector_rows  # {date: {ts_code: (sector, diff_ratio, pct_chg, amount)}}
        self._market = market
        self._advancers = advancers

    def get_sector_price_matrix(self, start, end):
        return {
            d: {code: row[2] for code, row in rows.items() if row[2] is not None}
            for d, rows in self._sector_rows.items()
            if start <= d <= end
        }

    def get_sector_marginal(self, date):
        rows = self._sector_rows.get(date, {})
        return {
            code: {"sector": row[0], "diff_ratio": row[1],
                   "pct_chg": row[2], "amount": row[3]}
            for code, row in rows.items()
        }

    def get_market_data(self, start, end):
        return [m for m in self._market if start <= m["date"] <= end]

    def get_advancers(self, start, end):
        return [a for a in self._advancers if start <= a["date"] <= end]

    def get_trading_dates(self, start, end):
        return [d for d in self._dates if start <= d <= end]

    def close(self):
        pass


class TestNextDayEntry:
    def _run(self, n_days=6, surge_day=1, hold_days=1):
        dates = DATES[:n_days]
        sector_rows = {
            d: {"885001.TI": ("测试板块", 20.0, 1.0, 100.0)}
            for d in dates
        }
        volumes = [100.0] * n_days
        volumes[surge_day] = 120.0  # 放量 +20% → 信号
        market = _market(volumes)[:n_days]
        advancers = _advancers([1000] * n_days)  # MA5 走平，无峰谷信号
        provider = FakeProvider(dates, sector_rows, market, advancers)
        engine = bs.SectorBacktestEngine(
            top_n=1, hold_days=hold_days, min_marginal=10.0, provider=provider,
        )
        return engine.run(dates[0], dates[-1]), dates

    def test_entry_is_next_trading_day_after_signal(self):
        result, dates = self._run(surge_day=1, hold_days=1)
        assert result.n_trades == 1
        trade = result.trades[0]
        signal_date = dates[1]
        assert trade.entry_date == dates[2], "入场必须在信号日的次一交易日"
        assert trade.entry_date > signal_date
        assert trade.exit_date == dates[3]
        assert trade.holding_days == 1

    def test_signal_on_last_day_produces_no_trade(self):
        # 信号在最后一日 → 次日入场日不存在 → 不建仓
        result, _ = self._run(n_days=4, surge_day=3, hold_days=1)
        assert result.n_trades == 0
