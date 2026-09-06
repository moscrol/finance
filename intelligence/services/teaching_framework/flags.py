"""Pure, fail-closed market flag and scalar calculations for teaching framework."""

from __future__ import annotations

import math
from datetime import date, datetime, time
from typing import Any, Iterable, Mapping


NULL = None


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


def _adjacent(rows: list[Mapping[str, Any]], i: int) -> bool:
    return i > 0 and (
        _date(rows[i - 1].get("trade_date")) is not None
        and _date(rows[i].get("trade_date")) is not None
    )


def _prev(
    rows: list[Mapping[str, Any]], i: int, calendar: Iterable[Any] | None
) -> Mapping[str, Any] | None:
    if i <= 0:
        return None
    prev = rows[i - 1]
    if calendar is None:
        return prev
    days = [_date(d) for d in calendar]
    indexes = {d: n for n, d in enumerate(days)}
    cur_i, prev_i = (
        indexes.get(_date(rows[i].get("trade_date"))),
        indexes.get(_date(prev.get("trade_date"))),
    )
    return (
        prev
        if cur_i is not None and prev_i is not None and cur_i - prev_i == 1
        else None
    )


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
        key = (d, str(ident))
        prev = out.get(key)
        if prev is None:
            out[key] = row
        elif prev.get("limit_times") != row.get("limit_times"):
            marker = dict(prev)
            marker["_conflict"] = True
            out[key] = marker
    return out


def _dedupe_stock_rows(
    rows: Iterable[Mapping[str, Any]],
) -> dict[tuple[Any, str], Mapping[str, Any]]:
    out: dict[tuple[Any, str], Mapping[str, Any]] = {}
    for row in rows:
        d, stock = (
            _date(row.get("trade_date")),
            row.get("stock_ts_code", row.get("stock")),
        )
        if d is None or stock is None:
            continue
        key = (d, str(stock))
        prev = out.get(key)
        # conflicting limit_times is unsafe; retain a marker for consumers
        if prev is not None and prev.get("limit_times") != row.get("limit_times"):
            r = dict(prev)
            r["_conflict"] = True
            out[key] = r
        elif prev is None:
            out[key] = row
    return out


def compute_flags(
    rows: Iterable[Mapping[str, Any]],
    *,
    calendar: Iterable[Any] | None = None,
    vendor_rows: Iterable[Mapping[str, Any]] | None = None,
    stock_rows: Iterable[Mapping[str, Any]] | None = None,
    amount_rows: Iterable[Mapping[str, Any]] | None = None,
    params: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Compute all A flags plus B scalars. Rows must represent fact_market_daily.

    Missing previous calendar day or any required NULL yields NULL; no false is inferred.
    """
    p = params or {}
    bands = p.get("deviation_bands", {})
    over_le = float(bands.get("oversold_le", -2.5))
    hot_ge = float(bands.get("overheated_ge", 1.5))
    rows = sorted((dict(r) for r in rows), key=lambda r: _date(r.get("trade_date")))
    cal = [_date(x) for x in calendar] if calendar is not None else None
    vendor = _dedupe_rows(
        vendor_rows or [], identity_keys=("sector_ts_code", "sector", "stock_ts_code")
    )
    stock = _dedupe_rows(
        stock_rows or [], identity_keys=("stock_ts_code", "stock", "ts_code", "code")
    )
    amounts = _dedupe_rows(
        amount_rows or [], identity_keys=("stock_ts_code", "stock", "ts_code", "code")
    )
    vendor_by_day: dict[Any, list[Mapping[str, Any]]] = {}
    for (d, _), r in vendor.items():
        vendor_by_day.setdefault(d, []).append(r)
    out: list[dict[str, Any]] = []
    streak = 0
    for i, row in enumerate(rows):
        prev = _prev(rows, i, cal)
        d = _date(row.get("trade_date"))
        rec = {"trade_date": d}
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
        rec["volume_surge"] = (
            _num(row.get("amount_vs_yesterday_pct")) > 10
            if _num(row.get("amount_vs_yesterday_pct")) is not None
            else None
        )
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
        rec["mainline_amount_stepping_up.volume_top3"] = _rising_streak(
            rows,
            i,
            "total_amount",
            int(p.get("mainline_amount_stepping_up_days", 3)),
            cal,
        )
        rec["mainline_amount_stepping_up.vendor"] = _vendor_rising(
            vendor_by_day,
            d,
            int(p.get("mainline_amount_stepping_up_days", 3)),
            rows,
            i,
            cal,
        )
        # B scalars
        day_stocks = [r for (dd, _), r in stock.items() if dd == d]
        rec["max_boards"] = _scalar_max(day_stocks, "limit_times")
        prev_stocks = [
            r
            for (dd, _), r in stock.items()
            if prev is not None and dd == _date(prev.get("trade_date"))
        ]
        rec["promotion_rate_total"] = _promotion(day_stocks, prev_stocks)
        rec["top100_amount_share"] = _top100_share(d, row, amounts)
        out.append(rec)
    return out


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


def _vendor_rising(by_day, d, n, rows, i, cal):
    # The vendor table has no all-market denominator; expose a conservative NULL unless amount rows are supplied.
    return None


def _rising_streak(rows, i, col, n, cal):
    if i < n - 1:
        return None
    vals = []
    for j in range(i - n + 1, i + 1):
        v = _num(rows[j].get(col))
        pv = _num(rows[j - 1].get(col)) if j else None
        if v is None or pv is None:
            return None
        if cal is not None:
            idx = {_date(x): n for n, x in enumerate(cal)}
            if (
                idx.get(_date(rows[j].get("trade_date"))) is None
                or idx.get(_date(rows[j - 1].get("trade_date")))
                != idx.get(_date(rows[j].get("trade_date"))) - 1
            ):
                return None
        vals.append(v > pv)
    return all(vals)


def _scalar_max(rows, col):
    vals = [_num(r.get(col)) for r in rows]
    vals = [v for v in vals if v is not None]
    return max(vals) if vals else None


def _promotion(today, prev):
    if not prev:
        return None
    n = len(prev)
    k = sum(1 for r in today if (_num(r.get("limit_times")) or 0) >= 2)
    return k / n if n else None


def _top100_share(d, market, amount_rows):
    den = _num(market.get("total_amount"))
    vals = [_num(r.get("amount")) for (dd, _), r in amount_rows.items() if dd == d]
    vals = sorted((v for v in vals if v is not None), reverse=True)
    if den is None or den <= 0 or len(vals) < 100:
        return None
    return sum(vals[:100]) / den
