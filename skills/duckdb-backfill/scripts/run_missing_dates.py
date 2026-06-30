"""通用缺失交易日回填驱动: 按日历缺口逐日跑指定 sync 命令, 带超时/进度/续跑/失败阈值。

复用 run_stock_high_missing.py 的思路, 推广到任意单日 sync 命令 (sector_stock / limit_heat)。
每个目标表用独立 CLI 子命令 + 独立 skip 文件, 逐日子进程隔离, 单日超时即跳过不卡死整批。

用法:
    # 先看会跑哪些日期 (默认最旧优先)
    python3 skills/duckdb-backfill/scripts/run_missing_dates.py --table sector_stock --max-days 3 --dry-run
    # 实跑一小批
    python3 skills/duckdb-backfill/scripts/run_missing_dates.py --table limit_heat --max-days 3 --timeout 600 --record-failures
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[3]
DB = ROOT / "db" / "market_feature_store.duckdb"
STATE_DIR = ROOT / "skills" / "duckdb-backfill" / "state"

# table -> (DuckDB 事实表, CLI 子命令). 子命令默认按单日 --trade-date 调用, 自带续跑/容错。
TABLES = {
    "sector_stock": ("fact_sector_stock_daily", ["sync-sector-stocks"]),
    "limit_heat": ("fact_theme_limit_heat_daily", ["sync-limit-heat"]),
    "limit_stock": ("fact_theme_limit_stock_daily", ["sync-limit-heat"]),
    "stock_high": ("fact_stock_high_daily", ["sync-stock-high"]),
}


def skip_file(table: str) -> Path:
    return STATE_DIR / f"{table}_skip.txt"


def load_known_skip(table: str) -> set[str]:
    fp = skip_file(table)
    if not fp.exists():
        return set()
    return {line.strip() for line in fp.read_text(encoding="utf-8").splitlines() if line.strip()}


def append_known_skip(table: str, date: str) -> None:
    if date in load_known_skip(table):
        return
    fp = skip_file(table)
    fp.parent.mkdir(parents=True, exist_ok=True)
    with fp.open("a", encoding="utf-8") as f:
        f.write(date + "\n")


def missing_dates(fact_table: str, limit: int, skip: set[str], newest_first: bool) -> list[str]:
    order = "DESC" if newest_first else "ASC"
    con = duckdb.connect(str(DB), read_only=True)
    try:
        rows = con.execute(
            f"""
            WITH cal AS (
                SELECT trade_date FROM fact_market_daily WHERE total_amount IS NOT NULL
            )
            SELECT trade_date FROM cal
            WHERE trade_date NOT IN (SELECT DISTINCT trade_date FROM {fact_table})
            ORDER BY trade_date {order}
            """
        ).fetchall()
    finally:
        con.close()
    dates = [str(r[0]) for r in rows if str(r[0]) not in skip]
    return dates[:limit]


def run_one(cli_args: list[str], date: str, timeout: int) -> int:
    cmd = [sys.executable, "-m", "market_feature_store.cli", *cli_args, "--trade-date", date]
    print(f"== {date} :: {' '.join(cli_args)} ==", flush=True)
    try:
        proc = subprocess.run(cmd, cwd=str(ROOT), text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        print(f"TIMEOUT {date} after {timeout}s", flush=True)
        return 124
    return int(proc.returncode)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", required=True, choices=sorted(TABLES.keys()))
    parser.add_argument("--max-days", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=600, help="单日子进程超时秒数, 默认600")
    parser.add_argument("--max-failures", type=int, default=2, help="连续失败达到即停止, 默认2")
    parser.add_argument("--newest-first", action="store_true", help="从最新缺失日往回补 (默认最旧优先)")
    parser.add_argument("--skip", default="", help="额外跳过的日期, 逗号分隔 YYYY-MM-DD")
    parser.add_argument("--no-known-skip", action="store_true")
    parser.add_argument("--record-failures", action="store_true", help="失败日期写入 state/{table}_skip.txt")
    parser.add_argument("--stop-on-failure", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    fact_table, cli_args = TABLES[args.table]
    skip = {x.strip() for x in args.skip.split(",") if x.strip()}
    if not args.no_known_skip:
        skip.update(load_known_skip(args.table))
    dates = missing_dates(fact_table, args.max_days, skip, args.newest_first)
    print(f"table={args.table} fact={fact_table} target_dates:",
          ",".join(dates) if dates else "-", flush=True)
    if args.dry_run or not dates:
        return 0

    failures = []
    consecutive = 0
    for date in dates:
        code = run_one(cli_args, date, args.timeout)
        if code != 0:
            failures.append((date, code))
            consecutive += 1
            print(f"FAILED {date} code={code}; consecutive={consecutive}", flush=True)
            if args.record_failures:
                append_known_skip(args.table, date)
            if args.stop_on_failure or consecutive >= args.max_failures:
                print("STOP: failure threshold reached", flush=True)
                break
        else:
            consecutive = 0
    if failures:
        print("failures:", ",".join(f"{d}:{c}" for d, c in failures), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
