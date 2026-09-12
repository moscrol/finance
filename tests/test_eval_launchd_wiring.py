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
SYNC_CODE_ROOT = "/Users/a77/finance-workspace-sync"  # path-literal-ok: 本机 sync 专用代码根契约
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


def test_nightly_resolves_quality_gate_from_code_root_not_workspace() -> None:
    """质检闸门必须从 CODE_ROOT 取，不能落在 `cd "$WORKSPACE"` 之后的裸相对路径。

    WORKSPACE=DATA_ROOT=各 agent 共用的主检出树，停在任意 detached 提交上。
    2026-09-12 实测：同一天、同一库、同一 REVIEW_SYNC_PLAN=local，主检出树那份
    检查器 exit=2 INCOMPLETE（没有 --plan，写死的表清单要 fact_theme_flow_daily），
    CODE_ROOT 那份 exit=0 COMPLETE。闸门读错树 = 数据齐了也判断档，
    20:40 守卫中止，方法飞轮永远轮不到。
    """
    nightly = ROOT / "skills" / "daily-full-review" / "scripts" / "nightly_full_review.sh"
    text = nightly.read_text(encoding="utf-8")
    assert 'REVIEW_CHECKER="$CODE_ROOT/scripts/check_daily_review_data.py"' in text
    # 裸相对路径调用一处都不许留（注释里提它可以，调用不行）。
    call_lines = [
        line
        for line in text.splitlines()
        if "check_daily_review_data.py" in line and not line.lstrip().startswith("#")
    ]
    assert call_lines, "没找到质检闸门调用，测试本身失效了"
    for line in call_lines:
        assert "$REVIEW_CHECKER" in line or "REVIEW_CHECKER=" in line, line
    # 三个 phase 都得走同一份。
    for phase in ("--phase l2", "--phase all", "--phase data"):
        assert f'"$OPS_PYTHON" "$REVIEW_CHECKER" "$D" {phase}' in text, phase
    # 缺了要停，不许回退到 WORKSPACE 那份顶替。
    assert '[ ! -f "$REVIEW_CHECKER" ]' in text
    assert '$WORKSPACE/scripts/check_daily_review_data.py' not in text


def test_review_sync_plist_source_pins_dedicated_sync_code_root() -> None:
    """sync 子进程的代码根必须显式钉住，不能退到共用的数据仓。

    nightly-review-sync-staged.py 的 SYNC_ROOT 缺省是 FINANCE_DATA_ROOT，而数据仓
    就是各 agent 共用的主检出树，会停在任意 detached 提交上：
    2026-09-12 实测它落后 main 548 个提交，`PLANS` 里没有 local，
    夜跑 09-10~09-11 连着三次 `unknown plan 'local'` rc=2，09-11 整个交易日没进库。
    缺省值在代码里，所以只有 plist 显式给值才挡得住；这条钉住它别再被删。

    也不能指回 FINANCE_CODE_ROOT（运行快照）：那是部分 rsync，缺 L2 与题材资金源。
    """
    with SPLIT_REVIEW_PLISTS[0].open("rb") as handle:
        plist = plistlib.load(handle)
    env = plist["EnvironmentVariables"]
    assert env.get("FINANCE_SYNC_CODE_ROOT") == SYNC_CODE_ROOT
    assert env["FINANCE_SYNC_CODE_ROOT"] != env.get("FINANCE_DATA_ROOT")
    assert env["FINANCE_SYNC_CODE_ROOT"] != env.get("FINANCE_CODE_ROOT")


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
