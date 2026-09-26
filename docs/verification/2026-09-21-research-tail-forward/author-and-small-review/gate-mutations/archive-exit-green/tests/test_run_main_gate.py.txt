"""Exercise the real shell wrapper using a fake runner, never a full nested suite."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_main_gate.sh"


@pytest.fixture
def gate(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    receipt = tmp_path / "this-run.json"
    fake = tmp_path / "python"
    fake.write_text(
        "#!/bin/bash\n"
        'if [ "$1" = "-m" ]; then\n'
        '  if [ "$2" = "ruff" ]; then exit 0; fi\n'
        '  if [ "${OMIT_RECEIPT:-0}" != 1 ]; then printf "读数收据: %s\\n" "$ACTUAL_RECEIPT"; fi\n'
        '  for n in {1..20}; do echo warning-tail; done\n'
        '  exit "${FAKE_EXIT:-0}"\n'
        "fi\n"
        f"exec {shlex.quote(sys.executable)} \"$@\"\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    (root / "test-environment.json").write_text(json.dumps({"interpreter": str(fake)}, indent=2))
    (root / "run_main_gate.sh").write_bytes(SCRIPT.read_bytes())
    for args in (("init", "-q"), ("add", "--", "test-environment.json", "run_main_gate.sh"),
                 ("-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                  "-c", "core.hooksPath=/dev/null", "commit", "-qm", "fixture")):
        subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    data = {
        "revision": revision, "tree": str(root), "dirty": False, "target": str(root),
        "counts": {"passed": 3, "failed": 0, "error": 0, "skipped": 0},
        "failed_ids": [], "exit_status": 0,
    }
    receipt.write_text(json.dumps(data))
    # Concurrent pytest may have replaced the global latest pointer.
    other = home / ".finance-runtime" / "test-receipts" / "latest.json"
    other.parent.mkdir(parents=True)
    other.write_text(json.dumps({**data, "revision": "other", "counts": {"passed": 999}}))
    env = {"HOME": str(home), "PATH": os.environ["PATH"], "LANG": "en_US.UTF-8",
           "ACTUAL_RECEIPT": str(receipt), "FWP_TEST_RECEIPT_DIR": str(tmp_path / "unused")}

    def run(*args, updates=None):
        return subprocess.run(
            ["/bin/bash", str(root / "run_main_gate.sh"), *args], cwd=root,
            env={**env, **(updates or {})}, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=15,
        )

    return run, receipt, data


def test_actual_stdout_receipt_wins_over_global_latest_and_unused_dir(gate):
    run, receipt, _ = gate
    result = run()
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"== receipt {receipt}" in result.stdout
    assert "passed=3" in result.stdout and "passed=999" not in result.stdout


def test_missing_receipt_fails_closed_under_utf8_locale(gate):
    run, receipt, _ = gate
    receipt.unlink()
    result = run()
    assert result.returncode == 4
    assert "unbound variable" not in result.stderr


def test_no_receipt_pointer_never_uses_stale_latest(gate):
    run, _, _ = gate
    result = run(updates={"OMIT_RECEIPT": "1"})
    assert result.returncode == 4
    assert "passed=999" not in result.stdout


@pytest.mark.parametrize("field,value", [("revision", "wrong"), ("tree", "/other/tree")])
def test_live_gate_checks_receipt_identity(gate, field, value):
    run, receipt, data = gate
    receipt.write_text(json.dumps({**data, field: value}))
    assert run().returncode == 4


def test_measured_exit_must_agree_with_receipt(gate):
    run, _, _ = gate
    assert run(updates={"FAKE_EXIT": "1"}).returncode == 4


def test_receipt_only_does_not_turn_a_failed_run_green(gate):
    run, receipt, data = gate
    data.update(exit_status=1, failed_ids=["test_bad"])
    data["counts"].update(failed=1)
    receipt.write_text(json.dumps(data))
    result = run("--receipt", str(receipt))
    assert result.returncode == 1


def test_explicit_baseline_allows_same_red_but_rejects_new_red(gate, tmp_path):
    run, receipt, data = gate
    data.update(exit_status=1, failed_ids=["test_bad"])
    data["counts"].update(failed=1)
    receipt.write_text(json.dumps(data))
    baseline = tmp_path / "baseline.json"
    shutil.copyfile(receipt, baseline)
    assert run("--receipt", str(receipt), "--baseline", str(baseline)).returncode == 0
    data["failed_ids"].append("test_new_bad")
    data["counts"]["failed"] = 2
    receipt.write_text(json.dumps(data))
    assert run("--receipt", str(receipt), "--baseline", str(baseline)).returncode == 3


@pytest.mark.parametrize("exit_status", [2, 3, 4, 5])
def test_baseline_cannot_hide_an_interrupted_or_broken_runner(gate, tmp_path, exit_status):
    run, receipt, data = gate
    baseline = tmp_path / "baseline.json"
    shutil.copyfile(receipt, baseline)
    receipt.write_text(json.dumps({**data, "exit_status": exit_status}))
    assert run("--receipt", str(receipt), "--baseline", str(baseline)).returncode == exit_status


@pytest.mark.parametrize("field,value", [("exit_status", None), ("counts", {}), ("dirty", True)])
def test_incomplete_or_dirty_receipt_cannot_be_a_green_gate(gate, field, value):
    run, receipt, data = gate
    receipt.write_text(json.dumps({**data, field: value}))
    assert run("--receipt", str(receipt)).returncode == 4
