"""Rebuild the fixed September 21 proposal and plan only its two missing rows.

This is an input-preparation contract, not a general repair or publication API.
The original 5551 rows must match a pinned preimage and the candidate's numbers;
existing names, turnover and provenance are preserved, not silently replaced.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import hashlib
import json
import math
from pathlib import Path

from market_feature_store.hithink_recovery_candidate import CANDIDATE_20260921, build_candidate
from market_feature_store.recovery_coverage import partition_scope
from market_feature_store.sync.sync_mootdx_stock_daily import COLS
from scripts.dated_quote_recovery import _digest, _path, read_pinned

CONTRACT = "historical-candidate-gap-preparation-v1"
FIXED_INPUT_FINGERPRINT = "52410f4ded44667b9249719e6ed300b84772c91bdf7160103131a6eea1501206"
FIXED_CANDIDATE_FINGERPRINT = "446cf3af8c3401f7e05ee20a007a187cfcb96b2e18802e7cd6ac8aead8b31d4a"
NUMERIC_FIELDS = ("open", "high", "low", "close", "pre_close", "pct_chg", "amount", "volume")


@dataclass(frozen=True)
class PreparedCandidate:
    trade_date: date
    rows: tuple[tuple, ...]
    missing_codes: tuple[str, ...]
    existing_sha256: str
    evidence: dict


def rows_fingerprint(rows) -> str:
    ordered = sorted(rows, key=lambda row: (str(row[0]), row[1]))
    raw = json.dumps({"columns": COLS, "rows": ordered}, sort_keys=True,
                     ensure_ascii=False, default=str, allow_nan=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def load_manifest(path: Path, expected_sha256: str) -> PreparedCandidate:
    manifest = json.loads(read_pinned(path, expected_sha256))
    if (not isinstance(manifest, dict) or manifest.get("contract_version") != CONTRACT
            or manifest.get("trade_date") != str(CANDIDATE_20260921.trade_date)):
        raise ValueError("unsupported historical candidate contract or date")
    expected_existing = _digest(manifest["existing_rows_sha256"])
    reference = manifest["inputs"]
    inputs_path = _path(path.parent, reference["path"])
    inputs = json.loads(read_pinned(inputs_path, reference["sha256"]))
    required = {"stock_codes", "bars", "actions", "quotes", "suspensions", "historical_witnesses"}
    if not isinstance(inputs, dict) or set(inputs) != required:
        raise ValueError("historical inputs must use the fixed explicit schema")
    for collection in ("bars", "actions"):
        for row in inputs[collection]:
            timestamp = datetime.fromisoformat(row["updated_at"])
            if str(timestamp) != row["updated_at"]:
                raise ValueError("historical provenance timestamp must retain its canonical representation")
            row["updated_at"] = timestamp
    candidate = build_candidate(CANDIDATE_20260921, **inputs)
    if (candidate["input_fingerprint"] != FIXED_INPUT_FINGERPRINT
            or candidate["candidate_fingerprint"] != FIXED_CANDIDATE_FINGERPRINT):
        raise ValueError("historical candidate differs from the fixed witnessed proposal")
    missing = tuple(sorted(ref.code for ref in CANDIDATE_20260921.resumptions))
    if manifest.get("missing_codes") != list(missing):
        raise ValueError("only the fixed named resumption gaps may be prepared")
    coverage = partition_scope(declared=inputs["stock_codes"],
        observed=[row["stock_ts_code"] for row in candidate["rows"]],
        suspended=[row["stock_ts_code"] for row in candidate["exclusions"]])
    now = datetime.now()
    rows = []
    for row in candidate["rows"]:
        canonical = {**row, "trade_date": CANDIDATE_20260921.trade_date,
                     "source": row["bar_source"], "updated_at": now}
        rows.append(tuple(canonical[column] for column in COLS))
    evidence = {key: value for key, value in candidate.items() if key not in {"rows", "exclusions"}}
    evidence.update(manifest_sha256=expected_sha256, inputs_sha256=reference["sha256"],
        coverage=coverage, missing_codes=list(missing), existing_rows_sha256=expected_existing,
        scope_basis="fixed captured September 21 declared scope, not official universe certification",
        existing_rows_policy="preserve every column, including differing display names",
        observations=[row for row in candidate["rows"] if row["stock_ts_code"] in missing],
        official_historical_universe_verified=False, production_ready=False)
    return PreparedCandidate(CANDIDATE_20260921.trade_date, tuple(rows), missing, expected_existing, evidence)


def plan_missing_rows(prepared: PreparedCandidate, existing: list[tuple]) -> tuple[tuple, ...]:
    """Check the complete day before returning insert-only rows; no database IO."""
    if rows_fingerprint(existing) != prepared.existing_sha256:
        raise ValueError("historical target-day preimage changed")
    old = {row[1]: row for row in existing}
    proposed = {row[1]: row for row in prepared.rows}
    if (len(old) != len(existing) or len(proposed) != len(prepared.rows)
            or any(row[0] != prepared.trade_date for row in (*existing, *prepared.rows))):
        raise ValueError("duplicate or misdated historical row")
    if set(old) - set(proposed) or set(proposed) - set(old) != set(prepared.missing_codes):
        raise ValueError("historical missing identities differ from the fixed gaps")
    for code, row in old.items():
        for field in NUMERIC_FIELDS:
            index = COLS.index(field)
            actual, expected = row[index], proposed[code][index]
            if (not isinstance(actual, (int, float)) or isinstance(actual, bool)
                    or not math.isclose(actual, expected, rel_tol=0, abs_tol=1e-8)):
                raise ValueError(f"existing historical numeric value differs: {code} {field}")
    return tuple(proposed[code] for code in prepared.missing_codes)
