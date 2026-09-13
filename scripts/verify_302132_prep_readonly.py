#!/usr/bin/env python3
"""Fixed-incident review of 302132 preparation; all file databases are read-only.

Does not invoke prep_verify.py, repair, stitch writers, or daily-full. An in-memory
connection attaches the original production and already-prepared clone read-only.
The output is review evidence, not production execution approval.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import subprocess
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import duckdb

CODE = "302132.SZ"
START, END = "2026-06-15", "2026-09-11"
TABLES = ("fact_stock_daily", "feature_stock_technical_daily", "feature_stock_window")


def identity(path: Path) -> dict:
    st = path.stat()
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"path": str(path), "sha256": digest,
            "stat": [st.st_ino, st.st_mtime_ns, st.st_size]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--production", type=Path, required=True)
    parser.add_argument("--clone", type=Path, required=True)
    parser.add_argument("--parquet", type=Path, required=True)
    parser.add_argument("--prep-script", type=Path, required=True)
    parser.add_argument("--prep-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    inputs = {name: getattr(args, name).resolve(strict=True)
              for name in ("production", "clone", "parquet", "prep_script", "prep_report")}
    if args.output.exists() or args.output.resolve() in inputs.values():
        parser.error("output must be a new file, distinct from all inputs")
    before = {name: identity(path) for name, path in inputs.items()}
    receipt = json.loads(inputs["prep_report"].read_text())
    checks = []
    observations = {}

    def check(name, ok, detail):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    with duckdb.connect(":memory:") as con:
        con.execute("SET threads=2")
        con.execute("SET memory_limit='1GB'")
        for alias, key in (("prod", "production"), ("prep", "clone")):
            path_sql = str(inputs[key]).replace("'", "''")
            con.execute(f"ATTACH '{path_sql}' AS {alias} (READ_ONLY)")
        parquet_sql = str(inputs["parquet"]).replace("'", "''")
        con.execute("CREATE TEMP VIEW pq AS SELECT *, CAST(to_timestamp(date_ms / 1000) AS DATE) AS td "
                    f"FROM read_parquet('{parquet_sql}')")

        def rows(sql, params=None):
            return con.execute(sql, params or []).fetchall()

        def scalar(sql, params=None):
            return rows(sql, params)[0][0]

        def delta(table, predicate="TRUE", values_only=False):
            names = [r[0] for r in rows(f"DESCRIBE prod.{table}")]
            cols = ", ".join(f'"{name}"' for name in names
                             if not (values_only and name == "calculated_at"))
            a = f"SELECT {cols} FROM prod.{table} WHERE {predicate}"
            b = f"SELECT {cols} FROM prep.{table} WHERE {predicate}"
            return [scalar(f"SELECT count(*) FROM ({a} EXCEPT ALL {b})"),
                    scalar(f"SELECT count(*) FROM ({b} EXCEPT ALL {a})")]

        check("production_bound_to_prep_receipt",
              all(before["production"][k] == receipt["production_before"][k]
                  == receipt["production_after"][k] for k in ("sha256", "stat")),
              before["production"])
        observations["freshness"] = {
            table: rows(f"SELECT max({'as_of_date' if table == 'feature_stock_window' else 'trade_date'}) "
                        f"FROM prod.{table}")[0][0]
            for table in (*TABLES, "fact_market_daily", "fact_stock_daily_hithink")
        }
        calendar = [r[0] for r in rows("SELECT trade_date FROM prod.fact_market_daily "
                                     "WHERE trade_date BETWEEN ? AND ? ORDER BY 1", [START, END])]
        reference = [r[0] for r in rows("SELECT trade_date FROM prod.fact_stock_daily "
                                      "WHERE stock_ts_code='600176.SH' AND trade_date BETWEEN ? AND ? "
                                      "ORDER BY 1", [START, END])]
        target = [r[0] for r in rows("SELECT trade_date FROM prep.fact_stock_daily "
                                   "WHERE stock_ts_code=? ORDER BY 1", [CODE])]
        check("canonical_calendar_exact_64_dates", calendar == reference == target and len(target) == 64,
              {"market_days": len(calendar), "reference_stock_days": len(reference),
               "target_days": len(target), "missing": sorted(set(calendar) - set(target)),
               "unexpected": sorted(set(target) - set(calendar))})
        old = rows("SELECT * FROM prod.fact_stock_daily WHERE stock_ts_code=? ORDER BY trade_date", [CODE])
        old_dates = {r[0] for r in old}
        missing = sorted(set(calendar) - old_dates)
        check("53_exact_missing_dates", [str(d) for d in missing] == sorted(
            receipt["gap_dates_parallel"] + receipt["gap_dates_parquet"]), missing)
        observations["original_target_rows"] = old
        check("retained_10_rows_including_0911_identical",
              delta("fact_stock_daily", f"stock_ts_code='{CODE}' AND trade_date IN "
                    f"(SELECT trade_date FROM prod.fact_stock_daily WHERE stock_ts_code='{CODE}' "
                    "AND trade_date <> DATE '2026-06-23')") == [0, 0], {"retained_rows": len(old) - 1})
        for table in TABLES:
            diff = delta(table, f"stock_ts_code <> '{CODE}'")
            if table == "fact_stock_daily":
                check("other_stock_facts_identical_all_columns", diff == [0, 0], diff)
            else:
                observations[f"{table}_other_stock_diff_including_timestamp"] = diff
                observations[f"{table}_other_stock_diff_values"] = delta(
                    table, f"stock_ts_code <> '{CODE}'", values_only=True)
        check("market_fact_unchanged", delta("fact_market_daily") == [0, 0], delta("fact_market_daily"))

        source = rows("SELECT min(trade_date), max(trade_date), count(*), list(DISTINCT adjusted) "
                      "FROM prod.fact_stock_daily_hithink WHERE stock_ts_code=?", [CODE])
        observations["parallel_source_history"] = source
        adjustments = rows("SELECT * FROM prod.fact_stock_adjustment_hithink WHERE stock_ts_code=? "
                           "AND ex_date BETWEEN DATE '2026-01-01' AND DATE '2026-12-31' ORDER BY ex_date", [CODE])
        observations["adjustments_2026"] = adjustments
        check("one_2026_cash_event_outside_changed_dates",
              len(adjustments) == 1 and str(adjustments[0][1]) == "2026-06-16"
              and adjustments[0][2] == 0.386 and not adjustments[0][3] and not adjustments[0][4], adjustments)
        count, equal = rows("SELECT count(*), count(*) FILTER (WHERE p.close=h.close) "
                            "FROM prod.fact_stock_daily p JOIN prod.fact_stock_daily_hithink h "
                            "USING (stock_ts_code, trade_date) WHERE p.stock_ts_code=? AND p.close IS NOT NULL", [CODE])[0]
        check("nine_old_closes_equal_parallel", count == equal == 9, {"overlap": count, "equal": equal})
        overlap = rows("SELECT p.td, h.open IS NOT DISTINCT FROM p.open_price, "
                       "h.high IS NOT DISTINCT FROM p.high_price, h.low IS NOT DISTINCT FROM p.low_price, "
                       "h.close IS NOT DISTINCT FROM p.close_price, h.volume IS NOT DISTINCT FROM p.volume, "
                       "h.turnover IS NOT DISTINCT FROM p.turnover, h.adjusted IS NOT DISTINCT FROM p.adjusted "
                       "FROM pq p JOIN prod.fact_stock_daily_hithink h ON h.trade_date=p.td AND h.stock_ts_code=p.thscode "
                       "WHERE p.thscode=? ORDER BY p.td", [CODE])
        check("seven_overlap_bars_all_ohlcv_turnover_adjusted_equal",
              len(overlap) == 7 and all(all(r[1:]) for r in overlap), overlap)
        con.execute("CREATE TEMP VIEW target_source AS "
                    "SELECT trade_date, open, high, low, close, volume, turnover, adjusted FROM prod.fact_stock_daily_hithink "
                    "WHERE stock_ts_code='302132.SZ' AND trade_date BETWEEN DATE '2026-06-12' AND DATE '2026-09-08' "
                    "UNION ALL SELECT td, open_price, high_price, low_price, close_price, volume, turnover, adjusted "
                    "FROM pq WHERE thscode='302132.SZ' AND td BETWEEN DATE '2026-09-09' AND DATE '2026-09-11'")
        check("sources_unadjusted", rows("SELECT DISTINCT adjusted FROM target_source") == [("none",)],
              rows("SELECT DISTINCT adjusted FROM target_source"))
        # Independent field expression uses repair module's pre_close DECIMAL(18,2).
        mapped = rows("WITH s AS (SELECT *, lag(close) OVER (ORDER BY trade_date)::DECIMAL(18,2) AS prev "
                      "FROM target_source) SELECT f.trade_date, "
                      "f.open IS NOT DISTINCT FROM s.open AND f.high IS NOT DISTINCT FROM s.high "
                      "AND f.low IS NOT DISTINCT FROM s.low AND f.close IS NOT DISTINCT FROM s.close "
                      "AND f.pre_close IS NOT DISTINCT FROM s.prev::DOUBLE "
                      "AND f.pct_chg IS NOT DISTINCT FROM round(((s.close::DECIMAL(18,4)/s.prev-1)*100)::DECIMAL(38,12),2)::DOUBLE "
                      "AND f.amount IS NOT DISTINCT FROM round(s.turnover::DECIMAL(38,2)/100000000,4)::DOUBLE "
                      "AND f.volume IS NOT DISTINCT FROM round(s.volume::DECIMAL(38,0)/100,0)::DOUBLE "
                      "AND f.turnover IS NULL AND f.stock_name='中航成飞' "
                      "AND f.source=CASE WHEN f.trade_date<=DATE '2026-09-08' "
                      "THEN 'hithink:daily-k:backfill-302132-20260914' ELSE 'hithink:daily-k-10d:backfill-302132-20260914' END "
                      "FROM prep.fact_stock_daily f JOIN s USING (trade_date) "
                      "WHERE f.stock_ts_code='302132.SZ' AND (f.trade_date NOT IN "
                      "(SELECT trade_date FROM prod.fact_stock_daily WHERE stock_ts_code='302132.SZ') "
                      "OR f.trade_date=DATE '2026-06-23') ORDER BY f.trade_date")
        check("all_54_changed_rows_match_full_field_mapping", len(mapped) == 54 and all(r[1] for r in mapped), mapped)
        prices = rows("SELECT trade_date, close, amount FROM prep.fact_stock_daily WHERE stock_ts_code=? ORDER BY 1", [CODE])
        tech = rows("SELECT close, ma26, std26, up_value, deviation_pct FROM prep.feature_stock_technical_daily "
                    "WHERE stock_ts_code=? AND trade_date=?", [CODE, END])
        closes = [r[1] for r in prices[-26:]]
        ma, std = statistics.mean(closes), statistics.pstdev(closes)
        up = ma + 0.764 * std
        expected_tech = [prices[-1][1], round(ma, 4), round(std, 4), round(up, 4),
                         round((prices[-1][1] / up - 1) * 100, 2)]
        check("independent_0911_technical_formula", len(tech) == 1 and all(
            math.isclose(a, b, abs_tol=1e-8) for a, b in zip(tech[0], expected_tech, strict=True)),
            {"actual": tech, "expected": expected_tech})
        wins = rows("SELECT start_date, end_date, interval_gain_pct, avg_amount FROM prep.feature_stock_window "
                    "WHERE stock_ts_code=? AND as_of_date=? ORDER BY start_date", [CODE, END])
        expected_wins = [(prices[-p-1][0], prices[-1][0], round((prices[-1][1]/prices[-p-1][1]-1)*100, 2),
                          float((sum(Decimal(str(r[2])) for r in prices[-p:]) / Decimal(p)).quantize(
                              Decimal('0.0001'), rounding=ROUND_HALF_UP))) for p in (60, 20, 10, 5)]
        check("independent_0911_all_four_window_formulas", wins == expected_wins,
              {"actual": wins, "expected": expected_wins})
        observations["target_derived_actual_counts_vs_64day_plan"] = {
            "technical_actual_in_window": scalar("SELECT count(*) FROM prep.feature_stock_technical_daily WHERE stock_ts_code=? AND trade_date BETWEEN ? AND ?", [CODE, START, END]),
            "window_actual_in_window": scalar("SELECT count(*) FROM prep.feature_stock_window WHERE stock_ts_code=? AND as_of_date BETWEEN ? AND ?", [CODE, START, END]),
            "technical_expected_after_full_execution": 39, "window_expected_after_full_execution": 161,
            "note": "Preparation samples six dates only, not the full scoped execution."}
        observations["original_target_technical_date_buckets"] = rows(
            "SELECT CASE WHEN trade_date < DATE '2026-06-15' THEN 'before_window' "
            "WHEN trade_date <= (SELECT trade_date FROM prod.fact_market_daily WHERE trade_date>=DATE '2026-06-15' ORDER BY trade_date LIMIT 1 OFFSET 24) "
            "THEN 'first_25_observations' WHEN trade_date<=DATE '2026-09-11' THEN 'remaining_window' ELSE 'after_window' END AS bucket, "
            "count(*), min(trade_date), max(trade_date) FROM prod.feature_stock_technical_daily WHERE stock_ts_code=? GROUP BY 1", [CODE])
        observations["original_target_window_rows"] = rows(
            "SELECT as_of_date,start_date,end_date FROM prod.feature_stock_window WHERE stock_ts_code=? ORDER BY 1,2", [CODE])
        observations["old_nonnull_rows_missing_ohlcv"] = rows(
            "SELECT count(*), count(*) FILTER(WHERE open IS NULL AND high IS NULL AND low IS NULL AND volume IS NULL), "
            "count(*) FILTER(WHERE amount <> round(amount, 2)) FROM prod.fact_stock_daily "
            "WHERE stock_ts_code=? AND trade_date<DATE '2026-09-11' AND close IS NOT NULL", [CODE])
        for table in TABLES[1:]:
            date_col = 'as_of_date' if table == 'feature_stock_window' else 'trade_date'
            observations[f"{table}_target_outside_window_diff"] = delta(
                table, f"stock_ts_code='{CODE}' AND {date_col} NOT BETWEEN DATE '{START}' AND DATE '{END}'")
        observations["0911_others_value_vs_timestamp_diff"] = {
            table: {"values": delta(table, f"stock_ts_code<>'{CODE}' AND "
                                    f"{'as_of_date' if table == 'feature_stock_window' else 'trade_date'}=DATE '{END}'", True),
                    "all_columns": delta(table, f"stock_ts_code<>'{CODE}' AND "
                                          f"{'as_of_date' if table == 'feature_stock_window' else 'trade_date'}=DATE '{END}'")}
            for table in TABLES[1:]}
        observations["window_rows_with_source_counts"] = rows(
            "SELECT w.as_of_date, w.start_date, w.end_date, count(f.trade_date) FROM prep.feature_stock_window w "
            "JOIN prep.fact_stock_daily f ON f.stock_ts_code=w.stock_ts_code AND f.trade_date BETWEEN w.start_date AND w.end_date "
            "WHERE w.stock_ts_code=? GROUP BY ALL ORDER BY 1,2", [CODE])
    after = {name: identity(path) for name, path in inputs.items()}
    check("all_inputs_unchanged_hash_and_stat", before == after, {"equal": before == after})
    report = {"kind": "302132-prep-independent-readonly-review", "review_revision": subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True).strip(), "script_sha256": identity(Path(__file__))["sha256"],
        "duckdb_version": duckdb.__version__, "inputs_before": before, "inputs_after": after,
        "checks": checks, "observations": observations,
        "verdict": "PASS" if all(c["ok"] for c in checks) else "FAIL",
        "scope": "Data/source/formula checks only; NOT full scoped execution or production authorization."}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, default=str)
        stream.write("\n")
    print(json.dumps({"verdict": report["verdict"], "checks": len(checks),
                      "failed": [c["name"] for c in checks if not c["ok"]],
                      "observations": observations, "output": str(args.output)}, ensure_ascii=False, default=str))
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
