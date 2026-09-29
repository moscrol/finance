#!/usr/bin/env python3
"""变异自检：按一份 spec 逐个「拆门」，确认点名的测试**因为这一处改动**变红，还原后树与 HEAD 一致。

用在「我写的测试真钉得住实现吗」这一步：把实现里的一处行为改坏（一个 mutant），跑测试，
点名的那几条必须变红（killed = 承重）；改回去，文件必须与 HEAD 逐字节一致。点名测试没红
（survived）= 这条测试对这处改动不承重——或者 spec 写错了，下面 1、5 两条就是为了把后者排除掉。

## 它防的失败形状（带日期的在本仓实际发生过；5 与 7 是同族的保护，7 是原地改树必须自带的）

1. **测的是空气**（2026-08-12、2026-09-15）：替换串一处也没匹配上，「变异」是 no-op，测试跑在
   原代码上照样绿，被读成「测试不承重」，然后去改本来正确的测试。
   → `old` 必须在文件里**恰好出现 1 次**（0 次 = 没拆；≥2 次 = 不知道拆的是哪处）。任一 mutant
   不满足，整份 spec 一轮 pytest 都不跑，退出码 2。
2. **还原把未提交的实现一起清掉**（2026-09-15）：`git checkout -- <file>` 还原到 HEAD，实现没提交就
   跟着变异一起没了，后面几门的替换串在旧文件上匹配不到，又落回形状 1。
   → 被变异文件必须已提交且与 HEAD 一致才开跑（顺序：实现 → 提交 → 拆门）。还原不靠 git：用内存里
   的原字节写回，再核三件事——与原字节相同、`git hash-object` 等于 HEAD 的 blob、`git status` 干净。
   只看 status 不够：assume-unchanged / skip-worktree 的文件改了也显示干净。
3. **过期字节码**（2026-08-01；2026-09-29 写本脚本时复现）：`.pyc` 只按源文件 (mtime 整秒, size) 判
   有效。同长度变异（`+`→`-`）在同一秒内写入，变异那轮 import 的仍是原版字节码（`add(2,3)` 应为
   -1，实得 5）；反过来，还原后留下变异体的 `.pyc`，之后全量里冒出「新回归」。
   → 跑基线前、写入变异后、还原后三处都删被变异模块的全部 `.pyc`（各解释器 tag、opt 级别，
   以及 `PYTHONPYCACHEPREFIX` 镜像处），子进程带 `PYTHONDONTWRITEBYTECODE=1`。后者只减少写入、
   不是保证：测试若用精简 env 另起 python，照样会写——所以三处删除缺一不可。
4. **红错原因**（2026-09-21）：变异后语法错或删了符号，测试红在 SyntaxError / ImportError /
   AttributeError 上，被测行为根本没跑到，「全红」什么也没证明。
   → 变异后的 .py 先 `compile()`；收集期报错、点名测试在 setup 报错 / 被跳过 / 没跑，都判
   `wrong_reason` 而不是承重；红在 NameError / ImportError / `module ... has no attribute` 上的带
   ⚠ 提示（AttributeError 也可能正是被测行为，所以只提示不改判）；spec 可给 `expected_message`
   （正则）把「必须红在这句断言上」钉死。
5. **尺子本身是红的，或名字写错了**：点名测试没变异时就不绿（本来就坏 / 被跳过），或名字拼错根本没
   收集到——变异后「没红」或「红」都不归这个 mutant。
   → 先跑一轮基线：pytest 必须 exit 0；每个点名测试必须恰好对应一条收集到的 node id，且在基线里
   passed。拼错的名字在这里报 spec 错，不会被读成「不承重」。
6. **部分红被读成全红**（2026-09-14）：参数化测试只红了一部分，其余变体被邻近的门接住；「有红就算」
   会把「这门只对其中一类反例承重」夸大成「整条验收都钉住了」。
   → 判据是**子集**：点名的每一条都必须红；没点名但也红了的只记进 `other_red`，不影响判定。
   点名哪几个变体由你决定，工具不替你推断。
7. **中断 / 并发把树留在变异态**：Ctrl-C、SIGTERM、SIGHUP、超时都先杀掉整个 pytest 进程组再还原，
   写入与还原那几行屏蔽信号。写回前核对文件仍是本脚本写入的变异体（开跑前也核对仍是原文件）——
   期间被别人改过就拒绝覆盖、退出码 3、留现场。开跑前与 HEAD 一致，所以 `git checkout -- <file>`
   永远能兜底。

## 和仓内其他变异件的分工

- `scripts/review_probes/run_extraction_mutations.py`：证据级。冻结 revision、临时 detached worktree、
  定义必须入库、留 JUnit / 日志证据目录，判据是「选中的测试里有失败」。给工单验收用。
- `scripts/review_probes/run_*_mutations.py`、`history_diagnostic_mutations.py`：在子进程内存里
  monkeypatch，不改源码。
- 本脚本：作者侧快速回路。在你自己的树里原地改、原地还原；spec 放哪都行（如
  `~/.finance-runtime/reviews/<任务>/`）；判据是点名子集。**会短暂改动工作树**：跑在你认领的
  worktree 里，别在别人正在跑测试的树上跑。

## spec（JSON；装了 PyYAML 时也收 .yaml / .yml——多行代码用 `|-` 块，别带尾换行）

    {
      "file": "scripts/gitea_pr.py",        # 缺省被变异文件（仓根相对），mutant 里可逐个覆盖
      "pytest": "tests/test_gitea_pr.py",   # 字符串或列表：路径 / node id；cwd = 仓根
      "pytest_args": ["-k", "merge"],       # 可选。别给 -x / --maxfail：点名测试会没跑到
      "mutants": [
        {"name": "M6 默认超时写回 30 s",
         "old": "_API_TIMEOUT_DEFAULT_S = 300.0",
         "new": "_API_TIMEOUT_DEFAULT_S = 30.0",
         "expected_red": ["test_api_timeout_default_env_override_and_rejects_bad_values"],
         "expected_message": "assert 30\\\\.0 == 300\\\\.0"}     # 可选
      ]
    }

`expected_red` 写完整 node id（`tests/x.py::TestA::test_b[p]`）或它 `::` 之后的后缀（`test_b[p]`），
必须唯一对应基线收集到的一条；参数化测试要点名到变体。未知字段直接报错——拼错的
`expected_mesage` 不会被静默忽略成「没钉原因」。

## 输出与退出码

基线一行，每个 mutant 一行（KILLED / SURVIVED / WRONG / TIMEOUT），末行是一行 JSON 汇总
（`--summary-json PATH` 另存一份；非 killed 的带 pytest 输出末尾，`--log-dir` 存完整日志）。
变异轮不写本仓 conftest 的测试收据（`FWP_TEST_RECEIPT=0`）：故意改坏的树上的红读数不是任何
revision 的证据，写了只会把 latest.json 指到一张脏收据；基线轮照常写。

    0    全部承重
    1    有 mutant 不承重（survived / wrong_reason / timeout）
    2    没测成：spec、前置条件或基线不满足
    3    还原失败或文件被并发改动——树可能不在原样，按提示人工处理
    130  被中断（已还原）

用法（仓根；执行本脚本的解释器也是跑 pytest 的解释器，`--python` 可改）：
    .venv-workbench/bin/python scripts/mutation_check.py spec.json
    .venv-workbench/bin/python scripts/mutation_check.py spec.yaml --dry-run    # 只验 spec、锚点与收集
    .venv-workbench/bin/python scripts/mutation_check.py spec.json --summary-json out.json --log-dir logs/
"""

