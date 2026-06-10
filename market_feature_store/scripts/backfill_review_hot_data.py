from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from market_feature_store.db import connect

TABLES = [
    "fact_sector_stock_daily",
    "fact_theme_limit_heat_daily",
    "fact_theme_limit_stock_daily",
    "fact_limit_advance_daily",
]


def _date_str(value) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _counts(trade_date: str) -> dict[str, int]:
    con = connect(read_only=True)
    try:
        return {
            table: con.execute(f"SELECT COUNT(*) FROM {table} WHERE trade_date = ?", [trade_date]).fetchone()[0]
            for table in TABLES
        }
    finally:
        con.close()


def _missing_dates(before: str, limit: int) -> list[str]:
    con = connect(read_only=True)
    try:
        rows = con.execute(
            """
            WITH dates AS (
              SELECT trade_date FROM fact_market_daily
              WHERE trade_date < CAST(? AS DATE)
            ), coverage AS (
              SELECT d.trade_date,
                COALESCE(ss.cnt,0) AS sector_stock_rows,
                COALESCE(lh.cnt,0) AS limit_heat_rows,
                COALESCE(ls.cnt,0) AS limit_stock_rows,
                COALESCE(la.cnt,0) AS limit_advance_rows
              FROM dates d
              LEFT JOIN (SELECT trade_date, count(*) cnt FROM fact_sector_stock_daily GROUP BY 1) ss USING(trade_date)
              LEFT JOIN (SELECT trade_date, count(*) cnt FROM fact_theme_limit_heat_daily GROUP BY 1) lh USING(trade_date)
              LEFT JOIN (SELECT trade_date, count(*) cnt FROM fact_theme_limit_stock_daily GROUP BY 1) ls USING(trade_date)
              LEFT JOIN (SELECT trade_date, count(*) cnt FROM fact_limit_advance_daily GROUP BY 1) la USING(trade_date)
            )
            SELECT trade_date
            FROM coverage
            WHERE sector_stock_rows = 0 OR limit_heat_rows = 0 OR limit_stock_rows = 0 OR limit_advance_rows = 0
            ORDER BY trade_date DESC
            LIMIT ?
            """,
            [before, int(limit)],
        ).fetchall()
        return [_date_str(row[0]) for row in rows]
    finally:
        con.close()


def _run(label: str, cmd: list[str], timeout: int) -> None:
    print(f"\n>>> {label}: {' '.join(cmd)}", flush=True)
    started = time.time()
    proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
    if proc.stdout:
        print(proc.stdout.rstrip(), flush=True)
    elapsed = time.time() - started
    print(f"<<< {label}: exit={proc.returncode}, elapsed={elapsed:.1f}s", flush=True)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def _backfill_one(trade_date: str, timeout: int) -> None:
    print(f"\n===== backfill {trade_date} =====", flush=True)
    before = _counts(trade_date)
    print(f"before={before}", flush=True)
    while True:
        current = _counts(trade_date)
        if current["fact_sector_stock_daily"] > 0:
            con = connect(read_only=True)
            try:
                sectors_done = con.execute(
                    "SELECT COUNT(DISTINCT sector_ts_code) FROM fact_sector_stock_daily WHERE trade_date = ?",
                    [trade_date],
                ).fetchone()[0]
                sectors_total = con.execute("SELECT COUNT(*) FROM dim_sector").fetchone()[0]
            finally:
                con.close()
            if sectors_done >= sectors_total:
                print(f"skip {trade_date} sector-stocks: {sectors_done}/{sectors_total} sectors done", flush=True)
                break
        _run(
            f"{trade_date} sector-stocks chunk",
            [sys.executable, "-m", "market_feature_store.cli", "sync-sector-stocks", "--trade-date", trade_date, "--limit", "20", "--sleep", "0.05"],
            timeout,
        )
    current = _counts(trade_date)
    if current["fact_theme_limit_heat_daily"] == 0 or current["fact_theme_limit_stock_daily"] == 0:
        _run(
            f"{trade_date} limit-heat",
            [sys.executable, "-m", "market_feature_store.cli", "sync-limit-heat", "--trade-date", trade_date, "--detail-chunk", "6", "--sleep", "0.05"],
            timeout,
        )
    else:
        print(f"skip {trade_date} limit-heat", flush=True)
    current = _counts(trade_date)
    if current["fact_limit_advance_daily"] == 0:
        _run(
            f"{trade_date} limit-advance",
            [sys.executable, "-m", "market_feature_store.cli", "sync-limit-advance", "--trade-date", trade_date, "--min-boards", "3"],
            timeout,
        )
    else:
        print(f"skip {trade_date} limit-advance", flush=True)
    print(f"after={_counts(trade_date)}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", default="2026-05-06")
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    dates = _missing_dates(args.before, args.limit)
    print(f"dates={dates}", flush=True)
    for trade_date in dates:
        _backfill_one(trade_date, args.timeout)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
