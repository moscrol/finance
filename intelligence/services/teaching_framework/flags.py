"""Pure, fail-closed market flag and scalar calculations for teaching framework."""

from __future__ import annotations

import math
from datetime import date, datetime, time
from typing import Any, Iterable, Mapping

from .coverage import collapse_limit_rows

NULL = None

# Source values copied next to the teaching flags for context and contingency
# tables.  They are written under the ``src.`` namespace, never ``tf.``: the
# supplier's ``market_stage`` must stay distinguishable from ``tf.stage_coarse``.
# The raw 环比 and 偏离度 ride along so a reader sees the number, not only the
# band or threshold verdict derived from it (创始人 09-07：都是分析视角).
SOURCE_PASSTHROUGH = (
    "market_stage",
    "volume_state",
    "ice_point",
    "sh_week_ma_source",
    "total_amount",
    "amount_vs_yesterday_pct",
    "sh_deviation_pct",
    "sh_index_close",
    "limit_up",
    "advancers",
    # 创始人 09-08：校准的靶子看赚钱 / 亏钱效应和资金——「成交占比前三、加权涨幅」两个供应商原值随行写出，
    # 供 stage_separation 读数用；此前只在派生旗标里用到，没有单独落列。
    "top3_industry_ratio",
    "strength_avg_pct",
)
SOURCE_PREFIX = "src."


def _date(v: Any) -> Any:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v)[:10]) if v is not None else None


def _num(v: Any) -> float | None:
    if v is None:
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _bool_cmp(a: Any, op: str, b: Any) -> bool | None:
    x, y = _num(a), _num(b)
    if x is None or y is None:
        return None
    return {"gt": x > y, "ge": x >= y, "lt": x < y, "le": x <= y, "eq": x == y}[op]


def _prev(
    rows: list[Mapping[str, Any]], i: int, calendar_index: Mapping[Any, int] | None
) -> Mapping[str, Any] | None:
    """Previous row only when it is the adjacent calendar day; otherwise unknown."""
    if i <= 0:
        return None
    prev = rows[i - 1]
    if calendar_index is None:
        return prev
    cur_i = calendar_index.get(_date(rows[i].get("trade_date")))
    prev_i = calendar_index.get(_date(prev.get("trade_date")))
    return prev if cur_i is not None and prev_i is not None and cur_i - prev_i == 1 else None


