from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from intelligence.paths import default_paths
from intelligence.services.akshare_market_snapshot import (
    sync_akshare_market_snapshot,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="将 AkShare A 股行情写入标准快照目录")
    parser.add_argument("--date", help="交易日，格式 YYYY-MM-DD")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_paths().market_snapshot_dir,
        help="快照目录，默认使用 MARKET_SNAPSHOT_DIR/finance root 配置",
    )
    args = parser.parse_args()
    try:
        result = sync_akshare_market_snapshot(
            args.output_dir,
            trade_date=args.date,
        )
    except (ImportError, ValueError) as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": f"{type(exc).__name__}: {exc}",
                },
                ensure_ascii=False,
            )
        )
        return 2
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
