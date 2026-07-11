#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from intelligence.eval.runtime_status import build_runtime_status


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--code-root", required=True)
    parser.add_argument("--data-root", required=True)
    parser.add_argument("--snapshot-dir", required=True)
    parser.add_argument("--date", required=True)
    args = parser.parse_args()

    status = build_runtime_status(
        code_root=args.code_root,
        data_root=args.data_root,
        snapshot_dir=args.snapshot_dir,
        report_date=args.date,
    )
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0 if status["capture_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
