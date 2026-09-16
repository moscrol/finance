#!/usr/bin/env python3
"""把影子库里的全A日线合进生产库：只填 open/high/low/volume，指定日期整行覆盖。

为什么先写影子库：3 年 OHLC 回拉要跑几十分钟 mootdx TCP，写生产库会长期占写锁；而且第一个新写入器
一跑就会给生产表加 4 列，主树上还在跑老代码（`INSERT ... SELECT * FROM _buf_df` 位置插入）的夜跑会当场炸。
所以回拉先落 `MARKET_FEATURE_STORE_DB=<shadow>`，等新写入器合进 main、主树更新后，再用本脚本一次合入。

    python3 skills/duckdb-backfill/scripts/merge_stock_ohlc_shadow.py --shadow ~/.finance-runtime/stock-ohlc-shadow.duckdb
    python3 skills/duckdb-backfill/scripts/merge_stock_ohlc_shadow.py --shadow ... --refresh-dates 2026-08-13 --apply

默认 dry-run 只打印会写多少行；--apply 才写。--refresh-dates 里的日期整行用影子库覆盖（东财快照写坏的日子）。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from market_feature_store.db import connect, init_db  # noqa: E402
from market_feature_store.sync.sync_mootdx_stock_daily import (  # noqa: E402
    COLS,
    ensure_stock_daily_columns,
)

_COL_LIST = ", ".join(COLS)
_SHADOW_COLS = ", ".join(f"s.{c}" for c in COLS)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--shadow", required=True, help="影子库路径（sync-stock-daily 用 MARKET_FEATURE_STORE_DB 指过去写的那份）")
    p.add_argument("--refresh-dates", nargs="*", default=[], help="这些日期整行用影子库覆盖（如 2026-08-13）")
    p.add_argument("--apply", action="store_true", help="真写；默认 dry-run")
    a = p.parse_args(argv)

    shadow = Path(a.shadow).expanduser()
    if not shadow.exists():
        print(f"影子库不存在: {shadow}")
        return 2
    init_db()
    con = connect()
    try:
        ensure_stock_daily_columns(con)
        con.execute(f"ATTACH '{shadow}' AS shadow (READ_ONLY)")
        n_shadow, d0, d1 = con.execute("SELECT COUNT(*), MIN(trade_date), MAX(trade_date) FROM shadow.fact_stock_daily").fetchone()
        new_rows = con.execute(
            "SELECT COUNT(*) FROM shadow.fact_stock_daily s LEFT JOIN fact_stock_daily p USING (trade_date, stock_ts_code) WHERE p.stock_ts_code IS NULL"
        ).fetchone()[0]
        fill_rows = con.execute(
            "SELECT COUNT(*) FROM shadow.fact_stock_daily s JOIN fact_stock_daily p USING (trade_date, stock_ts_code) WHERE p.high IS NULL AND s.high IS NOT NULL"
        ).fetchone()[0]
        print(f"影子库 {n_shadow} 行 {d0}~{d1}；生产缺的整行 {new_rows}；只补 OHLC 的行 {fill_rows}；整行覆盖日 {a.refresh_dates or '无'}")
        if not a.apply:
            print("dry-run，加 --apply 才写")
            return 0
        con.execute("BEGIN TRANSACTION")
        con.execute(
            f"""
            INSERT INTO fact_stock_daily ({_COL_LIST})
            SELECT {_SHADOW_COLS} FROM shadow.fact_stock_daily s
            ON CONFLICT (trade_date, stock_ts_code) DO UPDATE SET
                open = COALESCE(EXCLUDED.open, fact_stock_daily.open),
                high = COALESCE(EXCLUDED.high, fact_stock_daily.high),
                low = COALESCE(EXCLUDED.low, fact_stock_daily.low),
                volume = COALESCE(EXCLUDED.volume, fact_stock_daily.volume)
            """
        )
        for d in a.refresh_dates:
            con.execute(
                f"""
                INSERT INTO fact_stock_daily ({_COL_LIST})
                SELECT {_SHADOW_COLS} FROM shadow.fact_stock_daily s WHERE s.trade_date = ?
                ON CONFLICT (trade_date, stock_ts_code) DO UPDATE SET
                    stock_name = EXCLUDED.stock_name, close = EXCLUDED.close, pre_close = EXCLUDED.pre_close,
                    pct_chg = EXCLUDED.pct_chg, amount = EXCLUDED.amount, turnover = EXCLUDED.turnover,
                    source = EXCLUDED.source, updated_at = EXCLUDED.updated_at,
                    open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low, volume = EXCLUDED.volume
                """,
                [d],
            )
        con.execute("COMMIT")
        total, with_high, dmin = con.execute(
            "SELECT COUNT(*), COUNT(high), MIN(trade_date) FROM fact_stock_daily"
        ).fetchone()
        print(f"已合入：fact_stock_daily {total} 行，有 high 的 {with_high} 行，最早 {dmin}")
        return 0
    except Exception:
        try:
            con.execute("ROLLBACK")
        except Exception:  # noqa: BLE001
            pass
        raise
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
