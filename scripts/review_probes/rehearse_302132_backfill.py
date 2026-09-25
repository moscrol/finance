#!/usr/bin/env python3
"""Rehearse #83 on fresh full DB clones, never publish to the input database.

No network or production write path. Requires a clean checkout, immutable source
files without WAL, and a new external output directory. Failed runs retain their
copies; successful runs remove only database files created in that directory.
All reports, receipts, frozen parquet and command logs remain for inspection.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

import duckdb

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from market_feature_store import db  # noqa: E402
from market_feature_store.sync.repair_backfill_stock_history import (  # noqa: E402
    BackfillSpec,
    _code_revision,
    _sha256,
)


def save(path: Path, payload: dict) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, default=str)
        stream.write("\n")


def snapshot(path: Path) -> dict:
    stat = path.stat()
    with duckdb.connect(str(path), read_only=True) as con:
        tables = con.execute(
            "SELECT table_name FROM information_schema.columns "
            "WHERE table_schema='main' AND column_name='trade_date' "
            "AND starts_with(table_name, 'fact_') ORDER BY table_name"
        ).fetchall()
        freshness = {
            table: str(con.execute(
                'SELECT max(trade_date) FROM "' + table.replace('"', '""') + '"'
            ).fetchone()[0]) for (table,) in tables
        }
    return {"path": str(path), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns,
            "inode": stat.st_ino, "freshness": freshness}


def value_audit(path: Path, spec: BackfillSpec) -> dict:
    with duckdb.connect(str(path), read_only=True) as con:
        rows = con.execute(
            "SELECT trade_date, close, pct_chg, amount FROM fact_stock_daily "
            "WHERE stock_ts_code=? AND trade_date BETWEEN ? AND ? ORDER BY 1",
            [spec.code, spec.window_start, spec.window_end],
        ).fetchall()
    return {
        "rows": len(rows),
        "non_null": {key: sum(row[i] is not None for row in rows)
                     for i, key in enumerate(("date", "close", "pct_chg", "amount")) if i},
        "identical_adjacent_values": [str(b[0]) for a, b in zip(rows, rows[1:])
                                     if a[1:] == b[1:]],
        "values": rows,
    }


def run(args: argparse.Namespace) -> int:
    revision, dirty = _code_revision()
    if dirty:
        raise ValueError("rehearsal requires a clean committed checkout")
    prod, parquet = args.production.expanduser().absolute(), args.parquet.expanduser().absolute()
    out = args.output.expanduser().absolute()
    for path in (prod, parquet):
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"input must be a regular non-symlink file: {path}")
    if (out.exists() or out.resolve().is_relative_to(ROOT)
            or out.resolve().is_relative_to(prod.parent.resolve())
            or prod.resolve().is_relative_to(out.resolve())
            or parquet.resolve().is_relative_to(out.resolve())):
        raise ValueError("output must be a new isolated external directory")
    if db.wal_path(prod).exists():
        raise ValueError("source WAL present; refuse a potentially moving baseline")
    spec = BackfillSpec()
    if _sha256(parquet) != spec.parquet_sha256:
        raise ValueError("frozen parquet does not match the authorized contract")
    out.mkdir(parents=True, exist_ok=False)
    result = {"revision": revision, "dirty": dirty, "commands": [], "ok": False}
    baseline, target = out / "baseline.duckdb", out / "copy.duckdb"
    frozen = out / "frozen.parquet"
    env = {k: os.environ[k] for k in ("HOME", "PATH", "LANG", "TMPDIR") if k in os.environ}
    env.update({"MARKET_FEATURE_STORE_DB": str(target),
                "MARKET_FEATURE_STORE_PRODUCTION_DB": str(prod),
                "PYTHONDONTWRITEBYTECODE": "1"})

    def command(label: str, argv: list[str], expected: int = 0) -> None:
        started = time.monotonic()
        record = {"label": label, "argv": argv, "expected_exit": expected}
        with (out / f"{label}.log.txt").open("xb") as log:
            try:
                with subprocess.Popen(argv, cwd=ROOT, env=env, stdout=log,
                                      stderr=subprocess.STDOUT,
                                      start_new_session=True) as process:
                    try:
                        code = process.wait(timeout=900)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
                        raise
                record["exit_code"] = code
            except subprocess.TimeoutExpired:
                record["timeout"] = True
                raise
            finally:
                record["seconds"] = round(time.monotonic() - started, 3)
                result["commands"].append(record)
                save(out / f"{label}.command.json", record)
        if code != expected:
            raise RuntimeError(f"{label}: exit {code}, expected {expected}")

    def parent(label: str, source: Path = frozen) -> dict:
        known = set(out.glob("copy.duckdb.repair-backfill-execution.*.json"))
        command(label, [sys.executable, "-m", "market_feature_store.cli",
                        "repair-backfill-302132", "--parquet", str(source)])
        created = set(out.glob("copy.duckdb.repair-backfill-execution.*.json")) - known
        if len(created) != 1:
            raise RuntimeError(f"{label}: expected exactly one new execution receipt")
        return json.loads(created.pop().read_text())

    try:
        result["production_before"] = snapshot(prod)
        result["free_bytes_before"] = shutil.disk_usage(out).free
        if result["free_bytes_before"] < max(8 * 1024**3, prod.stat().st_size * 2):
            raise RuntimeError("insufficient physical headroom for full-copy rehearsal")
        # Hold the existing read lock across clone and source identity validation.
        with db.hold_swap_lock(prod) as lock:
            stat_before = lock.stat()
            result["baseline_copy"] = db.clone_to_staging(prod, baseline)
            db.assert_same_target(prod, lock.identity, stage="rehearsal snapshot")
            if (lock.stat().st_mtime_ns, lock.stat().st_size) != (
                    stat_before.st_mtime_ns, stat_before.st_size):
                raise RuntimeError("production changed while freezing baseline")
        result["baseline_sha256"] = _sha256(baseline)
        shutil.copyfile(parquet, frozen)
        result["parquet_sha256"] = _sha256(frozen)
        result["target_copy"] = db.clone_to_staging(baseline, target)
        result["values_before"] = value_audit(target, spec)
        save(out / "frozen-inputs.json", result)

        wrong = out / "wrong.parquet"
        wrong.write_bytes(b"deliberately invalid frozen input for failure control\n")
        command("refused-parent", [sys.executable, "-m", "market_feature_store.cli",
                                  "repair-backfill-302132", "--parquet", str(wrong)], 2)
        if _sha256(target) != result["baseline_sha256"] or list(out.glob("*.bak-*")):
            raise RuntimeError("failed child published or produced a pre-swap backup")
        result["failure_did_not_publish"] = True
        applied = parent("apply")
        verified = parent("verify")
        result["runs"] = {"apply": applied["run_id"], "verify": verified["run_id"]}
        verifier = [sys.executable, str(ROOT / "scripts/verify_302132_backfill_acceptance.py"),
                    "--production", str(baseline), "--clone", str(target),
                    "--parquet", str(frozen), "--run-apply", applied["run_id"],
                    "--run-verify", verified["run_id"], "--expected-revision", revision,
                    "--expected-production-sha256", result["baseline_sha256"]]
        command("acceptance", verifier + ["--output", str(out / "acceptance.json")])
        result["values_after"] = value_audit(target, spec)
        before, after = result["values_before"], result["values_after"]
        if after["rows"] != spec.expected_total_rows or after["identical_adjacent_values"]:
            raise RuntimeError("date coverage or cross-date value audit failed")
        if any(after["non_null"][k] != after["rows"] or
               after["non_null"][k] / after["rows"] < before["non_null"][k] / before["rows"]
               for k in after["non_null"]):
            raise RuntimeError("required value coverage regressed or is incomplete")

        with duckdb.connect(str(target)) as con:
            con.execute("UPDATE fact_stock_daily SET amount=1e15 "
                        "WHERE stock_ts_code=? AND trade_date=?",
                        [spec.code, spec.gap_parallel[0]])
        command("amount-control", verifier + ["--output", str(out / "amount-control.json")], 2)
        failure = json.loads((out / "amount-control.json").read_text())
        if failure["failed"] != ["keyset_fullfield_oracle"]:
            raise RuntimeError(f"amount control failed for an unexpected reason: {failure['failed']}")

        # Restore only the rehearsal target, using the parent's actual backup.
        backup = Path(applied["backup"]["backup_path"])
        if backup.parent != out or _sha256(backup) != result["baseline_sha256"]:
            raise RuntimeError("rollback backup not owned by this run or identity mismatch")
        restore = out / "restore.duckdb"
        result["rollback_copy"] = db.clone_to_staging(backup, restore)
        os.replace(restore, target)
        result["rollback_sha256"] = _sha256(target)
        if result["rollback_sha256"] != result["baseline_sha256"]:
            raise RuntimeError("rollback did not restore exact original bytes")
        result["ok"] = True
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        try:
            result["production_after"] = snapshot(prod)
            result["production_unchanged"] = result["production_before"] == result["production_after"]
            result["production_sha256_after"] = _sha256(prod)
            result["production_unchanged"] &= (
                result["production_sha256_after"] == result.get("baseline_sha256"))
            result["code_identity_after"] = _code_revision()
            result["ok"] &= result["production_unchanged"] and _code_revision() == (revision, False)
        except Exception as exc:
            result["closure_error"] = f"{type(exc).__name__}: {exc}"
            result["ok"] = False
        if result["ok"]:
            removed = []
            for path in sorted(out.iterdir()):
                if path.suffix == ".duckdb" or (".duckdb.bak-" in path.name
                                                and not path.name.endswith(".json")):
                    removed.append({"name": path.name, "sha256": _sha256(path),
                                    "bytes": path.stat().st_size})
                    path.unlink()
            result["removed_rehearsal_copies"] = removed
        result["free_bytes_after"] = shutil.disk_usage(out).free
        save(out / "summary.json", result)
        files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in out.iterdir() if p.is_file() and p.suffix in (".json", ".txt", ".parquet")}
        save(out / "manifest.json", files)
    print(json.dumps({"ok": result["ok"], "error": result.get("error"), "output": str(out)}))
    return 0 if result["ok"] else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--production", type=Path, required=True)
    parser.add_argument("--parquet", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
