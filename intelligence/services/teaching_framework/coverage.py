"""Coverage and deterministic deduplication for the limit-up source.

The limit table is a stock/sector relation, therefore one stock can occur more than
once on a trading day.  This module deliberately works on plain mappings so it can
be used by both DuckDB builders and small replay fixtures.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterable, Mapping


def _date(value: Any) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)[:10]


def normalize_hhmmss(value: Any) -> str | None:
    """Return compact intraday values as ``HH:MM``; malformed/NULL is unknown."""
    if value is None:
        return None
    if isinstance(value, float) and value != value:
        return None
    if isinstance(value, (int, float)):
        text = str(int(value))
    else:
        text = str(value).strip()
    if not text or text.lower() in {"none", "null", "nan", "nat"}:
        return None
    if ":" in text:
        bits = text.split(":")
        if len(bits) < 2 or not all(b.isdigit() for b in bits[:2]):
            return None
        hh, mm = int(bits[0]), int(bits[1])
    else:
        if not text.isdigit():
            return None
        # 92500 / 092500 are HHMMSS, while 925 is accepted as HHMM.
        text = text.zfill(6) if len(text) <= 6 else text
        if len(text) == 6:
            hh, mm = int(text[:2]), int(text[2:4])
        elif len(text) == 4:
            hh, mm = int(text[:2]), int(text[2:])
        else:
            return None
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        return None
    return f"{hh:02d}:{mm:02d}"


def _get(row: Any, name: str, pos: int | None = None) -> Any:
    if isinstance(row, Mapping):
        return row.get(name)
    if hasattr(row, name):
        return getattr(row, name)
    if pos is not None:
        try:
            return row[pos]
        except (IndexError, KeyError, TypeError):
            return None
    return None


def normalize_limit_row(row: Any) -> dict[str, Any]:
    """Normalize a DB tuple or mapping into the fields used by succession."""
    out = dict(row) if isinstance(row, Mapping) else {}
    fields = (
        "trade_date", "stock_ts_code", "stock_name", "limit_times", "open_times",
        "first_limit_time", "up_stat", "circ_mv", "amount", "limit_status",
    )
    # DuckDB fixtures commonly use this canonical positional order.
    for i, field in enumerate(fields):
        out.setdefault(field, _get(row, field, i))
    out["trade_date"] = _date(out.get("trade_date"))
    out["stock_ts_code"] = out.get("stock_ts_code") or out.get("stock") or out.get("entity_id")
    out["first_limit_time"] = normalize_hhmmss(out.get("first_limit_time"))
    return out


@dataclass(frozen=True)
class CoverageDay:
    trade_date: str
    status: str  # covered / covered_empty / missing
    rows: tuple[dict[str, Any], ...] = ()
    reason: str | None = None

    @property
    def is_complete(self) -> bool:
        return self.status in {"covered", "covered_empty"}


def collapse_limit_rows(rows: Iterable[Any]) -> dict[str, tuple[dict[str, Any], ...]]:
    """Collapse sector duplicates by ``(trade_date, stock_ts_code)``.

    ``limit_times`` uses the validated conservative conflict policy MAX.  Other
    fields use the first non-NULL value in stable input order; this keeps duplicate
    sector rows deterministic and preserves NULL when no source row has a value.
    """
    grouped: dict[tuple[str, Any], dict[str, Any]] = {}
    order: list[tuple[str, Any]] = []
    for raw in rows:
        row = normalize_limit_row(raw)
        day, stock = row.get("trade_date"), row.get("stock_ts_code")
        if not day or stock is None:
            continue
        key = (day, stock)
        if key not in grouped:
            grouped[key] = dict(row)
            order.append(key)
            continue
        current = grouped[key]
        a, b = current.get("limit_times"), row.get("limit_times")
        if a is None:
            current["limit_times"] = b
        elif b is not None:
            try:
                current["limit_times"] = max(float(a), float(b))
                if float(current["limit_times"]).is_integer():
                    current["limit_times"] = int(current["limit_times"])
            except (TypeError, ValueError):
                pass
        for field in ("stock_name", "open_times", "first_limit_time", "up_stat", "circ_mv", "amount", "limit_status"):
            if current.get(field) is None and row.get(field) is not None:
                current[field] = row[field]
    result: dict[str, list[dict[str, Any]]] = {}
    for key in order:
        result.setdefault(key[0], []).append(grouped[key])
    return {day: tuple(items) for day, items in result.items()}


def build_coverage(
    calendar_dates: Iterable[Any],
    rows: Iterable[Any] | Mapping[Any, Iterable[Any]],
    *,
    covered_dates: Iterable[Any] | None = None,
) -> dict[str, CoverageDay]:
    """Build a calendar-aligned coverage map.

    Pass ``covered_dates`` (the source's explicit day manifest) when available.  An
    explicit covered day with zero rows is ``covered_empty``; an absent day is
    ``missing``.  If no manifest is supplied, dates represented by rows are covered
    and every other date is conservatively missing.
    """
    dates = sorted({_date(d) for d in calendar_dates})
    mapping_days: set[str] = set()
    if isinstance(rows, Mapping):
        raw_by_day = {_date(k): tuple(v or ()) for k, v in rows.items()}
        mapping_days = set(raw_by_day)
        flat: list[Any] = []
        for day, values in raw_by_day.items():
            for value in values:
                if isinstance(value, Mapping):
                    item = dict(value)
                    item.setdefault("trade_date", day)
                    flat.append(item)
                else:
                    flat.append(value)
    else:
        raw_by_day = None
        flat = list(rows)
    grouped = collapse_limit_rows(flat)
    explicit = ({_date(d) for d in covered_dates} if covered_dates is not None else set(grouped)) | mapping_days
    result: dict[str, CoverageDay] = {}
    for day in dates:
        if day in explicit:
            items = grouped.get(day, ())
            result[day] = CoverageDay(day, "covered" if items else "covered_empty", items)
        else:
            result[day] = CoverageDay(day, "missing", (), "source_day_absent")
    return result


__all__ = [
    "CoverageDay", "build_coverage", "collapse_limit_rows", "normalize_hhmmss",
    "normalize_limit_row",
]
