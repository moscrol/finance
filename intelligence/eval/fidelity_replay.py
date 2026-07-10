"""Deterministic fidelity and point-in-time replay evaluation.

The evaluator deliberately separates three concerns:

* input snapshots contain only data available on or before ``as_of``;
* answer audits compare structured evidence with the source DuckDB;
* human gold labels judge semantic claims that code cannot settle safely.

Missing historical evidence is reported as ``pending`` rather than guessed.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

BASELINE_TABLES = (
    "fact_market_daily",
    "fact_sector_daily",
    "fact_stock_daily",
)
OPTIONAL_REPLAY_TABLES = (
    "fact_mainline_sector_daily",
    "fact_mainline_theme_daily",
    "fact_mainline_stock_daily",
    "fact_limit_advance_daily",
    "fact_theme_limit_heat_daily",
)
ALLOWED_GOLD_STATUSES = {"pass", "fail", "pending", "not_applicable"}
ALLOWED_CLAIM_TYPES = {"observation", "inference", "prediction"}
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_CODE = re.compile(r"^\d{6}(?:\.[A-Za-z]+)?$")


def _json_default(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def write_json(path: Path, body: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(body, ensure_ascii=False, indent=2, default=_json_default) + "\n",
        encoding="utf-8",
    )


def _metric(passed: int, checked: int, pending: int = 0) -> dict[str, Any]:
    return {
        "value": round(passed / checked, 6) if checked else None,
        "passed": passed,
        "checked": checked,
        "pending": pending,
        "status": "measured" if checked else "pending",
    }


def _rate_metric(numerator: int, denominator: int, pending: int = 0) -> dict[str, Any]:
    return {
        "value": round(numerator / denominator, 6) if denominator else None,
        "numerator": numerator,
        "denominator": denominator,
        "pending": pending,
        "status": "measured" if denominator else "pending",
    }


def _connect(db_path: str | Path):
    import duckdb

    return duckdb.connect(str(Path(db_path).expanduser()), read_only=True)


def _table_columns(con: Any, table: str) -> list[str]:
    if not _IDENTIFIER.fullmatch(table):
        return []
    rows = con.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'main' AND table_name = ?
        ORDER BY ordinal_position
        """,
        [table],
    ).fetchall()
    return [str(row[0]) for row in rows]


def _row_to_dict(columns: list[str], row: Iterable[Any]) -> dict[str, Any]:
    return {column: value for column, value in zip(columns, row)}


