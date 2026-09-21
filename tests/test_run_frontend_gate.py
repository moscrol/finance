"""Real Git/child-process counterexamples for frontend receipt provenance."""

import hashlib
import json
import subprocess
import sys

import pytest

from scripts.run_frontend_gate import run_gate


@pytest.fixture
def checkout(tmp_path):
    tree = tmp_path / "checkout"
    (tree / "intelligence/webapp").mkdir(parents=True)

    def git(*args):
        return subprocess.check_output(["git", *args], cwd=tree, text=True).strip()

    git("init", "-q")
    git("config", "user.email", "gate-test@example.invalid")
    git("config", "user.name", "Gate test")
    (tree / "source.txt").write_text("original\n")
    git("add", "--", "source.txt")
    git("commit", "-qm", "initial")
    return tree, tmp_path / "receipt", git("rev-parse", "HEAD")


def command(code):
    return (sys.executable, "-c", code)


def receipt(output):
    return json.loads((output / "frontend.json").read_text())


def test_clean_checkout_produces_bound_receipt(checkout):
    tree, output, sha = checkout
    assert run_gate(tree, output, sha, commands=[command("print('passed')")]) == 0
    data = receipt(output)
    assert data["complete"] and data["identity_stable"] and data["dirty"] is False
    for key in ("identity_before", "identity_after"):
        assert data[key]["revision"] == sha and data[key]["status_porcelain_z"] == ""
    log = output / data["checks"][0]["log"]
    assert data["checks"][0]["log_sha256"] == hashlib.sha256(log.read_bytes()).hexdigest()


@pytest.mark.parametrize("reason", ["dirty", "wrong-revision"])
def test_initial_identity_rejection_runs_no_command(checkout, reason):
    tree, output, sha = checkout
    if reason == "dirty":
        (tree / "source.txt").write_text("already changed\n")
    else:
        sha = "0" * 40
    assert run_gate(tree, output, sha, commands=[command("raise AssertionError")]) == 2
    data = receipt(output)
    assert data["checks"] == [] and not data["complete"] and not data["identity_stable"]
    assert data["identity_before"]["dirty"] is (reason == "dirty")


def test_command_success_with_changed_source_is_not_a_green_gate(checkout):
    tree, output, sha = checkout
    change = command("from pathlib import Path; Path('../../source.txt').write_text('changed')")
    assert run_gate(tree, output, sha, commands=[change]) == 2
    data = receipt(output)
    assert data["checks"][0]["exit_code"] == 0
    assert data["dirty"] and not data["identity_stable"]
    assert "source.txt" in data["identity_after"]["status_porcelain_z"]


def test_clean_but_changed_head_is_not_a_green_gate(checkout):
    tree, output, sha = checkout
    change = command("import subprocess; subprocess.run(['git','commit','--allow-empty','-qm','moved'],check=True)")
    assert run_gate(tree, output, sha, commands=[change]) == 2
    data = receipt(output)
    assert data["dirty"] is False and not data["identity_stable"]
    assert data["identity_after"]["revision"] != sha


def test_failed_check_is_preserved_with_later_success(checkout):
    tree, output, sha = checkout
    checks = [command("pass"), command("raise SystemExit(9)"), command("pass")]
    assert run_gate(tree, output, sha, commands=checks) == 1
    data = receipt(output)
    assert [check["exit_code"] for check in data["checks"]] == [0, 9, 0]
    assert data["complete"] and data["identity_stable"]


def test_git_failure_cannot_be_reported_as_clean(tmp_path):
    tree = tmp_path / "not-a-repo"
    tree.mkdir()
    output = tmp_path / "receipt"
    assert run_gate(tree, output, "0" * 40, commands=[command("pass")]) == 2
    data = receipt(output)
    assert data["dirty"] is None and not data["identity_stable"] and data["checks"] == []


def test_existing_receipt_directory_is_not_overwritten(checkout):
    tree, output, sha = checkout
    output.mkdir()
    original = output / "frontend.json"
    original.write_text("original evidence")
    with pytest.raises(FileExistsError):
        run_gate(tree, output, sha, commands=[command("pass")])
    assert original.read_text() == "original evidence"


def test_output_inside_target_is_rejected(checkout):
    tree, _, sha = checkout
    output = tree / "receipts"
    with pytest.raises(ValueError, match="outside"):
        run_gate(tree, output, sha, commands=[command("pass")])
    assert not output.exists()


def test_missing_command_has_a_failure_receipt(checkout):
    tree, output, sha = checkout
    missing = (str(output.parent / "absent-executable"),)
    assert run_gate(tree, output, sha, commands=[missing]) == 1
    assert receipt(output)["checks"][0]["exit_code"] == 127