def normalize_hhmm(value: Any) -> time | None:
    """Normalize HHMM/HHMMSS/HH:MM/HH:MM:SS values; malformed stays unknown."""
    if value is None:
        return None
    if isinstance(value, time):
        return value
    s = str(value).strip()
    if not s:
        return None
    if ":" in s:
        parts = s.split(":")
        try:
            return time(
                int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0
            )
        except (ValueError, IndexError):
            return None
    if s.isdigit():
        try:
            n = int(s)
            if len(s) <= 4:
                return time(n // 100, n % 100)
            return time(n // 10000, (n // 100) % 100, n % 100)
        except ValueError:
            return None
    return None


def _dedupe_rows(
    rows: Iterable[Mapping[str, Any]], identity_keys: tuple[str, ...]
) -> dict[tuple[Any, str], Mapping[str, Any]]:
    """Collapse duplicate source rows by date and the first available identity key."""
    out: dict[tuple[Any, str], Mapping[str, Any]] = {}
    for row in rows:
        d = _date(row.get("trade_date"))
        ident = next(
            (row.get(k) for k in identity_keys if row.get(k) is not None), None
        )
        if d is None or ident is None:
            continue
        out.setdefault((d, str(ident)), row)
    return out


def compute_flags(
    rows: Iterable[Mapping[str, Any]],
    *,
    calendar: Iterable[Any] | None = None,
    vendor_rows: Iterable[Mapping[str, Any]] | None = None,
    stock_rows: Iterable[Mapping[str, Any]] | None = None,
    amount_rows: Iterable[Mapping[str, Any]] | None = None,
    breadth_rows: Iterable[Mapping[str, Any]] | None = None,
    sector_rows: Iterable[Mapping[str, Any]] | None = None,
    params: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Compute all A flags plus B scalars. Rows must represent fact_market_daily.

    Missing previous calendar day or any required NULL yields NULL; no false is
    inferred.  B scalars that cannot be computed are NULL with the reason kept in
    ``scalar_gaps`` so the caller can write gap rows instead of silently skipping.
    ``breadth_rows`` are per-day aggregates over ``fact_stock_daily`` (see
    ``BREADTH_FIELDS``); they carry the founder's 「整体的水位」 views.
    """
    p = params or {}
    bands = p.get("deviation_bands", {})
    over_le = float(bands.get("oversold_le", -2.5))
    hot_ge = float(bands.get("overheated_ge", 1.5))
    top_n = int(p.get("top100_n", 100))
    breadth_floor = int(p.get("breadth_min_stocks", 4000))
    # 量能三档的尺子（创始人 2026-09-07 第十段：「20 日均量，量能比吧」）：当日成交额 /
    # 20 日均量 × 100，与复盘会同一口径。「100–120 属于温和放量」「20 是一个阈值」落在
    # 这把尺子上：< 100 缩量 · 100–120 温和放量 · > 120 暴量。回测层的 ``volume_surge``
    # 标签（环比 > 10）是另一个对象，这里不复用；环比本身仍以 ``src.`` 旁列写出。
    level_cfg = p.get("volume_level") or {}
    surge_threshold = float(level_cfg.get("surge_from_pct", 120))
    moderate_from = float(level_cfg.get("moderate_from_pct", 100))
    breadth_by_day = {
        _date(row.get("trade_date")): row for row in (breadth_rows or []) if row.get("trade_date") is not None
    }
    sector_by_day = {
        _date(row.get("trade_date")): row for row in (sector_rows or []) if row.get("trade_date") is not None
    }
    rows = sorted((dict(r) for r in rows), key=lambda r: _date(r.get("trade_date")))
    cal_index = (
        {_date(x): n for n, x in enumerate(calendar)} if calendar is not None else None
    )
    vendor = _dedupe_rows(
        vendor_rows or [], identity_keys=("sector_ts_code", "sector", "stock_ts_code")
    )
    # The limit table is collapsed with the same policy the succession builder
    # uses, so ``tf.max_boards`` and ``top(d)`` can never disagree on a stock-day.
    stock_by_day = collapse_limit_rows(stock_rows or [])
    amounts = _dedupe_rows(
        amount_rows or [], identity_keys=("stock_ts_code", "stock", "ts_code", "code")
    )
    amount_values_by_day: dict[Any, list[float]] = {}
    for (amount_day, _), amount_row in amounts.items():
        amount_value = _num(amount_row.get("amount"))
        if amount_value is not None:
            amount_values_by_day.setdefault(amount_day, []).append(amount_value)
    vendor_by_day: dict[Any, list[Mapping[str, Any]]] = {}
    for (d, _), r in vendor.items():
        vendor_by_day.setdefault(d, []).append(r)
    out: list[dict[str, Any]] = []
    streak = 0
    dev_streaks = _DeviationStreaks()
    episode = _MaSideEpisode(int(p.get("breakout_confirm_days", 3)))
    range_windows = [int(n) for n in (p.get("index_range_windows") or DEFAULT_RANGE_WINDOWS)]
    new_high_windows = [int(n) for n in (p.get("index_new_high_windows") or DEFAULT_NEW_HIGH_WINDOWS)]
    double_volume_dod = float(p.get("double_volume_dod_pct", DOUBLE_VOLUME_DOD_PCT))
    money_losing_lt = float((p.get("money_losing") or {}).get("lt_pct", DEFAULT_MONEY_LOSING["lt_pct"]))
    losing_streak = 0
    for i, row in enumerate(rows):
        prev = _prev(rows, i, cal_index)
        d = _date(row.get("trade_date"))
        rec: dict[str, Any] = {"trade_date": d, "scalar_gaps": {}}
        for passthrough in SOURCE_PASSTHROUGH:
            rec[f"{SOURCE_PREFIX}{passthrough}"] = row.get(passthrough)
        close, ma = _num(row.get("sh_index_close")), _num(row.get("sh_week_ma"))
        rec["above_week_ma"] = None if close is None or ma is None else close > ma
        rec["cross_above_week_ma"] = (
            None if prev is None else _cross(prev, row, "above")
        )
        rec["cross_below_week_ma"] = (
            None if prev is None else _cross(prev, row, "below")
        )
        op, pc = (
            _num(row.get("sh_index_open")),
            _num(prev.get("sh_index_close")) if prev else None,
        )
        rec["gap_down_open"] = None if op is None or pc is None else op < pc
        # 第十三段「跳空低开跌破周均」：低开本身在下穿日里是常态（真库 53 次下穿 38 次低开），有区别的是
        # 开盘就已经在周均线之下——缺口本身穿过了周均线。作旗标写出，供事件回溯与 ``left_down_entry`` 可选读法用。
        rec["open_below_week_ma"] = None if op is None or ma is None else op < ma
        # 创始人 09-07 第六段：「上穿周均线往往就伴随放量和指数的阳线」——阳线只是一个视角。
        rec["up_candle"] = None if op is None or close is None else close > op
        amount, ma20 = _num(row.get("total_amount")), _num(row.get("amount_ma20"))
        rec["shrink_day"] = None if amount is None or ma20 is None else amount < ma20
        if rec["shrink_day"] is None:
            streak = 0
            rec["volume_shrink_streak"] = None
        elif rec["shrink_day"]:
            streak += 1
            rec["volume_shrink_streak"] = streak
        else:
            streak = 0
            rec["volume_shrink_streak"] = 0
        dev = _num(row.get("sh_deviation_pct"))
        rec["deviation_band"] = _band(dev, over_le, hot_ge)
        prev_dev = _num(prev.get("sh_deviation_pct")) if prev else None
        rec["deviation_narrowing"] = (
            None
            if dev is None or prev_dev is None or rec["above_week_ma"] is None
            else (rec["above_week_ma"] is False and dev > prev_dev)
        )
        rec.update(dev_streaks.step(dev, prev_dev))
        ratio_pct = None if amount is None or ma20 is None or ma20 <= 0 else round(amount / ma20 * 100, SCALAR_DECIMALS)
        rec["amount_vs_ma20_pct"] = ratio_pct
        rec["volume_band"] = _volume_band(ratio_pct, moderate_from, surge_threshold)
        rec["volume_surge"] = None if ratio_pct is None else ratio_pct > surge_threshold
        # 「放量」= 至少温和放量（量能比 ≥ 100）：突破确认与残差判断都用它；暴量另有 volume_surge。
        rec["volume_expanding"] = None if ratio_pct is None else ratio_pct >= moderate_from
        rec.update(
            episode.step(
                rec["above_week_ma"], dev, adjacent=prev is not None, close=close, prev_close=pc,
                high=_num(row.get("sh_index_high")), low=_num(row.get("sh_index_low")), surge=rec["volume_expanding"],
            )
        )
        # 趋势中暴量：周均线上方、突破窗口之外的量能比 > 120。创始人第八段：是个双向因子，
        # 「有好有坏，出现的时候需要特殊情况特殊分析」——只写出，不计分，收据回溯其后走势。
        since_cross = rec["days_since_cross_above"]
        if rec["above_week_ma"] is None or rec["volume_surge"] is None:
            rec["surge_in_trend"] = None
        else:
            in_window = isinstance(since_cross, (int, float)) and since_cross <= episode.confirm_days
            rec["surge_in_trend"] = bool(rec["above_week_ma"] and rec["volume_surge"] and not in_window)
        top3, prev_top3 = (
            _num(row.get("top3_industry_ratio")),
            _num(prev.get("top3_industry_ratio")) if prev else None,
        )
        rec["mainline_share_expanding.volume_top3"] = (
            None if top3 is None or prev_top3 is None else top3 > prev_top3
        )
        rec["mainline_share_expanding.vendor"] = _vendor_share(
            vendor_by_day,
            d,
            row,
            prev,
            vendor_by_day.get(_date(prev.get("trade_date")) if prev else None),
        )
        rec["mainline_amount_stepping_up.volume_top3"] = _rising_top3_streak(
            rows, i, int(p.get("mainline_amount_stepping_up_days", 3)), cal_index
        )
        rec["mainline_amount_stepping_up.vendor"] = _vendor_rising(
            vendor_by_day,
            d,
            int(p.get("mainline_amount_stepping_up_days", 3)),
            rows,
            i,
        )
        # 创始人 09-08 第十九段：「共建主线到主流主升，就是成交占比不断放大，量能也逐步放大的过程，不是按日期看，
        # 一个阶段中单日的成交可能会有小缩量」→ 用窗口均值比窗口均值（近 n 日均 vs 再前 n 日均），单日缩量不翻它。
        # 三条：成交占比前三的均值在升、成交额的均值在升、两者相乘（主流板块自己的成交额）的均值在升。n 是 B 类候选。
        trend_n = int(p.get("upgrade_trend_window", UPGRADE_TREND_WINDOW))
        rec["mainline_share_trend_up"] = _window_mean_up(rows, i, trend_n, cal_index, lambda r: _num(r.get("top3_industry_ratio")))
        rec["volume_trend_up"] = _window_mean_up(rows, i, trend_n, cal_index, lambda r: _num(r.get("total_amount")))
        rec["mainline_amount_trend_up"] = _window_mean_up(
            rows, i, trend_n, cal_index,
            lambda r: (None if _num(r.get("total_amount")) is None or _num(r.get("top3_industry_ratio")) is None
                       else _num(r.get("total_amount")) * _num(r.get("top3_industry_ratio"))),
        )
        # B scalars
        day_stocks = stock_by_day.get(d.isoformat(), ()) if d is not None else ()
        prev_stocks = (
            stock_by_day.get(_date(prev.get("trade_date")).isoformat(), ())
            if prev is not None
            else ()
        )
        rec["max_boards"] = _scalar_max(day_stocks, "limit_times")
        if rec["max_boards"] is None:
            rec["scalar_gaps"]["max_boards"] = "limit_rows_absent"
        rec["promotion_rate_total"], reason = _promotion(day_stocks, prev_stocks)
        if reason:
            rec["scalar_gaps"]["promotion_rate_total"] = reason
        rec["top100_amount_share"], reason = _top100_share(
            d, row, amount_values_by_day, top_n
        )
        if reason:
            rec["scalar_gaps"]["top100_amount_share"] = reason
        for label, value, reason in _breadth_scalars(breadth_by_day.get(d), breadth_floor):
            rec[label] = value
            if reason:
                rec["scalar_gaps"][label] = reason
        rec["stock_up_ratio_ma5_pct"], reason = _up_ratio_ma(rows, i, cal_index, breadth_by_day, breadth_floor, UP_RATIO_MA_DAYS)
        if reason:
            rec["scalar_gaps"]["stock_up_ratio_ma5_pct"] = reason
        for label, value, reason in _sector_scalars(sector_by_day.get(d)):
            rec[label] = value
            if reason:
                rec["scalar_gaps"][label] = reason
        for label, value, reason in _index_range_scalars(rows, i, cal_index, range_windows):
            rec[label] = value
            if reason:
                rec["scalar_gaps"][label] = reason
        rec.update(_range_structure_flags(rows, i, cal_index, range_windows))
        rec.update(_index_new_high_flags(rows, i, cal_index, new_high_windows))
        # 双量日（每日复盘 `market_feature_store/reports/daily_review.py::_market_label` 的既有口径）：成交额环比
        # > 10% 且量能比 > 120。创始人 09-07 第十一段：「升级 2.0，大概率是进一步放量指数进一步走强」——
        # 「进一步放量」用这条既有尺子，「进一步走强」用 index_new_high_*d。
        dod = _num(row.get("amount_vs_yesterday_pct"))
        rec["double_volume_day"] = (
            None if dod is None or rec["volume_surge"] is None else bool(dod > double_volume_dod and rec["volume_surge"])
        )
        # 亏钱效应日（创始人 09-07 第十四段「亏钱效应也要可量」）：承接 5 日均值（昨日涨停股今日平均涨幅的 5 日均）低于
        # 门槛——打板的钱连 1% 都拿不到。九个候选口径里只有承接这一维在训练 / 验证两期都把底部四段与顶部三段分开
        # （< 1.0：15.8% vs 5.1% / 27.8% vs 8.5%，主升与 2.0 两段 0%）；5 日上涨比例低于分位在验证期分不开（2026 的
        # 窄行情顶部宽度也低）。门槛取训练期 p10（1.045）取整，进参数文件 ``money_losing``。
        premium_ma5 = rec.get("limit_premium_ma5_pct")
        rec["money_losing_day"] = None if premium_ma5 is None else bool(premium_ma5 < money_losing_lt)
        if rec["money_losing_day"] is None:
            losing_streak = 0
            rec["money_losing_streak"] = None
        elif rec["money_losing_day"]:
            losing_streak += 1
            rec["money_losing_streak"] = losing_streak
        else:
            losing_streak = 0
            rec["money_losing_streak"] = 0
        out.append(rec)
    return out


def _volume_band(ratio_pct: float | None, moderate_from: float, surge_threshold: float) -> str | None:
    """量能比（当日 / 20 日均量 × 100）分三档：shrink (< moderate_from) / moderate [moderate_from, threshold] / surge (> threshold).

    创始人 2026-09-07：「100–120 属于温和放量」「超过 20 很可能盛极而衰」，第十段定尺子为
    「20 日均量，量能比」——即 100–120 温和放量、> 120 暴量。低于 100 的一档叫 ``shrink``
    是 agent 起的名（复盘会在这一档里再分 85–100 抱团 / 60–85 强势抱团与冰点规则）。
    """
    if ratio_pct is None:
        return None
    if ratio_pct < moderate_from:
        return "shrink"
    if ratio_pct <= surge_threshold:
        return "moderate"
    return "surge"


class _DeviationStreaks:
    """Consecutive-day runs of the weekly-MA deviation: rising, falling, and moving toward the MA.

    创始人 09-07 第六段：「偏离度的变化就是和周均线的偏离度，比如说偏离度持续走高，或者说
    回归周均，或者说逐渐走低」。The three runs are the founder's three words; how many days
    make 「持续」 is a B 类 number applied later, so only counts are written here.  A NULL
    deviation or a non-adjacent previous day resets every run to unknown.
    """

    def __init__(self) -> None:
        self.rising = 0
        self.falling = 0
        self.toward = 0

    def step(self, dev: float | None, prev_dev: float | None) -> dict[str, int | None]:
        if dev is None or prev_dev is None:
            self.rising = self.falling = self.toward = 0
            return {"deviation_rising_streak": None, "deviation_falling_streak": None, "deviation_toward_ma_streak": None}
        self.rising = self.rising + 1 if dev > prev_dev else 0
        self.falling = self.falling + 1 if dev < prev_dev else 0
        self.toward = self.toward + 1 if abs(dev) < abs(prev_dev) else 0
        return {
            "deviation_rising_streak": self.rising,
            "deviation_falling_streak": self.falling,
            "deviation_toward_ma_streak": self.toward,
        }


EPISODE_FIELDS = (
    "ma_episode_day",
    "ma_episode_extreme_dev",
    "ma_episode_retrace_pts",
    "ma_episode_retrace_peak_pts",
    "ma_episode_pct_chg",
    "ma_episode_amplitude",
    "ma_episode_days_since_high",
    "days_since_cross_above",
    "cross_below_kind",
    "below_ma_cycle_day",
    "below_ma_cycle_retest_seen",
)


class _MaSideEpisode:
    """Structure of the current run of days on one side of the weekly MA, and the below-MA cycle.

    创始人 09-07 第六 / 七段 describe the below-MA flow as 下穿 → 探底 → 反弹到周均线（「一般都会
    触碰一下周均」）→ 回踩探底 → 放量上穿, with 「数据的残差」 in between, and say a cross above
    only counts as a turn when volume expands on the cross day or within ``confirm_days`` after
    it (「上穿要配合放量，不然很多上穿基本都是回落」).  Per day this writes:

    * the run's day index, extreme deviation, retrace from the extreme and retrace peak
      (a retrace now smaller than its peak is the 「又回踩」);
    * the run's index gain and amplitude against the close of the day before the cross —
      「那一个区间就是」: the founder's 区间 is the leg, not a fixed window;
    * days since the run's highest high (「高点不抬高」 reads as this staying > 0);
    * ``days_since_cross_above`` (0 on the cross day) so 「上穿后三天内放量」 is a predicate
      over today's inputs only;
    * ``cross_below_kind``: ``first`` when the cross below starts a cycle, ``retest`` when the
      above-MA excursion before it was a residual — it lasted at most ``confirm_days`` days
      and never saw a surge — so the touch of the MA was the 反弹, not a turn;
    * ``below_ma_cycle_day``: days since the cycle's first cross below, counted through
      residual excursions; it ends (NULL) once an above-MA run surges or outlives
      ``confirm_days`` without falling back.

    Everything is anchored at an observed cross; a run whose start was never seen (history
    begins mid-run, or a gap day) is unknown, never guessed.  The residual tolerance
    (= ``confirm_days``, no surge) is an agent reading of 「残差」 and is flagged as such.
    """

    def __init__(self, confirm_days: int = 3) -> None:
        self.confirm_days = int(confirm_days)
        self.side: bool | None = None
        self.day = 0
        self.extreme: float | None = None
        self.retrace_peak = 0.0
        self.anchored = False
        self.base_close: float | None = None
        self.max_high: float | None = None
        self.min_low: float | None = None
        self.hl_complete = True
        self.days_since_high = 0
        self.surge_seen = False
        self.cycle_day: int | None = None
        self.cycle_retest_seen = False

    def _reset(self) -> None:
        self.side, self.day, self.extreme, self.retrace_peak, self.anchored = None, 0, None, 0.0, False
        self.base_close = self.max_high = self.min_low = None
        self.hl_complete, self.days_since_high, self.surge_seen = True, 0, False
        self.cycle_day = None
        self.cycle_retest_seen = False

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
            "below_ma_cycle_retest_seen": (self.cycle_retest_seen if self.cycle_day is not None else None),
        }


# Per-day aggregates over ``fact_stock_daily`` that the CLI computes in SQL.
# 创始人 2026-09-07：「整体的水位就是市场涨幅中位数，或者 MA5、MA10 的偏离度……平均股价也可以」。
# (label, source field, count field that must clear ``breadth_min_stocks``)
BREADTH_FIELDS = (
    ("stock_pct_chg_median", "pct_chg_median", "stock_count"),
    ("stock_price_mean", "price_mean", "stock_count"),
    ("stock_ma5_deviation_median", "ma5_deviation_median", "ma5_count"),
    ("stock_ma10_deviation_median", "ma10_deviation_median", "ma10_count"),
    # 复盘会「情绪均值回归」的原料：当日上涨家数占比；其 5 日均值另算（UP_RATIO_MA_DAYS）。
    ("stock_up_ratio_pct", "up_ratio_pct", "stock_count"),
)
UP_RATIO_MA_DAYS = 5


# Market-level aggregates of the sector side, one row per day (the CLI computes them in SQL).
# 创始人 09-07 第六段：「向下左底和缩量右底，和成交占比前三板块主流板块是一体两面的，还有市场的
# 赚钱效应也是相关的」。Against the platform's daily stages, two of these separate the top range
# from the bottom range where every index view fails: 1-year-plus new highs (高位震荡 median 176
# vs 缩量右底 60 / 共建主线 119) and 严格双红 theme count (共建主线 15 / 缩量右底 13 vs 高位震荡 5).
# (label, source field)
SECTOR_FIELDS = (
    ("new_high_1y_count", "new_high_1y_count"),
    ("dual_red_theme_count", "dual_red_theme_count"),
    ("limit_themes_ge3", "limit_themes_ge3"),
    ("limit_top1_share_pct", "limit_top1_share_pct"),
    # 5 日涨幅前 10 的板块里落在成交占比前三申万一级之外的比例（创始人第五段的「赚钱效应不在成交
    # 占比前三」；候选规则在此定义下 supported：下方 59.6% vs 上方 45.6%）。
    ("rps5_outside_top3_pct", "rps5_outside_top3_pct"),
    # 题材层「先量再建」第二轮：双红题材散布的申万一级数；涨停领涨集合与 5 日前的 Jaccard（领涨题材持续度）。
    ("dual_red_l1_distinct", "dual_red_l1_distinct"),
    ("limit_top10_persist_5d_pct", "limit_top10_persist_5d_pct"),
    # 承接：昨日涨停股今日平均涨幅及其 5 日均值 / 负溢价天数 / 正负翻转次数（平台「承接盘反复」的字面对象）。
    ("limit_premium_pct", "limit_premium_pct"),
    ("limit_premium_ma5_pct", "limit_premium_ma5_pct"),
    ("limit_premium_neg_5d", "limit_premium_neg_5d"),
    ("limit_premium_flips_5d", "limit_premium_flips_5d"),
    # 区间涨幅高标的门槛：当日 20 / 60 日涨幅榜第 top 名的涨幅（第八段「涨幅多少算多，是基于历史行情去对比的」）。
    ("range_leader_entry_gain_20d_pct", "range_leader_entry_gain_20d_pct"),
    ("range_leader_entry_gain_60d_pct", "range_leader_entry_gain_60d_pct"),
    # 板块涨幅（创始人 09-08 校准靶子的一项）：当日全部板块涨幅的中位数与上涨比例。只写出。
    ("sector_pct_chg_median", "sector_pct_chg_median"),
    ("sector_up_ratio_pct", "sector_up_ratio_pct"),
    # 资金面（第十五段）市场级视角，全部只写出：龙虎榜净买入（亿 / 占全市场成交‰ / 买盘卖盘比，各带 5 日均）、
    # 涨停封单（中位万元 / 封单占流通市值中位 / 厚封单占比）、昨日涨停股竞价（涨幅中位 / 为正比例 / 竞价成交额）。
    # 先量（骨架 §8.15）：只有龙虎榜的两条 5 日均在训练 / 验证两期都把底部与顶部分开，进带区的实验读数见同节。
    ("dragon_count", "dragon_count"),
    ("dragon_net_amount", "dragon_net_amount"),
    ("dragon_net_amount_ratio_pm", "dragon_net_amount_ratio_pm"),
    ("dragon_net_amount_ratio_pm_ma5", "dragon_net_amount_ratio_pm_ma5"),
    ("dragon_buy_sell_ratio", "dragon_buy_sell_ratio"),
    ("dragon_buy_sell_ratio_ma5", "dragon_buy_sell_ratio_ma5"),
    ("limit_seal_amount_median_wan", "limit_seal_amount_median_wan"),
    ("limit_seal_mv_ratio_median", "limit_seal_mv_ratio_median"),
    ("limit_thick_seal_share_pct", "limit_thick_seal_share_pct"),
    ("auction_zt_pct_median", "auction_zt_pct_median"),
    ("auction_zt_positive_share_pct", "auction_zt_positive_share_pct"),
    ("auction_zt_amount", "auction_zt_amount"),
    # 消息面（第十六段）：知识库卖方观点事件聚成的市场级叙事读数（``teaching_framework/narrative.py``），只写出。
    # 没给知识库 → 缺口 narrative_source_absent；源断更 → narrative_stale；都不是 0。
    ("narrative_events", "narrative_events"),
    ("narrative_events_ratio_ma20_pct", "narrative_events_ratio_ma20_pct"),
    ("narrative_concepts", "narrative_concepts"),
    ("narrative_new_concepts", "narrative_new_concepts"),
    ("narrative_new_concept_share_pct", "narrative_new_concept_share_pct"),
    ("narrative_hard_share_pct", "narrative_hard_share_pct"),
    ("narrative_bull_share_pct", "narrative_bull_share_pct"),
    ("narrative_top3_share_pct", "narrative_top3_share_pct"),
    ("narrative_cover_rps5_pct", "narrative_cover_rps5_pct"),
    # 消息面第二个源：晨汇 Tier 投影（知识库 ``briefing-tier-events.jsonl``）。Tier 1 / 2 / 3 条目数、盘面共振条数
    # （只有带盘面输入的三维晨汇才有数，二维晨汇记缺口 briefing_no_market_input——不可知不是 0）、维度数、
    # 当日赚钱效应板块点名了多少比例的 Tier 1 / 2 主题（精确匹配）、晨汇写成滞后天数（回填批次晚数周）。
    ("briefing_tier1_items", "briefing_tier1_items"),
    ("briefing_tier2_items", "briefing_tier2_items"),
    ("briefing_tier3_items", "briefing_tier3_items"),
    ("briefing_market_confirmed", "briefing_market_confirmed"),
    ("briefing_dimensions", "briefing_dimensions"),
    ("briefing_hit_rps5_pct", "briefing_hit_rps5_pct"),
    ("briefing_lag_days", "briefing_lag_days"),
)

# 每个叙事源自己的缺口键：字段 NULL 时先看源级原因（未接知识库 / 断更 / 当日无晨汇），再退回 ``<field>_null``。
_SOURCE_GAP_KEYS = (("narrative_", "narrative_gap"), ("briefing_", "briefing_gap"))


def _sector_scalars(row: Mapping[str, Any] | None) -> list[tuple[str, float | None, str | None]]:
    """Fail closed on days the sector tables did not cover; each field NULL is its own gap."""
    out: list[tuple[str, float | None, str | None]] = []
    for label, field in SECTOR_FIELDS:
        if row is None:
            out.append((label, None, "sector_rows_absent"))
            continue
        value = _num(row.get(field))
        if value is None:
            reason = f"{field}_null"
            for prefix, gap_key in _SOURCE_GAP_KEYS:
                if field.startswith(prefix) and row.get(gap_key):
                    reason = str(row[gap_key])
            if field == "briefing_market_confirmed" and row.get("briefing_dimensions") == 2:
                reason = "briefing_no_market_input"
            out.append((label, None, reason))
        else:
            rounded = round(value, SCALAR_DECIMALS)
            # -0.0 → 0.0：并行 MEDIAN 对同样的输入可能给出任一符号的零，写库前归一，免得两次重建哈希不同。
            out.append((label, 0.0 if rounded == 0 else rounded, None))
    return out


# View scalars are canonicalized to this many decimals.  A parallel SQL AVG
# over ~5000 stocks sums in a different order run to run and moves the last
# bit of the mean; that must not change the content hash of an identical build.
SCALAR_DECIMALS = 6


def _breadth_scalars(
    row: Mapping[str, Any] | None, floor: int
) -> list[tuple[str, float | None, str | None]]:
    """Fail closed on absent days and on days covering too few stocks for a median to mean anything."""
    out: list[tuple[str, float | None, str | None]] = []
    for label, field, count_field in BREADTH_FIELDS:
        if row is None:
            out.append((label, None, "stock_rows_absent"))
            continue
        count = _num(row.get(count_field))
        value = _num(row.get(field))
        if count is None or count < floor:
            out.append((label, None, f"{count_field}_below_floor"))
        elif value is None:
            out.append((label, None, f"{field}_null"))
        else:
            out.append((label, round(value, SCALAR_DECIMALS), None))
    return out


def _up_ratio_ma(
    rows: list[Mapping[str, Any]],
    i: int,
    cal_index: Mapping[Any, int] | None,
    breadth_by_day: Mapping[Any, Mapping[str, Any]],
    floor: int,
    n: int,
) -> tuple[float | None, str | None]:
    """Mean of the last ``n`` days' up-ratio (复盘会 up_rate_ma5); every day must be adjacent and above the coverage floor."""
    if i < n - 1 or not _contiguous(rows, i - n + 1, i, cal_index):
        return None, "window_incomplete"
    values: list[float] = []
    for j in range(i - n + 1, i + 1):
        row = breadth_by_day.get(_date(rows[j].get("trade_date")))
        if row is None:
            return None, "stock_rows_absent"
        count, value = _num(row.get("stock_count")), _num(row.get("up_ratio_pct"))
        if count is None or count < floor:
            return None, "stock_count_below_floor"
        if value is None:
            return None, "up_ratio_pct_null"
        values.append(value)
    return round(sum(values) / len(values), SCALAR_DECIMALS), None


# 创始人 2026-09-07 第四段：「高位震荡并不是只看周均和量能，还要看指数的形态，区间涨幅和
# 振幅，周均偏离度的变化。」这三样能从 fact_market_daily 的上证 OHLC / 偏离度确定性算出，
# 先作视角写出、不进计分；窗口天数是 B 类候选值（参数 ``index_range_windows``）。「形态」
# 没有可对照的字段口径，仍待创始人填。
DEFAULT_RANGE_WINDOWS = (5, 10)
RANGE_SCALAR_STEMS = ("sh_index_pct_chg", "sh_index_amplitude", "sh_deviation_change")


def range_scalar_labels(windows: Iterable[int]) -> list[str]:
    """Label stems × windows, e.g. ``sh_index_pct_chg_5d``; order is stable for receipts."""
    return [f"{stem}_{int(n)}d" for n in windows for stem in RANGE_SCALAR_STEMS]


def _index_range_scalars(
    rows: list[Mapping[str, Any]],
    i: int,
    cal_index: Mapping[Any, int] | None,
    windows: Iterable[int],
) -> list[tuple[str, float | None, str | None]]:
    """Interval gain, interval amplitude and deviation change of the index over each window.

    For a window of ``n`` days ending today the base day is the day before the
    window; gain and amplitude are both expressed against the base close so the
    two read on one scale.  Every one of the ``n + 1`` rows must be an adjacent
    calendar day, otherwise the window is unknown rather than shortened.
    """
    out: list[tuple[str, float | None, str | None]] = []
    for n in windows:
        n = int(n)
        labels = range_scalar_labels((n,))
        if i < n or not _contiguous(rows, i - n, i, cal_index):
            out.extend((label, None, "window_incomplete") for label in labels)
            continue
        base, today = rows[i - n], rows[i]
        base_close, close = _num(base.get("sh_index_close")), _num(today.get("sh_index_close"))
        gain_label, amp_label, dev_label = labels
        if base_close is None or base_close <= 0 or close is None:
            out.append((gain_label, None, "close_null"))
            out.append((amp_label, None, "close_null"))
        else:
            out.append((gain_label, round((close / base_close - 1) * 100, SCALAR_DECIMALS), None))
            highs = [_num(rows[j].get("sh_index_high")) for j in range(i - n + 1, i + 1)]
            lows = [_num(rows[j].get("sh_index_low")) for j in range(i - n + 1, i + 1)]
            if any(x is None for x in highs) or any(x is None for x in lows):
                out.append((amp_label, None, "high_low_null"))
            else:
                amplitude = (max(highs) - min(lows)) / base_close * 100
                out.append((amp_label, round(amplitude, SCALAR_DECIMALS), None))
        base_dev, dev = _num(base.get("sh_deviation_pct")), _num(today.get("sh_deviation_pct"))
        if base_dev is None or dev is None:
            out.append((dev_label, None, "deviation_null"))
        else:
            out.append((dev_label, round(dev - base_dev, SCALAR_DECIMALS), None))
    return out


RANGE_STRUCTURE_STEMS = ("index_high_not_rising", "index_range_converging")


def _range_structure_flags(
    rows: list[Mapping[str, Any]],
    i: int,
    cal_index: Mapping[Any, int] | None,
    windows: Iterable[int],
) -> dict[str, bool | None]:
    """区间结构 of the last ``n`` days against the ``n`` days before them.

    创始人 09-07 第七段 confirmed 高位震荡's 形态 as 「高点不抬高加收敛」: the recent block's
    highest high does not exceed the previous block's, and its high-low range is narrower.
    Both blocks must be adjacent calendar days with high / low present; otherwise unknown.
    """
    out: dict[str, bool | None] = {}
    for n in windows:
        n = int(n)
        not_rising_label, converging_label = (f"{stem}_{n}d" for stem in RANGE_STRUCTURE_STEMS)
        if i < 2 * n - 1 or not _contiguous(rows, i - 2 * n + 1, i, cal_index):
            out[not_rising_label] = out[converging_label] = None
            continue
        recent = rows[i - n + 1 : i + 1]
        earlier = rows[i - 2 * n + 1 : i - n + 1]
        highs_r = [_num(r.get("sh_index_high")) for r in recent]
        lows_r = [_num(r.get("sh_index_low")) for r in recent]
        highs_e = [_num(r.get("sh_index_high")) for r in earlier]
        lows_e = [_num(r.get("sh_index_low")) for r in earlier]
        if any(x is None for x in highs_r + lows_r + highs_e + lows_e):
            out[not_rising_label] = out[converging_label] = None
            continue
        out[not_rising_label] = max(highs_r) <= max(highs_e)
        out[converging_label] = (max(highs_r) - min(lows_r)) < (max(highs_e) - min(lows_e))
    return out


# 创始人 2026-09-07 第十一段：「升级 2.0，大概率是进一步放量指数进一步走强」。「进一步走强」= 收盘创出
# 前 n 个交易日的新高；n 是 B 类候选值（参数 ``index_new_high_windows``，写出每个窗口；进入谓词用
# ``upgrade_new_high_window`` 指定的那一个）。平台八段上：2.0 有 58% 的日子是 60 日新高，主流主升只 14%
# （第一腿从底部起、只到 20 日新高），承接盘反复 16%。
DEFAULT_NEW_HIGH_WINDOWS = (20, 60)
DOUBLE_VOLUME_DOD_PCT = 10.0  # 每日复盘 双量日 的环比门槛（daily_review._market_label）
# 亏钱效应日的口径（参数 ``money_losing``）：承接 5 日均值 < lt_pct。数字是候选（训练期 p10 取整），见骨架 §8.14。
DEFAULT_MONEY_LOSING = {"basis": "limit_premium_ma5_pct", "lt_pct": 1.0}


def new_high_labels(windows: Iterable[int]) -> list[str]:
    return [f"index_new_high_{int(n)}d" for n in windows]


def _index_new_high_flags(
    rows: list[Mapping[str, Any]],
    i: int,
    cal_index: Mapping[Any, int] | None,
    windows: Iterable[int],
) -> dict[str, bool | None]:
    """Close above the highest close of the previous ``n`` adjacent calendar days; unknown when the window is short."""
    out: dict[str, bool | None] = {}
    for n in windows:
        n = int(n)
        label = f"index_new_high_{n}d"
        if i < n or not _contiguous(rows, i - n, i, cal_index):
            out[label] = None
            continue
        close = _num(rows[i].get("sh_index_close"))
        prior = [_num(rows[j].get("sh_index_close")) for j in range(i - n, i)]
        if close is None or any(x is None for x in prior):
            out[label] = None
            continue
        out[label] = close > max(prior)
    return out


def _contiguous(
    rows: list[Mapping[str, Any]], start: int, end: int, cal_index: Mapping[Any, int] | None
) -> bool:
    """True when rows[start..end] are consecutive calendar days (or no calendar was given)."""
    if cal_index is None:
        return True
    for j in range(start, end):
        a = cal_index.get(_date(rows[j].get("trade_date")))
        b = cal_index.get(_date(rows[j + 1].get("trade_date")))
        if a is None or b is None or b - a != 1:
            return False
    return True


def _cross(prev: Mapping[str, Any], row: Mapping[str, Any], side: str) -> bool | None:
    pc, pm = (_num(prev.get("sh_index_close")), _num(prev.get("sh_week_ma")))
    c, m = (_num(row.get("sh_index_close")), _num(row.get("sh_week_ma")))
    if None in (pc, pm, c, m):
        return None
    if side == "above":
        return pc <= pm and c > m
    return pc > pm and c < m


def _band(dev: float | None, over_le: float, hot_ge: float) -> str | None:
    if dev is None:
        return None
    if dev <= over_le:
        return "oversold"
    if dev < 0:
        return "below"
    if dev < hot_ge:
        return "above"
    return "overheated"


def _vendor_share(by_day, d, market, prev, prev_rows):
    now = by_day.get(d)
    old = prev_rows
    if not now or not old or prev is None:
        return None

    def amount(rs):
        vals = [_num(r.get("amount")) for r in rs]
        return (
            sum(x for x in vals if x is not None)
            if any(x is not None for x in vals)
            else None
        )

    a, b = amount(now), amount(old)
    den_now, den_old = _num(market.get("total_amount")), _num(prev.get("total_amount"))
    if (
        a is None
        or b is None
        or den_now is None
        or den_old is None
        or den_now <= 0
        or den_old <= 0
    ):
        return None
    return a / den_now > b / den_old


def _vendor_rising(by_day, d, n, rows, i):
    if i < n - 1:
        return None
    points = []
    for j in range(i - n + 1, i + 1):
        day = _date(rows[j].get("trade_date"))
        entries = by_day.get(day)
        if not entries:
            return None
        vals = [_num(r.get("amount")) for r in entries]
        if not vals or any(v is None for v in vals):
            return None
        points.append(sum(vals))
    return all(a < b for a, b in zip(points, points[1:]))


UPGRADE_TREND_WINDOW = 5


def _window_mean_up(rows, i, n, cal_index, value_of) -> bool | None:
    """Mean of ``value_of`` over the last ``n`` trading days vs the ``n`` before them — a process, not a day.

    Both windows must be calendar-contiguous and fully populated (2n consecutive trading days with a value);
    otherwise None.  A single shrinking day inside a rising window does not flip it (创始人 09-08：「单日的成交可能会有小缩量」).
    """
    if i < 2 * n - 1:
        return None
    if cal_index is not None:
        first = cal_index.get(_date(rows[i - 2 * n + 1].get("trade_date")))
        last = cal_index.get(_date(rows[i].get("trade_date")))
        if first is None or last is None or last - first != 2 * n - 1:
            return None
    recent = [value_of(rows[j]) for j in range(i - n + 1, i + 1)]
    before = [value_of(rows[j]) for j in range(i - 2 * n + 1, i - n + 1)]
    if any(v is None for v in recent) or any(v is None for v in before):
        return None
    return sum(recent) / n > sum(before) / n


def _rising_top3_streak(rows, i, n, cal_index):
    """Compare the derived top-three amount (market amount × top-three share)."""

    if i < n - 1:
        return None
    for j in range(i - n + 2, i + 1):
        current = _num(rows[j].get("total_amount"))
        previous = _num(rows[j - 1].get("total_amount"))
        current_share = _num(rows[j].get("top3_industry_ratio"))
        previous_share = _num(rows[j - 1].get("top3_industry_ratio"))
        if None in (current, previous, current_share, previous_share):
            return None
        if cal_index is not None:
            cur_i = cal_index.get(_date(rows[j].get("trade_date")))
            prev_i = cal_index.get(_date(rows[j - 1].get("trade_date")))
            if cur_i is None or prev_i is None or cur_i - prev_i != 1:
                return None
        if not current * current_share > previous * previous_share:
            return False
    return True


def _scalar_max(rows, col):
    vals = [_num(r.get(col)) for r in rows]
    vals = [v for v in vals if v is not None]
    return max(vals) if vals else None


def _promotion(today, prev) -> tuple[float | None, str | None]:
    """Today's ``limit_times >= 2`` count over yesterday's limit-up count.

    A NULL ``limit_times`` today makes the numerator unknowable; it is not
    counted as "below 2".
    """
    if not prev:
        return None, "prev_day_limit_rows_absent"
    values = [_num(r.get("limit_times")) for r in today]
    if any(v is None for v in values):
        return None, "limit_times_null"
    return sum(1 for v in values if v >= 2) / len(prev), None


def _top100_share(d, market, amount_values_by_day, top_n) -> tuple[float | None, str | None]:
    """Top-N stock amount over market total; fail closed when units disagree.

    Both columns must share a unit for the share to be meaningful.  A share above
    one is impossible when they do, so it is treated as a unit mismatch rather
    than reported.
    """
    den = _num(market.get("total_amount"))
    if den is None or den <= 0:
        return None, "total_amount_null_or_zero"
    vals = sorted(amount_values_by_day.get(d, ()), reverse=True)
    if len(vals) < top_n:
        return None, f"amount_rows_lt_top{top_n}"
    share = sum(vals[:top_n]) / den
    if share > 1:
        return None, "unit_mismatch_share_gt_1"
    return share, None
