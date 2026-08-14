#!/usr/bin/env python3
"""Read-only audit of local L2 recovery artifacts.

The script never loads credentials, opens no network connections, and opens DuckDB
read-only. It compares the 2026-08-06-style scan CSVs and scan caches with the
existing L2 feature rows, then emits a JSON evidence report.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import duckdb

# 数据根：从脚本自身位置推导（脚本在 <仓根>/scripts/ 下），不写死家目录。
# 此前是 Path("/Users/a77/finance-workspace-private")，从附属 worktree 跑时会  # path-literal-ok: 这是说明"改掉了什么"的历史注释，不是代码里的路径
# 去主树读产物、却在主树之外的分支上下文里汇报，两边对不上。
DEFAULT_DATA_ROOT = Path(__file__).resolve().parents[1]

CAPITAL_COLUMNS = {
    "主买净额(万)": "main_buy_net_wan",
    "总买净额(万)": "total_buy_net_wan",
    "当日涨幅%": "pct_change",
}
QUANT_COLUMNS = {
    "量化单总额(万)": "quant_amount_wan",
    "占大单买入%": "quant_pct_of_big_buy",
    "簇数": "cluster_count",
    "笔数": "order_count",
    "最大簇": "biggest_cluster",
    "当日涨幅%": "pct_change",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def number(value: object) -> float:
    return float(str(value))


def equal(left: object, right: object) -> bool:
    try:
        return abs(number(left) - number(right)) <= 1e-9
    except (TypeError, ValueError):
        return str(left) == str(right)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_scan(
    con: duckdb.DuckDBPyConnection,
    outputs: Path,
    date: str,
    csv_name: str,
    cache_name: str,
    query: str,
    column_map: dict[str, str],
) -> dict[str, Any]:
    csv_path = outputs / csv_name.format(date=date)
    cache_path = outputs / cache_name.format(date=date)
    csv_rows = read_csv(csv_path)
    cache = read_json(cache_path)
    db_rows = con.execute(query, [date]).fetchall()
    db_columns = [column[0] for column in con.description]
    db_by_code = {
        str(row[0]).zfill(6): dict(zip(db_columns, row)) for row in db_rows
    }
    csv_by_code = {row["code"].zfill(6): row for row in csv_rows}
    cache_codes = {str(code).zfill(6) for code in cache}
    csv_codes = set(csv_by_code)
    db_codes = set(db_by_code)
    mismatches: list[dict[str, str]] = []
    for code in sorted(csv_codes & db_codes):
        csv_row = csv_by_code[code]
        db_row = db_by_code[code]
        for csv_column, db_column in column_map.items():
            if not equal(csv_row[csv_column], db_row[db_column]):
                mismatches.append({
                    "code": code,
                    "column": csv_column,
                    "csv": csv_row[csv_column],
                    "duckdb": str(db_row[db_column]),
                })
                if len(mismatches) >= 20:
                    break
        if len(mismatches) >= 20:
            break
    return {
        "csv": {"path": str(csv_path), "sha256": sha256(csv_path), "rows": len(csv_rows)},
        "scan_cache": {
            "path": str(cache_path),
            "sha256": sha256(cache_path),
            "rows": len(cache_codes),
        },
        "duckdb_rows": len(db_rows),
        "csv_codes_match_duckdb": csv_codes == db_codes,
        "scan_cache_codes_match_csv": cache_codes == csv_codes,
        "csv_only_codes": sorted(csv_codes - db_codes)[:20],
        "duckdb_only_codes": sorted(db_codes - csv_codes)[:20],
        "cache_only_codes": sorted(cache_codes - csv_codes)[:20],
        "csv_only_vs_cache_codes": sorted(csv_codes - cache_codes)[:20],
        "value_mismatches": mismatches,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default="2026-08-06")
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--json", type=Path, help="Optional path for the JSON report")
    parser.add_argument(
        "--require-complete",
        action="store_true",
        help="Exit nonzero when the L2 status rows are not all complete.",
    )
    args = parser.parse_args()

    outputs = args.data_root / "scripts/moneyflow/outputs"
    database = args.data_root / "db/market_feature_store.duckdb"
    con = duckdb.connect(str(database), read_only=True)
    try:
        capital_query = (
            "SELECT stock_code, main_buy_net_wan, total_buy_net_wan, pct_change "
            "FROM feature_l2_capital_flow_daily "
            "WHERE trade_date = ? AND scan_type = '{scan_type}'"
        )
        report = {
            "date": args.date,
            "mode": "read-only; no credentials or network access",
            "database": str(database),
            "capital_limitup": validate_scan(
                con, outputs, args.date,
                "limitup_scan_{date}.csv",
                "scan_cache_limitup_server_v1_{date}.json",
                capital_query.format(scan_type="limitup"), CAPITAL_COLUMNS,
            ),
            "capital_top100": validate_scan(
                con, outputs, args.date,
                "top100_scan_{date}.csv",
                "scan_cache_top100_server_v1_{date}.json",
                capital_query.format(scan_type="top100"), CAPITAL_COLUMNS,
            ),
            "quant": validate_scan(
                con, outputs, args.date,
                "quant_scan_{date}.csv",
                "scan_cache_quant_server_v1_{date}.json",
                "SELECT stock_code, quant_amount_wan, quant_pct_of_big_buy, "
                "cluster_count, order_count, biggest_cluster, pct_change "
                "FROM feature_l2_quant_orders_daily WHERE trade_date = ?",
                QUANT_COLUMNS,
            ),
        }
        shared_path = outputs / f"l2_query_cache_{args.date}.json"
        shared = read_json(shared_path)
        entries = shared.get("entries", {}) if isinstance(shared, dict) else {}
        report["shared_query_cache"] = {
            "path": str(shared_path),
            "sha256": sha256(shared_path),
            "version": shared.get("version") if isinstance(shared, dict) else None,
            "entry_count": len(entries),
            "capital_entry_count": sum(str(key).startswith("capital:") for key in entries),
            "buyer_order_entry_count": sum(str(key).startswith("buyer-orders:") for key in entries),
        }
        status_rows = con.execute(
            "SELECT step, status, row_count, input_count, processed_count, "
            "failed_count, message, source, finished_at "
            "FROM ops_pipeline_run_daily "
            "WHERE trade_date = ? AND pipeline = 'l2-moneyflow' ORDER BY step",
            [args.date],
        ).fetchall()
        columns = [column[0] for column in con.description]
        report["pipeline_status"] = [dict(zip(columns, row, strict=True)) for row in status_rows]
    finally:
        con.close()

    artifact_sections = ("capital_limitup", "capital_top100", "quant")
    artifacts_match = all(
        section["csv_codes_match_duckdb"]
        and section["scan_cache_codes_match_csv"]
        and not section["value_mismatches"]
        for section in (report[name] for name in artifact_sections)
    )
    complete = len(report["pipeline_status"]) == 3 and all(
        row["status"] == "complete"
        and row["input_count"] == row["processed_count"]
        and not row["failed_count"]
        for row in report["pipeline_status"]
    )
    report["verdict"] = {
        "artifacts_match": artifacts_match,
        "pipeline_complete": complete,
        "recovery_safe_to_claim": artifacts_match and complete,
    }
    payload = json.dumps(report, ensure_ascii=False, indent=2, default=str)
    print(payload)
    if args.json:
        args.json.write_text(payload + "\n", encoding="utf-8")
    return 0 if artifacts_match and (complete or not args.require_complete) else 1


if __name__ == "__main__":
    raise SystemExit(main())
