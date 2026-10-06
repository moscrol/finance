"""切 8792 的前置核验：不过就不碰服务、不动链接。

2026-10-06 切 f3b97499aaff 时快照缺 .venv-workbench，启动器 exit 127 循环重启约 5 分钟；
2026-09-27 bootout 后立刻 bootstrap 撞 I/O error。这里用假的 launchctl / lsof 跑脚本，
只看它对服务和链接做了什么，不碰真实生产。
"""

from pathlib import Path
import shutil
import subprocess

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
    old.mkdir()
    link = home / "finance-workspace-runtime"
    link.symlink_to(old)
    effects = tmp_path / "effects"
    effects.write_text("")
    fakebin = tmp_path / "bin"
    # print 失败 = 已卸载；bootout / bootstrap 成功。
    _tool(fakebin / "launchctl", 'echo "launchctl $*" >> "$EFFECTS"\n[ "$1" = print ] && exit "${PRINT_RC:-1}"\nexit 0\n')
    _tool(fakebin / "lsof", 'exit 1\n')

    def run(revision: str, *, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
        env = {
            "HOME": str(home), "PATH": f"{fakebin}:/usr/bin:/bin", "EFFECTS": str(effects),
            "FINANCE_WS": str(tmp_path / "ws"), **(extra_env or {}),
        }
        return subprocess.run(
            [BASH, str(SCRIPT), revision, str(tmp_path / "record")],
            env=env, capture_output=True, text=True, timeout=60,
        )

    return {"sha": sha, "snap": snap, "old": old, "link": link, "effects": effects, "run": run}


def _add_venv(snap: Path) -> None:
    _tool(snap / ".venv-workbench/bin/python", 'echo "python $*" >> "$EFFECTS"\nexit 0\n')


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


def test_service_that_never_unloads_keeps_the_old_link(box) -> None:
    _add_venv(box["snap"])

    result = box["run"](box["sha"], extra_env={"PRINT_RC": "0", "WORKBENCH_UNLOAD_WAIT_SECONDS": "2"})

    assert result.returncode == 3
    assert box["link"].resolve() == box["old"].resolve()
    assert "bootstrap" not in box["effects"].read_text()
