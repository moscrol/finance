"""Real-index regression checks; all credential-shaped inputs are synthetic."""
from __future__ import annotations

import base64
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

GATE = Path(__file__).resolve().parents[1] / "scripts" / "check_staged_credentials.py"
spec = importlib.util.spec_from_file_location("staged_credentials_gate", GATE)
assert spec is not None and spec.loader is not None
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def _segment(value: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=")


def _session() -> str:
    return ".".join((_segment({"alg": "dir", "enc": "A256GCM"}), "", "i" * 16, "c" * 90, "t" * 22))


def _jwt() -> str:
    return ".".join((_segment({"alg": "RS256"}), _segment({"sub": "synthetic-only", "exp": 1}), "s" * 64))


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.name", "test")
    _git(tmp_path, "config", "user.email", "test@example.invalid")
    _git(tmp_path, "config", "core.hooksPath", str(tmp_path / "no-hooks"))
    return tmp_path


def _stage(repo: Path, path: str, content: str | bytes) -> None:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content.encode() if isinstance(content, str) else content)
    _git(repo, "add", "--", path)


def _run(repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(GATE)], cwd=repo, capture_output=True, text=True)


@pytest.mark.parametrize("field", ["sessionToken", "refresh_token", "accessToken", "APP_SECRET"])
def test_literals_in_ordinary_receipt_are_blocked_without_value_output(repo, field):
    value = "synthetic-only-" + "X" * 90
    _stage(repo, "docs/evidence.txt", json.dumps({field: value}))
    result = _run(repo)
    assert result.returncode == 1
    assert "docs/evidence.txt" in result.stdout
    assert value not in result.stdout + result.stderr


@pytest.mark.parametrize("value_factory", [_session, _jwt])
def test_token_shapes_even_expired_are_blocked_under_neutral_field(repo, value_factory):
    value = value_factory()
    _stage(repo, "plain", json.dumps({"payload": value}))
    result = _run(repo)
    assert result.returncode == 1
    assert value not in result.stdout + result.stderr


def test_index_not_clean_worktree_is_the_commit_source(repo):
    _stage(repo, "receipt.txt", json.dumps({"sessionToken": _session()}))
    (repo / "receipt.txt").write_text("cleaned but not re-staged")
    assert _run(repo).returncode == 1
    _git(repo, "add", "--", "receipt.txt")
    assert _run(repo).returncode == 0


def test_unstaged_credential_does_not_change_index_verdict(repo):
    _stage(repo, "receipt.txt", "safe")
    (repo / "receipt.txt").write_text(json.dumps({"sessionToken": _session()}))
    assert _run(repo).returncode == 0


def test_modifying_existing_receipt_is_checked(repo):
    _stage(repo, "receipt.txt", "old safe receipt")
    _git(repo, "commit", "-qm", "base")
    _stage(repo, "receipt.txt", json.dumps({"APP_SECRET": "z" * 32}))
    assert _run(repo).returncode == 1


def test_binary_is_not_a_scan_exemption(repo):
    _stage(repo, "receipt.bin", b"\x00\xff\n" + json.dumps({"sessionToken": _session()}).encode())
    assert _run(repo).returncode == 1


def test_tests_directory_is_not_a_scan_exemption(repo):
    _stage(repo, "tests/fixture.txt", json.dumps({"sessionToken": _session()}))
    assert _run(repo).returncode == 1


def test_rename_is_not_a_scan_exemption(repo):
    _stage(repo, "old.txt", json.dumps({"sessionToken": _session()}))
    _git(repo, "commit", "-qm", "legacy fixture")
    _git(repo, "mv", "old.txt", "new.txt")
    assert _run(repo).returncode == 1


def test_deleting_legacy_credential_is_allowed(repo):
    _stage(repo, "old.txt", json.dumps({"sessionToken": _session()}))
    _git(repo, "commit", "-qm", "legacy fixture")
    _git(repo, "rm", "--", "old.txt")
    assert _run(repo).returncode == 0


def test_no_changed_paths_is_explicitly_narrow(repo):
    _stage(repo, "ordinary", "safe")
    _git(repo, "commit", "-qm", "base")
    result = _run(repo)
    assert result.returncode == 0
    assert "0 个 blob" in result.stdout
    assert "不代表历史" in result.stdout


def test_hashes_env_reads_and_short_placeholders_are_not_credentials(repo):
    _stage(repo, "sample.py", '\n'.join([
        'credential_instance_sha256 = "' + "ab" * 32 + '"',
        'token_sha256 = "' + "cd" * 32 + '"',
        'app_secret = os.environ["APP_SECRET"]',
        'sessionToken = "<REDACTED>"',
    ]))
    assert _run(repo).returncode == 0


def test_symlink_is_not_followed(repo, tmp_path):
    outside = tmp_path.parent / (tmp_path.name + "-external")
    outside.write_text(json.dumps({"sessionToken": _session()}))
    (repo / "receipt.txt").symlink_to(outside)
    _git(repo, "add", "--", "receipt.txt")
    assert _run(repo).returncode == 0


def test_filename_control_characters_are_escaped(repo):
    _stage(repo, "receipt\nname.txt", json.dumps({"sessionToken": _session()}))
    result = _run(repo)
    assert result.returncode == 1
    assert '"receipt\\nname.txt"' in result.stdout


def test_git_failure_is_not_a_clean_scan(tmp_path):
    result = _run(tmp_path)
    assert result.returncode == 2
    assert "无法读取" in result.stderr


def test_scan_metadata_has_line_and_rule_but_no_value():
    value = _session()
    findings = gate.scan_bytes(b"safe first line\n" + json.dumps({"sessionToken": value}).encode())
    assert findings
    assert all(line == 2 and isinstance(rule, str) for line, rule in findings)
    assert value not in repr(findings)


def test_submodule_reference_is_not_silently_claimed_as_scanned(repo):
    _stage(repo, "ordinary", "safe")
    _git(repo, "commit", "-qm", "base")
    oid = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"]).decode().strip()
    _git(repo, "update-index", "--add", "--cacheinfo", f"160000,{oid},module")
    result = _run(repo)
    assert result.returncode == 0
    assert "1 个子模块" in result.stdout


def test_precommit_wires_index_guard_without_filename_exemptions():
    import yaml

    config = yaml.safe_load((GATE.parents[1] / ".pre-commit-config.yaml").read_text())
    hook = next(h for r in config["repos"] for h in r["hooks"] if h["id"] == "staged-credentials")
    assert hook["entry"] == "python3 scripts/check_staged_credentials.py"
    assert hook["pass_filenames"] is False
    assert hook["always_run"] is True
    assert not any(key in hook for key in ("files", "exclude", "types", "types_or"))


def test_unmerged_index_fails_closed(repo):
    _stage(repo, "receipt.txt", "base")
    _git(repo, "commit", "-qm", "base")
    branch = subprocess.check_output(["git", "-C", str(repo), "branch", "--show-current"]).decode().strip()
    _git(repo, "checkout", "-qb", "other")
    _stage(repo, "receipt.txt", "other")
    _git(repo, "commit", "-qm", "other")
    _git(repo, "checkout", "-q", branch)
    _stage(repo, "receipt.txt", "original")
    _git(repo, "commit", "-qm", "original")
    merged = subprocess.run(["git", "-C", str(repo), "merge", "other"], capture_output=True)
    assert merged.returncode != 0
    assert _run(repo).returncode == 2