from __future__ import annotations

import argparse
import contextlib
import glob
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import NamedTuple, Optional

EXIT_OK = 0
EXIT_NOT_LOAD_BEARING = 1
EXIT_UNMEASURED = 2
EXIT_TREE_UNSAFE = 3
EXIT_INTERRUPTED = 130

_SPEC_KEYS = frozenset({"file", "pytest", "pytest_args", "mutants"})
_MUTANT_KEYS = frozenset({"name", "file", "old", "new", "expected_red", "expected_message"})
_PYTEST_EXIT = {1: "有测试失败", 2: "被中断（多为收集期报错）", 3: "pytest 内部错误",
                4: "命令行用法错（路径 / 参数）", 5: "一条测试也没收集到"}
_TAGS = {"killed": "KILLED", "survived": "SURVIVED", "wrong_reason": "WRONG", "timeout": "TIMEOUT"}
_DEFERRED_SIGNALS = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)
# 红在这些异常上，多半是符号层断了（删了定义 / import），被测行为没跑到。只认 module 级缺属性：
# 普通 AttributeError 可能正是被测行为（变异让函数返回 None）。
_SYMBOL_LEVEL = re.compile(
    r"^(ImportError|ModuleNotFoundError|NameError|UnboundLocalError|SyntaxError|IndentationError)\b"
    r"|module '[^']+' has no attribute"
)
_REPORTER = "_mutation_check_reporter"
# 注入子进程的 pytest 插件：按 node id 记结局与崩溃行、收集期错误、被变异文件有没有被 import。
# 不解析终端输出——`FAILED x.py::t[a - b] - msg` 里参数化 id 本身就能带空格和 " - "。
_REPORTER_SOURCE = '''\
"""mutation_check 注入的 pytest 插件（临时文件，跑完即删）。"""
import json
import os
import sys

_collected = []
_tests = {}
_collect_errors = []


def _message(report):
    crash = getattr(report.longrepr, "reprcrash", None)
    text = getattr(crash, "message", None) or getattr(report, "longreprtext", "") or ""
    return str(text)[:2000]


def pytest_collection_finish(session):
    _collected.extend(item.nodeid for item in session.items)


def pytest_collectreport(report):
    if report.failed:
        _collect_errors.append({"nodeid": report.nodeid, "message": _message(report)})


def pytest_runtest_logreport(report):
    rec = _tests.setdefault(report.nodeid, {"outcome": "not_run", "message": ""})
    xfail = hasattr(report, "wasxfail")
    if report.when == "setup":
        if report.failed:
            rec.update(outcome="error", message="setup: " + _message(report))
        elif report.skipped:
            rec.update(outcome="xfailed" if xfail else "skipped", message=_message(report))
    elif report.when == "call":
        if report.failed:
            rec.update(outcome="failed", message=_message(report))
        elif report.skipped:
            rec.update(outcome="xfailed" if xfail else "skipped", message=_message(report))
        else:
            rec.update(outcome="xpassed" if xfail else "passed")
    elif report.failed and rec["outcome"] in ("not_run", "passed"):
        rec.update(outcome="error", message="teardown: " + _message(report))


def pytest_sessionfinish(session, exitstatus):
    watched = [p for p in os.environ.get("MUTATION_CHECK_WATCH", "").split(os.pathsep) if p]
    loaded = set()
    for module in list(sys.modules.values()):
        path = getattr(module, "__file__", None)
        if isinstance(path, str):
            loaded.add(os.path.realpath(path))
    payload = {
        "exitstatus": int(exitstatus),
        "collected": _collected,
        "tests": _tests,
        "collect_errors": _collect_errors,
        "imported": [p for p in watched if os.path.realpath(p) in loaded],
    }
    with open(os.environ["MUTATION_CHECK_REPORT"], "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)
'''


