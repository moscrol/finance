#!/usr/bin/env python3
"""Replay a captured Tencent quote batch without network or database access.

Prevent a successful HTTP response from hiding missing/duplicate codes, stale
quotes, altered raw files, or 100x volume-unit errors. This is evidence validation,
not a historical market-universe check or a publication gate. The observed 688/689
share unit is also checked against the OHLC-implied notional on every active row.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any

QUOTE = re.compile(r'v_((?:sh|sz|bj)[0-9]{6})="([^"\r\n]*)";')
CODE = re.compile(r'[0-9]{6}\.(?:SH|SZ|BJ)')


def unique_codes(values: Any) -> set[str]:
    if (not isinstance(values, list) or not values
            or any(not isinstance(v, str) or not CODE.fullmatch(v) for v in values)
            or len(values) != len(set(values))):
        raise ValueError("invalid or duplicate declared codes")
    return set(values)


def parse_quotes(raw: bytes, trade_date: date) -> dict[str, dict[str, Any]]:
    quotes = {}
    for line in raw.decode("gbk").splitlines():
        if not line.strip():
            continue
        match = QUOTE.fullmatch(line.strip())
        if match is None:
            raise ValueError("unrecognized quote record")
        symbol, body = match.groups()
        fields = body.split("~")
        code = symbol[2:] + "." + symbol[:2].upper()
        if len(fields) < 58 or fields[2] != symbol[2:] or code in quotes or not fields[1]:
            raise ValueError("short, nameless, mismatched or duplicate quote")
        stamp = datetime.strptime(fields[30], "%Y%m%d%H%M%S")
        if stamp.date() != trade_date or (stamp.hour, stamp.minute) < (15, 0):
            raise ValueError("quote is not from requested date after market close")
        trade = fields[35].split("/")
        if len(trade) != 3:
            raise ValueError("invalid trade tuple")
        numbers = {"close": fields[3], "pre_close": fields[4], "open": fields[5],
                   "raw_volume": fields[6], "pct_chg": fields[32],
                   "high": fields[33], "low": fields[34], "amount_yuan": trade[2],
                   "turnover_pct": fields[38]}
        values = {key: float(value) for key, value in numbers.items()}
        if any(not math.isfinite(value) for value in values.values()):
            raise ValueError("nonfinite quote")
        if values["close"] <= 0 or values["pre_close"] <= 0:
            raise ValueError("nonpositive reference or close")
        if (values["raw_volume"] < 0 or not values["raw_volume"].is_integer()
                or values["amount_yuan"] < 0 or values["turnover_pct"] < 0):
            raise ValueError("invalid volume, amount or turnover")
        if float(trade[0]) != values["close"] or float(trade[1]) != values["raw_volume"]:
            raise ValueError("inconsistent trade tuple")
        shares_unit = code.startswith(("688", "689")) and code.endswith(".SH")
        shares = values["raw_volume"] * (1 if shares_unit else 100)
        low, high = values["low"], values["high"]
        if shares > 0:
            if not 0 < low <= min(values["open"], values["close"]) <= max(values["open"], values["close"]) <= high:
                raise ValueError("invalid OHLC")
            tolerance = 1 if shares_unit else 100
            if (values["amount_yuan"] <= 0
                    or not low * max(0, shares - tolerance) - 1 <= values["amount_yuan"] <= high * (shares + tolerance) + 1):
                raise ValueError("volume unit or amount inconsistent with OHLC")
        elif (values["amount_yuan"] != 0
              or any(values[key] != 0 for key in ("open", "high", "low"))
              or values["close"] != values["pre_close"] or values["pct_chg"] != 0):
            raise ValueError("inconsistent zero-activity quote")
        quotes[code] = {"name": fields[1], "quote_timestamp": fields[30],
                        "raw_status_field_40": fields[40], "volume_shares": shares,
                        "raw_volume_unit": "shares" if shares_unit else "hands", **values}
    if not quotes:
        raise ValueError("empty quote capture")
    return quotes


def checked_raw(root: Path, entry: dict[str, Any]) -> bytes:
    name = entry["file"]
    if not isinstance(name, str) or Path(name).name != name:
        raise ValueError("raw file must be a local basename")
    path = root / name
    if path.is_symlink():
        raise ValueError("raw file must not be a symlink")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
        raise ValueError("raw capture hash changed")
    return raw


def load_capture(root: Path, trade_date: date, *, receipt_sha256: str | None = None
                 ) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Return the exact validated observations; never reread raw bytes to apply them."""
    raw_receipt = (root / "receipt.json").read_bytes()
    if receipt_sha256 is not None and hashlib.sha256(raw_receipt).hexdigest() != receipt_sha256:
        raise ValueError("capture receipt hash changed")
    receipt = json.loads(raw_receipt)
    if receipt["target_date"] != trade_date.isoformat():
        raise ValueError("receipt date mismatch")
    expected = unique_codes(receipt["codes"])
    quotes: dict[str, dict[str, Any]] = {}
    filenames: set[str] = set()
    for batch in receipt["batches"]:
        declared = unique_codes(batch["codes"])
        if "error_type" in batch or batch.get("http_status") != 200:
            raise ValueError("failed capture batch")
        if batch["file"] in filenames or declared & quotes.keys() or not declared <= expected:
            raise ValueError("duplicate or unexpected capture batch")
        parsed = parse_quotes(checked_raw(root, batch), trade_date)
        if set(parsed) != declared:
            raise ValueError("response identities do not match requested batch")
        filenames.add(batch["file"])
        quotes.update(parsed)
    if set(quotes) != expected or receipt["captured_code_count"] != len(expected):
        raise ValueError("capture does not cover its declared scope")
    return quotes, {"trade_date": trade_date.isoformat(), "declared_scope_count": len(expected),
            "validated_quote_count": len(quotes), "validated_batches": len(filenames),
            "volume_units": dict(Counter(q["raw_volume_unit"] for q in quotes.values())),
            "zero_activity_codes": sorted(c for c, q in quotes.items() if q["volume_shares"] == 0),
            "capture_validated": True, "independent_market_universe_verified": False,
            "official_suspension_status_verified": False, "production_ready": False,
            "database_writes": False, "publication_attempted": False}


def audit_capture(root: Path, trade_date: date) -> dict[str, Any]:
    return load_capture(root, trade_date)[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-dir", type=Path, required=True)
    parser.add_argument("--trade-date", type=date.fromisoformat, required=True)
    parser.add_argument("--json", type=Path, help="New output file; existing evidence is never overwritten")
    args = parser.parse_args(argv)
    try:
        result = audit_capture(args.capture_dir, args.trade_date)
        text = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if args.json:
            with args.json.open("x", encoding="utf-8") as handle:
                handle.write(text)
        print(text, end="")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"capture_validated": False, "error_type": type(exc).__name__,
                          "production_ready": False, "database_writes": False,
                          "publication_attempted": False}))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
