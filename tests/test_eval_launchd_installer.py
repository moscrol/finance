"""Run the real installer with a temporary HOME and a recording launchctl.

Protect against a nightly-only rollout silently replacing the other four jobs,
a typo selecting the whole fleet, and a purported preview modifying the host.
No scheduled script, model, data collector or real launchctl is executed.
"""
from __future__ import annotations

import os
from pathlib import Path
import plistlib
import subprocess

import pytest


pytestmark = pytest.mark.skipif(
    not os.path.exists("/bin/zsh"),
    reason="安装器是 zsh 脚本：需要 /bin/zsh（macOS 默认 shell）；Linux 上整份跳过，Mac 上照常跑",
)

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts/install_eval_launchd.sh"
SCRIPTS = {
    "ops_python.sh": "scripts/lib/ops_python.sh",
    "run_fidelity_daily_agent.sh": "scripts/run_fidelity_daily_agent.sh",
    "run_fidelity_forward_acceptance.sh": "scripts/run_fidelity_forward_acceptance.sh",
    "freeze_daily_pit_snapshot.sh": "scripts/freeze_daily_pit_snapshot.sh",
    "run_checkpoint_recheck.sh": "scripts/run_checkpoint_recheck.sh",
    "nightly_full_review.sh": "skills/daily-full-review/scripts/nightly_full_review.sh",
    "nightly-full-review-s7.sh": "skills/daily-full-review/scripts/nightly_full_review_s7.sh",
}
JOBS = {
    "fidelity-daily-agent": "eval",
    "fidelity-forward-acceptance": "eval",
    "pit-snapshot": "eval",
    "checkpoint-recheck": "eval",
    "daily-full-review-sync": "dream",
    "daily-full-review-finalize": "dream",
}
NIGHTLY = {"daily-full-review-sync", "daily-full-review-finalize"}


def inventory(home: Path) -> dict[str, bytes]:
    return {str(p.relative_to(home)): p.read_bytes() for p in home.rglob("*") if p.is_file()}


@pytest.fixture
def rig(tmp_path):
    repo, home, bins = (tmp_path / name for name in ("repo with spaces", "home", "bin"))
    repo.mkdir()
    home.mkdir()
    bins.mkdir()
    for name, relative in SCRIPTS.items():
        source = repo / relative
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(f"#!/bin/zsh\n# candidate {name}\nexit 0\n")
        installed = home / ".local/bin" / name
        installed.parent.mkdir(parents=True, exist_ok=True)
        installed.write_text(source.read_text() if name == "ops_python.sh" else f"old {name}")
    for job, folder in JOBS.items():
        name = f"com.financeworkspace.{job}.plist"
        source = repo / "intelligence" / folder / name
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(plistlib.dumps({"Label": name[:-6], "RunAtLoad": False}))
        installed = home / "Library/LaunchAgents" / name
        installed.parent.mkdir(parents=True, exist_ok=True)
        installed.write_bytes(b"old " + name.encode())
    log = tmp_path / "launchctl.calls"
    launchctl = bins / "launchctl"
    launchctl.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$INSTALL_CALL_LOG"\n')
    launchctl.chmod(0o755)
    env = {"HOME": str(home), "PATH": f"{bins}:/usr/bin:/bin:/usr/sbin:/sbin",
           "FINANCE_OPS_REPO": str(repo), "INSTALL_CALL_LOG": str(log)}

    def run(*args):
        return subprocess.run(["/bin/zsh", str(INSTALLER), *args], env=env,
                              text=True, capture_output=True, timeout=15)

    return repo, home, log, run


