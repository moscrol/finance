from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import date, datetime


LINEAGE_SCHEMA_VERSION = "claim-lineage-v1"


def _json_value(value: object) -> object:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {
            str(key): _json_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    return value


def evidence_id(source_ref: dict[str, object]) -> str:
    payload = json.dumps(
        _json_value(source_ref),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"ev-{digest}"


def register_evidence(
    catalog: dict[str, dict[str, object]],
    source_ref: dict[str, object],
) -> str:
    normalized = deepcopy(_json_value(source_ref))
    if not isinstance(normalized, dict):
        raise TypeError("source_ref must normalize to a dict")
    ref_id = evidence_id(normalized)
    catalog.setdefault(ref_id, normalized)
    return ref_id


def materialize_candidate_lineage(
    candidates: list[dict[str, object]],
) -> dict[str, dict[str, object]]:
    catalog: dict[str, dict[str, object]] = {}
    for candidate in candidates:
        raw_lineage = candidate.pop("_market_lineage", {})
        if not isinstance(raw_lineage, dict):
            continue
        evidence_refs: dict[str, list[str]] = {}
        materialized: dict[str, str] = {}
        active: set[str] = set()

        def materialize(field_path: str) -> str | None:
            if field_path in materialized:
                return materialized[field_path]
            source_ref = raw_lineage.get(field_path)
            if not isinstance(source_ref, dict) or field_path in active:
                return None
            active.add(field_path)
            normalized = deepcopy(source_ref)
            input_paths = normalized.pop("input_field_paths", [])
            input_source_refs = normalized.pop("input_source_refs", [])
            input_ids = []
            if isinstance(input_paths, list):
                for input_path in input_paths:
                    input_id = materialize(str(input_path))
                    if input_id:
                        input_ids.append(input_id)
            if isinstance(input_source_refs, list):
                for input_source_ref in input_source_refs:
                    if isinstance(input_source_ref, dict):
                        input_ids.append(
                            register_evidence(catalog, input_source_ref)
                        )
            derivation = normalized.get("derivation")
            if isinstance(derivation, dict) and input_ids:
                derivation["input_evidence_refs"] = list(dict.fromkeys(input_ids))
            ref_id = register_evidence(catalog, normalized)
            materialized[field_path] = ref_id
            active.remove(field_path)
            return ref_id

        for field_path, source_ref in sorted(raw_lineage.items()):
            if not isinstance(source_ref, dict):
                continue
            ref_id = materialize(str(field_path))
            if ref_id:
                evidence_refs[str(field_path)] = [ref_id]
        if evidence_refs:
            candidate["evidence_refs"] = evidence_refs
    return catalog


def resolve_candidate_lineage(
    candidate: dict[str, object],
    catalog: dict[str, object],
) -> dict[str, dict[str, object]]:
    resolved: dict[str, dict[str, object]] = {}
    raw_refs = candidate.get("evidence_refs")
    if not isinstance(raw_refs, dict):
        return resolved
    for field_path, ref_ids in raw_refs.items():
        if not isinstance(ref_ids, list):
            continue
        for ref_id in ref_ids:
            source_ref = catalog.get(str(ref_id))
            if isinstance(source_ref, dict):
                resolved[str(field_path)] = deepcopy(source_ref)
                break
    return resolved


def _value_at_path(body: object, field_path: str) -> object | None:
    current = body
    for part in field_path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
            continue
        if isinstance(current, list) and part.isdigit():
            index = int(part)
            if index >= len(current):
                return None
            current = current[index]
            continue
        return None
    return current


def _claim_type(value: object) -> str:
    if isinstance(value, bool):
        return "fact"
    if isinstance(value, (int, float)):
        return "number"
    return "fact"


def _unit_for_path(field_path: str) -> str | None:
    field = field_path.rsplit(".", 1)[-1]
    if field in {
        "pct_chg",
        "diff_ratio",
        "market_share",
        "ratio",
        "change_pct",
    }:
        return "%"
    if field in {"amount", "high_amount"}:
        return "亿元"
    if field in {"limit_up_count", "total_count", "high_count", "stock_count"}:
        return "只"
    if field == "max_boards":
        return "板"
    return None


def build_daily_agent_claim_manifest(
    batch: dict[str, object],
    *,
    report_date: str,
) -> tuple[list[dict[str, object]], dict[str, dict[str, object]]]:
    claims: list[dict[str, object]] = []
    catalog: dict[str, dict[str, object]] = {}
    results = batch.get("results")
    if not isinstance(results, list):
        return claims, catalog
    for result_index, result in enumerate(results):
        if not isinstance(result, dict):
            continue
        market_evidence = result.get("market_evidence")
        lineage = result.get("market_evidence_lineage")
        if not isinstance(market_evidence, dict) or not isinstance(lineage, dict):
            continue
        subject_value = result.get("matched_theme")
        if not subject_value:
            subject_value = result.get("market_theme")
        if not subject_value:
            subject_value = result.get("query")
        subject = str(subject_value or "")
        for field_path, source_ref in sorted(lineage.items()):
            if not isinstance(source_ref, dict):
                continue
            value = _value_at_path(market_evidence, str(field_path))
            if value is None or isinstance(value, (dict, list)):
                continue
            ref_id = register_evidence(catalog, source_ref)
            claim_id = f"claim-{report_date}-{result_index + 1}-{len(claims) + 1}"
            claim: dict[str, object] = {
                "claim_id": claim_id,
                "text": f"{subject} {field_path} = {value}",
                "claim_type": _claim_type(value),
                "expected_type": (
                    "numeric_fact"
                    if _claim_type(value) == "number"
                    else "factual_statement"
                ),
                "subject": subject,
                "predicate": str(field_path),
                "value": value,
                "valid_time": report_date,
                "evidence_refs": [ref_id],
            }
            unit = _unit_for_path(str(field_path))
            if unit:
                claim["unit"] = unit
            claims.append(claim)
    return claims, catalog
