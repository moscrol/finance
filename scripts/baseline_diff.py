#!/usr/bin/env python3
"""基线对照：把「这些失败是我引入的吗」「行为到底变没变」从推断变成实验。

## 为什么需要它

2026-08-10 一次审查里，一个提交自述「零行为变更 —— 3943 passed 佐证」。
两句都不成立，且错法不同：

- **计数证明不了行为不变。** 测试全绿只说明「没有测试钉住修复前的语义」，
  不说明语义没变。该提交实际放宽了一处拒收条件（required output 带 gap
  且有证据哈希 → 不再抛错），而全量测试照旧全绿，因为修复前的语义
  从来没有被任何测试钉住过。
- **计数本身还可能是错解释器的产物。** 宿主 python3 缺依赖，同一棵树
  用它跑得 71 failed，用 .venv-workbench 跑得 14 failed。拿前者当证据，
  会把 57 条环境噪声写进提交记录。

于是需要两个动作，本脚本各给一条命令：

    --mode diff    失败集合按**名字**与基线对照，回答「是不是我引入的」
    --mode probe   把 HEAD 改动的测试文件搬到基线上跑，回答「行为变没变」

## probe 模式为什么有效

若一个提交真是零行为变更，它的新测试搬到**未改动的基线**上应当同样通过。
若在基线上变红，且红在**断言**而不是 ImportError，就证明同一份输入在两棵树上
行为不同——「零行为变更」当场被证伪，不靠读 diff 猜。

这比人眼读 diff 可靠：diff 要靠人判断某个条件分支的语义变化，probe 让运行时说话。
（ImportError 会被单列为 `新符号` —— 那只说明测试引用了基线没有的名字，不是证据。）

## 只比名字，不比计数

计数相等不代表同一批失败：修好 3 条、引入 3 条，总数不变。本脚本比较测试 ID 集合，
输出 新增（回归）/ 消失（修好或删掉）/ 共有（既有失败），只有「新增」是本轮责任。

## 解释器由脚本自己定，不听调用方的

被审的正是「agent 用错解释器」这类错误，所以不继承 sys.executable——
那会复现同一个错误并把结论坐实。统一用 .venv-workbench，且在输出里写明路径。

退出码：
  0  无新增失败（diff）；探针已如实报告（probe）
  1  有新增失败 —— 本轮引入了回归
  2  用不了：不是 git 仓库 / 基线 ref 解析不了 / 解释器缺失
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# 与 check_agent_workspace_facts.py 同一个事实：全仓共享的唯一解释器。
VENV_PY = REPO / ".venv-workbench" / "bin" / "python"

# pytest 摘要行：`FAILED path::Class::test_name - AssertionError: ...`
_FAILED_RE = re.compile(r"^(?:FAILED|ERROR)\s+(\S+)")

DEFAULT_TARGET = "intelligence/tests"


@dataclass(frozen=True)
class RunResult:
    """一次 pytest 运行的结果。

    ``ids`` 只装测试 ID；**失败原因不在这里取**。

    实测（pytest 8.3.5）：``short test summary`` 的 FAILED 行只有测试 ID，
    没有 ``- 原因`` 后缀——那个后缀是别的版本/插件才有的。初版假设它存在，
    于是 ``reasons`` 全为空串，导致 ImportError 一条都识别不出来，
    把「新增符号」误报成「行为确有变更」。而分清这两者正是本脚本的唯一价值，
    所以这个默认值方向是错的：宁可报不出，不可报反。
    原因改由 ``_reason_for()`` 逐条取（见那里的注释）。
    """

    ids: frozenset[str]
    summary: str
    tree: str


def _git(*args: str, cwd: Path = REPO) -> str:
    try:
        out = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=30
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def _die(msg: str) -> None:
    print(f"用不了：{msg}", file=sys.stderr)
    raise SystemExit(2)


def _run_pytest(tree: Path, target: str, timeout: int) -> RunResult:
    """在 ``tree`` 里跑 pytest，抽出失败 ID 集合。

    ``-p no:cacheprovider`` 是必须的：否则 pytest 会往被审的树里写 .pytest_cache，
    让「基线树保持干净」这个前提失效，后续 git status 出现噪声。
    """

    # --tb=no：只要失败**名单**，不要 traceback。原因另外逐条取，见 _reason_for()。
    cmd = [
        str(VENV_PY), "-m", "pytest", *target.split(),
        "-q", "-rf", "-p", "no:cacheprovider", "--no-header", "--tb=no",
    ]
    try:
        out = subprocess.run(
            cmd, cwd=tree, capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        _die(f"pytest 在 {tree} 超时（{timeout}s）——加大 --timeout 或缩小 --target")
    text = (out.stdout or "") + (out.stderr or "")
    ids = frozenset(
        m.group(1)
        for line in text.splitlines()
        if (m := _FAILED_RE.match(line.strip()))
    )
    summary = next(
        (
            ln.strip()
            for ln in reversed(text.splitlines())
            if ("passed" in ln or "failed" in ln or "error" in ln)
            and ("=" in ln or " in " in ln)
        ),
        "(读不到 pytest 摘要行)",
    )
    return RunResult(ids=ids, summary=summary, tree=str(tree))


def _reason_for(tree: Path, test_id: str, timeout: int) -> str:
    """单跑一条测试，用 ``--tb=line`` 取它的失败原因首行。

    为什么单跑而不是批量解析：``--tb=line`` 批量输出里，每行是
    ``<文件>:<行号>: <异常>``，**不含测试名**。多条失败混在一起时，
    把某一行归给哪条测试只能靠顺序猜——顺序又不保证与 summary 一致。
    单跑一条，输出里的那一行必然属于它，配对无歧义。

    代价是每条失败多跑一次 pytest。探针模式下失败通常只有个位数，
    换来的是「新符号 vs 行为变更」判得准——这个判断错了整个脚本就没用了。
    """

    try:
        out = subprocess.run(
            [
                str(VENV_PY), "-m", "pytest", test_id,
                "-q", "--tb=line", "--no-header", "-p", "no:cacheprovider",
            ],
            cwd=tree, capture_output=True, text=True, timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    text = (out.stdout or "") + (out.stderr or "")
    # 取 FAILURES 段里带 `: ` 的那一行；collection 阶段的 ImportError 走 ERRORS 段，
    # 形态是 `E   ImportError: ...`，两种都收。
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("E   ") and ":" in stripped:
            return stripped[4:].strip()
        if re.match(r"^/.+:\d+: \w*(Error|Exception|Failed)", stripped):
            return stripped.split(": ", 1)[1] if ": " in stripped else stripped
    return ""


class _Baseline:
    """把基线 ref 检出成一棵**独立的临时 worktree**。

    为什么必须独立成树，而不是在当前树上 stash / checkout：本仓主检出树上另有
    4 个附属 worktree，且用户常有未提交改动。在主树上切分支去取基线，等于拿
    别人正在进行的工作做实验。临时 worktree 用完即拆，主树全程不动一根手指。

    独立性有一条必须验的前提：基线树里 `import intelligence` 得解析到**它自己**，
    而不是主树。否则跑的是主树代码，对照完全无效——所以 __enter__ 里实测一次。
    """

    def __init__(self, ref: str) -> None:
        self.ref = ref
        self.path: Path | None = None

    def __enter__(self) -> Path:
        if not _git("rev-parse", "--verify", f"{self.ref}^{{commit}}"):
            _die(f"基线 ref 解析不了：{self.ref}")
        self.path = Path(tempfile.mkdtemp(prefix="baseline-diff-"))
        # mkdtemp 已建目录，而 git worktree add 要求路径不存在。
        shutil.rmtree(self.path)
        if not _git("worktree", "add", "--detach", str(self.path), self.ref):
            _die(f"建不出基线 worktree（ref={self.ref}）")
        probe = subprocess.run(
            [str(VENV_PY), "-c", "import intelligence;print(intelligence.__file__)"],
            cwd=self.path, capture_output=True, text=True, timeout=60,
        )
        origin = (probe.stdout or "").strip()
        if str(self.path) not in origin:
            _die(
                "基线树串用了别处的代码，对照无效。\n"
                f"  期望前缀 {self.path}\n  实际 import 自 {origin or '(读不到)'}"
            )
        return self.path

    def __exit__(self, *exc: object) -> None:
        if self.path is None:
            return
        # --force：树里可能留下 probe 模式拷进去的测试文件。基线树是本脚本
        # 自己建的一次性产物，强制拆除不会碰用户的任何东西。
        _git("worktree", "remove", "--force", str(self.path))


def _mode_diff(baseline: str, target: str, timeout: int) -> int:
    """失败集合按名字对照，回答「这些失败是不是我引入的」。"""

    head_branch = _git("rev-parse", "--abbrev-ref", "HEAD") or "(unknown)"
    head_rev = _git("rev-parse", "--short", "HEAD") or "(unknown)"
    print("=" * 72)
    print("基线对照 — 失败集合按名字 diff（计数相等不代表同一批失败）")
    print("=" * 72)
    print(f"  当前     {head_branch} @ {head_rev}   树 {REPO}")
    print(f"  基线     {baseline} @ {_git('rev-parse', '--short', baseline) or '?'}")
    print(f"  解释器   {VENV_PY}")
    print(f"  目标     {target}\n")

    cur = _run_pytest(REPO, target, timeout)
    print(f"  当前 : {cur.summary}")
    with _Baseline(baseline) as base_tree:
        base = _run_pytest(base_tree, target, timeout)
    print(f"  基线 : {base.summary}\n")

    added = sorted(cur.ids - base.ids)
    gone = sorted(base.ids - cur.ids)
    shared = cur.ids & base.ids

    print(f"  共有失败 {len(shared)} 条 —— 基线上就红，非本轮引入")
    if gone:
        print(f"  消失   {len(gone)} 条 —— 本轮修好或删掉：")
        for t in gone:
            print(f"      - {t}")
    if not added:
        print("\n✅ 新增失败 0 条 —— 本轮没有引入回归")
        print(f"\n结论：通过（对 {head_branch}@{head_rev} vs {baseline}，解释器 {VENV_PY.name}）")
        return 0
    print(f"\n❌ 新增失败 {len(added)} 条 —— 这些是本轮的责任：")
    for t in added:
        print(f"      + {t}")
    print(f"\n结论：不通过（对 {head_branch}@{head_rev} vs {baseline}）")
    return 1


def _mode_probe(baseline: str, timeout: int) -> int:
    """把 HEAD 改动过的测试文件搬到基线上跑，回答「行为变没变」。

    在基线上**因断言而红** = 同一份输入两棵树行为不同 = 行为确有变更。
    ImportError 单列：那只说明测试引用了基线不存在的符号，不构成行为证���。
    """

    head_rev = _git("rev-parse", "--short", "HEAD") or "(unknown)"
    changed = [
        ln for ln in _git("diff", "--name-only", f"{baseline}...HEAD").splitlines()
        if "test" in ln and ln.endswith(".py")
    ]
    print("=" * 72)
    print("行为变更探针 — 新测试搬到基线上跑（零行为变更 ⇒ 应当同样通过）")
    print("=" * 72)
    print(f"  当前 @ {head_rev}   基线 {baseline}   解释器 {VENV_PY}")
    if not changed:
        print(f"\n  HEAD 相对 {baseline} 没有改动任何测试文件——无可探测。")
        print("  注意：这本身是个信号。改了行为却没动测试，说明没有测试钉住它。")
        return 0
    print(f"  被改动的测试文件 {len(changed)} 个：")
    for f in changed:
        print(f"      {f}")

    with _Baseline(baseline) as base_tree:
        for rel in changed:
            src = REPO / rel
            if not src.exists():
                continue
            dst = base_tree / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
        res = _run_pytest(base_tree, " ".join(changed), timeout)

        print(f"\n  基线上的结果 : {res.summary}")
        # 逐条取原因（必须在 with 块内——出块基线树就拆了）。
        reasons = {t: _reason_for(base_tree, t, timeout) for t in sorted(res.ids)}

    new_symbol = sorted(t for t in res.ids if _is_new_symbol(reasons.get(t, "")))
    behaviour = sorted(t for t in res.ids if t not in set(new_symbol))
    if new_symbol:
        print(f"\n  ⚠ {len(new_symbol)} 条因「基线没有这个符号」变红——只说明本轮新增了 API，")
        print("    不构成行为变更证据：")
        for t in new_symbol:
            print(f"      ? {t.rsplit('::', 1)[-1]}")
            print(f"        {reasons.get(t, '')[:100]}")
    if behaviour:
        print(f"\n🔬 {len(behaviour)} 条在基线上因**断言/异常**变红 —— 行为确有变更：")
        for t in behaviour:
            print(f"      ! {t.rsplit('::', 1)[-1]}")
            print(f"        基线上的表现: {reasons.get(t) or '(读不到原因)'}"[:160])
        print("\n结论：本轮**不是**零行为变更。提交自述若声称零变更，与本探针矛盾。")
    else:
        print("\n✅ 无断言级差异 —— 与「零行为变更」一致（限于被改动的测试所覆盖的范围）。")
    return 0


# 「基线上没有这个名字」类错误：只说明本轮新增了 API，不构成行为变更证据。
# 初版漏了这一层判别，把 2 条 ImportError 报成「行为确有变更」——而分清
# 「新符号」与「同一输入行为不同」正是本脚本存在的唯一理由，报错方向反而更糟。
_NEW_SYMBOL_MARKERS = (
    "ImportError",
    "AttributeError",
    "ModuleNotFoundError",
    "cannot import name",
    "has no attribute",
)


def _is_new_symbol(reason: str) -> bool:
    """失败原因是否属于「基线没有这个符号」，而非行为差异。"""

    return any(marker in reason for marker in _NEW_SYMBOL_MARKERS)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="基线对照：失败归属 diff + 行为变更探针",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "例：\n"
            "  scripts/baseline_diff.py --mode diff   --baseline main\n"
            "  scripts/baseline_diff.py --mode probe  --baseline main\n"
        ),
    )
    ap.add_argument("--mode", choices=("diff", "probe"), default="diff")
    ap.add_argument("--baseline", default="main", help="对照 ref，默认 main")
    ap.add_argument("--target", default=DEFAULT_TARGET, help=f"pytest 目标，默认 {DEFAULT_TARGET}")
    ap.add_argument("--timeout", type=int, default=600, help="单次 pytest 上限秒数")
    args = ap.parse_args()

    if not (REPO / ".git").exists():
        _die(f"{REPO} 不是 git 仓库")
    if not VENV_PY.exists():
        _die(f"解释器缺失：{VENV_PY}（别退回宿主 python3——那正是本脚本要防的错）")

    if args.mode == "diff":
        return _mode_diff(args.baseline, args.target, args.timeout)
    return _mode_probe(args.baseline, args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