class SpecError(Exception):
    """spec 本身不合法；消息里一次列全所有问题。"""


class TreeUnsafe(Exception):
    """还原没做成，或被变异文件被别处改了：树可能不在原样。"""


class Mutant(NamedTuple):
    name: str
    file: str
    old: str
    new: str
    expected_red: list
    expected_message: Optional[str] = None


class PytestRun(NamedTuple):
    exit: Optional[int]
    timed_out: bool
    duration_s: float
    report: Optional[dict]
    log: str

    def tail(self, lines: int = 30) -> str:
        return "\n".join(self.log.rstrip().splitlines()[-lines:])


def load_spec(path: Path) -> tuple[object, str]:
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError as exc:
            raise SpecError("YAML spec 需要 PyYAML（venv 里有），或改用 JSON") from exc
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise SpecError(f"YAML 解析失败：{exc}") from exc
    else:
        try:
            data = json.loads(text)
        except ValueError as exc:
            raise SpecError(f"JSON 解析失败：{exc}") from exc
    return data, hashlib.sha256(raw).hexdigest()


def _is_text_list(value: object) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(v, str) and v for v in value)


def parse_spec(data: object) -> tuple[list[str], list[str], list[Mutant]]:
    """返回 (pytest 目标, 额外 pytest 参数, mutants)。不合法就把**全部**问题攒成一个 SpecError。"""
    if not isinstance(data, dict):
        raise SpecError("spec 顶层必须是对象")
    problems = []
    if set(data) - _SPEC_KEYS:
        problems.append(f"未知字段 {sorted(set(data) - _SPEC_KEYS)}（允许 {sorted(_SPEC_KEYS)}）")
    targets = data.get("pytest")
    targets = [targets] if isinstance(targets, str) else targets
    if not _is_text_list(targets):
        problems.append("pytest 必须是非空字符串或非空字符串列表")
    extra = data.get("pytest_args", [])
    if not (isinstance(extra, list) and all(isinstance(a, str) for a in extra)):
        problems.append("pytest_args 必须是字符串列表")
    raw_mutants = data.get("mutants")
    if not (isinstance(raw_mutants, list) and raw_mutants):
        problems.append("mutants 必须是非空列表")
        raw_mutants = []
    mutants, seen = [], set()
    for index, raw in enumerate(raw_mutants, 1):
        if not isinstance(raw, dict):
            problems.append(f"mutants[{index}] 必须是对象")
            continue
        label = f"mutants[{index}] {raw.get('name')!r}"
        mine = []
        if set(raw) - _MUTANT_KEYS:
            mine.append(f"未知字段 {sorted(set(raw) - _MUTANT_KEYS)}（允许 {sorted(_MUTANT_KEYS)}）")
        name, file = raw.get("name"), raw.get("file", data.get("file"))
        old, new, expected = raw.get("old"), raw.get("new"), raw.get("expected_red")
        message = raw.get("expected_message")
        if not (isinstance(name, str) and name.strip()):
            mine.append("name 必须是非空字符串")
        elif name in seen:
            mine.append("name 重复")
        seen.add(name)
        if not (isinstance(file, str) and file):
            mine.append("没有 file（顶层或 mutant 里给）")
        if not (isinstance(old, str) and old):
            mine.append("old 必须是非空字符串")
        if not isinstance(new, str):
            mine.append("new 必须是字符串（删除写空串）")
        elif old == new:
            mine.append("old 与 new 相同，不是变异")
        if not _is_text_list(expected):
            mine.append("expected_red 必须是非空的测试 id 列表——没有点名的测试，就没有「承重」可判")
        if message is not None:
            try:
                re.compile(message)
            except (TypeError, re.error) as exc:
                mine.append(f"expected_message 不是合法正则：{exc}")
        problems.extend(f"{label}: {p}" for p in mine)
        if not mine:
            mutants.append(Mutant(name, file, old, new, list(expected), message))
    if problems:
        raise SpecError("\n".join(problems))
    return list(targets), list(extra), mutants


