"""scripts/mutation_check.py：每个测试钉住模块 docstring 里的一个失败形状。

夹具是 tmp_path 里的一个小 git 仓（calc.py + test_calc.py，自带空 pytest.ini 定死 rootdir），
工具以子进程方式真跑——它本身就要起 pytest 子进程、装信号处理、打一行一个 mutant 的输出，
进程内调用测不到这几层。夹具仓只有几条测试，单轮 pytest 约 0.2 s。

字节码陷阱用 UNCHECKED_HASH 的 .pyc 确定性复现：真实陷阱是「同秒 + 同长度」让按时间戳校验的
.pyc 仍被判有效，靠时钟撞不稳定；不校验源文件的 .pyc 会被无条件采信，效果相同且每次必现。

同一个失败形状有两层防御的地方（还原点三道核验、红错原因两条分支、并发两处核对），
每层各有一个只有它能拦住的用例——否则拆掉任一层，另一层接住，测试照绿。
"""

from __future__ import annotations

import importlib.util
import json
import os
import py_compile
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "mutation_check.py"
_spec = importlib.util.spec_from_file_location("mutation_check_under_test", SCRIPT)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

CALC = """\
LIMIT = 10


def add(a, b):
    return a + b


def clamp(x):
    return min(x, LIMIT)
"""

TESTS = """\
import calc


def test_add():
    assert calc.add(2, 3) == 5


def test_add_zero():
    assert calc.add(0, 0) == 0


def test_clamp():
    assert calc.clamp(99) == 10
"""

PLUS_TO_MINUS = {"name": "plus-to-minus", "old": "return a + b", "new": "return a - b",
                 "expected_red": ["test_add"]}

# 每轮都把磁盘上的 calc.py 编成「不校验源文件」的 .pyc 留在 __pycache__：
# 模拟同秒同长度留下、且仍被判有效的过期字节码。
TRUSTED_CACHE_WRITER = """

def test_zz_leave_trusted_bytecode():
    source = calc.__file__
    import importlib.util, py_compile
    py_compile.compile(source, cfile=importlib.util.cache_from_source(source),
                       invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH)
"""

# 模拟另一个 agent 在同一棵树上改被变异文件：mutant 轮（calc.add 已坏）或基线轮（第一次跑）。
EDIT_DURING_MUTANT_RUN = """

def test_zz_someone_else_edits_calc():
    if calc.add(2, 3) != 5:
        with open(calc.__file__, "a", encoding="utf-8") as fh:
            fh.write("# edited by someone else\\n")
"""
EDIT_DURING_BASELINE = """

def test_zz_someone_else_edits_calc():
    import os, pathlib
    flag = pathlib.Path(os.environ["MUTATION_CHECK_TEST_MARKER"])
    if not flag.exists():
        flag.write_text("edited")
        with open(calc.__file__, "a", encoding="utf-8") as fh:
            fh.write("# edited by someone else\\n")
"""

# 只在变异轮里挂住：起一个同进程组的孙进程，把两个 pid 写进 marker，然后睡到被杀。
HANG_UNDER_MUTANT = """

def test_zz_hang_under_mutant():
    if calc.add(2, 3) != 5:
        import os, pathlib, subprocess, sys, time
        grandchild = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
        pathlib.Path(os.environ["MUTATION_CHECK_TEST_MARKER"]).write_text(f"{os.getpid()} {grandchild.pid}")
        time.sleep(120)
"""

# 红错原因的两条分支各要一个只有它拦得住的用例（见 test_red_for_the_wrong_reason_is_not_a_kill）。
WRONG_REASON_TESTS = """\
import pytest


@pytest.fixture
def limit():
    import calc
    assert calc.LIMIT == 10, "fixture precondition"
    return calc.LIMIT


def test_clamp_via_fixture(limit):
    import calc
    assert calc.clamp(99) == limit


def test_lazy_add():
    import calc
    assert calc.add(2, 3) == 5
"""


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout


