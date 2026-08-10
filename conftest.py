"""测试环境门禁：解释器不对就**在收集之前**失败，并说清该用哪个。

## 为什么必须在这一层

本仓有两个 python，依赖完全不同：

    宿主 /usr/bin/python3        无 fastapi / agents / duckdb / yaml …
    .venv-workbench/bin/python   全部具备（AGENTS.md 与 CLAUDE.md 都写了用它）

用错的后果不是"跑不了"，而是**跑出一个看起来合理的错读数**。2026-08-10 实测，
同一棵树同一时刻：

    宿主 python3        71 failed / 3819 passed
    .venv-workbench     14 failed / 3996 passed

差出来的 57 条全是环境噪声。而当时的结论是「71 条分布在 11 个文件、本轮只碰
1 个文件，所以非本轮引入」——推理过程没错，输入数字是错的，于是错读数还通过了
一次看似严谨的归属分析，差点被写进提交记录当证据。

这个洞此前**已经有**一道门禁在管（`scripts/check_agent_workspace_facts.py`，
挂在 pre-commit 上），它确实抓住了这次错误。但它只在 `git commit` 时才说话——
那时二十多次错误的 pytest 已经跑完，结论已经形成。**门禁的位置必须在错误
产生的那一刻，而不是错误被提交的那一刻。**

pytest 启动时读 rootdir 的 conftest.py，对**所有**调用方一律生效：
agent、人、CI、`python -m pytest`、IDE 里点运行。这是本仓唯一一个"任何人跑测试
都必然经过"的位置，所以检查放这里。

## 为什么按"能力"判而不是按"路径"判

判据是**依赖在不在**，不是 `sys.executable` 等不等于某个字面路径。原因：
worktree 里跑测试时用的是主树的 `.venv-workbench/bin/python`（AGENTS.md:67），
路径与所在树不同；将来若换 venv 名字，按路径判会误伤一个完好的环境。
按能力判则永远只在"真的跑不动"时才拦，且拦的理由就是失败的真实原因。

要绕过（例如故意在裸环境验证依赖缺失时的行为）：`FWP_ALLOW_ANY_PYTHON=1`。
绕过时仍然打印横幅，不会静默。
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent

# 主检出树的共享解释器。worktree 也用它（AGENTS.md:67），所以写绝对路径。
EXPECTED_PY = Path("/Users/a77/finance-workspace-private/.venv-workbench/bin/python")

# 被反复误报成「环境缺包」的依赖。清单来自真实误报，与
# check_agent_workspace_facts.py 的 WATCHED 同源——两处都改才算改完。
REQUIRED = ("fastapi", "agents", "yaml", "duckdb", "pytest")

_ESCAPE = "FWP_ALLOW_ANY_PYTHON"


def _missing() -> tuple[str, ...]:
    """当前解释器里装不上的必需依赖。"""

    return tuple(m for m in REQUIRED if importlib.util.find_spec(m) is None)


def _revision() -> str:
    """自述 revision——`14 failed` 单独看无法复核是对哪棵树哪个提交成立的。"""

    def _git(*args: str) -> str:
        try:
            out = subprocess.run(
                ["git", *args], cwd=REPO, capture_output=True, text=True, timeout=10
            )
        except (OSError, subprocess.SubprocessError):
            return ""
        return out.stdout.strip() if out.returncode == 0 else ""

    branch = _git("rev-parse", "--abbrev-ref", "HEAD") or "(unknown)"
    rev = _git("rev-parse", "--short", "HEAD") or "(unknown)"
    dirty = " +未提交改动" if _git("status", "--porcelain") else ""
    return f"{branch} @ {rev}{dirty}"


def pytest_configure(config: pytest.Config) -> None:
    """收集之前先判解释器。用 UsageError 而非 assert：前者输出干净且退出码明确。"""

    missing = _missing()
    if not missing:
        return

    hint = (
        f"改用  {EXPECTED_PY} -m pytest ..."
        if EXPECTED_PY.exists()
        else f"⚠ 预期解释器不存在：{EXPECTED_PY}（环境本身需要修）"
    )
    detail = (
        f"\n解释器缺少必需依赖：{', '.join(missing)}"
        f"\n  当前解释器 : {sys.executable}"
        f"\n  应当使用   : {EXPECTED_PY}"
        f"\n"
        f"\n这不是「环境缺包」，是**解释器用错了**——这些包在 .venv-workbench 里都有。"
        f"\n继续跑下去不会得到空结果，而会得到一个偏高的失败数（实测 71 vs 14），"
        f"\n那个数字看起来完全合理，足以支撑一次错误的归属分析。"
        f"\n"
        f"\n{hint}"
        f"\n确实要在当前解释器上跑（例如故意验证缺依赖时的行为）：{_ESCAPE}=1"
    )
    if os.environ.get(_ESCAPE) == "1":
        print(f"\n⚠ {_ESCAPE}=1 已放行，但读数不可与正常环境比较：{detail}\n")
        return
    raise pytest.UsageError(detail)


def pytest_report_header() -> list[str]:
    """让每一次读数自带出处。

    「凡引用测试计数当证据，必须同时写明解释器路径」——把它做成自动输出，
    而不是指望调用方记得写。注意 `--no-header` 会压掉本行，引用计数时别加它。
    """

    lines = [f"解释器: {sys.executable}", f"树: {REPO}  {_revision()}"]
    if os.environ.get(_ESCAPE) == "1":
        lines.append(f"⚠ {_ESCAPE}=1 —— 依赖门禁已被绕过，读数不可跨环境比较")
    return lines
