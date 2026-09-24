#!/usr/bin/env python3
"""Capture dated Tencent A-share evidence, never write or publish market facts.

The scope is explicitly supplied, not inferred to be an official market universe.
Successful response bodies are retained before validation. Semantic failures remain visible;
transport failures stop the batch without retries. Existing evidence is never reused
or overwritten. Replay uses audit_dated_quote_capture, the existing date/unit gate.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from market_feature_store.hithink_stock_preview import _scope as validate_stock_scope  # noqa: E402
from scripts.audit_dated_quote_capture import audit_capture, parse_quotes, unique_codes  # noqa: E402

MAX_RESPONSE_BYTES = 1_048_576


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _save(path: Path, value: dict) -> None:
    temporary = path.with_suffix(".tmp")
    with temporary.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
    temporary.replace(path)


def capture_quotes(
    scope_path: Path, output: Path, trade_date: date, *, batch_size: int = 80,
    sleep_seconds: float = 1.0, timeout: float = 15.0,
) -> dict:
    if (type(batch_size) is not int or not 1 <= batch_size <= 80
            or not math.isfinite(sleep_seconds) or sleep_seconds < 0.2
            or not math.isfinite(timeout) or not 0 < timeout <= 60):
        raise ValueError("invalid capture limits")
    scope_raw = scope_path.read_bytes()
    scope = json.loads(scope_raw)
    if (not isinstance(scope, dict) or scope.get("trade_date") != str(trade_date)
            or not isinstance(scope.get("scope_basis"), str)
            or not scope["scope_basis"].strip()):
        raise ValueError("scope needs matching trade_date and explicit scope_basis")
    codes = sorted(unique_codes(scope.get("codes")))
    validate_stock_scope(trade_date, codes)
    output.mkdir(parents=True, exist_ok=False)
    (output / "scope.json").write_bytes(scope_raw)
    receipt = {
        "target_date": str(trade_date), "codes": codes,
        "scope_basis": scope["scope_basis"],
        "scope_sha256": hashlib.sha256(scope_raw).hexdigest(),
        "capture_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "audit_script_sha256": hashlib.sha256(
            (ROOT / "scripts/audit_dated_quote_capture.py").read_bytes()
        ).hexdigest(),
        "official_historical_universe_verified": False,
        "captured_code_count": 0, "started_at": _now(), "batches": [],
        "status": "running", "database_writes": False,
        "publication_attempted": False, "production_ready": False,
    }
    _save(output / "receipt.json", receipt)
    try:
        for offset in range(0, len(codes), batch_size):
            if offset:
                time.sleep(sleep_seconds)
            batch = codes[offset:offset + batch_size]
            index = offset // batch_size
            entry = {"codes": batch, "file": f"{index:03}.raw", "started_at": _now()}
            receipt["batches"].append(entry)
            # Persist the attempted scope before network I/O, including interruption.
            _save(output / "receipt.json", receipt)
            symbols = ",".join(code[-2:].lower() + code[:6] for code in batch)
            request = urllib.request.Request(
                "https://qt.gtimg.cn/q=" + symbols,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            transport_failed = False
            try:
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    entry["http_status"] = response.status
                    raw = response.read(MAX_RESPONSE_BYTES + 1)
                with (output / entry["file"]).open("xb") as handle:
                    handle.write(raw)
                entry["sha256"] = hashlib.sha256(raw).hexdigest()
                entry["bytes"] = len(raw)
            except (OSError, urllib.error.URLError) as exc:
                entry["error_type"] = type(exc).__name__
                if isinstance(exc, urllib.error.HTTPError):
                    entry["http_status"] = exc.code
                transport_failed = True
            else:
                transport_failed = entry["http_status"] != 200
                try:
                    if transport_failed or len(raw) > MAX_RESPONSE_BYTES:
                        raise ValueError("invalid response status or oversized response")
                    quotes = parse_quotes(raw, trade_date)
                    if set(quotes) != set(batch):
                        raise ValueError("response identities do not match requested batch")
                    receipt["captured_code_count"] += len(quotes)
                except (ValueError, KeyError, TypeError, OverflowError) as exc:
                    entry["error_type"] = type(exc).__name__
                    entry["validation_error"] = str(exc)
            entry["finished_at"] = _now()
            _save(output / "receipt.json", receipt)
            print(f"batch {index + 1}: {entry.get('error_type', 'ok')}", flush=True)
            if transport_failed:
                break
    except BaseException as exc:
        receipt.update(status="interrupted", error_type=type(exc).__name__, finished_at=_now())
        _save(output / "receipt.json", receipt)
        raise

    try:
        audit = audit_capture(output, trade_date)
    except (OSError, ValueError, KeyError, TypeError, OverflowError) as exc:
        audit = {"capture_validated": False, "error_type": type(exc).__name__,
                 "database_writes": False, "publication_attempted": False,
                 "production_ready": False}
    receipt.update(status="complete" if audit["capture_validated"] else "incomplete",
                   finished_at=_now())
    _save(output / "receipt.json", receipt)
    _save(output / "audit.json", audit)
    return audit


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope-json", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--trade-date", type=date.fromisoformat, required=True)
    parser.add_argument("--batch-size", type=int, default=80)
    parser.add_argument("--sleep", type=float, default=1.0)
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args(argv)
    try:
        result = capture_quotes(args.scope_json, args.output_dir, args.trade_date,
                                batch_size=args.batch_size, sleep_seconds=args.sleep,
                                timeout=args.timeout)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result = {"capture_validated": False, "error_type": type(exc).__name__,
                  "database_writes": False, "publication_attempted": False,
                  "production_ready": False}
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    return 0 if result["capture_validated"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