def _commit(repo: Path, name: str, content: str) -> None:
    (repo / name).write_text(content, encoding="utf-8")
    _git(repo, "add", name)
    _git(repo, "commit", "-qm", f"fixture {name}")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (root / "calc.py").write_text(CALC, encoding="utf-8")
    (root / "other.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "test_calc.py").write_text(TESTS, encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "mutation@test")
    _git(root, "config", "user.name", "mutation")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "base")
    return root


def _spec(tmp_path: Path, mutants: list, name: str = "spec.json", **top) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps({"file": "calc.py", "pytest": "test_calc.py", "mutants": mutants, **top},
                               ensure_ascii=False), encoding="utf-8")
    return path


def _check(repo: Path, spec: Path, *extra: str, env: dict | None = None) -> tuple[int, list, dict]:
    proc = subprocess.run([sys.executable, str(SCRIPT), str(spec), "--repo", str(repo), *extra],
                          capture_output=True, text=True, timeout=180, env=env)
    lines = proc.stdout.strip().splitlines()
    try:
        summary = json.loads(lines[-1])
    except (IndexError, ValueError):
        pytest.fail(f"末行不是 JSON 汇总\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}")
    return proc.returncode, lines[:-1], summary


def _assert_pristine(repo: Path) -> None:
    assert (repo / "calc.py").read_text(encoding="utf-8") == CALC
    assert _git(repo, "status", "--porcelain", "--untracked-files=no") == ""


def _gone(pid: int, timeout: float = 10) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.05)
    return False


# ——— 判定本身：承重 / 不承重 / 红错原因 ———

def test_killed_and_survived_are_told_apart_and_the_tree_comes_back(repo, tmp_path):
    """同一处 + → -：test_add 钉得住；test_add_zero（0+0 == 0-0）钉不住——后者就是「测试不承重」。"""
    summary_file = tmp_path / "out" / "summary.json"
    spec = _spec(tmp_path, [
        PLUS_TO_MINUS,
        {**PLUS_TO_MINUS, "name": "zero-cannot-see-it", "expected_red": ["test_add_zero"]},
        {**PLUS_TO_MINUS, "name": "partial", "expected_red": ["test_add", "test_add_zero"]},
        {"name": "never-imported", "file": "other.py", "old": "VALUE = 1", "new": "VALUE = 2",
         "expected_red": ["test_add"]},
    ])
    code, lines, summary = _check(repo, spec, "--summary-json", str(summary_file))

    assert code == 1 and summary["status"] == "not_load_bearing" and summary["exit_code"] == 1
    got = {m["name"]: m for m in summary["mutants"]}
    killed = got["plus-to-minus"]
    assert killed["verdict"] == "killed" and killed["red"] == ["test_calc.py::test_add"]
    assert killed["imported"] is True and killed["restored"] is True
    survived = got["zero-cannot-see-it"]
    assert survived["verdict"] == "survived"
    assert survived["not_red"] == {"test_calc.py::test_add_zero": "passed"}
    assert survived["other_red"] == ["test_calc.py::test_add"]  # 别的测试红了不替它承重
    partial = got["partial"]  # 点名两条只红一条：子集判定，不是「有红就算」
    assert partial["verdict"] == "survived" and partial["red"] == ["test_calc.py::test_add"]
    never = got["never-imported"]
    assert never["verdict"] == "survived" and never["imported"] is False and never["warnings"]
    assert summary["counts"] == {"killed": 1, "survived": 3}
    assert [line.split()[0] for line in lines[1:5]] == ["KILLED", "SURVIVED", "SURVIVED", "SURVIVED"]
    assert json.loads(summary_file.read_text(encoding="utf-8")) == summary
    _assert_pristine(repo)
    assert (repo / "other.py").read_text(encoding="utf-8") == "VALUE = 1\n"


