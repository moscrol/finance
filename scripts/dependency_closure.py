#!/usr/bin/env python3
"""从指定入口出发，用 AST 算出真实的第三方依赖闭环。

## 为什么不用 `pip freeze`

`pip freeze` 导出的是「这个 venv 里装了什么」，不是「这个入口用得到什么」。本仓
venv 里 68 个包同时供 ingest 侧（CDP 抓取、飞书写回、复盘同步）与消费侧使用，
而消费侧 agent 只是**读**这些数据。整体冻结会把一堆用不到的抓取库锁进消费侧的
运行环境，容器白胖一圈，且掩盖了「哪些依赖真的构成 agent 的运行面」这个事实。

## 为什么不用 pipreqs 之类的现成工具

它们普遍只扫模块顶层 import。本仓恰好有反例：`market_financials.py:175` 的
``import akshare as ak`` 藏在函数体里（懒加载，取不到就 fallback）。顶层扫描会
漏掉它，于是锁文件少一个包，而问题要等到**运行时**某条 fallback 路径被触发才
暴露——那是最难归因的一类缺失。所以这里遍历整棵 AST，函数体内的 import 一样算，
并单独标记出来（懒加载往往意味着"可选依赖"，值得人工确认该不该进锁）。

## 判据

- **仓内模块**（``intelligence.*`` 等）→ 解析成文件，递归进去
- **stdlib** → 用 ``sys.stdlib_module_names`` 判，不进锁
- **其余** → 第三方，映射到已安装发行版并取当前版本
- 发行版的**传递依赖**用 ``importlib.metadata.requires()`` 递归展开，
  带 ``extra ==`` 标记的可选依赖默认不展开（否则 fastapi 会拖进整个 standard 组）

## 输出

三段：直接第三方（含证据行号与是否懒加载）、传递依赖、以及可直接写入锁文件的
``name==version`` 清单。

退出码：
  0  算完
  2  用不了：入口文件不存在 / 不在仓内
"""

from __future__ import annotations

import argparse
import ast
import importlib.metadata as md
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

def _local_roots() -> frozenset[str]:
    """仓内顶层包/模块，**从文件系统推导**，不手写。

    初版把它硬编码成 ``{"intelligence", "market_feature_store", "scripts", "tests"}``，
    漏了 ``evolution/``。后果是双重的：它被误判成第三方（映射不到发行版，报成
    「未安装」），同时**没有被递归进去**——于是 ``evolution/`` 内部的第三方 import
    全部缺失在闭环里。锁文件会因此少包，而缺失只在运行时某条路径被触发��暴露。

    这正是本轮反复在修的同一个形状：手写清单会与事实分叉，且分叉时工具照旧
    「成功」输出。判据换成"目录里有没有 ``__init__.py``、根下有没有这个 .py"，
    新增顶层包自动纳入，没人需要记得登记。
    """

    roots: set[str] = set()
    for child in REPO.iterdir():
        if child.name.startswith((".", "_")):
            continue
        if child.is_dir() and (child / "__init__.py").is_file():
            roots.add(child.name)
        elif child.is_dir() and child.name in {"scripts"}:
            # scripts/ 不是包（无 __init__.py），但 `import scripts.x` 在测试里出现过。
            roots.add(child.name)
        elif child.suffix == ".py":
            roots.add(child.stem)
    return frozenset(roots)


LOCAL_ROOTS = _local_roots()

_REQ_NAME = re.compile(r"^\s*([A-Za-z0-9._-]+)")


@dataclass
class Hit:
    """一个第三方 import 的证据。"""

    module: str
    where: str
    lineno: int
    lazy: bool

    def render(self) -> str:
        tag = "  [懒加载]" if self.lazy else ""
        return f"{self.module:<22} {self.where}:{self.lineno}{tag}"


@dataclass
class Closure:
    third_party: dict[str, Hit] = field(default_factory=dict)
    visited: set[Path] = field(default_factory=set)
    unresolved: set[str] = field(default_factory=set)


def _module_to_path(module: str) -> Path | None:
    """把点分模块名解析成仓内文件。包则取 ``__init__.py``。"""

    rel = Path(*module.split("."))
    for candidate in (REPO / rel.with_suffix(".py"), REPO / rel / "__init__.py"):
        if candidate.is_file():
            return candidate
    return None


def _lazy_ranges(tree: ast.Module) -> list[tuple[int, int]]:
    """所有函数体的行区间——落在里面的 import 就是懒加载。"""

    spans: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            spans.append((node.lineno, node.end_lineno or node.lineno))
    return spans


