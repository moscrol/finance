"""launchd 评估/运维环接线：解释器、树指针、健康日志。

红线：修接线不修判分。这些测试只锁「用哪个 python、从哪棵树跑、失败看不看得见」，
不锁 fidelity/pit 的分数口径。
"""
from __future__ import annotations

import os
import plistlib
import stat
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
OPS_PYTHON_SH = ROOT / "scripts" / "lib" / "ops_python.sh"
WRAPPERS = [
    ROOT / "scripts" / "run_fidelity_daily_agent.sh",
    ROOT / "scripts" / "run_fidelity_forward_acceptance.sh",
    ROOT / "scripts" / "freeze_daily_pit_snapshot.sh",
    ROOT / "skills" / "daily-full-review" / "scripts" / "nightly_full_review.sh",
]
FIDELITY_PLISTS = [
    ROOT / "intelligence" / "eval" / "com.financeworkspace.fidelity-daily-agent.plist",
    ROOT / "intelligence" / "eval" / "com.financeworkspace.fidelity-forward-acceptance.plist",
    ROOT / "intelligence" / "eval" / "com.financeworkspace.pit-snapshot.plist",
]
SPLIT_REVIEW_PLISTS = [
    ROOT / "intelligence" / "dream" / "com.financeworkspace.daily-full-review-sync.plist",
    ROOT / "intelligence" / "dream" / "com.financeworkspace.daily-full-review-finalize.plist",
]
BUILD_PLIST = (
    ROOT
    / "skills"
    / "checkpoint-recheck-mac-setup"
    / "scripts"
    / "build_plist.py"
)
CLT_PYTHON = "/usr/bin/python3"
RUNTIME = "/Users/a77/finance-workspace-runtime"  # path-literal-ok: 本机 launchd 树指针契约
VENV_PYTHON = "/Users/a77/finance-workspace-private/.venv-workbench/bin/python"  # path-literal-ok: 本机 workbench venv 契约
LOCAL_BIN = "/Users/a77/.local/bin"  # path-literal-ok: 本机 wrapper 安装落点


def _zsh_source_ops(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    merged.update(env)
    return subprocess.run(
        [
            "/bin/zsh",
            "-c",
            f'source "{OPS_PYTHON_SH}" && printf %s "$OPS_PYTHON"',
        ],
        capture_output=True,
        text=True,
        env=merged,
        check=False,
    )


def test_ops_python_helper_exists() -> None:
    assert OPS_PYTHON_SH.is_file()


def test_ops_python_picks_workbench_venv(tmp_path: Path) -> None:
    venv_py = tmp_path / ".venv-workbench" / "bin" / "python"
    venv_py.parent.mkdir(parents=True)
    venv_py.write_text("#!/bin/zsh\n", encoding="utf-8")
    venv_py.chmod(venv_py.stat().st_mode | stat.S_IXUSR)
    result = _zsh_source_ops(
        {
            "FINANCE_WS": str(tmp_path),
            "FINANCE_PYTHON": "",
            "FINANCE_CODE_ROOT": "",
            "HOME": str(tmp_path / "home"),
        }
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == str(venv_py)


def test_ops_python_rejects_clt_python_even_when_forced(tmp_path: Path) -> None:
    result = _zsh_source_ops(
        {
            "FINANCE_PYTHON": CLT_PYTHON,
            "FINANCE_WS": str(tmp_path),
            "FINANCE_CODE_ROOT": "",
            "HOME": str(tmp_path / "home"),
        }
    )
    assert result.returncode != 0
    assert "CLT" in result.stderr or "usr/bin/python3" in result.stderr


@pytest.mark.parametrize("script", WRAPPERS)
def test_job_wrappers_use_ops_python_not_clt(script: Path) -> None:
    text = script.read_text(encoding="utf-8")
    assert script.is_file()
    assert "ops_python.sh" in text
    assert "OPS_PYTHON" in text
    assert "Path(sys.argv[1]).name[:10]" not in text
    if script.name == "run_fidelity_daily_agent.sh":
        assert 'sys.argv[2]' in text


@pytest.mark.parametrize("plist_path", FIDELITY_PLISTS)
def test_fidelity_plists_pin_runtime_tree_and_venv(plist_path: Path) -> None:
    with plist_path.open("rb") as handle:
        plist = plistlib.load(handle)
    env = plist["EnvironmentVariables"]
    assert env["FINANCE_CODE_ROOT"] == RUNTIME
    assert env["FINANCE_PYTHON"] == VENV_PYTHON
    args = plist["ProgramArguments"]
    assert args[0] == "/bin/zsh"
    script = args[1]
    assert script.startswith(f"{LOCAL_BIN}/")
    assert CLT_PYTHON not in args
    assert "finance-workspace-recheck" not in script
    assert "-standalone" not in script


@pytest.mark.parametrize("plist_path", SPLIT_REVIEW_PLISTS)
def test_split_review_plists_are_repo_sourced(plist_path: Path) -> None:
    with plist_path.open("rb") as handle:
        plist = plistlib.load(handle)
    env = plist.get("EnvironmentVariables") or {}
    assert env.get("FINANCE_PYTHON") == VENV_PYTHON
    joined = " ".join(plist["ProgramArguments"])
    assert CLT_PYTHON not in joined
    assert "-standalone" not in joined
    health = env.get("FINANCE_OPS_HEALTH_LOG", "")
    assert "ops-health.log" in health


def test_review_sync_plist_source_carries_tiered_plan() -> None:
    """切档决定必须落在仓内源，不能只活在 ~/Library 的装机副本里。

    2026-09-04 切档时只改了装机副本；install_eval_launchd.sh 是 cp 源 → bootstrap，
    下一次安装就会把 REVIEW_SYNC_PLAN 静默冲回 full。这里钉住源里有这个键、且是
    当前生产决定的档位；改档要连这条一起改。"""
    with SPLIT_REVIEW_PLISTS[0].open("rb") as handle:
        plist = plistlib.load(handle)
    env = plist["EnvironmentVariables"]
    assert env.get("REVIEW_SYNC_PLAN") == "auto"


def test_checkpoint_installer_defaults_to_venv_and_runtime() -> None:
    text = BUILD_PLIST.read_text(encoding="utf-8")
    assert 'os.environ.get("PYTHON", "/usr/bin/python3")' not in text
    assert ".venv-workbench/bin/python" in text
    assert 'os.environ.get("RECHECK_CLONE"' in text
    assert "finance-workspace-runtime" in text
    # 空 clone「只有 logs」不再是缺省。
    assert (
        'os.environ.get("RECHECK_CLONE", os.path.join(HOME, "finance-workspace-recheck"))'
        not in text
    )
