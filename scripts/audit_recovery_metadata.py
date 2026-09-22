#!/usr/bin/env python3
"""Offline recovery field/denominator diagnostics, never a database writer.

Named quote fields are parsed by the existing dated-capture validator. Tencent
positions 72/73/76 remain *unnamed denominator observations*: internal numerical
agreement does not establish their economic meaning, historical validity, or
independence from another vendor. A current comparison list is never a PIT list.
"""
from __future__ import annotations

import argparse
from datetime import date
import json
import math
from pathlib import Path
import re
from typing import Mapping, Sequence

from market_feature_store.recovery_coverage import market_breadth, partition_scope
from scripts.audit_dated_quote_capture import (
    QUOTE,
    audit_capture,
    checked_raw,
    parse_quotes,
    unique_codes,
)


def _number(value) -> float:
    if isinstance(value, bool):
        raise ValueError("boolean metadata number")
    try:
        result = float(value)
    except (ValueError, TypeError) as exc:
        raise ValueError("invalid metadata number") from exc
    if not math.isfinite(result) or result < 0:
        raise ValueError("invalid metadata number")
    return result


def _name_flags(name: str) -> dict:
    if not isinstance(name, str) or not name.strip() or any(ord(c) < 32 for c in name):
        raise ValueError("invalid display name")
    # Preserve the original spelling. This only diagnoses the current consumer's
    # name-based predicates; it does not establish official ST/IPO status.
    return {"st": "ST" in name, "new": name.startswith(("N", "C")),
            "ex_prefix": name.startswith(("XD", "XR", "DR"))}


