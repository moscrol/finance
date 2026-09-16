#!/usr/bin/env python3
"""Read-only sidecar drift audit; distinguish historical changes from appended days.

Usage: python scripts/audit_methodology_label_drift.py --before OLD --after NEW
Does not publish databases, rewrite receipts, or infer causes from matching totals.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb

CORE_TABLES = {"history_labels", "history_calendar", "history_data_gaps", "history_outcomes", "history_build_meta"}


def _ident(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def audit(before: Path, after: Path) -> dict:
    for path in (before, after):
        if not path.is_file():
            raise FileNotFoundError(path)
    with duckdb.connect(str(after), read_only=True) as con:
        quoted = str(before.resolve()).replace("'", "''")
        con.execute(f"ATTACH '{quoted}' AS old (READ_ONLY)")
        cutoff = con.execute("SELECT max(trade_date) FROM old.history_calendar").fetchone()[0]
        rows = con.execute("""
            SELECT coalesce(o.label, n.label) AS label,
                   count(o.label) AS old_rows, count(n.label) AS new_rows,
                   count(*) FILTER (WHERE o.label IS NOT NULL AND n.label IS NOT NULL) AS matched,
                   count(*) FILTER (WHERE o.label IS NOT NULL AND n.label IS NULL) AS removed,
                   count(*) FILTER (WHERE o.label IS NULL AND n.trade_date <= ?) AS added_historical,
                   count(*) FILTER (WHERE o.label IS NULL AND n.trade_date > ?) AS added_new_dates,
                   count(*) FILTER (WHERE o.label IS NOT NULL AND n.label IS NOT NULL AND
                       (o.value_num IS DISTINCT FROM n.value_num OR
                        o.value_text IS DISTINCT FROM n.value_text)) AS changed_values
            FROM old.history_labels o FULL OUTER JOIN history_labels n
            USING (entity_type, entity_id, trade_date, label)
            GROUP BY coalesce(o.label, n.label) ORDER BY label
        """, [cutoff, cutoff]).fetchall()
        keys = ("label", "old_rows", "new_rows", "matched", "removed", "added_historical", "added_new_dates", "changed_values")
        labels = [dict(zip(keys, row)) for row in rows]
        old_tables = {r[0] for r in con.execute("SELECT table_name FROM information_schema.tables WHERE table_catalog='old' AND table_type='BASE TABLE'").fetchall()}
        new_tables = {r[0] for r in con.execute("SELECT table_name FROM information_schema.tables WHERE table_catalog != 'old' AND table_type='BASE TABLE'").fetchall()}
        preserved = {}
        for table in sorted(old_tables - CORE_TABLES):
            if table not in new_tables:
                preserved[table] = {"missing": True}
                continue
            name = _ident(table)
            lost = con.execute(f"SELECT count(*) FROM (SELECT * FROM old.{name} EXCEPT ALL SELECT * FROM {name})").fetchone()[0]
            added = con.execute(f"SELECT count(*) FROM (SELECT * FROM {name} EXCEPT ALL SELECT * FROM old.{name})").fetchone()[0]
            preserved[table] = {"lost_rows": lost, "added_rows": added}
        preserved_ok = all(not row.get("missing") and row.get("lost_rows") == 0 and row.get("added_rows") == 0 for row in preserved.values())
        return {"before": str(before), "after": str(after), "old_calendar_end": str(cutoff),
                "labels": labels, "other_tables": preserved, "other_tables_preserved": preserved_ok,
                "note": "Counts exclude label_version/computed_at. Historical changes need source/code attribution; this audit does not infer causality."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", required=True, type=Path)
    parser.add_argument("--after", required=True, type=Path)
    args = parser.parse_args()
    report = audit(args.before, args.after)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["other_tables_preserved"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
