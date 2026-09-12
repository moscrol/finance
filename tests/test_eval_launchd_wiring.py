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


NIGHTLY = ROOT / "skills" / "daily-full-review" / "scripts" / "nightly_full_review.sh"

_FAKE_PYTHON = """#!/bin/sh
printf 'python %s\\n' "$*" >> "$CALL_LOG"
case "$*" in
  *check_daily_review_data.py*"--phase data"*) exit "${FAKE_GUARD_RC:-0}" ;;
  *check_daily_review_data.py*"--phase l2"*) exit "${FAKE_L2_GATE_RC:-0}" ;;
esac
exit 0
"""

_FAKE_MONEYFLOW = """#!/bin/sh
printf 'moneyflow %s\\n' "$*" >> "$CALL_LOG"
exit "${FAKE_MONEYFLOW_RC:-0}"
"""

_FAKE_NOOP = "#!/bin/sh\nexit 0\n"


def _run_nightly_finalize(
    tmp_path: Path,
    *,
    guard_rc: int = 0,
    l2_gate_rc: int = 0,
    moneyflow_rc: int = 0,
    script_text: str | None = None,
) -> tuple[subprocess.CompletedProcess[str], str, str]:
    """真启动 `nightly_full_review.sh finalize`，外呼与写库全换成假执行器。

    为什么必须真跑：原「不许嵌套调 S7」那条是文本断言，且为排除帮助文本过滤掉了以
    ``/bin/zsh /Users`` 开头的行——**真实的嵌套调用恰好长这样**，把它塞回脚本里测试
    照样绿（2026-09-12 变异测试实测）。文本断言挡不住它，只能真跑一遍看 S7 到底有
    没有被执行。

    返回 (完成的进程, 调用流水, zsh xtrace)。``script_text`` 用于变异测试。
    """
    code_root = tmp_path / "code"
    data_root = tmp_path / "data"
    stub_bin = tmp_path / "bin"
    for path in (
        code_root / "skills" / "daily-full-review" / "scripts",
        code_root / "scripts" / "lib",
        code_root / "scripts" / "moneyflow",
        data_root / "state",
        stub_bin,
    ):
        path.mkdir(parents=True, exist_ok=True)

    script = code_root / "skills" / "daily-full-review" / "scripts" / "nightly_full_review.sh"
    script.write_text(
        NIGHTLY.read_text(encoding="utf-8") if script_text is None else script_text,
        encoding="utf-8",
    )
    script.chmod(0o755)

    # 用真的 ops_python.sh：解释器解析不该被假掉，否则测的是夹具不是脚本。
    (code_root / "scripts" / "lib" / "ops_python.sh").write_text(
        OPS_PYTHON_SH.read_text(encoding="utf-8"), encoding="utf-8"
    )
    # 质检闸门只需**存在**（脚本对它 fail closed）；真正的退出码由假 python 给。
    (code_root / "scripts" / "check_daily_review_data.py").write_text("", encoding="utf-8")
    # 刻意不建 scripts/method_validation.py：绑定解析整段跳过，本夹具不测那条链。

    for target, body in (
        (stub_bin / "fake-python", _FAKE_PYTHON),
        (code_root / "scripts" / "moneyflow" / "run_l2_pipeline.sh", _FAKE_MONEYFLOW),
        (stub_bin / "osascript", _FAKE_NOOP),  # 免得真弹本机通知
    ):
        target.write_text(body, encoding="utf-8")
        target.chmod(0o755)

    call_log = tmp_path / "calls.log"
    call_log.write_text("", encoding="utf-8")

    env = os.environ.copy()
    env.update(
        {
            "FINANCE_CODE_ROOT": str(code_root),
            "FINANCE_DATA_ROOT": str(data_root),
            "FINANCE_LOCK_DIR": str(tmp_path / "locks"),
            "FINANCE_PYTHON": str(stub_bin / "fake-python"),
            "FINANCE_OPS_HEALTH_LOG": str(tmp_path / "ops-health.log"),
            "HOME": str(tmp_path / "home"),
            "CALL_LOG": str(call_log),
            "PATH": f"{stub_bin}{os.pathsep}{os.environ['PATH']}",
            "FAKE_GUARD_RC": str(guard_rc),
            "FAKE_L2_GATE_RC": str(l2_gate_rc),
            "FAKE_MONEYFLOW_RC": str(moneyflow_rc),
        }
    )
    proc = subprocess.run(
        ["/bin/zsh", "-x", str(script), "finalize", "2026-09-11"],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(tmp_path),
        check=False,
    )
    return proc, call_log.read_text(encoding="utf-8"), proc.stderr


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


