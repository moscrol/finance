"""Offline, hash-bound quote inputs for recover_local_review's preparation mode.

Hashes bind bytes, not supplier authenticity or publication authority. Suspensions
remain identities without bars. No database, network or publication writes here.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
import hashlib
import json
from pathlib import Path
import re

from market_feature_store.hithink_recovery_candidate import _cents, _quote, _suspension, _timestamp
from market_feature_store.hithink_stock_preview import _scope
from market_feature_store.recovery_coverage import market_breadth, partition_scope
from scripts.audit_dated_quote_capture import load_capture

SOURCE = "tencent:captured-dated-quote"
CONTRACT = "dated-quote-recovery-v1"


@dataclass(frozen=True)
class PreparedDay:
    trade_date: date
    rows: tuple[tuple, ...]
    evidence: dict


def _digest(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("expected an explicit lowercase SHA256")
    return value


def _path(base: Path, value: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError("expected an input path")
    path = Path(value).expanduser()
    return path if path.is_absolute() else base / path


def read_pinned(path: Path, expected_sha256: str) -> bytes:
    expected = _digest(expected_sha256)
    if path.is_symlink():
        raise ValueError("pinned input must not be a symlink")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f"input hash changed: {path.name}")
    return raw


def suspension_codes(raw: bytes, day: date) -> tuple[list[str], list[str]]:
    payload = json.loads(raw)
    if not isinstance(payload, dict) or not isinstance(payload.get("result"), dict):
        raise ValueError("invalid suspension directory response")
    result = payload["result"]
    rows = result.get("data")
    if (payload.get("success") is not True or type(payload.get("code")) is not int or payload["code"] != 0
            or type(result.get("pages")) is not int or result["pages"] != 1
            or not isinstance(rows, list) or type(result.get("count")) is not int
            or result["count"] != len(rows)):
        raise ValueError("suspension directory must be a successful complete single page")
    opened, closed = datetime.combine(day, time(9, 30)), datetime.combine(day, time(15))
    stopped, excluded = [], []
    for event in rows:
        code = event["SECUCODE"]
        if event["SECURITY_TYPE_CODE"] == "058001002":
            excluded.append(code)
            continue
        if event["SECURITY_TYPE_CODE"] != "058001001":
            raise ValueError("unknown suspension security type")
        _scope(day, [code])
        if event["SECURITY_CODE"] != code[:6]:
            raise ValueError("suspension identity mismatch")
        began = _timestamp(event["SUSPEND_START_TIME"])
        ended = _timestamp(event["SUSPEND_END_TIME"]) if event["SUSPEND_END_TIME"] else None
        if ended is not None and ended < began:
            raise ValueError("reversed suspension interval")
        if began > opened or (ended is not None and ended < closed):
            excluded.append(code)
            continue
        _suspension(event, code, opened, closed)
        if code in stopped:
            raise ValueError("duplicate applicable suspension identity")
        stopped.append(code)
    return sorted(stopped), sorted(excluded)


def load_manifest(path: Path, expected_sha256: str) -> tuple[PreparedDay, ...]:
    manifest = json.loads(read_pinned(path, expected_sha256))
    if not isinstance(manifest, dict):
        raise ValueError("invalid dated quote recovery manifest")
    days = manifest.get("days")
    if (manifest.get("contract_version") != CONTRACT or not isinstance(days, list)
            or not days or any(not isinstance(day, dict) for day in days)):
        raise ValueError("invalid dated quote recovery manifest")
    prepared = []
    now = datetime.now()
    for item in days:
        day, _, codes = _scope(item["trade_date"], item["declared_codes"])
        if prepared and day <= prepared[-1].trade_date:
            raise ValueError("recovery dates must be unique and increasing")
        basis = item.get("scope_basis")
        if not isinstance(basis, str) or not basis.strip():
            raise ValueError("explicit scope basis required")
        captures = item["captures"]
        if not isinstance(captures, list) or not captures:
            raise ValueError("at least one dated capture required")
        quotes, audits = {}, []
        for capture in captures:
            root = _path(path.parent, capture["directory"])
            receipt_hash = _digest(capture["receipt_sha256"])
            observations, audit = load_capture(root, day, receipt_sha256=receipt_hash)
            _scope(day, list(observations))
            if quotes.keys() & observations.keys():
                raise ValueError("overlapping capture identities")
            quotes.update(observations)
            audits.append({"directory": str(root.resolve()), "receipt_sha256": receipt_hash, **audit})
        reference = item["suspensions"]
        reference_path = _path(path.parent, reference["path"])
        stopped, excluded = suspension_codes(read_pinned(reference_path, reference["sha256"]), day)
        active = sorted(code for code, quote in quotes.items() if quote["volume_shares"] > 0)
        if not quotes.keys() <= set(codes):
            raise ValueError("captured identity outside declared recovery scope")
        coverage = partition_scope(declared=codes, observed=active, suspended=stopped)
        rows, breadth_rows = [], []
        for code, quote in sorted(quotes.items()):
            _quote(quote, code, day)
            close, previous, pct = (_cents(quote[k]) for k in ("close", "pre_close", "pct_chg"))
            # Integer arithmetic checks the supplier's two-decimal percentage:
            # either tie direction is valid, but > half a displayed tick is not.
            if abs((close - previous) * 10000 - pct * previous) * 2 > previous:
                raise ValueError(f"quoted percentage disagrees with reference: {code}")
            if quote["volume_shares"] == 0:
                continue
            for key in ("open", "high", "low"):
                _cents(quote[key])
            amount = quote["amount_yuan"] / 1e8
            rows.append((day, code, quote["name"], quote["close"], quote["pre_close"],
                         quote["pct_chg"], amount, None, SOURCE, now,
                         quote["open"], quote["high"], quote["low"], quote["volume_shares"] / 100))
            breadth_rows.append({"stock_ts_code": code, "pct_chg": quote["pct_chg"], "amount": amount})
        if not rows:
            raise ValueError("no traded observations to prepare")
        evidence = {
            "trade_date": str(day), "manifest_sha256": expected_sha256,
            "scope_basis": basis, "declared_codes": codes, "coverage": coverage,
            "captures": audits, "source": SOURCE,
            "name_basis": "same-date captured provider name",
            "reference_basis": "same-date captured provider reference, not prior raw close",
            "canonical_units": {"amount": "CNY 100 million", "volume": "hands"},
            "turnover_contract": "null_not_zero_not_carried_not_inferred",
            "observations": [{"stock_ts_code": code, "name_source": SOURCE,
                              "name_observed_at": quotes[code]["quote_timestamp"],
                              "observed_turnover_pct": quotes[code]["turnover_pct"]} for code in active],
            "suspensions": {"path": str(reference_path.resolve()), "sha256": reference["sha256"],
                            "applicable_codes": stopped, "excluded_codes": excluded},
            "breadth": market_breadth(breadth_rows, stopped), "synthetic_rows": 0,
            "official_suspension_status_verified": False, "production_ready": False,
        }
        prepared.append(PreparedDay(day, tuple(rows), evidence))
    return tuple(prepared)