def _walk(path: Path, closure: Closure) -> None:
    """递归遍历一个文��的 import 图。"""

    if path in closure.visited:
        return
    closure.visited.add(path)
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return

    spans = _lazy_ranges(tree)
    # 当前文件所属包，供相对 import（`from . import x`）解析。
    pkg = ".".join(path.relative_to(REPO).with_suffix("").parts)
    if path.name == "__init__.py":
        pkg = ".".join(pkg.split(".")[:-1])
    else:
        pkg = ".".join(pkg.split(".")[:-1])

    for node in ast.walk(tree):
        targets: list[str] = []
        # ``from pkg import (a, b)`` 里的 a/b 可能是**子模块**也可能只是类名/函数名。
        # 拿不准就都试一次，解析成文件的才递归，解析不到的静默跳过——不能计入
        # ``unresolved``（那会把每个被 import 的类名都报成"找不到模块"）。
        maybe_modules: list[str] = []
        if isinstance(node, ast.Import):
            targets = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                # 相对 import：按 level 回退包层级。
                parts = pkg.split(".") if pkg else []
                base = parts[: len(parts) - (node.level - 1)] if node.level > 1 else parts
                targets = [".".join([*base, node.module]) if node.module else ".".join(base)]
            elif node.module:
                targets = [node.module]
            # 初版只走 ``node.module``，于是
            # ``from intelligence.services import (answer_model, market_financials, ...)``
            # 只访问到 ``intelligence/services/__init__.py``，四个子模块一个没进。
            # 闭环因此漏掉整片子树（含 market_financials 里的 akshare 懒加载），
            # 锁文件少包，而缺失只在运行时那条 fallback 被触发才暴露。
            if targets and targets[0].split(".")[0] in LOCAL_ROOTS:
                maybe_modules = [f"{targets[0]}.{alias.name}" for alias in node.names]
        else:
            continue

        for candidate in maybe_modules:
            child = _module_to_path(candidate)
            if child is not None:
                _walk(child, closure)

        lazy = any(lo <= node.lineno <= hi for lo, hi in spans)
        for target in targets:
            root = target.split(".")[0]
            if root in LOCAL_ROOTS:
                child = _module_to_path(target)
                if child is not None:
                    _walk(child, closure)
                else:
                    closure.unresolved.add(target)
                continue
            if root in sys.stdlib_module_names or root in {"__future__"}:
                continue
            # 同名只留第一处证据；非懒加载优先（更能说明它是硬依赖）。
            prior = closure.third_party.get(root)
            if prior is None or (prior.lazy and not lazy):
                closure.third_party[root] = Hit(
                    module=root,
                    where=str(path.relative_to(REPO)),
                    lineno=node.lineno,
                    lazy=lazy,
                )


def _dist_for(module: str, mapping: dict[str, list[str]]) -> str | None:
    """顶层模块 → 发行版名。``packages_distributions`` 之外再兜一次同名尝试。"""

    names = mapping.get(module)
    if names:
        return sorted(names)[0]
    try:
        md.version(module)
    except md.PackageNotFoundError:
        return None
    return module


def _transitive(dists: set[str], include_extras: bool) -> dict[str, str]:
    """按已安装元数据展开传递依赖，返回 name → version。

    只展开**已安装**的依赖：未安装的说明当前运行环境并不需要它（可选依赖），
    强行锁进去会让锁文件描述一个从未被验证过的环境。
    """

    resolved: dict[str, str] = {}
    queue = list(dists)
    seen: set[str] = set()
    while queue:
        name = queue.pop()
        key = name.lower().replace("_", "-")
        if key in seen:
            continue
        seen.add(key)
        try:
            resolved[name] = md.version(name)
        except md.PackageNotFoundError:
            continue
        for req in md.requires(name) or []:
            if not include_extras and "extra ==" in req:
                continue
            matched = _REQ_NAME.match(req)
            if matched:
                queue.append(matched.group(1))
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__ and __doc__.splitlines()[0])
    parser.add_argument(
        "entries",
        nargs="*",
        default=["intelligence/api/app.py"],
        help="入口文件（仓内相对路径），默认消费侧 web 入口",
    )
    parser.add_argument("--include-extras", action="store_true")
    args = parser.parse_args()

    closure = Closure()
    for entry in args.entries:
        path = (REPO / entry).resolve()
        if not path.is_file():
            print(f"用不了：入口不存在 {path}", file=sys.stderr)
            return 2
        _walk(path, closure)

    mapping = md.packages_distributions()
    direct: dict[str, str] = {}
    unmapped: list[Hit] = []
    for module, hit in sorted(closure.third_party.items()):
        dist = _dist_for(module, mapping)
        if dist is None:
            unmapped.append(hit)
            continue
        direct[dist] = md.version(dist)

    print("=" * 72)
    print("依赖闭环 — 从入口 AST 递归，含函数体内的懒加载")
    print("=" * 72)
    print(f"  入口     {', '.join(args.entries)}")
    print(f"  解释器   {sys.executable}")
    print(f"  扫描     {len(closure.visited)} 个仓内模块\n")

    print(f"直接第三方 import（{len(closure.third_party)} 个顶层模块）：")
    for _, hit in sorted(closure.third_party.items()):
        print(f"  {hit.render()}")

    if unmapped:
        print(f"\n⚠ 映射不到已安装发行版（{len(unmapped)} 个）——可能未安装或名字不同：")
        for hit in unmapped:
            print(f"  {hit.render()}")

    full = _transitive(set(direct), args.include_extras)
    indirect = {k: v for k, v in full.items() if k not in direct}
    print(f"\n传递依赖（{len(indirect)} 个）：")
    print("  " + ", ".join(sorted(indirect)) or "  （无）")

    print(f"\n锁清单（{len(full)} 个，直接 {len(direct)} + 传递 {len(indirect)}）：")
    for name in sorted(full, key=str.lower):
        print(f"{name}=={full[name]}")

    if closure.unresolved:
        print(f"\n⚠ 仓内模块解析不到文件（{len(closure.unresolved)}）：")
        print("  " + ", ".join(sorted(closure.unresolved)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
