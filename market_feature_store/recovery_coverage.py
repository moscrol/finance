"""Pure recovery denominator contracts; explicit scope is not listing authority.

A missing bar remains a missing bar. Documented nontrading identities can explain
coverage, but cannot become flat quotes or disappear from a membership denominator.
No network, file, database, or publication side effects live in this module.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
import math
import re


def _codes(values: Sequence[str], label: str) -> set[str]:
    if isinstance(values, (str, bytes)):
        raise ValueError(f"invalid {label}")
    result = set()
    for code in values:
        if not isinstance(code, str) or not re.fullmatch(r"[0-9]{6}\.(SH|SZ|BJ)", code) or code in result:
            raise ValueError(f"invalid or duplicate {label}")
        result.add(code)
    return result


def partition_scope(*, declared: Sequence[str], observed: Sequence[str],
                    suspended: Sequence[str]) -> dict:
    """Require an exact partition, not a lower count justified by a tolerance."""
    scope = _codes(declared, "declared scope")
    active = _codes(observed, "observed scope")
    stopped = _codes(suspended, "nontrading scope")
    if not scope or active & stopped or active | stopped != scope:
        raise ValueError("scope must partition into observed bars and explained nontrading identities")
    return {"declared_count": len(scope), "observed_count": len(active),
            "nontrading_count": len(stopped), "bar_coverage_denominator": len(scope),
            "observed_bar_fraction": len(active) / len(scope),
            "disposition_coverage_fraction": 1.0,
            "official_historical_universe_verified": False}


def market_breadth(rows: Sequence[Mapping], suspended: Sequence[str]) -> dict:
    """Breadth is over traded observations; suspension is separate, not flat."""
    active = _codes([r["stock_ts_code"] for r in rows], "observed scope")
    stopped = _codes(suspended, "nontrading scope")
    if active & stopped:
        raise ValueError("nontrading identity has a bar")
    counts = Counter(advancers=0, decliners=0, unchanged_traded=0)
    for row in rows:
        for key in ("pct_chg", "amount"):
            value = row[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError("invalid breadth observation")
        if row["amount"] <= 0:
            raise ValueError("breadth requires positive traded amount")
        pct = row["pct_chg"]
        counts["advancers" if pct > 0 else "decliners" if pct < 0 else "unchanged_traded"] += 1
    return {**counts, "nontrading_not_flat": len(stopped), "observed_denominator": len(active)}


def sector_coverage(*, declared_members: Mapping[str, Sequence[str]],
                    expected_counts: Mapping[str, int], observed_members: Mapping[str, Sequence[str]],
                    suspended: Sequence[str]) -> dict[str, dict]:
    """Exact member identities, not just matching counts, justify a denominator.

    The caller supplies a frozen identity baseline and already-validated dated
    suspension identities. This validates consumption, not source authenticity.
    Unknown missing members, surplus members, or synthetic suspended rows refuse
    the entire batch before any delete/write. The usual shortfall tolerance is
    deliberately not used for this explicit recovery path.
    """
    stopped = _codes(suspended, "nontrading scope")
    if not declared_members or set(declared_members) != set(expected_counts):
        raise ValueError("sector declaration must cover the published universe")
    if not set(observed_members) <= set(declared_members):
        raise ValueError("observed sector outside published universe")
    result = {}
    for sector, codes in sorted(declared_members.items()):
        scope = _codes(codes, "sector members")
        observed = _codes(observed_members.get(sector, ()), "observed members")
        expected = expected_counts[sector]
        if type(expected) is not int or expected <= 0 or expected != len(scope):
            raise ValueError("sector identity baseline disagrees with declared count")
        coverage = partition_scope(declared=sorted(scope), observed=sorted(observed),
                                   suspended=sorted(scope & stopped))
        result[sector] = {**coverage, "nontrading_codes": sorted(scope & stopped),
                          "ratio_denominator": len(scope), "synthetic_rows": 0}
    return result
