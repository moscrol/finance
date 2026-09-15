#!/usr/bin/env python3
"""舆论生命周期阶段（工单 #36 / G-06）：单实体读数与区间覆盖率报告。

    # 一个板块某天的阶段读数（含 inputs / reasons）
    python3 scripts/opinion_stage.py readout --entity 半导体 --as-of 2026-09-05 [--cutoff 2026-09-05]

    # 区间覆盖率报告：多少 (板块, 日) 出阶段、多少 unverifiable、各段分布；回填批次日单列
    python3 scripts/opinion_stage.py report --start 2026-06-01 --end 2026-09-05 [--entities 半导体 军工电子] [--json]
    # 收据落 methodology/receipts/opinion_stage/<end>.json（--no-write 不落）

派生全部无状态：同一批研报事件 + 同一天 → 同一读数；``created_at`` 晚于 C 的研报那天看不见。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from intelligence.services import opinion_stage  # noqa: E402
from intelligence.services.river import DEFAULT_DB, _report_tags, load_reports_asof  # noqa: E402

RECEIPTS_DIR = REPO_ROOT / "methodology" / "receipts" / "opinion_stage"


def _connect(db_path: str | None):
    import duckdb

    db = Path(db_path or os.environ.get("MARKET_FEATURE_STORE_DB", DEFAULT_DB)).expanduser()
    if not db.exists():
        raise SystemExit(f"数据库不存在：{db}")
    return duckdb.connect(str(db), read_only=True)


def _sectors(con, entities: list[str] | None) -> list[tuple[str, str]]:
    rows = con.execute(
        "SELECT DISTINCT sector_ts_code, sector_name FROM fact_sector_daily "
        "WHERE sector_ts_code IS NOT NULL AND sector_name IS NOT NULL ORDER BY sector_name"
    ).fetchall()
    if entities:
        wanted = set(entities)
        rows = [r for r in rows if r[1] in wanted or r[0] in wanted]
    return [(str(c), str(n)) for c, n in rows]


def _trading_days(con, start: str, end: str) -> list[str]:
    rows = con.execute(
        "SELECT DISTINCT CAST(trade_date AS DATE) d FROM fact_market_daily "
        "WHERE CAST(trade_date AS DATE) BETWEEN CAST(? AS DATE) AND CAST(? AS DATE) ORDER BY d",
        [start, end],
    ).fetchall()
    return [str(r[0]) for r in rows]


def _hits_by_name(con, as_of: str) -> dict[str, list[dict]]:
    """一次取回截至 as_of 的全部研报，按 tag 名归组（与 river.coverage_hits 同口径：精确匹配）。"""
    pool = load_reports_asof(con, as_of)
    by_name: dict[str, list[dict]] = {}
    for r in pool:
        for tag in set(_report_tags(r["sector_tags"]) + _report_tags(r["concept_tags"])):
            by_name.setdefault(tag, []).append(r)
    return by_name


def cmd_readout(args: argparse.Namespace) -> int:
    con = _connect(args.db_path)
    try:
        hits = _hits_by_name(con, args.cutoff or args.as_of).get(args.entity, [])
    finally:
        con.close()
    r = opinion_stage.derive_stage(hits, args.as_of, knowledge_cutoff=args.cutoff)
    print(json.dumps(r.to_dict(), ensure_ascii=False, indent=2, default=str))
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    con = _connect(args.db_path)
    try:
        days = _trading_days(con, args.start, args.end)
        sectors = _sectors(con, args.entities)
        by_name = _hits_by_name(con, args.end)
    finally:
        con.close()
    if not days:
        raise SystemExit(f"{args.start}~{args.end} 没有交易日")

    dist: Counter[str] = Counter()
    dist_in_batch: Counter[str] = Counter()
    per_entity: dict[str, Counter[str]] = {}
    covered_entities = 0
    cells = 0
    batch_cells = 0
    for code, name in sectors:
        hits = by_name.get(name)
        if not hits:
            continue
        covered_entities += 1
        c = per_entity.setdefault(name, Counter())
        for day in days:
            r = opinion_stage.derive_stage(hits, day, knowledge_cutoff=day)
            cells += 1
            # 回填批次日 ±30 天内的斜率读数不可比，单列
            d = date.fromisoformat(day)
            in_batch = any(abs((d - date.fromisoformat(b)).days) <= opinion_stage.SLOPE_DAYS for b in r.inputs["backfill_batch_dates"])
            (dist_in_batch if in_batch else dist)[r.stage] += 1
            if in_batch:
                batch_cells += 1
            c[r.stage] += 1

    total = cells
    report = {
        "start": args.start,
        "end": args.end,
        "trading_days": len(days),
        "sectors_total": len(sectors),
        "sectors_with_any_coverage": covered_entities,
        "cells": total,
        "cells_near_backfill_batch": batch_cells,
        "distribution": dict(sorted(dist.items())),
        "distribution_near_backfill_batch": dict(sorted(dist_in_batch.items())),
        "unverifiable_share": round((dist[opinion_stage.UNVERIFIABLE] + dist_in_batch[opinion_stage.UNVERIFIABLE]) / total, 4) if total else None,
        "falsified_cells": dist[opinion_stage.STAGE_FALSIFIED] + dist_in_batch[opinion_stage.STAGE_FALSIFIED],
        "derivation_rule": opinion_stage.DERIVATION_RULE,
        "thresholds": opinion_stage.THRESHOLDS,
        "per_entity_top": {
            k: dict(v) for k, v in sorted(per_entity.items(), key=lambda kv: -sum(kv[1].values()))[:20]
        },
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    else:
        print(f"舆论生命周期覆盖率 {args.start} → {args.end}（{len(days)} 个交易日，{covered_entities}/{len(sectors)} 个板块名曾被研报 tag 命中）")
        print(f"  单元格 {total}，其中回填批次 ±{opinion_stage.SLOPE_DAYS} 天内 {batch_cells}（斜率不可比，单列）")
        print("  分布（批次外）：", dict(sorted(dist.items())))
        print("  分布（批次内）：", dict(sorted(dist_in_batch.items())))
        print(f"  unverifiable 占比 {report['unverifiable_share']}；证伪 {report['falsified_cells']}（河里尚无证伪事件对象，恒 0 是实话）")
    if not args.no_write:
        RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)
        out = RECEIPTS_DIR / f"{args.end}.json"
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print(f"收据：{out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    r = sub.add_parser("readout")
    r.add_argument("--entity", required=True)
    r.add_argument("--as-of", required=True)
    r.add_argument("--cutoff", default=None)
    r.add_argument("--db-path", default=None)
    r.set_defaults(func=cmd_readout)

    p = sub.add_parser("report")
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    p.add_argument("--entities", nargs="*", default=None)
    p.add_argument("--db-path", default=None)
    p.add_argument("--json", action="store_true")
    p.add_argument("--no-write", action="store_true")
    p.set_defaults(func=cmd_report)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
