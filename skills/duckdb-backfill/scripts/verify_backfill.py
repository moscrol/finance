#!/usr/bin/env python3
"""Post-backfill verification for the theme/sector fact tables.

Two layers of verification:

1. Integrity (read-only DuckDB, no network): coverage vs the trading calendar,
   duplicate primary keys, per-date row-count distribution / anomalies,
   cross-table date consistency, referential checks, and null sanity.

2. Sample re-fetch diff (CDP -> fupanhui): for a random sample of backfilled
   dates, re-fetch from the live source using the project's own fetchers and
   diff against what is stored:
     - limit_heat:   DB heat rows (dimension='sector', scope='all') vs the
                     number of sector items returned by limit-distribution.
     - sector_stock: DB stock rows for a sampled sector/date vs the live
                     sector-cycle stocks count.

DuckDB is single-writer; this opens the DB read_only and therefore MUST be run
when no backfill writer is active (otherwise the open fails with a lock error).
"""
from __future__ import annotations

import argparse
import random
import statistics
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[3]
DB = ROOT / "db" / "market_feature_store.duckdb"
STATE = ROOT / "skills" / "duckdb-backfill" / "state"

# table -> (fact name, primary-key columns)
SPEC = {
    "limit_heat": ("fact_theme_limit_heat_daily",
                   ("trade_date", "sector_ts_code", "dimension", "scope")),
    "limit_stock": ("fact_theme_limit_stock_daily",
                    ("trade_date", "sector_ts_code", "stock_ts_code")),
    "sector_stock": ("fact_sector_stock_daily",
                     ("trade_date", "sector_ts_code", "stock_ts_code")),
}

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"
_counts = {PASS: 0, WARN: 0, FAIL: 0}


def emit(level: str, check: str, msg: str) -> None:
    _counts[level] = _counts.get(level, 0) + 1
    print(f"[{level}] {check}: {msg}")


def load_skip(table: str) -> set[str]:
    f = STATE / f"{table}_skip.txt"
    if not f.exists():
        return set()
    return {ln.strip() for ln in f.read_text().splitlines() if ln.strip()}


def calendar(con) -> list[str]:
    rows = con.execute(
        """
        SELECT trade_date FROM fact_market_daily
        WHERE total_amount IS NOT NULL ORDER BY trade_date
        """
    ).fetchall()
    return [str(r[0]) for r in rows]


def present_dates(con, fact: str) -> list[str]:
    rows = con.execute(
        f"SELECT DISTINCT trade_date FROM {fact} ORDER BY trade_date"
    ).fetchall()
    return [str(r[0]) for r in rows]


def check_coverage(con, table: str, fact: str, cal: list[str]) -> None:
    present = set(present_dates(con, fact))
    skip = load_skip(table)
    missing = [d for d in cal if d not in present]
    real_missing = [d for d in missing if d not in skip]
    if not missing:
        emit(PASS, f"{table}/coverage", f"missing=0 over {len(cal)} calendar days")
    elif not real_missing:
        emit(PASS, f"{table}/coverage",
             f"missing={len(missing)} but all are skip-listed (real_missing=0)")
    else:
        emit(FAIL, f"{table}/coverage",
             f"real_missing={len(real_missing)} (excl skip); "
             f"first={real_missing[:8]}")


def check_duplicates(con, table: str, fact: str, pk: tuple[str, ...]) -> None:
    cols = ", ".join(pk)
    dups = con.execute(
        f"""
        SELECT COUNT(*) FROM (
            SELECT {cols} FROM {fact} GROUP BY {cols} HAVING COUNT(*) > 1
        )
        """
    ).fetchone()[0]
    if dups == 0:
        emit(PASS, f"{table}/duplicate_keys", f"0 duplicate ({', '.join(pk)})")
    else:
        emit(FAIL, f"{table}/duplicate_keys",
             f"{dups} duplicated key groups on ({', '.join(pk)})")


def check_rowcount_dist(con, table: str, fact: str) -> dict[str, int]:
    rows = con.execute(
        f"SELECT trade_date, COUNT(*) FROM {fact} GROUP BY trade_date"
    ).fetchall()
    counts = {str(d): int(c) for d, c in rows}
    if not counts:
        emit(WARN, f"{table}/rowcount", "no rows present")
        return counts
    vals = sorted(counts.values())
    med = statistics.median(vals)
    floor = max(1, int(med * 0.3))
    anomalies = sorted(d for d, c in counts.items() if c < floor)
    summary = (f"dates={len(counts)} rows/day min={vals[0]} "
               f"median={int(med)} max={vals[-1]} floor={floor}")
    if anomalies:
        emit(WARN, f"{table}/rowcount",
             f"{summary}; {len(anomalies)} low-row dates: {anomalies[:8]}")
    else:
        emit(PASS, f"{table}/rowcount", summary)
    return counts


