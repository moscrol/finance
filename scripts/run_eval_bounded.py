#!/usr/bin/env python3
"""Run a trusted evaluation batch under a once-only POSIX deadline supervisor.

Example (no model): python scripts/run_eval_bounded.py --seconds 2 \
  --receipt-dir /path/to/new-private-run -- python -c 'print("offline")'

Future model batches still need separately frozen request caps, identity checks
and raw HTTP receipts. Never point this at a closed experiment to rerun it.
"""

from __future__ import annotations
import argparse
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from intelligence.eval.batch_deadline import launch  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, required=True)
    parser.add_argument("--receipt-dir", type=Path, required=True)
    parser.add_argument("--cwd", type=Path)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        parser.error("a worker command after -- is required")
    try:
        return launch(
            command, seconds=args.seconds, receipt_dir=args.receipt_dir, cwd=args.cwd
        )
    except (OSError, ValueError, RuntimeError):
        print(
            "Launcher/storage failure; inspect the private receipts, do not rerun the same batch.",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