def test_red_for_the_wrong_reason_is_not_a_kill(repo, tmp_path):
    """import 就炸（收集期报错）与夹具 setup 报错：点名测试「红了」，但被测行为一步没跑到。

    `--continue-on-collection-errors` 让 test_calc.py 收集失败时 test_lazy_add 照跑、红在
    ModuleNotFoundError 上——这时只有「收集期报错」那条分支能拦；setup 报错只有「点名测试没以
    断言失败的方式变红」那条能拦。默认配置下收集报错会让所有测试都不跑，两条分支互相接住。
    """
    _commit(repo, "test_extra.py", WRONG_REASON_TESTS)
    spec = _spec(tmp_path, [
        {"name": "import-break", "old": "LIMIT = 10", "new": "LIMIT = 10\nimport no_such_module_for_mutation_check",
         "expected_red": ["test_lazy_add"]},
        {"name": "setup-error", "old": "LIMIT = 10", "new": "LIMIT = 11", "expected_red": ["test_clamp_via_fixture"]},
    ], pytest=["test_calc.py", "test_extra.py"], pytest_args=["--continue-on-collection-errors"])
    code, lines, summary = _check(repo, spec)
    got = {m["name"]: m for m in summary["mutants"]}
    assert code == 1 and {name: m["verdict"] for name, m in got.items()} == {
        "import-break": "wrong_reason", "setup-error": "wrong_reason"}
    assert got["import-break"]["collect_errors"] and got["import-break"]["red"] == ["test_extra.py::test_lazy_add"]
    assert got["setup-error"]["not_red"] == {"test_extra.py::test_clamp_via_fixture": "error"}
    assert [line.split()[0] for line in lines[1:3]] == ["WRONG", "WRONG"]
    _assert_pristine(repo)


def test_expected_message_pins_why_it_went_red(repo, tmp_path):
    spec = _spec(tmp_path, [
        {**PLUS_TO_MINUS, "name": "right-reason", "expected_message": r"assert -1 == 5"},
        {**PLUS_TO_MINUS, "name": "wrong-reason", "expected_message": r"ZeroDivisionError"},
    ])
    code, _, summary = _check(repo, spec)
    assert code == 1
    assert {m["name"]: m["verdict"] for m in summary["mutants"]} == {
        "right-reason": "killed", "wrong-reason": "wrong_reason"}


def test_red_on_a_deleted_symbol_is_flagged_but_still_counted(repo, tmp_path):
    spec = _spec(tmp_path, [{"name": "drop-limit", "old": "LIMIT = 10\n", "new": "",
                             "expected_red": ["test_clamp"]}])
    code, lines, summary = _check(repo, spec)
    mutant = summary["mutants"][0]
    assert code == 0 and summary["status"] == "ok" and mutant["verdict"] == "killed"
    assert "NameError" in mutant["messages"]["test_calc.py::test_clamp"]
    assert any("符号层" in w for w in mutant["warnings"]) and "符号层" in lines[1]


# ——— 前置条件：测不成就一轮也不跑，树原样不动 ———

def test_anchor_and_syntax_problems_stop_everything_before_any_run(repo, tmp_path):
    spec = _spec(tmp_path, [
        {**PLUS_TO_MINUS, "name": "matches-nothing", "old": "return a * b"},
        {**PLUS_TO_MINUS, "name": "matches-twice", "old": "return ", "new": "return -"},
        {**PLUS_TO_MINUS, "name": "syntax-error", "new": "return a +"},
        PLUS_TO_MINUS,
    ])
    code, lines, summary = _check(repo, spec)
    assert code == 2 and summary["status"] == "precondition_failed"
    assert summary["baseline"] is None and summary["mutants"] == []  # 连基线都没跑
    problems = "\n".join(summary["problems"])
    assert "matches-nothing: old 在 calc.py 里出现 0 次" in problems
    assert "matches-twice: old 在 calc.py 里出现 2 次" in problems
    assert "syntax-error: 变异后 calc.py 语法错" in problems
    assert "plus-to-minus" not in problems
    assert sum(line.startswith("INVALID") for line in lines) == 3
    _assert_pristine(repo)


