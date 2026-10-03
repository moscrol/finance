#!/usr/bin/env python3
"""Fail-closed read-only stock-day/captured-quote reconciliation.

This is a diagnostic, NOT a stock-day writer or release permission. The capture
has no independent market-universe or official suspension attestation; field 38
has not been cleared as a redistributable canonical turnover source.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path
import sys

import duckdb

from market_feature_store.hithink_stock_preview import preview_stock_calculation
from market_feature_store.sync.bridge_hithink_stock_daily import resolve_universe
from scripts.audit_dated_quote_capture import audit_capture, checked_raw, parse_quotes

CENT = Decimal("0.01")
AMOUNT_TOLERANCE = Decimal("1.01")  # capture's yuan amount has no decimal cents


class GapAuditRefused(ValueError):
    """Evidence incomplete or inconsistent; never emit a passing diagnostic."""


def dec(value: object) -> Decimal:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise GapAuditRefused("nonnumeric value") from exc
    if not number.is_finite():
        raise GapAuditRefused("nonfinite value")
    return number


def load_quotes(root: Path, target: date) -> tuple[dict, dict]:
    attestation = audit_capture(root, target)
    if not attestation.get("capture_validated") or attestation.get("production_ready") is not False:
        raise GapAuditRefused("capture attestation is not diagnostic-only")
    receipt = json.loads((root / "receipt.json").read_text(encoding="utf-8"))
    quotes: dict[str, dict] = {}
    for batch in receipt["batches"]:
        chunk = parse_quotes(checked_raw(root, batch), target)
        if set(chunk) & set(quotes):
            raise GapAuditRefused("duplicate quote identity")
        quotes.update(chunk)
    if set(quotes) != set(receipt["codes"]):
        raise GapAuditRefused("capture identity mismatch")
    return attestation, quotes


def validate_joined_bar(row: tuple, quote: dict, target: date) -> str:
    """Return diagnostic turnover candidate, never a canonical write value."""
    code, canonical_close, raw_shares, raw_amount = row
    if not quote or quote["quote_timestamp"][:8] != target.strftime("%Y%m%d"):
        raise GapAuditRefused(f"{code}: missing or wrong-date sealed quote")
    price, shares, amount = dec(quote["close"]), dec(raw_shares), dec(raw_amount)
    rate = dec(quote["turnover_pct"])
    if (price != dec(canonical_close) or dec(quote["amount_yuan"]) - amount > AMOUNT_TOLERANCE
            or amount - dec(quote["amount_yuan"]) > AMOUNT_TOLERANCE):
        raise GapAuditRefused(f"{code}: cross-source close/amount mismatch")
    if shares <= 0 or amount <= 0 or not 0 <= rate <= 100:
        raise GapAuditRefused(f"{code}: invalid active-bar/rate")
    # Tencent float-market-cap field 44 is not exposed by the existing parser.
    # The separate whole-day study confirms 5553/5553 against that field, but
    # this narrower reusable gate deliberately avoids trusting an untyped field.
    if abs(dec(quote["volume_shares"]) - shares) > 100:
        raise GapAuditRefused(f"{code}: cross-source volume mismatch")
    return str(rate.quantize(CENT))


def validate_gapfill_row(row: tuple, quote: dict | None, target: date) -> dict:
    """Audit an already-inserted exceptional row; never authorize that insertion."""
    (code, close, raw_shares, raw_amount, source, pre_close, pct_chg,
     op, high, low, volume_hands, amount_yi, raw_op, raw_high, raw_low, raw_close) = row
    if source != "hithink:daily-k-10d:gapfill-two-source":
        raise GapAuditRefused(f"{code}: unrecognized exceptional row source")
    if ([dec(x) for x in (op, high, low, close)]
            != [dec(x) for x in (raw_op, raw_high, raw_low, raw_close)]):
        raise GapAuditRefused(f"{code}: exceptional raw OHLC differs")
    expected_hands = (dec(raw_shares) / 100).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    expected_amount = (dec(raw_amount) / Decimal(10**8)).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP)
    if dec(volume_hands) != expected_hands or dec(amount_yi) != expected_amount:
        raise GapAuditRefused(f"{code}: exceptional volume/amount differs")
    if dec(pre_close) <= 0 or not dec(pct_chg).is_finite():
        raise GapAuditRefused(f"{code}: invalid exceptional reference")
    independent = "quote_reference_unavailable"
    if quote is not None:
        validate_joined_bar(row[:4], quote, target)
        if dec(pre_close) != dec(quote["pre_close"]) or dec(pct_chg) != dec(quote["pct_chg"]):
            raise GapAuditRefused(f"{code}: exceptional reference disagrees with quote")
        independent = "quote_reference_matched_not_official_event"
    return {"stock_ts_code": code, "source": source, "reference_check": independent}


def audit_day(con: duckdb.DuckDBPyConnection, root: Path, target: date) -> dict:
    if not isinstance(target, date) or type(target) is not date:
        raise GapAuditRefused("explicit date required")
    attestation, quotes = load_quotes(root, target)
    day = target.isoformat()
    vendor_codes = resolve_universe(con, day)
    if not vendor_codes or len(set(vendor_codes)) != len(vendor_codes):
        raise GapAuditRefused("missing or duplicate vendor scope")
    preview = preview_stock_calculation(con, day, stock_codes=vendor_codes)
    gaps = preview["gaps"]
    valid = preview["rows"]
    if (preview["requested_stock_count"] != len(vendor_codes)
            or preview["calculated_stock_count"] != len(valid)
            or len(valid) + len(gaps) != len(vendor_codes)
            or {r["stock_ts_code"] for r in valid} | {r["stock_ts_code"] for r in gaps} != set(vendor_codes)):
        raise GapAuditRefused("preview does not account for its declared scope")
    prev = con.execute(
        "SELECT max(trade_date) FROM fact_stock_daily WHERE trade_date < ?", [day]
    ).fetchone()[0]
    if prev is None or str(prev) != preview["previous_trade_date"]:
        raise GapAuditRefused("previous canonical day does not match schedule")
    previous_codes = {r[0] for r in con.execute(
        "SELECT stock_ts_code FROM fact_stock_daily WHERE trade_date=?", [prev]
    ).fetchall()}
    absent = sorted(previous_codes - set(vendor_codes))
    canonical = con.execute("""
        SELECT c.stock_ts_code,c.close,r.volume,r.turnover,c.source,
               c.pre_close,c.pct_chg,c.open,c.high,c.low,c.volume,c.amount,
               r.open,r.high,r.low,r.close
        FROM fact_stock_daily AS c JOIN fact_stock_daily_hithink AS r
          ON c.trade_date=r.trade_date AND c.stock_ts_code=r.stock_ts_code
        WHERE c.trade_date=? ORDER BY c.stock_ts_code
    """, [day]).fetchall()
    canonical_count = con.execute(
        "SELECT count(*) FROM fact_stock_daily WHERE trade_date=?", [day]
    ).fetchone()[0]
    c_codes = [r[0] for r in canonical]
    good = {r["stock_ts_code"]: r for r in valid}
    exceptional = {r["stock_ts_code"] for r in gaps}
    if (len(c_codes) != len(set(c_codes)) or len(canonical) != canonical_count
            or not set(good) <= set(c_codes) or not set(c_codes) <= set(good) | exceptional):
        raise GapAuditRefused("canonical identity differs from valid+exceptional scope")
    candidates: list[tuple[str, str, str]] = []
    inspected_exceptions = []
    for row in canonical:
        code = row[0]
        if code in exceptional:
            inspected_exceptions.append(validate_gapfill_row(row, quotes.get(code), target))
            continue
        ref = good[code]
        if (row[4] != ref["bar_source"] or dec(row[5]) != dec(ref["pre_close"])
                or dec(row[6]) != dec(ref["pct_chg"])
                or [dec(x) for x in (row[7], row[8], row[9], row[1], row[10], row[11])]
                != [dec(ref[x]) for x in ("open", "high", "low", "close", "volume", "amount")]):
            raise GapAuditRefused(f"{code}: preview-valid canonical row differs")
        value = validate_joined_bar(row[:4], quotes.get(code), target)
        candidates.append((day, code, value))
    counts = Counter(reason for gap in gaps for reason in gap["reasons"])
    fingerprint = hashlib.sha256(json.dumps(candidates, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    return {
        "trade_date": day, "kind": "read_only_gap_reconciliation_NOT_a_backfill",
        "source_scope_count": len(vendor_codes), "preview_calculated_count": len(valid),
        "preview_gaps": gaps, "preview_gap_reason_counts": dict(sorted(counts.items())),
        "absent_from_vendor_previous_canonical_codes": absent,
        "previous_canonical_day": str(prev), "canonical_rows_aligned": len(candidates),
        "canonical_total_rows": canonical_count,
        "canonical_gapfill_exceptions": inspected_exceptions,
        "canonical_gapfill_exception_count": len(inspected_exceptions),
        "gapfill_reference_unavailable_count": sum(
            x["reference_check"] == "quote_reference_unavailable" for x in inspected_exceptions),
        "quote_capture": {k: attestation[k] for k in (
            "validated_batches", "validated_quote_count", "capture_validated",
            "independent_market_universe_verified", "official_suspension_status_verified",
            "production_ready")},
        "quote_matched_canonical_count": len(candidates),
        "candidate_field38_percentage_sha256": fingerprint,
        "candidate_field38_value_count": len(candidates),
        "preview_input_fingerprint": preview["input_fingerprint"],
        "production_ready": False, "database_writes": False,
        "publication_attempted": False,
        "missing_permissions": ["independent_market_universe", "official_event_evidence",
                                "supplier_field_contract_and_usage_license", "field_level_provenance",
                                "review_and_write_authorization"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--capture-dir", type=Path, required=True)
    parser.add_argument("--trade-date", type=date.fromisoformat, required=True)
    parser.add_argument("--json", type=Path, help="Create a new diagnostic file; never overwrite")
    args = parser.parse_args(argv)
    try:
        with duckdb.connect(str(args.db), read_only=True) as con:
            report = audit_day(con, args.capture_dir, args.trade_date)
        content = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if args.json:
            with args.json.open("x", encoding="utf-8") as output:
                output.write(content)
        print(content, end="")
        return 0
    except (OSError, ValueError, KeyError, TypeError, duckdb.Error) as exc:
        print(json.dumps({"error_type": type(exc).__name__, "diagnostic_complete": False,
                          "production_ready": False, "database_writes": False,
                          "publication_attempted": False}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    sys.exit(main())
