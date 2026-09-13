#!/usr/bin/env python3
"""只读复验 2026-09-11 hithink 已发布修复，防 staging 成功被当成发布成功。

必须显式提供生产库、换前备份、两份报告、冻结 parquet、执行代码树与输出路径。
不调用修复/换库入口，不建数据库副本，不外呼；所有连接均 read_only。
仅证明当前文件状态，不追认过去的 CLI 退出码、环境变量或持锁时序。
固定本事故的钉值，不可用于其他日期/修复批次。异常/任一断言失败均非零退出。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

import duckdb

TD = "2026-09-11"
RUN_ID = "1ef953440995"
PARQUET_SHA = "51f9ee9cba1ceb4a6ff50c4c4dce8267cb39f78add28d6a33699cbf90bf28d17"
BEFORE_SHA = "c44a0f50f201de7ad4a48e872e3728cfc585d97798db4a4d11de4eb54275f9ca"


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def stat_id(path):
    stat = path.stat()
    return [stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns]


def git(tree, *args):
    return subprocess.run(
        ["git", "-C", str(tree), *args], check=True, capture_output=True, text=True,
    ).stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("production", "backup", "child-report", "receipt", "parquet", "code-tree", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    report = {"started_at": datetime.now().isoformat(), "checks": [], "observations": {}}
    observations = report["observations"]

    def check(name, ok, actual):
        report["checks"].append({"name": name, "ok": bool(ok), "actual": actual})
        print(f"{'PASS' if ok else 'FAIL'} {name}", flush=True)

    def rows(con, sql, params=None):
        return con.execute(sql, params or []).fetchall()

    def diff(con, table, where="", columns="*"):
        old = f"SELECT {columns} FROM before.{table} {where}"
        new = f"SELECT {columns} FROM {table} {where}"
        return [con.execute(f"SELECT count(*) FROM ({a} EXCEPT ALL {b})").fetchone()[0]
                for a, b in ((old, new), (new, old))]

    try:
        paths = (args.production, args.backup, args.child_report, args.receipt, args.parquet)
        if args.output.resolve() in [p.resolve() for p in paths] or args.output.exists():
            raise ValueError("输出须为新的独立证据文件")
        before_stats = {str(p): stat_id(p) for p in paths}
        observations["inputs_stat"] = before_stats
        observations["script_sha256"] = sha256(Path(__file__))
        revision = git(args.code_tree, "rev-parse", "HEAD")
        expected_revision = git(args.code_tree, "rev-parse", "1fef3d27^{commit}")
        check("code_tree", revision == expected_revision and not git(args.code_tree, "status", "--porcelain"), revision)
        if not report["checks"][-1]["ok"]:
            raise ValueError("执行代码树版本或干净状态不符")
        sys.path.insert(0, str(args.code_tree.resolve()))
        from market_feature_store.sync.repair_hithink_stock_day import _FP_EXPR
        from market_feature_store.sync.sync_local_sector_members import (
            _today_values,
            stitch_sector_members,
        )

        receipt = json.loads(args.receipt.read_text())
        child = json.loads(args.child_report.read_text())
        observations["input_hashes"] = {str(p): sha256(p) for p in paths}
        check("backup_hash", observations["input_hashes"][str(args.backup)] == receipt["backup_sha256"] == BEFORE_SHA, receipt["backup_sha256"])
        check("parquet_hash", observations["input_hashes"][str(args.parquet)] == child["evidence"]["parquet_sha256"] == PARQUET_SHA, PARQUET_SHA)
        check("backup_identity", receipt["run_id"] == RUN_ID and Path(receipt["source_db"]).resolve() == args.production.resolve() and Path(receipt["backup_path"]).resolve() == args.backup.resolve() and receipt["backup_bytes"] == args.backup.stat().st_size, receipt)
        check("child_report_scope", child["ok"] is True and child["trade_date"] == TD and child["kind"] == "repair-stock-daily-hithink" and child["target_db"] == str(args.production) + ".staging", {k: child[k] for k in ("ok", "trade_date", "kind", "target_db")})

        with duckdb.connect(str(args.production), read_only=True, config={"threads": 2, "memory_limit": "1GB"}) as con:
            backup_quoted = str(args.backup).replace("'", "''")
            con.execute(f"ATTACH '{backup_quoted}' AS before (READ_ONLY)")
            for name in ("fact_stock_daily", "feature_stock_technical_daily", "feature_stock_window", "fact_market_daily"):
                col = "as_of_date" if name == "feature_stock_window" else "trade_date"
                observations[f"freshness:{name}"] = rows(con, f"SELECT count(*), min({col}), max({col}) FROM {name}")
                where = "" if name == "fact_market_daily" else f"WHERE {col} IS DISTINCT FROM DATE '{TD}'"
                result = diff(con, name, where)
                check(f"unchanged:{name}", result == [0, 0], result)
            sources = dict(rows(con, "SELECT source,count(*) FROM fact_stock_daily WHERE trade_date=? GROUP BY 1", [TD]))
            check("sources", sources == {"hithink:daily-k-10d": 5547, "eastmoney:snapshot": 6}, sources)
            value = rows(con, "SELECT open,high,low,close,pre_close,pct_chg,amount,volume,turnover,stock_name FROM fact_stock_daily WHERE trade_date=? AND stock_ts_code='302132.SZ'", [TD])
            check("302132_values", value == [(64.01, 64.66, 62.82, 63.42, 64.35, -1.45, 5.9863, 94471.0, None, "中航成飞")], value)
            fp = rows(con, f"SELECT count(*),sum(hash({_FP_EXPR})) FROM fact_stock_daily WHERE trade_date=?", [TD])[0]
            check("published_matches_child_fingerprint", {"rows": fp[0], "hash": str(fp[1])} == child["fingerprint_target_date"], fp)
            retained = "'688291.SH','688432.SH','688496.SH','920045.BJ','920161.BJ','920375.BJ'"
            value = diff(con, "fact_stock_daily", f"WHERE trade_date='{TD}' AND stock_ts_code IN ({retained})")
            check("retained_full_rows", value == [0, 0], value)
            value = diff(con, "fact_stock_daily", f"WHERE trade_date='{TD}' AND stock_ts_code <> '302132.SZ'", "* EXCLUDE (source,updated_at,amount)")
            check("old_common_other_values", value == [0, 0], value)
            value = rows(con, "SELECT p.stock_ts_code,b.amount,p.amount FROM fact_stock_daily p JOIN before.fact_stock_daily b USING(trade_date,stock_ts_code) WHERE p.trade_date=? AND p.amount IS DISTINCT FROM b.amount", [TD])
            check("only_whitelisted_amount_drift", value == [("600176.SH", 113.6007, 113.6006)], value)
            for table, col, expected in (("feature_stock_technical_daily", "trade_date", 5529), ("feature_stock_window", "as_of_date", 22115)):
                value = rows(con, f"SELECT count(*),count(*) FILTER(WHERE stock_ts_code='302132.SZ') FROM {table} WHERE {col}=?", [TD])[0]
                check(f"derived:{table}", value == (expected, 0), value)
            value = rows(con, "SELECT b.start_date,b.avg_amount,p.avg_amount FROM feature_stock_window p JOIN before.feature_stock_window b USING(as_of_date,start_date,end_date,stock_ts_code) WHERE p.as_of_date=? AND p.stock_ts_code='600176.SH' AND p.avg_amount IS DISTINCT FROM b.avg_amount", [TD])
            check("600176_window_drift", len(value) == 1 and value[0][1:] == (93.1063, 93.1062), value)
            check("302132_unavailable_disclosed", "单独授权" in child["derived"]["new_codes_unavailable"]["302132.SZ"], child["derived"])
            stitch = stitch_sector_members(date.fromisoformat(TD), con=con, fetch_caps=False, dry_run=True, include_completed=True, max_baseline_age_days=180)
            stitch.pop("rows", None)
            check("stitch", stitch["candidates"] == stitch["stitched"] == 403 and len(_today_values(con, date.fromisoformat(TD))) == 5550, stitch)
            cursor = con.execute("SELECT * FROM ops_sync_run ORDER BY started_at DESC LIMIT 1")
            ops = dict(zip([d[0] for d in cursor.description], cursor.fetchone()))
            for key in ("rows_summary", "steps_summary"):
                ops[key] = json.loads(ops[key])
            check("ops_identity", (ops["run_id"], ops["kind"], ops["plan"], ops["trade_date"], ops["ok"]) == (RUN_ID, "repair-stock-daily-hithink", "staging-swap", TD, True), ops)
            check("ops_time_binding", ops["started_at"].replace(microsecond=0) <= datetime.fromisoformat(child["started_at"]) <= datetime.fromisoformat(child["finished_at"]) <= ops["finished_at"] <= datetime.fromisoformat(receipt["created_at"]), {"started": ops["started_at"], "finished": ops["finished_at"], "backup_created": receipt["created_at"], "precision_note": "child.started_at is truncated to seconds; compare parent start at the same precision"})
            value = diff(con, "ops_sync_run", f"WHERE run_id IS DISTINCT FROM '{RUN_ID}'")
            check("previous_ops_unchanged", value == [0, 0] and rows(con, "SELECT count(*) FROM ops_sync_run WHERE run_id=?", [RUN_ID])[0][0] == 1 and rows(con, "SELECT count(*) FROM before.ops_sync_run WHERE run_id=?", [RUN_ID])[0][0] == 0, value)
            for table in ("fact_stock_daily", "fact_stock_daily_hithink"):
                observations[f"302132_history:{table}"] = rows(con, f"SELECT min(trade_date),max(trade_date),count(*) FROM {table} WHERE stock_ts_code='302132.SZ' AND trade_date < DATE '{TD}'")
                observations[f"302132_recent:{table}"] = rows(con, f"SELECT trade_date,close FROM {table} WHERE stock_ts_code='302132.SZ' AND trade_date >= DATE '2026-07-01' ORDER BY trade_date")
            for table, group in (("fact_stock_daily_hithink", "source"), ("fact_sector_kline_daily", "source"), ("fact_limit_pool_hithink", "pool"), ("fact_dragon_tiger_hithink", "source"), ("fact_dragon_hot_money_hithink", "source"), ("fact_hot_stock_rank_hithink", "source"), ("fact_auction_hithink", "kind")):
                observations[f"parallel_freshness:{table}"] = rows(con, f"SELECT {group},min(trade_date),max(trade_date),max(updated_at),count(*) FROM {table} GROUP BY 1 ORDER BY 1")
            observations["adjustment_freshness"] = rows(con, "SELECT max(ex_date),min(updated_at),max(updated_at),count(*) FROM fact_stock_adjustment_hithink")
            observations["unchanged_table_counts"] = rows(con, "SELECT (SELECT count(*) FROM information_schema.tables WHERE table_catalog=current_database() AND table_schema='main'), (SELECT count(*) FROM information_schema.tables WHERE table_catalog='before' AND table_schema='main')")
        check("input_stats_unchanged", before_stats == {str(p): stat_id(p) for p in paths}, before_stats)
    except Exception as exc:
        check("exception", False, repr(exc))
    report["finished_at"] = datetime.now().isoformat()
    report["verdict"] = "PASS" if report["checks"] and all(c["ok"] for c in report["checks"]) else "FAIL"
    # 'x' prevents overwriting prior evidence, including on early failure.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, default=str)
        stream.write("\n")
    print(json.dumps({"verdict": report["verdict"], "checks": len(report["checks"]), "output": str(args.output)}))
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
