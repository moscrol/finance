"""切 8792 的前置核验：不过就不碰服务、不动链接。

2026-10-06 切 f3b97499aaff 时快照缺 .venv-workbench，启动器 exit 127 循环重启约 5 分钟；
2026-09-27 bootout 后立刻 bootstrap 撞 I/O error。这里用假的 launchctl / lsof 跑脚本，
只看它对服务和链接做了什么，不碰真实生产。
"""

from pathlib import Path
import shutil
import signal
import subprocess
import time

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/switch_8792.sh"
BASH = shutil.which("bash")
pytestmark = pytest.mark.skipif(BASH is None, reason="switch script needs bash")


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True,
    ).stdout.strip()


def _tool(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(0o755)


@pytest.fixture
def box(tmp_path: Path):
    home = tmp_path / "home"
    staging = tmp_path / "staging"
    (staging / "scripts").mkdir(parents=True)
    (staging / "scripts/audit_deploy_ledger.py").write_text("# stub\n")
    (staging / ".gitignore").write_text(".venv-workbench\n")
    _git(staging, "init", "-q")
    _git(staging, "add", "--", ".gitignore", "scripts/audit_deploy_ledger.py")
    _git(staging, "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
         "-c", "core.hooksPath=/dev/null", "commit", "-qm", "fixture")
    sha = _git(staging, "rev-parse", "HEAD")
    snap = home / ".finance-runtime" / f"finance-workspace-{sha[:12]}"
    snap.parent.mkdir(parents=True)
    staging.rename(snap)
    old = home / ".finance-runtime/finance-workspace-old"
    (old / "scripts").mkdir(parents=True)
    (old / "scripts/audit_deploy_ledger.py").write_text("# previous stub\n")
    (old / ".gitignore").write_text(".venv-workbench\n")
    _git(old, "init", "-q")
    _git(old, "add", "--", ".gitignore", "scripts/audit_deploy_ledger.py")
    _git(old, "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
         "-c", "core.hooksPath=/dev/null", "commit", "-qm", "previous fixture")
    old_sha = _git(old, "rev-parse", "HEAD")
    _add_venv(old)
    link = home / "finance-workspace-runtime"
    link.symlink_to(old)
    effects = tmp_path / "effects"
    effects.write_text("")
    record = tmp_path / "record"
    fakebin = tmp_path / "bin"
    # print 失败 = 已卸载；bootout / bootstrap 成功。
    _tool(fakebin / "launchctl", '''
echo "launchctl $*" >> "$EFFECTS"
if [ "$1" = print ]; then
  if [ -n "${INTERRUPT_WAIT:-}" ]; then
    stops=$(cat "$BOOTOUT_COUNT_FILE" 2>/dev/null || echo 0)
    [ "$stops" -eq 1 ] && exit 0
  fi
  boots=$(cat "${BOOTSTRAP_COUNT_FILE:-/dev/null}" 2>/dev/null || echo 0)
  if [ -n "${ROLLBACK_PRINTS_REQUIRED:-}" ] && [ "$boots" -ge 3 ]; then
    prints=$(cat "$AFTER_BOOTSTRAP_PRINT_FILE" 2>/dev/null || echo 0)
    prints=$((prints + 1))
    echo "$prints" > "$AFTER_BOOTSTRAP_PRINT_FILE"
    [ "$prints" -le "$ROLLBACK_PRINTS_REQUIRED" ] && exit 0
  fi
  [ -z "${PRINT_STDERR:-}" ] || echo "$PRINT_STDERR" >&2
  exit "${PRINT_RC:-1}"
fi
if [ "$1" = bootstrap ]; then
  count=$(cat "${BOOTSTRAP_COUNT_FILE:-/dev/null}" 2>/dev/null || echo 0)
  count=$((count + 1))
  [ -z "${BOOTSTRAP_COUNT_FILE:-}" ] || echo "$count" > "$BOOTSTRAP_COUNT_FILE"
  [ "$count" -le "${BOOTSTRAP_FAIL_COUNT:-0}" ] && exit "${BOOTSTRAP_RC:-7}"
  if [ -n "${ROLLBACK_PRINTS_REQUIRED:-}" ]; then
    prints=$(cat "$AFTER_BOOTSTRAP_PRINT_FILE" 2>/dev/null || echo 0)
    [ "$prints" -lt "$ROLLBACK_PRINTS_REQUIRED" ] && exit 7
  fi
fi
if [ "$1" = bootout ]; then
  if [ -n "${BOOTOUT_COUNT_FILE:-}" ]; then
    stops=$(cat "$BOOTOUT_COUNT_FILE" 2>/dev/null || echo 0)
    echo "$((stops + 1))" > "$BOOTOUT_COUNT_FILE"
  fi
  exit "${BOOTOUT_RC:-0}"
fi
exit 0
''')
    _tool(fakebin / "lsof", '''
count=$(cat "$LSOF_COUNT_FILE" 2>/dev/null || echo 0)
count=$((count + 1))
echo "$count" > "$LSOF_COUNT_FILE"
if [ -z "${LSOF_FAIL_COUNT:-}" ] || [ "$count" -le "$LSOF_FAIL_COUNT" ]; then
  [ -z "${LSOF_STDERR:-}" ] || echo "$LSOF_STDERR" >&2
  exit "${LSOF_RC:-1}"
fi
exit 1
''')
    _tool(fakebin / "ln", '''
if [ -n "${LN_COUNT_FILE:-}" ]; then
  count=$(cat "$LN_COUNT_FILE" 2>/dev/null || echo 0)
  count=$((count + 1))
  echo "$count" > "$LN_COUNT_FILE"
  [ "$count" -le "${LN_FAIL_COUNT:-0}" ] && exit "${LN_RC:-9}"
fi
exec /bin/ln "$@"
''')

    def run(revision: str, *, extra_env: dict[str, str] | None = None,
            interrupt: int | None = None) -> subprocess.CompletedProcess:
        env = {
            "HOME": str(home), "PATH": f"{fakebin}:/usr/bin:/bin", "EFFECTS": str(effects),
            "PREVIOUS_PYTHON": str(old / ".venv-workbench/bin/python"),
            "LSOF_COUNT_FILE": str(tmp_path / "lsof-count"),
            "FINANCE_WS": str(tmp_path / "ws"), **(extra_env or {}),
        }
        command = [BASH, str(SCRIPT), revision, str(record)]
        if interrupt is None:
            return subprocess.run(command, env=env, capture_output=True, text=True, timeout=60)
        with subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True) as process:
            try:
                deadline = time.monotonic() + 10
                while "launchctl print " not in effects.read_text():
                    assert process.poll() is None, "script exited before the interrupt point"
                    assert time.monotonic() < deadline, "script never reached the unload wait"
                    time.sleep(0.01)
                process.send_signal(interrupt)
                stdout, stderr = process.communicate(timeout=20)
                return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate(timeout=5)

    return {
        "sha": sha, "old_sha": old_sha, "snap": snap, "old": old, "link": link, "effects": effects,
        "record": record, "run": run,
    }


