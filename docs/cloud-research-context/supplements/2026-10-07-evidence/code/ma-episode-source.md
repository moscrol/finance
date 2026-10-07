# 周均同侧腿的实现

- 材料身份：代码摘录
- 本机正文核验：2026-10-07；未在线重新核验。
- 来源：`intelligence/services/teaching_framework/flags.py`
- 定位与指纹：见 `sources/index.json` 中 `code/ma-episode-source.md`。
- 下方为连续原文摘录；其中的历史统计、agent 落法与用户引语保留原身份，不是本次实测或新增指令。

<!-- BEGIN VERBATIM EXCERPT -->
    @staticmethod
    def _unknown() -> dict[str, Any]:
        return {name: None for name in EPISODE_FIELDS}

    def step(
        self,
        above: bool | None,
        dev: float | None,
        *,
        adjacent: bool,
        close: float | None,
        prev_close: float | None,
        high: float | None,
        low: float | None,
        surge: bool | None,
    ) -> dict[str, Any]:
        if above is None or dev is None or not adjacent:
            # Unknown side or a break in the calendar: the run cannot be continued or started.
            self._reset()
            if above is not None and dev is not None and not adjacent:
                # We can see today's side but not whether a cross happened: mid-run, unanchored.
                self.side = above
            return self._unknown()
        cross_below_kind: str | None = None
        if self.side is None or above != self.side:
            # Side changed relative to the previous known day: a cross was observed today,
            # unless we had no previous side at all (first row) — then the run is unanchored.
            anchored_now = self.side is not None
            if anchored_now and not above:
                # Crossing below.  The above run just ended: was it a residual excursion?
                residual = self.anchored and self.day <= self.confirm_days and not self.surge_seen
                if residual and self.cycle_day is not None:
                    cross_below_kind = "retest"
                    self.cycle_day += 1
                    self.cycle_retest_seen = True
                else:
                    cross_below_kind = "first"
                    self.cycle_day = 1
                    self.cycle_retest_seen = False
            elif anchored_now and above:
                # Crossing above: the cycle is pending until this run confirms or fades.
                if self.cycle_day is not None:
                    self.cycle_day += 1
            else:
                self.cycle_day = None
                self.cycle_retest_seen = False
            self.side, self.day, self.extreme, self.retrace_peak, self.anchored = above, 1, dev, 0.0, anchored_now
            self.base_close, self.max_high, self.min_low = prev_close, high, low
            self.hl_complete = high is not None and low is not None
            self.days_since_high, self.surge_seen = 0, surge is True
        else:
            self.day += 1
            if self.extreme is None:
                self.extreme = dev
            elif (not above and dev < self.extreme) or (above and dev > self.extreme):
                self.extreme = dev
            if high is None or low is None:
                self.hl_complete = False
            else:
                if self.max_high is None or high > self.max_high:
                    self.max_high, self.days_since_high = high, 0
                else:
                    self.days_since_high += 1
                if self.min_low is None or low < self.min_low:
                    self.min_low = low
            if surge is True:
                self.surge_seen = True
            if self.cycle_day is not None:
                self.cycle_day += 1
        if above and self.cycle_day is not None and (self.surge_seen or self.day > self.confirm_days):
            # A real above-MA leg (volume, or outlived the tolerance): the below cycle is over.
            self.cycle_day = None
            self.cycle_retest_seen = False
        if not self.anchored or self.extreme is None:
            return self._unknown()
        retrace = (dev - self.extreme) if not above else (self.extreme - dev)
        self.retrace_peak = max(self.retrace_peak, retrace)
        base_ok = self.base_close is not None and self.base_close > 0 and close is not None
        return {
            "ma_episode_day": self.day,
            "ma_episode_extreme_dev": round(self.extreme, SCALAR_DECIMALS),
            "ma_episode_retrace_pts": round(retrace, SCALAR_DECIMALS),
            "ma_episode_retrace_peak_pts": round(self.retrace_peak, SCALAR_DECIMALS),
            "ma_episode_pct_chg": round((close / self.base_close - 1) * 100, SCALAR_DECIMALS) if base_ok else None,
            "ma_episode_amplitude": (
                round((self.max_high - self.min_low) / self.base_close * 100, SCALAR_DECIMALS)
                if base_ok and self.hl_complete and self.max_high is not None and self.min_low is not None
                else None
            ),
            "ma_episode_days_since_high": self.days_since_high if self.hl_complete else None,
            "days_since_cross_above": (self.day - 1) if above else None,
            "cross_below_kind": cross_below_kind,
            "below_ma_cycle_day": self.cycle_day,
            # Inside a below-MA cycle: has the 回踩探底 (retest cross below) happened yet?
<!-- END VERBATIM EXCERPT -->
