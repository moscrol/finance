"""Read-only physical-catalog audit complementary to audit_dataset_registration.

The existing gate inventories schema.sql. This command also inspects objects
actually present in DuckDB and profiles the latest slice's exposed fields.
It does NOT register datasets, repair data, infer that NULL means zero, call
models, or claim every dedicated Agent route has been exercised.

Usage: .venv-workbench/bin/python scripts/audit_agent_data_consumption.py
       --db db/market_feature_store.duckdb --output .tmp/consumption.json
Exit 1 means observable catalog/field gaps, not that every gap is a defect.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any


def _quote(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def audit_consumption(
    db_path: Path,
    datasets: dict[str, dict[str, Any]],
    exemptions: dict[str, str],
    schema_objects: set[str],
    intentional_empty: set[str] | None = None,
) -> dict[str, Any]:
    """Profile real relations, using the registered semantic time column first."""
    if not db_path.is_file():
        raise FileNotFoundError("Audit requires an existing database; never creates one")
    import duckdb

    by_table: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for key, spec in datasets.items():
        by_table.setdefault(spec["table"], []).append((key, spec))
    result: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "scope": "physical catalog and registered fields, not full Agent route coverage",
        "relations": [],
    }
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        con.execute("SET threads=2")
        con.execute("SET memory_limit='512MB'")
        tables = con.execute(
            "SELECT table_schema,table_name,table_type FROM information_schema.tables "
            "WHERE table_schema NOT IN ('information_schema','pg_catalog') "
            "ORDER BY table_schema,table_name"
        ).fetchall()
        for schema, name, kind in tables:
            columns = con.execute(
                "SELECT column_name,data_type FROM information_schema.columns "
                "WHERE table_schema=? AND table_name=? ORDER BY ordinal_position",
                [schema, name],
            ).fetchall()
            column_types = dict(columns)
            table = f"{_quote(schema)}.{_quote(name)}"
            specs = by_table.get(name, [])
            audited_fact = name.startswith(("fact_", "feature_"))
            disposition = (
                "semantic_dataset" if specs else "explicit_exemption" if name in exemptions
                else "unaccounted_fact" if audited_fact else "infrastructure_or_dimension"
            )
            row: dict[str, Any] = {
                "schema": schema, "name": name, "kind": kind,
                "schema_declared": name in schema_objects,
                "disposition": disposition,
                "datasets": [key for key, _ in specs],
                "exemption": exemptions.get(name),
                "intentional_empty": name in (intentional_empty or set()),
                "columns": [{"name": n, "type": t} for n, t in columns],
            }
            try:
                row["rows"] = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                semantic_dates = [s.get("time_column") for _, s in specs if s.get("time_column") in column_types]
                date_columns = [n for n, t in columns if t == "DATE" or t.startswith("TIMESTAMP")]
                date_column = semantic_dates[0] if semantic_dates else next(
                    (n for n in ("trade_date", "source_date", "effective_date", "as_of_date", "date", "published_at", "recorded_at") if n in date_columns),
                    date_columns[0] if date_columns else None,
                )
                row["date_column"] = date_column
                row["time_basis"] = "semantic_registry" if semantic_dates else "physical_column_only_not_freshness_verdict"
                where, args = "", []
                if date_column and row["rows"]:
                    lo, hi = con.execute(f"SELECT min({_quote(date_column)}),max({_quote(date_column)}) FROM {table}").fetchone()
                    row.update(first_date=str(lo) if lo is not None else None, last_date=str(hi) if hi is not None else None)
                    if hi is not None:
                        where, args = f" WHERE {_quote(date_column)} = ?", [hi]
                stats = con.execute(
                    "SELECT count(*)," + ",".join(f"count({_quote(n)})" for n, _ in columns) + f" FROM {table}" + where,
                    args,
                ).fetchone()
                row["profile_rows"] = stats[0]
                row["non_null"] = {n: stats[i + 1] for i, (n, _) in enumerate(columns)}
                exposed = {col for _, spec in specs for col in spec.get("fields", {}).values()}
                metric_columns = {col for _, spec in specs for col in spec.get("metrics", {}).values()}
                row["missing_registered_columns"] = sorted(exposed - set(column_types))
                row["all_null_exposed_metrics"] = sorted(
                    col for col in metric_columns if stats[0] and row["non_null"].get(col) == 0
                )
                row["metric_surface_empty"] = bool(metric_columns and stats[0] and metric_columns <= set(row["all_null_exposed_metrics"]))
            except Exception as exc:
                row["error"] = f"{type(exc).__name__}: {exc}"
            result["relations"].append(row)
    finally:
        con.close()
    rows = result["relations"]
    present = {r["name"] for r in rows}
    result["unaccounted_facts"] = [r["name"] for r in rows if r["disposition"] == "unaccounted_fact"]
    result["registered_missing_relations"] = sorted(set(by_table) - present)
    result["summary"] = {
        "relations": len(rows),
        "fact_feature_relations": sum(r["name"].startswith(("fact_", "feature_")) for r in rows),
        "semantic_relations": sum(r["disposition"] == "semantic_dataset" for r in rows),
        "exempt_relations": sum(r["disposition"] == "explicit_exemption" for r in rows),
        "unaccounted_relations": len(result["unaccounted_facts"]),
        "nonempty_unaccounted_relations": sum(r["disposition"] == "unaccounted_fact" and r.get("rows", 0) > 0 for r in rows),
    }
    result["requires_attention"] = bool(
        result["unaccounted_facts"] or result["registered_missing_relations"]
        or any(r.get("error") or r.get("missing_registered_columns") or r.get("all_null_exposed_metrics") for r in rows)
    )
    result["null_semantics"] = "Counts only: NULL is not automatically zero or a defect; consult provider/enrichment contracts."
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    from intelligence.services import finance_query
    from market_feature_store.consumption_registry import schema_objects

    datasets = {
        key: {
            "table": spec.table,
            "time_column": spec.fields[spec.time_field].column if spec.time_field else None,
            "fields": {k: f.column for k, f in spec.fields.items()},
            "metrics": {k: f.column for k, f in spec.metrics.items()},
        }
        for key, spec in finance_query._DATASETS.items()
    }
    result = audit_consumption(
        args.db, datasets, finance_query._UNREGISTERED_TABLES,
        schema_objects(), set(finance_query._EMPTY_BY_DESIGN),
    )
    text = json.dumps(result, ensure_ascii=False, indent=2, default=str)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(json.dumps({"summary": result["summary"], "requires_attention": result["requires_attention"]}, ensure_ascii=False))
    else:
        print(text)
    return 1 if result["requires_attention"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
