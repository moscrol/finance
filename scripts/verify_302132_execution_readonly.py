#!/usr/bin/env python3
"""Fixed 302132 execution audit. File DBs are always ATTACH READ_ONLY.

No repair imports, no production writes, no copies of production.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import duckdb

CODE = "302132.SZ"
D0, D1 = "2026-06-15", "2026-09-11"


def identity(path):
    stat = path.stat()
    with path.open("rb") as stream:
        sha = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"sha256": sha, "stat": [stat.st_ino, stat.st_size, stat.st_mtime_ns]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ("production", "clone", "parquet", "output"):
        p.add_argument("--" + key, type=Path, required=True)
    a = p.parse_args()
    if a.output.exists():
        p.error("refuse overwrite")
    inputs = {k: getattr(a, k).resolve(strict=True) for k in ("production", "clone", "parquet")}
    before = {k: identity(v) for k, v in inputs.items()}
    checks, observations = [], {}

    def check(name, ok, detail):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    with duckdb.connect(":memory:") as con:
        con.execute("SET threads=2")
        con.execute("SET memory_limit='1GB'")
        for alias, key in (("prod", "production"), ("out", "clone")):
            escaped = str(inputs[key]).replace("'", "''")
            con.execute(f"ATTACH '{escaped}' AS {alias} (READ_ONLY)")

        def rows(sql, params=None):
            return con.execute(sql, params or []).fetchall()

        def delta(table, where="TRUE"):
            left = f"SELECT * FROM prod.{table} WHERE {where}"
            right = f"SELECT * FROM out.{table} WHERE {where}"
            return [rows(f"SELECT count(*) FROM ({left} EXCEPT ALL {right})")[0][0],
                    rows(f"SELECT count(*) FROM ({right} EXCEPT ALL {left})")[0][0]]

        cal = [r[0] for r in rows("SELECT trade_date FROM prod.fact_market_daily "
                                 "WHERE trade_date BETWEEN ? AND ? ORDER BY 1", [D0, D1])]
        observed = [r[0] for r in rows("SELECT trade_date FROM out.fact_stock_daily "
                                      "WHERE stock_ts_code=? ORDER BY 1", [CODE])]
        check("exact_64_dates", observed == cal and len(cal) == 64, len(observed))
        for table, where in (
            ("fact_stock_daily", f"stock_ts_code<>'{CODE}'"),
            ("fact_stock_daily", f"stock_ts_code='{CODE}' AND trade_date IN "
             f"(SELECT trade_date FROM prod.fact_stock_daily WHERE stock_ts_code='{CODE}' "
             "AND trade_date<>'2026-06-23')"),
            ("feature_stock_technical_daily", f"stock_ts_code<>'{CODE}' OR "
             f"trade_date NOT BETWEEN '{D0}' AND '{D1}'"),
            ("feature_stock_window", f"stock_ts_code<>'{CODE}' OR "
             f"as_of_date NOT BETWEEN '{D0}' AND '{D1}'"),
            ("fact_market_daily", "TRUE"),
            ("fact_sector_daily_generation", "TRUE"),
            ("fact_sector_stock_daily_generation", "TRUE"),
        ):
            diff = delta(table, where)
            check(table + ":" + where, diff == [0, 0], diff)
        pq = str(inputs["parquet"]).replace("'", "''")
        sources = rows("SELECT trade_date, open, high, low, close, volume, turnover "
                       "FROM prod.fact_stock_daily_hithink WHERE stock_ts_code=? "
                       "AND trade_date BETWEEN '2026-06-12' AND '2026-09-08' "
                       "UNION ALL SELECT CAST(to_timestamp(date_ms/1000) AS DATE), "
                       "open_price, high_price, low_price, close_price, volume, turnover "
                       f"FROM read_parquet('{pq}') WHERE thscode=? AND "
                       "CAST(to_timestamp(date_ms/1000) AS DATE) BETWEEN "
                       "'2026-09-09' AND '2026-09-11' ORDER BY 1", [CODE, CODE])
        targets = rows("SELECT trade_date, stock_name, open, high, low, close, pre_close, "
                       "pct_chg, amount, volume, turnover, source FROM out.fact_stock_daily "
                       "WHERE stock_ts_code=? ORDER BY 1", [CODE])
        prior_dates = {r[0] for r in rows("SELECT trade_date FROM prod.fact_stock_daily "
                                        "WHERE stock_ts_code=? AND trade_date<>'2026-06-23'", [CODE])}
        def q(value, digits):
            return Decimal(str(value)).quantize(Decimal(digits), rounding=ROUND_HALF_UP)
        expected = {}
        for i, s in enumerate(sources[1:], start=1):
            pre = q(sources[i-1][4], ".01")
            label = "hithink:daily-k:backfill-302132-20260914" if str(s[0]) <= "2026-09-08" else "hithink:daily-k-10d:backfill-302132-20260914"
            expected[s[0]] = ("中航成飞", *s[1:5], float(pre),
                              float(q((q(s[4], ".0001") / pre - 1) * 100, ".01")),
                              float(q(q(s[6], ".01") / 10**8, ".0001")),
                              float(q(q(s[5], "1") / 100, "1")), None, label)
        new = [r for r in targets if r[0] not in prior_dates]
        bad = [r[0] for r in new if tuple(r[1:]) != expected[r[0]]]
        check("54_full_field_oracle", len(new) == 54 and not bad, {"n": len(new), "bad": bad})
        tech_dates = [r[0] for r in rows("SELECT trade_date FROM out.feature_stock_technical_daily "
                                        "WHERE stock_ts_code=? AND trade_date BETWEEN ? AND ? ORDER BY 1",
                                        [CODE, D0, D1])]
        check("technical_exact_dates", tech_dates == cal[25:], len(tech_dates))
        wins = rows("SELECT as_of_date, start_date, end_date FROM out.feature_stock_window "
                    "WHERE stock_ts_code=? AND as_of_date BETWEEN ? AND ? ORDER BY 1,2", [CODE, D0, D1])
        exp_wins = sorted((cal[i], cal[i-period], cal[i]) for period in (5, 10, 20, 60)
                          for i in range(period, len(cal)))
        check("window_exact_tuples", wins == exp_wins, len(wins))
        pins = rows("SELECT ma26,std26,up_value,deviation_pct FROM out.feature_stock_technical_daily "
                    "WHERE stock_ts_code=? AND trade_date=?", [CODE, D1])
        check("technical_pins", pins == [(59.8542, 2.6845, 61.9052, 2.45)], pins)
        wins9 = rows("SELECT CAST(start_date AS VARCHAR),interval_gain_pct,avg_amount "
                     "FROM out.feature_stock_window WHERE stock_ts_code=? AND as_of_date=? ORDER BY 1", [CODE, D1])
        check("window_pins", wins9 == [("2026-06-18", 6.89, 5.0148), ("2026-08-14", 9.34, 6.198),
                                      ("2026-08-28", 5.7, 7.9351), ("2026-09-04", .19, 6.9264)], wins9)
        observations["retained_main_rows"] = len(prior_dates)
        observations["ops_schema"] = [r[0] for r in rows("DESCRIBE out.ops_sync_run")]
        observations["repair_ops"] = rows("SELECT run_id,kind,plan,ok,steps_summary FROM out.ops_sync_run "
                                          "WHERE kind='repair-backfill-302132' ORDER BY started_at")
        observations["freshness"] = {t: rows(f"SELECT MAX(trade_date) FROM prod.{t}")[0][0]
                                     for t in ("fact_market_daily", "fact_stock_daily", "fact_stock_daily_hithink")}
    after = {k: identity(v) for k, v in inputs.items()}
    check("inputs_unchanged", before == after, after)
    check("production_bound_to_reported_baseline", before["production"]["sha256"] ==
          "76a32fac9c8bcd542982e5f7ffd654ffcf0e8646f515487aeba3b74c3ceff168", before["production"])
    report = {"checks": checks, "observations": observations, "inputs": {k: str(v) for k,v in inputs.items()}}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with a.output.open("x") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, default=str)
        stream.write("\n")
    print(f"{sum(c['ok'] for c in checks)}/{len(checks)} PASS; output={a.output}")
    return int(any(not c["ok"] for c in checks))


if __name__ == "__main__":
    raise SystemExit(main())
