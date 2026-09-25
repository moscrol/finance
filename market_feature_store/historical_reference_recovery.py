"""Pure adjudication of the three September 22 reference-price gaps.

This is not a canonical row builder. Caller must authenticate captured bytes and
reproduce their decoded witnesses separately. Even accepted numbers lack dated
names and turnover; no output grants preparation, write or publication authority.
The adjacent-day preview and September 21 resumption contract are unchanged.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import (
    Context, Decimal, DecimalException, DivisionByZero, InvalidOperation, Overflow,
    ROUND_HALF_UP, localcontext,
)
import json
import re

from .hithink_recovery_candidate import CandidateRefused, _day, _index, _require, _require_fields
from .hithink_stock_preview import _as_float, _bar_gaps, _hash, _number

CONTRACT = "historical-reference-adjudication-20260922-v1"
DAY, PREVIOUS = date(2026, 9, 22), date(2026, 9, 21)
CODES = ("300803.SZ", "301686.SZ", "920229.BJ")
_CENT = Decimal("0.01")
_BAR_FIELDS = ("stock_ts_code", "trade_date", "open", "high", "low", "close",
               "volume", "turnover", "adjusted", "source", "updated_at")
_ACTION_FIELDS = ("stock_ts_code", "ex_date", "dividend_per_share", "per_share_bonus",
                  "allotment_ratio", "allotment_price", "currency", "source", "updated_at")


def _provenance(row, source):
    _require_fields(row, ("source", "raw_sha256"), "witness provenance")
    _require(row["source"] == source and isinstance(row["raw_sha256"], str)
             and re.fullmatch(r"[0-9a-f]{64}", row["raw_sha256"]) is not None,
             "invalid witness provenance")


def _positive(value):
    number = _number(value)
    _require(number is not None and number > 0, "invalid reference price")
    _require(number.quantize(_CENT) == number, "invalid reference tick")
    return number


def _check_bar(row, label):
    gaps = _bar_gaps(row, label)
    _require(not gaps, "invalid bar: " + ",".join(gaps))
    low, high, volume, amount = (_number(row[k]) for k in ("low", "high", "volume", "turnover"))
    _require(low * volume - 1 <= amount <= high * volume + 1,
             "bar amount/volume outside price range")


def _adjudicate(*, bars, actions, witnesses, listings):
    for row in bars:
        _require_fields(row, _BAR_FIELDS, "bar")
    bar_map = _index(bars, lambda r: (r["stock_ts_code"], _day(r["trade_date"])))
    _require(set(bar_map) == {(code, DAY) for code in CODES} | {(CODES[0], PREVIOUS)},
             "fixed bar scope changed; missing previous bar is not IPO proof")
    for row in actions:
        _require_fields(row, _ACTION_FIELDS, "action")
    action_map = _index(actions, lambda r: (r["stock_ts_code"], _day(r["ex_date"])))
    _require(set(action_map) == {(CODES[0], DAY)}, "fixed action scope changed")
    action = action_map[(CODES[0], DAY)]
    _require(action["source"] == "hithink:adjustment-factors" and action["currency"] == "CNY"
             and isinstance(action["updated_at"], datetime), "invalid action provenance")
    _require([_number(action[k]) for k in ("dividend_per_share", "per_share_bonus",
              "allotment_ratio", "allotment_price")] == [Decimal(0), Decimal("0.45"), Decimal(0), Decimal(0)],
             "only the named pure bonus action is supported")
    for row in witnesses:
        _require_fields(row, ("stock_ts_code", "trade_date", "open", "high", "low", "close",
                              "volume", "amount"), "historical witness")
        _provenance(row, "sina:historical:unadjusted")
    witness_map = _index(witnesses, lambda r: (r["stock_ts_code"], _day(r["trade_date"])))
    _require(set(witness_map) == {(code, DAY) for code in CODES}, "fixed witness scope changed")
    for row in listings:
        _require_fields(row, ("stock_ts_code", "listing_date", "offer_price"), "listing witness")
        _provenance(row, "sina:ipo-page")
    listing_map = _index(listings, lambda r: r["stock_ts_code"])
    _require(set(listing_map) == set(CODES[1:]), "fixed listing scope changed")
    for code, expected in zip(CODES[1:], (Decimal("55.28"), Decimal("15.67")), strict=True):
        listing = listing_map[code]
        _require(_day(listing["listing_date"]) == DAY and _positive(listing["offer_price"]) == expected,
                 "named listing date or offer price changed")
    previous = bar_map[(CODES[0], PREVIOUS)]
    _check_bar(previous, "previous")
    observations, gaps = [], []
    for code in CODES:
        current, witness = bar_map[(code, DAY)], witness_map[(code, DAY)]
        _check_bar(current, "current")
        for field in ("open", "high", "low", "close", "volume"):
            _require(_number(witness[field]) is not None and _number(witness[field]) == _number(current[field]),
                     "cross-source price/volume mismatch")
        amount = _number(witness["amount"])
        _require(amount is not None and amount > 0 and abs(amount - _number(current["turnover"])) <= 1,
                 "cross-source amount mismatch")
        if code == CODES[2]:
            # The sealed witness has no prevclose. New evidence needs a new review,
            # not an offer-price fallback or an invented previous trading bar.
            _require(witness.get("prevclose") is None, "unreviewed Beijing reference witness")
            gaps.append({"stock_ts_code": code, "reasons": ["missing-explicit-dated-reference"],
                         "observed_offer_price": 15.67, "offer_price_substituted": False})
            continue
        reference = _positive(witness.get("prevclose"))
        if code == CODES[0]:
            computed = (_number(previous["close"]) / (1 + _number(action["per_share_bonus"]))).quantize(_CENT)
            _require(computed == reference == Decimal("56.86"), "bonus reference disagrees with dated witness")
            basis = "named_bonus_formula_and_explicit_dated_prevclose"
        else:
            _require(reference == _number(listing_map[code]["offer_price"]) == Decimal("55.28"),
                     "IPO explicit dated reference disagrees with listing witness")
            basis = "explicit_dated_prevclose_with_provider_listing_corroboration"
        close = _number(current["close"])
        observations.append({
            "trade_date": str(DAY), "stock_ts_code": code, "stock_name": None, "turnover": None,
            **{field: _as_float(_number(current[field])) for field in ("open", "high", "low", "close")},
            "pre_close": _as_float(reference),
            "pct_chg": _as_float(((close - reference) * 100 / reference).quantize(_CENT)),
            "amount": _as_float((_number(current["turnover"]) / 100_000_000).quantize(Decimal("0.0001"))),
            "volume": _as_float((_number(current["volume"]) / 100).quantize(Decimal(1))),
            "raw_amount_yuan": _as_float(_number(current["turnover"])),
            "raw_volume_shares": _as_float(_number(current["volume"])),
            "reference_basis": basis, "reference_witness_sha256": witness["raw_sha256"],
            "bar_source": current["source"], "post_market_values_added": False,
        })
    return observations, gaps


def adjudicate_20260922(*, bars, actions, witnesses, listings) -> dict:
    """Validate explicit fixed-scope inputs, returning partial numbers, never rows to write."""
    context = Context(prec=50, rounding=ROUND_HALF_UP, Emin=-999999, Emax=999999,
                      capitals=1, clamp=0, flags=[], traps=[InvalidOperation, DivisionByZero, Overflow])
    try:
        with localcontext(context):
            observations, gaps = _adjudicate(bars=bars, actions=actions, witnesses=witnesses, listings=listings)
    except DecimalException as exc:
        raise CandidateRefused("invalid arithmetic") from exc
    inputs = {"contract_version": CONTRACT}
    for key, rows in (("bars", bars), ("actions", actions), ("witnesses", witnesses), ("listings", listings)):
        inputs[key] = sorted(json.dumps(row, sort_keys=True, default=str, allow_nan=False) for row in rows)
    result = {
        "contract_version": CONTRACT, "trade_date": str(DAY), "stock_codes": list(CODES),
        "scope_basis": "three_named_reference_gaps_not_market_universe",
        "requested_stock_count": len(CODES), "reference_accepted_count": len(observations),
        "observations": observations, "gaps": gaps, "reference_complete": not gaps,
        "canonical_rows_ready": False, "production_ready": False, "database_writes": False,
        "publication_attempted": False, "official_listing_status_verified": False,
        "input_authentication": "caller_must_verify_raw_bytes_and_reproduce_decoding",
        "unavailable_fields": ["stock_name", "turnover"],
        "blockers": ["missing_explicit_dated_reference", "same_day_names_unverified",
                     "turnover_unverified", "frozen_member_identities", "derivation_and_publication_gates"],
        "input_fingerprint": _hash(inputs),
    }
    result["adjudication_fingerprint"] = _hash(result)
    return result