def _add_venv(snap: Path) -> None:
    _tool(snap / ".venv-workbench/bin/python", '''
echo "python $*" >> "$EFFECTS"
if [ "$0" = "$PREVIOUS_PYTHON" ]; then
  exit "${ROLLBACK_LEDGER_RC:-0}"
fi
exit "${LEDGER_RC:-0}"
''')


def test_switch_waits_for_unload_then_records_with_port_and_bootstraps(box) -> None:
    _add_venv(box["snap"])

    result = box["run"](box["sha"])

    assert result.returncode == 0, result.stderr
    assert box["link"].resolve() == box["snap"].resolve()
    effects = box["effects"].read_text().splitlines()
    order = [line.split()[1] for line in effects if line.startswith("launchctl")]
    assert order[0] == "bootout" and "print" in order and order[-1] == "bootstrap"
    record = next(line for line in effects if line.startswith("python"))
    assert f"--rev {box['sha']}" in record and "--port 8792" in record
    assert "SWITCH_BOOTSTRAP_DONE rc=0 post_checks=required" in (box["record"] / "switch.log").read_text()


@pytest.mark.parametrize("defect", ["no-venv", "short-sha", "dirty-snapshot"])
def test_failed_precheck_never_touches_the_service_or_the_link(box, defect: str) -> None:
    revision = box["sha"]
    if defect != "no-venv":
        _add_venv(box["snap"])
    if defect == "short-sha":
        revision = revision[:12]
    if defect == "dirty-snapshot":
        (box["snap"] / "stray.txt").write_text("not from the gated tree\n")

    result = box["run"](revision)

    assert result.returncode == 2
    reason = {"no-venv": ".venv-workbench", "short-sha": "40-char", "dirty-snapshot": "dirty"}[defect]
    # 短 SHA 也过不了「快照 HEAD == SHA」那一关；钉住原因，长度检查才不是摆设。
    assert "ABORT" in result.stderr and reason in result.stderr
    assert "launchctl" not in box["effects"].read_text()
    assert box["link"].resolve() == box["old"].resolve()


