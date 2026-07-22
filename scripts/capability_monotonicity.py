#!/usr/bin/env python3
"""Create offline three-arm fixtures or score saved capability judgments."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Direct script execution puts ``scripts`` rather than the repository root on
# sys.path, so make the package imports behave like ``python -m`` execution.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from intelligence.eval.capability_monotonicity import (
    ThreeArmRecord,
    build_fixture_document,
    summarize_three_arm_records,
)
from scripts.smoke_workbench_self_use import _atomic_write_json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or score the offline bare/current/episode capability gate"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--write-fixture",
        type=Path,
        help="Write the fixed three-arm case inputs without calling an LLM",
    )
    mode.add_argument(
        "--input",
        type=Path,
        help="Read JSON records containing human-assigned five-dimension scores",
    )
    parser.add_argument("--output", type=Path, help="Write the comparison report")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.write_fixture is not None:
        _atomic_write_json(args.write_fixture, build_fixture_document())
        print(f"capability fixture written: {args.write_fixture}")
        return 0
    if args.output is None:
        print(
            "capability monotonicity failed: --output is required with --input",
            file=sys.stderr,
        )
        return 2
    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not isinstance(
            payload.get("records"), list
        ):
            raise ValueError("input must be a JSON object with a records list")
        records = [ThreeArmRecord.from_dict(item) for item in payload["records"]]
        report = summarize_three_arm_records(records)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"capability monotonicity failed: invalid input: {exc}", file=sys.stderr)
        return 2
    _atomic_write_json(args.output, report)
    print(
        "capability monotonicity outcome: "
        + ("passed" if report["passed"] else "failed")
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