@pytest.mark.parametrize("plist_path", SPLIT_REVIEW_PLISTS)
def test_both_review_plist_sources_carry_the_same_plan(plist_path: Path) -> None:
    """切档决定必须落在仓内源，且 sync 与 finalize **两份都要有**。

    2026-09-04 切档时只改了装机副本；install_eval_launchd.sh 是 cp 源 → bootstrap，
    下一次安装就会把 REVIEW_SYNC_PLAN 静默冲回缺省。原来这条只查 sync 那份，
    2026-09-12 实测 finalize 仓内源**从来没有这个键**（装机副本被手工加过 local）：
    三道质检闸门的 `--plan` 缺省读这个变量，缺了就按 full 期望裁判，plan=local 下
    不抓的 fact_theme_flow_daily 被判断档 → 守卫中止 → 方法飞轮轮不到。
    一份有一份没有，比两份都没有更难发现。

    档位为什么是 local：零复盘会请求，16 步用 *-local 替身覆盖标签需要的七张表。
    auto 的隐患是非周五 = cheap，而 cheap 仍要 fupanhui 登录态。改档两份一起改。
    """
    with plist_path.open("rb") as handle:
        plist = plistlib.load(handle)
    env = plist["EnvironmentVariables"]
    assert env.get("REVIEW_SYNC_PLAN") == "local", plist_path.name


def test_review_plist_sources_agree_on_plan() -> None:
    """两份源的档位必须一致：sync 抓什么、finalize 就按什么裁判。"""
    plans = set()
    for plist_path in SPLIT_REVIEW_PLISTS:
        with plist_path.open("rb") as handle:
            plans.add(plistlib.load(handle)["EnvironmentVariables"].get("REVIEW_SYNC_PLAN"))
    assert len(plans) == 1, f"sync 与 finalize 档位不一致: {plans}"


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


@pytest.mark.parametrize(
    "script_name",
    ["nightly_full_review.sh", "nightly_full_review_s7.sh"],
)
def test_manual_entries_carry_their_own_defaults(script_name: str) -> None:
    """两个手动入口必须自带缺省，不能靠 plist。

    plist 的 EnvironmentVariables 只作用于 launchd 启动的进程。人在终端手敲
    `nightly_full_review.sh sync|all` 或 `nightly-full-review-s7.sh <date>` 一个都拿不到：
    2026-09-12 干净 shell 实测，SYNC_CODE_ROOT 退到运行快照、REVIEW_SYNC_PLAN 未设 →
    CLI 默认 full → 要 fupanhui 登录态 → rc=3 停在 preflight。
    「两份 plist 同值」只保证它们启动的进程，不保证手动补跑。
    """
    script = ROOT / "skills" / "daily-full-review" / "scripts" / script_name
    text = script.read_text(encoding="utf-8")
    assert '"${REVIEW_SYNC_PLAN:-local}"' in text, "缺档位缺省"
    # 档位要 export，否则子进程（同步器 / 三道闸门）读不到。
    assert "export REVIEW_SYNC_PLAN=" in text
    if script_name == "nightly_full_review_s7.sh":
        # 只有 S7 这条路还起同步子进程，所以只有它需要同步代码根。
        assert f'"${{FINANCE_SYNC_CODE_ROOT:-{SYNC_CODE_ROOT}}}"' in text


def test_nightly_closes_the_staging_bypassing_sync_phases() -> None:
    """`nightly_full_review.sh` 不许再有一条直调同步器的路。

    同步器自己**不做** staging：写的就是 MARKET_FEATURE_STORE_DB 指向的库，也就是
    生产库。克隆 / 过闸 / 原子换名全在 nightly-review-sync-staged.py 里，只有 S7 入口
    走得到。上一版只把 SKILL.md 的推荐改走 S7，代码路径没关——**改了推荐不等于关了
    旁路**，而缺省 PHASE 就是 all，`nightly_full_review.sh <日期>` 一句就落回旁路。

    拒绝必须在加锁之前：本脚本持 daily-full-review.lock，S7 抢同一把锁，
    所以也不能在本脚本里套 S7（会变成自己抢自己的锁）。
    """
    nightly = ROOT / "skills" / "daily-full-review" / "scripts" / "nightly_full_review.sh"
    text = nightly.read_text(encoding="utf-8")
    lines = text.splitlines()

    # 1. 非注释行里一处 run_review_sync.py 调用都不许有。
    live = [ln for ln in lines if "run_review_sync.py" in ln and not ln.lstrip().startswith("#")]
    assert not live, f"仍有直调同步器的活代码：{live}"
    assert "run_sync()" not in text.replace("# run_sync()", "")

    # 2. 非 finalize 一律拒绝。
    assert 'if [ "$PHASE" != "finalize" ]; then' in text

    # 3. 拒绝点必须早于加锁，否则会留下锁目录。
    guard_at = next(i for i, ln in enumerate(lines) if 'if [ "$PHASE" != "finalize" ]' in ln)
    lock_at = next(i for i, ln in enumerate(lines) if 'mkdir "$LOCK_DIR"' in ln)
    assert guard_at < lock_at, f"拒绝点 {guard_at} 晚于加锁 {lock_at}"

    # 4. 「不许在本脚本里调 S7」改由行为测试承担，见
    #    test_nightly_finalize_never_invokes_s7。原先这里是文本断言，且为排除帮助
    #    文本过滤掉了以 "/bin/zsh /Users" 开头的行——真实嵌套调用恰好是那个形状，
    #    塞回去测试照样绿（变异测试实测）。别把它改回文本断言。


