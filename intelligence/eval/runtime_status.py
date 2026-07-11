from __future__ import annotations

import json
import subprocess
from pathlib import Path


STATUS_SCHEMA_VERSION = "fidelity-runtime-status-1.0"


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
    claim_count = len(claims) if isinstance(claims, list) else 0
    evidence_count = len(catalog) if isinstance(catalog, dict) else 0
    return {
        "path": str(path),
        "exists": True,
        "generated_at": body.get("generated_at"),
        "lineage_schema_version": body.get("lineage_schema_version"),
        "claim_count": claim_count,
        "evidence_count": evidence_count,
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
    body = _read_json(path)
    return {
        "path": str(path),
        "exists": True,
        "schema_version": body.get("schema_version"),
        "status": body.get("status"),
        "replay_eligible": body.get("replay_eligible"),
        "capture_root": body.get("capture_root"),
        "schema_ready": body.get("schema_version") == "pit-daily-manifest-1.1",
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
    capture_ready = bool(
        runtime["clean"]
        and daily_agent["lineage_ready"]
        and pit_manifest["schema_ready"]
    )
    return {
        "schema_version": STATUS_SCHEMA_VERSION,
        "report_date": report_date,
        "runtime": runtime,
        "daily_agent": daily_agent,
        "pit_manifest": pit_manifest,
        "capture_ready": capture_ready,
        "replay_ready": (
            capture_ready and pit_manifest["replay_eligible"] is True
        ),
    }
