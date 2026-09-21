#!/usr/bin/env python3
"""Read-only briefing -> sidecar -> river acceptance, not a production readiness check.

Missing source rows fail; a briefing beyond the market calendar exits 2 (BLOCKED),
never PASS. Build the sidecar separately with teaching_framework.py build-labels.
The cutoff check covers teaching objects only, not historical market data fidelity.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import date
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from intelligence.services.river import slice_river  # noqa: E402
from intelligence.services.teaching_framework.narrative import (  # noqa: E402
    BRIEFING_EVENTS_RELPATH,
    BRIEFING_FIELDS,
    briefing_daily,
)
from intelligence.services.teaching_framework.river_objects import teaching_objects  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def verify(args: argparse.Namespace) -> dict:
    for path in (args.db_path, args.labels_db, args.kb_wiki / BRIEFING_EVENTS_RELPATH):
        require(path.is_file(), f"Missing input: {path}")
    with (args.kb_wiki / BRIEFING_EVENTS_RELPATH).open(encoding="utf-8") as stream:
        events = [json.loads(line) for line in stream if line.strip()]
    with duckdb.connect(str(args.db_path), read_only=True) as source:
        calendar = [r[0] for r in source.execute("SELECT trade_date FROM fact_market_daily ORDER BY trade_date").fetchall()]
    require(bool(calendar), "Empty market calendar")
    daily = briefing_daily(events, calendar)
    results = []
    with tempfile.TemporaryDirectory(prefix="briefing-verify-") as temp:
        for material_day in args.briefing_date:
            items = [r for r in events if r.get("briefing_date") == material_day]
            require(bool(items), f"No projection rows for {material_day}")
            availability = {date.fromisoformat(r["available_from"]) for r in items}
            require(len(availability) == 1, f"Mixed availability for {material_day}")
            available = next(iter(availability))
            landing = next((day for day in calendar if day >= available), None)
            result = {"briefing_date": material_day, "source_rows": len(items), "available_from": str(available)}
            if landing is None:
                results.append({**result, "status": "BLOCKED", "reason": "market_calendar_ends_before_availability"})
                continue
            day = str(landing)
            expected = daily[landing]
            with duckdb.connect(str(args.labels_db), read_only=True) as labels:
                rows = labels.execute(
                    "SELECT label, value_num FROM history_teaching_labels "
                    "WHERE trade_date = ? AND entity_type = 'market' AND entity_id = 'market' AND label LIKE 'tf.briefing_%'",
                    [landing],
                ).fetchall()
            values = {label.removeprefix("tf."): value for label, value in rows}
            require(len(rows) == len(values), f"Duplicate label versions on {day}")
            for field in BRIEFING_FIELDS:
                if field == "briefing_hit_rps5_pct":
                    continue  # This audit does not recompute the independent price-ranking comparison.
                require(field in values and values[field] == expected[field], f"Label mismatch: {day} {field}")
            briefs = [o for o in teaching_objects(args.labels_db, day) if o.object_type == "teaching_briefing"]
            require(len(briefs) == 1, f"Expected one briefing object on {day}")
            obj = briefs[0]
            for field, value in values.items():
                require((field not in obj.payload) if value is None else obj.payload.get(field) == value,
                        f"River payload mismatch: {day} {field}")
            require(bool(obj.recorded_at) and obj.recorded_at[:10] >= expected["recorded_at"][:10], "Backdated computed_at")
            common = {"db_path": args.db_path, "checkpoints_path": Path(temp) / "absent-checkpoints.jsonl"}
            plain = slice_river(day, args.entity, **common).to_dict()
            off = slice_river(day, args.entity, teaching_labels_db=None, **common).to_dict()
            require(plain == off, "Disabled sidecar changed river output")
            live = slice_river(day, args.entity, teaching_labels_db=args.labels_db, **common)
            visible = [o for o in live.objects if o.object_type == "teaching_briefing"]
            require(len(visible) == 1 and visible[0] == obj, f"Briefing missing from river slice for {args.entity} on {day}")
            strict = slice_river(day, args.entity, teaching_labels_db=args.labels_db, require_strict=True, **common)
            late = [o for o in live.objects if o.object_type.startswith("teaching_") and (not o.recorded_at or o.recorded_at[:10] > day)]
            require(not {o.ref for o in late} & {o.ref for o in strict.objects}, "Late teaching object leaked through cutoff")
            results.append({**result, "status": "PASS", "landing": day, "labels": values,
                            "source_recorded_at": expected["recorded_at"], "object_recorded_at": obj.recorded_at,
                            "river_ref": obj.ref, "river_pit_grade": live.pit_grade,
                            "late_teaching_objects_filtered": len(late), "disabled_sidecar_unchanged": True})
    return {"status": "BLOCKED" if any(r["status"] == "BLOCKED" for r in results) else "PASS",
            "scope": "explicit_inputs_only; live_market_read_only; not_production_readiness",
            "market_latest": str(calendar[-1]), "briefings": results}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", type=Path, required=True)
    parser.add_argument("--labels-db", type=Path, required=True)
    parser.add_argument("--kb-wiki", type=Path, required=True)
    parser.add_argument("--briefing-date", action="append", required=True)
    parser.add_argument("--entity", required=True)
    args = parser.parse_args()
    try:
        report = verify(args)
    except (ValueError, KeyError, TypeError, OSError, duckdb.Error) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
