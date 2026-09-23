"""Read-only canonical value audit; row counts alone do not establish valid bars.

Usage: readback_values.py DATABASE
No connection initialization or migrations; prints a dated aggregate, never writes
any database. Zero/NULL amount may mean nontrading, not a license to invent bars.
"""
from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import duckdb
from market_feature_store.hithink_stock_preview import preview_stock_calculation

path = Path(sys.argv[1]).resolve(strict=True)
before = path.stat()
with duckdb.connect(str(path), read_only=True) as con:
    result = con.execute("""
        SELECT trade_date::VARCHAR AS trade_date, COUNT(*) AS rows,
               COUNT(*) FILTER (WHERE close IS NULL OR NOT isfinite(close) OR close <= 0) AS invalid_close,
               COUNT(*) FILTER (WHERE pre_close IS NULL) AS null_pre_close,
               COUNT(*) FILTER (WHERE pct_chg IS NULL) AS null_pct_chg,
               COUNT(*) FILTER (WHERE amount IS NULL) AS null_amount,
               COUNT(*) FILTER (WHERE amount = 0) AS zero_amount,
               COUNT(*) FILTER (WHERE stock_name IS NULL) AS null_stock_name,
               COUNT(*) FILTER (WHERE turnover IS NULL) AS null_turnover
        FROM fact_stock_daily WHERE trade_date >= ?::DATE
        GROUP BY trade_date ORDER BY trade_date
    """, ["2026-09-18"])
    columns = [col[0] for col in result.description]
    rows = [dict(zip(columns, row)) for row in result.fetchall()]
    vendor_only = con.execute("""
        SELECT h.trade_date::VARCHAR, h.stock_ts_code
        FROM fact_stock_daily_hithink AS h
        LEFT JOIN fact_stock_daily AS c USING (trade_date, stock_ts_code)
        WHERE h.trade_date >= ?::DATE AND c.stock_ts_code IS NULL
        ORDER BY h.trade_date, h.stock_ts_code
    """, ["2026-09-18"]).fetchall()
    missing_by_day = defaultdict(list)
    for trade_date, code in vendor_only:
        missing_by_day[trade_date].append(code)
    explanations = [preview_stock_calculation(con, day, stock_codes=codes)
                    for day, codes in sorted(missing_by_day.items())]
after = path.stat()
print(json.dumps({"database": str(path), "read_only": True,
                  "read_at": datetime.now(timezone.utc).isoformat(),
                  "vendor_bars_missing_from_canonical": [dict(zip(("trade_date", "stock_ts_code"), row)) for row in vendor_only],
                  "file_metadata_unchanged": (before.st_ino, before.st_size, before.st_mtime_ns) == (after.st_ino, after.st_size, after.st_mtime_ns),
                  "value_audit": rows, "missing_bar_previews": explanations}, indent=2))
