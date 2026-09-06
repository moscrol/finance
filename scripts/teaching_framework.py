#!/usr/bin/env python3
"""Build and inspect the teaching-framework slice 1 sidecar objects."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from intelligence.services.methodology_backtest.labels import LABEL_VERSION  # noqa: E402
from intelligence.services.methodology_backtest.store import (  # noqa: E402
    default_labels_db_path,
    open_labels_db,
)
from intelligence.services.teaching_framework.index_stage import (  # noqa: E402
    build_index_stage,
    to_label_rows,
)
from intelligence.services.teaching_framework.leader_succession import (  # noqa: E402
    build_succession,
)
from intelligence.services.teaching_framework.params import (  # noqa: E402
    framework_version,
    load_params,
    parameter_hash,
)
from intelligence.services.teaching_framework.readouts import (  # noqa: E402
    eligible_baseline,
    handoff_readout,
    receipt_summary,
)
from intelligence.services.teaching_framework.receipts import (  # noqa: E402
    canonical_rows_hash,
    make_receipt,
    write_receipt,
)


def _now(value: str | None) -> datetime:
    if value:
        text = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc).replace(microsecond=0)


def _rows(con: duckdb.DuckDBPyConnection, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
    cur = con.execute(sql, params or [])
    names = [str(item[0]) for item in cur.description]
    return [dict(zip(names, row, strict=True)) for row in cur.fetchall()]


def _market_inputs(source: duckdb.DuckDBPyConnection) -> tuple[list[dict], list[str], list[dict], list[dict], list[dict], list[dict]]:
    market = _rows(source, "SELECT * FROM fact_market_daily ORDER BY trade_date")
    dates = [str(row["trade_date"])[:10] for row in market]
    vendor = _rows(source, "SELECT trade_date, sector_ts_code, amount FROM fact_mainline_sector_daily ORDER BY trade_date, sector_ts_code")
    stocks = _rows(
        source,
        """SELECT trade_date, stock_ts_code, stock_name, limit_times, open_times,
                  first_limit_time, up_stat, circ_mv, amount
           FROM fact_theme_limit_stock_daily
           WHERE limit_status = 'U'
           ORDER BY trade_date, stock_ts_code""",
    )
    amounts = _rows(source, "SELECT trade_date, stock_ts_code, amount FROM fact_stock_daily ORDER BY trade_date, stock_ts_code")
    return market, dates, vendor, stocks, amounts, _rows(source, "SELECT trade_date, limit_up FROM fact_market_daily")


def _source_counts(source: duckdb.DuckDBPyConnection) -> dict[str, int]:
    out: dict[str, int] = {}
    for table in ("fact_market_daily", "fact_mainline_sector_daily", "fact_theme_limit_stock_daily", "fact_stock_daily"):
        out[table] = int(source.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    return out


def _insert_label_rows(side: duckdb.DuckDBPyConnection, rows: list[dict[str, Any]], build_time: datetime) -> int:
    side.executemany(
        """INSERT INTO history_teaching_labels
           (entity_type, entity_id, trade_date, label, value_num, value_text,
            label_version, framework_version, status, status_reason, computed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (
                row["entity_type"], row["entity_id"], row["trade_date"], row["label"],
                row["value_num"], row["value_text"], LABEL_VERSION, row["label_version"],
                "ok", None, build_time.replace(tzinfo=None),
            )
            for row in rows
        ],
    )
    return len(rows)