def _git(root: Path, *args: str) -> tuple[int, str]:
    proc = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    return proc.returncode, proc.stdout


def file_problem(root: Path, rel: str) -> Optional[str]:
    """被变异文件必须有已提交的还原点、且此刻与它一致；返回问题描述，没问题返回 None。"""
    path = root / rel
    if path.is_symlink():
        return f"{rel}: 是符号链接——写入会穿透到链接目标，拒绝"
    if not path.is_file():
        return f"{rel}: 文件不存在"
    code, blob = _git(root, "rev-parse", "--verify", "--quiet", f"HEAD:{rel}")
    if code != 0:
        return f"{rel}: 不在 HEAD 里——没有已提交的还原点（先提交实现再拆门）"
    _, status = _git(root, "status", "--porcelain", "--untracked-files=no", "--", rel)
    if status.strip():
        return (f"{rel}: 与 HEAD 不一致（{status.strip()}）——先提交：在未提交的实现上拆门，"
                "读数测的是混合树，中途崩溃时实现也没有还原点")
    _, current = _git(root, "hash-object", "--", rel)
    if current.strip() != blob.strip():
        return f"{rel}: git status 显示干净，内容却与 HEAD 不同（assume-unchanged / skip-worktree？）"
    return None


def purge_bytecode(path: Path) -> list[Path]:
    """删被变异模块的全部字节码缓存：各解释器 tag、opt 级别，以及 PYTHONPYCACHEPREFIX 镜像处。"""
    if path.suffix != ".py":
        return []
    directories = [path.parent / "__pycache__"]
    prefix = os.environ.get("PYTHONPYCACHEPREFIX")
    if prefix:
        directories.append(Path(prefix) / str(path.parent.absolute()).lstrip(os.sep))
    removed = []
    for directory in directories:
        for pyc in directory.glob(f"{glob.escape(path.stem)}.*.pyc"):
            with contextlib.suppress(FileNotFoundError):
                pyc.unlink()
                removed.append(pyc)
    return removed


def child_env(base: dict, plugin_dir: Path, report: Path, watch: list, *, mutant: bool) -> dict:
    env = dict(base)
    env["PYTHONPATH"] = os.pathsep.join(p for p in (str(plugin_dir), base.get("PYTHONPATH", "")) if p)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["MUTATION_CHECK_REPORT"] = str(report)
    env["MUTATION_CHECK_WATCH"] = os.pathsep.join(str(p) for p in watch)
    if mutant:
        env["FWP_TEST_RECEIPT"] = "0"
    return env


def resolve_expected(expected: str, collected: list) -> list:
    return [nodeid for nodeid in collected if nodeid == expected or nodeid.endswith("::" + expected)]


