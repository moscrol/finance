#!/usr/bin/env python3
"""Replay publication-guard regressions, optionally bypassing admission in memory.

The mutant must fail the same tests that pass on the frozen checkout. It never
edits candidate source or writes a normal revision test receipt for a mutant.
"""
from __future__ import annotations

import argparse
from contextlib import nullcontext
import hashlib
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--disable-admission", action="store_true")
    args = parser.parse_args()
    checkout = args.checkout.resolve()
    revision = subprocess.check_output(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True,
    ).strip()
    if revision != args.expected_revision:
        parser.error(f"Wrong candidate revision: {revision}")
    dirty = subprocess.check_output(
        ["git", "-C", str(checkout), "status", "--porcelain", "--untracked-files=no"],
        text=True,
    ).strip()
    if dirty:
        parser.error("Candidate checkout must be clean")
    os.environ["FWP_TEST_RECEIPT"] = "0"
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(checkout))
    import pytest
    from intelligence.services.premise_financial_calculation import (
        CALCULATION_MARKER,
        PremiseCalculation,
    )

    source = Path(inspect.getfile(PremiseCalculation)).resolve()
    if not source.is_relative_to(checkout):
        parser.error(f"Imported the wrong source: {source}")
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()

    def bypass_admission(self, draft, *, status):
        return draft.replace(CALCULATION_MARKER, self.table), ""

    mutation = (
        patch.object(PremiseCalculation, "admit", bypass_admission)
        if args.disable_admission else nullcontext()
    )
    metadata = {
        "revision": revision,
        "checkout": str(checkout),
        "imported_source": str(source),
        "source_sha256": source_hash,
        "process_local_mutation": args.disable_admission,
        "normal_receipt_disabled": True,
    }
    print(json.dumps(metadata, sort_keys=True), flush=True)
    with mutation:
        status = int(pytest.main([
            "-q", "-p", "no:cacheprovider",
            str(checkout / "intelligence/tests/test_premise_financial_calculation.py"),
            "-k", "public_gate_cannot_be_overruled_by_passing_judge or "
            "real_episode_reinjects_wrong_calculation_then_admits_owned_table",
        ]))
    metadata["exit_status"] = status
    metadata["source_unchanged"] = hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
    print(json.dumps(metadata, sort_keys=True), flush=True)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
