"""Freeze authorized L6 inputs and verify local retrieval readiness, without LLM calls.

The output is a new evidence directory, never a production write root. A ready
preflight is necessary but does not authorize submissions or replace the live
controller's port, identity, budget, and cleanup checks.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.request


IDENTITY_FIELDS = (
    "source_revision",
    "source_dirty",
    "loaded_code_root",
    "loaded_tree_fingerprint",
    "code_matches_repo",
    "users_dir",
    "agent_runtime",
)


def digest(path: Path) -> dict:
    h = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return {"bytes": path.stat().st_size, "sha256": h.hexdigest()}


def dump(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, default=str)
        handle.write("\n")


def manifest(root: Path) -> dict:
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("symlink is not a frozen input")
        if path.is_file():
            result[str(path.relative_to(root))] = digest(path)
    return result


def clone(source: Path, destination: Path) -> dict:
    if destination.exists() or destination.is_symlink():
        raise ValueError("refuse to overwrite frozen input")
    before = digest(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # macOS copy-on-write clone: independent inode without duplicating disk blocks.
    subprocess.run(
        ["/bin/cp", "-c", str(source), str(destination)],
        check=True,
        capture_output=True,
    )
    if before != digest(source) or before != digest(destination):
        raise RuntimeError("input changed during clone")
    if source.stat().st_ino == destination.stat().st_ino:
        raise RuntimeError("clone is not independent")
    destination.chmod(0o444)
    return before


def code_identity(code: Path, revision: str) -> dict:
    def git(*args):
        return subprocess.check_output(
            ["git", "-C", str(code), *args], text=True
        ).strip()

    result = {
        "revision": git("rev-parse", "HEAD"),
        "dirty": bool(git("status", "--porcelain")),
    }
    if result != {"revision": revision, "dirty": False}:
        raise RuntimeError("candidate identity mismatch")
    return result


def production_health() -> dict:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open("http://127.0.0.1:8792/api/health", timeout=15) as response:
        health = json.load(response)
    if not all(key in health.get("runtime", {}) for key in IDENTITY_FIELDS):
        raise ValueError("production identity fields missing")
    return health


def validate_authorization(protocol: dict) -> None:
    if protocol.get("authorization", {}).get("approved") is not True:
        raise ValueError("authorization missing")
    if protocol.get("baseline", {}).get("amendment_approved") is not True:
        raise ValueError("candidate-first amendment missing")
    limits = protocol["limits"]
    expected = {
        "question_count": 3,
        "initial_submissions_per_question": 1,
        "resubmissions": 0,
        "followups": 0,
        "merge_main": False,
        "deploy": False,
        "change_production": False,
    }
    if any(limits.get(key) != value for key, value in expected.items()):
        raise ValueError("authorization scope mismatch")
    questions = protocol["questions"]
    if len(questions) != 3 or len({q["id"] for q in questions}) != 3:
        raise ValueError("question count or IDs changed")
    for question in questions:
        if (
            hashlib.sha256(question["text"].encode()).hexdigest()
            != question["text_sha256"]
        ):
            raise ValueError("question hash mismatch")


def freeze_data(source: Path, output: Path, code: Path) -> dict:
    import duckdb

    source_db = source / "db/market_feature_store.duckdb"
    wal = source_db.with_suffix(".duckdb.wal")
    if wal.exists():
        raise RuntimeError("source database has active WAL")
    target = output / "data/db/market_feature_store.duckdb"
    database_hash = clone(source_db, target)
    if wal.exists():
        raise RuntimeError("source database WAL appeared during clone")
    con = duckdb.connect(str(target), read_only=True)
    try:
        tables = con.execute(
            "SELECT DISTINCT table_name FROM information_schema.columns WHERE table_schema='main' AND column_name='trade_date' AND starts_with(table_name,'fact_') ORDER BY table_name"
        ).fetchall()
        freshness = {}
        for (table,) in tables:
            if re.fullmatch(r"fact_[a-z0-9_]+", table) is None:
                raise ValueError("invalid canonical table name")
            count, low, high = con.execute(
                f'SELECT count(*), min(trade_date), max(trade_date) FROM "{table}"'
            ).fetchone()
            freshness[table] = {
                "rows": count,
                "min_trade_date": str(low) if low else None,
                "max_trade_date": str(high) if high else None,
            }
    finally:
        con.close()
    selected = {}
    for relative in ("market_snapshot", "market_feature_store/exports"):
        folder = source / relative
        for path in sorted(folder.rglob("*")):
            if path.is_symlink():
                raise ValueError("source snapshot symlink requires explicit policy")
            if path.is_file():
                selected[str(path)] = clone(
                    path, output / "data" / relative / path.relative_to(folder)
                )
    sys.path.insert(0, str(code))
    from intelligence.services.market_snapshot_contract import (
        validate_market_snapshot_root,
    )

    contract = validate_market_snapshot_root(output / "data/market_snapshot")
    dump(output / "snapshot-contract.json", contract)
    if not contract["ready"]:
        raise RuntimeError("frozen market snapshot contract failed")
    snapshot_day = str(
        contract["summary"].get("served_trade_date") or contract.get("date") or ""
    )[:10]
    if (
        not snapshot_day
        or freshness["fact_market_daily"]["max_trade_date"] < snapshot_day
    ):
        raise RuntimeError("snapshot newer than canonical market database")
    result = {
        "database": database_hash,
        "freshness": freshness,
        "snapshot_date": snapshot_day,
        "source_db": str(source_db),
        "snapshot_files": selected,
        "kb_external_inputs_frozen": False,
    }
    dump(output / "frozen-data.json", result)
    dump(output / "frozen-data-manifest.json", manifest(output / "data"))
    return result


def retrieval_probe(python: Path, kb: Path, model: Path, output: Path) -> dict:
    worker = Path(__file__).with_name("retrieval_readiness_worker.py")
    started = time.monotonic()
    env = {
        "HOME": str(Path.home()),
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "RAG_BGE_MODEL": str(model),
        "PYTHONDONTWRITEBYTECODE": "1",
        "HF_HUB_DISABLE_PROGRESS_BARS": "1",
        "TRANSFORMERS_VERBOSITY": "error",
        "TQDM_DISABLE": "1",
    }
    with (output / "retrieval-probe.log").open("xb") as log:
        try:
            process = subprocess.run(
                [str(python), "-u", "-B", str(worker), str(kb / "skills/lib")],
                env=env,
                cwd=kb,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=120,
            )
            code = process.returncode
        except subprocess.TimeoutExpired:
            code = 124
    events = []
    for line in (output / "retrieval-probe.log").read_text(errors="replace").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict) and "event" in event:
            events.append(event)
    complete = [event for event in events if event["event"] == "complete"]
    valid = len(complete) == 1 and complete[0].get("ready") is True and complete[0].get("shape") == [1, 1024]
    result = {
        "ready": code == 0 and valid and events[-1].get("event") == "complete",
        "exit_code": code,
        "timeout_seconds": 120,
        "wall_elapsed_seconds": round(time.monotonic() - started, 6),
        "last_event": events[-1] if events else None,
        "events": events,
        "worker": digest(worker),
        "model_path": str(model),
        "offline": True,
        "downloads": False,
        "paid_model_requests": 0,
        "model_weights_present": any(
            (model / name).is_file()
            for name in ("pytorch_model.bin", "model.safetensors")
        ),
        "log": digest(output / "retrieval-probe.log"),
    }
    dump(output / "retrieval-probe.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "protocol",
        "output",
        "code-root",
        "source-root",
        "kb-root",
        "rag-python",
        "rag-model",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    protocol = json.loads(args.protocol.read_text())
    validate_authorization(protocol)
    revision = protocol["baseline"]["premerge_candidate_revision"]
    identity = code_identity(args.code_root, revision)
    args.output.mkdir(parents=True, exist_ok=False)
    before = production_health()
    dump(args.output / "production-health-before.json", before)
    dump(args.output / "protocol.json", protocol)
    result = {
        "at": datetime.now(timezone.utc).isoformat(),
        "revision": revision,
        "authorization_valid": True,
        "new_model_requests": 0,
        "financial_submissions": 0,
        "sidecar_started": False,
        "data_frozen": False,
    }
    try:
        data = freeze_data(args.source_root, args.output, args.code_root)
        result.update(data_frozen=True, snapshot_date=data["snapshot_date"])
        retrieval = retrieval_probe(
            args.rag_python, args.kb_root, args.rag_model, args.output
        )
        result["verdict"] = (
            "PREFLIGHT_READY" if retrieval["ready"] else "BLOCKED_RETRIEVAL_DEPENDENCY"
        )
    except Exception as exc:
        result.update(verdict="BLOCKED_PREFLIGHT", error_type=type(exc).__name__)
        raise
    finally:
        after = production_health()
        dump(args.output / "production-health-after.json", after)
        same = {
            key: before["runtime"][key] == after["runtime"][key]
            for key in IDENTITY_FIELDS
        }
        frozen = args.output / "frozen-data-manifest.json"
        unchanged = (
            json.loads(frozen.read_text()) == manifest(args.output / "data")
            if frozen.exists()
            else None
        )
        code_stable = code_identity(args.code_root, revision) == identity
        dump(
            args.output / "closure.json",
            {
                "scope": "preparation only; no sidecar or model request",
                "production_identity_unchanged": same,
                "frozen_data_unchanged": unchanged,
                "code_identity_unchanged": code_stable,
                "sidecars_started": 0,
                "locks_acquired": 0,
            },
        )
        if not all(same.values()) or unchanged is not True or not code_stable:
            result["verdict"] = "BLOCKED_CLOSURE"
        dump(args.output / "audit.json", result)
    print(json.dumps(result))
    return int(result["verdict"] != "PREFLIGHT_READY")


if __name__ == "__main__":
    raise SystemExit(main())
