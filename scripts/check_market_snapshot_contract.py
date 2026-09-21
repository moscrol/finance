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

    日期差异保留为 WARN，不撤销格式/质量合格快照的 ready；读不到日期仍报对账失败。
    这是数据诊断，不赋予补采权限，也不要求各来源同日才能分析。
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
    result["warnings"] = list(result["warnings"]) + list(reconciliation["warnings"])
    if reconciliation["status"] == "WARN" and result["status"] == "PASS":
        result["status"] = "WARN"
    if reconciliation["status"] == "FAIL":
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