_UNCOMMITTED_STATES = {
    "modified": "与 HEAD 不一致",
    "staged": "与 HEAD 不一致",
    "staged-then-reverted": "与 HEAD 不一致",  # 工作区 == HEAD、索引不是：只有 git status 看得见
    "untracked": "不在 HEAD 里",
    "assume-unchanged": "内容却与 HEAD 不同",  # git status 说干净：只有与 HEAD blob 比才看得见
}


@pytest.mark.parametrize(("state", "reason"), list(_UNCOMMITTED_STATES.items()), ids=list(_UNCOMMITTED_STATES))
def test_target_without_a_committed_restore_point_is_refused_and_left_alone(repo, tmp_path, state, reason):
    target = repo / ("new.py" if state == "untracked" else "calc.py")
    uncommitted = CALC.replace("LIMIT = 10", "LIMIT = 10  # uncommitted implementation")
    if state == "assume-unchanged":
        _git(repo, "update-index", "--assume-unchanged", "calc.py")
    target.write_text(uncommitted, encoding="utf-8")
    if state.startswith("staged"):
        _git(repo, "add", "calc.py")
    if state == "staged-then-reverted":
        target.write_text(CALC, encoding="utf-8")
    spec = _spec(tmp_path, [{**PLUS_TO_MINUS, "file": target.name}])
    code, _, summary = _check(repo, spec)
    assert code == 2 and summary["baseline"] is None
    assert summary["problems"][0].startswith(f"{target.name}: ") and reason in summary["problems"][0]
    # 未提交的实现原样还在：工作区与索引都没被「还原」
    assert target.read_text(encoding="utf-8") == (CALC if state == "staged-then-reverted" else uncommitted)
    if state.startswith("staged"):
        assert _git(repo, "show", ":calc.py") == uncommitted


def test_misnamed_expected_test_is_a_spec_error_not_a_survivor(repo, tmp_path):
    spec = _spec(tmp_path, [{**PLUS_TO_MINUS, "expected_red": ["test_ad"]}])
    code, _, summary = _check(repo, spec, "--dry-run")
    assert code == 2 and summary["mutants"] == []
    assert "'test_ad' 没被收集到" in summary["problems"][0]
    assert "test_calc.py::test_add" in summary["problems"][0]  # 给出相近的候选
    _assert_pristine(repo)


def test_dry_run_checks_spec_and_collection_without_touching_the_tree(repo, tmp_path):
    spec = tmp_path / "spec.yaml"
    spec.write_text(
        "file: calc.py\npytest: test_calc.py\nmutants:\n"
        "  - name: plus-to-minus\n    old: |-\n      def add(a, b):\n          return a + b\n"
        "    new: |-\n      def add(a, b):\n          return a - b\n"
        "    expected_red: [test_add]\n", encoding="utf-8")
    code, _, summary = _check(repo, spec, "--dry-run")
    assert code == 0 and summary["status"] == "dry_run_ok" and summary["mutants"] == []
    assert summary["baseline"]["collected"] == 3
    _assert_pristine(repo)


@pytest.mark.parametrize("case", ["another-test-red", "expected-test-skipped"])
def test_ruler_that_is_not_green_at_baseline_blocks_every_mutant(repo, tmp_path, case):
    if case == "another-test-red":
        _commit(repo, "test_calc.py", TESTS.replace("== 10", "== 11"))
        expected = ["test_add"]
    else:
        _commit(repo, "test_calc.py", TESTS + "\n\nimport pytest\n\n\n@pytest.mark.skip\ndef test_skipped():\n"
                                              "    assert calc.add(2, 3) == 5\n")
        expected = ["test_skipped"]
    code, lines, summary = _check(repo, _spec(tmp_path, [{**PLUS_TO_MINUS, "expected_red": expected}]))
    assert code == 2 and summary["mutants"] == []
    assert any(line.startswith("BASELINE") for line in lines)
    _assert_pristine(repo)


