#!/usr/bin/env python3
"""Descriptive independent arithmetic over saved history-query JSON originals.

Usage: python scripts/audit_historical_research_artifacts.py ARTIFACT_OR_RUN_DIR
       [ARTIFACT_OR_RUN_DIR ...] [--output receipt.json]

Only explicitly named files and history-query-*.json immediately inside named
run directories are read. No database, model, engine, or application imports.
Exit 0: supported checks completed (see explicit skips); 1: error/mismatch;
2: no supported calculation in the supplied artifacts. This is not certification.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any


AUDIT_VERSION = "history-artifact-arithmetic-v1"
SCHEMA_VERSION = "historical-research-v1"
FEATURE_VERSION = "history-features-v1"
# Deliberately independent, frozen v1 definitions; do not import the engine.
RED_RULE = "题材涨幅为正、边际量大于 10 且成交额大于 500 亿。"
DEFINITIONS = {
    "return_pct": (
        ["pct_chg"],
        "percent",
        "compound every daily percentage in the declared window",
    ),
    "amount_ratio": (
        ["amount"],
        "ratio",
        "last amount / first amount; require complete window and nonzero denominator",
    ),
    "market_relative_return_pct": (
        ["pct_chg", "market.sh_index_pct_chg"],
        "percentage_points",
        "entity compounded return minus index compounded return over identical days",
    ),
    "double_red_days": (["pct_chg", "amount", "diff_ratio"], "trading_days", RED_RULE),
    "max_double_red_streak": (
        ["pct_chg", "amount", "diff_ratio"],
        "trading_days",
        "maximum consecutive days satisfying " + RED_RULE,
    ),
}
CELLS = ("x_true_y_true", "x_true_y_false", "x_false_y_true", "x_false_y_false")


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()
    ).hexdigest()


def _finite(value: Any) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def _compound(values: list[float]) -> float:
    return (math.prod(1 + value / 100 for value in values) - 1) * 100


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError(f"non-finite JSON constant: {value}")


def _parse_float(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"non-finite JSON number: {value}")
    return number


def _day(value):
    if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
        raise ValueError("trade dates must be ISO YYYY-MM-DD strings")
    return value


class _Audit:
    def __init__(self, path: Path):
        self.receipt = {
            "artifact": str(path),
            "audit_version": AUDIT_VERSION,
            "calculation_checks": Counter(),
            "integrity_checks": Counter(),
            "skips": [],
            "errors": [],
            "duplicate_facts": {},
        }

    def error(self, field, **detail):
        self.receipt["errors"].append({"field": field, **detail})

    def skip(self, reason, **detail):
        self.receipt["skips"].append({"reason": reason, **detail})

    def check(self, field, observed, expected, *, row=None, calculation=False):
        if type(expected) is float and not math.isfinite(expected):
            raise ValueError(f"non-finite independent calculation: {field}")
        bucket = "calculation_checks" if calculation else "integrity_checks"
        self.receipt[bucket][field] += 1
        equal = observed == expected and type(observed) is type(expected)
        if _finite(expected):
            equal = _finite(observed) and math.isclose(
                observed, expected, abs_tol=1e-8, rel_tol=1e-10
            )
        if not equal:
            self.error(field, row=row, observed=observed, recomputed=expected)

    def index(self, table, rows, code_key):
        if not isinstance(rows, list):
            raise ValueError(f"{table} inputs must be a list")
        facts, repeats, conflicts = {}, 0, 0
        for row in rows:
            code = row[code_key] if code_key else ""
            if not isinstance(code, str) or (code_key and not code):
                raise ValueError(f"{table} needs an exact nonempty entity code")
            key = (code, _day(row["trade_date"]))
            if key in facts:
                if row == facts[key]:
                    repeats += 1
                else:
                    conflicts += 1
                    self.error("duplicate_fact_key", table=table, key=list(key))
                continue  # Keep the first explicitly reported read; never overwrite.
            facts[key] = row
        self.receipt["duplicate_facts"][table] = {
            "unique_keys": len(facts),
            "identical_repeats": repeats,
            "conflicts": conflicts,
        }
        return facts

    def finish(self):
        receipt = self.receipt
        receipt["result"] = (
            "error"
            if receipt["errors"]
            else "unsupported"
            if not receipt["calculation_checks"]
            else "partial"
            if receipt["skips"]
            else "checked"
        )
        return receipt


def _integrity(doc, audit):
    inputs = doc["inputs"]
    fingerprints = {table: _hash(values) for table, values in inputs.items()}
    fingerprints["calendar_inputs"] = _hash(doc["calendar_inputs"])
    audit.check("input_fingerprint", doc["input_fingerprint"], _hash(fingerprints))
    audit.check(
        "query_id",
        doc["query_id"],
        _hash(
            [
                doc["spec"],
                fingerprints,
                SCHEMA_VERSION,
                doc["feature_definitions"],
            ]
        ),
    )
    seen = set()
    for ref in doc["source_refs"]:
        table = ref["table"]
        if table in seen:
            audit.error("duplicate_source_ref", table=table)
        seen.add(table)
        audit.check(
            "source_input_fingerprint", ref["input_fingerprint"], fingerprints[table]
        )
        audit.check("source_row_count", ref["row_count"], len(inputs[table]))
        snapshots = sorted(
            {
                r["sector_universe_snapshot_id"]
                for r in inputs[table]
                if r.get("sector_universe_snapshot_id")
            }
        )
        audit.check("source_snapshot_ids", ref["snapshot_ids"], snapshots)
    audit.check("source_tables", sorted(seen), sorted(inputs))
    rows, preview = doc["rows"], doc["preview"]
    if not isinstance(rows, list) or not isinstance(preview, list):
        raise ValueError("rows and preview must be lists")
    audit.check("total_matched", doc["total_matched"], len(rows))
    audit.check("returned_count", doc["returned_count"], len(preview))
    audit.check("preview", preview, rows[: len(preview)])
    audit.check("truncated", doc["truncated"], len(preview) < len(rows))


def _supported(name, doc, audit):
    definition = doc["feature_definitions"].get(name)
    if not isinstance(definition, dict):
        audit.error("feature_definition", feature=name, reason="missing definition")
        return False
    if definition.get("version") != FEATURE_VERSION:
        audit.skip(
            "unsupported_feature_version",
            feature=name,
            version=definition.get("version"),
        )
        return False
    if name not in DEFINITIONS:
        audit.skip("unsupported_feature", feature=name)
        return False
    fields, unit, rule = DEFINITIONS[name]
    if definition != dict(
        fields=fields,
        unit=unit,
        rule=rule,
        version=FEATURE_VERSION,
        entity_kind=doc["spec"]["entity_kind"],
    ):
        audit.skip("unsupported_definition", feature=name)
        return False
    if doc["spec"]["entity_kind"] == "stock" and name in {
        "double_red_days",
        "max_double_red_streak",
    }:
        audit.skip("unsupported_stock_definition", feature=name)
        return False
    return True


def _calculate(name, days, facts, markets, code):
    rows = [facts.get((code, day)) for day in days]
    if not days or any(row is None for row in rows):
        return None, "missing_input_dates"
    fields = DEFINITIONS[name][0]
    for field in fields:
        values = (
            [markets.get(("", d), {}).get("sh_index_pct_chg") for d in days]
            if field.startswith("market.")
            else [row.get(field) for row in rows]
        )
        if not all(_finite(v) for v in values):
            return None, "missing_or_invalid_input_values"
    if name == "return_pct":
        return _compound([r["pct_chg"] for r in rows]), None
    if name == "amount_ratio":
        if rows[0]["amount"] == 0:
            return None, "zero_denominator"
        return rows[-1]["amount"] / rows[0]["amount"], None
    if name == "market_relative_return_pct":
        return _compound([r["pct_chg"] for r in rows]) - _compound(
            [markets["", day]["sh_index_pct_chg"] for day in days]
        ), None
    longest = streak = total = 0
    for row in rows:
        red = row["pct_chg"] > 0 and row["diff_ratio"] > 10 and row["amount"] > 500
        streak = streak + 1 if red else 0
        total += red
        longest = max(longest, streak)
    return (total if name == "double_red_days" else longest), None


def _compare_row(doc, row, index, derived, days, facts, markets, supported, audit):
    condition, outcome = doc["spec"]["condition"], doc["spec"]["outcome"]
    name = condition["feature"]
    if name not in derived or condition["op"] not in {"gte", "lte"}:
        audit.skip("condition_not_independently_recomputed", row=index)
    else:
        value = derived[name]
        if not _finite(condition["value"]):
            raise ValueError("condition threshold must be finite")
        x = (
            None
            if value is None
            else (
                value >= condition["value"]
                if condition["op"] == "gte"
                else value <= condition["value"]
            )
        )
        audit.check("x", row["x"], x, row=index)
        audit.receipt["calculation_checks"]["condition_x"] += 1
    if "return_pct" not in supported:
        audit.skip("outcome_definition_not_supported", row=index)
        return
    horizon = outcome["horizon_days"]
    if (
        type(horizon) is not int
        or horizon <= 0
        or not _finite(outcome["threshold_pct"])
    ):
        raise ValueError(
            "outcome needs a positive integer horizon and finite threshold"
        )
    future = [day for day in days if day > row["end"]][:horizon]
    audit.check(
        "outcome_end", row["outcome_end"], future[-1] if future else None, row=index
    )
    if row["x"] is None:
        state, value, reason = "missing_feature", None, "missing_feature"
    elif len(future) < horizon:
        state, value, reason = "immature", None, "immature"
    else:
        value, reason = _calculate(
            "return_pct", future, facts, markets, row["entity_code"]
        )
        state = "missing_outcome" if value is None else "observed"
    audit.check("comparison_state", row["comparison_state"], state, row=index)
    audit.check(
        "forward_return_pct",
        row["forward_return_pct"],
        value,
        row=index,
        calculation=value is not None,
    )
    audit.check(
        "y",
        row["y"],
        None if value is None else value >= outcome["threshold_pct"],
        row=index,
    )
    if value is not None:
        audit.receipt["calculation_checks"]["outcome_y"] += 1
    else:
        audit.skip(reason, row=index, feature="forward_return_pct")


def _comparison(doc, audit):
    rows, comparison = doc["rows"], doc["comparison"]
    if set(comparison["four_cells"]) != set(CELLS) or any(
        type(value) is not int or value < 0
        for value in [
            *comparison["four_cells"].values(),
            *(comparison[key] for key in ("enumerated", "missing", "immature")),
        ]
    ):
        raise ValueError(
            "comparison counts must be nonnegative integers with exactly four known cells"
        )
    cells = dict.fromkeys(CELLS, 0)
    states = Counter()
    for index, row in enumerate(rows):
        state = row["comparison_state"]
        states[state] += 1
        x, y = row["x"], row["y"]
        forward = row["forward_return_pct"]
        valid_state = {
            "observed": type(x) is bool and type(y) is bool and _finite(forward),
            "missing_feature": x is None and y is None and forward is None,
            "missing_outcome": type(x) is bool and y is None and forward is None,
            "immature": type(x) is bool and y is None and forward is None,
        }.get(state, False)
        if not valid_state:
            audit.error("comparison_state_contract", row=index, state=state)
        if type(x) is bool and type(y) is bool:
            cells[f"x_{str(x).lower()}_y_{str(y).lower()}"] += 1
            if state != "observed":
                audit.error(
                    "comparison_state",
                    row=index,
                    reason="boolean pair must be observed",
                )
        elif state not in {"missing_feature", "missing_outcome", "immature"}:
            audit.error("comparison_state", row=index, reason="invalid missing state")
        if (
            x is not None
            and type(x) is not bool
            or y is not None
            and type(y) is not bool
        ):
            audit.error("comparison_label_type", row=index)
    audit.check("four_cells", comparison["four_cells"], cells)
    audit.check("enumerated", comparison["enumerated"], len(rows))
    audit.check(
        "missing",
        comparison["missing"],
        states["missing_feature"] + states["missing_outcome"],
    )
    audit.check("immature", comparison["immature"], states["immature"])
    audit.check(
        "denominator_conservation",
        sum(comparison["four_cells"].values())
        + comparison["missing"]
        + comparison["immature"],
        len(rows),
    )
    audit.receipt["calculation_checks"]["four_cell_summary"] += 1


def audit_artifact(path: Path | str) -> dict:
    """Read one artifact and return a JSON-safe receipt; never mutate the artifact."""
    path = Path(path).resolve()
    audit = _Audit(path)
    try:
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        audit.receipt["file_sha256"] = digest
        match = re.fullmatch(r"history-query-([0-9a-f]{64})\.json", path.name)
        if match:
            audit.check("file_sha256", digest, match[1])
        doc = json.loads(
            raw,
            object_pairs_hook=_object,
            parse_constant=_reject_constant,
            parse_float=_parse_float,
        )
        if not isinstance(doc, dict) or not isinstance(doc.get("schema_version"), str):
            raise ValueError("expected history-query object with schema_version")
        audit.receipt.update(
            schema_version=doc["schema_version"], query_id=doc.get("query_id")
        )
        if doc["schema_version"] != SCHEMA_VERSION:
            audit.skip("unsupported_schema_version", version=doc["schema_version"])
            return audit.finish()
        _integrity(doc, audit)
        audit.receipt["feature_versions"] = sorted(
            {
                str(value.get("version"))
                for value in doc["feature_definitions"].values()
                if isinstance(value, dict)
            }
        )
        kind = doc["spec"]["entity_kind"]
        if kind not in {"stock", "sector"}:
            raise ValueError("entity_kind must be stock or sector")
        operation = doc["spec"]["operation"]
        audit.receipt.update(operation=operation, rows=len(doc["rows"]))
        if operation not in {
            "compute_history",
            "compare_cases",
            "find_analogues",
            "inspect_history",
        }:
            audit.skip("unsupported_operation", operation=operation)
            return audit.finish()
        table, code_key = f"fact_{kind}_daily", f"{kind}_ts_code"
        facts = audit.index(table, doc["inputs"].get(table, []), code_key)
        markets = audit.index(
            "fact_market_daily", doc["inputs"].get("fact_market_daily", []), None
        )
        days = sorted(
            {
                _day(day)
                for read in doc["calendar_inputs"]
                for key in ("stock_dates", "market_dates")
                for day in read[key]
            }
        )
        supported = {
            name for name in doc["feature_definitions"] if _supported(name, doc, audit)
        }
        feature_rows = list(enumerate(doc["rows"]))
        if doc.get("reference"):
            feature_rows.append(("reference", doc["reference"]))
        for index, row in feature_rows:
            if "features" not in row:
                if operation != "inspect_history":
                    raise ValueError("calculation row is missing features")
                continue
            start, end = _day(row["start"]), _day(row["end"])
            if start > end or not isinstance(row["entity_code"], str):
                raise ValueError("invalid feature window or entity code")
            window = [d for d in days if start <= d <= end]
            extra = [
                d
                for code, d in facts
                if code == row["entity_code"] and start <= d <= end and d not in window
            ]
            if extra:
                audit.error("calendar_gap", row=index, dates=extra)
            derived = {}
            for name, observed in row["features"].items():
                if name not in supported:
                    audit.skip("feature_not_recomputed", row=index, feature=name)
                    continue
                value, reason = _calculate(
                    name, window, facts, markets, row["entity_code"]
                )
                derived[name] = value
                audit.check(
                    name, observed, value, row=index, calculation=value is not None
                )
                coverage = row["feature_coverage"][name]
                audit.check(
                    "expected_dates", coverage["expected_dates"], len(window), row=index
                )
                if value is not None:
                    audit.check(
                        "feature_status", coverage["status"], "complete", row=index
                    )
                elif coverage["status"] == "complete":
                    audit.error(
                        "feature_status", row=index, feature=name, reason=reason
                    )
                if reason:
                    audit.skip(reason, row=index, feature=name)
            if operation == "compare_cases":
                _compare_row(
                    doc, row, index, derived, days, facts, markets, supported, audit
                )
        if operation == "compare_cases":
            _comparison(doc, audit)
        if operation in {"inspect_history", "find_analogues"}:
            audit.skip(
                "inspection_or_analogue_ranking_not_recomputed", operation=operation
            )
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        OverflowError,
        AttributeError,
    ) as exc:
        audit.error("format_or_read_error", reason=str(exc))
    return audit.finish()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "inputs",
        nargs="+",
        type=Path,
        help="Explicit artifact file or run directory (no recursion)",
    )
    parser.add_argument(
        "--output", type=Path, help="Optional new receipt file; defaults to stdout only"
    )
    args = parser.parse_args(argv)
    paths, errors = set(), []
    for path in args.inputs:
        if path.is_dir():
            selected = list(path.glob("history-query-*.json"))
            if not selected:
                errors.append(
                    {
                        "path": str(path),
                        "reason": "no history-query artifacts in run directory",
                    }
                )
            paths.update(p.resolve() for p in selected)
        else:
            paths.add(path.resolve())
    if args.output and args.output.resolve() in paths:
        errors.append(
            {
                "path": str(args.output),
                "reason": "output must not overwrite an input artifact",
            }
        )
    receipts = [audit_artifact(path) for path in sorted(paths)]
    report = {
        "audit_version": AUDIT_VERSION,
        "supported_schema_version": SCHEMA_VERSION,
        "supported_feature_version": FEATURE_VERSION,
        "certification_eligible": False,
        "method": "Descriptive independent arithmetic on saved facts only; no database, model, or engine IO.",
        "limits": [
            "Checks internal arithmetic and fingerprints, not vendor authenticity, strict PIT, strategy validity, or promotion eligibility.",
            "Only five scalar features plus forward returns, X/Y and four-cell summaries are supported; other features and analogue ranking are explicitly skipped.",
            "For entity/market tables used by supported arithmetic, identical repeated reads are counted and collapsed explicitly; conflicting exact entity/date keys are errors. Other inputs receive fingerprint checks only.",
            "Calendar completeness is relative to saved calendar_inputs; missing vendor trading dates cannot be proven absent without an external source.",
        ],
        "artifacts": receipts,
        "errors": errors,
        "summary": {
            "artifacts": len(receipts),
            "calculation_checks": sum(
                sum(r["calculation_checks"].values()) for r in receipts
            ),
            "skips": sum(len(r["skips"]) for r in receipts),
            "errors": len(errors) + sum(len(r["errors"]) for r in receipts),
            "results": dict(Counter(r["result"] for r in receipts)),
        },
    }
    if args.output and not errors:
        try:
            # Receipt publication is opt-in and must not replace existing files.
            with args.output.open("x", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
                    + "\n"
                )
        except OSError as exc:
            errors.append({"path": str(args.output), "reason": str(exc)})
            report["summary"]["errors"] += 1
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    if report["summary"]["errors"]:
        return 1
    return 0 if report["summary"]["calculation_checks"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
