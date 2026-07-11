from __future__ import annotations

import json
import subprocess
from pathlib import Path

from intelligence.eval.pit_snapshot import validate_frozen_snapshot
from intelligence.services.fidelity_contract import (
    CONTRACT_SCHEMA_VERSION,
    LOCAL_TIMEZONE,
    PIT_MANIFEST_SCHEMA_VERSION,
    parse_timestamp,
    validate_daily_agent_report,
)

STATUS_SCHEMA_VERSION = "fidelity-runtime-status-1.2"


def _read_json(path: Path) -> dict[str, object]:
    body = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(body, dict):
        raise ValueError(f"expected JSON object: {path}")
    return body


def git_runtime_status(code_root: str | Path) -> dict[str, object]:
    root = Path(code_root).expanduser().resolve()
    commit = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    dirty_paths = [
        line[3:]
        for line in subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        if line.strip()
    ]
    return {
        "code_root": str(root),
        "commit": commit,
        "clean": not dirty_paths,
        "dirty_paths": dirty_paths,
    }


def daily_agent_status(
    data_root: str | Path,
    report_date: str,
) -> dict[str, object]:
    path = (
        Path(data_root).expanduser()
        / "market_feature_store"
        / "exports"
        / f"{report_date}-daily-agent.json"
    )
    if not path.is_file():
        return {
            "path": str(path),
            "exists": False,
            "lineage_ready": False,
        }
    body = _read_json(path)
    claims = body.get("claims")
    catalog = body.get("evidence_catalog")
    input_artifacts = body.get("input_artifacts")
    claim_count = len(claims) if isinstance(claims, list) else 0
    evidence_count = len(catalog) if isinstance(catalog, dict) else 0
    contract_validation = validate_daily_agent_report(body)
    knowledge_snapshot = body.get("knowledge_snapshot")
    if not isinstance(knowledge_snapshot, dict):
        knowledge_snapshot = {}
    upstream_complete = bool(
        isinstance(input_artifacts, list)
        and input_artifacts
        and all(
            isinstance(artifact, dict)
            and artifact.get("contract_valid") is True
            for artifact in input_artifacts
        )
    )
    try:
        generated_local_date = (
            parse_timestamp(body.get("report_generated_at"))
            .astimezone(LOCAL_TIMEZONE)
            .date()
            .isoformat()
        )
    except (TypeError, ValueError):
        generated_local_date = None
    return {
        "path": str(path),
        "exists": True,
        "generated_at": body.get("generated_at"),
        "lineage_schema_version": body.get("lineage_schema_version"),
        "claim_count": claim_count,
        "evidence_count": evidence_count,
        "fidelity_contract_version": body.get(
            "fidelity_contract_version"
        ),
        "report_generated_at": body.get("report_generated_at"),
        "evidence_cutoff": body.get("evidence_cutoff"),
        "decision_cutoff": body.get("decision_cutoff"),
        "snapshot_captured_at": body.get("snapshot_captured_at"),
        "generator_commit": body.get("generator_commit"),
        "run_id": body.get("run_id"),
        "artifact_sha": body.get("artifact_sha"),
        "manifest_sha": body.get("manifest_sha"),
        "knowledge_snapshot_artifact_sha": knowledge_snapshot.get(
            "artifact_sha"
        ),
        "knowledge_snapshot_base_commit": knowledge_snapshot.get(
            "base_commit"
        ),
        "knowledge_snapshot_dirty": knowledge_snapshot.get("dirty"),
        "contract_errors": contract_validation,
        "contract_ready": not contract_validation,
        "upstream_complete": upstream_complete,
        "forward_generated": generated_local_date == report_date,
        "lineage_ready": (
            body.get("lineage_schema_version") == "claim-lineage-v1"
            and claim_count > 0
            and evidence_count > 0
        ),
    }