def test_spec_schema_reports_every_problem_at_once():
    with pytest.raises(mod.SpecError) as err:
        mod.parse_spec({"pytest": "t.py", "file": "calc.py", "mutants": [
            {"name": "a", "old": "x", "new": "y", "expected_red": ["t"], "expected_mesage": "typo"},
            {"name": "b", "old": "x", "new": "x", "expected_red": []},
            {"name": "a", "old": "x", "new": "y", "expected_red": ["t"], "expected_message": "("},
        ]})
    text = str(err.value)
    assert "'expected_mesage'" in text  # 拼错的字段不会被静默忽略
    assert "old 与 new 相同" in text and "expected_red 必须是非空" in text
    assert "name 重复" in text and "expected_message 不是合法正则" in text


# ——— 字节码：三处删除各有一条只有它拦得住的断言 ———

def test_trusted_stale_bytecode_cannot_fake_the_baseline_or_the_mutant_run(repo, tmp_path):
    """基线前删：否则基线跑的是预埋的坏字节码；写入变异后删：否则变异轮跑的是基线留下的原版字节码。"""
    _commit(repo, "test_calc.py", TESTS + TRUSTED_CACHE_WRITER)
    staging = tmp_path / "calc_minus.py"
    staging.write_text(CALC.replace("a + b", "a - b"), encoding="utf-8")
    py_compile.compile(str(staging), cfile=importlib.util.cache_from_source(str(repo / "calc.py")),
                       invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH)
    code, _, summary = _check(repo, _spec(tmp_path, [PLUS_TO_MINUS]))
    assert summary["baseline"]["exit"] == 0, summary["problems"]
    assert code == 0 and summary["mutants"][0]["verdict"] == "killed"


def test_restored_tree_keeps_no_mutant_bytecode(repo, tmp_path):
    """还原后删：变异轮留下的变异体字节码不清掉，之后谁 import calc 都拿到 a - b。"""
    _commit(repo, "test_calc.py", TESTS + TRUSTED_CACHE_WRITER)
    code, _, _ = _check(repo, _spec(tmp_path, [PLUS_TO_MINUS]))
    assert code == 0
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONPYCACHEPREFIX")}
    fresh = subprocess.run([sys.executable, "-c", "import calc; print(calc.add(2, 3))"],
                           cwd=repo, capture_output=True, text=True, env=env)
    assert fresh.stdout.strip() == "5", fresh.stderr


def test_purge_covers_every_tag_and_the_pycache_prefix_mirror(tmp_path, monkeypatch):
    prefix = tmp_path / "prefix"
    monkeypatch.setenv("PYTHONPYCACHEPREFIX", str(prefix))
    source = tmp_path / "pkg" / "calc.py"
    # 镜像位置以解释器自己算的为准，不抄实现里的拼法
    mirrored = subprocess.run(
        [sys.executable, "-c", f"import importlib.util; print(importlib.util.cache_from_source({str(source)!r}))"],
        capture_output=True, text=True, check=True).stdout.strip()
    assert mirrored.startswith(str(prefix)), mirrored
    doomed = [source.parent / "__pycache__" / "calc.cpython-312.pyc",
              source.parent / "__pycache__" / "calc.cpython-39.opt-1.pyc",
              Path(mirrored)]
    spared = source.parent / "__pycache__" / "calc_utils.cpython-312.pyc"
    for path in [*doomed, spared]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"")
    assert sorted(mod.purge_bytecode(source)) == sorted(doomed)
    assert spared.exists() and not any(p.exists() for p in doomed)