def assess_metadata(candidate: Mapping, *, raw_batches: Sequence[bytes],
                    comparison_rows: Sequence[Mapping]) -> dict:
    """Audit fixed inputs. No IO, no candidate mutation, and no publication grant."""
    td = date.fromisoformat(candidate["trade_date"])
    quotes, fields = {}, {}
    for raw in raw_batches:
        parsed = parse_quotes(raw, td)
        if quotes.keys() & parsed.keys():
            raise ValueError("duplicate quote across batches")
        quotes.update(parsed)
        for line in raw.decode("gbk").splitlines():
            if not line.strip():
                continue
            match = QUOTE.fullmatch(line.strip())  # parse_quotes already validated it
            symbol, body = match.groups()
            fields[symbol[2:] + "." + symbol[:2].upper()] = body.split("~")
    rows = candidate["rows"]
    active = [r["stock_ts_code"] for r in rows]
    suspended = [r["stock_ts_code"] for r in candidate["exclusions"]]
    partition = partition_scope(declared=sorted(quotes), observed=active, suspended=suspended)
    for key, expected in (("declared_scope_count", partition["declared_count"]),
                          ("candidate_row_count", len(rows)), ("excluded_count", len(suspended))):
        if type(candidate[key]) is not int or candidate[key] != expected:
            raise ValueError("candidate count mismatch")
    if any(r.get("synthetic_bar") is not False for r in candidate["exclusions"]):
        raise ValueError("synthetic nontrading bar")
    for code in suspended:
        if quotes[code]["volume_shares"] != 0:
            raise ValueError("nontrading quote has activity")
    refs = {}
    for row in comparison_rows:
        code = row["code"] + "." + row["symbol"][:2].upper()
        unique_codes([code])
        if row["symbol"] != code[-2:].lower() + code[:6] or code in refs or code not in quotes:
            raise ValueError("comparison identity mismatch")
        _name_flags(row["name"])
        refs[code] = row
    name_diffs, rate_diffs, internal_mismatches = [], [], []
    for row in rows:
        code = row["stock_ts_code"]
        q = quotes[code]
        if (q["volume_shares"] <= 0 or row["stock_name"] != q["name"]
                or row["name_observed_at"] != q["quote_timestamp"]
                or row["name_source"] != "tencent:captured-dated-quote"
                or row["turnover"] is not None
                or row["observed_turnover_pct"] != q["turnover_pct"]):
            raise ValueError("candidate field provenance mismatch")
        _name_flags(q["name"])
        if code not in refs:
            continue
        ref = refs[code]
        a, b = _name_flags(ref["name"]), _name_flags(q["name"])
        if ref["name"] != q["name"]:
            def compact(name):
                return re.sub(r"\s+", "", name)

            name_diffs.append({"code": code, "dated_display_name": q["name"],
                "undated_comparison_name": ref["name"],
                "whitespace_only": compact(ref["name"]) == compact(q["name"]),
                "classification_flags_differ": any(a[k] != b[k] for k in ("st", "new")),
                "ex_prefix_differs": a["ex_prefix"] != b["ex_prefix"]})
        rate = _number(ref["turnoverratio"])
        volume, price, cap = (_number(ref[k]) for k in ("volume", "trade", "nmc"))
        # Sina nmc is observed in 10k yuan. These equations are diagnostic,
        # not acceptance tests for a free-float/negotiable-share definition.
        ref_denom = cap * 10000 / price if price > 0 and cap > 0 else None
        ref_calc = volume / ref_denom * 100 if ref_denom else None
        raw_fields = fields[code]
        observations = {}
        for position in (72, 73, 76):
            value = raw_fields[position] if len(raw_fields) > position else ""
            denominator = _number(value) if value else None
            calc = q["volume_shares"] / denominator * 100 if denominator else None
            # Raw hand quotes round at up to 100 shares; percentage at .01 pp.
            tolerance = .005001 + (10000 / denominator if q["raw_volume_unit"] == "hands" else 0) if denominator else None
            observations[str(position)] = {"raw_denominator": denominator, "calculated_pct": calc,
                "matches_quoted_pct": calc is not None and abs(calc - q["turnover_pct"]) <= tolerance}
        primary_matches = observations["72"]["matches_quoted_pct"]
        ref_matches = ref_calc is not None and abs(ref_calc - rate) <= .000011
        if not primary_matches or not ref_matches:
            internal_mismatches.append({"code": code, "tencent_field72_matches": primary_matches,
                                        "sina_nmc_matches": ref_matches})
        if abs(rate - q["turnover_pct"]) > .011:
            rate_diffs.append({"code": code, "dated_quote_pct": q["turnover_pct"],
                "undated_comparison_pct": rate, "comparison_implied_denominator": ref_denom,
                "comparison_calculated_pct": ref_calc, "raw_quote_denominators": observations,
                "both_internally_reproducible": primary_matches and ref_matches,
                "official_denominator_verified": False})
    return {"trade_date": str(td), "partition": partition,
            "name_contract": "dated_provider_display_name_not_legal_name_or_official_status",
            "name_differences": name_diffs,
            "name_classification_difference_count": sum(r["classification_flags_differ"] for r in name_diffs),
            "turnover_contract": "null_not_zero_not_carried_not_inferred",
            "turnover_missing_count": len(rows), "turnover_differences": rate_diffs,
            "internal_denominator_mismatches": internal_mismatches,
            "comparison_has_target_date": False,
            "comparison_missing_codes": sorted(set(active) - refs.keys()),
            "breadth": market_breadth(rows, suspended),
            "production_ready": False, "database_writes": False, "publication_attempted": False,
            "remaining_gates": ["official_historical_universe", "adjustment_completeness",
                "official_turnover_denominator_if_required", "downstream_same_day_cross_day_l2",
                "write_and_publish_authorization"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-dir", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--comparison-json", type=Path, required=True,
                        help="Decoded undated second-vendor rows; a current list is not a PIT list")
    parser.add_argument("--extra-raw", action="append", default=[], metavar="PATH:SHA256",
                        help="Sealed out-of-batch quote evidence (nontrading names), verified by hash")
    parser.add_argument("--trade-date", type=date.fromisoformat, required=True)
    parser.add_argument("--json", type=Path, help="New output file; existing evidence is never overwritten")
    args = parser.parse_args(argv)
    try:
        capture = audit_capture(args.capture_dir, args.trade_date)
        receipt = json.loads((args.capture_dir / "receipt.json").read_text(encoding="utf-8"))
        batches = [checked_raw(args.capture_dir, batch) for batch in receipt["batches"]]
        for spec in args.extra_raw:
            text, _, digest = spec.rpartition(":")
            if not text or not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError("extra raw evidence must be PATH:SHA256")
            extra = Path(text)
            batches.append(checked_raw(extra.parent, {"file": extra.name, "sha256": digest}))
        candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
        comparison = json.loads(args.comparison_json.read_text(encoding="utf-8"))
        if not isinstance(comparison, list):
            raise ValueError("comparison rows must be a list")
        result = {"capture": {**capture, "extra_evidence_files": len(args.extra_raw)},
                  **assess_metadata(candidate, raw_batches=batches, comparison_rows=comparison)}
        text = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if args.json:
            with args.json.open("x", encoding="utf-8") as handle:
                handle.write(text)
        print(text, end="")
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        print(json.dumps({"metadata_assessed": False, "error_type": type(exc).__name__,
                          "production_ready": False, "database_writes": False,
                          "publication_attempted": False}))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