@pytest.mark.parametrize("snapshot", ["snap", "old"])
def test_unreadable_git_index_aborts_before_touching_service(box, snapshot: str) -> None:
    _add_venv(box["snap"])
    (box[snapshot] / ".git/index").write_bytes(b"corrupt index")

    result = box["run"](box["sha"])

    assert result.returncode == 2, result.stderr
    assert "cannot inspect" in result.stderr
    assert "launchctl" not in box["effects"].read_text()
    assert "python" not in box["effects"].read_text()
    assert box["link"].resolve() == box["old"].resolve()


def test_service_that_never_unloads_keeps_the_old_link(box) -> None:
    _add_venv(box["snap"])

    result = box["run"](box["sha"], extra_env={"PRINT_RC": "0", "WORKBENCH_UNLOAD_WAIT_SECONDS": "2"})

    assert result.returncode == 7
    assert box["link"].resolve() == box["old"].resolve()
    assert "bootstrap" not in box["effects"].read_text()
    assert "ROLLBACK_WAIT_FAILED" in (box["record"] / "switch.log").read_text()


@pytest.mark.parametrize("interrupt,exit_code", [
    (signal.SIGINT, 130), (signal.SIGTERM, 143), (signal.SIGHUP, 129),
], ids=["INT", "TERM", "HUP"])
def test_interrupt_after_bootout_restores_previous_runtime_once(box, tmp_path, interrupt, exit_code):
    _add_venv(box["snap"])
    result = box["run"](box["sha"], interrupt=interrupt, extra_env={
        "INTERRUPT_WAIT": "1", "BOOTOUT_COUNT_FILE": str(tmp_path / "bootout-count"),
        "WORKBENCH_UNLOAD_WAIT_SECONDS": "5",
    })
    log = (box["record"] / "switch.log").read_text()
    effects = box["effects"].read_text().splitlines()
    assert result.returncode == exit_code, result.stderr
    assert box["link"].resolve() == box["old"].resolve()
    assert sum(line.startswith("launchctl bootout ") for line in effects) == 2
    assert any(line.startswith("python ") and f"--rev {box['old_sha']}" in line for line in effects)
    assert sum(line.startswith("launchctl bootstrap ") for line in effects) == 1
    assert "ROLLBACK_DONE rc=0" in log and "ABORT signal=" in log
    assert "SWITCH_BOOTSTRAP_DONE" not in log


def test_interrupt_with_incomplete_rollback_reports_exit_seven(box, tmp_path):
    _add_venv(box["snap"])
    result = box["run"](box["sha"], interrupt=signal.SIGTERM, extra_env={
        "INTERRUPT_WAIT": "1", "BOOTOUT_COUNT_FILE": str(tmp_path / "bootout-count"),
        "WORKBENCH_UNLOAD_WAIT_SECONDS": "5", "ROLLBACK_LEDGER_RC": "9",
    })
    log = (box["record"] / "switch.log").read_text()
    assert result.returncode == 7, result.stderr
    assert box["link"].resolve() == box["old"].resolve()
    assert "launchctl bootstrap " in box["effects"].read_text()
    assert "ROLLBACK_FAILED after signal=TERM" in log
    assert "ROLLBACK_DONE" not in log and "SWITCH_BOOTSTRAP_DONE" not in log


def test_macos_missing_service_exit_113_allows_the_switch(box) -> None:
    _add_venv(box["snap"])
    result = box["run"](box["sha"], extra_env={
        "PRINT_RC": "113", "PRINT_STDERR": 'Could not find service "com.a77.finance-workbench"',
    })
    assert result.returncode == 0
    assert box["link"].resolve() == box["snap"].resolve()


def test_lsof_error_is_not_treated_as_an_empty_port(box) -> None:
    _add_venv(box["snap"])

    result = box["run"](box["sha"], extra_env={"LSOF_RC": "2", "LSOF_FAIL_COUNT": "1"})

    assert result.returncode == 4
    assert box["link"].resolve() == box["old"].resolve()
    assert "bootstrap" in box["effects"].read_text()
    assert "ROLLBACK_DONE" in (box["record"] / "switch.log").read_text()
    assert "lsof failed" in (result.stderr + (box["record"] / "switch.log").read_text())


def test_ledger_failure_restores_the_old_link(box) -> None:
    _add_venv(box["snap"])

    result = box["run"](box["sha"], extra_env={"LEDGER_RC": "9"})

    log = (box["record"] / "switch.log").read_text()
    assert result.returncode == 5
    assert box["link"].resolve() == box["old"].resolve()
    assert "ledger_record_exit=9" in log
    assert "ROLLBACK_DONE" in log
    assert "SWITCH_BOOTSTRAP_DONE" not in log