def test_child_env_keeps_bytecode_and_receipts_out_of_mutant_runs():
    base = {"PYTHONPATH": "/existing", "FWP_TEST_RECEIPT": "1"}
    mutant = mod.child_env(base, Path("/plugin"), Path("/r.json"), [Path("/w.py")], mutant=True)
    assert mutant["PYTHONPATH"] == os.pathsep.join(["/plugin", "/existing"])
    assert mutant["PYTHONDONTWRITEBYTECODE"] == "1" and mutant["FWP_TEST_RECEIPT"] == "0"
    baseline = mod.child_env(base, Path("/plugin"), Path("/r.json"), [], mutant=False)
    assert baseline["FWP_TEST_RECEIPT"] == "1"  # 基线是真读数，收据照写
    assert base == {"PYTHONPATH": "/existing", "FWP_TEST_RECEIPT": "1"}


# ——— 中断 / 超时 / 并发：树不能留在变异态，也不能覆盖别人的改动 ———

@pytest.mark.parametrize("when", ["during-mutant-run", "during-baseline"])
def test_file_edited_by_someone_else_is_never_overwritten(repo, tmp_path, when):
    """变异轮里被改：还原前核对拦住；基线轮里被改：写入变异前核对拦住（否则那份改动被静默吞掉）。"""
    _commit(repo, "test_calc.py", TESTS + (EDIT_DURING_MUTANT_RUN if when == "during-mutant-run"
                                           else EDIT_DURING_BASELINE))
    env = {**os.environ, "MUTATION_CHECK_TEST_MARKER": str(tmp_path / "marker")}
    spec = _spec(tmp_path, [PLUS_TO_MINUS, {**PLUS_TO_MINUS, "name": "never-reached"}])
    code, lines, summary = _check(repo, spec, env=env)
    assert code == 3 and summary["status"] == "tree_unsafe"
    ran = [m["name"] for m in summary["mutants"]]
    assert ran == (["plus-to-minus"] if when == "during-mutant-run" else [])  # 之后的不再跑
    assert all(m["restored"] is False for m in summary["mutants"])
    assert any(line.startswith("UNSAFE") for line in lines)
    assert (repo / "calc.py").read_text(encoding="utf-8").endswith("# edited by someone else\n")


def test_timeout_is_not_a_kill_and_the_whole_process_group_is_reaped(repo, tmp_path):
    _commit(repo, "test_calc.py", TESTS + HANG_UNDER_MUTANT)
    marker = tmp_path / "marker"
    env = {**os.environ, "MUTATION_CHECK_TEST_MARKER": str(marker)}
    code, lines, summary = _check(repo, _spec(tmp_path, [PLUS_TO_MINUS]), "--timeout", "6", env=env)
    assert code == 1 and summary["mutants"][0]["verdict"] == "timeout"
    assert lines[1].startswith("TIMEOUT")
    assert all(_gone(int(pid)) for pid in marker.read_text().split())  # pytest 与它起的孙进程
    _assert_pristine(repo)


def test_sigterm_mid_run_restores_the_file_and_kills_the_run(repo, tmp_path):
    _commit(repo, "test_calc.py", TESTS + HANG_UNDER_MUTANT)
    marker = tmp_path / "marker"
    proc = subprocess.Popen(
        [sys.executable, str(SCRIPT), str(_spec(tmp_path, [PLUS_TO_MINUS])), "--repo", str(repo)],
        env={**os.environ, "MUTATION_CHECK_TEST_MARKER": str(marker)},
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    deadline = time.monotonic() + 60
    while not (marker.exists() and len(marker.read_text().split()) == 2):
        assert proc.poll() is None, proc.communicate()
        assert time.monotonic() < deadline, "变异轮没按时挂住"
        time.sleep(0.05)
    assert (repo / "calc.py").read_text(encoding="utf-8") != CALC  # 此刻确实在变异态
    proc.send_signal(signal.SIGTERM)
    out, err = proc.communicate(timeout=60)
    assert proc.returncode == 130, (out, err)
    assert json.loads(out.strip().splitlines()[-1])["status"] == "interrupted"
    assert all(_gone(int(pid)) for pid in marker.read_text().split())
    _assert_pristine(repo)
