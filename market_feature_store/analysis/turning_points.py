"""无前视的市场转折信号检测。

模块只接收已整理的市场序列，不负责数据库访问、文件写入或 CLI 输出。
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

VOLUME_SURGE_PCT = 10.0
MA5_MIN_SWING = 500


@dataclass
class Signal:
    date: str
    type: str
    detail: str
    ma5: float | None

    def __repr__(self):
        return f"Signal({self.date}, {self.type}, {self.detail})"


class SignalDetector:
    """在确认日输出放量和 MA5 峰谷信号。"""

    def __init__(
        self,
        volume_surge_pct: float = VOLUME_SURGE_PCT,
        ma5_min_swing: float = MA5_MIN_SWING,
    ):
        self.volume_surge_pct = volume_surge_pct
        self.ma5_min_swing = ma5_min_swing

    def detect(
        self,
        market_data: list[dict],
        advancers: list[dict],
    ) -> list[Signal]:
        adv_dict = {item["date"]: item for item in advancers}
        market_dict = {item["date"]: item for item in market_data}
        dates = sorted(adv_dict)
        if not dates:
            return []

        signals: list[Signal] = []
        previous_volume = None
        for date in dates:
            market = market_dict.get(date)
            if market is None or market["volume"] is None:
                if market is not None:
                    previous_volume = market["volume"]
                continue
            volume = market["volume"]
            if previous_volume and previous_volume > 0:
                change = (volume - previous_volume) / previous_volume * 100
                if change > self.volume_surge_pct:
                    signals.append(
                        Signal(
                            date=date,
                            type="volume_surge",
                            detail=f"成交额 {previous_volume:.0f}→{volume:.0f} (+{change:.1f}%)",
                            ma5=adv_dict[date].get("ma5"),
                        )
                    )
            previous_volume = volume

        pivots = self._find_pivots(adv_dict, dates)
        for date in dates:
            if date not in pivots:
                continue
            point_type, pivot_date, pivot_ma5 = pivots[date]
            label = "顶" if point_type == "peak" else "谷"
            signals.append(
                Signal(
                    date=date,
                    type=f"{point_type}_confirmed",
                    detail=f"{label}点日 {pivot_date} MA5={pivot_ma5:.0f} 于 {date} 确认",
                    ma5=adv_dict[date].get("ma5"),
                )
            )
        return self._dedup_signals(signals)

    def _find_pivots(
        self,
        advancers: dict,
        dates: list[str],
    ) -> dict[str, tuple[str, str, float]]:
        ma5_series = [
            (date, advancers[date]["ma5"])
            for date in dates
            if advancers.get(date) and advancers[date].get("ma5") is not None
        ]
        if len(ma5_series) < 2:
            return {}

        confirms: dict[str, tuple[str, str, float]] = {}
        high_date, high = ma5_series[0]
        low_date, low = ma5_series[0]
        direction = None

        for current_date, current_ma5 in ma5_series[1:]:
            if direction is None:
                if current_ma5 > high:
                    high_date, high = current_date, current_ma5
                if current_ma5 < low:
                    low_date, low = current_date, current_ma5
                if high - current_ma5 >= self.ma5_min_swing:
                    confirms[current_date] = ("peak", high_date, high)
                    direction = -1
                    low_date, low = current_date, current_ma5
                elif current_ma5 - low >= self.ma5_min_swing:
                    confirms[current_date] = ("valley", low_date, low)
                    direction = 1
                    high_date, high = current_date, current_ma5
            elif direction == 1:
                if current_ma5 > high:
                    high_date, high = current_date, current_ma5
                elif high - current_ma5 >= self.ma5_min_swing:
                    confirms[current_date] = ("peak", high_date, high)
                    direction = -1
                    low_date, low = current_date, current_ma5
            else:
                if current_ma5 < low:
                    low_date, low = current_date, current_ma5
                elif current_ma5 - low >= self.ma5_min_swing:
                    confirms[current_date] = ("valley", low_date, low)
                    direction = 1
                    high_date, high = current_date, current_ma5
        return confirms

    @staticmethod
    def _dedup_signals(signals: list[Signal]) -> list[Signal]:
        by_date: dict[str, list[Signal]] = defaultdict(list)
        for signal in signals:
            by_date[signal.date].append(signal)

        merged = []
        for date in sorted(by_date):
            items = by_date[date]
            merged.append(
                Signal(
                    date=date,
                    type="+".join(item.type for item in items),
                    detail="; ".join(item.detail for item in items),
                    ma5=items[0].ma5,
                )
            )
        return merged