def test_link_failure_restores_the_old_link(box, tmp_path: Path) -> None:
    _add_venv(box["snap"])
    count_file = tmp_path / "ln-count"

    result = box["run"](
        box["sha"],
        extra_env={"LN_COUNT_FILE": str(count_file), "LN_FAIL_COUNT": "1"},
    )

    log = (box["record"] / "switch.log").read_text()
    assert result.returncode == 5
    assert box["link"].resolve() == box["old"].resolve()
    assert "cannot point runtime link" in log
    assert "ROLLBACK_DONE" in log


def test_three_bootstrap_failures_restore_the_old_link(box, tmp_path: Path) -> None:
    _add_venv(box["snap"])
    count_file = tmp_path / "bootstrap-count"

    result = box["run"](
        box["sha"],
        extra_env={
            "BOOTSTRAP_RC": "7",
            "BOOTSTRAP_FAIL_COUNT": "3",
            "BOOTSTRAP_COUNT_FILE": str(count_file),
        },
    )

    log = (box["record"] / "switch.log").read_text()
    assert result.returncode == 6
    assert box["link"].resolve() == box["old"].resolve()
    assert "bootstrap failed after three attempts rc=7" in log
    assert "ROLLBACK_DONE" in log
    assert "SWITCH_BOOTSTRAP_DONE" not in log


def test_lsof_diagnostic_with_exit_one_is_an_error_not_an_empty_port(box) -> None:
    _add_venv(box["snap"])
    result = box["run"](box["sha"], extra_env={
        "LSOF_RC": "1", "LSOF_STDERR": "lsof: cannot inspect sockets", "LSOF_FAIL_COUNT": "1",
    })
    log = (box["record"] / "switch.log").read_text()
    assert result.returncode == 4
    assert box["link"].resolve() == box["old"].resolve()
    assert "cannot inspect sockets" in log
    assert f"--rev {box['sha']}" not in box["effects"].read_text()


def test_rollback_waits_for_asynchronous_unload_before_starting_previous_runtime(box, tmp_path: Path) -> None:
    _add_venv(box["snap"])
    result = box["run"](box["sha"], extra_env={
        "BOOTSTRAP_FAIL_COUNT": "3", "BOOTSTRAP_COUNT_FILE": str(tmp_path / "bootstrap-count"),
        "ROLLBACK_PRINTS_REQUIRED": "2", "AFTER_BOOTSTRAP_PRINT_FILE": str(tmp_path / "rollback-prints"),
    })
    assert result.returncode == 6, result.stderr
    assert box["link"].resolve() == box["old"].resolve()
    assert "ROLLBACK_DONE" in (box["record"] / "switch.log").read_text()


def test_relative_previous_link_is_resolved_for_rollback_accounting(box, tmp_path: Path) -> None:
    _add_venv(box["snap"])
    target = ".finance-runtime/finance-workspace-old"
    box["link"].unlink()
    box["link"].symlink_to(target)
    result = box["run"](box["sha"], extra_env={
        "BOOTSTRAP_FAIL_COUNT": "3", "BOOTSTRAP_COUNT_FILE": str(tmp_path / "bootstrap-count"),
    })
    assert result.returncode == 6
    assert box["link"].readlink() == Path(target)
    assert f"--rev {box['old_sha']}" in box["effects"].read_text()


def test_failed_rollback_accounting_is_reported_even_if_previous_service_starts(box, tmp_path: Path) -> None:
    _add_venv(box["snap"])
    result = box["run"](box["sha"], extra_env={
        "BOOTSTRAP_FAIL_COUNT": "3", "BOOTSTRAP_COUNT_FILE": str(tmp_path / "bootstrap-count"),
        "ROLLBACK_LEDGER_RC": "8",
    })
    assert result.returncode == 7
    assert box["link"].resolve() == box["old"].resolve()
    log = (box["record"] / "switch.log").read_text()
    assert "ROLLBACK_LEDGER_FAILED rc=8" in log
    assert "ROLLBACK_DONE" not in log


def test_bootout_error_recovers_previous_runtime_if_job_is_already_unloaded(box) -> None:
    _add_venv(box["snap"])
    result = box["run"](box["sha"], extra_env={"BOOTOUT_RC": "7"})
    assert result.returncode == 4
    assert box["link"].resolve() == box["old"].resolve()
    assert "ROLLBACK_DONE" in (box["record"] / "switch.log").read_text()


def test_dirty_previous_snapshot_aborts_before_touching_the_service(box) -> None:
    _add_venv(box["snap"])
    (box["old"] / "stray.txt").write_text("unverified rollback changes")
    result = box["run"](box["sha"])
    assert result.returncode == 2
    assert "previous runtime snapshot is dirty" in result.stderr
    assert "launchctl" not in box["effects"].read_text()
