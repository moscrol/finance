from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[3]
DB = ROOT / "db" / "market_feature_store.duckdb"
SKIP_FILE = ROOT / "skills" / "duckdb-backfill" / "state" / "stock_high_skip.txt"


def load_known_skip() -> set[str]:
    if not SKIP_FILE.exists():
        return set()
    return {line.strip() for line in SKIP_FILE.read_text(encoding="utf-8").splitlines() if line.strip()}


def append_known_skip(date: str) -> None:
    known = load_known_skip()
    if date in known:
        return
    SKIP_FILE.parent.mkdir(parents=True, exist_ok=True)
    with SKIP_FILE.open("a", encoding="utf-8") as f:
        f.write(date + "\n")


def missing_dates(limit: int, skip: set[str]) -> list[str]:
    con = duckdb.connect(str(DB), read_only=True)
    try:
        rows = con.execute(
            """
            WITH cal AS (
                SELECT trade_date
                FROM fact_market_daily
                WHERE total_amount IS NOT NULL
            )
            SELECT trade_date
            FROM cal
            WHERE trade_date NOT IN (SELECT DISTINCT trade_date FROM fact_stock_high_daily)
            ORDER BY trade_date
            """
        ).fetchall()
    finally:
        con.close()
    dates = [str(row[0]) for row in rows if str(row[0]) not in skip]
    return dates[:limit]


def run_one(date: str, timeout: int, page_size: int) -> int:
    cmd = [
        sys.executable,
        "-m",
        "market_feature_store.cli",
        "sync-stock-high",
        "--trade-date",
        date,
        "--page-size",
        str(page_size),
    ]
    print(f"== {date} ==", flush=True)
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(ROOT),
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        print(f"TIMEOUT {date} after {timeout}s", flush=True)
        return 124
    return int(proc.returncode)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-days", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--page-size", type=int, default=200)
    parser.add_argument("--skip", default="", help="comma-separated YYYY-MM-DD dates")
    parser.add_argument("--max-failures", type=int, default=3)
    parser.add_argument("--stop-on-failure", action="store_true")
    parser.add_argument("--no-known-skip", action="store_true")
    parser.add_argument("--record-failures", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    skip = {x.strip() for x in args.skip.split(",") if x.strip()}
    if not args.no_known_skip:
        skip.update(load_known_skip())
    dates = missing_dates(args.max_days, skip)
    print("target_dates:", ",".join(dates) if dates else "-", flush=True)
    if args.dry_run:
        return 0

    failures = []
    consecutive_failures = 0
    for date in dates:
        code = run_one(date, args.timeout, args.page_size)
        if code != 0:
            failures.append((date, code))
            consecutive_failures += 1
            print(f"FAILED {date} code={code}; consecutive_failures={consecutive_failures}", flush=True)
            if args.record_failures:
                append_known_skip(date)
            if args.stop_on_failure or consecutive_failures >= args.max_failures:
                print("STOP: failure threshold reached", flush=True)
                break
        else:
            consecutive_failures = 0
    if failures:
        print("failures:", ",".join(f"{date}:{code}" for date, code in failures), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
