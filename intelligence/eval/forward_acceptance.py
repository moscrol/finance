from __future__ import annotations

import hashlib
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path


FORWARD_ACCEPTANCE_SCHEMA_VERSION = "fidelity-forward-acceptance-1.0"
FORWARD_ACCEPTANCE_SUMMARY_SCHEMA_VERSION = (
    "fidelity-forward-acceptance-summary-1.0"
)
GOLD_SAMPLING_MIN_DAYS = 5
GOLD_SAMPLING_MIN_CLAIMS = 150
ELIGIBILITY_OBSERVATION_MIN_DAYS = 10
ELIGIBILITY_OBSERVATION_TARGET_DAYS = 20


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _record_payload(record: dict[str, object]) -> dict[str, object]:
    return {
        key: value
        for key, value in record.items()
        if key != "record_sha256"
    }


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _blockers(status: dict[str, object]) -> list[str]:
    blockers: list[str] = []
    runtime = status.get("runtime")
    if not isinstance(runtime, dict):
        runtime = {}
    daily = status.get("daily_agent")
    if not isinstance(daily, dict):
        daily = {}
    pit = status.get("pit_manifest")
    if not isinstance(pit, dict):
        pit = {}
    checks = (
        ("runtime_dirty", runtime.get("clean") is not True),
        ("daily_agent_missing", daily.get("exists") is not True),
        ("daily_agent_lineage_invalid", daily.get("lineage_ready") is not True),
        ("daily_agent_contract_invalid", daily.get("contract_ready") is not True),
        ("daily_agent_upstream_incomplete", daily.get("upstream_complete") is not True),
        ("daily_agent_not_forward", daily.get("forward_generated") is not True),
        ("pit_manifest_missing", pit.get("exists") is not True),
        ("pit_schema_invalid", pit.get("schema_ready") is not True),
        ("pit_contract_invalid", pit.get("contract_ready") is not True),
        ("pit_not_replay_eligible", pit.get("replay_eligible") is not True),
        ("provenance_not_linked", status.get("provenance_linked") is not True),
        (
            "generator_commit_mismatch",
            status.get("generator_commit_matches") is not True,
        ),
        ("capture_not_ready", status.get("capture_ready") is not True),
        ("replay_not_ready", status.get("replay_ready") is not True),
    )
    for name, blocked in checks:
        if blocked:
            blockers.append(name)
    return blockers


def build_acceptance_record(
    status: dict[str, object],
    *,
    checked_at: str | None = None,
) -> dict[str, object]:
    report_date = status.get("report_date")
    if not isinstance(report_date, str) or not report_date:
        raise ValueError("runtime status requires report_date")
    date.fromisoformat(report_date)
    timestamp = checked_at or datetime.now(timezone.utc).isoformat()
    parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("checked_at must include timezone")
    daily = status.get("daily_agent")
    if not isinstance(daily, dict):
        daily = {}
    blockers = _blockers(status)
    record = {
        "schema_version": FORWARD_ACCEPTANCE_SCHEMA_VERSION,
        "report_date": report_date,
        "checked_at": parsed.isoformat(),
        "result": "accepted" if not blockers else "blocked",
        "capture_ready": status.get("capture_ready") is True,
        "replay_ready": status.get("replay_ready") is True,
        "decision_eligible": False,
        "claim_count": (
            int(daily.get("claim_count", 0))
            if isinstance(daily.get("claim_count", 0), int)
            else 0
        ),
        "blockers": blockers,
        "runtime_status": status,
    }
    record["record_sha256"] = _sha256(_record_payload(record))
    return record


def validate_acceptance_record(record: object) -> list[str]:
    if not isinstance(record, dict):
        return ["acceptance record must be an object"]
    errors: list[str] = []
    if record.get("schema_version") != FORWARD_ACCEPTANCE_SCHEMA_VERSION:
        errors.append("acceptance record schema mismatch")
    if not record.get("report_date"):
        errors.append("report_date is required")
    else:
        try:
            date.fromisoformat(str(record["report_date"]))
        except ValueError:
            errors.append("report_date is invalid")
    try:
        checked_at = datetime.fromisoformat(
            str(record.get("checked_at") or "").replace("Z", "+00:00")
        )
        if checked_at.tzinfo is None:
            errors.append("checked_at must include timezone")
    except ValueError:
        errors.append("checked_at is invalid")
    if record.get("result") not in {"accepted", "blocked"}:
        errors.append("result must be accepted or blocked")
    blockers = record.get("blockers")
    if not isinstance(blockers, list):
        errors.append("blockers must be a list")
        blockers = []
    expected_result = "accepted" if not blockers else "blocked"
    if record.get("result") != expected_result:
        errors.append("result does not match blockers")
    if record.get("decision_eligible") is not False:
        errors.append("decision_eligible must remain false")
    expected_sha = _sha256(_record_payload(record))
    if record.get("record_sha256") != expected_sha:
        errors.append("record_sha256 mismatch")
    return errors


