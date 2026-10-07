#!/usr/bin/env python3
"""Local read-only audit. Requires Python 3.10+ and duckdb; never builds/writes DB labels.

Run with --main-db /path/to/market_feature_store.duckdb --labels-db /path/to/history_labels.duckdb.
Code snapshots and SQL live next to this script under ../code/. Outputs only ../data/.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
LOG = []


def write_json(name, value):
    (DATA / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str, allow_nan=False) + "\n")


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "code" / (name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def query(con, db_id, sql, params=None):
    result = con.execute(sql, params or [])
    cols = [x[0] for x in result.description]
    rows = [dict(zip(cols, row)) for row in result.fetchall()]
    LOG.append({"database": db_id, "sql": sql, "parameters": params or [], "returned_rows": len(rows)})
    return rows


def fingerprint(path):
    st = path.stat()
    return {"file": path.name, "bytes": st.st_size, "mtime_ns": st.st_mtime_ns,
            "identity_limit": "stat only, not a database-content hash"}


def series_coverage(rows, fields):
    out = []
    for field in fields:
        known = [r for r in rows if r.get(field) is not None]
        out.append({"field": field, "rows": len(rows), "non_null_rows": len(known),
                    "null_rows": len(rows) - len(known),
                    "first_non_null": known[0]["trade_date"] if known else None,
                    "last_non_null": known[-1]["trade_date"] if known else None,
                    "true_rows": sum(r.get(field) is True for r in rows) if any(isinstance(r.get(field), bool) for r in rows) else None})
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--main-db", type=Path, required=True)
    p.add_argument("--labels-db", type=Path, required=True)
    args = p.parse_args()
    for f in (args.main_db, args.labels_db):
        if not f.is_file():
            p.error(f"missing database: {f.name}")
    DATA.mkdir(exist_ok=True)
    started = datetime.now(timezone.utc).isoformat()
    before = [fingerprint(f) for f in (args.main_db, args.labels_db)]
    view = load("source_views")
    structure = load("structure")
    side = duckdb.connect(str(args.labels_db), read_only=True)
    side.execute("BEGIN TRANSACTION")
    side_counts = []
    for name in ("history_calendar", "history_teaching_labels", "history_teaching_receipts", "history_range_leaders", "history_range_leader_handoffs", "history_dynasties", "history_dynasty_handoffs", "history_reference_stages"):
        try:
            count = query(side, "labels", f'SELECT COUNT(*) AS rows FROM "{name}"')[0]
            side_counts.append({"table": name, **count})
        except duckdb.CatalogException:
            side_counts.append({"table": name, "status": "absent"})
    label_groups = query(side, "labels", "SELECT label, entity_type, status, COUNT(*) AS rows, MIN(trade_date) AS first_day, MAX(trade_date) AS last_day FROM history_teaching_labels GROUP BY ALL ORDER BY label, entity_type, status")
    side_calendar = query(side, "labels", "SELECT COUNT(*) AS days, MIN(trade_date) AS first_day, MAX(trade_date) AS last_day FROM history_calendar")
    side.execute("ROLLBACK")
    side.close()
    write_json("sidecar_audit.json", {"kind": "PERSISTED_DB_READ", "tables": side_counts, "label_groups": label_groups, "calendar": side_calendar})

    con = duckdb.connect(str(args.main_db), read_only=True)
    con.execute("BEGIN TRANSACTION")
    market_cols = ["trade_date", "total_amount", "sh_index_open", "sh_index_high", "sh_index_low", "sh_index_close", "sh_week_ma", "sh_deviation_pct", "cycle_stage"]
    market = query(con, "main", "SELECT " + ", ".join(market_cols) + " FROM fact_market_daily ORDER BY trade_date")
    first, last, days = market[0]["trade_date"], market[-1]["trade_date"], len(market)
    table_fields = {
        "fact_market_daily": market_cols[1:],
        "fact_dragon_tiger_hithink": ["net_value", "buy_value", "sell_value", "range_days"],
        "fact_dragon_tiger_daily": ["net_amount", "l_buy", "l_sell"],
        "fact_theme_limit_stock_daily": ["fd_amount", "circ_mv", "limit_status"],
        "fact_auction_hithink": ["auction_pct", "auction_amount", "kind"],
        "fact_auction_stock_daily": ["auction_pct", "auction_amount", "panel_key"],
        "fact_stock_daily_hithink": ["close", "high", "low", "adjusted"],
        "fact_stock_adjustment_hithink": ["dividend_per_share", "per_share_bonus", "allotment_ratio"],
        "fact_sector_kline_daily": ["close", "high", "low"],
    }
    coverage, schemas, raw_samples = [], {}, {}
    for table, fields in table_fields.items():
        date_col = "ex_date" if table == "fact_stock_adjustment_hithink" else "trade_date"
        schemas[table] = query(con, "main", f'DESCRIBE "{table}"')
        total = query(con, "main", f'SELECT COUNT(*) AS rows, COUNT(DISTINCT {date_col}) AS dates, MIN({date_col}) AS first_day, MAX({date_col}) AS last_day FROM "{table}"')[0]
        for f in fields:
            total[f + "__nonnull_rows"] = query(con, "main", f'SELECT COUNT("{f}") AS n FROM "{table}"')[0]["n"]
        scope = query(con, "main", f'SELECT COUNT(*) AS rows, COUNT(DISTINCT s.{date_col}) AS dates FROM "{table}" s JOIN fact_market_daily c ON s.{date_col}=c.trade_date')[0]
        non_null_days = {}
        for f in fields:
            non_null_days[f] = query(con, "main", f'SELECT COUNT(DISTINCT s.{date_col}) AS n FROM "{table}" s JOIN fact_market_daily c ON s.{date_col}=c.trade_date WHERE s."{f}" IS NOT NULL')[0]["n"]
        coverage.append({"table": table, "date_column": date_col, "whole_table": total,
                         "on_market_calendar": scope, "days_with_non_null_field_on_calendar": non_null_days,
                         "calendar_denominator": days, "limit": "One non-null row makes a day present; not full stock-universe coverage."})
        schema_names = {r["column_name"] for r in schemas[table]}
        cols = [date_col] + [x for x in ("stock_ts_code", "sector_ts_code") if x in schema_names] + fields
        raw_samples[table] = query(con, "main", 'SELECT ' + ', '.join('"' + x + '"' for x in cols) + f' FROM "{table}" WHERE {date_col} <= ? ORDER BY ' + date_col + ' DESC, ' + ', '.join(cols[1:]) + ' LIMIT 5', [last])
    write_json("source_coverage.json", {"kind": "PERSISTED_DB_READ", "calendar": {"days": days, "first_day": first, "last_day": last}, "tables": coverage})
    write_json("source_schemas.json", schemas)
    write_json("source_samples.json", {"kind": "PERSISTED_SOURCE_ROWS", "selection": "Latest five rows at or before market calendar end; deterministic field sort, not representative of the full market.", "tables": raw_samples})

    input_groups = {}
    for table, group in (("fact_auction_hithink", "kind"), ("fact_theme_limit_stock_daily", "limit_status"), ("fact_dragon_tiger_hithink", "range_days")):
        input_groups[table] = query(con, "main", f'SELECT "{group}", COUNT(*) AS rows, COUNT(DISTINCT trade_date) AS days, MIN(trade_date) AS first_day, MAX(trade_date) AS last_day FROM "{table}" GROUP BY "{group}" ORDER BY "{group}"')
    write_json("input_group_audit.json", {"kind": "PERSISTED_DB_READ", "groups": input_groups,
        "limits": "Auction benchmark rows are not snapshot rows; a null limit_status is not a confirmed limit-up. Dragon range_days mixes reporting intervals; aggregation does not filter it."})

    sources = view.attach_teaching_sources(con)  # TEMP views only; read_only=True remains in force.
    capital_sql = (ROOT / "code" / "capital.sql").read_text()
    capital = query(con, "main", capital_sql)
    capital_fields = [x for x in capital[0] if x != "trade_date"]
    capital_coverage = series_coverage(capital, capital_fields)
    complete = [r for r in capital if all(r.get(f) is not None for f in capital_fields)]
    write_json("capital_recomputed.json", {"kind": "READ_ONLY_RECOMPUTED_NOT_PERSISTED_LABELS", "sources": sources,
        "calendar_days": days, "field_coverage": capital_coverage,
        "samples_latest": capital[-5:], "samples_latest_all_fields_non_null": complete[-3:],
        "limit": "Non-null coverage is not correctness, unit validation or founder approval. SQL is reproduced unchanged."})

    logical = {}
    for name in (view.DRAGON_VIEW, view.AUCTION_ZT_VIEW):
        logical[name] = query(con, "main", f'SELECT * FROM {name} WHERE trade_date <= ? ORDER BY trade_date DESC, stock_ts_code LIMIT 5', [last])
    auction_duplicates = query(con, "main", f'SELECT COUNT(*) AS duplicated_stock_days, COALESCE(SUM(n-1),0) AS excess_rows FROM (SELECT trade_date, stock_ts_code, COUNT(*) AS n FROM {view.AUCTION_ZT_VIEW} GROUP BY ALL HAVING COUNT(*)>1)')
    write_json("adapted_source_samples.json", {"kind": "TEMP_VIEW_READ", "samples": logical, "auction_duplicate_audit": auction_duplicates})

    params = json.loads((ROOT / "code" / "selected_params.json").read_text())
    srows = structure.structure_daily(market, **structure.structure_params(params))
    sr = [{"trade_date": r["trade_date"], **s} for r, s in zip(market, srows)]
    events = [r for r in sr if any(r.get(f) is True for f in ("macd_bottom_div_observe", "macd_bottom_div_confirm", "macd_bottom_div_failed", "macd_top_div", "chan_third_buy", "chan_third_sell"))]
    picked = {str(r["trade_date"]): r for r in sr[-5:] + events[-10:]}
    input_by_date = {str(r["trade_date"]): r for r in market}
    write_json("structure_recomputed.json", {"kind": "READ_ONLY_RECOMPUTED_NOT_PERSISTED_LABELS", "scope": "Shanghai index daily only, full market calendar", "parameters": params["structure"],
        "field_coverage": series_coverage(sr, structure.STRUCTURE_FIELDS),
        "samples": [{"inputs": input_by_date[d], "outputs": picked[d]} for d in sorted(picked)],
        "valid_ohlc_days": sum(all(r.get(f) is not None for f in ("sh_index_high", "sh_index_low", "sh_index_close")) for r in market),
        "limit": "Boolean false can exist on input-gap days in this implementation; non-null event fields do not prove observability. Samples are ex-post computations, not historical point-in-time labels."})
    # A narrow causality check, not a full algorithm audit: full-series output for day t
    # versus the last output from prefix ending at t. Never alters production or code.
    mismatches, counts = [], Counter()
    for i, expected in enumerate(srows):
        prefix = structure.structure_daily(market[:i+1], **structure.structure_params(params))[-1]
        diff = {k: {"full_series": expected[k], "prefix_ending_on_day": prefix[k]} for k in structure.STRUCTURE_FIELDS if expected[k] != prefix[k]}
        if diff:
            counts.update(diff.keys())
            if len(mismatches) < 12:
                mismatches.append({"trade_date": market[i]["trade_date"], "differences": diff})
    write_json("structure_prefix_check.json", {"kind": "READ_ONLY_RECOMPUTATION_CHECK", "comparison": "For each calendar day, full-series output versus prefix output for that same day; no code changes.", "days_checked": len(market), "mismatch_counts_by_field": dict(counts), "first_mismatch_examples": mismatches,
        "limit": "A mismatch disproves same-day prefix invariance for this input. A match alone is not a general proof of no future dependence."})

    # Execute the repository's unmodified query for a bounded leaderboard window.
    range_mod = load("range_query")
    range_sql = range_mod._range_leader_sql([20], 30)
    (DATA / "range_query_20d.sql").write_text(range_sql + "\n")
    ranked = query(con, "main", 'SELECT * FROM (' + range_sql + ') q WHERE trade_date = ? ORDER BY rank', [last])
    write_json("range_sample_20d.json", {"kind": "READ_ONLY_RECOMPUTED_NOT_PERSISTED_LABELS", "trade_date": last,
        "window_days": 20, "rows": ranked[:10], "available_top30_rows": len(ranked),
        "actual_formula": "(close / close_20_trading_rows_ago - 1) * 100, requiring calendar index gap = 20",
        "limit": "Current source view exposes raw close; adjustment events alter pct_chg but not close. This is a sample of the implementation, not an endorsed wave-gain definition. Latest industry mapping is ex-post."})

    con.execute("ROLLBACK")
    con.close()
    after = [fingerprint(f) for f in (args.main_db, args.labels_db)]
    write_json("query_log.json", LOG)
    write_json("run_receipt.json", {"started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(),
        "duckdb_version": duckdb.__version__, "python_version": sys.version.split()[0],
        "connections": "duckdb.connect(..., read_only=True); independent read transactions; TEMP views only; ROLLBACK then close",
        "writes": "Files under this package/data only; no database writes, profile edits, network or uploads.",
        "database_before": before, "database_after": after, "database_stat_unchanged": before == after,
        "limitations": "Separate source/sidecar snapshots; file stats are not full content hashes. No alternate labels DB exhaustively searched. No full framework build or history-return validation."})
    print(json.dumps({"calendar_days": days, "capital_fields": len(capital_fields), "structure_fields": len(structure.STRUCTURE_FIELDS), "prefix_mismatch_fields": dict(counts), "database_stat_unchanged": before == after}, ensure_ascii=False))


if __name__ == "__main__":
    main()
