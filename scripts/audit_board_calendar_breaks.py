#!/usr/bin/env python3
"""Read-only sampling audit of the board-calendar 断板 / 待核 classification.

Purpose: before trusting the calendar on real data, put every confirmed break
and every unresolved candidate next to the raw rows that produced the verdict,
so a human can spot-check ``closed_at_limit`` (list looks incomplete) and
``source_mismatch`` (list source switched between two days).

This is a diagnostic, NOT a writer and NOT a release gate.  It opens the
database read-only, reuses ``build_board_calendar`` for the verdicts (no second
implementation of the rules) and only adds raw evidence columns.  It never
fills gaps: a missing quote row stays ``null``.

Usage::

    python scripts/audit_board_calendar_breaks.py --db PATH \
        --start 2026-07-01 --end 2026-09-30 [--json out.json] [--md out.md]
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
import json
from pathlib import Path
import sys
from typing import Any

import duckdb

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from intelligence.services.board_calendar import (  # noqa: E402
    BOARD_TABLE,
    QUOTE_TABLE,
    UNRESOLVED_REASONS,
    _UP_PRICE_SQL,
    build_board_calendar,
)
from market_feature_store.trading_days import previous_scheduled_trading_day  # noqa: E402

#: A traded break whose close is within this many yuan of the limit price is
#: flagged for review: rounding of the limit price may have decided the verdict.
NEAR_LIMIT_YUAN = 0.011


def _table_exists(con: duckdb.DuckDBPyConnection, table: str) -> bool:
    row = con.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?", [table]
    ).fetchone()
    return bool(row and row[0])


def _col(con: duckdb.DuckDBPyConnection, table: str, column: str) -> str:
    """Select expression for an optional column: absent columns read as NULL, never 0."""
    row = con.execute(
        "SELECT COUNT(*) FROM information_schema.columns WHERE table_name = ? AND column_name = ?",
        [table, column],
    ).fetchone()
    return column if row and row[0] else "NULL"


def _quote(con: duckdb.DuckDBPyConnection, day: date, code: str) -> dict[str, Any] | None:
    if not _table_exists(con, QUOTE_TABLE):
        return None
    row = con.execute(
        f"""
        SELECT stock_name, close, pre_close, pct_chg, amount, {_col(con, QUOTE_TABLE, "source")},
               {_UP_PRICE_SQL} AS up_px
        FROM {QUOTE_TABLE} WHERE trade_date = ? AND stock_ts_code = ?
        """,
        [day, code],
    ).fetchone()
    if row is None:
        return None
    keys = ("stock_name", "close", "pre_close", "pct_chg", "amount", "source", "up_px")
    return dict(zip(keys, row))


def _list_row(con: duckdb.DuckDBPyConnection, day: date | None, code: str) -> dict[str, Any] | None:
    if day is None:
        return None
    row = con.execute(
        f"SELECT boards, {_col(con, BOARD_TABLE, 'source')}, {_col(con, BOARD_TABLE, 'pct_chg')} FROM {BOARD_TABLE} WHERE trade_date = ? AND stock_ts_code = ?",
        [day, code],
    ).fetchone()
    return None if row is None else {"boards": row[0], "source": row[1], "pct_chg": row[2]}


def _day_sources(con: duckdb.DuckDBPyConnection, day: date | None) -> list[str | None]:
    if day is None:
        return []
    rows = con.execute(
        f"SELECT {_col(con, BOARD_TABLE, 'source')}, COUNT(*) FROM {BOARD_TABLE} WHERE trade_date = ? GROUP BY 1 ORDER BY 1 NULLS FIRST",
        [day],
    ).fetchall()
    return [f"{src}×{n}" for src, n in rows]


def _flags(kind: str, item: dict[str, Any], quote: dict[str, Any] | None) -> list[str]:
    flags: list[str] = []
    if quote is None:
        return flags
    close, up_px = quote.get("close"), quote.get("up_px")
    if kind == "break" and close is not None and up_px is not None and up_px - close <= NEAR_LIMIT_YUAN:
        flags.append("near_limit_price")  # 收盘离涨停价不到 1 分：涨停价取整可能决定了判定
    if kind == "break" and quote.get("pct_chg") is not None and quote["pct_chg"] >= 9.5:
        flags.append("high_pct_but_not_sealed")
    if item.get("reason") == "closed_at_limit":
        flags.append("verify_list_completeness")  # 行情在涨停价但名单缺席：核对名单源当日是否漏行
    return flags


def audit(db: Path, start: date, end: date, high_board_min: int | None = None) -> dict[str, Any]:
    payload = build_board_calendar(
        db, start_date=start, end_date=end, high_board_min=high_board_min
    )
    if payload.get("status") not in {"ok", "partial"}:
        return {"status": payload.get("status"), "message": payload.get("message"), "items": []}
    items: list[dict[str, Any]] = []
    with duckdb.connect(str(db), read_only=True) as con:
        for kind, rows in (("break", payload.get("high_board_breaks") or []),
                           ("unresolved", payload.get("high_board_unresolved") or [])):
            for item in rows:
                day = date.fromisoformat(item["date"])
                previous = previous_scheduled_trading_day(day)
                code = item["stock_ts_code"]
                quote = _quote(con, day, code)
                items.append({
                    "kind": kind,
                    "date": item["date"],
                    "previous": previous.isoformat() if previous else None,
                    "stock_ts_code": code,
                    "stock_name": item.get("stock_name"),
                    "height_at_break": item.get("height_at_break"),
                    "verification": item.get("verification"),
                    "reason": item.get("reason"),
                    "reason_text": UNRESOLVED_REASONS.get(item.get("reason") or ""),
                    "quote": quote,
                    "list_previous": _list_row(con, previous, code),
                    "list_day": _list_row(con, day, code),
                    "sources_previous": _day_sources(con, previous),
                    "sources_day": _day_sources(con, day),
                    "flags": _flags(kind, item, quote),
                })
    counts = Counter(
        item["verification"] if item["kind"] == "break" else item["reason"] for item in items
    )
    return {
        "status": payload.get("status"),
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "high_board_min": payload.get("high_board_min"),
        "counts": dict(sorted(counts.items())),
        "flagged": sum(1 for item in items if item["flags"]),
        "items": items,
        "boundary": "只读诊断；判定来自 build_board_calendar，本脚本只并列原始行，不补档、不改判。",
    }


def _fmt(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def to_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# 连板日历断板抽样核对 {report.get('start_date')} → {report.get('end_date')}",
        "",
        f"状态：{report.get('status')} · 高标阈值 ≥{report.get('high_board_min')} 板 · 需人工看 {report.get('flagged', 0)} 条",
        "",
        "| 判定 | 数量 |",
        "| --- | ---: |",
    ]
    lines += [f"| {k} | {v} |" for k, v in (report.get("counts") or {}).items()]
    lines += [
        "",
        "> “—”表示原始行不存在或字段为空，不是零。" + str(report.get("boundary", "")),
        "",
        "| 日期 | 代码 | 名称 | 断于 | 判定 | 收盘 | 涨停价 | 涨跌% | 成交额 | 前日名单源 | 当日名单源 | 标记 |",
        "| --- | --- | --- | ---: | --- | ---: | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for item in report.get("items", []):
        quote = item.get("quote") or {}
        verdict = item["verification"] if item["kind"] == "break" else f"待核:{item['reason']}"
        lines.append(
            "| " + " | ".join([
                item["date"], item["stock_ts_code"], _fmt(item.get("stock_name")),
                _fmt(item.get("height_at_break")), verdict,
                _fmt(quote.get("close")), _fmt(quote.get("up_px")), _fmt(quote.get("pct_chg")),
                _fmt(quote.get("amount")),
                ", ".join(item["sources_previous"]) or "—", ", ".join(item["sources_day"]) or "—",
                ", ".join(item["flags"]) or "",
            ]) + " |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--start", required=True, type=date.fromisoformat)
    parser.add_argument("--end", required=True, type=date.fromisoformat)
    parser.add_argument("--high-board-min", type=int, default=None)
    parser.add_argument("--json", type=Path, default=None)
    parser.add_argument("--md", type=Path, default=None)
    args = parser.parse_args(argv)
    report = audit(args.db, args.start, args.end, args.high_board_min)
    if args.json:
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    markdown = to_markdown(report)
    if args.md:
        args.md.write_text(markdown, encoding="utf-8")
    else:
        sys.stdout.write(markdown)
    return 0 if report.get("status") in {"ok", "partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
