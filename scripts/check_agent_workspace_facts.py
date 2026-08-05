#!/usr/bin/env python3
"""提交时把「你在哪棵树、用哪个解释器」摆到 agent 眼前。

不是风格检查，是**事实投递**。本仓有 7 个 worktree 各在不同分支、3 处代码位置
（工作树 / .finance-runtime 快照 / finance-workspace-runtime 软链），
以及一个和宿主 python3 完全不同的 .venv-workbench。

2026-08-05 一晚上，两个 agent 在这两件事上合计出错 7 次：

- 用宿主 `python3`（3.14，无依赖）跑 pytest，得到 ModuleNotFoundError，
  报告成「预存环境问题，与本次改动无关」——而那些包在 .venv-workbench 里全都有；
- 在主检出树上 grep 不到某符号，断言「该符号不存在」——它在另一棵 worktree 上；
- 在主检出树上新建分支并 stash 掉用户未提交的工作。

这些没有一次被文档拦住（AGENTS.md / CLAUDE.md 都写了正确解释器）。提醒的到达率不可靠，
门禁是 100%。本脚本不试图阻止上述操作——提交时它们已经发生了——而是在
**唯一保证会被看到的时刻**，把与错误信念直接矛盾的事实打出来。

退出码：
  0  正常（含仅打印事实）
  1  环境本身坏了：.venv-workbench 缺失或关键依赖真的不在
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# .venv-workbench 是全仓共享的唯一解释器，用绝对路径。
VENV_PY = Path("/Users/a77/finance-workspace-private/.venv-workbench/bin/python")
# 主检出树（各 worktree 的 .git 都指向它）；用于区分「主树 vs 附属 worktree」。
MAIN_CHECKOUT = "/Users/a77/finance-workspace-private"

# 被反复误报为「缺失」的包。清单来自真实误报，不是凭空列的。
WATCHED = ("fastapi", "agents", "yaml", "uvicorn", "duckdb", "pytest", "ruff")


def _git(*args: str) -> str:
    """在**调用方所在的树**里执行，不是脚本所在的树。

    初版用了 `cwd=<脚本目录>`，于是从附属 worktree 里跑却报告主树的分支——
    一个专门用来防「在错误的树上工作」的检查，自己认错了树。
    pre-commit 以被提交仓库的根为 cwd，继承它才是对的。
    """

    try:
        return subprocess.run(
            ["git", *args], capture_output=True, text=True, timeout=10
        ).stdout.strip()
    except Exception:
        return ""


def _modules_in_venv() -> dict[str, bool] | None:
    """在 .venv-workbench 里查包，而不是在当前解释器里查。

    当前解释器可能就是那个出错的宿主 python3——用它查等于复现同一个错误，
    得到的「缺失」清单会和 agent 的误报一模一样，从而确认而非纠正错误信念。
    """

    if not VENV_PY.exists():
        return None
    code = (
        "import importlib.util,json,sys;"
        f"print(json.dumps({{m: importlib.util.find_spec(m) is not None for m in {WATCHED!r}}}))"
    )
    try:
        out = subprocess.run(
            [str(VENV_PY), "-c", code], capture_output=True, text=True, timeout=30
        )
        if out.returncode != 0:
            return None
        import json

        return json.loads(out.stdout)
    except Exception:
        return None


def main() -> int:
    worktree = _git("rev-parse", "--show-toplevel")
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    head = _git("rev-parse", "--short", "HEAD")

    lines = ["", "── 工作区事实（提交时自述，非风格检查）──"]
    lines.append(f"  worktree : {worktree or '未知'}")
    lines.append(f"  分支     : {branch or '未知'} @ {head or '?'}")

    # 主检出树 vs 附属 worktree：今晚的误操作（切分支 + stash 用户改动）就发生在主树上
    is_main_checkout = worktree == MAIN_CHECKOUT
    others = [
        ln.split()[0]
        for ln in _git("worktree", "list").splitlines()
        if ln and not ln.startswith(MAIN_CHECKOUT + " ")
    ]
    if is_main_checkout and others:
        lines.append(
            f"  ⚠ 这是**主检出树**，另有 {len(others)} 个 worktree 各在不同分支。"
        )
        lines.append(
            "    在这里切分支/stash 会影响其他人正在进行的工作——先确认这是你该待的树。"
        )

    mods = _modules_in_venv()
    if mods is None:
        print("\n".join(lines))
        print(f"  ✗ 找不到或无法运行 {VENV_PY}")
        print("    这是本仓唯一的 Python 入口（pytest / ruff / uvicorn 一律如此）。")
        return 1

    missing = sorted(m for m, ok in mods.items() if not ok)
    lines.append(f"  解释器   : {VENV_PY}")
    if missing:
        lines.append(f"  ✗ .venv-workbench 里确实缺: {', '.join(missing)}")
        print("\n".join(lines))
        return 1

    lines.append(
        f"  依赖     : {', '.join(sorted(mods))} —— 全部可用（宿主 python3 没有，别用它）"
    )
    lines.append(
        "  若刚才某次 pytest 报 ModuleNotFoundError，那是解释器用错了，不是环境缺包。"
    )
    lines.append("")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
