"""Validated run catalog for the acceptance board."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping


class RunArtifactError(ValueError):
    """A stored acceptance run is malformed or conflicts with the case canon."""


@dataclass(frozen=True)
class SelectedCaseRun:
    """Newest stored execution selected for one canonical acceptance case."""

    case_id: str
    tier: str
    generated_at: str
    source_path: Path
    source_sha256: str
    run_record: Mapping[str, Any]
    case_run: Mapping[str, Any]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_validated_run(
    path: Path,
    case_tiers: Mapping[str, str],
) -> dict[str, Any]:
    """Load one immutable run artifact and validate its canonical case bindings."""

    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RunArtifactError(f"{path}: invalid JSON: {exc}") from exc

    if not isinstance(record, dict):
        raise RunArtifactError(f"{path}: run artifact must be a JSON object")

    generated_at = record.get("generated_at")
    if not isinstance(generated_at, str):
        raise RunArtifactError(f"{path}: generated_at must be a canonical UTC timestamp")
    try:
        parsed_generated_at = datetime.strptime(generated_at, "%Y%m%dT%H%M%SZ")
    except ValueError as exc:
        raise RunArtifactError(
            f"{path}: invalid generated_at {generated_at!r}; expected YYYYMMDDTHHMMSSZ"
        ) from exc
    if parsed_generated_at.strftime("%Y%m%dT%H%M%SZ") != generated_at:
        raise RunArtifactError(
            f"{path}: invalid generated_at {generated_at!r}; expected YYYYMMDDTHHMMSSZ"
        )

    cases = record.get("cases")
    if not isinstance(cases, list):
        raise RunArtifactError(f"{path}: cases must be a list")

    seen: set[str] = set()
    for index, case_run in enumerate(cases):
        if not isinstance(case_run, dict):
            raise RunArtifactError(f"{path}: cases[{index}] must be an object")
        case_id = case_run.get("case_id")
        tier = case_run.get("tier")
        if not isinstance(case_id, str) or not case_id:
            raise RunArtifactError(f"{path}: cases[{index}].case_id must be a string")
        if case_id in seen:
            raise RunArtifactError(f"{path}: duplicate case_id {case_id!r}")
        seen.add(case_id)
        if case_id not in case_tiers:
            raise RunArtifactError(f"{path}: unknown case_id {case_id!r}")
        expected_tier = case_tiers[case_id]
        if tier != expected_tier:
            raise RunArtifactError(
                f"{path}: tier mismatch for {case_id!r}: "
                f"got {tier!r}, expected {expected_tier!r}"
            )

    return record


def select_latest_case_runs(
    run_dir: Path,
    case_tiers: Mapping[str, str],
) -> dict[str, SelectedCaseRun]:
    """Select the newest stored occurrence of every canonical case."""

    selected: dict[str, SelectedCaseRun] = {}
    for path in sorted(run_dir.glob("*.json")):
        record = load_validated_run(path, case_tiers)
        # Legacy records predate the field and remain usable as historical
        # evidence.  A new formal record explicitly marked ineligible must not
        # silently replace a valid case in the board.
        if (
            "acceptance_eligible" in record
            and record.get("acceptance_eligible") is not True
        ):
            continue
        source_sha256 = sha256_file(path)
        for case_run in record["cases"]:
            case_id = case_run["case_id"]
            candidate = SelectedCaseRun(
                case_id=case_id,
                tier=case_run["tier"],
                generated_at=record["generated_at"],
                source_path=path,
                source_sha256=source_sha256,
                run_record=record,
                case_run=case_run,
            )
            previous = selected.get(case_id)
            if previous is None or (
                candidate.generated_at,
                candidate.source_path.name,
            ) > (previous.generated_at, previous.source_path.name):
                selected[case_id] = candidate
    return selected