def pit_manifest_status(
    snapshot_dir: str | Path,
    as_of: str,
) -> dict[str, object]:
    path = Path(snapshot_dir).expanduser() / f"{as_of}.manifest.json"
    if not path.is_file():
        return {
            "path": str(path),
            "exists": False,
            "schema_ready": False,
        }
    try:
        body = validate_frozen_snapshot(snapshot_dir, as_of)
        validation_errors: list[str] = []
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        body = _read_json(path)
        validation_errors = [str(exc)]
    repositories = body.get("repositories")
    if not isinstance(repositories, dict):
        repositories = {}
    return {
        "path": str(path),
        "exists": True,
        "schema_version": body.get("schema_version"),
        "status": body.get("status"),
        "replay_eligible": body.get("replay_eligible"),
        "capture_root": body.get("capture_root"),
        "fidelity_contract_version": body.get(
            "fidelity_contract_version"
        ),
        "report_generated_at": body.get("report_generated_at"),
        "evidence_cutoff": body.get("evidence_cutoff"),
        "decision_cutoff": body.get("decision_cutoff"),
        "snapshot_captured_at": body.get("snapshot_captured_at"),
        "generator_commit": body.get("generator_commit"),
        "run_id": body.get("run_id"),
        "artifact_sha": body.get("artifact_sha"),
        "manifest_sha": body.get("manifest_sha"),
        "upstream_daily_agent": body.get("upstream_daily_agent"),
        "wiki_content_delta": repositories.get("wiki_content_delta"),
        "validation_errors": validation_errors,
        "schema_ready": (
            body.get("schema_version") == PIT_MANIFEST_SCHEMA_VERSION
            and body.get("fidelity_contract_version")
            == CONTRACT_SCHEMA_VERSION
        ),
        "contract_ready": not validation_errors,
    }


def build_runtime_status(
    *,
    code_root: str | Path,
    data_root: str | Path,
    snapshot_dir: str | Path,
    report_date: str,
) -> dict[str, object]:
    runtime = git_runtime_status(code_root)
    daily_agent = daily_agent_status(data_root, report_date)
    pit_manifest = pit_manifest_status(snapshot_dir, report_date)
    upstream = pit_manifest.get("upstream_daily_agent")
    provenance_linked = bool(
        isinstance(upstream, dict)
        and upstream.get("status") == "valid"
        and upstream.get("run_id") == daily_agent.get("run_id")
        and upstream.get("artifact_sha") == daily_agent.get("artifact_sha")
        and upstream.get("manifest_sha") == daily_agent.get("manifest_sha")
        and upstream.get("generator_commit")
        == daily_agent.get("generator_commit")
        and pit_manifest.get("report_generated_at")
        == daily_agent.get("report_generated_at")
        and pit_manifest.get("evidence_cutoff")
        == daily_agent.get("evidence_cutoff")
        and pit_manifest.get("decision_cutoff")
        == daily_agent.get("decision_cutoff")
        and upstream.get("daily_snapshot_captured_at")
        == daily_agent.get("snapshot_captured_at")
        and upstream.get("knowledge_snapshot_artifact_sha")
        == daily_agent.get("knowledge_snapshot_artifact_sha")
        and (pit_manifest.get("wiki_content_delta") or {}).get(
            "artifact_sha"
        )
        == daily_agent.get("knowledge_snapshot_artifact_sha")
    )
    generator_commit_matches = bool(
        runtime["commit"]
        and runtime["commit"] == daily_agent.get("generator_commit")
        and runtime["commit"] == pit_manifest.get("generator_commit")
    )
    capture_ready = bool(
        runtime["clean"]
        and daily_agent["lineage_ready"]
        and daily_agent.get("contract_ready")
        and daily_agent.get("upstream_complete")
        and daily_agent.get("forward_generated")
        and pit_manifest["schema_ready"]
        and pit_manifest.get("contract_ready")
        and provenance_linked
        and generator_commit_matches
    )
    return {
        "schema_version": STATUS_SCHEMA_VERSION,
        "report_date": report_date,
        "runtime": runtime,
        "daily_agent": daily_agent,
        "pit_manifest": pit_manifest,
        "provenance_linked": provenance_linked,
        "generator_commit_matches": generator_commit_matches,
        "capture_ready": capture_ready,
        "replay_ready": (
            capture_ready and pit_manifest["replay_eligible"] is True
        ),
        "decision_eligible": False,
    }