def test_nightly_finalize_attempts_l2_even_when_the_sync_guard_fails(tmp_path: Path) -> None:
    """同步守卫失败时，L2 仍然被尝试；生成段仍然被挡住。（工单 #51）

    L2 读的是逐笔日包，不依赖同步段产物。这条不变量原先只钉在 `all)` 分支的测试里，
    而生产是 sync plist + finalize plist 两个独立 job，`finalize)` 里守卫在前、L2 在
    后——**生产路径从未满足过它**，代价是 feature_l2_* 两表 9-10 / 9-11 两天没有行。
    """
    proc, calls, _ = _run_nightly_finalize(tmp_path, guard_rc=1)

    # 夹具自证：真的走进了 finalize，不是在更早的地方就退了（否则下面全是空过）。
    assert "moneyflow " in calls, f"L2 段根本没被调用，夹具没走到 finalize：\n{calls}\n{proc.stderr[-2000:]}"
    assert "--phase l2" in calls, f"L2 质量门没跑：\n{calls}"

    # 守卫失败 → 退出码是守卫的，生成段不许跑。
    assert proc.returncode == 1, f"期望以守卫退出码 1 退出，实际 {proc.returncode}"
    assert "intelligence.cli daily" not in calls, f"同步守卫没通过却跑了生成段：\n{calls}"

    # L2 必须排在守卫之前——顺序反了就又回到「同步失败连坐 L2」。
    assert calls.index("moneyflow ") < calls.index("--phase data"), (
        f"L2 仍排在同步守卫之后：\n{calls}"
    )


def test_nightly_finalize_happy_path_still_runs_generation(tmp_path: Path) -> None:
    """守卫绿时行为不变：L2 → 守卫 → 生成段 → 方法飞轮，退出 0。（工单 #51 验收 2）

    把 L2 提到守卫之前，只解除「同步失败连坐 L2」，**不放宽生成段的门**。
    """
    proc, calls, _ = _run_nightly_finalize(tmp_path, guard_rc=0)

    assert "moneyflow " in calls, f"L2 段没跑：\n{calls}"
    assert "--phase data" in calls, f"同步守卫没跑：\n{calls}"
    assert "intelligence.cli daily" in calls, f"守卫放行了却没跑生成段：\n{calls}"
    assert proc.returncode == 0, f"顺利路径应退 0，实际 {proc.returncode}\n{proc.stderr[-2000:]}"


def test_nightly_finalize_blocks_generation_when_l2_fails(tmp_path: Path) -> None:
    """L2 失败仍然挡住生成段——提前跑 L2 不等于放宽它。（工单 #51「不要做」第 2 条）"""
    proc, calls, _ = _run_nightly_finalize(tmp_path, guard_rc=0, moneyflow_rc=1)

    assert "moneyflow " in calls, f"L2 段没跑：\n{calls}"
    assert "intelligence.cli daily" not in calls, f"L2 失败却跑了生成段：\n{calls}"
    assert proc.returncode == 1, f"L2 失败应退 1，实际 {proc.returncode}"


def test_nightly_finalize_never_invokes_s7(tmp_path: Path) -> None:
    """本脚本不许嵌套调 S7：两者抢同一把 daily-full-review.lock，会自己锁死自己。

    行为测试而非文本断言——理由见 `_run_nightly_finalize` 的 docstring。
    finalize 分支里那段印推荐命令的 heredoc 根本不会执行，所以 xtrace 里只要出现
    S7，就一定是真的调用了它。
    """
    proc, calls, xtrace = _run_nightly_finalize(tmp_path, guard_rc=0)

    # 先自证夹具真的跑到了 finalize，否则「没调 S7」是空过。
    assert "moneyflow " in calls, f"夹具没走到 finalize：\n{calls}\n{proc.stderr[-2000:]}"

    assert "nightly-full-review-s7" not in xtrace, (
        "finalize 里执行了 S7（会抢自己持有的锁）：\n"
        + "\n".join(ln for ln in xtrace.splitlines() if "nightly-full-review-s7" in ln)
    )


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
