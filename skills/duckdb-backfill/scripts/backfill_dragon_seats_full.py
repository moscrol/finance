#!/usr/bin/env python3
"""席位表（fact_dragon_seat_daily）大窗口回补 driver：断点续跑 + 撞锁退避 + 完整性修复。

用法（建议经 spawn.py 守护，日志另落文件）：
    python3 skills/duckdb-backfill/scripts/backfill_dragon_seats_full.py \
        --start-date 2025-01-02 --end-date 2026-05-19

防的失败形状（都是 2026-08-13 回补实测踩过/看到的）：
1. **撞 DuckDB 写锁整个 run 炸死**：sync_range 里子任务失败后 _mark_ops 会再
   connect()，锁被占时二次抛异常逃逸、整批终止。driver 捕获非零退出码，
   退避后重跑；sync_range 的 skip 逻辑（_has_rows/_ops_done）保证断点续跑。
2. **单股 detail 静默失败**：sync_dragon_seats 单股异常只 continue，当日仍标
   complete，skip 逻辑永不回头——行数对、覆盖对，值却缺一角。主循环收敛后
   按「seats 覆盖股数 < 同源 fact_dragon_tiger_daily 股数」逐日 --refresh 修复
   （干净窗口校准：正常回补日两者逐日相等）。
3. **停不下来**：missing 连续 STALL_LIMIT 个 pass 不收敛即熔断，打印残余清单
   而不是无限重试（比如某天接口恒 404 时）。

ops status='empty' 的日子视为「源头就没有」，不算缺口——与 check_daily 口径一致。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import duckdb  # noqa: E402

from market_feature_store.db import DB_PATH  # noqa: E402

MAX_PASSES = 40
STALL_LIMIT = 3


def q(sql: str, params=None):
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        return con.execute(sql, params or []).fetchall()
    finally:
        con.close()


def missing_days(start: str, end: str) -> list[str]:
    return [str(r[0]) for r in q(
        """
        SELECT trade_date FROM fact_market_daily
        WHERE trade_date BETWEEN ? AND ?
          AND trade_date NOT IN (SELECT DISTINCT trade_date FROM fact_dragon_seat_daily)
          AND trade_date NOT IN (
            SELECT trade_date FROM ops_pipeline_run_daily
            WHERE pipeline='fupanhui-public-assets' AND step='dragon_seats' AND status='empty')
        ORDER BY trade_date
        """,
        [start, end],
    )]


def incomplete_days(start: str, end: str) -> list[str]:
    return [str(r[0]) for r in q(
        """
        WITH t AS (SELECT trade_date, COUNT(DISTINCT stock_ts_code) n
                   FROM fact_dragon_tiger_daily WHERE trade_date BETWEEN ? AND ? GROUP BY 1),
             s AS (SELECT trade_date, COUNT(DISTINCT stock_ts_code) n
                   FROM fact_dragon_seat_daily WHERE trade_date BETWEEN ? AND ? GROUP BY 1)
        SELECT t.trade_date FROM t LEFT JOIN s USING (trade_date)
        WHERE COALESCE(s.n, 0) < t.n ORDER BY 1
        """,
        [start, end, start, end],
    )]


def run_cli(sleep: float, *args: str) -> int:
    cmd = [sys.executable, "-m", "market_feature_store.cli", "sync-fupanhui-public-assets",
           "--only", "dragon_seats", "--sleep", str(sleep), *args]
    return subprocess.call(cmd, cwd=str(ROOT))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--start-date", required=True)
    ap.add_argument("--end-date", required=True)
    ap.add_argument("--sleep", type=float, default=0.15, help="detail 请求间隔秒，默认 0.15")
    ap.add_argument("--lock-backoff", type=float, default=180, help="撞锁/失败后的退避秒数")
    args = ap.parse_args()
    start, end = args.start_date, args.end_date

    prev = None
    stall = 0
    for p in range(1, MAX_PASSES + 1):
        miss = missing_days(start, end)
        print(f"== pass {p}: missing={len(miss)} ==", flush=True)
        if not miss:
            break
        if prev is not None and len(miss) >= prev:
            stall += 1
            if stall >= STALL_LIMIT:
                print(f"== STALLED: {len(miss)} 日连续 {STALL_LIMIT} pass 不收敛，熔断 ==", flush=True)
                print("residual:", miss[:20], flush=True)
                break
        else:
            stall = 0
        prev = len(miss)
        rc = run_cli(args.sleep, "--start-date", start, "--end-date", end)
        print(f"== pass {p} rc={rc} ==", flush=True)
        if rc != 0:
            time.sleep(args.lock_backoff)

    for r in range(1, 4):
        inc = incomplete_days(start, end)
        print(f"== repair round {r}: incomplete={len(inc)} ==", flush=True)
        if not inc:
            break
        for d in inc:
            rc = run_cli(args.sleep, "--start-date", d, "--end-date", d, "--refresh")
            if rc != 0:
                time.sleep(args.lock_backoff)

    print("== FINAL ==", flush=True)
    print("missing:", len(missing_days(start, end)), flush=True)
    print("incomplete:", len(incomplete_days(start, end)), flush=True)
    print(q("SELECT COUNT(DISTINCT trade_date), COUNT(*) FROM fact_dragon_seat_daily"), flush=True)


if __name__ == "__main__":
    main()