def cmd_build_labels(args: argparse.Namespace) -> int:
    params = load_params(args.params)
    fw = framework_version(params)
    build_time = _now(args.computed_at)
    source_path = Path(args.db_path).expanduser()
    labels_path = Path(args.labels_db).expanduser()
    source = duckdb.connect(str(source_path), read_only=True)
    try:
        market, dates, vendor, stocks, amounts, _ = _market_inputs(source)
        source_counts = _source_counts(source)
    finally:
        source.close()
    records = build_index_stage(
        market, calendar=dates, vendor_rows=vendor, stock_rows=stocks,
        amount_rows=amounts, params=params,
        supplier_normalizer=lambda value: str(value or "未知").removesuffix("阶段"),
    )
    required = ("sh_index_close", "sh_index_open", "sh_week_ma", "sh_deviation_pct", "total_amount", "amount_ma20", "top3_industry_ratio")
    market_by_date = {str(row["trade_date"])[:10]: row for row in market}
    usable, gaps = [], []
    for record in records:
        row = market_by_date[str(record["trade_date"])]
        missing = [name for name in required if row.get(name) is None]
        if missing:
            gaps.append((record["trade_date"], "market_input", json.dumps(missing), fw, "gap", "required_market_field_null"))
        else:
            usable.append(record)
    label_rows = to_label_rows(usable, framework_version=fw, computed_at=build_time)
    side = open_labels_db(labels_path, read_only=False)
    try:
        side.execute("DELETE FROM history_teaching_labels")
        side.execute("DELETE FROM history_teaching_gaps WHERE gap_kind = 'market_input'")
        _insert_label_rows(side, label_rows, build_time)
        if gaps:
            side.executemany(
                """INSERT INTO history_teaching_gaps
                   (trade_date, gap_kind, missing_cols, framework_version, status, status_reason, computed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [(*gap, build_time.replace(tzinfo=None)) for gap in gaps],
            )
        hash_rows = side.execute(
            """SELECT entity_type, entity_id, trade_date, label, value_num, value_text,
                      label_version, status, status_reason, computed_at
               FROM history_teaching_labels"""
        ).fetchall()
        canonical = canonical_rows_hash(
            hash_rows,
            columns=("entity_type", "entity_id", "trade_date", "label", "value_num", "value_text", "label_version", "status", "status_reason", "computed_at"),
            primary_key=("entity_type", "entity_id", "trade_date", "label"),
        )
        receipt = make_receipt(
            build_kind="teaching_labels", framework_version=fw, label_version=LABEL_VERSION,
            source_db=str(source_path), source_max_trade_date=max(dates) if dates else None,
            source_row_counts=source_counts, parameter_hash=parameter_hash(params),
            canonical_hash=canonical,
            coverage_summary={"market_days": len(dates), "usable_days": len(usable), "gap_days": len(gaps)},
            gap_summary={"market_input": len(gaps)}, computed_at=build_time,
        )
        write_receipt(side, receipt)
    finally:
        side.close()
    print(json.dumps({"build_kind": "teaching_labels", "framework_version": fw, "rows": len(label_rows), "gaps": len(gaps), "canonical_hash": canonical}, ensure_ascii=False, indent=2))
    return 0


def cmd_build_succession(args: argparse.Namespace) -> int:
    params = load_params(args.params)
    fw = framework_version(params)
    build_time = _now(args.computed_at)
    source_path = Path(args.db_path).expanduser()
    labels_path = Path(args.labels_db).expanduser()
    source = duckdb.connect(str(source_path), read_only=True)
    try:
        market, dates, _, stocks, _, market_limits = _market_inputs(source)
        source_counts = _source_counts(source)
    finally:
        source.close()
    limit_days = {str(row["trade_date"])[:10] for row in stocks}
    market_limit = {str(row["trade_date"])[:10]: row.get("limit_up") for row in market_limits}
    covered_dates = limit_days | {day for day, value in market_limit.items() if value == 0}
    context: dict[str, dict[str, Any]] = {}
    side = open_labels_db(labels_path, read_only=False)
    try:
        try:
            for day, label, value_num, value_text in side.execute(
                """SELECT trade_date, label, value_num, value_text
                   FROM history_teaching_labels
                   WHERE entity_type='market' AND entity_id='market'"""
            ).fetchall():
                d = str(day)
                value = value_text if value_text is not None else value_num
                context.setdefault(d, {})[label.removeprefix("tf.")] = value
        except duckdb.CatalogException:
            pass
    finally:
        side.close()
    result = build_succession(
        dates, stocks, covered_dates=covered_dates, params=params,
        knowledge_cutoff=max(dates) if dates else None, context_by_date=context,
        framework_version=fw,
    )
    baseline_rows = eligible_baseline(result, dates)
    readout = handoff_readout(result["nodes"], baseline=[row["handoff"] for row in baseline_rows], min_n=int(params["min_n"]))
    side = open_labels_db(labels_path, read_only=False)
    try:
        side.execute("DELETE FROM history_leader_succession")
        side.execute("DELETE FROM history_overtaken")
        for node in result["nodes"]:
            side.execute(
                """INSERT INTO history_leader_succession
                   (node_id, break_day, leader_i, leader_i_name, leader_i_peak_boards,
                    birth_day, leader_next, leader_next_name, birth_boards, candidates_json,
                    gap_days, path_json, shape_tags_json, handoff, context_break, context_birth, forward,
                    framework_version, status, status_reason, computed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    node.node_id, node.break_day, node.leader_i, node.leader_i_name,
                    node.leader_i_peak_boards, node.birth_day, node.leader_next,
                    node.leader_next_name, node.birth_boards, json.dumps(node.candidates, ensure_ascii=False),
                    node.gap_days, json.dumps(node.path, ensure_ascii=False), json.dumps(node.shape_tags, ensure_ascii=False),
                    node.handoff, json.dumps(node.context_break, ensure_ascii=False), json.dumps(node.context_birth, ensure_ascii=False),
                    json.dumps(node.forward, ensure_ascii=False),
                    fw, node.status, node.status_reason, build_time.replace(tzinfo=None),
                ],
            )
        for event in result["overtaken"]:
            side.execute(
                """INSERT INTO history_overtaken
                   (event_day, leader_i, leader_next, granularity, status, status_reason, computed_at)
                   VALUES (?, ?, ?, ?, 'ok', NULL, ?)""",
                [event["event_day"], event["previous_top"], event["overtaken_by"], event["event_granularity"], build_time.replace(tzinfo=None)],
            )
        hash_rows = side.execute("SELECT * FROM history_leader_succession").fetchall()
        columns = [str(item[0]) for item in side.execute("SELECT * FROM history_leader_succession LIMIT 0").description]
        canonical = canonical_rows_hash(hash_rows, columns=columns, primary_key=("break_day", "node_id"))
        statuses = {}
        for node in result["nodes"]:
            statuses[node.status] = statuses.get(node.status, 0) + 1
        receipt = make_receipt(
            build_kind="leader_succession", framework_version=fw, label_version=LABEL_VERSION,
            source_db=str(source_path), source_max_trade_date=max(dates) if dates else None,
            source_row_counts=source_counts, parameter_hash=parameter_hash(params), canonical_hash=canonical,
            coverage_summary={"calendar_days": len(dates), "limit_days": len(limit_days), "covered_days": len(covered_dates)},
            gap_summary=statuses, computed_at=build_time,
        )
        write_receipt(side, receipt)
    finally:
        side.close()
    print(json.dumps({
        "build_kind": "leader_succession", "framework_version": fw,
        "nodes": len(result["nodes"]), "overtaken": len(result["overtaken"]),
        "canonical_hash": canonical,
        "handoff_readout": readout.to_dict(),
        "baseline": receipt_summary(result["nodes"], [row["handoff"] for row in baseline_rows]),
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    side = open_labels_db(Path(args.labels_db).expanduser(), read_only=True)
    try:
        result = {
            "teaching_labels": side.execute("SELECT COUNT(*) FROM history_teaching_labels").fetchone()[0],
            "teaching_gaps": side.execute("SELECT COUNT(*) FROM history_teaching_gaps").fetchone()[0],
            "succession_nodes": side.execute("SELECT COUNT(*) FROM history_leader_succession").fetchone()[0],
            "succession_status": dict(side.execute("SELECT status, COUNT(*) FROM history_leader_succession GROUP BY status").fetchall()),
            "overtaken": side.execute("SELECT COUNT(*) FROM history_overtaken").fetchone()[0],
            "receipts": [dict(zip(("build_id", "build_kind", "framework_version", "status"), row, strict=True)) for row in side.execute("SELECT build_id, build_kind, framework_version, status FROM history_teaching_receipts ORDER BY computed_at").fetchall()],
        }
    finally:
        side.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Teaching framework slice 1")
    sub = ap.add_subparsers(dest="command", required=True)
    for name, func in (("build-labels", cmd_build_labels), ("build-succession", cmd_build_succession)):
        p = sub.add_parser(name)
        p.add_argument("--db-path", default="db/market_feature_store.duckdb")
        p.add_argument("--labels-db", default=None)
        p.add_argument("--params", default=None)
        p.add_argument("--computed-at", default=None)
        p.set_defaults(func=func)
    p = sub.add_parser("report")
    p.add_argument("--labels-db", default=None)
    p.set_defaults(func=cmd_report)
    return ap


def main(argv: list[str] | None = None) -> int:
    ap = parser()
    args = ap.parse_args(argv)
    if getattr(args, "labels_db", None) is None:
        args.labels_db = str(default_labels_db_path(getattr(args, "db_path", None)))
    try:
        return int(args.func(args) or 0)
    except (duckdb.Error, FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
