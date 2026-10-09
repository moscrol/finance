"""Read-only, model-free transport for the shared Workbench history blocks.

Explicit database and cutoff are required: an external consumer must not silently
read the operator's default database or replace a historical date with today.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import date
from pathlib import Path

from intelligence.services.market_history_context import market_history_blocks
from intelligence.services.research_contract import ResearchDeadline

SCHEMA_VERSION = "finance-history-context/v1"
MAX_OUTPUT_BYTES = 48_000
MAX_OUTPUT_LINES = 2_000


def history_payload(db_path: Path, *, as_of: str, timeout: float = 30.0, review_readouts: bool = False) -> dict:
    day = date.fromisoformat(as_of)
    if day.isoformat() != as_of:
        raise ValueError("as_of must be YYYY-MM-DD")
    if not math.isfinite(timeout) or not 0 < timeout <= 120:
        raise ValueError("timeout must be finite and within (0, 120]")
    if not db_path.is_file():
        raise FileNotFoundError("market database unavailable")
    blocks = market_history_blocks(
        db_path, as_of=day, deadline=ResearchDeadline.from_timeout(timeout), include_readouts=review_readouts,
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "as_of": as_of,
        "evidence_grade": "INFERRED",
        "blocks": [
            {
                "title": block.title,
                "detail": block.detail,
                # Content identity, not certification of truth or PIT completeness.
                "sha256": hashlib.sha256(block.detail.encode("utf-8")).hexdigest(),
            }
            for block in blocks
        ],
    }
    if review_readouts:
        return {
            "schema_version": "finance-history-review-source/v1",
            "public_text": encode_payload(payload),
            "readouts": [{"source_sha256": public["sha256"], "payload": block.readout}
                         for public, block in zip(payload["blocks"], blocks, strict=True)],
        }
    return payload


def encode_payload(payload: dict) -> str:
    text = json.dumps(payload, ensure_ascii=False, allow_nan=False)
    if len(text.encode("utf-8")) > MAX_OUTPUT_BYTES or len(text.splitlines()) > MAX_OUTPUT_LINES:
        raise ValueError("history context exceeds atomic output budget")
    return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--review-readouts", action="store_true")
    args = parser.parse_args(argv)
    try:
        text = encode_payload(history_payload(args.db, as_of=args.as_of, timeout=args.timeout, review_readouts=args.review_readouts))
    except (ValueError, OSError):
        # Do not disclose paths, SQL or exception text to an external model.
        print(json.dumps({"schema_version": SCHEMA_VERSION, "error": "history_context_unavailable"}))
        return 2
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
