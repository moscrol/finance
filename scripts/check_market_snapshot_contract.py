#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from intelligence.paths import default_paths
from intelligence.services.market_snapshot_contract import validate_market_snapshot_root


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate synced market_snapshot JSON contract.")
    parser.add_argument("--root", default=None, help="market_snapshot directory; defaults to MARKET_SNAPSHOT_DIR or repo market_snapshot/")
    parser.add_argument("--date", default=None, help="trade date YYYY-MM-DD; defaults to meta.latest_trade_date")
    parser.add_argument("--pretty", action="store_true", help="print indented JSON")
    args = parser.parse_args()

    root = Path(args.root).expanduser() if args.root else default_paths().market_snapshot_dir
    result = validate_market_snapshot_root(root, args.date)
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0 if result["status"] in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
