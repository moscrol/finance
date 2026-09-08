"""锚点标签 ``history_event_anchors``：日历行 → 每 (事件类, 反应日) 一条 market 锚点，或每个映射成功的板块一条 sector 锚点。

列与 ``history_labels`` 相同，label = ``ev.<event_class>``，``value_text`` 是 JSON（事件日 / 来源等级 / 指标 / 所属期 /
日程公布日）。板块代码映射不上 → ``history_event_gaps(anchor, unmapped_sector)``，不猜。
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

import duckdb

from market_feature_store.db import DB_PATH as CANONICAL_DB_PATH

from intelligence.services.methodology_backtest.store import (
    SOURCE_ALIAS,
    BuildReport,
    attach_source,
    default_labels_db_path,
    detach_source,
    naive_utc,
    open_labels_db,
    read_meta,
    utc_now,
    write_meta,
)

from .params import EventParams, load_params
from .store import ensure_event_schema

GAP_KIND_ANCHOR = "anchor"
GRADE_RANK = {"official": 0, "both": 1, "conflict": 2, "rule_derived": 3, "editorial": 4, "narrative": 5}


def anchor_label(event_class: str) -> str:
    return f"ev.{event_class}"


def _load_sector_codes(con: duckdb.DuckDBPyConnection) -> set[str]:
    rows = con.execute(f"SELECT DISTINCT sector_ts_code FROM {SOURCE_ALIAS}.fact_sector_daily WHERE sector_ts_code IS NOT NULL").fetchall()
    return {str(r[0]) for r in rows}


def build_anchors(
    source_db: str | Path | None,
    labels_db: str | Path | None,
    *,
    params: EventParams | None = None,
    now: datetime | None = None,
) -> BuildReport:
    params = params or load_params()
    source = Path(source_db).expanduser() if source_db else CANONICAL_DB_PATH
    labels_path = Path(labels_db).expanduser() if labels_db else default_labels_db_path(source)
    computed_at = naive_utc(now or utc_now())

    con = open_labels_db(labels_path, read_only=False)
    try:
        ensure_event_schema(con)
        meta = read_meta(con)
        if "event_calendar" not in meta:
            raise RuntimeError("旁路库没有 event_calendar 构建记录，先跑 build-calendar")
        if meta["event_calendar"]["label_version"] != params.ev_version:
            raise RuntimeError(
                f"event_calendar 版本 {meta['event_calendar']['label_version']} ≠ 当前参数 {params.ev_version}，先重跑 build-calendar"
            )
        source_path = attach_source(con, source)
        try:
            sector_codes = _load_sector_codes(con)
            rows = con.execute(
                """
                SELECT event_class, indicator, event_date, reaction_day, scheduled, source_grade,
                       schedule_published_at, period, sectors_json, reaction_day_confidence
                FROM history_event_calendar
                WHERE reaction_day IS NOT NULL AND source_grade <> 'editorial_ambiguous'
                ORDER BY reaction_day, event_class, indicator
                """
            ).fetchall()
            grouped: dict[tuple[str, date], dict[str, Any]] = {}
            for cls, ind, ed, rd, sched, grade, pub, period, sectors_json, conf in rows:
                g = grouped.setdefault(
                    (cls, rd),
                    {
                        "event_class": cls,
                        "reaction_day": rd,
                        "event_dates": set(),
                        "indicators": [],
                        "periods": [],
                        "grades": [],
                        "published": [],
                        "scheduled": bool(sched),
                        "sectors": [],
                        "confidence": conf,
                    },
                )
                g["event_dates"].add(ed)
                if ind and ind not in g["indicators"]:
                    g["indicators"].append(ind)
                if period and period not in g["periods"]:
                    g["periods"].append(period)
                g["grades"].append(grade)
                g["published"].append(pub)
                if sectors_json:
                    try:
                        for item in json.loads(sectors_json):
                            if isinstance(item, dict) and item.get("ts_code") and item["ts_code"] not in [s["ts_code"] for s in g["sectors"]]:
                                g["sectors"].append({"ts_code": item["ts_code"], "name": item.get("name")})
                    except (TypeError, ValueError):
                        pass

            con.execute("DELETE FROM history_event_anchors")
            con.execute("DELETE FROM history_event_gaps WHERE gap_kind = ?", [GAP_KIND_ANCHOR])
            anchor_rows: list[list[Any]] = []
            gap_rows: list[list[Any]] = []
            n_market = n_sector = 0
            for (cls, rd), g in grouped.items():
                spec = params.classes[cls]
                grade = min(g["grades"], key=lambda x: GRADE_RANK.get(x, 9))
                published = None if any(p is None for p in g["published"]) else max(g["published"])
                payload = {
                    "event_date": min(g["event_dates"]).isoformat(),
                    "source_grade": grade,
                    "scheduled": g["scheduled"],
                    "indicators": g["indicators"],
                    "periods": g["periods"],
                    "schedule_published_at": published.isoformat() if published else None,
                    "reaction_day_confidence": g["confidence"],
                }
                text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
                if spec.scope == "market":
                    anchor_rows.append(["market", "market", rd, anchor_label(cls), 1.0, text, params.ev_version, naive_utc(computed_at)])
                    n_market += 1
                    continue
                for s in g["sectors"]:
                    code = str(s["ts_code"])
                    if code not in sector_codes:
                        gap_rows.append(
                            [GAP_KIND_ANCHOR, f"{cls}:{rd.isoformat()}:{code}", "unmapped_sector", s.get("name"), params.ev_version, naive_utc(computed_at)]
                        )
                        continue
                    anchor_rows.append(["sector", code, rd, anchor_label(cls), 1.0, text, params.ev_version, naive_utc(computed_at)])
                    n_sector += 1
            if anchor_rows:
                con.executemany(
                    "INSERT INTO history_event_anchors (entity_type, entity_id, trade_date, label, value_num, value_text, label_version, computed_at) VALUES (?,?,?,?,?,?,?,?)",
                    anchor_rows,
                )
            if gap_rows:
                # 同一板块代码在多个锚点日都映射不上会重复，主键 (kind, key, reason) 已含日期，直接插
                con.executemany(
                    "INSERT OR IGNORE INTO history_event_gaps (gap_kind, gap_key, reason, detail, ev_version, computed_at) VALUES (?,?,?,?,?,?)",
                    gap_rows,
                )
            by_label = dict(
                con.execute("SELECT label, COUNT(*) FROM history_event_anchors GROUP BY 1 ORDER BY 1").fetchall()
            )
            source_max = con.execute(f"SELECT MAX(trade_date) FROM {SOURCE_ALIAS}.fact_market_daily").fetchone()[0]
            write_meta(
                con,
                build_kind="event_anchors",
                label_version=params.ev_version,
                source_db=source_path,
                source_max_trade_date=source_max,
                source_row_counts={
                    "calendar_rows_with_reaction_day": len(rows),
                    "anchor_groups": len(grouped),
                    "market_anchors": n_market,
                    "sector_anchors": n_sector,
                    "unmapped_sector_rows": len(gap_rows),
                    "sector_codes_in_source": len(sector_codes),
                },
                row_count=len(anchor_rows),
                horizons=None,
                computed_at=computed_at,
            )
            cal = con.execute("SELECT MIN(trade_date), MAX(trade_date), COUNT(*) FROM history_calendar").fetchone()
        finally:
            detach_source(con)
    finally:
        con.close()
    return BuildReport(
        build_kind="event_anchors",
        labels_db=str(labels_path),
        source_db=str(source_path),
        label_version=params.ev_version,
        source_max_trade_date=str(source_max) if source_max is not None else None,
        calendar_start=str(cal[0]) if cal and cal[0] else None,
        calendar_end=str(cal[1]) if cal and cal[1] else None,
        calendar_days=int(cal[2]) if cal else 0,
        row_count=len(anchor_rows),
        computed_at=computed_at.isoformat(timespec="seconds") + "Z",
        rows_by_label={str(k): int(v) for k, v in by_label.items()},
        extras={"market_anchors": n_market, "sector_anchors": n_sector, "unmapped_sector_rows": len(gap_rows)},
    )


__all__ = ["anchor_label", "build_anchors", "GAP_KIND_ANCHOR"]
