#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from intelligence.eval.forward_acceptance import (  # noqa: E402
    build_acceptance_record,
    summarize_forward_acceptance,
    write_acceptance_record,
)
from intelligence.eval.runtime_status import build_runtime_status  # noqa: E402


def _record(args: argparse.Namespace) -> int:
    status = build_runtime_status(
        code_root=args.code_root,
        data_root=args.data_root,
        snapshot_dir=args.snapshot_dir,
        report_date=args.date,
    )
    record = build_acceptance_record(status)
    path = write_acceptance_record(args.output_root, record)
    print(
        json.dumps(
            {"record_path": str(path), "record": record},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if record["result"] == "accepted" else 1


def _summary(args: argparse.Namespace) -> int:
    summary = summarize_forward_acceptance(
        args.output_root,
        start_date=args.start_date,
        end_date=args.end_date,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return (
        0
        if not summary["invalid_records"]
        and summary["blocked_day_count"] == 0
        else 1
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Record and summarize forward fidelity acceptance."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    record = subparsers.add_parser("record")
    record.add_argument("--code-root", required=True)
    record.add_argument("--data-root", required=True)
    record.add_argument("--snapshot-dir", required=True)
    record.add_argument("--output-root", required=True)
    record.add_argument("--date", required=True)
    record.set_defaults(handler=_record)

    summary = subparsers.add_parser("summary")
    summary.add_argument("--output-root", required=True)
    summary.add_argument("--start-date")
    summary.add_argument("--end-date")
    summary.set_defaults(handler=_summary)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
