#!/usr/bin/env python3
"""Validate and publish an immutable opinion correction batch, never rewrite originals.

Input is a reviewed JSON object with batch_id and corrections. The writer supplies
recorded_at. A repeated batch with identical input is a no-op; conflicts fail closed.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from intelligence.services.opinion_events import (  # noqa: E402
    SCHEMA, STORE_RELPATH, OpinionDataError, read_batches, read_originals,
    utc_now, validate_batches,
)


def publish(wiki: Path, proposal: dict) -> tuple[Path, bool]:
    if not isinstance(proposal, dict) or set(proposal) != {"batch_id", "corrections"}:
        raise OpinionDataError("proposal requires exactly batch_id and corrections")
    batch = {**proposal, "schema": SCHEMA, "recorded_at": utc_now()}
    store = wiki / STORE_RELPATH
    bid = proposal["batch_id"]
    if not isinstance(bid, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,99}", bid):
        raise OpinionDataError("invalid batch_id")
    directory = store.parent / "corrections"
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{proposal['batch_id']}.json"
    with (directory / ".writer.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        originals = read_originals(store)
        if target.exists():
            existing = json.loads(target.read_text(encoding="utf-8"))
            if {k: existing.get(k) for k in proposal} != proposal:
                raise OpinionDataError("batch_id already exists with different content")
            validate_batches(wiki, originals, read_batches(store))
            return target, False
        validate_batches(wiki, originals, [*read_batches(store), batch])
        tmp_name = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=directory, delete=False) as handle:
                tmp_name = handle.name
                json.dump(batch, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.link(tmp_name, target)
        finally:
            if tmp_name is not None:
                Path(tmp_name).unlink(missing_ok=True)
    return target, True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wiki", required=True, type=Path)
    parser.add_argument("--input", required=True, type=Path)
    args = parser.parse_args()
    path, created = publish(args.wiki, json.loads(args.input.read_text(encoding="utf-8")))
    print(json.dumps({"path": str(path), "created": created}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