def write_acceptance_record(
    output_root: str | Path,
    record: dict[str, object],
) -> Path:
    errors = validate_acceptance_record(record)
    if errors:
        raise ValueError("; ".join(errors))
    root = Path(output_root).expanduser()
    report_date = str(record["report_date"])
    checked_at = str(record["checked_at"])
    safe_timestamp = (
        checked_at.replace(":", "")
        .replace("+", "_")
        .replace("-", "")
        .replace(".", "_")
    )
    record_sha = str(record["record_sha256"])
    attempt_dir = root / "records" / report_date
    attempt_dir.mkdir(parents=True, exist_ok=True)
    attempt_path = attempt_dir / f"{safe_timestamp}-{record_sha[:12]}.json"
    encoded = json.dumps(record, ensure_ascii=False, indent=2) + "\n"
    try:
        with attempt_path.open("x", encoding="utf-8") as handle:
            handle.write(encoded)
    except FileExistsError:
        if attempt_path.read_text(encoding="utf-8") != encoded:
            raise FileExistsError("acceptance attempt already exists")
    latest_dir = root / "latest"
    latest_dir.mkdir(parents=True, exist_ok=True)
    latest_path = latest_dir / f"{report_date}.json"
    if latest_path.exists():
        latest = _read_record(latest_path)
        latest_errors = validate_acceptance_record(latest)
        if latest_errors:
            raise ValueError(
                "existing latest acceptance record is invalid: "
                + "; ".join(latest_errors)
            )
        latest_checked_at = datetime.fromisoformat(
            str(latest["checked_at"]).replace("Z", "+00:00")
        )
        record_checked_at = datetime.fromisoformat(
            checked_at.replace("Z", "+00:00")
        )
        if latest_checked_at > record_checked_at:
            return attempt_path
    temporary_path = latest_path.with_name(
        f".{latest_path.name}.{os.getpid()}.tmp"
    )
    temporary_path.write_text(encoded, encoding="utf-8")
    temporary_path.replace(latest_path)
    return attempt_path


def _read_record(path: Path) -> dict[str, object]:
    body = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(body, dict):
        raise ValueError(f"acceptance record must be an object: {path}")
    return body


def summarize_forward_acceptance(
    output_root: str | Path,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, object]:
    latest_root = Path(output_root).expanduser() / "latest"
    records: list[dict[str, object]] = []
    invalid_records: list[dict[str, object]] = []
    for path in sorted(latest_root.glob("*.json")):
        report_date = path.stem
        if start_date and report_date < start_date:
            continue
        if end_date and report_date > end_date:
            continue
        try:
            record = _read_record(path)
            errors = validate_acceptance_record(record)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            invalid_records.append(
                {"path": str(path), "errors": [str(exc)]}
            )
            continue
        if errors:
            invalid_records.append({"path": str(path), "errors": errors})
            continue
        records.append(record)
    accepted = [
        record for record in records if record.get("result") == "accepted"
    ]
    blocked = [
        record for record in records if record.get("result") == "blocked"
    ]
    accepted_claim_count = sum(
        int(record.get("claim_count", 0)) for record in accepted
    )
    accepted_day_count = len(accepted)
    return {
        "schema_version": FORWARD_ACCEPTANCE_SUMMARY_SCHEMA_VERSION,
        "start_date": start_date,
        "end_date": end_date,
        "record_count": len(records),
        "accepted_day_count": accepted_day_count,
        "blocked_day_count": len(blocked),
        "accepted_claim_count": accepted_claim_count,
        "accepted_dates": [
            str(record["report_date"]) for record in accepted
        ],
        "blocked_dates": [
            str(record["report_date"]) for record in blocked
        ],
        "invalid_records": invalid_records,
        "gold_sampling_ready": (
            accepted_day_count >= GOLD_SAMPLING_MIN_DAYS
            and accepted_claim_count >= GOLD_SAMPLING_MIN_CLAIMS
            and not blocked
            and not invalid_records
        ),
        "eligibility_observation_ready": (
            accepted_day_count >= ELIGIBILITY_OBSERVATION_MIN_DAYS
            and not blocked
            and not invalid_records
        ),
        "observation_target": {
            "minimum_days": ELIGIBILITY_OBSERVATION_MIN_DAYS,
            "target_days": ELIGIBILITY_OBSERVATION_TARGET_DAYS,
        },
        "decision_eligible": False,
    }
