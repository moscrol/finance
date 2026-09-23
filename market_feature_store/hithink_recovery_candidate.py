"""Pure dated recovery proposal, not a writer or a publication authorization.

Reuse the strict preview arithmetic without changing its adjacent-day contract.
Named resumption exceptions require matching historical witnesses and suspension
intervals. Nontrading members remain in the denominator, never synthetic bars.
Callers must authenticate captured bytes separately; fingerprints are not signatures.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta
from decimal import DecimalException
import json
import re
from typing import Any, Mapping, Sequence

from .hithink_stock_preview import _calculate, _hash, _number, _scope
from .trading_days import closed_dates

CONTRACT_VERSION = "hithink-recovery-candidate-v1"


class CandidateRefused(ValueError):
    """An input or a named exception does not satisfy its dated contract."""


@dataclass(frozen=True)
class Resumption:
    code: str
    last_trade_date: date
    close: float
    suspension_start: date


@dataclass(frozen=True)
class RoundingDifference:
    code: str
    close: float
    pre_close: float
    calculated_pct: float
    quoted_pct: float


@dataclass(frozen=True)
class RecoverySpec:
    trade_date: date
    scope_sha256: str
    suspended_codes: tuple[str, ...]
    resumptions: tuple[Resumption, ...]
    adjustment_codes: tuple[str, ...]
    rounding_differences: tuple[RoundingDifference, ...] = ()


CANDIDATE_20260921 = RecoverySpec(
    trade_date=date(2026, 9, 21),
    scope_sha256="f4e2568884bcfdc2bf0f80681995f76faaed813527bc9f61d88c426cdf276cd7",
    suspended_codes=("000016.SZ", "002731.SZ", "300082.SZ", "300585.SZ", "301139.SZ",
                     "601059.SH", "601198.SH", "601238.SH", "601995.SH", "603400.SH",
                     "605303.SH", "688496.SH"),
    resumptions=(Resumption("600301.SH", date(2026, 9, 11), 45.43, date(2026, 9, 14)),
                 Resumption("600825.SH", date(2026, 9, 4), 5.31, date(2026, 9, 7))),
    adjustment_codes=("002328.SZ", "002926.SZ", "002969.SZ", "300274.SZ", "300277.SZ",
                      "300566.SZ", "300628.SZ", "300751.SZ", "301047.SZ", "301266.SZ",
                      "600032.SH", "600096.SH", "600236.SH", "601133.SH", "601886.SH",
                      "603018.SH", "603193.SH", "605123.SH", "605228.SH", "688131.SH", "920211.BJ"),
    rounding_differences=(RoundingDifference("600184.SH", 21.08, 21.76, -3.13, -3.12),
                          RoundingDifference("603259.SH", 167.96, 160., 4.98, 4.97)),
)


def scope_fingerprint(trade_date: date, codes: Sequence[str]) -> str:
    td, _, codes = _scope(trade_date, codes)
    return _hash({"trade_date": str(td), "stock_codes": codes})


def _require(ok: bool, reason: str) -> None:
    if not ok:
        raise CandidateRefused(reason)


def _cents(value) -> int:
    number = _number(value)
    _require(number is not None, "invalid cent value")
    numerator, denominator = number.as_integer_ratio()
    _require(numerator * 100 % denominator == 0, "invalid cent tick")
    return numerator * 100 // denominator


def _day(value: Any) -> date:
    if type(value) is date:
        return value
    if isinstance(value, str) and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise CandidateRefused("invalid day") from exc
    raise CandidateRefused("invalid day")


def _timestamp(value: Any) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise CandidateRefused("invalid interval timestamp") from exc
    _require(parsed.tzinfo is None, "provider interval must use Shanghai wall time")
    return parsed


def _require_fields(value: Any, fields: Sequence[str], label: str) -> None:
    _require(isinstance(value, Mapping) and all(field in value for field in fields),
             f"missing {label} field")


def _index(rows, key):
    result = {}
    for row in rows:
        identity = key(row)
        _require(identity not in result, "duplicate input identity")
        result[identity] = row
    return result


def _quote(quote, code, td):
    _require_fields(quote, ("quote_timestamp", "name", "open", "high", "low", "close",
                            "pre_close", "pct_chg", "volume_shares", "amount_yuan",
                            "turnover_pct", "raw_volume_unit"), "quote")
    _require(isinstance(quote["quote_timestamp"], str)
             and re.fullmatch(r"[0-9]{14}", quote["quote_timestamp"]) is not None,
             "invalid quote timestamp")
    try:
        stamp = datetime.strptime(quote["quote_timestamp"], "%Y%m%d%H%M%S")
    except ValueError as exc:
        raise CandidateRefused("invalid quote timestamp") from exc
    _require(stamp.date() == td and stamp.time() >= time(15), "stale or intraday quote")
    name = quote["name"]
    _require(isinstance(name, str) and bool(name.strip())
             and not any(ord(c) < 32 for c in name), "invalid captured name")
    for field in ("open", "high", "low", "close", "pre_close", "volume_shares", "amount_yuan", "turnover_pct"):
        number = _number(quote[field])
        _require(number is not None and number >= 0, "invalid quote number")
    _require(_number(quote["pct_chg"]) is not None, "invalid quote percentage")
    _require(quote["close"] > 0 and quote["pre_close"] > 0, "invalid quote reference")
    _require(quote["volume_shares"] == int(quote["volume_shares"]), "fractional quote shares")
    unit = "shares" if code.startswith(("688", "689")) and code.endswith(".SH") else "hands"
    _require(quote["raw_volume_unit"] == unit, "quote volume unit mismatch")
    return unit


def _suspension(event, code, start, end):
    _require_fields(event, ("SECUCODE", "SECURITY_CODE", "SECURITY_TYPE_CODE",
                            "SUSPEND_START_TIME", "SUSPEND_END_TIME"), "suspension")
    _require(event["SECUCODE"] == code and event["SECURITY_CODE"] == code[:6], "suspension identity")
    _require(event["SECURITY_TYPE_CODE"] == "058001001", "not an A-share suspension")
    began = _timestamp(event["SUSPEND_START_TIME"])
    ended = _timestamp(event["SUSPEND_END_TIME"]) if event["SUSPEND_END_TIME"] else None
    _require(began <= start and (ended is None or ended >= end), "suspension does not cover interval")
    return began, ended


def _scheduled_between(start: date, end: date):
    day = start + timedelta(days=1)
    while day < end:
        closures = closed_dates(day.year)
        _require(closures is not None, "unknown trading calendar")
        if day.weekday() < 5 and day not in closures:
            yield day
        day += timedelta(days=1)


def build_candidate(
    spec: RecoverySpec, *, stock_codes: Sequence[str], bars: Sequence[dict],
    actions: Sequence[dict], quotes: Mapping[str, dict], suspensions: Sequence[dict],
    historical_witnesses: Sequence[dict],
) -> dict:
    """Return proposed rows plus exclusions and unresolved publication blockers.

    Inputs are explicit rows, not live providers or a DB connection. Bad/missing
    input fails closed; source rows and caller collections are never mutated.
    """
    td, prev, codes = _scope(spec.trade_date, stock_codes)
    scope = set(codes)
    _require(scope_fingerprint(td, codes) == spec.scope_sha256, "scope fingerprint changed")
    _require(set(quotes) == scope, "quote scope mismatch")
    resumed = _index(spec.resumptions, lambda r: r.code)
    rounding = _index(spec.rounding_differences, lambda r: r.code)
    for declared in (spec.suspended_codes, tuple(resumed), spec.adjustment_codes, tuple(rounding)):
        _require(len(declared) == len(set(declared)) and set(declared) <= scope, "invalid exception scope")
    _require(not set(resumed) & set(spec.suspended_codes), "conflicting resumption and suspension")
    for ref in resumed.values():
        _require(type(ref.last_trade_date) is date and type(ref.suspension_start) is date
                 and ref.last_trade_date < ref.suspension_start <= prev,
                 "invalid resumption dates")
        _scope(ref.last_trade_date, [ref.code])
        _scope(ref.suspension_start, [ref.code])
        _require(_number(ref.close) is not None and ref.close > 0, "invalid resumption close")
    first = min([prev, *(r.last_trade_date for r in resumed.values())])
    for row in bars:
        _require_fields(row, ("stock_ts_code", "trade_date", "open", "high", "low", "close",
                              "volume", "turnover", "adjusted", "source", "updated_at"), "bar")
    for row in actions:
        _require_fields(row, ("stock_ts_code", "ex_date", "dividend_per_share", "per_share_bonus",
                              "allotment_ratio", "allotment_price", "currency", "source", "updated_at"),
                        "adjustment")
    bar_map = _index(bars, lambda r: (r["stock_ts_code"], _day(r["trade_date"])))
    action_map = _index(actions, lambda r: (r["stock_ts_code"], _day(r["ex_date"])))
    _require(all(code in scope and first <= day <= td for code, day in bar_map), "bar outside declared window")
    _require(all(code in scope and first <= day <= td for code, day in action_map), "action outside declared window")
    _require({code for code, day in action_map if day == td} == set(spec.adjustment_codes),
             "target adjustment set changed")
    current_codes = {code for code, day in bar_map if day == td}
    _require(scope - current_codes == set(spec.suspended_codes), "unexpected missing or resumed current bar")
    for row in suspensions:
        _require_fields(row, ("SECUCODE",), "suspension")
    events = _index(suspensions, lambda r: r["SECUCODE"])
    for row in historical_witnesses:
        _require_fields(row, ("stock_ts_code", "trade_date", "open", "high", "low", "close",
                              "volume", "amount", "source", "raw_sha256"), "historical witness")
    witnesses = _index(historical_witnesses, lambda r: (r["stock_ts_code"], _day(r["trade_date"])))
    _require(set(witnesses) == {(r.code, r.last_trade_date) for r in resumed.values()}, "historical witness scope")
    proposed, excluded, used_rounding = [], [], set()
    for code in codes:
        quote = quotes[code]
        unit = _quote(quote, code, td)
        if code in spec.suspended_codes:
            _require(code in events, "missing suspension evidence")
            _suspension(events[code], code, datetime.combine(td, time(9, 30)), datetime.combine(td, time(15)))
            _require(all(quote[field] == 0 for field in ("open", "high", "low", "volume_shares", "amount_yuan", "pct_chg"))
                     and quote["close"] == quote["pre_close"], "suspended quote has activity")
            excluded.append({"stock_ts_code": code, "reason": "provider_suspension_and_zero_activity",
                             "synthetic_bar": False, "official_status_verified": False})
            continue
        previous_day = prev
        reference = resumed.get(code)
        if reference:
            _require(code in events, "missing resumption event")
            _require_fields(events[code], ("PREDICT_RESUME_DATE",), "resumption")
            previous_day = reference.last_trade_date
            began, ended = _suspension(events[code], code,
                datetime.combine(reference.suspension_start, time(9, 30)), datetime.combine(prev, time(15)))
            _require(began == datetime.combine(reference.suspension_start, time(9, 30))
                     and ended == datetime.combine(prev, time(15))
                     and _timestamp(events[code]["PREDICT_RESUME_DATE"]).date() == td, "resumption interval changed")
            _require(all(day >= reference.suspension_start for day in _scheduled_between(previous_day, td)),
                     "unexplained scheduled days before suspension")
            _require(not any(c == code and previous_day < day < td for c, day in bar_map),
                     "unexpected bar during suspension")
            _require(not any(c == code and previous_day < day <= td for c, day in action_map),
                     "recorded action across resumption gap")
            witness = witnesses[(code, previous_day)]
            _require(witness["source"] == "sina:historical:unadjusted"
                     and isinstance(witness["raw_sha256"], str)
                     and re.fullmatch(r"[a-f0-9]{64}", witness["raw_sha256"]) is not None
                     and witness["close"] == reference.close == quote["pre_close"], "resumption witness mismatch")
        _require((code, previous_day) in bar_map, "missing required previous bar")
        _require(quote["volume_shares"] > 0 and quote["amount_yuan"] > 0, "inactive quote for trading bar")
        current, previous = bar_map[(code, td)], bar_map[(code, previous_day)]
        if reference:
            _require(previous["close"] == reference.close, "resumption stored close mismatch")
            _require(all(previous[field] == witness[field] for field in ("open", "high", "low", "close", "volume"))
                     and _number(witness["amount"]) is not None
                     and abs(previous["turnover"] - witness["amount"]) <= 1,
                     "resumption historical bar mismatch")
        try:
            row, gaps = _calculate(code, current, previous, action_map.get((code, td)))
        except (DecimalException, ValueError, OverflowError) as exc:
            raise CandidateRefused("invalid arithmetic") from exc
        _require(not gaps, "invalid bar or action: " + ",".join(gaps))
        for field in ("open", "high", "low", "close", "pre_close"):
            _require(row[field] == quote[field], "cross-source price mismatch")
        _require(abs(current["turnover"] - quote["amount_yuan"]) <= 1.0, "cross-source amount mismatch")
        _require(abs(current["volume"] - quote["volume_shares"]) <= (0 if unit == "shares" else 100),
                 "cross-source volume mismatch")
        _require(current["low"] * current["volume"] - 1 <= current["turnover"] <= current["high"] * current["volume"] + 1,
                 "historical amount and volume inconsistent with price range")
        if row["pct_chg"] != quote["pct_chg"]:
            exception = rounding.get(code)
            _require(exception is not None and (row["close"], row["pre_close"], row["pct_chg"], quote["pct_chg"])
                     == (exception.close, exception.pre_close, exception.calculated_pct, exception.quoted_pct),
                     "unapproved percentage difference")
            # Integer cents avoid context-dependent Decimal division at exact half-cent ties.
            close_cents, pre_cents = _cents(row["close"]), _cents(row["pre_close"])
            _require((abs(close_cents - pre_cents) * 10000) % pre_cents * 2 == pre_cents
                     and abs(_cents(row["pct_chg"]) - _cents(quote["pct_chg"])) == 1,
                     "percentage difference is not a one-cent rounding tie")
            used_rounding.add(code)
        row = {**row, "trade_date": str(td), "stock_name": quote["name"], "turnover": None,
               "name_source": "tencent:captured-dated-quote", "name_observed_at": quote["quote_timestamp"],
               "observed_turnover_pct": quote["turnover_pct"], "turnover_status": "unverified_not_projected",
               "previous_observation_date": str(previous_day)}
        if reference:
            row["reference_basis"] = "named_resumption_no_recorded_interval_action"
            row["reference_witness_sha256"] = witnesses[(code, previous_day)]["raw_sha256"]
        proposed.append(row)
    _require(used_rounding == set(rounding), "unused rounding exception")
    result = {"contract_version": CONTRACT_VERSION, "trade_date": str(td),
              "previous_trade_date": str(prev), "scope_fingerprint": spec.scope_sha256,
              "declared_scope_count": len(codes), "candidate_row_count": len(proposed),
              "excluded_count": len(excluded), "rows": proposed, "exclusions": excluded,
              "rounding_difference_codes": sorted(used_rounding), "candidate_constructed": True,
              "production_ready": False, "database_writes": False, "publication_attempted": False,
              "blockers": ["historical_universe_authority", "name_source_acceptance", "turnover_unverified",
                           "adjustment_completeness_unverified", "nontrading_denominator_policy",
                           "downstream_and_l2_gates", "write_and_publish_authorization"]}
    # Include unused interval observations too: a report hash alone cannot bind evidence.
    inputs = {"spec": asdict(spec), "stock_codes": codes, "quotes": quotes}
    for name, collection in (("bars", bars), ("actions", actions),
                             ("suspensions", suspensions), ("witnesses", historical_witnesses)):
        inputs[name] = sorted(json.dumps(row, sort_keys=True, default=str, allow_nan=False)
                              for row in collection)
    result["input_fingerprint"] = _hash(json.loads(json.dumps(inputs, default=str, allow_nan=False)))
    result["candidate_fingerprint"] = _hash(result)
    return result
