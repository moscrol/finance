from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from intelligence.paths import default_paths
from intelligence.services.market_snapshot_sync import sync_market_snapshot


def main() -> int:
    paths = default_paths()
    parser = argparse.ArgumentParser(
        description="按 DuckDB → AkShare → 历史 DuckDB 顺序生成标准行情快照"
    )
    parser.add_argument("--date", help="目标交易日，格式 YYYY-MM-DD")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=paths.market_snapshot_dir,
        help="canonical market_snapshot 目录",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path(
            os.environ.get(
                "MARKET_DB_PATH",
                paths.finance_root / "db" / "market_feature_store.duckdb",
            )
        ).expanduser(),
        help="canonical DuckDB 路径",
    )
    parser.add_argument(
        "--akshare-python",
        type=Path,
        default=_default_akshare_python(),
        help="独立 AkShare venv 的 Python",
    )
    parser.add_argument(
        "--code-root",
        type=Path,
        default=Path(
            os.environ.get("FINANCE_WORKSPACE_CODE_ROOT", Path.cwd())
        ).expanduser(),
        help="固定 runtime 代码根",
    )
    parser.add_argument(
        "--akshare-timeout",
        type=float,
        default=float(os.environ.get("AKSHARE_TIMEOUT_SEC", "240")),
        help="AkShare 子进程绝对超时秒数",
    )
    args = parser.parse_args()
    try:
        result = sync_market_snapshot(
            args.output_dir,
            db_path=args.db_path,
            target_date=args.date,
            akshare_python=args.akshare_python,
            code_root=args.code_root,
            akshare_timeout_sec=args.akshare_timeout,
        )
    except (OSError, ValueError) as exc:
        print(
            json.dumps(
                {"ok": False, "error": f"{type(exc).__name__}: {exc}"},
                ensure_ascii=False,
            )
        )
        return 2
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0 if result.ok and result.quality == "complete" else 1


def _default_akshare_python() -> Path:
    explicit = os.environ.get("AKSHARE_PYTHON")
    if explicit:
        return Path(explicit).expanduser()
    venv = Path(
        os.environ.get(
            "AKSHARE_VENV",
            "/Users/a77/.local/share/finance-workbench/akshare-venv",
        )
    ).expanduser()
    return venv / "bin" / "python"


if __name__ == "__main__":
    sys.exit(main())
