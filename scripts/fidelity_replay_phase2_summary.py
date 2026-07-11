#!/usr/bin/env python3
"""Aggregate Phase 2 selection, PIT, claim, outcome, and comparison reports."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from intelligence.eval.phase2_summary import (  # noqa: E402
    build_phase2_summary,
    read_json,
    render_phase2_summary,
    write_json,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", required=True)
    parser.add_argument("--input-report", required=True)
    parser.add_argument("--claim-summary", required=True)
    parser.add_argument("--outcome-report", required=True)
    parser.add_argument("--comparison-report", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args(argv)
    summary = build_phase2_summary(
        selection=read_json(args.selection),
        input_report=read_json(args.input_report),
        claim_summary=read_json(args.claim_summary),
        outcome_report=read_json(args.outcome_report),
        comparison_report=read_json(args.comparison_report),
    )
    output = Path(args.out_dir).expanduser()
    write_json(output / "phase2.summary.json", summary)
    write_json(
        output / "phase2.negative-controls.json",
        summary["negative_controls"],
    )
    (output / "phase2.summary.md").write_text(
        render_phase2_summary(summary),
        encoding="utf-8",
    )
    print(output / "phase2.summary.json")
    print(output / "phase2.negative-controls.json")
    print(output / "phase2.summary.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
