"""收集面的门禁。

`pytest.ini` 的 `norecursedirs` 是唯一拦住「历史工作 clone 参与收集」的东西。
它失效的表现不是某条测试变红，而是**一条测试都跑不了**：

    !!! Interrupted: 1031 errors during collection !!!

这种失败很容易被读成「环境坏了」而不是「配置回退了」，所以值得钉住。

**断言的是生效结果，不是配置值。** 直接读 `pytest.ini` 或 `pytestconfig.getini(
"norecursedirs")` 都只能证明「配置里写了 tmp」，证明不了「收集真的干净」——
命令行 `-o`、`--rootdir` 指错、上游新增另一处同名包，任何一条都能让配置正确而结果
错误。所以这里 fork 一个真的 `--collect-only` 出去，看它的退出码和产出。

两条用例是一对，缺第二条第一条会假绿：`tmp/` 空的机器上第一条无条件通过，
而它通过的原因是「没有冲突源」而不是「门禁挡住了冲突源」。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]

# pytest 默认值去掉 tmp。这是 pytest.ini 里那行的「变异体」——把唯一的改动撤销，
# 用来证明绿灯确实由那一项贡献。
_MUTATED_NORECURSEDIRS = "*.egg .* _darcs build CVS dist node_modules venv {arch}"


def _collect(*extra_args: str) -> subprocess.CompletedProcess[str]:
    """在仓库根跑一次 --collect-only。

    `-p no:cacheprovider`：不写 .pytest_cache，避免污染宿主的缓存目录。
    不会递归：--collect-only 只收集不执行，收到本文件也不会再 fork。
    """
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "--no-header",
            "-p",
            "no:cacheprovider",
            *extra_args,
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )


def _colliding_clones() -> list[Path]:
    """`tmp/` 下与主树 `tests/` 同包名的历史工作 clone。

    判据是 `tmp/*/tests/__init__.py` 存在——有 __init__.py 才会被解析成包
    `tests.<模块名>`，与主树的 `tests/` 撞名。没有 __init__.py 的目录走
    rootdir-relative 路径导入，不构成冲突。
    """
    return sorted((_REPO_ROOT / "tmp").glob("*/tests/__init__.py"))


def test_repo_root_collection_has_no_errors() -> None:
    """在主树跑全量收集必须零 error —— 路线图那条验收命令的前提。"""
    result = _collect()

    assert result.returncode == 0, (
        "主树 --collect-only 非零退出，说明收集面又漏进了不该收的树。\n"
        f"stdout 末尾:\n{result.stdout[-2000:]}"
    )
    assert "errors during collection" not in result.stdout, (
        f"收集期报错:\n{result.stdout[-2000:]}"
    )


def test_the_gate_is_what_keeps_collection_clean() -> None:
    """变异测试：撤掉 tmp 这一项，收集必须转红。

    没有这条，上一条在 `tmp/` 为空的机器上会因为「没有冲突源」而通过，
    读起来却像「门禁有效」。
    """
    clones = _colliding_clones()
    if not clones:
        pytest.skip(
            "本机 tmp/ 下没有带 tests/__init__.py 的历史工作 clone，"
            "无冲突源可供变异——上一条用例此时证明的是「本机干净」，"
            "不是「门禁有效」。"
        )

    result = _collect("-o", f"norecursedirs={_MUTATED_NORECURSEDIRS}")

    assert result.returncode != 0, (
        f"撤掉 norecursedirs 里的 tmp 后收集仍然干净，"
        f"但本机存在 {len(clones)} 个同包名 clone："
        f"{[str(p.relative_to(_REPO_ROOT)) for p in clones]}。\n"
        "要么冲突判据（tests/__init__.py）已经不成立，要么绿灯另有来源——"
        "无论哪种，上一条用例都不再由这条配置保护。"
    )
    assert "errors during collection" in result.stdout, (
        f"变异后非零退出，但不是收集期错误，可能是别的原因导致的红：\n"
        f"{result.stdout[-2000:]}"
    )
