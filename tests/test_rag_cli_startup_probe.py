"""Evidence collection must preserve failures and restore process environment."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.review_probes import check_rag_cli_startup as probe


def test_inventory_binds_only_selected_python_sources(tmp_path):
    for relative in probe.CODE_PATHS:
        path = tmp_path / relative
        if path.suffix == ".py":
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# fixture\n")
        else:
            path.mkdir(parents=True)
            (path / "config.py").write_text("VALUE = 1\n")
            (path / "cache.pyc").write_bytes(b"ignored")
    (tmp_path / "credentials.txt").write_text("not part of code identity")
    before = probe.inventory(tmp_path)
    assert len(before) == 4
    assert all(name.endswith(".py") for name in before)
    (tmp_path / "skills/lib/rag/config.py").write_text("VALUE = 2\n")
    after = probe.inventory(tmp_path)
    assert before["skills/lib/rag/config.py"] != after["skills/lib/rag/config.py"]


def test_environment_is_allowlisted_and_restored_on_failure(monkeypatch):
    monkeypatch.setenv("STARTUP_PROBE_TEST_SECRET", "must not propagate")
    before = dict(os.environ)
    with pytest.raises(RuntimeError, match="failure"):
        with probe.environment({"PATH": os.defpath}):
            assert dict(os.environ) == {"PATH": os.defpath}
            raise RuntimeError("failure")
    assert dict(os.environ) == before


def test_run_retains_nonzero_outputs_and_hashes(tmp_path):
    result = probe.run(
        [sys.executable, "-c", "import sys; print('out'); print('err', file=sys.stderr); sys.exit(7)"],
        tmp_path, {"PATH": os.defpath}, tmp_path, "nonzero",
    )
    assert result["exit_code"] == 7
    assert not result["timeout"]
    assert result["elapsed_ms"] >= 0
    assert (tmp_path / "nonzero.stderr").read_bytes() == b"err\n"
    assert result["output_sha256"]["stdout"] == hashlib.sha256(b"out\n").hexdigest()


def test_run_preserves_partial_output_after_timeout(tmp_path):
    result = probe.run(
        [sys.executable, "-c", "import time; print('started', flush=True); time.sleep(10)"],
        tmp_path, {"PATH": os.defpath}, tmp_path, "timeout", timeout=0.5,
    )
    assert result["exit_code"] is None
    assert result["timeout"]
    assert (tmp_path / "timeout.stdout").read_bytes() == b"started\n"
    assert (tmp_path / "timeout.stderr").read_bytes() == b""


def test_fault_guard_disables_network(tmp_path):
    guard = tmp_path / "sitecustomize.py"
    guard.write_text(probe.GUARD)
    proc = subprocess.run(
        [sys.executable, "-c", "import socket; socket.create_connection(('127.0.0.1', 9))"],
        env={"PATH": os.defpath, "PYTHONPATH": str(tmp_path), "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True, text=True, timeout=5,
    )
    assert proc.returncode != 0
    assert "network forbidden in startup experiment" in proc.stderr


def test_existing_evidence_directory_is_not_overwritten(tmp_path, monkeypatch):
    marker = tmp_path / "receipt.json"
    marker.write_text("original\n")
    monkeypatch.setattr(sys, "argv", [
        str(Path(probe.__file__)), "--baseline", str(tmp_path / "baseline"),
        "--candidate", str(tmp_path / "candidate"), "--python", sys.executable,
        "--output-dir", str(tmp_path),
    ])
    with pytest.raises(SystemExit) as exc:
        probe.main()
    assert exc.value.code == 2
    assert marker.read_text() == "original\n"