def _canonical_sha(body: dict[str, Any]) -> str:
    raw = json.dumps(body, ensure_ascii=False, sort_keys=True, default=_json_default)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def extract_claims(answer: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert a dual-blind answer into reviewable semantic claim units."""
    explicit = answer.get("claims")
    if isinstance(explicit, list):
        normalized: list[dict[str, Any]] = []
        for index, claim in enumerate(explicit):
            if not isinstance(claim, dict) or not str(claim.get("text") or "").strip():
                continue
            declared_type = str(claim.get("declared_type") or "")
            normalized.append(
                {
                    "id": str(claim.get("id") or f"claim:{index + 1}"),
                    "text": str(claim["text"]),
                    "declared_type": declared_type,
                    "evidence_refs": [
                        str(ref)
                        for ref in claim.get("evidence_refs") or []
                        if str(ref).strip()
                    ],
                    "entity": claim.get("entity"),
                }
            )
        return normalized

    claims: list[dict[str, Any]] = []

    def add(
        claim_id: str,
        text: str,
        declared_type: str,
        evidence_refs: Any = None,
        entity: str | None = None,
    ) -> None:
        if not str(text or "").strip():
            return
        refs = (
            [str(ref) for ref in evidence_refs if str(ref).strip()]
            if isinstance(evidence_refs, list)
            else []
        )
        claims.append(
            {
                "id": claim_id,
                "text": str(text),
                "declared_type": declared_type,
                "evidence_refs": refs,
                "entity": entity,
            }
        )

    add(
        "stage",
        str(answer.get("stage") or ""),
        "inference",
        (answer.get("stage_features") or {}).get("evidence_refs"),
    )
    add("main_judgment", str(answer.get("main_judgment") or ""), "inference")
    for index, direction in enumerate(answer.get("direction_ranking") or []):
        add(f"direction:{index + 1}", str(direction), "inference", entity=str(direction))
    for index, pick in enumerate(answer.get("picks") or []):
        entity = str(pick.get("code") or pick.get("name") or "")
        add(
            f"pick:{index + 1}",
            f"{pick.get('name') or entity}: {pick.get('reason') or ''}",
            "inference",
            pick.get("evidence_refs"),
            entity=entity,
        )
    for name, threshold in (answer.get("thresholds") or {}).items():
        provenance = (answer.get("threshold_provenance") or {}).get(name) or {}
        refs = [provenance["evidence_ref"]] if provenance.get("evidence_ref") else []
        add(f"threshold:{name}", str(threshold), "inference", refs)
    for index, hypothesis in enumerate(answer.get("hypotheses") or []):
        add(
            f"hypothesis:{hypothesis.get('id') or index + 1}",
            str(hypothesis.get("claim") or ""),
            "prediction",
            hypothesis.get("evidence_refs"),
        )
    return claims


def build_gold_template(answer: dict[str, Any], *, answer_path: str = "") -> dict[str, Any]:
    claims = extract_claims(answer)
    return {
        "schema_version": "1.0",
        "answer_path": answer_path,
        "reviewer": None,
        "reviewed_at": None,
        "claims": {
            claim["id"]: {
                "text": claim["text"],
                "expected_type": None,
                "entity_classification": "pending",
                "timeline_sequence": "pending",
                "causal_evidence_binding": "pending",
                "notes": "",
            }
            for claim in claims
        },
        "instructions": {
            "expected_type": sorted(ALLOWED_CLAIM_TYPES),
            "review_status": sorted(ALLOWED_GOLD_STATUSES),
            "rule": "不确定或证据不足时保留 pending，不猜测。",
        },
    }


def validate_gold(gold: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    claims = gold.get("claims")
    if not isinstance(claims, dict):
        return ["claims 应为对象"]
    for claim_id, review in claims.items():
        if not isinstance(review, dict):
            errors.append(f"claims.{claim_id} 应为对象")
            continue
        expected_type = review.get("expected_type")
        if expected_type is not None and expected_type not in ALLOWED_CLAIM_TYPES:
            errors.append(
                f"claims.{claim_id}.expected_type 应为 {sorted(ALLOWED_CLAIM_TYPES)} 或 null"
            )
        for field in (
            "entity_classification",
            "timeline_sequence",
            "causal_evidence_binding",
        ):
            status = review.get(field, "pending")
            if status not in ALLOWED_GOLD_STATUSES:
                errors.append(
                    f"claims.{claim_id}.{field} 应为 {sorted(ALLOWED_GOLD_STATUSES)}"
                )
    return errors


def validate_answer_claims(answer: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    claims = extract_claims(answer)
    catalog = answer.get("evidence_catalog")
    catalog_ids = set(catalog) if isinstance(catalog, dict) else set()
    seen: set[str] = set()
    for claim in claims:
        claim_id = claim["id"]
        if claim_id in seen:
            errors.append(f"claim id 重复：{claim_id}")
        seen.add(claim_id)
        if claim["declared_type"] not in ALLOWED_CLAIM_TYPES:
            errors.append(
                f"{claim_id}.declared_type 应为 {sorted(ALLOWED_CLAIM_TYPES)}"
            )
        for evidence_ref in claim["evidence_refs"]:
            if evidence_ref not in catalog_ids:
                errors.append(f"{claim_id} 引用不存在的 evidence id：{evidence_ref}")
    return errors


def _entity_filters(
    columns: list[str], entity: Any
) -> tuple[str, list[Any], str | None]:
    value = str(entity or "").strip()
    if not value or value.lower() == "market":
        return "", [], None
    if _CODE.fullmatch(value):
        for column in ("stock_ts_code", "ts_code", "sector_ts_code"):
            if column in columns:
                if "." in value:
                    return f" AND {column} = ?", [value], None
                return (
                    f" AND split_part(CAST({column} AS VARCHAR), '.', 1) = ?",
                    [value],
                    None,
                )
    for column in (
        "stock_name",
        "sector_name",
        "theme_name",
        "name",
        "entity_name",
    ):
        if column in columns:
            return f" AND {column} = ?", [value], None
    return "", [], f"无法把 entity={value} 映射到 {columns}"


def _compare_value(expected: Any, actual: Any) -> bool:
    if isinstance(expected, bool) or isinstance(actual, bool):
        return expected is actual
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        if math.isnan(float(expected)) or math.isnan(float(actual)):
            return False
        return math.isclose(float(expected), float(actual), rel_tol=1e-6, abs_tol=1e-6)
    return str(expected) == str(actual)


def _snapshot_rows(
    snapshot: dict[str, Any], source: str, source_time: str
) -> list[dict[str, Any]]:
    data = snapshot.get("data") or {}
    key = "market_history" if source == "fact_market_daily" else source
    rows = data.get(key) or []
    return [
        row
        for row in rows
        if isinstance(row, dict)
        and str(row.get("trade_date") or "")[:10] == source_time
    ]


def _snapshot_entity_match(row: dict[str, Any], entity: Any) -> bool:
    value = str(entity or "").strip()
    if not value or value.lower() == "market":
        return True
    if _CODE.fullmatch(value):
        for column in ("stock_ts_code", "ts_code", "sector_ts_code"):
            actual = str(row.get(column) or "")
            if actual and (
                actual == value or actual.split(".", maxsplit=1)[0] == value
            ):
                return True
        return False
    return any(
        str(row.get(column) or "") == value
        for column in (
            "stock_name",
            "sector_name",
            "theme_name",
            "name",
            "entity_name",
        )
    )


def audit_numeric_evidence(
    answer: dict[str, Any],
    *,
    db_path: str | Path | None,
    cutoff: str,
    input_snapshot: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    catalog = answer.get("evidence_catalog")
    if not isinstance(catalog, dict):
        return [], _metric(0, 0, 0)
    audits: list[dict[str, Any]] = []
    passed = checked = pending = 0
    con = _connect(db_path) if db_path and input_snapshot is None else None
    try:
        for evidence_id, evidence in catalog.items():
            if not isinstance(evidence, dict):
                continue
            expected = evidence.get("value")
            source = str(evidence.get("source") or "")
            field = str(evidence.get("field") or "")
            source_time = str(evidence.get("source_time") or "")[:10]
            if expected is None:
                continue
            item = {
                "evidence_id": evidence_id,
                "source": source,
                "field": field,
                "expected": expected,
                "actual": None,
                "status": "pending",
                "reason": "",
            }
            if input_snapshot is not None:
                rows = [
                    row
                    for row in _snapshot_rows(input_snapshot, source, source_time)
                    if _snapshot_entity_match(row, evidence.get("entity"))
                ]
                if len(rows) != 1:
                    item["reason"] = f"冻结快照源行数量={len(rows)}，无法唯一核对"
                    pending += 1
                elif field not in rows[0]:
                    item["reason"] = "冻结快照中不存在该字段"
                    pending += 1
                else:
                    actual = rows[0][field]
                    item["actual"] = actual
                    checked += 1
                    if _compare_value(expected, actual):
                        item["status"] = "pass"
                        passed += 1
                    else:
                        item["status"] = "fail"
                        item["reason"] = "答卷值与冻结快照不一致"
            elif not con:
                item["reason"] = "未提供 DuckDB"
                pending += 1
            elif not _IDENTIFIER.fullmatch(source) or not source.startswith("fact_"):
                item["reason"] = "非 DuckDB fact 表证据"
                pending += 1
            elif not _IDENTIFIER.fullmatch(field):
                item["reason"] = "字段名不可安全查询"
                pending += 1
            else:
                columns = _table_columns(con, source)
                if not columns or "trade_date" not in columns or field not in columns:
                    item["reason"] = "表、trade_date 或字段不存在"
                    pending += 1
                elif not source_time or source_time > cutoff:
                    item["reason"] = "证据时间越过 cutoff"
                    pending += 1
                else:
                    entity_sql, entity_params, reason = _entity_filters(
                        columns, evidence.get("entity")
                    )
                    if reason:
                        item["reason"] = reason
                        pending += 1
                    else:
                        rows = con.execute(
                            f"SELECT {field} FROM {source} "
                            f"WHERE CAST(trade_date AS DATE) = CAST(? AS DATE){entity_sql} "
                            "LIMIT 2",
                            [source_time, *entity_params],
                        ).fetchall()
                        if len(rows) != 1:
                            item["reason"] = f"源行数量={len(rows)}，无法唯一核对"
                            pending += 1
                        else:
                            actual = rows[0][0]
                            item["actual"] = actual
                            checked += 1
                            if _compare_value(expected, actual):
                                item["status"] = "pass"
                                passed += 1
                            else:
                                item["status"] = "fail"
                                item["reason"] = "答卷值与 DuckDB 不一致"
            audits.append(item)
    finally:
        if con:
            con.close()
    return audits, _metric(passed, checked, pending)


def _review_metric(
    claims: list[dict[str, Any]],
    gold: dict[str, Any] | None,
    field: str,
) -> dict[str, Any]:
    reviews = (gold or {}).get("claims") or {}
    passed = checked = pending = 0
    for claim in claims:
        review = reviews.get(claim["id"])
        if not isinstance(review, dict):
            pending += 1
            continue
        status = str(review.get(field) or "pending")
        if status == "pending":
            pending += 1
        elif status == "not_applicable":
            continue
        elif status in {"pass", "fail"}:
            checked += 1
            passed += int(status == "pass")
        else:
            pending += 1
    return _metric(passed, checked, pending)


def audit_answer(
    answer: dict[str, Any],
    manifest: dict[str, Any],
    *,
    db_path: str | Path | None = None,
    gold: dict[str, Any] | None = None,
    input_snapshot: dict[str, Any] | None = None,
    answer_path: str = "",
) -> dict[str, Any]:
    cutoff = str(manifest.get("perspective_date") or "")[:10]
    catalog = answer.get("evidence_catalog")
    evidence = catalog if isinstance(catalog, dict) else {}
    claims = extract_claims(answer)
    numeric_audits, numeric_metric = audit_numeric_evidence(
        answer,
        db_path=db_path,
        cutoff=cutoff,
        input_snapshot=input_snapshot,
    )

    cutoff_violations: list[str] = []
    for evidence_id, item in evidence.items():
        if not isinstance(item, dict):
            continue
        source_time = str(item.get("source_time") or "")[:10]
        if cutoff and source_time and source_time > cutoff:
            cutoff_violations.append(str(evidence_id))

    catalog_ids = set(evidence)
    covered = sum(
        1
        for claim in claims
        if claim["evidence_refs"]
        and all(ref in catalog_ids for ref in claim["evidence_refs"])
    )
    evidence_coverage = _rate_metric(covered, len(claims))
    cutoff_metric = _rate_metric(len(cutoff_violations), len(evidence))

    expected_type_reviews = (gold or {}).get("claims") or {}
    confusion = type_checked = type_pending = 0
    for claim in claims:
        review = expected_type_reviews.get(claim["id"])
        expected_type = review.get("expected_type") if isinstance(review, dict) else None
        if expected_type not in ALLOWED_CLAIM_TYPES:
            type_pending += 1
            continue
        type_checked += 1
        confusion += int(expected_type != claim["declared_type"])
    confusion_metric = _rate_metric(confusion, type_checked, type_pending)

    gold_errors = validate_gold(gold) if gold is not None else []
    answer_errors = validate_answer_claims(answer)
    return {
        "schema_version": "1.0",
        "answer_path": answer_path,
        "answer_schema_version": answer.get("schema_version"),
        "date": answer.get("date"),
        "as_of": cutoff,
        "agent": answer.get("agent"),
        "source": answer.get("source", "duckdb"),
        "metrics": {
            "numeric_match_rate": numeric_metric,
            "evidence_coverage_rate": evidence_coverage,
            "cutoff_violation_rate": cutoff_metric,
            "fact_inference_confusion_rate": confusion_metric,
            "entity_classification_accuracy": _review_metric(
                claims, gold, "entity_classification"
            ),
            "event_timeline_sequence_accuracy": _review_metric(
                claims, gold, "timeline_sequence"
            ),
            "causal_statement_evidence_binding_rate": _review_metric(
                claims, gold, "causal_evidence_binding"
            ),
        },
        "counts": {
            "claims": len(claims),
            "evidence": len(evidence),
            "cutoff_violations": len(cutoff_violations),
        },
        "cutoff_violation_evidence_ids": cutoff_violations,
        "numeric_audits": numeric_audits,
        "claim_audits": claims,
        "gold_errors": gold_errors,
        "answer_errors": answer_errors,
        "decision_eligible": False,
        "status": (
            "invalid_gold"
            if gold_errors
            else "invalid_answer"
            if answer_errors
            else "audited"
        ),
    }


def aggregate_audits(audits: list[dict[str, Any]]) -> dict[str, Any]:
    metric_names = (
        "numeric_match_rate",
        "evidence_coverage_rate",
        "cutoff_violation_rate",
        "fact_inference_confusion_rate",
        "entity_classification_accuracy",
        "event_timeline_sequence_accuracy",
        "causal_statement_evidence_binding_rate",
    )
    metrics: dict[str, Any] = {}
    for name in metric_names:
        numerator = denominator = pending = 0
        for audit in audits:
            metric = audit.get("metrics", {}).get(name) or {}
            if "passed" in metric:
                numerator += int(metric.get("passed") or 0)
                denominator += int(metric.get("checked") or 0)
            else:
                numerator += int(metric.get("numerator") or 0)
                denominator += int(metric.get("denominator") or 0)
            pending += int(metric.get("pending") or 0)
        metrics[name] = _rate_metric(numerator, denominator, pending)
    return {
        "schema_version": "1.0",
        "answers": len(audits),
        "metrics": metrics,
        "schema_versions": dict(
            sorted(
                (
                    str(version),
                    sum(
                        1
                        for audit in audits
                        if str(audit.get("answer_schema_version")) == str(version)
                    ),
                )
                for version in {
                    audit.get("answer_schema_version") for audit in audits
                }
            )
        ),
        "decision_eligible": False,
    }


def _market_rows(
    db_path: str | Path, start: str, end: str
) -> list[dict[str, Any]]:
    con = _connect(db_path)
    try:
        columns = _table_columns(con, "fact_market_daily")
        stage_column = "market_stage" if "market_stage" in columns else None
        select_stage = f", {stage_column}" if stage_column else ""
        rows = con.execute(
            f"""
            SELECT DISTINCT CAST(trade_date AS VARCHAR){select_stage}
            FROM fact_market_daily
            WHERE CAST(trade_date AS DATE) BETWEEN CAST(? AS DATE) AND CAST(? AS DATE)
            ORDER BY 1
            """,
            [start, end],
        ).fetchall()
        return [
            {
                "as_of": str(row[0])[:10],
                "market_stage": str(row[1] or "unknown") if len(row) > 1 else "unknown",
            }
            for row in rows
        ]
    finally:
        con.close()


def _all_trade_dates(db_path: str | Path) -> list[str]:
    con = _connect(db_path)
    try:
        return [
            str(row[0])[:10]
            for row in con.execute(
                "SELECT DISTINCT trade_date FROM fact_market_daily ORDER BY trade_date"
            ).fetchall()
        ]
    finally:
        con.close()


def select_pilot_dates(
    db_path: str | Path, start: str, end: str, *, count: int = 10
) -> list[dict[str, Any]]:
    """Choose deterministic dates across month × market-stage buckets."""
    rows = _market_rows(db_path, start, end)
    if not rows:
        return []
    by_bucket: dict[tuple[str, str], list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        by_bucket[(row["as_of"][:7], row["market_stage"])].append(index)
    candidates = sorted(
        {
            indexes[len(indexes) // 2]
            for indexes in by_bucket.values()
            if indexes
        }
    )
    if len(candidates) > count:
        candidates = [
            candidates[round(i * (len(candidates) - 1) / (count - 1))]
            for i in range(count)
        ]
    selected = set(candidates)
    while len(selected) < min(count, len(rows)):
        remaining = [i for i in range(len(rows)) if i not in selected]
        best = max(
            remaining,
            key=lambda i: min(abs(i - picked) for picked in selected)
            if selected
            else len(rows),
        )
        selected.add(best)
    ordered = sorted(selected)[:count]
    all_dates = _all_trade_dates(db_path)
    date_indexes = {trade_date: index for index, trade_date in enumerate(all_dates)}
    results: list[dict[str, Any]] = []
    for index in ordered:
        as_of = rows[index]["as_of"]
        date_index = date_indexes[as_of]
        outcome_dates = all_dates[date_index + 1 : date_index + 4]
        results.append(
            {
                **rows[index],
                "target_date": outcome_dates[0] if outcome_dates else None,
                "t3_date": outcome_dates[2] if len(outcome_dates) >= 3 else None,
            }
        )
    return results


def find_kb_commit_as_of(kb_root: str | Path, as_of: str) -> dict[str, Any] | None:
    root = Path(kb_root).expanduser()
    try:
        commit = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "rev-list",
                "-1",
                f"--before={as_of} 23:59:59 +0800",
                "HEAD",
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if not commit:
            return None
        timestamp = subprocess.run(
            ["git", "-C", str(root), "show", "-s", "--format=%cI", commit],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        return {"commit": commit, "committed_at": timestamp}
    except (OSError, subprocess.CalledProcessError):
        return None


def _table_count(con: Any, table: str, as_of: str) -> int | None:
    columns = _table_columns(con, table)
    if not columns or "trade_date" not in columns:
        return None
    row = con.execute(
        f"SELECT COUNT(*) FROM {table} WHERE CAST(trade_date AS DATE) = CAST(? AS DATE)",
        [as_of],
    ).fetchone()
    return int(row[0]) if row else 0


def _table_readiness(con: Any, table: str, as_of: str) -> dict[str, Any]:
    columns = _table_columns(con, table)
    if not columns or "trade_date" not in columns:
        return {
            "total_rows": 0,
            "provable_as_of_rows": 0,
            "status": "missing",
            "timestamp_field": None,
        }
    total = _table_count(con, table, as_of) or 0
    if not total:
        return {
            "total_rows": 0,
            "provable_as_of_rows": 0,
            "status": "missing",
            "timestamp_field": "updated_at" if "updated_at" in columns else None,
        }
    if "updated_at" not in columns:
        return {
            "total_rows": total,
            "provable_as_of_rows": 0,
            "status": "unverifiable",
            "timestamp_field": None,
        }
    row = con.execute(
        f"""
        SELECT COUNT(*)
        FROM {table}
        WHERE CAST(trade_date AS DATE) = CAST(? AS DATE)
          AND updated_at < CAST(? AS DATE) + INTERVAL 1 DAY
        """,
        [as_of, as_of],
    ).fetchone()
    provable = int(row[0]) if row else 0
    status = "ready" if provable == total else "partial" if provable else "unavailable"
    return {
        "total_rows": total,
        "provable_as_of_rows": provable,
        "status": status,
        "timestamp_field": "updated_at",
    }


def build_pilot_plan(
    db_path: str | Path,
    kb_root: str | Path,
    *,
    start: str,
    end: str,
    count: int = 10,
) -> dict[str, Any]:
    selected = select_pilot_dates(db_path, start, end, count=count)
    con = _connect(db_path)
    cases: list[dict[str, Any]] = []
    try:
        for item in selected:
            as_of = item["as_of"]
            readiness = {
                table: _table_readiness(con, table, as_of)
                for table in (*BASELINE_TABLES, *OPTIONAL_REPLAY_TABLES)
            }
            table_counts = {
                table: item["total_rows"] for table, item in readiness.items()
            }
            missing_baseline = [
                table
                for table in BASELINE_TABLES
                if readiness[table]["status"] != "ready"
            ]
            optional_gaps = [
                (
                    f"{table}({readiness[table]['status']} "
                    f"{readiness[table]['provable_as_of_rows']}/"
                    f"{readiness[table]['total_rows']})"
                )
                for table in OPTIONAL_REPLAY_TABLES
                if readiness[table]["status"] != "ready"
            ]
            kb = find_kb_commit_as_of(kb_root, as_of)
            blockers: list[str] = []
            if missing_baseline:
                blockers.extend(
                    (
                        f"无可证明的 as-of {table} 快照："
                        f"{readiness[table]['provable_as_of_rows']}/"
                        f"{readiness[table]['total_rows']} 行在截止前写入"
                    )
                    for table in missing_baseline
                )
            if not kb:
                blockers.append("无 as-of 知识库 commit")
            cases.append(
                {
                    "case_id": f"FR-{as_of}",
                    **item,
                    "db_table_counts": table_counts,
                    "db_table_readiness": readiness,
                    "kb_snapshot": kb,
                    "optional_gaps": optional_gaps,
                    "status": "ready" if not blockers else "pending",
                    "blockers": blockers,
                }
            )
    finally:
        con.close()
    body = {
        "schema_version": "1.0",
        "task_id": "fidelity-replay-v1",
        "start": start,
        "end": end,
        "requested_cases": count,
        "cases": cases,
        "status_counts": {
            status: sum(1 for case in cases if case["status"] == status)
            for status in ("ready", "pending")
        },
        "rules": {
            "lookahead": "answer input contains D0 and earlier only",
            "missing": "pending; never backfill from current knowledge",
            "outcomes": "generated by a separate command after answers are frozen",
            "db_pit": "trade_date alone is insufficient; rows require updated_at before cutoff",
        },
        "sampling_note": "market_stage is used only for stratification and comes from the current DB row; it is not treated as PIT gold.",
    }
    body["plan_sha256"] = _canonical_sha(body)
    return body


def _ordered_rows(
    con: Any,
    table: str,
    where_sql: str,
    params: list[Any],
    *,
    order_by: str,
    limit: int,
) -> list[dict[str, Any]]:
    columns = _table_columns(con, table)
    if not columns:
        return []
    rows = con.execute(
        f"SELECT * FROM {table} WHERE {where_sql} ORDER BY {order_by} LIMIT {int(limit)}",
        params,
    ).fetchall()
    return [_row_to_dict(columns, row) for row in rows]


def _best_order(columns: list[str], candidates: tuple[str, ...]) -> str:
    for candidate in candidates:
        if candidate in columns:
            return f"{candidate} DESC NULLS LAST"
    return "trade_date DESC"


def _pit_where(columns: list[str], base_where: str) -> str:
    if "updated_at" not in columns:
        return f"({base_where}) AND FALSE"
    return (
        f"({base_where}) "
        "AND updated_at < CAST(? AS DATE) + INTERVAL 1 DAY"
    )


def _max_embedded_date(value: Any) -> str | None:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {
                "trade_date",
                "source_time",
                "as_of",
                "date",
                "published_at",
            }:
                raw = str(item or "")[:10]
                if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
                    found.append(raw)
            nested = _max_embedded_date(item)
            if nested:
                found.append(nested)
    elif isinstance(value, list):
        for item in value:
            nested = _max_embedded_date(item)
            if nested:
                found.append(nested)
    return max(found) if found else None


def build_input_snapshot(
    db_path: str | Path,
    case: dict[str, Any],
    *,
    sector_limit: int = 30,
    stock_limit: int = 30,
) -> dict[str, Any]:
    """Build an answer-phase artifact that cannot contain future market rows."""
    if case.get("status") != "ready":
        raise ValueError(f"{case.get('case_id')} is pending and cannot produce an input snapshot")
    as_of = str(case["as_of"])
    con = _connect(db_path)
    try:
        market_columns = _table_columns(con, "fact_market_daily")
        data: dict[str, Any] = {
            "market_history": _ordered_rows(
                con,
                "fact_market_daily",
                _pit_where(
                    market_columns,
                    "CAST(trade_date AS DATE) <= CAST(? AS DATE)",
                ),
                [as_of, as_of],
                order_by="trade_date DESC",
                limit=20,
            )
        }
        for table, limit in (
            ("fact_sector_daily", sector_limit),
            ("fact_stock_daily", stock_limit),
            ("fact_mainline_sector_daily", sector_limit),
            ("fact_mainline_theme_daily", sector_limit),
            ("fact_mainline_stock_daily", stock_limit),
            ("fact_limit_advance_daily", stock_limit),
            ("fact_theme_limit_heat_daily", sector_limit),
        ):
            columns = _table_columns(con, table)
            if not columns:
                data[table] = []
                continue
            data[table] = _ordered_rows(
                con,
                table,
                _pit_where(
                    columns,
                    "CAST(trade_date AS DATE) = CAST(? AS DATE)",
                ),
                [as_of, as_of],
                order_by=_best_order(
                    columns,
                    (
                        "strength",
                        "diff_ratio",
                        "amount",
                        "pct_chg",
                        "limit_up_count",
                        "rank",
                    ),
                ),
                limit=limit,
            )
    finally:
        con.close()
    body = {
        "schema_version": "1.0",
        "task_id": "fidelity-replay-v1",
        "case_id": case["case_id"],
        "as_of": as_of,
        "target_date": case.get("target_date"),
        "kb_snapshot": case.get("kb_snapshot"),
        "data": data,
        "boundary": {
            "max_allowed_date": as_of,
            "outcome_data_included": False,
        },
    }
    max_date = _max_embedded_date(body["data"])
    if max_date and max_date > as_of:
        raise ValueError(f"snapshot contains future date {max_date} > {as_of}")
    body["boundary"]["max_embedded_date"] = max_date
    body["snapshot_sha256"] = _canonical_sha(body)
    return body


def build_outcome_snapshot(
    db_path: str | Path, case: dict[str, Any]
) -> dict[str, Any]:
    """Build result-phase data separately from answer-phase inputs."""
    dates = [
        value
        for value in (case.get("target_date"), case.get("t3_date"))
        if value
    ]
    con = _connect(db_path)
    try:
        data: dict[str, Any] = {}
        for outcome_date in dates:
            per_date: dict[str, Any] = {}
            for table in (
                "fact_market_daily",
                "fact_sector_daily",
                "fact_stock_daily",
                "fact_theme_limit_heat_daily",
            ):
                per_date[table] = _ordered_rows(
                    con,
                    table,
                    "CAST(trade_date AS DATE) = CAST(? AS DATE)",
                    [outcome_date],
                    order_by="trade_date",
                    limit=100_000,
                )
            data[outcome_date] = per_date
    finally:
        con.close()
    body = {
        "schema_version": "1.0",
        "task_id": "fidelity-replay-v1",
        "case_id": case["case_id"],
        "as_of": case["as_of"],
        "input_snapshot_sha256": case.get("input_snapshot_sha256"),
        "outcomes": data,
        "boundary": {"answer_phase_allowed": False},
    }
    body["outcome_sha256"] = _canonical_sha(body)
    return body


def render_report(report: dict[str, Any]) -> str:
    lines = [
        "# 现状忠实度 / 历史重放评测",
        "",
        f"- 答卷数：{report.get('answers', 0)}",
        "- 决策资格：否（仅评测，不进入硬闸门）",
        "",
        "| 指标 | 值 | 已检查 | pending |",
        "|---|---:|---:|---:|",
    ]
    labels = {
        "numeric_match_rate": "数字一致率",
        "evidence_coverage_rate": "证据覆盖率",
        "cutoff_violation_rate": "截止违规率（越低越好）",
        "fact_inference_confusion_rate": "事实/推断混淆率（越低越好）",
        "entity_classification_accuracy": "实体归类准确率",
        "event_timeline_sequence_accuracy": "事件时间线准确率",
        "causal_statement_evidence_binding_rate": "因果陈述证据绑定率",
    }
    for name, metric in (report.get("metrics") or {}).items():
        value = metric.get("value")
        display = "pending" if value is None else f"{value:.1%}"
        lines.append(
            f"| {labels.get(name, name)} | {display} "
            f"| {metric.get('denominator', metric.get('checked', 0))} "
            f"| {metric.get('pending', 0)} |"
        )
    lines.extend(
        [
            "",
            "> `pending` 表示缺少 PIT 快照或人工金标准，不能当作通过或失败。",
            "",
        ]
    )
    return "\n".join(lines)


def render_pilot_plan(plan: dict[str, Any]) -> str:
    lines = [
        "# Fidelity / Replay 10 日 Pilot",
        "",
        f"- 范围：{plan.get('start')} ～ {plan.get('end')}",
        f"- ready：{plan.get('status_counts', {}).get('ready', 0)}",
        f"- pending：{plan.get('status_counts', {}).get('pending', 0)}",
        "- 纪律：输入快照不含结果数据；缺 PIT 证据不补猜。",
        "",
        "| case | as-of | T+1 | 阶段 | 状态 | 缺口 |",
        "|---|---|---|---|---|---|",
    ]
    for case in plan.get("cases", []):
        gaps = [*case.get("blockers", []), *case.get("optional_gaps", [])]
        lines.append(
            f"| {case.get('case_id')} | {case.get('as_of')} "
            f"| {case.get('target_date') or '—'} | {case.get('market_stage') or '—'} "
            f"| {case.get('status')} | {'；'.join(gaps) or '—'} |"
        )
    lines.extend(
        [
            "",
            "> optional gap 只表示该日缺少增强表，不会用今天的数据补齐；"
            "缺基础表或 as-of wiki commit 才会把 case 标为 pending。",
            "",
        ]
    )
    return "\n".join(lines)