@contextlib.contextmanager
def _signals_deferred():
    """写入 / 还原那几行不可被打断：期间到的信号先挂起，出块后再投递。"""
    previous = signal.pthread_sigmask(signal.SIG_BLOCK, _DEFERRED_SIGNALS)
    try:
        yield
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, previous)


@contextlib.contextmanager
def _signals_as_interrupts():
    """SIGTERM / SIGHUP 的默认动作直接结束进程、不走 finally；换成 KeyboardInterrupt，还原照常执行。"""
    def _interrupt(signum, _frame):
        raise KeyboardInterrupt(f"signal {signum}")

    previous = {sig: signal.signal(sig, _interrupt) for sig in (signal.SIGTERM, signal.SIGHUP)}
    try:
        yield
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def _kill_group(proc: subprocess.Popen) -> None:
    """收掉整个进程组：pytest 自己退出了，测试起的孙进程也可能还在。"""
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(proc.pid, signal.SIGKILL)
    with contextlib.suppress(subprocess.TimeoutExpired):
        proc.wait(timeout=10)


def _short(nodeid: str) -> str:
    return nodeid.split("::", 1)[-1]


class Checker:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.root = Path()
        self.targets, self.extra = [], []
        self.originals = {}
        self.resolved = {}
        self.workdir = Path()
        self.runs = 0
        self.summary = {
            "tool": "mutation_check", "spec": os.path.abspath(args.spec), "spec_sha256": None,
            "repo": None, "head": None, "tree_dirty": [], "python": args.python,
            "pytest": [], "pytest_args": [], "timeout_s": args.timeout, "dry_run": args.dry_run,
            "status": None, "exit_code": None, "problems": [], "baseline": None,
            "mutants": [], "counts": {},
        }

    def run(self) -> int:
        self.workdir = Path(tempfile.mkdtemp(prefix="mutation-check-"))
        try:
            with _signals_as_interrupts():
                return self._run()
        except KeyboardInterrupt:
            return self._finish("interrupted", EXIT_INTERRUPTED)
        except TreeUnsafe as exc:
            self.summary["problems"].append(str(exc))
            print(f"UNSAFE   {exc}", flush=True)
            return self._finish("tree_unsafe", EXIT_TREE_UNSAFE)
        finally:
            shutil.rmtree(self.workdir, ignore_errors=True)

    def _run(self) -> int:
        try:
            data, self.summary["spec_sha256"] = load_spec(self.args.spec)
            self.targets, self.extra, mutants = parse_spec(data)
        except (OSError, UnicodeDecodeError, SpecError) as exc:
            return self._unmeasured(str(exc).splitlines(), "INVALID")
        code, top = _git(self.args.repo, "rev-parse", "--show-toplevel")
        if code != 0:
            return self._unmeasured([f"{self.args.repo} 不在 git 仓库里"], "INVALID")
        self.root = Path(top.strip()).resolve()
        _, head = _git(self.root, "rev-parse", "--verify", "--quiet", "HEAD")
        _, dirty = _git(self.root, "status", "--porcelain", "--untracked-files=no")
        self.summary.update(repo=str(self.root), head=head.strip() or None, tree_dirty=dirty.splitlines(),
                            pytest=self.targets, pytest_args=self.extra)
        mutants, problems = self._preflight(mutants)
        if problems:
            return self._unmeasured(problems, "INVALID")

        (self.workdir / f"{_REPORTER}.py").write_text(_REPORTER_SOURCE, encoding="utf-8")
        for rel in self.originals:
            purge_bytecode(self.root / rel)
        baseline = self._pytest("baseline", mutant=False, collect_only=self.args.dry_run)
        problems = self._check_baseline(baseline, mutants)
        if problems:
            self.summary["baseline"]["output_tail"] = baseline.tail()
            return self._unmeasured(problems, "BASELINE", tail=baseline.tail(15))
        if self.args.dry_run:
            return self._finish("dry_run_ok", EXIT_OK)

        for mutant in mutants:
            self._run_mutant(mutant)
        bad = [m for m in self.summary["mutants"] if m["verdict"] != "killed"]
        return self._finish("not_load_bearing" if bad else "ok",
                            EXIT_NOT_LOAD_BEARING if bad else EXIT_OK)

    def _preflight(self, mutants: list) -> tuple[list, list]:
        """文件有还原点且干净、锚点恰好一处、变异后能编译——全部核完再说，一次报全。"""
        problems, checked = [], {}
        normalized = []
        for m in mutants:
            path = Path(os.path.normpath(self.root / m.file))  # 折叠 ..，免得 a/../../x 冒充仓内路径
            if not path.is_relative_to(self.root):
                problems.append(f"{m.name}: {m.file} 不在仓库 {self.root} 里")
                continue
            rel = path.relative_to(self.root).as_posix()
            if rel not in checked:
                checked[rel] = file_problem(self.root, rel)
                if checked[rel]:
                    problems.append(checked[rel])
            if checked[rel]:
                continue
            original = self.originals.setdefault(rel, path.read_bytes())
            try:
                source = original.decode("utf-8")
            except UnicodeDecodeError:
                problems.append(f"{m.name}: {rel} 不是 UTF-8 文本")
                continue
            count = source.count(m.old)
            if count != 1:
                why = ("没拆，跑出来测的是原代码，「没红」会被误读成测试不承重" if count == 0
                       else "不知道拆的是哪一处；把上下文带进 old 让它唯一")
                problems.append(f"{m.name}: old 在 {rel} 里出现 {count} 次（应恰好 1 次）——{why}")
                continue
            if rel.endswith(".py"):
                try:
                    compile(source.replace(m.old, m.new, 1), rel, "exec")
                except (SyntaxError, ValueError) as exc:
                    where = f"第 {exc.lineno} 行 " if getattr(exc, "lineno", None) else ""
                    problems.append(f"{m.name}: 变异后 {rel} 语法错（{where}{exc}）——"
                                    "测试会红在 import 上，不在被测行为上")
                    continue
            normalized.append(m._replace(file=rel))
        return normalized, problems

    def _pytest(self, label: str, *, mutant: bool, watch: tuple = (), collect_only: bool = False) -> PytestRun:
        self.runs += 1
        report_path = self.workdir / f"{self.runs:02d}.json"
        log_path = self.workdir / f"{self.runs:02d}.log"
        cmd = [self.args.python, "-m", "pytest", "-p", _REPORTER, "-p", "no:cacheprovider",
               "-q", "-rfE", "--tb=short", *(["--collect-only"] if collect_only else []),
               *self.extra, *self.targets]
        env = child_env(dict(os.environ), self.workdir, report_path, list(watch), mutant=mutant)
        started, timed_out, exit_code = time.monotonic(), False, None
        with log_path.open("wb") as log:
            try:
                proc = subprocess.Popen(cmd, cwd=self.root, env=env, stdin=subprocess.DEVNULL,
                                        stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            except OSError as exc:
                log.write(f"无法启动 pytest：{exc}\n".encode("utf-8"))
            else:
                try:
                    exit_code = proc.wait(timeout=self.args.timeout)
                except subprocess.TimeoutExpired:
                    timed_out = True
                finally:
                    _kill_group(proc)
        report = None
        if report_path.exists():
            with contextlib.suppress(ValueError):
                report = json.loads(report_path.read_text(encoding="utf-8"))
        if self.args.log_dir:
            self.args.log_dir.mkdir(parents=True, exist_ok=True)
            slug = re.sub(r"[^\w.-]+", "_", label)[:60]
            shutil.copyfile(log_path, self.args.log_dir / f"{self.runs:02d}-{slug}.log")
        return PytestRun(exit_code, timed_out, round(time.monotonic() - started, 2), report,
                         log_path.read_text(encoding="utf-8", errors="replace"))

    def _check_baseline(self, run: PytestRun, mutants: list) -> list:
        rep = run.report
        self.summary["baseline"] = {
            "exit": run.exit, "timed_out": run.timed_out, "duration_s": run.duration_s,
            "collected": len(rep["collected"]) if rep else None,
            "passed": sum(t["outcome"] == "passed" for t in rep["tests"].values()) if rep else None,
            "failed": sorted(n for n, t in rep["tests"].items() if t["outcome"] in ("failed", "error")) if rep else [],
        }
        if run.timed_out:
            return [f"基线超时（>{self.args.timeout}s）——调大 --timeout 或收窄 pytest 目标"]
        if rep is None:
            return [f"基线没产出报告（pytest exit {run.exit}）——多半是解释器、参数或路径不对"]
        if rep["collect_errors"]:
            return [f"基线收集期报错：{[e['nodeid'] for e in rep['collect_errors']]}"]
        if run.exit != 0:
            meaning = _PYTEST_EXIT.get(run.exit, "异常退出")
            return [f"基线不绿（pytest exit {run.exit}：{meaning}）{self.summary['baseline']['failed'][:10]}"
                    "——尺子本身是红的，先修好或收窄 pytest 目标"]
        passed = "" if self.args.dry_run else f"，passed {self.summary['baseline']['passed']}"
        print(f"BASELINE exit=0  收集 {len(rep['collected'])} 条{passed}  {run.duration_s}s", flush=True)
        problems = []
        for m in mutants:
            ids = []
            for expected in m.expected_red:
                hits = resolve_expected(expected, rep["collected"])
                if not hits:
                    near = [n for n in rep["collected"] if expected in n][:3]
                    hint = f"相近：{near}" if near else "检查 node id / pytest 目标 / -k"
                    problems.append(f"{m.name}: 点名测试 {expected!r} 没被收集到（{hint}）")
                elif len(hits) > 1:
                    problems.append(f"{m.name}: 点名测试 {expected!r} 对应多条 {hits[:5]}——写完整 node id")
                else:
                    outcome = "passed" if self.args.dry_run else rep["tests"].get(hits[0], {}).get("outcome")
                    if outcome != "passed":
                        problems.append(f"{m.name}: 点名测试 {hits[0]} 在基线里是 {outcome}——"
                                        "没变异时就不绿，变异后的红不归这个 mutant")
                    if hits[0] not in ids:
                        ids.append(hits[0])
            self.resolved[m.name] = ids
        return problems

    def _run_mutant(self, m: Mutant) -> None:
        path = self.root / m.file
        original = self.originals[m.file]
        mutated = original.decode("utf-8").replace(m.old, m.new, 1).encode("utf-8")
        written = False
        try:
            with _signals_deferred():
                if path.read_bytes() != original:
                    raise TreeUnsafe(f"{m.file}: 开跑后被别处改过（已不是开跑时读到的内容），不写入变异体；"
                                     f"现场：git -C {self.root} diff -- {m.file}")
                path.write_bytes(mutated)
                written = True
            purge_bytecode(path)
            run = self._pytest(m.name, mutant=True, watch=(path,))
            result = self._classify(m, run)
            self.summary["mutants"].append(result)
        finally:
            if written:
                self._restore(path, m.file, original, mutated)
        result["restored"] = True
        print(self._line(result), flush=True)

    def _restore(self, path: Path, rel: str, original: bytes, mutated: bytes) -> None:
        hint = f"现场：git -C {self.root} diff -- {rel}；确认后 git -C {self.root} checkout -- {rel}"
        with _signals_deferred():
            try:
                if path.read_bytes() != mutated:
                    raise TreeUnsafe(f"{rel}: 变异期间被别处改过（已不是本脚本写入的变异体），拒绝覆盖。{hint}")
                path.write_bytes(original)
            except OSError as exc:
                raise TreeUnsafe(f"{rel}: 还原写入失败（{exc}）。{hint}") from exc
            finally:
                purge_bytecode(path)
        problem = None if path.read_bytes() == original else "写回后字节与原文件不同"
        problem = problem or file_problem(self.root, rel)
        if problem:
            raise TreeUnsafe(f"{rel}: 还原后核验失败：{problem}。{hint}")

    def _classify(self, m: Mutant, run: PytestRun) -> dict:
        ids = self.resolved[m.name]
        out = {"name": m.name, "file": m.file, "verdict": None, "expected_red": ids, "red": [],
               "not_red": {}, "other_red": [], "pytest_exit": run.exit, "duration_s": run.duration_s,
               "messages": {}, "collect_errors": [], "imported": None, "warnings": [], "restored": False}
        rep = run.report
        if run.timed_out:
            out["verdict"] = "timeout"
            out["warnings"].append(f"超时（>{self.args.timeout}s）已杀进程组——挂住不等于钉住")
        elif rep is None:
            out["verdict"] = "wrong_reason"
            out["warnings"].append(f"pytest 没产出报告（exit {run.exit}）")
        else:
            tests = rep["tests"]
            outcomes = {nodeid: tests.get(nodeid, {}).get("outcome", "not_run") for nodeid in ids}
            out["red"] = [n for n, o in outcomes.items() if o == "failed"]
            out["not_red"] = {n: o for n, o in outcomes.items() if o != "failed"}
            out["other_red"] = sorted(n for n, t in tests.items()
                                      if t["outcome"] in ("failed", "error") and n not in outcomes)
            out["messages"] = {n: tests[n]["message"] for n in ids if tests.get(n, {}).get("message")}
            out["collect_errors"] = rep["collect_errors"]
            out["imported"] = bool(rep["imported"]) if m.file.endswith(".py") else None
            unmatched = [n for n in out["red"] if m.expected_message
                         and not re.search(m.expected_message, out["messages"].get(n, ""))]
            if any(o in ("passed", "xpassed") for o in outcomes.values()):
                out["verdict"] = "survived"
                if out["imported"] is False:
                    out["warnings"].append("被变异文件没被 pytest 进程 import 过：测试可能走子进程，"
                                           "或 import 的是另一份拷贝（别的树 / site-packages）")
            elif rep["collect_errors"]:
                out["verdict"] = "wrong_reason"
                out["warnings"].append("收集期报错：变异让 import 就失败了，被测行为没跑到")
            elif out["not_red"]:
                out["verdict"] = "wrong_reason"
                out["warnings"].append("点名测试没以断言失败的方式变红（error / skipped / 没跑）")
            elif unmatched:
                out["verdict"] = "wrong_reason"
                out["warnings"].append(f"红了，但崩溃行不匹配 expected_message：{[_short(n) for n in unmatched]}")
            else:
                out["verdict"] = "killed"
            if any(_SYMBOL_LEVEL.search(out["messages"].get(n, "")) for n in out["red"]):
                out["warnings"].append("⚠ 红在符号层（NameError / ImportError / module 缺属性）：是不是删了"
                                       "定义或 import？被测行为可能没跑到，可用 expected_message 钉原因")
        if out["verdict"] != "killed":
            out["output_tail"] = run.tail()
        return out

    def _line(self, result: dict) -> str:
        detail = f"红 {len(result['red'])}/{len(result['expected_red'])}"
        if result["other_red"]:
            detail += f"（另红 {len(result['other_red'])}）"
        if result["not_red"]:
            detail += "  没红：" + ", ".join(f"{_short(n)}={o}" for n, o in result["not_red"].items())
        detail += f"  exit={result['pytest_exit']}  {result['duration_s']}s"
        warnings = "  " + "；".join(result["warnings"]) if result["warnings"] else ""
        return f"{_TAGS[result['verdict']]:<9}{result['name']}  {detail}{warnings}"

    def _unmeasured(self, problems: list, tag: str, tail: str = "") -> int:
        self.summary["problems"].extend(problems)
        for problem in problems:
            print(f"{tag:<9}{problem}", flush=True)
        for line in tail.splitlines():
            print(f"    | {line}", flush=True)
        return self._finish("precondition_failed", EXIT_UNMEASURED)

    def _finish(self, status: str, code: int) -> int:
        summary = self.summary
        summary["status"], summary["exit_code"] = status, code
        counts = {}
        for m in summary["mutants"]:
            counts[m["verdict"]] = counts.get(m["verdict"], 0) + 1
        summary["counts"] = counts
        killed, total = counts.get("killed", 0), len(summary["mutants"])
        print({
            "ok": f"== 全部承重：{killed}/{total}",
            "not_load_bearing": f"== {total - killed}/{total} 条读数不承重或不可归因 {counts} → exit {code}",
            "dry_run_ok": "== dry-run：spec、锚点、还原点与点名收集都过了（没跑变异）",
            "precondition_failed": f"== 没测成：前置条件不满足 → exit {code}",
            "tree_unsafe": f"== 树可能不在原样，按上面的提示人工处理 → exit {code}",
            "interrupted": f"== 被中断：pytest 进程组已杀，树上没有留下变异体 → exit {code}",
        }[status], flush=True)
        if self.args.summary_json:
            self.args.summary_json.parent.mkdir(parents=True, exist_ok=True)
            self.args.summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
                                              encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False), flush=True)
        return code


def _parse_args(argv: Optional[list] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("spec", type=Path, help="变异 spec（.json / .yaml / .yml）")
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="仓库（默认当前目录所在仓）")
    parser.add_argument("--python", default=sys.executable, help="跑 pytest 的解释器（默认执行本脚本的这个）")
    parser.add_argument("--timeout", type=float, default=600.0, help="单轮 pytest 超时秒数（默认 600）")
    parser.add_argument("--dry-run", action="store_true", help="只验 spec、锚点、还原点与点名收集，不跑变异")
    parser.add_argument("--summary-json", type=Path, help="汇总 JSON 另存到这里")
    parser.add_argument("--log-dir", type=Path, help="每轮 pytest 的完整输出存到这个目录")
    args = parser.parse_args(argv)
    if os.sep in args.python and not os.path.isabs(args.python):
        # Popen 会相对子进程的 cwd（仓根）找相对路径的可执行文件，先按调用处的 cwd 定死
        args.python = os.path.abspath(args.python)
    return args


def main(argv: Optional[list] = None) -> int:
    return Checker(_parse_args(argv)).run()


if __name__ == "__main__":
    raise SystemExit(main())
