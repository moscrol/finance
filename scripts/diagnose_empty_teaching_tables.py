#!/usr/bin/env python3
"""只读诊断教学旁路库：行数、DDL 列集合、教学构建收据、PIT 戳。

教学构建写 history_teaching_receipts，不写 legacy 的 history_build_meta。
没有收据不能证明从未构建（reset 会清掉收据）；有收据但空表也不能证明数据被删
（构建可能合法产出零行）。这里只陈列证据，不猜操作历史，不写库、不联网。

    python3 scripts/diagnose_empty_teaching_tables.py --labels-db db/history_labels.duckdb
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from intelligence.services.methodology_backtest.store import TEACHING_DDL, TEACHING_TABLES  # noqa: E402

LEGACY_TABLES = ("history_calendar", "history_labels", "history_data_gaps", "history_outcomes")


def diagnose(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"旁路库不存在: {path}")
    out = {"labels_db": str(path), "bytes": path.stat().st_size, "read_only": True, "writes": "none"}
    con = duckdb.connect(str(path), read_only=True)
    reference = duckdb.connect(":memory:")
    try:
        for ddl in TEACHING_DDL:
            reference.execute(ddl)
        present = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        out["legacy_rows"] = {
            t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in LEGACY_TABLES if t in present
        }
        tables = {}
        for table in TEACHING_TABLES:
            if table not in present:
                tables[table] = {"state": "absent"}
                continue
            actual = {r[1] for r in con.execute(f"PRAGMA table_info('{table}')").fetchall()}
            expected = {r[1] for r in reference.execute(f"PRAGMA table_info('{table}')").fetchall()}
            n = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            tables[table] = {
                "state": "has_rows" if n else "empty", "rows": n,
                "missing_columns": sorted(expected - actual), "extra_columns": sorted(actual - expected),
            }
            if "first_known_at" in actual:
                distinct, missing, earliest, latest = con.execute(
                    f"SELECT count(DISTINCT first_known_at), count(*) FILTER (WHERE first_known_at IS NULL), "
                    f"min(first_known_at), max(first_known_at) FROM {table}"
                ).fetchone()
                tables[table]["pit_stamps"] = {
                    "distinct": distinct, "null": missing, "earliest": earliest, "latest": latest,
                    "note": "PIT 读 first_known_at 而非 computed_at；戳分布本身不证明前缀稳定性。",
                }
        out["teaching_tables"] = tables
        receipt = "history_teaching_receipts"
        required = {"build_kind", "computed_at", "coverage_summary", "status"}
        if receipt in present and required <= {
            r[1] for r in con.execute(f"PRAGMA table_info('{receipt}')").fetchall()
        }:
            out["teaching_build_receipts_latest_100"] = [
                {"build_kind": r[0], "computed_at": r[1], "coverage_summary": r[2], "status": r[3]}
                for r in con.execute(
                    f"SELECT build_kind, computed_at, coverage_summary, status FROM {receipt} "
                    "ORDER BY computed_at DESC, build_kind LIMIT 100"
                ).fetchall()
            ]
        else:
            out["receipt_note"] = "教学收据表不存在或列过期，无法判断历史构建。"
        out["interpretation"] = [
            "has_rows 是当前非空证据，不等于标签语义正确或已被日常 agent 消费。",
            "empty 只说明当前零行；需与对应收据的覆盖/缺口读数及构建日志对照。",
            "无教学收据不等于从未构建；reset-teaching 会同时清空这些收据。",
            "有列差异时按 reset-teaching 流程仅重建教学表，勿删除含 legacy 数据的整个库。",
        ]
    finally:
        reference.close()
        con.close()
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--labels-db", required=True, type=Path)
    args = ap.parse_args()
    print(json.dumps(diagnose(args.labels_db.expanduser()), ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
