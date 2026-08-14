#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from intelligence.paths import default_market_db_path, default_paths
from intelligence.services.market_snapshot_contract import validate_market_snapshot_root
from intelligence.services.market_snapshot_reconcile import (
    reconcile_snapshot_with_market_db,
)


def run_check(
    root: str | Path,
    date: str | None = None,
    *,
    db_path: str | Path | None = None,
    skip_db: bool = False,
) -> dict[str, Any]:
    """格式校验 + 快照↔DuckDB 对账（默认必跑，`skip_db` 仅供无库环境做纯格式校验）。

    对账不等 → 整体 FAIL、ready=False。原脚本只校验快照自身格式，
    快照与库差一天时完全静默——那正是 2026-08-12「28 题真值通过 0」的根因。
    """

    result = validate_market_snapshot_root(root, date)
    if skip_db:
        result["reconciliation"] = {"status": "SKIPPED"}
        return result
    reconciliation = reconcile_snapshot_with_market_db(
        result,
        db_path if db_path is not None else default_market_db_path(),
    )
    result["reconciliation"] = reconciliation
    if reconciliation["status"] != "PASS":
        result["errors"] = list(result["errors"]) + list(reconciliation["errors"])
        result["status"] = "FAIL"
        result["ready"] = False
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate synced market_snapshot JSON contract and reconcile with DuckDB.",
    )
    parser.add_argument("--root", default=None, help="market_snapshot directory; defaults to MARKET_SNAPSHOT_DIR or repo market_snapshot/")
    parser.add_argument("--date", default=None, help="trade date YYYY-MM-DD; defaults to meta.latest_trade_date")
    parser.add_argument("--db", default=None, help="market DuckDB path; defaults to MARKET_FEATURE_STORE_DB or data root db/market_feature_store.duckdb")
    parser.add_argument("--skip-db", action="store_true", help="format-only check without DuckDB reconciliation (for hosts without the db)")
    parser.add_argument("--pretty", action="store_true", help="print indented JSON")
    args = parser.parse_args()

    root = Path(args.root).expanduser() if args.root else default_paths().market_snapshot_dir
    result = run_check(
        root,
        args.date,
        db_path=Path(args.db).expanduser() if args.db else None,
        skip_db=args.skip_db,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0 if result["status"] in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
