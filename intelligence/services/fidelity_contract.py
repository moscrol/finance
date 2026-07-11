from __future__ import annotations

import hashlib
import json
import re
import subprocess
from copy import deepcopy
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo


CONTRACT_SCHEMA_VERSION = "fidelity-contract-1.2"
CLAIM_MANIFEST_SCHEMA_VERSION = "claim-manifest-1.2"
PIT_SNAPSHOT_SCHEMA_VERSION = "pit-daily-snapshot-1.2"
PIT_MANIFEST_SCHEMA_VERSION = "pit-daily-manifest-1.2"
LOCAL_TIMEZONE = ZoneInfo("Asia/Shanghai")

REQUIRED_TIME_FIELDS = (
    "report_generated_at",
    "evidence_cutoff",
    "decision_cutoff",
    "snapshot_captured_at",
)
REQUIRED_PROVENANCE_FIELDS = (
    "generator_commit",
    "run_id",
    "artifact_sha",
    "manifest_sha",
)
REQUIRED_CONTRACT_FIELDS = REQUIRED_TIME_FIELDS + REQUIRED_PROVENANCE_FIELDS
_MANIFEST_CONTRACT_FIELDS = (
    "fidelity_contract_version",
    *REQUIRED_TIME_FIELDS,
    "generator_commit",
    "run_id",
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_PUBLIC_REPORT_ROOTS = (
    "date",
    "ledger",
    "logic_batch",
    "decision",
    "semantic_rag",
    "research_judge",
    "research_queue",
    "kb_ingest_queue",
    "catalyst_attribution",
    "logic_effectiveness",
    "evidence_catalog",
    "next_actions",
    "notes",
)


def canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def sha256_value(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def git_commit(root: str | Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(Path(root).expanduser()), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def parse_timestamp(value: object) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise ValueError("timestamp is required")
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=LOCAL_TIMEZONE)
    return parsed.astimezone(timezone.utc)


def report_cutoffs(
    report_date: str,
    *,
    snapshot_captured_at: str,
    report_generated_at: str,
) -> dict[str, str]:
    captured = parse_timestamp(snapshot_captured_at)
    end_of_day = datetime.combine(
        datetime.fromisoformat(report_date).date(),
        time(23, 59, 59, 999999),
        tzinfo=LOCAL_TIMEZONE,
    ).astimezone(timezone.utc)
    evidence = min(captured, end_of_day)
    generated = parse_timestamp(report_generated_at)
    return {
        "report_generated_at": generated.astimezone(LOCAL_TIMEZONE).isoformat(),
        "evidence_cutoff": evidence.astimezone(LOCAL_TIMEZONE).isoformat(),
        "decision_cutoff": generated.astimezone(LOCAL_TIMEZONE).isoformat(),
        "snapshot_captured_at": captured.astimezone(LOCAL_TIMEZONE).isoformat(),
    }


def build_run_id(
    artifact_kind: str,
    report_date: str,
    generator_commit: str,
    report_generated_at: str,
) -> str:
    digest = sha256_value(
        {
            "artifact_kind": artifact_kind,
            "report_date": report_date,
            "generator_commit": generator_commit,
            "report_generated_at": report_generated_at,
        }
    )
    return f"{artifact_kind}-{digest[:20]}"


def _walk_public(
    value: object,
    location: str,
) -> Iterable[tuple[str, object]]:
    if isinstance(value, dict):
        for key in sorted(value):
            if str(key).startswith("_"):
                continue
            yield from _walk_public(value[key], f"{location}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk_public(item, f"{location}[{index}]")
    elif value is not None and value != "":
        yield location, value


def public_narratives(report: dict[str, Any]) -> list[dict[str, object]]:
    narratives: list[dict[str, object]] = []
    for root in _PUBLIC_REPORT_ROOTS:
        if root not in report:
            continue
        for location, value in _walk_public(report[root], f"$.{root}"):
            text = str(value)
            key = sha256_value({"location": location, "text": text})
            narratives.append(
                {
                    "narrative_key": key,
                    "location": location,
                    "text": text,
                    "value": value,
                }
            )
    return narratives


def build_claim_manifest_metadata(
    report: dict[str, Any],
    claims: list[dict[str, object]],
) -> dict[str, object]:
    narratives = public_narratives(report)
    return {
        "schema_version": CLAIM_MANIFEST_SCHEMA_VERSION,
        "claim_count": len(claims),
        "public_narrative_count": len(narratives),
        "public_narrative_sha": sha256_value(narratives),
        "complete": True,
    }


def artifact_payload(body: dict[str, Any]) -> dict[str, Any]:
    payload = deepcopy(body)
    payload.pop("artifact_sha", None)
    return payload


def manifest_envelope(
    body: dict[str, Any],
    manifest_payload: object,
) -> dict[str, object]:
    return {
        "contract": {
            field: body.get(field)
            for field in _MANIFEST_CONTRACT_FIELDS
        },
        "manifest": manifest_payload,
    }


def seal_artifact(
    body: dict[str, Any],
    *,
    artifact_kind: str,
    report_date: str,
    generator_commit: str,
    snapshot_captured_at: str,
    report_generated_at: str,
    manifest_payload: object,
    run_id: str | None = None,
) -> dict[str, Any]:
    body["fidelity_contract_version"] = CONTRACT_SCHEMA_VERSION
    body.update(
        report_cutoffs(
            report_date,
            snapshot_captured_at=snapshot_captured_at,
            report_generated_at=report_generated_at,
        )
    )
    body["generator_commit"] = generator_commit
    body["run_id"] = run_id or build_run_id(
        artifact_kind,
        report_date,
        generator_commit,
        body["report_generated_at"],
    )
    body["manifest_sha"] = sha256_value(
        manifest_envelope(body, manifest_payload)
    )
    body["artifact_sha"] = sha256_value(artifact_payload(body))
    return body


def manifest_errors(
    report: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    claims = report.get("claims")
    catalog = report.get("evidence_catalog")
    metadata = report.get("claim_manifest")
    if not isinstance(claims, list) or not claims:
        errors.append("claims must be a non-empty list")
        claims = []
    if not isinstance(catalog, dict):
        errors.append("evidence_catalog must be an object")
        catalog = {}
    if not isinstance(metadata, dict):
        errors.append("claim_manifest must be an object")
        metadata = {}

    narratives = public_narratives(report)
    expected_narratives = {
        str(item["narrative_key"]): item
        for item in narratives
    }
    claim_ids: set[str] = set()
    manifested_narratives: set[str] = set()
    for index, claim in enumerate(claims):
        if not isinstance(claim, dict):
            errors.append(f"claims[{index}] must be an object")
            continue
        claim_id = str(claim.get("claim_id") or "")
        if not claim_id:
            errors.append(f"claims[{index}] missing claim_id")
        elif claim_id in claim_ids:
            errors.append(f"duplicate claim_id: {claim_id}")
        claim_ids.add(claim_id)
        narrative_key = str(claim.get("narrative_key") or "")
        if narrative_key:
            manifested_narratives.add(narrative_key)
            expected = expected_narratives.get(narrative_key)
            if expected is None:
                errors.append(
                    f"{claim_id or index} has unexpected narrative key"
                )
            elif (
                claim.get("location") != expected["location"]
                or claim.get("text") != expected["text"]
                or claim.get("value") != expected["value"]
            ):
                errors.append(
                    f"{claim_id or index} narrative payload mismatch"
                )
        refs = claim.get("evidence_refs") or []
        if not isinstance(refs, list):
            errors.append(f"{claim_id or index} evidence_refs must be a list")
            continue
        for ref in refs:
            if str(ref) not in catalog:
                errors.append(
                    f"{claim_id or index} references missing evidence {ref}"
                )

    required = set(expected_narratives)
    missing = sorted(required - manifested_narratives)
    if missing:
        errors.append(
            f"{len(missing)} public narratives missing from claim manifest"
        )
    if metadata.get("schema_version") != CLAIM_MANIFEST_SCHEMA_VERSION:
        errors.append("claim manifest schema mismatch")
    if metadata.get("public_narrative_count") != len(narratives):
        errors.append("claim manifest narrative count mismatch")
    if metadata.get("public_narrative_sha") != sha256_value(narratives):
        errors.append("claim manifest narrative hash mismatch")
    if metadata.get("claim_count") != len(claims):
        errors.append("claim manifest claim count mismatch")
    if metadata.get("complete") is not True:
        errors.append("claim manifest is not complete")
    return errors


def contract_errors(
    body: dict[str, Any],
    *,
    manifest_payload: object,
    expected_generator_commit: str | None = None,
    require_claim_manifest: bool = False,
) -> list[str]:
    errors: list[str] = []
    if body.get("fidelity_contract_version") != CONTRACT_SCHEMA_VERSION:
        errors.append("fidelity contract schema mismatch")
    for field in REQUIRED_CONTRACT_FIELDS:
        if not body.get(field):
            errors.append(f"missing {field}")
    timestamps: dict[str, datetime] = {}
    for field in REQUIRED_TIME_FIELDS:
        if not body.get(field):
            continue
        try:
            timestamps[field] = parse_timestamp(body[field])
        except (TypeError, ValueError):
            errors.append(f"invalid {field}")
    evidence = timestamps.get("evidence_cutoff")
    decision = timestamps.get("decision_cutoff")
    captured = timestamps.get("snapshot_captured_at")
    generated = timestamps.get("report_generated_at")
    if evidence and decision and evidence > decision:
        errors.append("evidence_cutoff is after decision_cutoff")
    if evidence and captured and evidence > captured:
        errors.append("evidence_cutoff is after snapshot_captured_at")
    if decision and generated and decision > generated:
        errors.append("decision_cutoff is after report_generated_at")
    if captured and generated and captured > generated:
        errors.append("snapshot_captured_at is after report_generated_at")

    commit = str(body.get("generator_commit") or "")
    if commit and not _COMMIT.fullmatch(commit):
        errors.append("generator_commit must be a full git SHA")
    if expected_generator_commit and commit != expected_generator_commit:
        errors.append("generator_commit mismatch")
    for field in ("artifact_sha", "manifest_sha"):
        value = str(body.get(field) or "")
        if value and not _SHA256.fullmatch(value):
            errors.append(f"{field} must be sha256")
    if body.get("manifest_sha") and body.get("manifest_sha") != sha256_value(
        manifest_envelope(body, manifest_payload)
    ):
        errors.append("manifest_sha mismatch")
    if body.get("artifact_sha") and body.get("artifact_sha") != sha256_value(
        artifact_payload(body)
    ):
        errors.append("artifact_sha mismatch")

    catalog = body.get("evidence_catalog")
    if isinstance(catalog, dict) and evidence:
        for evidence_id, source in catalog.items():
            if not isinstance(source, dict):
                continue
            source_time = (
                source.get("source_published_at")
                or source.get("source_time")
                or source.get("known_at")
            )
            if not source_time:
                continue
            try:
                if parse_timestamp(source_time) > evidence:
                    errors.append(
                        f"evidence {evidence_id} is after evidence_cutoff"
                    )
            except (TypeError, ValueError):
                errors.append(f"evidence {evidence_id} has invalid source time")
    if require_claim_manifest:
        errors.extend(manifest_errors(body))
    return errors


def report_manifest_payload(report: dict[str, Any]) -> dict[str, object]:
    return {
        "claim_manifest": report.get("claim_manifest"),
        "claims": report.get("claims"),
        "evidence_catalog": report.get("evidence_catalog"),
        "input_artifacts": report.get("input_artifacts"),
    }


def validate_daily_agent_report(
    report: dict[str, Any],
    *,
    expected_generator_commit: str | None = None,
) -> list[str]:
    errors = contract_errors(
        report,
        manifest_payload=report_manifest_payload(report),
        expected_generator_commit=expected_generator_commit,
        require_claim_manifest=True,
    )
    try:
        generated_at_matches = parse_timestamp(
            report.get("generated_at")
        ) == parse_timestamp(report.get("report_generated_at"))
    except (TypeError, ValueError):
        generated_at_matches = False
    if not generated_at_matches:
        errors.append("generated_at does not match report_generated_at")
    input_artifacts = report.get("input_artifacts")
    if not isinstance(input_artifacts, list) or not input_artifacts:
        errors.append("input_artifacts missing")
    else:
        for index, artifact in enumerate(input_artifacts):
            if not isinstance(artifact, dict):
                errors.append(f"input_artifacts[{index}] is invalid")
                continue
            if artifact.get("contract_valid") is not True:
                errors.append(
                    f"input_artifacts[{index}] contract invalid"
                )
    return errors


def provenance_marker(body: dict[str, Any]) -> str:
    return (
        f"fidelity_contract={body.get('fidelity_contract_version')} "
        f"run_id={body.get('run_id')} "
        f"artifact_sha={body.get('artifact_sha')} "
        f"manifest_sha={body.get('manifest_sha')}"
    )


def rendered_output_errors(
    report: dict[str, Any],
    *,
    markdown: str,
    html: str,
    expected_markdown: str | None = None,
) -> list[str]:
    marker = provenance_marker(report)
    errors: list[str] = []
    if f"<!-- {marker} -->" not in markdown:
        errors.append("markdown provenance marker mismatch")
    if f'<meta name="fidelity-contract" content="{marker}">' not in html:
        errors.append("html provenance marker mismatch")
    if expected_markdown is not None and markdown != expected_markdown:
        errors.append("markdown content does not match canonical report")
    return errors
