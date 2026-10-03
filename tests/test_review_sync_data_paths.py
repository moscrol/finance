"""Frozen nightly code must not become a storage root after a release.

Execute copied entrypoints against temporary data. Sync children are stopped at
the subprocess boundary; export tests use a tiny temporary DuckDB only.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

import duckdb
import pytest


ROOT = Path(__file__).resolve().parents[1]
DAY = "2026-10-02"


def _copy_script(code: Path, filename: str) -> Path:
    relative = Path("skills/daily-full-review/scripts") / filename
    target = code / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / relative, target)
    return target


def _load(path: Path):
    spec = importlib.util.spec_from_file_location("review_sync_data_paths", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {str(path.relative_to(root)): path.read_bytes()
            for path in root.rglob("*") if path.is_file()}


@pytest.mark.parametrize("root_env", ["FINANCE_DATA_ROOT", "FINANCE_WS", None])
@pytest.mark.parametrize("gate_failure", [False, True])
def test_sync_state_honors_data_root_on_success_and_failure(tmp_path, monkeypatch, root_env, gate_failure):
    code, data, decoy = (tmp_path / name for name in ("code", "data", "decoy"))
    script = _copy_script(code, "run_review_sync.py")
    monkeypatch.delenv("FINANCE_DATA_ROOT", raising=False)
    monkeypatch.delenv("FINANCE_WS", raising=False)
    if root_env:
        monkeypatch.setenv("FINANCE_WS", str(decoy))
        monkeypatch.setenv(root_env, str(data))
    else:
        data = code
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    module = _load(script)
    before = _tree_bytes(code)

    def child(argv, **kwargs):
        # All real child work is blocked. Simulate only its documented --json
        # output so the test observes files written to the chosen destination.
        if gate_failure and "scripts/check_daily_review_data.py" in argv:
            return subprocess.CompletedProcess(argv, 1)
        if "--json" in argv:
            output = Path(argv[argv.index("--json") + 1])
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps({"complete": True}), encoding="utf-8")
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(module.subprocess, "run", child)
    monkeypatch.setattr(sys, "argv", [str(script), "--date", DAY, "--only", "db-lock",
                                     "--skip-preflight", "--retry-rounds", "0", "--plan", "local"])
    assert module.main() == int(gate_failure)
    state = data / "skills/daily-full-review/state"
    assert "plan=local" in (state / "runlog.md").read_text()
    quality = state / f"quality-{DAY}.json"
    if gate_failure:
        assert not quality.exists()
        assert "INCOMPLETE" in (state / "runlog.md").read_text()
    else:
        assert json.loads(quality.read_text()) == {"complete": True}
    assert not decoy.exists()
    if root_env:
        assert _tree_bytes(code) == before
    else:
        # Legacy manual use still records state under its own checkout.
        assert {name: content for name, content in _tree_bytes(code).items()
                if not name.startswith("skills/daily-full-review/state/")} == before


def _tiny_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(path)) as con:
        con.execute("CREATE TABLE fact_market_daily(trade_date DATE, amount DOUBLE)")
        con.execute("INSERT INTO fact_market_daily VALUES (?, 123.0)", [DAY])


def test_increment_export_keeps_backup_out_of_frozen_code(tmp_path, monkeypatch):
    code, data = tmp_path / "code", tmp_path / "data"
    script = _copy_script(code, "export_increment.py")
    staging = data / "db/market_feature_store.staging.duckdb"
    _tiny_db(staging)
    monkeypatch.setenv("FINANCE_DATA_ROOT", str(data))
    monkeypatch.setenv("FINANCE_WS", str(tmp_path / "decoy"))
    monkeypatch.delenv("DUCKDB_SNAPSHOT_OUT_ROOT", raising=False)
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "1")
    before = _tree_bytes(code)

    result = subprocess.run([sys.executable, str(script), "--date", DAY, "--db", str(staging)],
                            cwd=code, env=os.environ.copy(), capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    backup = data / "db/snapshots/increments" / f"market_feature_store-inc-{DAY}.tar.gz"
    assert backup.is_file()
    with tarfile.open(backup) as archive:
        manifest_file = archive.extractfile("manifest.json")
        assert manifest_file is not None
        manifest = json.load(manifest_file)
    assert manifest["db"] == str(staging)
    assert manifest["total_rows"] == 1
    assert _tree_bytes(code) == before


@pytest.mark.parametrize("root_env", ["FINANCE_DATA_ROOT", "FINANCE_WS", None])
def test_export_defaults_read_the_same_data_root(tmp_path, monkeypatch, root_env):
    code = tmp_path / "code"
    script = _copy_script(code, "export_increment.py")
    data = tmp_path / "data" if root_env else code
    _tiny_db(data / "db/market_feature_store.duckdb")
    for key in ("FINANCE_DATA_ROOT", "FINANCE_WS", "MARKET_FEATURE_STORE_DB", "DUCKDB_SNAPSHOT_OUT_ROOT"):
        monkeypatch.delenv(key, raising=False)
    if root_env:
        monkeypatch.setenv(root_env, str(data))
    result = subprocess.run([sys.executable, str(script), "--date", DAY],
                            cwd=code, env=os.environ.copy(), capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert (data / "db/snapshots/increments" / f"market_feature_store-inc-{DAY}.tar.gz").is_file()


@pytest.mark.parametrize("explicit_cli", [False, True])
def test_export_preserves_explicit_database_and_destination(tmp_path, monkeypatch, explicit_cli):
    code, data = tmp_path / "code", tmp_path / "data"
    script = _copy_script(code, "export_increment.py")
    staging = tmp_path / "external-staging.duckdb"
    _tiny_db(staging)
    monkeypatch.setenv("FINANCE_DATA_ROOT", str(data))
    monkeypatch.setenv("MARKET_FEATURE_STORE_DB", str(staging))
    monkeypatch.setenv("DUCKDB_SNAPSHOT_OUT_ROOT", str(tmp_path / "configured-backups"))
    output = tmp_path / ("cli-backups" if explicit_cli else "configured-backups")
    argv = [sys.executable, str(script), "--date", DAY]
    if explicit_cli:
        # Explicit flags win even over existing environment configuration.
        monkeypatch.setenv("MARKET_FEATURE_STORE_DB", str(tmp_path / "missing.duckdb"))
        argv.extend(["--db", str(staging), "--out-root", str(output)])
    before = _tree_bytes(code)
    result = subprocess.run(argv, cwd=code, env=os.environ.copy(), capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert (output / "increments" / f"market_feature_store-inc-{DAY}.tar.gz").is_file()
    assert not (data / "db/snapshots").exists()
    assert _tree_bytes(code) == before