def check_heat_stock_consistency(con) -> None:
    heat = set(present_dates(con, SPEC["limit_heat"][0]))
    stock = set(present_dates(con, SPEC["limit_stock"][0]))
    stock_only = sorted(stock - heat)
    if stock_only:
        emit(FAIL, "consistency/heat_vs_stock",
             f"{len(stock_only)} dates have limit_stock but no limit_heat: "
             f"{stock_only[:8]}")
    else:
        emit(PASS, "consistency/heat_vs_stock",
             f"every limit_stock date has limit_heat "
             f"(heat={len(heat)} stock={len(stock)})")
    # heat dates with limit-up sectors but no stock rows are suspicious.
    heat_with_limitups = con.execute(
        """
        SELECT DISTINCT h.trade_date
        FROM fact_theme_limit_heat_daily h
        WHERE COALESCE(h.limit_up_count, 0) > 0
          AND h.trade_date NOT IN (
              SELECT DISTINCT trade_date FROM fact_theme_limit_stock_daily)
        """
    ).fetchall()
    bad = sorted(str(r[0]) for r in heat_with_limitups)
    if bad:
        emit(WARN, "consistency/heat_has_limitups_no_stock",
             f"{len(bad)} dates have limit-up sectors but 0 stock rows: {bad[:8]}")
    else:
        emit(PASS, "consistency/heat_has_limitups_no_stock",
             "all dates with limit-up sectors have stock detail rows")


def check_sector_universe(con) -> None:
    fact = SPEC["sector_stock"][0]
    total = con.execute("SELECT COUNT(*) FROM dim_sector").fetchone()[0]
    rows = con.execute(
        f"SELECT trade_date, COUNT(DISTINCT sector_ts_code) FROM {fact} "
        f"GROUP BY trade_date"
    ).fetchall()
    if not rows:
        emit(WARN, "sector_stock/sector_coverage", "no rows present")
        return
    per = {str(d): int(c) for d, c in rows}
    vals = sorted(per.values())
    med = statistics.median(vals)
    floor = max(1, int(med * 0.5))
    low = sorted(d for d, c in per.items() if c < floor)
    summary = (f"dim_sector={total} sectors/day min={vals[0]} "
               f"median={int(med)} max={vals[-1]}")
    if low:
        emit(WARN, "sector_stock/sector_coverage",
             f"{summary}; {len(low)} dates with few sectors: {low[:8]}")
    else:
        emit(PASS, "sector_stock/sector_coverage", summary)
    unknown = con.execute(
        f"""
        SELECT COUNT(DISTINCT sector_ts_code) FROM {fact}
        WHERE sector_ts_code NOT IN (SELECT sector_ts_code FROM dim_sector)
        """
    ).fetchone()[0]
    if unknown == 0:
        emit(PASS, "sector_stock/referential",
             "all sector_ts_code exist in dim_sector")
    else:
        emit(WARN, "sector_stock/referential",
             f"{unknown} sector_ts_code not in dim_sector")


def check_nulls(con) -> None:
    heat_bad = con.execute(
        "SELECT COUNT(*) FROM fact_theme_limit_heat_daily "
        "WHERE rank IS NULL OR sector_name IS NULL"
    ).fetchone()[0]
    emit(PASS if heat_bad == 0 else WARN, "limit_heat/nulls",
         f"{heat_bad} rows with NULL rank/sector_name")
    ss_bad = con.execute(
        "SELECT COUNT(*) FROM fact_sector_stock_daily "
        "WHERE price IS NULL AND pct_chg IS NULL AND amount IS NULL"
    ).fetchone()[0]
    emit(PASS if ss_bad == 0 else WARN, "sector_stock/nulls",
         f"{ss_bad} rows with price+pct_chg+amount all NULL")