def test_nightly_only_changes_exactly_two_jobs_and_wrappers(rig):
    repo, home, log, run = rig
    before = inventory(home)
    result = run("--nightly-only")
    assert result.returncode == 0, result.stderr
    after = inventory(home)
    changed = {name for name in before.keys() | after.keys() if before.get(name) != after.get(name)}
    expected = {f"Library/LaunchAgents/com.financeworkspace.{job}.plist" for job in NIGHTLY}
    expected.update({".local/bin/nightly_full_review.sh", ".local/bin/nightly-full-review-s7.sh"})
    assert changed == expected
    calls = log.read_text().splitlines()
    assert len(calls) == 4
    assert sum(c.startswith("bootout ") for c in calls) == 2
    assert sum(c.startswith("bootstrap ") for c in calls) == 2
    assert all(any(job in c for job in NIGHTLY) for c in calls)
    assert not any("kickstart" in c for c in calls)
    for name in ("nightly_full_review.sh", "nightly-full-review-s7.sh"):
        installed = home / ".local/bin" / name
        assert installed.read_bytes() == (repo / SCRIPTS[name]).read_bytes()
        assert os.access(installed, os.X_OK)


@pytest.mark.parametrize("args", [("--dry-run",), ("--nightly-only", "--dry-run"),
                                  ("--dry-run", "--nightly-only")])
def test_preview_has_no_file_or_launchctl_side_effects(rig, args):
    _, home, log, run = rig
    before = inventory(home)
    result = run(*args)
    assert result.returncode == 0, result.stderr
    assert "dry-run:" in result.stdout
    assert inventory(home) == before
    assert not (home / ".finance-runtime").exists()
    assert not log.exists()


def test_default_preserves_existing_six_job_install_contract(rig):
    _, _, log, run = rig
    result = run()
    assert result.returncode == 0, result.stderr
    assert len(log.read_text().splitlines()) == 12
    assert "installed 6 jobs" in result.stdout


@pytest.mark.parametrize("args", [("--nightly-only", "--kickstart"),
                                  ("--kickstart", "--nightly-only")])
def test_explicit_kickstart_is_order_independent_and_scoped(rig, args):
    _, _, log, run = rig
    result = run(*args)
    assert result.returncode == 0, result.stderr
    calls = log.read_text().splitlines()
    assert len(calls) == 6
    assert sum(c.startswith("kickstart -k ") for c in calls) == 2
    assert all(any(job in c for job in NIGHTLY) for c in calls)


@pytest.mark.parametrize("args", [("--nightly-onyl",), ("--unknown", "--kickstart"),
                                  ("--dry-run", "--kickstart"), ("--kickstart", "--dry-run")])
def test_unknown_or_contradictory_options_fail_before_side_effects(rig, args):
    _, home, log, run = rig
    before = inventory(home)
    result = run(*args)
    assert result.returncode == 2
    assert inventory(home) == before
    assert not log.exists()


@pytest.mark.parametrize("fault", ["shared_helper", "missing_helper", "missing_script", "shell",
                                   "plist", "scalar_plist", "wrong_label", "run_at_load"])
def test_preflight_failure_prevents_partial_install(rig, fault):
    repo, home, log, run = rig
    if fault == "shared_helper":
        (home / ".local/bin/ops_python.sh").write_text("different shared helper")
    elif fault == "missing_helper":
        (home / ".local/bin/ops_python.sh").unlink()
    elif fault == "missing_script":
        (repo / SCRIPTS["nightly-full-review-s7.sh"]).unlink()
    elif fault == "shell":
        (repo / SCRIPTS["nightly-full-review-s7.sh"]).write_text("if;\n")
    else:
        source = repo / "intelligence/dream/com.financeworkspace.daily-full-review-finalize.plist"
        if fault == "plist":
            source.write_text("<plist><dict><key>broken")
        elif fault == "scalar_plist":
            # OpenStep plists accept a bare string; syntax alone is not enough.
            source.write_text("invalid")
        else:
            value = plistlib.loads(source.read_bytes())
            value["Label" if fault == "wrong_label" else "RunAtLoad"] = (
                "com.a77.finance-workbench" if fault == "wrong_label" else True
            )
            source.write_bytes(plistlib.dumps(value))
    before = inventory(home)
    result = run("--nightly-only")
    assert result.returncode != 0
    assert inventory(home) == before
    assert not log.exists()


def test_full_preview_does_not_create_launchagent_directories(tmp_path):
    home = tmp_path / "empty-home"
    env = {"HOME": str(home), "PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "FINANCE_OPS_REPO": str(ROOT)}
    result = subprocess.run(["/bin/zsh", str(INSTALLER), "--dry-run"], env=env,
                            text=True, capture_output=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert not home.exists()