# ---------------------------------------------------------------------------
# Sample re-fetch diff (network)
# ---------------------------------------------------------------------------
def refetch_diff(con, sample: int, seed: int | None) -> None:
    try:
        sys.path.insert(0, str(ROOT))
        from market_feature_store.sources import fupanhui_source as fs
    except Exception as exc:  # noqa: BLE001
        emit(WARN, "refetch/import",
             f"cannot import fupanhui_source ({exc}); skipping re-fetch diff")
        return

    rng = random.Random(seed)

    # ---- limit_heat: heat rows vs distribution items -----------------------
    heat_dates = present_dates(con, SPEC["limit_heat"][0])
    for d in rng.sample(heat_dates, min(sample, len(heat_dates))):
        db_n = con.execute(
            "SELECT COUNT(*) FROM fact_theme_limit_heat_daily "
            "WHERE trade_date = ? AND dimension = 'sector' AND scope = 'all'",
            [d],
        ).fetchone()[0]
        try:
            data = fs.api_get(
                "/api/v1/client/watchlist/limit-distribution",
                {"trade_date": d, "dimension": "sector",
                 "mode": "auto", "scope": "all"},
                timeout=90,
            )
            items = (data or {}).get("items") or []
            src_n = sum(1 for it in items if it.get("code") and it.get("name"))
        except Exception as exc:  # noqa: BLE001
            emit(WARN, "refetch/limit_heat", f"{d}: source fetch failed ({exc})")
            continue
        diff = abs(db_n - src_n)
        msg = f"{d}: db={db_n} source={src_n} diff={diff}"
        if diff == 0:
            emit(PASS, "refetch/limit_heat", msg)
        elif diff <= max(5, int(src_n * 0.05)):
            emit(WARN, "refetch/limit_heat", msg + " (within tolerance)")
        else:
            emit(FAIL, "refetch/limit_heat", msg)

    # ---- sector_stock: stocks for a sampled sector/date --------------------
    ss_dates = present_dates(con, SPEC["sector_stock"][0])
    for d in rng.sample(ss_dates, min(sample, len(ss_dates))):
        secs = con.execute(
            "SELECT sector_ts_code, COUNT(*) FROM fact_sector_stock_daily "
            "WHERE trade_date = ? GROUP BY sector_ts_code",
            [d],
        ).fetchall()
        if not secs:
            continue
        sec, db_n = rng.choice(secs)
        db_n = int(db_n)
        try:
            payload = fs.get_sector_stocks(sec, trade_date=d)
            src_n = len(payload.get("stocks") or [])
        except Exception as exc:  # noqa: BLE001
            emit(WARN, "refetch/sector_stock",
                 f"{d}/{sec}: source fetch failed ({exc})")
            continue
        diff = abs(db_n - src_n)
        msg = f"{d}/{sec}: db={db_n} source={src_n} diff={diff}"
        if diff == 0:
            emit(PASS, "refetch/sector_stock", msg)
        elif diff <= max(3, int(src_n * 0.10)):
            emit(WARN, "refetch/sector_stock", msg + " (within tolerance)")
        else:
            emit(FAIL, "refetch/sector_stock", msg)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=4,
                    help="dates to re-fetch per table (default 4)")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--no-refetch", action="store_true",
                    help="integrity checks only, skip network re-fetch diff")
    a = ap.parse_args()

    if not DB.exists():
        print(f"DB not found: {DB}", file=sys.stderr)
        return 2
    try:
        con = duckdb.connect(str(DB), read_only=True)
    except Exception as exc:  # noqa: BLE001
        print(f"cannot open DB read-only (writer active?): {exc}", file=sys.stderr)
        return 3

    try:
        cal = calendar(con)
        print(f"=== calendar: {len(cal)} trading days "
              f"({cal[0]} ~ {cal[-1]}) ===")
        print("--- integrity ---")
        for table in ("limit_heat", "limit_stock", "sector_stock"):
            fact, pk = SPEC[table]
            check_coverage(con, table, fact, cal)
            check_duplicates(con, table, fact, pk)
            check_rowcount_dist(con, table, fact)
        check_heat_stock_consistency(con)
        check_sector_universe(con)
        check_nulls(con)
        if not a.no_refetch:
            print("--- sample re-fetch diff (CDP -> fupanhui) ---")
            refetch_diff(con, a.sample, a.seed)
    finally:
        con.close()

    print("--- summary ---")
    print(f"PASS={_counts[PASS]} WARN={_counts[WARN]} FAIL={_counts[FAIL]}")
    return 1 if _counts[FAIL] else 0


if __name__ == "__main__":
    raise SystemExit(main())
